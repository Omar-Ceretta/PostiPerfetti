# -*- coding: utf-8 -*-
"""Editor grafico delle classi di «PostiPerfetti».

Carica file base o completi, valida anagrafica e vincoli, mantiene la
bidirezionalità delle relazioni e salva il formato testuale del progetto.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGroupBox, QScrollArea, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap
import os
from html import escape

from moduli.tema import C
from moduli.lingua import quantita
from moduli.profilo_gui import ProfiloGUI


from moduli.percorsi import (
    get_resource_path,
    inizializza_cartella_classi,
)
from moduli.file_classe import (
    FORMATO_BASE, FORMATO_COMPLETO, PLACEHOLDER_GENERE,
    FileClasseVuoto, ErroreCodificaFileClasse, ErroreValidazioneFileClasse,
    analizza_coerenza_bidirezionale_dati, carica_file_classe,
    crea_copia_utf8_file_classe,
    nomi_studenti_fissi, serializza_file_classe,
    scrivi_file_classe_atomico,
)


from moduli.utilita import (
    conta_vincoli, formato_vincoli,
    dettaglio_vincoli, formato_dettaglio_vincoli,
    ordina_studenti,
    adatta_finestra_allo_schermo,
    applica_icona, applica_stile_pulsante_popup, applica_icona_finestra,
    applica_icona_applicazione_finestra,
    applica_icona_etichetta, crea_popup_semantico, mostra_popup_semantico,
    apri_file_con_applicazione_default,
)


# I placeholder rendono incompleto il dato finché l’utente non sceglie
# esplicitamente il valore; le guardie di salvataggio li riconoscono.
PLACEHOLDER_VINCOLO = "Seleziona studente..."


PLACEHOLDER_LIVELLO = "Seleziona intensità del vincolo..."


def _imposta_proprieta_stile(widget, nome, valore, *, ripolisci=True):
    """Aggiorna una proprietà dinamica e, se serve, ripolisce un solo widget."""
    valore_testo = str(valore)
    if widget.property(nome) == valore_testo:
        return
    widget.setProperty(nome, valore_testo)
    if ripolisci:
        stile = widget.style()
        stile.unpolish(widget)
        stile.polish(widget)
        widget.update()


def _misura_profilo(profilo, nome, funzione):
    """Misura una fase se è stato fornito un profiler diagnostico."""
    if profilo is None:
        return funzione()
    return profilo.misura(nome, funzione)



def _popup_info(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un messaggio informativo con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "info", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_successo(parent, titolo, messaggio, *, dettagli=""):
    """Mostra una conferma con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "circle-check", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_avviso(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un avviso con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "triangle-alert", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_errore(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un errore con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "circle-x", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


class DialogoErroreFileClasse(QDialog):
    """Mostra gli errori di un file e permette di aprirlo senza chiudere l'avviso."""

    def __init__(self, parent, titolo, percorso, dettagli):
        super().__init__(parent)
        self._percorso = os.fspath(percorso)

        self.setWindowTitle(titolo)
        applica_icona_applicazione_finestra(self)
        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=720,
            altezza_ideale=520,
            larghezza_minima=560,
            altezza_minima=360,
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intestazione = QHBoxLayout()
        icona = QLabel()
        applica_icona_etichetta(icona, "circle-x", 42)
        intestazione.addWidget(icona, 0, Qt.AlignTop)

        testo = QLabel("Il nuovo file non è stato caricato.")
        testo.setWordWrap(True)
        testo.setStyleSheet("font-size: 14px; font-weight: bold;")
        intestazione.addWidget(testo, 1)
        layout.addLayout(intestazione)

        area_errori = QTextEdit()
        area_errori.setReadOnly(True)
        area_errori.setPlainText(str(dettagli))
        area_errori.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(area_errori, 1)

        percorso_label = QLabel(f"File selezionato:\n{self._percorso}")
        percorso_label.setWordWrap(True)
        percorso_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(percorso_label)

        pulsanti = QHBoxLayout()
        pulsanti.addStretch()

        btn_apri = QPushButton("Apri file")
        applica_icona(btn_apri, "file-text", 18)
        btn_apri.setMinimumHeight(40)
        btn_apri.clicked.connect(self._apri_file)
        pulsanti.addWidget(btn_apri)

        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.clicked.connect(self.accept)
        pulsanti.addWidget(btn_chiudi)

        layout.addLayout(pulsanti)

    def _apri_file(self):
        """Avvia l'applicazione predefinita senza chiudere il dialogo."""
        if apri_file_con_applicazione_default(self._percorso):
            return

        _popup_errore(
            self,
            "Apertura non riuscita",
            "Impossibile aprire automaticamente il file selezionato.",
            dettagli=(
                "Aprilo manualmente dalla cartella delle classi.\n\n"
                f"Percorso:\n{self._percorso}"
            ),
        )


# Evita che lo scorrimento verticale modifichi inavvertitamente una scelta.
class ComboBoxProtetto(QComboBox):
    """QComboBox protetto dalle modifiche accidentali durante lo scorrimento.

    La rotella agisce soltanto dopo un focus esplicito; una selezione completata
    rilascia il focus e restituisce la rotella al pannello.
    """

    def __init__(self, parent=None):
        super().__init__(parent)


        self.setFocusPolicy(Qt.StrongFocus)


        self.activated.connect(self._rilascia_focus)

    def _rilascia_focus(self):
        """Rilascia il focus dopo una selezione esplicita."""
        self.clearFocus()

    def wheelEvent(self, event):
        """Accetta la rotella soltanto quando il widget ha il focus."""
        if self.hasFocus():

            super().wheelEvent(event)
        else:

            event.ignore()


# Una relazione diventa effettiva soltanto quando entrambi i menu sono completi.
class RigaVincolo(QWidget):
    """Rappresenta una singola incompatibilità o affinità.

    Il vincolo è valido soltanto dopo la scelta del compagno e del livello; le
    modifiche e la rimozione vengono comunicate alla scheda tramite segnali.
    """


    vincolo_cambiato = Signal()
    vincolo_rimosso = Signal()

    def __init__(self, lista_studenti_disponibili, tipo_vincolo="incompatibilita",
                 studente_selezionato=None, livello=3,
                 stato_promemoria_livello=None, parent=None):
        """Crea una riga nuova oppure precompilata.

        Lo stato del promemoria è condiviso dall’intero Editor, separatamente per
        incompatibilità e affinità.
        """
        super().__init__(parent)

        self.tipo_vincolo = tipo_vincolo
        self._stato_promemoria_livello = (
            stato_promemoria_livello
            if stato_promemoria_livello is not None
            else {"incompatibilita": False, "affinita": False}
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)


        self.combo_studente = ComboBoxProtetto()
        self.combo_studente.setMinimumWidth(160)
        self.combo_studente.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if studente_selezionato and studente_selezionato in lista_studenti_disponibili:


            self.combo_studente.addItems(lista_studenti_disponibili)
            self.combo_studente.setCurrentText(studente_selezionato)
        else:


            self.combo_studente.addItem(PLACEHOLDER_VINCOLO)
            self.combo_studente.addItems(lista_studenti_disponibili)
            self.combo_studente.setCurrentText(PLACEHOLDER_VINCOLO)


        # Serve a rimuovere la vecchia copia speculare quando cambia il compagno.
        self._studente_precedente = self.combo_studente.currentText()


        self._aggiorna_stile_combobox()


        self.combo_studente.currentTextChanged.connect(self._on_cambiato)

        layout.addWidget(self.combo_studente, 1)


        self.combo_livello = ComboBoxProtetto()
        self.combo_livello.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


        self.combo_livello.setMinimumWidth(280)


        if tipo_vincolo == "incompatibilita":
            self._etichette_livello = [
                "Liv. 1 — Leggera",
                "Liv. 2 — Media",
                "Liv. 3 — ASSOLUTA (= mai insieme)",
            ]
        else:
            self._etichette_livello = [
                "Liv. 1 — Leggera",
                "Liv. 2 — Buona",
                "Liv. 3 — Forte",
            ]

        for livello_numerico, etichetta in enumerate(
                self._etichette_livello, start=1):
            self.combo_livello.addItem(etichetta, livello_numerico)

        if studente_selezionato:


            indice_livello = self.combo_livello.findData(int(livello))
            if indice_livello < 0:
                raise ValueError(
                    f"Livello vincolo non valido: {livello!r}"
                )
            self.combo_livello.setCurrentIndex(indice_livello)

            self._registrato = True
        else:


            # Il valore interno 0 identifica un livello ancora non scelto.
            self.combo_livello.insertItem(
                0,
                PLACEHOLDER_LIVELLO,
                0
            )
            self.combo_livello.setCurrentIndex(0)

            self._registrato = False


        self._aggiorna_stile_combo_livello()

        self.combo_livello.currentTextChanged.connect(self._on_cambiato)

        layout.addWidget(self.combo_livello, 1)


        btn_rimuovi = QPushButton("Rimuovi")
        applica_icona(btn_rimuovi, "trash-2", 16)
        btn_rimuovi.setMinimumWidth(96)
        btn_rimuovi.setFixedHeight(36)
        btn_rimuovi.setToolTip("Rimuovi questo vincolo")
        btn_rimuovi.setProperty("editorRuolo", "rimuovi_vincolo")
        btn_rimuovi.clicked.connect(self._on_rimosso)
        layout.addWidget(btn_rimuovi)

    def get_studente(self):
        """Restituisce il compagno selezionato, o una stringa vuota se manca."""
        testo = self.combo_studente.currentText()
        if testo == PLACEHOLDER_VINCOLO:
            return ""
        return testo

    def is_placeholder_attivo(self):
        """Indica se manca ancora il compagno."""
        return self.combo_studente.currentText() == PLACEHOLDER_VINCOLO

    def is_placeholder_livello_attivo(self):
        """Indica se manca ancora il livello."""
        return self.combo_livello.currentText() == PLACEHOLDER_LIVELLO

    def _prefisso_colori_vincolo(self):
        """Restituisce la famiglia cromatica del vincolo."""
        if self.tipo_vincolo == "incompatibilita":
            return "combo_incomp"
        return "combo_aff"

    def _stylesheet_combo_vincolo(self, incompleto):
        """Costruisce lo stile dei due menu della riga.

        Il colore identifica il tipo di vincolo; il bordo di avviso segnala un campo
        ancora incompleto senza cancellare tale distinzione.
        """
        prefisso = self._prefisso_colori_vincolo()
        sfondo = C(f"{prefisso}_sf")
        testo_semantico = C(f"{prefisso}_txt")
        bordo_semantico = C(f"{prefisso}_bordo")
        sfondo_selezione = C(f"{prefisso}_selezione_sf")

        bordo = C("combo_ph_bordo") if incompleto else bordo_semantico
        testo_campo = C("combo_ph_txt") if incompleto else testo_semantico
        spessore_bordo = 2 if incompleto else 1

        return f"""
            QComboBox {{
                border: {spessore_bordo}px solid {bordo};
                background-color: {sfondo};
                color: {testo_campo};
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QComboBox::drop-down {{
                width: 28px;
                border-left: 1px solid {bordo_semantico};
                background-color: {sfondo};
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {bordo_semantico};
                background-color: {sfondo};
                color: {testo_semantico};
                selection-background-color: {sfondo_selezione};
                selection-color: {testo_semantico};
                outline: 0;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 26px;
                background-color: {sfondo};
                color: {testo_semantico};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {sfondo_selezione};
                color: {testo_semantico};
            }}
        """

    def _aggiorna_stile_combobox(self):
        """Aggiorna le proprietà semantiche del menu del compagno."""
        _imposta_proprieta_stile(
            self.combo_studente,
            "editorTipoVincolo",
            self.tipo_vincolo,
            ripolisci=False,
        )
        _imposta_proprieta_stile(
            self.combo_studente,
            "editorIncompleto",
            "1" if self.is_placeholder_attivo() else "0",
        )

    def _aggiorna_stile_combo_livello(self):
        """Aggiorna le proprietà semantiche del menu del livello."""
        _imposta_proprieta_stile(
            self.combo_livello,
            "editorTipoVincolo",
            self.tipo_vincolo,
            ripolisci=False,
        )
        _imposta_proprieta_stile(
            self.combo_livello,
            "editorIncompleto",
            "1" if self.is_placeholder_livello_attivo() else "0",
        )

    def get_livello(self):
        """Restituisce il livello numerico, oppure 0 finché manca la scelta."""
        dato_livello = self.combo_livello.currentData()

        try:
            livello = int(dato_livello)
        except (TypeError, ValueError):
            return 0

        return livello if livello in (1, 2, 3) else 0

    def get_studente_precedente(self):
        """Restituisce il compagno registrato prima dell’ultima modifica."""
        if self._studente_precedente == PLACEHOLDER_VINCOLO:
            return ""
        return self._studente_precedente

    def aggiorna_precedente(self):
        """Memorizza il compagno corrente come riferimento sincronizzato."""
        self._studente_precedente = self.combo_studente.currentText()

    def _on_cambiato(self):
        """Gestisce il completamento della riga e notifica la modifica.

        I placeholder vengono rimossi dopo una scelta reale; il promemoria sul livello
        compare una sola volta per tipo nell’intera sessione.
        """

        testo_corrente = self.combo_studente.currentText()


        if testo_corrente != PLACEHOLDER_VINCOLO:
            idx_placeholder = self.combo_studente.findText(PLACEHOLDER_VINCOLO)
            if idx_placeholder >= 0:

                self.combo_studente.blockSignals(True)
                self.combo_studente.removeItem(idx_placeholder)
                self.combo_studente.blockSignals(False)


        testo_livello = self.combo_livello.currentText()


        if testo_livello != PLACEHOLDER_LIVELLO:
            idx_ph_livello = self.combo_livello.findText(PLACEHOLDER_LIVELLO)
            if idx_ph_livello >= 0:
                self.combo_livello.blockSignals(True)
                self.combo_livello.removeItem(idx_ph_livello)
                self.combo_livello.blockSignals(False)


        self._aggiorna_stile_combobox()
        self._aggiorna_stile_combo_livello()


        if (not self.is_placeholder_attivo()
                and self.is_placeholder_livello_attivo()
                and not self._stato_promemoria_livello.get(
                    self.tipo_vincolo, False
                )):
            self._stato_promemoria_livello[self.tipo_vincolo] = True


            QTimer.singleShot(0, self._mostra_promemoria_livello)


        self.vincolo_cambiato.emit()

    def _mostra_promemoria_livello(self):
        """Ricorda di scegliere il livello del vincolo appena aggiunto."""
        if self.tipo_vincolo == "incompatibilita":
            nome_vincolo = "incompatibilità"
            legenda = "~ 1 = Leggera   ~ 2 = Media   ~ 3 = ASSOLUTA"
        else:
            nome_vincolo = "affinità"
            legenda = "~ 1 = Leggera   ~ 2 = Buona   ~ 3 = Forte"

        _popup_info(
            self,
            "Seleziona il livello",
            f"Hai scelto lo studente per una {nome_vincolo}.",
            dettagli=(
                "Ora seleziona anche l'intensità del vincolo:\n"
                f"{legenda}\n\n"
                "Il livello determina quanto l'algoritmo rispetterà "
                "questo vincolo durante l'assegnazione dei posti."
            ),
        )

    def _on_rimosso(self):
        """Notifica la richiesta di rimozione."""
        self.vincolo_rimosso.emit()

    def aggiorna_tema(self):
        """Il tema discende dallo stylesheet unico dell’Editor."""
        return


# La scheda conserva una sola direzione; l’Editor aggiorna quella speculare.
class SchedaStudente(QGroupBox):
    """Scheda collassabile con dati e vincoli di uno studente.

    Comunica all’Editor le modifiche da rendere bidirezionali. La posizione FISSO
    disabilita i vincoli della scheda, che devono essere impostati sugli altri.
    """


    vincolo_modificato_signal = Signal(str, str, str, int, str)

    def __init__(self, cognome, nome, tutti_studenti, sesso="M", posizione="NORMALE",
                 incompatibilita=None, affinita=None,
                 stato_promemoria_livello=None, parent=None):
        """Inizializza la scheda e le relazioni già presenti nel file."""

        self.cognome = cognome
        self.nome = nome
        self.nome_completo = f"{cognome} {nome}"
        super().__init__(self.nome_completo, parent)


        self._espanso = False
        self.setCheckable(False)


        self._tutti_studenti = tutti_studenti


        self._stato_promemoria_livello = (
            stato_promemoria_livello
            if stato_promemoria_livello is not None
            else {"incompatibilita": False, "affinita": False}
        )


        self._aggiornamento_programmatico = False


        self._righe_incompatibilita = []
        self._righe_affinita = []


        self._costruisci_ui(sesso, posizione, incompatibilita or {}, affinita or {})


        self._aggiorna_stile_genere(sesso)

    def _costruisci_ui(self, sesso, posizione, incompatibilita, affinita):
        """Costruisce i controlli della scheda."""


        self._layout_contenuto = QVBoxLayout(self)
        self._layout_contenuto.setSpacing(8)


        self._contenitore = QWidget()
        self._layout_interno = QVBoxLayout(self._contenitore)
        self._layout_interno.setContentsMargins(8, 4, 8, 4)
        self._layout_interno.setSpacing(6)


        riga_base = QHBoxLayout()


        riga_base.addWidget(QLabel("Genere:"))
        self.combo_genere = ComboBoxProtetto()

        if sesso == PLACEHOLDER_GENERE or sesso == "":


            self.combo_genere.addItems([PLACEHOLDER_GENERE, "M", "F"])
            self.combo_genere.setCurrentText(PLACEHOLDER_GENERE)


            self.combo_genere.setProperty("editorGenereIncompleto", "1")
        else:

            self.combo_genere.addItems(["M", "F"])
            self.combo_genere.setCurrentText(sesso)

        if self.combo_genere.property("editorGenereIncompleto") is None:
            self.combo_genere.setProperty("editorGenereIncompleto", "0")
        self.combo_genere.setFixedWidth(70)


        self.combo_genere.currentTextChanged.connect(self._on_genere_cambiato)

        riga_base.addWidget(self.combo_genere)

        riga_base.addSpacing(20)


        riga_base.addWidget(QLabel("Posizione:"))
        self.combo_posizione = ComboBoxProtetto()

        self._mappa_posizioni = {
            "NORMALE (nessuna preferenza)": "NORMALE",
            "PRIMA — VINCOLANTE": "PRIMA",
            "ULTIMA — Preferenza": "ULTIMA",
            "FISSO — Posizione fissa": "FISSO"
        }

        self._mappa_posizioni_inversa = {v: k for k, v in self._mappa_posizioni.items()}
        self.combo_posizione.addItems(list(self._mappa_posizioni.keys()))

        etichetta = self._mappa_posizioni_inversa.get(posizione, "NORMALE (nessuna preferenza)")
        self.combo_posizione.setCurrentText(etichetta)
        self._posizione_confermata = posizione
        self.combo_posizione.setFixedWidth(250)
        riga_base.addWidget(self.combo_posizione)

        riga_base.addStretch()
        self._layout_interno.addLayout(riga_base)


        self._label_info_fisso = QLabel(
            "ℹ️ Questo studente è impostato come FISSO: i suoi vincoli di "
            "incompatibilità e affinità sono disabilitati. Per influenzare "
            "chi gli siede accanto, imposta i vincoli degli altri studenti "
            "verso lo studente FISSO."
        )
        self._label_info_fisso.setProperty("editorRuolo", "info_fisso")
        self._label_info_fisso.setWordWrap(True)
        self._label_info_fisso.setVisible(False)
        self._layout_interno.addWidget(self._label_info_fisso)


        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.HLine)
        self._sep1.setProperty("editorRuolo", "separatore")
        self._layout_interno.addWidget(self._sep1)


        self._label_incomp = QLabel("INCOMPATIBILITÀ:")
        self._label_incomp.setProperty("editorRuolo", "label_incompatibilita")
        self._label_incomp.setProperty("editorAttenuato", "0")
        self._layout_interno.addWidget(self._label_incomp)


        self._container_incomp = QVBoxLayout()
        self._container_incomp.setSpacing(4)
        self._layout_interno.addLayout(self._container_incomp)


        for nome_target, livello in incompatibilita.items():
            self._aggiungi_riga_vincolo("incompatibilita", nome_target, livello, notifica=False)


        self._btn_aggiungi_incomp = QPushButton("Aggiungi incompatibilità")
        applica_icona(self._btn_aggiungi_incomp, "plus", 16)
        self._btn_aggiungi_incomp.setProperty("editorRuolo", "aggiungi_incompatibilita")
        self._btn_aggiungi_incomp.setToolTip("Aggiungi un vincolo di incompatibilità con un altro studente")
        self._btn_aggiungi_incomp.clicked.connect(lambda: self._aggiungi_riga_vincolo("incompatibilita"))
        self._layout_interno.addWidget(self._btn_aggiungi_incomp)


        self._sep2 = QFrame()
        self._sep2.setFrameShape(QFrame.HLine)
        self._sep2.setProperty("editorRuolo", "separatore")
        self._layout_interno.addWidget(self._sep2)


        self._label_aff = QLabel("AFFINITÀ:")
        self._label_aff.setProperty("editorRuolo", "label_affinita")
        self._label_aff.setProperty("editorAttenuato", "0")
        self._layout_interno.addWidget(self._label_aff)


        self._container_aff = QVBoxLayout()
        self._container_aff.setSpacing(4)
        self._layout_interno.addLayout(self._container_aff)


        for nome_target, livello in affinita.items():
            self._aggiungi_riga_vincolo("affinita", nome_target, livello, notifica=False)


        self._btn_aggiungi_aff = QPushButton("Aggiungi affinità")
        applica_icona(self._btn_aggiungi_aff, "plus", 16)
        self._btn_aggiungi_aff.setProperty("editorRuolo", "aggiungi_affinita")
        self._btn_aggiungi_aff.setToolTip("Aggiungi un vincolo di affinità con un altro studente")
        self._btn_aggiungi_aff.clicked.connect(lambda: self._aggiungi_riga_vincolo("affinita"))
        self._layout_interno.addWidget(self._btn_aggiungi_aff)


        self.combo_posizione.currentTextChanged.connect(self._on_posizione_cambiata)


        posizione_iniziale = self._mappa_posizioni.get(
            self.combo_posizione.currentText(), "NORMALE"
        )
        if posizione_iniziale == "FISSO":
            self._imposta_vincoli_abilitati(False)


        self._layout_contenuto.addWidget(self._contenitore)


        self._contenitore.setVisible(False)
        self.setTitle(self.nome_completo)

    def _get_studenti_disponibili(self, tipo_vincolo):
        """Restituisce i compagni selezionabili per un nuovo vincolo.

        Esclude lo studente corrente, i FISSO e i nomi già usati in entrambe le
        sezioni, così una coppia non può essere duplicata o contraddittoria.
        """

        disponibili = [s for s in self._tutti_studenti if s != self.nome_completo]


        righe_stessa_sezione = (
            self._righe_incompatibilita if tipo_vincolo == "incompatibilita"
            else self._righe_affinita
        )
        gia_usati_stessa = {riga.get_studente() for riga in righe_stessa_sezione}


        righe_sezione_opposta = (
            self._righe_affinita if tipo_vincolo == "incompatibilita"
            else self._righe_incompatibilita
        )
        gia_usati_opposta = {riga.get_studente() for riga in righe_sezione_opposta}


        tutti_esclusi = gia_usati_stessa | gia_usati_opposta
        disponibili = [s for s in disponibili if s not in tutti_esclusi]

        return disponibili

    def _aggiungi_riga_vincolo(self, tipo, studente_target=None, livello=3, notifica=True):
        """Aggiunge una riga di incompatibilità o affinità."""

        disponibili = self._get_studenti_disponibili(tipo)

        if not disponibili:


            _popup_info(
                self,
                "Nessuno studente disponibile",
                "Non ci sono altri studenti selezionabili.",
                dettagli=(
                    "Tutti gli studenti sono già presenti tra le "
                    "incompatibilità o le affinità di questo studente."
                ),
            )
            return


        riga = RigaVincolo(
            disponibili,
            tipo_vincolo=tipo,
            studente_selezionato=studente_target,
            livello=livello,
            stato_promemoria_livello=self._stato_promemoria_livello
        )


        riga.vincolo_cambiato.connect(lambda: self._on_vincolo_cambiato(riga, tipo))
        riga.vincolo_rimosso.connect(lambda: self._on_vincolo_rimosso(riga, tipo))


        if tipo == "incompatibilita":
            self._container_incomp.addWidget(riga)
            self._righe_incompatibilita.append(riga)
        else:
            self._container_aff.addWidget(riga)
            self._righe_affinita.append(riga)


        if notifica and not self._aggiornamento_programmatico:
            studente_b = riga.get_studente()
            livello_b = riga.get_livello()
            if studente_b and livello_b > 0:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, studente_b, tipo, livello_b, "aggiungi"
                )

    def _on_vincolo_cambiato(self, riga, tipo):
        """Propaga all’Editor la modifica di una relazione."""
        if self._aggiornamento_programmatico:
            return

        nuovo_studente = riga.get_studente()
        livello = riga.get_livello()


        if livello == 0 or not nuovo_studente:


            if nuovo_studente or livello > 0:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente or "incompleto",
                    tipo, 0, "incompleto"
                )
            riga.aggiorna_precedente()
            return

        vecchio_studente = riga.get_studente_precedente()

        if not riga._registrato:


            self.vincolo_modificato_signal.emit(
                self.nome_completo, nuovo_studente, tipo, livello, "aggiungi"
            )
            riga._registrato = True
        elif vecchio_studente != nuovo_studente:


            if vecchio_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, vecchio_studente, tipo, 0, "rimuovi"
                )
            if nuovo_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente, tipo, livello, "aggiungi"
                )
        else:

            if nuovo_studente:
                self.vincolo_modificato_signal.emit(
                    self.nome_completo, nuovo_studente, tipo, livello, "modifica"
                )


        riga.aggiorna_precedente()

    def _on_vincolo_rimosso(self, riga, tipo):
        """Rimuove una riga e propaga la cancellazione speculare."""

        studente_b = riga.get_studente()
        era_registrato = riga._registrato


        if tipo == "incompatibilita":
            if riga in self._righe_incompatibilita:
                self._righe_incompatibilita.remove(riga)
        else:
            if riga in self._righe_affinita:
                self._righe_affinita.remove(riga)


        riga.setParent(None)
        riga.deleteLater()


        if not self._aggiornamento_programmatico and studente_b and era_registrato:
            self.vincolo_modificato_signal.emit(
                self.nome_completo, studente_b, tipo, 0, "rimuovi"
            )


        if not self._aggiornamento_programmatico and not era_registrato:
            self.vincolo_modificato_signal.emit(
                self.nome_completo, studente_b or "",
                tipo, 0, "rimosso_incompleto"
            )


    def aggiungi_vincolo_programmatico(self, tipo, studente_target, livello):
        """Aggiunge la copia speculare di un vincolo senza duplicarla."""

        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        for riga in righe:
            if riga.get_studente() == studente_target:
                return


        self._aggiornamento_programmatico = True
        self._aggiungi_riga_vincolo(tipo, studente_target, livello, notifica=False)
        self._aggiornamento_programmatico = False

    def modifica_vincolo_programmatico(self, tipo, studente_target, nuovo_livello):
        """Aggiorna il livello della copia speculare."""
        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        self._aggiornamento_programmatico = True
        for riga in righe:
            if riga.get_studente() == studente_target:


                indice = riga.combo_livello.findData(
                    int(nuovo_livello)
                )
                if indice < 0:
                    raise ValueError(
                        f"Livello vincolo non valido: "
                        f"{nuovo_livello!r}"
                    )
                riga.combo_livello.setCurrentIndex(indice)
                break
        self._aggiornamento_programmatico = False

    def rimuovi_vincolo_programmatico(self, tipo, studente_target):
        """Rimuove la copia speculare di un vincolo."""
        righe = self._righe_incompatibilita if tipo == "incompatibilita" else self._righe_affinita
        self._aggiornamento_programmatico = True
        for riga in list(righe):
            if riga.get_studente() == studente_target:
                righe.remove(riga)
                riga.setParent(None)
                riga.deleteLater()
                break
        self._aggiornamento_programmatico = False

    def get_dati(self):
        """Restituisce i dati correnti della scheda in forma serializzabile."""
        incomp = {}
        for riga in self._righe_incompatibilita:
            studente = riga.get_studente()
            livello = riga.get_livello()


            if studente and livello > 0:
                incomp[studente] = livello

        aff = {}
        for riga in self._righe_affinita:
            studente = riga.get_studente()
            livello = riga.get_livello()

            if studente and livello > 0:
                aff[studente] = livello

        return {
            "cognome": self.cognome,
            "nome": self.nome,
            "sesso": self.combo_genere.currentText(),


            "posizione": self._mappa_posizioni.get(
                self.combo_posizione.currentText(), "NORMALE"
            ),
            "incompatibilita": incomp,
            "affinita": aff
        }

    def _on_genere_cambiato(self, nuovo_valore):
        """Registra il genere scelto e aggiorna lo stile della scheda."""
        if nuovo_valore in ("M", "F"):

            idx_placeholder = self.combo_genere.findText(PLACEHOLDER_GENERE)
            if idx_placeholder >= 0:
                self.combo_genere.removeItem(idx_placeholder)

            _imposta_proprieta_stile(
                self.combo_genere, "editorGenereIncompleto", "0"
            )


        self._aggiorna_stile_genere(nuovo_valore)

    def _on_posizione_cambiata(self, nuova_etichetta):
        """Aggiorna la posizione interna e lo stato dei vincoli."""
        posizione_interna = self._mappa_posizioni.get(nuova_etichetta, "NORMALE")
        is_fisso = (posizione_interna == "FISSO")
        self._imposta_vincoli_abilitati(not is_fisso)


        sesso_attuale = self.combo_genere.currentText()
        self._aggiorna_stile_genere(sesso_attuale)

    def _imposta_vincoli_abilitati(self, abilitato: bool):
        """Abilita o disabilita entrambe le sezioni dei vincoli.

        Quando la posizione è FISSO, le righe esistenti restano visibili ma inattive.
        """

        self._btn_aggiungi_incomp.setEnabled(abilitato)
        self._btn_aggiungi_aff.setEnabled(abilitato)


        stato_attenuato = "0" if abilitato else "1"
        _imposta_proprieta_stile(
            self._label_incomp, "editorAttenuato", stato_attenuato
        )
        _imposta_proprieta_stile(
            self._label_aff, "editorAttenuato", stato_attenuato
        )


        for riga in self._righe_incompatibilita:
            riga.setEnabled(abilitato)
        for riga in self._righe_affinita:
            riga.setEnabled(abilitato)


        self._label_info_fisso.setVisible(not abilitato)

    def conferma_posizione_corrente(self):
        """Memorizza la posizione corrente come ultimo valore valido."""
        self._posizione_confermata = self.get_dati()["posizione"]

    def ripristina_posizione_confermata(self):
        """Ripristina senza segnali la posizione valida precedente."""
        posizione = getattr(self, "_posizione_confermata", "NORMALE")
        etichetta = self._mappa_posizioni_inversa.get(
            posizione,
            self._mappa_posizioni_inversa["NORMALE"],
        )
        segnali_bloccati = self.combo_posizione.blockSignals(True)
        try:
            self.combo_posizione.setCurrentText(etichetta)
        finally:
            self.combo_posizione.blockSignals(segnali_bloccati)
        self._on_posizione_cambiata(etichetta)

    def genere_impostato(self):
        """Indica se il genere è stato scelto."""
        return self.combo_genere.currentText() in ("M", "F")

    def _aggiorna_stile_genere(self, sesso):
        """Aggiorna la proprietà semantica della scheda."""

        etichetta_posizione = self.combo_posizione.currentText()
        posizione_interna = self._mappa_posizioni.get(
            etichetta_posizione, "NORMALE"
        )
        is_fisso = posizione_interna == "FISSO"

        if sesso not in ("M", "F"):
            stato = "X"
        elif is_fisso:
            stato = f"FISSO_{sesso}"
        else:
            stato = sesso

        _imposta_proprieta_stile(self, "editorScheda", stato)


    def aggiorna_tema(self):
        """Il tema discende dallo stylesheet unico dell’Editor."""
        return

    def mousePressEvent(self, event):
        """Collassa o espande la scheda quando si preme il titolo."""

        if event.position().y() < 24:
            self._espanso = not self._espanso
            self._contenitore.setVisible(self._espanso)

            self.setTitle(self.nome_completo)
        super().mousePressEvent(event)


# Coordina validazione, sincronizzazione e persistenza dell’intera classe.
class EditorStudentiWidget(QWidget):
    """Editor integrabile come scheda o finestra autonoma.

    Riconosce file base e completi, costruisce le schede, sincronizza i vincoli in
    entrambe le direzioni, controlla i dati pendenti e salva il file della classe.
    """


    # I segnali tengono allineati Editor e finestra principale.
    file_cambiato_signal = Signal()


    file_chiuso_signal = Signal()


    dati_modificati_signal = Signal()


    genere_cambiato_signal = Signal()


    file_salvato_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)


        self._schede_studenti = []

        self._lista_nomi = []

        self._nome_file_caricato = ""

        self._percorso_file_caricato = ""


        # Guardia contro il rimbalzo infinito delle modifiche speculari.
        self._sincronizzazione_in_corso = False


        self._modifiche_non_salvate = False


        self._callback_pre_caricamento = None
        self._callback_pre_chiusura_file = None


        self._correzioni_applicate = False


        # Lo stato vive per l’intera sessione, non per singola scheda.
        self._promemoria_livello_mostrato = {
            "incompatibilita": False,
            "affinita": False,
        }


        self._costruisci_ui()

        # Schede, righe dei vincoli e area di scorrimento ereditano il QSS
        # unico installato dalla finestra principale. Uno stylesheet locale
        # conserverebbe invece i colori del tema attivo all’avvio.

        self.dati_modificati_signal.connect(self._aggiorna_contatore_vincoli)

    def _stylesheet_componenti_dinamici(self):
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

    def aggiorna_tema(self):
        """Riapplica il tema all’intero Editor."""

        profilo = ProfiloGUI("editor_tema_dettaglio")
        try:
            # Il QSS dei componenti ripetuti e della QScrollArea è globale:
            # qui restano soltanto i pochi stili inline non ereditabili.

            profilo.misura(
                "label_apri_info",
                lambda: self.label_apri_info.setStyleSheet(
                    f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
                ),
            )

            self._aggiorna_stili_bottoni_editor(profilo=profilo)

            profilo.misura(
                "banner_formato_base",
                lambda: self._banner_formato_base.setStyleSheet(f"""
                    background-color: {C("label_attenzione_bg")};
                    border-radius: 6px;
                    border: 1px solid {C("label_attenzione_bordo")};
                """),
            )
            profilo.misura(
                "banner_formato_base_testo",
                lambda: self._banner_formato_base_testo.setStyleSheet(f"""
                    color: {C("banner_formato_txt")};
                    font-weight: bold;
                    font-size: 13px;
                """),
            )

            if self._schede_studenti:
                self._aggiorna_contatore_vincoli(profilo=profilo)
        finally:
            profilo.chiudi()

    def _aggiorna_stili_bottoni_editor(self, profilo=None):
        """Aggiorna gli stili dei comandi dell’Editor."""

        def applica(nome, widget, css):
            return _misura_profilo(
                profilo,
                f"bottone_{nome}",
                lambda: widget.setStyleSheet(css),
            )

        def stile(bg, hover, testo, bordo, *, font_size=13,
                  padding="6px 10px", raggio=6, disabilitato=True):
            css = f"""
                QPushButton {{
                    background-color: {bg};
                    color: {testo};
                    border: 1px solid {bordo};
                    font-size: {font_size}px;
                    font-weight: bold;
                    border-radius: {raggio}px;
                    padding: {padding};
                }}
                QPushButton:hover {{
                    background-color: {hover};
                    border-color: {bordo};
                }}
            """
            if disabilitato:
                css += f"""
                QPushButton:disabled {{
                    background-color: {C('btn_azione_disabled_bg')};
                    color: {C('btn_azione_disabled_txt')};
                    border-color: {C('btn_azione_disabled_bordo')};
                }}
                """
            return css

        applica("apri_cartella", self.btn_apri_cartella, stile(
            C("editor_btn_cartella_bg"),
            C("editor_btn_cartella_hover"),
            C("editor_btn_cartella_txt"),
            C("editor_btn_cartella_bordo"),
        ))
        applica("carica", self.btn_carica, stile(
            C("editor_btn_classe_bg"),
            C("editor_btn_classe_hover"),
            C("editor_btn_classe_txt"),
            C("editor_btn_classe_bordo"),
        ))
        applica("esporta", self.btn_esporta, stile(
            C("btn_salva_bg"), C("btn_salva_hover"),
            C("btn_salva_txt"), C("btn_salva_bordo"),
        ))

        stile_neutro = stile(
            C("editor_btn_neutro_bg"),
            C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"),
            C("editor_btn_neutro_bordo"),
            font_size=12, raggio=5,
        )
        applica("toggle_schede", self.btn_toggle_schede, stile_neutro)
        applica("dettaglio_vincoli", self._btn_dettaglio_vincoli, stile_neutro)

        applica("preview", self.btn_preview, stile(
            C("btn_indaco_bg"), C("btn_indaco_hover"),
            C("btn_indaco_txt"), C("btn_indaco_bordo"),
            padding="10px 20px",
        ))
        applica("chiudi", self.btn_chiudi, stile(
            C("editor_btn_neutro_bg"),
            C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"),
            C("editor_btn_neutro_bordo"),
            padding="10px 20px",
        ))

    def _popola_placeholder_file_non_selezionato(self):
        """Mostra lo stato iniziale senza una classe caricata."""
        self._logo_placeholder = QLabel()
        percorso_logo = get_resource_path(
            "icone",
            "postiperfetti_logo.png",
        )

        if os.path.exists(percorso_logo):
            pixmap = QPixmap(percorso_logo)
            pixmap = pixmap.scaled(
                320,
                150,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._logo_placeholder.setPixmap(pixmap)
        else:

            self._logo_placeholder.setText("«PostiPerfetti»")
            self._logo_placeholder.setStyleSheet("font-size: 36px;")

        self._logo_placeholder.setAlignment(Qt.AlignCenter)

        self._label_placeholder = QLabel(
            "NESSUN FILE SELEZIONATO.\n\n"
            "• Clicca su 'Apri cartella' per creare un nuovo file .txt in formato BASE con\n"
            "'Cognome;Nome;M/F' degli allievi (uno per riga, in ordine alfabetico).\n\n"
            "• Clicca su 'Seleziona classe' per modificare posizione e vincoli degli studenti\n"
            "di una classe presente in un file .txt già creato in precedenza.\n\n"
        )
        self._label_placeholder.setAlignment(Qt.AlignCenter)
        self._label_placeholder.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 20px;"
        )


        self.layout_schede.addStretch()
        self.layout_schede.addWidget(
            self._logo_placeholder,
            alignment=Qt.AlignHCenter
        )
        self.layout_schede.addSpacing(12)
        self.layout_schede.addWidget(self._label_placeholder)
        self.layout_schede.addStretch()

    def _costruisci_ui(self):
        """Costruisce l’interfaccia dell’Editor."""

        layout_principale = QVBoxLayout(self)
        layout_principale.setSpacing(10)


        header = QHBoxLayout()


        self.btn_apri_cartella = QPushButton("Apri cartella")
        applica_icona(self.btn_apri_cartella, "folder-open", 18)
        self.btn_apri_cartella.setMinimumHeight(40)
        self.btn_apri_cartella.setToolTip(
            "Apre la cartella delle classi nel file manager del sistema.\n"
            "Qui puoi creare un nuovo file .txt con la lista degli studenti."
        )
        self.btn_apri_cartella.clicked.connect(self._apri_cartella_classi)
        header.addWidget(self.btn_apri_cartella)


        self.label_apri_info = QLabel("CREA qui la classe")
        self.label_apri_info.setStyleSheet(
            f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
        )
        header.addWidget(self.label_apri_info)

        header.addSpacing(8)


        self.btn_carica = QPushButton("Seleziona classe")
        applica_icona(self.btn_carica, "file-search-corner", 18)
        self.btn_carica.setMinimumHeight(40)
        self.btn_carica.setToolTip(
            "Seleziona un file .txt dalla cartella classi\n"
            "per modificare posizione e vincoli degli studenti"
        )
        self.btn_carica.clicked.connect(self._carica_file)
        header.addWidget(self.btn_carica)

        header.addSpacing(8)


        self.btn_esporta = QPushButton("SALVA e CARICA")
        applica_icona(self.btn_esporta, "save", 18)
        self.btn_esporta.setMinimumHeight(40)
        self.btn_esporta.setEnabled(False)
        self.btn_esporta.setToolTip("Salva il file completo con tutti i dati e vincoli degli studenti")
        self.btn_esporta.clicked.connect(self._esporta_file)
        header.addWidget(self.btn_esporta)


        header.addStretch()
        layout_principale.addLayout(header)


        self._dati_riga_info = None

        self.label_contatore_vincoli = QLabel("")
        self.label_contatore_vincoli.setTextFormat(Qt.RichText)
        self.label_contatore_vincoli.setWordWrap(True)
        self.label_contatore_vincoli.setStyleSheet("font-size: 14px;")
        self.label_contatore_vincoli.setVisible(False)


        self._schede_tutte_espanse = False
        self.btn_toggle_schede = QPushButton("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setMinimumHeight(36)
        self.btn_toggle_schede.setMinimumWidth(190)
        self.btn_toggle_schede.setEnabled(False)
        self.btn_toggle_schede.setVisible(False)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.clicked.connect(self._alterna_schede)

        self._btn_dettaglio_vincoli = QPushButton("Dettaglio vincoli")
        applica_icona(self._btn_dettaglio_vincoli, "list-tree", 16)
        self._btn_dettaglio_vincoli.setMinimumHeight(36)
        self._btn_dettaglio_vincoli.setMinimumWidth(190)
        self._btn_dettaglio_vincoli.setToolTip(
            "Mostra l'elenco completo dei vincoli (con i nomi), raggruppato per categoria"
        )
        self._btn_dettaglio_vincoli.setVisible(False)
        self._btn_dettaglio_vincoli.clicked.connect(self._mostra_dettaglio_vincoli)


        self.label_contatore_vincoli.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        colonna_azioni_vincoli = QVBoxLayout()
        colonna_azioni_vincoli.setSpacing(6)
        colonna_azioni_vincoli.addStretch(1)
        colonna_azioni_vincoli.addWidget(self.btn_toggle_schede)
        colonna_azioni_vincoli.addWidget(self._btn_dettaglio_vincoli)
        colonna_azioni_vincoli.addStretch(1)

        riga_contatore = QHBoxLayout()
        riga_contatore.setSpacing(10)
        riga_contatore.addWidget(self.label_contatore_vincoli, 1)
        riga_contatore.addLayout(colonna_azioni_vincoli)
        layout_principale.addLayout(riga_contatore)


        self._banner_formato_base = QWidget()
        layout_banner_base = QHBoxLayout(self._banner_formato_base)
        layout_banner_base.setContentsMargins(12, 9, 12, 9)
        layout_banner_base.setSpacing(10)

        self._banner_formato_base_icona = QLabel()
        self._banner_formato_base_icona.setFixedSize(26, 26)
        self._banner_formato_base_icona.setAlignment(Qt.AlignCenter)
        applica_icona_etichetta(
            self._banner_formato_base_icona, "triangle-alert", 22
        )
        layout_banner_base.addWidget(
            self._banner_formato_base_icona, alignment=Qt.AlignTop
        )

        self._banner_formato_base_testo = QLabel(
            "FORMATO BASE — Prima di salvare, verifica il genere e la "
            "posizione di ogni studente. Incompatibilità e affinità sono "
            "facoltative e possono essere aggiunte quando servono. "
            "Poi clicca «SALVA e CARICA»."
        )
        self._banner_formato_base_testo.setWordWrap(True)
        layout_banner_base.addWidget(self._banner_formato_base_testo, 1)

        self._banner_formato_base.setStyleSheet(f"""
            background-color: {C("label_attenzione_bg")};
            border-radius: 6px;
            border: 1px solid {C("label_attenzione_bordo")};
        """)
        self._banner_formato_base_testo.setStyleSheet(f"""
            color: {C("banner_formato_txt")};
            font-weight: bold;
            font-size: 13px;
        """)
        self._banner_formato_base.setVisible(False)
        layout_principale.addWidget(self._banner_formato_base)


        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setProperty("editorRuolo", "scroll_area")

        self.widget_scroll = QWidget()
        self.layout_schede = QVBoxLayout(self.widget_scroll)
        self.layout_schede.setSpacing(12)
        self.layout_schede.setContentsMargins(10, 10, 10, 10)


        self._popola_placeholder_file_non_selezionato()
        self.scroll_area.setWidget(self.widget_scroll)


        layout_principale.addWidget(self.scroll_area, 1)


        footer = QHBoxLayout()
        footer.setSpacing(12)


        self.btn_preview = QPushButton("Anteprima file classe (.txt)")
        applica_icona(self.btn_preview, "eye", 18)
        self.btn_preview.setMinimumHeight(45)
        self.btn_preview.setEnabled(False)
        self.btn_preview.setToolTip("Mostra un'anteprima del file .txt che verrà generato")
        self.btn_preview.clicked.connect(self._mostra_preview)
        footer.addWidget(self.btn_preview)

        footer.addStretch()


        self.btn_chiudi = QPushButton("CHIUDI FILE")
        applica_icona(self.btn_chiudi, "x", 18)
        self.btn_chiudi.setMinimumHeight(45)
        self.btn_chiudi.setEnabled(False)
        self.btn_chiudi.setToolTip("Chiudi il file corrente (chiederà conferma se ci sono modifiche)")
        self.btn_chiudi.clicked.connect(self._chiudi_editor)
        footer.addWidget(self.btn_chiudi)

        layout_principale.addLayout(footer)


        self._aggiorna_stili_bottoni_editor()


    def _carica_file(self):
        """Seleziona e valida transazionalmente un file di classe."""
        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se selezioni un'altra classe ora, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return

        if self._callback_pre_caricamento is not None:
            if not self._callback_pre_caricamento():
                return

        if self._modifiche_non_salvate:
            azione = self._conferma_chiusura()
            if azione == "salva":
                self._esporta_file()
                if self._modifiche_non_salvate:
                    return
            elif azione == "annulla":
                return

        percorso, _ = QFileDialog.getOpenFileName(
            self,
            "SELEZIONA CLASSE (.txt)",
            self._get_cartella_classi(),
            "File di testo (*.txt);;Tutti i file (*)",
        )
        if not percorso:
            return

        try:
            risultato = carica_file_classe(percorso)
        except FileClasseVuoto:
            _popup_avviso(
                self,
                "File vuoto",
                "Il file non contiene righe utili.",
            )
            return
        except ErroreCodificaFileClasse as errore:
            DialogoErroreFileClasse(
                self,
                "Codifica del file non supportata",
                percorso,
                f"{errore}\n\nIl nuovo file non è stato caricato.",
            ).exec()
            return
        except ErroreValidazioneFileClasse as errore:
            testo = "\n".join(f"• {voce}" for voce in errore.errori[:20])
            if len(errore.errori) > 20:
                testo += f"\n\n... e altri {len(errore.errori) - 20} errori."

            if errore.formato == FORMATO_COMPLETO:
                titolo = "File completo non valido"
                istruzione = "Correggi il file .txt e selezionalo di nuovo."
            elif errore.formato == FORMATO_BASE:
                titolo = "File base non valido"
                istruzione = "Correggi i dati indicati nel file .txt e selezionalo di nuovo."
            else:
                titolo = "Formato non valido"
                istruzione = (
                    "Un file BASE deve avere 2 o 3 campi per riga; "
                    "un file COMPLETO deve averne esattamente 6."
                )

            DialogoErroreFileClasse(
                self,
                titolo,
                percorso,
                f"{testo}\n\n{istruzione}",
            ).exec()
            return
        except Exception as errore:
            _popup_errore(
                self,
                "Lettura del file non riuscita",
                "Impossibile leggere il file selezionato.",
                dettagli=str(errore),
            )
            return

        if risultato.get("conversione_utf8_disponibile"):
            codifica = risultato.get("codifica_sorgente", "UTF-16")
            dialog = crea_popup_semantico(
                self,
                "Conversione UTF-8",
                (
                    f"Il file usa la codifica {codifica}, mentre "
                    "PostiPerfetti utilizza UTF-8."
                ),
                "file-check",
                testo_informativo=(
                    "Vuoi crearne automaticamente una copia compatibile "
                    "senza modificare il contenuto del file originale?"
                ),
                messaggio_in_grassetto=True,
            )
            btn_converti = dialog.addButton(
                "Crea copia UTF-8 e carica", QMessageBox.AcceptRole
            )
            applica_icona(btn_converti, "file-check", 18)
            btn_annulla = dialog.addButton("Annulla", QMessageBox.RejectRole)
            applica_icona(btn_annulla, "x", 18)
            dialog.setDefaultButton(btn_converti)
            dialog.setEscapeButton(btn_annulla)
            dialog.exec()
            if dialog.clickedButton() != btn_converti:
                return

            try:
                percorso_copia = crea_copia_utf8_file_classe(percorso)
                risultato = carica_file_classe(percorso_copia)
            except Exception as errore:
                _popup_errore(
                    self,
                    "Conversione UTF-8 non riuscita",
                    "Non è stato possibile creare la copia compatibile.",
                    dettagli=(
                        f"Il file originale non è stato modificato.\n\n{errore}"
                    ),
                )
                return

            percorso = os.fspath(percorso_copia)

        if risultato.get("codifica_legacy"):
            dialog = crea_popup_semantico(
                self,
                "Codifica precedente rilevata",
                "Il file non è in UTF-8.",
                "triangle-alert",
                testo_informativo=(
                    f"{risultato.get('avviso_codifica', '')}\n\n"
                    "Vuoi caricarlo comunque nell’Editor? La classe già aperta "
                    "resterà invariata se scegli Annulla."
                ),
                messaggio_in_grassetto=True,
            )
            btn_carica = dialog.addButton(
                "Carica e controlla", QMessageBox.AcceptRole
            )
            applica_icona(btn_carica, "file-check", 18)
            btn_annulla = dialog.addButton("Annulla", QMessageBox.RejectRole)
            applica_icona(btn_annulla, "x", 18)
            dialog.setDefaultButton(btn_annulla)
            dialog.setEscapeButton(btn_annulla)
            dialog.exec()
            if dialog.clickedButton() != btn_carica:
                return

        # Soltanto un risultato completamente validato e accettato sostituisce la classe aperta.
        self._nome_file_caricato = os.path.splitext(os.path.basename(percorso))[0]
        self._percorso_file_caricato = percorso
        formato = risultato["formato"]

        if formato == FORMATO_COMPLETO:
            self._correzioni_applicate = bool(
                risultato["avvisi"]
                or risultato["vincoli_aggiunti"]
                or risultato.get("codifica_legacy")
            )
            self._popola_editor(risultato["studenti"], FORMATO_COMPLETO)

            segnalazioni = list(risultato["avvisi"])
            for vincolo in risultato["vincoli_aggiunti"]:
                tipo_visibile = (
                    "Incompatibilità"
                    if vincolo["tipo"] == "incompatibilita"
                    else "Affinità"
                )
                segnalazioni.append(
                    f"{tipo_visibile}: aggiunto il vincolo speculare: "
                    f"{vincolo['target']} → {vincolo['sorgente']} "
                    f"(livello {vincolo['livello']})."
                )

            if segnalazioni:
                testo = "\n".join(f"• {voce}" for voce in segnalazioni[:20])
                if len(segnalazioni) > 20:
                    testo += (
                        f"\n\n... e altre {len(segnalazioni) - 20} "
                        "segnalazioni."
                    )
                _popup_info(
                    self,
                    "Normalizzazioni sicure applicate",
                    "Il file è stato caricato con alcune correzioni automatiche sicure.",
                    dettagli=testo,
                )
        else:
            self._correzioni_applicate = False
            self._popola_editor(risultato["studenti"], FORMATO_BASE)

        self.file_cambiato_signal.emit()


    def _popola_editor(self, studenti_dati, formato):
        """Crea le schede a partire dai dati validati."""


        studenti_dati, riordino_avvenuto = ordina_studenti(studenti_dati)


        if riordino_avvenuto:
            QTimer.singleShot(0, lambda: _popup_info(
                                             self,
                                             "Elenco riordinato",
                                             "L'elenco studenti è stato riordinato alfabeticamente.",
                                             dettagli=(
                                                 "È cambiato soltanto l'ordine di visualizzazione; "
                                                 "nessun altro dato è stato modificato."
                                             ),
                                         ))


        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()


        if self._label_placeholder:
            self._label_placeholder.setParent(None)
            self._label_placeholder.deleteLater()
            self._label_placeholder = None


        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()


        self._lista_nomi = [f"{s['cognome']} {s['nome']}" for s in studenti_dati]


        for dati in studenti_dati:
            scheda = SchedaStudente(
                cognome=dati["cognome"],
                nome=dati["nome"],
                tutti_studenti=self._lista_nomi,
                sesso=dati["sesso"],
                posizione=dati["posizione"],
                incompatibilita=dati["incompatibilita"],
                affinita=dati["affinita"],
                stato_promemoria_livello=self._promemoria_livello_mostrato
            )


            scheda.vincolo_modificato_signal.connect(self._sincronizza_vincolo)


            scheda.combo_genere.currentTextChanged.connect(
                lambda _: (
                    self._segna_modificato(),
                    self.genere_cambiato_signal.emit(),
                    self._aggiorna_contatore_vincoli(),
                )
            )


            scheda.combo_posizione.currentTextChanged.connect(
                lambda _, s=scheda: self._on_posizione_cambiata_editor(s)
            )

            self.layout_schede.addWidget(scheda)
            self._schede_studenti.append(scheda)


        self.layout_schede.addStretch()


        self.btn_preview.setEnabled(True)
        self.btn_esporta.setEnabled(True)
        self._schede_tutte_espanse = False
        self.btn_toggle_schede.setText("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.setEnabled(True)
        self.btn_chiudi.setEnabled(True)


        if formato == "BASE":
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True
        else:


            self._modifiche_non_salvate = self._correzioni_applicate


        if formato == "BASE":

            descrizione_formato = "formato BASE"


            self._banner_formato_base.setVisible(True)


            _popup_info(
                self,
                "File in formato base",
                f"Il file «{self._nome_file_caricato}.txt» contiene soltanto "
                "cognome e nome, con il genere solo se era già indicato.",
                dettagli=(
                    "Prima di usare «SALVA e CARICA», verifica il genere e la "
                    "posizione di ciascuno studente. Incompatibilità e affinità "
                    "sono facoltative:\n\n"
                    "  • posizione (PRIMA, NORMALE, ULTIMA o FISSO)\n"
                    "  • eventuali incompatibilità\n"
                    "  • eventuali affinità\n\n"
                    "Senza vincoli, l'assegnazione sarà basata soltanto sulle regole "
                    "generali e sulla rotazione. Potrai aggiungerli o modificarli "
                    "in seguito riselezionando il file."
                ),
            )
        else:

            descrizione_formato = "formato COMPLETO"

            self._banner_formato_base.setVisible(False)


        self._dati_riga_info = {
            "nome": self._nome_file_caricato,
            "num": len(studenti_dati),
            "formato": descrizione_formato,
        }


        if formato == "COMPLETO":
            self._controlla_anomalie_editor()


        self._aggiorna_contatore_vincoli()


    def _alterna_schede(self):
        """Espande o comprime tutte le schede."""
        if self._schede_tutte_espanse:
            self._comprimi_tutti()
            self._schede_tutte_espanse = False
            self.btn_toggle_schede.setText("Espandi schede")
            applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
            self.btn_toggle_schede.setToolTip(
                "Espandi tutte le schede per vedere i dettagli"
            )
        else:
            self._espandi_tutti()
            self._schede_tutte_espanse = True
            self.btn_toggle_schede.setText("Comprimi schede")
            applica_icona(self.btn_toggle_schede, "fold-vertical", 16)
            self.btn_toggle_schede.setToolTip(
                "Comprimi tutte le schede per una visione d'insieme"
            )

    def _espandi_tutti(self):
        """Espande tutte le schede."""
        for scheda in self._schede_studenti:
            scheda._espanso = True
            scheda._contenitore.setVisible(True)
            scheda.setTitle(scheda.nome_completo)

    def _comprimi_tutti(self):
        """Comprime tutte le schede."""
        for scheda in self._schede_studenti:
            scheda._espanso = False
            scheda._contenitore.setVisible(False)
            scheda.setTitle(scheda.nome_completo)


    def get_vincoli_incompleti(self):
        """Restituisce le relazioni prive del compagno o del livello.

        La stessa guardia viene usata prima del salvataggio, della chiusura e
        dell’avvio dell’assegnazione.
        """
        vincoli_incompleti = []
        for scheda in self._schede_studenti:

            for riga in scheda._righe_incompatibilita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(incompatibilità senza livello)"
                    )

            for riga in scheda._righe_affinita:
                studente = riga.get_studente()
                if studente and riga.is_placeholder_livello_attivo():
                    vincoli_incompleti.append(
                        f"  • {scheda.nome_completo} ↔ {studente} "
                        f"(affinità senza livello)"
                    )
        return vincoli_incompleti

    def _segna_modificato(self):
        """Registra modifiche non salvate e le comunica alla finestra principale."""
        self._modifiche_non_salvate = True
        self.dati_modificati_signal.emit()

    def _on_posizione_cambiata_editor(self, scheda_modificata):
        """Accetta una posizione valida e annulla un secondo FISSO."""
        dati = scheda_modificata.get_dati()
        if dati["posizione"] != "FISSO":
            scheda_modificata.conferma_posizione_corrente()
            self._segna_modificato()
            return

        studenti_fisso = [
            scheda.nome_completo
            for scheda in self._schede_studenti
            if scheda.get_dati()["posizione"] == "FISSO"
        ]
        if len(studenti_fisso) <= 1:
            scheda_modificata.conferma_posizione_corrente()
            self._segna_modificato()
            return

        scheda_modificata.ripristina_posizione_confermata()
        elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
        _popup_avviso(
            self,
            "Troppi studenti con posizione FISSO",
            "Al massimo uno studente può avere posizione FISSO.",
            dettagli=(
                f"La modifica è stata annullata. Prima del ripristino erano "
                f"{quantita(len(studenti_fisso), 'studente', 'studenti')} "
                f"con posizione FISSO:\n\n{elenco}"
            ),
        )


    def _sincronizza_vincolo(self, studente_a, studente_b, tipo, livello, azione):
        """Mantiene identiche le due direzioni di una relazione.

        Aggiunge, aggiorna o rimuove la copia speculare senza riattivare ricorsivamente
        i segnali dell’Editor.
        """

        # Le copie programmatiche non devono generare una nuova sincronizzazione.
        if self._sincronizzazione_in_corso:
            return


        if azione == "incompleto":
            self.dati_modificati_signal.emit()
            return


        if azione == "rimosso_incompleto":
            self.dati_modificati_signal.emit()
            return


        self._sincronizzazione_in_corso = True
        try:

            scheda_b = self._trova_scheda(studente_b)
            if not scheda_b:
                print(f"⚠️ Sincronizzazione: scheda '{studente_b}' non trovata")
            else:

                if azione == "aggiungi":
                    scheda_b.aggiungi_vincolo_programmatico(
                        tipo,
                        studente_a,
                        livello
                    )
                elif azione == "modifica":
                    scheda_b.modifica_vincolo_programmatico(
                        tipo,
                        studente_a,
                        livello
                    )
                elif azione == "rimuovi":
                    scheda_b.rimuovi_vincolo_programmatico(
                        tipo,
                        studente_a
                    )
        finally:

            self._sincronizzazione_in_corso = False


        self._segna_modificato()

    def _trova_scheda(self, nome_completo):
        """Trova la scheda associata a un nome completo."""
        for scheda in self._schede_studenti:
            if scheda.nome_completo == nome_completo:
                return scheda
        return None

    def _controlla_anomalie_editor(self):
        """Completa i vincoli sicuri e segnala anomalie da correggere nell'Editor."""
        dati_correnti = self.get_dati_tutti_studenti()
        coerenza = analizza_coerenza_bidirezionale_dati(
            dati_correnti,
            completa_mancanti=True,
        )

        vincoli_aggiunti = coerenza["vincoli_aggiunti"]
        contraddizioni = coerenza["contraddizioni"]
        discordanze_livello = coerenza["discordanze_livello"]
        studenti_fissi = nomi_studenti_fissi(dati_correnti)

        for vincolo in vincoli_aggiunti:
            scheda_target = self._trova_scheda(vincolo["target"])
            if scheda_target is not None:
                scheda_target.aggiungi_vincolo_programmatico(
                    vincolo["tipo"],
                    vincolo["sorgente"],
                    vincolo["livello"],
                )

        if contraddizioni or discordanze_livello or len(studenti_fissi) > 1:
            sezioni = []
            if len(studenti_fissi) > 1:
                righe = [
                    f"Trovati {quantita(len(studenti_fissi), 'studente', 'studenti')} "
                    "con posizione FISSO.",
                    "",
                    "Al massimo uno studente può avere posizione FISSO. "
                    "Modifica le posizioni nelle schede prima di salvare e usare la classe.",
                    "",
                ]
                righe.extend(f"• {nome}" for nome in studenti_fissi)
                sezioni.append("\n".join(righe))

            if contraddizioni:
                verbo = "Trovata" if len(contraddizioni) == 1 else "Trovate"
                righe = [
                    f"{verbo} {quantita(len(contraddizioni), 'contraddizione', 'contraddizioni')}.",
                    "",
                    "Le coppie seguenti hanno vincoli opposti. Decidi nell'Editor "
                    "quale relazione mantenere e rimuovi manualmente quella errata.",
                    "",
                ]
                righe.extend(contraddizioni[:10])
                if len(contraddizioni) > 10:
                    residue = len(contraddizioni) - 10
                    righe.append(
                        "... e "
                        + (
                            "un’altra contraddizione"
                            if residue == 1
                            else f"altre {residue} contraddizioni"
                        )
                    )
                sezioni.append("\n".join(righe))

            if discordanze_livello:
                verbo = "Trovata" if len(discordanze_livello) == 1 else "Trovate"
                righe = [
                    f"{verbo} {quantita(len(discordanze_livello), 'coppia', 'coppie')} "
                    "con livelli diversi.",
                    "",
                    "Allinea manualmente i livelli nelle due schede interessate.",
                    "",
                ]
                righe.extend(discordanze_livello[:10])
                if len(discordanze_livello) > 10:
                    residue = len(discordanze_livello) - 10
                    righe.append(
                        "... e "
                        + (
                            "un’altra coppia"
                            if residue == 1
                            else f"altre {residue} coppie"
                        )
                    )
                sezioni.append("\n".join(righe))

            if (
                hasattr(self, "_dialog_anomalie")
                and self._dialog_anomalie is not None
                and self._dialog_anomalie.isVisible()
            ):
                self._dialog_anomalie.raise_()
                self._dialog_anomalie.activateWindow()
                return

            self._dialog_anomalie = QDialog(self)
            dialog = self._dialog_anomalie
            dialog.setWindowTitle("Anomalie nel file classe")
            applica_icona_applicazione_finestra(dialog)
            adatta_finestra_allo_schermo(
                dialog,
                larghezza_ideale=650,
                altezza_ideale=450,
                larghezza_minima=520,
                altezza_minima=320,
            )

            layout_d = QVBoxLayout(dialog)
            header_anomalie = QHBoxLayout()
            icona_anomalie = QLabel()
            applica_icona_etichetta(icona_anomalie, "triangle-alert", 36)
            header_anomalie.addWidget(icona_anomalie, 0, Qt.AlignTop)

            testo_header = QLabel(
                "Sono state rilevate anomalie che richiedono una correzione manuale."
            )
            testo_header.setWordWrap(True)
            testo_header.setStyleSheet("font-size: 14px; font-weight: bold;")
            header_anomalie.addWidget(testo_header, 1)
            layout_d.addLayout(header_anomalie)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Segoe UI", 11))
            text_edit.setPlainText(("\n\n" + "─" * 50 + "\n\n").join(sezioni))
            layout_d.addWidget(text_edit)

            btn_chiudi = QPushButton("Chiudi avviso")
            applica_icona(btn_chiudi, "circle-check", 18)
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
            dialog.show()

        if vincoli_aggiunti:
            self._correzioni_applicate = True
            self._modifiche_non_salvate = True
            righe = []
            for vincolo in vincoli_aggiunti[:15]:
                etichetta = (
                    "Incompatibilità"
                    if vincolo["tipo"] == "incompatibilita"
                    else "Affinità"
                )
                righe.append(
                    f"{etichetta}: {vincolo['target']} ← {vincolo['sorgente']} "
                    f"(livello {vincolo['livello']})"
                )
            if len(vincoli_aggiunti) > 15:
                residui = len(vincoli_aggiunti) - 15
                righe.append(
                    "... e "
                    + (
                        "un altro vincolo"
                        if residui == 1
                        else f"altri {residui} vincoli"
                    )
                )

            numero_vincoli = len(vincoli_aggiunti)
            messaggio = (
                "È stato completato un vincolo speculare mancante."
                if numero_vincoli == 1
                else "Sono stati completati alcuni vincoli speculari mancanti."
            )
            verbo_aggiunto = (
                "È stato aggiunto"
                if numero_vincoli == 1
                else "Sono stati aggiunti"
            )
            _popup_info(
                self,
                "Coerenza bidirezionale",
                messaggio,
                dettagli=(
                    f"{verbo_aggiunto} "
                    f"{quantita(numero_vincoli, 'vincolo mancante', 'vincoli mancanti')} "
                    "per garantire la bidirezionalità:\n\n"
                    + "\n".join(righe)
                ),
            )



    def _chiudi_editor(self):
        """Chiude la classe corrente dopo le guardie sui dati pendenti."""


        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se chiudi adesso, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return


        if self._callback_pre_chiusura_file is not None:
            if not self._callback_pre_chiusura_file():
                return

        if self._modifiche_non_salvate:

            azione = self._conferma_chiusura()
            if azione == "salva":

                self._esporta_file()

                if self._modifiche_non_salvate:
                    return
                self._resetta_editor()
            elif azione == "esci":

                self._resetta_editor()
            else:

                return
        else:

            self._resetta_editor()

    def _conferma_chiusura(self):
        """Chiede se salvare, scartare o annullare le modifiche."""


        nome_file = self._nome_file_caricato or "sconosciuto"
        dialog = crea_popup_semantico(
            self,
            "Modifiche non salvate",
            f"Il file «{nome_file}.txt» contiene modifiche non salvate.",
            "triangle-alert",
            testo_informativo=(
                "Se esci ora, le modifiche a vincoli, genere e posizione "
                "andranno perse.\n\nChe cosa vuoi fare?"
            ),
            messaggio_in_grassetto=True,
        )


        btn_salva = dialog.addButton(
            "Salva ed esci", QMessageBox.AcceptRole
        )
        applica_icona(btn_salva, "save", 18)

        btn_esci = dialog.addButton(
            "Esci senza salvare", QMessageBox.DestructiveRole
        )
        applica_icona(btn_esci, "trash-2", 18)
        applica_stile_pulsante_popup(btn_esci, "distruttivo")

        btn_annulla = dialog.addButton(
            "Annulla", QMessageBox.RejectRole
        )
        applica_icona(btn_annulla, "x", 18)

        dialog.setDefaultButton(btn_annulla)

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
        """Ripristina l’Editor allo stato iniziale."""

        for scheda in self._schede_studenti:
            scheda.setParent(None)
            scheda.deleteLater()
        self._schede_studenti.clear()
        self._lista_nomi.clear()
        self._nome_file_caricato = ""
        self._percorso_file_caricato = ""
        self._modifiche_non_salvate = False
        self._correzioni_applicate = False


        while self.layout_schede.count() > 0:
            item = self.layout_schede.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()


        self._popola_placeholder_file_non_selezionato()


        self.btn_preview.setEnabled(False)
        self.btn_esporta.setEnabled(False)
        self._schede_tutte_espanse = False
        self.btn_toggle_schede.setText("Espandi schede")
        applica_icona(self.btn_toggle_schede, "unfold-vertical", 16)
        self.btn_toggle_schede.setToolTip(
            "Espandi tutte le schede per vedere i dettagli"
        )
        self.btn_toggle_schede.setEnabled(False)
        self.btn_chiudi.setEnabled(False)


        self._dati_riga_info = None


        self.label_contatore_vincoli.setText("")
        self.label_contatore_vincoli.setVisible(False)
        self.btn_toggle_schede.setVisible(False)
        self._btn_dettaglio_vincoli.setVisible(False)


        self._banner_formato_base.setVisible(False)


        self.file_chiuso_signal.emit()

    def richiedi_conferma_chiusura(self):
        """Verifica se l’applicazione può chiudersi senza perdere dati."""


        if self._schede_studenti:
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                _popup_avviso(
                    self,
                    "Vincoli incompleti",
                    "Sono presenti vincoli senza livello impostato.",
                    dettagli=(
                        f"{elenco}\n\n"
                        "Se chiudi adesso, questi vincoli andranno persi.\n\n"
                        "Per ogni vincolo puoi selezionare il livello e poi salvare, "
                        "oppure rimuoverlo con il pulsante «Rimuovi»."
                    ),
                )
                return False

        if not self._modifiche_non_salvate:
            return True

        azione = self._conferma_chiusura()
        if azione == "salva":
            self._esporta_file()

            return not self._modifiche_non_salvate
        elif azione == "esci":
            return True
        else:
            return False


    def tutti_generi_impostati(self):
        """Indica se tutte le schede hanno un genere valido."""
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                return False
        return True

    def get_nomi_studenti_senza_genere(self):
        """Restituisce gli studenti che conservano il placeholder del genere."""
        return [
            scheda.nome_completo
            for scheda in self._schede_studenti
            if not scheda.genere_impostato()
        ]

    def _componi_riga_info_html(self):
        """Compone la riga con nome, composizione e formato del file corrente."""
        if not self._dati_riga_info:
            return ""

        nome = self._dati_riga_info["nome"]
        num = self._dati_riga_info["num"]
        formato = self._dati_riga_info["formato"]
        colore = C("testo_affinita")

        maschi = sum(
            scheda.combo_genere.currentText() == "M"
            for scheda in self._schede_studenti
        )
        femmine = sum(
            scheda.combo_genere.currentText() == "F"
            for scheda in self._schede_studenti
        )

        parola_maschi = "maschio" if maschi == 1 else "maschi"
        parola_femmine = "femmina" if femmine == 1 else "femmine"
        nome_html = escape(f"{nome}.txt")

        return (
            f'<span style="color:{colore};">'
            f"Il file '<b>{nome_html}</b>' è stato selezionato — "
            f"{quantita(num, 'studente presente', 'studenti presenti')} "
            f"[{maschi} {parola_maschi}, {femmine} {parola_femmine}] "
            f"({formato})"
            f"</span>"
        )

    def _aggiorna_contatore_vincoli(self, profilo=None):
        """Aggiorna il riepilogo dei vincoli della classe."""

        if not self._schede_studenti:
            self.label_contatore_vincoli.setVisible(False)
            self.btn_toggle_schede.setVisible(False)
            self._btn_dettaglio_vincoli.setVisible(False)
            return

        dati = _misura_profilo(
            profilo,
            "contatore_estrai_dati",
            self.get_dati_tutti_studenti,
        )
        conteggi = _misura_profilo(
            profilo,
            "contatore_conta_vincoli",
            lambda: conta_vincoli(dati),
        )
        testo_html = _misura_profilo(
            profilo,
            "contatore_formatta_vincoli",
            lambda: formato_vincoli(
                conteggi,
                colore_etichetta=C("testo_info"),
                colore_critico=C("testo_arancione"),
                colore_normale=C("testo_secondario"),
            ),
        )
        riga_info = _misura_profilo(
            profilo,
            "contatore_riga_info",
            self._componi_riga_info_html,
        )
        separatore_info = "<br>" if riga_info else ""
        _misura_profilo(
            profilo,
            "contatore_set_text",
            lambda: self.label_contatore_vincoli.setText(
                riga_info + separatore_info + testo_html
            ),
        )
        _misura_profilo(
            profilo,
            "contatore_set_stylesheet",
            lambda: self.label_contatore_vincoli.setStyleSheet(f"""
                background-color: {C('vincoli_riepilogo_bg')};
                border: 1px solid {C('vincoli_riepilogo_bordo')};
                border-radius: 5px;
                padding: 6px 8px;
                font-size: 14px;
            """),
        )
        _misura_profilo(
            profilo,
            "contatore_visibilita",
            lambda: (
                self.label_contatore_vincoli.setVisible(True),
                self.btn_toggle_schede.setVisible(True),
                self._btn_dettaglio_vincoli.setVisible(True),
            ),
        )

    def _mostra_dettaglio_vincoli(self):
        """Mostra l’elenco completo dei vincoli in una finestra scorrevole."""


        if not self._schede_studenti:
            return


        dati = self.get_dati_tutti_studenti()
        dettaglio = dettaglio_vincoli(dati)
        testo_html = formato_dettaglio_vincoli(
            dettaglio,
            colore_titolo=C("testo_info"),
            colore_critico=C("testo_arancione"),
            colore_normale=C("testo_secondario"),
        )


        dialog = QDialog(self)
        nome_classe = self._nome_file_caricato or "classe"
        dialog.setWindowTitle(f"Dettaglio vincoli — {nome_classe}")
        applica_icona_finestra(dialog, "list-tree")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=520,
            altezza_ideale=600,
            larghezza_minima=420,
            altezza_minima=360,
        )

        layout_d = QVBoxLayout(dialog)


        area = QTextEdit()
        area.setReadOnly(True)
        area.setHtml(testo_html)


        area.setStyleSheet(f"""
            QTextEdit {{
                background-color: {C('dettaglio_vincoli_bg')};
                border: 1px solid {C('bordo_normale')};
                border-radius: 4px;
                font-size: 14px;
                padding: 6px;
            }}
        """)
        layout_d.addWidget(area)


        riga_pulsanti = QHBoxLayout()
        riga_pulsanti.addStretch()
        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.clicked.connect(dialog.accept)
        riga_pulsanti.addWidget(btn_chiudi)
        layout_d.addLayout(riga_pulsanti)


        dialog.exec()

    def get_dati_tutti_studenti(self):
        """Restituisce i dati correnti di tutte le schede."""
        return [scheda.get_dati() for scheda in self._schede_studenti]

    def ha_studenti_caricati(self):
        """Indica se l’Editor contiene almeno una scheda."""
        return len(self._schede_studenti) > 0


    def genera_contenuto_file(self):
        """Valida e genera il contenuto canonico completo della classe."""
        return serializza_file_classe(
            self._nome_file_caricato,
            self.get_dati_tutti_studenti(),
        )

    def _genera_contenuto_o_segnala_errori(self):
        """Restituisce il testo serializzato oppure mostra gli errori canonici."""
        try:
            return self.genera_contenuto_file()
        except ErroreValidazioneFileClasse as errore:
            testo = "\n".join(f"• {voce}" for voce in errore.errori[:20])
            if len(errore.errori) > 20:
                testo += f"\n\n... e altri {len(errore.errori) - 20} errori."
            _popup_errore(
                self,
                "Dati della classe non validi",
                "Il file non può essere generato finché restano dati incoerenti.",
                dettagli=testo,
            )
            return None



    def _mostra_preview(self):
        """Mostra l’anteprima del file dopo la validazione del genere."""

        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            _popup_avviso(
                self,
                "Genere non impostato",
                (
                    "Uno studente non ha ancora il genere selezionato."
                    if len(studenti_senza_genere) == 1
                    else "Alcuni studenti non hanno ancora il genere selezionato."
                ),
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di procedere."
                ),
            )
            return

        contenuto = self._genera_contenuto_o_segnala_errori()
        if contenuto is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Anteprima file classe (.txt)")
        applica_icona_finestra(dialog, "eye")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1300,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )

        layout = QVBoxLayout(dialog)


        text_edit = QTextEdit()
        text_edit.setReadOnly(True)


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


        num_righe_dati = len(self._schede_studenti)
        label_info = QLabel(
            f"{quantita(num_righe_dati, 'studente', 'studenti')} — "
            "Ogni riga ha 6 campi separati da «;»"
        )
        label_info.setStyleSheet(f"color: {C('testo_info_grigio')}; font-size: 11px;")
        layout.addWidget(label_info)


        bottoni = QDialogButtonBox(QDialogButtonBox.Close)
        btn_close_preview = bottoni.button(QDialogButtonBox.Close)
        if btn_close_preview is not None:
            btn_close_preview.setText("Chiudi")
            applica_icona(btn_close_preview, "x", 18)
        bottoni.rejected.connect(dialog.close)
        layout.addWidget(bottoni)

        dialog.exec()


    def _esporta_file(self):
        """Valida e salva il file corrente.

        Aggiorna atomicamente il file già selezionato e, dopo il successo,
        notifica la finestra principale.
        """

        studenti_senza_genere = []
        for scheda in self._schede_studenti:
            if not scheda.genere_impostato():
                studenti_senza_genere.append(scheda.nome_completo)

        if studenti_senza_genere:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_senza_genere)
            _popup_avviso(
                self,
                "Genere non impostato",
                (
                    "Uno studente non ha ancora il genere selezionato."
                    if len(studenti_senza_genere) == 1
                    else "Alcuni studenti non hanno ancora il genere selezionato."
                ),
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di salvare."
                ),
            )
            return


        studenti_fisso = []
        for scheda in self._schede_studenti:
            dati = scheda.get_dati()
            if dati["posizione"] == "FISSO":
                studenti_fisso.append(scheda.nome_completo)

        if len(studenti_fisso) > 1:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
            _popup_avviso(
                self,
                "Troppi studenti con posizione FISSO",
                "Al massimo uno studente può avere posizione FISSO.",
                dettagli=(
                    f"Attualmente sono "
                    f"{quantita(len(studenti_fisso), 'studente', 'studenti')}:\n\n"
                    f"{elenco}\n\n"
                    "Modifica la posizione degli studenti in eccesso prima di salvare."
                ),
            )
            return


        vincoli_incompleti = self.get_vincoli_incompleti()
        if vincoli_incompleti:
            elenco = "\n".join(vincoli_incompleti)
            _popup_avviso(
                self,
                "Vincoli incompleti",
                "Sono presenti vincoli senza livello impostato.",
                dettagli=(
                    f"{elenco}\n\n"
                    "Per ogni vincolo, seleziona il livello di intensità oppure "
                    "rimuovilo con il pulsante «Rimuovi»."
                ),
            )
            return


        self._controlla_anomalie_editor()

        dati_correnti = [
            scheda.get_dati()
            for scheda in self._schede_studenti
        ]
        coerenza = analizza_coerenza_bidirezionale_dati(
            dati_correnti,
            completa_mancanti=False,
        )

        anomalie = (
            coerenza["contraddizioni"]
            + coerenza["discordanze_livello"]
        )
        if anomalie:
            testo = "\n".join(
                f"• {voce}" for voce in anomalie[:15]
            )
            if len(anomalie) > 15:
                residue = len(anomalie) - 15
                testo += (
                    "\n\n... e "
                    + (
                        "un’altra anomalia."
                        if residue == 1
                        else f"altre {residue} anomalie."
                    )
                )

            _popup_errore(
                self,
                "Vincoli incoerenti",
                "Il salvataggio è bloccato da contraddizioni o livelli diversi nelle due direzioni.",
                dettagli=(
                    f"{testo}\n\n"
                    "Correggi i vincoli nelle schede e riprova."
                ),
            )
            return

        contenuto = self._genera_contenuto_o_segnala_errori()
        if contenuto is None:
            return

        percorso = self._percorso_file_caricato
        if not percorso:
            _popup_errore(
                self,
                "File sorgente non disponibile",
                "Non è presente un file di classe da aggiornare.",
                dettagli="Chiudi l'Editor e seleziona nuovamente il file della classe.",
            )
            return

        try:
            scrivi_file_classe_atomico(percorso, contenuto)


            self._modifiche_non_salvate = False

            self._percorso_file_caricato = percorso


            self._banner_formato_base.setVisible(False)


            self._dati_riga_info = {
                "nome": self._nome_file_caricato,
                "num": len(self._schede_studenti),
                "formato": "formato COMPLETO",
            }
            self._aggiorna_contatore_vincoli()


            nome_file = os.path.basename(percorso)
            _popup_successo(
                self,
                "File aggiornato",
                f"Il file «{nome_file}» è stato aggiornato,\n"
                f"caricato ed è pronto per l'assegnazione.",
                dettagli=(
                    f"Percorso:\n{percorso}\n\n"
                    f"Studenti: {len(self._schede_studenti)}"
                ),
            )


            self.file_salvato_signal.emit(percorso)

        except Exception as e:
            _popup_errore(
                self,
                "Salvataggio non riuscito",
                "Impossibile salvare il file.",
                dettagli=str(e),
            )

    def _get_cartella_classi(self):
        """Restituisce la cartella locale dei file-classe."""
        return inizializza_cartella_classi()

    def _apri_cartella_classi(self):
        """Apre la cartella delle classi con il gestore di file del sistema."""

        cartella_classi = self._get_cartella_classi()

        if apri_file_con_applicazione_default(cartella_classi):
            return

        _popup_avviso(
            self,
            "Apertura della cartella non riuscita",
            "Impossibile aprire automaticamente la cartella delle classi.",
            dettagli=f"Aprila manualmente dal percorso:\n{cartella_classi}",
        )
