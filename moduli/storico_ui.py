# -*- coding: utf-8 -*-
"""
storico_ui.py — interfaccia e consultazione dello Storico.

Gestisce la tabella delle assegnazioni salvate, i filtri per classe e le
finestre che mostrano report e piantine. Il popup del layout viene riutilizzato
anche per l'anteprima delle assegnazioni annuali non ancora salvate.

Parte di «PostiPerfetti».
Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3; software distribuito senza garanzie.
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QWidget, QLabel, QPushButton, QGroupBox,
    QScrollArea, QTextEdit, QTableWidgetItem,
    QMessageBox, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

from moduli.utilita import (
    pulisci_nome_file,
    mostra_popup_file_salvato,
    PATTERN_EVIDENZIAZIONE_REPORT,
    adatta_finestra_allo_schermo,
    applica_icona, applica_stile_pulsante_popup, applica_icona_finestra,
    crea_bottone, crea_popup_semantico, mostra_popup_semantico,
)
from moduli.statistiche_generali import applica_formattazione_statistiche_generali
from moduli.esportazione import sostituisci_nome_assegnazione_report
from moduli.tema import C


_NOTA_T4_VISIBILE = "Riutilizzo ammesso per completare l’assegnazione."


def _rimuovi_nota_t4_da_report(testo: str) -> str:
    """Nasconde dal report il dettaglio interno del quarto tentativo.

    Il filtro vale anche per report già conservati nello Storico: non modifica
    i dati salvati, ma impedisce che una nota tecnica dismessa ricompaia in
    Dettagli o in un TXT esportato dal popup Layout.
    """
    righe_visibili = []
    for riga in str(testo or "").splitlines():
        contenuto = riga.strip().lstrip("•- \t").strip()
        if (
            contenuto == _NOTA_T4_VISIBILE
            or contenuto.startswith("Penalità blacklist T4")
        ):
            continue
        righe_visibili.append(riga)
    return "\n".join(righe_visibili)


def _descrivi_abbinamenti(assegnazione: dict) -> str:
    """Restituisce la descrizione fisica salvata con l'assegnazione."""
    return assegnazione["abbinamenti"]


def _crea_bottone_tematico(
    testo: str,
    prefisso_colore: str,
    *,
    tooltip: str = "",
    altezza: int = 40,
    larghezza: int | None = None,
    font_size: int = 13,
    padding: str = "8px 20px",
):
    """Crea un pulsante dello Storico usando la palette semantica attiva."""
    bottone = crea_bottone(
        testo,
        C(f"{prefisso_colore}_bg"),
        C(f"{prefisso_colore}_hover"),
        tooltip=tooltip,
        altezza_min=altezza,
        font_size=font_size,
        padding=padding,
        colore_testo=C(f"{prefisso_colore}_txt"),
        colore_bordo=C(f"{prefisso_colore}_bordo"),
    )
    if larghezza is not None:
        bottone.setMinimumWidth(larghezza)
    return bottone


class PopupLayoutStorico(QDialog):
    """Mostra la piantina di un’assegnazione salvata o in anteprima."""

    def __init__(self, parent, config_app, indice_assegnazione):
        """Ricostruisce e apre il layout individuato nello Storico."""
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.indice_assegnazione = indice_assegnazione

        self.config_ricostruita, self.dati_assegnazione = self.config_app.ricostruisci_layout_da_storico(indice_assegnazione)

        if not self.config_ricostruita or not self.dati_assegnazione:
            mostra_popup_semantico(
                parent,
                "Layout non disponibile",
                "Impossibile ricostruire il layout dell'assegnazione.",
                "triangle-alert",
                testo_informativo=(
                    "I dati dello Storico potrebbero essere incompleti o danneggiati. "
                    "Questa assegnazione non può essere visualizzata."
                ),
            )
            self.reject()
            return

        self._setup_ui()
        self._applica_stile()

    @classmethod
    def da_configurazione(cls, parent, config_app, configurazione_aula, dati_assegnazione):
        """Crea il popup per un’assegnazione ancora in memoria.

        L’anteprima annuale non possiede ancora un indice nello Storico: riceve quindi
        la configurazione dell’aula e i metadati direttamente dal chiamante.
        """
        # L’anteprima non ha ancora una voce nello Storico: inizializza il
        # QDialog senza eseguire il costruttore che richiede un indice.
        popup = cls.__new__(cls)
        QDialog.__init__(popup, parent)

        popup.parent_window = parent
        popup.config_app = config_app
        popup.indice_assegnazione = None
        popup.config_ricostruita = configurazione_aula
        popup.dati_assegnazione = dati_assegnazione
        # In anteprima l’utente può soltanto consultare e chiudere il popup.
        popup.modalita_anteprima = True

        popup._setup_ui()
        popup._applica_stile()
        return popup

    def _setup_ui(self):
        """Costruisce intestazione, griglia e comandi del popup."""
        nome_assegnazione = self.dati_assegnazione.get(
            "nome", "Assegnazione Storico"
        )

        self.setWindowTitle(f"Layout assegnazione - {nome_assegnazione}")
        applica_icona_finestra(self, "layout-grid")
        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )

        layout_principale = QVBoxLayout(self)

        header_widget = self._crea_header()
        layout_principale.addWidget(header_widget)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        widget_griglia = QWidget()
        self.layout_griglia = QGridLayout(widget_griglia)

        self._popola_griglia_aula()

        scroll_area.setWidget(widget_griglia)
        layout_principale.addWidget(scroll_area)

        footer_widget = self._crea_footer()
        layout_principale.addWidget(footer_widget)

    def _crea_header(self):
        """Crea il riepilogo essenziale dell'assegnazione."""
        header = QGroupBox("Informazioni assegnazione")
        layout = QVBoxLayout(header)

        label_classe = QLabel(
            f"<b>Classe:</b> {self.dati_assegnazione.get('classe', 'N/A')}"
        )
        label_classe.setStyleSheet("font-size: 13px;")
        layout.addWidget(label_classe)

        label_data = QLabel(
            f"<b>Data creazione:</b> "
            f"{self.dati_assegnazione.get('data_creazione', 'N/A')}"
        )
        layout.addWidget(label_data)

        label_assegnazione = QLabel(
            f"<b>Assegnazione:</b> "
            f"{self.dati_assegnazione.get('nome', 'N/A')}"
        )
        layout.addWidget(label_assegnazione)

        label_abbinamenti = QLabel(
            f"<b>Abbinamenti:</b> "
            f"{_descrivi_abbinamenti(self.dati_assegnazione)}"
        )
        layout.addWidget(label_abbinamenti)

        return header

    def _crea_footer(self):
        """Crea i comandi disponibili per storico o anteprima."""
        footer = QWidget()
        layout = QHBoxLayout(footer)

        if getattr(self, 'modalita_anteprima', False):
            btn_chiudi = _crea_bottone_tematico(
                "Chiudi", "storico_btn_neutro", altezza=45, font_size=14
            )
            applica_icona(btn_chiudi, "x", 18)
            btn_chiudi.clicked.connect(self.close)
            layout.addWidget(btn_chiudi)
            return footer

        btn_excel = _crea_bottone_tematico(
            "Esporta Excel", "btn_excel", altezza=45, font_size=14
        )
        applica_icona(btn_excel, "table-2", 18)
        btn_excel.clicked.connect(self._esporta_excel)
        layout.addWidget(btn_excel)

        btn_report = _crea_bottone_tematico(
            "Salva Report assegnazione (.txt)",
            "btn_export",
            altezza=45,
            font_size=14,
        )
        applica_icona(btn_report, "file-down", 18)
        btn_report.clicked.connect(self._salva_report_txt)
        layout.addWidget(btn_report)

        btn_chiudi = _crea_bottone_tematico(
            "Chiudi", "storico_btn_neutro", altezza=45, font_size=14
        )
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.clicked.connect(self.close)
        layout.addWidget(btn_chiudi)

        return footer

    def _popola_griglia_aula(self):
        """Disegna la configurazione ricostruita nella griglia del popup."""
        while self.layout_griglia.count():
            child = self.layout_griglia.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Le righe vuote non devono creare spazi fra banchi e arredi.
        griglia_invertita = list(reversed(self.config_ricostruita.griglia))
        riga_display = 0
        for riga in griglia_invertita:
            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                continue

            for col_idx, posto in enumerate(riga):
                # Ogni arredo occupa due celle logiche ma viene mostrato come
                # un unico widget largo due colonne.
                if posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:
                        widget_posto = self.parent_window.crea_widget_posto(
                            posto, merged=True)
                        self.layout_griglia.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)
                else:
                    widget_posto = self.parent_window.crea_widget_posto(posto)
                    self.layout_griglia.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1

    def _applica_stile(self):
        """Applica al popup il tema attivo."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
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
            QLabel {{
                color: {C("testo_principale")};
            }}
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_pannello")};
            }}
        """)

    def _esporta_excel(self):
        """Esporta in Excel la piantina mostrata nel popup.

        Per i terzetti usa direttamente la griglia ricostruita; per le coppie
        ricrea il contenitore richiesto dall’esportatore. Titolo e nome proposto
        derivano dall'assegnazione selezionata.
        """
        try:
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            nome_suggerito = f"{nome_pulito}.xlsx"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Esporta Layout in Excel",
                nome_suggerito,
                "File Excel (*.xlsx);;Tutti i file (*)"
            )

            if file_path:
                # I terzetti esportano la stessa griglia già mostrata; il modo
                # a coppie richiede invece il contenitore storico ricostruito.
                if self.dati_assegnazione["modo"] == "terzetti":
                    class _SorgenteAulaTerzetti:
                        """Espone all’esportatore la configurazione dell’aula."""
                        pass
                    sorgente = _SorgenteAulaTerzetti()
                    sorgente.configurazione_aula = self.config_ricostruita
                else:
                    sorgente = self._crea_assegnatore_fittizio()

                self.parent_window.crea_file_excel(
                    file_path,
                    sorgente,
                    nome_assegnazione=nome_assegnazione,
                )

                mostra_popup_file_salvato(self, "Export completato", "File Excel salvato con successo!", file_path)

        except Exception as e:
            mostra_popup_semantico(
                self,
                "Esportazione Excel non riuscita",
                "Non è stato possibile creare il file Excel.",
                "circle-x",
                testo_informativo=str(e),
            )

    def _salva_report_txt(self):
        """Salva su file il report associato all’assegnazione."""
        try:
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            nome_suggerito = f"{nome_pulito}.txt"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva Report (.txt)",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                report = self._genera_report_testuale()

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report)

                mostra_popup_file_salvato(self, "Report salvato", "Report testuale salvato con successo!", file_path)

        except Exception as e:
            mostra_popup_semantico(
                self,
                "Salvataggio Report non riuscito",
                "Non è stato possibile salvare il Report.",
                "circle-x",
                testo_informativo=str(e),
            )

    def _crea_assegnatore_fittizio(self):
        """Ricostruisce il contenitore richiesto dall’export delle coppie.

        Le coppie e l’eventuale trio vengono ricavati dal layout salvato.
        """
        from moduli.algoritmo import AssegnatorePosti

        assegnatore = AssegnatorePosti()
        assegnatore.configurazione_aula = self.config_ricostruita

        layout_data = self.dati_assegnazione.get('layout', [])

        coppie_ricostruite = []
        trio_ricostruito = None

        studenti_per_tipo = {}
        for studente_info in layout_data:
            nome = studente_info['studente']
            studenti_per_tipo[nome] = studente_info

        coppie_processate = set()
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'coppia':
                compagno = info.get('compagno')
                # Le due righe speculari del layout rappresentano una sola coppia.
                coppia_key = tuple(sorted([nome_studente, compagno]))
                if coppia_key not in coppie_processate:
                    coppie_processate.add(coppia_key)

                    from moduli.studenti import Student
                    parti1 = nome_studente.split(' ', 1)
                    parti2 = compagno.split(' ', 1)

                    s1 = Student(parti1[0], parti1[1] if len(parti1) > 1 else '', 'M')
                    s2 = Student(parti2[0], parti2[1] if len(parti2) > 1 else '', 'F')

                    punteggio = info.get('punteggio', 0)
                    info_coppia = {
                        'punteggio_totale': punteggio,
                        'valutazione': 'STORICO',
                        'note': []
                    }

                    coppie_ricostruite.append((s1, s2, info_coppia))

        trio_nomi = []
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'trio':
                trio_nomi.append(nome_studente)

        if len(trio_nomi) == 3:
            from moduli.studenti import Student
            trio_studenti = []
            for nome in sorted(trio_nomi):
                parti = nome.split(' ', 1)
                s = Student(parti[0], parti[1] if len(parti) > 1 else '', 'M')
                trio_studenti.append(s)
            trio_ricostruito = trio_studenti

        assegnatore.coppie_formate = coppie_ricostruite
        assegnatore.trio_identificato = trio_ricostruito
        assegnatore.studenti_singoli = []

        assegnatore.stats = {
            'coppie_ottimali': 0,
            'coppie_accettabili': len(coppie_ricostruite),
            'coppie_problematiche': 0,
            'coppie_riutilizzate': 0
        }

        return assegnatore

    def _genera_report_testuale(self):
        """Restituisce il report completo salvato nella voce dello Storico."""
        if "report_completo" in self.dati_assegnazione:
            return _rimuovi_nota_t4_da_report(
                self.dati_assegnazione["report_completo"]
            )

        return "Report non disponibile per questa assegnazione."


class StoricoUIMixin:
    """Aggiunge alla finestra principale la gestione della scheda Storico.

    Popola la tabella, rinomina ed elimina le voci, aggiorna il filtro delle classi
    e apre report o piantine delle assegnazioni selezionate.
    """


    def _aggiorna_info_storico(self):
        """Aggiorna il riepilogo e la tabella dello Storico."""
        storico = self.config_app.config_data["storico_assegnazioni"]
        num_assegnazioni = len(storico)

        if num_assegnazioni == 0:
            self.label_storico.setText("Storico: nessuna assegnazione precedente")
        else:
            ultima_data = storico[-1]["data_creazione"] if storico else "N/A"
            self.label_storico.setText(
                f"Storico: {num_assegnazioni} assegnazioni "
                f"(ultima creazione: {ultima_data})"
            )

        self._aggiorna_tabella_storico()


    def _aggiorna_tabella_storico(self):
        """Popola la tabella con dati e comandi delle assegnazioni salvate."""
        storico = self.config_app.config_data["storico_assegnazioni"]

        if storico:
            self.label_storico_vuoto.setVisible(False)
            self.tabella_storico.setVisible(True)
        else:
            self.label_storico_vuoto.setVisible(True)
            self.tabella_storico.setVisible(False)

        # Evita che il popolamento venga interpretato come rinomina manuale.
        self.tabella_storico.blockSignals(True)

        self.tabella_storico.setRowCount(len(storico))

        for row, assegnazione in enumerate(storico):
            item_data = QTableWidgetItem(assegnazione["data_creazione"])
            item_data.setFlags(item_data.flags() & ~Qt.ItemIsEditable)
            item_data.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.tabella_storico.setItem(row, 0, item_data)

            item_nome = QTableWidgetItem(assegnazione['nome'])
            item_nome.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.tabella_storico.setItem(row, 1, item_nome)

            testo_abbinamenti = _descrivi_abbinamenti(assegnazione)

            item_abbinamenti = QTableWidgetItem(testo_abbinamenti)
            item_abbinamenti.setFlags(item_abbinamenti.flags() & ~Qt.ItemIsEditable)
            item_abbinamenti.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.tabella_storico.setItem(row, 2, item_abbinamenti)

            widget_azioni = QWidget()
            widget_azioni.setObjectName("contenitoreAzioniStorico")
            widget_azioni.setAutoFillBackground(True)
            # Un QTableWidget non dipinge il fondo dell'item sotto un cell widget.
            # La trasparenza mostrava quindi lo sfondo principale (#2B2B2B nel
            # tema scuro, #F0F2F5 nel chiaro), creando l'effetto di un box
            # appoggiato sulla riga. Il contenitore usa esplicitamente lo stesso
            # sfondo delle altre celle della tabella.
            widget_azioni.setStyleSheet(
                "QWidget#contenitoreAzioniStorico {"
                f" background-color: {C('sfondo_pannello')};"
                " border: none; margin: 0px; padding: 0px; }"
            )
            widget_azioni.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )

            layout_azioni = QHBoxLayout(widget_azioni)
            layout_azioni.setContentsMargins(6, 4, 6, 4)
            layout_azioni.setSpacing(6)
            layout_azioni.setAlignment(Qt.AlignVCenter)

            btn_elimina = _crea_bottone_tematico(
                "Elimina",
                "storico_btn_elimina",
                tooltip="Rimuove definitivamente questa assegnazione dallo storico",
                altezza=32,
                larghezza=110,
                font_size=12,
                padding="2px 9px",
            )
            applica_icona(btn_elimina, "trash-2", 15)
            btn_elimina.setFixedHeight(32)
            btn_elimina.clicked.connect(
                lambda checked, idx=row: self._elimina_assegnazione(idx)
            )
            layout_azioni.addWidget(btn_elimina, alignment=Qt.AlignVCenter)

            btn_dettagli = _crea_bottone_tematico(
                "Dettagli",
                "storico_btn_dettagli",
                tooltip="Visualizza il Report completo di questa assegnazione",
                altezza=32,
                larghezza=110,
                font_size=12,
                padding="2px 9px",
            )
            applica_icona(btn_dettagli, "list", 15)
            btn_dettagli.setFixedHeight(32)
            btn_dettagli.clicked.connect(
                lambda checked, idx=row: self._visualizza_dettagli_assegnazione(idx)
            )
            layout_azioni.addWidget(btn_dettagli, alignment=Qt.AlignVCenter)

            btn_layout = _crea_bottone_tematico(
                "Layout",
                "storico_btn_layout",
                tooltip="Visualizza il Layout grafico di questa assegnazione",
                altezza=32,
                larghezza=110,
                font_size=12,
                padding="2px 9px",
            )
            applica_icona(btn_layout, "layout-grid", 15)
            btn_layout.setFixedHeight(32)
            btn_layout.clicked.connect(
                lambda checked, idx=row: self._visualizza_layout_storico(idx)
            )
            layout_azioni.addWidget(btn_layout, alignment=Qt.AlignVCenter)

            layout_azioni.addStretch()
            self.tabella_storico.setCellWidget(row, 3, widget_azioni)

        self.tabella_storico.resizeColumnsToContents()
        # Il padding globale degli item sottrae spazio al rettangolo realmente
        # disponibile per il cell widget. Pulsanti compatti da 32 px e margini
        # verticali da 4 px lasciano un margine di sicurezza anche con DPI e font
        # diversi; la riga resta abbastanza alta da centrare le celle testuali.
        altezza_riga = 60
        self.tabella_storico.verticalHeader().setMinimumSectionSize(altezza_riga)
        self.tabella_storico.verticalHeader().setDefaultSectionSize(altezza_riga)
        for row in range(self.tabella_storico.rowCount()):
            self.tabella_storico.setRowHeight(row, altezza_riga)

        self.tabella_storico.blockSignals(False)


    def _on_storico_nome_modificato(self, row, column):
        """Salva la rinomina effettuata nella colonna Nome."""
        if column != 1:
            return

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if row < 0 or row >= len(storico):
            return

        item = self.tabella_storico.item(row, column)
        if item is None:
            return

        nuovo_nome = item.text().strip()
        if not nuovo_nome:
            self.tabella_storico.blockSignals(True)
            item.setText(storico[row]["nome"])
            self.tabella_storico.blockSignals(False)
            return

        storico[row]["nome"] = nuovo_nome

        report_salvato = storico[row].get("report_completo")
        if report_salvato:
            storico[row]["report_completo"] = (
                sostituisci_nome_assegnazione_report(
                    report_salvato,
                    nuovo_nome,
                )
            )

        if getattr(self, "indice_assegnazione_corrente", None) == row:
            self._aggiorna_riga_identificativa_report(nuovo_nome)
            self.nome_assegnazione_corrente = nuovo_nome

        self.config_app.salva_configurazione()
        print(f"📝 Storico: assegnazione {row} rinominata → '{nuovo_nome}'")


    def _popola_filtro_classi(self):
        """Aggiorna il filtro con le classi presenti nello Storico."""
        self.filtro_classe_combo.clear()

        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            self.filtro_classe_combo.addItem("Nessuna assegnazione salvata", None)
            return

        classi_trovate = {}

        for assegnazione in storico:
            file_origine = assegnazione.get('file_origine', 'File non specificato')
            if file_origine not in classi_trovate:
                classi_trovate[file_origine] = 0
            classi_trovate[file_origine] += 1

        classi_ordinate = sorted(classi_trovate.items())

        # La sentinella impedisce di mescolare statistiche di classi diverse.
        if len(classi_ordinate) > 1:
            self.filtro_classe_combo.addItem(
                "— Seleziona una classe per visualizzare le statistiche —",
                "__placeholder__"
            )

        for file_origine, count in classi_ordinate:
            nome_file = os.path.basename(file_origine) if file_origine else "File non specificato"
            self.filtro_classe_combo.addItem(
                f"{nome_file} ({count} assegnazioni)",
                file_origine
            )

        print(f"📊 Filtro classi popolato: {len(classi_ordinate)} classi trovate")

        # Il menu viene ricreato dinamicamente e deve ricevere subito il tema.
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


    def _elimina_assegnazione(self, indice_assegnazione: int):
        """Elimina una voce confermata e riallinea blacklist e interfaccia."""
        try:
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]
                nome_assegnazione = assegnazione.get("nome", "Senza nome")
                data_assegnazione = assegnazione.get("data_creazione", "N/A")

                if assegnazione["modo"] == "terzetti":
                    gruppi = assegnazione.get("gruppi", [])
                    n_ter = sum(1 for g in gruppi if g.get("tipo") == "terzetto")
                    n_qua = sum(1 for g in gruppi if g.get("tipo") == "quartetto")
                    n_cop = sum(1 for g in gruppi if g.get("tipo") == "coppia")
                    messaggio_abbinamenti = f"Terzetti: {n_ter}"
                    if n_qua:
                        messaggio_abbinamenti += f" | Quartetti: {n_qua}"
                    if n_cop:
                        messaggio_abbinamenti += f" | Coppia di resto: {n_cop}"
                else:
                    layout = assegnazione.get("layout", [])
                    studenti_coppia = [s for s in layout if s.get("tipo") == "coppia"]
                    num_coppie = len(studenti_coppia) // 2
                    studenti_trio = [s for s in layout if s.get("tipo") == "trio"]
                    num_trio = 1 if len(studenti_trio) == 3 else 0
                    messaggio_abbinamenti = f"Coppie: {num_coppie}"
                    if num_trio > 0:
                        messaggio_abbinamenti += f" | Trio: {num_trio}"

                conferma = crea_popup_semantico(
                    self,
                    "Elimina assegnazione",
                    "Eliminare definitivamente questa assegnazione?",
                    "triangle-alert",
                    testo_informativo=(
                        f"Data creazione: {data_assegnazione}\n"
                        f"Nome: {nome_assegnazione}\n"
                        f"{messaggio_abbinamenti}\n\n"
                        "Questa azione non può essere annullata."
                    ),
                )
                btn_elimina_popup = conferma.addButton(
                    "Elimina", QMessageBox.AcceptRole
                )
                applica_icona(btn_elimina_popup, "trash-2", 18)
                applica_stile_pulsante_popup(
                    btn_elimina_popup, "distruttivo"
                )
                btn_annulla_popup = conferma.addButton(
                    "Annulla", QMessageBox.RejectRole
                )
                applica_icona(btn_annulla_popup, "x", 18)
                conferma.setDefaultButton(btn_annulla_popup)
                conferma.exec()

                if conferma.clickedButton() == btn_elimina_popup:
                    del self.config_app.config_data["storico_assegnazioni"][indice_assegnazione]

                    indice_corrente = getattr(
                        self, "indice_assegnazione_corrente", None
                    )
                    if indice_corrente == indice_assegnazione:
                        self.indice_assegnazione_corrente = None
                    elif (
                        indice_corrente is not None
                        and indice_corrente > indice_assegnazione
                    ):
                        self.indice_assegnazione_corrente -= 1

                    print(f"🔄 Eliminazione assegnazione: avvio ricostruzione blacklist...")
                    # Dopo l’eliminazione le blacklist devono riflettere soltanto
                    # le assegnazioni ancora presenti.
                    self.config_app._ricostruisci_blacklist_da_storico()
                    print(f"✅ Blacklist ricostruita - coerenza garantita")

                    self.config_app.salva_configurazione()

                    self._aggiorna_info_storico()
                    self._popola_filtro_classi()

                    mostra_popup_semantico(
                        self,
                        "Assegnazione eliminata",
                        "L'assegnazione è stata rimossa dallo Storico.",
                        "circle-check",
                        testo_informativo=nome_assegnazione,
                    )

                    # Gli export correnti potrebbero riferirsi alla voce rimossa.
                    self.btn_export_excel.setEnabled(False)
                    self.btn_export_excel.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )
                    self.btn_export_report_txt.setEnabled(False)
                    self.btn_export_report_txt.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )

            else:
                mostra_popup_semantico(
                    self,
                    "Assegnazione non trovata",
                    "Non è possibile eliminare la voce selezionata.",
                    "triangle-alert",
                    testo_informativo=(
                        "Aggiorna lo Storico e riprova."
                    ),
                )

        except Exception as e:
            mostra_popup_semantico(
                self,
                "Eliminazione non riuscita",
                "Si è verificato un errore durante l'eliminazione.",
                "circle-x",
                testo_informativo=str(e),
            )


    def _visualizza_dettagli_assegnazione(self, indice_assegnazione: int):
        """Mostra il report completo di un’assegnazione salvata."""
        try:
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]

                dettagli = _rimuovi_nota_t4_da_report(
                    assegnazione.get(
                        "report_completo",
                        "Report non disponibile per questa assegnazione.",
                    )
                )

                dialog = QDialog(self)
                dialog.setWindowTitle(f"Dettagli assegnazione - {assegnazione.get('nome', 'Senza nome')}")
                applica_icona_finestra(dialog, "list")
                adatta_finestra_allo_schermo(
                    dialog,
                    larghezza_ideale=1200,
                    altezza_ideale=750,
                    larghezza_minima=760,
                    altezza_minima=480,
                )

                layout = QVBoxLayout(dialog)

                text_edit = QTextEdit()
                text_edit.setPlainText(dettagli)
                text_edit.setReadOnly(True)
                font_mono = QFont()
                font_mono.setFamily("Consolas")
                font_mono.setStyleHint(QFont.Monospace)
                font_mono.setPointSize(10)
                text_edit.setFont(font_mono)
                layout.addWidget(text_edit)


                formato_ocra = QTextCharFormat()
                formato_ocra.setForeground(QColor(C("testo_ocra")))
                formato_ocra.setFontWeight(QFont.Bold)

                # Le note di riuso seguono pattern testuali; le statistiche
                # generali usano invece i metadati strutturati salvati.
                patterns_da_evidenziare = list(PATTERN_EVIDENZIAZIONE_REPORT)

                for pattern in patterns_da_evidenziare:
                    cursore = text_edit.textCursor()
                    cursore.movePosition(QTextCursor.Start)
                    text_edit.setTextCursor(cursore)

                    while True:
                        cursore = text_edit.document().find(pattern, cursore)
                        if cursore.isNull():
                            break
                        cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                        cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursore.setCharFormat(formato_ocra)

                applica_formattazione_statistiche_generali(
                    text_edit, assegnazione.get("statistiche_generali", []))

                cursore_iniziale = text_edit.textCursor()
                cursore_iniziale.movePosition(QTextCursor.Start)
                text_edit.setTextCursor(cursore_iniziale)

                footer_dettagli = QHBoxLayout()
                footer_dettagli.setSpacing(12)

                btn_salva_report = _crea_bottone_tematico(
                    "Salva Report assegnazione (.txt)",
                    "btn_export",
                    altezza=40,
                    font_size=13,
                )
                applica_icona(btn_salva_report, "file-down", 18)

                def _salva_report_dettagli():
                    """Salva il report visualizzato come file di testo."""
                    try:
                        nome_ass = assegnazione.get('nome', 'Assegnazione')
                        nome_suggerito = f"{pulisci_nome_file(nome_ass)}.txt"

                        file_path, _ = QFileDialog.getSaveFileName(
                            dialog,
                            "Salva Report assegnazione (.txt)",
                            nome_suggerito,
                            "File di testo (*.txt);;Tutti i file (*)"
                        )

                        if file_path:
                            report_testo = text_edit.toPlainText()
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(report_testo)
                            mostra_popup_file_salvato(
                                dialog, "Report salvato",
                                "Report assegnazione salvato con successo!",
                                file_path
                            )

                    except Exception as e:
                        mostra_popup_semantico(
                            dialog,
                            "Salvataggio Report non riuscito",
                            "Non è stato possibile salvare il Report.",
                            "circle-x",
                            testo_informativo=str(e),
                        )

                btn_salva_report.clicked.connect(_salva_report_dettagli)
                footer_dettagli.addWidget(btn_salva_report)

                btn_chiudi = _crea_bottone_tematico(
                    "Chiudi", "storico_btn_neutro", altezza=40, font_size=13
                )
                applica_icona(btn_chiudi, "x", 18)
                btn_chiudi.clicked.connect(dialog.close)
                footer_dettagli.addWidget(btn_chiudi)

                layout.addLayout(footer_dettagli)

                dialog.setStyleSheet(f"""
                    QDialog {{
                        background-color: {C("sfondo_principale")};
                        color: {C("testo_principale")};
                    }}
                    QTextEdit {{
                        border: 2px solid {C("bordo_normale")};
                        border-radius: 6px;
                        background-color: {C("sfondo_testo_area")};
                        color: {C("testo_principale")};
                        padding: 10px;
                    }}
                """)

                dialog.exec()

            else:
                mostra_popup_semantico(
                    self,
                    "Assegnazione non trovata",
                    "Il Report selezionato non è più disponibile.",
                    "triangle-alert",
                    testo_informativo="Aggiorna lo Storico e riprova.",
                )

        except Exception as e:
            mostra_popup_semantico(
                self,
                "Report non disponibile",
                "Non è stato possibile visualizzare il Report.",
                "circle-x",
                testo_informativo=str(e),
            )


    def _visualizza_layout_storico(self, indice_assegnazione):
        """Apre la piantina grafica dell’assegnazione selezionata."""
        try:
            popup = PopupLayoutStorico(self, self.config_app, indice_assegnazione)
            popup.exec()

        except Exception as e:
            mostra_popup_semantico(
                self,
                "Layout non disponibile",
                "Non è stato possibile aprire il layout dell'assegnazione.",
                "circle-x",
                testo_informativo=str(e),
            )
            import traceback
            traceback.print_exc()
