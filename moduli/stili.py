    # =================================================================
"""
    «PostiPerfetti» v. 2.0 — Programma per l'assegnazione automatica
    dei posti degli allievi in una classe scolastica,
    con gestione di vincoli, affinità, incompatibilità,
    rotazione allievi e storico assegnazioni.

    Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD)
    Licenza: GNU GPLv3

    ▣ Questo software è libero: puoi usarlo, copiarlo, studiarlo
    e redistribuirlo liberamente.
    ▣ Se lo modifichi e redistribuisci, sei tenuto a mantenere
    l'attribuzione al creatore originale e a rendere pubblico
    il codice sorgente delle tue modifiche con la stessa licenza GPLv3.
    ▣ Questo programma è distribuito «così com'è», senza alcuna
    garanzia espressa o implicita.
"""
    # =================================================================
"""
    Gestione degli stili grafici.

    Contiene la classe StiliMixin con 2 metodi estratti dalla classe
    FinestraPostiPerfetti:
    • setup_stili()                → Stylesheet globale (CSS Qt completo)
    • _aggiorna_stili_widget()     → Stili inline per widget specifici

    USO (Mixin Pattern):
        La classe StiliMixin va aggiunta come classe base a FinestraPostiPerfetti:
            from moduli.stili import StiliMixin
            class FinestraPostiPerfetti(QMainWindow, StatisticheMixin, StiliMixin):
            ...
    I metodi usano `self` perché, una volta mixata, `self` è l'istanza di
    FinestraPostiPerfetti — esattamente come se fossero definiti lì dentro.
"""

# Importa la funzione C() per leggere i colori del tema attivo
from moduli.tema import C
# QPalette + QColor: per impostare i colori dei tooltip a livello applicazione.
# I tooltip Qt sono finestre top-level, NON figli della QMainWindow, quindi
# non ereditano dallo stylesheet della finestra.
# Usare QPalette è MOLTO più veloce di QApplication.setStyleSheet():
# quest'ultimo forza il restyle di TUTTI i widget ad ogni chiamata,
# mentre setPalette aggiorna solo i ruoli colore specificati → istantaneo.
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor


class StiliMixin:
    """
    Mixin che aggiunge la gestione degli stili a FinestraPostiPerfetti.

    Attributi usati da self (devono esistere nella classe principale):
        - self.setStyleSheet()               (ereditato da QMainWindow)
        - self.input_nome_classe             (QLineEdit)
        - self.input_num_file                (QLineEdit)
        - self.input_posti_fila              (QLineEdit)
        - self.btn_file_meno, btn_file_piu   (QPushButton)
        - self.btn_posti_meno, btn_posti_piu (QPushButton)
        - self.btn_istruzioni                (QPushButton)
        - self.btn_toggle_tema               (QPushButton)
        - self.btn_crediti                   (QPushButton)
        - self.btn_avvia_assegnazione        (QPushButton)
        - self.btn_salva_progetto            (QPushButton)
        - self.btn_export_excel              (QPushButton)
        - self.btn_export_report_txt         (QPushButton)
        - self.btn_export_stats              (QPushButton)
        - self.btn_aiuto_aula               (QPushButton)
        - self.label_storico                 (QLabel)
        - self.label_studenti_caricati       (QLabel)
        - self.label_info_dispari            (QLabel)
        - self.filtro_classe_combo           (ComboBoxProtetto)
        - self.config_app                    (ConfigurazioneApp)
    """

    # =================================================================
    # STYLESHEET GLOBALE — Tema completo per tutta l'applicazione
    # =================================================================

    def setup_stili(self):
        """
        Applica il tema attivo all'interfaccia principale.
        I colori vengono letti dal dizionario TEMI tramite la funzione C(),
        quindi basta cambiare TEMA_ATTIVO per aggiornare l'intera interfaccia.
        """

        # Costruisce lo stylesheet completo usando i colori del tema attivo.
        # Ogni C("nome") restituisce il colore corretto per scuro o chiaro.
        stylesheet = f"""
            /* === FINESTRA PRINCIPALE === */
            QMainWindow {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            QWidget {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            /* === GRUPPI E CONTAINER === */
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {C("bordo_normale")};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: {C("sfondo_pannello")};
                color: {C("testo_principale")};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            /* === TAB WIDGET === */
            QTabWidget::pane {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_pannello")};
            }}

            QTabBar::tab {{
                background: {C("sfondo_tab_normale")};
                border: 1px solid {C("bordo_normale")};
                padding: 10px 18px;
                margin-right: 2px;
                border-radius: 4px 4px 0px 0px;
                color: {C("testo_secondario")};
            }}

            QTabBar::tab:selected {{
                background: {C("accento")};
                color: {C("selezione_testo")};
                font-weight: bold;
                border-bottom-color: {C("accento")};
            }}

            QTabBar::tab:hover:!selected {{
                background: {C("btn_hover")};
                color: {C("testo_principale")};
            }}

            /* === BOTTONI === */
            QPushButton {{
                padding: 10px 16px;
                border-radius: 6px;
                border: 1px solid {C("bordo_leggero")};
                background-color: {C("btn_sfondo")};
                color: {C("testo_principale")};
                font-weight: bold;
            }}

            QPushButton:hover {{
                background-color: {C("btn_hover")};
                border: 1px solid {C("bordo_normale")};
            }}

            QPushButton:pressed {{
                background-color: {C("btn_premuto")};
            }}

            QPushButton:disabled {{
                background-color: {C("btn_disabilitato_sf")};
                color: {C("btn_disabilitato_txt")};
                border: 1px solid {C("bordo_normale")};
            }}

            /* === INPUT FIELDS === */
            QLineEdit, QSpinBox, QComboBox {{
                padding: 8px 12px;
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
            }}

            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 2px solid {C("bordo_focus")};
                background-color: {C("sfondo_input")};
            }}

            QLineEdit::placeholder {{
                color: {C("testo_placeholder")};
            }}

            /* === SLIDER === */
            QSlider::groove:horizontal {{
                border: 1px solid {C("bordo_normale")};
                height: 6px;
                background: {C("sfondo_input")};
                margin: 2px 0;
                border-radius: 3px;
            }}

            QSlider::handle:horizontal {{
                background: {C("accento")};
                border: 2px solid {C("accento_scuro")};
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}

            QSlider::handle:horizontal:hover {{
                background: {C("accento_hover")};
            }}

            QSlider::sub-page:horizontal {{
                background: {C("accento")};
                border-radius: 3px;
            }}

            /* === RADIO BUTTON === */
            QRadioButton {{
                color: {C("testo_principale")};
                spacing: 8px;
            }}

            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid {C("bordo_leggero")};
                background-color: {C("sfondo_input")};
            }}

            QRadioButton::indicator:checked {{
                background-color: {C("accento")};
                border: 2px solid {C("accento_scuro")};
            }}

            QRadioButton::indicator:hover {{
                border: 2px solid {C("accento")};
            }}

            /* === CHECKBOX === */
            QCheckBox {{
                color: {C("testo_principale")};
                spacing: 8px;
            }}

            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {C("bordo_leggero")};
                border-radius: 3px;
                background-color: {C("sfondo_input")};
            }}

            QCheckBox::indicator:checked {{
                background-color: {C("accento")};
                border: 2px solid {C("accento_scuro")};
                font-weight: bold;
            }}

            /* === PROGRESS BAR === */
            QProgressBar {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                text-align: center;
                font-weight: bold;
            }}

            QProgressBar::chunk {{
                background-color: {C("accento")};
                border-radius: 4px;
            }}

            /* === TEXT EDIT === */
            QTextEdit {{
                border: 2px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_testo_area")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
            }}

            /* === TABLE === */
            QTableWidget {{
                gridline-color: {C("bordo_normale")};
                background-color: {C("sfondo_pannello")};
                alternate-background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
            }}

            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {C("bordo_normale")};
            }}

            QTableWidget::item:selected {{
                background-color: {C("accento")};
                color: {C("selezione_testo")};
            }}

            QHeaderView::section {{
                background-color: {C("sfondo_header_tabella")};
                color: {C("testo_principale")};
                padding: 8px;
                border: 1px solid {C("bordo_normale")};
                font-weight: bold;
            }}

            /* === LABEL === */
            QLabel {{
                color: {C("testo_principale")};
            }}

            /* === SCROLL BAR === */
            QScrollBar:vertical {{
                background: {C("sfondo_input")};
                width: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical {{
                background: {C("bordo_leggero")};
                min-height: 20px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {C("accento")};
            }}

            QScrollBar:horizontal {{
                background: {C("sfondo_input")};
                height: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal {{
                background: {C("bordo_leggero")};
                min-width: 20px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: {C("accento")};
            }}

            /* === SPIN BOX === */
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                background-color: {C("sfondo_input_alt")};
                border: 1px solid {C("bordo_leggero")};
            }}

            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {C("accento")};
            }}

            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
            }}

            /* === COMBO BOX === */
            QComboBox::drop-down {{
                border: none;
                width: 20px;
                background-color: {C("sfondo_input_alt")};
            }}

            QComboBox::down-arrow {{
                width: 8px;
                height: 8px;
                background: {C("testo_principale")};
            }}

            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
                border: 1px solid {C("bordo_leggero")};
            }}

            /* === TOOLTIP — Sfondo e testo espliciti per evitare === */
            /* === testo bianco su sfondo chiaro (KDE Plasma/Wayland) === */
            QToolTip {{
                background-color: {C("sfondo_pannello")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                padding: 4px 8px;
            }}
        """

        # Applica il tema all'intera finestra principale.
        # Tutti i widget figli ereditano questi stili salvo override locali.
        self.setStyleSheet(stylesheet)

        # === TOOLTIP VIA PALETTE (istantaneo, senza restyle globale) ===
        # I tooltip Qt sono finestre top-level: NON ereditano da self.setStyleSheet().
        palette = QApplication.instance().palette()
        palette.setColor(QPalette.ToolTipBase, QColor(C("sfondo_pannello")))
        palette.setColor(QPalette.ToolTipText, QColor(C("testo_principale")))
        QApplication.instance().setPalette(palette)

    # =================================================================
    # STILI INLINE — Widget che non ereditano dallo stylesheet globale
    # =================================================================

    def _aggiorna_stili_widget(self):
        """
        Riapplica gli stili inline ai widget che non ereditano
        automaticamente dallo stylesheet globale della finestra.
        Chiamato sia all'avvio (per caricare il tema salvato)
        sia al cambio tema (toggle scuro/chiaro).

        Include:
        - Campo nome classe (read-only)
        - Campi numerici file/posti e bottoni +/−
        - Tutti i bottoni standard (Istruzioni, Tema, Crediti, Avvia,
          Salva, Excel, TXT, Statistiche, Aiuto aula)
        - Label storico
        """

        # === Helper: genera lo stylesheet per un bottone standard ===
        # Evita ripetizione del pattern CSS per i bottoni con factory crea_bottone().
        # Al cambio tema, i colori C() producono valori diversi → lo stile si aggiorna.
        def _stile_btn(bg, hover, disabled_bg=None, disabled_txt=None,
                       font_size=13, border_radius=6, padding="10px 20px"):
            """Genera la stringa CSS per un bottone standard."""
            s = f"""
                QPushButton {{
                    background-color: {bg};
                    color: white;
                    font-size: {font_size}px;
                    font-weight: bold;
                    border-radius: {border_radius}px;
                    padding: {padding};
                }}
                QPushButton:hover {{
                    background-color: {hover};
                }}"""
            if disabled_bg and disabled_txt:
                s += f"""
                QPushButton:disabled {{
                    background-color: {disabled_bg};
                    color: {disabled_txt};
                }}"""
            return s

        # --- Campo nome classe (read-only: sfondo leggermente diverso) ---
        self.input_nome_classe.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_pannello")};
                color: {C("testo_secondario")};
                border: 1px solid {C("bordo_normale")};
            }}
        """)

        # --- Campi numerici file/posti ---
        stile_campo_numero = f"""
            QLineEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
        """
        self.input_num_file.setStyleSheet(stile_campo_numero)
        self.input_posti_fila.setStyleSheet(stile_campo_numero)

        # --- Bottoni spinbox +/− (usano chiavi semantiche dedicate) ---
        stile_btn_meno = f"""
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
        """
        stile_btn_piu = f"""
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
        """
        self.btn_file_meno.setStyleSheet(stile_btn_meno)
        self.btn_file_piu.setStyleSheet(stile_btn_piu)
        self.btn_posti_meno.setStyleSheet(stile_btn_meno)
        self.btn_posti_piu.setStyleSheet(stile_btn_piu)

        # --- Bottoni standard: rigenerazione stili per cambio tema ---
        # I bottoni creati con crea_bottone() hanno lo stylesheet "congelato"
        # al momento della creazione. Al cambio tema, C() restituisce i nuovi
        # colori e questi setStyleSheet() li aggiornano.

        # Bottone Istruzioni (indaco)
        self.btn_istruzioni.setStyleSheet(
            _stile_btn(C("btn_indaco_bg"), C("btn_indaco_hover"), font_size=14))

        # Bottone Toggle tema (ambra)
        self.btn_toggle_tema.setStyleSheet(
            _stile_btn(C("btn_tema_bg"), C("btn_tema_hover"),
                       font_size=12, padding="8px 14px"))

        # Bottone Crediti (grigio-blu, rotondo — CSS speciale)
        self.btn_crediti.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_crediti_bg")};
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_crediti_hover")};
            }}
        """)

        # Bottone Avvia assegnazione (verde, con disabled)
        self.btn_avvia_assegnazione.setStyleSheet(
            _stile_btn(C("btn_avvia_bg"), C("btn_avvia_hover"),
                       C("btn_avvia_disabled_bg"), C("btn_avvia_disabled_txt"),
                       font_size=16, border_radius=8))

        # Bottone Salva (verde scuro, con disabled)
        self.btn_salva_progetto.setStyleSheet(
            _stile_btn(C("btn_salva_bg"), C("btn_salva_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt")))

        # Bottone Export Excel (azzurro, con disabled)
        self.btn_export_excel.setStyleSheet(
            _stile_btn(C("btn_excel_bg"), C("btn_excel_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt")))

        # Bottone Export TXT (arancione, con disabled)
        self.btn_export_report_txt.setStyleSheet(
            _stile_btn(C("btn_export_bg"), C("btn_export_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt")))

        # Bottone Export Statistiche (arancione, senza disabled)
        self.btn_export_stats.setStyleSheet(
            _stile_btn(C("btn_export_bg"), C("btn_export_hover"), font_size=14))

        # Bottone Aiuto aula (?) — indaco, rotondo — CSS speciale
        self.btn_aiuto_aula.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_indaco_bg")};
                color: white;
                font-weight: bold;
                font-size: 15px;
                border-radius: 16px;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: {C("btn_indaco_hover")}; }}
        """)

        # --- Label storico (se non ci sono dati, rimane grigia) ---
        num_storico = len(self.config_app.config_data.get("storico_assegnazioni", []))
        if num_storico == 0:
            self.label_storico.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;"
            )

        # --- Label studenti caricati (stato grigio iniziale) ---
        # Riapplica solo se non contiene già dati (evita sovrascrittura di colori verdi/rossi)
        testo = self.label_studenti_caricati.text()
        if "Nessun file" in testo or "Nuova classe" in testo:
            self.label_studenti_caricati.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 13px; font-style: italic;"
            )

        # --- Label info dispari ---
        self.label_info_dispari.setStyleSheet(
            f"color: {C('testo_info')}; font-size: 13px; font-style: italic;"
        )

        # --- Combo filtro classi (tab Statistiche) ---
        # Lo stylesheet inline non eredita dal tema globale → rigenerazione esplicita
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

        # --- Banner hint nella tab Report (rich text) ---
        # Rigenera il testo HTML con il colore del nuovo tema.
        self.label_hint_report.setText(
            f'<p align="center" style="color: {C("testo_secondario")}; '
            f'font-size: 14px; font-style: italic; padding: 6px;">'
            f'💡 Per esportare il Report in formato .txt, vai nella tab 🏫 Aula.'
            f'</p>'
        )

        # --- Placeholder storico vuoto ---
        self.label_storico_vuoto.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
        )
