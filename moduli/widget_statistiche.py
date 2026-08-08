# -*- coding: utf-8 -*-
"""Renderer Qt delle righe statistiche strutturate.

Trasforma le righe prodotte da ``statistiche_generali.py`` in widget con icone
Lucide separate dal testo. La scelta delle segnalazioni resta nel modulo puro
``righe_statistiche.py``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

from moduli.righe_statistiche import seleziona_righe_segnalazioni
from moduli.statistiche_generali import render_statistiche_html
from moduli.utilita import applica_icona_etichetta


def crea_widget_righe_statistiche(
        righe, *, solo_segnalazioni=False, sfondo_trasparente=False):
    """Renderizza righe statistiche con icone Lucide separate dal testo."""
    contenitore = QWidget()
    if sfondo_trasparente:
        contenitore.setAutoFillBackground(False)
        contenitore.setStyleSheet(
            "background-color: transparent; border: none;"
        )
    layout = QVBoxLayout(contenitore)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    righe_visibili = (
        seleziona_righe_segnalazioni(righe)
        if solo_segnalazioni
        else list(righe or [])
    )

    for riga in righe_visibili:
        riga_widget = QWidget()
        if sfondo_trasparente:
            riga_widget.setAutoFillBackground(False)
            riga_widget.setStyleSheet(
                "background-color: transparent; border: none;"
            )
        riga_layout = QHBoxLayout(riga_widget)
        riga_layout.setContentsMargins(0, 0, 0, 0)
        riga_layout.setSpacing(6)

        icona_nome = riga.get("icona_ui")
        if icona_nome:
            icona = QLabel()
            icona.setFixedSize(18, 18)
            icona.setAlignment(Qt.AlignCenter)
            if sfondo_trasparente:
                icona.setAutoFillBackground(False)
                icona.setStyleSheet(
                    "background-color: transparent; border: none;"
                )
            applica_icona_etichetta(icona, icona_nome, 16)
            riga_layout.addWidget(icona, alignment=Qt.AlignTop)
        else:
            riga_layout.addSpacing(24)

        testo_html = render_statistiche_html([riga])[0]
        etichetta = QLabel(testo_html)
        etichetta.setTextFormat(Qt.RichText)
        etichetta.setWordWrap(True)
        if sfondo_trasparente:
            etichetta.setAutoFillBackground(False)
            etichetta.setStyleSheet(
                "background-color: transparent; border: none;"
            )
        riga_layout.addWidget(etichetta, 1)
        layout.addWidget(riga_widget)

    return contenitore
