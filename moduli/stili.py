# -*- coding: utf-8 -*-
"""Stili Qt dell'interfaccia principale di «PostiPerfetti».

Definisce il foglio di stile globale e rigenera gli stili inline dei widget
che non ereditano automaticamente il tema. Tutti i colori provengono da
tema.py.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from moduli.tema import C
# I tooltip sono finestre autonome: la palette applicativa ne aggiorna i
# colori senza forzare il restyle di tutti i widget.
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor


class StiliMixin:
    """Aggiunge alla finestra principale la gestione del tema Qt."""

    # Stile globale

    def setup_stili(self):
        """Applica alla finestra il tema attivo e aggiorna i tooltip Qt."""

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
                border-radius: 0px 6px 6px 6px;
                background-color: {C("sfondo_pannello")};
                top: -1px;
            }}

            QTabBar::tab {{
                background: {C("sfondo_tab_normale")};
                border: 1px solid {C("bordo_normale")};
                border-bottom: none;
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                color: {C("testo_secondario")};
            }}

            QTabBar::tab:selected {{
                background: {C("accento")};
                color: {C("selezione_testo")};
                font-weight: bold;
                margin-bottom: -1px;
            }}

            QTabBar::tab:!selected {{
                margin-top: 2px;
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

            QPushButton:focus {{
                border: 2px solid {C("bordo_focus")};
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

            QRadioButton:focus {{
                color: {C("bordo_focus")};
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

            QCheckBox:focus {{
                color: {C("bordo_focus")};
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

            QTextEdit:focus, QTableWidget:focus, QTabWidget:focus {{
                border: 2px solid {C("bordo_focus")};
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

        if hasattr(self, "editor_studenti"):
            stylesheet += (
                "\n"
                + self.editor_studenti._stylesheet_componenti_dinamici()
            )

        self.setStyleSheet(stylesheet)

        # I tooltip non ereditano lo stylesheet della finestra.
        palette = QApplication.instance().palette()
        palette.setColor(QPalette.ToolTipBase, QColor(C("sfondo_pannello")))
        palette.setColor(QPalette.ToolTipText, QColor(C("testo_principale")))
        QApplication.instance().setPalette(palette)

    # Label semantiche

    def _applica_stile_label_stato_classe(self, stato=None):
        """Applica la grammatica cromatica alla label «Stato classe»."""
        if stato is None:
            stato = self.label_studenti_caricati.property("stato_classe")
        stato = stato if stato in {"attenzione", "successo"} else "neutro"
        self.label_studenti_caricati.setProperty("stato_classe", stato)

        if stato == "attenzione":
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: {C("label_attenzione_bg")};
                color: {C("label_attenzione_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_attenzione_bordo")};
            """)
        elif stato == "successo":
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: {C("label_successo_bg")};
                color: {C("label_successo_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_successo_bordo")};
            """)
        else:
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: transparent;
                color: {C("testo_grigio")};
                border: none;
                padding: 0px;
                font-size: 13px;
                font-style: italic;
                font-weight: normal;
            """)

    def _applica_stile_label_capienza(self, stato=None):
        """Rende neutra la capienza normale e rossa solo l'insufficienza."""
        if stato is None:
            stato = self.label_posti_totali.property("stato_capienza")
        stato = "errore" if stato == "errore" else "neutro"
        self.label_posti_totali.setProperty("stato_capienza", stato)

        if stato == "errore":
            self.label_posti_totali.setStyleSheet(f"""
                background-color: {C("label_errore_bg")};
                color: white;
                font-weight: bold;
                font-size: 15px;
                padding: 8px;
                border: 3px solid {C("label_errore_bordo")};
                border-radius: 6px;
            """)
        else:
            self.label_posti_totali.setStyleSheet(f"""
                background-color: {C("label_capienza_bg")};
                color: {C("label_capienza_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_capienza_bordo")};
            """)

    # Stili inline

    def _aggiorna_stili_widget(self):
        """Rigenera gli stili inline all'avvio e dopo un cambio di tema."""

        def _stile_btn(bg, hover, disabled_bg=None, disabled_txt=None,
                       font_size=13, border_radius=6, padding="10px 20px",
                       testo="#ffffff", bordo=None, disabled_bordo=None):
            """Genera il CSS dei pulsanti, inclusi testo e bordo tematici."""
            bordo = bordo or bg
            disabled_bordo = disabled_bordo or disabled_bg
            s = f"""
                QPushButton {{
                    background-color: {bg};
                    color: {testo};
                    border: 1px solid {bordo};
                    font-size: {font_size}px;
                    font-weight: bold;
                    border-radius: {border_radius}px;
                    padding: {padding};
                }}
                QPushButton:hover {{
                    background-color: {hover};
                    border-color: {bordo};
                }}"""
            if disabled_bg and disabled_txt:
                s += f"""
                QPushButton:disabled {{
                    background-color: {disabled_bg};
                    color: {disabled_txt};
                    border-color: {disabled_bordo};
                }}"""
            return s

        self.input_nome_classe.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_pannello")};
                color: {C("testo_secondario")};
                border: 1px solid {C("bordo_normale")};
            }}
        """)

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
        self.btn_posti_meno.setStyleSheet(stile_btn_meno)
        self.btn_posti_piu.setStyleSheet(stile_btn_piu)

        # Gli stylesheet creati dalla factory incorporano i colori correnti e
        # devono quindi essere rigenerati quando cambia il tema.
        self.btn_istruzioni.setStyleSheet(
            _stile_btn(C("btn_indaco_bg"), C("btn_indaco_hover"),
                       font_size=13, padding="0px",
                       testo=C("btn_indaco_txt"), bordo=C("btn_indaco_bordo")))

        # Il pulsante del tema usa il colore del testo previsto dalla palette,
        # perciò richiede uno stile dedicato invece dell'helper standard.
        self.btn_toggle_tema.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_tema_bg")};
                color: {C("btn_tema_txt")};
                border: 1px solid {C("btn_tema_bordo")};
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_tema_hover")};
            }}
        """)

        # Il raggio pari a metà del lato mantiene circolare il pulsante Crediti.
        self.btn_crediti.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_crediti_bg")};
                color: {C("btn_crediti_txt")};
                font-size: 16px;
                font-weight: bold;
                border-radius: {self.btn_crediti.width() // 2}px;
                border: 1px solid {C("btn_crediti_bordo")};
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_crediti_hover")};
            }}
        """)

        self.btn_avvia_assegnazione.setStyleSheet(
            _stile_btn(C("btn_avvia_bg"), C("btn_avvia_hover"),
                       C("btn_avvia_disabled_bg"), C("btn_avvia_disabled_txt"),
                       font_size=16, border_radius=8,
                       testo=C("btn_avvia_txt"), bordo=C("btn_avvia_bordo"),
                       disabled_bordo=C("btn_avvia_disabled_bordo")))

        self.btn_salva_progetto.setStyleSheet(
            _stile_btn(C("btn_salva_bg"), C("btn_salva_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt"),
                       testo=C("btn_salva_txt"), bordo=C("btn_salva_bordo"),
                       disabled_bordo=C("btn_azione_disabled_bordo")))

        self.btn_export_excel.setStyleSheet(
            _stile_btn(C("btn_excel_bg"), C("btn_excel_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt"),
                       testo=C("btn_excel_txt"), bordo=C("btn_excel_bordo"),
                       disabled_bordo=C("btn_azione_disabled_bordo")))

        self.btn_export_report_txt.setStyleSheet(
            _stile_btn(C("btn_export_bg"), C("btn_export_hover"),
                       C("btn_azione_disabled_bg"), C("btn_azione_disabled_txt"),
                       testo=C("btn_export_txt"), bordo=C("btn_export_bordo"),
                       disabled_bordo=C("btn_azione_disabled_bordo")))

        self.btn_export_stats.setStyleSheet(
            _stile_btn(
                C("btn_statistiche_export_bg"),
                C("btn_statistiche_export_hover"),
                font_size=14,
                testo=C("btn_statistiche_export_txt"),
                bordo=C("btn_statistiche_export_bordo"),
            )
        )

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

        num_storico = len(self.config_app.config_data.get("storico_assegnazioni", []))
        if num_storico == 0:
            self.label_storico.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;"
            )

        # Le proprietà Qt conservano lo stato semantico durante il cambio tema.
        self._applica_stile_label_stato_classe()
        self._applica_stile_label_capienza()

        self.label_info_dispari.setStyleSheet(
            f"color: {C('testo_info')}; font-size: 13px; font-style: italic;"
        )

        # Lo stile inline del filtro non eredita il tema globale.
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

        # L'icona del banner è gestita dal refresh globale.
        self.label_hint_report.setText(
            "Per esportare il Report in formato .txt, vai nella scheda Aula."
        )
        self.label_hint_report.setStyleSheet(
            f'color: {C("testo_secondario")}; font-size: 14px; '
            f'font-style: italic; padding: 6px;'
        )

        self.label_storico_vuoto.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
        )
