# -*- coding: utf-8 -*-
"""Coordinamento GUI dell’elaborazione Annuale.

La fase F6 concentra qui avvio, monitoraggio, annullamento, classificazione
dei risultati e apertura dell’anteprima annuale. I motori, i worker e il
salvataggio transazionale dei mesi restano nei rispettivi moduli.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import copy

from PySide6.QtCore import QTimer

from moduli.aula import ConfigurazioneAula
from moduli.annuale import (
    BUDGET_STAGIONI_SEC,
    formatta_durata,
    riordina_e_cattura_stagione_coppie,
)
from moduli.metrica_pulizia import punteggio_stagione
from moduli.lingua import quantita
from moduli.worker_annuale import (
    SeasonWorkerProcessBridge,
    SeasonWorkerProcessBridgeTerzetti,
)
from moduli.risultati_annuali import (
    EsitoRisultatoAnnuale,
    classifica_risultato_annuale,
)
from moduli.anteprima_annuale import AnteprimaStagioneDialog
from moduli.utilita import mostra_popup_semantico
from moduli.stato_sessione import risultato_appartiene_sessione


class FlussoAnnualeUIMixin:
    """Coordina l’Annuale senza possedere motori o persistenza."""

    def _on_stato_annuale(self, stato: dict):
        """Memorizza lo stato corrente comunicato dal worker annuale."""
        self.sessione.annuale.aggiorna_progresso(stato)

    def _avvia_monitoraggio_annuale(
            self, numero_mesi: int, numero_stagioni_fisso=None) -> None:
        """Inizializza stato, annullamento e timer comuni ai due modi."""
        self.sessione.annuale.avvia(
            numero_mesi,
            numero_stagioni_fisso=numero_stagioni_fisso,
        )
        self.btn_annulla_annuale.setEnabled(True)
        self.btn_annulla_annuale.show()
        self.label_status.setText("Elaborazione delle assegnazioni annuali…")

        if not hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale = QTimer(self)
            self.timer_eta_annuale.timeout.connect(
                self._aggiorna_eta_annuale
            )
        self.timer_eta_annuale.start(500)

    def _worker_annuale_finito(self) -> None:
        """Rilascia il QThread bridge soltanto dopo il segnale ``finished``."""
        worker = self.sender()
        if getattr(self, 'season_worker', None) is worker:
            self.season_worker = None

    def _rilascia_worker_annuale_se_inattivo(self) -> None:
        """Pulisce un bridge che non e' mai partito o e' gia' terminato."""
        worker = getattr(self, 'season_worker', None)
        if worker is None:
            return
        try:
            in_esecuzione = worker.isRunning()
        except Exception:
            in_esecuzione = False
        if not in_esecuzione:
            self.season_worker = None

    def _concludi_monitoraggio_annuale(self) -> None:
        """Ferma i soli elementi UI legati al calcolo annuale."""
        if hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale.stop()
        self.btn_annulla_annuale.hide()
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)

    def _aggiorna_eta_annuale(self):
        """Aggiorna periodicamente stato ed attesa massima dell'Annuale."""
        testo = self.sessione.annuale.testo_attesa(
            BUDGET_STAGIONI_SEC,
            formatta_durata,
        )
        if testo:
            self.label_status.setText(testo)

    def _annulla_annuale(self):
        """Richiede l'arresto cooperativo dell'elaborazione annuale."""
        worker = getattr(self, 'season_worker', None)
        if worker is None:
            return
        if self.sessione.annuale.richiedi_annullamento():
            self.btn_annulla_annuale.setEnabled(False)
            worker.richiedi_stop()

    def _fallimento_preparazione_annuale(self, messaggio: str) -> None:
        """Ripristina la GUI se il bridge Annuale non arriva nemmeno allo start."""
        self._contesto_annuale = None
        self.season_worker = None
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)
        self._mostra_errore("Errore Assegnazione", messaggio)

    def _avvia_annuale_coppie(self, modalita_trio, studente_fisso):
        """Avvia in background la generazione annuale a coppie."""
        num_mesi = self.spinbox_mesi.value()

        nome_classe_report = self.input_nome_classe.text() or "Classe"
        studenti_report = copy.deepcopy(self.sessione.studenti)
        genere_misto = self.checkbox_genere_misto.isChecked()
        studente_fisso_report = next(
            (
                studente
                for studente in studenti_report
                if getattr(studente, "nota_posizione", None) == "FISSO"
            ),
            None,
        )

        cattura_report = lambda asg, uc, uv, foto, vicini: self.costruisci_testo_report(
            asg, nome_classe_report, studenti_report,
            ultimo_uso_coppie=uc, ultimo_uso_vicino=uv,
            coppie_gia_usate_esplicite=foto,
            vicini_fisso_espliciti=vicini,
            consenti_fallback_gui=False,
        )[0]

        self._cattura_report_annuale_coppie = cattura_report
        self._contesto_annuale = {
            "file_origine": self.sessione.file_origine,
            "studenti_live": self.sessione.studenti,
            "aula_live": self.sessione.aula,
            "studenti_report": studenti_report,
            "nome_classe": nome_classe_report,
            "genere_misto": genere_misto,
            "studente_fisso": studente_fisso_report,
        }
        try:
            self.season_worker = SeasonWorkerProcessBridge(
                self.sessione.studenti,
                self.sessione.aula,
                self.config_app,
                num_mesi,
                modalita_trio,
                genere_misto,
                studente_fisso,
            )
        except Exception as errore:
            self._fallimento_preparazione_annuale(
                "Impossibile preparare il processo Annuale a coppie: "
                f"{errore}"
            )
            return

        self.season_worker.status_updated.connect(self.label_status.setText)

        self.season_worker.stagione_completata.connect(self._stagione_completata_coppie)

        self.season_worker.error_occurred.connect(self._elaborazione_fallita)

        self.season_worker.stato_annuale_updated.connect(
            self._on_stato_annuale
        )
        self.season_worker.finished.connect(self._worker_annuale_finito)
        self._avvia_monitoraggio_annuale(
            num_mesi,
            self.season_worker.numero_stagioni_fisso,
        )
        try:
            self.season_worker.start()
        except Exception as errore:
            self._elaborazione_fallita(
                "Impossibile avviare il processo Annuale a coppie: "
                f"{errore}",
                None,
            )

    def _avvia_annuale_terzetti(self, studente_fisso, ha_fisso):
        """Avvia in background la generazione annuale a terzetti."""

        num_studenti = len(self.sessione.studenti)
        posti_per_fila = int(self.input_posti_fila.text())
        terzetti_per_fila = posti_per_fila // 3
        if self.radio_resto_quartetti.isChecked():
            preferenza_resto2 = 'due_quartetti'
        else:
            preferenza_resto2 = 'coppia'
        if self.radio_trio_prima.isChecked():
            posizione_blocco_finale = 'prima'
        elif self.radio_trio_centro.isChecked():
            posizione_blocco_finale = 'centro'
        elif self.radio_trio_ultima.isChecked():
            posizione_blocco_finale = 'ultima'
        else:
            posizione_blocco_finale = 'ultima'

        num_mesi = self.spinbox_mesi.value()
        genere_misto = self.checkbox_genere_misto.isChecked()
        nome_classe_report = self.input_nome_classe.text() or "Classe"
        studenti_report = copy.deepcopy(self.sessione.studenti)
        studente_fisso_report = next(
            (
                studente
                for studente in studenti_report
                if getattr(studente, "nota_posizione", None) == "FISSO"
            ),
            None,
        )

        aula_capienza = ConfigurazioneAula(
            "Calcolo capienza annuale terzetti"
        )
        aula_capienza.crea_layout_terzetti(
            num_studenti,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            ha_fisso=ha_fisso,
            preferenza_resto2=preferenza_resto2,
        )
        capienza_prima = (
            aula_capienza.capienza_prima_fila_terzetti()
        )

        num_studenti_prima = sum(
            1
            for studente in self.sessione.studenti
            if studente.nota_posizione == 'PRIMA'
        )
        posti_prima_utilizzabili = max(
            0,
            capienza_prima['posti'] - (1 if ha_fisso else 0)
        )

        if num_studenti_prima > posti_prima_utilizzabili:
            verbo = "ha" if num_studenti_prima == 1 else "hanno"
            eccesso = num_studenti_prima - posti_prima_utilizzabili
            self._mostra_errore(
                "Posizione PRIMA impossibile",
                f"La prima fila offre "
                f"{quantita(posti_prima_utilizzabili, 'posto utilizzabile', 'posti utilizzabili')}, "
                f"ma {quantita(num_studenti_prima, 'studente', 'studenti')} "
                f"{verbo} posizione PRIMA.\n\n"
                f"{quantita(eccesso, 'Richiesta in eccesso', 'Richieste in eccesso')}.\n\n"
                "Apri «Editor studenti» e riduci le posizioni PRIMA, "
                "oppure aumenta i posti per fila."
            )
            return

        self._geometria_annuale_terzetti = {
            'terzetti_per_fila': terzetti_per_fila,
            'posizione_blocco_finale': posizione_blocco_finale,
            'ha_fisso': ha_fisso,
            'preferenza_resto2': preferenza_resto2,
            'max_terzetti_prima_fila': capienza_prima['terzetti'],
            'max_resti_prima_fila': capienza_prima['resti'],
        }

        self._imposta_modalita_elaborazione(True)


        self._contesto_annuale = {
            "file_origine": self.sessione.file_origine,
            "studenti_live": self.sessione.studenti,
            "aula_live": self.sessione.aula,
            "studenti_report": studenti_report,
            "nome_classe": nome_classe_report,
            "genere_misto": genere_misto,
            "studente_fisso": studente_fisso_report,
        }
        try:
            self.season_worker = SeasonWorkerProcessBridgeTerzetti(
                self.sessione.studenti,
                self.config_app,
                num_mesi,
                genere_misto,
                preferenza_resto2,
                0 in aula_capienza.file_blocchi_finali,
                max_terzetti_prima_fila=(
                    capienza_prima['terzetti']
                ),
                max_resti_prima_fila=(
                    capienza_prima['resti']
                ),
            )
        except Exception as errore:
            self._fallimento_preparazione_annuale(
                "Impossibile preparare il processo Annuale a terzetti: "
                f"{errore}"
            )
            return

        self.season_worker.status_updated.connect(self.label_status.setText)
        self.season_worker.stagione_completata.connect(
            self._stagione_completata_terzetti
        )
        self.season_worker.error_occurred.connect(self._elaborazione_fallita)
        self.season_worker.stato_annuale_updated.connect(self._on_stato_annuale)
        self.season_worker.finished.connect(self._worker_annuale_finito)

        self._avvia_monitoraggio_annuale(
            num_mesi,
            self.season_worker.numero_stagioni_fisso,
        )
        try:
            self.season_worker.start()
        except Exception as errore:
            self._elaborazione_fallita(
                "Impossibile avviare il processo Annuale a terzetti: "
                f"{errore}",
                None,
            )

    def _sessione_annuale_invariata(self) -> bool:
        """Verifica che il risultato appartenga ancora alla classe avviata."""
        contesto = getattr(self, "_contesto_annuale", None)
        if not contesto:
            return False
        return risultato_appartiene_sessione(
            file_origine_corrente=self.sessione.file_origine,
            studenti_correnti=self.sessione.studenti,
            aula_corrente=self.sessione.aula,
            file_origine_atteso=contesto["file_origine"],
            studenti_attesi=contesto["studenti_live"],
            aula_attesa=contesto["aula_live"],
        )

    def _scarta_annuale_se_sessione_cambiata(self) -> bool:
        """Scarta un esito tardivo senza applicarlo a una nuova sessione."""
        if self._sessione_annuale_invariata():
            return False
        self._concludi_monitoraggio_annuale()
        self.sessione.annuale.segna_fallita()
        self._contesto_annuale = None
        mostra_popup_semantico(
            self,
            "Risultato non applicato",
            "La classe è stata chiusa o sostituita durante il calcolo.",
            "triangle-alert",
            testo_informativo=(
                "Il risultato Annuale tardivo è stato scartato e nessun dato "
                "è stato salvato."
            ),
            messaggio_in_grassetto=True,
        )
        return True

    def _stagione_completata_terzetti(self, risultato: dict):
        """Delega al gestore comune il risultato annuale a terzetti."""
        if self._scarta_annuale_se_sessione_cambiata():
            return
        self._gestisci_risultato_annuale(risultato, modo='terzetti')

    def _gestisci_risultato_annuale(
            self, risultato: dict, *, modo: str) -> None:
        """Classifica il risultato, apre l'anteprima e aggiorna lo stato."""
        self._concludi_monitoraggio_annuale()
        contesto = getattr(self, "_contesto_annuale", None) or {}
        self._contesto_annuale = None
        ricevuto = classifica_risultato_annuale(risultato)

        if ricevuto.esito == EsitoRisultatoAnnuale.ANNULLATO:
            self.sessione.annuale.segna_annullata()
            mostra_popup_semantico(
                self,
                "Operazione annullata",
                "La preparazione annuale è stata annullata.",
                "info",
                testo_informativo=(
                    "Nulla è stato salvato: lo Storico è rimasto "
                    "esattamente com'era."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if ricevuto.esito == EsitoRisultatoAnnuale.VUOTO:
            self.sessione.annuale.segna_fallita()
            mostra_popup_semantico(
                self,
                "Nessuna assegnazione",
                "Non è stato preparato alcun mese.",
                "triangle-alert",
                testo_informativo="Nulla è stato salvato.",
                messaggio_in_grassetto=True,
            )
            return

        self.sessione.annuale.apri_anteprima()
        nome_classe = contesto.get("nome_classe", "Classe")
        opzioni_dialogo = {
            "genere_misto": bool(contesto.get("genere_misto", False)),
            "studenti": list(contesto.get("studenti_report") or []),
            "studente_fisso": contesto.get("studente_fisso"),
        }
        if modo == 'terzetti':
            geo = getattr(self, '_geometria_annuale_terzetti', {})
            opzioni_dialogo.update({
                'modo': 'terzetti',
                'terzetti_per_fila': geo.get('terzetti_per_fila'),
                'posizione_blocco_finale': geo.get(
                    'posizione_blocco_finale'
                ),
                'ha_fisso': geo.get('ha_fisso', False),
                'preferenza_resto2': geo.get(
                    'preferenza_resto2', 'coppia'
                ),
            })

        dialog = AnteprimaStagioneDialog(
            self,
            self.config_app,
            ricevuto.mesi,
            ricevuto.info,
            contesto.get("file_origine", self.sessione.file_origine),
            nome_classe,
            **opzioni_dialogo,
        )
        dialog.exec()

        if dialog.accettato:
            self.sessione.annuale.segna_salvata()
            self._aggiorna_info_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()
            self.tab_widget.setCurrentIndex(3)
        else:
            self.sessione.annuale.segna_scartata()

    def _gestisci_fallimento_annuale(self) -> bool:
        """Conclude lo stato Annuale fallito e segnala se era attivo."""
        if not self.sessione.annuale.in_corso:
            return False
        self.sessione.annuale.segna_fallita()
        self._contesto_annuale = None
        self._concludi_monitoraggio_annuale()
        self._rilascia_worker_annuale_se_inattivo()
        return True

    def _stagione_completata_coppie(self, risultato: dict):
        """Completa l'eventuale esito grezzo del processo e apre l'anteprima."""
        if self._scarta_annuale_se_sessione_cambiata():
            return
        info = risultato.get("info") or {}
        if info.pop("_risultato_grezzo_processo", False):
            try:
                worker = getattr(self, "season_worker", None)
                config_snapshot = getattr(worker, "config_snapshot", None)
                cattura_report = getattr(
                    self,
                    "_cattura_report_annuale_coppie",
                    None,
                )
                if config_snapshot is None or cattura_report is None:
                    raise RuntimeError(
                        "fotografia o callback del report Annuale non disponibile"
                    )

                mesi, chiavi = riordina_e_cattura_stagione_coppie(
                    risultato.get("mesi") or [],
                    config_snapshot,
                    cattura_report,
                    ordine_iniziale=info.get(
                        "ordine_stagione_preferito"
                    ),
                )
                info["punteggio"] = punteggio_stagione(chiavi)
                info["tot_ripetizioni"] = info["punteggio"][0]
                info["riordino_temporale"] = True
                risultato = {
                    "mesi": mesi,
                    "chiavi": chiavi,
                    "info": info,
                }
            except Exception as errore:
                self._elaborazione_fallita(
                    "Errore durante la finalizzazione dell'Annuale: "
                    f"{errore}",
                    None,
                )
                return

        self._gestisci_risultato_annuale(risultato, modo='coppie')
