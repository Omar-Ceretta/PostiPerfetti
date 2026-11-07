# -*- coding: utf-8 -*-
"""Controlli delle relazioni: selettori protetti, placeholder e righe dei vincoli.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton,
    QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer

from moduli.interfaccia.tema import C




from moduli.interfaccia.utilita import (
    applica_icona,
)

from moduli.interfaccia.dialoghi_editor import _popup_info

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


            QTimer.singleShot(0, self, self._mostra_promemoria_livello)


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


