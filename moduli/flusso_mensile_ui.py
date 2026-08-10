# -*- coding: utf-8 -*-
"""Avvio, calcolo e diagnostica delle assegnazioni correnti.

La fase F5a concentra qui il worker mensile e il coordinamento GUI condiviso
dall'avvio dell'assegnazione. Il salvataggio nello Storico resta nella finestra
principale ed è demandato alla fase F5b.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import copy
from html import escape

from PySide6.QtWidgets import (
    QGridLayout, QLabel, QMessageBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Signal, QThread

from moduli.aula import ConfigurazioneAula
from moduli.stato_sessione import (
    calcola_abilitazione_controlli,
    puo_avviare_elaborazione,
    risultato_appartiene_sessione,
)
from moduli.algoritmo import AssegnatorePosti
from moduli.vincoli import MotoreVincoliConfigurato
import moduli.motore_terzetti as mt
from moduli.metrica_pulizia import snapshot_blacklist
from moduli.lingua import quantita
from moduli.strato_storico import (
    applica_penalita_storico as _applica_penalita_storico_mese,
)
from moduli.generazione import calcola_miglior_mese
from moduli.casualita import risolvi_seed_principale
from moduli.worker_mensile import MensileTerzettiProcessBridge
from moduli.risultati_annuali import (
    data_creazione_corrente as _data_creazione_corrente,
    nome_assegnazione_automatico as _nome_assegnazione_automatico,
    prossimo_progressivo_storico as _prossimo_progressivo_storico,
)
from moduli.widget_statistiche import crea_widget_righe_statistiche
from moduli.tema import C
from moduli.utilita import (
    applica_icona,
    applica_stile_pulsante_popup,
    mostra_popup_con_dettagli_persistente,
    crea_popup_semantico,
    mostra_popup_semantico,
)
from moduli.statistiche_generali import (
    applica_formattazione_statistiche_generali,
)
from moduli.esportazione import evidenzia_riutilizzi


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

class MensileCoppieWorkerThread(QThread):
    """Esegue l’assegnazione mensile senza bloccare l’interfaccia."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    completed = Signal(object)
    error_occurred = Signal(str, object)

    def __init__(self, studenti, configurazione_aula, config_app, modalita_trio='centro', flag_genere_misto=False, studente_fisso=None, seed_principale=None):
        super().__init__()

        # La deepcopy unica conserva anche la relazione d'identità fra
        # l'eventuale FISSO e la sua voce nella lista degli studenti. Il worker
        # non legge né modifica oggetti vivi della sessione GUI.
        (
            self.studenti,
            self.configurazione_aula,
            self.studente_fisso,
        ) = copy.deepcopy((
            list(studenti),
            configurazione_aula,
            studente_fisso,
        ))
        self.config_app = config_app.copia_temporanea()

        self.modalita_rotazione = True
        self.modalita_trio = modalita_trio
        self.flag_genere_misto = flag_genere_misto
        self.seed_principale = risolvi_seed_principale(seed_principale)

    def run(self):
        """Genera e pubblica la migliore assegnazione mensile disponibile."""
        try:
            self.status_updated.emit("Inizializzazione algoritmo...")
            self.progress_updated.emit(10)

            coppie_gia_usate = snapshot_blacklist(self.config_app)

            self.status_updated.emit("Cerco la disposizione migliore...")
            self.progress_updated.emit(30)

            print(f"🎲 Operazione mensile a coppie — seed principale: {self.seed_principale}")
            miglior_assegnatore, ultimo_assegnatore = calcola_miglior_mese(
                self.studenti,
                self.configurazione_aula,
                self.config_app,
                self.modalita_trio,
                self.flag_genere_misto,
                self.studente_fisso,
                coppie_gia_usate,
                seed_principale=self.seed_principale,
                contesto_casuale={
                    "operazione": "mensile",
                    "mese": 1,
                },
            )

            self.progress_updated.emit(90)

            if miglior_assegnatore is not None:
                self.status_updated.emit("Assegnazione completata!")
                self.progress_updated.emit(100)
                self.completed.emit(miglior_assegnatore)
            else:

                report = getattr(ultimo_assegnatore, 'report_fallimento', None)
                self.error_occurred.emit(
                    "Non è stata trovata una disposizione valida",
                    report
                )

        except Exception as e:

            self.error_occurred.emit(f"Errore durante l'assegnazione: {str(e)}", None)


class FlussoMensileUIMixin:
    """Coordina avvio, completamento e fallimento delle assegnazioni."""

    def _esegui_assegnazione_terzetti(self, studente_fisso, ha_fisso):
            """Esegue un’assegnazione mensile a terzetti e prepara i risultati."""

            if self.radio_annuale.isChecked():
                self._avvia_annuale_terzetti(studente_fisso, ha_fisso)
                return

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

            self.sessione.imposta_aula(ConfigurazioneAula(
                f"Aula {self.input_nome_classe.text()}"
            ))
            self.sessione.aula.crea_layout_terzetti(
                num_studenti,
                terzetti_per_fila=terzetti_per_fila,
                posizione_blocco_finale=posizione_blocco_finale,
                ha_fisso=ha_fisso,
                preferenza_resto2=preferenza_resto2,
            )

            capienza_prima = (
                self.sessione.aula
                .capienza_prima_fila_terzetti()
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

            genere_misto = self.checkbox_genere_misto.isChecked()
            nome_classe = self.input_nome_classe.text() or "Classe"
            seed_principale = risolvi_seed_principale(None)
            print(
                f"🎲 Operazione mensile a terzetti — seed principale: "
                f"{seed_principale}"
            )

            self._avvia_mensile_terzetti_processo(
                studente_fisso=studente_fisso,
                posizione_blocco_finale=posizione_blocco_finale,
                preferenza_resto2=preferenza_resto2,
                genere_misto=genere_misto,
                capienza_prima=capienza_prima,
                seed_principale=seed_principale,
                nome_classe=nome_classe,
            )

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

    def _avvia_mensile_terzetti_processo(
            self, *, studente_fisso, posizione_blocco_finale,
            preferenza_resto2, genere_misto, capienza_prima,
            seed_principale, nome_classe):
            """Avvia il Mensile a terzetti in un processo Python separato."""

            try:
                worker = MensileTerzettiProcessBridge(
                    self.sessione.studenti,
                    self.config_app,
                    genere_misto,
                    preferenza_resto2,
                    0 in self.sessione.aula.file_blocchi_finali,
                    capienza_prima['terzetti'],
                    capienza_prima['resti'],
                    mt.NUM_CANDIDATI_TERZETTI,
                    seed_principale=seed_principale,
                )
            except Exception as errore:
                self._elaborazione_terzetti_processo_fallita(
                    "Impossibile preparare il processo Mensile a terzetti: "
                    f"{errore}",
                    None,
                )
                return
            self.worker_thread = worker
            self._contesto_mensile_terzetti_processo = {
                "aula": self.sessione.aula,
                "studenti_live": self.sessione.studenti,
                "file_origine": self.sessione.file_origine,
                "nome_classe": nome_classe,
                "studente_fisso": studente_fisso,
                "posizione_blocco_finale": posizione_blocco_finale,
                "preferenza_resto2": preferenza_resto2,
                "genere_misto": genere_misto,
                "config_snapshot": worker.config_snapshot,
            }

            self.indice_messaggio = 0
            self.timer_messaggi.start(2000)
            self._imposta_modalita_elaborazione(True)

            worker.status_updated.connect(self.label_status.setText)
            worker.completed.connect(
                self._elaborazione_terzetti_processo_completata
            )
            worker.error_occurred.connect(
                self._elaborazione_terzetti_processo_fallita
            )
            worker.finished.connect(self._worker_mensile_finito)
            try:
                worker.start()
            except Exception as errore:
                self._elaborazione_terzetti_processo_fallita(
                    "Impossibile avviare il processo Mensile a terzetti: "
                    f"{errore}",
                    None,
                )

    def _concludi_mensile_terzetti_processo(self):
            """Ripristina la GUI dopo l'esito del processo Mensile terzetti."""
            self.timer_messaggi.stop()
            self._imposta_modalita_elaborazione(False)

    def _elaborazione_terzetti_processo_completata(self, risultato: dict):
            """Applica nel thread GUI il risultato Mensile ricevuto via IPC."""
            self._concludi_mensile_terzetti_processo()
            contesto = getattr(
                self,
                '_contesto_mensile_terzetti_processo',
                None,
            )
            self._contesto_mensile_terzetti_processo = None

            if contesto is None:
                self._mostra_errore(
                    "Risultato non applicato",
                    "Il contesto dell'assegnazione Mensile non è più disponibile."
                )
                return

            if not risultato_appartiene_sessione(
                file_origine_corrente=self.sessione.file_origine,
                studenti_correnti=self.sessione.studenti,
                aula_corrente=self.sessione.aula,
                file_origine_atteso=contesto['file_origine'],
                studenti_attesi=contesto['studenti_live'],
                aula_attesa=contesto['aula'],
            ):
                self._mostra_errore(
                    "Risultato non applicato",
                    "La classe è stata chiusa o sostituita durante il calcolo.\n\n"
                    "Il risultato tardivo è stato scartato e nessun dato è "
                    "stato salvato."
                )
                return

            gruppi = risultato.get('gruppi')
            metadati_casualita = risultato.get(
                'metadati_casualita',
                {},
            )
            if gruppi is None:
                self._mostra_fallimento_mensile_terzetti(
                    metadati_casualita
                )
                return

            motore = MotoreVincoliConfigurato()
            motore.imposta_genere_misto_obbligatorio(
                contesto['genere_misto']
            )
            _applica_penalita_storico_mese(
                motore,
                contesto['config_snapshot'],
                modo="terzetti",
            )
            self._finalizza_assegnazione_terzetti(
                gruppi,
                metadati_casualita,
                motore=motore,
                aula=contesto['aula'],
                studente_fisso=contesto['studente_fisso'],
                posizione_blocco_finale=(
                    contesto['posizione_blocco_finale']
                ),
                preferenza_resto2=contesto['preferenza_resto2'],
                file_origine=contesto['file_origine'],
                nome_classe=contesto['nome_classe'],
                genere_misto=contesto['genere_misto'],
            )

    def _elaborazione_terzetti_processo_fallita(
            self, messaggio_errore: str, report: dict | None = None):
            """Ripristina la GUI e mostra un errore prodotto dal processo."""
            self._concludi_mensile_terzetti_processo()
            self._contesto_mensile_terzetti_processo = None
            self._elaborazione_fallita(messaggio_errore, report)

    def _mostra_fallimento_mensile_terzetti(self, metadati_casualita):
            """Mostra il fallimento semantico del Mensile a terzetti."""
            report = metadati_casualita.get("report_fallimento")
            if report is None:
                report = {
                    "casualita": metadati_casualita,
                    "cause_certe": [],
                    "ricerca_incompleta": False,
                    "suggerimenti": [
                        "Riprova l'assegnazione; se il fallimento si ripete, "
                        "controlla incompatibilità di livello 3, posizioni "
                        "PRIMA e configurazione dei blocchi a terzetti."
                    ],
                }
            self._mostra_popup_fallimento_dettagliato(report)

    def _finalizza_assegnazione_terzetti(
            self, gruppi, metadati_casualita, *, motore, aula,
            studente_fisso, posizione_blocco_finale,
            preferenza_resto2, file_origine, nome_classe, genere_misto):
            """Costruisce layout, report e stato Mensile nel solo thread GUI."""

            report = aula.piazza_gruppi_terzetti(gruppi)

            if not report.get('valido_struttura', True):
                dettaglio = "\n".join(report.get('avvisi', []))
                self._mostra_errore(
                    "Errore interno di posizionamento",
                    f"{dettaglio}\n\nNessun dato è stato salvato."
                )
                return

            if not report.get('valido_prima', True):
                self._mostra_errore(
                    "Errore interno di posizionamento",
                    "La disposizione prodotta non rispetta il vincolo assoluto "
                    "PRIMA ed è stata scartata.\n\n"
                    "Nessun dato è stato salvato."
                )
                return

            self._aggiorna_visualizzazione_aula(aula)

            data_creazione = _data_creazione_corrente()
            numero = _prossimo_progressivo_storico(
                self.config_app,
                file_origine,
                "mensile",
                "terzetti",
            )
            nome_assegnazione = _nome_assegnazione_automatico(
                nome_classe,
                "mensile",
                "terzetti",
                numero,
            )

            testo_report, _ = self.costruisci_testo_report_terzetti(
                gruppi,
                motore,
                nome_assegnazione=nome_assegnazione,
                data_creazione=data_creazione,
            )
            self.text_report.setPlainText(testo_report)
            evidenzia_riutilizzi(self.text_report)
            applica_formattazione_statistiche_generali(
                self.text_report,
                getattr(self, '_statistiche_generali_terzetti_correnti', []),
            )
            self.widget_hint_report.setVisible(False)
            self.tab_widget.setCurrentIndex(1)

            avvisi = report.get('avvisi', [])
            self._mostra_popup_riepilogo_terzetti(gruppi, motore, avvisi)

            dati_terzetti = {
                'gruppi': gruppi,
                'configurazione_aula': aula,
                'studente_fisso': studente_fisso,
                'posizione_blocco_finale': posizione_blocco_finale,
                'preferenza_resto2': preferenza_resto2,
                'statistiche_generali': [
                    dict(riga) for riga in getattr(
                        self, '_statistiche_generali_terzetti_correnti', [])
                ],
                'metadati_casualita': metadati_casualita,
            }
            self.sessione.mensile.prepara_terzetti(
                dati_terzetti,
                nome=nome_assegnazione,
                progressivo=numero,
                data_creazione=data_creazione,
                file_origine=file_origine,
                nome_classe=nome_classe,
                genere_misto=genere_misto,
            )

            self.btn_salva_progetto.setEnabled(True)
            self.btn_salva_progetto.setToolTip(
                "Salva questa disposizione nello Storico."
            )
            self.btn_export_excel.setEnabled(False)
            self.btn_export_excel.setToolTip(
                "Disponibile dopo il salvataggio dell'assegnazione."
            )
            self.btn_export_report_txt.setEnabled(False)
            self.btn_export_report_txt.setToolTip(
                "Disponibile dopo il salvataggio dell'assegnazione."
            )

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
                    self.tab_widget.setCurrentIndex(0)
                    return

            if hasattr(self, 'editor_studenti') and self.editor_studenti._modifiche_non_salvate:
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

                self.tab_widget.setCurrentIndex(0)
                return

            if self.sessione.posti_insufficienti:
                posti_disponibili = getattr(
                    self, '_ultimo_totale_posti', None
                )
                if posti_disponibili is None:
                    posti_disponibili = (
                        int(self.input_num_file.text())
                        * int(self.input_posti_fila.text())
                    )
                mostra_popup_semantico(
                    self,
                    "Posti insufficienti",
                    "Non ci sono abbastanza posti per tutti gli studenti.",
                    "circle-x",
                    testo_informativo=(
                        f"Studenti da sistemare: {len(self.sessione.studenti)}\n"
                        f"Posti disponibili: {posti_disponibili}\n\n"
                        "Aumenta il numero di file di banchi oppure i posti per fila."
                    ),
                    messaggio_in_grassetto=True,
                )
                return

            if self.sessione.mensile.non_salvata:
                dialog_avvia = crea_popup_semantico(
                    self,
                    "Assegnazione non salvata",
                    "L'assegnazione corrente non è stata salvata nello Storico.",
                    "triangle-alert",
                    testo_informativo=(
                        "Se scegli di proseguire, verrà scartata definitivamente: "
                        "le schede Aula e Report saranno svuotate e non sarà più "
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

                    # Il comando richiesto era avviare una nuova assegnazione:
                    # dopo un salvataggio riuscito si prosegue. Se il salvataggio
                    # è stato annullato o è fallito, lo stato resta DA_SALVARE e
                    # la nuova elaborazione non deve partire.
                    if self.sessione.mensile.non_salvata:
                        return

                elif bottone_avvia == btn_annulla_avvia:

                    return


            # Una nuova elaborazione parte sempre da una superficie vuota: il docente
            # vede subito che il programma sta preparando un risultato differente.
            self._resetta_tab_aula_report()

            num_studenti = len(self.sessione.studenti)
            self.sessione.imposta_aula(
                ConfigurazioneAula(f"Aula {self.input_nome_classe.text()}")
            )

            num_file = int(self.input_num_file.text())
            posti_per_fila = int(self.input_posti_fila.text())

            studente_fisso = None
            num_fissi = 0
            for s in self.sessione.studenti:
                if s.nota_posizione == 'FISSO':
                    num_fissi += 1
                    studente_fisso = s

            if num_fissi > 1:
                self._mostra_errore(
                    "ERRORE CONFIGURAZIONE!",
                    f"Trovati {num_fissi} studenti con posizione 'FISSO'.\n\n"
                    f"Al massimo 1 studente può avere posizione FISSO.\n"
                    f"Correggi eliminando le posizioni 'FISSO' in eccesso."
                )
                return

            ha_fisso = (studente_fisso is not None)
            if ha_fisso:
                print(f"📌 Studente FISSO individuato: {studente_fisso.get_nome_completo()}")

            if self.sessione.geometria == 'terzetti':
                self._esegui_assegnazione_terzetti(studente_fisso, ha_fisso)
                return

            num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti

            posizione_trio = None
            modalita_trio = 'centro'

            if num_rimanenti % 2 == 1:
                if self.radio_trio_prima.isChecked():
                    posizione_trio = "prima"
                    modalita_trio = "prima"
                elif self.radio_trio_ultima.isChecked():
                    posizione_trio = "ultima"
                    modalita_trio = "ultima"
                elif self.radio_trio_centro.isChecked():
                    posizione_trio = "centro"
                    modalita_trio = "centro"

            self.sessione.aula.crea_layout_standard(
                num_studenti, num_file, posti_per_fila, posizione_trio, ha_fisso=ha_fisso
            )

            if num_studenti > self.sessione.aula.posti_disponibili:
                self._mostra_errore(
                    "Configurazione NON valida",
                    f"Non ci sono abbastanza posti.\n"
                    f"Studenti: {num_studenti}\n"
                    f"Posti disponibili: {self.sessione.aula.posti_disponibili}\n\n"
                    f"Aumenta il numero di file o posti per fila."
                )
                return

            self._imposta_modalita_elaborazione(True)

            if self.radio_annuale.isChecked():
                self._avvia_annuale_coppie(
                    modalita_trio,
                    studente_fisso,
                )

            else:

                self.indice_messaggio = 0
                self.timer_messaggi.start(2000)

                genere_misto = self.checkbox_genere_misto.isChecked()
                nome_classe = self.input_nome_classe.text() or "Classe"
                self._contesto_mensile_coppie = {
                    "file_origine": self.sessione.file_origine,
                    "studenti_live": self.sessione.studenti,
                    "aula_live": self.sessione.aula,
                    "nome_classe": nome_classe,
                    "genere_misto": genere_misto,
                }
                try:
                    self.worker_thread = MensileCoppieWorkerThread(
                        self.sessione.studenti,
                        self.sessione.aula,
                        self.config_app,
                        modalita_trio,
                        genere_misto,
                        studente_fisso
                    )
                except Exception as errore:
                    self._elaborazione_fallita(
                        "Impossibile preparare il calcolo Mensile a coppie: "
                        f"{errore}",
                        None,
                    )
                    return

                self.worker_thread.status_updated.connect(self.label_status.setText)
                self.worker_thread.completed.connect(self._elaborazione_completata)
                self.worker_thread.error_occurred.connect(self._elaborazione_fallita)
                self.worker_thread.finished.connect(self._worker_mensile_finito)

                try:
                    self.worker_thread.start()
                except Exception as errore:
                    self._elaborazione_fallita(
                        "Impossibile avviare il calcolo Mensile a coppie: "
                        f"{errore}",
                        None,
                    )

    def _imposta_modalita_elaborazione(self, in_elaborazione: bool):
            """Congela le sole sorgenti del calcolo durante l'elaborazione."""

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
            self.tabella_storico.setEnabled(stato.storico)

            if in_elaborazione:
                self.label_status.setText("Elaborazione in corso...")
            else:
                self.label_status.setText("")

    def _elaborazione_completata(self, assegnatore: AssegnatorePosti):
            """Riceve una disposizione a coppie completata e ne mostra i risultati."""

            self.timer_messaggi.stop()
            self._imposta_modalita_elaborazione(False)

            contesto = getattr(self, "_contesto_mensile_coppie", None)
            self._contesto_mensile_coppie = None
            if contesto is None or not risultato_appartiene_sessione(
                file_origine_corrente=self.sessione.file_origine,
                studenti_correnti=self.sessione.studenti,
                aula_corrente=self.sessione.aula,
                file_origine_atteso=contesto["file_origine"],
                studenti_attesi=contesto["studenti_live"],
                aula_attesa=contesto["aula_live"],
            ):
                self._mostra_errore(
                    "Risultato non applicato",
                    "La classe è stata chiusa o sostituita durante il calcolo.\n\n"
                    "Il risultato tardivo è stato scartato e nessun dato è "
                    "stato salvato."
                )
                return

            data_creazione = _data_creazione_corrente()
            numero = _prossimo_progressivo_storico(
                self.config_app,
                contesto["file_origine"],
                "mensile",
                "coppie",
            )
            nome_assegnazione = _nome_assegnazione_automatico(
                contesto["nome_classe"],
                "mensile",
                "coppie",
                numero,
            )
            self.sessione.mensile.prepara_coppie(
                assegnatore,
                nome=nome_assegnazione,
                progressivo=numero,
                data_creazione=data_creazione,
                file_origine=contesto["file_origine"],
                nome_classe=contesto["nome_classe"],
                genere_misto=contesto["genere_misto"],
            )

            self._visualizza_risultati(assegnatore)

            self.btn_salva_progetto.setEnabled(True)

            self.btn_export_excel.setEnabled(False)
            self.btn_export_excel.setToolTip(
                "Salva prima l'assegnazione nello Storico per abilitare l'esportazione."
            )
            self.btn_export_report_txt.setEnabled(False)
            self.btn_export_report_txt.setToolTip(
                "Salva prima l'assegnazione nello Storico per abilitare l'esportazione."
            )

            righe_statistiche = assegnatore.statistiche_generali
            ha_precedenti_altro_modo = self._precedenti_altro_modo > 0

            msg_box = crea_popup_semantico(
                self,
                "Assegnazione completata",
                "",
                "info" if ha_precedenti_altro_modo else "circle-check",
            )
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(
                "<b>Assegnazione completata con successo.</b><br><br>"
                "<b>Statistiche generali</b>"
            )
            msg_box.addButton(QMessageBox.Ok)
            _aggiungi_widget_popup(
                msg_box,
                crea_widget_righe_statistiche(righe_statistiche),
            )

            if ha_precedenti_altro_modo:
                nota = QLabel(
                    f'<span style="color: {C("testo_info")};">'
                    f'<b>Nota informativa</b> — '
                    f'{quantita(self._precedenti_altro_modo, "vicinanza", "vicinanze")} '
                    f'con precedenti nella modalità terzetti. Le rotazioni delle due modalità '
                    f'restano indipendenti.</span>'
                )
                nota.setTextFormat(Qt.RichText)
                nota.setWordWrap(True)
                _aggiungi_widget_popup(msg_box, nota)

            msg_box.exec()

    def _mostra_popup_riepilogo_terzetti(self, gruppi, motore, avvisi=None):
            """Mostra il riepilogo strutturato dell’assegnazione a terzetti."""

            righe_statistiche = self._statistiche_generali_terzetti_correnti
            ha_precedenti_altro_modo = self._precedenti_altro_modo > 0

            msg_box = crea_popup_semantico(
                self,
                "Assegnazione completata",
                "",
                "info" if ha_precedenti_altro_modo else "circle-check",
            )
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setText(
                "<b>Assegnazione completata con successo.</b><br><br>"
                "<b>Statistiche generali</b>"
            )
            msg_box.addButton(QMessageBox.Ok)
            _aggiungi_widget_popup(
                msg_box,
                crea_widget_righe_statistiche(righe_statistiche),
            )

            note = []
            if ha_precedenti_altro_modo:
                note.append(
                    f'<span style="color: {C("testo_info")};">'
                    f'<b>Nota informativa</b> — '
                    f'{quantita(self._precedenti_altro_modo, "vicinanza", "vicinanze")} '
                    f'con precedenti nella modalità coppie. Le rotazioni delle due modalità '
                    f'restano indipendenti.</span>'
                )
            if avvisi:
                note.append(
                    f'<span style="color: {C("testo_ocra")}; font-weight: bold;">'
                    f'Avvisi di capienza: {"<br>".join(avvisi)}</span>'
                )
            if note:
                etichetta_note = QLabel("<br><br>".join(note))
                etichetta_note.setTextFormat(Qt.RichText)
                etichetta_note.setWordWrap(True)
                _aggiungi_widget_popup(msg_box, etichetta_note)

            msg_box.exec()

    def _elaborazione_fallita(
            self, messaggio_errore: str, report: dict | None = None):
            """Mostra il fallimento dell’elaborazione con gli eventuali dati diagnostici."""

            self._contesto_mensile_coppie = None
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
                html_parti.append(
                    "La ricerca ha raggiunto il limite di sicurezza prima di "
                    "dimostrare se esiste una disposizione valida.<br><br>"
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
            """Ruota il messaggio mostrato durante l’elaborazione."""

            self.indice_messaggio = (self.indice_messaggio + 1) % len(self.messaggi_elaborazione)
            messaggio_corrente = self.messaggi_elaborazione[self.indice_messaggio]

            self.label_status.setText(messaggio_corrente)
