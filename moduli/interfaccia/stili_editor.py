# -*- coding: utf-8 -*-
"""Stile dei componenti dell’Editor, derivato dal tema corrente.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from moduli.interfaccia.tema import C

def stylesheet_componenti_dinamici():
    """Costruisce il QSS unico per schede e righe dei vincoli."""
    return f"""
        QGroupBox[editorScheda="X"] {{
            font-size: 14px; font-weight: bold;
            border: 2px solid {C("scheda_X_bordo")};
            border-radius: 8px; margin-top: 12px; padding-top: 18px;
            background-color: {C("scheda_X_sf")};
        }}
        QGroupBox[editorScheda="X"]::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 4px 12px; border-radius: 4px;
            background-color: {C("scheda_X_titolo_sf")};
            color: {C("scheda_X_titolo_txt")};
        }}
        QGroupBox[editorScheda="M"] {{
            font-size: 14px; font-weight: bold;
            border: 2px solid {C("scheda_M_bordo")};
            border-radius: 8px; margin-top: 12px; padding-top: 18px;
            background-color: {C("scheda_M_sf")};
        }}
        QGroupBox[editorScheda="M"]::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 4px 12px; border-radius: 4px;
            background-color: {C("scheda_M_titolo_sf")};
            color: {C("scheda_M_titolo_txt")};
        }}
        QGroupBox[editorScheda="F"] {{
            font-size: 14px; font-weight: bold;
            border: 2px solid {C("scheda_F_bordo")};
            border-radius: 8px; margin-top: 12px; padding-top: 18px;
            background-color: {C("scheda_F_sf")};
        }}
        QGroupBox[editorScheda="F"]::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 4px 12px; border-radius: 4px;
            background-color: {C("scheda_F_titolo_sf")};
            color: {C("scheda_F_titolo_txt")};
        }}
        QGroupBox[editorScheda="FISSO_M"] {{
            font-size: 14px; font-weight: bold;
            border: 2px solid {C("errore_bordo")};
            border-radius: 8px; margin-top: 12px; padding-top: 18px;
            background-color: {C("scheda_M_sf")};
        }}
        QGroupBox[editorScheda="FISSO_F"] {{
            font-size: 14px; font-weight: bold;
            border: 2px solid {C("errore_bordo")};
            border-radius: 8px; margin-top: 12px; padding-top: 18px;
            background-color: {C("scheda_F_sf")};
        }}
        QGroupBox[editorScheda="FISSO_M"]::title,
        QGroupBox[editorScheda="FISSO_F"]::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            padding: 4px 12px; border-radius: 4px;
            background-color: {C("errore_titolo_sf")};
            color: {C("errore_titolo_txt")};
        }}

        QComboBox[editorGenereIncompleto="1"] {{
            border: 2px solid {C("genere_ph_bordo")};
            background-color: {C("genere_ph_sf")};
        }}

        QComboBox[editorTipoVincolo="incompatibilita"] {{
            border: 1px solid {C("combo_incomp_bordo")};
            background-color: {C("combo_incomp_sf")};
            color: {C("combo_incomp_txt")};
            padding: 4px 8px; border-radius: 4px;
        }}
        QComboBox[editorTipoVincolo="affinita"] {{
            border: 1px solid {C("combo_aff_bordo")};
            background-color: {C("combo_aff_sf")};
            color: {C("combo_aff_txt")};
            padding: 4px 8px; border-radius: 4px;
        }}
        QComboBox[editorIncompleto="1"] {{
            border: 2px solid {C("combo_ph_bordo")};
            color: {C("combo_ph_txt")};
        }}
        QComboBox[editorTipoVincolo="incompatibilita"]::drop-down {{
            width: 28px; border-left: 1px solid {C("combo_incomp_bordo")};
            background-color: {C("combo_incomp_sf")};
        }}
        QComboBox[editorTipoVincolo="affinita"]::drop-down {{
            width: 28px; border-left: 1px solid {C("combo_aff_bordo")};
            background-color: {C("combo_aff_sf")};
        }}
        QComboBox[editorTipoVincolo="incompatibilita"] QAbstractItemView {{
            border: 1px solid {C("combo_incomp_bordo")};
            background-color: {C("combo_incomp_sf")};
            color: {C("combo_incomp_txt")};
            selection-background-color: {C("combo_incomp_selezione_sf")};
            selection-color: {C("combo_incomp_txt")}; outline: 0;
        }}
        QComboBox[editorTipoVincolo="affinita"] QAbstractItemView {{
            border: 1px solid {C("combo_aff_bordo")};
            background-color: {C("combo_aff_sf")};
            color: {C("combo_aff_txt")};
            selection-background-color: {C("combo_aff_selezione_sf")};
            selection-color: {C("combo_aff_txt")}; outline: 0;
        }}
        QComboBox[editorTipoVincolo] QAbstractItemView::item {{
            min-height: 26px;
        }}

        QScrollArea[editorRuolo="scroll_area"] {{
            border: 1px solid {C("bordo_normale")};
            border-radius: 4px;
            background-color: {C("editor_scroll_sf")};
        }}

        QFrame[editorRuolo="separatore"] {{
            background-color: {C("editor_sep")};
        }}
        QLabel[editorRuolo="label_incompatibilita"] {{
            font-weight: bold; color: {C("testo_incomp")}; font-size: 13px;
        }}
        QLabel[editorRuolo="label_affinita"] {{
            font-weight: bold; color: {C("testo_affinita")}; font-size: 13px;
        }}
        QLabel[editorAttenuato="1"] {{
            color: {C("testo_placeholder")};
        }}
        QLabel[editorRuolo="info_fisso"] {{
            color: {C("testo_arancione")}; font-style: italic;
            font-size: 11px; padding: 6px;
            border: 1px dashed {C("testo_arancione")};
            border-radius: 4px; background-color: rgba(255, 167, 38, 0.1);
        }}
        QPushButton[editorRuolo="aggiungi_incompatibilita"] {{
            background-color: {C("editor_btn_incomp_sf")};
            color: {C("editor_btn_incomp_txt")}; border-radius: 4px;
            padding: 6px 12px; font-size: 12px;
        }}
        QPushButton[editorRuolo="aggiungi_incompatibilita"]:hover {{
            background-color: {C("editor_btn_incomp_hover")};
        }}
        QPushButton[editorRuolo="aggiungi_affinita"] {{
            background-color: {C("editor_btn_aff_sf")};
            color: {C("editor_btn_aff_txt")}; border-radius: 4px;
            padding: 6px 12px; font-size: 12px;
        }}
        QPushButton[editorRuolo="aggiungi_affinita"]:hover {{
            background-color: {C("editor_btn_aff_hover")};
        }}
        QPushButton[editorRuolo="rimuovi_vincolo"] {{
            background-color: {C("btn_rosso_bg")}; color: white;
            font-size: 12px; border-radius: 4px; font-weight: bold;
            padding: 4px 10px;
        }}
        QPushButton[editorRuolo="rimuovi_vincolo"]:hover {{
            background-color: {C("btn_rosso_hover")};
        }}
    """

