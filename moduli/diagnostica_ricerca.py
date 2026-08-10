# -*- coding: utf-8 -*-
"""Diagnostica strutturata e opzionale del motore combinatorio.

Il modulo non decide nulla e non usa casualità. Quando nessuna istanza di
``DiagnosticaRicerca`` viene passata ai motori, il percorso produttivo non crea
record, firme o messaggi. Le firme usano identità persistenti degli studenti e
sono quindi confrontabili fra processi diversi.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock, get_ident
from time import perf_counter_ns
from typing import Any, Iterable, Mapping


_DIAGNOSTICA_CORRENTE: ContextVar["DiagnosticaRicerca | None"] = ContextVar(
    "postiperfetti_diagnostica_ricerca", default=None
)


def identita_stabile(valore: Any) -> Any:
    """Converte oggetti del motore in valori JSON stabili.

    Gli studenti vengono identificati tramite nome completo, mai tramite ``id``.
    Le collezioni non ordinate vengono ordinate sulla loro forma serializzata.
    """
    if hasattr(valore, "get_nome_completo"):
        return valore.get_nome_completo()
    if isinstance(valore, Mapping):
        return {
            str(chiave): identita_stabile(contenuto)
            for chiave, contenuto in sorted(
                valore.items(), key=lambda voce: str(voce[0])
            )
        }
    if isinstance(valore, (set, frozenset)):
        normalizzati = [identita_stabile(elemento) for elemento in valore]
        return sorted(
            normalizzati,
            key=lambda elemento: json.dumps(
                elemento, ensure_ascii=False, sort_keys=True
            ),
        )
    if isinstance(valore, (list, tuple)):
        return [identita_stabile(elemento) for elemento in valore]
    if isinstance(valore, (str, int, float, bool)) or valore is None:
        return valore
    return repr(valore)


def firma_stabile(*valori: Any) -> str:
    """Restituisce una firma SHA-256 della rappresentazione JSON stabile."""
    contenuto = identita_stabile(valori)
    serializzato = json.dumps(
        contenuto,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serializzato).hexdigest()


def firma_ordine_coppie(coppie: Iterable[tuple]) -> str:
    """Firma l'ordine visitato dal backtracking a coppie."""
    voci = []
    for studente_a, studente_b, info in coppie:
        voci.append((
            identita_stabile(studente_a),
            identita_stabile(studente_b),
            info.get("punteggio_totale"),
            info.get("valutazione"),
        ))
    return firma_stabile("ordine_coppie", voci)


def firma_indice_terzetti(indice: Mapping[int, list], studenti: Iterable[Any]) -> str:
    """Firma le liste ordinate dei terzetti senza dipendere dagli ``id`` Python."""
    per_id = {id(studente): studente for studente in studenti}
    voci = []
    for chiave_id, alternative in indice.items():
        ancora = per_id.get(chiave_id, f"id:{chiave_id}")
        lista = []
        for membri, punti in alternative:
            lista.append((tuple(identita_stabile(membro) for membro in membri), punti))
        voci.append((identita_stabile(ancora), lista))
    voci.sort(key=lambda voce: str(voce[0]))
    return firma_stabile("indice_terzetti", voci)


@dataclass(slots=True)
class TelemetriaRicerca:
    """Contatori locali di una singola invocazione di backtracking."""

    proprietario: "DiagnosticaRicerca"
    metadati: dict[str, Any]
    firma_ordine: str | None = None
    max_decisioni: int = 64
    inizio_ns: int = field(default_factory=perf_counter_ns)
    contatori: Counter = field(default_factory=Counter)
    profondita_massima: int = 0
    prime_decisioni: list[Any] = field(default_factory=list)
    _hash_percorso: Any = field(default_factory=sha256)
    _chiusa: bool = False

    def nodo(self, profondita: int) -> None:
        self.contatori["nodi"] += 1
        if profondita > self.profondita_massima:
            self.profondita_massima = profondita

    def incrementa(self, voce: str, quantita: int = 1) -> None:
        self.contatori[voce] += quantita

    def potatura(self, motivo: str) -> None:
        self.contatori["pruning_totali"] += 1
        self.contatori[f"pruning:{motivo}"] += 1

    def decisione(self, tipo: str, valore: Any, profondita: int) -> None:
        normalizzato = identita_stabile((tipo, valore, profondita))
        serializzato = json.dumps(
            normalizzato,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._hash_percorso.update(serializzato)
        self._hash_percorso.update(b"\n")
        self.contatori["decisioni"] += 1
        if len(self.prime_decisioni) < self.max_decisioni:
            self.prime_decisioni.append(normalizzato)

    def backtrack(self) -> None:
        self.contatori["backtrack"] += 1

    def finalizza(
        self,
        *,
        successo: bool,
        soluzione: Any = None,
        punteggio: int | float | None = None,
        tetto_nodi: bool = False,
        dati: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._chiusa:
            raise RuntimeError("Telemetria di ricerca già finalizzata")
        self._chiusa = True
        record = {
            **identita_stabile(self.metadati),
            "durata_ns": perf_counter_ns() - self.inizio_ns,
            "successo": bool(successo),
            "tetto_nodi": bool(tetto_nodi),
            "firma_ordine": self.firma_ordine,
            "firma_percorso": self._hash_percorso.hexdigest(),
            "firma_soluzione": (
                firma_stabile("soluzione", soluzione)
                if soluzione is not None
                else None
            ),
            "punteggio": punteggio,
            "profondita_massima": self.profondita_massima,
            "contatori": dict(sorted(self.contatori.items())),
            "prime_decisioni": self.prime_decisioni,
        }
        if dati:
            record["dati"] = identita_stabile(dict(dati))
        self.proprietario._registra_ricerca(record)
        return record


class DiagnosticaRicerca:
    """Raccoglitore thread-safe degli eventi di un esperimento."""

    def __init__(
        self,
        *,
        etichetta: str | None = None,
        raccogli_messaggi: bool = False,
        max_messaggi: int = 500,
        max_decisioni_per_ricerca: int = 64,
    ) -> None:
        self.etichetta = etichetta
        self.raccogli_messaggi = bool(raccogli_messaggi)
        self.max_messaggi = max(0, int(max_messaggi))
        self.max_decisioni_per_ricerca = max(0, int(max_decisioni_per_ricerca))
        self._inizio_ns = perf_counter_ns()
        self._lock = RLock()
        self._eventi: list[dict[str, Any]] = []
        self._ricerche: list[dict[str, Any]] = []
        self._messaggi: list[dict[str, Any]] = []

    @contextmanager
    def attiva(self):
        """Rende questa diagnostica disponibile ai messaggi del thread corrente."""
        token = _DIAGNOSTICA_CORRENTE.set(self)
        try:
            yield self
        finally:
            _DIAGNOSTICA_CORRENTE.reset(token)

    def evento(self, tipo: str, **dati: Any) -> dict[str, Any]:
        record = {
            "t_ns": perf_counter_ns() - self._inizio_ns,
            "thread": get_ident(),
            "tipo": tipo,
            "dati": identita_stabile(dati),
        }
        with self._lock:
            self._eventi.append(record)
        return record

    def nuova_ricerca(
        self,
        *,
        firma_ordine: str | None = None,
        **metadati: Any,
    ) -> TelemetriaRicerca:
        return TelemetriaRicerca(
            proprietario=self,
            metadati=dict(metadati),
            firma_ordine=firma_ordine,
            max_decisioni=self.max_decisioni_per_ricerca,
        )

    def _registra_ricerca(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._ricerche.append(record)

    def messaggio(self, *valori: Any, sep: str = " ", end: str = "\n", **_: Any) -> None:
        if not self.raccogli_messaggi or self.max_messaggi == 0:
            return
        testo = sep.join(str(valore) for valore in valori) + end
        record = {
            "t_ns": perf_counter_ns() - self._inizio_ns,
            "thread": get_ident(),
            "testo": testo,
        }
        with self._lock:
            if len(self._messaggi) < self.max_messaggi:
                self._messaggi.append(record)

    def esporta(self) -> dict[str, Any]:
        with self._lock:
            eventi = list(self._eventi)
            ricerche = list(self._ricerche)
            messaggi = list(self._messaggi)

        firme_ordine = [
            ricerca["firma_ordine"]
            for ricerca in ricerche
            if ricerca.get("firma_ordine")
        ]
        firme_percorso = [
            ricerca["firma_percorso"]
            for ricerca in ricerche
            if ricerca.get("firma_percorso")
        ]
        riepilogo = {
            "eventi": len(eventi),
            "ricerche": len(ricerche),
            "ordini_distinti": len(set(firme_ordine)),
            "percorsi_distinti": len(set(firme_percorso)),
            "nodi_totali": sum(
                ricerca.get("contatori", {}).get("nodi", 0)
                for ricerca in ricerche
            ),
            "backtrack_totali": sum(
                ricerca.get("contatori", {}).get("backtrack", 0)
                for ricerca in ricerche
            ),
            "pruning_totali": sum(
                ricerca.get("contatori", {}).get("pruning_totali", 0)
                for ricerca in ricerche
            ),
            "memo_hit_totali": sum(
                ricerca.get("contatori", {}).get("memo_hit", 0)
                for ricerca in ricerche
            ),
            "nodi_logici_risparmiati": sum(
                ricerca.get("contatori", {}).get(
                    "nodi_logici_risparmiati", 0
                )
                for ricerca in ricerche
            ),
        }
        return {
            "schema": 1,
            "etichetta": self.etichetta,
            "durata_ns": perf_counter_ns() - self._inizio_ns,
            "riepilogo": riepilogo,
            "eventi": eventi,
            "ricerche": ricerche,
            "messaggi": messaggi,
        }

    def salva_json(self, percorso: str | Path) -> Path:
        destinazione = Path(percorso)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        destinazione.write_text(
            json.dumps(self.esporta(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return destinazione


def messaggio_motore(*valori: Any, **opzioni: Any) -> None:
    """Sostituto strutturato di ``print`` nei moduli del motore.

    A diagnostica spenta ritorna immediatamente e non effettua I/O. Con una
    diagnostica attiva, conserva il testo soltanto se ``raccogli_messaggi`` è
    stato esplicitamente richiesto.
    """
    diagnostica = _DIAGNOSTICA_CORRENTE.get()
    if diagnostica is not None:
        diagnostica.messaggio(*valori, **opzioni)
