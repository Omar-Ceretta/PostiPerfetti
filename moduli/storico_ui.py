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
    Interfaccia dello storico assegnazioni.

    Contiene:
    • PopupLayoutStorico (QDialog)  → Finestra popup per layout storico
    • StoricoUIMixin               → 8 metodi storico per FinestraPostiPerfetti

    PopupLayoutStorico è una classe standalone (QDialog) che mostra il layout
    grafico di un'assegnazione salvata nello storico, con possibilità di
    esportare in Excel o TXT.

    StoricoUIMixin è un mixin che aggiunge a FinestraPostiPerfetti i metodi
    per gestire la tab Storico:
    • _aggiorna_info_storico()              → Aggiorna label contatore storico
    • _aggiorna_tabella_storico()           → Popola tabella con assegnazioni
    • _on_storico_nome_modificato()         → Salva rinomina assegnazione
    • _popola_filtro_classi()               → Popola dropdown filtro statistiche
    • _elimina_assegnazione()               → Elimina un'assegnazione dallo storico
    • _visualizza_dettagli_assegnazione()   → Mostra report completo in dialog
    • _genera_report_da_layout()            → Genera report fallback dal layout
    • _visualizza_layout_storico()          → Apre PopupLayoutStorico
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QWidget, QLabel, QPushButton, QGroupBox,
    QScrollArea, QTextEdit, QTableWidgetItem,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

# Importa funzioni di utilità e tema
from moduli.utilita import pulisci_nome_file, mostra_popup_file_salvato
from moduli.tema import C

# =============================================================================
# POPUP LAYOUT STORICO — Visualizzazione grafica assegnazione salvata
# =============================================================================

class PopupLayoutStorico(QDialog):
    """
    Finestra popup per visualizzare il layout di un'assegnazione storica.
    Mostra la griglia dell'aula con studenti posizionati + bottoni export.
    """

    def __init__(self, parent, config_app, indice_assegnazione):
        """
        Inizializza il popup.

        Args:
            parent: Finestra parent (FinestraPostiPerfetti)
            config_app: Oggetto ConfigurazioneApp
            indice_assegnazione: Indice dell'assegnazione nello storico
        """
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.indice_assegnazione = indice_assegnazione

        # Ricostruisce il layout
        self.config_ricostruita, self.dati_assegnazione = self.config_app.ricostruisci_layout_da_storico(indice_assegnazione)

        if not self.config_ricostruita or not self.dati_assegnazione:
            # Mostra errore e chiudi popup
            QMessageBox.warning(
                parent,
                "Errore ricostruzione",
                "❌ Impossibile ricostruire il layout.\n\n"
                "Possibili cause:\n"
                "• dati JSON corrotti\n\n"
                "Questa assegnazione non può essere visualizzata."
            )
            self.reject()  # Chiude il popup
            return

        # Setup interfaccia
        self._setup_ui()
        self._applica_stile()

    def _setup_ui(self):
        """Crea l'interfaccia del popup."""
        # Configurazione finestra
        nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione Storico')
        data_assegnazione = self.dati_assegnazione.get('data', 'N/A')

        self.setWindowTitle(f"🔍 Layout assegnazione - {nome_assegnazione} - {data_assegnazione}")
        self.setMinimumSize(1200, 750)
        self.resize(1200, 750)  # Imposta anche dimensione iniziale - CONFIGURABILE

        # Layout principale verticale
        layout_principale = QVBoxLayout(self)

        # === HEADER: Informazioni assegnazione ===
        header_widget = self._crea_header()
        layout_principale.addWidget(header_widget)

        # === GRIGLIA AULA (scrollabile) ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        widget_griglia = QWidget()
        self.layout_griglia = QGridLayout(widget_griglia)

        # Popola la griglia con il layout ricostruito
        self._popola_griglia_aula()

        scroll_area.setWidget(widget_griglia)
        layout_principale.addWidget(scroll_area)

        # === FOOTER: Bottoni export ===
        footer_widget = self._crea_footer()
        layout_principale.addWidget(footer_widget)

    def _crea_header(self):
        """Crea il widget header con info assegnazione."""
        header = QGroupBox("📋 Informazioni assegnazione")
        layout = QVBoxLayout(header)

        # Nome assegnazione
        label_nome = QLabel(f"<b>Nome:</b> {self.dati_assegnazione.get('nome', 'N/A')}")
        label_nome.setStyleSheet("font-size: 13px;")
        layout.addWidget(label_nome)

        # Data e ora
        data = self.dati_assegnazione.get('data', 'N/A')
        ora = self.dati_assegnazione.get('ora', 'N/A')
        label_data = QLabel(f"<b>Data/Ora:</b> {data} - {ora}")
        layout.addWidget(label_data)

        # File origine
        file_origine = self.dati_assegnazione.get('file_origine', 'Non specificato')
        label_file = QLabel(f"<b>File origine:</b> {file_origine}")
        layout.addWidget(label_file)

        # Configurazione aula
        config_aula = self.dati_assegnazione.get('configurazione_aula', {})
        num_file = config_aula.get('num_file', '?')
        posti_fila = config_aula.get('posti_per_fila', '?')
        num_studenti = config_aula.get('num_studenti', '?')
        label_config = QLabel(f"<b>Configurazione:</b> {num_file} file × {posti_fila} posti - {num_studenti} studenti")
        layout.addWidget(label_config)

        return header

    def _crea_footer(self):
        """Crea il widget footer con bottoni export."""
        footer = QWidget()
        layout = QHBoxLayout(footer)

        # Bottone Export Excel
        btn_excel = QPushButton("📊 Esporta Excel")
        btn_excel.setMinimumHeight(45)
        btn_excel.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("accento")};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("accento_hover")};
            }}
        """)
        btn_excel.clicked.connect(self._esporta_excel)
        layout.addWidget(btn_excel)

        # Bottone Export Report TXT
        btn_report = QPushButton("📋 Salva Report assegnazione (.txt)")
        btn_report.setMinimumHeight(45)
        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_excel_bg")};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_excel_hover")};
            }}
        """)
        btn_report.clicked.connect(self._salva_report_txt)
        layout.addWidget(btn_report)

        # Bottone Chiudi
        btn_chiudi = QPushButton("❌ Chiudi")
        btn_chiudi.setMinimumHeight(45)
        btn_chiudi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_grigio_bg")};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_grigio_hover")};
            }}
        """)
        btn_chiudi.clicked.connect(self.close)
        layout.addWidget(btn_chiudi)

        return footer

    def _popola_griglia_aula(self):
        """Popola la griglia con il layout ricostruito."""
        # Pulisce layout esistente
        while self.layout_griglia.count():
            child = self.layout_griglia.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Ricrea griglia dal layout ricostruito
        # Arredi (LIM, CAT, LAV) in basso, ultima fila banchi in alto
        # IMPORTANTE: Salta le righe completamente vuote (solo corridoio)
        # per evitare "buchi" visivi tra le file di banchi e gli arredi
        griglia_invertita = list(reversed(self.config_ricostruita.griglia))
        riga_display = 0  # Contatore separato per le righe del QGridLayout
        for riga in griglia_invertita:
            # Verifica se la riga ha almeno un elemento visibile
            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                continue  # Salta righe completamente vuote

            for col_idx, posto in enumerate(riga):
                # --- MERGE VISIVO ARREDI (come nell'Excel) ---
                # Stessa logica di _aggiorna_visualizzazione_aula() in postiperfetti.py:
                # gli arredi sono 2 PostoAula consecutivi → una sola cella larga 2 colonne
                if posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:
                        # Prima cella della coppia → widget merged largo 2 colonne
                        widget_posto = self.parent_window.crea_widget_posto(
                            posto, merged=True)
                        self.layout_griglia.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)  # colspan=2
                    # else: seconda cella → coperta dal colspan=2 della prima
                else:
                    # Banchi e corridoi: rendering normale (1 widget per cella)
                    widget_posto = self.parent_window.crea_widget_posto(posto)
                    self.layout_griglia.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1

    def _applica_stile(self):
        """Applica il tema attivo al popup layout storico."""
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
        """Esporta il layout ricostruito in formato Excel."""
        try:
            # Suggerisce nome file basato su nome assegnazione salvato
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            nome_suggerito = f"{nome_pulito}.xlsx"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Esporta Layout in Excel",
                nome_suggerito,
                "File Excel (*.xlsx);;Tutti i file (*)"
            )

            if file_path:
                # Crea file Excel riutilizzando metodo esistente
                # NOTA: Il metodo crea_file_excel della parent window richiede un AssegnatorePosti
                # ma noi abbiamo solo ConfigurazioneAula - dobbiamo creare un oggetto fittizio

                # Crea AssegnatorePosti fittizio con dati ricostruiti
                assegnatore_fittizio = self._crea_assegnatore_fittizio()

                # Chiama metodo esistente per creare Excel
                self.parent_window.crea_file_excel(file_path, assegnatore_fittizio)

                mostra_popup_file_salvato(self, "Export completato", "✅ File Excel salvato con successo!", file_path)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore Export",
                f"❌ Errore durante l'export Excel:\n{str(e)}"
            )

    def _salva_report_txt(self):
        """Salva il report testuale dell'assegnazione."""
        try:
            # Suggerisce nome file basato su nome assegnazione salvato
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            nome_suggerito = f"{nome_pulito}.txt"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva Report (.txt)",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                # Genera report testuale
                report = self._genera_report_testuale()

                # Salva su file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report)

                mostra_popup_file_salvato(self, "Report salvato", "✅ Report testuale salvato con successo!", file_path)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore salvataggio",
                f"❌ Errore durante il salvataggio:\n{str(e)}"
            )

    def _crea_assegnatore_fittizio(self):
        """
        Crea un oggetto AssegnatorePosti fittizio per riutilizzare crea_file_excel.
        Estrae le informazioni dal layout ricostruito.
        """
        from moduli.algoritmo import AssegnatorePosti

        assegnatore = AssegnatorePosti()
        assegnatore.configurazione_aula = self.config_ricostruita

        # Estrae coppie e trio dal layout salvato
        layout_data = self.dati_assegnazione.get('layout', [])

        # Ricostruisce coppie (serve per statistiche Excel)
        coppie_ricostruite = []
        trio_ricostruito = None

        # Mappa studenti per tipo abbinamento
        studenti_per_tipo = {}
        for studente_info in layout_data:
            nome = studente_info['studente']
            studenti_per_tipo[nome] = studente_info

        # Ricostruisce coppie
        coppie_processate = set()
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'coppia':
                compagno = info.get('compagno')
                # Evita duplicati (coppia A-B = coppia B-A)
                coppia_key = tuple(sorted([nome_studente, compagno]))
                if coppia_key not in coppie_processate:
                    coppie_processate.add(coppia_key)

                    # Crea oggetti Student fittizi
                    from moduli.studenti import Student
                    parti1 = nome_studente.split(' ', 1)
                    parti2 = compagno.split(' ', 1)

                    s1 = Student(parti1[0], parti1[1] if len(parti1) > 1 else '', 'M')
                    s2 = Student(parti2[0], parti2[1] if len(parti2) > 1 else '', 'F')

                    # Info punteggio (se disponibile)
                    punteggio = info.get('punteggio', 0)
                    info_coppia = {
                        'punteggio_totale': punteggio,
                        'valutazione': 'STORICO',
                        'note': []
                    }

                    coppie_ricostruite.append((s1, s2, info_coppia))

        # Ricostruisce trio se presente
        trio_nomi = []
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'trio':
                trio_nomi.append(nome_studente)

        if len(trio_nomi) == 3:
            from moduli.studenti import Student
            trio_studenti = []
            for nome in sorted(trio_nomi):  # Ordina per avere sempre stesso ordine
                parti = nome.split(' ', 1)
                s = Student(parti[0], parti[1] if len(parti) > 1 else '', 'M')
                trio_studenti.append(s)
            trio_ricostruito = trio_studenti

        assegnatore.coppie_formate = coppie_ricostruite
        assegnatore.trio_identificato = trio_ricostruito
        assegnatore.studenti_singoli = []

        # Statistiche fittizie (non abbiamo i dati originali)
        assegnatore.stats = {
            'coppie_ottimali': 0,
            'coppie_accettabili': len(coppie_ricostruite),
            'coppie_problematiche': 0,
            'coppie_riutilizzate': 0
        }

        return assegnatore

    def _genera_report_testuale(self):
        """Genera il report testuale completo dell'assegnazione."""
        # Usa il report completo salvato se disponibile
        if "report_completo" in self.dati_assegnazione:
            return self.dati_assegnazione["report_completo"]

        # FALLBACK: Genera report basilare dal layout
        report = []

        # Header
        report.append("═" * 70)
        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("═" * 70)

        # Informazioni base
        report.append(f"Classe: {self.dati_assegnazione.get('nome', 'N/A')}")
        report.append(f"File origine: {self.dati_assegnazione.get('file_origine', 'Non specificato')}")
        report.append(f"Data/Ora: {self.dati_assegnazione.get('data', 'N/A')} {self.dati_assegnazione.get('ora', 'N/A')}")

        # Configurazione aula
        config = self.dati_assegnazione.get('configurazione_aula', {})
        report.append(f"Studenti elaborati: {config.get('num_studenti', 'N/A')}")
        report.append("")

        # Layout salvato
        layout_data = self.dati_assegnazione.get('layout', [])

        # Conta tipi abbinamenti
        num_coppie = len([s for s in layout_data if s.get('tipo') == 'coppia']) // 2
        num_trio = len([s for s in layout_data if s.get('tipo') == 'trio'])

        report.append("📊 STATISTICHE GENERALI")
        report.append("─" * 70)
        report.append(f"Coppie totali: {num_coppie}")
        if num_trio > 0:
            report.append(f"Trio formato: 1 ({num_trio} studenti)")
        report.append("")

        # Lista abbinamenti
        report.append("💥 ABBINAMENTI FORMATI")
        report.append("─" * 70)

        # Coppie
        coppie_mostrate = set()
        idx_coppia = 1
        for studente_info in layout_data:
            if studente_info.get('tipo') == 'coppia':
                nome = studente_info['studente']
                compagno = studente_info.get('compagno', '?')
                coppia_key = tuple(sorted([nome, compagno]))

                if coppia_key not in coppie_mostrate:
                    coppie_mostrate.add(coppia_key)
                    punteggio = studente_info.get('punteggio', 'N/A')
                    report.append(f"{idx_coppia:2d}. {nome} + {compagno}")
                    report.append(f"    Punteggio: {punteggio}")
                    report.append("")
                    idx_coppia += 1

        # Trio
        if num_trio > 0:
            trio_studenti = [s['studente'] for s in layout_data if s.get('tipo') == 'trio']
            if len(trio_studenti) == 3:
                report.append("💥 TRIO FORMATO")
                report.append("─" * 70)
                report.append(f"Trio: {' + '.join(trio_studenti)}")
                report.append("")

        report.append("═" * 70)

        return "\n".join(report)

# =============================================================================
# MIXIN STORICO UI — Metodi per la gestione della tab Storico
# =============================================================================

class StoricoUIMixin:
    """
    Mixin che aggiunge la gestione della tab Storico a FinestraPostiPerfetti.

    Attributi usati da self (devono esistere nella classe principale):
        - self.config_app                (ConfigurazioneApp)
        - self.label_storico             (QLabel)
        - self.tabella_storico           (QTableWidget)
        - self.filtro_classe_combo       (QComboBox)
        - self.btn_export_excel          (QPushButton)
        - self.btn_export_report_txt     (QPushButton)
        - self.text_report               (QTextEdit)
    """

    # =================================================================
    # AGGIORNAMENTO INFO STORICO — Label contatore + stato
    # =================================================================

    def _aggiorna_info_storico(self):
        """Aggiorna le informazioni sullo storico delle assegnazioni."""
        storico = self.config_app.config_data["storico_assegnazioni"]
        num_assegnazioni = len(storico)

        if num_assegnazioni == 0:
            self.label_storico.setText("Storico: nessuna assegnazione precedente")
        else:
            ultima_data = storico[-1]["data"] if storico else "N/A"
            self.label_storico.setText(f"Storico: {num_assegnazioni} assegnazioni (ultima: {ultima_data})")

        # Aggiorna anche la tabella dello storico
        self._aggiorna_tabella_storico()

    # =================================================================
    # TABELLA STORICO — Popolamento con dati + bottoni azione
    # =================================================================

    def _aggiorna_tabella_storico(self):
        """Aggiorna la tabella dello storico nelle tab."""
        storico = self.config_app.config_data["storico_assegnazioni"]

        # --- Gestione placeholder storico vuoto ---
        # Se non ci sono assegnazioni: mostra il messaggio centrato,
        # nasconde la tabella. Viceversa quando ci sono dati.
        if storico:
            self.label_storico_vuoto.setVisible(False)
            self.tabella_storico.setVisible(True)
        else:
            self.label_storico_vuoto.setVisible(True)
            self.tabella_storico.setVisible(False)

        # Blocca il segnale cellChanged durante il popolamento
        # per evitare che scatti per ogni setItem()
        self.tabella_storico.blockSignals(True)

        self.tabella_storico.setRowCount(len(storico))

        for row, assegnazione in enumerate(storico):
            # Colonna "Data" — NON editabile (solo visualizzazione)
            item_data = QTableWidgetItem(f"{assegnazione['data']} {assegnazione['ora']}")
            item_data.setFlags(item_data.flags() & ~Qt.ItemIsEditable)
            self.tabella_storico.setItem(row, 0, item_data)

            # Colonna "Nome" — editabile (l'utente può rinominarla)
            self.tabella_storico.setItem(row, 1, QTableWidgetItem(assegnazione['nome']))

            # Conta abbinamenti dal campo "layout"
            layout = assegnazione.get('layout', [])

            if layout:
                # Conta coppie (ogni coppia ha 2 studenti nel layout)
                studenti_coppia = [s for s in layout if s.get('tipo') == 'coppia']
                num_coppie = len(studenti_coppia) // 2  # Diviso 2 perché ogni coppia = 2 studenti

                # Conta trio (3 studenti nel layout)
                studenti_trio = [s for s in layout if s.get('tipo') == 'trio']
                num_trio = 1 if len(studenti_trio) == 3 else 0

                if num_trio > 0:
                    testo_abbinamenti = f"{num_coppie} coppie + {num_trio} trio"
                else:
                    testo_abbinamenti = f"{num_coppie} coppie"
            else:
                # Assegnazione senza layout (non dovrebbe succedere con nuovo formato)
                testo_abbinamenti = "Formato non supportato"

            # Colonna "Abbinamenti" — NON editabile (dato calcolato)
            item_abbinamenti = QTableWidgetItem(testo_abbinamenti)
            item_abbinamenti.setFlags(item_abbinamenti.flags() & ~Qt.ItemIsEditable)
            self.tabella_storico.setItem(row, 2, item_abbinamenti)

            # Container per bottoni azioni multiple
            widget_azioni = QWidget()
            layout_azioni = QHBoxLayout(widget_azioni)
            layout_azioni.setContentsMargins(2, 2, 2, 2)

            # Bottone Elimina
            btn_elimina = QPushButton("🗑 Elimina")
            btn_elimina.setToolTip("Rimuove definitivamente questa assegnazione dallo storico")
            btn_elimina.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_elimina.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_elimina.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("btn_rosso_bg")};
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    background-color: {C("btn_rosso_hover")};
                }}
            """)
            btn_elimina.clicked.connect(lambda checked, idx=row: self._elimina_assegnazione(idx))
            layout_azioni.addWidget(btn_elimina)

            # Bottone Dettagli - dimensioni e colori ottimizzati
            btn_dettagli = QPushButton("👁 Dettagli")
            btn_dettagli.setToolTip("Visualizza il Report completo di questa assegnazione")
            btn_dettagli.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_dettagli.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_dettagli.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("btn_blu_bg")};
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    background-color: {C("btn_blu_hover")};
                }}
            """)
            btn_dettagli.clicked.connect(lambda checked, idx=row: self._visualizza_dettagli_assegnazione(idx))
            layout_azioni.addWidget(btn_dettagli)

            # Bottone Visualizza Layout
            btn_layout = QPushButton("🔍 Layout")
            btn_layout.setToolTip("Visualizza il Layout grafico di questa assegnazione")
            btn_layout.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_layout.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_layout.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("accento")};
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    background-color: {C("accento_hover")};
                }}
            """)
            btn_layout.clicked.connect(lambda checked, idx=row: self._visualizza_layout_storico(idx))
            layout_azioni.addWidget(btn_layout)

            layout_azioni.addStretch()  # Spinge i bottoni a sinistra
            self.tabella_storico.setCellWidget(row, 3, widget_azioni)

        self.tabella_storico.resizeColumnsToContents()
        # Altezza righe calcolata automaticamente in base al contenuto.
        # Usiamo setMinimumSectionSize (non setDefaultSectionSize) per
        # garantire un minimo leggibile, ma lasciando a Qt la libertà
        # di espandere la riga se il DPI scaling lo richiede.
        self.tabella_storico.verticalHeader().setMinimumSectionSize(50)
        self.tabella_storico.resizeRowsToContents()

        # Sblocca il segnale cellChanged (popolamento completato)
        self.tabella_storico.blockSignals(False)

    # =================================================================
    # RINOMINA ASSEGNAZIONE — Salvataggio modifica nome nella tabella
    # =================================================================

    def _on_storico_nome_modificato(self, row, column):
        """
        Salva la modifica quando l'utente rinomina un'assegnazione
        nella colonna "Nome" dello Storico.

        Args:
            row: riga modificata
            column: colonna modificata (solo colonna 1 = Nome è editabile)
        """
        # Solo la colonna "Nome" (indice 1) è editabile
        if column != 1:
            return

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if row < 0 or row >= len(storico):
            return

        # Legge il nuovo testo dalla cella
        item = self.tabella_storico.item(row, column)
        if item:
            nuovo_nome = item.text().strip()
            if nuovo_nome:
                storico[row]["nome"] = nuovo_nome
                self.config_app.salva_configurazione()
                print(f"📝 Storico: assegnazione {row} rinominata → '{nuovo_nome}'")

    # =================================================================
    # FILTRO CLASSI — Dropdown per selezionare classe nelle statistiche
    # =================================================================

    def _popola_filtro_classi(self):
        """
        Popola il dropdown filtro con tutte le classi presenti nello storico.
        """
        self.filtro_classe_combo.clear()

        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            # Nessuna assegnazione - mostra messaggio
            self.filtro_classe_combo.addItem("📭 Nessuna assegnazione salvata", None)
            return

        # Trova tutti i file_origine unici
        classi_trovate = {}  # {file_origine: conteggio_assegnazioni}

        for assegnazione in storico:
            file_origine = assegnazione.get('file_origine', 'File non specificato')
            if file_origine not in classi_trovate:
                classi_trovate[file_origine] = 0
            classi_trovate[file_origine] += 1

        # Ordina per nome file
        classi_ordinate = sorted(classi_trovate.items())

        # Aggiungi placeholder "Seleziona una classe" (solo se più di una classe).
        # Con una sola classe, viene selezionata automaticamente.
        # Il placeholder usa userData = "__placeholder__" come sentinella:
        # _aggiorna_statistiche() in statistiche.py lo intercetta e mostra
        # un messaggio invito anziché statistiche mescolate di classi diverse.
        if len(classi_ordinate) > 1:
            self.filtro_classe_combo.addItem(
                "— Seleziona una classe per visualizzare le statistiche —",
                "__placeholder__"
            )

        # Aggiungi ogni classe trovata
        for file_origine, count in classi_ordinate:
            # Estrae solo nome file (senza path)
            nome_file = os.path.basename(file_origine) if file_origine else "File non specificato"
            self.filtro_classe_combo.addItem(
                f"📁 {nome_file} ({count} assegnazioni)",
                file_origine  # userData = file_origine per filtrare
            )

        print(f"📊 Filtro classi popolato: {len(classi_ordinate)} classi trovate")

        # Applica stile del tema attivo al combo filtro.
        # Va fatto qui (e non solo nel global stylesheet) perché il combo
        # viene ripopolato dinamicamente: senza questo, al cambio tema
        # il dropdown mantiene i colori vecchi finché non viene ricreato.
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

    # =================================================================
    # ELIMINAZIONE ASSEGNAZIONE — Con conferma utente
    # =================================================================

    def _elimina_assegnazione(self, indice_assegnazione: int):
        """
        Elimina un'assegnazione dallo storico dopo conferma dell'utente.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione da eliminare
        """
        try:
            # Ottiene i dati dell'assegnazione da eliminare
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]
                nome_assegnazione = assegnazione.get("nome", "Senza nome")
                data_assegnazione = assegnazione.get("data", "N/A")

                # Conta coppie e trio dal campo "layout" (formato standard)
                layout = assegnazione.get("layout", [])
                studenti_coppia = [s for s in layout if s.get("tipo") == "coppia"]
                num_coppie = len(studenti_coppia) // 2  # Diviso 2: ogni coppia = 2 studenti
                studenti_trio = [s for s in layout if s.get("tipo") == "trio"]
                num_trio = 1 if len(studenti_trio) == 3 else 0

                # Crea messaggio dettagliato
                messaggio_abbinamenti = f"👥 Coppie: {num_coppie}"
                if num_trio > 0:
                    messaggio_abbinamenti += f" | Trio: {num_trio}"

                # Chiede conferma all'utente
                risposta = QMessageBox.question(
                    self,
                    "Conferma eliminazione",
                    f"‼️ Sei sicuro di voler eliminare questa assegnazione?\n\n"
                    f"📅 Data: {data_assegnazione}\n"
                    f"📝 Nome: {nome_assegnazione}\n"
                    f"{messaggio_abbinamenti}\n\n"
                    f"⚠️ QUESTA AZIONE NON PUÒ ESSERE ANNULLATA!",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No  # Pulsante predefinito: No (sicurezza)
                )

                if risposta == QMessageBox.Yes:
                    # Rimuove l'assegnazione dallo storico
                    del self.config_app.config_data["storico_assegnazioni"][indice_assegnazione]

                    # NUOVO: Ricostruisce blacklist per coerenza dopo eliminazione
                    print(f"🔄 Eliminazione assegnazione: avvio ricostruzione blacklist...")
                    self.config_app._ricostruisci_blacklist_da_storico()
                    print(f"✅ Blacklist ricostruita - coerenza garantita")

                    # Salva immediatamente la configurazione aggiornata
                    self.config_app.salva_configurazione()

                    # Aggiorna l'interfaccia
                    self._aggiorna_info_storico()  # Aggiorna contatore e stato
                    self._popola_filtro_classi()   # Riallinea il combo Statistiche

                    # Messaggio di conferma
                    QMessageBox.information(
                        self,
                        "Eliminazione completata",
                        f"✅ Assegnazione '{nome_assegnazione}' eliminata con successo."
                    )

                    # Disabilita i bottoni export: l'assegnazione a cui si
                    # riferivano potrebbe essere quella appena eliminata,
                    # e il nome suggerito per il file verrebbe preso da
                    # una voce diversa dello storico (fuorviante).
                    # L'utente può riesportare dopo aver salvato di nuovo.
                    self.btn_export_excel.setEnabled(False)
                    self.btn_export_excel.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )
                    self.btn_export_report_txt.setEnabled(False)
                    self.btn_export_report_txt.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )

            else:
                # Errore: indice non valido
                QMessageBox.warning(
                    self,
                    "Errore",
                    "Impossibile eliminare: assegnazione non trovata."
                )

        except Exception as e:
            # Gestione errori imprevisti
            QMessageBox.critical(
                self,
                "Errore eliminazione",
                f"Si è verificato un errore durante l'eliminazione:\n{str(e)}"
            )

    # =================================================================
    # DETTAGLI ASSEGNAZIONE — Visualizza report completo in dialog
    # =================================================================

    def _visualizza_dettagli_assegnazione(self, indice_assegnazione: int):
        """
        Visualizza i dettagli completi di un'assegnazione storica in una finestra separata.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione da visualizzare
        """
        try:
            # Ottiene i dati dell'assegnazione
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]

                # Usa il report completo salvato se disponibile
                if "report_completo" in assegnazione:
                    dettagli = assegnazione["report_completo"]
                else:
                    # Fallback: genera report basilare dal layout
                    dettagli = self._genera_report_da_layout(assegnazione)

                # Crea dialog custom ridimensionabile
                dialog = QDialog(self)
                dialog.setWindowTitle(f"📋 Dettagli assegnazione - {assegnazione.get('nome', 'Senza nome')}")
                dialog.setMinimumSize(1150, 800)  # CONFIGURABILE
                dialog.resize(1150, 800)  # CONFIGURABILE

                # Layout verticale
                layout = QVBoxLayout(dialog)

                # TextEdit in sola lettura per il report
                text_edit = QTextEdit()
                text_edit.setPlainText(dettagli)
                text_edit.setReadOnly(True)
                # Usa una famiglia di font monospace con fallback cross-platform
                # "Consolas" → Windows | "Courier New" → macOS | "DejaVu Sans Mono" → Linux
                font_mono = QFont()
                font_mono.setFamily("Consolas")           # Tentativo 1: Windows
                font_mono.setStyleHint(QFont.Monospace)   # Fallback automatico Qt al monospace del sistema
                font_mono.setPointSize(10)
                text_edit.setFont(font_mono)
                layout.addWidget(text_edit)

                # === EVIDENZIAZIONE COPPIE RIUTILIZZATE ===

                # Formato ocra/giallo grassetto
                formato_ocra = QTextCharFormat()
                formato_ocra.setForeground(QColor(C("testo_ocra")))
                formato_ocra.setFontWeight(QFont.Bold)

                # Pattern da evidenziare
                patterns_da_evidenziare = ["Coppia già usata", "BLACKLISTATA_SOFT", "RIUTILIZZATA"]

                # Se il report contiene coppie riutilizzate > 0, evidenzia
                # anche la riga di riepilogo nella sezione statistiche.
                # Controlla che NON sia "Coppie riutilizzate: 0" (quella resta normale).
                if "Coppie riutilizzate:" in dettagli and "Coppie riutilizzate: 0" not in dettagli:
                    patterns_da_evidenziare.append("Coppie riutilizzate:")

                for pattern in patterns_da_evidenziare:
                    cursore = text_edit.textCursor()
                    cursore.movePosition(QTextCursor.Start)
                    text_edit.setTextCursor(cursore)

                    while True:
                        cursore = text_edit.document().find(pattern, cursore)
                        if cursore.isNull():
                            break
                        # Seleziona l'intera riga e applica formato ocra
                        cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                        cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursore.setCharFormat(formato_ocra)

                # Riporta il cursore all'inizio
                cursore_iniziale = text_edit.textCursor()
                cursore_iniziale.movePosition(QTextCursor.Start)
                text_edit.setTextCursor(cursore_iniziale)

                # === FOOTER DIALOG: Salva Report + Chiudi ===
                footer_dettagli = QHBoxLayout()
                footer_dettagli.setSpacing(12)

                # --- Bottone Salva Report ---
                # Salva il report testuale come file .txt con QFileDialog
                btn_salva_report = QPushButton("💾 Salva Report assegnazione (.txt)")
                btn_salva_report.setMinimumHeight(40)
                btn_salva_report.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {C("btn_blu_bg")};
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 6px;
                        padding: 8px 20px;
                    }}
                    QPushButton:hover {{
                        background-color: {C("btn_blu_hover")};
                    }}
                """)

                # Funzione di salvataggio (closure: cattura text_edit e assegnazione)
                def _salva_report_dettagli():
                    """Salva il report della finestra Dettagli come file .txt."""
                    try:
                        # Costruisce nome suggerito: "NomeClasse_-_Report_-_Assegnazione_XX_-_data.txt"
                        nome_ass = assegnazione.get('nome', 'Assegnazione')
                        file_origine = assegnazione.get('file_origine', '')
                        # Estrae nome classe dal file origine (senza estensione .txt)
                        nome_classe = os.path.splitext(file_origine)[0] if file_origine else nome_ass

                        # nome_ass contiene già "Classe2D - Assegnazione 02 - 21/03/2026"
                        # Rimuoviamo il prefisso "Classe2D - " per evitare ridondanza
                        prefisso_classe = nome_classe + " - "
                        nome_senza_classe = nome_ass
                        if nome_senza_classe.startswith(prefisso_classe):
                            nome_senza_classe = nome_senza_classe[len(prefisso_classe):]

                        nome_classe_pulito = pulisci_nome_file(nome_classe)
                        nome_parte_pulita = pulisci_nome_file(nome_senza_classe)
                        nome_suggerito = f"{nome_classe_pulito}_-_Report_-_{nome_parte_pulita}.txt"

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
                                "✅ Report assegnazione salvato con successo!",
                                file_path
                            )

                    except Exception as e:
                        QMessageBox.critical(
                            dialog, "Errore salvataggio",
                            f"❌ Errore durante il salvataggio:\n{str(e)}"
                        )

                btn_salva_report.clicked.connect(_salva_report_dettagli)
                footer_dettagli.addWidget(btn_salva_report)

                # --- Bottone Chiudi ---
                btn_chiudi = QPushButton("✅ Chiudi")
                btn_chiudi.setMinimumHeight(40)
                btn_chiudi.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {C("accento")};
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 6px;
                        padding: 8px 20px;
                    }}
                    QPushButton:hover {{
                        background-color: {C("accento_hover")};
                    }}
                """)
                btn_chiudi.clicked.connect(dialog.close)
                footer_dettagli.addWidget(btn_chiudi)

                layout.addLayout(footer_dettagli)

                # Applica tema attivo al dialog dettagli
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

                # Mostra dialog
                dialog.exec()

            else:
                QMessageBox.warning(self, "Errore", "Assegnazione non trovata.")

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nella visualizzazione:\n{str(e)}")

    # =================================================================
    # REPORT DA LAYOUT — Fallback se manca il report completo salvato
    # =================================================================

    def _genera_report_da_layout(self, assegnazione: dict) -> str:
        """
        Genera un report basilare dal campo 'layout' (fallback se manca report_completo).

        Args:
            assegnazione (dict): Dati dell'assegnazione

        Returns:
            str: Report formattato
        """
        report = []

        # Header
        report.append(f"📋 DETTAGLI ASSEGNAZIONE")
        report.append("=" * 40)
        report.append(f"📝 Nome: {assegnazione.get('nome', 'Senza nome')}")
        report.append(f"📅 Data: {assegnazione.get('data', 'N/A')}")
        report.append(f"🕐 Ora: {assegnazione.get('ora', 'N/A')}")
        report.append(f"📁 File origine: {assegnazione.get('file_origine', 'Non specificato')}")

        # Layout
        layout = assegnazione.get('layout', [])

        if layout:
            # Conta coppie e trio
            studenti_coppia = [s for s in layout if s.get('tipo') == 'coppia']
            studenti_trio = [s for s in layout if s.get('tipo') == 'trio']

            num_coppie = len(studenti_coppia) // 2
            num_trio = 1 if len(studenti_trio) == 3 else 0

            report.append(f"👥 Coppie: {num_coppie}")
            if num_trio > 0:
                report.append(f"👥 Trio: {num_trio}")
            report.append("")

            # Lista abbinamenti
            report.append("💫 ABBINAMENTI FORMATI:")
            report.append("-" * 20)

            # Mostra coppie
            coppie_mostrate = set()
            idx = 1
            for studente_info in layout:
                if studente_info.get('tipo') == 'coppia':
                    nome = studente_info['studente']
                    compagno = studente_info.get('compagno', '?')
                    coppia_key = tuple(sorted([nome, compagno]))

                    if coppia_key not in coppie_mostrate:
                        coppie_mostrate.add(coppia_key)
                        report.append(f"{idx:2d}. {nome} + {compagno}")
                        idx += 1

            # Mostra trio
            if num_trio > 0:
                trio_studenti = [s['studente'] for s in layout if s.get('tipo') == 'trio']
                if len(trio_studenti) == 3:
                    report.append("")
                    report.append(f"TRIO: {' + '.join(trio_studenti)}")
        else:
            report.append("")
            report.append("⚠️ Nessun layout disponibile")

        return "\n".join(report)

    # =================================================================
    # VISUALIZZA LAYOUT STORICO — Apre il popup PopupLayoutStorico
    # =================================================================

    def _visualizza_layout_storico(self, indice_assegnazione):
        """
        Apre il popup per visualizzare il layout grafico di un'assegnazione storica.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione nello storico
        """
        try:
            # Crea e mostra il popup
            popup = PopupLayoutStorico(self, self.config_app, indice_assegnazione)
            popup.exec()  # Mostra come dialog modale

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore Visualizzazione",
                f"❌ Errore durante l'apertura del layout:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
