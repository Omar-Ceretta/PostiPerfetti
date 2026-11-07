# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Ponti Qt verso i processi di generazione annuale di «PostiPerfetti»."""

from __future__ import annotations

from PySide6.QtCore import Signal

from moduli.casualita import risolvi_seed_principale
from moduli.calcolo.motore_blocchi import NUM_CANDIDATI_BLOCCHI
from moduli.dominio.aula_personalizzata import richiedi_zone_aula_personalizzata_valide
from moduli.processi.ponte_processo import PonteProcessoQtBase


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

    def _emetti_annullamento(self) -> None:
        self.stagione_completata.emit({
            'mesi': [], 'chiavi': [], 'info': {'motivo_stop': 'annullato'}})

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
            if testo.startswith('Errore processo Annuale Q21:'):
                dettaglio = testo.partition(':')[2].strip()
                testo = ('Problema durante l’assegnazione annuale. '
                         f'Dettaglio: {dettaglio}')
            self.error_occurred.emit(testo, None)
            return True
        return False


class SeasonWorkerProcessBridgeQ21(_SeasonWorkerProcessBridgeBase):
    """Trasporto operativo Q21 per l’Annuale del Layout unico."""

    def __init__(self, fotografia, config_app, num_mesi, *,
                 num_candidati=NUM_CANDIDATI_BLOCCHI, seed_principale=None,
                 budget_totale=600, riserva=60):
        from moduli.processi.processo_q21_contesto import (
            prepara_richiesta_annuale_q21, esegui_annuale_q21_in_processo)
        # Blocca subito gli errori di capienza, prima della serializzazione
        # e prima di creare/avviare qualunque processo di calcolo.
        richiedi_zone_aula_personalizzata_valide(
            fotografia.layout.schema, fotografia.crea_studenti(),
        )
        seed = risolvi_seed_principale(seed_principale)
        richiesta = prepara_richiesta_annuale_q21(
            fotografia, config_app, numero_mesi=num_mesi,
            seed_principale=seed, num_candidati=num_candidati,
            budget_totale=budget_totale, riserva=riserva)
        super().__init__(
            richiesta, config_snapshot=None,
            target_processo=esegui_annuale_q21_in_processo,
            nome_processo='PostiPerfettiAnnualQ21Process')
        self.seed_principale = seed
        self.numero_stagioni_fisso = None
        # Diagnostica esplicita: registra i medesimi byte gia' consegnati a IPC.
        # Nessuna acquisizione di dati dell'utente nel normale funzionamento.
        from moduli.processi.cattura_q21_diagnostica import cattura_payload_se_richiesto
        cattura_payload_se_richiesto(self._payload)
