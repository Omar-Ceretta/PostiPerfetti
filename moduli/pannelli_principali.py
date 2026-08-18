# -*- coding: utf-8 -*-
"""Costruzione dei pannelli della finestra principale di «PostiPerfetti».

Il mixin crea esclusivamente widget, layout e collegamenti dei segnali. Le
azioni applicative restano in ``FinestraPostiPerfetti`` e negli altri mixin.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QRadioButton, QButtonGroup, QCheckBox, QSpinBox,
    QTableWidget, QTabWidget, QAbstractItemView, QScrollArea, QLineEdit,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from moduli.editor_studenti import EditorStudentiWidget, ComboBoxProtetto
from moduli.lingua import forma_numerata
from moduli.tema import C
from moduli.utilita import (
    crea_bottone, applica_icona, applica_icona_etichetta, applica_icona_tab,
)


class PannelliPrincipaliMixin:
    """Crea i pannelli di configurazione, risultati, Editor e Storico."""

    def setup_ui(self):
        """Costruisce l’interfaccia principale."""

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        left_panel = self._crea_pannello_controlli()
        main_layout.addWidget(left_panel, 1)

        right_panel = self._crea_pannello_risultati()
        main_layout.addWidget(right_panel, 4)

        self._configura_accessibilita_principale()

    def _configura_accessibilita_principale(self) -> None:
        """Descrive i controlli e rende prevedibile la navigazione da tastiera."""
        self.scroll_pannello_sx.setAccessibleName(
            "Controlli di configurazione"
        )
        self.input_nome_classe.setAccessibleName("Classe caricata")
        self.input_num_file.setAccessibleName("Numero di file di banchi")
        self.input_posti_fila.setAccessibleName("Posti per fila")
        self.input_num_file.setFocusPolicy(Qt.NoFocus)
        self.input_posti_fila.setFocusPolicy(Qt.NoFocus)

        self.btn_posti_meno.setAccessibleName("Riduci i posti per fila")
        self.btn_posti_piu.setAccessibleName("Aumenta i posti per fila")
        self.checkbox_genere_misto.setAccessibleDescription(
            "Applica una preferenza, non un obbligo, agli abbinamenti misti."
        )
        self.spinbox_mesi.setAccessibleName("Numero di mesi Annuali")
        self.btn_avvia_assegnazione.setAccessibleName(
            "Avvia assegnazione dei posti"
        )
        self.btn_annulla_annuale.setAccessibleName(
            "Annulla elaborazione Annuale"
        )
        self.label_status.setAccessibleName("Stato dell'elaborazione")

        self.tab_widget.setAccessibleName("Risultati e Storico")
        self.text_report.setAccessibleName("Report dell'assegnazione corrente")
        self.tabella_storico.setAccessibleName("Assegnazioni salvate")
        self.filtro_classe_combo.setAccessibleName(
            "Filtro delle statistiche per classe"
        )
        self.btn_export_stats.setAccessibleName(
            "Esporta le statistiche in formato testo"
        )

        sequenza = (
            self.btn_istruzioni,
            self.btn_toggle_tema,
            self.btn_crediti,
            self.radio_geo_coppie,
            self.radio_geo_terzetti,
            self.btn_posti_meno,
            self.btn_posti_piu,
            self.radio_resto_coppia,
            self.radio_resto_quartetti,
            self.radio_trio_prima,
            self.radio_trio_centro,
            self.radio_trio_ultima,
            self.checkbox_genere_misto,
            self.radio_mensile,
            self.radio_annuale,
            self.spinbox_mesi,
            self.btn_avvia_assegnazione,
        )
        for corrente, successivo in zip(sequenza, sequenza[1:]):
            QWidget.setTabOrder(corrente, successivo)

    def _crea_pannello_controlli(self) -> QWidget:
        """Crea il pannello scorrevole con i controlli di configurazione."""

        self.scroll_pannello_sx = QScrollArea()
        self.scroll_pannello_sx.setWidgetResizable(True)

        self.scroll_pannello_sx.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_pannello_sx.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_pannello_sx.setFrameShape(QFrame.NoFrame)

        self.scroll_pannello_sx.setMinimumWidth(380)

        panel = QWidget()
        layout = QVBoxLayout(panel)

        font_pannello = QFont()
        font_pannello.setPointSize(12)
        panel.setFont(font_pannello)

        SPAZIO_TRA_BOX = 8

        layout.addStretch()
        self._crea_sezione_bottoni_superiori(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_stato_classe(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_configurazione_aula(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_gestione_dispari(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_opzioni_vincoli(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_modalita(layout, SPAZIO_TRA_BOX)
        self._crea_bottone_avvia(layout)

        layout.addStretch()

        self.scroll_pannello_sx.setWidget(panel)

        return self.scroll_pannello_sx

    def _crea_sezione_bottoni_superiori(self, layout, SPAZIO_TRA_BOX):
        """Crea la barra dei comandi di servizio."""

        LARGHEZZA_BTN_TEMA = 130

        ALTEZZA_BTN = 34

        barra_bottoni = QWidget()
        barra_layout = QHBoxLayout(barra_bottoni)
        barra_layout.setContentsMargins(0, 0, 0, 0)
        barra_layout.setSpacing(8)

        self.btn_istruzioni = crea_bottone(
            "Istruzioni", C("btn_indaco_bg"), C("btn_indaco_hover"),
            tooltip="Mostra la guida completa all'uso del programma",
            font_size=13, padding="0px",
            colore_testo=C("btn_indaco_txt"),
            colore_bordo=C("btn_indaco_bordo")
        )
        self.btn_istruzioni.setFixedWidth(LARGHEZZA_BTN_TEMA)
        self.btn_istruzioni.setFixedHeight(ALTEZZA_BTN)
        applica_icona(self.btn_istruzioni, "book-open", 18)
        self.btn_istruzioni.clicked.connect(self._mostra_istruzioni)
        barra_layout.addWidget(self.btn_istruzioni)

        self.btn_toggle_tema = crea_bottone(
            "Tema chiaro", C("btn_tema_bg"), C("btn_tema_hover"),
            tooltip="Alterna tra tema scuro e tema chiaro",
            font_size=13, padding="0px",
            colore_testo=C("btn_tema_txt"),
            colore_bordo=C("btn_tema_bordo")
        )
        self.btn_toggle_tema.setFixedWidth(LARGHEZZA_BTN_TEMA)
        self.btn_toggle_tema.setFixedHeight(ALTEZZA_BTN)
        applica_icona(self.btn_toggle_tema, "sun", 18)
        self.btn_toggle_tema.clicked.connect(self._cambia_tema)
        barra_layout.addWidget(self.btn_toggle_tema)

        self.btn_crediti = QPushButton()
        self.btn_crediti.setFixedSize(ALTEZZA_BTN, ALTEZZA_BTN)
        self.btn_crediti.setToolTip("Informazioni e crediti")
        self.btn_crediti.setAccessibleName("Informazioni e crediti")
        applica_icona(self.btn_crediti, "info", 18)

        self.btn_crediti.clicked.connect(self._mostra_crediti)
        barra_layout.addWidget(self.btn_crediti)

        layout.addWidget(barra_bottoni, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_stato_classe(self, layout, SPAZIO_TRA_BOX):
        """Crea il riepilogo dello stato della classe caricata."""

        group_dati = QGroupBox("STATO CLASSE")
        layout_dati = QVBoxLayout(group_dati)
        layout_dati.setContentsMargins(9, 2, 9, 9)

        self.input_nome_classe = QLineEdit()
        self.input_nome_classe.setPlaceholderText("   < si compila automaticamente >")
        self.input_nome_classe.setReadOnly(True)
        self.input_nome_classe.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_pannello")};
                color: {C("testo_secondario")};
                border: 1px solid {C("bordo_normale")};
            }}
        """)

        font_nome_classe = self.input_nome_classe.font()
        font_nome_classe.setBold(True)
        self.input_nome_classe.setFont(font_nome_classe)
        label_nome_classe = QLabel("  Nome classe:  ")
        label_nome_classe.setStyleSheet("font-size: 13px;")

        riga_nome_classe = QHBoxLayout()
        riga_nome_classe.addWidget(label_nome_classe)
        riga_nome_classe.addWidget(self.input_nome_classe)
        layout_dati.addLayout(riga_nome_classe)

        self.label_studenti_caricati = QLabel(
            "NESSUN FILE SELEZIONATO.\n\n"
            "Vai in 'Editor studenti' e clicca su 'Seleziona classe'."
        )
        self.label_studenti_caricati.setProperty("stato_classe", "neutro")
        self._applica_stile_label_stato_classe("neutro")

        self.label_studenti_caricati.setWordWrap(True)
        layout_dati.addWidget(self.label_studenti_caricati)

        layout.addWidget(group_dati)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_configurazione_aula(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per la geometria dell’aula."""

        self.group_aula = QGroupBox("CONFIGURAZIONE AULA")
        layout_aula = QVBoxLayout(self.group_aula)
        layout_aula.setContentsMargins(9, 2, 9, 9)
        layout_aula.setSpacing(6)

        riga_geometria = QHBoxLayout()
        riga_geometria.addStretch()
        self.radio_geo_coppie = QRadioButton("A coppie  ")
        self.radio_geo_coppie.setToolTip(
            "Dispone gli allievi a banchi da DUE (la modalità originaria del programma)."
        )
        self.radio_geo_terzetti = QRadioButton("A terzetti  ")
        self.radio_geo_terzetti.setToolTip(
            "Dispone gli allievi a banchi lunghi da TRE in fila.\n"
            "Si toccano solo 1-2 e 2-3 (gli estremi 1 e 3 non sono vicini)."
        )
        riga_geometria.addWidget(self.radio_geo_coppie)
        riga_geometria.addSpacing(12)
        riga_geometria.addWidget(self.radio_geo_terzetti)
        riga_geometria.addStretch()
        layout_aula.addLayout(riga_geometria)

        self.radio_geo_coppie.setChecked(True)
        self.radio_geo_coppie.toggled.connect(self._on_geometria_cambiata)
        self.radio_geo_terzetti.toggled.connect(self._on_geometria_cambiata)

        container_file = QWidget()
        container_file.setMaximumWidth(54)
        layout_file = QHBoxLayout(container_file)
        layout_file.setContentsMargins(0, 0, 0, 0)
        layout_file.setSpacing(4)

        self.input_num_file = QLineEdit()
        self.input_num_file.setText(str(self.DEFAULT_NUM_FILE_SENZA_CLASSE))
        self.input_num_file.setReadOnly(True)
        self.input_num_file.setAlignment(Qt.AlignCenter)
        self.input_num_file.setMaximumWidth(50)
        self.input_num_file.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
        """)

        layout_file.addWidget(self.input_num_file)

        riga_posti_fila = QHBoxLayout()
        riga_posti_fila.addStretch()
        riga_posti_fila.addWidget(QLabel("  Posti per fila:  "))
        riga_posti_fila.addSpacing(8)

        container_posti = QWidget()
        container_posti.setMaximumWidth(130)
        layout_posti = QHBoxLayout(container_posti)
        layout_posti.setContentsMargins(0, 0, 0, 0)
        layout_posti.setSpacing(4)

        self.input_posti_fila = QLineEdit()
        self.input_posti_fila.setText(str(self.DEFAULT_POSTI_PER_FILA_COPPIE))
        self.input_posti_fila.setReadOnly(True)
        self.input_posti_fila.setAlignment(Qt.AlignCenter)
        self.input_posti_fila.setMaximumWidth(50)
        self.input_posti_fila.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
        """)

        self.btn_posti_meno = QPushButton("−")
        self.btn_posti_meno.setMaximumWidth(30)
        self.btn_posti_meno.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_spinbox_bg")};
                color: {C("btn_spinbox_txt")};
                border: 1px solid {C("btn_spinbox_bordo")};
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_meno_hover_bg")};
                border: 1px solid {C("btn_meno_hover_bordo")};
            }}
        """)
        self.btn_posti_meno.setToolTip("Riduci i posti per fila (di 2 alla volta)")
        self.btn_posti_meno.clicked.connect(lambda: self._cambia_posti_fila(-2))

        self.btn_posti_piu = QPushButton("+")
        self.btn_posti_piu.setMaximumWidth(30)
        self.btn_posti_piu.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_spinbox_bg")};
                color: {C("btn_spinbox_txt")};
                border: 1px solid {C("btn_spinbox_bordo")};
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_piu_hover_bg")};
                border: 1px solid {C("btn_piu_hover_bordo")};
            }}
        """)
        self.btn_posti_piu.setToolTip("Aggiungi 2 posti per fila")
        self.btn_posti_piu.clicked.connect(lambda: self._cambia_posti_fila(+2))

        layout_posti.addWidget(self.btn_posti_meno)
        layout_posti.addWidget(self.input_posti_fila)
        layout_posti.addWidget(self.btn_posti_piu)

        riga_posti_fila.addWidget(container_posti)
        riga_posti_fila.addSpacing(14)
        riga_posti_fila.addWidget(QLabel("  File:  "))
        riga_posti_fila.addSpacing(4)
        riga_posti_fila.addWidget(container_file)
        riga_posti_fila.addStretch()
        layout_aula.addLayout(riga_posti_fila)

        riga_posti = QHBoxLayout()
        riga_posti.addStretch()
        self.label_posti_totali = QLabel("  Posti totali: 24  ")
        self.label_posti_totali.setWordWrap(True)
        riga_posti.addWidget(self.label_posti_totali)
        riga_posti.addSpacing(6)

        self.btn_aiuto_aula = QPushButton()
        applica_icona(self.btn_aiuto_aula, "circle-help", 18)
        self.btn_aiuto_aula.setFixedSize(32, 32)
        self.btn_aiuto_aula.setToolTip("Clicca per capire come contare file e posti")
        self.btn_aiuto_aula.setAccessibleName("Aiuto configurazione aula")
        self.btn_aiuto_aula.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_indaco_bg")};
                color: {C("btn_indaco_txt")};
                font-weight: bold;
                font-size: 15px;
                border-radius: 16px;
                border: 1px solid {C("btn_indaco_bordo")};
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: {C("btn_indaco_hover")}; }}
        """)
        self.btn_aiuto_aula.clicked.connect(self._mostra_aiuto_configurazione_aula)
        riga_posti.addWidget(self.btn_aiuto_aula)
        riga_posti.addStretch()
        layout_aula.addLayout(riga_posti)

        layout.addWidget(self.group_aula)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_gestione_dispari(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per la posizione del blocco finale."""

        self.group_dispari = QGroupBox("GESTIONE NUMERO DISPARI")
        layout_dispari = QVBoxLayout(self.group_dispari)
        layout_dispari.setContentsMargins(9, 2, 9, 9)

        self.widget_composizione_resto = QWidget()
        layout_composizione = QVBoxLayout(self.widget_composizione_resto)
        layout_composizione.setContentsMargins(0, 0, 0, 0)
        self.label_composizione_resto = QLabel("I 2 allievi in più formano:")
        self.label_composizione_resto.setWordWrap(True)
        self.label_composizione_resto.setStyleSheet(f"color: {C('testo_info')}; font-size: 13px; font-style: italic;")
        layout_composizione.addWidget(self.label_composizione_resto)

        self.radio_resto_coppia = QRadioButton("1 coppia (un banco da 2)")
        self.radio_resto_coppia.setChecked(True)
        self.radio_resto_quartetti = QRadioButton("2 quartetti (due banchi da 4)")
        layout_composizione.addWidget(self.radio_resto_coppia)
        layout_composizione.addWidget(self.radio_resto_quartetti)

        self.gruppo_composizione_resto = QButtonGroup(self.widget_composizione_resto)
        self.gruppo_composizione_resto.addButton(self.radio_resto_coppia)
        self.gruppo_composizione_resto.addButton(self.radio_resto_quartetti)
        self.widget_composizione_resto.setVisible(False)
        layout_dispari.addWidget(self.widget_composizione_resto)

        self.radio_resto_coppia.toggled.connect(self._on_composizione_resto_cambiata)

        self.label_info_dispari = QLabel("Se si formerà un 'trio', il banco da 3 sarà posizionato:")
        self.label_info_dispari.setWordWrap(True)
        self.label_info_dispari.setStyleSheet(f"color: {C('testo_info')}; font-size: 13px; font-style: italic;")
        layout_dispari.addWidget(self.label_info_dispari)

        self.radio_trio_prima = QRadioButton("Davanti")
        self.radio_trio_centro = QRadioButton("In mezzo")
        self.radio_trio_centro.setChecked(True)
        self.radio_trio_ultima = QRadioButton("In fondo")

        riga_posizioni_resto = QHBoxLayout()
        riga_posizioni_resto.addWidget(self.radio_trio_prima)
        riga_posizioni_resto.addWidget(self.radio_trio_centro)
        riga_posizioni_resto.addWidget(self.radio_trio_ultima)
        riga_posizioni_resto.addStretch()
        layout_dispari.addLayout(riga_posizioni_resto)

        self.gruppo_posizione_resto = QButtonGroup(self.group_dispari)
        self.gruppo_posizione_resto.addButton(self.radio_trio_prima)
        self.gruppo_posizione_resto.addButton(self.radio_trio_centro)
        self.gruppo_posizione_resto.addButton(self.radio_trio_ultima)

        self._memoria_posizione_resto = dict(self.DEFAULT_POSIZIONE_RESTO)

        self._modo_box_resto_corrente = 'coppie'

        self.group_dispari.setVisible(False)

        layout.addWidget(self.group_dispari)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_opzioni_vincoli(self, layout, SPAZIO_TRA_BOX):
        """Crea le opzioni avanzate sui vincoli."""

        self.group_opzioni = QGroupBox("GENERE MISTO")
        layout_opzioni = QVBoxLayout(self.group_opzioni)
        layout_opzioni.setContentsMargins(9, 2, 9, 9)

        self.checkbox_genere_misto = QCheckBox("Preferisci coppie miste (M+F)")
        self.checkbox_genere_misto.setToolTip(
            "Se attivo, dà forte preferenza alle coppie M+F.\n"
            "Non vieta coppie dello stesso genere se necessarie per variare "
            "le rotazioni."
        )
        layout_opzioni.addWidget(self.checkbox_genere_misto)

        layout.addWidget(self.group_opzioni)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_modalita(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per scegliere fra assegnazione mensile e annuale."""

        self.group_modalita = QGroupBox("MODALITÀ DI ASSEGNAZIONE")
        layout_modalita = QVBoxLayout(self.group_modalita)
        layout_modalita.setContentsMargins(9, 2, 9, 9)

        self.label_storico = QLabel("Storico: nessuna assegnazione precedente")
        self.label_storico.setWordWrap(True)
        self.label_storico.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;")
        layout_modalita.addWidget(self.label_storico)

        riga_radio = QHBoxLayout()
        self.radio_mensile = QRadioButton("Mensile (un mese)")
        self.radio_mensile.setToolTip(
            "Assegna i posti per UN solo mese: è il flusso di sempre."
        )
        self.radio_annuale = QRadioButton("Annuale (più mesi)")
        self.radio_annuale.setToolTip(
            "Genera in un colpo solo più mesi consecutivi, confrontando\n"
            "più tentativi e scegliendo la combinazione più pulita."
        )
        riga_radio.addWidget(self.radio_mensile)
        riga_radio.addWidget(self.radio_annuale)
        riga_radio.addStretch()
        layout_modalita.addLayout(riga_radio)

        self.widget_mesi_annuale = QWidget()
        riga_mesi = QHBoxLayout(self.widget_mesi_annuale)
        riga_mesi.setContentsMargins(0, 0, 0, 0)
        riga_mesi.addWidget(QLabel("Genera"))
        self.spinbox_mesi = QSpinBox()
        self.spinbox_mesi.setRange(1, 10)
        self.spinbox_mesi.setValue(self.DEFAULT_MESI_ANNUALE)
        riga_mesi.addWidget(self.spinbox_mesi)
        self.label_mesi_annuale = QLabel()
        riga_mesi.addWidget(self.label_mesi_annuale)
        self.spinbox_mesi.valueChanged.connect(
            self._aggiorna_etichetta_mesi_annuale
        )
        self._aggiorna_etichetta_mesi_annuale(self.spinbox_mesi.value())
        riga_mesi.addStretch()
        layout_modalita.addWidget(self.widget_mesi_annuale)

        self.radio_mensile.setChecked(True)
        self.widget_mesi_annuale.setVisible(False)
        self.radio_annuale.toggled.connect(self.widget_mesi_annuale.setVisible)

        layout.addWidget(self.group_modalita)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _aggiorna_etichetta_mesi_annuale(self, valore: int) -> None:
        """Accorda la descrizione del numero di mesi selezionato."""
        parola_mese = forma_numerata(valore, "mese", "mesi")
        self.label_mesi_annuale.setText(
            f"{parola_mese} in coda allo Storico"
        )

    def _crea_bottone_avvia(self, layout):
        """Crea il comando principale di avvio e la relativa area di stato."""

        self.btn_avvia_assegnazione = crea_bottone(
            "ASSEGNA I POSTI!", C("btn_avvia_bg"), C("btn_avvia_hover"),
            tooltip="Calcola la disposizione ottimale dei posti\n"
                    "rispettando vincoli, affinità e rotazioni precedenti",
            altezza_min=50, font_size=16, border_radius=8,
            colore_disabled_bg=C("btn_avvia_disabled_bg"),
            colore_disabled_txt=C("btn_avvia_disabled_txt"),
            colore_testo=C("btn_avvia_txt"),
            colore_bordo=C("btn_avvia_bordo"),
            colore_disabled_bordo=C("btn_avvia_disabled_bordo")
        )
        applica_icona(self.btn_avvia_assegnazione, "wand-sparkles", 20)
        self.btn_avvia_assegnazione.clicked.connect(self.avvia_assegnazione)

        self._imposta_visibilita_configurazione(False)

        layout.addWidget(self.btn_avvia_assegnazione)

        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)

        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)

        self.btn_annulla_annuale = crea_bottone(
            "Annulla", C("btn_rosso_bg"), C("btn_rosso_hover"),
            tooltip="Interrompe la preparazione annuale.\n"
                    "L'interruzione avviene alla fine del mese in corso.",
            colore_disabled_bg=C("btn_avvia_disabled_bg")
        )
        applica_icona(self.btn_annulla_annuale, "circle-stop", 18)
        self.btn_annulla_annuale.clicked.connect(self._annulla_annuale)
        self.btn_annulla_annuale.hide()
        layout.addWidget(self.btn_annulla_annuale)

    def _crea_pannello_risultati(self) -> QWidget:
        """Crea il pannello che mostra aula, report e azioni sui risultati."""

        self.tab_widget = QTabWidget()

        self.tab_aula = QWidget()
        layout_aula = QVBoxLayout(self.tab_aula)

        self.scroll_aula = QScrollArea()
        self.widget_aula = QWidget()
        self.layout_griglia_aula = QGridLayout(self.widget_aula)
        self.scroll_aula.setWidget(self.widget_aula)
        self.scroll_aula.setWidgetResizable(True)
        layout_aula.addWidget(self.scroll_aula)

        controls_export = QHBoxLayout()

        self.btn_salva_progetto = crea_bottone(
            "Salva assegnazione", C("btn_salva_bg"), C("btn_salva_hover"),
            tooltip="Salva l'assegnazione nello Storico.\n"
                    "Indispensabile per le rotazioni future!",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_salva_txt"),
            colore_bordo=C("btn_salva_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_salva_progetto, "save", 18)
        self.btn_salva_progetto.clicked.connect(self.salva_assegnazione)
        self.btn_salva_progetto.setEnabled(False)
        controls_export.addWidget(self.btn_salva_progetto)

        self.btn_export_excel = crea_bottone(
            "Esporta Excel", C("btn_excel_bg"), C("btn_excel_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'esportazione.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_excel_txt"),
            colore_bordo=C("btn_excel_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_export_excel, "table-2", 18)
        self.btn_export_excel.clicked.connect(self.esporta_excel)
        self.btn_export_excel.setEnabled(False)
        controls_export.addWidget(self.btn_export_excel)

        self.btn_export_report_txt = crea_bottone(
            "Esporta report", C("btn_export_bg"), C("btn_export_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'esportazione.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_export_txt"),
            colore_bordo=C("btn_export_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_export_report_txt, "file-down", 18)
        self.btn_export_report_txt.clicked.connect(self.esporta_report_txt)
        self.btn_export_report_txt.setEnabled(False)
        controls_export.addWidget(self.btn_export_report_txt)

        controls_export.addStretch()
        layout_aula.addLayout(controls_export)

        self.editor_studenti = EditorStudentiWidget()
        indice_editor = self.tab_widget.addTab(
            self.editor_studenti, "Editor studenti"
        )
        applica_icona_tab(
            self.tab_widget, indice_editor, "notebook-pen", 20
        )

        indice_aula = self.tab_widget.addTab(self.tab_aula, "Aula")
        applica_icona_tab(
            self.tab_widget, indice_aula, "school", 20
        )

        self.tab_report = QWidget()
        layout_report = QVBoxLayout(self.tab_report)

        self.text_report = QTextEdit()
        self.text_report.setReadOnly(True)

        font_report = QFont()
        font_report.setFamily("Consolas")
        font_report.setPointSize(9)
        font_report.setStyleHint(QFont.Monospace)
        self.text_report.setFont(font_report)
        layout_report.addWidget(self.text_report)

        self.widget_hint_report = QWidget()
        layout_hint_report = QHBoxLayout(self.widget_hint_report)
        layout_hint_report.setContentsMargins(6, 4, 6, 4)
        layout_hint_report.setSpacing(8)
        layout_hint_report.addStretch()

        self.icona_hint_report = QLabel()
        self.icona_hint_report.setFixedSize(22, 22)
        self.icona_hint_report.setAlignment(Qt.AlignCenter)
        applica_icona_etichetta(self.icona_hint_report, "info", 18)
        layout_hint_report.addWidget(self.icona_hint_report)

        self.label_hint_report = QLabel(
            "Per esportare il Report in formato .txt, vai nella scheda Aula."
        )
        self.label_hint_report.setAlignment(Qt.AlignCenter)
        self.label_hint_report.setStyleSheet(
            f'color: {C("testo_secondario")}; font-size: 14px; '
            f'font-style: italic; padding: 6px;'
        )
        layout_hint_report.addWidget(self.label_hint_report)
        layout_hint_report.addStretch()

        self.widget_hint_report.setVisible(False)
        layout_report.addWidget(self.widget_hint_report)

        indice_report = self.tab_widget.addTab(self.tab_report, "Report")
        applica_icona_tab(
            self.tab_widget, indice_report, "file-text", 20
        )

        self.tab_storico = QWidget()
        layout_storico = QVBoxLayout(self.tab_storico)

        self.label_storico_vuoto = QLabel(
            "NESSUNA ASSEGNAZIONE SALVATA.\n\n"
            "Esegui almeno un'assegnazione e salvala\n"
            "per visualizzare lo Storico."
        )
        self.label_storico_vuoto.setAlignment(Qt.AlignCenter)
        self.label_storico_vuoto.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
        )
        layout_storico.addWidget(self.label_storico_vuoto)

        self.tabella_storico = QTableWidget()

        self.tabella_storico.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tabella_storico.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tabella_storico.setColumnCount(4)
        self.tabella_storico.setHorizontalHeaderLabels(["Data creazione", "Nome (modificabile)", "Abbinamenti", "Azioni"])

        self.tabella_storico.cellChanged.connect(self._on_storico_nome_modificato)
        layout_storico.addWidget(self.tabella_storico)

        indice_storico = self.tab_widget.addTab(
            self.tab_storico, "Storico"
        )
        applica_icona_tab(
            self.tab_widget, indice_storico, "history", 20
        )

        self.tab_statistiche = QWidget()
        layout_statistiche = QVBoxLayout(self.tab_statistiche)

        header_stats = QHBoxLayout()

        label_filtro = QLabel("Visualizza statistiche per:")
        label_filtro.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_stats.addWidget(label_filtro)

        self.filtro_classe_combo = ComboBoxProtetto()
        label_filtro.setBuddy(self.filtro_classe_combo)
        self.filtro_classe_combo.setMinimumWidth(400)

        self.filtro_classe_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px;
                font-size: 12px;
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                background-color: {C("sfondo_input_alt")};
            }}
            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
            }}
        """)

        self.filtro_classe_combo.currentIndexChanged.connect(self._aggiorna_statistiche)
        header_stats.addWidget(self.filtro_classe_combo)

        header_stats.addStretch()
        layout_statistiche.addLayout(header_stats)

        scroll_stats = QScrollArea()
        scroll_stats.setWidgetResizable(True)

        self.widget_statistiche = QWidget()
        self.layout_statistiche_content = QVBoxLayout(self.widget_statistiche)

        scroll_stats.setWidget(self.widget_statistiche)
        layout_statistiche.addWidget(scroll_stats)

        self.btn_export_stats = crea_bottone(
            "Esporta le statistiche (.txt)",
            C("btn_statistiche_export_bg"),
            C("btn_statistiche_export_hover"),
            tooltip="Salva le statistiche dettagliate in un file di testo",
            altezza_min=45,
            font_size=14,
            colore_testo=C("btn_statistiche_export_txt"),
            colore_bordo=C("btn_statistiche_export_bordo"),
        )
        applica_icona(self.btn_export_stats, "file-down", 18)
        self.btn_export_stats.clicked.connect(self._esporta_statistiche_txt)
        layout_statistiche.addWidget(self.btn_export_stats)

        indice_statistiche = self.tab_widget.addTab(
            self.tab_statistiche, "Statistiche"
        )
        applica_icona_tab(
            self.tab_widget, indice_statistiche, "chart-column", 20
        )

        self.tab_widget.setTabToolTip(0, "Modifica genere, posizione e vincoli degli studenti")
        self.tab_widget.setTabToolTip(1, "Visualizza la disposizione grafica dei banchi nell'aula")
        self.tab_widget.setTabToolTip(2, "Leggi il report dettagliato dell'assegnazione")
        self.tab_widget.setTabToolTip(3, "Consulta e gestisci lo storico delle assegnazioni passate")
        self.tab_widget.setTabToolTip(4, "Analizza le statistiche sugli abbinamenti e sulle rotazioni")

        self.tab_widget.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        self.editor_studenti.file_cambiato_signal.connect(self._on_editor_file_cambiato)

        self.editor_studenti.dati_modificati_signal.connect(self._on_editor_dati_modificati)

        self.editor_studenti.genere_cambiato_signal.connect(self._on_editor_genere_cambiato)

        self.editor_studenti.file_chiuso_signal.connect(self._on_editor_file_chiuso)

        self.editor_studenti.file_salvato_signal.connect(self._on_editor_file_salvato)

        self.editor_studenti._callback_pre_caricamento = self._verifica_prima_di_caricare
        self.editor_studenti._callback_pre_chiusura_file = self._verifica_prima_di_chiudere_file

        return self.tab_widget
