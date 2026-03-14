"""
Editor Grafico per classe da modificare (.txt)
========================================
Modulo PySide6 che fornisce un widget per creare e modificare
i file .txt degli studenti con i relativi vincoli.

Integrato come tab nell'applicazione principale.

"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGroupBox, QScrollArea, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QFrame, QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
import os
import sys
# Importa la funzione C() per accedere ai colori del tema attivo
from modelli.tema import C


# Testo del placeholder che appare nel ComboBox prima che il docente
# scelga uno studente. Finché è selezionato, il vincolo NON viene
# creato e la riga viene ignorata nell'esportazione.
PLACEHOLDER_VINCOLO = "⬇️ Seleziona studente..."

# Placeholder per il ComboBox del livello: appare quando il docente
# aggiunge un nuovo vincolo, così è COSTRETTO a scegliere consapevolmente
# il livello di incompatibilità/affinità invece di accettare un default.
PLACEHOLDER_LIVELLO = "⬇️ Seleziona intensità del vincolo..."

# Placeholder per il ComboBox del genere: appare quando il genere
# NON è stato ancora selezionato (es: caricamento formato base).
# Il docente è OBBLIGATO a scegliere M o F prima di esportare.
PLACEHOLDER_GENERE = "---"


# =============================================================================
# CLASSE: ComboBox protetto dalla rotella del mouse
# =============================================================================
class ComboBoxProtetto(QComboBox):
    """
    QComboBox personalizzato che IGNORA la rotella del mouse
    a meno che il widget non abbia il focus esplicito (click del docente).

    Problema risolto: quando il docente scrolla la lista delle schede
    studenti, se il cursore passa sopra un ComboBox, la rotella
    cambierebbe accidentalmente il valore selezionato. Questo ComboBox
    impedisce quel comportamento: la rotella funziona SOLO dopo un
    click diretto sul ComboBox.

    Tecnica: si imposta la FocusPolicy su StrongFocus (= solo click,
    non Tab) e si rifiuta l'evento wheelEvent se il widget non ha il focus.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # StrongFocus = il widget riceve il focus solo con un click diretto
        # (non con Tab, non con il passaggio del mouse)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        """
        Intercetta la rotella del mouse.
        Se il ComboBox NON ha il focus (= il docente non ci ha cliccato),
        ignora l'evento e lo passa al widget padre (la ScrollArea),
        così lo scroll della pagina continua normalmente.
        """
        if self.hasFocus():
            # Il docente ha cliccato sul ComboBox → la rotella funziona
            super().wheelEvent(event)
        else:
            # Il mouse è passato sopra senza click → ignora, lascia scrollare
            event.ignore()


# =============================================================================
# CLASSE: Riga vincolo (una singola riga incompatibilità o affinità)
# =============================================================================
class RigaVincolo(QWidget):
    """
    Widget che rappresenta una singola riga di vincolo (incompatibilità o affinità).
    Contiene:
    - ComboBox per selezionare lo studente target
    - ComboBox per il livello (1, 2, 3)
    - Bottone per rimuovere la riga

    Segnali:
    - vincolo_cambiato: emesso quando l'utente modifica studente o livello
    - vincolo_rimosso: emesso quando l'utente clicca il bottone rimuovi
    """

    # Segnali personalizzati per comunicare con il widget padre
    vincolo_cambiato = Signal()   # Notifica che il vincolo è stato modificato
    vincolo_rimosso = Signal()    # Notifica che il vincolo è stato rimosso

    def __init__(self, lista_studenti_disponibili, tipo_vincolo="incompatibilita",
                 studente_selezionato=None, livello=3, parent=None):
        """
        Args:
            lista_studenti_disponibili: lista di stringhe "Cognome Nome" selezionabili
            tipo_vincolo: "incompatibilita" o "affinita" (determina le etichette del livello)
            studente_selezionato: stringa "Cognome Nome" da pre-selezionare (o None)
            livello: livello del vincolo (1, 2 o 3), default 3
        """
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # --- ComboBox studente target (occupa ~2/3 dello spazio) ---
        # Usa ComboBoxProtetto per impedire modifiche accidentali con la rotella
        self.combo_studente = ComboBoxProtetto()
        self.combo_studente.setMinimumWidth(160)  # Stessa larghezza minima del combo livello
        self.combo_studente.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if studente_selezionato and studente_selezionato in lista_studenti_disponibili:
            # === MODALITÀ PRE-COMPILATA (caricamento da file) ===
            # Lo studente è già noto: popola direttamente senza placeholder
            self.combo_studente.addItems(lista_studenti_disponibili)
            self.combo_studente.setCurrentText(studente_selezionato)
        else:
            # === MODALITÀ NUOVO VINCOLO (click su "Aggiungi") ===
            # Inserisci il placeholder come prima voce, così il docente
            # è COSTRETTO a scegliere uno studente prima che il vincolo
            # venga effettivamente creato
            self.combo_studente.addItem(PLACEHOLDER_VINCOLO)
            self.combo_studente.addItems(lista_studenti_disponibili)
            self.combo_studente.setCurrentText(PLACEHOLDER_VINCOLO)

        # --- TRACKING STUDENTE PRECEDENTE ---
        # Salva lo studente attualmente selezionato nel ComboBox.
        # Serve per la sincronizzazione bidirezionale: quando l'utente
        # cambia studente nel ComboBox, dobbiamo sapere chi c'era PRIMA
        # per poter rimuovere il vecchio vincolo speculare.
        self._studente_precedente = self.combo_studente.currentText()

        # --- STILE VISIVO: bordo arancione finché il placeholder è attivo ---
        self._aggiorna_stile_combobox()

        # Connetti il cambio selezione al segnale
        self.combo_studente.currentTextChanged.connect(self._on_cambiato)
        # Proporzione 1:1 con il combo livello → stessa larghezza
        layout.addWidget(self.combo_studente, 1)

        # --- ComboBox livello con etichette descrittive (occupa ~1/3 dello spazio) ---
        # Le etichette cambiano in base al tipo di vincolo:
        # - Incompatibilità: il livello 3 è VINCOLANTE (blacklist assoluta)
        # - Affinità: il livello 3 è Forte (priorità alta ma non assoluta)
        # Usa ComboBoxProtetto per impedire modifiche accidentali con la rotella
        self.combo_livello = ComboBoxProtetto()
        self.combo_livello.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_livello.setMinimumWidth(160)  # Stessa larghezza minima del combo studente

        # Etichette differenziate per tipo di vincolo
        if tipo_vincolo == "incompatibilita":
            self._etichette_livello = ["1 — Leggera", "2 — Media", "3 — ASSOLUTA"]
        else:
            self._etichette_livello = ["1 — Leggera", "2 — Media", "3 — Forte"]

        self.combo_livello.addItems(self._etichette_livello)

        if studente_selezionato:
            # === MODALITÀ PRE-COMPILATA (caricamento da file) ===
            # Il livello è già noto: seleziona direttamente
            indice_livello = max(0, min(int(livello) - 1, 2))
            self.combo_livello.setCurrentIndex(indice_livello)
            # Il vincolo è già stato registrato (viene dal file)
            self._registrato = True
        else:
            # === MODALITÀ NUOVO VINCOLO (click su "Aggiungi") ===
            # Inserisci il placeholder come prima voce, così il docente
            # è COSTRETTO a scegliere un livello consapevolmente.
            # Evita che venga lasciato il livello 3 "per distrazione".
            self.combo_livello.insertItem(0, PLACEHOLDER_LIVELLO)
            self.combo_livello.setCurrentIndex(0)
            # Il vincolo non è ancora stato registrato nella sincronizzazione
            self._registrato = False
            # Flag per mostrare il promemoria livello UNA SOLA VOLTA per riga
            self._promemoria_livello_mostrato = False

        # --- STILE VISIVO: bordo arancione finché il placeholder è attivo ---
        self._aggiorna_stile_combo_livello()

        self.combo_livello.currentTextChanged.connect(self._on_cambiato)
        # Proporzione 1:1 con il combo studente → stessa larghezza
        layout.addWidget(self.combo_livello, 1)

        # --- Bottone "Rimuovi" vincolo (più leggibile del vecchio ➖) ---
        btn_rimuovi = QPushButton("Rimuovi")
        btn_rimuovi.setMinimumWidth(80)
        btn_rimuovi.setFixedHeight(36)
        btn_rimuovi.setToolTip("Rimuovi questo vincolo")
        btn_rimuovi.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-size: 12px;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #b71c1c; }
        """)
        btn_rimuovi.clicked.connect(self._on_rimosso)
        layout.addWidget(btn_rimuovi)

    def get_studente(self):
        """
        Restituisce il nome completo dello studente selezionato.
        Se il placeholder è ancora attivo, restituisce stringa vuota
        (= nessuno studente selezionato, il vincolo non è ancora valido).
        """
        testo = self.combo_studente.currentText()
        if testo == PLACEHOLDER_VINCOLO:
            return ""  # Nessuno studente selezionato
        return testo

    def is_placeholder_attivo(self):
        """Restituisce True se il ComboBox studente ha ancora il placeholder selezionato."""
        return self.combo_studente.currentText() == PLACEHOLDER_VINCOLO

    def is_placeholder_livello_attivo(self):
        """Restituisce True se il ComboBox livello ha ancora il placeholder selezionato."""
        return self.combo_livello.currentText() == PLACEHOLDER_LIVELLO

    def _aggiorna_stile_combobox(self):
        """
        Cambia lo stile visivo del ComboBox:
        - Bordo ARANCIONE se il placeholder è ancora attivo (= attenzione!)
        - Bordo NORMALE se è stato selezionato uno studente reale
        """
        if self.is_placeholder_attivo():
            # Bordo arancione: segnala che lo studente non è ancora scelto
            self.combo_studente.setStyleSheet(f"""
                QComboBox {{
                    border: 2px solid {C("combo_ph_bordo")};
                    background-color: {C("combo_ph_sf")};
                    color: {C("combo_ph_txt")};
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
            """)
        else:
            # Stile normale: studente selezionato
            self.combo_studente.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {C("combo_ok_bordo")};
                    background-color: {C("combo_ok_sf")};
                    color: {C("combo_ok_txt")};
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
            """)

    def _aggiorna_stile_combo_livello(self):
        """
        Cambia lo stile visivo del ComboBox livello:
        - Bordo ARANCIONE se il placeholder è ancora attivo (= attenzione!)
        - Bordo NORMALE se è stato selezionato un livello reale
        Stessa logica visiva del ComboBox studente per coerenza.
        """
        if self.is_placeholder_livello_attivo():
            # Bordo arancione: segnala che il livello non è ancora scelto
            self.combo_livello.setStyleSheet(f"""
                QComboBox {{
                    border: 2px solid {C("combo_ph_bordo")};
                    background-color: {C("combo_ph_sf")};
                    color: {C("combo_ph_txt")};
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
            """)
        else:
            # Stile normale: livello selezionato
            self.combo_livello.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {C("combo_ok_bordo")};
                    background-color: {C("combo_ok_sf")};
                    color: {C("combo_ok_txt")};
                    padding: 4px 8px;
                    border-radius: 4px;
                }}
            """)

    def get_livello(self):
        """
        Restituisce il livello come intero (1, 2 o 3).
        Restituisce 0 se il placeholder è ancora attivo (= livello non scelto).
        Estrae il numero dal primo carattere dell'etichetta descrittiva.
        Es: "3 — ASSOLUTA" → 3, "1 — Leggera" → 1
        """
        # Se il placeholder è ancora attivo, il vincolo non è completo
        if self.is_placeholder_livello_attivo():
            return 0
        testo = self.combo_livello.currentText()
        # Il primo carattere è sempre il numero del livello
        try:
            return int(testo[0])
        except (ValueError, IndexError):
            return 3  # Fallback sicuro: livello massimo

    def get_studente_precedente(self):
        """
        Restituisce il nome dello studente che era selezionato PRIMA
        dell'ultima modifica. Serve per la sincronizzazione bidirezionale:
        quando l'utente cambia da "Rossi Mario" a "Bianchi Anna",
        questo metodo restituisce "Rossi Mario" (il vecchio).

        Se il precedente era il placeholder, restituisce stringa vuota
        (= non c'era nessun vincolo reale da rimuovere).
        """
        if self._studente_precedente == PLACEHOLDER_VINCOLO:
            return ""
        return self._studente_precedente

    def aggiorna_precedente(self):
        """
        Aggiorna il tracking dello studente precedente al valore corrente.
        Va chiamato DOPO aver gestito la sincronizzazione bidirezionale,
        in modo che il prossimo cambio possa rilevare di nuovo la differenza.
        """
        self._studente_precedente = self.combo_studente.currentText()

    def aggiorna_lista_studenti(self, nuova_lista, studente_corrente=None):
        """
        Aggiorna la lista degli studenti nel ComboBox senza perdere la selezione.

        Args:
            nuova_lista: nuova lista di "Cognome Nome" disponibili
            studente_corrente: se specificato, mantieni questa selezione
        """
        # Salva la selezione corrente prima di aggiornare
        selezione = studente_corrente or self.combo_studente.currentText()
        # Blocca i segnali per evitare trigger durante l'aggiornamento
        self.combo_studente.blockSignals(True)
        self.combo_studente.clear()
        self.combo_studente.addItems(nuova_lista)
        # Ripristina la selezione se ancora disponibile
        if selezione in nuova_lista:
            self.combo_studente.setCurrentText(selezione)
        self.combo_studente.blockSignals(False)

    def _on_cambiato(self):
        """
        Slot interno: emette il segnale vincolo_cambiato.
        Gestisce i placeholder di ENTRAMBI i ComboBox (studente e livello):
        - Quando il docente sceglie un nome reale, rimuove il placeholder studente
        - Quando il docente sceglie un livello reale, rimuove il placeholder livello
        - Aggiorna lo stile visivo di entrambi i ComboBox
        """
        # --- Gestione placeholder STUDENTE ---
        testo_corrente = self.combo_studente.currentText()

        # Se il docente ha selezionato un nome reale (non il placeholder),
        # rimuovi il placeholder dalla lista così non può più tornarci
        if testo_corrente != PLACEHOLDER_VINCOLO:
            idx_placeholder = self.combo_studente.findText(PLACEHOLDER_VINCOLO)
            if idx_placeholder >= 0:
                # Blocca i segnali durante la rimozione per evitare trigger
                self.combo_studente.blockSignals(True)
                self.combo_studente.removeItem(idx_placeholder)
                self.combo_studente.blockSignals(False)

        # --- Gestione placeholder LIVELLO ---
        testo_livello = self.combo_livello.currentText()

        # Se il docente ha selezionato un livello reale (non il placeholder),
        # rimuovi il placeholder dalla lista così non può più tornarci
        if testo_livello != PLACEHOLDER_LIVELLO:
            idx_ph_livello = self.combo_livello.findText(PLACEHOLDER_LIVELLO)
            if idx_ph_livello >= 0:
                self.combo_livello.blockSignals(True)
                self.combo_livello.removeItem(idx_ph_livello)
                self.combo_livello.blockSignals(False)

        # Aggiorna lo stile visivo di entrambi (bordo arancione → normale)
        self._aggiorna_stile_combobox()
        self._aggiorna_stile_combo_livello()

        # --- PROMEMORIA: studente scelto ma livello ancora da selezionare ---
        # Mostrato UNA SOLA VOLTA per riga, con leggero ritardo (QTimer)
        # per non interferire con il processing interno del ComboBox.
        if (not self.is_placeholder_attivo()
                and self.is_placeholder_livello_attivo()
                and not self._promemoria_livello_mostrato):
            self._promemoria_livello_mostrato = True
            # QTimer.singleShot(0, ...) esegue il popup nel prossimo ciclo
            # dell'event loop → sicuro, non interferisce con i segnali in corso
            QTimer.singleShot(0, self._mostra_promemoria_livello)

        # Emetti il segnale per la sincronizzazione bidirezionale
        self.vincolo_cambiato.emit()

    def _mostra_promemoria_livello(self):
        """
        Mostra un popup di promemoria che invita il docente a selezionare
        il livello del vincolo. Non è bloccante per il flusso di lavoro:
        basta cliccare OK e il docente può scegliere il livello con calma.
        """
        QMessageBox.information(
            self,
            "Seleziona il livello",
            "Hai scelto lo studente\n"
            "Ora seleziona anche l'intensità del livello del vincolo\n"
            "~ 1 = Leggera     ~ 2 = Media     ~ 3 = ASSOLUTA/Forte\n\n"
            "Il livello determina quanto l'algoritmo rispetterà\n"
            "questo vincolo durante l'assegnazione dei posti."
        )

    def _on_rimosso(self):
        """Slot interno: emette il segnale vincolo_rimosso."""
        self.vincolo_rimosso.emit()

    def aggiorna_tema(self):
        """Riapplica gli stili del tema attivo ai ComboBox studente e livello."""
        # _aggiorna_stile_combobox() e _aggiorna_stile_combo_livello()
        # usano già C() internamente
        self._aggiorna_stile_combobox()
        self._aggiorna_stile_combo_livello()


# =============================================================================
# CLASSE: Scheda singolo studente (QGroupBox collassabile)
# =============================================================================
class SchedaStudente(QGroupBox):
    """
    Widget che rappresenta la scheda completa di un singolo studente.
    Contiene:
    - Genere (M/F)
    - Posizione (NORMALE/PRIMA/ULTIMA)
    - Lista dinamica di incompatibilità
    - Lista dinamica di affinità

    È collassabile: cliccando sul titolo si espande/comprime.

    Segnali:
    - vincolo_modificato_signal: emesso quando un vincolo viene aggiunto/rimosso/modificato
      Payload: (cognome_nome_studente_a, cognome_nome_studente_b, tipo, livello, azione)
    """

    # Segnale per notificare all'EditorWidget che un vincolo è cambiato
    # Parametri: studente_a (str), studente_b (str), tipo (str), livello (int), azione (str)
    vincolo_modificato_signal = Signal(str, str, str, int, str)

    def __init__(self, cognome, nome, tutti_studenti, sesso="M", posizione="NORMALE",
                 incompatibilita=None, affinita=None, parent=None):
        """
        Args:
            cognome: cognome dello studente
            nome: nome dello studente
            tutti_studenti: lista di TUTTI gli studenti ["Cognome Nome", ...]
            sesso: "M" o "F"
            posizione: "NORMALE", "PRIMA" o "ULTIMA"
            incompatibilita: dict {nome_completo: livello} o None
            affinita: dict {nome_completo: livello} o None
        """
        # Il titolo del GroupBox mostra Cognome Nome
        self.cognome = cognome
        self.nome = nome
        self.nome_completo = f"{cognome} {nome}"
        super().__init__(f"📋 {self.nome_completo}", parent)

        # Stato collassabile: inizia COLLASSATO per evitare che con molti
        # studenti la lista sia troppo lunga e il docente rischi di
        # modificare accidentalmente i ComboBox scrollando
        self._espanso = False
        self.setCheckable(False)

        # Salva la lista di tutti gli studenti (per i ComboBox dei vincoli)
        self._tutti_studenti = tutti_studenti

        # Flag per bloccare la sincronizzazione durante aggiornamenti programmatici
        self._aggiornamento_programmatico = False

        # Liste per tenere traccia delle righe vincolo create
        self._righe_incompatibilita = []
        self._righe_affinita = []

        # Costruisci l'interfaccia della scheda
        self._costruisci_ui(sesso, posizione, incompatibilita or {}, affinita or {})

        # Applica lo stile visivo in base al genere
        # (verrà aggiornato ogni volta che il docente cambia il genere)
        self._aggiorna_stile_genere(sesso)

    def _costruisci_ui(self, sesso, posizione, incompatibilita, affinita):
        """Costruisce tutti i widget interni della scheda studente."""

        # Layout principale della scheda
        self._layout_contenuto = QVBoxLayout(self)
        self._layout_contenuto.setSpacing(8)

        # Widget contenitore (per poterlo nascondere nel collasso)
        self._contenitore = QWidget()
        self._layout_interno = QVBoxLayout(self._contenitore)
        self._layout_interno.setContentsMargins(8, 4, 8, 4)
        self._layout_interno.setSpacing(6)

        # --- RIGA 1: Genere e Posizione affiancati ---
        riga_base = QHBoxLayout()

        # Genere (con supporto placeholder per formato base)
        riga_base.addWidget(QLabel("Genere:"))
        self.combo_genere = ComboBoxProtetto()

        if sesso == PLACEHOLDER_GENERE or sesso == "":
            # === GENERE NON IMPOSTATO (formato base: solo cognome;nome) ===
            # Mostra il placeholder "---" come prima voce, obbligando
            # il docente a selezionare manualmente M o F
            self.combo_genere.addItems([PLACEHOLDER_GENERE, "M", "F"])
            self.combo_genere.setCurrentText(PLACEHOLDER_GENERE)
            # Bordo arancione per segnalare che il genere va impostato
            # Bordo arancione: il genere non è ancora stato impostato
            self.combo_genere.setStyleSheet(f"""
                QComboBox {{
                    border: 2px solid {C("genere_ph_bordo")};
                    background-color: {C("genere_ph_sf")};
                }}
            """)
        else:
            # === GENERE GIÀ NOTO (formato completo o selezionato dal docente) ===
            self.combo_genere.addItems(["M", "F"])
            self.combo_genere.setCurrentText(sesso)

        self.combo_genere.setFixedWidth(70)

        # Quando il docente seleziona M o F, rimuovi il placeholder e lo stile arancione
        self.combo_genere.currentTextChanged.connect(self._on_genere_cambiato)

        riga_base.addWidget(self.combo_genere)

        riga_base.addSpacing(20)

        # Posizione (etichette descrittive, valori interni invariati)
        riga_base.addWidget(QLabel("Posizione:"))
        self.combo_posizione = ComboBoxProtetto()
        # Mappa: etichetta visualizzata → valore interno usato nel file .txt
        self._mappa_posizioni = {
            "NORMALE (nessuna preferenza)": "NORMALE",
            "PRIMA — VINCOLANTE": "PRIMA",
            "ULTIMA — Preferenza": "ULTIMA"
        }
        # Mappa inversa: valore interno → etichetta visualizzata
        self._mappa_posizioni_inversa = {v: k for k, v in self._mappa_posizioni.items()}
        self.combo_posizione.addItems(list(self._mappa_posizioni.keys()))
        # Seleziona l'etichetta corrispondente al valore interno
        etichetta = self._mappa_posizioni_inversa.get(posizione, "NORMALE (nessuna preferenza)")
        self.combo_posizione.setCurrentText(etichetta)
        self.combo_posizione.setFixedWidth(250)  # Più largo per etichette descrittive
        riga_base.addWidget(self.combo_posizione)

        riga_base.addStretch()
        self._layout_interno.addLayout(riga_base)

        # --- SEPARATORE ---
        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.HLine)
        self._sep1.setStyleSheet(f"background-color: {C('editor_sep')};")
        self._layout_interno.addWidget(self._sep1)

        # --- SEZIONE INCOMPATIBILITÀ ---
        # Colore rosso: semantico (incompatibilità = attenzione), invariato nei temi
        label_incomp = QLabel("⛔ INCOMPATIBILITÀ:")
        label_incomp.setStyleSheet("font-weight: bold; color: #ef5350; font-size: 13px;")
        self._layout_interno.addWidget(label_incomp)

        # Container per le righe di incompatibilità
        self._container_incomp = QVBoxLayout()
        self._container_incomp.setSpacing(4)
        self._layout_interno.addLayout(self._container_incomp)

        # Popola le incompatibilità esistenti (dal file caricato)
        for nome_target, livello in incompatibilita.items():
            self._aggiungi_riga_vincolo("incompatibilita", nome_target, livello, notifica=False)

        # Bottone "Aggiungi incompatibilità"
        self._btn_aggiungi_incomp = QPushButton("➕ Aggiungi incompatibilità")
        self._btn_aggiungi_incomp.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("editor_btn_incomp_sf")};
                color: {C("editor_btn_incomp_txt")};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {C("editor_btn_incomp_hover")}; }}
        """)
        self._btn_aggiungi_incomp.setToolTip("Aggiungi un vincolo di incompatibilità con un altro studente")
        self._btn_aggiungi_incomp.clicked.connect(lambda: self._aggiungi_riga_vincolo("incompatibilita"))
        self._layout_interno.addWidget(self._btn_aggiungi_incomp)

        # --- SEPARATORE ---
        self._sep2 = QFrame()
        self._sep2.setFrameShape(QFrame.HLine)
        self._sep2.setStyleSheet(f"background-color: {C('editor_sep')};")
        self._layout_interno.addWidget(self._sep2)

        # --- SEZIONE AFFINITÀ ---
        # Colore verde: semantico (affinità = positivo), invariato nei temi
        label_aff = QLabel("💚 AFFINITÀ:")
        label_aff.setStyleSheet("font-weight: bold; color: #66bb6a; font-size: 13px;")
        self._layout_interno.addWidget(label_aff)

        # Container per le righe di affinità
        self._container_aff = QVBoxLayout()
        self._container_aff.setSpacing(4)
        self._layout_interno.addLayout(self._container_aff)

        # Popola le affinità esistenti (dal file caricato)
        for nome_target, livello in affinita.items():
            self._aggiungi_riga_vincolo("affinita", nome_target, livello, notifica=False)

        # Bottone "Aggiungi affinità"
        self._btn_aggiungi_aff = QPushButton("➕ Aggiungi affinità")
        self._btn_aggiungi_aff.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("editor_btn_aff_sf")};
                color: {C("editor_btn_aff_txt")};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {C("editor_btn_aff_hover")}; }}
        """)
        self._btn_aggiungi_aff.setToolTip("Aggiungi un vincolo di affinità con un altro studente")
        self._btn_aggiungi_aff.clicked.connect(lambda: self._aggiungi_riga_vincolo("affinita"))
        self._layout_interno.addWidget(self._btn_aggiungi_aff)

        # Aggiungi il contenitore al layout principale
        self._layout_contenuto.addWidget(self._contenitore)

        # Stato iniziale: collassato (contenitore nascosto, icona ▶)
        self._contenitore.setVisible(False)
        self.setTitle(f"▶ {self.nome_completo}")

    def _get_studenti_disponibili(self, tipo_vincolo):
        """
        Restituisce la lista degli studenti selezionabili per un nuovo vincolo.
        Esclude:
        - Lo studente stesso (non puoi essere incompatibile con te stesso)
        - Gli studenti già presenti nella stessa sezione vincoli
        - Gli studenti già presenti nella sezione OPPOSTA (anti-contraddizione):
          se uno studente è già incompatibile, NON può essere anche affine,
          e viceversa

        Args:
            tipo_vincolo: "incompatibilita" o "affinita"

        Returns:
            Lista di stringhe "Cognome Nome"
        """
        # Parti da tutti gli studenti, escludendo se stesso
        disponibili = [s for s in self._tutti_studenti if s != self.nome_completo]

        # Rimuovi quelli già usati nella sezione CORRENTE
        # (es: se sto aggiungendo un'incompatibilità, escludi chi è già incompatibile)
        righe_stessa_sezione = (
            self._righe_incompatibilita if tipo_vincolo == "incompatibilita"
            else self._righe_affinita
        )
        gia_usati_stessa = {riga.get_studente() for riga in righe_stessa_sezione}

        # Rimuovi quelli già usati nella sezione OPPOSTA (anti-contraddizione)
        # (es: se sto aggiungendo un'incompatibilità, escludi chi è già affine)
        righe_sezione_opposta = (
            self._righe_affinita if tipo_vincolo == "incompatibilita"
            else self._righe_incompatibilita
        )
        gia_usati_opposta = {riga.get_studente() for riga in righe_sezione_opposta}

        # Unisci le due esclusioni e filtra
        tutti_esclusi = gia_usati_stessa | gia_usati_opposta
        disponibili = [s for s in disponibili if s not in tutti_esclusi]

        return disponibili

    def _aggiungi_riga_vincolo(self, tipo, studente_target=None, livello=3, notifica=True):
        """
        Aggiunge una nuova riga di vincolo (incompatibilità o affinità).

        Args:
            tipo: "incompatibilita" o "affinita"
            studente_target: "Cognome Nome" da pre-selezionare (None = primo disponibile)
            livello: livello del vincolo (1, 2, 3)
            notifica: se True, emette il segnale vincolo_modificato_signal
        """
        # Calcola gli studenti ancora disponibili
        disponibili = self._get_studenti_disponibili(tipo)

        if not disponibili:
            # Tutti gli studenti sono già vincolati (nella stessa sezione
            # o nella sezione opposta, per evitare contraddizioni)
            QMessageBox.information(
                self, "Nessuno studente disponibile",
                "Tutti gli studenti sono già presenti tra le\n"
                "incompatibilità o le affinità di questo studente."
            )
            return

        # Crea la riga vincolo, passando il tipo per le etichette livello corrette
        riga = RigaVincolo(
            disponibili,
            tipo_vincolo=tipo,
            studente_selezionato=studente_target,
            livello=livello
        )

        # Connetti i segnali della riga
        riga.vincolo_cambiato.connect(lambda: self._on_vincolo_cambiato(riga, tipo))
        riga.vincolo_rimosso.connect(lambda: self._on_vincolo_rimosso(riga, tipo))

        # Aggiungi al layout e alla lista interna
        if tipo == "incompatibilita":
            self._container_incomp.addWidget(riga)
            self._righe_incompatibilita.append(riga)
        else:
            self._container_aff.addWidget(riga)
            self._righe_affinita.append(riga)

        # Notifica il cambiamento (per la sincronizzazione bidirezionale)
        # Emette solo se il vincolo è completo: studente E livello selezionati.
        # Quando il docente clicca "Aggiungi", entrambi hanno placeholder → nessuna emissione.
        if notifica and not self._aggiornamento_programmatico:
            studente_b = riga.get_studente()
            livello_b = riga.get_livello()
            if studente_b and livello_b > 0:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, studente_b, tipo, livello_b, "aggiungi"
                )

    def _on_vincolo_cambiato(self, riga, tipo):
        """
        Slot chiamato quando l'utente cambia studente O livello in una riga.

        Gestisce tre scenari:
        1. VINCOLO INCOMPLETO: studente o livello ancora su placeholder
           → Non fare nulla (aspetta che entrambi siano selezionati)
        2. PRIMA REGISTRAZIONE: entrambi selezionati per la prima volta
           → Emetti "aggiungi" per creare il vincolo speculare
        3. VINCOLO GIÀ REGISTRATO:
           a. Cambio studente → Rimuovi vecchio speculare + Aggiungi nuovo
           b. Cambio livello → Aggiorna il livello nel vincolo speculare
        """
        if self._aggiornamento_programmatico:
            return

        nuovo_studente = riga.get_studente()
        livello = riga.get_livello()

        # --- SCENARIO 1: VINCOLO INCOMPLETO ---
        # Se il livello è 0 (placeholder attivo) o lo studente è vuoto
        # (placeholder attivo), il vincolo non è ancora valido.
        # Aggiorna solo il tracking dello studente precedente.
        if livello == 0 or not nuovo_studente:
            riga.aggiorna_precedente()
            return

        vecchio_studente = riga.get_studente_precedente()

        if not riga._registrato:
            # --- SCENARIO 2: PRIMA REGISTRAZIONE ---
            # Entrambi i ComboBox sono stati compilati per la prima volta.
            # Emetti "aggiungi" per creare il vincolo speculare.
            self.vincolo_modificato_signal.emit(
                self.nome_completo, nuovo_studente, tipo, livello, "aggiungi"
            )
            riga._registrato = True
        elif vecchio_studente != nuovo_studente:
            # --- SCENARIO 3a: CAMBIO STUDENTE (vincolo già registrato) ---
            # Rimuovi il vincolo speculare dal vecchio studente
            # e creane uno nuovo nel nuovo studente
            if vecchio_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, vecchio_studente, tipo, 0, "rimuovi"
                )
            if nuovo_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente, tipo, livello, "aggiungi"
                )
        else:
            # --- SCENARIO 3b: CAMBIO LIVELLO (stesso studente, già registrato) ---
            if nuovo_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente, tipo, livello, "modifica"
                )

        # Aggiorna il tracking dello studente precedente
        # IMPORTANTE: va fatto DOPO aver emesso i segnali, non prima!
        riga.aggiorna_precedente()

    def _on_vincolo_rimosso(self, riga, tipo):
        """
        Slot chiamato quando l'utente clicca ➖ per rimuovere un vincolo.
        Rimuove la riga e notifica per la sincronizzazione bidirezionale.
        """
        # Salva i dati della riga PRIMA di rimuoverla
        studente_b = riga.get_studente()
        era_registrato = riga._registrato

        # Rimuovi dalla lista interna
        if tipo == "incompatibilita":
            if riga in self._righe_incompatibilita:
                self._righe_incompatibilita.remove(riga)
        else:
            if riga in self._righe_affinita:
                self._righe_affinita.remove(riga)

        # Rimuovi il widget dall'interfaccia
        riga.setParent(None)
        riga.deleteLater()

        # Notifica per la sincronizzazione bidirezionale.
        # Emette "rimuovi" SOLO se il vincolo era stato effettivamente registrato
        # (cioè entrambi i ComboBox erano stati compilati). Se la riga aveva
        # ancora un placeholder, il vincolo speculare non esiste → niente da rimuovere.
        if not self._aggiornamento_programmatico and studente_b and era_registrato:
            self.vincolo_modificato_signal.emit(
                self.nome_completo, studente_b, tipo, 0, "rimuovi"
            )

    # ----- METODI PUBBLICI per la sincronizzazione bidirezionale -----

    def aggiungi_vincolo_programmatico(self, tipo, studente_target, livello):
        """
        Aggiunge un vincolo in modo programmatico (senza triggerare la sincronizzazione).
        Usato dalla sincronizzazione bidirezionale per aggiungere il vincolo speculare.

        Args:
            tipo: "incompatibilita" o "affinita"
            studente_target: "Cognome Nome" dello studente
            livello: livello del vincolo
        """
        # Verifica che il vincolo non esista già
        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        for riga in righe:
            if riga.get_studente() == studente_target:
                return  # Già presente, non duplicare

        # Aggiungi senza notificare (notifica=False)
        self._aggiornamento_programmatico = True
        self._aggiungi_riga_vincolo(tipo, studente_target, livello, notifica=False)
        self._aggiornamento_programmatico = False

    def modifica_vincolo_programmatico(self, tipo, studente_target, nuovo_livello):
        """
        Modifica il livello di un vincolo esistente in modo programmatico.

        Args:
            tipo: "incompatibilita" o "affinita"
            studente_target: "Cognome Nome" dello studente
            nuovo_livello: nuovo livello (1, 2, 3)
        """
        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        self._aggiornamento_programmatico = True
        for riga in righe:
            if riga.get_studente() == studente_target:
                # Il livello va impostato come indice (0, 1, 2) perché
                # le voci del ComboBox sono etichette descrittive
                # ("1 — Leggera", "2 — Media", ecc.)
                indice = max(0, min(int(nuovo_livello) - 1, 2))
                riga.combo_livello.setCurrentIndex(indice)
                break
        self._aggiornamento_programmatico = False

    def rimuovi_vincolo_programmatico(self, tipo, studente_target):
        """
        Rimuove un vincolo in modo programmatico (senza triggerare la sincronizzazione).

        Args:
            tipo: "incompatibilita" o "affinita"
            studente_target: "Cognome Nome" dello studente
        """
        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        self._aggiornamento_programmatico = True
        for riga in list(righe):  # list() per evitare modifica durante iterazione
            if riga.get_studente() == studente_target:
                righe.remove(riga)
                riga.setParent(None)
                riga.deleteLater()
                break
        self._aggiornamento_programmatico = False

    def get_dati(self):
        """
        Restituisce tutti i dati dello studente come dizionario.

        Returns:
            dict con chiavi: cognome, nome, genere, posizione, incompatibilita, affinita
        """
        incomp = {}
        for riga in self._righe_incompatibilita:
            studente = riga.get_studente()
            livello = riga.get_livello()
            # Salva solo vincoli completi: studente selezionato E livello scelto
            # (livello == 0 significa che il placeholder è ancora attivo)
            if studente and livello > 0:
                incomp[studente] = livello

        aff = {}
        for riga in self._righe_affinita:
            studente = riga.get_studente()
            livello = riga.get_livello()
            # Salva solo vincoli completi (stesso controllo)
            if studente and livello > 0:
                aff[studente] = livello

        return {
            "cognome": self.cognome,
            "nome": self.nome,
            "sesso": self.combo_genere.currentText(),
            # Converte l'etichetta visualizzata nel valore interno
            # es: "PRIMA — VINCOLANTE" → "PRIMA"
            "posizione": self._mappa_posizioni.get(
                self.combo_posizione.currentText(), "NORMALE"
            ),
            "incompatibilita": incomp,
            "affinita": aff
        }

    def _on_genere_cambiato(self, nuovo_valore):
        """
        Gestisce il cambio di selezione nel ComboBox genere.
        Se il docente seleziona M o F (dopo il placeholder "---"),
        rimuove il placeholder e ripristina lo stile normale.
        Aggiorna anche il colore della scheda.
        """
        if nuovo_valore in ("M", "F"):
            # Rimuovi il placeholder dalla lista se presente
            idx_placeholder = self.combo_genere.findText(PLACEHOLDER_GENERE)
            if idx_placeholder >= 0:
                self.combo_genere.removeItem(idx_placeholder)
            # Ripristina lo stile normale (rimuovi bordo arancione)
            self.combo_genere.setStyleSheet("")

        # Aggiorna il colore della scheda in base al genere scelto
        self._aggiorna_stile_genere(nuovo_valore)

    def genere_impostato(self):
        """
        Restituisce True se il docente ha selezionato un genere valido (M o F).
        Restituisce False se il placeholder '---' è ancora attivo.
        """
        return self.combo_genere.currentText() in ("M", "F")

    def _aggiorna_stile_genere(self, sesso):
        """
        Applica lo stile visivo della scheda in base al genere.
        - M → bordo e titolo azzurro
        - F → bordo e titolo rosa
        - Placeholder/altro → bordo grigio neutro con accento arancione

        Args:
            sesso: "M", "F" o PLACEHOLDER_GENERE
        """
        if sesso == "M":
            # Maschio: colori azzurri (dal tema attivo)
            colore_bordo     = C("scheda_M_bordo")
            colore_titolo_bg = C("scheda_M_titolo_sf")
            colore_titolo_txt = C("scheda_M_titolo_txt")
            colore_sfondo    = C("scheda_M_sf")
        elif sesso == "F":
            # Femmina: colori rosa (dal tema attivo)
            colore_bordo     = C("scheda_F_bordo")
            colore_titolo_bg = C("scheda_F_titolo_sf")
            colore_titolo_txt = C("scheda_F_titolo_txt")
            colore_sfondo    = C("scheda_F_sf")
        else:
            # Genere non impostato: colori arancioni (dal tema attivo)
            colore_bordo     = C("scheda_X_bordo")
            colore_titolo_bg = C("scheda_X_titolo_sf")
            colore_titolo_txt = C("scheda_X_titolo_txt")
            colore_sfondo    = C("scheda_X_sf")

        self.setStyleSheet(f"""
            QGroupBox {{
                font-size: 14px;
                font-weight: bold;
                border: 2px solid {colore_bordo};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
                background-color: {colore_sfondo};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 12px;
                background-color: {colore_titolo_bg};
                border-radius: 4px;
                color: {colore_titolo_txt};
            }}
        """)

    # ----- Collassamento -----

    def aggiorna_tema(self):
        """
        Riapplica tutti gli stili della scheda al tema attivo.
        Chiamato da EditorStudentiWidget.aggiorna_tema() al cambio tema.
        """
        # Aggiorna il colore della scheda (bordo + titolo) in base al genere attuale
        sesso_attuale = self.combo_genere.currentText()
        self._aggiorna_stile_genere(sesso_attuale)

        # Aggiorna i separatori orizzontali
        stile_sep = f"background-color: {C('editor_sep')};"
        if hasattr(self, '_sep1'):
            self._sep1.setStyleSheet(stile_sep)
        if hasattr(self, '_sep2'):
            self._sep2.setStyleSheet(stile_sep)

        # Aggiorna il bottone "Aggiungi incompatibilità"
        if hasattr(self, '_btn_aggiungi_incomp'):
            self._btn_aggiungi_incomp.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("editor_btn_incomp_sf")};
                    color: {C("editor_btn_incomp_txt")};
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background-color: {C("editor_btn_incomp_hover")}; }}
            """)

        # Aggiorna il bottone "Aggiungi affinità"
        if hasattr(self, '_btn_aggiungi_aff'):
            self._btn_aggiungi_aff.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("editor_btn_aff_sf")};
                    color: {C("editor_btn_aff_txt")};
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background-color: {C("editor_btn_aff_hover")}; }}
            """)

        # Aggiorna tutte le righe vincolo (ComboBox studente)
        for riga in self._righe_incompatibilita + self._righe_affinita:
            riga.aggiorna_tema()

    def mousePressEvent(self, event):
        """Gestisce il click sul titolo per collassare/espandere."""
        # Verifica che il click sia nella zona del titolo (parte alta)
        if event.position().y() < 24:
            self._espanso = not self._espanso
            self._contenitore.setVisible(self._espanso)
            # Aggiorna l'icona nel titolo
            icona = "📋" if self._espanso else "▶"
            self.setTitle(f"{icona} {self.nome_completo}")
        super().mousePressEvent(event)


# =============================================================================
# CLASSE PRINCIPALE: EditorStudentiWidget
# =============================================================================
class EditorStudentiWidget(QWidget):
    """
    Widget principale dell'editor studenti.
    Può essere usato come:
    - Tab aggiuntiva nell'applicazione principale (addTab)
    - Widget in una finestra separata (QDialog/QMainWindow)

    Funzionalità:
    - Carica file BASE (solo Cognome;Nome;M/F) o COMPLETO (6 campi)
    - Auto-rileva il formato del file
    - Genera schede interattive per ogni studente
    - Sincronizza automaticamente i vincoli bidirezionali
    - Preview del file generato
    - Esporta file .txt nel formato standard
    """

    # Segnale emesso quando l'Editor carica un nuovo file (tramite il suo bottone).
    # Il pannello principale lo riceve e resetta i propri dati (self.studenti),
    # evitando la "mescolanza" tra classi diverse caricate da percorsi diversi.
    file_cambiato_signal = Signal()

    # Segnale emesso quando l'Editor CHIUDE il file corrente (bottone "Chiudi file").
    # Il pannello principale lo riceve e riporta la label alla dicitura iniziale
    # "Nessun file caricato", evitando che resti un messaggio ambiguo.
    file_chiuso_signal = Signal()

    # Segnale emesso quando un docente cambia il genere di uno studente.
    # Il pannello principale lo riceve e aggiorna la label "Genere da completare"
    # in tempo reale, senza che il docente debba tornare a cliccare "Seleziona file classe (.txt)".
    genere_cambiato_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Dati interni ---
        # Lista di tutte le schede studente (oggetti SchedaStudente)
        self._schede_studenti = []
        # Lista ordinata di tutti i nomi "Cognome Nome" (per i ComboBox)
        self._lista_nomi = []
        # Nome del file caricato (per l'header del .txt generato)
        self._nome_file_caricato = ""
        # Percorso COMPLETO del file caricato (per auto-salvataggio)
        self._percorso_file_caricato = ""

        # --- Flag anti-ricorsione per sincronizzazione bidirezionale ---
        self._sincronizzazione_in_corso = False

        # --- Flag per tracciare se ci sono modifiche non salvate ---
        # Diventa True quando si carica un file o si modifica qualcosa.
        # Torna False quando si esporta con successo.
        self._modifiche_non_salvate = False

        # --- Flag per tracciare se l'Editor ha applicato correzioni ---
        # Diventa True se _check_coerenza_bidirezionale() ha aggiunto vincoli
        # o se il formato era BASE (posizione da completare).
        # Usato dal pannello principale per decidere se auto-salvare.
        self._correzioni_applicate = False

        # --- Costruzione interfaccia ---
        self._costruisci_ui()

    def aggiorna_tema(self):
        """
        Riapplica tutti gli stili dell'editor al tema attivo.
        Chiamato dalla finestra principale al cambio tema.
        """
        # Aggiorna ScrollArea
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("editor_scroll_sf")};
            }}
        """)

        # Aggiorna label informativa
        self.label_info.setStyleSheet(
            f"color: {C('editor_info_txt')}; font-style: italic; font-size: 14px;"
        )

        # Aggiorna bottoni Comprimi/Espandi
        stile_btn_neutro = f"""
            QPushButton {{
                background-color: {C("btn_sfondo")};
                color: {C("testo_principale")};
                font-size: 12px;
                border-radius: 5px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: {C("btn_hover")}; }}
            QPushButton:disabled {{
                background-color: {C("btn_disabilitato_sf")};
                color: {C("btn_disabilitato_txt")};
            }}
        """
        self.btn_comprimi.setStyleSheet(stile_btn_neutro)
        self.btn_espandi.setStyleSheet(stile_btn_neutro)

        # Aggiorna ogni scheda studente
        for scheda in self._schede_studenti:
            scheda.aggiorna_tema()

    def _costruisci_ui(self):
        """Costruisce l'interfaccia dell'editor."""

        layout_principale = QVBoxLayout(self)
        layout_principale.setSpacing(10)

        # ==============================================
        # HEADER: Titolo + bottone caricamento
        # ==============================================
        header = QHBoxLayout()

        # Titolo
        titolo = QLabel("✏️ Editor studenti")
        titolo.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {C('editor_titolo_txt')};")
        header.addWidget(titolo)

        header.addStretch()

        # Bottone "Comprimi tutti" — comprime tutte le schede studente
        self.btn_comprimi = QPushButton("🔽 Comprimi tutti")
        self.btn_comprimi.setMinimumHeight(36)
        self.btn_comprimi.setEnabled(False)
        self.btn_comprimi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_sfondo")};
                color: {C("testo_principale")};
                font-size: 12px;
                border-radius: 5px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: {C("btn_hover")}; }}
            QPushButton:disabled {{ background-color: {C("btn_disabilitato_sf")}; color: {C("btn_disabilitato_txt")}; }}
        """)
        self.btn_comprimi.setToolTip("Comprimi tutte le schede per una visione d'insieme")
        self.btn_comprimi.clicked.connect(self._comprimi_tutti)
        header.addWidget(self.btn_comprimi)

        # Bottone "Espandi tutti" — espande tutte le schede studente
        self.btn_espandi = QPushButton("🔼 Espandi tutti")
        self.btn_espandi.setMinimumHeight(36)
        self.btn_espandi.setEnabled(False)
        self.btn_espandi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_sfondo")};
                color: {C("testo_principale")};
                font-size: 12px;
                border-radius: 5px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background-color: {C("btn_hover")}; }}
            QPushButton:disabled {{ background-color: {C("btn_disabilitato_sf")}; color: {C("btn_disabilitato_txt")}; }}
        """)
        self.btn_espandi.setToolTip("Espandi tutte le schede per vedere i dettagli")
        self.btn_espandi.clicked.connect(self._espandi_tutti)
        header.addWidget(self.btn_espandi)

        header.addSpacing(10)

        # Bottone carica file
        self.btn_carica = QPushButton("📝 Carica classe da modificare (.txt)")
        self.btn_carica.setMinimumHeight(40)
        self.btn_carica.setStyleSheet("""
            QPushButton {
                background-color: #1565c0;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #0d47a1; }
        """)
        self.btn_carica.setToolTip("Carica un file .txt per modificare posizione e vincoli degli studenti")
        self.btn_carica.clicked.connect(self._carica_file)
        header.addWidget(self.btn_carica)

        layout_principale.addLayout(header)

        # Label informativa (mostra nome file caricato e numero studenti)
        self.label_info = QLabel("Nessun file caricato. Clicca  '📝 Carica classe da modificare (.txt)' per iniziare.")
        self.label_info.setStyleSheet(f"color: {C('editor_info_txt')}; font-style: italic; font-size: 14px;")
        layout_principale.addWidget(self.label_info)

        # ==============================================
        # AREA PRINCIPALE: ScrollArea con le schede studenti
        # ==============================================
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("editor_scroll_sf")};
            }}
        """)

        # Widget interno alla scroll area
        self.widget_scroll = QWidget()
        self.layout_schede = QVBoxLayout(self.widget_scroll)
        self.layout_schede.setSpacing(12)
        self.layout_schede.setContentsMargins(10, 10, 10, 10)

        # Messaggio iniziale (placeholder)
        self._label_placeholder = QLabel(
            "📝 Carica un file .txt per iniziare a modificare posizione e vincoli degli studenti.\n\n"
            "Formati supportati:\n"
            "• File BASE: 'Cognome;Nome;M/F' (uno per riga)\n"
            "• File COMPLETO: 'Cognome;Nome;Genere;Posizione;Incompatibilità;Affinità'"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet("color: #757575; font-size: 15px; padding: 40px;")
        self.layout_schede.addWidget(self._label_placeholder)

        self.layout_schede.addStretch()
        self.scroll_area.setWidget(self.widget_scroll)
        layout_principale.addWidget(self.scroll_area)

        # ==============================================
        # FOOTER: Bottoni Preview ed Esporta
        # ==============================================
        footer = QHBoxLayout()
        footer.setSpacing(12)

        # Bottone Preview
        self.btn_preview = QPushButton("👁️ Preview file generato")
        self.btn_preview.setMinimumHeight(45)
        self.btn_preview.setEnabled(False)
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background-color: #6a1b9a;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #4a148c; }
            QPushButton:disabled { background-color: #616161; color: #9e9e9e; }
        """)
        self.btn_preview.setToolTip("Mostra un'anteprima del file .txt che verrà generato")
        self.btn_preview.clicked.connect(self._mostra_preview)
        footer.addWidget(self.btn_preview)

        # Bottone Esporta
        self.btn_esporta = QPushButton("💾 Salva file CLASSE completo (.txt)")
        self.btn_esporta.setMinimumHeight(45)
        self.btn_esporta.setEnabled(False)
        self.btn_esporta.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #1b5e20; }
            QPushButton:disabled { background-color: #616161; color: #9e9e9e; }
        """)
        self.btn_esporta.setToolTip("Salva il file completo con tutti i dati e vincoli degli studenti")
        self.btn_esporta.clicked.connect(self._esporta_file)
        footer.addWidget(self.btn_esporta)

        footer.addStretch()

        # Bottone Chiudi (a destra) — chiude/scarica il file corrente
        self.btn_chiudi = QPushButton("✖ Chiudi file")
        self.btn_chiudi.setMinimumHeight(45)
        self.btn_chiudi.setEnabled(False)
        self.btn_chiudi.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover { background-color: #b71c1c; }
            QPushButton:disabled { background-color: #616161; color: #9e9e9e; }
        """)
        self.btn_chiudi.setToolTip("Chiudi il file corrente (chiederà conferma se ci sono modifiche)")
        self.btn_chiudi.clicked.connect(self._chiudi_editor)
        footer.addWidget(self.btn_chiudi)

        layout_principale.addLayout(footer)

    # =========================================================================
    # CARICAMENTO FILE
    # =========================================================================

    def _carica_file(self):
        """
        Apre un QFileDialog per selezionare il file .txt e lo carica.
        Auto-rileva se è formato BASE o COMPLETO.
        Se ci sono modifiche non salvate, chiede conferma prima.
        """
        # Se ci sono modifiche non salvate, chiedi conferma
        if self._modifiche_non_salvate:
            azione = self._conferma_chiusura()
            if azione == "salva":
                self._esporta_file()
                if self._modifiche_non_salvate:
                    return  # Salvataggio annullato, resta nell'editor
            elif azione == "annulla":
                return  # L'utente vuole restare
            # Se "esci" → prosegui col caricamento del nuovo file

        # Apri il dialog nella cartella dati/ se esiste
        cartella_dati = self._get_cartella_dati()

        percorso, _ = QFileDialog.getOpenFileName(
            self,
            "Carica classe da modificare (.txt)",
            cartella_dati,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if not percorso:
            return  # L'utente ha annullato

        # Lettura file con fallback encoding: prova UTF-8, poi Latin-1.
        # Su Windows, il Blocco Note salva in ANSI (= Latin-1) per default,
        # quindi è fondamentale avere il fallback per i docenti che
        # creano i file .txt con strumenti non configurati per UTF-8.
        # Stessa logica già presente in carica_file_da_percorso().
        try:
            with open(percorso, 'r', encoding='utf-8') as f:
                righe = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(percorso, 'r', encoding='latin-1') as f:
                    righe = f.readlines()
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile leggere il file:\n{e}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile leggere il file:\n{e}")
            return

        # Salva il nome del file (senza percorso ed estensione) per l'header
        self._nome_file_caricato = os.path.splitext(os.path.basename(percorso))[0]
        # Salva il percorso completo per eventuale auto-salvataggio
        self._percorso_file_caricato = percorso

        # Filtra le righe utili (non vuote, non commenti)
        righe_utili = []
        for riga in righe:
            riga_strip = riga.strip()
            if riga_strip and not riga_strip.startswith('#'):
                righe_utili.append(riga_strip)

        if not righe_utili:
            QMessageBox.warning(self, "File vuoto", "Il file non contiene righe utili.")
            return

        # --- AUTO-RILEVAMENTO FORMATO ---
        # Guarda il MASSIMO numero di punto e virgola su TUTTE le righe.
        # Se anche una sola riga ha 5+ separatori, il file è formato COMPLETO
        # (alcune righe potrebbero essere corrotte, ma verranno riparate).
        # Se si guardasse solo la prima riga, un file completo con la prima
        # riga corrotta verrebbe trattato come formato base → vincoli persi.
        max_separatori = max(riga.count(';') for riga in righe_utili)

        if max_separatori >= 5:
            # Formato COMPLETO: Cognome;Nome;Sesso;Posizione;Incomp;Affinità
            # Le righe con meno campi verranno completate automaticamente
            self._carica_formato_completo(righe_utili)
        elif max_separatori >= 1:
            # Formato BASE: Cognome;Nome (oppure Cognome;Nome;Sesso, ecc.)
            # I campi oltre cognome e nome vengono gestiti se presenti
            self._carica_formato_base(righe_utili)
        else:
            QMessageBox.warning(
                self, "Formato non riconosciuto",
                f"Nessuna riga contiene il separatore ';'.\n"
                "Il file deve usare il formato: 'Cognome;Nome;M/F'..."
            )
            return

        # Notifica il pannello principale che l'Editor ha caricato un nuovo file.
        # Il pannello resetta i propri dati (self.studenti) per evitare
        # mescolanza tra classi diverse.
        self.file_cambiato_signal.emit()

    def _carica_formato_base(self, righe):
        """
        Carica un file in formato BASE (solo Cognome;Nome;M/F oppure con campi parziali).
        Se il genere è presente nel file lo usa, altrimenti mostra il placeholder "---"
        per obbligare il docente a selezionarlo manualmente.

        Args:
            righe: lista di stringhe "Cognome;Nome;M/F"
        """
        studenti_dati = []

        for riga in righe:
            parti = riga.split(';')
            if len(parti) >= 2:
                cognome = parti[0].strip()
                nome = parti[1].strip()

                # Se il file ha anche il campo genere (cognome;nome;M/F)
                # lo usa, altrimenti lascia il placeholder "---"
                sesso = PLACEHOLDER_GENERE  # Default: obbliga selezione manuale
                if len(parti) >= 3 and parti[2].strip().upper() in ("M", "F"):
                    sesso = parti[2].strip().upper()

                studenti_dati.append({
                    "cognome": cognome,
                    "nome": nome,
                    "sesso": sesso,
                    "posizione": "NORMALE", # Default
                    "incompatibilita": {},
                    "affinita": {}
                })

        self._popola_editor(studenti_dati, "BASE")

    def _carica_formato_completo(self, righe):
        """
        Carica un file in formato COMPLETO (6 campi separati da ;).
        Popola le schede con i dati esistenti, poi esegue check coerenza.

        SICUREZZA: se una riga ha meno di 6 campi (es: manca un ";"),
        NON viene scartata. Viene usato un RILEVAMENTO INTELLIGENTE
        basato sul CONTENUTO dei campi per capire quali campi sono
        presenti e quali mancano, evitando che i vincoli vadano persi
        a causa dello "spostamento" dei campi.

        Args:
            righe: lista di stringhe "Cognome;Nome;Sesso;Posizione;Incomp;Affinità"
        """
        studenti_dati = []
        # Lista delle righe con problemi (per avviso all'utente)
        righe_con_problemi = []
        # Reset flag correzioni: parte da False, diventa True solo se servono
        self._correzioni_applicate = False

        # Prima passata: leggi TUTTI i nomi (anche da righe incomplete)
        # Serve per risolvere i vincoli nella seconda passata
        nomi_completi = []

        for riga in righe:
            parti = riga.split(';')
            if len(parti) >= 2:
                cognome = parti[0].strip()
                nome = parti[1].strip()
                if cognome and nome:
                    nomi_completi.append(f"{cognome} {nome}")

        # Seconda passata: leggi tutti i dati
        for riga in righe:
            parti = riga.split(';')

            # Servono ALMENO 2 campi (cognome e nome)
            if len(parti) < 2:
                righe_con_problemi.append(
                    f"• Riga ignorata (nessun dato riconoscibile): '{riga[:40]}...'"
                )
                continue

            cognome = parti[0].strip()
            nome = parti[1].strip()

            if not cognome or not nome:
                righe_con_problemi.append(
                    f"• Riga ignorata (cognome o nome vuoto): '{riga[:40]}...'"
                )
                continue

            nome_completo = f"{cognome} {nome}"
            num_campi = len(parti)

            if num_campi >= 6:
                # === RIGA COMPLETA (6+ campi): parsing posizionale standard ===
                sesso, posizione, incomp_str, aff_str = self._parsing_posizionale(
                    parti, nome_completo, righe_con_problemi
                )
            else:
                # === RIGA INCOMPLETA (<6 campi): rilevamento intelligente ===
                # Analizza il CONTENUTO di ogni campo per capire a cosa corrisponde,
                # invece di fidarsi della posizione (che è sbagliata).
                righe_con_problemi.append(
                    f"• {nome_completo}: solo {num_campi} campi "
                    f"(servono 6). Ricostruita con rilevamento intelligente."
                )
                self._correzioni_applicate = True

                sesso, posizione, incomp_str, aff_str = self._parsing_intelligente(
                    parti[2:], nome_completo, righe_con_problemi
                )

            # === PARSING DEI VINCOLI (comune a entrambi i percorsi) ===
            incomp = self._parsing_vincoli(incomp_str, nomi_completi, cognome, nome, "incomp")
            aff = self._parsing_vincoli(aff_str, nomi_completi, cognome, nome, "affinità")

            studenti_dati.append({
                "cognome": cognome,
                "nome": nome,
                "sesso": sesso,
                "posizione": posizione,
                "incompatibilita": incomp,
                "affinita": aff
            })

        self._popola_editor(studenti_dati, "COMPLETO")

        # === MOSTRA AVVISO RIGHE CON PROBLEMI ===
        if righe_con_problemi:
            testo = "\n".join(righe_con_problemi[:20])
            if len(righe_con_problemi) > 20:
                testo += f"\n\n... e altri {len(righe_con_problemi) - 20} problemi"

            QMessageBox.warning(
                self,
                "⚠️ Problemi rilevati nel file",
                f"Il file è stato caricato, ma con {len(righe_con_problemi)} "
                f"problema/i:\n\n{testo}\n\n"
                f"💡 Controlla e correggi i dati nelle schede dell'Editor."
            )

    def _parsing_posizionale(self, parti, nome_completo, righe_con_problemi):
        """
        Parsing standard per righe COMPLETE (6+ campi).
        I campi vengono letti in base alla posizione fissa:
        [0]=Cognome, [1]=Nome, [2]=Sesso, [3]=Posizione, [4]=Incomp, [5]=Affinità

        Args:
            parti: lista dei campi già splittati per ';'
            nome_completo: "Cognome Nome" per i messaggi di errore
            righe_con_problemi: lista a cui aggiungere eventuali problemi

        Returns:
            tuple: (sesso, posizione, incomp_str, aff_str)
        """
        # Campo 3: Genere
        sesso_raw = parti[2].strip().upper()
        if sesso_raw in ("M", "F"):
            sesso = sesso_raw
        else:
            sesso = PLACEHOLDER_GENERE
            if sesso_raw:
                righe_con_problemi.append(
                    f"• {nome_completo}: genere '{parti[2].strip()}' "
                    f"non valido (deve essere M o F). Da impostare."
                )
            else:
                righe_con_problemi.append(
                    f"• {nome_completo}: genere mancante. Da impostare."
                )
            self._correzioni_applicate = True

        # Campo 4: Posizione
        posizione_raw = parti[3].strip().upper()
        if posizione_raw in ("NORMALE", "PRIMA", "ULTIMA"):
            posizione = posizione_raw
        else:
            posizione = "NORMALE"
            if posizione_raw:
                righe_con_problemi.append(
                    f"• {nome_completo}: posizione '{parti[3].strip()}' "
                    f"non valida. Impostata a NORMALE."
                )

        return sesso, posizione, parti[4].strip(), parti[5].strip()

    def _parsing_intelligente(self, campi_rimanenti, nome_completo, righe_con_problemi):
        """
        Parsing intelligente per righe INCOMPLETE (<6 campi).
        Analizza il CONTENUTO di ogni campo per capire a cosa corrisponde,
        invece di fidarsi della posizione (che è sbagliata perché
        manca un campo e tutti gli altri si spostano).

        Regole di classificazione:
        - "M" o "F" → è il Genere
        - "NORMALE", "PRIMA", "ULTIMA" → è la Posizione
        - Contiene ":" (es: "Rossi Marco:3") → è un Vincolo
        - Stringa vuota → campo mancante, ignorato

        Il primo vincolo trovato diventa Incompatibilità,
        il secondo diventa Affinità.

        Args:
            campi_rimanenti: lista dei campi DOPO cognome e nome
            nome_completo: "Cognome Nome" per i messaggi di errore
            righe_con_problemi: lista a cui aggiungere eventuali problemi

        Returns:
            tuple: (sesso, posizione, incomp_str, aff_str)
        """
        sesso = PLACEHOLDER_GENERE
        posizione = "NORMALE"
        vincoli_trovati = []  # Lista ordinata dei campi vincolo

        for campo in campi_rimanenti:
            valore = campo.strip()

            if not valore:
                # Campo vuoto: uno dei campi mancanti, lo saltiamo
                continue

            valore_upper = valore.upper()

            if valore_upper in ("M", "F"):
                # È il genere
                sesso = valore_upper
            elif valore_upper in ("NORMALE", "PRIMA", "ULTIMA"):
                # È la posizione
                posizione = valore_upper
            elif ":" in valore:
                # È un campo vincolo (contiene "NomeCognome:livello")
                vincoli_trovati.append(valore)
            else:
                # Campo non riconosciuto: potrebbe essere un valore corrotto
                righe_con_problemi.append(
                    f"• {nome_completo}: campo '{valore[:30]}' non riconosciuto, ignorato."
                )

        # Assegna i vincoli trovati: il primo è incompatibilità, il secondo affinità
        incomp_str = vincoli_trovati[0] if len(vincoli_trovati) >= 1 else ""
        aff_str = vincoli_trovati[1] if len(vincoli_trovati) >= 2 else ""

        # Se il genere è ancora placeholder, segnala
        if sesso == PLACEHOLDER_GENERE:
            righe_con_problemi.append(
                f"• {nome_completo}: genere mancante. Da impostare."
            )
            self._correzioni_applicate = True

        return sesso, posizione, incomp_str, aff_str

    def _parsing_vincoli(self, vincoli_str, nomi_completi, cognome, nome, tipo_vincolo):
        """
        Converte una stringa di vincoli in un dizionario.

        Args:
            vincoli_str: es. "Rossi Marco:3,Bianchi Anna:2"
            nomi_completi: lista di tutti i nomi per verifica
            cognome, nome: dello studente corrente (per messaggi debug)
            tipo_vincolo: "incomp" o "affinità" (per messaggi debug)

        Returns:
            dict: {nome_completo: livello}
        """
        risultato = {}
        if not vincoli_str:
            return risultato

        for coppia in vincoli_str.split(','):
            coppia = coppia.strip()
            if ':' in coppia:
                rif, liv = coppia.rsplit(':', 1)
                rif = rif.strip()
                try:
                    liv = int(liv.strip())
                except ValueError:
                    liv = 3
                if rif in nomi_completi:
                    risultato[rif] = liv
                else:
                    print(f"⚠️ Vincolo {tipo_vincolo} non trovato: '{rif}' per {cognome} {nome}")

        return risultato

    def _popola_editor(self, studenti_dati, formato):
        """
        Crea tutte le schede studente nell'editor.

        Args:
            studenti_dati: lista di dict con i dati di ogni studente
            formato: "BASE" o "COMPLETO" (per il messaggio informativo)
        """
        # --- Pulisci l'editor precedente ---
        # Rimuovi tutte le schede esistenti
        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()

        # Rimuovi il placeholder se presente
        if self._label_placeholder:
            self._label_placeholder.setParent(None)
            self._label_placeholder.deleteLater()
            self._label_placeholder = None

        # Rimuovi lo stretch dal layout
        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        # --- Costruisci la lista nomi completi ---
        self._lista_nomi = [f"{s['cognome']} {s['nome']}" for s in studenti_dati]

        # --- Crea le schede studente ---
        for dati in studenti_dati:
            scheda = SchedaStudente(
                cognome=dati["cognome"],
                nome=dati["nome"],
                tutti_studenti=self._lista_nomi,
                sesso=dati["sesso"],
                posizione=dati["posizione"],
                incompatibilita=dati["incompatibilita"],
                affinita=dati["affinita"]
            )

            # Connetti il segnale di modifica vincolo alla sincronizzazione
            scheda.vincolo_modificato_signal.connect(self._sincronizza_vincolo)

            # Connetti il cambio genere al segnale dell'Editor,
            # così il pannello principale può aggiornare la label in tempo reale.
            # In più, segna il file come "modificato" per il popup di conferma.
            scheda.combo_genere.currentTextChanged.connect(
                lambda _: (
                    self._segna_modificato(),
                    self.genere_cambiato_signal.emit()
                )
            )

            # Connetti il cambio posizione → segna il file come "modificato"
            scheda.combo_posizione.currentTextChanged.connect(
                lambda _: self._segna_modificato()
            )

            self.layout_schede.addWidget(scheda)
            self._schede_studenti.append(scheda)

        # Stretch finale per spingere le schede in alto
        self.layout_schede.addStretch()

        # Abilita i bottoni preview/esporta, espandi/comprimi e chiudi
        self.btn_preview.setEnabled(True)
        self.btn_esporta.setEnabled(True)
        self.btn_espandi.setEnabled(True)
        self.btn_comprimi.setEnabled(True)
        self.btn_chiudi.setEnabled(True)

        # Segna modifiche non salvate SOLO se ci sono effettive correzioni.
        # Se il file era già perfetto (formato COMPLETO senza problemi),
        # il flag resta False → nessun popup alla chiusura.
        # Per formato BASE, ci sono sempre modifiche (conversione a 6 campi).
        # Per formato COMPLETO, il flag viene impostato da:
        #   - _carica_formato_completo() se ci sono righe problematiche
        #   - _check_coerenza_bidirezionale() se aggiunge vincoli

        # Segnala se il formato richiede correzioni
        # BASE → il file verrà convertito in formato completo (sempre una correzione)
        # COMPLETO → le correzioni vengono rilevate altrove
        if formato == "BASE":
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True
        else:
            # Per COMPLETO: _correzioni_applicate potrebbe essere già True
            # se _carica_formato_completo ha trovato righe problematiche.
            # Se _check_coerenza aggiunge vincoli, lo imposterà.
            # Se nessuno lo imposta → file era perfetto → niente popup.
            self._modifiche_non_salvate = self._correzioni_applicate

        # Aggiorna la label informativa con dettaglio formato
        if formato == "BASE":
            # Formato BASE = Cognome;Nome;Genere → mancano posizione e vincoli
            descrizione_formato = "formato BASE — aggiungi posizione, incompatibilità e affinità"
        else:
            # Formato COMPLETO = tutti e 6 i campi presenti
            descrizione_formato = "formato COMPLETO"

        self.label_info.setText(
            f"' 📂 {self._nome_file_caricato}.txt' — "
            f"{len(studenti_dati)} studenti caricati ({descrizione_formato})"
        )
        self.label_info.setStyleSheet("color: #66bb6a; font-style: normal; font-size: 12px;")

        # --- Check coerenza bidirezionale (solo per formato COMPLETO) ---
        if formato == "COMPLETO":
            self._check_coerenza_bidirezionale()

    # =========================================================================
    # ESPANDI / COMPRIMI TUTTE LE SCHEDE
    # =========================================================================

    def _espandi_tutti(self):
        """Espande tutte le schede studente (mostra i dettagli di ognuno)."""
        for scheda in self._schede_studenti:
            scheda._espanso = True
            scheda._contenitore.setVisible(True)
            scheda.setTitle(f"📋 {scheda.nome_completo}")

    def _comprimi_tutti(self):
        """Comprime tutte le schede studente (mostra solo i titoli)."""
        for scheda in self._schede_studenti:
            scheda._espanso = False
            scheda._contenitore.setVisible(False)
            scheda.setTitle(f"▶ {scheda.nome_completo}")

    # =========================================================================
    # TRACKING MODIFICHE NON SALVATE
    # =========================================================================

    def _segna_modificato(self):
        """
        Segna il file come "modificato" dal docente.
        Viene chiamato ogni volta che l'utente cambia genere, posizione
        o vincoli di uno studente. Il flag attiva il popup di conferma
        quando si tenta di chiudere il file o l'applicazione senza salvare.
        """
        self._modifiche_non_salvate = True

    # =========================================================================
    # SINCRONIZZAZIONE BIDIREZIONALE
    # =========================================================================

    def _sincronizza_vincolo(self, studente_a, studente_b, tipo, livello, azione):
        """
        Sincronizza un vincolo in modo bidirezionale.
        Se A→B viene aggiunto/modificato/rimosso, la stessa operazione
        viene applicata automaticamente a B→A.

        PREVENZIONE LOOP: usa il flag _sincronizzazione_in_corso
        per bloccare la ricorsione infinita.

        Args:
            studente_a: "Cognome Nome" dello studente sorgente
            studente_b: "Cognome Nome" dello studente target
            tipo: "incompatibilita" o "affinita"
            livello: livello del vincolo (intero)
            azione: "aggiungi", "modifica" o "rimuovi"
        """
        # --- BLOCCO RICORSIONE ---
        if self._sincronizzazione_in_corso:
            return

        # L'utente ha modificato un vincolo → segna il file come "modificato"
        # così il popup di conferma comparirà alla chiusura
        self._segna_modificato()

        self._sincronizzazione_in_corso = True
        try:
            # Trova la scheda dello studente B (target)
            scheda_b = self._trova_scheda(studente_b)
            if not scheda_b:
                print(f"⚠️ Sincronizzazione: scheda '{studente_b}' non trovata")
                return

            # Esegui l'operazione speculare su B→A
            if azione == "aggiungi":
                scheda_b.aggiungi_vincolo_programmatico(tipo, studente_a, livello)
            elif azione == "modifica":
                scheda_b.modifica_vincolo_programmatico(tipo, studente_a, livello)
            elif azione == "rimuovi":
                scheda_b.rimuovi_vincolo_programmatico(tipo, studente_a)
        finally:
            # --- SBLOCCO RICORSIONE (sempre, anche se c'è un'eccezione) ---
            self._sincronizzazione_in_corso = False

    def _trova_scheda(self, nome_completo):
        """
        Cerca una scheda studente per nome completo.

        Args:
            nome_completo: "Cognome Nome"

        Returns:
            SchedaStudente o None
        """
        for scheda in self._schede_studenti:
            if scheda.nome_completo == nome_completo:
                return scheda
        return None

    def _check_coerenza_bidirezionale(self):
        """
        Controlla la coerenza bidirezionale dopo il caricamento di un file COMPLETO.
        Se A ha un vincolo con B, ma B non ha il vincolo speculare con A,
        lo aggiunge automaticamente e mostra un riepilogo all'utente.
        """
        vincoli_aggiunti = []

        for scheda in self._schede_studenti:
            dati = scheda.get_dati()

            # Controlla ogni incompatibilità
            for target, livello in dati["incompatibilita"].items():
                scheda_target = self._trova_scheda(target)
                if scheda_target:
                    dati_target = scheda_target.get_dati()
                    if scheda.nome_completo not in dati_target["incompatibilita"]:
                        # Vincolo mancante! Aggiungilo
                        scheda_target.aggiungi_vincolo_programmatico(
                            "incompatibilita", scheda.nome_completo, livello
                        )
                        vincoli_aggiunti.append(
                            f"⛔ {target} ← {scheda.nome_completo} (livello {livello})"
                        )

            # Controlla ogni affinità
            for target, livello in dati["affinita"].items():
                scheda_target = self._trova_scheda(target)
                if scheda_target:
                    dati_target = scheda_target.get_dati()
                    if scheda.nome_completo not in dati_target["affinita"]:
                        scheda_target.aggiungi_vincolo_programmatico(
                            "affinita", scheda.nome_completo, livello
                        )
                        vincoli_aggiunti.append(
                            f"💚 {target} ← {scheda.nome_completo} (livello {livello})"
                        )

        # Mostra il riepilogo all'utente se sono stati aggiunti vincoli
        if vincoli_aggiunti:
            # Segnala che sono state applicate correzioni (per auto-salvataggio)
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True

            msg = (
                f"Sono stati aggiunti {len(vincoli_aggiunti)} vincoli mancanti "
                "per garantire la bidirezionalità:\n\n"
            )
            # Mostra max 15 vincoli per non creare un popup gigantesco
            for v in vincoli_aggiunti[:15]:
                msg += f"  {v}\n"
            if len(vincoli_aggiunti) > 15:
                msg += f"\n  ... e altri {len(vincoli_aggiunti) - 15}"

            QMessageBox.information(self, "Coerenza bidirezionale", msg)

    # =========================================================================
    # CHIUSURA E CONFERMA SALVATAGGIO
    # =========================================================================

    def _chiudi_editor(self):
        """
        Chiamato dal pulsante "Chiudi": scarica il file corrente
        dall'editor (NON chiude il programma). Mostra un popup di
        conferma se ci sono modifiche non salvate.
        """
        if self._modifiche_non_salvate:
            # Ci sono modifiche: chiedi conferma
            azione = self._conferma_chiusura()
            if azione == "salva":
                # L'utente vuole salvare prima di chiudere
                self._esporta_file()
                # Se dopo l'export il flag è ancora True, l'utente ha annullato il salvataggio
                if self._modifiche_non_salvate:
                    return  # Non chiudere
                self._resetta_editor()
            elif azione == "esci":
                # L'utente vuole uscire senza salvare
                self._resetta_editor()
            else:
                # L'utente ha annullato → non fare nulla
                return
        else:
            # Nessuna modifica non salvata, chiudi direttamente
            self._resetta_editor()

    def _conferma_chiusura(self):
        """
        Mostra un popup con 3 opzioni quando l'utente cerca di chiudere
        con modifiche non salvate.

        Returns:
            "salva" → l'utente vuole salvare prima
            "esci" → l'utente vuole uscire senza salvare
            "annulla" → l'utente vuole restare nell'editor
        """
        dialog = QMessageBox(self)
        dialog.setWindowTitle("⚠️ Modifiche non salvate")
        dialog.setIcon(QMessageBox.Warning)
        # Mostra il nome del file per chiarezza
        nome_file = self._nome_file_caricato or "sconosciuto"
        dialog.setText(
            f"⚠️ Hai modificato i dati di '{nome_file}' nell'Editor\n"
            f"(vincoli, genere, posizione...) ma NON hai ancora\n"
            f"salvato il file '{nome_file}.txt' su disco.\n\n"
            f"Se prosegui senza salvare, tutte le modifiche\n"
            f"fatte nell'Editor andranno PERSE.\n\n"
            f"Cosa vuoi fare?"
        )

        # Crea i 3 bottoni personalizzati
        btn_salva = dialog.addButton("💾 Salva ed esci", QMessageBox.AcceptRole)
        btn_esci = dialog.addButton("🚪 Esci senza salvare", QMessageBox.DestructiveRole)
        btn_annulla = dialog.addButton("↩️ Annulla", QMessageBox.RejectRole)

        dialog.setDefaultButton(btn_annulla)
        # Se il docente chiude con la X, equivale ad "Annulla" (nessuna azione)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()

        bottone_cliccato = dialog.clickedButton()
        if bottone_cliccato == btn_salva:
            return "salva"
        elif bottone_cliccato == btn_esci:
            return "esci"
        else:
            return "annulla"

    def _resetta_editor(self):
        """
        Riporta l'editor allo stato iniziale: rimuove tutte le schede,
        disabilita i bottoni, mostra il placeholder.
        Chiamato dopo una chiusura confermata.
        """
        # Rimuovi tutte le schede studente
        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()
        self._nome_file_caricato = ""
        self._percorso_file_caricato = ""
        self._modifiche_non_salvate = False
        self._correzioni_applicate = False

        # Pulisci il layout
        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()

        # Ricrea il placeholder
        self._label_placeholder = QLabel(
            "📝 Carica un file .txt per iniziare a modificare gli studenti.\n\n"
            "Formati supportati:\n"
            "• File BASE: 'Cognome;Nome;M/F' (uno per riga)\n"
            "• File COMPLETO: 'Cognome;Nome;Genere;Posizione;Incompatibilità;Affinità'"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet("color: #757575; font-size: 13px; padding: 40px;")
        self.layout_schede.addWidget(self._label_placeholder)
        self.layout_schede.addStretch()

        # Disabilita tutti i bottoni
        self.btn_preview.setEnabled(False)
        self.btn_esporta.setEnabled(False)
        self.btn_espandi.setEnabled(False)
        self.btn_comprimi.setEnabled(False)
        self.btn_chiudi.setEnabled(False)

        # Aggiorna la label informativa
        self.label_info.setText("Nessun file caricato. Clicca '📝 Carica classe da modificare (.txt)' per iniziare.")
        self.label_info.setStyleSheet("color: #757575; font-style: italic; font-size: 12px;")

        # Notifica il pannello principale che l'Editor ha chiuso il file,
        # così la label "Nuova classe caricata nell'Editor..." torna allo stato iniziale
        self.file_chiuso_signal.emit()

    def richiedi_conferma_chiusura(self):
        """
        Metodo PUBBLICO chiamato dalla finestra principale quando
        l'utente clicca la X della GUI. Restituisce True se è OK
        chiudere (nessuna modifica o utente ha confermato), False
        se l'utente vuole restare.

        Returns:
            bool: True se si può chiudere, False se bloccare la chiusura
        """
        if not self._modifiche_non_salvate:
            return True  # Nessuna modifica, ok chiudere

        azione = self._conferma_chiusura()
        if azione == "salva":
            self._esporta_file()
            # Se il flag è ancora True, il salvataggio è stato annullato
            return not self._modifiche_non_salvate
        elif azione == "esci":
            return True  # L'utente ha scelto di uscire senza salvare
        else:
            return False  # L'utente ha annullato

    # =========================================================================
    # METODI PUBBLICI PER INTEGRAZIONE CON IL PANNELLO PRINCIPALE
    # =========================================================================
    # Questi metodi vengono chiamati dal pulsante "Carica classe da modificare (.txt)"
    # del pannello sinistro, per usare l'Editor come unico punto
    # di caricamento e validazione dei dati.

    def carica_file_da_percorso(self, percorso):
        """
        Carica un file .txt nell'Editor SENZA aprire il QFileDialog.
        Metodo PUBBLICO: chiamato dal pannello principale quando il docente
        usa il pulsante "Seleziona file classe (.txt)".

        Il flusso è identico a _carica_file(), ma il percorso viene
        passato dall'esterno invece che selezionato con il dialog.

        Args:
            percorso: Percorso completo al file .txt

        Returns:
            bool: True se il caricamento è riuscito, False se errore
        """
        # Se ci sono modifiche non salvate nell'Editor, chiedi conferma
        if self._modifiche_non_salvate:
            azione = self._conferma_chiusura()
            if azione == "salva":
                self._esporta_file()
                if self._modifiche_non_salvate:
                    return False  # Salvataggio annullato
            elif azione == "annulla":
                return False  # L'utente vuole restare

        # Leggi il file
        try:
            with open(percorso, 'r', encoding='utf-8') as f:
                righe = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(percorso, 'r', encoding='latin-1') as f:
                    righe = f.readlines()
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile leggere il file:\n{e}")
                return False
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile leggere il file:\n{e}")
            return False

        # Salva il nome del file (senza percorso ed estensione)
        self._nome_file_caricato = os.path.splitext(os.path.basename(percorso))[0]
        # Salva il percorso completo per eventuale auto-salvataggio
        self._percorso_file_caricato = percorso

        # Filtra le righe utili (non vuote, non commenti)
        righe_utili = []
        for riga in righe:
            riga_strip = riga.strip()
            if riga_strip and not riga_strip.startswith('#'):
                righe_utili.append(riga_strip)

        if not righe_utili:
            QMessageBox.warning(self, "File vuoto", "Il file non contiene righe utili.")
            return False

        # --- AUTO-RILEVAMENTO FORMATO (stessa logica di _carica_file) ---
        # Guarda il MASSIMO numero di punto e virgola su TUTTE le righe.
        # Se anche una sola riga ha 5+ separatori → formato COMPLETO.
        max_separatori = max(riga.count(';') for riga in righe_utili)

        if max_separatori >= 5:
            self._carica_formato_completo(righe_utili)
        elif max_separatori >= 1:
            self._carica_formato_base(righe_utili)
        else:
            QMessageBox.warning(
                self, "Formato non riconosciuto",
                f"Nessuna riga contiene il separatore ';'.\n"
                "Il file deve usare il formato: 'Cognome;Nome;M/F'..."
            )
            return False

        return True  # Caricamento riuscito

    def tutti_generi_impostati(self):
        """
        Controlla se TUTTI gli studenti caricati nell'Editor
        hanno un genere valido (M o F) selezionato.

        Returns:
            bool: True se tutti hanno M o F, False se qualcuno ha ancora '---'
        """
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                return False
        return True

    def get_nomi_studenti_senza_genere(self):
        """
        Restituisce la lista dei nomi degli studenti che hanno
        ancora il placeholder '---' come genere.

        Returns:
            list: Lista di stringhe "Cognome Nome"
        """
        return [
            scheda.nome_completo
            for scheda in self._schede_studenti
            if not scheda.genere_impostato()
        ]

    def get_dati_tutti_studenti(self):
        """
        Restituisce i dati strutturati di TUTTI gli studenti caricati
        nell'Editor, con vincoli già validati e bidirezionali.

        Returns:
            list: Lista di dict, ciascuno con chiavi:
                  cognome, nome, sesso, posizione, incompatibilita, affinita

                  Restituisce lista vuota se nessuno studente caricato.
        """
        return [scheda.get_dati() for scheda in self._schede_studenti]

    def ha_studenti_caricati(self):
        """
        Restituisce True se l'Editor ha delle schede studente caricate.

        Returns:
            bool: True se ci sono schede, False se Editor è vuoto
        """
        return len(self._schede_studenti) > 0

    # =========================================================================
    # GENERAZIONE FILE .TXT
    # =========================================================================

    def _genera_txt(self):
        """
        Genera il contenuto del file .txt nel formato standard.

        Returns:
            Stringa con il contenuto completo del file
        """
        linee = []

        # --- HEADER con commenti ---
        num_studenti = len(self._schede_studenti)
        linee.append(f"# Classe: {self._nome_file_caricato} ({num_studenti} studenti)")
        linee.append("# Formato: Cognome;Nome;Genere;Posizione;Incompatibilità;Affinità")
        linee.append("# Genere: M/F (in caso di attivazione del flag \"Genere misto\" l'abbinamento [maschio][femmina] diventa un vincolo FORTE)")
        linee.append("# Posizione: PRIMA (= VINCOLO OBBLIGATORIO) / ULTIMA (= vincolo soft) / NORMALE (= vincolo neutro)")
        linee.append("# Vincoli \"Incompatibilità\": Cognome Nome:livello (1-3, dove 1= vincolo neutro, 2 = vincolo soft, 3 = VINCOLO OBBLIGATORIO)")
        linee.append("# Vincoli \"Affinità\": Cognome Nome:livello (1-3, dove 1 = vincolo neutro, 2 = vincolo soft, 3 = vincolo FORTE)")
        linee.append("")

        # --- RIGHE STUDENTI ---
        for scheda in self._schede_studenti:
            dati = scheda.get_dati()

            # Costruisci stringa incompatibilità: "Cognome Nome:livello,Cognome Nome:livello"
            incomp_parts = []
            for nome_completo, livello in dati["incompatibilita"].items():
                incomp_parts.append(f"{nome_completo}:{livello}")
            incomp_str = ",".join(incomp_parts)

            # Costruisci stringa affinità
            aff_parts = []
            for nome_completo, livello in dati["affinita"].items():
                aff_parts.append(f"{nome_completo}:{livello}")
            aff_str = ",".join(aff_parts)

            # Genera riga con ESATTAMENTE 6 campi separati da ;
            riga = (
                f"{dati['cognome']};{dati['nome']};"
                f"{dati['sesso']};{dati['posizione']};"
                f"{incomp_str};{aff_str}"
            )
            linee.append(riga)

        return "\n".join(linee)

    # =========================================================================
    # PREVIEW
    # =========================================================================

    def _mostra_preview(self):
        """
        Mostra una finestra di preview con il file .txt che verrà generato.
        Blocca se ci sono studenti senza genere impostato.
        """
        # === VALIDAZIONE: Controlla che tutti gli studenti abbiano il genere impostato ===
        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            QMessageBox.warning(
                self,
                "⚠️ Genere non impostato",
                f"I seguenti studenti hanno ancora il genere su '---':\n\n"
                f"{elenco}\n\n"
                f"Seleziona M o F per ogni studente prima di procedere."
            )
            return

        contenuto = self._genera_txt()

        # Crea il dialog di preview
        dialog = QDialog(self)
        dialog.setWindowTitle("👁️ Preview file generato")
        dialog.setMinimumSize(1300, 750)

        layout = QVBoxLayout(dialog)

        # Area di testo con il contenuto
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        # Font monospazio cross-platform: "Consolas" (Windows) con fallback
        # automatico Qt al monospazio del sistema (Linux/macOS)
        font_preview = QFont()
        font_preview.setFamily("Consolas")
        font_preview.setPointSize(11)
        font_preview.setStyleHint(QFont.Monospace)
        text_edit.setFont(font_preview)
        text_edit.setPlainText(contenuto)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                padding: 10px;
            }
        """)
        layout.addWidget(text_edit)

        # Info riepilogativa
        num_righe_dati = len(self._schede_studenti)
        label_info = QLabel(f"📊 {num_righe_dati} studenti — Ogni riga ha 6 campi separati da ';'")
        label_info.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        layout.addWidget(label_info)

        # Bottoni
        bottoni = QDialogButtonBox(QDialogButtonBox.Close)
        bottoni.rejected.connect(dialog.close)
        layout.addWidget(bottoni)

        dialog.exec()

    # =========================================================================
    # ESPORTAZIONE FILE
    # =========================================================================

    def _esporta_file(self):
        """
        Salva il file .txt generato su disco.
        Blocca se ci sono studenti senza genere impostato.
        """
        # === VALIDAZIONE: Controlla che tutti gli studenti abbiano il genere impostato ===
        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            QMessageBox.warning(
                self,
                "⚠️ Genere non impostato",
                f"I seguenti studenti hanno ancora il genere su '---':\n\n"
                f"{elenco}\n\n"
                f"Seleziona M o F per ogni studente prima di esportare."
            )
            return

        # Suggerisci il nome del file basato sul file caricato
        nome_suggerito = f"{self._nome_file_caricato}.txt" if self._nome_file_caricato else "studenti.txt"

        # --- Calcola la cartella dati/ come directory predefinita ---
        # La cartella dati/ si trova nella stessa directory del file principale
        # dell'applicazione (accanto ad assegnazione-posti.py)
        cartella_dati = self._get_cartella_dati()
        percorso_suggerito = os.path.join(cartella_dati, nome_suggerito)

        percorso, _ = QFileDialog.getSaveFileName(
            self,
            "Salva file 'ClasseXY.txt'",
            percorso_suggerito,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if not percorso:
            return  # L'utente ha annullato

        try:
            contenuto = self._genera_txt()
            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(contenuto)

            # Segna che le modifiche sono state salvate
            self._modifiche_non_salvate = False

            QMessageBox.information(
                self,
                "File salvato",
                f"✅ File salvato con successo:\n{percorso}\n\n"
                f"Contiene {len(self._schede_studenti)} studenti."
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare il file:\n{e}")

    def _get_cartella_dati(self):
        """
        Restituisce il percorso della cartella 'dati/' del progetto.
        La crea se non esiste. Compatibile con PyInstaller (.exe).

        Returns:
            Percorso assoluto della cartella dati/
        """
        if getattr(sys, 'frozen', False):
            # Modalità .exe (PyInstaller): la cartella dati/ è accanto al .exe
            cartella_progetto = os.path.dirname(sys.executable)
        else:
            # Modalità script: questo file è in modelli/ → risali di un livello
            cartella_modulo = os.path.dirname(os.path.abspath(__file__))
            cartella_progetto = os.path.dirname(cartella_modulo)
        cartella_dati = os.path.join(cartella_progetto, "dati")

        # Crea la cartella se non esiste
        os.makedirs(cartella_dati, exist_ok=True)

        return cartella_dati
