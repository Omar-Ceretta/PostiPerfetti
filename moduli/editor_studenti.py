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
import platform
import subprocess
# Importa la funzione C() per accedere ai colori del tema attivo
from moduli.tema import C

# Testo del placeholder che appare nel ComboBox prima che l'utente
# scelga uno studente. Finché è selezionato, il vincolo NON viene
# creato e la riga viene ignorata nell'esportazione.
PLACEHOLDER_VINCOLO = "⬇️ Seleziona studente..."

# Placeholder per il ComboBox del livello: appare quando l'utente
# aggiunge un nuovo vincolo, così è COSTRETTO a scegliere consapevolmente
# il livello di incompatibilità/affinità invece di accettare un default.
PLACEHOLDER_LIVELLO = "⬇️ Seleziona intensità del vincolo..."

# Placeholder per il ComboBox del genere: appare quando il genere
# NON è stato ancora selezionato (es: caricamento formato base).
# L'utente è OBBLIGATO a scegliere M o F prima di esportare.
PLACEHOLDER_GENERE = "---"

# =============================================================================
# CLASSE: ComboBox protetto dalla rotella del mouse
# =============================================================================
class ComboBoxProtetto(QComboBox):
    """
    QComboBox personalizzato con due protezioni:

    1) IGNORA la rotella del mouse a meno che il widget non abbia
       il focus esplicito (click diretto dell'utente).
       → Evita modifiche accidentali durante lo scroll della pagina.

    2) TOGLIE il focus automaticamente dopo la selezione di un valore.
       → Dopo aver scelto uno studente dal dropdown, la rotella del mouse
       torna a scorrere il pannello anziché ciclare tra i nomi.

    Tecnica: FocusPolicy su StrongFocus + segnale 'activated' → clearFocus().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # StrongFocus = il widget riceve il focus solo con un click diretto
        # (non con Tab, non con il passaggio del mouse)
        self.setFocusPolicy(Qt.StrongFocus)

        # Quando l'utente seleziona un elemento dal dropdown (click o Invio),
        # toglie il focus dal ComboBox. Così la rotellina del mouse
        # torna a scorrere il pannello invece di cambiare la selezione.
        # 'activated' si emette SOLO su azione esplicita dell'utente,
        # non quando il valore viene impostato via codice (setCurrentIndex, ecc.)
        self.activated.connect(self._rilascia_focus)

    def _rilascia_focus(self):
        """Toglie il focus dal ComboBox dopo che l'utente ha selezionato un valore."""
        self.clearFocus()

    def wheelEvent(self, event):
        """
        Intercetta la rotella del mouse.
        Se il ComboBox NON ha il focus (= l'utente non ci ha cliccato),
        ignora l'evento e lo passa al widget padre (la ScrollArea),
        così lo scroll della pagina continua normalmente.
        """
        if self.hasFocus():
            # L'utente ha cliccato sul ComboBox → la rotella funziona
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
            # Inserisci il placeholder come prima voce, così l'utente
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
            # Inserisci il placeholder come prima voce, così l'utente
            # è COSTRETTO a scegliere un livello consapevolmente.
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

        # --- Bottone "Rimuovi" vincolo ---
        btn_rimuovi = QPushButton("Rimuovi")
        btn_rimuovi.setMinimumWidth(80)
        btn_rimuovi.setFixedHeight(36)
        btn_rimuovi.setToolTip("Rimuovi questo vincolo")
        btn_rimuovi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_rosso_bg")};
                color: white;
                font-size: 12px;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background-color: {C("btn_rosso_hover")}; }}
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

    def _on_cambiato(self):
        """
        Slot interno: emette il segnale vincolo_cambiato.
        Gestisce i placeholder di ENTRAMBI i ComboBox (studente e livello):
        - Quando l'utente sceglie un nome reale, rimuove il placeholder studente
        - Quando l'utente sceglie un livello reale, rimuove il placeholder livello
        - Aggiorna lo stile visivo di entrambi i ComboBox
        """
        # --- Gestione placeholder STUDENTE ---
        testo_corrente = self.combo_studente.currentText()

        # Se l'utente ha selezionato un nome reale (non il placeholder),
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

        # Se l'utente ha selezionato un livello reale (non il placeholder),
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
        Mostra un popup di promemoria che invita l'utente a selezionare
        il livello del vincolo. Non è bloccante per il flusso di lavoro:
        basta cliccare OK e l'utente può scegliere il livello con calma.
        """
        QMessageBox.information(
            self,
            "Seleziona il livello",
            "Hai scelto lo studente\n"
            "Ora seleziona anche l'intensità del livello del vincolo\n"
            "~ 1 = Leggera   ~ 2 = Media   ~ 3 = ASSOLUTA/Forte\n\n"
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
    - Posizione (NORMALE/PRIMA/ULTIMA/FISSO)
    - Lista dinamica di incompatibilità
    - Lista dinamica di affinità

    Quando la posizione è FISSO, le sezioni incompatibilità e affinità
    vengono disabilitate. Per influenzare chi siede accanto al FISSO,
    l'insegnante imposta i vincoli sugli ALTRI studenti verso di lui.

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
            posizione: "NORMALE", "PRIMA", "ULTIMA" o "FISSO"
            incompatibilita: dict {nome_completo: livello} o None
            affinita: dict {nome_completo: livello} o None
        """
        # Il titolo del GroupBox mostra Cognome Nome
        self.cognome = cognome
        self.nome = nome
        self.nome_completo = f"{cognome} {nome}"
        super().__init__(f"📋 {self.nome_completo}", parent)

        # Stato collassabile: inizia COLLASSATO per evitare che con molti
        # studenti la lista sia troppo lunga e l'utente rischi di
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
        # (verrà aggiornato ogni volta che l'utente cambia il genere)
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
            # l'utente a selezionare manualmente M o F
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
            # === GENERE GIÀ NOTO (formato completo o selezionato dall'utente) ===
            self.combo_genere.addItems(["M", "F"])
            self.combo_genere.setCurrentText(sesso)

        self.combo_genere.setFixedWidth(70)

        # Quando l'utente seleziona M o F, rimuovi il placeholder e lo stile arancione
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
            "ULTIMA — Preferenza": "ULTIMA",
            "FISSO — Posizione fissa": "FISSO"
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

        # --- LABEL INFORMATIVA PER POSIZIONE FISSO ---
        # Posizionata subito SOTTO il nome e la riga genere/posizione,
        # ben visibile quando la scheda è espansa.
        # Visibile SOLO quando lo studente ha posizione FISSO.
        # Spiega perché i vincoli sono disabilitati e come influenzare
        # chi siede accanto al FISSO (impostando vincoli sugli ALTRI).
        self._label_info_fisso = QLabel(
            "ℹ️ Questo studente ha posizione FISSA: i vincoli di incompatibilità/affinità sono disabilitati. Per influenzare chi gli siede accanto, imposta affinità e incompatibilità degli ALTRI studenti verso di lui."
            ""
            ""
        )
        self._label_info_fisso.setStyleSheet(
            f"color: {C('testo_arancione')}; font-style: italic; font-size: 11px; "
            f"padding: 6px; border: 1px dashed {C('testo_arancione')}; border-radius: 4px; "
            f"background-color: rgba(255, 167, 38, 0.1);"
        )
        self._label_info_fisso.setWordWrap(True)
        self._label_info_fisso.setVisible(False)  # Nascosta di default
        self._layout_interno.addWidget(self._label_info_fisso)

        # --- SEPARATORE ---
        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.HLine)
        self._sep1.setStyleSheet(f"background-color: {C('editor_sep')};")
        self._layout_interno.addWidget(self._sep1)

        # --- SEZIONE INCOMPATIBILITÀ ---
        # Colore rosso: semantico (incompatibilità = attenzione)
        self._label_incomp = QLabel("⛔ INCOMPATIBILITÀ:")
        self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_incomp')}; font-size: 13px;")
        self._layout_interno.addWidget(self._label_incomp)

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
        self._label_aff = QLabel("💚 AFFINITÀ:")
        self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_affinita')}; font-size: 13px;")
        self._layout_interno.addWidget(self._label_aff)

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

        # --- CONNESSIONE CAMBIO POSIZIONE → ABILITA/DISABILITA VINCOLI ---
        # Quando l'utente seleziona "FISSO", disabilita le sezioni vincoli.
        # Quando seleziona un'altra posizione, le riabilita.
        self.combo_posizione.currentTextChanged.connect(self._on_posizione_cambiata)

        # Applica lo stato iniziale (se lo studente è stato caricato con FISSO)
        posizione_iniziale = self._mappa_posizioni.get(
            self.combo_posizione.currentText(), "NORMALE"
        )
        if posizione_iniziale == "FISSO":
            self._imposta_vincoli_abilitati(False)

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
        # Quando l'utente clicca "Aggiungi", entrambi hanno placeholder → nessuna emissione.
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
        # NON impostiamo _modifiche_non_salvate (il vincolo incompleto
        # non è una modifica salvabile — _esporta_file lo bloccherebbe).
        # Emettiamo però vincolo_modificato_signal per aggiornare la
        # label del pannello sinistro tramite _sincronizza_vincolo →
        # dati_modificati_signal, così l'utente vede il messaggio
        # arancione "modificato nell'Editor".
        if livello == 0 or not nuovo_studente:
            # Emette il segnale solo se l'utente ha fatto una scelta parziale
            # (studente scelto ma livello mancante), non se entrambi sono placeholder
            if nuovo_studente or livello > 0:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente or "incompleto",
                    tipo, 0, "incompleto"
                )
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

        # Se il vincolo rimosso era INCOMPLETO (non registrato),
        # notifica comunque per aggiornare la label del pannello sinistro.
        # Senza questo, dopo aver rimosso un vincolo pendente la label
        # resterebbe arancione anche se non ci sono più problemi.
        if not self._aggiornamento_programmatico and not era_registrato:
            self.vincolo_modificato_signal.emit(
                self.nome_completo, studente_b or "",
                tipo, 0, "rimosso_incompleto"
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
        Se l'utente seleziona M o F (dopo il placeholder "---"),
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

    def _on_posizione_cambiata(self, nuova_etichetta):
        """
        Gestisce il cambio di selezione nel ComboBox posizione.
        Quando l'utente seleziona "FISSO", disabilita le sezioni vincoli
        (incompatibilità e affinità), mostra la label informativa e
        cambia il bordo della scheda in rosso.
        Quando seleziona un'altra posizione, riabilita tutto e ripristina
        il colore in base al genere (azzurro/rosa/arancione).
        """
        posizione_interna = self._mappa_posizioni.get(nuova_etichetta, "NORMALE")
        is_fisso = (posizione_interna == "FISSO")
        self._imposta_vincoli_abilitati(not is_fisso)

        # Aggiorna il colore della scheda: FISSO → rosso, altrimenti → genere
        sesso_attuale = self.combo_genere.currentText()
        self._aggiorna_stile_genere(sesso_attuale)

    def _imposta_vincoli_abilitati(self, abilitato: bool):
        """
        Abilita o disabilita le sezioni incompatibilità e affinità.

        Quando disabilitato (studente FISSO):
        - I bottoni "Aggiungi" diventano grigi e non cliccabili
        - Le righe vincolo esistenti diventano grigie
        - La label informativa FISSO diventa visibile
        - Le label di sezione diventano grigie

        Quando riabilitato (posizione non-FISSO):
        - Tutto torna allo stato normale

        Args:
            abilitato (bool): True per abilitare, False per disabilitare
        """
        # --- Bottoni "Aggiungi" ---
        self._btn_aggiungi_incomp.setEnabled(abilitato)
        self._btn_aggiungi_aff.setEnabled(abilitato)

        # --- Label di sezione ---
        if abilitato:
            self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_incomp')}; font-size: 13px;")
            self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_affinita')}; font-size: 13px;")
        else:
            self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_placeholder')}; font-size: 13px;")
            self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_placeholder')}; font-size: 13px;")

        # --- Righe vincolo esistenti ---
        for riga in self._righe_incompatibilita:
            riga.setEnabled(abilitato)
        for riga in self._righe_affinita:
            riga.setEnabled(abilitato)

        # --- Label informativa FISSO ---
        self._label_info_fisso.setVisible(not abilitato)

    def genere_impostato(self):
        """
        Restituisce True se l'utente ha selezionato un genere valido (M o F).
        Restituisce False se il placeholder '---' è ancora attivo.
        """
        return self.combo_genere.currentText() in ("M", "F")

    def _aggiorna_stile_genere(self, sesso):
        """
        Applica lo stile visivo della scheda in base al genere e alla posizione.

        PRIORITÀ DEI COLORI:
        1. Genere non impostato → ARANCIONE (dato mancante, va compilato)
        2. Posizione FISSO con genere impostato → ROSSO (stato speciale bloccato)
        3. M → AZZURRO, F → ROSA (caso normale)

        Args:
            sesso: "M", "F" o PLACEHOLDER_GENERE
        """
        # Legge la posizione corrente dalla ComboBox
        etichetta_posizione = self.combo_posizione.currentText()
        posizione_interna = self._mappa_posizioni.get(etichetta_posizione, "NORMALE")
        is_fisso = (posizione_interna == "FISSO")

        if sesso not in ("M", "F"):
            # PRIORITÀ 1: Genere non impostato → arancione (avviso dato mancante)
            # Prevale su tutto: anche se è FISSO, il genere va compilato prima
            colore_bordo     = C("scheda_X_bordo")
            colore_titolo_bg = C("scheda_X_titolo_sf")
            colore_titolo_txt = C("scheda_X_titolo_txt")
            colore_sfondo    = C("scheda_X_sf")
        elif is_fisso:
            # PRIORITÀ 2: Studente FISSO con genere già impostato → bordo ROSSO
            # Bordo e titolo rossi fissi: segnalano lo stato "bloccato" in modo
            # inequivocabile, distinto da M (azzurro) e F (rosa).
            # Lo SFONDO invece segue la palette del genere (dal tema attivo),
            # così resta coerente col resto delle schede sia in tema chiaro che scuro.
            colore_bordo      = C("errore_bordo")      # Rosso bordo (Material Red 600)
            colore_titolo_bg  = C("errore_titolo_sf")   # Rosso scuro per sfondo titolo
            colore_titolo_txt = C("errore_titolo_txt")  # Bianco per testo titolo
            if sesso == "M":
                colore_sfondo = C("scheda_M_sf")   # Sfondo maschile dal tema
            else:
                colore_sfondo = C("scheda_F_sf")   # Sfondo femminile dal tema
        elif sesso == "M":
            # Maschio: colori azzurri (dal tema attivo)
            colore_bordo     = C("scheda_M_bordo")
            colore_titolo_bg = C("scheda_M_titolo_sf")
            colore_titolo_txt = C("scheda_M_titolo_txt")
            colore_sfondo    = C("scheda_M_sf")
        else:
            # Femmina: colori rosa (dal tema attivo)
            colore_bordo     = C("scheda_F_bordo")
            colore_titolo_bg = C("scheda_F_titolo_sf")
            colore_titolo_txt = C("scheda_F_titolo_txt")
            colore_sfondo    = C("scheda_F_sf")

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

    # Segnale emesso quando l'utente modifica QUALSIASI dato nell'Editor
    # (posizione, vincoli, genere). La finestra principale lo riceve
    # e aggiorna la label del pannello sinistro per avvisare che ci sono
    # modifiche non salvate. Per il genere esiste anche un segnale
    # specifico (genere_cambiato_signal) che gestisce il caso dei
    # generi mancanti — ha priorità su questo segnale generico.
    dati_modificati_signal = Signal()

    # Segnale emesso quando l'utente cambia il genere di uno studente.
    # Il pannello principale lo riceve e aggiorna la label "Genere da completare"
    # in tempo reale.
    genere_cambiato_signal = Signal()

    # Segnale emesso quando l'Editor SALVA il file con successo
    # (bottone "💾 SALVA e CARICA classe").
    # Trasporta il percorso del file salvato (str) come parametro.
    # Il pannello principale lo riceve, chiama _carica_studenti_da_editor()
    # e abilita automaticamente il bottone "Avvia assegnazione".
    file_salvato_signal = Signal(str)

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

        # --- Callback pre-caricamento ---
        # Se impostato dalla finestra principale, viene chiamato PRIMA
        # di aprire il QFileDialog per caricare una nuova classe.
        # Deve restituire True (procedi) o False (blocca il caricamento).
        # Usato per verificare se c'è un'assegnazione non salvata.
        self._callback_pre_caricamento = None

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

        # Aggiorna label esplicativa accanto al bottone "Apri cartella"
        self.label_apri_info.setStyleSheet(
            f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
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

        # Aggiorna banner formato base (se visibile)
        self._banner_formato_base.setStyleSheet(f"""
            background-color: {C("label_attenzione_bg")};
            color: {C("banner_formato_txt")};
            font-weight: bold;
            font-size: 13px;
            padding: 10px 14px;
            border-radius: 6px;
            border: 1px solid {C("label_attenzione_bordo")};
        """)

    def _costruisci_ui(self):
        """Costruisce l'interfaccia dell'editor."""

        layout_principale = QVBoxLayout(self)
        layout_principale.setSpacing(10)

        # ==============================================
        # HEADER: Apri cartella + Seleziona classe (sinistra)
        #         Comprimi/Espandi (destra)
        # ==============================================
        # Layout orizzontale: i bottoni operativi a sinistra,
        # i bottoni di visualizzazione (comprimi/espandi) a destra
        # separati da uno stretch che li tiene lontani.
        header = QHBoxLayout()

        # --- SINISTRA: Bottone "Apri cartella" + label esplicativa ---

        # Bottone per aprire la cartella dati/ nel file manager del sistema.
        # Colore teal/ciano per distinguerlo dal bottone "Seleziona classe" (blu).
        self.btn_apri_cartella = QPushButton("📂 Apri cartella")
        self.btn_apri_cartella.setMinimumHeight(40)
        self.btn_apri_cartella.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_primario_sf")};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {C("btn_primario_hover")}; }}
        """)
        self.btn_apri_cartella.setToolTip(
            "Apre la cartella 'dati' nel file manager del sistema.\n"
            "Qui puoi creare un nuovo file .txt con la lista degli studenti."
        )
        self.btn_apri_cartella.clicked.connect(self._apri_cartella_dati)
        header.addWidget(self.btn_apri_cartella)

        # Label esplicativa ACCANTO al bottone (non sotto!)
        # Spiega brevemente a cosa serve il bottone, senza occupare
        # troppo spazio orizzontale.
        self.label_apri_info = QLabel("◄  CREA qui dentro una NUOVA CLASSE")
        self.label_apri_info.setStyleSheet(
            f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
        )
        header.addWidget(self.label_apri_info)

        header.addSpacing(16)  # Separatore tra i due gruppi di bottoni

        # --- CENTRO-SINISTRA: Bottone "Seleziona classe" ---
        # Il tooltip mantiene la spiegazione completa.
        self.btn_carica = QPushButton("📝 Seleziona classe")
        self.btn_carica.setMinimumHeight(40)
        self.btn_carica.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_blu_bg")};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ background-color: {C("btn_blu_hover")}; }}
        """)
        self.btn_carica.setToolTip(
            "Seleziona un file .txt dalla cartella dati\n"
            "per modificare posizione e vincoli degli studenti"
        )
        self.btn_carica.clicked.connect(self._carica_file)
        header.addWidget(self.btn_carica)

        header.addSpacing(12)  # Separatore tra 'Seleziona classe' e 'SALVA e CARICA classe'

        # --- Bottone "SALVA e CARICA classe" (accanto a 'Seleziona classe') ---
        # L'utente carica, modifica, salva — tutto nella stessa zona.
        self.btn_esporta = QPushButton("💾 SALVA e CARICA classe")
        self.btn_esporta.setMinimumHeight(40)
        self.btn_esporta.setEnabled(False)
        self.btn_esporta.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_salva_bg")};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{ background-color: {C("btn_salva_hover")}; }}
            QPushButton:disabled {{ background-color: {C("btn_colore_disabled_sf")}; color: {C("btn_colore_disabled_txt")}; }}
        """)
        self.btn_esporta.setToolTip("Salva il file completo con tutti i dati e vincoli degli studenti")
        self.btn_esporta.clicked.connect(self._esporta_file)
        header.addWidget(self.btn_esporta)

        # --- STRETCH: spinge Comprimi/Espandi verso destra ---
        header.addStretch()

        # --- DESTRA: Bottoni Comprimi/Espandi ---

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

        layout_principale.addLayout(header)

        # Label informativa (mostra nome file caricato e numero studenti)
        # Inizialmente NASCOSTA: diventa visibile solo dopo il caricamento di un file.
        # Quando visibile, mostra es. "📂 2B.txt — 24 studenti caricati (formato COMPLETO)"
        self.label_info = QLabel("")
        self.label_info.setStyleSheet(f"color: {C('editor_info_txt')}; font-style: italic; font-size: 14px;")
        self.label_info.setVisible(False)  # Nascosta finché non si carica un file
        layout_principale.addWidget(self.label_info)

        # ==============================================
        # BANNER FORMATO BASE — Avviso per vincoli mancanti
        # ==============================================
        # Visibile solo quando si carica un file in formato BASE.
        # Ricorda all'utente di aggiungere i vincoli prima di salvare.
        # Scompare dopo il salvataggio o la chiusura dell'editor.
        self._banner_formato_base = QLabel(
            "⚠️  FORMATO BASE — PRIMA DI SALVARE, imposta per ogni studente: "
            "posizione, incompatibilità e affinità. "
            "Poi clicca '💾 SALVA e CARICA classe'."
        )
        self._banner_formato_base.setWordWrap(True)
        self._banner_formato_base.setStyleSheet(f"""
            background-color: {C("label_attenzione_bg")};
            color: {C("banner_formato_txt")};
            font-weight: bold;
            font-size: 13px;
            padding: 10px 14px;
            border-radius: 6px;
            border: 1px solid {C("label_attenzione_bordo")};
        """)
        self._banner_formato_base.setVisible(False)
        layout_principale.addWidget(self._banner_formato_base)

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
            "NESSUN FILE CARICATO.\n\n"
            "• Clicca su '📂 Apri cartella' per creare un nuovo file .txt in formato BASE\n"
            "con 'Cognome;Nome;M/F' degli allievi (uno per riga, in ordine alfabetico).\n\n"
            "• Clicca su '📝 Seleziona classe' per modificare posizione e vincoli degli studenti.\n\n"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 40px;")
        # Stretch SOPRA + SOTTO il placeholder → centratura verticale
        self.layout_schede.addStretch()
        self.layout_schede.addWidget(self._label_placeholder)

        self.layout_schede.addStretch()
        self.scroll_area.setWidget(self.widget_scroll)
        layout_principale.addWidget(self.scroll_area)

        # ==============================================
        # FOOTER: Bottone Preview (sinistra) e Chiudi (destra)
        # ==============================================
        footer = QHBoxLayout()
        footer.setSpacing(12)

        # Bottone Preview
        self.btn_preview = QPushButton("👁️ Preview file classe (.txt)")
        self.btn_preview.setMinimumHeight(45)
        self.btn_preview.setEnabled(False)
        self.btn_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_viola_bg")};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{ background-color: {C("btn_viola_hover")}; }}
            QPushButton:disabled {{ background-color: {C("btn_colore_disabled_sf")}; color: {C("btn_colore_disabled_txt")}; }}
        """)
        self.btn_preview.setToolTip("Mostra un'anteprima del file .txt che verrà generato")
        self.btn_preview.clicked.connect(self._mostra_preview)
        footer.addWidget(self.btn_preview)

        footer.addStretch()

        # Bottone Chiudi (a destra) — chiude/scarica il file corrente
        self.btn_chiudi = QPushButton("✖ CHIUDI FILE")
        self.btn_chiudi.setMinimumHeight(45)
        self.btn_chiudi.setEnabled(False)
        self.btn_chiudi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_rosso_bg")};
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{ background-color: {C("btn_rosso_hover")}; }}
            QPushButton:disabled {{ background-color: {C("btn_colore_disabled_sf")}; color: {C("btn_colore_disabled_txt")}; }}
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
        Se ci sono modifiche non salvate o vincoli incompleti, chiede conferma.
        """
        # === GUARDIA: vincoli incompleti (studente senza livello) ===
        # Controllato PRIMA delle modifiche non salvate perché un vincolo
        # incompleto non imposta _modifiche_non_salvate (il segnale
        # _segna_modificato non viene chiamato per vincoli non validi).
        # Senza questo controllo, l'utente perderebbe il vincolo pendente
        # senza alcun avviso caricando un'altra classe.
        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                risposta = QMessageBox.warning(
                    self,
                    "⚠️ Vincoli INCOMPLETI",
                    f"I seguenti vincoli non hanno il livello impostato:\n\n"
                    f"{elenco}\n\n"
                    f"❗ Se carichi un'altra classe adesso, questi vincoli andranno PERSI.\n\n"
                    f"💡 Per ogni vincolo, puoi:\n"
                    f"  • Selezionare il livello e poi salvare\n"
                    f"  • Rimuoverlo con il pulsante 'Rimuovi'",
                    QMessageBox.Ok
                )
                return

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

        # === GUARDIA: Chiedi alla finestra principale se si può procedere ===
        # Se c'è un'assegnazione non salvata nello Storico, la finestra
        # principale mostra il popup di avviso e restituisce False per bloccare.
        if self._callback_pre_caricamento is not None:
            if not self._callback_pre_caricamento():
                return  # La finestra principale ha bloccato il caricamento

        # Apri il dialog nella cartella dati/ se esiste
        cartella_dati = self._get_cartella_dati()

        percorso, _ = QFileDialog.getOpenFileName(
            self,
            "SELEZIONA CLASSE (.txt)",
            cartella_dati,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if not percorso:
            return  # L'utente ha annullato

        # Lettura file con fallback encoding: prova UTF-8, poi Latin-1.
        # Su Windows, il Blocco Note salva in ANSI (= Latin-1) per default,
        # quindi è fondamentale avere il fallback per gli utenti che
        # creano i file .txt con strumenti non configurati per UTF-8.
        # Stessa logica già presente in carica_file_da_percorso().
        try:
            with open(percorso, 'r', encoding='utf-8-sig') as f:
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
        per obbligare l'utente a selezionarlo manualmente.

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
                "⚠️ PROBLEMI RILEVATI NEL FILE",
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
        if posizione_raw in ("NORMALE", "PRIMA", "ULTIMA", "FISSO"):
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
        - "NORMALE", "PRIMA", "ULTIMA", "FISSO" → è la Posizione
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
            elif valore_upper in ("NORMALE", "PRIMA", "ULTIMA", "FISSO"):
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
            tipo_vincolo: "incompatibilità" o "affinità" (per messaggi debug)

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
            # + controlla in tempo reale che non ci siano più di 1 studente FISSO
            scheda.combo_posizione.currentTextChanged.connect(
                lambda _, s=scheda: self._on_posizione_cambiata_editor(s)
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
            descrizione_formato = "formato BASE"

            # --- BANNER FORMATO BASE: reso visibile ---
            # Resta visibile finché l'utente non salva o chiude l'editor
            self._banner_formato_base.setVisible(True)

            # --- POPUP INFORMATIVO (ogni caricamento formato BASE) ---
            # Spiega all'utente cosa deve fare prima di salvare.
            # Mostrato OGNI volta che si carica un file BASE, perché
            # è un promemoria importante: senza vincoli l'assegnazione
            # sarebbe completamente casuale.
            QMessageBox.information(
                self,
                "📋 File in formato base caricato",
                f"Il file '{self._nome_file_caricato}.txt' contiene solo "
                f"cognome, nome e genere degli studenti.\n\n"
                f"⚠️ PRIMA di cliccare '💾 SALVA e CARICA classe', "
                f"è consigliabile impostare per ciascun studente:\n\n"
                f"  • Posizione (PRIMA, NORMALE, ULTIMA o FISSO)\n"
                f"  • Incompatibilità (studenti da NON mettere vicini)\n"
                f"  • Affinità (studenti da mettere vicini)\n\n"
                f"‼️ SE NON IMPOSTI I VINCOLI ADESSO, L'ASSEGNAZIONE DEI POSTI "
                f"SARÀ COMPLETAMENTE CASUALE!\n\n"
                f"💡 Potrai comunque aggiungere o modificare i vincoli in qualsiasi "
                f"momento, ricaricando il file nell'Editor."
            )
        else:
            # Formato COMPLETO = tutti e 6 i campi presenti
            descrizione_formato = "formato COMPLETO"
            # Nasconde il banner (potrebbe essere rimasto da un caricamento base precedente)
            self._banner_formato_base.setVisible(False)

        self.label_info.setText(
            f"Il file ' 📂 {self._nome_file_caricato}.txt' è stato caricato — "
            f"{len(studenti_dati)} studenti presenti ({descrizione_formato})"
        )
        self.label_info.setStyleSheet(f"color: {C('testo_affinita')}; font-style: normal; font-size: 14px;")
        self.label_info.setVisible(True)  # Mostra la label ora che c'è un file caricato

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

    def get_vincoli_incompleti(self):
        """
        Restituisce la lista dei vincoli incompleti (studente scelto
        ma livello di intensità non selezionato).

        Usato sia dalla validazione al salvataggio (_esporta_file)
        sia dal controllo pre-assegnazione (avvia_assegnazione in
        postiperfetti.py) per impedire che vincoli "pendenti"
        vengano silenziosamente ignorati.

        Returns:
            list[str]: Lista di stringhe descrittive dei vincoli incompleti.
                       Lista vuota se tutti i vincoli sono completi.
        """
        vincoli_incompleti = []
        for scheda in self._schede_studenti:
            # Controlla le righe di incompatibilità
            for riga in scheda._righe_incompatibilita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(incompatibilità senza livello)"
                    )
            # Controlla le righe di affinità
            for riga in scheda._righe_affinita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(affinità senza livello)"
                    )
        return vincoli_incompleti

    def _segna_modificato(self):
        """
        Segna il file come "modificato" dall'utente.
        Viene chiamato ogni volta che l'utente cambia genere, posizione
        o vincoli di uno studente. Il flag attiva il popup di conferma
        quando si tenta di chiudere il file o l'applicazione senza salvare.
        Emette anche dati_modificati_signal per aggiornare la label
        nel pannello sinistro della finestra principale.
        """
        self._modifiche_non_salvate = True
        self.dati_modificati_signal.emit()

    def _on_posizione_cambiata_editor(self, scheda_modificata):
        """
        Chiamata quando l'utente cambia la posizione di uno studente.
        Segna il file come modificato e controlla in tempo reale che
        non ci siano più di 1 studente con posizione FISSO.

        Se l'utente seleziona FISSO su un secondo studente, mostra
        un avviso immediato (senza bloccare: la validazione all'export
        impedirà comunque il salvataggio).

        Args:
            scheda_modificata: La SchedaStudente su cui è avvenuto il cambio
        """
        self._segna_modificato()

        # Controlla se la nuova posizione è 'FISSO'
        dati = scheda_modificata.get_dati()
        if dati["posizione"] != "FISSO":
            return  # Non è FISSO → nessun controllo necessario

        # Conta quanti studenti hanno FISSO (inclusa la scheda appena modificata)
        studenti_fisso = []
        for scheda in self._schede_studenti:
            dati_scheda = scheda.get_dati()
            if dati_scheda["posizione"] == "FISSO":
                studenti_fisso.append(scheda.nome_completo)

        if len(studenti_fisso) > 1:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
            QMessageBox.warning(
                self,
                "⚠️ ATTENZIONE: PIÙ DI 1 STUDENTE 'FISSO'!",
                f"Al massimo 1 studente può avere posizione 'FISSO'.\n\n"
                f"Attualmente {len(studenti_fisso)} studenti hanno posizione 'FISSO':\n\n"
                f"{elenco}\n\n"
                f"Modifica la 'posizione' degli studenti in eccesso prima di esportare."
            )

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
            azione: "aggiungi", "modifica", "rimuovi" o "incompleto"
        """
        # --- BLOCCO RICORSIONE ---
        if self._sincronizzazione_in_corso:
            return

        # --- VINCOLO INCOMPLETO: solo aggiornamento label ---
        # L'utente ha selezionato uno studente ma NON il livello.
        # Non è una modifica salvabile (verrebbe bloccata da _esporta_file),
        # quindi NON impostiamo _modifiche_non_salvate.
        # Emettiamo solo dati_modificati_signal per aggiornare la label
        # del pannello sinistro con il messaggio arancione.
        if azione == "incompleto":
            self.dati_modificati_signal.emit()
            return

        # --- VINCOLO INCOMPLETO RIMOSSO: rivaluta lo stato della label ---
        # L'utente ha rimosso un vincolo che era pendente (senza livello).
        # Emettiamo dati_modificati_signal per far rivalutare al pannello
        # principale se lo stato è ora "pulito" (→ label verde) oppure
        # ci sono ancora problemi (→ label arancione).
        if azione == "rimosso_incompleto":
            self.dati_modificati_signal.emit()
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

        Due controlli distinti:
        1. CONTRADDIZIONI: A ha incomp con B, ma B ha affinità con A (o viceversa).
           Queste vengono segnalate all'utente perché richiedono una scelta umana.
        2. VINCOLI MANCANTI: A ha incomp con B, ma B non ha incomp con A
           (e nemmeno un vincolo contraddittorio). Questi vengono aggiunti
           automaticamente.
        """
        vincoli_aggiunti = []
        contraddizioni = []

        for scheda in self._schede_studenti:
            dati = scheda.get_dati()

            # Controlla ogni incompatibilità
            for target, livello in dati["incompatibilita"].items():
                scheda_target = self._trova_scheda(target)
                if scheda_target:
                    dati_target = scheda_target.get_dati()
                    if scheda.nome_completo not in dati_target["incompatibilita"]:
                        # Il vincolo speculare non esiste. Ma c'è una CONTRADDIZIONE?
                        # (cioè: A ha incomp→B, ma B ha affinità→A)
                        if scheda.nome_completo in dati_target["affinita"]:
                            # CONTRADDIZIONE: non aggiungere, segnalare all'utente
                            contraddizioni.append(
                                f"⚠️ {scheda.nome_completo} ha INCOMPATIBILITÀ "
                                f"con {target} (lv {livello}),\n"
                                f"      ma {target} ha AFFINITÀ "
                                f"con {scheda.nome_completo} "
                                f"(lv {dati_target['affinita'][scheda.nome_completo]})"
                            )
                        else:
                            # Vincolo mancante senza contraddizioni: aggiungilo
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
                        # Il vincolo speculare non esiste. Ma c'è una CONTRADDIZIONE?
                        # (cioè: A ha affinità→B, ma B ha incompatibilità→A)
                        if scheda.nome_completo in dati_target["incompatibilita"]:
                            # CONTRADDIZIONE: segnalare (potrebbe essere già
                            # stata rilevata dal ciclo incompatibilità sopra,
                            # ma evitiamo duplicati controllando)
                            coppia_key = tuple(sorted([scheda.nome_completo, target]))
                            duplicato = any(
                                coppia_key == tuple(sorted([scheda.nome_completo, target]))
                                for c in contraddizioni
                                if target in c and scheda.nome_completo in c
                            )
                            if not duplicato:
                                contraddizioni.append(
                                    f"⚠️ {scheda.nome_completo} ha AFFINITÀ "
                                    f"con {target} (lv {livello}),\n"
                                    f"      ma {target} ha INCOMPATIBILITÀ "
                                    f"con {scheda.nome_completo} "
                                    f"(lv {dati_target['incompatibilita'][scheda.nome_completo]})"
                                )
                        else:
                            # Vincolo mancante senza contraddizioni: aggiungilo
                            scheda_target.aggiungi_vincolo_programmatico(
                                "affinita", scheda.nome_completo, livello
                            )
                            vincoli_aggiunti.append(
                                f"💚 {target} ← {scheda.nome_completo} (livello {livello})"
                            )

        # === MOSTRA CONTRADDIZIONI (priorità alta, richiedono intervento) ===
        if contraddizioni:
            msg_contr = (
                f"⚠️ ATTENZIONE: trovate {len(contraddizioni)} CONTRADDIZIONI!\n\n"
                "‼️ Le seguenti coppie hanno VINCOLI OPPOSTI:\n"
                "uno studente considera incompatibile un altro che lo considera affine!\n\n"
                "💡 Apri le schede di questi studenti nell'Editor\n"
                "e decidi quale mantenere ('incompatibilità' o 'affinità').\n"
                "   ➡ Il vincolo opposto va tolto manualmente col tasto 'RIMUOVI'.\n\n\n"
            )
            for c in contraddizioni[:10]:
                msg_contr += f"{c}\n\n"
            if len(contraddizioni) > 10:
                msg_contr += f"... e altre {len(contraddizioni) - 10}"
            # Usa un QDialog non-modale (come le Istruzioni) per permettere
            # all'utente di leggere le contraddizioni E contemporaneamente
            # intervenire nell'Editor per correggerle.
            if hasattr(self, '_dialog_contraddizioni') and self._dialog_contraddizioni is not None:
                if self._dialog_contraddizioni.isVisible():
                    self._dialog_contraddizioni.raise_()
                    self._dialog_contraddizioni.activateWindow()
                    return

            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
            from PySide6.QtGui import QFont

            self._dialog_contraddizioni = QDialog(self)
            dialog = self._dialog_contraddizioni
            dialog.setWindowTitle("⚠️ CONTRADDIZIONI NEI VINCOLI")
            dialog.setMinimumSize(650, 400)  # CONFIGURABILE
            dialog.resize(650, 450)          # CONFIGURABILE

            layout_d = QVBoxLayout(dialog)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Segoe UI", 11))
            text_edit.setPlainText(msg_contr)
            layout_d.addWidget(text_edit)

            btn_chiudi = QPushButton("✅ Ho capito e ho corretto nell'Editor")
            btn_chiudi.setMinimumHeight(40)
            btn_chiudi.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C("btn_arancione_bg")};
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                    border-radius: 6px;
                    padding: 8px 20px;
                }}
                QPushButton:hover {{ background-color: {C("btn_arancione_hover")}; }}
            """)
            btn_chiudi.clicked.connect(dialog.close)
            layout_d.addWidget(btn_chiudi)

            # Mostra come finestra NON-MODALE (show, non exec)
            dialog.show()

        # === MOSTRA VINCOLI AGGIUNTI (bidirezionalità corretta) ===
        if vincoli_aggiunti:
            # Segnala che sono state applicate correzioni (per auto-salvataggio)
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True

            msg = (
                f"Sono stati aggiunti {len(vincoli_aggiunti)} vincoli mancanti "
                "per garantire la bidirezionalità:\n\n"
            )
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
        conferma se ci sono modifiche non salvate o vincoli incompleti.
        """
        # === GUARDIA: vincoli incompleti (studente senza livello) ===
        # Controllato PRIMA di _modifiche_non_salvate perché un vincolo
        # incompleto non imposta quel flag. Senza questo controllo,
        # l'utente perderebbe il vincolo pendente chiudendo l'Editor.
        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                QMessageBox.warning(
                    self,
                    "⚠️ Vincoli INCOMPLETI",
                    f"I seguenti vincoli non hanno il livello impostato:\n\n"
                    f"{elenco}\n\n"
                    f"❗ Se chiudi adesso, questi vincoli andranno PERSI.\n\n"
                    f"💡 Per ogni vincolo, puoi:\n"
                    f"  • Selezionare il livello e poi salvare\n"
                    f"  • Rimuoverlo con il pulsante 'Rimuovi'"
                )
                return

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
        dialog.setWindowTitle("⚠️ MODIFICHE NON SALVATE")
        dialog.setIcon(QMessageBox.Warning)
        # Mostra il nome del file per chiarezza
        nome_file = self._nome_file_caricato or "sconosciuto"
        dialog.setText(
            f"⚠️ Hai modificato i dati di '{nome_file}.txt' nell'Editor\n"
            f"(vincoli, genere, posizione...) ma NON hai ancora salvato\n"
            f"il file '{nome_file}.txt' su disco.\n\n"
            f"❗ Se prosegui senza salvare, tutte le modifiche\n"
            f"fatte nell'Editor andranno PERSE.\n\n"
            f"Che cosa vuoi fare?\n"
        )

        # Crea i 3 bottoni personalizzati
        btn_salva = dialog.addButton("💾 Salva ed esci", QMessageBox.AcceptRole)
        btn_esci = dialog.addButton("🚪 Esci senza salvare", QMessageBox.DestructiveRole)
        btn_annulla = dialog.addButton("↩️ Annulla", QMessageBox.RejectRole)

        dialog.setDefaultButton(btn_annulla)
        # Se l'utente chiude con la X, equivale ad "Annulla" (nessuna azione)
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
        Riporta l'Editor allo stato iniziale: rimuove tutte le schede,
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

        # Ricrea il placeholder (coerente con quello iniziale)
        self._label_placeholder = QLabel(
            "NESSUN FILE CARICATO.\n\n"
            "• Clicca su '📂 Apri cartella' per creare un nuovo file .txt in formato BASE\n"
            "con 'Cognome;Nome;M/F' degli allievi (uno per riga, in ordine alfabetico).\n\n"
            "• Clicca su '📝 Seleziona classe' per modificare posizione e vincoli degli studenti.\n\n"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 40px;")
        # Stretch SOPRA + SOTTO il placeholder → centratura verticale
        # (stessa logica usata in _costruisci_ui all'avvio)
        self.layout_schede.addStretch()
        self.layout_schede.addWidget(self._label_placeholder)
        self.layout_schede.addStretch()

        # Disabilita tutti i bottoni
        self.btn_preview.setEnabled(False)
        self.btn_esporta.setEnabled(False)
        self.btn_espandi.setEnabled(False)
        self.btn_comprimi.setEnabled(False)
        self.btn_chiudi.setEnabled(False)

        # Nasconde la label informativa (tornerà visibile al prossimo caricamento)
        self.label_info.setText("")
        self.label_info.setVisible(False)

        # Nasconde il banner formato base (se era visibile)
        self._banner_formato_base.setVisible(False)

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
        # === GUARDIA: vincoli incompleti (studente senza livello) ===
        # Controllato PRIMA di _modifiche_non_salvate perché un vincolo
        # incompleto non imposta quel flag. Blocca la chiusura del
        # programma e avvisa l'utente, che può completare o rimuovere
        # i vincoli pendenti prima di uscire.
        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                QMessageBox.warning(
                    self,
                    "⚠️ Vincoli INCOMPLETI",
                    f"I seguenti vincoli non hanno il livello impostato:\n\n"
                    f"{elenco}\n\n"
                    f"❗ Se chiudi adesso, questi vincoli andranno PERSI.\n\n"
                    f"💡 Per ogni vincolo, puoi:\n"
                    f"  • Selezionare il livello e poi salvare\n"
                    f"  • Rimuoverlo con il pulsante 'Rimuovi'"
                )
                return False  # Blocca la chiusura

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
    # Questi metodi vengono chiamati dal pannello principale
    # del pannello sinistro, per usare l'Editor come unico punto
    # di caricamento e validazione dei dati.

    def carica_file_da_percorso(self, percorso):
        """
        Carica un file .txt nell'Editor SENZA aprire il QFileDialog.
        Metodo PUBBLICO: chiamato dal pannello principale quando l'utente
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
            with open(percorso, 'r', encoding='utf-8-sig') as f:
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
                  cognome, nome, genere, posizione, incompatibilita, affinita

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
        linee.append("# Posizione: NORMALE (= vincolo neutro) / PRIMA (= VINCOLO OBBLIGATORIO) / ULTIMA (= vincolo soft) / FISSO (= posizione fissa primo banco)")
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
                "⚠️ GENERE non impostato",
                f"I seguenti studenti hanno ancora il genere su '---':\n\n"
                f"{elenco}\n\n"
                f"Seleziona M o F per ogni studente prima di procedere."
            )
            return

        contenuto = self._genera_txt()

        # Crea il dialog di preview
        dialog = QDialog(self)
        dialog.setWindowTitle("👁️ Preview file classe (.txt)")
        dialog.setMinimumSize(1300, 750) # CONFIGURABILE

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
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C("anteprima_sf")};
                color: {C("anteprima_txt")};
                border: 1px solid {C("bordo_normale")};
                padding: 10px;
            }}
        """)
        layout.addWidget(text_edit)

        # Info riepilogativa
        num_righe_dati = len(self._schede_studenti)
        label_info = QLabel(f"📊 {num_righe_dati} studenti — Ogni riga ha 6 campi separati da ';'")
        label_info.setStyleSheet(f"color: {C('testo_info_grigio')}; font-size: 11px;")
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
                "⚠️ GENERE non impostato",
                f"I seguenti studenti hanno ancora il genere su '---':\n\n"
                f"{elenco}\n\n"
                f"Seleziona M o F per ogni studente prima di esportare."
            )
            return

        # === VALIDAZIONE: Controlla che al massimo 1 studente abbia posizione FISSO ===
        studenti_fisso = []
        for scheda in self._schede_studenti:
            dati = scheda.get_dati()
            if dati["posizione"] == "FISSO":
                studenti_fisso.append(scheda.nome_completo)

        if len(studenti_fisso) > 1:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
            QMessageBox.warning(
                self,
                "⚠️ Troppi studenti FISSO",
                f"Al massimo 1 studente può avere posizione 'FISSO'.\n\n"
                f"Attualmente {len(studenti_fisso)} studenti hanno posizione FISSO:\n\n"
                f"{elenco}\n\n"
                f"Modifica la 'posizione' degli studenti in eccesso prima di esportare."
            )
            return

        # === VALIDAZIONE: Controlla vincoli incompleti (studente senza livello) ===
        # Usa il metodo centralizzato get_vincoli_incompleti(), condiviso
        # anche con avvia_assegnazione() in postiperfetti.py.
        vincoli_incompleti = self.get_vincoli_incompleti()
        if vincoli_incompleti:
            elenco = "\n".join(vincoli_incompleti)
            QMessageBox.warning(
                self,
                "⚠️ Vincoli INCOMPLETI",
                f"I seguenti vincoli non hanno il livello impostato:\n\n"
                f"{elenco}\n\n"
                f"Per ogni vincolo, scegli una delle due opzioni:\n"
                f"  • Seleziona il livello di intensità del vincolo\n"
                f"  • Oppure rimuovilo con il pulsante 'Rimuovi'"
            )
            return

        if self._percorso_file_caricato:
            # --- MODALITÀ SOVRASCRITTURA DIRETTA ---
            # Il file era già stato caricato dall'utente, quindi sovrascriviamo
            # lo stesso file con i vincoli aggiornati.
            percorso = self._percorso_file_caricato
        else:
            # --- FALLBACK: QFileDialog per file mai salvato ---
            nome_suggerito = f"{self._nome_file_caricato}.txt" if self._nome_file_caricato else "studenti.txt"
            cartella_dati = self._get_cartella_dati()
            percorso_suggerito = os.path.join(cartella_dati, nome_suggerito)

            percorso, _ = QFileDialog.getSaveFileName(
                self,
                "Salva file classe (.txt)",
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
            # Aggiorna il percorso salvato (utile se era il primo salvataggio via dialog)
            self._percorso_file_caricato = percorso

            # Nasconde il banner formato base (l'utente ha completato il flusso)
            self._banner_formato_base.setVisible(False)

            # Aggiorna la label informativa: dopo il salvataggio il file su disco
            # contiene tutti e 6 i campi, quindi il formato è ora COMPLETO.
            self.label_info.setText(
                f"Il file ' 📂 {self._nome_file_caricato}.txt' è stato caricato — "
                f"{len(self._schede_studenti)} studenti presenti (formato COMPLETO)"
            )

            # Popup di conferma: messaggio diverso a seconda della modalità
            nome_file = os.path.basename(percorso)
            QMessageBox.information(
                self,
                "💾 File aggiornato",
                f"✅ Il file '{nome_file}\n"
                f"✅ è stato aggiornato con i nuovi vincoli.\n"
                f"✅ ed è PRONTO per avviare l'ASSEGNAZIONE!\n\n"
                f"📁 Percorso:\n"
                f"{percorso}\n"
                f"👥 Contiene {len(self._schede_studenti)} studenti."
            )

            # Emette il segnale per notificare la finestra principale
            # che il file è stato salvato (→ auto-caricamento dati per l'assegnazione)
            self.file_salvato_signal.emit(percorso)

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
            # Modalità script: questo file è in moduli/ → risali di un livello
            cartella_modulo = os.path.dirname(os.path.abspath(__file__))
            cartella_progetto = os.path.dirname(cartella_modulo)
        cartella_dati = os.path.join(cartella_progetto, "dati")

        # Crea la cartella se non esiste
        os.makedirs(cartella_dati, exist_ok=True)

        return cartella_dati

    def _apri_cartella_dati(self):
        """
        Apre la cartella 'dati/' nel file manager predefinito del sistema operativo.
        Cross-platform: funziona su Linux (xdg-open), Windows (explorer),
        macOS (open). La cartella viene creata se non esiste ancora.

        Se l'apertura fallisce (es: sistema non riconosciuto o xdg-open
        non installato), mostra un popup con il percorso da raggiungere manualmente.
        """
        # Ottieni il percorso della cartella dati/ (la crea se necessario)
        cartella_dati = self._get_cartella_dati()

        try:
            sistema = platform.system()

            if sistema == 'Linux':
                # Linux: xdg-open apre la cartella nel file manager predefinito
                # (Dolphin su KDE, Nautilus su GNOME, Thunar su XFCE, ecc.)
                subprocess.run(['xdg-open', cartella_dati], check=False)

            elif sistema == 'Windows':
                # Windows: os.startfile apre la cartella in Esplora File
                os.startfile(cartella_dati)

            elif sistema == 'Darwin':
                # macOS: open apre la cartella in Finder
                subprocess.run(['open', cartella_dati], check=False)

            else:
                # Sistema non riconosciuto: mostra il percorso da raggiungere manualmente
                QMessageBox.information(
                    self,
                    "📂 Cartella dati",
                    f"Sistema operativo non riconosciuto.\n\n"
                    f"La cartella dati si trova in:\n{cartella_dati}"
                )
                return

        except Exception as e:
            # Se qualcosa va storto, mostra il percorso da raggiungere manualmente
            QMessageBox.warning(
                self,
                "⚠️ Impossibile aprire la cartella",
                f"Errore nell'apertura automatica:\n{e}\n\n"
                f"Puoi raggiungere la cartella manualmente:\n{cartella_dati}"
            )
