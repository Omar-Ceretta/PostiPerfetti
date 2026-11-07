# -*- coding: utf-8 -*-
"""Editor Qt del Layout a posizioni permanenti 6 × 5.

Compone griglia, comandi, contatori e validazione live. Lo stato autorevole resta ``ModelloAulaPersonalizzata``;
nessun algoritmo di assegnazione viene eseguito qui.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from moduli.dominio.aula_personalizzata import ModelloAulaPersonalizzata
from moduli.interfaccia.canvas_layout_aula import CanvasLayoutAula as CanvasAulaPersonalizzata
from moduli.dominio.schema_blocchi_semantico import SchemaBlocchiSemantico
from moduli.dominio.layout_unico import ErroreLayoutUnico, congela_layout_unico
from moduli.interfaccia.tema import C
from moduli.interfaccia.utilita import (
    applica_icona,
    carica_icona,
    applica_stile_pulsante_popup,
    crea_popup_semantico,
)


class EditorAulaPersonalizzata(QWidget):
    """Editor a selezione: geometria stabile, zone esplicite e posto FISSO."""

    schemaCambiato = Signal(object)
    validitaCambiata = Signal(bool, str)
    bozzaModificata = Signal()

    def __init__(
        self,
        *,
        numero_studenti: int | None = None,
        ha_fisso: bool = False,
        nome_fisso: str | None = None,
        modello: ModelloAulaPersonalizzata | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.numero_studenti = numero_studenti
        self.ha_fisso = bool(ha_fisso)
        self.nome_fisso = (nome_fisso or "").strip()
        self.modello = modello or ModelloAulaPersonalizzata()
        self._schema_valido: SchemaBlocchiSemantico | None = None
        self._sospendi_segnale_bozza = False
        self._feedback = ""
        self._stato_valido = False
        self._testo_stato = ""

        self._costruisci_ui()
        self._collega_segnali()
        self.aggiorna_tema()
        self._aggiorna_tutto()

    @property
    def schema_valido(self) -> SchemaBlocchiSemantico | None:
        return self._schema_valido

    def schema_corrente(self) -> SchemaBlocchiSemantico:
        """Restituisce lo schema pronto per il motore oppure solleva ValueError."""
        layout = congela_layout_unico(
            self.modello,
            numero_studenti=self.numero_studenti,
            numero_fissi=int(self.ha_fisso),
            griglia=self.canvas.GRIGLIA,
        )
        return layout.schema

    def carica_schema(self, schema: SchemaBlocchiSemantico) -> None:
        self.modello = ModelloAulaPersonalizzata.da_schema(schema)
        self.canvas.imposta_modello(self.modello)
        self._aggiorna_tutto()

    def modello_persistibile(self) -> ModelloAulaPersonalizzata:
        """Restituisce la bozza effettivamente destinata al JSON laterale."""
        return self.canvas.modello_persistibile()

    def carica_bozza_persistita(self, modello: ModelloAulaPersonalizzata) -> None:
        """Ripristina una bozza su disco senza risalvarla durante il caricamento."""
        if not isinstance(modello, ModelloAulaPersonalizzata):
            raise TypeError("modello deve essere un ModelloAulaPersonalizzata.")
        self._sospendi_segnale_bozza = True
        try:
            self.modello = modello
            self.canvas.imposta_ha_fisso(self.ha_fisso)
            self.canvas.imposta_modello(self.modello)
            self.btn_modalita_fisso.setChecked(False)
            self._aggiorna_tutto()
        finally:
            self._sospendi_segnale_bozza = False

    def imposta_classe(
        self,
        *,
        numero_studenti: int | None,
        ha_fisso: bool,
        nome_fisso: str | None = None,
    ) -> None:
        self._feedback = ""
        self.numero_studenti = numero_studenti
        self.ha_fisso = bool(ha_fisso)
        self.nome_fisso = (nome_fisso or "").strip()
        self.canvas.imposta_ha_fisso(self.ha_fisso)
        self.btn_modalita_fisso.setChecked(False)
        self._aggiorna_tutto()

    def resetta_classe(
        self,
        *,
        numero_studenti: int | None,
        ha_fisso: bool,
        nome_fisso: str | None = None,
    ) -> None:
        """Azzera l'aula bozza e la riallinea a una nuova classe."""
        self._feedback = ""
        self.numero_studenti = numero_studenti
        self.ha_fisso = bool(ha_fisso)
        self.nome_fisso = (nome_fisso or "").strip()
        self.modello = ModelloAulaPersonalizzata()
        self._sospendi_segnale_bozza = True
        try:
            self.canvas.imposta_ha_fisso(self.ha_fisso)
            self.canvas.imposta_modello(self.modello)
        finally:
            self._sospendi_segnale_bozza = False
        self.btn_modalita_fisso.setChecked(False)
        self._aggiorna_tutto()

    def _costruisci_ui(self) -> None:
        principale = QVBoxLayout(self)
        principale.setContentsMargins(8, 8, 8, 8)
        principale.setSpacing(6)

        self.menu_aggiungi = QMenu(self)
        self.menu_occupato = QMenu(self)
        self.menu_spazio = QMenu(self)
        self.menu_blocco = self.menu_aggiungi
        self.azione_banco2 = QAction("Blocco da 2", self)
        self.azione_banco3 = QAction("Blocco da 3", self)
        self.azione_spazio = QAction("Spazio", self)
        self.azione_davanti = QAction("Davanti", self)
        self.azione_neutro = QAction("Neutro", self)
        self.azione_fondo = QAction("In fondo", self)
        for azione in (self.azione_davanti, self.azione_neutro, self.azione_fondo):
            azione.setCheckable(True)
        self.azione_sposta = QAction("Sposta", self)
        self.azione_elimina = QAction("Elimina", self)
        for menu, azioni in (
            (self.menu_aggiungi, (self.azione_banco2, self.azione_banco3, self.azione_spazio)),
            (self.menu_occupato, (self.azione_fondo, self.azione_neutro, self.azione_davanti,
                                  self.azione_sposta, self.azione_elimina)),
            (self.menu_spazio, (self.azione_elimina,)),
        ):
            for indice, azione in enumerate(azioni):
                menu.addAction(azione)
                if (menu is self.menu_aggiungi and indice == 1
                        or menu is self.menu_occupato and indice == 2):
                    menu.addSeparator()

        barra = QHBoxLayout()
        barra.setSpacing(6)
        self.btn_annulla = QPushButton("Annulla")
        barra.addWidget(self.btn_annulla)

        self.btn_modalita_fisso = QPushButton("Assegna posto FISSO")
        self.btn_modalita_fisso.setCheckable(True)
        self.btn_modalita_fisso.setToolTip(
            "Attiva la scelta e fai clic sul singolo posto dello studente FISSO. "
            "Dopo l'assegnazione il cursore torna automaticamente normale."
        )
        self.btn_rimuovi_fisso = QPushButton("Libera posto FISSO")
        self.btn_rimuovi_fisso.setToolTip(
            "Rimuove il posto riservato al FISSO dal Layout, senza eliminare il banco.\n"
            "Il vincolo FISSO dello studente rimane: scegli poi un nuovo posto."
        )
        barra.addWidget(self.btn_modalita_fisso)
        barra.addWidget(self.btn_rimuovi_fisso)

        barra.addStretch(1)
        self.btn_reset = QPushButton("Reset aula")
        self.btn_reset.setToolTip("Rimuove tutti i banchi, gli Spazi e l'eventuale posto FISSO.")
        barra.addWidget(self.btn_reset)
        principale.addLayout(barra)

        self.canvas = CanvasAulaPersonalizzata(self.modello, ha_fisso=self.ha_fisso)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.canvas)
        self.scroll.setMinimumHeight(200)
        principale.addWidget(self.scroll, 1)
        contatori = QHBoxLayout()
        self.label_studenti = QLabel()
        self.label_posti = QLabel()
        self.label_blocchi = QLabel()
        self.label_zone = QLabel()
        self.label_ancora = QLabel()
        for label in (
            self.label_studenti,
            self.label_posti,
            self.label_blocchi,
            self.label_zone,
            self.label_ancora,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumWidth(90)
            label.setMinimumHeight(58)
            contatori.addWidget(label)
        principale.addLayout(contatori)

        self.label_stato = QLabel()
        self.label_stato.setWordWrap(True)
        self.label_stato.setMinimumHeight(42)
        principale.addWidget(self.label_stato)


    def _collega_segnali(self) -> None:
        self.azione_spazio.triggered.connect(self.canvas.aggiungi_spazio)
        self.azione_sposta.triggered.connect(self.canvas.avvia_spostamento)
        self.btn_annulla.clicked.connect(self.canvas.annulla_operazione)
        self.azione_banco2.triggered.connect(lambda: self._aggiungi_da_menu(2))
        self.azione_banco3.triggered.connect(lambda: self._aggiungi_da_menu(3))
        self.azione_davanti.triggered.connect(
            lambda: self.canvas.applica_zona_ai_selezionati("prima")
        )
        self.azione_neutro.triggered.connect(
            lambda: self.canvas.applica_zona_ai_selezionati("neutra")
        )
        self.azione_fondo.triggered.connect(
            lambda: self.canvas.applica_zona_ai_selezionati("ultima")
        )
        self.btn_modalita_fisso.toggled.connect(self.canvas.imposta_modalita_fisso)
        self.canvas.modalitaFissoTerminata.connect(
            lambda: self.btn_modalita_fisso.setChecked(False)
        )
        self.btn_rimuovi_fisso.clicked.connect(self.canvas.rimuovi_ancora_fisso)
        self.azione_elimina.triggered.connect(self.canvas.elimina_selezionati)
        self.btn_reset.clicked.connect(self._reset_aula_con_conferma)

        self.canvas.modelloModificato.connect(self._on_modello_modificato)
        self.canvas.selezioneCambiata.connect(self._aggiorna_azioni_selezione)
        self.canvas.messaggio.connect(self._mostra_messaggio_transitorio)
        self.canvas.menuRichiesto.connect(self._apri_menu_posizione)

    def _apri_menu_posizione(self, riga: int, colonna: int) -> None:
        self._feedback = ""
        self._aggiorna_azioni_selezione()
        self.menu_blocco.close()
        if self.canvas.blocco_selezionato():
            self.menu_blocco = self.menu_occupato
        elif self.canvas.spazio_selezionato():
            self.menu_blocco = self.menu_spazio
        else:
            self.menu_blocco = self.menu_aggiungi
        corpo = self.canvas.vista.spazi[riga, colonna][2]
        centro = corpo.mapToGlobal(corpo.rect().center())
        dimensioni = self.menu_blocco.sizeHint()
        punto = centro - QPoint(dimensioni.width() // 2, dimensioni.height() // 2)
        self.menu_blocco.popup(punto)

    def _aggiungi_da_menu(self, capienza: int) -> None:
        self.canvas.aggiungi_primo_spazio(capienza)

    def _reset_aula_con_conferma(self) -> None:
        """Azzera l'aula soltanto dopo una conferma esplicita."""
        if not self.modello.blocchi and not self.modello.spazi:
            return

        conferma = crea_popup_semantico(
            self,
            "Resettare l'aula?",
            "L'intera configurazione dell'aula verrà eliminata.",
            "triangle-alert",
            testo_informativo=(
                "Verranno rimossi tutti i banchi, gli Spazi, le marcature DAVANTI / "
                "IN FONDO e l'eventuale puntina FISSO.\n\n"
                "Questa operazione non può essere annullata."
            ),
            messaggio_in_grassetto=True,
        )

        btn_annulla = conferma.addButton("Annulla", QMessageBox.RejectRole)
        btn_reset = conferma.addButton("Reset aula", QMessageBox.DestructiveRole)
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_reset, "trash-2", 18)
        applica_stile_pulsante_popup(btn_reset, "distruttivo")
        conferma.setDefaultButton(btn_annulla)
        conferma.setEscapeButton(btn_annulla)
        conferma.exec()

        if conferma.clickedButton() == btn_reset:
            self.canvas.svuota()

    def _on_modello_modificato(self) -> None:
        self._feedback = ""
        self.menu_blocco.close()
        self._aggiorna_tutto()
        if not self._sospendi_segnale_bozza:
            self.bozzaModificata.emit()

    def _aggiorna_azioni_selezione(self) -> None:
        blocco = self.canvas.blocco_selezionato()
        operazione = self.canvas.sta_spostando or self.canvas._modalita_fisso
        vuoto = self.canvas.posizione_selezionata is not None and blocco is None and not self.canvas.spazio_selezionato()
        self.azione_spazio.setEnabled(vuoto and not operazione)
        self.azione_banco2.setEnabled(vuoto and not operazione)
        self.azione_banco3.setEnabled(vuoto and not operazione)
        self.azione_sposta.setEnabled(blocco is not None and not operazione)
        self.btn_annulla.setVisible(operazione)
        for bottone, zona in ((self.azione_davanti, "prima"),
                               (self.azione_neutro, "neutra"),
                               (self.azione_fondo, "ultima")):
            bottone.setEnabled(blocco is not None and not operazione)
            bottone.setChecked(blocco is not None and blocco.zona == zona)
        self.azione_elimina.setEnabled((blocco is not None or self.canvas.spazio_selezionato()) and not operazione)
        self.btn_modalita_fisso.setEnabled(
            self.ha_fisso and bool(self.modello.blocchi) and not self.canvas.sta_spostando)
        self.btn_rimuovi_fisso.setEnabled(self.modello.ancora_fisso is not None and not operazione)
        self.btn_reset.setEnabled(bool(self.modello.blocchi or self.modello.spazi) and not operazione)
        self._imposta_stato(self._stato_valido, self._testo_stato)

    def _riepilogo_fisso(self) -> str:
        """Testo sintetico per il pannello: non ripete ID e posto del Layout."""
        if not self.ha_fisso or self.modello.ancora_fisso is None:
            return ""
        return f"FISSO: {self.nome_fisso or 'studente FISSO'}."

    def _componi_stato_incompleto(
        self,
        contatori: dict,
        errore: Exception | None = None,
    ) -> str:
        """Compone uno stato persistente con tutte le azioni ancora necessarie."""
        cause = []
        note = []
        if self.numero_studenti is None:
            cause.append("Puoi già preparare il Layout. Carica la classe con SALVA e CARICA per verificarne capienza e FISSO.")

        differenza = contatori.get("differenza")
        if differenza is not None and differenza < 0:
            mancanti = abs(int(differenza))
            cause.append(
                f"Mancano {mancanti} "
                f"{'posto' if mancanti == 1 else 'posti'} rispetto agli studenti."
            )
        elif differenza is not None and differenza > 0:
            eccedenti = int(differenza)
            cause.append(
                f"Ci {'è' if eccedenti == 1 else 'sono'} {eccedenti} "
                f"{'posto' if eccedenti == 1 else 'posti'} in eccesso."
            )

        if self.ha_fisso:
            nome = self.nome_fisso or "studente FISSO"
            ancora = self.modello.ancora_fisso
            if ancora is None:
                cause.append(f"Assegna il posto dello studente FISSO {nome}.")
            else:
                note.append(self._riepilogo_fisso())

        if isinstance(errore, ErroreLayoutUnico):
            # I contatori e il nome del FISSO sono già spiegati sopra; le cause
            # geometriche vanno mostrate anche quando mancano altri posti.
            cause.extend(p.messaggio for p in errore.esito.problemi
                         if p.codice not in {"capienza_classe", "ancora_mancante", "studenti_non_specificati"})
        elif not cause and errore is not None:
            cause.append(str(errore))

        return " ".join(cause + note)

    def _aggiorna_tutto(self) -> None:
        contatori = self.modello.contatori(numero_studenti=self.numero_studenti)
        studenti = contatori["studenti"]
        self.label_studenti.setText(
            "Studenti\n—" if studenti is None else f"Studenti\n{studenti}"
        )
        differenza = contatori["differenza"]
        if differenza is None:
            testo_posti = f"Posti\n{contatori['posti']}"
        elif differenza == 0:
            testo_posti = f"Posti\n{contatori['posti']} ✓"
        elif differenza > 0:
            testo_posti = f"Posti\n{contatori['posti']} (+{differenza})"
        else:
            testo_posti = f"Posti\n{contatori['posti']} ({differenza})"
        self.label_posti.setText(testo_posti)
        self.label_blocchi.setText(
            f"Banchi\n2p: {contatori['coppie']} · 3p: {contatori['terzetti']}"
        )
        self.label_zone.setText(
            f"Zone\nDavanti: {contatori['posti_prima']} · Fondo: {contatori['posti_ultima']}"
        )
        self.label_ancora.setText(
            "FISSO\nnon presente" if not self.ha_fisso
            else "FISSO\nassegnato ✓" if contatori["fisso_assegnato"]
            else "FISSO\nnon assegnato"
        )

        self.btn_modalita_fisso.setEnabled(self.ha_fisso)
        self.btn_rimuovi_fisso.setEnabled(
            self.modello.ancora_fisso is not None
        )
        if not self.ha_fisso:
            self.btn_modalita_fisso.setChecked(False)

        try:
            schema = self.schema_corrente()
        except (TypeError, ValueError) as exc:
            self._schema_valido = None
            messaggio = self._componi_stato_incompleto(
                contatori, exc,
            )
            self._imposta_stato(False, messaggio)
            self.validitaCambiata.emit(False, messaggio)
        else:
            self._schema_valido = schema
            messaggio = "Aula pronta. I vincoli degli studenti saranno verificati durante il calcolo."
            if self.ha_fisso and self.modello.ancora_fisso:
                messaggio += " " + self._riepilogo_fisso()
            self._imposta_stato(True, messaggio)
            self.validitaCambiata.emit(True, messaggio.removeprefix("Aula pronta. "))
            self.schemaCambiato.emit(schema)

        self.canvas.update()
        self._aggiorna_azioni_selezione()

    def _imposta_stato(self, valido: bool, testo: str) -> None:
        self._stato_valido = valido
        self._testo_stato = testo
        if valido:
            sfondo = C("label_successo_bg")
            bordo = C("label_successo_bordo")
            colore = C("label_successo_txt")
        else:
            sfondo = C("label_attenzione_bg")
            bordo = C("label_attenzione_bordo")
            colore = C("label_attenzione_txt")
        self.label_stato.setStyleSheet(
            "QLabel {"
            f"background-color: {sfondo}; color: {colore}; "
            f"border: 1px solid {bordo}; border-radius: 6px; "
            "padding: 8px 10px; font-weight: bold;"
            "}"
        )
        if not self.modello.blocchi:
            testo += " Clicca su Aggiungi per inserire un blocco o uno Spazio."
        if self.canvas.sta_spostando:
            testo += " Clicca su Aggiungi nella posizione di destinazione; Esc o Annulla per interrompere."
        elif self.canvas._modalita_fisso:
            testo += f" Clicca sul singolo posto per {self.nome_fisso or 'lo studente FISSO'}."
        if self._feedback:
            testo += " " + self._feedback
        self.label_stato.setText(testo)

    def _mostra_messaggio_transitorio(self, testo: str) -> None:
        # Stato e istruzione convivono: nessun messaggio operativo nasconde errori.
        self._feedback = "" if testo.startswith(("Sposta ", "Clicca sul singolo posto", "Posto FISSO assegnato")) else testo
        self._imposta_stato(self._stato_valido, self._testo_stato)

    def aggiorna_tema(self) -> None:
        """Ridisegna gli elementi inline dopo un cambio tema dell'applicazione."""

        def stile_bottone(
            sfondo: str,
            hover: str,
            testo: str,
            bordo: str,
            *,
            checked: str | None = None,
        ) -> str:
            css = (
                "QPushButton {"
                f"background-color: {sfondo}; color: {testo}; "
                f"border: 1px solid {bordo}; border-radius: 6px; "
                "padding: 5px 6px; font-weight: bold;"
                "}"
                "QPushButton:hover {"
                f"background-color: {hover}; border-color: {bordo};"
                "}"
            )
            if checked is not None:
                css += (
                    "QPushButton:checked {"
                    f"background-color: {checked}; border-color: {bordo};"
                    "}"
                )
            css += (
                "QPushButton:disabled {"
                f"background-color: {C('btn_azione_disabled_bg')}; "
                f"color: {C('btn_azione_disabled_txt')}; "
                f"border-color: {C('btn_azione_disabled_bordo')};"
                "}"
            )
            return css

        for menu in (self.menu_aggiungi, self.menu_occupato, self.menu_spazio):
            menu.setMinimumWidth(230)
            menu.setToolTipsVisible(True)
            menu.setStyleSheet(
                f"QMenu {{background-color: {C('layout_menu_bg')}; color: {C('testo_principale')}; "
                f"border: 1px solid {C('layout_menu_bordo')}; border-radius: 9px; "
                "padding: 6px; font-size: 14px;}"
                "QMenu::item {padding: 8px 16px 8px 12px; margin: 2px; "
                "border: 1px solid transparent; border-radius: 5px;}"
                f"QMenu::item:selected {{background-color: {C('layout_menu_hover_bg')}; "
                f"border-color: {C('layout_menu_bordo')}; color: {C('testo_principale')};}}"
                f"QMenu::item:disabled {{color: {C('btn_azione_disabled_txt')};}}"
                f"QMenu::separator {{height: 1px; background: {C('layout_card_bordo')}; margin: 5px 10px;}}"
            )

        for azione, icona in (
            (self.azione_banco2, "layout-pair"),
            (self.azione_banco3, "layout-trio"),
            (self.azione_spazio, "layout-space"),
            (self.azione_davanti, "layout-back"),
            (self.azione_neutro, "layout-neutral"),
            (self.azione_fondo, "layout-front"),
            (self.azione_sposta, "layout-move"),
            (self.azione_elimina, "layout-delete"),
        ):
            azione.setIcon(carica_icona(icona))
        for bottone, icona in (
            (self.btn_modalita_fisso, "layout-fixed"),
            (self.btn_rimuovi_fisso, "layout-unfixed"),
            (self.btn_annulla, "x"),
            (self.btn_reset, "repeat-2"),
        ):
            applica_icona(bottone, icona, 18)

        for label in (self.label_studenti, self.label_posti, self.label_blocchi,
                      self.label_zone, self.label_ancora):
            label.setStyleSheet(
                f"QLabel {{background-color: {C('layout_card_bg')}; color: {C('testo_principale')}; "
                f"border: 1px solid {C('layout_card_bordo')}; border-radius: 8px; "
                "padding: 7px 10px; font-size: 13px;}"
            )

        # FISSO: indaco durante la scelta del posto; rimozione neutra.
        self.btn_modalita_fisso.setStyleSheet(stile_bottone(
            C("btn_indaco_bg"), C("btn_indaco_hover"),
            C("btn_indaco_txt"), C("btn_indaco_bordo"),
            checked=C("btn_indaco_hover"),
        ))
        self.btn_rimuovi_fisso.setStyleSheet(stile_bottone(
            C("editor_btn_neutro_bg"), C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"), C("editor_btn_neutro_bordo"),
        ))

        for bottone in (self.btn_annulla,):
            bottone.setStyleSheet(stile_bottone(
                C("editor_btn_neutro_bg"), C("editor_btn_neutro_hover"),
                C("editor_btn_neutro_txt"), C("editor_btn_neutro_bordo"),
                checked=C("editor_btn_neutro_hover"),
            ))

        # Azioni distruttive: rosso esplicito e coerente in entrambi i temi.
        stile_distruttivo = stile_bottone(
            C("btn_rosso_bg"), C("btn_rosso_hover"),
            "#ffffff", C("btn_rosso_bg"),
        )
        self.btn_reset.setStyleSheet(stile_distruttivo)

        riferimento = self.btn_modalita_fisso.sizeHint()
        for bottone in (self.btn_annulla, self.btn_reset):
            bottone.setFixedSize(riferimento)

        self.canvas.aggiorna_tema()
        self._aggiorna_tutto()
