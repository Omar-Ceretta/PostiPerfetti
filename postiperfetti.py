    # =================================================================
"""
    «PostiPerfetti» - v. 2.0 — Programma per l'assegnazione automatica
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

import sys
# Disabilita la creazione delle cartelle __pycache__ e dei file .pyc
sys.dont_write_bytecode = True
import os
# Protezione cross-platform: su Windows in modalità "windowed" (PyInstaller --windowed),
# sys.stdout e sys.stderr sono None → ogni print() causerebbe un crash.
# Redirigiamo a devnull per renderle innocue.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
import math
from datetime import datetime
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QFileDialog, QTextEdit,
    QGroupBox, QRadioButton, QCheckBox,
    QTableWidget, QTabWidget,
    QMessageBox, QScrollArea, QLineEdit,
    QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QPixmap, QIcon

# Import delle classi del dominio
from moduli.studenti import Student
from moduli.aula import ConfigurazioneAula
from moduli.algoritmo import AssegnatorePosti
from moduli.vincoli import MotoreVincoli
# Import dell'editor grafico studenti (nella cartella moduli/)
from moduli.editor_studenti import EditorStudentiWidget, ComboBoxProtetto
# Importa il sistema di gestione tema (colori scuro/chiaro)
from moduli.tema import C, imposta_tema, get_tema
# Funzioni di utilità globali (percorsi, file, popup, cursore, factory bottoni)
from moduli.utilita import (
    get_base_path, pulisci_nome_file, apri_file_con_applicazione_default,
    mostra_popup_file_salvato, abbrevia_nome_assegnazione, FiltroCursoreManina,
    crea_bottone  # Factory per bottoni standard con stile uniforme
)
# Classe ConfigurazioneApp (gestione JSON, storico, blacklist)
from moduli.configurazione import ConfigurazioneApp
# Mixin statistiche (calcolo e visualizzazione nella tab Statistiche)
from moduli.statistiche import StatisticheMixin
# Mixin stili (stylesheet globale + stili inline widget)
from moduli.stili import StiliMixin
# Mixin esportazione (Excel, report TXT, utility nomi)
from moduli.esportazione import EsportazioneMixin
# Mixin storico UI (tabella, dettagli, filtro, eliminazione, layout popup)
from moduli.storico_ui import StoricoUIMixin, PopupLayoutStorico
# Finestre informative (istruzioni, crediti, aiuto aula)
from moduli.istruzioni import mostra_istruzioni, mostra_crediti, mostra_aiuto_configurazione_aula

class WorkerThread(QThread):
    """
    Thread separato per eseguire l'algoritmo di assegnazione senza bloccare l'interfaccia.
    """

    # Signals per comunicare con l'interfaccia principale
    progress_updated = Signal(int)  # Percentuale di completamento
    status_updated = Signal(str)    # Messaggio di stato
    completed = Signal(object)      # Risultato finale (AssegnatorePosti)
    error_occurred = Signal(str, object)    # (messaggio_testo, report_diagnostico_o_None)

    def __init__(self, studenti, configurazione_aula, config_app, modalita_trio='centro', flag_genere_misto=False, studente_fisso=None):
        super().__init__()
        self.studenti = studenti
        self.configurazione_aula = configurazione_aula
        self.config_app = config_app
        # La rotazione è SEMPRE attiva: con storico vuoto (prima assegnazione)
        # la blacklist è vuota → zero penalità, comportamento identico.
        # Con storico pieno, il sistema a cascata rilassa automaticamente.
        self.modalita_rotazione = True
        self.modalita_trio = modalita_trio             # Posizione trio: 'prima', 'ultima', 'centro'
        self.flag_genere_misto = flag_genere_misto     # Flag genere misto dal checkbox
        self.studente_fisso = studente_fisso           # Studente con posizione FISSO (o None)

    def run(self):
        """Esegue l'assegnazione in background."""
        try:
            self.status_updated.emit("🔄 Inizializzazione algoritmo...")
            self.progress_updated.emit(10)

            # Crea l'assegnatore con configurazione personalizzata
            assegnatore = AssegnatorePosti()

            # Passa parametri necessari all'assegnatore per penalità storico
            assegnatore.config_app = self.config_app
            assegnatore.modalita_rotazione = True  # Sempre attivo
            print("🔧 Assegnatore configurato: rotazione sempre attiva")

            motore = assegnatore.motore_vincoli
            # I pesi dei vincoli sono fissi in MotoreVincoli, solo flag genere misto è configurabile
            # Imposta flag genere misto obbligatorio dal checkbox
            motore.imposta_genere_misto_obbligatorio(self.flag_genere_misto)

            # Passa riferimento configurazione per equità tentativo 4
            motore._config_app_ref = self.config_app
            print(f"🔧 Motore vincoli configurato con riferimento config per equità")

            # Le penalità storico si applicano SEMPRE.
            # Con storico vuoto la blacklist è vuota → nessun effetto.
            self._applica_penalita_storico(motore)

            self.status_updated.emit("🧮 Calcolo coppie ottimali...")
            self.progress_updated.emit(30)

            self.status_updated.emit("📍 Assegnazione posizioni...")
            self.progress_updated.emit(60)

            # Esegue l'assegnazione completa
            successo = assegnatore.esegui_assegnazione_completa(
                self.studenti,
                self.configurazione_aula,
                self.modalita_trio,  # USA LA VARIABILE DI ISTANZA
                studente_fisso=self.studente_fisso  # Passa studente FISSO (o None)
            )

            self.progress_updated.emit(90)

            if successo:
                self.status_updated.emit("✅ Assegnazione completata!")
                self.progress_updated.emit(100)
                self.completed.emit(assegnatore)
            else:
                # Passa il report diagnostico strutturato (o None se non disponibile)
                # alla GUI, così il popup può mostrare dettagli utili all'utente
                report = getattr(assegnatore, 'report_fallimento', None)
                self.error_occurred.emit(
                    "Assegnazione fallita - vincoli irrisolvibili",
                    report
                )

        except Exception as e:
            # Errore imprevisto: nessun report diagnostico disponibile
            self.error_occurred.emit(f"Errore durante l'assegnazione: {str(e)}", None)

    def _applica_penalita_storico(self, motore_vincoli: MotoreVincoli):
        """
        Modifica il motore vincoli per penalizzare coppie già utilizzate.
        """
        coppie_usate = self.config_app.config_data["coppie_da_evitare"]

        if not coppie_usate:
            return  # Nessuno storico, niente da fare

        # Salva il metodo originale
        calcola_originale = motore_vincoli.calcola_punteggio_coppia

        def calcola_con_penalita_storico(studente1: Student, studente2: Student) -> Dict:
            # Calcola punteggio normale
            risultato = calcola_originale(studente1, studente2)

            # Cerca se questa coppia è già stata usata
            for coppia_usata in coppie_usate:
                # Estrae nomi dalla coppia in blacklist (formato unico)
                studenti = coppia_usata.get("studenti", [])
                if len(studenti) != 2:
                    continue  # Salta voci malformate
                cognomi_coppia = {studenti[0], studenti[1]}

                # Confronta con la coppia attuale usando nomi completi
                cognomi_attuali = {studente1.get_nome_completo(), studente2.get_nome_completo()}

                if cognomi_coppia == cognomi_attuali:
                    volte_usata = coppia_usata["volte_usata"]
                    penalita = 500 * volte_usata  # Penalità aumentata per scoraggiare riutilizzo

                    # Trova QUANDO è stata usata (cerca nelle assegnazioni storiche)
                    info_quando = self._trova_quando_coppia_usata(cognomi_attuali)

                    risultato["punteggio_totale"] -= penalita
                    if info_quando:
                        risultato["note"].append(f"Coppia già usata {volte_usata} volte (penalità: -{penalita}) - {info_quando}")
                    else:
                        risultato["note"].append(f"Coppia già usata {volte_usata} volte (penalità: -{penalita})")

                    # Aggiusta valutazione
                    if risultato["punteggio_totale"] < 0:
                        risultato["valutazione"] = "RIUTILIZZATA"
                    break

            return risultato

        # Sostituisce il metodo con la versione che include le penalità
        motore_vincoli.calcola_punteggio_coppia = calcola_con_penalita_storico

    def _trova_quando_coppia_usata(self, cognomi_coppia):
        """
        Trova quando una coppia è stata usata nelle assegnazioni precedenti.
        Cerca nel campo "layout" (formato corrente) di ogni assegnazione.

        Args:
            cognomi_coppia: Set con i nomi completi dei due studenti

        Returns:
            str: Informazione su quando è stata usata (es: "ultima volta: Assegnazione 21/09/2025")
        """
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        # Cerca nell'ordine cronologico inverso (più recenti per primi)
        assegnazioni_trovate = []

        for assegnazione in reversed(storico):
            nome_assegnazione = assegnazione.get("nome", "Assegnazione senza nome")
            data_assegnazione = assegnazione.get("data", "")
            layout = assegnazione.get("layout", [])

            # Cerca la coppia nel layout (formato corrente)
            trovata = False
            for studente_info in layout:
                tipo = studente_info.get("tipo")
                nome = studente_info.get("studente", "")

                # Cerca nelle coppie normali
                if tipo == "coppia":
                    compagno = studente_info.get("compagno", "")
                    if {nome, compagno} == cognomi_coppia:
                        assegnazioni_trovate.append(nome_assegnazione)
                        trovata = True
                        break

                # Cerca nei trio (coppie virtuali adiacenti)
                elif tipo == "trio":
                    compagni = studente_info.get("compagni_trio", [])
                    for compagno in compagni:
                        if {nome, compagno} == cognomi_coppia:
                            assegnazioni_trovate.append(f"{nome_assegnazione} [trio]")
                            trovata = True
                            break
                    if trovata:
                        break

        if assegnazioni_trovate:
            if len(assegnazioni_trovate) == 1:
                return f"usata in: {assegnazioni_trovate[0]}"
            else:
                return f"ultima volta: {assegnazioni_trovate[0]}"

        return None  # Non trovata (non dovrebbe succedere se penalità applicata)

class FinestraPostiPerfetti(QMainWindow, StatisticheMixin, StiliMixin, EsportazioneMixin, StoricoUIMixin):
    """
    Finestra principale dell'applicazione.
    """

    def __init__(self):
        super().__init__()

        # Configurazione dell'applicazione
        self.config_app = ConfigurazioneApp()
        self.config_app.carica_configurazione()

        # Dati dell'applicazione
        self.studenti = []
        self.configurazione_aula = None
        self.ultimo_assegnatore = None
        self.file_origine_studenti = None  # Nome del file .txt caricato

        # Flag per tracking posti insufficienti
        self.posti_insufficienti = False

        # Flag per tracking assegnazione non salvata nello Storico
        # Diventa True dopo un'elaborazione completata, torna False dopo il salvataggio
        self.assegnazione_non_salvata = False

        # Sistema messaggi rotativi per feedback elaborazione
        self.timer_messaggi = QTimer()
        self.timer_messaggi.timeout.connect(self._aggiorna_messaggio_elaborazione)
        self.indice_messaggio = 0
        self.messaggi_elaborazione = [
            "🔄 Elaborazione in corso...",
            "🧮 Calcolo coppie ottimali...",
            "🔍 Verifica vincoli...",
            "⚡ Ottimizzazione assegnazione...",
            "🎯 Ricerca soluzione migliore...",
            "🔄 Elaborazione in corso..."
        ]

        # Setup interfaccia - DIMENSIONE MINIMA CONFIGURABILE
        self.setWindowTitle("«PostiPerfetti» — v2.0")
        self.setMinimumSize(1425, 975)
        # Apre la finestra massimizzata per una migliore visualizzazione
        self.showMaximized()
        self.setup_ui()
        self.setup_stili()

        # Carica dati iniziali se disponibili
        self._carica_dati_iniziali()

        # Applica gli stili inline al tema attivo (caricato da config o default scuro)
        self._aggiorna_stili_widget()

    def setup_ui(self):
        """Crea l'interfaccia utente principale."""

        # Widget centrale con layout principale
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout principale orizzontale
        main_layout = QHBoxLayout(central_widget)

        # PANNELLO SINISTRO: Controlli e configurazione
        left_panel = self._crea_pannello_controlli()
        main_layout.addWidget(left_panel, 1)  # 1/4 dello spazio

        # PANNELLO DESTRO: Visualizzazione risultati
        right_panel = self._crea_pannello_risultati()
        main_layout.addWidget(right_panel, 4)  # 3/4 dello spazio

    # =================================================================
    # PANNELLO SINISTRO (CONTROLLI) — Metodo orchestratore
    # =================================================================
    # Ognuno dei 7 metodi seguenti, separati fra loro per miglior leggibilità,
    # crea una sezione del pannello e aggiunge i widget al layout.
    # L'ordine di chiamata determina l'ordine visivo dall'alto al basso.
    # =================================================================

    def _crea_pannello_controlli(self) -> QWidget:
        """Crea il pannello sinistro con tutti i controlli, dentro una QScrollArea
        per adattarsi anche a schermi piccoli (ad es. notebook 13")."""

        # === SCROLL AREA: contenitore esterno scrollabile ===
        # Su schermi grandi: nessuna scrollbar visibile.
        # Su schermi piccoli (13"): appare la scrollbar verticale.
        self.scroll_pannello_sx = QScrollArea()
        self.scroll_pannello_sx.setWidgetResizable(True)
        # Scrollbar orizzontale: MAI (il pannello non deve allargarsi)
        self.scroll_pannello_sx.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Scrollbar verticale: solo se il contenuto non entra nello schermo
        self.scroll_pannello_sx.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Bordo invisibile: la scroll area non deve aggiungere cornici visive
        self.scroll_pannello_sx.setFrameShape(QFrame.NoFrame)
        # Larghezza minima: impedisce al pannello destro di "mangiare" il sinistro
        # quando la finestra viene ridimensionata. 350px è sufficiente per contenere
        # tutti i pulsanti, label e il box vincoli con font 12pt.
        # CONFIGURABILE: aumenta se i contenuti risultano ancora tagliati,
        # riduci (min ~300) se vuoi permettere finestre più strette.
        self.scroll_pannello_sx.setMinimumWidth(350)

        # Widget interno che contiene tutti i controlli
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # === FONT PER TUTTO IL PANNELLO SINISTRO ===
        # Impostazione globale: tutti i widget figli ereditano questo font
        font_pannello = QFont()
        font_pannello.setPointSize(12)  # Font base più grande (CONFIGURABILE)
        panel.setFont(font_pannello)

        # ─────────────────────────────────────────────────
        # SPAZIATURA TRA I BOX — VALORE CONFIGURABILE
        # Modifica questo valore per aumentare/diminuire
        # lo spazio tra un gruppo e l'altro nel pannello.
        # Valori consigliati: 6 (compatto), 8 (normale), 12 (ampio)
        SPAZIO_TRA_BOX = 8
        # ─────────────────────────────────────────────────

        # === ASSEMBLAGGIO SEZIONI (ordine = dall'alto al basso) ===
        self._crea_sezione_logo_bottoni(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_stato_classe(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_configurazione_aula(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_gestione_dispari(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_opzioni_vincoli(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_modalita(layout, SPAZIO_TRA_BOX)
        self._crea_bottone_avvia(layout)

        # Inserisce il widget dei controlli nella scroll area.
        # Su schermi grandi il contenuto entra tutto → nessuna scrollbar.
        # Su schermi piccoli → appare scrollbar verticale automatica.
        self.scroll_pannello_sx.setWidget(panel)

        return self.scroll_pannello_sx

    # -----------------------------------------------------------------
    # Sotto-metodo 1/7: Logo del programma + bottoni Istruzioni/Tema/Crediti
    # -----------------------------------------------------------------
    def _crea_sezione_logo_bottoni(self, layout, SPAZIO_TRA_BOX):
        """Crea la parte superiore del pannello: logo, bottone Istruzioni,
        e la riga con toggle Tema + bottone Crediti."""

        # === ICONA DEL PROGRAMMA ===
        # Inserita in cima al pannello sinistro, sopra i bottoni Istruzioni/Tema.
        # Usare QLabel con QPixmap è il metodo più stabile in PySide6 per mostrare immagini.
        icona_label = QLabel()
        icona_path = os.path.join(get_base_path(), "moduli", "postiperfetti_logo.png")
        if os.path.exists(icona_path):
            pixmap = QPixmap(icona_path)
            # Dimensione massima del logo.
            # CONFIGURABILE: modifica questi valori per ingrandire/rimpicciolire il logo
            LOGO_LARGHEZZA_MAX = 220  # pixel — larghezza massima
            LOGO_ALTEZZA_MAX = 110    # pixel — altezza massima
            pixmap = pixmap.scaled(LOGO_LARGHEZZA_MAX, LOGO_ALTEZZA_MAX,
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icona_label.setPixmap(pixmap)
        else:
            # Fallback silenzioso: se il file non c'è (es. distribuzione incompleta)
            # non mostra nulla e non causa errori.
            icona_label.setText("«Posti🪑Perfetti»")
            icona_label.setStyleSheet("font-size: 40px;")

        # Centra orizzontalmente l'icona nel pannello
        icona_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icona_label)

        # Piccolo spazio tra icona e bottoni (ridotto per schermi compatti)
        layout.addSpacing(10)

        # === RIGA 1: Bottone Istruzioni (tutta la larghezza) ===
        self.btn_istruzioni = crea_bottone(
            "👉 Istruzioni 👈", C("btn_indaco_bg"), C("btn_indaco_hover"),
            tooltip="Mostra la guida completa all'uso del programma",
            font_size=14
        )
        self.btn_istruzioni.clicked.connect(self._mostra_istruzioni)
        layout.addWidget(self.btn_istruzioni)

        # === RIGA 2: Toggle tema + Info/Crediti (centrati, dimensione ridotta) ===
        riga_tema_info = QHBoxLayout()
        riga_tema_info.addStretch()  # Spazio elastico a sinistra → centra i bottoni

        # Bottone toggle tema: colore ambra/ocra per distinguerlo.
        self.btn_toggle_tema = crea_bottone(
            "☀️ Tema chiaro", C("btn_tema_bg"), C("btn_tema_hover"),
            tooltip="Alterna tra tema scuro e tema chiaro",
            font_size=12, padding="8px 14px"
        )
        self.btn_toggle_tema.clicked.connect(self._cambia_tema)
        riga_tema_info.addWidget(self.btn_toggle_tema)

        riga_tema_info.addSpacing(8)  # Piccolo spazio tra i due bottoni

        # Bottone "Info / Crediti": piccolo bottone rotondo per mostrare
        # informazioni sul programma, l'autore e la licenza.
        self.btn_crediti = QPushButton("💬")
        self.btn_crediti.setFixedSize(42, 42)
        self.btn_crediti.setToolTip("Informazioni e crediti")
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
        self.btn_crediti.clicked.connect(self._mostra_crediti)
        riga_tema_info.addWidget(self.btn_crediti)

        riga_tema_info.addStretch()  # Spazio elastico a destra → centra i bottoni

        layout.addLayout(riga_tema_info)

        # Spazio tra pulsante Istruzioni e primo box
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 2/7: GroupBox "STATO CLASSE"
    # -----------------------------------------------------------------
    def _crea_sezione_stato_classe(self, layout, SPAZIO_TRA_BOX):
        """Crea la sezione informativa sullo stato della classe caricata.
        Il caricamento avviene dalla tab 'Editor studenti'."""

        group_dati = QGroupBox("📋 STATO CLASSE")
        layout_dati = QVBoxLayout(group_dati)

        # Nome classe (read-only: si popola automaticamente dal nome del file .txt)
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
        label_nome_classe = QLabel("Nome classe:")
        label_nome_classe.setStyleSheet("font-size: 13px;")
        layout_dati.addWidget(label_nome_classe)
        layout_dati.addWidget(self.input_nome_classe)

        # Label di stato: mostra lo stato del caricamento/classe
        # (si aggiorna automaticamente quando l'Editor salva e carica un file)
        self.label_studenti_caricati = QLabel(
            "NESSUN FILE CARICATO.\n\n"
            "➡ Vai in '✏️ Editor studenti'e clicca su '📝 Seleziona classe'."
        )
        self.label_studenti_caricati.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 13px; font-style: italic;")
        # Word wrap: il testo lungo (es. "Nuova classe nell'Editor — Clicca...")
        # va a capo automaticamente invece di allargare il pannello sinistro
        self.label_studenti_caricati.setWordWrap(True)
        layout_dati.addWidget(self.label_studenti_caricati)

        layout.addWidget(group_dati)
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 3/7: GroupBox "CONFIGURAZIONE AULA"
    # -----------------------------------------------------------------
    def _crea_sezione_configurazione_aula(self, layout, SPAZIO_TRA_BOX):
        """Crea la sezione con i controlli per file di banchi e posti per fila,
        inclusi i bottoni +/− e il bottone '?' di aiuto."""

        self.group_aula = QGroupBox("🏫 CONFIGURAZIONE AULA")
        layout_aula = QVBoxLayout(self.group_aula)
        layout_aula.setSpacing(6)

        # --- RIGA 1: File di banchi (centrata) ---
        riga_file = QHBoxLayout()
        riga_file.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        riga_file.addWidget(QLabel("  File di banchi:  "))
        riga_file.addSpacing(8)

        # === NUMERO DI FILE - Widget personalizzato con bottoni visibili ===
        # Container per campo + bottoni (larghezza limitata per non sprecare spazio)
        container_file = QWidget()
        container_file.setMaximumWidth(130)  # — [campo] + (bastano ~130px)
        layout_file = QHBoxLayout(container_file)
        layout_file.setContentsMargins(0, 0, 0, 0)
        layout_file.setSpacing(4)

        # Campo numero (read-only, centrato)
        # Valore iniziale: SEMPRE il default (4 file), indipendentemente
        # dall'ultimo valore salvato in config.json. Il numero di file
        # è un parametro operativo che dipende dalla classe/aula corrente,
        # non una preferenza persistente come il tema.
        NUM_FILE_DEFAULT = 4  # CONFIGURABILE: default ragionevole per la maggior parte delle aule
        self.input_num_file = QLineEdit()
        self.input_num_file.setText(str(NUM_FILE_DEFAULT))
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

        # Bottone - (diminuisci)
        self.btn_file_meno = QPushButton("−")  # Unicode minus sign
        self.btn_file_meno.setMaximumWidth(30)
        self.btn_file_meno.setStyleSheet(f"""
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
        self.btn_file_meno.setToolTip("Riduci il numero di file di banchi")
        self.btn_file_meno.clicked.connect(lambda: self._cambia_num_file(-1))

        # Bottone + (aumenta)
        self.btn_file_piu = QPushButton("+")  # Unicode plus sign
        self.btn_file_piu.setMaximumWidth(30)
        self.btn_file_piu.setStyleSheet(f"""
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
        self.btn_file_piu.setToolTip("Aggiungi una fila di banchi")
        self.btn_file_piu.clicked.connect(lambda: self._cambia_num_file(+1))

        # Assembla il widget
        layout_file.addWidget(self.btn_file_meno)
        layout_file.addWidget(self.input_num_file)
        layout_file.addWidget(self.btn_file_piu)

        riga_file.addWidget(container_file)
        riga_file.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_file)

        # --- RIGA 2: Posti per fila (centrata) ---
        riga_posti_fila = QHBoxLayout()
        riga_posti_fila.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        riga_posti_fila.addWidget(QLabel("  Posti per fila:  "))
        riga_posti_fila.addSpacing(8)

        # === POSTI PER FILA - Widget personalizzato (solo valori PARI) ===

        # Container per campo + bottoni (larghezza limitata per non sprecare spazio)
        container_posti = QWidget()
        container_posti.setMaximumWidth(130)  # — [campo] + (bastano ~130px)
        layout_posti = QHBoxLayout(container_posti)
        layout_posti.setContentsMargins(0, 0, 0, 0)
        layout_posti.setSpacing(4)

        # Campo numero (read-only, centrato)
        # Valore iniziale: SEMPRE il default (6 posti), stessa logica di num_file.
        # Deve essere PARI (i banchi sono da 2), quindi 6 è il valore più comune.
        POSTI_PER_FILA_DEFAULT = 6  # Configurabile: deve essere pari (banchi da 2)
        self.input_posti_fila = QLineEdit()
        self.input_posti_fila.setText(str(POSTI_PER_FILA_DEFAULT))
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

        # Bottone - (diminuisci di 2)
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

        # Bottone + (aumenta di 2)
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

        # Assembla il widget
        layout_posti.addWidget(self.btn_posti_meno)
        layout_posti.addWidget(self.input_posti_fila)
        layout_posti.addWidget(self.btn_posti_piu)

        riga_posti_fila.addWidget(container_posti)
        riga_posti_fila.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_posti_fila)

        # --- RIGA 3: Posti totali + bottone aiuto (centrata) ---
        riga_posti = QHBoxLayout()
        riga_posti.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        self.label_posti_totali = QLabel("  Posti totali: 24  ")
        self.label_posti_totali.setWordWrap(True)
        riga_posti.addWidget(self.label_posti_totali)
        riga_posti.addSpacing(6)

        # Bottone "?" per spiegare visivamente il layout dell'aula
        self.btn_aiuto_aula = QPushButton("?")
        self.btn_aiuto_aula.setFixedSize(32, 32)
        self.btn_aiuto_aula.setToolTip("Clicca per capire come contare file e posti")
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
        self.btn_aiuto_aula.clicked.connect(self._mostra_aiuto_configurazione_aula)
        riga_posti.addWidget(self.btn_aiuto_aula)
        riga_posti.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_posti)

        layout.addWidget(self.group_aula)
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 4/7: GroupBox "GESTIONE NUMERO DISPARI"
    # -----------------------------------------------------------------
    def _crea_sezione_gestione_dispari(self, layout, SPAZIO_TRA_BOX):
        """Crea la sezione per gestire la posizione del banco da 3
        quando viene formato un trio. Inizialmente nascosta."""

        self.group_dispari = QGroupBox("GESTIONE NUMERO DISPARI")
        layout_dispari = QVBoxLayout(self.group_dispari)

        # Info label
        self.label_info_dispari = QLabel("Se si formerà un 'trio', il banco da 3 sarà posizionato:")
        self.label_info_dispari.setWordWrap(True)
        self.label_info_dispari.setStyleSheet(f"color: {C('testo_info')}; font-size: 13px; font-style: italic;")
        layout_dispari.addWidget(self.label_info_dispari)

        # Radio buttons per posizione 'trio'
        # L'algoritmo forma sempre le stesse coppie indipendentemente dalla posizione fisica del trio
        # Ordine verticale: dalla cattedra verso il fondo dell'aula
        self.radio_trio_prima = QRadioButton("Inizio (prima fila)")
        self.radio_trio_centro = QRadioButton("Centro aula")
        self.radio_trio_centro.setChecked(True)  # Default: centro aula
        self.radio_trio_ultima = QRadioButton("Fine (ultima fila)")

        layout_dispari.addWidget(self.radio_trio_prima)
        layout_dispari.addWidget(self.radio_trio_centro)
        layout_dispari.addWidget(self.radio_trio_ultima)

        # Inizialmente nascosto
        self.group_dispari.setVisible(False)

        layout.addWidget(self.group_dispari)
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 5/7: GroupBox "OPZIONI VINCOLI"
    # -----------------------------------------------------------------
    def _crea_sezione_opzioni_vincoli(self, layout, SPAZIO_TRA_BOX):
        """Crea la sezione con le opzioni avanzate sui vincoli"""

        self.group_opzioni = QGroupBox("⚙️ OPZIONI VINCOLI")
        layout_opzioni = QVBoxLayout(self.group_opzioni)

        # Checkbox per preferenza genere misto
        # È una PREFERENZA FORTE, non un vincolo assoluto
        # Questo permette di gestire classi sbilanciate e migliora le performance
        self.checkbox_genere_misto = QCheckBox("Preferisci coppie miste (M+F)")
        self.checkbox_genere_misto.setToolTip(
            "Se attivo, dà forte preferenza alle coppie miste.\n"
            "NON vieta coppie stesso genere se necessario per varietà rotazioni."
        )
        layout_opzioni.addWidget(self.checkbox_genere_misto)

        layout.addWidget(self.group_opzioni)
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 6/7: GroupBox "MODALITÀ ASSEGNAZIONE"
    # -----------------------------------------------------------------
    def _crea_sezione_modalita(self, layout, SPAZIO_TRA_BOX):
        """Crea la sezione informativa sullo Storico assegnazioni.
        La rotazione è SEMPRE attiva (con Storico vuoto si comporta come
        'prima assegnazione'; con Storico pieno il sistema a cascata rilassa
        automaticamente la blacklist)."""

        self.group_modalita = QGroupBox("🔄 ROTAZIONE AUTOMATICA")
        layout_modalita = QVBoxLayout(self.group_modalita)

        # Info Storico — label usata anche da storico_ui.py (_aggiorna_info_storico)
        self.label_storico = QLabel("Storico: nessuna assegnazione precedente")
        self.label_storico.setWordWrap(True)
        self.label_storico.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;")
        layout_modalita.addWidget(self.label_storico)

        layout.addWidget(self.group_modalita)
        layout.addSpacing(SPAZIO_TRA_BOX)

    # -----------------------------------------------------------------
    # Sotto-metodo 7/7: Bottone "ASSEGNA I POSTI!" + label status
    # -----------------------------------------------------------------
    def _crea_bottone_avvia(self, layout):
        """Crea il bottone principale di avvio assegnazione, la label di status,
        e disabilita i gruppi finché non si carica una classe."""

        self.btn_avvia_assegnazione = crea_bottone(
            "🚀 ASSEGNA I POSTI!", C("btn_avvia_bg"), C("btn_avvia_hover"),
            tooltip="Calcola la disposizione ottimale dei posti\n"
                    "rispettando vincoli, affinità e rotazioni precedenti",
            altezza_min=50, font_size=16, border_radius=8,  #CONFIGURABILE
            colore_disabled_bg=C("btn_avvia_disabled_bg"),
            colore_disabled_txt=C("btn_avvia_disabled_txt")
        )
        self.btn_avvia_assegnazione.clicked.connect(self.avvia_assegnazione)
        self.btn_avvia_assegnazione.setEnabled(False)  # Disabilitato finché non si caricano dati
        # Disabilita i box di configurazione finché non si carica una classe.
        # Evita che l'utente modifichi parametri senza avere dati caricati,
        # il che causerebbe confusione (es: le modifiche verrebbero poi sovrascritte
        # dal caricamento). Si abilitano in _carica_studenti_da_editor().
        self.group_aula.setEnabled(False)
        self.group_opzioni.setEnabled(False)
        self.group_modalita.setEnabled(False)

        layout.addWidget(self.btn_avvia_assegnazione)

        # Status label
        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_status)

    def _crea_pannello_risultati(self) -> QWidget:
        """Crea il pannello destro per visualizzare i risultati."""

        # Tab widget principale per organizzare i risultati
        self.tab_widget = QTabWidget()

        # === TAB 1: VISUALIZZAZIONE AULA ===
        self.tab_aula = QWidget()
        layout_aula = QVBoxLayout(self.tab_aula)

        # Area scrollabile per la visualizzazione dell'aula
        scroll_aula = QScrollArea()
        self.widget_aula = QWidget()
        self.layout_griglia_aula = QGridLayout(self.widget_aula)
        scroll_aula.setWidget(self.widget_aula)
        scroll_aula.setWidgetResizable(True)
        layout_aula.addWidget(scroll_aula)

        # Controlli per export
        controls_export = QHBoxLayout()

        # 1. SALVA ASSEGNAZIONE (verde scuro - azione primaria)
        self.btn_salva_progetto = crea_bottone(
            "💾 Salva assegnazione", C("btn_salva_bg"), C("btn_salva_hover"),
            tooltip="Salva l'assegnazione nello Storico.\n"
                    "Indispensabile per le rotazioni future!",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt")
        )
        self.btn_salva_progetto.clicked.connect(self.salva_assegnazione)
        self.btn_salva_progetto.setEnabled(False)
        controls_export.addWidget(self.btn_salva_progetto)

        # 2. ESPORTA EXCEL (azzurro - export visuale)
        self.btn_export_excel = crea_bottone(
            "📊 Esporta Excel", C("btn_excel_bg"), C("btn_excel_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'export.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt")
        )
        self.btn_export_excel.clicked.connect(self.esporta_excel)
        self.btn_export_excel.setEnabled(False)
        controls_export.addWidget(self.btn_export_excel)

        # 3. ESPORTA REPORT TXT (arancione - export testuale)
        self.btn_export_report_txt = crea_bottone(
            "📋 Esporta Report assegnazione (.txt)", C("btn_export_bg"), C("btn_export_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'export.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt")
        )
        self.btn_export_report_txt.clicked.connect(self.esporta_report_txt)
        self.btn_export_report_txt.setEnabled(False)
        controls_export.addWidget(self.btn_export_report_txt)

        controls_export.addStretch()
        layout_aula.addLayout(controls_export)

        # === TAB 1 EDITOR STUDENTI ===
        # L'Editor è il PRIMO tab perché il flusso di lavoro inizia da qui:
        # l'utente crea/carica il file classe, imposta vincoli, salva,
        # e solo dopo procede con l'assegnazione nelle tab successive.
        self.editor_studenti = EditorStudentiWidget()
        self.tab_widget.addTab(self.editor_studenti, "✏️ Editor studenti")

        self.tab_widget.addTab(self.tab_aula, "🏫 Aula")

        # === TAB 3: REPORT DETTAGLIATO ===
        self.tab_report = QWidget()
        layout_report = QVBoxLayout(self.tab_report)

        self.text_report = QTextEdit()
        self.text_report.setReadOnly(True)
        # Font monospazio cross-platform: "Consolas" (Windows) con fallback
        # automatico Qt al monospazio del sistema (Linux/macOS)
        font_report = QFont()
        font_report.setFamily("Consolas")
        font_report.setPointSize(9)
        font_report.setStyleHint(QFont.Monospace)
        self.text_report.setFont(font_report)
        layout_report.addWidget(self.text_report)

        # Banner informativo in fondo alla tab Report.
        # Orienta l'utente verso la tab Aula per l'export, senza
        # duplicare il pulsante (che creerebbe ambiguità).
        # Nascosto inizialmente: diventa visibile quando c'è un report attivo.
        # Usa rich text (HTML) per controllare dimensione e stile del font:
        # in Qt, sia setFont() che font-size nel CSS inline vengono spesso
        # ignorati quando uno stylesheet globale agisce sulle QLabel.
        # L'HTML inline bypassa completamente la cascata CSS.
        self.label_hint_report = QLabel()
        self.label_hint_report.setTextFormat(Qt.RichText)
        self.label_hint_report.setText(
            f'<p align="center" style="color: {C("testo_secondario")}; '
            f'font-size: 14px; font-style: italic; padding: 6px;">'
            f'💡 Per esportare il Report in formato .txt, vai nella tab 🏫 Aula.'
            f'</p>'
        )
        self.label_hint_report.setAlignment(Qt.AlignCenter)
        self.label_hint_report.setVisible(False)
        layout_report.addWidget(self.label_hint_report)

        self.tab_widget.addTab(self.tab_report, "📊 Report")

        # === TAB 3: STORICO ASSEGNAZIONI ===
        self.tab_storico = QWidget()
        layout_storico = QVBoxLayout(self.tab_storico)

        # --- Placeholder visibile quando lo storico è vuoto ---
        # Messaggio centrato coerente con la tab Statistiche.
        # Viene mostrato/nascosto da _aggiorna_tabella_storico() in storico_ui.py.
        self.label_storico_vuoto = QLabel(
            "📭 NESSUNA ASSEGNAZIONE SALVATA.\n\n"
            "📚 Esegui almeno un'assegnazione e salvala\n"
            "per visualizzare lo Storico."
        )
        self.label_storico_vuoto.setAlignment(Qt.AlignCenter)
        self.label_storico_vuoto.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
        )
        layout_storico.addWidget(self.label_storico_vuoto)

        # --- Tabella storico (nascosta finché non ci sono assegnazioni) ---
        self.tabella_storico = QTableWidget()
        self.tabella_storico.setColumnCount(4)
        self.tabella_storico.setHorizontalHeaderLabels(["Data", "Nome", "Abbinamenti", "Azioni"])
        # Salva automaticamente se l'utente rinomina un'assegnazione (colonna 'Nome')
        self.tabella_storico.cellChanged.connect(self._on_storico_nome_modificato)
        layout_storico.addWidget(self.tabella_storico)

        self.tab_widget.addTab(self.tab_storico, "📚 Storico")

        # === TAB 4: STATISTICHE AGGREGATE ===
        self.tab_statistiche = QWidget()
        layout_statistiche = QVBoxLayout(self.tab_statistiche)

        # Header con filtro classe
        header_stats = QHBoxLayout()

        label_filtro = QLabel("📊 Visualizza statistiche per:")
        label_filtro.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_stats.addWidget(label_filtro)

        self.filtro_classe_combo = ComboBoxProtetto()
        self.filtro_classe_combo.setMinimumWidth(400)
        # Stylesheet tematizzato: i colori si adattano al tema scuro/chiaro.
        # Viene rigenerato al cambio tema da _aggiorna_stili_widget() in stili.py.
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

        # Area scrollabile per statistiche
        scroll_stats = QScrollArea()
        scroll_stats.setWidgetResizable(True)

        self.widget_statistiche = QWidget()
        self.layout_statistiche_content = QVBoxLayout(self.widget_statistiche)

        scroll_stats.setWidget(self.widget_statistiche)
        layout_statistiche.addWidget(scroll_stats)

        # Bottone export statistiche
        self.btn_export_stats = crea_bottone(
            "📋 Esporta le Statistiche (.txt)", C("btn_export_bg"), C("btn_export_hover"),
            tooltip="Salva le statistiche dettagliate in un file di testo",
            altezza_min=45, font_size=14
        )
        self.btn_export_stats.clicked.connect(self._esporta_statistiche_txt)
        layout_statistiche.addWidget(self.btn_export_stats)

        self.tab_widget.addTab(self.tab_statistiche, "📊 Statistiche")

        # --- TOOLTIP sulle linguette delle tab ---
        # ORDINE TAB: Editor(0), Aula(1), Report(2), Storico(3), Statistiche(4)
        self.tab_widget.setTabToolTip(0, "Modifica genere, posizione e vincoli degli studenti")
        self.tab_widget.setTabToolTip(1, "Visualizza la disposizione grafica dei banchi nell'aula")
        self.tab_widget.setTabToolTip(2, "Leggi il report dettagliato dell'assegnazione")
        self.tab_widget.setTabToolTip(3, "Consulta e gestisci lo storico delle assegnazioni passate")
        self.tab_widget.setTabToolTip(4, "Analizza le statistiche sulle coppie e le rotazioni")

        # Cursore "manina" sulle etichette delle tab: coerente con tutti
        # gli altri elementi cliccabili dell'interfaccia (pulsanti, ecc.)
        self.tab_widget.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        # Connetti il segnale: quando l'Editor carica un nuovo file
        # (tramite il suo bottone "📝 Seleziona classe"), resetta
        # i dati del pannello principale per evitare mescolanza tra classi.
        self.editor_studenti.file_cambiato_signal.connect(self._on_editor_file_cambiato)

        # Connetti il segnale: quando l'utente cambia un genere nell'Editor,
        # aggiorna la label "Genere da completare" nel pannello sinistro
        self.editor_studenti.dati_modificati_signal.connect(self._on_editor_dati_modificati)

        # Connetti il segnale: quando l'Editor CHIUDE il file corrente
        # (bottone "Chiudi file"), riporta la label nel pannello sinistro
        # allo stato iniziale "Nessun file caricato"
        self.editor_studenti.file_chiuso_signal.connect(self._on_editor_file_chiuso)

        # Connetti il segnale: quando l'Editor SALVA il file con successo,
        # carica automaticamente i dati nell'algoritmo di assegnazione
        # e abilita il bottone "Assegna i posti!".
        self.editor_studenti.file_salvato_signal.connect(self._on_editor_file_salvato)

        # Imposta il callback pre-caricamento: l'Editor lo chiamerà
        # PRIMA di aprire il QFileDialog per caricare una nuova classe.
        # Se c'è un'assegnazione non salvata, l'utente viene avvisato.
        self.editor_studenti._callback_pre_caricamento = self._verifica_prima_di_caricare

        return self.tab_widget

    def _mostra_istruzioni(self):
        """Delega a moduli/istruzioni.py — guida d'uso completa."""
        mostra_istruzioni(self)

    def _carica_dati_iniziali(self):
        """Carica dati iniziali dalla configurazione salvata."""

        # Carica e applica il tema salvato (scuro o chiaro)
        # Deve avvenire PRIMA di qualsiasi aggiornamento dell'interfaccia
        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        # Aggiorna l'etichetta e lo stile del toggle in base al tema caricato
        if tema_salvato == "chiaro":
            self.btn_toggle_tema.setText("🌚 Tema scuro")
        else:
            self.btn_toggle_tema.setText("☀️ Tema chiaro")
        # Aggiorna il colore del testo (nero su tema chiaro, bianco su tema scuro)
        self.btn_toggle_tema.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_tema_bg")};
                color: {C("btn_tema_txt")};
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_tema_hover")};
            }}
        """)

        # Riapplica lo stylesheet globale col tema appena caricato
        self.setup_stili()

        # Genere misto: NON caricare la preferenza all'avvio.
        # All'avvio nessuna classe è caricata, e i gruppi opzioni
        # sono disabilitati: mostrare il checkbox spuntato sarebbe
        # fuorviante. Il valore viene salvato in config.json per
        # coerenza, ma la scelta è sempre dell'utente al momento
        # dell'assegnazione — non una preferenza persistente.
        self.checkbox_genere_misto.setChecked(False)

        # Aggiorna la label storico con i dati reali già disponibili
        # (lo storico è globale, non dipende dal file classe caricato)
        self._aggiorna_info_storico()

        self._aggiorna_posti_totali()

        # Popola filtro statistiche
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        # Popola la tabella dello Storico con le assegnazioni precedenti.
        # L'utente potrebbe voler consultare o esportare assegnazioni
        # già fatte senza dover prima ricaricare una classe.
        self._aggiorna_tabella_storico()

    def _aggiorna_posti_totali(self):
        """Aggiorna il calcolo dei posti totali."""
        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())
        posti_totali = num_file * posti_per_fila

        self.label_posti_totali.setText(f"  Posti totali: {posti_totali}  ")

        # Controlla compatibilità con studenti caricati
        if self.studenti:
            num_studenti = len(self.studenti)
            if num_studenti > posti_totali:
                # WARNING EVIDENTE: Sfondo rosso lampeggiante + testo grande
                self.label_posti_totali.setStyleSheet(f"""
                    background-color: {C("label_errore_bg")};
                    color: white;
                    font-weight: bold;
                    font-size: 15px;
                    padding: 8px;
                    border: 3px solid {C("label_errore_bordo")};
                    border-radius: 6px;
                """)
                self.label_posti_totali.setText(f"🚨 POSTI INSUFFICIENTI! 🚨\nServono: {num_studenti} | Disponibili: {posti_totali}")

                # Salva stato per controllo successivo
                self.posti_insufficienti = True
            elif num_studenti < posti_totali:
                # Sfondo ocra/ambra per rendere l'informazione ben visibile
                self.label_posti_totali.setStyleSheet(f"""
                    background-color: {C("label_caricato_bg")};
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 6px 8px;
                    border-radius: 5px;
                    border: 1px solid {C("label_caricato_bordo")};
                """)
                posti_liberi = posti_totali - num_studenti
                self.label_posti_totali.setText(
                    f"✅ Posti totali: {posti_totali}\n"
                    f"{posti_liberi} post{'o vuoto' if posti_liberi == 1 else 'i vuoti'} sar{'à tolto' if posti_liberi == 1 else 'anno tolti'}"
                )
                # Reset flag posti insufficienti
                self.posti_insufficienti = False
            else:
                # Sfondo ocra/ambra per rendere l'informazione ben visibile
                self.label_posti_totali.setStyleSheet(f"""
                    background-color: {C("label_caricato_bg")};
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 6px 8px;
                    border-radius: 5px;
                    border: 1px solid {C("label_caricato_bordo")};
                """)
                self.label_posti_totali.setText(f"🎯 Posti totali: {posti_totali} (PERFETTO!)")
                # Reset flag posti insufficienti
                self.posti_insufficienti = False

    def _cambia_num_file(self, delta):
        """
        Cambia il numero di file di banchi.

        Args:
            delta: +1 per aumentare, -1 per diminuire
        """
        valore_attuale = int(self.input_num_file.text())
        nuovo_valore = valore_attuale + delta

        # Limiti: min 1, max 6
        if 1 <= nuovo_valore <= 6:
            self.input_num_file.setText(str(nuovo_valore))
            self._aggiorna_posti_totali()

    def _cambia_posti_fila(self, delta):
        """
        Cambia il numero di posti per fila (solo valori PARI).

        Args:
            delta: +2 per aumentare, -2 per diminuire
        """
        valore_attuale = int(self.input_posti_fila.text())
        nuovo_valore = valore_attuale + delta

        # Limiti: min 2, max 12 (solo pari)
        if 2 <= nuovo_valore <= 12:
            self.input_posti_fila.setText(str(nuovo_valore))
            self._aggiorna_posti_totali()

    def _aggiorna_visibilita_dispari(self):
        """
        Mostra/nasconde controlli per numero dispari.
        Se c'è uno studente FISSO, il trio dipende
        dalla parità dei RIMANENTI (N-1), non di N.
        """
        if hasattr(self, 'group_dispari'):  # Controlla che il gruppo esista
            if self.studenti:
                # Conta quanti studenti hanno posizione FISSO
                num_fissi = sum(1 for s in self.studenti if s.nota_posizione == 'FISSO')
                # I rimanenti (esclusi i FISSO) determinano se serve il trio
                num_rimanenti = len(self.studenti) - num_fissi
                ha_bisogno_trio = (num_rimanenti % 2 == 1)

                if ha_bisogno_trio:
                    self.group_dispari.setVisible(True)
                    if num_fissi > 0:
                        # Con FISSO: specifica che il conteggio è sui rimanenti
                        self.label_info_dispari.setText(
                            f"Con {len(self.studenti)} studenti ({num_fissi} 'FISSO', "
                            f"{num_rimanenti} rimanenti dispari), il banco da 3 sarà posizionato:"
                        )
                    else:
                        # Senza FISSO: messaggio originale
                        self.label_info_dispari.setText(
                            f"Con {len(self.studenti)} studenti, il banco da 3 sarà posizionato:"
                        )
                else:
                    self.group_dispari.setVisible(False)
            else:
                self.group_dispari.setVisible(False)

    def _resetta_tab_aula_report(self):
        """
        Pulisce le tab Aula e Report quando si cambia classe o si chiude
        un file, eliminando i dati dell'assegnazione precedente.

        Viene chiamato da:
        - _on_editor_file_cambiato() → quando l'Editor carica un nuovo file
        - _on_editor_file_chiuso() → quando l'Editor chiude il file corrente
        - _carica_studenti_da_editor() → quando il pannello principale carica nuovi dati

        Effetti:
        - Svuota la griglia visuale dell'aula (tab Aula)
        - Svuota il report testuale (tab Report)
        - Disabilita i bottoni di salvataggio e export
        """
        # --- Pulisci la griglia dell'aula ---
        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # --- Pulisci il report testuale ---
        self.text_report.clear()

        # --- Nasconde il banner-guida nella tab Report ---
        self.label_hint_report.setVisible(False)

        # --- Disabilita i bottoni (nessuna assegnazione attiva) ---
        self.btn_salva_progetto.setEnabled(False)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_report_txt.setEnabled(False)

    def _verifica_prima_di_caricare(self) -> bool:
        """
        Callback chiamato dall'Editor PRIMA di aprire il QFileDialog
        per caricare una nuova classe. Verifica se c'è un'assegnazione
        non salvata e, in quel caso, chiede conferma all'utente.

        Returns:
            True = procedi col caricamento, False = blocca
        """
        if not self.assegnazione_non_salvata:
            return True  # Nessuna assegnazione pendente, procedi

        # C'è un'assegnazione non salvata: chiedi conferma
        dialog = QMessageBox(self)
        dialog.setWindowTitle("⚠️ ASSEGNAZIONE NON SALVATA!")
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText(
            "❗ L'ultima assegnazione NON è stata salvata nello Storico.\n\n"
            "Se carichi una nuova classe adesso, le coppie formate\n"
            "NON verranno considerate nelle rotazioni future.\n\n"
            "Che cosa vuoi fare?\n"
        )

        btn_salva = dialog.addButton(
            "💾 Salva assegnazione", QMessageBox.AcceptRole
        )
        btn_prosegui = dialog.addButton(
            "🚪 Prosegui senza salvare", QMessageBox.DestructiveRole
        )
        btn_annulla = dialog.addButton(
            "↩️ Annulla", QMessageBox.RejectRole
        )

        dialog.setDefaultButton(btn_salva)
        dialog.setEscapeButton(btn_annulla)

        dialog.exec()

        bottone = dialog.clickedButton()

        if bottone == btn_annulla:
            return False  # Blocca il caricamento

        if bottone == btn_salva:
            self.salva_assegnazione()
            # Se dopo il salvataggio il flag è ancora True,
            # l'utente ha annullato → blocca
            if self.assegnazione_non_salvata:
                return False
            return True  # Salvata con successo, procedi

        # "Prosegui senza salvare" → procedi
        return True

    def _on_editor_file_cambiato(self):
        """
        Slot chiamato quando l'Editor carica un nuovo file tramite il suo
        bottone "Seleziona classe".

        Resetta i dati del pannello principale (self.studenti) per evitare
        che restino in memoria gli studenti di una classe precedente
        mentre l'Editor mostra una classe diversa.

        L'utente dovrà salvare nell'Editor per ri-caricare
        i dati nel pannello principale (di sinistra).
        """
        # Resetta gli studenti caricati
        self.studenti = []
        self.file_origine_studenti = None

        # Pulisci Aula e Report (dati "vecchi" dell'assegnazione precedente)
        self._resetta_tab_aula_report()

        # Resetta il nome classe (si ripopolerà dal nuovo file)
        self.input_nome_classe.clear()

        # Disabilita il bottone di assegnazione e i box di configurazione
        # (non ci sono più dati pronti — verranno riabilitati dopo
        # "SALVA e CARICA classe" in _carica_studenti_da_editor)
        self.btn_avvia_assegnazione.setEnabled(False)
        self.group_aula.setEnabled(False)
        self.group_opzioni.setEnabled(False)
        self.group_modalita.setEnabled(False)

        # Ripristina lo schema aula ai default
        self.input_num_file.setText("4")
        self.input_posti_fila.setText("6")
        self._aggiorna_posti_totali()

        # Resetta le opzioni che dipendono dalla classe caricata
        self.checkbox_genere_misto.setChecked(False)

        # Nasconde i controlli trio (self.studenti è vuoto → niente trio)
        self._aggiorna_visibilita_dispari()

        # Aggiorna la label in base allo stato del file appena caricato nell'Editor:
        # - Se ci sono generi mancanti → avvisa che servono modifiche
        # - Se il file è già completo → invita a salvare nell'Editor
        if (self.editor_studenti.ha_studenti_caricati() and
                not self.editor_studenti.tutti_generi_impostati()):
            # Ci sono generi da completare: indica chiaramente che servono modifiche
            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"⚠️ NUOVA CLASSE CARICATA NELL'EDITOR!\n\n"
                f"➡ MODIFICHE NECESSARIE: {len(mancanti)} gener{'e' if len(mancanti) == 1 else 'i'} da impostare)"
            )
        else:
            # File già completo: invita a salvare per abilitare l'assegnazione
            self.label_studenti_caricati.setText(
                "⚠️ NUOVA CLASSE CARICATA NELL'EDITOR!\n\n"
                "➡ Clicca '💾 SALVA e CARICA classe' per abilitare l'assegnazione."
            )
        self.label_studenti_caricati.setStyleSheet(f"""
            background-color: {C("label_attenzione_bg")};
            color: {C("label_attenzione_txt")};
            font-weight: bold;
            font-size: 13px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid {C("label_attenzione_bordo")};
        """)

        # Resetta il flag di assegnazione non salvata
        self.assegnazione_non_salvata = False

        print("🔄 L'Editor ha caricato un nuovo file → dati pannello resettati")

        # Mostra la tab Editor per dare conferma visiva del caricamento
        self.tab_widget.setCurrentIndex(0)  # Tab "✏️ Editor studenti" (primo tab)

    def _on_editor_dati_modificati(self):
        """
        Slot chiamato quando l'utente modifica qualsiasi dato nell'Editor
        (posizione, vincoli, genere) o quando lo stato cambia (es: rimozione
        di un vincolo incompleto). Rivaluta lo stato corrente e aggiorna
        la label nel pannello sinistro di conseguenza:
        - ARANCIONE se ci sono modifiche non salvate o vincoli incompleti
        - VERDE se lo stato è tornato pulito (es: vincolo pendente rimosso)

        NON aggiorna la label se ci sono generi incompleti: in quel caso
        lascia che _on_editor_genere_cambiato() gestisca il messaggio
        più specifico ("genere da completare").
        """
        if not self.editor_studenti.ha_studenti_caricati():
            return

        # Se ci sono generi incompleti, lascia fare al segnale specifico
        # genere_cambiato_signal → _on_editor_genere_cambiato()
        if not self.editor_studenti.tutti_generi_impostati():
            return

        # Verifica lo stato attuale: ci sono ancora problemi pendenti?
        ha_vincoli_incompleti = bool(self.editor_studenti.get_vincoli_incompleti())
        ha_modifiche_non_salvate = self.editor_studenti._modifiche_non_salvate

        if ha_vincoli_incompleti or ha_modifiche_non_salvate:
            # Stato NON pulito: label arancione "modifiche da salvare"
            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"⚠️ '{nome_file}' modificato nell'Editor!\n\n"
                f"➡ Clicca '💾 SALVA e CARICA classe' per aggiornare."
            )
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: {C("label_attenzione_bg")};
                color: {C("label_attenzione_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_attenzione_bordo")};
            """)
        else:
            # Stato pulito: label verde "pronto per l'assegnazione"
            # (il vincolo incompleto è stato rimosso, nessun'altra modifica)
            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"✅ File '{nome_file}.txt' salvato e caricato\n\n"
                f"➡ Pronto per l'ASSEGNAZIONE!"
            )
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: {C("label_successo_bg")};
                color: {C("label_successo_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_successo_bordo")};
            """)

    def _on_editor_genere_cambiato(self):
        """
        Slot chiamato quando l'utente cambia il genere di uno studente
        nell'Editor. Aggiorna la label nel pannello sinistro in tempo reale.

        Se tutti i generi sono ora impostati, la label diventa verde
        e invita l'utente a salvare per procedere.
        Se restano generi da completare, la label resta arancione.
        """
        if not self.editor_studenti.ha_studenti_caricati():
            return  # Editor vuoto, niente da fare

        if self.editor_studenti.tutti_generi_impostati():
            # Tutti i generi impostati → pronto per il salvataggio
            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"✅ '{nome_file}' pronto!\n\n"
                f"➡ Clicca '💾 SALVA e CARICA classe' per procedere."
            )
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
            # Restano generi da completare → conta quanti mancano
            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"⏳ Genere da completare ({len(mancanti)} rimast{'o' if len(mancanti) == 1 else 'i'})"
            )
            self.label_studenti_caricati.setStyleSheet(f"""
                background-color: {C("label_attenzione_bg")};
                color: {C("label_attenzione_txt")};
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid {C("label_attenzione_bordo")};
            """)

    def _on_editor_file_chiuso(self):
        """
        Slot chiamato quando l'Editor chiude il file corrente
        (bottone "Chiudi file" o chiusura confermata).

        Riporta la label del pannello sinistro allo stato iniziale
        e resetta i dati caricati, così non resta nessun messaggio
        ambiguo che suggerisca che un file sia ancora in memoria.
        """
        # Resetta gli studenti caricati nel pannello principale
        self.studenti = []
        self.file_origine_studenti = None

        # Pulisci Aula e Report (dati vecchi dell'assegnazione precedente)
        self._resetta_tab_aula_report()

        # Resetta il nome classe
        self.input_nome_classe.clear()

        # Disabilita il bottone di assegnazione e i box di configurazione
        self.btn_avvia_assegnazione.setEnabled(False)
        self.group_aula.setEnabled(False)
        self.group_opzioni.setEnabled(False)
        self.group_modalita.setEnabled(False)

        # Riporta la label allo stato iniziale (identico a quando si apre il programma)
        self.label_studenti_caricati.setText(
            "NESSUN FILE CARICATO.\n\n"
            "➡ Vai in '✏️ Editor studenti' e clicca su '📝 Seleziona classe'.\n"
        )
        self.label_studenti_caricati.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 13px; font-style: italic;"
        )

        # Ripristina lo schema aula ai default (nessuna classe caricata → default)
        self.input_num_file.setText("4")
        self.input_posti_fila.setText("6")
        self._aggiorna_posti_totali()

        # Resetta le opzioni che dipendono dalla classe caricata
        self.checkbox_genere_misto.setChecked(False)

        # Nasconde i controlli trio (self.studenti è vuoto → niente trio)
        self._aggiorna_visibilita_dispari()

        # Resetta il flag di assegnazione non salvata
        self.assegnazione_non_salvata = False

    def _on_editor_file_salvato(self, percorso_file: str):
        """
        Slot chiamato quando l'Editor salva con successo il file .txt
        (bottone "💾 SALVA e CARICA classe").

        Args:
            percorso_file: Percorso completo del file .txt salvato dall'Editor
        """
        # Carica i dati dall'Editor e crea gli oggetti Student
        # per l'algoritmo di assegnazione
        self._carica_studenti_da_editor(percorso_file)

        # Aggiorna la label di stato per comunicare all'utente
        # che la classe è pronta per l'assegnazione
        nome_file = os.path.basename(percorso_file)
        self.label_studenti_caricati.setText(
            f"✅ File '{nome_file}' salvato e caricato\n\n"
            f"➡ Pronto per l'ASSEGNAZIONE!"
        )
        self.label_studenti_caricati.setStyleSheet(f"""
            background-color: {C("label_successo_bg")};
            color: {C("label_successo_txt")};
            font-weight: bold;
            font-size: 13px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid {C("label_successo_bordo")};
        """)

        # Messaggio nella label_status in basso (scompare dopo 10 secondi)
        self.label_status.setText("✅ Classe pronta per l'assegnazione!")
        self.label_status.setStyleSheet(f"color: {C('testo_stato_ok')}; font-weight: bold;")
        QTimer.singleShot(10000, lambda: (
            self.label_status.setText("")
            if not self.timer_messaggi.isActive()
            else None
        ))

    def _carica_studenti_da_editor(self, file_path: str):
        """
        Legge i dati dall'Editor e crea gli oggetti Student.
        Chiamato quando l'Editor ha completato il caricamento senza problemi.

        Questo metodo invece di leggere dal file .txt, prende i dati già validati
        dall'Editor, garantendo coerenza e completezza.

        Args:
            file_path: Percorso del file (per salvare il nome e auto-rilevamento)
        """
        # Pulisci Aula e Report della classe precedente.
        # La nuova classe richiederà una nuova assegnazione,
        # quindi i risultati vecchi non hanno più senso.
        self._resetta_tab_aula_report()
        # Recupera i dati strutturati da TUTTE le schede dell'Editor
        dati_studenti = self.editor_studenti.get_dati_tutti_studenti()

        if not dati_studenti:
            self._mostra_errore("File vuoto", "Il file selezionato non contiene studenti validi.")
            return

        # === Conversione dati Editor → oggetti Student ===
        # L'Editor restituisce dict con chiavi:
        # 'cognome, nome, sesso, posizione, incompatibilità, affinità'
        # L'algoritmo ha bisogno di oggetti Student con i medesimi attributi

        # NOTA: L'Editor usa "Cognome Nome" come chiave nei vincoli,
        # e anche Student usa "Cognome Nome" come chiave interna,
        # per evitare ambiguità con eventuali studenti omonimi.

        studenti = []
        for dati in dati_studenti:
            # Crea lo studente base
            studente = Student(
                cognome=dati["cognome"],
                nome=dati["nome"],
                sesso=dati["sesso"],
                nota_posizione=dati["posizione"]
            )

            # Aggiunge le incompatibilità
            # Nell'Editor: dict {"Cognome Nome": livello}
            # Nello Student: dict {"Cognome Nome": livello} (nome completo come chiave)
            for nome_completo, livello in dati["incompatibilita"].items():
                # Passa direttamente il nome completo dall'Editor allo Student
                studente.aggiungi_incompatibilita(nome_completo, livello)

            # Aggiunge le affinità (stessa logica)
            for nome_completo, livello in dati["affinita"].items():
                studente.aggiungi_affinita(nome_completo, livello)

            studenti.append(studente)

        # === AUTO-SALVATAGGIO del file corretto ===
        # Se l'Editor ha applicato correzioni (vincoli bidirezionali aggiunti,
        # conversione da formato base a completo), sovrascrive il file originale
        # con la versione corretta. Questo evita che l'utente debba gestire
        # manualmente un file con problemi noti.
        self._auto_salva_file_corretto()

        # === Aggiorna lo stato dell'applicazione ===
        self.studenti = studenti
        self.file_origine_studenti = Path(file_path).name
        num_studenti = len(studenti)

        # Aggiorna interfaccia con sfondo ocra per evidenziare l'informazione
        self.label_studenti_caricati.setText(
            f"✅ Caricati {num_studenti} studenti da '{Path(file_path).name}'"
        )
        self.label_studenti_caricati.setStyleSheet(f"""
            background-color: {C("label_caricato_bg")};
            color: {C("label_caricato_txt")};
            font-weight: bold;
            font-size: 13px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid {C("label_caricato_bordo")};
        """)

        # Abilita il bottone di assegnazione e i box di configurazione
        self.btn_avvia_assegnazione.setEnabled(True)
        self.group_aula.setEnabled(True)
        self.group_opzioni.setEnabled(True)
        self.group_modalita.setEnabled(True)

        # Aggiorna visibilità controlli numero dispari
        self._aggiorna_visibilita_dispari()

        # Estrae il nome file per auto-rilevamento classe
        nome_file = Path(file_path).stem.replace("_", " ").title()

        # Aggiorna nome classe dal file (il campo è read-only)
        self.input_nome_classe.setText(nome_file)

        # AUTO-RILEVAMENTO: Se classe già elaborata, attiva rotazione
        # e RIPRISTINA LO SCHEMA AULA dallo storico (num_file, posti_per_fila).
        # Deve avvenire PRIMA di _aggiorna_posti_totali, altrimenti il calcolo
        # userebbe lo schema default 4x6 invece di quello salvato.
        self._controlla_classe_gia_elaborata(nome_file)

        # Aggiorna calcolo posti (ora con lo schema corretto, ripristinato sopra)
        self._aggiorna_posti_totali()

        # Aggiorna la label storico ORA che sappiamo quale classe è caricata.
        # Non viene fatto all'avvio (nessun file ancora caricato),
        # ma solo qui, dopo che l'utente ha selezionato il file .txt.
        self._aggiorna_info_storico()

        # Mostra la tab Editor per dare all'utente conferma visiva
        # che la classe è stata caricata.
        self.tab_widget.setCurrentIndex(0)  # Tab "✏️ Editor studenti" (primo tab)

    def _auto_salva_file_corretto(self):
        """
        Salva automaticamente il file .txt corretto dall'Editor.

        Viene chiamato dopo che l'Editor ha applicato correzioni:
        - Vincoli bidirezionali aggiunti
        - Conversione da formato base a formato completo a 6 campi
        - Genere/posizione completati dall'utente

        Il file originale viene sovrascritto con la versione corretta.
        Se il salvataggio fallisce (es: file read-only), mostra un avviso
        ma NON blocca il flusso (i dati in memoria sono già corretti).
        """
        # Verifica se ci sono correzioni da salvare
        if not self.editor_studenti._correzioni_applicate:
            # Nessuna correzione: il file su disco era già perfetto.
            # Resetta il flag "modifiche non salvate" perché non c'è nulla
            # da salvare → evita il popup alla chiusura del programma.
            self.editor_studenti._modifiche_non_salvate = False
            return

        # Recupera il percorso del file originale
        percorso = self.editor_studenti._percorso_file_caricato

        if not percorso:
            # Nessun percorso (non dovrebbe mai succedere), skip silenzioso
            print("⚠️ Auto-save: nessun percorso file disponibile")
            return

        try:
            # Genera il contenuto corretto dall'Editor (formato completo a 6 campi)
            contenuto_corretto = self.editor_studenti._genera_txt()

            # Sovrascrive il file originale
            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(contenuto_corretto)

            # Segna che le modifiche sono state salvate
            self.editor_studenti._modifiche_non_salvate = False
            self.editor_studenti._correzioni_applicate = False

            # === POPUP VISIBILE per informare l'utente ===
            nome_file = Path(percorso).name
            QMessageBox.information(
                self,
                "💾 FILE SALVATO E PRONTO ALL'USO",
                f"Il file è stato automaticamente salvato e caricato:\n\n"
                f"📄 {nome_file}\n"
                f"📁 {percorso}\n\n"
                f"👍 ORA L'INTERA LISTA DEGLI STUDENTI\n"
                f"È CARICATA E PRONTA PER L'ASSEGNAZIONE!"
            )

            print(f"💾 Auto-save: file corretto salvato in '{percorso}'")

        except PermissionError:
            # File read-only o protetto: avvisa ma non bloccare
            QMessageBox.warning(
                self,
                "⚠️ Salvataggio automatico non riuscito",
                f"Il file non può essere sovrascritto (potrebbe essere protetto):\n"
                f"{percorso}\n\n"
                f"Le correzioni sono comunque attive per l'assegnazione corrente.\n"
                f"💡 Puoi salvare manualmente dalla tab 'Editor studenti' con\n"
                f"'💾 Preview file classe (.txt)'."
            )

        except Exception as e:
            # Altro errore: avvisa ma non bloccare
            print(f"⚠️ Auto-save fallito: {e}")
            QMessageBox.warning(
                self,
                "⚠️ Salvataggio automatico non riuscito",
                f"Errore nel salvataggio automatico:\n{e}\n\n"
                f"Le correzioni sono comunque attive per l'assegnazione corrente."
            )

    def avvia_assegnazione(self):
        """Avvia il processo di assegnazione automatica."""

        if not self.studenti:
            self._mostra_errore("Nessun dato", "Carica prima un file con gli studenti.")
            return

        # CONTROLLO VINCOLI INCOMPLETI NELL'EDITOR:
        # Controllato PRIMA delle modifiche non salvate.
        if hasattr(self, 'editor_studenti') and self.editor_studenti.ha_studenti_caricati():
            vincoli_incompleti = self.editor_studenti.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                QMessageBox.warning(
                    self,
                    "⚠️ Vincoli INCOMPLETI nell'Editor",
                    f"I seguenti vincoli non hanno il livello impostato:\n\n"
                    f"{elenco}\n\n"
                    f"Questi vincoli verrebbero IGNORATI dall'assegnazione.\n\n"
                    f"💡 Torna nell'Editor e, per ogni vincolo:\n"
                    f"  • Seleziona il livello di intensità\n"
                    f"  • Oppure rimuovilo con il pulsante 'Rimuovi'\n\n"
                    f"Poi clicca '💾 SALVA e CARICA classe' prima di assegnare.\n",
                    QMessageBox.Ok
                )
                self.tab_widget.setCurrentIndex(0)  # Porta alla tab Editor
                return

        # CONTROLLO MODIFICHE EDITOR NON SALVATE:
        # Se l'utente ha modificato vincoli/genere/posizione nell'Editor
        # ma non ha ancora cliccato "SALVA e CARICA classe",
        # l'assegnazione userebbe i dati VECCHI (quelli dell'ultimo salvataggio).
        # Avvisiamo l'utente e suggeriamo di salvare prima.
        if hasattr(self, 'editor_studenti') and self.editor_studenti._modifiche_non_salvate:
            risposta = QMessageBox.warning(
                self,
                "⚠️ MODIFICHE NON SALVATE NELL'EDITOR",
                "❗ Hai modificato dei vincoli nell'Editor ma NON hai ancora salvato.\n\n"
                "L'assegnazione utilizzerebbe i dati dell'ULTIMO salvataggio,\n"
                "ignorando le modifiche recenti.\n\n"
                "💡 Torna nell'Editor e clicca '💾 SALVA e CARICA classe'\n"
                "per aggiornare i dati prima di procedere.",
                QMessageBox.Ok
            )
            # Porta l'utente nell'Editor per salvare
            self.tab_widget.setCurrentIndex(0)  # Tab Editor (primo tab)
            return

        # CONTROLLO POSTI INSUFFICIENTI: Blocca assegnazione con popup
        if hasattr(self, 'posti_insufficienti') and self.posti_insufficienti:
            risposta = QMessageBox.critical(
                self,
                "🚨 POSTI INSUFFICIENTI",
                f"🚫 IMPOSSIBILE PROCEDERE!\n\n"
                f"👥 Studenti da sistemare: {len(self.studenti)}\n"
                f"🪑 Posti disponibili: {int(self.input_num_file.text()) * int(self.input_posti_fila.text())}\n\n"
                f"💡 SOLUZIONI:\n"
                f"• Aumenta il numero di file di banchi\n"
                f"• Aumenta i posti per fila",
                QMessageBox.Ok
            )
            return

        # CONTROLLO ASSEGNAZIONE NON SALVATA: Avvisa l'utente prima di sovrascrivere
        if self.assegnazione_non_salvata:
            dialog_avvia = QMessageBox(self)
            dialog_avvia.setWindowTitle("⚠️ ASSEGNAZIONE NON SALVATA!")
            dialog_avvia.setIcon(QMessageBox.Warning)
            dialog_avvia.setText(
                "❗ L'assegnazione corrente NON è stata salvata nello storico.\n\n"
                "Se procedi con una nuova elaborazione, le coppie formate\n"
                "NON verranno considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?\n"
            )

            btn_salva_avvia = dialog_avvia.addButton(
                "💾 Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_prosegui_avvia = dialog_avvia.addButton(
                "🔄 Prosegui senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_avvia = dialog_avvia.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            dialog_avvia.setDefaultButton(btn_salva_avvia)
            # X della finestra e tasto Esc = Annulla
            dialog_avvia.setEscapeButton(btn_annulla_avvia)

            dialog_avvia.exec()

            bottone_avvia = dialog_avvia.clickedButton()

            if bottone_avvia == btn_salva_avvia:
                # L'utente vuole salvare prima → apri dialogo salvataggio
                self.salva_assegnazione()
                # Dopo il salvataggio (riuscito o annullato) torniamo al controllo dell'utente.
                # Se vuole lanciare una nuova elaborazione, cliccherà di nuovo "Avvia".
                return

            elif bottone_avvia == btn_annulla_avvia:
                # Annulla → non fare nulla
                return

            # Se "Prosegui senza salvare" → prosegui con la nuova elaborazione

        # Salva nome classe in configurazione
        self.config_app.config_data["classe_info"]["nome_classe"] = self.input_nome_classe.text()

        # Aggiorna configurazione aula
        self.config_app.config_data["configurazione_aula"]["num_file"] = int(self.input_num_file.text())
        self.config_app.config_data["configurazione_aula"]["posti_per_fila"] = int(self.input_posti_fila.text())

        # Salva opzioni vincoli
        self.config_app.config_data["opzioni_vincoli"]["genere_misto_obbligatorio"] = self.checkbox_genere_misto.isChecked()

        # Crea configurazione aula
        num_studenti = len(self.studenti)
        self.configurazione_aula = ConfigurazioneAula(f"Aula {self.input_nome_classe.text()}")

        # Usa configurazione personalizzata
        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())

        # === INDIVIDUA STUDENTE FISSO ===
        # Cerca nella lista studenti chi ha nota_posizione="FISSO"
        studente_fisso = None
        num_fissi = 0
        for s in self.studenti:
            if s.nota_posizione == 'FISSO':
                num_fissi += 1
                studente_fisso = s

        # Controllo: al massimo 1 studente FISSO
        if num_fissi > 1:
            self._mostra_errore(
                "ERRORE CONFIGURAZIONE!",
                f"⚠️ Trovati {num_fissi} studenti con posizione 'FISSO'.\n\n"
                f"Al massimo 1 studente può avere posizione FISSO.\n"
                f"❗ CORREGGI eliminado le posizioni 'FISSO' in eccesso!"
            )
            return

        ha_fisso = (studente_fisso is not None)
        if ha_fisso:
            print(f"📌 Studente FISSO individuato: {studente_fisso.get_nome_completo()}")

        # === LOGICA TRIO ===
        # Se c'è un FISSO, il trio dipende dalla parità dei RIMANENTI (N-1)
        num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti

        # Determina posizione trio dai radio button
        # 3 opzioni: prima, ultima, centro
        posizione_trio = None
        modalita_trio = 'centro'  # Default coerente con radio button UI

        if num_rimanenti % 2 == 1:  # Trio necessario sui rimanenti
            if self.radio_trio_prima.isChecked():
                posizione_trio = "prima"
                modalita_trio = "prima"
            elif self.radio_trio_ultima.isChecked():
                posizione_trio = "ultima"
                modalita_trio = "ultima"
            elif self.radio_trio_centro.isChecked():
                posizione_trio = "centro"
                modalita_trio = "centro"

        # === CREA LAYOUT AULA ===
        # Passa ha_fisso per attivare il layout con blocco sinistro appropriato
        self.configurazione_aula.crea_layout_standard(
            num_studenti, num_file, posti_per_fila, posizione_trio, ha_fisso=ha_fisso
        )

        # Verifica compatibilità
        if num_studenti > self.configurazione_aula.posti_disponibili:
            self._mostra_errore(
                "Configurazione NON valida",
                f"⚠️ NON CI SONO ABBASTANZA POSTI!\n"
                f"Studenti: {num_studenti}\n"
                f"Posti disponibili: {self.configurazione_aula.posti_disponibili}\n\n"
                f"Aumenta il numero di file o posti per fila."
            )
            return

        # Disabilita controlli durante elaborazione
        self._imposta_modalita_elaborazione(True)

        # Avvia timer messaggi rotativi (cambia messaggio ogni 2 secondi)
        self.indice_messaggio = 0  # Reset indice
        self.timer_messaggi.start(2000)  # 2000 ms = 2 secondi

        # Avvia thread di elaborazione
        self.worker_thread = WorkerThread(
            self.studenti,
            self.configurazione_aula,
            self.config_app,
            modalita_trio,
            self.checkbox_genere_misto.isChecked(),
            studente_fisso  # Passa lo studente FISSO (o None)
        )

        self.worker_thread.status_updated.connect(self.label_status.setText)
        self.worker_thread.completed.connect(self._elaborazione_completata)
        self.worker_thread.error_occurred.connect(self._elaborazione_fallita)

        self.worker_thread.start()

    def _imposta_modalita_elaborazione(self, in_elaborazione: bool):
        """Imposta l'interfaccia in modalità elaborazione o normale."""

        self.btn_avvia_assegnazione.setEnabled(not in_elaborazione)

        if in_elaborazione:
            self.label_status.setText("🔄 Elaborazione in corso...")
        else:
            self.label_status.setText("")

    def _elaborazione_completata(self, assegnatore: AssegnatorePosti):
        """Chiamata quando l'elaborazione è completata con successo."""

        self.ultimo_assegnatore = assegnatore

        # Segna che c'è un'assegnazione non ancora salvata nello storico
        self.assegnazione_non_salvata = True

        # Ferma timer messaggi rotativi
        self.timer_messaggi.stop()

        # Ripristina interfaccia
        self._imposta_modalita_elaborazione(False)

        # Mostra risultati
        self._visualizza_risultati(assegnatore)

        # Abilita il salvataggio: l'utente deve prima salvare
        # prima di poter esportare (garantisce naming coerente)
        self.btn_salva_progetto.setEnabled(True)

        # I bottoni export rimangono disabilitati finché non si salva.
        # I tooltip spiegano il motivo all'utente.
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "SALVA prima l'assegnazione nello storico per abilitare l'export."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "SALVA prima l'assegnazione nello storico per abilitare l'export."
        )

        # Prepara messaggio con trio se presente
        messaggio_trio = ""
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            messaggio_trio = f"<br>• Trio formato: 1 ({len(assegnatore.trio_identificato)} studenti)"

        # Messaggio di successo con coppie riutilizzate evidenziate in giallo/ocra
        num_riutilizzate = assegnatore.stats['coppie_riutilizzate']

        # Riga coppie riutilizzate: evidenziata in ocra se > 0, normale se 0
        if num_riutilizzate > 0:
            riga_riutilizzate = (
                f'<span style="color: {C("testo_ocra")}; font-weight: bold;">'
                f'⚠️ Coppie riutilizzate: {num_riutilizzate}</span>'
            )
        else:
            riga_riutilizzate = f"• Coppie riutilizzate: {num_riutilizzate}"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("ASSEGNAZIONE COMPLETATA")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setTextFormat(Qt.RichText)  # Abilita HTML nel testo

        # Costruisce le righe delle statistiche
        # Le categorie corrispondono 1:1 alle etichette che l'utente
        # vede nel report dettagliato di ogni coppia (OTTIMA, BUONA, ecc.)
        righe_stats = []
        righe_stats.append(f"• Coppie totali: {len(assegnatore.coppie_formate)}")
        righe_stats.append(f"• Coppie ottimali: {assegnatore.stats['coppie_ottimali']}")
        righe_stats.append(f"• Coppie buone: {assegnatore.stats['coppie_buone']}")
        righe_stats.append(f"• Coppie accettabili: {assegnatore.stats['coppie_accettabili']}")
        # Mostra problematiche e critiche solo se presenti (evita rumore visivo)
        if assegnatore.stats['coppie_problematiche'] > 0:
            righe_stats.append(f"• Coppie problematiche: {assegnatore.stats['coppie_problematiche']}")
        if assegnatore.stats['coppie_critiche'] > 0:
            righe_stats.append(f"• Coppie critiche: {assegnatore.stats['coppie_critiche']}")

        msg_box.setText(
            f"✅ ASSEGNAZIONE COMPLETATA CON SUCCESSO!<br><br>"
            f"📊 <b>Statistiche:</b><br>"
            f"{'<br>'.join(righe_stats)}<br>"
            f"{riga_riutilizzate}{messaggio_trio}"
        )
        msg_box.exec()

    def _elaborazione_fallita(self, messaggio_errore: str, report: dict = None):
        """
        Chiamata quando l'elaborazione fallisce.
        Se l'algoritmo ha prodotto un report diagnostico strutturato,
        mostra un popup dettagliato con analisi e suggerimenti.
        Altrimenti mostra il messaggio generico.

        Args:
            messaggio_errore: Testo breve dell'errore
            report: Dizionario diagnostico da algoritmo.py (o None)
        """
        # Ferma timer messaggi rotativi
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)

        if report:
            # Report disponibile → popup dettagliato con diagnostica
            self._mostra_popup_fallimento_dettagliato(report)
        else:
            # Nessun report (errore imprevisto) → popup generico
            self._mostra_errore("Errore Assegnazione", messaggio_errore)

    def _mostra_popup_fallimento_dettagliato(self, report: dict):
        """
        Mostra un QMessageBox ricco con analisi dettagliata del fallimento.
        Il testo principale è un sommario HTML; il bottone "Mostra dettagli"
        espande un'area con l'analisi completa in testo semplice.

        Args:
            report: Dizionario diagnostico da AssegnatorePosti._costruisci_report_diagnostico()
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("ASSEGNAZIONE NON RIUSCITA")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setTextFormat(Qt.RichText)

        # === TESTO PRINCIPALE (HTML): sommario visivo ===
        html_parti = []
        html_parti.append(
            "<b>L'algoritmo non è riuscito a trovare una disposizione valida</b> "
            "dopo aver provato tutti i 4 tentativi progressivi.<br><br>"
        )

        # Incompatibilità assolute
        incomp = report.get("incompatibilita_assolute", [])
        if incomp:
            html_parti.append(
                f"🚫 <b>Incompatibilità ASSOLUTE (livello 3):</b> {len(incomp)}<br>"
            )
            # Mostra le prime 4 nel sommario
            for coppia in incomp[:4]:
                html_parti.append(f"&nbsp;&nbsp;&nbsp;&nbsp;• {coppia}<br>")
            if len(incomp) > 4:
                html_parti.append(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;<i>... e altre {len(incomp) - 4}</i><br>"
                )
            html_parti.append("<br>")

        # Studenti prima fila
        prima_fila = report.get("studenti_prima_fila", [])
        if len(prima_fila) > 2:
            html_parti.append(
                f"⬆️ <b>Studenti PRIMA fila:</b> {len(prima_fila)} "
                f"(potrebbero essere troppi)<br><br>"
            )

        # Genere misto sbilanciato
        gm = report.get("genere_misto")
        if gm and gm.get("sbilanciamento"):
            html_parti.append(
                f"⚖️ <b>Sbilanciamento genere:</b> "
                f"{gm['maschi']} maschi, {gm['femmine']} femmine "
                f"(flag «Genere misto» attivo)<br><br>"
            )

        # Blacklist
        bl = report.get("blacklist", {})
        if bl.get("coppie", 0) > 5:
            html_parti.append(
                f"📋 <b>Blacklist:</b> {bl['coppie']} coppie già usate "
                f"in precedenti assegnazioni<br><br>"
            )

        # Suggerimenti
        suggerimenti = report.get("suggerimenti", [])
        if suggerimenti:
            html_parti.append("<b>💡 Suggerimenti per risolvere:</b><br>")
            for i, sugg in enumerate(suggerimenti, 1):
                html_parti.append(f"&nbsp;&nbsp;{i}. {sugg}<br>")

        msg_box.setText("".join(html_parti))

        # === TESTO DETTAGLIATO (plain text): analisi completa ===
        # Visibile cliccando "Mostra dettagli..." nel QMessageBox
        dettagli_parti = []
        dettagli_parti.append("=" * 50)
        dettagli_parti.append("REPORT DIAGNOSTICO COMPLETO")
        dettagli_parti.append("=" * 50)

        # Sezione incompatibilità
        dettagli_parti.append("")
        dettagli_parti.append("INCOMPATIBILITÀ ASSOLUTE (livello 3):")
        if incomp:
            for coppia in incomp:
                dettagli_parti.append(f"  • {coppia}")
        else:
            dettagli_parti.append("  Nessuna")

        # Sezione prima fila
        dettagli_parti.append("")
        dettagli_parti.append("STUDENTI CHE RICHIEDONO PRIMA FILA:")
        if prima_fila:
            for nome in prima_fila:
                dettagli_parti.append(f"  • {nome}")
        else:
            dettagli_parti.append("  Nessuno")

        # Sezione genere misto
        if gm:
            dettagli_parti.append("")
            dettagli_parti.append("GENERE MISTO:")
            dettagli_parti.append("  Flag attivo: Sì")
            dettagli_parti.append(f"  Maschi: {gm['maschi']}, Femmine: {gm['femmine']}")
            if gm["sbilanciamento"]:
                dettagli_parti.append("  ⚠ Sbilanciamento rilevato")

        # Sezione blacklist
        dettagli_parti.append("")
        dettagli_parti.append("BLACKLIST (storico rotazioni):")
        dettagli_parti.append(f"  Coppie in blacklist: {bl.get('coppie', 0)}")
        dettagli_parti.append(f"  Trii in blacklist: {bl.get('trii', 0)}")
        piu_usate = bl.get("piu_usate", [])
        if piu_usate:
            dettagli_parti.append("  Coppie più riutilizzate:")
            for cu in piu_usate:
                dettagli_parti.append(f"    - {cu}")

        # Sezione suggerimenti
        dettagli_parti.append("")
        dettagli_parti.append("SUGGERIMENTI:")
        for i, sugg in enumerate(suggerimenti, 1):
            dettagli_parti.append(f"  {i}. {sugg}")

        dettagli_parti.append("")
        dettagli_parti.append("=" * 50)

        msg_box.setDetailedText("\n".join(dettagli_parti))

        msg_box.exec()

    def _visualizza_risultati(self, assegnatore: AssegnatorePosti):
        """Visualizza i risultati dell'assegnazione nell'interfaccia."""

        # Aggiorna visualizzazione aula
        self._aggiorna_visualizzazione_aula(assegnatore.configurazione_aula)

        # Aggiorna report testuale
        self._aggiorna_report_testuale(assegnatore)

        # Mostra il banner-guida nella tab Report
        self.label_hint_report.setVisible(True)

        # Seleziona tab Aula per mostrare risultato (Aula è tab 1, Editor è tab 0)
        self.tab_widget.setCurrentIndex(1)

    def _aggiorna_visualizzazione_aula(self, configurazione_aula: ConfigurazioneAula):
        """Aggiorna la griglia visuale dell'aula."""

        # Pulisce layout esistente
        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Ricrea griglia aula: arredi (LIM, CAT, LAV) in basso,
        # ultima fila di banchi in alto (visione "dalla cattedra")
        # Salta le righe completamente vuote (tipo 'corridoio' ovunque)
        # per evitare "buchi" visivi causati da:
        #   - la riga spaziatore (riga 1) tra arredi e banchi
        #   - file di banchi rimaste vuote dopo rimuovi_banchi_vuoti()
        griglia_invertita = list(reversed(configurazione_aula.griglia))
        riga_display = 0  # Contatore separato per le righe effettive nel QGridLayout
        for riga in griglia_invertita:
            # Verifica se la riga ha almeno un elemento visibile
            # (banco occupato/vuoto, cattedra, LIM, lavagna — NON solo corridoio)
            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                continue  # Salta righe completamente vuote

            for col_idx, posto in enumerate(riga):
                # --- MERGE VISIVO ARREDI (come nell'Excel) ---
                # Gli arredi (LIM, Cattedra, Lavagna) nella struttura dati sono
                # 2 oggetti PostoAula consecutivi. In UI li renderizziamo come
                # una sola cella larga 2 colonne con testo leggibile.
                # Logica di rilevamento: è "prima cella" della coppia se la cella
                # precedente nella riga NON è dello stesso tipo.
                if posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:
                        # Prima cella della coppia → widget merged largo 2 colonne
                        widget_posto = self.crea_widget_posto(posto, merged=True)
                        self.layout_griglia_aula.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)  # colspan=2
                    # else: seconda cella della coppia → non aggiungiamo nulla,
                    # il colspan=2 della prima cella copre questo spazio
                else:
                    # Banchi e corridoi: rendering normale (1 widget per cella)
                    widget_posto = self.crea_widget_posto(posto)
                    self.layout_griglia_aula.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1  # Incrementa solo per righe effettivamente renderizzate

    def crea_widget_posto(self, posto, merged=False) -> QWidget:
        """
        Crea un widget per rappresentare un singolo posto nell'aula.
        Gestisce identificatori univoci e mostra nomi completi.

        Parametri:
            posto:   oggetto PostoAula con tipo e occupante
            merged:  se True, l'arredo viene reso come cella unica larga 2 colonne
                     con testo "LIM"/"CATTEDRA"/"LAVAGNA" (come nell'Excel).
                     Usato dai loop di rendering per le coppie di arredi.
        """

        widget = QLabel()
        # Se merged, larghezza doppia (2 colonne); altrimenti larghezza standard
        larghezza_min = 250 if merged else 120
        widget.setMinimumSize(larghezza_min, 60)
        widget.setAlignment(Qt.AlignCenter)
        # Stile predefinito (verrà sovrascritto dai rami specifici sotto)
        widget.setStyleSheet(f"border: 1px solid {C('banco_libero_bordo')}; margin: 1px;")

        if posto.tipo == 'banco':
            if posto.occupato_da:
                # Banco occupato - usa nome completo
                nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                widget.setText(nome_completo)
                widget.setWordWrap(True)  # Permette a capo per nomi lunghi
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
                # Banco libero — colori dal tema per adattarsi a scuro/chiaro
                widget.setText("🪑")
                widget.setStyleSheet(f"""
                    border: 2px dashed {C("banco_libero_bordo")};
                    background-color: {C("banco_libero_sf")};
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip("Posto libero")

        elif posto.tipo == 'cattedra':
            # Cattedra — colori dal tema per adattarsi a scuro/chiaro
            # Se merged: testo "CATTEDRA" leggibile (come nell'Excel)
            # Se non merged: emoji (per eventuale uso da terminale)
            widget.setText("CATTEDRA" if merged else "🏫")
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
            # LIM — colori dal tema per adattarsi a scuro/chiaro
            # Se merged: testo "LIM" leggibile (come nell'Excel)
            widget.setText("LIM" if merged else "📺")
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
            # Lavagna — colori dal tema per adattarsi a scuro/chiaro
            # Se merged: testo "LAVAGNA" leggibile (come nell'Excel)
            widget.setText("LAVAGNA" if merged else "⬛")
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

        else:  # corridoio
            widget.setText("")
            widget.setStyleSheet("""
                border: none;
                background-color: transparent;
                margin: 1px;
            """)

        return widget

    def salva_assegnazione(self):
        """Salva l'assegnazione corrente nello Storico."""

        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        # Dialog per nome assegnazione
        nome_assegnazione, ok = self._chiedi_nome_assegnazione()

        if ok and nome_assegnazione:

            # Salva nello storico (coppie + trio se presente)
            trio_presente = getattr(self.ultimo_assegnatore, 'trio_identificato', None)
            # Recupera dati FISSO dall'assegnatore (None se non presente)
            studente_fisso = getattr(self.ultimo_assegnatore, 'studente_fisso', None)
            gruppo_adiacente_fisso = getattr(self.ultimo_assegnatore, 'gruppo_adiacente_fisso', None)
            # Nome adiacente diretto (col 1) — fonte di verità per il contatore
            nome_adiacente_fisso = getattr(self.ultimo_assegnatore, 'nome_adiacente_fisso', None)

            # Aggiorna la riga identificativa nel report con il nome assegnazione
            # (deve avvenire PRIMA di catturare report_completo)
            self._aggiorna_riga_identificativa_report(nome_assegnazione)

            # Genera report completo PRIMA di salvare
            report_completo = self.text_report.toPlainText()

            self.config_app.aggiungi_assegnazione_storico(
                nome_assegnazione,
                self.ultimo_assegnatore.coppie_formate,
                trio_presente,
                self.ultimo_assegnatore.configurazione_aula,  # Passa configurazione aula
                self.file_origine_studenti,  # Passa nome file origine
                report_completo,  # Passa report completo
                studente_fisso=studente_fisso,  # studente FISSO (o None)
                gruppo_adiacente_fisso=gruppo_adiacente_fisso,  # coppia adiacente (o None)
                nome_adiacente_fisso=nome_adiacente_fisso,  # nome col 1 (o None)
                genere_misto=self.checkbox_genere_misto.isChecked()  # Preferenza per-classe
            )

            # Aggiorna interfaccia
            self._aggiorna_info_storico()  # Aggiorna contatore e stato
            self._popola_filtro_classi()  # Aggiorna filtro statistiche
            self._aggiorna_statistiche()  # Ricalcola statistiche

            QMessageBox.information(
                self,
                "Assegnazione salvata",
                f"✅ Assegnazione"
                f"✅ '{nome_assegnazione}'"
                f"✅ salvata nello Storico."
            )

            # Segna che l'assegnazione è stata salvata
            self.assegnazione_non_salvata = False

            # Abilita i bottoni export ora che l'assegnazione è salvata.
            # Il nome del file esportato corrisponderà esattamente al nome
            # dell'assegnazione nello Storico.
            self.btn_export_excel.setEnabled(True)
            self.btn_export_excel.setToolTip("Esporta questa assegnazione in formato Excel.")
            self.btn_export_report_txt.setEnabled(True)
            self.btn_export_report_txt.setToolTip("Esporta il Report testuale di questa assegnazione.")

    def _chiedi_nome_assegnazione(self) -> tuple:
        """Chiede il nome per l'assegnazione da salvare."""

        from PySide6.QtWidgets import QInputDialog

        # Recupera il nome classe dal campo (popolato dal file .txt)
        nome_classe = self.input_nome_classe.text() or "Classe"

        # Calcola numero progressivo basato sullo storico esistente.
        # Conta quante assegnazioni esistono già per questa classe
        # usando il campo file_origine (match esatto, affidabile).
        # Il vecchio sistema a parole (fuzzy) era inaffidabile:
        # parole comuni come "classe" matchavano tutte le classi.
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        conteggio = 0
        for assegnazione in storico:
            if assegnazione.get("file_origine") == self.file_origine_studenti:
                conteggio += 1

        # Numero progressivo = assegnazioni esistenti + 1
        numero_progressivo = conteggio + 1
        numero_str = f"{numero_progressivo:02d}"  # Formato "01", "02", ecc.

        # Data corrente in formato compatto
        data_oggi = datetime.now().strftime('%d/%m/%Y')

        # Nome suggerito: es. "Classe 3A - Assegnazione 01 - 07/03/2026"
        nome_suggerito = f"{nome_classe} - Assegnazione {numero_str} - {data_oggi}"

        # Crea un QInputDialog personalizzato per avere il controllo sulla larghezza.
        # Il getText() statico non permette di impostare le dimensioni, e con
        # nomi lunghi il campo risulta troppo stretto per leggere il testo completo.
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Nome assegnazione")
        dialog.setLabelText("Inserisci un nome per questa assegnazione:")
        dialog.setTextValue(nome_suggerito)
        dialog.resize(550, 150)  # Largo per gestire nomi lunghi - CONFIGURABILE

        ok = dialog.exec()
        return dialog.textValue(), ok

    def _cambia_tema(self):
        """
        Alterna tra tema scuro e tema chiaro.
        Aggiorna tutti i widget visibili e salva la preferenza in config.json.
        """
        # Determina il nuovo tema (opposto a quello attuale)
        nuovo_tema = "chiaro" if get_tema() == "scuro" else "scuro"

        # Aggiorna la variabile globale nel modulo tema
        imposta_tema(nuovo_tema)

        # Aggiorna lo stylesheet globale della finestra principale
        self.setup_stili()

        # Aggiorna i widget con stili inline (non coperti dal stylesheet globale)
        self._aggiorna_stili_widget()

        # Aggiorna l'editor studenti (schede, separatori, bottoni)
        if hasattr(self, 'editor_studenti'):
            self.editor_studenti.aggiorna_tema()

        # Aggiorna lo stile del combo filtro Statistiche al nuovo tema.
        # NON ripopola il combo (_popola_filtro_classi) per non perdere
        # la classe attualmente selezionata dall'utente.
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
        # Rigenera le statistiche con i colori del nuovo tema,
        # mantenendo la classe selezionata nel combo filtro.
        self._aggiorna_statistiche()

        # Aggiorna l'etichetta e lo stile del bottone toggle
        # (mostra sempre il tema verso cui si può passare)
        if nuovo_tema == "chiaro":
            self.btn_toggle_tema.setText("🌚 Tema scuro")
        else:
            self.btn_toggle_tema.setText("☀️ Tema chiaro")
        # Aggiorna il colore del testo (nero su tema chiaro, bianco su tema scuro)
        self.btn_toggle_tema.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_tema_bg")};
                color: {C("btn_tema_txt")};
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_tema_hover")};
            }}
        """)

        # Salva la preferenza in config.json
        self.config_app.config_data["tema"] = nuovo_tema
        self.config_app.salva_configurazione()

    def _mostra_crediti(self):
        """Delega a moduli/istruzioni.py — crediti, versione, licenza."""
        mostra_crediti(self, get_base_path())

    def _mostra_aiuto_configurazione_aula(self):
        """Delega a moduli/istruzioni.py — schema visivo dell'aula."""
        mostra_aiuto_configurazione_aula(self)

    def _mostra_errore(self, titolo: str, messaggio: str):
        """Mostra un messaggio di errore."""
        QMessageBox.warning(self, titolo, messaggio)

    def _aggiorna_messaggio_elaborazione(self):
        """
        Aggiorna il messaggio di elaborazione in modo rotativo.
        Chiamato automaticamente dal timer ogni 2 secondi.
        """
        # Cambia al messaggio successivo nella lista
        self.indice_messaggio = (self.indice_messaggio + 1) % len(self.messaggi_elaborazione)
        messaggio_corrente = self.messaggi_elaborazione[self.indice_messaggio]

        # Aggiorna la label di status
        self.label_status.setText(messaggio_corrente)

    def _controlla_classe_gia_elaborata(self, nome_file_classe):
        """
        Controlla se la classe è già stata elaborata in precedenza.
        Tre livelli di riconoscimento, in ordine di priorità:

        1. MATCH ESATTO per file_origine (es: "2B.txt" == "2B.txt")
        2. FINGERPRINT per nomi studenti (5+ nomi in comune con una classe
           nello Storico che ha un file_origine diverso → l'utente ha
           probabilmente rinominato il file)
        3. CLASSE NUOVA (nessun match → auto-calcolo layout)

        Se la classe viene riconosciuta (livello 1 o 2):
        → ripristina lo schema aula dall'ultima assegnazione.
        Se è nuova (livello 3):
        → calcola automaticamente il numero di file necessarie.

        Args:
            nome_file_classe (str): Nome derivato dal file (es: "Classe 3A")
        """
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        # =================================================================
        # LIVELLO 1: MATCH ESATTO per file_origine
        # =================================================================
        # Ogni assegnazione nello storico salva il campo 'file_origine' con il
        # nome esatto del file .txt. Confrontiamo con self.file_origine_studenti.
        classe_trovata = False
        layout_ripristinato = False

        if self.file_origine_studenti and storico:
            # Cerca l'assegnazione PIÙ RECENTE che appartiene a questa classe
            for assegnazione in reversed(storico):
                if assegnazione.get("file_origine") == self.file_origine_studenti:
                    classe_trovata = True
                    # Ripristina lo schema aula dall'assegnazione trovata
                    config_aula_salvata = assegnazione.get("configurazione_aula", {})
                    num_file_salvato = config_aula_salvata.get("num_file")
                    posti_salvati = config_aula_salvata.get("posti_per_fila")
                    if num_file_salvato is not None:
                        self.input_num_file.setText(str(num_file_salvato))
                        layout_ripristinato = True
                    if posti_salvati is not None:
                        self.input_posti_fila.setText(str(posti_salvati))
                        layout_ripristinato = True
                    if layout_ripristinato:
                        self._aggiorna_posti_totali()
                        print(f"   🔄 Layout ripristinato dallo storico: "
                              f"{num_file_salvato}×{posti_salvati}")
                    # Ripristina la preferenza genere misto per questa classe
                    genere_misto_salvato = config_aula_salvata.get("genere_misto", False)
                    self.checkbox_genere_misto.setChecked(genere_misto_salvato)
                    break  # Basta l'ultima assegnazione

        # =================================================================
        # LIVELLO 2: FINGERPRINT per nomi studenti
        # =================================================================
        # Se il match esatto non ha funzionato, prova a riconoscere la classe
        # tramite i nomi degli studenti. Questo copre il caso in cui l'utente
        # ha rinominato il file .txt (es: "1A.txt" → "2A.txt").
        if not classe_trovata and storico:
            match = self._cerca_classe_per_fingerprint()
            if match:
                file_vecchio, nomi_comuni, totale = match
                # Chiedi conferma all'utente prima di ricollegare
                if self._chiedi_ricollegamento_storico(file_vecchio, nomi_comuni, totale):
                    # L'utente ha confermato: lo storico è stato aggiornato.
                    # Ora il file_origine delle vecchie assegnazioni punta al
                    # nuovo nome → ripetiamo il match esatto (livello 1),
                    # che questa volta troverà la corrispondenza.
                    for assegnazione in reversed(storico):
                        if assegnazione.get("file_origine") == self.file_origine_studenti:
                            classe_trovata = True
                            config_aula_salvata = assegnazione.get("configurazione_aula", {})
                            num_file_salvato = config_aula_salvata.get("num_file")
                            posti_salvati = config_aula_salvata.get("posti_per_fila")
                            if num_file_salvato is not None:
                                self.input_num_file.setText(str(num_file_salvato))
                                layout_ripristinato = True
                            if posti_salvati is not None:
                                self.input_posti_fila.setText(str(posti_salvati))
                                layout_ripristinato = True
                            if layout_ripristinato:
                                self._aggiorna_posti_totali()
                                print(f"   🔗 Layout ripristinato dopo ricollegamento: "
                                      f"{num_file_salvato}×{posti_salvati}")
                            # Ripristina la preferenza genere misto per questa classe
                            genere_misto_salvato = config_aula_salvata.get("genere_misto", False)
                            self.checkbox_genere_misto.setChecked(genere_misto_salvato)
                            break

        # =================================================================
        # ESITO: classe riconosciuta (livello 1 o 2) oppure nuova (livello 3)
        # =================================================================
        if classe_trovata:
            # CLASSE GIÀ ELABORATA: la rotazione è sempre attiva.
            # Se il layout NON è stato ripristinato (assegnazione trovata ma
            # senza configurazione_aula), esegui auto-calcolo come fallback.
            if not layout_ripristinato:
                self._auto_calcola_layout_aula()

            # Mostra notifica all'utente
            self.label_status.setText("🔄 Classe riconosciuta: pronta per rotazione")
            self.label_status.setStyleSheet(f"color: {C('testo_stato_ok')}; font-weight: bold;")

            # Rimuovi messaggio dopo 15 secondi, MA solo se nel frattempo
            # non è partita un'elaborazione (che usa label_status per i
            # suoi messaggi rotativi).
            QTimer.singleShot(15000, lambda: (
                self.label_status.setText("")
                if not self.timer_messaggi.isActive()
                else None
            ))
        else:
            # CLASSE NUOVA (mai elaborata): auto-calcolo layout
            self.checkbox_genere_misto.setChecked(False)
            self._auto_calcola_layout_aula()

    def _cerca_classe_per_fingerprint(self):
        """
        Cerca nello storico una classe con almeno 5 nomi studenti in comune
        con la classe appena caricata, ma con un file_origine diverso.

        Questo rileva il caso in cui l'utente ha rinominato il file .txt
        della classe, o ha creato un nuovo file con gli stessi studenti
        (es: passaggio da "1A.txt" a "2A.txt" a inizio anno).

        Returns:
            tuple: (file_origine_vecchio, nomi_in_comune, totale_storico)
                   oppure None se nessun match trovato.
            - file_origine_vecchio: il file_origine della classe nello storico
            - nomi_in_comune: set dei nomi condivisi (per il popup informativo)
            - totale_storico: numero totale di studenti nell'ultima assegnazione
        """
        if not self.studenti or not self.file_origine_studenti:
            return None

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if not storico:
            return None

        # Nomi della classe appena caricata: set di "Cognome Nome"
        nomi_caricati = set()
        for studente in self.studenti:
            nomi_caricati.add(studente.get_nome_completo())

        # Raggruppa le assegnazioni per file_origine (ogni classe ha il suo)
        classi_storico = {}  # {file_origine: [assegnazioni]}
        for assegnazione in storico:
            fo = assegnazione.get("file_origine", "")
            if fo and fo != self.file_origine_studenti:
                # Solo classi con file_origine DIVERSO da quello corrente
                # (se fosse uguale, il match esatto l'avrebbe già trovato)
                if fo not in classi_storico:
                    classi_storico[fo] = []
                classi_storico[fo].append(assegnazione)

        # Per ogni classe nello storico, estrai i nomi dall'ULTIMA assegnazione
        # (la più recente ha la lista studenti più aggiornata)
        soglia_minima = 5  # Almeno 5 nomi in comune per considerarlo un match
        miglior_match = None
        max_nomi_comuni = 0

        for file_origine_vecchio, assegnazioni in classi_storico.items():
            # Prendi l'ultima assegnazione (la più recente)
            ultima = assegnazioni[-1]
            layout = ultima.get("layout", [])

            # Estrai i nomi studenti dal layout
            nomi_storico = set()
            for entry in layout:
                nome = entry.get("studente", "")
                if nome:
                    nomi_storico.add(nome)

            # Calcola intersezione
            nomi_comuni = nomi_caricati & nomi_storico

            # Aggiorna il miglior match (quello con più nomi in comune)
            if len(nomi_comuni) >= soglia_minima and len(nomi_comuni) > max_nomi_comuni:
                max_nomi_comuni = len(nomi_comuni)
                miglior_match = (file_origine_vecchio, nomi_comuni, len(nomi_storico))

        return miglior_match

    def _chiedi_ricollegamento_storico(self, file_origine_vecchio, nomi_in_comune, totale_storico):
        """
        Mostra un popup che chiede all'utente se vuole ricollegare
        lo Storico di una classe riconosciuta tramite fingerprint.

        Se l'utente conferma, aggiorna il campo file_origine in TUTTE
        le assegnazioni della vecchia classe, sostituendolo con il
        nome del file corrente. Da quel momento la classe viene
        riconosciuta normalmente dal match esatto.

        Args:
            file_origine_vecchio: nome file della classe nello storico (es: "1A.txt")
            nomi_in_comune: set dei nomi condivisi (per informazione)
            totale_storico: numero studenti nell'ultima assegnazione storica

        Returns:
            bool: True se l'utente ha confermato e lo storico è stato aggiornato
        """
        # Prepara il messaggio con i dettagli del match
        num_comuni = len(nomi_in_comune)
        num_caricati = len(self.studenti)

        # Mostra al massimo 8 nomi in comune come esempio
        nomi_esempio = sorted(nomi_in_comune)[:8]
        elenco_nomi = "\n".join(f"  • {nome}" for nome in nomi_esempio)
        if len(nomi_in_comune) > 8:
            elenco_nomi += f"\n  ... e altri {len(nomi_in_comune) - 8} studenti"

        # Conta quante assegnazioni ha la vecchia classe
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        num_assegnazioni = sum(
            1 for a in storico
            if a.get("file_origine") == file_origine_vecchio
        )

        dialog = QMessageBox(self)
        dialog.setWindowTitle("🔍 Classe riconosciuta!")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(
            f"La classe appena caricata ({file_origine_vecchio}) condivide\n"
            f"{num_comuni} studenti con '{file_origine_vecchio}',\n"
            f"che ha {num_assegnazioni} assegnazion{'e' if num_assegnazioni == 1 else 'i'} "
            f"nello Storico.\n\n"
            f"Studenti in comune:\n"
            f"{elenco_nomi}\n\n"
            f"Vuoi RICOLLEGARE lo Storico di '{file_origine_vecchio}'\n"
            f"a questa classe ('{self.file_origine_studenti}')?\n\n"
            f"💡 Se confermi, tutte le assegnazioni precedenti verranno\n"
            f"associate al nuovo file e la rotazione proseguirà\n"
            f"tenendo conto delle coppie già formate."
        )

        btn_collega = dialog.addButton(
            "✅ Sì, ricollega lo Storico", QMessageBox.AcceptRole
        )
        btn_no = dialog.addButton(
            "❌ No, è una classe diversa", QMessageBox.RejectRole
        )

        dialog.setDefaultButton(btn_collega)
        dialog.setEscapeButton(btn_no)
        dialog.exec()

        if dialog.clickedButton() != btn_collega:
            return False

        # === AGGIORNAMENTO file_origine E nomi nello Storico ===
        # Sostituisce il vecchio nome file con il nuovo in TUTTE
        # le assegnazioni che appartenevano alla classe rinominata.
        # Aggiorna anche il campo 'nome' di ogni assegnazione,
        # sostituendo il vecchio nome classe con il nuovo, così
        # la tab Storico non mostra nomi misti (vecchi e nuovi).
        assegnazioni_aggiornate = 0

        # Ricava i nomi classe "puliti" (senza estensione) per la sostituzione.
        # Es: "Classe1A.txt" → "Classe1A", "Classe2A.txt" → "Classe2A"
        nome_vecchio_stem = os.path.splitext(file_origine_vecchio)[0]
        nome_nuovo_stem = os.path.splitext(self.file_origine_studenti)[0]

        for assegnazione in storico:
            if assegnazione.get("file_origine") == file_origine_vecchio:
                assegnazione["file_origine"] = self.file_origine_studenti

                # Aggiorna il nome dell'assegnazione se contiene il vecchio nome.
                # Es: "Classe1A - Assegnazione 01 - 07/03/2026"
                #   → "Classe2A - Assegnazione 01 - 07/03/2026"
                # La sostituzione è case-insensitive per robustezza.
                nome_originale = assegnazione.get("nome", "")
                if nome_vecchio_stem.lower() in nome_originale.lower():
                    # Trova la posizione case-insensitive e sostituisce
                    # preservando il formato originale del resto della stringa
                    idx = nome_originale.lower().find(nome_vecchio_stem.lower())
                    if idx >= 0:
                        assegnazione["nome"] = (
                            nome_originale[:idx]
                            + nome_nuovo_stem
                            + nome_originale[idx + len(nome_vecchio_stem):]
                        )

                assegnazioni_aggiornate += 1

        # Salva il JSON aggiornato
        self.config_app.salva_configurazione()

        print(f"🔗 Storico ricollegato: '{file_origine_vecchio}' → "
              f"'{self.file_origine_studenti}' ({assegnazioni_aggiornate} assegnazioni)")

        # Aggiorna la tabella Storico (i nomi sono cambiati)
        self._aggiorna_tabella_storico()

        # Aggiorna il filtro classi nelle Statistiche (il vecchio nome scompare)
        self._popola_filtro_classi()

        return True

    def _auto_calcola_layout_aula(self):
        """
        Calcola automaticamente il numero di file necessarie per contenere
        tutti gli studenti caricati, usando 6 posti per fila come default.

        Chiamato da _controlla_classe_gia_elaborata() quando:
        - La classe è nuova (mai elaborata prima)
        - La classe è nota ma il layout salvato non è disponibile (fallback)
        """
        # === AUTO-CALCOLO FILE NECESSARIE ===
        # Anziché usare un default fisso (4×6=24) che spesso crea
        # molti "banchi fantasma", calcoliamo il numero MINIMO di file
        # necessarie per contenere tutti gli studenti.
        # I posti per fila restano a 6 (default ragionevole: 3 coppie),
        # ma l'utente può comunque regolarli manualmente con +/-.
        posti_per_fila_default = 6
        self.input_posti_fila.setText(str(posti_per_fila_default))

        if self.studenti:
            num_studenti = len(self.studenti)
            file_necessarie = math.ceil(num_studenti / posti_per_fila_default)
            # Assicura almeno 1 fila e non più di 6 (limite dell'interfaccia)
            file_necessarie = max(1, min(file_necessarie, 6))
            self.input_num_file.setText(str(file_necessarie))
            print(f"   📐 Auto-calcolo aula: {num_studenti} studenti → "
                  f"{file_necessarie} file × {posti_per_fila_default} posti "
                  f"= {file_necessarie * posti_per_fila_default} banchi")
        else:
            # Nessuno studente caricato (non dovrebbe succedere qui,
            # ma per sicurezza usiamo il default)
            self.input_num_file.setText("4")

        self._aggiorna_posti_totali()

    def resizeEvent(self, event):
        """
        Gestisce il ridimensionamento della finestra.
        Forza il ricalcolo del layout del pannello sinistro per garantire
        che il testo faccia auto-wrap correttamente alla nuova larghezza.
        Senza questo, le label rimarrebbero "bloccate" alla larghezza precedente
        e il testo verrebbe tagliato fino al successivo aggiornamento del contenuto.
        """
        super().resizeEvent(event)
        # Forza il ricalcolo del layout del pannello sinistro
        if hasattr(self, 'scroll_pannello_sx'):
            widget_interno = self.scroll_pannello_sx.widget()
            if widget_interno:
                widget_interno.updateGeometry()

    def closeEvent(self, event):
        """Gestisce la chiusura dell'applicazione."""

        # Controlla se l'Editor studenti ha modifiche non salvate
        # Se sì, mostra il popup di conferma (salva/esci/annulla)
        if hasattr(self, 'editor_studenti'):
            if not self.editor_studenti.richiedi_conferma_chiusura():
                # L'utente ha annullato → blocca la chiusura
                event.ignore()
                return

        # Controlla se c'è un'assegnazione non salvata nello storico
        if self.assegnazione_non_salvata:
            dialog_chiudi = QMessageBox(self)
            dialog_chiudi.setWindowTitle("⚠️ ASSEGNAZIONE NON SALVATA!")
            dialog_chiudi.setIcon(QMessageBox.Warning)
            dialog_chiudi.setText(
                "❗ L'ultima assegnazione NON è stata salvata nello Storico.\n\n"
                "Se chiudi ora, le coppie formate NON verranno\n"
                "considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?\n"
            )

            btn_salva_chiudi = dialog_chiudi.addButton(
                "💾 Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_esci_chiudi = dialog_chiudi.addButton(
                "🚪 Chiudi senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_chiudi = dialog_chiudi.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            dialog_chiudi.setDefaultButton(btn_salva_chiudi)
            # X della finestra e tasto Esc = Annulla (blocca la chiusura)
            dialog_chiudi.setEscapeButton(btn_annulla_chiudi)

            dialog_chiudi.exec()

            bottone_chiudi = dialog_chiudi.clickedButton()

            if bottone_chiudi == btn_salva_chiudi:
                # L'utente vuole salvare prima di chiudere
                self.salva_assegnazione()
                # Se dopo il salvataggio il flag è ancora True, ha annullato
                if self.assegnazione_non_salvata:
                    event.ignore()  # Annullato → blocca la chiusura
                    return

            elif bottone_chiudi == btn_annulla_chiudi:
                # Annulla → blocca la chiusura
                event.ignore()
                return

            # Se "Chiudi senza salvare" → procedi con la chiusura

        # Salva configurazione prima di chiudere
        self.config_app.salva_configurazione()

        event.accept()


def main():
    """Funzione principale per avviare l'interfaccia dell'applicazione."""

    app = QApplication(sys.argv)

    # Imposta stile e icona dell'applicazione
    app.setApplicationName("PostiPerfetti")
    app.setApplicationVersion("2.0")

    # Installa il filtro globale per il cursore "manina" sui pulsanti.
    # Deve essere creato PRIMA della finestra, così cattura tutti i pulsanti
    # fin dalla loro creazione (inclusi quelli nei dialog dinamici).
    filtro_cursore = FiltroCursoreManina(app)
    app.installEventFilter(filtro_cursore)

    # Imposta l'icona dell'applicazione (visibile nella taskbar e nella barra del titolo)
    percorso_icona = os.path.join(get_base_path(), "moduli", "postiperfetti.ico")
    if os.path.exists(percorso_icona):
        app.setWindowIcon(QIcon(percorso_icona))

    # Crea e mostra finestra principale
    finestra = FinestraPostiPerfetti()
    finestra.show()

    # Avvia loop eventi
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

