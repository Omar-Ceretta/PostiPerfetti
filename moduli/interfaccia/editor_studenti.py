# -*- coding: utf-8 -*-
"""Coordinamento dell’Editor: sessione, relazioni, caricamento e salvataggio.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QSizePolicy, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap
import os
from html import escape

from moduli.interfaccia.tema import C
from moduli.lingua import quantita
from moduli.processi.profilo_gui import ProfiloGUI


from moduli.percorsi import (
    get_resource_path,
    inizializza_cartella_classi,
)
from moduli.persistenza.file_classe import (
    FORMATO_BASE, FORMATO_COMPLETO, ErroreValidazioneFileClasse,
    analizza_coerenza_bidirezionale_dati, chiave_nome_completo, nomi_studenti_fissi, rimuovi_studente_e_vincoli,
    serializza_file_classe, scrivi_file_classe_atomico,
)


from moduli.interfaccia.utilita import (
    conta_vincoli, formato_vincoli,
    dettaglio_vincoli, formato_dettaglio_vincoli,
    ordina_studenti,
    adatta_finestra_allo_schermo,
    applica_icona, applica_stile_pulsante_popup, applica_icona_finestra,
    applica_icona_applicazione_finestra,
    applica_icona_etichetta, crea_popup_semantico, apri_file_con_applicazione_default,
)

from moduli.interfaccia.controlli_editor import (
    ComboBoxProtetto as ComboBoxProtetto, RigaVincolo as RigaVincolo,
    _misura_profilo,
)
from moduli.interfaccia.scheda_studente import SchedaStudente as SchedaStudente
from moduli.interfaccia.dialoghi_editor import (
    DialogoErroreFileClasse as DialogoErroreFileClasse,
    _popup_info, _popup_successo, _popup_avviso, _popup_errore,
    seleziona_file_classe,
)


from moduli.interfaccia.stili_editor import stylesheet_componenti_dinamici


class EditorStudentiWidget(QWidget):
    """Editor integrabile come scheda o finestra autonoma.

    Riconosce file base e completi, costruisce le schede, sincronizza i vincoli in
    entrambe le direzioni, controlla i dati pendenti e salva il file della classe.
    """


    # I segnali tengono allineati Editor e finestra principale.
    file_cambiato_signal = Signal()


    file_chiuso_signal = Signal()


    dati_modificati_signal = Signal()


    genere_cambiato_signal = Signal()


    file_salvato_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


        self._schede_studenti = []

        self._lista_nomi = []

        self._nome_file_caricato = ""

        self._percorso_file_caricato = ""


        # Guardia contro il rimbalzo infinito delle modifiche speculari.
        self._sincronizzazione_in_corso = False


        self._modifiche_non_salvate = False


        self._callback_pre_caricamento = None
        self._callback_pre_chiusura_file = None
        self._callback_pre_salvataggio = None


        self._correzioni_applicate = False


        # Lo stato vive per l’intera sessione, non per singola scheda.
        self._promemoria_livello_mostrato = {
            "incompatibilita": False,
            "affinita": False,
        }


        self._costruisci_ui()

        # Schede, righe dei vincoli e area di scorrimento ereditano il QSS
        # unico installato dalla finestra principale. Uno stylesheet locale
        # conserverebbe invece i colori del tema attivo all’avvio.

        self.dati_modificati_signal.connect(self._aggiorna_contatore_vincoli)

    def stylesheet_componenti(self):
        return stylesheet_componenti_dinamici()

    @property
    def percorso_file(self) -> str:
        return self._percorso_file_caricato

    @property
    def nome_file(self) -> str:
        return self._nome_file_caricato

    @property
    def ha_modifiche_non_salvate(self) -> bool:
        return self._modifiche_non_salvate

    @property
    def correzioni_applicate(self) -> bool:
        return self._correzioni_applicate

    def configura_protezioni(self, *, prima_caricamento, prima_chiusura,
                            prima_salvataggio=None):
        """Installa le decisioni della finestra senza esporre i campi interni."""
        self._callback_pre_caricamento = prima_caricamento
        self._callback_pre_chiusura_file = prima_chiusura
        self._callback_pre_salvataggio = prima_salvataggio

    def conferma_acquisizione_classe(self):
        """L’acquisizione non annulla correzioni ancora da scrivere."""
        if not self._correzioni_applicate:
            self._modifiche_non_salvate = False

    def conferma_salvataggio(self):
        """Segna persistite le modifiche soltanto dopo una scrittura riuscita."""
        self._modifiche_non_salvate = False
        self._correzioni_applicate = False

    def aggiorna_tema(self):
        """Riapplica il tema all’intero Editor."""

        profilo = ProfiloGUI("editor_tema_dettaglio")
        try:
            # Il QSS dei componenti ripetuti e della QScrollArea è globale:
            # qui restano soltanto i pochi stili inline non ereditabili.

            profilo.misura(
                "label_apri_info",
                lambda: self.label_apri_info.setStyleSheet(
                    f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
                ),
            )

            self._aggiorna_stili_bottoni_editor(profilo=profilo)

            profilo.misura(
                "banner_formato_base",
                lambda: self._banner_formato_base.setStyleSheet(f"""
                    background-color: {C("label_attenzione_bg")};
                    border-radius: 6px;
                    border: 1px solid {C("label_attenzione_bordo")};
                """),
            )
            profilo.misura(
                "banner_formato_base_testo",
                lambda: self._banner_formato_base_testo.setStyleSheet(f"""
                    color: {C("banner_formato_txt")};
                    font-weight: bold;
                    font-size: 13px;
                """),
            )

            if self._schede_studenti:
                self._aggiorna_contatore_vincoli(profilo=profilo)
        finally:
            profilo.chiudi()

    def _aggiorna_stili_bottoni_editor(self, profilo=None):
        """Aggiorna gli stili dei comandi dell’Editor."""

        def applica(nome, widget, css):
            return _misura_profilo(
                profilo,
                f"bottone_{nome}",
                lambda: widget.setStyleSheet(css),
            )

        def stile(bg, hover, testo, bordo, *, font_size=13,
                  padding="6px 10px", raggio=6, disabilitato=True):
            css = f"""
                QPushButton {{
                    background-color: {bg};
                    color: {testo};
                    border: 1px solid {bordo};
                    font-size: {font_size}px;
                    font-weight: bold;
                    border-radius: {raggio}px;
                    padding: {padding};
                }}
                QPushButton:hover {{
                    background-color: {hover};
                    border-color: {bordo};
                }}
            """
            if disabilitato:
                css += f"""
                QPushButton:disabled {{
                    background-color: {C('btn_azione_disabled_bg')};
                    color: {C('btn_azione_disabled_txt')};
                    border-color: {C('btn_azione_disabled_bordo')};
                }}
                """
            return css

        applica("apri_cartella", self.btn_apri_cartella, stile(
            C("editor_btn_cartella_bg"),
            C("editor_btn_cartella_hover"),
            C("editor_btn_cartella_txt"),
            C("editor_btn_cartella_bordo"),
        ))
        applica("carica", self.btn_carica, stile(
            C("editor_btn_classe_bg"),
            C("editor_btn_classe_hover"),
            C("editor_btn_classe_txt"),
            C("editor_btn_classe_bordo"),
        ))
        applica("aggiungi_studente", self.btn_aggiungi_studente, stile(
            C("btn_indaco_bg"),
            C("btn_indaco_hover"),
            C("btn_indaco_txt"),
            C("btn_indaco_bordo"),
        ))
        applica("esporta", self.btn_esporta, stile(
            C("btn_salva_bg"), C("btn_salva_hover"),
            C("btn_salva_txt"), C("btn_salva_bordo"),
        ))

        stile_neutro = stile(
            C("editor_btn_neutro_bg"),
            C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"),
            C("editor_btn_neutro_bordo"),
            font_size=12, raggio=5,
        )
        applica("toggle_schede", self.btn_toggle_schede, stile_neutro)
        applica("dettaglio_vincoli", self._btn_dettaglio_vincoli, stile_neutro)

        applica("preview", self.btn_preview, stile(
            C("btn_indaco_bg"), C("btn_indaco_hover"),
            C("btn_indaco_txt"), C("btn_indaco_bordo"),
            padding="10px 20px",
        ))
        applica("chiudi", self.btn_chiudi, stile(
            C("editor_btn_neutro_bg"),
            C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"),
            C("editor_btn_neutro_bordo"),
            padding="10px 20px",
        ))

    def _popola_placeholder_file_non_selezionato(self):
        """Mostra lo stato iniziale senza una classe caricata."""
        self._logo_placeholder = QLabel()
        percorso_logo = get_resource_path(
            "icone",
            "postiperfetti_logo.png",
        )

        if os.path.exists(percorso_logo):
            pixmap = QPixmap(percorso_logo)
            pixmap = pixmap.scaled(
                496,
                336,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._logo_placeholder.setPixmap(pixmap)
        else:

            self._logo_placeholder.setText("«PostiPerfetti»")
            self._logo_placeholder.setStyleSheet("font-size: 36px;")

        self._logo_placeholder.setAlignment(Qt.AlignCenter)

        self._label_placeholder = QLabel(
            "NESSUN FILE SELEZIONATO.\n\n"
            "• Clicca su 'Apri cartella' per creare un nuovo file classe in formato BASE con\n"
            "'Cognome;Nome;M/F' degli allievi (uno per riga; l'Editor li riordina automaticamente).\n\n"
            "• Clicca su 'Seleziona classe' per modificare posizione e vincoli degli studenti\n"
            "di una classe presente in un file testuale già creato in precedenza.\n\n"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 20px;"
        )


        self.layout_schede.addStretch()
        self.layout_schede.addWidget(
            self._logo_placeholder,
            alignment=Qt.AlignHCenter
        )
        self.layout_schede.addSpacing(12)
        self.layout_schede.addWidget(self._label_placeholder)
        self.layout_schede.addStretch()

    def _costruisci_ui(self):
        """Costruisce l’interfaccia dell’Editor."""

        layout_principale = QVBoxLayout(self)
        layout_principale.setSpacing(10)


        header = QHBoxLayout()


        self.btn_apri_cartella = QPushButton("Apri cartella")
        applica_icona(self.btn_apri_cartella, "folder-open", 18)
        self.btn_apri_cartella.setMinimumHeight(40)
        self.btn_apri_cartella.setToolTip(
            "Apre la cartella delle classi nel file manager del sistema.\n"
            "Qui puoi creare un nuovo file di testo con la lista degli studenti."
        )
        self.btn_apri_cartella.clicked.connect(self._apri_cartella_classi)
        header.addWidget(self.btn_apri_cartella)


        self.label_apri_info = QLabel("CREA qui la classe")
        self.label_apri_info.setStyleSheet(
            f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
        )
        header.addWidget(self.label_apri_info)

        header.addSpacing(8)


        self.btn_carica = QPushButton("Seleziona classe")
        applica_icona(self.btn_carica, "file-search-corner", 18)
        self.btn_carica.setMinimumHeight(40)
        self.btn_carica.setToolTip(
            "Seleziona un file di testo dalla cartella classi\n"
            "per modificare posizione e vincoli degli studenti"
        )
        self.btn_carica.clicked.connect(self._carica_file)
        header.addWidget(self.btn_carica)

        header.addSpacing(8)

        self.btn_esporta = QPushButton("SALVA e CARICA")
        applica_icona(self.btn_esporta, "save", 18)
        self.btn_esporta.setMinimumHeight(40)
        self.btn_esporta.setEnabled(False)
        self.btn_esporta.setToolTip("Salva il file completo con tutti i dati e vincoli degli studenti")
        self.btn_esporta.clicked.connect(self._esporta_file)
        header.addWidget(self.btn_esporta)


        header.addStretch()

        self.btn_aggiungi_studente = QPushButton("Aggiungi studente")
        applica_icona(self.btn_aggiungi_studente, "plus", 18)
        self.btn_aggiungi_studente.setMinimumHeight(45)
        self.btn_aggiungi_studente.setMinimumWidth(190)
        self.btn_aggiungi_studente.setEnabled(False)
        self.btn_aggiungi_studente.setVisible(False)
        self.btn_aggiungi_studente.setToolTip(
            "Aggiunge un nuovo studente alla classe aperta. "
            "Nascerà con posizione NORMALE e senza vincoli."
        )
        self.btn_aggiungi_studente.clicked.connect(self._aggiungi_studente_editor)

        layout_principale.addLayout(header)


        self._dati_riga_info = None

        self.label_contatore_vincoli = QLabel("")
        self.label_contatore_vincoli.setTextFormat(Qt.RichText)
        self.label_contatore_vincoli.setWordWrap(True)
        self.label_contatore_vincoli.setStyleSheet("font-size: 14px;")
        self.label_contatore_vincoli.setVisible(False)


        self._schede_tutte_espanse = False
        self.btn_toggle_schede = QPushButton("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setMinimumHeight(36)
        self.btn_toggle_schede.setMinimumWidth(190)
        self.btn_toggle_schede.setEnabled(False)
        self.btn_toggle_schede.setVisible(False)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.clicked.connect(self._alterna_schede)

        self._btn_dettaglio_vincoli = QPushButton("Dettaglio vincoli")
        applica_icona(self._btn_dettaglio_vincoli, "list-tree", 16)
        self._btn_dettaglio_vincoli.setMinimumHeight(36)
        self._btn_dettaglio_vincoli.setMinimumWidth(190)
        self._btn_dettaglio_vincoli.setToolTip(
            "Mostra l'elenco completo dei vincoli (con i nomi), raggruppato per categoria"
        )
        self._btn_dettaglio_vincoli.setVisible(False)
        self._btn_dettaglio_vincoli.clicked.connect(self._mostra_dettaglio_vincoli)


        self.label_contatore_vincoli.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        colonna_azioni_vincoli = QVBoxLayout()
        colonna_azioni_vincoli.setSpacing(6)
        colonna_azioni_vincoli.addStretch(1)
        colonna_azioni_vincoli.addWidget(self.btn_toggle_schede)
        colonna_azioni_vincoli.addWidget(self._btn_dettaglio_vincoli)
        colonna_azioni_vincoli.addStretch(1)

        riga_contatore = QHBoxLayout()
        riga_contatore.setSpacing(10)
        riga_contatore.addWidget(self.label_contatore_vincoli, 1)
        riga_contatore.addLayout(colonna_azioni_vincoli)
        layout_principale.addLayout(riga_contatore)


        self._banner_formato_base = QWidget()
        layout_banner_base = QHBoxLayout(self._banner_formato_base)
        layout_banner_base.setContentsMargins(12, 9, 12, 9)
        layout_banner_base.setSpacing(10)

        self._banner_formato_base_icona = QLabel()
        self._banner_formato_base_icona.setFixedSize(26, 26)
        self._banner_formato_base_icona.setAlignment(Qt.AlignCenter)
        applica_icona_etichetta(
            self._banner_formato_base_icona, "triangle-alert", 22
        )
        layout_banner_base.addWidget(
            self._banner_formato_base_icona, alignment=Qt.AlignTop
        )

        self._banner_formato_base_testo = QLabel(
            "FORMATO BASE — Verifica genere e posizione di ogni "
            "studente, e imposta le necessarie incompatibilità "
            "e affinità (di livello 1, 2 o 3). "
            "Clicca infine su «SALVA e CARICA»."
        )
        self._banner_formato_base_testo.setWordWrap(True)
        layout_banner_base.addWidget(self._banner_formato_base_testo, 1)

        self._banner_formato_base.setStyleSheet(f"""
            background-color: {C("label_attenzione_bg")};
            border-radius: 6px;
            border: 1px solid {C("label_attenzione_bordo")};
        """)
        self._banner_formato_base_testo.setStyleSheet(f"""
            color: {C("banner_formato_txt")};
            font-weight: normal;
            font-size: 14px;
        """)
        self._banner_formato_base.setVisible(False)
        layout_principale.addWidget(self._banner_formato_base)


        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setProperty("editorRuolo", "scroll_area")

        self.widget_scroll = QWidget()
        self.layout_schede = QVBoxLayout(self.widget_scroll)
        self.layout_schede.setSpacing(12)
        self.layout_schede.setContentsMargins(10, 10, 10, 10)


        self._popola_placeholder_file_non_selezionato()
        self.scroll_area.setWidget(self.widget_scroll)


        layout_principale.addWidget(self.scroll_area, 1)


        footer = QHBoxLayout()
        footer.setSpacing(12)


        self.btn_preview = QPushButton("Anteprima file classe (.txt)")
        applica_icona(self.btn_preview, "eye", 18)
        self.btn_preview.setMinimumHeight(45)
        self.btn_preview.setEnabled(False)
        self.btn_preview.setToolTip("Mostra un'anteprima del file .txt che verrà generato")
        self.btn_preview.clicked.connect(self._mostra_preview)
        footer.addWidget(self.btn_preview, alignment=Qt.AlignLeft)

        # Tre colonne uguali tengono l'aggiunta al centro anche con testi
        # di lunghezza diversa nei pulsanti laterali.
        footer.addWidget(self.btn_aggiungi_studente, alignment=Qt.AlignHCenter)


        self.btn_chiudi = QPushButton("CHIUDI FILE")
        applica_icona(self.btn_chiudi, "x", 18)
        self.btn_chiudi.setMinimumHeight(45)
        self.btn_chiudi.setEnabled(False)
        self.btn_chiudi.setToolTip(
            "Chiudi il file corrente (protegge modifiche e assegnazioni non salvate)"
        )
        self.btn_chiudi.clicked.connect(self._chiudi_editor)
        footer.addWidget(self.btn_chiudi, alignment=Qt.AlignRight)
        for colonna in range(3):
            footer.setStretch(colonna, 1)
        layout_principale.addLayout(footer)
        QWidget.setTabOrder(self.btn_preview, self.btn_aggiungi_studente)
        QWidget.setTabOrder(self.btn_aggiungi_studente, self.btn_chiudi)


        self._aggiorna_stili_bottoni_editor()


    def _carica_file(self):
        """Seleziona e valida transazionalmente un file di classe."""
        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se selezioni un'altra classe ora, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return

        if self._callback_pre_caricamento is not None:
            if not self._callback_pre_caricamento():
                return

        if self._modifiche_non_salvate:
            azione = self._conferma_chiusura()
            if azione == "salva":
                self._esporta_file()
                if self._modifiche_non_salvate:
                    return
            elif azione == "annulla":
                return

        caricato = seleziona_file_classe(self, self._get_cartella_classi())
        if caricato is None:
            return
        percorso, risultato = caricato

        # Soltanto un risultato completamente validato e accettato sostituisce la classe aperta.
        self._nome_file_caricato = os.path.splitext(os.path.basename(percorso))[0]
        self._percorso_file_caricato = percorso
        formato = risultato["formato"]

        if formato == FORMATO_COMPLETO:
            self._correzioni_applicate = bool(
                risultato["avvisi"]
                or risultato["vincoli_aggiunti"]
                or risultato.get("vincoli_orfani")
                or risultato.get("studenti_base_promossi")
                or risultato.get("codifica_legacy")
            )
            self._popola_editor(risultato["studenti"], FORMATO_COMPLETO)

            studenti_base_promossi = list(
                risultato.get("studenti_base_promossi", [])
            )
            if studenti_base_promossi:
                elenco = "\n".join(
                    f"  • {nome}" for nome in studenti_base_promossi
                )
                numero = len(studenti_base_promossi)
                if numero == 1:
                    messaggio = "È stato trovato 1 studente scritto nel formato base."
                    descrizione_caricamento = (
                        "È stato caricato con posizione NORMALE e senza vincoli. "
                    )
                else:
                    messaggio = (
                        f"Sono stati trovati {numero} studenti scritti nel formato base."
                    )
                    descrizione_caricamento = (
                        "Sono stati caricati con posizione NORMALE e senza vincoli. "
                    )
                _popup_info(
                    self,
                    "File normalizzato",
                    messaggio,
                    dettagli=(
                        f"{elenco}\n\n"
                        + descrizione_caricamento
                        + "Puoi completarne i dati nell'Editor prima di salvare.\n\n"
                        + "Con «SALVA e CARICA» il file verrà riscritto nel "
                        "formato completo canonico."
                    ),
                )

            segnalazioni = list(risultato["avvisi"])
            for vincolo in risultato["vincoli_aggiunti"]:
                tipo_visibile = (
                    "Incompatibilità"
                    if vincolo["tipo"] == "incompatibilita"
                    else "Affinità"
                )
                segnalazioni.append(
                    f"{tipo_visibile}: aggiunto il vincolo speculare: "
                    f"{vincolo['target']} → {vincolo['sorgente']} "
                    f"(livello {vincolo['livello']})."
                )

            if segnalazioni:
                testo = "\n".join(f"• {voce}" for voce in segnalazioni[:20])
                if len(segnalazioni) > 20:
                    testo += (
                        f"\n\n... e altre {len(segnalazioni) - 20} "
                        "segnalazioni."
                    )
                _popup_info(
                    self,
                    "Normalizzazioni sicure applicate",
                    "Il file è stato caricato con alcune correzioni automatiche sicure.",
                    dettagli=testo,
                )
        else:
            self._correzioni_applicate = False
            self._popola_editor(risultato["studenti"], FORMATO_BASE)

        self.file_cambiato_signal.emit()


    def _popola_editor(self, studenti_dati, formato):
        """Crea le schede a partire dai dati validati."""


        studenti_dati, riordino_avvenuto = ordina_studenti(studenti_dati)


        if riordino_avvenuto:
            QTimer.singleShot(0, self, lambda: _popup_info(
                                             self,
                                             "Elenco riordinato",
                                             "L'elenco studenti è stato riordinato alfabeticamente.",
                                             dettagli=(
                                                 "È cambiato soltanto l'ordine di visualizzazione; "
                                                 "nessun altro dato è stato modificato."
                                             ),
                                         ))


        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()


        if self._label_placeholder:
            self._label_placeholder.setParent(None)
            self._label_placeholder.deleteLater()
            self._label_placeholder = None


        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()


        self._lista_nomi = [f"{s['cognome']} {s['nome']}" for s in studenti_dati]


        for dati in studenti_dati:
            scheda = SchedaStudente(
                cognome=dati["cognome"],
                nome=dati["nome"],
                tutti_studenti=self._lista_nomi,
                sesso=dati["sesso"],
                posizione=dati["posizione"],
                incompatibilita=dati["incompatibilita"],
                affinita=dati["affinita"],
                stato_promemoria_livello=self._promemoria_livello_mostrato
            )


            scheda.vincolo_modificato_signal.connect(self._sincronizza_vincolo)
            scheda.elimina_studente_signal.connect(self._elimina_studente_editor)


            scheda.combo_genere.currentTextChanged.connect(
                lambda _: (
                    self._segna_modificato(),
                    self.genere_cambiato_signal.emit(),
                    self._aggiorna_contatore_vincoli(),
                )
            )


            scheda.combo_posizione.currentTextChanged.connect(
                lambda _, s=scheda: self._on_posizione_cambiata_editor(s)
            )

            self.layout_schede.addWidget(scheda)
            self._schede_studenti.append(scheda)


        self.layout_schede.addStretch()


        self.btn_preview.setEnabled(True)
        self.btn_esporta.setEnabled(True)
        self.btn_aggiungi_studente.setEnabled(True)
        self.btn_aggiungi_studente.setVisible(True)
        self._schede_tutte_espanse = False
        self.btn_toggle_schede.setText("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.setEnabled(True)
        self.btn_chiudi.setEnabled(True)


        if formato == "BASE":
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True
        else:


            self._modifiche_non_salvate = self._correzioni_applicate


        if formato == "BASE":

            descrizione_formato = "formato BASE"


            self._banner_formato_base.setVisible(True)


            _popup_info(
                self,
                "File in formato base",
                f"Il file «{self._nome_file_caricato}.txt» contiene solo\n"
                "cognome, nome e genere degli allievi.",
                dettagli=(
                    "Prima di usare «SALVA e CARICA», verifica il genere\n"
                    "e la posizione di ciascuno studente. Imposta quindi\n"
                    "le necessarie incompatibilità e affinità:\n\n"
                    "  • posizione (PRIMA, NORMALE, ULTIMA o FISSO)\n"
                    "  • incompatibilità (di livello 1, 2 o 3)\n"
                    "  • affinità (di livello 1, 2 o 3)\n\n"
                    "Senza vincoli, l'assegnazione sarà basata soltanto\n"
                    "sulle regole generali. Potrai comunque aggiungerli\n"
                    "o modificarli in seguito, riselezionando il file."
                ),
            )
        else:

            descrizione_formato = "formato COMPLETO"

            self._banner_formato_base.setVisible(False)


        self._dati_riga_info = {
            "nome": self._nome_file_caricato,
            "num": len(studenti_dati),
            "formato": descrizione_formato,
        }


        if formato == "COMPLETO":
            self._controlla_anomalie_editor()


        self._aggiorna_contatore_vincoli()


    def _aggiungi_studente_editor(self) -> None:
        """Aggiunge uno studente senza richiedere modifiche manuali al .txt."""
        if not self._schede_studenti:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Aggiungi studente")
        applica_icona_finestra(dialog, "plus")
        layout = QVBoxLayout(dialog)

        info = QLabel(
            "Il nuovo studente verrà aggiunto con posizione NORMALE e senza "
            "affinità o incompatibilità. Potrai modificare tutto dalla sua scheda."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        riga_cognome = QHBoxLayout()
        riga_cognome.addWidget(QLabel("Cognome:"))
        input_cognome = QLineEdit()
        riga_cognome.addWidget(input_cognome, 1)
        layout.addLayout(riga_cognome)

        riga_nome = QHBoxLayout()
        riga_nome.addWidget(QLabel("Nome:"))
        input_nome = QLineEdit()
        riga_nome.addWidget(input_nome, 1)
        layout.addLayout(riga_nome)

        riga_genere = QHBoxLayout()
        riga_genere.addWidget(QLabel("Genere:"))
        combo_genere = QComboBox()
        combo_genere.addItems(["M", "F"])
        combo_genere.setFixedWidth(90)
        riga_genere.addWidget(combo_genere)
        riga_genere.addStretch()
        layout.addLayout(riga_genere)

        bottoni = QDialogButtonBox()
        btn_annulla = bottoni.addButton("Annulla", QDialogButtonBox.RejectRole)
        btn_aggiungi = bottoni.addButton("Aggiungi studente", QDialogButtonBox.AcceptRole)
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_aggiungi, "plus", 18)
        bottoni.rejected.connect(dialog.reject)
        bottoni.accepted.connect(dialog.accept)
        layout.addWidget(bottoni)
        input_cognome.setFocus()

        while dialog.exec() == QDialog.Accepted:
            cognome = " ".join(input_cognome.text().split())
            nome = " ".join(input_nome.text().split())
            if not cognome or not nome:
                _popup_avviso(
                    self,
                    "Dati incompleti",
                    "Cognome e nome devono essere entrambi presenti.",
                )
                continue
            if "_" in cognome or "_" in nome:
                _popup_avviso(
                    self,
                    "Nome non valido",
                    "Cognome e nome non possono contenere il carattere underscore (_).",
                    dettagli="Usa uno spazio oppure un trattino.",
                )
                continue

            nome_completo = f"{cognome} {nome}"
            esistenti = {
                chiave_nome_completo(scheda.nome_completo)
                for scheda in self._schede_studenti
            }
            if chiave_nome_completo(nome_completo) in esistenti:
                _popup_avviso(
                    self,
                    "Studente già presente",
                    f"«{nome_completo}» è già presente nella classe.",
                )
                continue

            dati = self.get_dati_tutti_studenti()
            dati.append({
                "cognome": cognome,
                "nome": nome,
                "sesso": combo_genere.currentText(),
                "posizione": "NORMALE",
                "incompatibilita": {},
                "affinita": {},
            })
            self._popola_editor(dati, FORMATO_COMPLETO)
            self._segna_modificato()
            _popup_info(
                self,
                "Studente aggiunto",
                f"{nome_completo} è stato aggiunto alla classe.",
                dettagli=(
                    "Ricorda di usare «SALVA e CARICA» per aggiornare il file .txt "
                    "e la classe attiva in PostiPerfetti."
                ),
            )
            return

    def _elimina_studente_editor(self, nome_completo: str) -> None:
        """Rimuove uno studente e pulisce i vincoli che lo referenziano."""
        if len(self._schede_studenti) <= 1:
            _popup_avviso(
                self,
                "Impossibile eliminare lo studente",
                "La classe deve contenere almeno uno studente.",
            )
            return

        dati_correnti = self.get_dati_tutti_studenti()
        try:
            nuovi_dati, riferimenti = rimuovi_studente_e_vincoli(
                dati_correnti,
                nome_completo,
            )
        except ValueError as errore:
            _popup_errore(
                self,
                "Eliminazione non riuscita",
                "Lo studente selezionato non è più presente nell'Editor.",
                dettagli=str(errore),
            )
            return

        n_riferimenti = len(riferimenti)
        dettaglio = (
            f"Verranno rimossi anche {n_riferimenti} "
            f"{'riferimento' if n_riferimenti == 1 else 'riferimenti'} ai suoi "
            "vincoli dalle schede degli altri studenti.\n\n"
            "Le assegnazioni già salvate nello Storico non verranno modificate."
        )
        conferma = crea_popup_semantico(
            self,
            "Eliminare lo studente?",
            f"Stai per eliminare {nome_completo} dalla classe.",
            "triangle-alert",
            testo_informativo=dettaglio,
            messaggio_in_grassetto=True,
        )
        btn_annulla = conferma.addButton("Annulla", QMessageBox.RejectRole)
        btn_elimina = conferma.addButton("Elimina studente", QMessageBox.DestructiveRole)
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_elimina, "trash-2", 18)
        applica_stile_pulsante_popup(btn_elimina, "distruttivo")
        conferma.setDefaultButton(btn_annulla)
        conferma.setEscapeButton(btn_annulla)
        conferma.exec()
        if conferma.clickedButton() != btn_elimina:
            return

        self._popola_editor(nuovi_dati, FORMATO_COMPLETO)
        self._segna_modificato()
        _popup_info(
            self,
            "Studente eliminato",
            f"{nome_completo} è stato rimosso dalla classe.",
            dettagli=(
                f"Riferimenti ai suoi vincoli rimossi: {n_riferimenti}.\n\n"
                "Usa «SALVA e CARICA» per aggiornare il file .txt e la classe "
                "attiva in PostiPerfetti."
            ),
        )

    def _alterna_schede(self):
        """Espande o comprime tutte le schede."""
        if self._schede_tutte_espanse:
            self._comprimi_tutti()
            self._schede_tutte_espanse = False
            self.btn_toggle_schede.setText("Espandi schede")
            applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
            self.btn_toggle_schede.setToolTip(
                "Espandi tutte le schede per vedere i dettagli"
            )
        else:
            self._espandi_tutti()
            self._schede_tutte_espanse = True
            self.btn_toggle_schede.setText("Comprimi schede")
            applica_icona(self.btn_toggle_schede, "fold-vertical", 16)
            self.btn_toggle_schede.setToolTip(
                "Comprimi tutte le schede per una visione d'insieme"
            )

    def _espandi_tutti(self):
        """Espande tutte le schede."""
        for scheda in self._schede_studenti:
            scheda._espanso = True
            scheda._contenitore.setVisible(True)
            scheda.setTitle(scheda.nome_completo)

    def _comprimi_tutti(self):
        """Comprime tutte le schede."""
        for scheda in self._schede_studenti:
            scheda._espanso = False
            scheda._contenitore.setVisible(False)
            scheda.setTitle(scheda.nome_completo)


    def get_vincoli_incompleti(self):
        """Restituisce le relazioni prive del compagno o del livello.

        La stessa guardia viene usata prima del salvataggio, della chiusura e
        dell’avvio dell’assegnazione.
        """
        vincoli_incompleti = []
        for scheda in self._schede_studenti:

            for riga in scheda._righe_incompatibilita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(incompatibilità senza livello)"
                    )

            for riga in scheda._righe_affinita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(affinità senza livello)"
                    )
        return vincoli_incompleti

    def _segna_modificato(self):
        """Registra modifiche non salvate e le comunica alla finestra principale."""
        self._modifiche_non_salvate = True
        self.dati_modificati_signal.emit()

    def _on_posizione_cambiata_editor(self, scheda_modificata):
        """Accetta una posizione valida e annulla un secondo FISSO."""
        dati = scheda_modificata.get_dati()
        if dati["posizione"] != "FISSO":
            scheda_modificata.conferma_posizione_corrente()
            self._segna_modificato()
            return

        studenti_fisso = [
            scheda.nome_completo
            for scheda in self._schede_studenti
            if scheda.get_dati()["posizione"] == "FISSO"
        ]
        if len(studenti_fisso) <= 1:
            scheda_modificata.conferma_posizione_corrente()
            self._segna_modificato()
            return

        scheda_modificata.ripristina_posizione_confermata()
        elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
        _popup_avviso(
            self,
            "Troppi studenti con posizione FISSO",
            "Al massimo uno studente può avere posizione FISSO.",
            dettagli=(
                f"La modifica è stata annullata. Prima del ripristino erano "
                f"{quantita(len(studenti_fisso), 'studente', 'studenti')} "
                f"con posizione FISSO:\n\n{elenco}"
            ),
        )


    def _sincronizza_vincolo(self, studente_a, studente_b, tipo, livello, azione):
        """Mantiene identiche le due direzioni di una relazione.

        Aggiunge, aggiorna o rimuove la copia speculare senza riattivare ricorsivamente
        i segnali dell’Editor.
        """

        # Le copie programmatiche non devono generare una nuova sincronizzazione.
        if self._sincronizzazione_in_corso:
            return


        if azione == "incompleto":
            self.dati_modificati_signal.emit()
            return


        if azione == "rimosso_incompleto":
            self.dati_modificati_signal.emit()
            return


        self._sincronizzazione_in_corso = True
        try:

            scheda_b = self._trova_scheda(studente_b)
            if not scheda_b:
                print(f"⚠️ Sincronizzazione: scheda '{studente_b}' non trovata")
            else:

                if azione == "aggiungi":
                    scheda_b.aggiungi_vincolo_programmatico(
                        tipo,
                        studente_a,
                        livello
                    )
                elif azione == "modifica":
                    scheda_b.modifica_vincolo_programmatico(
                        tipo,
                        studente_a,
                        livello
                    )
                elif azione == "rimuovi":
                    scheda_b.rimuovi_vincolo_programmatico(
                        tipo,
                        studente_a
                    )
        finally:

            self._sincronizzazione_in_corso = False


        self._segna_modificato()

    def _trova_scheda(self, nome_completo):
        """Trova la scheda associata a un nome completo."""
        for scheda in self._schede_studenti:
            if scheda.nome_completo == nome_completo:
                return scheda
        return None

    def _controlla_anomalie_editor(self):
        """Completa i vincoli sicuri e segnala anomalie da correggere nell'Editor."""
        dati_correnti = self.get_dati_tutti_studenti()
        coerenza = analizza_coerenza_bidirezionale_dati(
            dati_correnti,
            completa_mancanti=True,
        )

        vincoli_aggiunti = coerenza["vincoli_aggiunti"]
        contraddizioni = coerenza["contraddizioni"]
        discordanze_livello = coerenza["discordanze_livello"]
        studenti_fissi = nomi_studenti_fissi(dati_correnti)

        for vincolo in vincoli_aggiunti:
            scheda_target = self._trova_scheda(vincolo["target"])
            if scheda_target is not None:
                scheda_target.aggiungi_vincolo_programmatico(
                    vincolo["tipo"],
                    vincolo["sorgente"],
                    vincolo["livello"],
                )

        if contraddizioni or discordanze_livello or len(studenti_fissi) > 1:
            sezioni = []
            if len(studenti_fissi) > 1:
                righe = [
                    f"Trovati {quantita(len(studenti_fissi), 'studente', 'studenti')} "
                    "con posizione FISSO.",
                    "",
                    "Al massimo uno studente può avere posizione FISSO. "
                    "Modifica le posizioni nelle schede prima di salvare e usare la classe.",
                    "",
                ]
                righe.extend(f"• {nome}" for nome in studenti_fissi)
                sezioni.append("\n".join(righe))

            if contraddizioni:
                verbo = "Trovata" if len(contraddizioni) == 1 else "Trovate"
                righe = [
                    f"{verbo} {quantita(len(contraddizioni), 'contraddizione', 'contraddizioni')}.",
                    "",
                    "Le coppie seguenti hanno vincoli opposti. Decidi nell'Editor "
                    "quale relazione mantenere e rimuovi manualmente quella errata.",
                    "",
                ]
                righe.extend(contraddizioni[:10])
                if len(contraddizioni) > 10:
                    residue = len(contraddizioni) - 10
                    righe.append(
                        "... e "
                        + (
                            "un’altra contraddizione"
                            if residue == 1
                            else f"altre {residue} contraddizioni"
                        )
                    )
                sezioni.append("\n".join(righe))

            if discordanze_livello:
                verbo = "Trovata" if len(discordanze_livello) == 1 else "Trovate"
                righe = [
                    f"{verbo} {quantita(len(discordanze_livello), 'coppia', 'coppie')} "
                    "con livelli diversi.",
                    "",
                    "Allinea manualmente i livelli nelle due schede interessate.",
                    "",
                ]
                righe.extend(discordanze_livello[:10])
                if len(discordanze_livello) > 10:
                    residue = len(discordanze_livello) - 10
                    righe.append(
                        "... e "
                        + (
                            "un’altra coppia"
                            if residue == 1
                            else f"altre {residue} coppie"
                        )
                    )
                sezioni.append("\n".join(righe))

            if (
                hasattr(self, "_dialog_anomalie")
                and self._dialog_anomalie is not None
                and self._dialog_anomalie.isVisible()
            ):
                self._dialog_anomalie.raise_()
                self._dialog_anomalie.activateWindow()
                return

            self._dialog_anomalie = QDialog(self)
            dialog = self._dialog_anomalie
            dialog.setWindowTitle("Anomalie nel file classe")
            applica_icona_applicazione_finestra(dialog)
            adatta_finestra_allo_schermo(
                dialog,
                larghezza_ideale=650,
                altezza_ideale=450,
                larghezza_minima=520,
                altezza_minima=320,
            )

            layout_d = QVBoxLayout(dialog)
            header_anomalie = QHBoxLayout()
            icona_anomalie = QLabel()
            applica_icona_etichetta(icona_anomalie, "triangle-alert", 36)
            header_anomalie.addWidget(icona_anomalie, 0, Qt.AlignTop)

            testo_header = QLabel(
                "Sono state rilevate anomalie che richiedono una correzione manuale."
            )
            testo_header.setWordWrap(True)
            testo_header.setStyleSheet("font-size: 14px; font-weight: bold;")
            header_anomalie.addWidget(testo_header, 1)
            layout_d.addLayout(header_anomalie)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Segoe UI", 11))
            text_edit.setPlainText(("\n\n" + "─" * 50 + "\n\n").join(sezioni))
            layout_d.addWidget(text_edit)

            btn_chiudi = QPushButton("Chiudi avviso")
            applica_icona(btn_chiudi, "circle-check", 18)
            btn_chiudi.setMinimumHeight(40)
            btn_chiudi.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("btn_arancione_bg")};
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 8px 20px;
                }}
                QPushButton:hover {{ background-color: {C("btn_arancione_hover")}; }}
            """)
            btn_chiudi.clicked.connect(dialog.close)
            layout_d.addWidget(btn_chiudi)
            dialog.show()

        if vincoli_aggiunti:
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True
            righe = []
            for vincolo in vincoli_aggiunti[:15]:
                etichetta = (
                    "Incompatibilità"
                    if vincolo["tipo"] == "incompatibilita"
                    else "Affinità"
                )
                righe.append(
                    f"{etichetta}: {vincolo['target']} ← {vincolo['sorgente']} "
                    f"(livello {vincolo['livello']})"
                )
            if len(vincoli_aggiunti) > 15:
                residui = len(vincoli_aggiunti) - 15
                righe.append(
                    "... e "
                    + (
                        "un altro vincolo"
                        if residui == 1
                        else f"altri {residui} vincoli"
                    )
                )

            numero_vincoli = len(vincoli_aggiunti)
            messaggio = (
                "È stato completato un vincolo speculare mancante."
                if numero_vincoli == 1
                else "Sono stati completati alcuni vincoli speculari mancanti."
            )
            verbo_aggiunto = (
                "È stato aggiunto"
                if numero_vincoli == 1
                else "Sono stati aggiunti"
            )
            _popup_info(
                self,
                "Coerenza bidirezionale",
                messaggio,
                dettagli=(
                    f"{verbo_aggiunto} "
                    f"{quantita(numero_vincoli, 'vincolo mancante', 'vincoli mancanti')} "
                    "per garantire la bidirezionalità:\n\n"
                    + "\n".join(righe)
                ),
            )



    def _chiudi_editor(self):
        """Chiude la classe corrente dopo le guardie sui dati pendenti."""


        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se chiudi adesso, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return


        if self._callback_pre_chiusura_file is not None:
            if not self._callback_pre_chiusura_file():
                return

        if self._modifiche_non_salvate:

            azione = self._conferma_chiusura()
            if azione == "salva":

                self._esporta_file()

                if self._modifiche_non_salvate:
                    return
                self._resetta_editor()
            elif azione == "esci":

                self._resetta_editor()
            else:

                return
        else:

            self._resetta_editor()

    def _conferma_chiusura(self):
        """Chiede se salvare, scartare o annullare le modifiche."""


        nome_file = self._nome_file_caricato or "sconosciuto"
        dialog = crea_popup_semantico(
            self,
            "Modifiche non salvate",
            f"Il file «{nome_file}.txt» contiene modifiche non salvate.",
            "triangle-alert",
            testo_informativo=(
                "Se esci ora, le modifiche a studenti, vincoli, genere e posizione "
                "andranno perse.\n\nChe cosa vuoi fare?"
            ),
            messaggio_in_grassetto=True,
        )


        btn_salva = dialog.addButton(
            "Salva ed esci", QMessageBox.AcceptRole
        )
        applica_icona(btn_salva, "save", 18)

        btn_esci = dialog.addButton(
            "Esci senza salvare", QMessageBox.DestructiveRole
        )
        applica_icona(btn_esci, "trash-2", 18)
        applica_stile_pulsante_popup(btn_esci, "distruttivo")

        btn_annulla = dialog.addButton(
            "Annulla", QMessageBox.RejectRole
        )
        applica_icona(btn_annulla, "x", 18)

        dialog.setDefaultButton(btn_annulla)

        dialog.setEscapeButton(btn_annulla)
        dialog.exec()

        bottone_cliccato = dialog.clickedButton()
        if bottone_cliccato == btn_salva:
            return "salva"
        elif bottone_cliccato == btn_esci:
            return "esci"
        else:
            return "annulla"

    def _resetta_editor(self):
        """Ripristina l’Editor allo stato iniziale."""

        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()
        self._nome_file_caricato = ""
        self._percorso_file_caricato = ""
        self._modifiche_non_salvate = False
        self._correzioni_applicate = False


        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()


        self._popola_placeholder_file_non_selezionato()


        self.btn_preview.setEnabled(False)
        self.btn_esporta.setEnabled(False)
        self.btn_aggiungi_studente.setEnabled(False)
        self.btn_aggiungi_studente.setVisible(False)
        self._schede_tutte_espanse = False
        self.btn_toggle_schede.setText("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.setEnabled(False)
        self.btn_chiudi.setEnabled(False)


        self._dati_riga_info = None


        self.label_contatore_vincoli.setText("")
        self.label_contatore_vincoli.setVisible(False)
        self.btn_toggle_schede.setVisible(False)
        self._btn_dettaglio_vincoli.setVisible(False)


        self._banner_formato_base.setVisible(False)


        self.file_chiuso_signal.emit()

    def richiedi_conferma_chiusura(self):
        """Verifica se l’applicazione può chiudersi senza perdere dati."""


        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se chiudi adesso, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return False

        if not self._modifiche_non_salvate:
            return True

        azione = self._conferma_chiusura()
        if azione == "salva":
            self._esporta_file()

            return not self._modifiche_non_salvate
        elif azione == "esci":
            return True
        else:
            return False


    def tutti_generi_impostati(self):
        """Indica se tutte le schede hanno un genere valido."""
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                return False
        return True

    def get_nomi_studenti_senza_genere(self):
        """Restituisce gli studenti che conservano il placeholder del genere."""
        return [
            scheda.nome_completo
            for scheda in self._schede_studenti
            if not scheda.genere_impostato()
        ]

    def _componi_riga_info_html(self):
        """Compone la riga con nome, composizione e formato del file corrente."""
        if not self._dati_riga_info:
            return ""

        nome = self._dati_riga_info["nome"]
        num = self._dati_riga_info["num"]
        formato = self._dati_riga_info["formato"]
        colore = C("testo_affinita")

        maschi = sum(
            scheda.combo_genere.currentText() == "M"
            for scheda in self._schede_studenti
        )
        femmine = sum(
            scheda.combo_genere.currentText() == "F"
            for scheda in self._schede_studenti
        )

        parola_maschi = "maschio" if maschi == 1 else "maschi"
        parola_femmine = "femmina" if femmine == 1 else "femmine"
        nome_html = escape(f"{nome}.txt")

        return (
            f'<span style="color:{colore};">'
            f"Il file '<b>{nome_html}</b>' è stato selezionato — "
            f"{quantita(num, 'studente presente', 'studenti presenti')} "
            f"[{maschi} {parola_maschi}, {femmine} {parola_femmine}] "
            f"({formato})"
            f"</span>"
        )

    def _aggiorna_contatore_vincoli(self, profilo=None):
        """Aggiorna il riepilogo dei vincoli della classe."""

        if not self._schede_studenti:
            self.label_contatore_vincoli.setVisible(False)
            self.btn_toggle_schede.setVisible(False)
            self._btn_dettaglio_vincoli.setVisible(False)
            return

        dati = _misura_profilo(
            profilo,
            "contatore_estrai_dati",
            self.get_dati_tutti_studenti,
        )
        conteggi = _misura_profilo(
            profilo,
            "contatore_conta_vincoli",
            lambda: conta_vincoli(dati),
        )
        testo_html = _misura_profilo(
            profilo,
            "contatore_formatta_vincoli",
            lambda: formato_vincoli(
                conteggi,
                colore_etichetta=C("testo_info"),
                colore_critico=C("testo_arancione"),
                colore_normale=C("testo_secondario"),
            ),
        )
        riga_info = _misura_profilo(
            profilo,
            "contatore_riga_info",
            self._componi_riga_info_html,
        )
        separatore_info = "<br>" if riga_info else ""
        _misura_profilo(
            profilo,
            "contatore_set_text",
            lambda: self.label_contatore_vincoli.setText(
                riga_info + separatore_info + testo_html
            ),
        )
        _misura_profilo(
            profilo,
            "contatore_set_stylesheet",
            lambda: self.label_contatore_vincoli.setStyleSheet(f"""
                background-color: {C('vincoli_riepilogo_bg')};
                border: 1px solid {C('vincoli_riepilogo_bordo')};
                border-radius: 5px;
                padding: 6px 8px;
                font-size: 14px;
            """),
        )
        _misura_profilo(
            profilo,
            "contatore_visibilita",
            lambda: (
                self.label_contatore_vincoli.setVisible(True),
                self.btn_toggle_schede.setVisible(True),
                self._btn_dettaglio_vincoli.setVisible(True),
            ),
        )

    def _mostra_dettaglio_vincoli(self):
        """Mostra l’elenco completo dei vincoli in una finestra scorrevole."""


        if not self._schede_studenti:
            return


        dati = self.get_dati_tutti_studenti()
        dettaglio = dettaglio_vincoli(dati)
        testo_html = formato_dettaglio_vincoli(
            dettaglio,
            colore_titolo=C("testo_info"),
            colore_critico=C("testo_arancione"),
            colore_normale=C("testo_secondario"),
        )


        dialog = QDialog(self)
        nome_classe = self._nome_file_caricato or "classe"
        dialog.setWindowTitle(f"Dettaglio vincoli — {nome_classe}")
        applica_icona_finestra(dialog, "list-tree")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=520,
            altezza_ideale=600,
            larghezza_minima=420,
            altezza_minima=360,
        )

        layout_d = QVBoxLayout(dialog)


        area = QTextEdit()
        area.setReadOnly(True)
        area.setHtml(testo_html)


        area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C('dettaglio_vincoli_bg')};
                border: 1px solid {C('bordo_normale')};
                border-radius: 4px;
                font-size: 14px;
                padding: 6px;
            }}
        """)
        layout_d.addWidget(area)


        riga_pulsanti = QHBoxLayout()
        riga_pulsanti.addStretch()
        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.clicked.connect(dialog.accept)
        riga_pulsanti.addWidget(btn_chiudi)
        layout_d.addLayout(riga_pulsanti)


        dialog.exec()

    def get_dati_tutti_studenti(self):
        """Restituisce i dati correnti di tutte le schede."""
        return [scheda.get_dati() for scheda in self._schede_studenti]

    def ha_studenti_caricati(self):
        """Indica se l’Editor contiene almeno una scheda."""
        return len(self._schede_studenti) > 0


    def genera_contenuto_file(self):
        """Valida e genera il contenuto canonico completo della classe."""
        return serializza_file_classe(
            self._nome_file_caricato,
            self.get_dati_tutti_studenti(),
        )

    def _genera_contenuto_o_segnala_errori(self):
        """Restituisce il testo serializzato oppure mostra gli errori canonici."""
        try:
            return self.genera_contenuto_file()
        except ErroreValidazioneFileClasse as errore:
            testo = "\n".join(f"• {voce}" for voce in errore.errori[:20])
            if len(errore.errori) > 20:
                testo += f"\n\n... e altri {len(errore.errori) - 20} errori."
            _popup_errore(
                self,
                "Dati della classe non validi",
                "Il file non può essere generato finché restano dati incoerenti.",
                dettagli=testo,
            )
            return None



    def _mostra_preview(self):
        """Mostra l’anteprima del file dopo la validazione del genere."""

        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            _popup_avviso(
                self,
                "Genere non impostato",
                (
                    "Uno studente non ha ancora il genere selezionato."
                    if len(studenti_senza_genere) == 1
                    else "Alcuni studenti non hanno ancora il genere selezionato."
                ),
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di procedere."
                ),
            )
            return

        contenuto = self._genera_contenuto_o_segnala_errori()
        if contenuto is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Anteprima file classe (.txt)")
        applica_icona_finestra(dialog, "eye")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1300,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )

        layout = QVBoxLayout(dialog)


        text_edit = QTextEdit()
        text_edit.setReadOnly(True)


        font_preview = QFont()
        font_preview.setFamily("Consolas")
        font_preview.setPointSize(11)
        font_preview.setStyleHint(QFont.Monospace)
        text_edit.setFont(font_preview)
        text_edit.setPlainText(contenuto)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C("anteprima_sf")};
                color: {C("anteprima_txt")};
                border: 1px solid {C("bordo_normale")};
                padding: 10px;
            }}
        """)
        layout.addWidget(text_edit)


        num_righe_dati = len(self._schede_studenti)
        label_info = QLabel(
            f"{quantita(num_righe_dati, 'studente', 'studenti')} — "
            "Ogni riga ha 6 campi separati da «;»"
        )
        label_info.setStyleSheet(f"color: {C('testo_info_grigio')}; font-size: 11px;")
        layout.addWidget(label_info)


        bottoni = QDialogButtonBox(QDialogButtonBox.Close)
        btn_close_preview = bottoni.button(QDialogButtonBox.Close)
        if btn_close_preview is not None:
            btn_close_preview.setText("Chiudi")
            applica_icona(btn_close_preview, "x", 18)
        bottoni.rejected.connect(dialog.close)
        layout.addWidget(bottoni)

        dialog.exec()


    def _esporta_file(self):
        """Valida e salva il file corrente.

        Aggiorna atomicamente il file già selezionato e, dopo il successo,
        notifica la finestra principale.
        """

        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            _popup_avviso(
                self,
                "Genere non impostato",
                (
                    "Uno studente non ha ancora il genere selezionato."
                    if len(studenti_senza_genere) == 1
                    else "Alcuni studenti non hanno ancora il genere selezionato."
                ),
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di salvare."
                ),
            )
            return


        studenti_fisso = []
        for scheda in self._schede_studenti:
            dati = scheda.get_dati()
            if dati["posizione"] == "FISSO":
                studenti_fisso.append(scheda.nome_completo)

        if len(studenti_fisso) > 1:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
            _popup_avviso(
                self,
                "Troppi studenti con posizione FISSO",
                "Al massimo uno studente può avere posizione FISSO.",
                dettagli=(
                    f"Attualmente sono "
                    f"{quantita(len(studenti_fisso), 'studente', 'studenti')}:\n\n"
                    f"{elenco}\n\n"
                    "Modifica la posizione degli studenti in eccesso prima di salvare."
                ),
            )
            return


        vincoli_incompleti = self.get_vincoli_incompleti()
        if vincoli_incompleti:
            elenco = "\n".join(vincoli_incompleti)
            _popup_avviso(
                self,
                "Vincoli incompleti",
                "Sono presenti vincoli senza livello impostato.",
                dettagli=(
                    f"{elenco}\n\n"
                    "Per ogni vincolo, seleziona il livello di intensità oppure "
                    "rimuovilo con il pulsante «Rimuovi»."
                ),
            )
            return


        self._controlla_anomalie_editor()

        dati_correnti = [
            scheda.get_dati()
            for scheda in self._schede_studenti
        ]
        coerenza = analizza_coerenza_bidirezionale_dati(
            dati_correnti,
            completa_mancanti=False,
        )

        anomalie = (
            coerenza["contraddizioni"]
            + coerenza["discordanze_livello"]
        )
        if anomalie:
            testo = "\n".join(
                f"• {voce}" for voce in anomalie[:15]
            )
            if len(anomalie) > 15:
                residue = len(anomalie) - 15
                testo += (
                    "\n\n... e "
                    + (
                        "un’altra anomalia."
                        if residue == 1
                        else f"altre {residue} anomalie."
                    )
                )

            _popup_errore(
                self,
                "Vincoli incoerenti",
                "Il salvataggio è bloccato da contraddizioni o livelli diversi nelle due direzioni.",
                dettagli=(
                    f"{testo}\n\n"
                    "Correggi i vincoli nelle schede e riprova."
                ),
            )
            return

        contenuto = self._genera_contenuto_o_segnala_errori()
        if contenuto is None:
            return

        percorso = self._percorso_file_caricato
        if not percorso:
            _popup_errore(
                self,
                "File sorgente non disponibile",
                "Non è presente un file di classe da aggiornare.",
                dettagli="Chiudi l'Editor e seleziona nuovamente il file della classe.",
            )
            return

        # La proposta appartiene ancora alla classe precedente: proteggerla
        # prima di scrivere il file e prima del segnale che la ricarichera'.
        if (self._callback_pre_salvataggio is not None
                and not self._callback_pre_salvataggio()):
            return

        try:
            scrivi_file_classe_atomico(percorso, contenuto)


            self._modifiche_non_salvate = False
            # La scrittura esplicita ha già incorporato tutte le correzioni
            # sicure: il successivo caricamento non deve riscrivere il file né
            # mostrare una seconda conferma di salvataggio.
            self._correzioni_applicate = False

            self._percorso_file_caricato = percorso


            self._banner_formato_base.setVisible(False)


            self._dati_riga_info = {
                "nome": self._nome_file_caricato,
                "num": len(self._schede_studenti),
                "formato": "formato COMPLETO",
            }
            self._aggiorna_contatore_vincoli()


            nome_file = os.path.basename(percorso)
            _popup_successo(
                self,
                "File aggiornato",
                f"Il file «{nome_file}» è stato aggiornato,\n"
                f"caricato ed è pronto per l'assegnazione.",
                dettagli=(
                    f"Percorso:\n{percorso}\n\n"
                    f"Studenti: {len(self._schede_studenti)}"
                ),
            )


            self.file_salvato_signal.emit(percorso)

        except Exception as e:
            _popup_errore(
                self,
                "Salvataggio non riuscito",
                "Impossibile salvare il file.",
                dettagli=str(e),
            )

    def _get_cartella_classi(self):
        """Restituisce la cartella locale dei file-classe."""
        return inizializza_cartella_classi()

    def _apri_cartella_classi(self):
        """Apre la cartella delle classi con il gestore di file del sistema."""

        cartella_classi = self._get_cartella_classi()

        if apri_file_con_applicazione_default(cartella_classi):
            return

        _popup_avviso(
            self,
            "Apertura della cartella non riuscita",
            "Impossibile aprire automaticamente la cartella delle classi.",
            dettagli=f"Aprila manualmente dal percorso:\n{cartella_classi}",
        )
