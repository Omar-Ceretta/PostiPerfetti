# -*- coding: utf-8 -*-
"""
casualita.py — semi locali, riproducibili e derivati stabilmente.

Parte di «PostiPerfetti».

Questo modulo è l'unica infrastruttura condivisa per la casualità dei motori.
Non usa mai random.seed(): ogni ramo riceve un proprio random.Random(seed),
quindi una generazione non modifica lo stato casuale globale di Python.

Contratto:
  • ogni operazione (Mensile o Annuale) ha un seed principale a 64 bit;
  • se il chiamante non lo fornisce, viene letto POSTIPERFETTI_SEED;
  • se manca anche la variabile d'ambiente, nasce da secrets.randbits(64);
  • i seed figli si derivano con SHA-256 da componenti serializzate in JSON;
  • non si usa hash(), che cambia fra processi Python.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import secrets
from typing import Any

VARIABILE_SEED = "POSTIPERFETTI_SEED"
VARIABILE_STAGIONI = "POSTIPERFETTI_STAGIONI"
_MASCHERA_64_BIT = (1 << 64) - 1


def _normalizza_seed(seed: int | str) -> int:
    """Converte un seed esplicito in intero unsigned a 64 bit."""
    if isinstance(seed, bool):
        raise ValueError("Il seed non può essere un valore booleano.")

    if isinstance(seed, int):
        valore = seed
    else:
        testo = str(seed).strip()
        if not testo:
            raise ValueError("Il seed è vuoto.")
        try:
            # base=0 accetta sia decimale sia prefissi espliciti (0x..., 0o...).
            valore = int(testo, 0)
        except ValueError as errore:
            raise ValueError(
                f"Seed non valido: {seed!r}. Usa un numero intero."
            ) from errore

    return valore & _MASCHERA_64_BIT


def risolvi_seed_principale(seed: int | str | None = None) -> int:
    """
    Restituisce il seed principale effettivo dell'operazione.

    Precedenza:
      1) parametro esplicito;
      2) variabile d'ambiente POSTIPERFETTI_SEED;
      3) nuovo valore casuale crittograficamente forte a 64 bit.
    """
    if seed is not None:
        return _normalizza_seed(seed)

    seed_ambiente = os.environ.get(VARIABILE_SEED)
    if seed_ambiente is not None:
        return _normalizza_seed(seed_ambiente)

    return secrets.randbits(64)


def _rendi_json_stabile(valore: Any) -> Any:
    """Converte ricorsivamente un valore in una forma JSON stabile."""
    if valore is None or isinstance(valore, (str, int, float, bool)):
        return valore
    if isinstance(valore, dict):
        return {
            str(chiave): _rendi_json_stabile(valore[chiave])
            for chiave in sorted(valore, key=lambda elemento: str(elemento))
        }
    if isinstance(valore, (list, tuple)):
        return [_rendi_json_stabile(elemento) for elemento in valore]
    if isinstance(valore, (set, frozenset)):
        elementi = [_rendi_json_stabile(elemento) for elemento in valore]
        return sorted(
            elementi,
            key=lambda elemento: json.dumps(
                elemento,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return str(valore)


def risolvi_numero_stagioni_riproduzione(
        numero: int | str | None = None) -> int | None:
    """
    Restituisce l'eventuale numero FISSO di stagioni da rigenerare.

    È una modalità avanzata, usata soltanto per riprodurre esattamente un
    Annuale già eseguito: il normale stop a tempo può dipendere dalla velocità
    della macchina. Precedenza: parametro esplicito, poi variabile d'ambiente
    POSTIPERFETTI_STAGIONI. Se entrambi mancano, ritorna None e il comportamento
    normale (budget/tetto/convergenza) resta invariato.
    """
    valore = numero
    if valore is None:
        valore = os.environ.get(VARIABILE_STAGIONI)
    if valore is None:
        return None

    if isinstance(valore, bool):
        raise ValueError("Il numero di stagioni non può essere booleano.")
    try:
        numero_intero = int(str(valore).strip(), 10)
    except ValueError as errore:
        raise ValueError(
            f"Numero di stagioni non valido: {valore!r}. Usa un intero positivo."
        ) from errore
    if numero_intero < 1:
        raise ValueError("Il numero di stagioni deve essere almeno 1.")
    return numero_intero


def deriva_seed(seed_principale: int | str, *componenti: Any) -> int:
    """
    Deriva un seed figlio stabile a 64 bit dal seed principale e dal contesto.

    La stessa sequenza di componenti produce lo stesso valore in processi e
    piattaforme differenti. L'ordine delle componenti è significativo.
    """
    payload = {
        "seed_principale": _normalizza_seed(seed_principale),
        "componenti": [_rendi_json_stabile(c) for c in componenti],
    }
    serializzato = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(serializzato).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def crea_generatore(seed: int | str) -> random.Random:
    """Crea un generatore locale senza toccare random globale."""
    return random.Random(_normalizza_seed(seed))
