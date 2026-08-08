# -*- coding: utf-8 -*-
"""Rendering del risultato corrente nella finestra principale.

Il mixin gestisce esclusivamente la superficie Aula e la presentazione del
Report dell'assegnazione mensile già calcolata. Calcolo, salvataggio ed export
restano nei rispettivi moduli applicativi.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtCore import Qt, QEventLoop

from moduli.aula import ConfigurazioneAula
from moduli.algoritmo import AssegnatorePosti
from moduli.tema import C
from moduli.profilo_gui import ProfiloGUI
from moduli.utilita import applica_icona_etichetta


class RisultatoCorrenteUIMixin:
    """Visualizza, aggiorna e azzera Aula e Report correnti."""

    def _forza_ridisegno_aula(self):
        """Completa subito il ridisegno della superficie Aula.

        I popup riepilogativi sono modali: senza un repaint sincrono, il viewport
        della QScrollArea può conservare per qualche istante i pixel della
        geometria precedente, soprattutto passando da coppie a terzetti. Il
        metodo aggiorna layout, widget e viewport prima di aprire il popup, senza
        accettare input dell’utente durante il breve ciclo di eventi.
        """
        profilo = ProfiloGUI("ridisegno_aula")
        try:
            def aggiorna_layout():
                self.layout_griglia_aula.invalidate()
                self.layout_griglia_aula.activate()
                self.widget_aula.updateGeometry()

            profilo.misura("layout_e_geometria", aggiorna_layout)
            profilo.misura("repaint_widget_aula", self.widget_aula.repaint)

            scroll_aula = getattr(self, "scroll_aula", None)
            if scroll_aula is not None:
                profilo.misura(
                    "repaint_viewport_scroll",
                    scroll_aula.viewport().repaint,
                )
                profilo.misura("repaint_scroll", scroll_aula.repaint)

            profilo.misura("repaint_tab_aula", self.tab_aula.repaint)
            profilo.misura(
                "process_events_senza_input",
                lambda: QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
                ),
            )
        finally:
            profilo.chiudi()

    def _resetta_tab_aula_report(self):
        """Rimuove dall’interfaccia l’assegnazione corrente."""

        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            widget = child.widget()
            if widget is not None:
                # setParent(None) rimuove subito il widget dalla superficie visibile;
                # deleteLater() ne completa poi la distruzione in sicurezza.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self.text_report.clear()

        self.widget_hint_report.setVisible(False)

        self.btn_salva_progetto.setEnabled(False)
        self.btn_salva_progetto.setToolTip(
            "Disponibile dopo aver generato un'assegnazione."
        )
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "Disponibile dopo aver salvato un'assegnazione."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "Disponibile dopo aver salvato un'assegnazione."
        )

        self.sessione.azzera_risultato_mensile()

        self._precedenti_altro_modo = 0
        self._statistiche_generali_terzetti_correnti = []

        # La superficie vuota deve diventare visibile prima che inizi una nuova
        # elaborazione sincrona, altrimenti il viewport può mantenere il vecchio
        # fotogramma fino alla chiusura del popup successivo.
        self._forza_ridisegno_aula()

    def _visualizza_risultati(self, assegnatore: AssegnatorePosti):
        """Aggiorna aula e report con l’assegnazione completata."""

        self._aggiorna_visualizzazione_aula(assegnatore.configurazione_aula)

        self._aggiorna_report_testuale(
            assegnatore,
            nome_assegnazione=self.sessione.mensile.nome,
            data_creazione=self.sessione.mensile.data_creazione,
        )

        self.widget_hint_report.setVisible(True)

        self.tab_widget.setCurrentIndex(1)

    def _aggiorna_visualizzazione_aula(self, configurazione_aula: ConfigurazioneAula):
        """Ridisegna la griglia dell’aula corrente."""

        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            widget = child.widget()
            if widget is not None:
                # Evita che widget in attesa di deleteLater() restino dipinti
                # sotto la nuova configurazione durante un popup modale.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        griglia_invertita = list(reversed(configurazione_aula.griglia))
        riga_display = 0
        for riga in griglia_invertita:

            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                continue

            for col_idx, posto in enumerate(riga):

                if posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:

                        widget_posto = self.crea_widget_posto(posto, merged=True)
                        self.layout_griglia_aula.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)

                else:

                    widget_posto = self.crea_widget_posto(posto)
                    self.layout_griglia_aula.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1

        # Il riepilogo viene aperto subito dopo questo metodo. Si completa il
        # repaint ora, così il popup non congela nel viewport tracce del layout
        # precedente mentre la nuova geometria è già presente.
        self._forza_ridisegno_aula()

    def crea_widget_posto(self, posto, merged=False) -> QWidget:
        """Crea il widget grafico di un posto o di un arredo dell’aula."""

        widget = QLabel()

        larghezza_min = 250 if merged else 120
        widget.setMinimumSize(larghezza_min, 60)
        widget.setAlignment(Qt.AlignCenter)

        widget.setStyleSheet(f"border: 1px solid {C('banco_libero_bordo')}; margin: 1px;")

        if posto.tipo == 'banco':
            if posto.occupato_da:

                nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                widget.setText(nome_completo)
                widget.setWordWrap(True)
                widget.setStyleSheet(f"""
                    border: 2px solid {C("banco_occupato_bordo")};
                    background-color: {C("banco_occupato_sf")};
                    color: {C("banco_occupato_txt")};
                    font-weight: bold;
                    font-size: 11px;
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip(f"Studente: {nome_completo}")
            else:

                applica_icona_etichetta(widget, "armchair", 28)
                widget.setStyleSheet(f"""
                    border: 2px dashed {C("banco_libero_bordo")};
                    background-color: {C("banco_libero_sf")};
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip("Posto libero")

        elif posto.tipo == 'cattedra':

            if merged:
                widget.setText("CATTEDRA")
            else:
                applica_icona_etichetta(widget, "school", 28)
            widget.setStyleSheet(f"""
                border: 2px solid {C("cattedra_bordo")};
                background-color: {C("cattedra_sf")};
                color: {C("cattedra_bordo")};
                font-weight: bold;
                font-size: 13px;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("Cattedra")

        elif posto.tipo == 'lim':

            if merged:
                widget.setText("LIM")
            else:
                applica_icona_etichetta(widget, "monitor", 28)
            widget.setStyleSheet(f"""
                border: 2px solid {C("lim_bordo")};
                background-color: {C("lim_sf")};
                color: {C("lim_bordo")};
                font-weight: bold;
                font-size: 13px;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("LIM")

        elif posto.tipo == 'lavagna':

            if merged:
                widget.setText("LAVAGNA")
            else:
                applica_icona_etichetta(widget, "presentation", 28)
            widget.setStyleSheet(f"""
                border: 2px solid {C("lavagna_bordo")};
                background-color: {C("lavagna_sf")};
                color: {C("lavagna_bordo")};
                font-weight: bold;
                font-size: 13px;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("Lavagna")

        else:
            widget.setText("")
            widget.setStyleSheet("""
                border: none;
                background-color: transparent;
                margin: 1px;
            """)

        return widget
