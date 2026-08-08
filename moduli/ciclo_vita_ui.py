# -*- coding: utf-8 -*-
"""Ciclo di vita e coordinamento generale della finestra principale.

Gestisce avvio, tema, finestre informative, riconoscimento prudente delle
classi nello Storico, chiusura sicura e anomalie del file di configurazione.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import copy
import os

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer

from moduli.profilo_gui import ProfiloGUI
from moduli.lingua import quantita
from moduli.tema import C, imposta_tema, get_tema
from moduli.utilita import (
    applica_icona, applica_stile_pulsante_popup,
    aggiorna_icone_applicazione, crea_popup_semantico,
    mostra_popup_semantico,
)
from moduli.istruzioni import (
    mostra_istruzioni, mostra_crediti, mostra_aiuto_configurazione_aula,
    aggiorna_tema_finestre_informative,
)
from moduli.configurazione import (
    AZIONE_FILE_ASSENTE_RICREA,
    AZIONE_FILE_ASSENTE_AZZERA,
    AZIONE_FILE_ASSENTE_ANNULLA,
    ESITO_SALVATAGGIO_AZZERATO,
    ESITO_SALVATAGGIO_ANNULLATO,
    ESITO_SALVATAGGIO_ERRORE,
)


class CicloVitaUIMixin:
    """Coordina lo stato generale della finestra durante l'intera sessione."""

    def _chiedi_azione_file_config_assente(self, percorso_file: str) -> str:
        """Chiede come trattare il JSON eliminato durante la sessione."""
        dialog = crea_popup_semantico(
            self,
            "File di stato non più presente",
            "Il file dello Storico è stato eliminato o spostato mentre "
            "PostiPerfetti era aperto.",
            "triangle-alert",
            testo_informativo=(
                "Storico e rotazioni sono ancora disponibili in memoria.\n\n"
                "• Ricrea il file: conserva i dati attuali e completa "
                "l'operazione richiesta.\n"
                "• Azzera Storico e rotazioni: crea un nuovo file vuoto. "
                "L'eventuale disposizione corrente resta aperta, ma non viene "
                "salvata automaticamente.\n"
                "• Annulla: non scrive alcun file.\n\n"
                f"Percorso atteso:\n{percorso_file}"
            ),
            messaggio_in_grassetto=True,
        )

        btn_ricrea = dialog.addButton(
            "Ricrea il file", QMessageBox.AcceptRole
        )
        btn_azzera = dialog.addButton(
            "Azzera Storico e rotazioni", QMessageBox.DestructiveRole
        )
        btn_annulla = dialog.addButton(
            "Annulla", QMessageBox.RejectRole
        )
        applica_icona(btn_ricrea, "file-plus-2", 18)
        applica_icona(btn_azzera, "trash-2", 18)
        applica_stile_pulsante_popup(btn_azzera, "distruttivo")
        applica_icona(btn_annulla, "x", 18)
        dialog.setDefaultButton(btn_ricrea)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()

        selezionato = dialog.clickedButton()
        if selezionato == btn_ricrea:
            return AZIONE_FILE_ASSENTE_RICREA
        if selezionato == btn_azzera:
            return AZIONE_FILE_ASSENTE_AZZERA
        return AZIONE_FILE_ASSENTE_ANNULLA

    def _dopo_azzeramento_storico_e_rotazioni(self) -> None:
        """Riallinea sessione e viste dopo la creazione del JSON vuoto."""
        self.sessione.mensile.scollega_dallo_storico()

        self._aggiorna_info_storico()
        self._aggiorna_tabella_storico()
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        for bottone, tooltip in (
            (
                self.btn_export_excel,
                "Salva prima l'assegnazione nello Storico per abilitare l'esportazione.",
            ),
            (
                self.btn_export_report_txt,
                "Salva prima l'assegnazione nello Storico per abilitare l'esportazione.",
            ),
        ):
            bottone.setEnabled(False)
            bottone.setToolTip(tooltip)

    def _mostra_avviso_recupero_json(self):
        """Mostra l’esito di un eventuale recupero automatico della configurazione."""
        avviso = self.config_app.avviso_recupero

        if not avviso:
            return

        titolo = avviso.get(
            "titolo",
            "Configurazione"
        )
        messaggio = avviso.get(
            "messaggio",
            "Si è verificato un problema con la configurazione."
        )
        gravita = avviso.get(
            "gravita",
            "avviso"
        )

        if gravita == "critico":
            mostra_popup_semantico(
                self,
                titolo,
                "La configurazione non è stata recuperata completamente.",
                "circle-x",
                testo_informativo=messaggio,
                messaggio_in_grassetto=True,
            )
        else:
            mostra_popup_semantico(
                self,
                titolo,
                "PostiPerfetti ha eseguito un recupero automatico.",
                "triangle-alert",
                testo_informativo=messaggio,
                messaggio_in_grassetto=True,
            )

        self.config_app.avviso_recupero = None


    def _mostra_istruzioni(self):
        """Apre la guida dell’applicazione."""
        mostra_istruzioni(self)


    def _carica_dati_iniziali(self):
        """Carica tema e stato persistente necessari all’avvio."""

        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        if tema_salvato == "chiaro":
            self.btn_toggle_tema.setText("Tema scuro")
            applica_icona(self.btn_toggle_tema, "moon", 18)
        else:
            self.btn_toggle_tema.setText("Tema chiaro")
            applica_icona(self.btn_toggle_tema, "sun", 18)

        self.setup_stili()

        aggiorna_icone_applicazione()

        self._ripristina_default_operativi()

        self._aggiorna_info_storico()

        self._aggiorna_posti_totali()

        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        self._aggiorna_tabella_storico()


    def _cambia_tema(self):
        """Alterna il tema, aggiorna i widget e salva la preferenza."""

        profilo = ProfiloGUI("cambio_tema")
        try:
            nuovo_tema = "chiaro" if get_tema() == "scuro" else "scuro"

            profilo.misura("imposta_tema", lambda: imposta_tema(nuovo_tema))
            profilo.misura("setup_stili", self.setup_stili)
            profilo.misura("stili_widget_principali", self._aggiorna_stili_widget)

            if hasattr(self, 'editor_studenti'):
                profilo.misura(
                    "editor_studenti",
                    self.editor_studenti.aggiorna_tema,
                )

            def aggiorna_filtro_classe():
                self.filtro_classe_combo.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {C("sfondo_input")};
                        color: {C("testo_principale")};
                        border: 2px solid {C("bordo_normale")};
                        border-radius: 4px;
                        padding: 6px;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {C("sfondo_input")};
                        color: {C("testo_principale")};
                        selection-background-color: {C("accento")};
                        selection-color: {C('selezione_testo')};
                        border: 1px solid {C("bordo_leggero")};
                    }}
                """)

            profilo.misura("filtro_classe", aggiorna_filtro_classe)

            profilo.misura("statistiche", self._aggiorna_statistiche)

            profilo.misura("tabella_storico", self._aggiorna_tabella_storico)

            def aggiorna_toggle_tema():
                if nuovo_tema == "chiaro":
                    self.btn_toggle_tema.setText("Tema scuro")
                    applica_icona(self.btn_toggle_tema, "moon", 18)
                else:
                    self.btn_toggle_tema.setText("Tema chiaro")
                    applica_icona(self.btn_toggle_tema, "sun", 18)

            profilo.misura("toggle_tema", aggiorna_toggle_tema)

            profilo.misura("icone_applicazione", aggiorna_icone_applicazione)

            profilo.misura(
                "programma_finestre_informative",
                lambda: QTimer.singleShot(
                    0, self._aggiorna_finestre_informative_aperte
                ),
            )

            self.config_app.config_data["tema"] = nuovo_tema
            profilo.misura(
                "salva_configurazione",
                self.config_app.salva_configurazione,
            )
        finally:
            profilo.chiudi()


    def _aggiorna_finestre_informative_aperte(self):
        """Aggiorna col tema corrente le finestre informative già aperte."""
        aggiorna_tema_finestre_informative(self)


    def _mostra_crediti(self):
        """Apre crediti e licenza."""
        mostra_crediti(self)


    def _mostra_aiuto_configurazione_aula(self):
        """Apre lo schema di aiuto per la configurazione dell’aula."""
        mostra_aiuto_configurazione_aula(self)


    def _mostra_errore(self, titolo: str, messaggio: str):
        """Mostra un errore con il protocollo visivo comune."""
        mostra_popup_semantico(
            self,
            titolo,
            messaggio,
            "circle-x",
            messaggio_in_grassetto=True,
        )


    def _controlla_classe_gia_elaborata(self, nome_file_classe):
        """Collega la classe caricata al relativo Storico e alle rotazioni."""
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        classe_trovata = False

        if self.sessione.file_origine and storico:
            classe_trovata = any(
                assegnazione.get("file_origine") == self.sessione.file_origine
                for assegnazione in storico
            )

        if not classe_trovata and storico:
            match = self._cerca_classe_per_fingerprint()
            if match:
                file_vecchio, nomi_comuni, totale = match
                classe_trovata = self._chiedi_ricollegamento_storico(
                    file_vecchio,
                    nomi_comuni,
                    totale,
                )

        if classe_trovata:
            self.label_status.setText(
                "Classe riconosciuta: pronta per rotazione"
            )
            self.label_status.setStyleSheet(
                f"color: {C('testo_stato_ok')}; font-weight: bold;"
            )
            QTimer.singleShot(15000, lambda: (
                self.label_status.setText("")
                if not self.timer_messaggi.isActive()
                else None
            ))


    def _cerca_classe_per_fingerprint(self):
        """Cerca nello Storico una classe simile associata a un nome file diverso."""
        if not self.sessione.studenti or not self.sessione.file_origine:
            return None

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if not storico:
            return None

        nomi_caricati = set()
        for studente in self.sessione.studenti:
            nomi_caricati.add(studente.get_nome_completo())

        classi_storico = {}
        for assegnazione in storico:
            fo = assegnazione.get("file_origine", "")
            if fo and fo != self.sessione.file_origine:

                if fo not in classi_storico:
                    classi_storico[fo] = []
                classi_storico[fo].append(assegnazione)

        soglia_minima = 5
        miglior_match = None
        max_nomi_comuni = 0

        for file_origine_vecchio, assegnazioni in classi_storico.items():

            ultima = assegnazioni[-1]
            layout = ultima.get("layout", [])

            nomi_storico = set()
            for entry in layout:
                nome = entry.get("studente", "")
                if nome:
                    nomi_storico.add(nome)

            nomi_comuni = nomi_caricati & nomi_storico

            if len(nomi_comuni) >= soglia_minima and len(nomi_comuni) > max_nomi_comuni:
                max_nomi_comuni = len(nomi_comuni)
                miglior_match = (file_origine_vecchio, nomi_comuni, len(nomi_storico))

        return miglior_match


    def _chiedi_ricollegamento_storico(self, file_origine_vecchio, nomi_in_comune, totale_storico):
        """Propone di ricollegare lo Storico a un file classe rinominato."""

        num_comuni = len(nomi_in_comune)
        num_caricati = len(self.sessione.studenti)

        elenco_nomi = "\n".join(
            f"• {nome}" for nome in sorted(nomi_in_comune)
        )

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        num_assegnazioni = sum(
            1 for a in storico
            if a.get("file_origine") == file_origine_vecchio
        )

        dialog = crea_popup_semantico(
            self,
            "Classe riconosciuta",
            "Vuoi ricollegare questa classe allo Storico riconosciuto?",
            "history",
            testo_informativo=(
                "File appena caricato:\n"
                f"  {self.sessione.file_origine}\n\n"
                "Classe storica riconosciuta:\n"
                f"  {file_origine_vecchio}\n\n"
                f"Corrispondenza: {quantita(num_comuni, 'studente', 'studenti')} "
                f"in comune su {num_caricati} nella classe caricata.\n"
                f"Da ricollegare: "
                f"{quantita(num_assegnazioni, 'assegnazione', 'assegnazioni')}.\n\n"
                "Confermando, le assegnazioni precedenti verranno associate "
                "al nuovo file e la rotazione continuerà tenendo conto delle "
                "vicinanze già formate."
            ),
            testo_dettagliato=(
                f"Nell'ultima assegnazione storica: "
                f"{quantita(totale_storico, 'studente', 'studenti')}.\n"
                f"Riconosciuti in comune: "
                f"{quantita(num_comuni, 'studente', 'studenti')}.\n\n"
                f"{elenco_nomi}"
            ),
            messaggio_in_grassetto=True,
        )

        btn_collega = dialog.addButton(
            "Ricollega lo Storico", QMessageBox.AcceptRole
        )
        btn_no = dialog.addButton(
            "È una classe diversa", QMessageBox.RejectRole
        )
        applica_icona(btn_collega, "history", 18)
        applica_icona(btn_no, "x", 18)

        dialog.setDefaultButton(btn_collega)
        dialog.setEscapeButton(btn_no)
        dialog.exec()

        if dialog.clickedButton() != btn_collega:
            return False

        configurazione_precedente = copy.deepcopy(
            self.config_app.config_data
        )
        assegnazioni_aggiornate = 0

        nome_vecchio_stem = os.path.splitext(file_origine_vecchio)[0]
        nome_nuovo_stem = os.path.splitext(self.sessione.file_origine)[0]

        for assegnazione in storico:
            if assegnazione.get("file_origine") == file_origine_vecchio:
                assegnazione["file_origine"] = self.sessione.file_origine

                nome_originale = assegnazione.get("nome", "")
                if nome_vecchio_stem.lower() in nome_originale.lower():

                    idx = nome_originale.lower().find(nome_vecchio_stem.lower())
                    if idx >= 0:
                        assegnazione["nome"] = (
                            nome_originale[:idx]
                            + nome_nuovo_stem
                            + nome_originale[idx + len(nome_vecchio_stem):]
                        )

                assegnazioni_aggiornate += 1

        if not self.config_app.salva_configurazione():
            if (
                self.config_app.ultimo_esito_salvataggio
                != ESITO_SALVATAGGIO_AZZERATO
            ):
                self.config_app.config_data = configurazione_precedente
            self._aggiorna_tabella_storico()
            self._popola_filtro_classi()
            return False

        print(f"🔗 Storico ricollegato: '{file_origine_vecchio}' → "
              f"'{self.sessione.file_origine}' ({assegnazioni_aggiornate} assegnazioni)")

        self._aggiorna_tabella_storico()

        self._popola_filtro_classi()

        return True


    def closeEvent(self, event):
        """Protegge i dati non salvati durante la chiusura dell’applicazione."""

        worker_mensile = getattr(self, 'worker_thread', None)
        worker_annuale = getattr(self, 'season_worker', None)

        mensile_in_corso = (
            worker_mensile is not None
            and worker_mensile.isRunning()
        )
        annuale_in_corso = (
            worker_annuale is not None
            and worker_annuale.isRunning()
        )

        if mensile_in_corso:
            mostra_popup_semantico(
                self,
                "Elaborazione in corso",
                "L'assegnazione Mensile è ancora in corso.",
                "triangle-alert",
                testo_informativo=(
                    "Per evitare un'interruzione brusca, la finestra non può "
                    "essere chiusa finché il calcolo non è terminato."
                ),
                messaggio_in_grassetto=True,
            )
            event.ignore()
            return

        if annuale_in_corso:

            if self.sessione.annuale.annullamento_richiesto:
                mostra_popup_semantico(
                    self,
                    "Annullamento in corso",
                    "L'annullamento è già stato richiesto.",
                    "info",
                    testo_informativo=(
                        "Attendi la conclusione del mese attualmente in calcolo; "
                        "poi potrai chiudere il programma in sicurezza."
                    ),
                    messaggio_in_grassetto=True,
                )
            else:
                dialog = crea_popup_semantico(
                    self,
                    "Elaborazione Annuale in corso",
                    "La preparazione Annuale è ancora in corso.",
                    "triangle-alert",
                    testo_informativo=(
                        "La finestra non verrà chiusa durante l'elaborazione. "
                        "Puoi restare nel programma oppure richiedere un "
                        "annullamento controllato."
                    ),
                    messaggio_in_grassetto=True,
                )

                btn_annulla_elaborazione = dialog.addButton(
                    "Annulla elaborazione",
                    QMessageBox.DestructiveRole
                )
                btn_resta = dialog.addButton(
                    "Resta nel programma",
                    QMessageBox.RejectRole
                )
                applica_icona(btn_annulla_elaborazione, "circle-stop", 18)
                applica_stile_pulsante_popup(
                    btn_annulla_elaborazione, "distruttivo"
                )
                dialog.setDefaultButton(btn_resta)
                dialog.setEscapeButton(btn_resta)
                dialog.exec()

                if dialog.clickedButton() == btn_annulla_elaborazione:
                    self._annulla_annuale()

            event.ignore()
            return

        if hasattr(self, 'editor_studenti'):
            if not self.editor_studenti.richiedi_conferma_chiusura():

                event.ignore()
                return

        if self.sessione.mensile.non_salvata:
            dialog_chiudi = crea_popup_semantico(
                self,
                "Assegnazione non salvata",
                "L'ultima assegnazione non è stata salvata nello Storico.",
                "triangle-alert",
                testo_informativo=(
                    "Se chiudi ora, le vicinanze formate non verranno considerate "
                    "nelle rotazioni future.\n\n"
                    "Che cosa vuoi fare?"
                ),
                messaggio_in_grassetto=True,
            )

            btn_salva_chiudi = dialog_chiudi.addButton(
                "Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_esci_chiudi = dialog_chiudi.addButton(
                "Chiudi senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_chiudi = dialog_chiudi.addButton(
                "Annulla", QMessageBox.RejectRole
            )
            applica_icona(btn_salva_chiudi, "save", 18)
            applica_icona(btn_esci_chiudi, "trash-2", 18)
            applica_stile_pulsante_popup(
                btn_esci_chiudi, "distruttivo"
            )
            applica_icona(btn_annulla_chiudi, "x", 18)

            dialog_chiudi.setDefaultButton(btn_salva_chiudi)

            dialog_chiudi.setEscapeButton(btn_annulla_chiudi)

            dialog_chiudi.exec()

            bottone_chiudi = dialog_chiudi.clickedButton()

            if bottone_chiudi == btn_salva_chiudi:

                self.salva_assegnazione()

                if self.sessione.mensile.non_salvata:
                    event.ignore()
                    return

            elif bottone_chiudi == btn_annulla_chiudi:

                event.ignore()
                return

        salvataggio_finale = self.config_app.salva_configurazione()

        if not salvataggio_finale:
            esito = self.config_app.ultimo_esito_salvataggio

            if esito == ESITO_SALVATAGGIO_AZZERATO:
                if self.sessione.mensile.non_salvata:
                    mostra_popup_semantico(
                        self,
                        "Storico azzerato",
                        "La disposizione corrente non è stata salvata.",
                        "triangle-alert",
                        testo_informativo=(
                            "PostiPerfetti resta aperto per permetterti di "
                            "salvarla come prima voce del nuovo Storico oppure "
                            "di chiuderla consapevolmente."
                        ),
                        messaggio_in_grassetto=True,
                    )
                    event.ignore()
                    return
            elif esito == ESITO_SALVATAGGIO_ERRORE:
                mostra_popup_semantico(
                    self,
                    "Chiusura non completata",
                    "Non è stato possibile salvare la configurazione.",
                    "circle-x",
                    testo_informativo=(
                        "Il programma resta aperto per evitare di perdere "
                        "modifiche ancora presenti in memoria."
                    ),
                    messaggio_in_grassetto=True,
                )
                event.ignore()
                return
            elif esito == ESITO_SALVATAGGIO_ANNULLATO:
                event.ignore()
                return

        event.accept()
