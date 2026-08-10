# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Ponti Qt verso i processi di generazione annuale di «PostiPerfetti»."""

from __future__ import annotations

from PySide6.QtCore import Signal

from moduli.casualita import (
    risolvi_numero_stagioni_riproduzione,
    risolvi_seed_principale,
)
from moduli.generazione import NUM_CANDIDATI
from moduli.ponte_processo import PonteProcessoQtBase
from moduli.processo_annuale import (
    esegui_annuale_coppie_in_processo,
    esegui_annuale_terzetti_in_processo,
)


class _SeasonWorkerProcessBridgeBase(PonteProcessoQtBase):
    """Traduce il protocollo Annuale nei segnali Qt usati dalla GUI."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    stagione_completata = Signal(object)
    error_occurred = Signal(str, object)
    stato_annuale_updated = Signal(object)

    def __init__(
        self,
        richiesta: dict,
        *,
        config_snapshot,
        target_processo,
        nome_processo: str,
    ):
        self.config_snapshot = config_snapshot
        super().__init__(
            richiesta,
            target_processo=target_processo,
            nome_processo=nome_processo,
            descrizione="Annuale",
            usa_evento_stop=True,
        )

    def _gestisci_messaggio(self, messaggio: dict) -> bool:
        tipo = messaggio.get("tipo")
        if tipo == "stato":
            self.stato_annuale_updated.emit(messaggio["stato"])
            return False
        if tipo == "risultato":
            self.stagione_completata.emit(messaggio["risultato"])
            return True
        if tipo == "errore":
            self.error_occurred.emit(
                messaggio.get("messaggio", "Errore Annuale."),
                messaggio.get("report"),
            )
            return True
        if tipo == "eccezione":
            testo = messaggio.get("messaggio", "Errore nel processo Annuale.")
            traccia = messaggio.get("traceback")
            if traccia:
                print(traccia)
            self.error_occurred.emit(testo, None)
            return True
        return False


class SeasonWorkerProcessBridge(_SeasonWorkerProcessBridgeBase):
    """Ponte Qt verso l'Annuale a coppie eseguito in un altro processo."""

    def __init__(
        self,
        studenti,
        configurazione_aula,
        config_app,
        num_mesi,
        modalita_trio="centro",
        flag_genere_misto=False,
        studente_fisso=None,
        num_candidati=NUM_CANDIDATI,
        seed_principale=None,
    ):
        config_snapshot = config_app.copia_temporanea()
        seed_principale = risolvi_seed_principale(seed_principale)
        numero_stagioni_fisso = risolvi_numero_stagioni_riproduzione()
        richiesta = {
            "studenti": studenti,
            "configurazione_aula": configurazione_aula,
            "config_app": config_snapshot,
            "num_mesi": num_mesi,
            "modalita_trio": modalita_trio,
            "flag_genere_misto": flag_genere_misto,
            "studente_fisso": studente_fisso,
            "num_candidati": num_candidati,
            "seed_principale": seed_principale,
            "numero_stagioni_fisso": numero_stagioni_fisso,
        }
        super().__init__(
            richiesta,
            config_snapshot=config_snapshot,
            target_processo=esegui_annuale_coppie_in_processo,
            nome_processo="PostiPerfettiAnnualProcess",
        )
        self.seed_principale = seed_principale
        self.numero_stagioni_fisso = numero_stagioni_fisso


class SeasonWorkerProcessBridgeTerzetti(_SeasonWorkerProcessBridgeBase):
    """Ponte Qt verso l'Annuale a terzetti eseguito in un altro processo."""

    def __init__(
        self,
        studenti,
        config_app,
        num_mesi,
        genere_misto,
        preferenza_resto2,
        resto_in_prima_fila,
        max_terzetti_prima_fila=None,
        max_resti_prima_fila=None,
        num_candidati=None,
        seed_principale=None,
    ):
        config_snapshot = config_app.copia_temporanea()
        seed_principale = risolvi_seed_principale(seed_principale)
        numero_stagioni_fisso = risolvi_numero_stagioni_riproduzione()
        richiesta = {
            "studenti": studenti,
            "config_app": config_snapshot,
            "num_mesi": num_mesi,
            "genere_misto": genere_misto,
            "preferenza_resto2": preferenza_resto2,
            "resto_in_prima_fila": resto_in_prima_fila,
            "max_terzetti_prima_fila": max_terzetti_prima_fila,
            "max_resti_prima_fila": max_resti_prima_fila,
            "num_candidati": num_candidati,
            "seed_principale": seed_principale,
            "numero_stagioni_fisso": numero_stagioni_fisso,
        }
        super().__init__(
            richiesta,
            config_snapshot=config_snapshot,
            target_processo=esegui_annuale_terzetti_in_processo,
            nome_processo="PostiPerfettiAnnualTerzettiProcess",
        )
        self.seed_principale = seed_principale
        self.numero_stagioni_fisso = numero_stagioni_fisso
