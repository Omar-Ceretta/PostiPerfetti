# -*- coding: utf-8 -*-
"""Scheda di uno studente: dati visuali e segnali di modifica, senza accesso ai file.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFrame
)
from PySide6.QtCore import Signal

from moduli.interfaccia.tema import C
from moduli.interfaccia.dialoghi_editor import _popup_info


from moduli.persistenza.file_classe import (
    PLACEHOLDER_GENERE,
)


from moduli.interfaccia.utilita import (
    applica_icona,
)

from moduli.interfaccia.controlli_editor import (
    ComboBoxProtetto, RigaVincolo, _imposta_proprieta_stile,
)

class SchedaStudente(QGroupBox):
    """Scheda collassabile con dati e vincoli di uno studente.

    Comunica all’Editor le modifiche da rendere bidirezionali. La posizione FISSO
    disabilita i vincoli della scheda, che devono essere impostati sugli altri.
    """


    vincolo_modificato_signal = Signal(str, str, str, int, str)
    elimina_studente_signal = Signal(str)

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

        self._btn_elimina_studente = QPushButton("Elimina studente")
        applica_icona(self._btn_elimina_studente, "trash-2", 16)
        self._btn_elimina_studente.setToolTip(
            "Rimuove questo studente dalla classe e pulisce automaticamente "
            "i vincoli che lo riguardano."
        )
        self._btn_elimina_studente.clicked.connect(
            lambda: self.elimina_studente_signal.emit(self.nome_completo)
        )
        riga_base.addWidget(self._btn_elimina_studente)
        self._aggiorna_stile_btn_elimina_studente()

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
        self._aggiorna_stile_btn_elimina_studente()

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


    def _aggiorna_stile_btn_elimina_studente(self):
        if not hasattr(self, "_btn_elimina_studente"):
            return
        self._btn_elimina_studente.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_rosso_bg")};
                color: white;
                font-size: 12px;
                border-radius: 4px;
                font-weight: bold;
                padding: 5px 10px;
            }}
            QPushButton:hover {{ background-color: {C("btn_rosso_hover")}; }}
        """)

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


