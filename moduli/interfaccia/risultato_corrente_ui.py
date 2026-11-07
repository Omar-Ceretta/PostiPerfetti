# -*- coding: utf-8 -*-
"""Rendering del risultato corrente nella finestra principale.

Il mixin gestisce esclusivamente la superficie Aula e la presentazione del
Report dell'assegnazione mensile già calcolata. Calcolo, salvataggio ed export
restano nei rispettivi moduli applicativi.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import QApplication, QWidget, QLabel, QHBoxLayout, QDialog
from PySide6.QtCore import Qt, QEventLoop, QTimer

from moduli.dominio.aula import ConfigurazioneAula, PostoAula
from moduli.interfaccia.arredi_visualizzazione import ETICHETTA_DOCENTE, riga_solo_arredi
from moduli.interfaccia.tema import C
from moduli.processi.profilo_gui import ProfiloGUI
from moduli.interfaccia.utilita import (
    applica_icona_etichetta, mostra_popup_semantico,
)
from moduli.interfaccia.statistiche_generali import applica_formattazione_statistiche_generali
from moduli.interfaccia.esportazione import evidenzia_riutilizzi
from moduli.dominio.adozione_dragdrop_mensile import prepara_risultato_editato
from moduli.dominio.presentazione_aula_personalizzata import (
    costruisci_configurazione_aula_personalizzata,
)


class RisultatoCorrenteUIMixin:
    """Visualizza, aggiorna e azzera Aula e Report correnti."""

    def _forza_ridisegno_aula(self):
        """Completa subito il ridisegno della superficie Aula.

        I popup riepilogativi sono modali: senza un repaint sincrono, il viewport
        della QScrollArea può conservare per qualche istante i pixel della
        geometria precedente dopo una modifica del Layout. Il
        metodo aggiorna layout, widget e viewport prima di aprire il popup, senza
        accettare input dell’utente durante il breve ciclo di eventi.
        """
        # Se un commit tiene sospesi gli aggiornamenti, il repaint intermedio
        # non aggiunge nulla: verrà eseguito automaticamente alla riattivazione.
        if not self.tab_aula.updatesEnabled():
            return
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

    def _aggiorna_testo_bottone_modifica_posti(self) -> None:
        """Mostra il ripristino solo per una proposta ritoccata e non salvata."""
        bottone = getattr(self, 'btn_prova_dragdrop', None)
        if bottone is None:
            return
        mensile = self.sessione.mensile
        dati = mensile.dati_personalizzata
        ritoccata = bool(
            mensile.non_salvata and dati and dati.get('modificata_manualmente')
        )
        bottone.setText(
            'Modifica/ripristina posti' if ritoccata else 'Modifica posti'
        )
        bottone.setToolTip(
            'Modifica gli studenti o ripristina la disposizione automatica, '
            'prima del salvataggio nello Storico.'
            if ritoccata else
            'Modifica la proposta prima di salvarla nello Storico.'
        )

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

        if hasattr(self, "btn_prova_dragdrop"):
            self.btn_prova_dragdrop.setEnabled(False)
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

        self._anteprima_fisica_standard_corrente = None
        self.sessione.azzera_risultato_mensile()
        self._aggiorna_testo_bottone_modifica_posti()
        self._vista_aula_personalizzata_corrente = None
        self._configurazione_aula_visualizzata = None

        self._precedenti_altro_modo = 0
        self._precedenti_altri_modi = {}
        self._statistiche_generali_terzetti_correnti = []

        # La superficie vuota deve diventare visibile prima che inizi una nuova
        # elaborazione sincrona, altrimenti il viewport può mantenere il vecchio
        # fotogramma fino alla chiusura del popup successivo.
        self._forza_ridisegno_aula()


    def _aggiorna_visualizzazione_aula(self, configurazione_aula: ConfigurazioneAula):
        """Ridisegna la griglia dell’aula corrente."""
        self._configurazione_aula_visualizzata = configurazione_aula

        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            widget = child.widget()
            if widget is not None:
                # Evita che widget in attesa di deleteLater() restino dipinti
                # sotto la nuova configurazione durante un popup modale.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self._vista_aula_personalizzata_corrente = None

        griglia_invertita = list(reversed(configurazione_aula.griglia))
        riga_display = 0
        for indice, riga in enumerate(griglia_invertita):

            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                riga_logica = len(configurazione_aula.griglia) - indice - 1
                if riga_logica in getattr(configurazione_aula, 'righe_spazio_personalizzato', ()):
                    fascia = QWidget()
                    fascia.setMinimumHeight(60)
                    self.layout_griglia_aula.addWidget(fascia, riga_display, 0, 1, len(riga))
                    riga_display += 1
                continue

            if riga_solo_arredi(riga):
                # Geometria legacy standard: un'unica cattedra centrale,
                # senza inventare la presenza e posizione di LIM/lavagna.
                self._inserisci_postazione_docente_centrata(
                    self.layout_griglia_aula, riga_display, len(riga)
                )
                riga_display += 1
                continue

            for col_idx, posto in enumerate(riga):
                if posto.tipo in ('lim', 'lavagna'):
                    continue

                if posto.tipo in ('cattedra', 'postazione_docente'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:

                        widget_posto = self.crea_widget_posto(posto, merged=True)
                        self.layout_griglia_aula.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)

                else:

                    widget_posto = self.crea_widget_posto(posto, configurazione=configurazione_aula)
                    self.layout_griglia_aula.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1

        # Il riepilogo viene aperto subito dopo questo metodo. Si completa il
        # repaint ora, così il popup non congela nel viewport tracce del layout
        # precedente mentre la nuova geometria è già presente.
        self._forza_ridisegno_aula()

    def _proposta_dragdrop_ancora_valida(self, dati):
        """Evita di adottare una bozza dopo cambi di classe o sessione."""
        return bool(
            self.sessione.mensile.non_salvata
            and self.sessione.mensile.dati_personalizzata is dati
            and getattr(self, '_risultato_mensile_personalizzata_p31', None) is dati
            and getattr(self, 'worker_thread', None) is None
            and getattr(self, 'season_worker', None) is None
            and not self.sessione.annuale.in_corso
        )

    def _apri_prova_dragdrop(self):
        """Apre D3; il commit parte dopo la scomparsa grafica del dialogo."""
        dati = self.sessione.mensile.dati_personalizzata
        if not (dati and self._proposta_dragdrop_ancora_valida(dati)):
            return
        from moduli.interfaccia.dialogo_dragdrop_prova import DialogoProvaDragDrop

        dialogo = DialogoProvaDragDrop(
            self, dati, lambda: self._proposta_dragdrop_ancora_valida(dati),
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        # Copia i soli riferimenti al modello: non conserviamo il QWidget
        # nella callback. Il dialogo è già stato chiuso da QDialog.accept().
        bozza = dialogo.bozza
        disposizione_all_apertura = dialogo.disposizione_all_apertura

        # La chiusura della finestra è inviata al window manager, ma il
        # compositore può completarla solo quando Qt torna al suo event loop.
        # Evita di ricostruire immediatamente Aula/Report (e aprire un altro
        # popup) sullo stesso stack di dialogo.exec(): questo può lasciare
        # per un istante un bordo residuo su Wayland. Il breve intervallo
        # permette il normale aggiornamento grafico, senza processEvents(),
        # sleep() o eventi annidati. Il context QObject annulla la callback
        # se la finestra principale viene distrutta nel frattempo.
        QTimer.singleShot(
            60, self,
            lambda: self._completa_adozione_dragdrop(
                dati, bozza, disposizione_all_apertura,
            ),
        )

    def _completa_adozione_dragdrop(self, dati, bozza, disposizione_all_apertura):
        """Valida e adotta la bozza solo se la stessa proposta è ancora attiva."""
        if not self._proposta_dragdrop_ancora_valida(dati):
            # Una sessione sostituita o già salvata non va modificata.
            return
        ancora_valida = lambda: self._proposta_dragdrop_ancora_valida(dati)
        try:
            proposta = prepara_risultato_editato(
                dati, bozza,
                disposizione_all_apertura=disposizione_all_apertura,
            )
            foto = proposta['fotografia_generazione']
            configurazione = costruisci_configurazione_aula_personalizzata(
                proposta['layout_visuale'], proposta['collocazioni'],
            )
            report = self.prepara_report_personalizzata(
                proposta['gruppi'], proposta['collocazioni'],
                nome_classe=self.sessione.mensile.nome_classe,
                studenti=foto.crea_studenti(),
                configurazione_aula=configurazione,
                genere_misto=self.sessione.mensile.genere_misto,
                nome_assegnazione=self.sessione.mensile.nome,
                data_creazione=self.sessione.mensile.data_creazione,
                adiacenze_gia_usate=set(proposta['adiacenze_prima']),
                modificata_manualmente=bool(proposta.get('modificata_manualmente')),
            )
            proposta.update(
                configurazione_aula=configurazione,
                report_completo=report.testo,
                statistiche_generali=[dict(riga) for riga in report.statistiche],
            )
            # Secondo controllo prima del commit: nessun risultato scaduto.
            if not ancora_valida():
                raise ValueError('La proposta è cambiata durante la preparazione.')
        except Exception as errore:
            mostra_popup_semantico(
                self, 'Modifiche non adottate',
                'Non è stato possibile validare e aggiornare la disposizione.',
                'circle-x', testo_informativo=str(errore),
            )
            return

        # Una sola fonte di verità: conserviamo l'identità del dizionario
        # condiviso tra stato Mensile, salvataggio e controlli di sessione.
        dati.update(proposta)
        # Non mostrare fotogrammi intermedi: Aula e Report vengono aggiornati
        # per intero prima di riabilitare il disegno. Evita i micro-flash Qt
        # senza cambiare modello, viewport o politica di ridisegno generale.
        self.tab_aula.setUpdatesEnabled(False)
        self.text_report.setUpdatesEnabled(False)
        try:
            self._configurazione_aula_personalizzata_corrente = configurazione
            self._aggiorna_visualizzazione_aula(configurazione)
            self._adotta_riepilogo_report_personalizzata(report)
            self.text_report.setPlainText(report.testo)
            evidenzia_riutilizzi(self.text_report)
            applica_formattazione_statistiche_generali(
                self.text_report, proposta['statistiche_generali'],
            )
        finally:
            self.text_report.setUpdatesEnabled(True)
            self.tab_aula.setUpdatesEnabled(True)
        self._aggiorna_testo_bottone_modifica_posti()
        mostra_popup_semantico(
            self, 'Modifiche adottate',
            'La disposizione Mensile è stata aggiornata.', 'circle-check',
            testo_informativo=(
                'Le modifiche non sono ancora nello Storico. '
                'Premi «Salva assegnazione» per registrarle.'
            ),
        )

    def _inserisci_postazione_docente_centrata(
            self, griglia, riga_display, numero_colonne):
        """Arredo standard centrato, condiviso con Layout Storico/Annuale.

        Non va usato per le righe della Personalizzata con banchi a lato:
        quelle mantengono la posizione fisica originaria dell'arredo.
        """
        fascia = QWidget()
        riga = QHBoxLayout(fascia)
        riga.setContentsMargins(0, 4, 0, 4)
        riga.addStretch()
        cattedra = self.crea_widget_posto(
            PostoAula(0, 0, 'postazione_docente'), merged=True
        )
        cattedra.setMinimumWidth(320)
        cattedra.setMaximumWidth(420)
        riga.addWidget(cattedra)
        riga.addStretch()
        griglia.addWidget(fascia, riga_display, 0, 1, numero_colonne)

    def _aggiorna_visualizzazione_aula_personalizzata(
            self, istantanea, collocazioni) -> None:
        """Ridisegna Personalizzata con la stessa griglia di Coppie/Terzetti."""

        configurazione = costruisci_configurazione_aula_personalizzata(
            istantanea,
            collocazioni,
        )
        self._configurazione_aula_personalizzata_corrente = configurazione
        self._aggiorna_visualizzazione_aula(configurazione)

    def crea_widget_posto(self, posto, merged=False, *, configurazione=None, mostra_fisso=True) -> QWidget:
        """Crea il widget grafico di un posto o di un arredo dell’aula."""

        widget = QLabel()

        larghezza_min = 250 if merged else 120
        widget.setMinimumSize(larghezza_min, 60)
        widget.setAlignment(Qt.AlignCenter)

        widget.setStyleSheet(f"border: 1px solid {C('banco_libero_bordo')}; margin: 1px;")

        if posto.tipo == 'banco':
            if posto.occupato_da:

                nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                fisso = mostra_fisso and (posto.riga, posto.colonna) == getattr(configurazione, 'coord_fisso', None)
                sesso = getattr(configurazione, 'sessi_studenti', {}).get(nome_completo)
                prefisso = 'banco_fisso' if fisso else 'banco_femmina' if sesso == 'F' else 'banco_occupato'
                widget.setText(nome_completo)
                widget.setWordWrap(True)
                widget.setStyleSheet(f"""
                    border: 2px solid {C(prefisso + "_bordo")};
                    background-color: {C(prefisso + "_sf")};
                    color: {C(prefisso + "_txt")};
                    font-weight: bold;
                    font-size: 11px;
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip(f"{'Posto FISSO' if fisso else 'Studente'}: {nome_completo}")
                widget.setAccessibleName(f"{'Posto fisso' if fisso else 'Posto'}: {nome_completo}")
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
                widget.setText(ETICHETTA_DOCENTE)
                widget.setWordWrap(True)
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
            widget.setToolTip(ETICHETTA_DOCENTE)

        elif posto.tipo == 'postazione_docente':

            if merged:
                widget.setText(ETICHETTA_DOCENTE)
                widget.setWordWrap(True)
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
            widget.setToolTip(ETICHETTA_DOCENTE)

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
