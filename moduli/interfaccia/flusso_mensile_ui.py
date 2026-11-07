# -*- coding: utf-8 -*-
"""Avvio, calcolo e diagnostica delle assegnazioni correnti.

Mensile e Annuale partono dalla fotografia del Layout unico e usano Q21.
Il salvataggio nello Storico resta nel mixin dedicato.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from copy import deepcopy
from html import escape

from PySide6.QtWidgets import QGridLayout, QMessageBox, QDialogButtonBox
from PySide6.QtCore import Qt

from moduli.dominio.stato_sessione import calcola_abilitazione_controlli, puo_avviare_elaborazione
from moduli.lingua import quantita
from moduli.casualita import risolvi_seed_principale
from moduli.processi.worker_mensile import MensileQ21ProcessBridge
from moduli.persistenza.risultati_annuali import (
    data_creazione_corrente as _data_creazione_corrente,
    nome_assegnazione_automatico as _nome_assegnazione_automatico,
    prossimo_progressivo_storico as _prossimo_progressivo_storico,
)
from moduli.dominio.presentazione_aula_personalizzata import costruisci_configurazione_aula_personalizzata
from moduli.interfaccia.widget_statistiche import crea_widget_righe_statistiche
from moduli.interfaccia.utilita import (
    applica_icona,
    applica_stile_pulsante_popup,
    mostra_popup_con_dettagli_persistente,
    crea_popup_semantico,
    mostra_popup_semantico,
)
from moduli.interfaccia.statistiche_generali import (
    applica_formattazione_statistiche_generali,
)
from moduli.interfaccia.esportazione import evidenzia_riutilizzi
from moduli.processi.diagnostica_personalizzata import (
    costruisci_report_diagnostico_personalizzata,
)
from moduli.processi.diagnostica_fallimento_layout import analizza_fallimento_layout


def _aggiungi_widget_popup(msg_box, widget) -> None:
    """Inserisce un widget prima della barra dei pulsanti del QMessageBox."""
    layout = msg_box.layout()
    if isinstance(layout, QGridLayout):
        barra_pulsanti = msg_box.findChild(QDialogButtonBox)
        if barra_pulsanti is not None:
            indice = layout.indexOf(barra_pulsanti)
            if indice >= 0:
                riga, colonna, righe, colonne = layout.getItemPosition(indice)
                layout.removeWidget(barra_pulsanti)
                layout.addWidget(
                    widget, riga, 0, 1, max(1, layout.columnCount())
                )
                layout.addWidget(
                    barra_pulsanti, riga + 1, colonna, righe, colonne
                )
                return

        layout.addWidget(
            widget, layout.rowCount(), 0, 1, max(1, layout.columnCount())
        )
        return

    layout.addWidget(widget)


class FlussoMensileUIMixin:
    """Coordina avvio, completamento e fallimento delle assegnazioni."""


    def _esegui_assegnazione_personalizzata(self) -> None:
            """I2c: avvia il Mensile usando la stessa pipeline Q21 dell'Annuale."""
            from moduli.dominio.aula_personalizzata import (
                PostiDavantiInsufficienti,
                richiedi_zone_aula_personalizzata_valide,
            )

            schema = self.sessione.schema_personalizzato
            if schema is None:
                self._mostra_errore(
                    "Layout incompleto",
                    "Completa e valida il Layout prima di avviare "
                    "l'assegnazione."
                )
                return
            if self.radio_annuale.isChecked():
                self._avvia_annuale_personalizzata()
                return

            genere_misto = self.checkbox_genere_misto.isChecked()
            seed_principale = risolvi_seed_principale(None)
            nome_classe = self.input_nome_classe.text() or "Classe"
            try:
                fotografia = self._fotografa_generazione_layout()
                schema = fotografia.layout.schema
                layout_visuale = fotografia.layout.istantanea_visuale
                zone = richiedi_zone_aula_personalizzata_valide(
                    schema, fotografia.crea_studenti(),
                )
                if not self._conferma_preferenza_ultima(zone):
                    return
                worker = MensileQ21ProcessBridge(
                    fotografia, self.config_app,
                    seed_principale=seed_principale,
                )
            except PostiDavantiInsufficienti as errore:
                self._mostra_errore('Posti DAVANTI insufficienti', str(errore))
                return
            except Exception as errore:
                self._elaborazione_personalizzata_processo_fallita(
                    "Impossibile preparare il processo Mensile: "
                    f"{errore}",
                    None,
                )
                return

            self.worker_thread = worker
            self._contesto_mensile_personalizzata_processo = {
                "worker": worker,
                "fotografia_generazione": fotografia,
                "file_origine": self.sessione.file_origine,
                "studenti_live": self.sessione.studenti,
                "schema_live": schema,
                "schema_identita": schema.identita_semantica(),
                "layout_visuale": layout_visuale,
                "nome_classe": nome_classe,
                "genere_misto": genere_misto,
                "seed_principale": seed_principale,
            }

            print(
                "🎲 Operazione mensile — seed principale: "
                f"{seed_principale}"
            )
            self.indice_messaggio = 0
            self.timer_messaggi.start(2000)
            self._imposta_modalita_elaborazione(True)
            if hasattr(self, 'btn_annulla_mensile'):
                self.btn_annulla_mensile.setEnabled(True)
                self.btn_annulla_mensile.show()

            worker.status_updated.connect(self._stato_mensile_personalizzata)
            worker.completed.connect(
                self._elaborazione_personalizzata_processo_completata
            )
            worker.error_occurred.connect(
                self._errore_mensile_personalizzata
            )
            worker.finished.connect(self._worker_mensile_finito)
            try:
                worker.start()
            except Exception as errore:
                self._elaborazione_personalizzata_processo_fallita(
                    "Impossibile avviare il processo Mensile: "
                    f"{errore}",
                    None,
                )

    def _stato_mensile_personalizzata(self, testo: str) -> None:
            contesto = getattr(self, "_contesto_mensile_personalizzata_processo", None)
            if not self._segnale_generazione_corrente(contesto, "worker_thread"):
                return
            # La telemetria dei riusi resta nel processo a fini diagnostici,
            # ma non viene mostrata durante la generazione: la valutazione
            # completa e affidabile compare nell’anteprima.
            if testo.startswith("Il migliore finora ripete "):
                return
            if contesto.get('annullamento_richiesto'):
                return
            self.label_status.setText(testo)

    def _errore_mensile_personalizzata(self, messaggio, report=None) -> None:
            contesto = getattr(self, "_contesto_mensile_personalizzata_processo", None)
            if not self._segnale_generazione_corrente(contesto, 'worker_thread'):
                return
            if contesto.get('annullamento_richiesto'):
                self._concludi_mensile_personalizzata_processo()
                self._contesto_mensile_personalizzata_processo = None
                self.label_status.setText('Elaborazione mensile annullata.')
                return
            # Soltanto per il fallimento combinatorio Q21: gli errori di I/O,
            # di contratto o infrastrutturali devono conservare il loro testo.
            fallimento_ricerca = (
                isinstance(messaggio, str)
                and messaggio.startswith((
                    'Non è stato possibile completare una disposizione mensile',
                    'Budget totale contestuale esaurito.',
                    'Preparazione oltre la riserva.',
                ))
            )
            if report is None and fallimento_ricerca:
                try:
                    report = analizza_fallimento_layout(
                        contesto['fotografia_generazione'])
                    report['tempo_esaurito'] = messaggio.startswith((
                        'Budget totale contestuale esaurito.',
                        'Preparazione oltre la riserva.',
                    ))
                except Exception:
                    # Il diagnostico non deve mai mascherare l'errore originale.
                    report = None
            self._elaborazione_personalizzata_processo_fallita(messaggio, report)

    def _annulla_mensile(self) -> None:
            # Arresta Q21; ignora i risultati tardivi.
            contesto = getattr(self, '_contesto_mensile_personalizzata_processo', None)
            worker = getattr(self, 'worker_thread', None)
            if (not contesto or contesto.get('worker') is not worker
                    or contesto.get('annullamento_richiesto')):
                return
            contesto['annullamento_richiesto'] = True
            self.btn_annulla_mensile.setEnabled(False)
            self.label_status.setText('Interruzione del Mensile in corso…')
            worker.richiedi_stop()

    def _concludi_mensile_personalizzata_processo(self) -> None:
            """Ripristina la GUI dopo l'esito del processo Personalizzato."""
            self.timer_messaggi.stop()
            if hasattr(self, 'btn_annulla_mensile'):
                self.btn_annulla_mensile.hide()
            self._imposta_modalita_elaborazione(False)
            if hasattr(self, "_aggiorna_disponibilita_avvio_geometria"):
                self._aggiorna_disponibilita_avvio_geometria()

    @staticmethod
    def _testo_tecnico_personalizzata_p31(
            risultato: dict, *, genere_misto: bool) -> str:
            """P3.1a: diagnostica leggibile ricavata dalle collocazioni reali."""
            return costruisci_report_diagnostico_personalizzata(
                risultato,
                genere_misto_attivo=genere_misto,
            )

    def _elaborazione_personalizzata_processo_completata(
            self, risultato: dict) -> None:
            """Riceve e valida il risultato strutturato del Mensile P3.1."""
            contesto = getattr(
                self,
                "_contesto_mensile_personalizzata_processo",
                None,
            )
            if not self._segnale_generazione_corrente(contesto, "worker_thread"):
                return
            if contesto.get('annullamento_richiesto'):
                self._concludi_mensile_personalizzata_processo()
                self._contesto_mensile_personalizzata_processo = None
                self.label_status.setText('Elaborazione mensile annullata.')
                return
            self._concludi_mensile_personalizzata_processo()
            self._contesto_mensile_personalizzata_processo = None

            stessa_sessione = self._generazione_layout_invariata(contesto)
            if not stessa_sessione:
                self._mostra_errore(
                    "Risultato non applicato",
                    "La classe, i vincoli, il Layout o le opzioni sono cambiati "
                    "durante il calcolo.\n\nIl risultato tardivo è stato scartato."
                )
                return

            if risultato.get("schema_identita") != contesto["schema_identita"]:
                self._mostra_errore(
                    "Risultato non applicato",
                    "Lo schema restituito dal processo non coincide con la "
                    "fotografia usata per avviare il calcolo."
                )
                return

            # La GUI possiede una copia del risultato ricevuto.
            risultato = deepcopy(risultato)
            gruppi = risultato.get("gruppi")
            if gruppi is None:
                metadati = risultato.get("metadati_casualita") or {}
                report = metadati.get("report_fallimento")
                if report:
                    self._mostra_popup_fallimento_dettagliato(report)
                else:
                    self._mostra_errore(
                        "Nessuna disposizione valida",
                        "Il motore non ha trovato una disposizione "
                        "valida per lo schema corrente."
                    )
                return

            collocazioni = risultato.get("collocazioni")
            if not collocazioni or len(collocazioni) != len(gruppi):
                self._mostra_errore(
                    "Risultato incompleto",
                    "Il processo ha restituito gruppi senza una collocazione "
                    "fisica completa. Il risultato è stato scartato."
                )
                return

            layout_visuale = contesto["layout_visuale"]
            try:
                contesto["fotografia_generazione"].verifica_risultato(risultato)
                configurazione = costruisci_configurazione_aula_personalizzata(
                    layout_visuale, collocazioni,
                )
                data_creazione = _data_creazione_corrente()
                numero = _prossimo_progressivo_storico(
                    self.config_app, contesto["file_origine"],
                    "mensile", "personalizzata",
                )
                nome_assegnazione = _nome_assegnazione_automatico(
                    contesto["nome_classe"], "mensile", "personalizzata", numero,
                )
                report = self.prepara_report_personalizzata(
                    gruppi, collocazioni,
                    nome_classe=contesto["nome_classe"],
                    studenti=contesto["fotografia_generazione"].crea_studenti(),
                    configurazione_aula=configurazione,
                    genere_misto=contesto["genere_misto"],
                    nome_assegnazione=nome_assegnazione,
                    data_creazione=data_creazione,
                    # La stessa fotografia storica usata da Q21, anche se vuota.
                    adiacenze_gia_usate=set(risultato["adiacenze_prima"]),
                )
            except Exception as errore:
                self._mostra_errore(
                    "Risultato non applicato",
                    "Non è stato possibile preparare una disposizione completa "
                    "e verificata. Il risultato è stato scartato:\n\n"
                    f"{errore}"
                )
                return

            # Pubblica soltanto dopo aver preparato anche il Report.
            risultato.update(
                layout_visuale=layout_visuale,
                fotografia_generazione=contesto["fotografia_generazione"],
                nome_assegnazione=nome_assegnazione, progressivo=numero,
                data_creazione=data_creazione, report_completo=report.testo,
                configurazione_aula=configurazione,
                statistiche_generali=[dict(riga) for riga in report.statistiche],
            )
            self._configurazione_aula_personalizzata_corrente = configurazione
            self._aggiorna_visualizzazione_aula(configurazione)
            self._adotta_riepilogo_report_personalizzata(report)
            self.text_report.setPlainText(report.testo)
            evidenzia_riutilizzi(self.text_report)
            applica_formattazione_statistiche_generali(
                self.text_report, risultato["statistiche_generali"],
            )
            self._risultato_mensile_personalizzata_p31 = risultato
            self.sessione.mensile.prepara_personalizzata(
                risultato,
                nome=nome_assegnazione,
                progressivo=numero,
                data_creazione=data_creazione,
                file_origine=contesto["file_origine"],
                nome_classe=contesto["nome_classe"],
                genere_misto=contesto["genere_misto"],
            )
            self.widget_hint_report.setVisible(True)
            self.tab_widget.setCurrentWidget(self.tab_aula)
            if hasattr(self, "btn_prova_dragdrop"):
                self.btn_prova_dragdrop.setEnabled(True)
                self._aggiorna_testo_bottone_modifica_posti()
            self.btn_salva_progetto.setEnabled(True)
            self.btn_salva_progetto.setToolTip(
                "Salva questa disposizione nello Storico."
            )
            self.btn_export_excel.setEnabled(False)
            self.btn_export_report_txt.setEnabled(False)

            # Lo stesso riepilogo del Mensile originale: statistiche generali
            # effettivamente calcolate dal Report e nessuna modalità fittizia.
            popup = crea_popup_semantico(
                self, "Assegnazione completata", "", "circle-check"
            )
            popup.setTextFormat(Qt.RichText)
            popup.setText(
                "<b>Assegnazione completata con successo.</b><br><br>"
                "<b>Statistiche generali</b>"
            )
            popup.addButton(QMessageBox.Ok)
            _aggiungi_widget_popup(
                popup,
                crea_widget_righe_statistiche(
                    getattr(self, "_statistiche_generali_personalizzata_correnti", [])
                ),
            )
            popup.exec()

    def _elaborazione_personalizzata_processo_fallita(
            self, messaggio_errore: str, report: dict | None = None) -> None:
            """Ripristina la GUI dopo un errore IPC o di calcolo Personalizzato."""
            self._concludi_mensile_personalizzata_processo()
            self._contesto_mensile_personalizzata_processo = None
            self._risultato_mensile_personalizzata_p31 = None
            self._elaborazione_fallita(messaggio_errore, report)


    def _worker_mensile_finito(self) -> None:
            """Rilascia l'ownership Qt soltanto dopo il vero ``finished``."""
            worker = self.sender()
            if getattr(self, 'worker_thread', None) is worker:
                self.worker_thread = None

    def _rilascia_worker_mensile_se_inattivo(self) -> None:
            """Pulisce un worker che non e' mai partito o e' gia' terminato."""
            worker = getattr(self, 'worker_thread', None)
            if worker is None:
                return
            try:
                in_esecuzione = worker.isRunning()
            except Exception:
                in_esecuzione = False
            if not in_esecuzione:
                self.worker_thread = None


    def avvia_assegnazione(self):
            """Valida le scelte e avvia il flusso mensile o annuale richiesto."""

            if not puo_avviare_elaborazione(
                worker_mensile_presente=getattr(self, "worker_thread", None) is not None,
                worker_annuale_presente=getattr(self, "season_worker", None) is not None,
                annuale_in_corso=self.sessione.annuale.in_corso,
            ):
                mostra_popup_semantico(
                    self,
                    "Elaborazione già in corso",
                    "È già attivo un calcolo Mensile o Annuale.",
                    "info",
                    testo_informativo=(
                        "Attendi la conclusione dell'elaborazione corrente prima "
                        "di avviarne un'altra."
                    ),
                    messaggio_in_grassetto=True,
                )
                return

            if not self.sessione.studenti:
                self._mostra_errore("Nessun dato", "Carica prima un file con gli studenti.")
                return

            if self.sessione.geometria != 'personalizzata':
                self._mostra_errore(
                    "Layout non disponibile",
                    "La generazione richiede il Layout della classe. "
                    "Completa e valida la scheda «Layout»."
                )
                return

            if hasattr(self, 'editor_studenti') and self.editor_studenti.ha_studenti_caricati():
                vincoli_incompleti = self.editor_studenti.get_vincoli_incompleti()
                if vincoli_incompleti:
                    elenco = "\n".join(vincoli_incompleti)
                    mostra_popup_semantico(
                        self,
                        "Vincoli incompleti nell'Editor",
                        "Alcuni vincoli non hanno il livello impostato.",
                        "triangle-alert",
                        testo_informativo=(
                            f"{elenco}\n\n"
                            "Questi vincoli verrebbero ignorati dall'assegnazione.\n\n"
                            "Torna nell'Editor e, per ogni vincolo, seleziona il "
                            "livello di intensità oppure rimuovilo. Poi clicca "
                            "«SALVA e CARICA» prima di assegnare."
                        ),
                        messaggio_in_grassetto=True,
                    )
                    self.tab_widget.setCurrentWidget(self.editor_studenti)
                    return

            if hasattr(self, 'editor_studenti') and self.editor_studenti.ha_modifiche_non_salvate:
                mostra_popup_semantico(
                    self,
                    "Modifiche non salvate nell'Editor",
                    "Le modifiche dell'Editor non sono state salvate.",
                    "triangle-alert",
                    testo_informativo=(
                        "L'assegnazione utilizzerebbe i dati dell'ultimo salvataggio, "
                        "ignorando le modifiche recenti.\n\n"
                        "Torna nell'Editor e clicca «SALVA e CARICA» per aggiornare "
                        "i dati prima di procedere."
                    ),
                    messaggio_in_grassetto=True,
                )

                self.tab_widget.setCurrentWidget(self.editor_studenti)
                return

            if self.sessione.mensile.non_salvata:
                dialog_avvia = crea_popup_semantico(
                    self,
                    "Assegnazione non salvata",
                    "L'assegnazione corrente non è stata salvata nello Storico.",
                    "triangle-alert",
                    testo_informativo=(
                        "Se scegli di proseguire, verrà scartata definitivamente: "
                        "le schede Disposizione e Report saranno svuotate e non sarà più "
                        "possibile salvarla o includerla nelle rotazioni future.\n\n"
                        "Che cosa vuoi fare?"
                    ),
                    messaggio_in_grassetto=True,
                )

                btn_salva_avvia = dialog_avvia.addButton(
                    "Salva assegnazione", QMessageBox.AcceptRole
                )
                btn_prosegui_avvia = dialog_avvia.addButton(
                    "Scarta e prosegui", QMessageBox.DestructiveRole
                )
                btn_annulla_avvia = dialog_avvia.addButton(
                    "Annulla", QMessageBox.RejectRole
                )
                applica_icona(btn_salva_avvia, "save", 18)
                applica_icona(btn_prosegui_avvia, "trash-2", 18)
                applica_stile_pulsante_popup(
                    btn_prosegui_avvia, "distruttivo"
                )
                applica_icona(btn_annulla_avvia, "x", 18)

                dialog_avvia.setDefaultButton(btn_salva_avvia)
                dialog_avvia.setEscapeButton(btn_annulla_avvia)
                dialog_avvia.exec()

                bottone_avvia = dialog_avvia.clickedButton()

                if bottone_avvia == btn_salva_avvia:
                    self.salva_assegnazione()

                    # Dopo un salvataggio riuscito si prosegue. Se il salvataggio
                    # viene annullato o fallisce, lo stato resta DA_SALVARE.
                    if self.sessione.mensile.non_salvata:
                        return

                elif bottone_avvia == btn_annulla_avvia:
                    return


            # Una nuova elaborazione parte sempre da una superficie vuota: il docente
            # vede subito che il programma sta preparando un risultato differente.
            self._resetta_tab_aula_report()
            self._risultato_mensile_personalizzata_p31 = None

            self._esegui_assegnazione_personalizzata()

    def _imposta_modalita_elaborazione(self, in_elaborazione: bool):
            """Congela le sole sorgenti del calcolo durante l'elaborazione."""

            self._layout_in_elaborazione = bool(in_elaborazione)
            stato = calcola_abilitazione_controlli(
                in_elaborazione=in_elaborazione,
                classe_caricata=self.sessione.classe_caricata,
            )
            self.btn_avvia_assegnazione.setEnabled(stato.avvio)
            for gruppo in (
                    self.group_aula,
                    self.group_opzioni,
                    self.group_modalita):
                gruppo.setEnabled(stato.configurazione)

            # La navigazione fra schede resta possibile, ma Editor e Storico non
            # possono mutare gli input fotografati dal worker mentre calcola.
            self.editor_studenti.setEnabled(stato.editor)
            if hasattr(self, "editor_aula_personalizzata"):
                self.editor_aula_personalizzata.setEnabled(
                    not in_elaborazione
                )
            self.tabella_storico.setEnabled(stato.storico)
            if not in_elaborazione:
                self._aggiorna_disponibilita_avvio_geometria()

            if in_elaborazione:
                self.label_status.setText("Elaborazione in corso...")
            else:
                self.label_status.setText("")


    def _elaborazione_fallita(
            self, messaggio_errore: str, report: dict | None = None):
            """Mostra il fallimento dell’elaborazione con gli eventuali dati diagnostici."""

            if not self._gestisci_fallimento_annuale():
                self.timer_messaggi.stop()
                self._imposta_modalita_elaborazione(False)
            self._rilascia_worker_mensile_se_inattivo()

            if report:

                self._mostra_popup_fallimento_dettagliato(report)
            else:

                self._mostra_errore("Errore Assegnazione", messaggio_errore)

    def _mostra_popup_fallimento_dettagliato(self, report: dict):
            """Mostra analisi e suggerimenti del report diagnostico di fallimento."""
            html_parti = []
            html_parti.append(
                "<b>L'algoritmo non è riuscito a completare una "
                "disposizione valida.</b><br><br>"
            )

            cause_certe = report.get("cause_certe", [])

            if cause_certe:
                titolo_cause = (
                    "Causa certa individuata"
                    if len(cause_certe) == 1
                    else "Cause certe individuate"
                )
                html_parti.append(
                    f"<b>{titolo_cause}:</b><br>"
                )
                for causa in cause_certe:
                    html_parti.append(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;• {escape(str(causa))}<br>"
                    )
                html_parti.append("<br>")
            elif report.get("ricerca_incompleta"):
                if report.get('tempo_esaurito'):
                    html_parti.append(
                        "Il tempo disponibile è terminato senza una "
                        "disposizione completa.<br><br>"
                    )
                html_parti.append(
                    "La ricerca non ha prodotto una disposizione completa. "
                    "Non è dimostrato che una soluzione sia impossibile; "
                    "i fattori seguenti possono averla resa difficile.<br><br>"
                )
            else:
                html_parti.append(
                    "Nessuna causa singola è stata dimostrata. Il fallimento "
                    "può dipendere dalla combinazione dei vincoli oppure "
                    "dall'ordine esplorato dalla ricerca.<br><br>"
                )

            incomp = report.get("incompatibilita_assolute", [])
            if incomp:
                etichetta_incompatibilita = quantita(
                    len(incomp),
                    "incompatibilità assoluta",
                    "incompatibilità assolute",
                )
                html_parti.append(
                    f"<b>{etichetta_incompatibilita} (livello 3)</b><br>"
                )

                for coppia in incomp[:4]:
                    html_parti.append(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;• {escape(str(coppia))}<br>"
                    )
                if len(incomp) > 4:
                    residue = len(incomp) - 4
                    coda = (
                        "un’altra incompatibilità"
                        if residue == 1
                        else f"altre {residue} incompatibilità"
                    )
                    html_parti.append(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;<i>... e {coda}</i><br>"
                    )
                html_parti.append("<br>")

            prima_fila = report.get(
                "studenti_prima_fila",
                []
            )
            info_prima = report.get("prima_fila", {})

            if info_prima.get("impossibile_per_capienza"):
                richieste = info_prima.get("richieste", 0)
                posti_prima = info_prima.get("posti_utilizzabili", 0)
                html_parti.append(
                    f"<b>Posizione PRIMA impossibile:</b> "
                    f"{quantita(richieste, 'richiesta', 'richieste')}, "
                    f"ma soltanto "
                    f"{quantita(posti_prima, 'posto utilizzabile', 'posti utilizzabili')} "
                    "nella prima fila.<br><br>"
                )
            elif prima_fila:
                posti_prima = info_prima.get("posti_utilizzabili", "?")
                studenti_prima = quantita(
                    len(prima_fila),
                    "studente con posizione PRIMA",
                    "studenti con posizione PRIMA",
                )
                if posti_prima is None:
                    html_parti.append(
                        f"<b>{studenti_prima}.</b> La capienza esatta della "
                        "prima fila non è disponibile nel report.<br><br>"
                    )
                else:
                    posti_testo = (
                        f"{posti_prima} posto utilizzabile"
                        if posti_prima == 1
                        else f"{posti_prima} posti utilizzabili"
                    )
                    html_parti.append(
                        f"<b>{studenti_prima}:</b> su {posti_testo}; "
                        "la capienza della prima fila è sufficiente.<br><br>"
                    )

            gruppo_incompatibile = report.get(
                "gruppo_incompatibile_sovrabbondante"
            )
            if gruppo_incompatibile is not None:
                html_parti.append(
                    "<b>Gruppo incompatibile determinante:</b> "
                    + ", ".join(
                        escape(str(nome))
                        for nome in gruppo_incompatibile.get("studenti", [])
                    )
                    + ".<br><br>"
                )

            gm = report.get("genere_misto")

            bl = report.get("blacklist", {})
            if bl.get("coppie", 0) > 5:
                html_parti.append(
                    f"<b>Rotazioni precedenti:</b> "
                    f"{quantita(bl['coppie'], 'coppia già usata', 'coppie già usate')} "
                    f"in precedenti assegnazioni<br><br>"
                )

            suggerimenti = report.get("suggerimenti", [])
            if suggerimenti:
                html_parti.append("<b>Suggerimenti per risolvere:</b><br>")
                for i, sugg in enumerate(suggerimenti, 1):
                    html_parti.append(
                        f"&nbsp;&nbsp;{i}. {escape(str(sugg))}<br>"
                    )

            testo_warning_html = "".join(html_parti)

            dettagli_parti = []
            dettagli_parti.append("=" * 50)
            dettagli_parti.append("REPORT DIAGNOSTICO COMPLETO")
            dettagli_parti.append("=" * 50)

            dettagli_parti.append("")
            dettagli_parti.append("INCOMPATIBILITÀ ASSOLUTE (livello 3):")
            if incomp:
                for coppia in incomp:
                    dettagli_parti.append(f"  • {coppia}")
            else:
                dettagli_parti.append("  Nessuna")

            dettagli_parti.append("")
            dettagli_parti.append("POSIZIONE PRIMA:")
            richieste_prima = info_prima.get("richieste", len(prima_fila))
            posti_prima = info_prima.get("posti_utilizzabili", "N/D")
            etichetta_richieste = (
                "Richiesta" if richieste_prima == 1 else "Richieste"
            )
            etichetta_posti = (
                "Posto utilizzabile nella prima fila"
                if posti_prima == 1
                else "Posti utilizzabili nella prima fila"
            )
            dettagli_parti.append(
                f"  {etichetta_richieste}: {richieste_prima}"
            )
            dettagli_parti.append(
                f"  {etichetta_posti}: {posti_prima}"
            )

            if info_prima.get("eccesso", 0) > 0:
                eccesso = info_prima["eccesso"]
                etichetta_eccesso = (
                    "Richiesta in eccesso"
                    if eccesso == 1
                    else "Richieste in eccesso"
                )
                dettagli_parti.append(
                    f"  {etichetta_eccesso}: {eccesso}"
                )

            if prima_fila:
                dettagli_parti.append("  Studenti:")
                for nome in prima_fila:
                    dettagli_parti.append(f"    • {nome}")
            else:
                dettagli_parti.append("  Nessuno")

            dettagli_parti.append("")
            dettagli_parti.append(
                "GRUPPO RECIPROCAMENTE INCOMPATIBILE DETERMINANTE:"
            )
            if gruppo_incompatibile is not None:
                dettagli_parti.append(
                    f"  Dimensione: "
                    f"{gruppo_incompatibile.get('dimensione', 0)}"
                )
                studenti_esterni = gruppo_incompatibile.get(
                    "studenti_esterni",
                    0,
                )
                dettagli_parti.append(
                    "  "
                    + quantita(
                        studenti_esterni,
                        "studente esterno disponibile",
                        "studenti esterni disponibili",
                    )
                )
                for nome in gruppo_incompatibile.get("studenti", []):
                    dettagli_parti.append(f"    • {nome}")
            else:
                dettagli_parti.append("  Nessuno")

            senza_vicini = report.get(
                "studenti_senza_vicini_compatibili",
                []
            )
            if senza_vicini:
                dettagli_parti.append("")
                dettagli_parti.append(
                    "STUDENTI SENZA ALCUN VICINO COMPATIBILE:"
                )
                for nome in senza_vicini:
                    dettagli_parti.append(f"  • {nome}")

            info_fisso = report.get("fisso", {})
            if info_fisso.get("presente"):
                dettagli_parti.append("")
                dettagli_parti.append("STUDENTE FISSO:")
                dettagli_parti.append(
                    f"  Nome: {info_fisso.get('nome')}"
                )
                numero_vicini = len(info_fisso.get("possibili_vicini", []))
                dettagli_parti.append(
                    "  "
                    + quantita(
                        numero_vicini,
                        "possibile vicino compatibile",
                        "possibili vicini compatibili",
                    )
                )

            if gm:
                dettagli_parti.append("")
                dettagli_parti.append("GENERE MISTO:")
                dettagli_parti.append(
                    "  Preferenza attiva: Sì (non è un vincolo assoluto)"
                )
                dettagli_parti.append(f"  Maschi: {gm['maschi']}, Femmine: {gm['femmine']}")
                if gm["sbilanciamento"]:
                    dettagli_parti.append("  Sbilanciamento rilevato")

            dettagli_parti.append("")
            dettagli_parti.append("ROTAZIONI PRECEDENTI:")
            dettagli_parti.append(
                "  "
                + quantita(
                    bl.get("coppie", 0),
                    "coppia già usata",
                    "coppie già usate",
                )
            )
            piu_usate = bl.get("piu_usate", [])
            if piu_usate:
                dettagli_parti.append("  Coppie più riutilizzate:")
                for cu in piu_usate:
                    dettagli_parti.append(f"    - {cu}")

            dettagli_parti.append("")
            dettagli_parti.append("SUGGERIMENTI:")
            for i, sugg in enumerate(suggerimenti, 1):
                dettagli_parti.append(f"  {i}. {sugg}")

            dettagli_parti.append("")
            dettagli_parti.append("=" * 50)

            testo_dettagliato = "\n".join(dettagli_parti)
            mostra_popup_con_dettagli_persistente(
                self,
                "Assegnazione non riuscita",
                testo_warning_html,
                "circle-x",
                "Dettagli dell'assegnazione non riuscita",
                testo_dettagliato,
            )

    def _aggiorna_messaggio_elaborazione(self):
            """Ruota solo i messaggi di lavorazione leggibili."""
            self.indice_messaggio = (self.indice_messaggio + 1) % len(self.messaggi_elaborazione)
            messaggio_corrente = self.messaggi_elaborazione[self.indice_messaggio]
            self.label_status.setText(messaggio_corrente)
