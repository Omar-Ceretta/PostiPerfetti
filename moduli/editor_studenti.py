# -*- coding: utf-8 -*-
"""Editor grafico delle classi di «PostiPerfetti».

Carica file base o completi, valida anagrafica e vincoli, mantiene la
bidirezionalità delle relazioni e salva il formato testuale del progetto.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGroupBox, QScrollArea, QTextEdit,
    QMessageBox, QDialog, QDialogButtonBox, QFrame, QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap
import os
import sys
import platform
import subprocess

from moduli.tema import C


from moduli.studenti import chiave_identita_studente


from moduli.utilita import (
    conta_vincoli, formato_vincoli,
    dettaglio_vincoli, formato_dettaglio_vincoli,
    ordina_studenti,
    adatta_finestra_allo_schermo,
    get_base_path,
    applica_icona, applica_stile_pulsante_popup, applica_icona_finestra,
    applica_icona_applicazione_finestra,
    applica_icona_etichetta, crea_popup_semantico, mostra_popup_semantico,
)


# I placeholder rendono incompleto il dato finché l’utente non sceglie
# esplicitamente il valore; le guardie di salvataggio li riconoscono.
PLACEHOLDER_VINCOLO = "Seleziona studente..."


PLACEHOLDER_LIVELLO = "Seleziona intensità del vincolo..."


PLACEHOLDER_GENERE = "---"


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


class ErroreValidazioneFileClasse(ValueError):
    """Raccoglie gli errori che impediscono di caricare un file completo."""

    def __init__(self, errori):
        self.errori = list(errori)
        super().__init__("\n".join(self.errori))


def _normalizza_spazi(valore):
    """Uniforma gli spazi esterni e interni di un valore."""
    return " ".join(str(valore).strip().split())


def _chiave_nome_completo(nome_completo):
    """Restituisce la chiave normalizzata di un nome completo."""
    return _normalizza_spazi(nome_completo).casefold()


def _analizza_coerenza_bidirezionale_dati(studenti_dati, completa_mancanti=False):
    """Rileva contraddizioni, livelli discordanti e vincoli non speculari.

    Con ``completa_mancanti=True`` aggiunge soltanto le copie speculari
    inequivocabili; non corregge contraddizioni o livelli discordanti.
    """
    per_nome = {
        f"{dati['cognome']} {dati['nome']}": dati
        for dati in studenti_dati
    }

    contraddizioni = []
    discordanze_livello = []
    vincoli_aggiunti = []
    coppie_contraddittorie_viste = set()
    coppie_discordi_viste = set()

    for nome_sorgente, dati_sorgente in per_nome.items():
        for tipo, tipo_opposto, etichetta in (
            ("incompatibilita", "affinita", "INCOMPATIBILITÀ"),
            ("affinita", "incompatibilita", "AFFINITÀ"),
        ):
            for nome_target, livello in list(dati_sorgente[tipo].items()):
                dati_target = per_nome[nome_target]
                coppia = tuple(sorted((nome_sorgente, nome_target)))

                if nome_sorgente in dati_target[tipo_opposto]:
                    if coppia not in coppie_contraddittorie_viste:
                        coppie_contraddittorie_viste.add(coppia)
                        livello_opposto = dati_target[tipo_opposto][nome_sorgente]
                        contraddizioni.append(
                            f"{nome_sorgente} → {nome_target}: {etichetta} "
                            f"livello {livello}; direzione opposta: "
                            f"{'AFFINITÀ' if tipo_opposto == 'affinita' else 'INCOMPATIBILITÀ'} "
                            f"livello {livello_opposto}."
                        )
                    continue

                if nome_sorgente in dati_target[tipo]:
                    livello_speculare = dati_target[tipo][nome_sorgente]
                    chiave_discordanza = (coppia, tipo)
                    if (
                        livello != livello_speculare
                        and chiave_discordanza not in coppie_discordi_viste
                    ):
                        coppie_discordi_viste.add(chiave_discordanza)
                        discordanze_livello.append(
                            f"{etichetta}: {nome_sorgente} → {nome_target} "
                            f"livello {livello}; {nome_target} → {nome_sorgente} "
                            f"livello {livello_speculare}."
                        )
                    continue

                if completa_mancanti:
                    dati_target[tipo][nome_sorgente] = livello
                    vincoli_aggiunti.append({
                        "tipo": tipo,
                        "sorgente": nome_sorgente,
                        "target": nome_target,
                        "livello": livello,
                    })

    return {
        "contraddizioni": contraddizioni,
        "discordanze_livello": discordanze_livello,
        "vincoli_aggiunti": vincoli_aggiunti,
    }


def prepara_file_completo(righe):
    """Valida le sei colonne di un file completo e prepara i dati per l’Editor.

    Normalizza solo i casi inequivocabili, rifiuta i dati ambigui e completa i
    vincoli speculari sicuri. Solleva ``ErroreValidazioneFileClasse`` se trova
    almeno un errore strutturale o semantico.
    """
    errori = []
    avvisi = []
    righe_preparate = []


    for numero_riga, riga in enumerate(righe, start=1):
        parti = riga.split(';')

        if len(parti) != 6:
            errori.append(
                f"Riga {numero_riga}: trovati {len(parti)} campi; "
                "un file completo deve averne esattamente 6."
            )
            continue

        cognome = _normalizza_spazi(parti[0])
        nome = _normalizza_spazi(parti[1])

        if not cognome or not nome:
            errori.append(
                f"Riga {numero_riga}: cognome e nome devono essere entrambi presenti."
            )
            continue

        righe_preparate.append({
            "numero_riga": numero_riga,
            "parti": parti,
            "cognome": cognome,
            "nome": nome,
            "nome_completo": f"{cognome} {nome}",
        })

    if errori:
        raise ErroreValidazioneFileClasse(errori)

    nomi_canonici = {}
    for riga in righe_preparate:
        chiave = _chiave_nome_completo(riga["nome_completo"])
        if chiave in nomi_canonici:
            errori.append(
                f"Riga {riga['numero_riga']}: lo studente "
                f"'{riga['nome_completo']}' duplica "
                f"'{nomi_canonici[chiave]}'."
            )
        else:
            nomi_canonici[chiave] = riga["nome_completo"]

    if errori:
        raise ErroreValidazioneFileClasse(errori)

    def parsing_vincoli_rigoroso(
        testo,
        tipo,
        nome_sorgente,
        numero_riga,
    ):
        risultato = {}
        testo = testo.strip()
        if not testo:
            return risultato

        for indice, elemento in enumerate(testo.split(','), start=1):
            elemento = elemento.strip()
            descrizione = f"riga {numero_riga}, {tipo}, elemento {indice}"

            if not elemento:
                errori.append(
                    f"{descrizione}: vincolo vuoto; controlla virgole doppie o finali."
                )
                continue

            if elemento.count(':') != 1:
                errori.append(
                    f"{descrizione}: '{elemento}' deve avere la sintassi "
                    "'Cognome Nome:livello'."
                )
                continue

            riferimento_raw, livello_raw = elemento.rsplit(':', 1)
            riferimento_raw = _normalizza_spazi(riferimento_raw)
            livello_raw = livello_raw.strip()

            if not riferimento_raw or not livello_raw:
                errori.append(
                    f"{descrizione}: riferimento o livello mancante in '{elemento}'."
                )
                continue

            try:
                livello = int(livello_raw)
            except ValueError:
                errori.append(
                    f"{descrizione}: il livello '{livello_raw}' non è numerico."
                )
                continue

            if livello not in (1, 2, 3):
                errori.append(
                    f"{descrizione}: il livello {livello} è fuori dall'intervallo 1-3."
                )
                continue

            chiave_riferimento = _chiave_nome_completo(riferimento_raw)
            nome_target = nomi_canonici.get(chiave_riferimento)

            if nome_target is None:
                errori.append(
                    f"{descrizione}: lo studente '{riferimento_raw}' non esiste nel file."
                )
                continue

            if nome_target == nome_sorgente:
                errori.append(
                    f"{descrizione}: uno studente non può avere un vincolo verso se stesso."
                )
                continue

            if nome_target in risultato:
                errori.append(
                    f"{descrizione}: '{nome_target}' è duplicato nello stesso campo."
                )
                continue

            risultato[nome_target] = livello

        return risultato

    studenti_dati = []


    for riga in righe_preparate:
        parti = riga["parti"]
        numero_riga = riga["numero_riga"]
        nome_completo = riga["nome_completo"]

        sesso_raw = parti[2].strip().upper()
        if not sesso_raw:
            sesso = PLACEHOLDER_GENERE
            avvisi.append(
                f"Riga {numero_riga} — {nome_completo}: genere mancante; "
                "nell'Editor resta il placeholder '---'."
            )
        elif sesso_raw in ("M", "F"):
            sesso = sesso_raw
        else:
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: genere "
                f"'{parti[2].strip()}' non valido; usare M, F oppure lasciare vuoto."
            )
            sesso = PLACEHOLDER_GENERE

        posizione = parti[3].strip().upper()
        if posizione not in ("NORMALE", "PRIMA", "ULTIMA", "FISSO"):
            valore = parti[3].strip() or "<vuoto>"
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: posizione '{valore}' "
                "non valida; usare NORMALE, PRIMA, ULTIMA o FISSO."
            )

        incompatibilita = parsing_vincoli_rigoroso(
            parti[4], "incompatibilità", nome_completo, numero_riga
        )
        affinita = parsing_vincoli_rigoroso(
            parti[5], "affinità", nome_completo, numero_riga
        )

        presenti_in_entrambi = sorted(
            set(incompatibilita).intersection(affinita)
        )
        for nome_target in presenti_in_entrambi:
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: '{nome_target}' compare "
                "sia tra le incompatibilità sia tra le affinità."
            )

        studenti_dati.append({
            "cognome": riga["cognome"],
            "nome": riga["nome"],
            "sesso": sesso,
            "posizione": posizione,
            "incompatibilita": incompatibilita,
            "affinita": affinita,
        })

    if errori:
        raise ErroreValidazioneFileClasse(errori)

    coerenza = _analizza_coerenza_bidirezionale_dati(
        studenti_dati,
        completa_mancanti=True,
    )

    return {
        "studenti": studenti_dati,
        "avvisi": avvisi,
        "contraddizioni": coerenza["contraddizioni"],
        "discordanze_livello": coerenza["discordanze_livello"],
        "vincoli_aggiunti": coerenza["vincoli_aggiunti"],
    }


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
        """Aggiorna lo stile del menu del compagno."""
        self.combo_studente.setStyleSheet(
            self._stylesheet_combo_vincolo(self.is_placeholder_attivo())
        )

    def _aggiorna_stile_combo_livello(self):
        """Aggiorna lo stile del menu del livello."""
        self.combo_livello.setStyleSheet(
            self._stylesheet_combo_vincolo(
                self.is_placeholder_livello_attivo()
            )
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
        """Riapplica i colori del tema attivo."""


        self._aggiorna_stile_combobox()
        self._aggiorna_stile_combo_livello()


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


            self.combo_genere.setStyleSheet(f"""
                QComboBox {{
                    border: 2px solid {C("genere_ph_bordo")};
                    background-color: {C("genere_ph_sf")};
                }}
            """)
        else:

            self.combo_genere.addItems(["M", "F"])
            self.combo_genere.setCurrentText(sesso)

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
        self.combo_posizione.setFixedWidth(250)
        riga_base.addWidget(self.combo_posizione)

        riga_base.addStretch()
        self._layout_interno.addLayout(riga_base)


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
        self._label_info_fisso.setVisible(False)
        self._layout_interno.addWidget(self._label_info_fisso)


        self._sep1 = QFrame()
        self._sep1.setFrameShape(QFrame.HLine)
        self._sep1.setStyleSheet(f"background-color: {C('editor_sep')};")
        self._layout_interno.addWidget(self._sep1)


        self._label_incomp = QLabel("INCOMPATIBILITÀ:")
        self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_incomp')}; font-size: 13px;")
        self._layout_interno.addWidget(self._label_incomp)


        self._container_incomp = QVBoxLayout()
        self._container_incomp.setSpacing(4)
        self._layout_interno.addLayout(self._container_incomp)


        for nome_target, livello in incompatibilita.items():
            self._aggiungi_riga_vincolo("incompatibilita", nome_target, livello, notifica=False)


        self._btn_aggiungi_incomp = QPushButton("Aggiungi incompatibilità")
        applica_icona(self._btn_aggiungi_incomp, "plus", 16)
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


        self._sep2 = QFrame()
        self._sep2.setFrameShape(QFrame.HLine)
        self._sep2.setStyleSheet(f"background-color: {C('editor_sep')};")
        self._layout_interno.addWidget(self._sep2)


        self._label_aff = QLabel("AFFINITÀ:")
        self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_affinita')}; font-size: 13px;")
        self._layout_interno.addWidget(self._label_aff)


        self._container_aff = QVBoxLayout()
        self._container_aff.setSpacing(4)
        self._layout_interno.addLayout(self._container_aff)


        for nome_target, livello in affinita.items():
            self._aggiungi_riga_vincolo("affinita", nome_target, livello, notifica=False)


        self._btn_aggiungi_aff = QPushButton("Aggiungi affinità")
        applica_icona(self._btn_aggiungi_aff, "plus", 16)
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

            self.combo_genere.setStyleSheet("")


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


        if abilitato:
            self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_incomp')}; font-size: 13px;")
            self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_affinita')}; font-size: 13px;")
        else:
            self._label_incomp.setStyleSheet(f"font-weight: bold; color: {C('testo_placeholder')}; font-size: 13px;")
            self._label_aff.setStyleSheet(f"font-weight: bold; color: {C('testo_placeholder')}; font-size: 13px;")


        for riga in self._righe_incompatibilita:
            riga.setEnabled(abilitato)
        for riga in self._righe_affinita:
            riga.setEnabled(abilitato)


        self._label_info_fisso.setVisible(not abilitato)

    def genere_impostato(self):
        """Indica se il genere è stato scelto."""
        return self.combo_genere.currentText() in ("M", "F")

    def _aggiorna_stile_genere(self, sesso):
        """Aggiorna colori e titolo in base al genere corrente."""

        etichetta_posizione = self.combo_posizione.currentText()
        posizione_interna = self._mappa_posizioni.get(etichetta_posizione, "NORMALE")
        is_fisso = (posizione_interna == "FISSO")

        if sesso not in ("M", "F"):


            colore_bordo     = C("scheda_X_bordo")
            colore_titolo_bg = C("scheda_X_titolo_sf")
            colore_titolo_txt = C("scheda_X_titolo_txt")
            colore_sfondo    = C("scheda_X_sf")
        elif is_fisso:


            colore_bordo      = C("errore_bordo")
            colore_titolo_bg  = C("errore_titolo_sf")
            colore_titolo_txt = C("errore_titolo_txt")
            if sesso == "M":
                colore_sfondo = C("scheda_M_sf")
            else:
                colore_sfondo = C("scheda_F_sf")
        elif sesso == "M":

            colore_bordo     = C("scheda_M_bordo")
            colore_titolo_bg = C("scheda_M_titolo_sf")
            colore_titolo_txt = C("scheda_M_titolo_txt")
            colore_sfondo    = C("scheda_M_sf")
        else:

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


    def aggiorna_tema(self):
        """Riapplica il tema alla scheda e alle sue righe."""

        sesso_attuale = self.combo_genere.currentText()
        self._aggiorna_stile_genere(sesso_attuale)


        stile_sep = f"background-color: {C('editor_sep')};"
        if hasattr(self, '_sep1'):
            self._sep1.setStyleSheet(stile_sep)
        if hasattr(self, '_sep2'):
            self._sep2.setStyleSheet(stile_sep)


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


        for riga in self._righe_incompatibilita + self._righe_affinita:
            riga.aggiorna_tema()

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


        self.dati_modificati_signal.connect(self._aggiorna_contatore_vincoli)

    def aggiorna_tema(self):
        """Riapplica il tema all’intero Editor."""

        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("editor_scroll_sf")};
            }}
        """)


        self.label_apri_info.setStyleSheet(
            f"color: {C('testo_secondario')}; font-size: 14px; font-style: italic;"
        )


        self._aggiorna_stili_bottoni_editor()


        for scheda in self._schede_studenti:
            scheda.aggiorna_tema()


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


        if self._schede_studenti:
            self._aggiorna_contatore_vincoli()

    def _aggiorna_stili_bottoni_editor(self):
        """Aggiorna gli stili dei comandi dell’Editor."""

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

        self.btn_apri_cartella.setStyleSheet(stile(
            C("editor_btn_cartella_bg"),
            C("editor_btn_cartella_hover"),
            C("editor_btn_cartella_txt"),
            C("editor_btn_cartella_bordo"),
        ))
        self.btn_carica.setStyleSheet(stile(
            C("editor_btn_classe_bg"),
            C("editor_btn_classe_hover"),
            C("editor_btn_classe_txt"),
            C("editor_btn_classe_bordo"),
        ))
        self.btn_esporta.setStyleSheet(stile(
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
        self.btn_toggle_schede.setStyleSheet(stile_neutro)
        self._btn_dettaglio_vincoli.setStyleSheet(stile_neutro)

        self.btn_preview.setStyleSheet(stile(
            C("btn_indaco_bg"), C("btn_indaco_hover"),
            C("btn_indaco_txt"), C("btn_indaco_bordo"),
            padding="10px 20px",
        ))
        self.btn_chiudi.setStyleSheet(stile(
            C("editor_btn_neutro_bg"),
            C("editor_btn_neutro_hover"),
            C("editor_btn_neutro_txt"),
            C("editor_btn_neutro_bordo"),
            padding="10px 20px",
        ))

    def _popola_placeholder_file_non_selezionato(self):
        """Mostra lo stato iniziale senza una classe caricata."""
        self._logo_placeholder = QLabel()
        percorso_logo = os.path.join(
            get_base_path(),
            "dati",
            "icone",
            "postiperfetti_logo.png"
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
            "Apre la cartella 'dati' nel file manager del sistema.\n"
            "Qui puoi creare un nuovo file .txt con la lista degli studenti."
        )
        self.btn_apri_cartella.clicked.connect(self._apri_cartella_dati)
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
            "Seleziona un file .txt dalla cartella dati\n"
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
            "FORMATO BASE — PRIMA DI SALVARE, imposta per ogni studente: "
            "posizione, incompatibilità e affinità. "
            "Poi clicca 'SALVA e CARICA'."
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
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("editor_scroll_sf")};
            }}
        """)


        self.widget_scroll = QWidget()
        self.layout_schede = QVBoxLayout(self.widget_scroll)
        self.layout_schede.setSpacing(12)
        self.layout_schede.setContentsMargins(10, 10, 10, 10)


        self._popola_placeholder_file_non_selezionato()
        self.scroll_area.setWidget(self.widget_scroll)


        layout_principale.addWidget(self.scroll_area, 1)


        footer = QHBoxLayout()
        footer.setSpacing(12)


        self.btn_preview = QPushButton("Preview file classe (.txt)")
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
        """Seleziona, riconosce e valida un file di classe.

        Prima di sostituire la classe corrente applica le guardie sulle modifiche non
        salvate e sull’eventuale assegnazione ancora pendente.
        """


        if self._schede_studenti:
            # Un placeholder pendente non sempre imposta il flag delle modifiche.
            vincoli_incompleti = self.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                risposta = _popup_avviso(
                               self,
                               "Vincoli incompleti",
                               "Alcuni vincoli non hanno il livello impostato.",
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


        cartella_dati = self._get_cartella_dati()

        percorso, _ = QFileDialog.getOpenFileName(
            self,
            "SELEZIONA CLASSE (.txt)",
            cartella_dati,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if not percorso:
            return


        try:
            with open(percorso, 'r', encoding='utf-8-sig') as f:
                righe = f.readlines()
        except UnicodeDecodeError:
            try:
                with open(percorso, 'r', encoding='latin-1') as f:
                    righe = f.readlines()
            except Exception as e:
                _popup_errore(
                    self,
                    "Lettura del file non riuscita",
                    "Impossibile leggere il file selezionato.",
                    dettagli=str(e),
                )
                return
        except Exception as e:
            _popup_errore(
                self,
                "Lettura del file non riuscita",
                "Impossibile leggere il file selezionato.",
                dettagli=str(e),
            )
            return


        righe_utili = []
        for riga in righe:
            riga_strip = riga.strip()
            if riga_strip and not riga_strip.startswith('#'):
                righe_utili.append(riga_strip)

        if not righe_utili:
            _popup_avviso(
                self,
                "File vuoto",
                "Il file non contiene righe utili.",
            )
            return


        conteggi_identita = {}
        nomi_visualizzati = {}

        for riga in righe_utili:
            parti = riga.split(';')


            if len(parti) < 2:
                continue

            cognome = parti[0].strip()
            nome = parti[1].strip()

            if not cognome or not nome:
                continue

            chiave = chiave_identita_studente(
                cognome,
                nome
            )


            nome_visuale = (
                f"{' '.join(cognome.split())} "
                f"{' '.join(nome.split())}"
            )

            nomi_visualizzati.setdefault(
                chiave,
                nome_visuale
            )
            conteggi_identita[chiave] = (
                conteggi_identita.get(chiave, 0) + 1
            )

        duplicati = [
            (
                nomi_visualizzati[chiave],
                occorrenze
            )
            for chiave, occorrenze
            in conteggi_identita.items()
            if occorrenze > 1
        ]

        if duplicati:
            elenco = "\n".join(
                f"  • {nome} — presente {occorrenze} volte"
                for nome, occorrenze in sorted(duplicati)
            )

            _popup_errore(
                self,
                "Studenti non distinguibili",
                "Il file contiene studenti con lo stesso identico cognome e nome.",
                dettagli=(
                    f"{elenco}\n\n"
                    "PostiPerfetti usa «Cognome Nome» per distinguere gli studenti "
                    "nei vincoli e nelle assegnazioni.\n\n"
                    "Modifica il file .txt aggiungendo, per esempio, un secondo nome "
                    "o una sigla distintiva:\n"
                    "  • Rossi Mario A.\n"
                    "  • Rossi Mario B."
                ),
            )
            return


        nome_file_candidato = os.path.splitext(
            os.path.basename(percorso)
        )[0]
        percorso_file_candidato = percorso


        numeri_campi = [len(riga.split(';')) for riga in righe_utili]
        risultato_completo = None

        if any(numero >= 4 for numero in numeri_campi):
            try:
                risultato_completo = self._carica_formato_completo(
                    righe_utili
                )
            except ErroreValidazioneFileClasse as errore:
                errori = errore.errori
                testo = "\n".join(f"• {voce}" for voce in errori[:20])
                if len(errori) > 20:
                    testo += (
                        f"\n\n... e altri {len(errori) - 20} errori."
                    )

                _popup_errore(
                    self,
                    "File completo non valido",
                    "Il nuovo file non è stato caricato.",
                    dettagli=(
                        f"{testo}\n\n"
                        "Correggi il file .txt e selezionalo di nuovo."
                    ),
                )
                return

            formato_rilevato = "COMPLETO"

        elif all(numero in (2, 3) for numero in numeri_campi):
            formato_rilevato = "BASE"

        else:
            _popup_errore(
                self,
                "Formato non valido",
                "Il nuovo file non è stato caricato; la classe precedente è rimasta intatta.",
                dettagli=(
                    "Un file BASE deve avere 2 o 3 campi per riga; "
                    "un file COMPLETO deve averne esattamente 6."
                ),
            )
            return


        self._nome_file_caricato = nome_file_candidato
        self._percorso_file_caricato = percorso_file_candidato

        if formato_rilevato == "COMPLETO":
            self._correzioni_applicate = bool(
                risultato_completo["avvisi"]
                or risultato_completo["vincoli_aggiunti"]
            )
            self._popola_editor(
                risultato_completo["studenti"],
                "COMPLETO"
            )

            segnalazioni = list(risultato_completo["avvisi"])
            for vincolo in risultato_completo["vincoli_aggiunti"]:
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
                testo = "\n".join(
                    f"• {voce}" for voce in segnalazioni[:20]
                )
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
            self._carica_formato_base(righe_utili)


        self.file_cambiato_signal.emit()

    def _carica_formato_base(self, righe):
        """Converte le righe base nei dati iniziali dell’Editor."""
        studenti_dati = []

        for riga in righe:
            parti = riga.split(';')
            if len(parti) >= 2:
                cognome = parti[0].strip()
                nome = parti[1].strip()


                sesso = PLACEHOLDER_GENERE
                if len(parti) >= 3 and parti[2].strip().upper() in ("M", "F"):
                    sesso = parti[2].strip().upper()

                studenti_dati.append({
                    "cognome": cognome,
                    "nome": nome,
                    "sesso": sesso,
                    "posizione": "NORMALE",
                    "incompatibilita": {},
                    "affinita": {}
                })

        self._popola_editor(studenti_dati, "BASE")

    def _carica_formato_completo(self, righe):
        """Valida e converte un file completo senza correzioni ambigue."""
        return prepara_file_completo(righe)

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
                    self.genere_cambiato_signal.emit()
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
                "cognome, nome e genere degli studenti.",
                dettagli=(
                    "Prima di usare «SALVA e CARICA», è consigliato impostare "
                    "per ciascuno studente:\n\n"
                    "  • posizione (PRIMA, NORMALE, ULTIMA o FISSO)\n"
                    "  • incompatibilità\n"
                    "  • affinità\n\n"
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
            self._check_coerenza_bidirezionale()


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
        """Verifica l’unicità della posizione FISSO.

        Se un secondo studente viene impostato come FISSO, la modifica viene annullata.
        """
        self._segna_modificato()


        dati = scheda_modificata.get_dati()
        if dati["posizione"] != "FISSO":
            return


        studenti_fisso = []
        for scheda in self._schede_studenti:
            dati_scheda = scheda.get_dati()
            if dati_scheda["posizione"] == "FISSO":
                studenti_fisso.append(scheda.nome_completo)

        if len(studenti_fisso) > 1:
            elenco = "\n".join(f"  • {nome}" for nome in studenti_fisso)
            _popup_avviso(
                self,
                "Troppi studenti con posizione FISSO",
                "Al massimo uno studente può avere posizione FISSO.",
                dettagli=(
                    f"Attualmente sono {len(studenti_fisso)}:\n\n"
                    f"{elenco}\n\n"
                    "Modifica la posizione degli studenti in eccesso prima di procedere."
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

    def _check_coerenza_bidirezionale(self):
        """Controlla contraddizioni e livelli discordanti fra le due direzioni.

        Completa soltanto i vincoli speculari inequivocabili e mostra le anomalie che
        richiedono una decisione dell’utente.
        """
        vincoli_aggiunti = []
        contraddizioni = []


        discordanze_livello = []


        _coppie_discordi_viste = set()

        for scheda in self._schede_studenti:
            dati = scheda.get_dati()


            for target, livello in dati["incompatibilita"].items():
                scheda_target = self._trova_scheda(target)
                if scheda_target:
                    dati_target = scheda_target.get_dati()
                    if scheda.nome_completo not in dati_target["incompatibilita"]:


                        if scheda.nome_completo in dati_target["affinita"]:

                            contraddizioni.append(
                                f"{scheda.nome_completo} ha INCOMPATIBILITÀ "
                                f"con {target} (lv {livello}),\n"
                                f"      ma {target} ha AFFINITÀ "
                                f"con {scheda.nome_completo} "
                                f"(lv {dati_target['affinita'][scheda.nome_completo]})"
                            )
                        else:

                            scheda_target.aggiungi_vincolo_programmatico(
                                "incompatibilita", scheda.nome_completo, livello
                            )
                            vincoli_aggiunti.append(
                                f"Incompatibilità: {target} ← {scheda.nome_completo} (livello {livello})"
                            )
                    else:


                        livello_speculare = dati_target["incompatibilita"][scheda.nome_completo]
                        if livello != livello_speculare:


                            coppia_key = tuple(sorted([scheda.nome_completo, target]))
                            if coppia_key not in _coppie_discordi_viste:
                                _coppie_discordi_viste.add(coppia_key)


                                discordanze_livello.append(
                                    f"INCOMPATIBILITÀ con livelli diversi:\n"
                                    f"      {scheda.nome_completo} → {target} (lv {livello})\n"
                                    f"      {target} → {scheda.nome_completo} (lv {livello_speculare})"
                                )


            for target, livello in dati["affinita"].items():
                scheda_target = self._trova_scheda(target)
                if scheda_target:
                    dati_target = scheda_target.get_dati()
                    if scheda.nome_completo not in dati_target["affinita"]:


                        if scheda.nome_completo in dati_target["incompatibilita"]:


                            coppia_key = tuple(sorted([scheda.nome_completo, target]))
                            duplicato = any(
                                coppia_key == tuple(sorted([scheda.nome_completo, target]))
                                for c in contraddizioni
                                if target in c and scheda.nome_completo in c
                            )
                            if not duplicato:
                                contraddizioni.append(
                                    f"{scheda.nome_completo} ha AFFINITÀ "
                                    f"con {target} (lv {livello}),\n"
                                    f"      ma {target} ha INCOMPATIBILITÀ "
                                    f"con {scheda.nome_completo} "
                                    f"(lv {dati_target['incompatibilita'][scheda.nome_completo]})"
                                )
                        else:

                            scheda_target.aggiungi_vincolo_programmatico(
                                "affinita", scheda.nome_completo, livello
                            )
                            vincoli_aggiunti.append(
                                f"Affinità: {target} ← {scheda.nome_completo} (livello {livello})"
                            )
                    else:


                        livello_speculare = dati_target["affinita"][scheda.nome_completo]
                        if livello != livello_speculare:


                            coppia_key = tuple(sorted([scheda.nome_completo, target]))
                            if coppia_key not in _coppie_discordi_viste:
                                _coppie_discordi_viste.add(coppia_key)
                                discordanze_livello.append(
                                    f"AFFINITÀ con livelli diversi:\n"
                                    f"      {scheda.nome_completo} → {target} (lv {livello})\n"
                                    f"      {target} → {scheda.nome_completo} (lv {livello_speculare})"
                                )


        if contraddizioni or discordanze_livello:


            msg_contr = ""


            if contraddizioni:
                msg_contr += (
                    f"Trovate {len(contraddizioni)} contraddizioni.\n\n"
                    "Le seguenti coppie hanno vincoli opposti: uno studente "
                    "considera incompatibile un compagno che lo considera affine.\n\n"
                    "Apri le relative schede nell'Editor e decidi quale vincolo "
                    "mantenere. Quello opposto va rimosso manualmente.\n\n\n"
                )
                for c in contraddizioni[:10]:
                    msg_contr += f"{c}\n\n"
                if len(contraddizioni) > 10:
                    msg_contr += f"... e altre {len(contraddizioni) - 10}\n\n"


            if discordanze_livello:

                if contraddizioni:
                    msg_contr += "\n" + ("─" * 50) + "\n\n"
                msg_contr += (
                    f"Trovate {len(discordanze_livello)} coppie con livelli diversi.\n\n"
                    "Nelle coppie seguenti il vincolo esiste in entrambe le "
                    "direzioni, ma con intensità diverse.\n\n"
                    "Apri le relative schede nell'Editor e allinea i due livelli.\n\n\n"
                )
                for d in discordanze_livello[:10]:
                    msg_contr += f"{d}\n\n"
                if len(discordanze_livello) > 10:
                    msg_contr += f"... e altre {len(discordanze_livello) - 10}"


            if hasattr(self, '_dialog_contraddizioni') and self._dialog_contraddizioni is not None:
                if self._dialog_contraddizioni.isVisible():
                    self._dialog_contraddizioni.raise_()
                    self._dialog_contraddizioni.activateWindow()
                    return

            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
            from PySide6.QtGui import QFont

            self._dialog_contraddizioni = QDialog(self)
            dialog = self._dialog_contraddizioni
            dialog.setWindowTitle("Anomalie nei vincoli")
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
            text_edit.setPlainText(msg_contr)
            layout_d.addWidget(text_edit)

            btn_chiudi = QPushButton("Ho capito e ho corretto nell'Editor")
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

            msg = (
                f"Sono stati aggiunti {len(vincoli_aggiunti)} vincoli mancanti "
                "per garantire la bidirezionalità:\n\n"
            )
            for v in vincoli_aggiunti[:15]:
                msg += f"  {v}\n"
            if len(vincoli_aggiunti) > 15:
                msg += f"\n  ... e altri {len(vincoli_aggiunti) - 15}"

            _popup_info(
                self,
                "Coerenza bidirezionale",
                "Sono stati completati alcuni vincoli speculari mancanti.",
                dettagli=msg,
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
                    "Alcuni vincoli non hanno il livello impostato.",
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
                    "Alcuni vincoli non hanno il livello impostato.",
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
        """Compone la riga con nome e formato del file corrente."""
        if not self._dati_riga_info:
            return ""
        nome = self._dati_riga_info["nome"]
        num = self._dati_riga_info["num"]
        formato = self._dati_riga_info["formato"]
        colore = C("testo_affinita")
        return (
            f'<span style="color:{colore};">'
            f"Il file '{nome}.txt' è stato selezionato — "
            f"{num} studenti presenti ({formato})"
            f"</span>"
        )

    def _aggiorna_contatore_vincoli(self):
        """Aggiorna il riepilogo dei vincoli della classe."""

        if not self._schede_studenti:
            self.label_contatore_vincoli.setVisible(False)
            self.btn_toggle_schede.setVisible(False)
            self._btn_dettaglio_vincoli.setVisible(False)
            return


        dati = self.get_dati_tutti_studenti()


        conteggi = conta_vincoli(dati)


        testo_html = formato_vincoli(
            conteggi,
            colore_etichetta=C("testo_info"),
            colore_critico=C("testo_arancione"),
            colore_normale=C("testo_secondario"),
        )


        riga_info = self._componi_riga_info_html()
        separatore_info = "<br>" if riga_info else ""
        self.label_contatore_vincoli.setText(riga_info + separatore_info + testo_html)


        self.label_contatore_vincoli.setStyleSheet(f"""
            background-color: {C('vincoli_riepilogo_bg')};
            border: 1px solid {C('vincoli_riepilogo_bordo')};
            border-radius: 5px;
            padding: 6px 8px;
            font-size: 14px;
        """)
        self.label_contatore_vincoli.setVisible(True)
        self.btn_toggle_schede.setVisible(True)
        self._btn_dettaglio_vincoli.setVisible(True)

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


    def _genera_txt(self):
        """Genera il contenuto completo del file di classe a sei campi."""
        linee = []


        num_studenti = len(self._schede_studenti)
        linee.append(f"# Classe: {self._nome_file_caricato} ({num_studenti} studenti)")
        linee.append("# Formato: Cognome;Nome;Genere;Posizione;Incompatibilità;Affinità")
        linee.append("# Genere: M/F (se il flag \"Genere misto\" è attivo, l'abbinamento [maschio][femmina] riceve un BONUS forte, non obbligatorio)")
        linee.append("# Vincoli di posizione: NORMALE (= neutro) / PRIMA (= OBBLIGATORIO: prima fila) / ULTIMA (= preferenza per ultima fila) / FISSO (= OBBLIGATORIO: primo banco a sinistra della prima fila)")
        linee.append("# Vincoli di \"Incompatibilità\": Cognome Nome:livello (1-3, dove 1 = Leggera, 2 = Media, 3 = ASSOLUTA [= mai insieme])")
        linee.append("# Vincoli di \"Affinità\": Cognome Nome:livello (1-3, dove 1 = Leggera, 2 = Buona, 3 = Forte)")
        linee.append("")


        for scheda in self._schede_studenti:
            dati = scheda.get_dati()


            incomp_parts = []
            for nome_completo, livello in dati["incompatibilita"].items():
                incomp_parts.append(f"{nome_completo}:{livello}")
            incomp_str = ",".join(incomp_parts)


            aff_parts = []
            for nome_completo, livello in dati["affinita"].items():
                aff_parts.append(f"{nome_completo}:{livello}")
            aff_str = ",".join(aff_parts)


            riga = (
                f"{dati['cognome']};{dati['nome']};"
                f"{dati['sesso']};{dati['posizione']};"
                f"{incomp_str};{aff_str}"
            )
            linee.append(riga)

        return "\n".join(linee)


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
                "Alcuni studenti non hanno ancora il genere selezionato.",
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di procedere."
                ),
            )
            return

        contenuto = self._genera_txt()


        dialog = QDialog(self)
        dialog.setWindowTitle("Preview file classe (.txt)")
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
        label_info = QLabel(f"{num_righe_dati} studenti — Ogni riga ha 6 campi separati da ';'")
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

        Sovrascrive il file già caricato oppure chiede una destinazione al primo
        salvataggio; dopo il successo notifica la finestra principale.
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
                "Alcuni studenti non hanno ancora il genere selezionato.",
                dettagli=(
                    f"{elenco}\n\n"
                    "Seleziona M o F per ogni studente prima di esportare."
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
                    f"Attualmente sono {len(studenti_fisso)}:\n\n"
                    f"{elenco}\n\n"
                    "Modifica la posizione degli studenti in eccesso prima di esportare."
                ),
            )
            return


        vincoli_incompleti = self.get_vincoli_incompleti()
        if vincoli_incompleti:
            elenco = "\n".join(vincoli_incompleti)
            _popup_avviso(
                self,
                "Vincoli incompleti",
                "Alcuni vincoli non hanno il livello impostato.",
                dettagli=(
                    f"{elenco}\n\n"
                    "Per ogni vincolo, seleziona il livello di intensità oppure "
                    "rimuovilo con il pulsante «Rimuovi»."
                ),
            )
            return


        self._check_coerenza_bidirezionale()

        dati_correnti = [
            scheda.get_dati()
            for scheda in self._schede_studenti
        ]
        coerenza = _analizza_coerenza_bidirezionale_dati(
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
                testo += f"\n\n... e altre {len(anomalie) - 15} anomalie."

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

        # Dopo il primo salvataggio si aggiorna direttamente lo stesso file.
        if self._percorso_file_caricato:


            percorso = self._percorso_file_caricato
        else:

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
                return

        try:
            contenuto = self._genera_txt()
            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(contenuto)


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

    def _get_cartella_dati(self):
        """Restituisce la cartella delle classi, creandola se necessario."""
        if getattr(sys, 'frozen', False):

            cartella_progetto = os.path.dirname(sys.executable)
        else:

            cartella_modulo = os.path.dirname(os.path.abspath(__file__))
            cartella_progetto = os.path.dirname(cartella_modulo)
        cartella_dati = os.path.join(cartella_progetto, "dati")


        os.makedirs(cartella_dati, exist_ok=True)

        return cartella_dati

    def _apri_cartella_dati(self):
        """Apre la cartella delle classi con il gestore di file del sistema."""

        cartella_dati = self._get_cartella_dati()

        try:
            sistema = platform.system()

            if sistema == 'Linux':


                subprocess.run(['xdg-open', cartella_dati], check=False)

            elif sistema == 'Windows':

                os.startfile(cartella_dati)

            elif sistema == 'Darwin':

                subprocess.run(['open', cartella_dati], check=False)

            else:

                _popup_info(
                    self,
                    "Cartella dati",
                    "Il sistema operativo non è stato riconosciuto.",
                    dettagli=f"Apri manualmente la cartella:\n{cartella_dati}",
                )
                return

        except Exception as e:

            _popup_avviso(
                self,
                "Apertura della cartella non riuscita",
                "Impossibile aprire automaticamente la cartella dati.",
                dettagli=(
                    f"Errore: {e}\n\n"
                    f"Aprila manualmente dal percorso:\n{cartella_dati}"
                ),
            )
