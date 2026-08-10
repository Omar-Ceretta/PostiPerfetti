# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Ponti Qt verso i processi mensili di «PostiPerfetti»."""

from __future__ import annotations

from PySide6.QtCore import Signal

from moduli.casualita import risolvi_seed_principale
from moduli.ponte_processo import PonteProcessoQtBase
from moduli.processo_mensile import esegui_mensile_terzetti_in_processo


class MensileTerzettiProcessBridge(PonteProcessoQtBase):
    """Ponte Qt verso il Mensile a terzetti eseguito in un altro processo."""

    status_updated = Signal(str)
    completed = Signal(object)
    error_occurred = Signal(str, object)

    def __init__(
        self,
        studenti,
        config_app,
        genere_misto,
        preferenza_resto2,
        resto_in_prima_fila,
        max_terzetti_prima_fila,
        max_resti_prima_fila,
        num_candidati,
        seed_principale=None,
    ):
        self.config_snapshot = config_app.copia_temporanea()
        self.seed_principale = risolvi_seed_principale(seed_principale)
        richiesta = {
            "studenti": studenti,
            "config_app": self.config_snapshot,
            "genere_misto": genere_misto,
            "preferenza_resto2": preferenza_resto2,
            "resto_in_prima_fila": resto_in_prima_fila,
            "max_terzetti_prima_fila": max_terzetti_prima_fila,
            "max_resti_prima_fila": max_resti_prima_fila,
            "num_candidati": num_candidati,
            "seed_principale": self.seed_principale,
        }
        super().__init__(
            richiesta,
            target_processo=esegui_mensile_terzetti_in_processo,
            nome_processo="PostiPerfettiMonthlyTerzettiProcess",
            descrizione="Mensile a terzetti",
        )

    def _prima_di_avviare(self) -> None:
        self.status_updated.emit("Cerco la disposizione migliore...")

    def _gestisci_messaggio(self, messaggio: dict) -> bool:
        tipo = messaggio.get("tipo")
        if tipo == "risultato":
            self.completed.emit(messaggio["risultato"])
            return True
        if tipo == "eccezione":
            traccia = messaggio.get("traceback")
            if traccia:
                print(traccia)
            self.error_occurred.emit(
                messaggio.get(
                    "messaggio",
                    "Errore nel processo Mensile a terzetti.",
                ),
                None,
            )
            return True
        return False
