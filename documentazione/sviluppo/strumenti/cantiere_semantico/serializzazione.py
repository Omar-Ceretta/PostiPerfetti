"""Serializzazione JSON stabile e scrittura atomica degli output."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import Any, Mapping


def rendi_json_stabile(valore: Any) -> Any:
    """Converte un oggetto supportato in una struttura JSON deterministica.

    Le dataclass vengono attraversate campo per campo; Enum e Path diventano
    stringhe; mapping e insiemi vengono ordinati. Valori non rappresentabili o
    numeri non finiti vengono rifiutati invece di essere corretti silenziosamente.
    """
    if valore is None or isinstance(valore, (str, bool, int)):
        return valore
    if isinstance(valore, float):
        if not isfinite(valore):
            raise ValueError("Il JSON canonico non ammette NaN o infinito.")
        return valore
    if isinstance(valore, Enum):
        return rendi_json_stabile(valore.value)
    if isinstance(valore, (Path, date, datetime)):
        return valore.isoformat() if isinstance(valore, (date, datetime)) else os.fspath(valore)
    if is_dataclass(valore) and not isinstance(valore, type):
        return {
            campo.name: rendi_json_stabile(getattr(valore, campo.name))
            for campo in fields(valore)
        }
    if isinstance(valore, Mapping):
        risultato: dict[str, Any] = {}
        for chiave, contenuto in valore.items():
            chiave_testo = str(chiave)
            if chiave_testo in risultato:
                raise ValueError(
                    f"Collisione fra chiavi dopo la conversione a stringa: {chiave_testo!r}."
                )
            risultato[chiave_testo] = rendi_json_stabile(contenuto)
        return {chiave: risultato[chiave] for chiave in sorted(risultato)}
    if isinstance(valore, (list, tuple)):
        return [rendi_json_stabile(elemento) for elemento in valore]
    if isinstance(valore, (set, frozenset)):
        elementi = [rendi_json_stabile(elemento) for elemento in valore]
        return sorted(
            elementi,
            key=lambda elemento: json.dumps(
                elemento,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    raise TypeError(
        f"Tipo non serializzabile nel JSON canonico: {type(valore).__name__}."
    )


def _json_compatto_bytes(valore: Any) -> bytes:
    normalizzato = rendi_json_stabile(valore)
    testo = json.dumps(
        normalizzato,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return testo.encode("utf-8")


def serializza_json(valore: Any, *, indentazione: int = 2) -> str:
    """Restituisce JSON leggibile, stabile e terminato da newline."""
    if isinstance(indentazione, bool) or not isinstance(indentazione, int) or indentazione < 0:
        raise ValueError("indentazione deve essere un intero non negativo.")
    normalizzato = rendi_json_stabile(valore)
    return json.dumps(
        normalizzato,
        ensure_ascii=False,
        sort_keys=True,
        indent=indentazione,
        allow_nan=False,
    ) + "\n"


def firma_json_sha256(valore: Any) -> str:
    """Firma SHA-256 della rappresentazione JSON compatta e canonica."""
    return hashlib.sha256(_json_compatto_bytes(valore)).hexdigest()


def firma_file_sha256(percorso: str | os.PathLike[str]) -> str:
    """Firma SHA-256 di un file senza caricarlo interamente in memoria."""
    digest = hashlib.sha256()
    with open(percorso, "rb") as file:
        for blocco in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(blocco)
    return digest.hexdigest()


def leggi_json(percorso: str | os.PathLike[str]) -> Any:
    """Legge un file JSON UTF-8."""
    with open(percorso, "r", encoding="utf-8") as file:
        return json.load(file)


def scrivi_json_atomico(
    percorso: str | os.PathLike[str],
    valore: Any,
    *,
    indentazione: int = 2,
) -> str:
    """Scrive JSON mediante file temporaneo e sostituzione atomica.

    Restituisce la firma SHA-256 del contenuto canonico scritto.
    """
    destinazione = Path(percorso)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    testo = serializza_json(valore, indentazione=indentazione)

    descrittore, temporaneo = tempfile.mkstemp(
        prefix=f".{destinazione.name}.",
        suffix=".tmp",
        dir=destinazione.parent,
        text=True,
    )
    try:
        with os.fdopen(descrittore, "w", encoding="utf-8", newline="\n") as file:
            file.write(testo)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporaneo, destinazione)
        try:
            dir_fd = os.open(destinazione.parent, os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temporaneo)
        except FileNotFoundError:
            pass
        raise

    return firma_json_sha256(valore)


def scrivi_testo_atomico(
    percorso: str | os.PathLike[str],
    testo: str,
) -> str:
    """Scrive testo UTF-8 con newline finale e sostituzione atomica.

    Restituisce la firma SHA-256 dei byte effettivamente scritti.
    """
    if not isinstance(testo, str):
        raise TypeError("testo deve essere una stringa.")
    destinazione = Path(percorso)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    contenuto = testo if testo.endswith("\n") else testo + "\n"

    descrittore, temporaneo = tempfile.mkstemp(
        prefix=f".{destinazione.name}.",
        suffix=".tmp",
        dir=destinazione.parent,
        text=True,
    )
    try:
        with os.fdopen(descrittore, "w", encoding="utf-8", newline="\n") as file:
            file.write(contenuto)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporaneo, destinazione)
        try:
            dir_fd = os.open(destinazione.parent, os.O_RDONLY)
        except OSError:
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temporaneo)
        except FileNotFoundError:
            pass
        raise
    return firma_file_sha256(destinazione)
