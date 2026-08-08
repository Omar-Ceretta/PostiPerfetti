# -*- coding: utf-8 -*-
"""Profilazione diagnostica leggera delle operazioni sincrone della GUI.

Attiva soltanto con POSTIPERFETTI_GUI_PROFILE=1. Non modifica dati, seed,
opzioni o risultati: misura con perf_counter e scrive al termine dell'operazione.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar

from moduli.percorsi import get_log_path

_T = TypeVar("_T")
_TRUE = {"1", "true", "yes", "on", "si", "sì"}


def _attivo() -> bool:
    return os.environ.get("POSTIPERFETTI_GUI_PROFILE", "").strip().lower() in _TRUE


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class ProfiloGUI:
    """Accumula tempi di fase e li scrive con un'unica I/O finale."""

    def __init__(self, operazione: str):
        self.attivo = _attivo()
        self.operazione = operazione
        self.run = os.environ.get(
            "POSTIPERFETTI_GUI_WATCHDOG_RUN", "run"
        ).strip() or "run"
        self._inizio = time.perf_counter()
        self._fasi: list[dict[str, float | str]] = []

    def misura(self, nome: str, funzione: Callable[[], _T]) -> _T:
        """Esegue una funzione e registra la sua durata anche se solleva."""
        if not self.attivo:
            return funzione()
        inizio = time.perf_counter()
        try:
            return funzione()
        finally:
            fine = time.perf_counter()
            self._fasi.append({
                "fase": nome,
                "durata_ms": round((fine - inizio) * 1000.0, 3),
            })

    def chiudi(self) -> None:
        """Registra un riepilogo JSONL e una riga leggibile."""
        if not self.attivo:
            return
        totale_ms = round((time.perf_counter() - self._inizio) * 1000.0, 3)
        record = {
            "timestamp": _timestamp(),
            "run": self.run,
            "operazione": self.operazione,
            "totale_ms": totale_ms,
            "fasi": self._fasi,
        }
        json_path = Path(get_log_path(
            f"profilo-gui-{self.run}.jsonl", crea_genitori=True
        ))
        txt_path = Path(get_log_path(
            f"profilo-gui-{self.run}.log", crea_genitori=True
        ))
        with json_path.open("a", encoding="utf-8") as file_json:
            file_json.write(json.dumps(record, ensure_ascii=False) + "\n")
        parti = " | ".join(
            f"{fase['fase']}={fase['durata_ms']:.3f}ms" for fase in self._fasi
        )
        with txt_path.open("a", encoding="utf-8") as file_txt:
            file_txt.write(
                f"{record['timestamp']} | {self.operazione} | "
                f"totale={totale_ms:.3f}ms | {parti}\n"
            )
