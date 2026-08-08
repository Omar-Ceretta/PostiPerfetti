# -*- coding: utf-8 -*-
"""Ponte Qt comune verso elaborazioni eseguite in processi Python separati.

La classe concentra il solo trasporto IPC: serializza una fotografia degli
input, avvia un processo con ``spawn`` e inoltra al thread GUI i messaggi del
protocollo specifico. I motori figli restano in moduli privi di import Qt.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import multiprocessing
import pickle
from multiprocessing.connection import Connection

from PySide6.QtCore import QThread

from moduli.supervisione_processi import finalizza_processo


class PonteProcessoQtBase(QThread):
    """Esegue il ciclo di vita IPC condiviso dai worker a processo."""

    def __init__(
        self,
        richiesta: dict,
        *,
        target_processo,
        nome_processo: str,
        descrizione: str,
        usa_evento_stop: bool = False,
    ):
        super().__init__()
        self._payload = pickle.dumps(
            richiesta,
            protocol=pickle.HIGHEST_PROTOCOL,
        )
        self._target_processo = target_processo
        self._nome_processo = nome_processo
        self._descrizione = descrizione
        self._usa_evento_stop = bool(usa_evento_stop)
        self._stop_richiesto = False
        self._evento_stop = None
        self._processo = None

    def richiedi_stop(self) -> None:
        """Propaga una richiesta cooperativa quando il motore la supporta."""
        if not self._usa_evento_stop:
            return
        self._stop_richiesto = True
        evento = self._evento_stop
        if evento is not None:
            evento.set()

    def _prima_di_avviare(self) -> None:
        """Hook eseguito nel QThread immediatamente prima dello spawn."""

    def _gestisci_messaggio(self, messaggio: dict) -> bool:
        """Traduce un messaggio IPC; True indica un esito terminale."""
        raise NotImplementedError

    def _emetti_errore_ponte(self, messaggio: str) -> None:
        """Pubblica un errore infrastrutturale col segnale del sottotipo."""
        self.error_occurred.emit(messaggio, None)

    def run(self) -> None:
        """Avvia il processo spawn e inoltra i suoi messaggi alla GUI."""
        contesto = multiprocessing.get_context("spawn")
        ricezione: Connection
        invio: Connection
        ricezione, invio = contesto.Pipe(duplex=False)

        evento_stop = None
        if self._usa_evento_stop:
            evento_stop = contesto.Event()
            self._evento_stop = evento_stop
            if self._stop_richiesto:
                evento_stop.set()

        argomenti = (
            (self._payload, invio, evento_stop)
            if self._usa_evento_stop
            else (self._payload, invio)
        )
        processo = contesto.Process(
            target=self._target_processo,
            args=argomenti,
            name=self._nome_processo,
            daemon=False,
        )
        self._processo = processo
        terminale_ricevuto = False
        canale_inutilizzabile = False

        try:
            self._prima_di_avviare()
            processo.start()
            invio.close()

            while True:
                if ricezione.poll(0.05):
                    try:
                        messaggio = ricezione.recv()
                    except EOFError:
                        canale_inutilizzabile = True
                        break
                    terminale_ricevuto = self._gestisci_messaggio(messaggio)
                    if terminale_ricevuto:
                        break
                    continue

                if not processo.is_alive():
                    break

            esito_chiusura = finalizza_processo(
                processo,
                terminale_ricevuto=terminale_ricevuto,
                canale_inutilizzabile=canale_inutilizzabile,
            )
            if esito_chiusura.ancora_vivo:
                raise RuntimeError(
                    f"il processo {self._descrizione} non si e' chiuso "
                    "dopo l'esito terminale"
                )

            if not terminale_ricevuto:
                dettaglio = (
                    "ha chiuso il canale IPC senza restituire un esito"
                    if canale_inutilizzabile
                    else "si e' chiuso senza restituire un esito"
                )
                self._emetti_errore_ponte(
                    f"Il processo {self._descrizione} {dettaglio} "
                    f"(codice {processo.exitcode})."
                )
        except Exception as errore:
            canale_inutilizzabile = True
            # Se il figlio e' ancora vivo ma il bridge non puo' piu' parlargli,
            # non avrebbe alcun modo di consegnare un risultato utile.
            try:
                finalizza_processo(
                    processo,
                    terminale_ricevuto=terminale_ricevuto,
                    canale_inutilizzabile=True,
                )
            except Exception:
                pass
            self._emetti_errore_ponte(
                f"Impossibile eseguire il processo {self._descrizione}: "
                f"{errore}"
            )
        finally:
            try:
                ricezione.close()
            except Exception:
                pass
            try:
                invio.close()
            except Exception:
                pass
            # Nessun join indefinito qui: la raccolta e l'eventuale terminazione
            # sono gia' responsabilita' di finalizza_processo().
            try:
                finalizza_processo(
                    processo,
                    terminale_ricevuto=terminale_ricevuto,
                    canale_inutilizzabile=canale_inutilizzabile,
                    tempo_grazia=0.0,
                )
            except Exception:
                pass
            self._processo = None
            self._evento_stop = None
