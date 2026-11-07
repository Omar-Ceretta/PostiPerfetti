# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Ponti Qt verso i processi mensili di «PostiPerfetti»."""

from __future__ import annotations

from PySide6.QtCore import Signal

from moduli.casualita import risolvi_seed_principale
from moduli.processi.ponte_processo import PonteProcessoQtBase
from moduli.calcolo.motore_blocchi import NUM_CANDIDATI_BLOCCHI
from moduli.dominio.aula_personalizzata import richiedi_zone_aula_personalizzata_valide


class MensileQ21ProcessBridge(PonteProcessoQtBase):
    """I2c: Mensile e Annuale condividono lo stesso processo/motore Q21."""

    status_updated = Signal(str)
    completed = Signal(object)
    error_occurred = Signal(str, object)

    def __init__(self, fotografia, config_app, *,
                 num_candidati=NUM_CANDIDATI_BLOCCHI, seed_principale=None,
                 budget_totale=600, riserva=60):
        from moduli.processi.processo_q21_contesto import (
            prepara_richiesta_annuale_q21, esegui_annuale_q21_in_processo)
        studenti = fotografia.crea_studenti()
        self.preflight_zone = richiedi_zone_aula_personalizzata_valide(
            fotografia.layout.schema, studenti)
        self.seed_principale = risolvi_seed_principale(seed_principale)
        richiesta = prepara_richiesta_annuale_q21(
            fotografia, config_app, numero_mesi=1,
            seed_principale=self.seed_principale, num_candidati=num_candidati,
            budget_totale=budget_totale, riserva=riserva)
        self._fotografia = richiesta['ingresso'].fotografia
        # La fotografia dei precedenti letta dal processo deve ritornare
        # immutata; altrimenti nessun Mensile viene promosso alla GUI.
        self._adiacenze_attese = {
            (a, b) for a, b, _volte in richiesta['ingresso'].frequenze_iniziali
        }
        super().__init__(
            richiesta, target_processo=esegui_annuale_q21_in_processo,
            nome_processo='PostiPerfettiMonthlyQ21Process',
            descrizione='Mensile Q21', usa_evento_stop=True)

    def _prima_di_avviare(self):
        self.status_updated.emit('Cerco la disposizione migliore...')

    def _gestisci_messaggio(self, messaggio: dict) -> bool:
        tipo = messaggio.get('tipo')
        if tipo == 'stato':
            stato = messaggio.get('stato') or {}
            migliore = stato.get('best')
            if type(migliore) is int and migliore >= 0:
                precedente = getattr(self, '_ultimo_migliore_q21_emesso', None)
                if precedente is None or migliore < precedente:
                    self._ultimo_migliore_q21_emesso = migliore
                    self.status_updated.emit(
                        f'Il migliore finora ripete {migliore} coppie')
            return False
        if tipo == 'risultato':
            try:
                from moduli.processi.contratto_mensile_q21 import estrai_mese_q21
                mese = estrai_mese_q21(
                    messaggio.get('risultato'), self._fotografia,
                    adiacenze_attese=getattr(self, '_adiacenze_attese', None))
            except (TypeError, ValueError, KeyError, AttributeError) as errore:
                self.error_occurred.emit(str(errore), None)
            else:
                if self._stop_richiesto:
                    self.error_occurred.emit(
                        'Operazione mensile annullata: nessun risultato applicato.', None)
                else:
                    self.completed.emit(mese)
            return True
        if tipo in ('errore', 'eccezione'):
            if messaggio.get('traceback'):
                print(messaggio['traceback'])
            testo = messaggio.get('messaggio', 'Errore nel Mensile Q21.')
            if 'Non è stata generata un\'Annuale completa.' in testo:
                testo = (
                    'Non è stato possibile completare una disposizione mensile '
                    'con i vincoli e il Layout attuali. Controlla anzitutto i '
                    'banchi contrassegnati DAVANTI e gli studenti con obbligo PRIMA. '
                    'La causa specifica non è ancora stata accertata.'
                )
            elif testo.startswith('Errore processo Annuale Q21:'):
                testo = 'Problema durante l’assegnazione mensile:' + testo.partition(':')[2]
            self.error_occurred.emit(
                testo, messaggio.get('report') if tipo == 'errore' else None)
            return True
        return False
