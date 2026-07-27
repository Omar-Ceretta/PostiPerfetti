# -*- coding: utf-8 -*-

"""Interfaccia principale e coordinamento dei flussi di «PostiPerfetti».

Gestisce assegnazioni mensili e annuali, modalità a coppie e terzetti,
anteprime, salvataggio e integrazione dei moduli dell’applicazione.

Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3."""

import sys

sys.dont_write_bytecode = True
import os

# Output e gestione degli errori
# In produzione stdout viene scartato; stderr resta disponibile per i traceback.
MODALITA_SILENZIOSA = True

class _PozzoNero:
    """Implementa un flusso di output che scarta ogni scrittura."""
    def write(self, testo):
        return len(testo)
    def flush(self):
        pass
    def isatty(self):
        return False

if MODALITA_SILENZIOSA or sys.stdout is None:
    sys.stdout = _PozzoNero()
if sys.stderr is None:
    sys.stderr = _PozzoNero()

def _gestisci_crash(tipo, valore, tb):

    # Il gestore è best effort: un errore nel logging non deve causare un secondo crash.
    if issubclass(tipo, KeyboardInterrupt):
        sys.__excepthook__(tipo, valore, tb)
        return

    percorso_log = None
    try:
        import traceback
        from datetime import datetime as _dt

        try:
            from moduli.utilita import get_base_path
            base = get_base_path()
        except Exception:
            base = os.path.dirname(os.path.abspath(__file__))

        cartella = os.path.join(base, "dati")
        os.makedirs(cartella, exist_ok=True)
        percorso_log = os.path.join(cartella, "crash.log")

        with open(percorso_log, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"CRASH {_dt.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("".join(traceback.format_exception(tipo, valore, tb)))
    except Exception:
        pass

    try:
        import threading
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()

        if app is not None and threading.current_thread() is threading.main_thread():
            dettaglio = (f"Il dettaglio tecnico è stato salvato in:\n{percorso_log}"
                         if percorso_log else
                         "Non è stato possibile salvare il file di dettaglio.")
            QMessageBox.critical(
                None,
                "PostiPerfetti — errore imprevisto",
                "Si è verificato un errore imprevisto.\n\n"
                f"{dettaglio}\n\n"
                "Puoi inviare quel file all'autore per aiutarlo "
                "a correggere il problema."
            )
    except Exception:
        pass

    sys.__excepthook__(tipo, valore, tb)

sys.excepthook = _gestisci_crash

# Le eccezioni dei thread Python non passano da sys.excepthook.
import threading as _threading_per_hook
_threading_per_hook.excepthook = lambda args: _gestisci_crash(
    args.exc_type, args.exc_value, args.exc_traceback)
import math
import time
import copy

from datetime import datetime
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QFileDialog, QTextEdit,
    QGroupBox, QRadioButton, QButtonGroup, QCheckBox, QSpinBox,
    QTableWidget, QTabWidget, QAbstractItemView,
    QMessageBox, QScrollArea, QLineEdit,
    QFrame, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QEventLoop
from PySide6.QtGui import QFont, QIcon, QFontDatabase

from moduli.studenti import Student
from moduli.aula import ConfigurazioneAula
from moduli.algoritmo import AssegnatorePosti
from moduli.vincoli import MotoreVincoli, MotoreVincoliConfigurato

import moduli.motore_terzetti as mt

from moduli.metrica_pulizia import (
                                    chiave_pulizia,
                                    snapshot_blacklist,
                                    snapshot_vicini_fisso,
                                    punteggio_stagione,
                                    conta_incompatibilita_per_livello,

                                    riordina_stagione_per_pulizia,

                                    snapshot_blacklist_terzetti, chiave_pulizia_terzetti,
                                    adiacenze_per_blacklist_terzetti,

                                    riordina_stagione_per_pulizia_terzetti,

                                    conta_ripetizioni_terzetti,
                                    conta_incompatibilita_per_livello_terzetti)

from moduli.strato_storico import (
    trova_quando_coppia_usata as _trova_quando_coppia_usata_mese,
    applica_penalita_storico as _applica_penalita_storico_mese,

    aggiorna_blacklist_terzetti,
)

from moduli.generazione import genera_candidato_mese as _genera_un_candidato_mese
from moduli.casualita import (
    risolvi_seed_principale,
    risolvi_numero_stagioni_riproduzione,
)

from moduli.editor_studenti import EditorStudentiWidget, ComboBoxProtetto

from moduli.tema import C, imposta_tema, get_tema

from moduli.utilita import (
    get_base_path, pulisci_nome_file, apri_file_con_applicazione_default,
    mostra_popup_file_salvato, FiltroCursoreManina,
    crea_bottone,
    giudizio_da_note,
    conta_riutilizzate,
    conta_riutilizzate_con_foto,
    adatta_finestra_allo_schermo,
    applica_icona,
    applica_icona_etichetta,
    applica_stile_pulsante_popup,
    prepara_area_dettagli_popup,
    applica_icona_finestra,
    applica_icona_tab,
    aggiorna_icone_applicazione,
    crea_popup_semantico,
    mostra_popup_semantico,
)

from moduli.statistiche_generali import (
    costruisci_statistiche_generali_coppie,
    costruisci_statistiche_generali_terzetti,
    render_statistiche_html,
    applica_formattazione_statistiche_generali,
)
from moduli.configurazione import ConfigurazioneApp

from moduli.statistiche import StatisticheMixin

from moduli.stili import StiliMixin

from moduli.esportazione import EsportazioneMixin, evidenzia_riutilizzi

from moduli.storico_ui import StoricoUIMixin, PopupLayoutStorico

from moduli.istruzioni import (
    mostra_istruzioni,
    mostra_crediti,
    mostra_aiuto_configurazione_aula,
    aggiorna_tema_finestre_informative,
)

def carica_font_emoji():
    percorso = os.path.join(
        get_base_path(),
        "dati",
        "font",
        "NotoColorEmoji.ttf"
    )

    if not os.path.isfile(percorso):
        print(f"Font emoji non trovato: {percorso}")
        return False

    id_font = QFontDatabase.addApplicationFont(percorso)

    if id_font == -1:
        print(f"Impossibile caricare il font emoji: {percorso}")
        return False

    famiglie = QFontDatabase.applicationFontFamilies(id_font)

    if famiglie:
        QFontDatabase.setApplicationEmojiFontFamilies(famiglie)
        print("Font emoji caricato:", famiglie)
        return True

    print("Il font è stato caricato ma non espone alcuna famiglia.")
    return False

# Parametri della ricerca mensile e annuale
NUM_CANDIDATI = 10

# Il budget è il limite reale; tetto e convergenza evitano lavoro inutile.
BUDGET_STAGIONI_SEC = 600
TETTO_STAGIONI = 5000
K_CONVERGENZA = 300

BUDGET_STAGIONI_TERZETTI_SEC = 600
TETTO_STAGIONI_TERZETTI = 5000
K_CONVERGENZA_TERZETTI = 300


def _data_creazione_corrente() -> str:
    """Restituisce la data tecnica usata da report e Storico."""
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _nome_assegnazione_automatico(
        nome_classe: str, generazione: str, modo: str, numero: int) -> str:
    """Compone il nome uniforme di una voce dello Storico."""
    etichetta_generazione = "Annuale" if generazione == "annuale" else "Mensile"
    etichetta_modo = "Terzetti" if modo == "terzetti" else "Coppie"
    return (
        f"{nome_classe} - {etichetta_generazione} "
        f"{etichetta_modo} - {numero:02d}"
    )


def _prossimo_progressivo_storico(
        config_app, file_origine: str, generazione: str, modo: str) -> int:
    """Conta la serie omogenea classe/generazione/geometria."""
    storico = config_app.config_data.get("storico_assegnazioni", [])
    progressivi = [
        int(assegnazione["progressivo"])
        for assegnazione in storico
        if assegnazione["file_origine"] == file_origine
        and assegnazione["generazione"] == generazione
        and assegnazione["modo"] == modo
    ]
    return max(progressivi, default=0) + 1


def _sostituisci_campo_report(testo: str, prefisso: str, valore: str) -> str:
    """Aggiorna la prima riga del report che usa il prefisso indicato."""
    righe = testo.splitlines()
    for indice, riga in enumerate(righe):
        if riga.startswith(prefisso):
            righe[indice] = f"{prefisso}{valore}"
            break
    return "\n".join(righe)


def _descrivi_abbinamenti_coppie(assegnatore) -> str:
    """Descrive i blocchi fisici visibili nell'Aula a coppie.

    Il FISSO non è un gruppo isolato: con la coppia collocata al suo fianco
    forma un trio; se il trio ordinario è disposto accanto al FISSO, i quattro
    studenti formano invece un quartetto.
    """
    num_coppie = len(getattr(assegnatore, "coppie_formate", []) or [])
    num_trii = 1 if getattr(assegnatore, "trio_identificato", None) else 0
    num_quartetti = 0

    if getattr(assegnatore, "studente_fisso", None) is not None:
        if getattr(assegnatore, "gruppo_adiacente_fisso", None):
            num_trii += 1
        elif getattr(assegnatore, "trio_identificato", None):
            num_trii -= 1
            num_quartetti = 1

    parti = []
    if num_coppie or not (num_trii or num_quartetti):
        parti.append(f"{num_coppie} coppi{'a' if num_coppie == 1 else 'e'}")
    if num_trii:
        parti.append(f"{num_trii} tri{'o' if num_trii == 1 else 'i'}")
    if num_quartetti:
        parti.append(f"{num_quartetti} quartett{'o' if num_quartetti == 1 else 'i'}")
    return " + ".join(parti)


def _descrivi_abbinamenti_terzetti(gruppi) -> str:
    """Descrive i gruppi a terzetti con la grammatica dello Storico."""
    n_ter = sum(1 for gruppo in gruppi if gruppo.tipo == "terzetto")
    n_qua = sum(1 for gruppo in gruppi if gruppo.tipo == "quartetto")
    n_cop = sum(1 for gruppo in gruppi if gruppo.tipo == "coppia")
    parti = [f"{n_ter} terzett{'o' if n_ter == 1 else 'i'}"]
    if n_qua:
        parti.append(f"{n_qua} quartett{'o' if n_qua == 1 else 'i'}")
    if n_cop:
        parti.append(f"{n_cop} coppi{'a' if n_cop == 1 else 'e'}")
    return " + ".join(parti)


def _seleziona_righe_segnalazioni(righe):
    """Seleziona riusi e criticità per le schede sintetiche dell'Annuale."""
    selezionate = []
    for riga in righe or []:
        chiave = riga.get("chiave")
        valore = riga.get("valore")
        if chiave == "riutilizzate":
            selezionate.append(riga)
        elif chiave in {"vicino_fisso_riutilizzato", "dettaglio_vicino_fisso"}:
            selezionate.append(riga)
        elif chiave in {"problematiche", "critiche"}:
            if isinstance(valore, (int, float)) and valore > 0:
                selezionate.append(riga)
    return selezionate


def _crea_widget_righe_statistiche(
        righe, *, solo_segnalazioni=False, sfondo_trasparente=False):
    """Renderizza righe statistiche con icone Lucide separate dal testo."""
    contenitore = QWidget()
    if sfondo_trasparente:
        contenitore.setAutoFillBackground(False)
        contenitore.setStyleSheet(
            "background-color: transparent; border: none;"
        )
    layout = QVBoxLayout(contenitore)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    righe_visibili = (
        _seleziona_righe_segnalazioni(righe)
        if solo_segnalazioni
        else list(righe or [])
    )

    for riga in righe_visibili:
        riga_widget = QWidget()
        if sfondo_trasparente:
            riga_widget.setAutoFillBackground(False)
            riga_widget.setStyleSheet(
                "background-color: transparent; border: none;"
            )
        riga_layout = QHBoxLayout(riga_widget)
        riga_layout.setContentsMargins(0, 0, 0, 0)
        riga_layout.setSpacing(6)

        icona_nome = riga.get("icona_ui")
        if icona_nome:
            icona = QLabel()
            icona.setFixedSize(18, 18)
            icona.setAlignment(Qt.AlignCenter)
            if sfondo_trasparente:
                icona.setAutoFillBackground(False)
                icona.setStyleSheet(
                    "background-color: transparent; border: none;"
                )
            applica_icona_etichetta(icona, icona_nome, 16)
            riga_layout.addWidget(icona, alignment=Qt.AlignTop)
        else:
            riga_layout.addSpacing(24)

        testo_html = render_statistiche_html([riga])[0]
        etichetta = QLabel(testo_html)
        etichetta.setTextFormat(Qt.RichText)
        etichetta.setWordWrap(True)
        if sfondo_trasparente:
            etichetta.setAutoFillBackground(False)
            etichetta.setStyleSheet(
                "background-color: transparent; border: none;"
            )
        riga_layout.addWidget(etichetta, 1)
        layout.addWidget(riga_widget)

    return contenitore


def _aggiungi_widget_popup(msg_box, widget) -> None:
    """Inserisce un widget prima della barra dei pulsanti del QMessageBox."""
    layout = msg_box.layout()
    if isinstance(layout, QGridLayout):
        barra_pulsanti = msg_box.findChild(QDialogButtonBox)
        if barra_pulsanti is not None:
            indice = layout.indexOf(barra_pulsanti)
            if indice >= 0:
                riga, colonna, righe, colonne = layout.getItemPosition(indice)
                layout.removeWidget(barra_pulsanti)
                layout.addWidget(
                    widget, riga, 0, 1, max(1, layout.columnCount())
                )
                layout.addWidget(
                    barra_pulsanti, riga + 1, colonna, righe, colonne
                )
                return

        layout.addWidget(
            widget, layout.rowCount(), 0, 1, max(1, layout.columnCount())
        )
        return

    layout.addWidget(widget)


# Generazione mensile e annuale

def calcola_miglior_mese(studenti, aula_originale, config_app,
                         modalita_trio, flag_genere_misto, studente_fisso,
                         coppie_gia_usate, num_candidati=NUM_CANDIDATI,
                         deve_fermarsi=None, seed_principale=None,
                         contesto_casuale=None):
    """Genera più candidati per un mese e restituisce la disposizione con la migliore chiave di pulizia."""
    miglior_assegnatore = None
    miglior_chiave = None
    ultimo_assegnatore = None

    seed_principale = risolvi_seed_principale(seed_principale)
    contesto_casuale = dict(contesto_casuale or {})

    # Tutti i candidati confrontano i riusi rispetto alla stessa fotografia iniziale.
    vicini_fisso_gia_usati = snapshot_vicini_fisso(config_app)

    # Dopo un candidato arrivato al quarto tentativo si possono saltare i tentativi già inutili.
    tentativo_partenza = 1

    for _n_candidato in range(num_candidati):
        indice_candidato = _n_candidato + 1

        if deve_fermarsi is not None and deve_fermarsi():
            break
        successo, assegnatore = _genera_un_candidato_mese(
            studenti, aula_originale, config_app,
            modalita_trio, flag_genere_misto, studente_fisso,
            tentativo_iniziale=tentativo_partenza,
            seed_principale=seed_principale,
            contesto_casuale=contesto_casuale,
            indice_candidato=indice_candidato,
        )
        ultimo_assegnatore = assegnatore

        _tent_cand = getattr(assegnatore.motore_vincoli, 'tentativo_corrente', None)
        if _tent_cand == 4:
            tentativo_partenza = 4

        if not successo:

            continue

        chiave = chiave_pulizia(
            assegnatore,
            coppie_gia_usate,
            vicini_fisso_gia_usati,
        )
        if miglior_chiave is None or chiave < miglior_chiave:
            miglior_chiave = chiave
            miglior_assegnatore = assegnatore

        tentativo = getattr(assegnatore.motore_vincoli, 'tentativo_corrente', None)
        # Nei primi tre tentativi non vengono tollerate incompatibilità: il risultato è già pienamente valido.
        if tentativo is not None and tentativo <= 3:
            break

    return miglior_assegnatore, ultimo_assegnatore

# Worker di calcolo

class WorkerThread(QThread):
    """Esegue l’assegnazione mensile senza bloccare l’interfaccia."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    completed = Signal(object)
    error_occurred = Signal(str, object)

    def __init__(self, studenti, configurazione_aula, config_app, modalita_trio='centro', flag_genere_misto=False, studente_fisso=None, seed_principale=None):
        super().__init__()
        self.studenti = studenti
        self.configurazione_aula = configurazione_aula
        self.config_app = config_app

        self.modalita_rotazione = True
        self.modalita_trio = modalita_trio
        self.flag_genere_misto = flag_genere_misto
        self.studente_fisso = studente_fisso
        self.seed_principale = risolvi_seed_principale(seed_principale)

    def run(self):
        """Genera e pubblica la migliore assegnazione mensile disponibile."""
        try:
            self.status_updated.emit("Inizializzazione algoritmo...")
            self.progress_updated.emit(10)

            coppie_gia_usate = snapshot_blacklist(self.config_app)

            self.status_updated.emit("Cerco la disposizione migliore...")
            self.progress_updated.emit(30)

            print(f"🎲 Operazione mensile a coppie — seed principale: {self.seed_principale}")
            miglior_assegnatore, ultimo_assegnatore = calcola_miglior_mese(
                self.studenti,
                self.configurazione_aula,
                self.config_app,
                self.modalita_trio,
                self.flag_genere_misto,
                self.studente_fisso,
                coppie_gia_usate,
                seed_principale=self.seed_principale,
                contesto_casuale={
                    "operazione": "mensile",
                    "mese": 1,
                },
            )

            self.progress_updated.emit(90)

            if miglior_assegnatore is not None:
                self.status_updated.emit("Assegnazione completata!")
                self.progress_updated.emit(100)
                self.completed.emit(miglior_assegnatore)
            else:

                report = getattr(ultimo_assegnatore, 'report_fallimento', None)
                self.error_occurred.emit(
                    "Assegnazione fallita - vincoli irrisolvibili",
                    report
                )

        except Exception as e:

            self.error_occurred.emit(f"Errore durante l'assegnazione: {str(e)}", None)

def genera_una_stagione_gui(
        studenti,
        configurazione_aula,
        config_app,
        modalita_trio,
        flag_genere_misto,
        studente_fisso,
        num_mesi,
        num_candidati=NUM_CANDIDATI,
        progresso=None,
        t0_globale=None,
        budget_secondi=None,
        deve_fermarsi=None,
        on_fallimento=None,
        seed_principale=None,
        indice_stagione=1):
    """Genera una sequenza di mesi a coppie su una configurazione temporanea, senza modificare lo Storico reale."""
    seed_principale = risolvi_seed_principale(seed_principale)

    # La stagione cresce su una copia: lo Storico reale cambia soltanto dopo l’accettazione.
    config_temp = copy.deepcopy(config_app)

    mesi = []
    chiavi = []
    stop_mese = None
    ultima_durata = 0.0

    for mese in range(1, num_mesi + 1):

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if t0_globale is not None and budget_secondi is not None:
            elapsed = time.monotonic() - t0_globale
            proiezione = elapsed + (ultima_durata if mese > 1 else 0.0)
            if proiezione >= budget_secondi:
                stop_mese = "budget"
                break

        t_inizio_mese = time.monotonic()

        coppie_gia_usate = snapshot_blacklist(config_temp)
        vicini_fisso_gia_usati = snapshot_vicini_fisso(
            config_temp
        )

        def _budget_scaduto():
            if t0_globale is None or budget_secondi is None:
                return False
            return (time.monotonic() - t0_globale) >= budget_secondi

        def _stop_mese_corrente():
            if deve_fermarsi is not None and deve_fermarsi():
                return True
            return _budget_scaduto()

        miglior, _ultimo = calcola_miglior_mese(
            studenti, configurazione_aula, config_temp,
            modalita_trio, flag_genere_misto, studente_fisso,
            coppie_gia_usate, num_candidati,
            deve_fermarsi=_stop_mese_corrente,
            seed_principale=seed_principale,
            contesto_casuale={
                "operazione": "annuale",
                "stagione": indice_stagione,
                "mese": mese,
            },
        )

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break
        if _budget_scaduto():
            stop_mese = "budget"
            break

        if miglior is None:
            if on_fallimento is not None:
                report = getattr(
                    _ultimo,
                    'report_fallimento',
                    None
                )
                on_fallimento(report)

            stop_mese = "mese_fallito"
            break

        mesi.append(miglior)
        chiavi.append(chiave_pulizia(
            miglior,
            coppie_gia_usate,
            vicini_fisso_gia_usati,
        ))

        config_temp._aggiorna_coppie_da_evitare(
            miglior.coppie_formate,
            getattr(miglior, 'trio_identificato', None),
            studente_fisso=getattr(miglior, 'studente_fisso', None),
            gruppo_adiacente_fisso=getattr(miglior, 'gruppo_adiacente_fisso', None),
            nome_adiacente_fisso=getattr(miglior, 'nome_adiacente_fisso', None),
        )

        ultima_durata = time.monotonic() - t_inizio_mese

        if progresso is not None:
            progresso(mese, num_mesi)

    return mesi, chiavi, config_temp, stop_mese

def genera_una_stagione_terzetti_gui(studenti, config_app, genere_misto,
                                     preferenza_resto2, resto_in_prima_fila,
                                     num_mesi,
                                     max_terzetti_prima_fila=None,
                                     max_resti_prima_fila=None,
                                     num_candidati=None, progresso=None,
                                     t0_globale=None, budget_secondi=None,
                                     deve_fermarsi=None, on_fallimento=None,
                                     seed_principale=None, indice_stagione=1):
    """Genera una sequenza di mesi a terzetti su una configurazione temporanea, senza modificare lo Storico reale."""

    if num_candidati is None:
        num_candidati = mt.NUM_CANDIDATI_TERZETTI

    seed_principale = risolvi_seed_principale(seed_principale)

    # La stagione cresce su una copia: lo Storico reale cambia soltanto dopo l’accettazione.
    config_temp = copy.deepcopy(config_app)

    mesi = []
    chiavi = []
    stop_mese = None
    ultima_durata = 0.0

    for mese in range(1, num_mesi + 1):

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if t0_globale is not None and budget_secondi is not None:
            elapsed = time.monotonic() - t0_globale
            proiezione = elapsed + (ultima_durata if mese > 1 else 0.0)
            if proiezione >= budget_secondi:
                stop_mese = "budget"
                break

        t_inizio_mese = time.monotonic()

        adiacenze_prima = snapshot_blacklist_terzetti(config_temp)

        gruppi, metadati_casualita = mt.calcola_miglior_mese_terzetti(
            studenti,
            genere_misto,
            config_app=config_temp,
            preferenza_resto2=preferenza_resto2,
            resto_in_prima_fila=resto_in_prima_fila,
            max_terzetti_prima_fila=max_terzetti_prima_fila,
            max_resti_prima_fila=max_resti_prima_fila,
            num_candidati=num_candidati,
            seed_base=seed_principale,
            contesto_casuale={
                "operazione": "annuale",
                "stagione": indice_stagione,
                "mese": mese,
            },
            restituisci_metadati=True,
        )

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if gruppi is None:
            if on_fallimento is not None:
                on_fallimento({
                    "casualita": metadati_casualita,
                    "cause_certe": [],
                    "suggerimenti": [
                        "Controlla incompatibilità di livello 3, posizioni PRIMA "
                        "e configurazione dei blocchi a terzetti."
                    ],
                })
            stop_mese = "mese_fallito"
            break

        mesi.append({
            'gruppi': gruppi,
            'adiacenze_prima': adiacenze_prima,
            'metadati_casualita': metadati_casualita,
        })
        chiavi.append(chiave_pulizia_terzetti(gruppi, adiacenze_prima))

        adiacenze = adiacenze_per_blacklist_terzetti(gruppi)
        aggiorna_blacklist_terzetti(config_temp, adiacenze)

        ultima_durata = time.monotonic() - t_inizio_mese
        if progresso is not None:
            progresso(mese, num_mesi)

    return mesi, chiavi, config_temp, stop_mese

def _formatta_durata(secondi):
    """Formatta una durata in secondi come stringa breve per l’interfaccia."""
    secondi = int(round(secondi))
    ore, resto = divmod(secondi, 3600)
    minuti, sec = divmod(resto, 60)
    if ore > 0:
        return f"{ore}h {minuti:02d}m"
    if minuti > 0:
        return f"{minuti}m {sec:02d}s"
    return f"{sec}s"

def genera_migliore_stagione(genera_una_stagione, num_mesi,
                             budget_secondi=BUDGET_STAGIONI_SEC,
                             tetto=TETTO_STAGIONI, k_convergenza=K_CONVERGENZA,
                             progresso=None, deve_fermarsi=None,
                             numero_stagioni_fisso=None):
    """Seleziona la migliore stagione con arresto per budget, convergenza, limite o annullamento."""
    numero_stagioni_fisso = risolvi_numero_stagioni_riproduzione(
        numero_stagioni_fisso
    )
    budget_generatore = (
        float('inf')
        if numero_stagioni_fisso is not None
        else budget_secondi
    )
    t0 = time.monotonic()

    def _genera_una(indice_stagione):

        return genera_una_stagione(
            indice_stagione, t0, budget_generatore, deve_fermarsi
        )

    migliori_mesi, migliori_chiavi, _ct, stop1 = _genera_una(1)
    miglior_punteggio = punteggio_stagione(migliori_chiavi)

    n_stagioni = 1

    n_stagioni_complete = 1 if stop1 is None else 0

    indice_stagione_migliore = 1
    senza_migliorare = 0
    k = time.monotonic() - t0
    motivo_stop = None

    def _emetti(motivo):

        if progresso is None:
            return
        elapsed = time.monotonic() - t0

        if numero_stagioni_fisso is not None:
            eta_max = max(0, numero_stagioni_fisso - n_stagioni) * k
        else:
            eta_a_budget = max(0.0, budget_secondi - elapsed)
            eta_a_tetto = max(0, tetto - n_stagioni) * k
            eta_max = min(eta_a_budget, eta_a_tetto)
        progresso({
            'n_stagioni': n_stagioni,
            'tot_ripetizioni': miglior_punteggio[0],
            'elapsed': elapsed,
            'eta_max': eta_max,
            'k': k,
            'motivo_stop': motivo,
        })

    if stop1 == "annullato":

        motivo_stop = "annullato"
        _emetti(motivo_stop)
    elif stop1 == "mese_fallito":

        motivo_stop = "mese_fallito"
        _emetti(motivo_stop)
    elif stop1 == "budget":

        motivo_stop = "budget (1ª annata parziale)"
        _emetti(motivo_stop)
    else:

        _emetti(None)
        while True:

            if deve_fermarsi is not None and deve_fermarsi():
                motivo_stop = "annullato"; break

            elapsed = time.monotonic() - t0

            if numero_stagioni_fisso is not None:
                if n_stagioni >= numero_stagioni_fisso:
                    motivo_stop = "riproduzione"; break
            else:
                if elapsed + k > budget_secondi:
                    motivo_stop = "budget"; break
                if n_stagioni >= tetto:
                    motivo_stop = "tetto"; break
                if senza_migliorare >= k_convergenza:
                    motivo_stop = "convergenza"; break

            indice_stagione = n_stagioni + 1
            mesi_i, chiavi_i, _ct, stop_i = _genera_una(indice_stagione)

            if stop_i == "annullato":

                motivo_stop = "annullato"; break
            if stop_i == "budget":

                motivo_stop = "budget"; break

            n_stagioni += 1

            # Solo le stagioni complete sono confrontabili: una stagione parziale avrebbe un punteggio artificialmente basso.
            if stop_i is None:

                n_stagioni_complete += 1
                punteggio_i = punteggio_stagione(chiavi_i)
                if punteggio_i < miglior_punteggio:
                    miglior_punteggio = punteggio_i
                    migliori_mesi, migliori_chiavi = mesi_i, chiavi_i
                    indice_stagione_migliore = indice_stagione
                    senza_migliorare = 0
                else:
                    senza_migliorare += 1
            else:

                senza_migliorare += 1

            k = (time.monotonic() - t0) / n_stagioni
            _emetti(None)

        _emetti(motivo_stop)

    info = {

        'n_stagioni': n_stagioni,

        'n_stagioni_complete': n_stagioni_complete,
        'punteggio': miglior_punteggio,
        'tot_ripetizioni': miglior_punteggio[0],
        'motivo_stop': motivo_stop,
        'elapsed': time.monotonic() - t0,
        'k': k,
        'mesi_completi': len(migliori_mesi),
        'num_mesi_richiesti': num_mesi,
        'indice_stagione_migliore': indice_stagione_migliore,
        'numero_stagioni_fisso': numero_stagioni_fisso,
    }
    return migliori_mesi, migliori_chiavi, info

def riordina_e_cattura_stagione_coppie(mesi, config_app, cattura_report=None):
    """Riordina la stagione a coppie per pulizia e ricostruisce report e fotografie nel nuovo ordine."""

    foto_iniziale = snapshot_blacklist(config_app)

    _contatore_vic = config_app.config_data.get(
        "studenti_vicino_fisso_contatore", {})
    vicini_visti = {nome for nome, volte in _contatore_vic.items()
                    if volte >= 1}

    # Report e fotografie vengono ricostruiti dopo il riordino, così descrivono il nuovo ordine reale.
    ordine_nuovo = riordina_stagione_per_pulizia(
        mesi,
        foto_iniziale,
        vicini_visti,
    )

    ultimo_uso_coppie = {}
    ultimo_uso_vicino = {}
    mesi_riordinati = []
    chiavi_nuove = []

    for _idx_orig, asg, chiave_nuova, foto in ordine_nuovo:

        asg.riutilizzate_snapshot = conta_riutilizzate_con_foto(
            asg, foto, vicini_visti)

        if cattura_report is not None:
            asg.report_testo = cattura_report(
                asg, ultimo_uso_coppie, ultimo_uso_vicino,
                foto, set(vicini_visti))

        etichetta_mese = f"mese {len(mesi_riordinati) + 1}"
        for _s1, _s2, _ in asg.coppie_formate:
            _k = tuple(sorted([_s1.get_nome_completo(), _s2.get_nome_completo()]))
            ultimo_uso_coppie[_k] = etichetta_mese
        _trio = getattr(asg, 'trio_identificato', None)
        if _trio and len(_trio) == 3:
            for _a, _b in [(_trio[0], _trio[1]), (_trio[1], _trio[2])]:
                _k = tuple(sorted([_a.get_nome_completo(), _b.get_nome_completo()]))
                ultimo_uso_coppie[_k] = etichetta_mese
        _gruppo = getattr(asg, 'gruppo_adiacente_fisso', None)
        if _gruppo and len(_gruppo) >= 2:
            _k = tuple(sorted([_gruppo[0].get_nome_completo(),
                               _gruppo[1].get_nome_completo()]))
            ultimo_uso_coppie[_k] = etichetta_mese
        _nome_vic = getattr(asg, 'nome_adiacente_fisso', None)
        if _nome_vic:
            ultimo_uso_vicino[_nome_vic] = etichetta_mese
            vicini_visti.add(_nome_vic)

        mesi_riordinati.append(asg)
        chiavi_nuove.append(chiave_nuova)

    return mesi_riordinati, chiavi_nuove

def riordina_stagione_terzetti_gui(mesi, config_app):
    """Riordina la stagione a terzetti e aggiorna le fotografie delle adiacenze nel nuovo ordine."""

    foto_iniziale = snapshot_blacklist_terzetti(config_app)

    ordine_nuovo = riordina_stagione_per_pulizia_terzetti(mesi, foto_iniziale)

    mesi_riordinati = [mese_nuovo for _idx_orig, mese_nuovo, _chiave in ordine_nuovo]
    chiavi_riordinate = [chiave for _idx_orig, _mese_nuovo, chiave in ordine_nuovo]

    return mesi_riordinati, chiavi_riordinate

class _SilenziaStdout:
    """Sospende temporaneamente l’output standard durante i calcoli annuali."""

    def __enter__(self):
        self._old_stdout = sys.stdout
        self._devnull = open(os.devnull, 'w')
        sys.stdout = self._devnull
        return self

    def __exit__(self, *exc):
        sys.stdout = self._old_stdout
        self._devnull.close()
        return False

class SeasonWorkerThread(QThread):
    """Genera in background la migliore stagione a coppie."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    stagione_completata = Signal(object)
    error_occurred = Signal(str, object)
    stato_annuale_updated = Signal(object)

    def __init__(self, studenti, configurazione_aula, config_app, num_mesi,
                 modalita_trio='centro', flag_genere_misto=False,
                 studente_fisso=None, num_candidati=NUM_CANDIDATI,
                 cattura_report=None, seed_principale=None):
        super().__init__()
        self.studenti = studenti
        self.configurazione_aula = configurazione_aula
        self.config_app = config_app
        self.num_mesi = num_mesi
        self.modalita_trio = modalita_trio
        self.flag_genere_misto = flag_genere_misto
        self.studente_fisso = studente_fisso
        self.num_candidati = num_candidati

        self.cattura_report = cattura_report
        self.seed_principale = risolvi_seed_principale(seed_principale)

        self._stop_richiesto = False

    def richiedi_stop(self):
        """Richiede un arresto cooperativo al primo controllo disponibile."""
        self._stop_richiesto = True

    def run(self):
        """Genera la migliore stagione a coppie e ne comunica stato ed esito."""
        try:

            self._stagione_corrente = 1
            self._ultimo_best = None
            self._ultima_eta = None

            def _emetti_stato(mese):

                self.stato_annuale_updated.emit({
                    'tentativo': self._stagione_corrente,
                    'mese': mese,
                    'num_mesi': self.num_mesi,
                    'best': self._ultimo_best,
                    'eta_max': self._ultima_eta,
                })

            def _progresso_mese(mese, num_mesi):
                _emetti_stato(mese)

            def _progresso(info):
                if info['motivo_stop'] is not None:
                    return
                self._ultimo_best = info['tot_ripetizioni']
                self._ultima_eta = info['eta_max']
                self._stagione_corrente = info['n_stagioni'] + 1
                _emetti_stato(0)

            self._report_fallimento_annuale = None

            def _cattura_fallimento_annuale(report):
                self._report_fallimento_annuale = report

            def _stagione_coppie(indice_stagione, t0_globale,
                                  budget_secondi, deve_fermarsi):
                return genera_una_stagione_gui(
                    self.studenti,
                    self.configurazione_aula,
                    self.config_app,
                    self.modalita_trio,
                    self.flag_genere_misto,
                    self.studente_fisso,
                    self.num_mesi,
                    self.num_candidati,
                    progresso=_progresso_mese,
                    t0_globale=t0_globale,
                    budget_secondi=budget_secondi,
                    deve_fermarsi=deve_fermarsi,
                    on_fallimento=(
                        _cattura_fallimento_annuale
                    ),
                    seed_principale=self.seed_principale,
                    indice_stagione=indice_stagione,
                )

            print(
                f"🎲 Operazione annuale a coppie — seed principale: "
                f"{self.seed_principale}"
            )
            with _SilenziaStdout():
                migliori_mesi, migliori_chiavi, info = genera_migliore_stagione(
                    _stagione_coppie,
                    self.num_mesi,
                    progresso=_progresso,
                    deve_fermarsi=lambda: self._stop_richiesto,
                    numero_stagioni_fisso=(
                        risolvi_numero_stagioni_riproduzione()
                    ),
                )

            info['seed_principale'] = self.seed_principale
            info['modalita'] = 'coppie'

            for assegnatore in migliori_mesi:
                assegnatore.contesto_casuale.update({
                    "stagioni_generate": info.get('n_stagioni'),
                    "stagione_vincente": info.get(
                        'indice_stagione_migliore'
                    ),
                })
            motivo = info['motivo_stop']

            if motivo == "mese_fallito":
                generati = len(migliori_mesi) if migliori_mesi else 0
                self.error_occurred.emit(
                    f"Non è stato possibile completare una disposizione "
                    f"valida per uno dei mesi "
                    f"(completati {generati} mesi su {self.num_mesi}).",
                    self._report_fallimento_annuale
                )
                return

            migliori_mesi, migliori_chiavi = riordina_e_cattura_stagione_coppie(
                migliori_mesi, self.config_app, self.cattura_report)

            info['tot_ripetizioni'] = sum(
                assegnatore.riutilizzate_snapshot['totali']
                for assegnatore in migliori_mesi
            )

            self.stagione_completata.emit({
                'mesi': migliori_mesi,
                'chiavi': migliori_chiavi,
                'info': info,
            })

        except Exception as e:
            self.error_occurred.emit(
                f"Errore durante la generazione delle assegnazioni: {str(e)}", None
            )

class SeasonWorkerThreadTerzetti(QThread):
    """Genera in background la migliore stagione a terzetti."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    stagione_completata = Signal(object)
    error_occurred = Signal(str, object)
    stato_annuale_updated = Signal(object)

    def __init__(self, studenti, config_app, num_mesi, genere_misto,
                 preferenza_resto2, resto_in_prima_fila,
                 max_terzetti_prima_fila=None,
                 max_resti_prima_fila=None,
                 num_candidati=None, seed_principale=None):
        super().__init__()
        self.studenti = studenti
        self.config_app = config_app
        self.num_mesi = num_mesi
        self.genere_misto = genere_misto
        self.preferenza_resto2 = preferenza_resto2
        self.resto_in_prima_fila = resto_in_prima_fila
        self.max_terzetti_prima_fila = max_terzetti_prima_fila
        self.max_resti_prima_fila = max_resti_prima_fila

        self.num_candidati = num_candidati
        self.seed_principale = risolvi_seed_principale(seed_principale)
        self._report_fallimento_annuale = None

        self._stop_richiesto = False

    def richiedi_stop(self):
        """Richiede un arresto cooperativo al primo controllo disponibile."""
        self._stop_richiesto = True

    def run(self):
        """Genera la migliore stagione a terzetti e ne comunica stato ed esito."""
        try:

            self._stagione_corrente = 1
            self._ultimo_best = None
            self._ultima_eta = None

            def _emetti_stato(mese):

                self.stato_annuale_updated.emit({
                    'tentativo': self._stagione_corrente,
                    'mese': mese,
                    'num_mesi': self.num_mesi,
                    'best': self._ultimo_best,
                    'eta_max': self._ultima_eta,
                })

            def _progresso_mese(mese, num_mesi):
                _emetti_stato(mese)

            def _progresso(info):
                if info['motivo_stop'] is not None:
                    return
                self._ultimo_best = info['tot_ripetizioni']
                self._ultima_eta = info['eta_max']
                self._stagione_corrente = info['n_stagioni'] + 1
                _emetti_stato(0)

            def _cattura_fallimento_annuale(report):
                self._report_fallimento_annuale = report

            def _stagione_terzetti(indice_stagione, t0_globale,
                                     budget_secondi, deve_fermarsi):
                return genera_una_stagione_terzetti_gui(
                    self.studenti,
                    self.config_app,
                    self.genere_misto,
                    self.preferenza_resto2,
                    self.resto_in_prima_fila,
                    self.num_mesi,
                    max_terzetti_prima_fila=(
                        self.max_terzetti_prima_fila
                    ),
                    max_resti_prima_fila=(
                        self.max_resti_prima_fila
                    ),
                    num_candidati=self.num_candidati,
                    progresso=_progresso_mese,
                    t0_globale=t0_globale,
                    budget_secondi=budget_secondi,
                    deve_fermarsi=deve_fermarsi,
                    on_fallimento=_cattura_fallimento_annuale,
                    seed_principale=self.seed_principale,
                    indice_stagione=indice_stagione,
                )

            print(
                f"🎲 Operazione annuale a terzetti — seed principale: "
                f"{self.seed_principale}"
            )
            with _SilenziaStdout():
                migliori_mesi, migliori_chiavi, info = genera_migliore_stagione(
                    _stagione_terzetti,
                    self.num_mesi,

                    budget_secondi=BUDGET_STAGIONI_TERZETTI_SEC,
                    tetto=TETTO_STAGIONI_TERZETTI,
                    k_convergenza=K_CONVERGENZA_TERZETTI,
                    progresso=_progresso,
                    deve_fermarsi=lambda: self._stop_richiesto,
                    numero_stagioni_fisso=(
                        risolvi_numero_stagioni_riproduzione()
                    ),
                )

            info['seed_principale'] = self.seed_principale
            info['modalita'] = 'terzetti'

            for mese in migliori_mesi:
                metadati = mese.get('metadati_casualita') or {}
                contesto = metadati.setdefault('contesto', {})
                contesto.update({
                    "stagioni_generate": info.get('n_stagioni'),
                    "stagione_vincente": info.get(
                        'indice_stagione_migliore'
                    ),
                })
                mese['metadati_casualita'] = metadati
            motivo = info['motivo_stop']

            if motivo == "mese_fallito":
                generati = len(migliori_mesi) if migliori_mesi else 0
                self.error_occurred.emit(
                    f"La classe sembra avere vincoli irrisolvibili: un mese non "
                    f"ammette alcuna disposizione valida "
                    f"(completati {generati} mesi su {self.num_mesi}).",
                    self._report_fallimento_annuale
                )
                return

            migliori_mesi, migliori_chiavi = riordina_stagione_terzetti_gui(
                migliori_mesi, self.config_app)

            self.stagione_completata.emit({
                'mesi': migliori_mesi,
                'chiavi': migliori_chiavi,
                'info': info,
            })

        except Exception as e:
            self.error_occurred.emit(
                f"Errore durante la generazione delle assegnazioni: {str(e)}", None
            )

# Anteprima e accettazione delle stagioni

class AnteprimaStagioneDialog(QDialog):
    """Mostra una stagione mese per mese e consente di accettarla o scartarla."""

    def __init__(self, parent, config_app, mesi, info, file_origine, nome_classe,
                 modo='coppie', terzetti_per_fila=None, posizione_blocco_finale=None,
                 ha_fisso=False, preferenza_resto2='coppia'):
        """Inizializza l’anteprima con i mesi generati e i dati di riepilogo."""
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.mesi = mesi or []
        self.info = info or {}
        self.file_origine = file_origine
        self.nome_classe = nome_classe or "Classe"

        self.modo = modo
        self._terzetti_per_fila = terzetti_per_fila
        self._posizione_blocco_finale = posizione_blocco_finale
        self._ha_fisso = ha_fisso
        self._preferenza_resto2 = preferenza_resto2

        self.generazione = "annuale"
        self.data_creazione = _data_creazione_corrente()
        self.numero_partenza = _prossimo_progressivo_storico(
            self.config_app,
            self.file_origine,
            self.generazione,
            self.modo,
        )
        self.progressivi_assegnazioni = [
            self.numero_partenza + indice
            for indice in range(len(self.mesi))
        ]
        self.nomi_assegnazioni = [
            _nome_assegnazione_automatico(
                self.nome_classe,
                self.generazione,
                self.modo,
                progressivo,
            )
            for progressivo in self.progressivi_assegnazioni
        ]

        if self.modo == "coppie":
            for indice, assegnatore in enumerate(self.mesi):
                report = getattr(assegnatore, "report_testo", None)
                if not report:
                    continue
                report = _sostituisci_campo_report(
                    report, "Data creazione: ", self.data_creazione
                )
                report = _sostituisci_campo_report(
                    report, "Assegnazione: ", self.nomi_assegnazioni[indice]
                )
                assegnatore.report_testo = report

        self._mesi_non_validi_prima = 0
        if self.modo == 'terzetti':

            self._prepara_mesi_terzetti()

        self.accettato = False

        self._concluso = False

        self.setWindowTitle(
            "Anteprima assegnazioni annuali — Accetta o Scarta"
        )
        applica_icona_finestra(self, "history")
        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )

        self._setup_ui()
        self._applica_stile()

    def _prepara_mesi_terzetti(self):
        """Posiziona i gruppi di ogni mese a terzetti e prepara le relative aule."""

        motore_statistiche = MotoreVincoliConfigurato()

        for mese in self.mesi:
            gruppi = mese['gruppi']

            num_studenti = sum(len(g.membri) for g in gruppi)

            aula = ConfigurazioneAula("Anteprima terzetti")
            aula.crea_layout_terzetti(
                num_studenti,
                terzetti_per_fila=self._terzetti_per_fila,
                posizione_blocco_finale=self._posizione_blocco_finale,
                ha_fisso=self._ha_fisso,
                preferenza_resto2=self._preferenza_resto2,
            )

            report = aula.piazza_gruppi_terzetti(gruppi)
            mese['aula'] = aula
            mese['prima_fuori'] = report.get('prima_fuori_capienza', 0)
            righe_statistiche, _dati_statistiche = \
                costruisci_statistiche_generali_terzetti(
                    gruppi,
                    motore_statistiche,
                    adiacenze_gia_usate=mese.get('adiacenze_prima', set()),
                )
            mese['statistiche_generali'] = righe_statistiche
            if not report.get('valido_prima', True):
                self._mesi_non_validi_prima += 1

    def _setup_ui(self):
        """Costruisce intestazione, elenco dei mesi e comandi dell’anteprima."""
        layout_principale = QVBoxLayout(self)

        layout_principale.addWidget(self._crea_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        contenitore = QWidget()
        layout_mesi = QVBoxLayout(contenitore)

        for indice, assegnatore in enumerate(self.mesi):
            layout_mesi.addWidget(self._crea_scheda_mese(indice, assegnatore))
        layout_mesi.addStretch()
        scroll.setWidget(contenitore)
        layout_principale.addWidget(scroll)

        layout_principale.addWidget(self._crea_footer())

    def _crea_header(self):
        """Crea il riepilogo generale della stagione."""
        num_mesi = len(self.mesi)
        num_richiesti = self.info.get('num_mesi_richiesti', num_mesi)

        n_stagioni_complete = self.info.get(
            'n_stagioni_complete',
            self.info.get('n_stagioni', 1),
        )
        ripetizioni = self.info.get('tot_ripetizioni', 0)
        punteggio = self.info.get('punteggio', (0, 0, 0))

        incomp_pesate = punteggio[1] if len(punteggio) > 1 else 0
        elapsed = self.info.get('elapsed', 0)

        parziale = num_mesi < num_richiesti

        header = QGroupBox("Riepilogo")
        layout = QVBoxLayout(header)

        DIM_FONT_HEADER = 14

        def _riga(testo_html, icona_nome):
            contenitore_riga = QWidget()
            contenitore_riga.setAutoFillBackground(False)
            contenitore_riga.setStyleSheet(
                "background-color: transparent; border: none;"
            )
            layout_riga = QHBoxLayout(contenitore_riga)
            layout_riga.setContentsMargins(0, 1, 0, 1)
            layout_riga.setSpacing(8)

            icona = QLabel()
            icona.setFixedSize(24, 24)
            icona.setAlignment(Qt.AlignCenter)
            icona.setAutoFillBackground(False)
            icona.setStyleSheet(
                "background-color: transparent; border: none;"
            )
            applica_icona_etichetta(icona, icona_nome, 20)
            layout_riga.addWidget(icona, alignment=Qt.AlignTop)

            etichetta = QLabel(testo_html)
            etichetta.setTextFormat(Qt.RichText)
            etichetta.setWordWrap(True)
            etichetta.setAutoFillBackground(False)
            etichetta.setStyleSheet(
                f"font-size: {DIM_FONT_HEADER}px; "
                "background-color: transparent; border: none;"
            )
            layout_riga.addWidget(etichetta, 1)
            return contenitore_riga

        if parziale:
            testo_mesi = (f"<b>{num_mesi}</b> mesi pronti su {num_richiesti} "
                          f"(annata <b>parziale</b>: raggiunto il tempo massimo).")
            icona_mesi = "triangle-alert"
        else:
            testo_mesi = f"<b>{num_mesi}</b> mesi pronti (annata completa)."
            icona_mesi = "circle-check"
        layout.addWidget(_riga(testo_mesi, icona_mesi))

        if n_stagioni_complete <= 1:
            testo_confronto = "Disposizione unica (nessun confronto)."
            icona_confronto = "file-text"
        else:
            testo_confronto = (
                f"Migliore tra {n_stagioni_complete} "
                f"annate complete confrontate."
            )
            icona_confronto = "wand-sparkles"
        layout.addWidget(_riga(testo_confronto, icona_confronto))

        if self.modo == 'terzetti':
            if ripetizioni == 0:
                testo_rip = "Nessuna vicinanza ripetuta."
                icona_rip = "circle-check"
            else:
                testo_rip = f"Vicinanze che si ripresentano: <b>{ripetizioni}</b>."
                icona_rip = "repeat-2"
        else:
            if ripetizioni == 0:
                testo_rip = "Nessuna ripetizione di coppie."
                icona_rip = "circle-check"
            else:
                testo_rip = f"Coppie che si ritrovano vicine: <b>{ripetizioni}</b>."
                icona_rip = "repeat-2"
        layout.addWidget(_riga(testo_rip, icona_rip))

        if incomp_pesate == 0:
            testo_incomp = "Tutti i vincoli di incompatibilità rispettati."
            icona_incomp = "circle-check"
        else:
            testo_incomp = ("Alcuni vincoli di incompatibilità non pienamente "
                            "rispettati (dettagli nei singoli mesi).")
            icona_incomp = "triangle-alert"
        layout.addWidget(_riga(testo_incomp, icona_incomp))

        layout.addWidget(_riga(
            f"Tempo impiegato: {_formatta_durata(elapsed)}.",
            "timer",
        ))

        if self.modo == 'terzetti' and self._mesi_non_validi_prima > 0:
            n = self._mesi_non_validi_prima
            layout.addWidget(_riga(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Errore interno in {n} '
                f'{"mese" if n == 1 else "mesi"}: il vincolo assoluto PRIMA '
                f'non è stato rispettato. L’annata non può essere salvata.</span>',
                "circle-x",
            ))

        return header

    def _crea_scheda_mese(self, indice, assegnatore):
        """Crea la scheda riepilogativa di un mese a coppie."""

        if self.modo == 'terzetti':
            return self._crea_scheda_mese_terzetti(indice, assegnatore)
        scheda = QFrame()
        scheda.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(scheda)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        etichetta_mese = QLabel(f"Mese {indice + 1}")
        etichetta_mese.setStyleSheet(
            f"color: {C('testo_blu')}; font-weight: bold; font-size: 16px;"
        )

        layout.addWidget(etichetta_mese, alignment=Qt.AlignTop)
        layout.addSpacing(20)

        colonna_note = QVBoxLayout()

        colonna_note.addWidget(
            self._crea_widget_righe_anteprima(
                getattr(assegnatore, 'statistiche_generali', [])
            )
        )

        colonna_note.addStretch()
        layout.addLayout(colonna_note)

        layout.addStretch()

        btn_vedi = QPushButton("Vedi disposizione")
        applica_icona(btn_vedi, "eye", 16)
        btn_vedi.setMinimumHeight(36)

        btn_vedi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_layout_bg")};
                color: {C("storico_btn_layout_txt")};
                border: 1px solid {C("storico_btn_layout_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_layout_hover")};
                border-color: {C("storico_btn_layout_bordo")};
            }}
        """)

        btn_vedi.clicked.connect(
            lambda _checked=False, i=indice, a=assegnatore: self._vedi_disposizione(i, a)
        )
        layout.addWidget(btn_vedi)

        btn_report = QPushButton("Report")
        applica_icona(btn_report, "file-text", 16)
        btn_report.setMinimumHeight(36)

        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_dettagli_bg")};
                color: {C("storico_btn_dettagli_txt")};
                border: 1px solid {C("storico_btn_dettagli_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_dettagli_hover")};
                border-color: {C("storico_btn_dettagli_bordo")};
            }}
        """)
        btn_report.clicked.connect(
            lambda _checked=False, i=indice, a=assegnatore: self._vedi_report(i, a)
        )
        layout.addWidget(btn_report)

        return scheda

    def _crea_scheda_mese_terzetti(self, indice, mese):
        """Crea la scheda riepilogativa di un mese a terzetti."""
        gruppi = mese['gruppi']
        adiacenze_prima = mese['adiacenze_prima']

        scheda = QFrame()
        scheda.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(scheda)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        etichetta_mese = QLabel(f"Mese {indice + 1}")
        etichetta_mese.setStyleSheet(
            f"color: {C('testo_blu')}; font-weight: bold; font-size: 16px;"
        )
        layout.addWidget(etichetta_mese, alignment=Qt.AlignTop)
        layout.addSpacing(20)

        colonna_note = QVBoxLayout()

        colonna_note.addWidget(
            self._crea_widget_righe_anteprima(
                mese.get('statistiche_generali', [])
            )
        )

        prima_fuori = mese.get('prima_fuori', 0)
        if prima_fuori > 0:
            etichetta_prima = QLabel(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Disposizione non valida: {prima_fuori} '
                f'{"gruppo" if prima_fuori == 1 else "gruppi"} con studenti PRIMA '
                f'fuori dalla prima fila</span>'
            )
            etichetta_prima.setTextFormat(Qt.RichText)
            colonna_note.addWidget(etichetta_prima)

        colonna_note.addStretch()
        layout.addLayout(colonna_note)
        layout.addStretch()

        btn_vedi = QPushButton("Vedi disposizione")
        applica_icona(btn_vedi, "eye", 16)
        btn_vedi.setMinimumHeight(36)
        btn_vedi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_layout_bg")};
                color: {C("storico_btn_layout_txt")};
                border: 1px solid {C("storico_btn_layout_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_layout_hover")};
                border-color: {C("storico_btn_layout_bordo")};
            }}
        """)

        btn_vedi.clicked.connect(
            lambda _checked=False, i=indice, m=mese: self._vedi_disposizione_terzetti(i, m)
        )
        layout.addWidget(btn_vedi)

        btn_report = QPushButton("Report")
        applica_icona(btn_report, "file-text", 16)
        btn_report.setMinimumHeight(36)
        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_dettagli_bg")};
                color: {C("storico_btn_dettagli_txt")};
                border: 1px solid {C("storico_btn_dettagli_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_dettagli_hover")};
                border-color: {C("storico_btn_dettagli_bordo")};
            }}
        """)
        btn_report.clicked.connect(
            lambda _checked=False, i=indice, m=mese: self._vedi_report_terzetti(i, m)
        )
        layout.addWidget(btn_report)

        return scheda

    @staticmethod
    def _seleziona_righe_anteprima(righe):
        """Seleziona le segnalazioni sintetiche della scheda mensile."""
        return _seleziona_righe_segnalazioni(righe)

    @staticmethod
    def _icona_riga_anteprima(riga):
        """Restituisce l'icona Lucide dichiarata dalla riga strutturata."""
        return riga.get("icona_ui")

    def _crea_widget_righe_anteprima(self, righe):
        """Crea il riepilogo mensile con lo stesso renderer dei popup."""
        return _crea_widget_righe_statistiche(
            righe,
            solo_segnalazioni=True,
            sfondo_trasparente=True,
        )

    def _formatta_conteggi_html_terzetti(self, mese):
        """Formatta in HTML il riepilogo di un mese a terzetti."""
        righe = []
        for riga in self._seleziona_righe_anteprima(
            mese.get('statistiche_generali', [])
        ):
            copia = dict(riga)
            copia['icona'] = None
            righe.append(copia)
        return '<br>'.join(render_statistiche_html(righe))

    def _vedi_disposizione_terzetti(self, indice, mese):
        """Apre in sola lettura la piantina di un mese a terzetti."""
        configurazione_aula = mese['aula']

        dati = {
            "nome": self.nomi_assegnazioni[indice],
            "classe": self.nome_classe,
            "data_creazione": self.data_creazione,
            "abbinamenti": _descrivi_abbinamenti_terzetti(mese["gruppi"]),
            "modo": "terzetti",
        }

        popup = PopupLayoutStorico.da_configurazione(
            self.parent_window, self.config_app, configurazione_aula, dati
        )
        popup.exec()

    def _formatta_conteggi_html(self, assegnatore):
        """Formatta in HTML il riepilogo di un mese a coppie."""
        righe = []
        for riga in self._seleziona_righe_anteprima(
            getattr(assegnatore, 'statistiche_generali', [])
        ):
            copia = dict(riga)
            copia['icona'] = None
            righe.append(copia)
        return '<br>'.join(render_statistiche_html(righe))

    def _vedi_disposizione(self, indice, assegnatore):
        """Apre in sola lettura la piantina di un mese a coppie."""
        configurazione_aula = assegnatore.configurazione_aula

        dati = {
            "nome": self.nomi_assegnazioni[indice],
            "classe": self.nome_classe,
            "data_creazione": self.data_creazione,
            "abbinamenti": _descrivi_abbinamenti_coppie(assegnatore),
            "modo": "coppie",
        }

        popup = PopupLayoutStorico.da_configurazione(
            self.parent_window, self.config_app, configurazione_aula, dati
        )
        popup.exec()

    def _vedi_report(self, indice, assegnatore):
        """Apre il report di un mese a coppie in sola lettura."""

        testo = getattr(assegnatore, 'report_testo', None)
        if not testo:
            testo = ("Report non disponibile per questo mese.\n\n"
                     "(Il report viene catturato durante la generazione annuale.)")

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Report — {self.nomi_assegnazioni[indice]}")
        applica_icona_finestra(dialog, "file-text")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )
        layout = QVBoxLayout(dialog)

        area = QTextEdit()
        area.setReadOnly(True)
        area.setLineWrapMode(QTextEdit.NoWrap)
        font_mono = QFont("monospace")
        font_mono.setStyleHint(QFont.Monospace)
        area.setFont(font_mono)
        area.setPlainText(testo)

        evidenzia_riutilizzi(area)
        applica_formattazione_statistiche_generali(
            area, getattr(assegnatore, 'statistiche_generali', []))
        layout.addWidget(area)

        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.clicked.connect(dialog.close)
        layout.addWidget(btn_chiudi)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QTextEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
            }}
        """)
        dialog.exec()

    def _costruisci_report_mese_terzetti(self, indice):
        """Costruisce il report e il conteggio dei riutilizzi di un mese a terzetti."""
        mese = self.mesi[indice]
        gruppi = mese['gruppi']

        config_report = copy.deepcopy(self.config_app)
        ultimo_uso_vicinanze = {}
        for j, m_prec in enumerate(self.mesi[:indice], start=1):
            adiacenze = adiacenze_per_blacklist_terzetti(m_prec['gruppi'])
            aggiorna_blacklist_terzetti(config_report, adiacenze)

            for coppia in adiacenze:
                ultimo_uso_vicinanze[tuple(sorted(coppia))] = f"mese {j}"

        motore = MotoreVincoliConfigurato()
        motore.imposta_genere_misto_obbligatorio(
            self.parent_window.checkbox_genere_misto.isChecked()
        )
        _applica_penalita_storico_mese(motore, config_report, modo="terzetti")

        aula_salvata = getattr(self.parent_window, 'configurazione_aula', None)
        riga_salvata = getattr(self.parent_window, '_riga_identificativa_report', None)
        self.parent_window.configurazione_aula = mese['aula']
        try:
            testo, riutilizzi = self.parent_window.costruisci_testo_report_terzetti(
                gruppi, motore,
                nome_classe=self.nome_classe,
                studenti=self.parent_window.studenti,
                ultimo_uso_vicinanze=ultimo_uso_vicinanze,
                metadati_casualita=mese.get('metadati_casualita'),
                nome_assegnazione=self.nomi_assegnazioni[indice],
                data_creazione=self.data_creazione,
            )
            mese['statistiche_generali'] = [
                dict(riga) for riga in getattr(
                    self.parent_window,
                    '_statistiche_generali_terzetti_correnti',
                    [],
                )
            ]
        finally:
            self.parent_window.configurazione_aula = aula_salvata
            self.parent_window._riga_identificativa_report = riga_salvata
        return testo, riutilizzi

    def _vedi_report_terzetti(self, indice, mese):
        """Apre il report di un mese a terzetti in sola lettura."""
        testo, _riutilizzi = self._costruisci_report_mese_terzetti(indice)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Report — {self.nomi_assegnazioni[indice]}")
        applica_icona_finestra(dialog, "file-text")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )
        layout = QVBoxLayout(dialog)

        area = QTextEdit()
        area.setReadOnly(True)
        area.setLineWrapMode(QTextEdit.NoWrap)
        font_mono = QFont("monospace")
        font_mono.setStyleHint(QFont.Monospace)
        area.setFont(font_mono)
        area.setPlainText(testo)

        evidenzia_riutilizzi(area)
        applica_formattazione_statistiche_generali(
            area, mese.get('statistiche_generali', []))
        layout.addWidget(area)

        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.clicked.connect(dialog.close)
        layout.addWidget(btn_chiudi)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QTextEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
            }}
        """)
        dialog.exec()

    def _crea_footer(self):
        """Crea i comandi per accettare o scartare la stagione."""
        footer = QWidget()
        layout = QHBoxLayout(footer)
        layout.addStretch()

        btn_scarta = QPushButton("Scarta")
        applica_icona(btn_scarta, "trash-2", 18)
        btn_scarta.setMinimumHeight(45)
        btn_scarta.setStyleSheet(f"""
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
        btn_scarta.clicked.connect(self._on_scarta)
        layout.addWidget(btn_scarta)

        self.btn_accetta = QPushButton("Accetta e salva nello Storico")
        applica_icona(self.btn_accetta, "circle-check", 18)
        self.btn_accetta.setMinimumHeight(45)
        self.btn_accetta.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_salva_bg")};
                color: {C("btn_salva_txt")};
                border: 1px solid {C("btn_salva_bordo")};
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_salva_hover")};
                border-color: {C("btn_salva_bordo")};
            }}
            QPushButton:disabled {{
                background-color: {C("btn_azione_disabled_bg")};
                color: {C("btn_azione_disabled_txt")};
                border-color: {C("btn_azione_disabled_bordo")};
            }}
        """)
        self.btn_accetta.clicked.connect(self._on_accetta)
        if self._mesi_non_validi_prima > 0:
            self.btn_accetta.setEnabled(False)
            self.btn_accetta.setToolTip(
                "Salvataggio bloccato: almeno un mese non rispetta il "
                "vincolo assoluto PRIMA."
            )
        layout.addWidget(self.btn_accetta)

        return footer

    def _conferma_scarto(self):
        """Chiede conferma prima di scartare la stagione."""

        n = len(self.mesi)
        parola = "assegnazione mensile" if n == 1 else "assegnazioni mensili"

        conferma = crea_popup_semantico(
            self.parent_window,
            "Scartare l'intera annata?",
            "L'intera annata appena generata verrà eliminata.",
            "triangle-alert",
            testo_informativo=(
                f"Le {n} {parola} che vedi in anteprima andranno perse e, "
                "se ti servono, dovrai rigenerarle da capo.\n\n"
                "Lo Storico già salvato non viene toccato.\n\n"
                "Vuoi davvero scartare tutto?"
            ),
            messaggio_in_grassetto=True,
        )

        btn_annulla = conferma.addButton("Annulla", QMessageBox.RejectRole)
        btn_scarta = conferma.addButton("Scarta tutto", QMessageBox.DestructiveRole)
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_scarta, "trash-2", 18)
        applica_stile_pulsante_popup(btn_scarta, "distruttivo")

        conferma.setDefaultButton(btn_annulla)
        conferma.setEscapeButton(btn_annulla)

        conferma.exec()
        return conferma.clickedButton() == btn_scarta

    def _on_scarta(self):
        """Scarta la stagione senza modificare lo Storico."""
        self.reject()

    def reject(self):
        """Chiude l’anteprima senza salvare, dopo l’eventuale conferma."""

        if self._concluso:
            super().reject()
            return
        if self._conferma_scarto():
            self.accettato = False
            self._concluso = True
            super().reject()

    def closeEvent(self, event):
        """Gestisce la chiusura della finestra senza salvataggio implicito."""

        if self._concluso:
            event.accept()
            return
        if self._conferma_scarto():
            self.accettato = False
            self._concluso = True
            event.accept()
        else:
            event.ignore()

    def _on_accetta(self):
        """Salva nello Storico tutti i mesi della stagione accettata."""

        if self._mesi_non_validi_prima > 0:
            mostra_popup_semantico(
                self.parent_window,
                "Annata non salvabile",
                "Almeno un mese non rispetta il vincolo assoluto PRIMA.",
                "circle-x",
                testo_informativo=(
                    "L'intera annata deve essere scartata e rigenerata."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if self.modo == 'terzetti':
            self._salva_annata_terzetti()
            return

        genere_misto = self.parent_window.checkbox_genere_misto.isChecked()

        for indice, assegnatore in enumerate(self.mesi):
            nome = self.nomi_assegnazioni[indice]
            report_completo = getattr(assegnatore, 'report_testo', None)

            self.config_app.aggiungi_assegnazione_storico(
                nome,
                assegnatore.coppie_formate,
                trio=getattr(assegnatore, 'trio_identificato', None),
                configurazione_aula=assegnatore.configurazione_aula,
                file_origine=self.file_origine,
                report_completo=report_completo,
                studente_fisso=getattr(assegnatore, 'studente_fisso', None),
                gruppo_adiacente_fisso=getattr(assegnatore, 'gruppo_adiacente_fisso', None),
                nome_adiacente_fisso=getattr(assegnatore, 'nome_adiacente_fisso', None),
                genere_misto=genere_misto,
                statistiche_generali=getattr(
                    assegnatore, 'statistiche_generali', []),
                metadati_casualita=assegnatore.esporta_metadati_casualita(),
                nome_classe=self.nome_classe,
                generazione=self.generazione,
                data_creazione=self.data_creazione,
                progressivo=self.progressivi_assegnazioni[indice],
                abbinamenti=_descrivi_abbinamenti_coppie(assegnatore),
            )

        self.accettato = True

        mostra_popup_semantico(
            self.parent_window,
            "Annata salvata nello Storico",
            "L'intera annata è stata salvata.",
            "circle-check",
            testo_informativo=(
                f"Tutte le {len(self.mesi)} assegnazioni sono state aggiunte "
                "allo Storico\n"
                f"— da «{self.nomi_assegnazioni[0]}» a "
                f"«{self.nomi_assegnazioni[-1]}».\n\n"
                "Puoi consultarle, rinominarle, esportarle o stamparle "
                "dalla tab Storico."
            ),
            messaggio_in_grassetto=True,
        )

        self._concluso = True
        self.accept()

    def _salva_annata_terzetti(self):
        """Salva nello Storico una stagione a terzetti mantenendo l’ordine dei mesi."""
        studente_fisso = None
        for s in self.parent_window.studenti:
            if getattr(s, 'nota_posizione', None) == 'FISSO':
                studente_fisso = s
                break

        genere_misto = self.parent_window.checkbox_genere_misto.isChecked()

        report_per_mese = [self._costruisci_report_mese_terzetti(i)[0]
                           for i in range(len(self.mesi))]

        for indice, mese in enumerate(self.mesi):
            nome = self.nomi_assegnazioni[indice]
            report_testo = report_per_mese[indice]
            self.config_app.aggiungi_assegnazione_storico_terzetti(
                nome,
                mese['gruppi'],
                mese['aula'],
                file_origine=self.file_origine,
                report_completo=report_testo,
                studente_fisso=studente_fisso,
                genere_misto=genere_misto,
                posizione_blocco_finale=self._posizione_blocco_finale,
                preferenza_resto2=self._preferenza_resto2,
                statistiche_generali=mese.get('statistiche_generali', []),
                metadati_casualita=mese.get('metadati_casualita'),
                nome_classe=self.nome_classe,
                generazione=self.generazione,
                data_creazione=self.data_creazione,
                progressivo=self.progressivi_assegnazioni[indice],
                abbinamenti=_descrivi_abbinamenti_terzetti(mese['gruppi']),
            )

        self.accettato = True
        self._concluso = True

        mostra_popup_semantico(
            self.parent_window,
            "Annata salvata nello Storico",
            "L'intera annata a terzetti è stata salvata.",
            "circle-check",
            testo_informativo=(
                f"Tutte le {len(self.mesi)} assegnazioni sono state aggiunte "
                "allo Storico\n"
                f"— da «{self.nomi_assegnazioni[0]}» a "
                f"«{self.nomi_assegnazioni[-1]}».\n\n"
                "Puoi consultarle, rinominarle o eliminarle dalla tab Storico."
            ),
            messaggio_in_grassetto=True,
        )
        self.accept()

    def _applica_stile(self):
        """Applica all’anteprima il tema corrente."""
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
            QFrame {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_pannello")};
            }}
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_pannello")};
            }}
        """)

# Interfaccia principale

class FinestraPostiPerfetti(QMainWindow, StatisticheMixin, StiliMixin, EsportazioneMixin, StoricoUIMixin):
    """Coordina l’interfaccia principale e i flussi dell’applicazione."""

    DEFAULT_MESI_ANNUALE = 10
    DEFAULT_POSTI_PER_FILA_COPPIE = 6
    DEFAULT_NUM_FILE_SENZA_CLASSE = 4
    DEFAULT_POSIZIONE_RESTO = {
        'coppie': 'centro',
        'terzetti': 'ultima',
    }

    def __init__(self):
        super().__init__()

        self.config_app = ConfigurazioneApp()
        self.config_app.carica_configurazione()

        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        self.studenti = []
        self.configurazione_aula = None
        self.ultimo_assegnatore = None
        self.file_origine_studenti = None

        self.modo_ultima_assegnazione = None
        self.nome_assegnazione_corrente = None
        self.progressivo_assegnazione_corrente = None
        self.data_creazione_assegnazione_corrente = None
        self.indice_assegnazione_corrente = None

        self.dati_ultima_assegnazione_terzetti = None

        self._precedenti_altro_modo = 0

        self.modalita_geometria = 'coppie'

        self.posti_insufficienti = False

        self.assegnazione_non_salvata = False

        self.timer_messaggi = QTimer()
        self.timer_messaggi.timeout.connect(self._aggiorna_messaggio_elaborazione)
        self.indice_messaggio = 0
        self.messaggi_elaborazione = [
            "Elaborazione in corso...",
            "Calcolo coppie ottimali...",
            "Verifica vincoli...",
            "Ottimizzazione assegnazione...",
            "Ricerca soluzione migliore...",
            "Elaborazione in corso..."
        ]

        self.setWindowTitle("«PostiPerfetti»")

        self.setup_ui()
        self.setup_stili()

        self._carica_dati_iniziali()

        self._aggiorna_stili_widget()

        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=1600,
            altezza_ideale=1000,
            larghezza_minima=960,
            altezza_minima=600,
            margine_larghezza=0.96,
            margine_altezza=0.90,
        )

        if self.config_app.avviso_recupero:
            QTimer.singleShot(
                0,
                self._mostra_avviso_recupero_json
            )

    def _mostra_avviso_recupero_json(self):
        """Mostra l’esito di un eventuale recupero automatico della configurazione."""
        avviso = self.config_app.avviso_recupero

        if not avviso:
            return

        titolo = avviso.get(
            "titolo",
            "Configurazione"
        )
        messaggio = avviso.get(
            "messaggio",
            "Si è verificato un problema con la configurazione."
        )
        gravita = avviso.get(
            "gravita",
            "avviso"
        )

        if gravita == "critico":
            mostra_popup_semantico(
                self,
                titolo,
                "La configurazione non è stata recuperata completamente.",
                "circle-x",
                testo_informativo=messaggio,
                messaggio_in_grassetto=True,
            )
        else:
            mostra_popup_semantico(
                self,
                titolo,
                "PostiPerfetti ha eseguito un recupero automatico.",
                "triangle-alert",
                testo_informativo=messaggio,
                messaggio_in_grassetto=True,
            )

        self.config_app.avviso_recupero = None

    def setup_ui(self):
        """Costruisce l’interfaccia principale."""

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        left_panel = self._crea_pannello_controlli()
        main_layout.addWidget(left_panel, 1)

        right_panel = self._crea_pannello_risultati()
        main_layout.addWidget(right_panel, 4)

    def _crea_pannello_controlli(self) -> QWidget:
        """Crea il pannello scorrevole con i controlli di configurazione."""

        self.scroll_pannello_sx = QScrollArea()
        self.scroll_pannello_sx.setWidgetResizable(True)

        self.scroll_pannello_sx.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_pannello_sx.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_pannello_sx.setFrameShape(QFrame.NoFrame)

        self.scroll_pannello_sx.setMinimumWidth(380)

        panel = QWidget()
        layout = QVBoxLayout(panel)

        font_pannello = QFont()
        font_pannello.setPointSize(12)
        panel.setFont(font_pannello)

        SPAZIO_TRA_BOX = 8

        layout.addStretch()
        self._crea_sezione_bottoni_superiori(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_stato_classe(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_configurazione_aula(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_gestione_dispari(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_opzioni_vincoli(layout, SPAZIO_TRA_BOX)
        self._crea_sezione_modalita(layout, SPAZIO_TRA_BOX)
        self._crea_bottone_avvia(layout)

        layout.addStretch()

        self.scroll_pannello_sx.setWidget(panel)

        return self.scroll_pannello_sx

    def _crea_sezione_bottoni_superiori(self, layout, SPAZIO_TRA_BOX):
        """Crea la barra dei comandi di servizio."""

        LARGHEZZA_BTN_TEMA = 130

        ALTEZZA_BTN = 34

        barra_bottoni = QWidget()
        barra_layout = QHBoxLayout(barra_bottoni)
        barra_layout.setContentsMargins(0, 0, 0, 0)
        barra_layout.setSpacing(8)

        self.btn_istruzioni = crea_bottone(
            "Istruzioni", C("btn_indaco_bg"), C("btn_indaco_hover"),
            tooltip="Mostra la guida completa all'uso del programma",
            font_size=13, padding="0px",
            colore_testo=C("btn_indaco_txt"),
            colore_bordo=C("btn_indaco_bordo")
        )
        self.btn_istruzioni.setFixedWidth(LARGHEZZA_BTN_TEMA)
        self.btn_istruzioni.setFixedHeight(ALTEZZA_BTN)
        applica_icona(self.btn_istruzioni, "book-open", 18)
        self.btn_istruzioni.clicked.connect(self._mostra_istruzioni)
        barra_layout.addWidget(self.btn_istruzioni)

        self.btn_toggle_tema = crea_bottone(
            "Tema chiaro", C("btn_tema_bg"), C("btn_tema_hover"),
            tooltip="Alterna tra tema scuro e tema chiaro",
            font_size=13, padding="0px",
            colore_testo=C("btn_tema_txt"),
            colore_bordo=C("btn_tema_bordo")
        )
        self.btn_toggle_tema.setFixedWidth(LARGHEZZA_BTN_TEMA)
        self.btn_toggle_tema.setFixedHeight(ALTEZZA_BTN)
        applica_icona(self.btn_toggle_tema, "sun", 18)
        self.btn_toggle_tema.clicked.connect(self._cambia_tema)
        barra_layout.addWidget(self.btn_toggle_tema)

        self.btn_crediti = QPushButton()
        self.btn_crediti.setFixedSize(ALTEZZA_BTN, ALTEZZA_BTN)
        self.btn_crediti.setToolTip("Informazioni e crediti")
        self.btn_crediti.setAccessibleName("Informazioni e crediti")
        applica_icona(self.btn_crediti, "info", 18)

        self.btn_crediti.clicked.connect(self._mostra_crediti)
        barra_layout.addWidget(self.btn_crediti)

        layout.addWidget(barra_bottoni, alignment=Qt.AlignHCenter)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_stato_classe(self, layout, SPAZIO_TRA_BOX):
        """Crea il riepilogo dello stato della classe caricata."""

        group_dati = QGroupBox("STATO CLASSE")
        layout_dati = QVBoxLayout(group_dati)
        layout_dati.setContentsMargins(9, 2, 9, 9)

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

        font_nome_classe = self.input_nome_classe.font()
        font_nome_classe.setBold(True)
        self.input_nome_classe.setFont(font_nome_classe)
        label_nome_classe = QLabel("  Nome classe:  ")
        label_nome_classe.setStyleSheet("font-size: 13px;")

        riga_nome_classe = QHBoxLayout()
        riga_nome_classe.addWidget(label_nome_classe)
        riga_nome_classe.addWidget(self.input_nome_classe)
        layout_dati.addLayout(riga_nome_classe)

        self.label_studenti_caricati = QLabel(
            "NESSUN FILE SELEZIONATO.\n\n"
            "Vai in 'Editor studenti' e clicca su 'Seleziona classe'."
        )
        self.label_studenti_caricati.setProperty("stato_classe", "neutro")
        self._applica_stile_label_stato_classe("neutro")

        self.label_studenti_caricati.setWordWrap(True)
        layout_dati.addWidget(self.label_studenti_caricati)

        layout.addWidget(group_dati)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_configurazione_aula(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per la geometria dell’aula."""

        self.group_aula = QGroupBox("CONFIGURAZIONE AULA")
        layout_aula = QVBoxLayout(self.group_aula)
        layout_aula.setContentsMargins(9, 2, 9, 9)
        layout_aula.setSpacing(6)

        riga_geometria = QHBoxLayout()
        riga_geometria.addStretch()
        self.radio_geo_coppie = QRadioButton("A coppie  ")
        self.radio_geo_coppie.setToolTip(
            "Dispone gli allievi a banchi da DUE (il modo storico del programma)."
        )
        self.radio_geo_terzetti = QRadioButton("A terzetti  ")
        self.radio_geo_terzetti.setToolTip(
            "Dispone gli allievi a banchi lunghi da TRE in fila.\n"
            "Si toccano solo 1-2 e 2-3 (gli estremi 1 e 3 non sono vicini)."
        )
        riga_geometria.addWidget(self.radio_geo_coppie)
        riga_geometria.addSpacing(12)
        riga_geometria.addWidget(self.radio_geo_terzetti)
        riga_geometria.addStretch()
        layout_aula.addLayout(riga_geometria)

        self.radio_geo_coppie.setChecked(True)
        self.radio_geo_coppie.toggled.connect(self._on_geometria_cambiata)
        self.radio_geo_terzetti.toggled.connect(self._on_geometria_cambiata)

        container_file = QWidget()
        container_file.setMaximumWidth(54)
        layout_file = QHBoxLayout(container_file)
        layout_file.setContentsMargins(0, 0, 0, 0)
        layout_file.setSpacing(4)

        self.input_num_file = QLineEdit()
        self.input_num_file.setText(str(self.DEFAULT_NUM_FILE_SENZA_CLASSE))
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

        layout_file.addWidget(self.input_num_file)

        riga_posti_fila = QHBoxLayout()
        riga_posti_fila.addStretch()
        riga_posti_fila.addWidget(QLabel("  Posti per fila:  "))
        riga_posti_fila.addSpacing(8)

        container_posti = QWidget()
        container_posti.setMaximumWidth(130)
        layout_posti = QHBoxLayout(container_posti)
        layout_posti.setContentsMargins(0, 0, 0, 0)
        layout_posti.setSpacing(4)

        self.input_posti_fila = QLineEdit()
        self.input_posti_fila.setText(str(self.DEFAULT_POSTI_PER_FILA_COPPIE))
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

        layout_posti.addWidget(self.btn_posti_meno)
        layout_posti.addWidget(self.input_posti_fila)
        layout_posti.addWidget(self.btn_posti_piu)

        riga_posti_fila.addWidget(container_posti)
        riga_posti_fila.addSpacing(14)
        riga_posti_fila.addWidget(QLabel("  File:  "))
        riga_posti_fila.addSpacing(4)
        riga_posti_fila.addWidget(container_file)
        riga_posti_fila.addStretch()
        layout_aula.addLayout(riga_posti_fila)

        riga_posti = QHBoxLayout()
        riga_posti.addStretch()
        self.label_posti_totali = QLabel("  Posti totali: 24  ")
        self.label_posti_totali.setWordWrap(True)
        riga_posti.addWidget(self.label_posti_totali)
        riga_posti.addSpacing(6)

        self.btn_aiuto_aula = QPushButton()
        applica_icona(self.btn_aiuto_aula, "circle-help", 18)
        self.btn_aiuto_aula.setFixedSize(32, 32)
        self.btn_aiuto_aula.setToolTip("Clicca per capire come contare file e posti")
        self.btn_aiuto_aula.setAccessibleName("Aiuto configurazione aula")
        self.btn_aiuto_aula.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_indaco_bg")};
                color: {C("btn_indaco_txt")};
                font-weight: bold;
                font-size: 15px;
                border-radius: 16px;
                border: 1px solid {C("btn_indaco_bordo")};
                padding: 0px;
            }}
            QPushButton:hover {{ background-color: {C("btn_indaco_hover")}; }}
        """)
        self.btn_aiuto_aula.clicked.connect(self._mostra_aiuto_configurazione_aula)
        riga_posti.addWidget(self.btn_aiuto_aula)
        riga_posti.addStretch()
        layout_aula.addLayout(riga_posti)

        layout.addWidget(self.group_aula)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _on_geometria_cambiata(self, _checked=False):
        """Aggiorna l’interfaccia quando cambia la modalità geometrica."""

        if self.radio_geo_terzetti.isChecked():
            self.modalita_geometria = 'terzetti'
        else:
            self.modalita_geometria = 'coppie'

        self._precompila_schema_per_modo()

        self._aggiorna_disponibilita_annuale()

        self._aggiorna_box_resto()

    def _aggiorna_disponibilita_annuale(self):
        """Aggiorna la disponibilità dell’assegnazione annuale per la modalità corrente."""

        if not hasattr(self, 'radio_annuale'):
            return

        if self.modalita_geometria == 'terzetti':

            self.radio_annuale.setEnabled(True)
            self.radio_annuale.setToolTip(
                "Genera in un colpo solo più mesi consecutivi, scegliendo\n"
                "internamente (best-of-N) la combinazione più pulita."
            )
        else:

            self.radio_annuale.setEnabled(True)
            self.radio_annuale.setToolTip(
                "Genera in un colpo solo più mesi consecutivi, scegliendo\n"
                "internamente (best-of-N) la combinazione più pulita."
            )

    def _crea_sezione_gestione_dispari(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per la posizione del blocco finale."""

        self.group_dispari = QGroupBox("GESTIONE NUMERO DISPARI")
        layout_dispari = QVBoxLayout(self.group_dispari)
        layout_dispari.setContentsMargins(9, 2, 9, 9)

        self.widget_composizione_resto = QWidget()
        layout_composizione = QVBoxLayout(self.widget_composizione_resto)
        layout_composizione.setContentsMargins(0, 0, 0, 0)
        self.label_composizione_resto = QLabel("I 2 allievi in più formano:")
        self.label_composizione_resto.setWordWrap(True)
        self.label_composizione_resto.setStyleSheet(f"color: {C('testo_info')}; font-size: 13px; font-style: italic;")
        layout_composizione.addWidget(self.label_composizione_resto)

        self.radio_resto_coppia = QRadioButton("1 coppia (un banco da 2)")
        self.radio_resto_coppia.setChecked(True)
        self.radio_resto_quartetti = QRadioButton("2 quartetti (due banchi da 4)")
        layout_composizione.addWidget(self.radio_resto_coppia)
        layout_composizione.addWidget(self.radio_resto_quartetti)

        self.gruppo_composizione_resto = QButtonGroup(self.widget_composizione_resto)
        self.gruppo_composizione_resto.addButton(self.radio_resto_coppia)
        self.gruppo_composizione_resto.addButton(self.radio_resto_quartetti)
        self.widget_composizione_resto.setVisible(False)
        layout_dispari.addWidget(self.widget_composizione_resto)

        self.radio_resto_coppia.toggled.connect(self._on_composizione_resto_cambiata)

        self.label_info_dispari = QLabel("Se si formerà un 'trio', il banco da 3 sarà posizionato:")
        self.label_info_dispari.setWordWrap(True)
        self.label_info_dispari.setStyleSheet(f"color: {C('testo_info')}; font-size: 13px; font-style: italic;")
        layout_dispari.addWidget(self.label_info_dispari)

        self.radio_trio_prima = QRadioButton("Davanti")
        self.radio_trio_centro = QRadioButton("In mezzo")
        self.radio_trio_centro.setChecked(True)
        self.radio_trio_ultima = QRadioButton("In fondo")

        riga_posizioni_resto = QHBoxLayout()
        riga_posizioni_resto.addWidget(self.radio_trio_prima)
        riga_posizioni_resto.addWidget(self.radio_trio_centro)
        riga_posizioni_resto.addWidget(self.radio_trio_ultima)
        riga_posizioni_resto.addStretch()
        layout_dispari.addLayout(riga_posizioni_resto)

        self.gruppo_posizione_resto = QButtonGroup(self.group_dispari)
        self.gruppo_posizione_resto.addButton(self.radio_trio_prima)
        self.gruppo_posizione_resto.addButton(self.radio_trio_centro)
        self.gruppo_posizione_resto.addButton(self.radio_trio_ultima)

        self._memoria_posizione_resto = dict(self.DEFAULT_POSIZIONE_RESTO)

        self._modo_box_resto_corrente = 'coppie'

        self.group_dispari.setVisible(False)

        layout.addWidget(self.group_dispari)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_opzioni_vincoli(self, layout, SPAZIO_TRA_BOX):
        """Crea le opzioni avanzate sui vincoli."""

        self.group_opzioni = QGroupBox("GENERE MISTO")
        layout_opzioni = QVBoxLayout(self.group_opzioni)
        layout_opzioni.setContentsMargins(9, 2, 9, 9)

        self.checkbox_genere_misto = QCheckBox("Preferisci coppie miste (M+F)")
        self.checkbox_genere_misto.setToolTip(
            "Se attivo, dà forte preferenza alle coppie miste.\n"
            "NON vieta coppie stesso genere se necessario per varietà rotazioni."
        )
        layout_opzioni.addWidget(self.checkbox_genere_misto)

        layout.addWidget(self.group_opzioni)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_sezione_modalita(self, layout, SPAZIO_TRA_BOX):
        """Crea i controlli per scegliere fra assegnazione mensile e annuale."""

        self.group_modalita = QGroupBox("MODALITÀ DI ASSEGNAZIONE")
        layout_modalita = QVBoxLayout(self.group_modalita)
        layout_modalita.setContentsMargins(9, 2, 9, 9)

        self.label_storico = QLabel("Storico: nessuna assegnazione precedente")
        self.label_storico.setWordWrap(True)
        self.label_storico.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;")
        layout_modalita.addWidget(self.label_storico)

        riga_radio = QHBoxLayout()
        self.radio_mensile = QRadioButton("Mensile (un mese)")
        self.radio_mensile.setToolTip(
            "Assegna i posti per UN solo mese: è il flusso di sempre."
        )
        self.radio_annuale = QRadioButton("Annuale (più mesi)")
        self.radio_annuale.setToolTip(
            "Genera in un colpo solo più mesi consecutivi, scegliendo\n"
            "internamente (best-of-N) la combinazione più pulita."
        )
        riga_radio.addWidget(self.radio_mensile)
        riga_radio.addWidget(self.radio_annuale)
        riga_radio.addStretch()
        layout_modalita.addLayout(riga_radio)

        self.widget_mesi_annuale = QWidget()
        riga_mesi = QHBoxLayout(self.widget_mesi_annuale)
        riga_mesi.setContentsMargins(0, 0, 0, 0)
        riga_mesi.addWidget(QLabel("Genera"))
        self.spinbox_mesi = QSpinBox()
        self.spinbox_mesi.setRange(1, 10)
        self.spinbox_mesi.setValue(self.DEFAULT_MESI_ANNUALE)
        riga_mesi.addWidget(self.spinbox_mesi)
        riga_mesi.addWidget(QLabel("mesi in coda allo Storico"))
        riga_mesi.addStretch()
        layout_modalita.addWidget(self.widget_mesi_annuale)

        self.radio_mensile.setChecked(True)
        self.widget_mesi_annuale.setVisible(False)
        self.radio_annuale.toggled.connect(self.widget_mesi_annuale.setVisible)

        layout.addWidget(self.group_modalita)
        layout.addSpacing(SPAZIO_TRA_BOX)

    def _crea_bottone_avvia(self, layout):
        """Crea il comando principale di avvio e la relativa area di stato."""

        self.btn_avvia_assegnazione = crea_bottone(
            "ASSEGNA I POSTI!", C("btn_avvia_bg"), C("btn_avvia_hover"),
            tooltip="Calcola la disposizione ottimale dei posti\n"
                    "rispettando vincoli, affinità e rotazioni precedenti",
            altezza_min=50, font_size=16, border_radius=8,
            colore_disabled_bg=C("btn_avvia_disabled_bg"),
            colore_disabled_txt=C("btn_avvia_disabled_txt"),
            colore_testo=C("btn_avvia_txt"),
            colore_bordo=C("btn_avvia_bordo"),
            colore_disabled_bordo=C("btn_avvia_disabled_bordo")
        )
        applica_icona(self.btn_avvia_assegnazione, "wand-sparkles", 20)
        self.btn_avvia_assegnazione.clicked.connect(self.avvia_assegnazione)

        self._imposta_visibilita_configurazione(False)

        layout.addWidget(self.btn_avvia_assegnazione)

        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)

        self.label_status.setWordWrap(True)
        layout.addWidget(self.label_status)

        self.btn_annulla_annuale = crea_bottone(
            "Annulla", C("btn_rosso_bg"), C("btn_rosso_hover"),
            tooltip="Interrompe la preparazione annuale.\n"
                    "L'interruzione avviene alla fine del mese in corso.",
            colore_disabled_bg=C("btn_avvia_disabled_bg")
        )
        applica_icona(self.btn_annulla_annuale, "circle-stop", 18)
        self.btn_annulla_annuale.clicked.connect(self._annulla_annuale)
        self.btn_annulla_annuale.hide()
        layout.addWidget(self.btn_annulla_annuale)

    def _crea_pannello_risultati(self) -> QWidget:
        """Crea il pannello che mostra aula, report e azioni sui risultati."""

        self.tab_widget = QTabWidget()

        self.tab_aula = QWidget()
        layout_aula = QVBoxLayout(self.tab_aula)

        self.scroll_aula = QScrollArea()
        self.widget_aula = QWidget()
        self.layout_griglia_aula = QGridLayout(self.widget_aula)
        self.scroll_aula.setWidget(self.widget_aula)
        self.scroll_aula.setWidgetResizable(True)
        layout_aula.addWidget(self.scroll_aula)

        controls_export = QHBoxLayout()

        self.btn_salva_progetto = crea_bottone(
            "Salva assegnazione", C("btn_salva_bg"), C("btn_salva_hover"),
            tooltip="Salva l'assegnazione nello Storico.\n"
                    "Indispensabile per le rotazioni future!",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_salva_txt"),
            colore_bordo=C("btn_salva_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_salva_progetto, "save", 18)
        self.btn_salva_progetto.clicked.connect(self.salva_assegnazione)
        self.btn_salva_progetto.setEnabled(False)
        controls_export.addWidget(self.btn_salva_progetto)

        self.btn_export_excel = crea_bottone(
            "Esporta Excel", C("btn_excel_bg"), C("btn_excel_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'export.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_excel_txt"),
            colore_bordo=C("btn_excel_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_export_excel, "table-2", 18)
        self.btn_export_excel.clicked.connect(self.esporta_excel)
        self.btn_export_excel.setEnabled(False)
        controls_export.addWidget(self.btn_export_excel)

        self.btn_export_report_txt = crea_bottone(
            "Esporta Report", C("btn_export_bg"), C("btn_export_hover"),
            tooltip="Salva prima l'assegnazione nello Storico per abilitare l'export.",
            altezza_min=45,
            colore_disabled_bg=C("btn_azione_disabled_bg"),
            colore_disabled_txt=C("btn_azione_disabled_txt"),
            colore_testo=C("btn_export_txt"),
            colore_bordo=C("btn_export_bordo"),
            colore_disabled_bordo=C("btn_azione_disabled_bordo")
        )
        applica_icona(self.btn_export_report_txt, "file-down", 18)
        self.btn_export_report_txt.clicked.connect(self.esporta_report_txt)
        self.btn_export_report_txt.setEnabled(False)
        controls_export.addWidget(self.btn_export_report_txt)

        controls_export.addStretch()
        layout_aula.addLayout(controls_export)

        self.editor_studenti = EditorStudentiWidget()
        indice_editor = self.tab_widget.addTab(
            self.editor_studenti, "Editor studenti"
        )
        applica_icona_tab(
            self.tab_widget, indice_editor, "notebook-pen", 20
        )

        indice_aula = self.tab_widget.addTab(self.tab_aula, "Aula")
        applica_icona_tab(
            self.tab_widget, indice_aula, "school", 20
        )

        self.tab_report = QWidget()
        layout_report = QVBoxLayout(self.tab_report)

        self.text_report = QTextEdit()
        self.text_report.setReadOnly(True)

        font_report = QFont()
        font_report.setFamily("Consolas")
        font_report.setPointSize(9)
        font_report.setStyleHint(QFont.Monospace)
        self.text_report.setFont(font_report)
        layout_report.addWidget(self.text_report)

        self.widget_hint_report = QWidget()
        layout_hint_report = QHBoxLayout(self.widget_hint_report)
        layout_hint_report.setContentsMargins(6, 4, 6, 4)
        layout_hint_report.setSpacing(8)
        layout_hint_report.addStretch()

        self.icona_hint_report = QLabel()
        self.icona_hint_report.setFixedSize(22, 22)
        self.icona_hint_report.setAlignment(Qt.AlignCenter)
        applica_icona_etichetta(self.icona_hint_report, "info", 18)
        layout_hint_report.addWidget(self.icona_hint_report)

        self.label_hint_report = QLabel(
            "Per esportare il Report in formato .txt, vai nella tab Aula."
        )
        self.label_hint_report.setAlignment(Qt.AlignCenter)
        self.label_hint_report.setStyleSheet(
            f'color: {C("testo_secondario")}; font-size: 14px; '
            f'font-style: italic; padding: 6px;'
        )
        layout_hint_report.addWidget(self.label_hint_report)
        layout_hint_report.addStretch()

        self.widget_hint_report.setVisible(False)
        layout_report.addWidget(self.widget_hint_report)

        indice_report = self.tab_widget.addTab(self.tab_report, "Report")
        applica_icona_tab(
            self.tab_widget, indice_report, "file-text", 20
        )

        self.tab_storico = QWidget()
        layout_storico = QVBoxLayout(self.tab_storico)

        self.label_storico_vuoto = QLabel(
            "NESSUNA ASSEGNAZIONE SALVATA.\n\n"
            "Esegui almeno un'assegnazione e salvala\n"
            "per visualizzare lo Storico."
        )
        self.label_storico_vuoto.setAlignment(Qt.AlignCenter)
        self.label_storico_vuoto.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
        )
        layout_storico.addWidget(self.label_storico_vuoto)

        self.tabella_storico = QTableWidget()

        self.tabella_storico.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tabella_storico.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tabella_storico.setColumnCount(4)
        self.tabella_storico.setHorizontalHeaderLabels(["Data creazione", "Nome", "Abbinamenti", "Azioni"])

        self.tabella_storico.cellChanged.connect(self._on_storico_nome_modificato)
        layout_storico.addWidget(self.tabella_storico)

        indice_storico = self.tab_widget.addTab(
            self.tab_storico, "Storico"
        )
        applica_icona_tab(
            self.tab_widget, indice_storico, "history", 20
        )

        self.tab_statistiche = QWidget()
        layout_statistiche = QVBoxLayout(self.tab_statistiche)

        header_stats = QHBoxLayout()

        label_filtro = QLabel("Visualizza statistiche per:")
        label_filtro.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_stats.addWidget(label_filtro)

        self.filtro_classe_combo = ComboBoxProtetto()
        self.filtro_classe_combo.setMinimumWidth(400)

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

        scroll_stats = QScrollArea()
        scroll_stats.setWidgetResizable(True)

        self.widget_statistiche = QWidget()
        self.layout_statistiche_content = QVBoxLayout(self.widget_statistiche)

        scroll_stats.setWidget(self.widget_statistiche)
        layout_statistiche.addWidget(scroll_stats)

        self.btn_export_stats = crea_bottone(
            "Esporta le Statistiche (.txt)",
            C("btn_statistiche_export_bg"),
            C("btn_statistiche_export_hover"),
            tooltip="Salva le statistiche dettagliate in un file di testo",
            altezza_min=45,
            font_size=14,
            colore_testo=C("btn_statistiche_export_txt"),
            colore_bordo=C("btn_statistiche_export_bordo"),
        )
        applica_icona(self.btn_export_stats, "file-down", 18)
        self.btn_export_stats.clicked.connect(self._esporta_statistiche_txt)
        layout_statistiche.addWidget(self.btn_export_stats)

        indice_statistiche = self.tab_widget.addTab(
            self.tab_statistiche, "Statistiche"
        )
        applica_icona_tab(
            self.tab_widget, indice_statistiche, "chart-column", 20
        )

        self.tab_widget.setTabToolTip(0, "Modifica genere, posizione e vincoli degli studenti")
        self.tab_widget.setTabToolTip(1, "Visualizza la disposizione grafica dei banchi nell'aula")
        self.tab_widget.setTabToolTip(2, "Leggi il report dettagliato dell'assegnazione")
        self.tab_widget.setTabToolTip(3, "Consulta e gestisci lo storico delle assegnazioni passate")
        self.tab_widget.setTabToolTip(4, "Analizza le statistiche sulle coppie e le rotazioni")

        self.tab_widget.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        self.editor_studenti.file_cambiato_signal.connect(self._on_editor_file_cambiato)

        self.editor_studenti.dati_modificati_signal.connect(self._on_editor_dati_modificati)

        self.editor_studenti.genere_cambiato_signal.connect(self._on_editor_genere_cambiato)

        self.editor_studenti.file_chiuso_signal.connect(self._on_editor_file_chiuso)

        self.editor_studenti.file_salvato_signal.connect(self._on_editor_file_salvato)

        self.editor_studenti._callback_pre_caricamento = self._verifica_prima_di_caricare
        self.editor_studenti._callback_pre_chiusura_file = self._verifica_prima_di_chiudere_file

        return self.tab_widget

    def _mostra_istruzioni(self):
        """Apre la guida dell’applicazione."""
        mostra_istruzioni(self)

    def _carica_dati_iniziali(self):
        """Carica tema e stato persistente necessari all’avvio."""

        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        if tema_salvato == "chiaro":
            self.btn_toggle_tema.setText("Tema scuro")
            applica_icona(self.btn_toggle_tema, "moon", 18)
        else:
            self.btn_toggle_tema.setText("Tema chiaro")
            applica_icona(self.btn_toggle_tema, "sun", 18)

        self.setup_stili()

        aggiorna_icone_applicazione()

        self._ripristina_default_operativi()

        self._aggiorna_info_storico()

        self._aggiorna_posti_totali()

        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        self._aggiorna_tabella_storico()

    def _aggiorna_posti_totali(self):
        """Ricalcola capienza e informazioni sulla geometria corrente."""
        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())

        dettaglio_geometria = None

        if getattr(self, 'modalita_geometria', 'coppie') == 'terzetti' and self.studenti:
            P = max(1, posti_per_fila // 3)
            num_fissi = sum(1 for s in self.studenti if s.nota_posizione == 'FISSO')

            due_quartetti = (hasattr(self, 'radio_resto_quartetti')
                             and self.radio_resto_quartetti.isChecked())
            try:

                per_fila = self._terzetti_posti_per_fila(
                    len(self.studenti), P, num_fissi > 0, due_quartetti)
                posti_totali = sum(per_fila)
                if per_fila:

                    dettaglio_geometria = " + ".join(str(x) for x in per_fila)
            except Exception:
                posti_totali = num_file * posti_per_fila
        else:

            posti_totali = num_file * posti_per_fila

        self.label_posti_totali.setText(f"  Posti totali: {posti_totali}  ")
        self._applica_stile_label_capienza("neutro")

        if self.studenti:
            num_studenti = len(self.studenti)
            if num_studenti > posti_totali:

                self._applica_stile_label_capienza("errore")
                self.label_posti_totali.setText(f"POSTI INSUFFICIENTI!\nServono: {num_studenti} | Disponibili: {posti_totali}")

                self.posti_insufficienti = True
            elif num_studenti < posti_totali:

                self._applica_stile_label_capienza("neutro")
                posti_liberi = posti_totali - num_studenti

                riga_dettaglio = f"\n({dettaglio_geometria} posti)" if dettaglio_geometria else ""
                self.label_posti_totali.setText(
                    f"Posti totali: {posti_totali}{riga_dettaglio}\n"
                    f"{posti_liberi} post{'o vuoto' if posti_liberi == 1 else 'i vuoti'} sar{'à tolto' if posti_liberi == 1 else 'anno tolti'}"
                )

                self.posti_insufficienti = False
            else:

                self._applica_stile_label_capienza("neutro")

                if dettaglio_geometria:
                    posti_nominali = num_file * posti_per_fila
                    if posti_nominali > posti_totali:
                        differenza = posti_nominali - posti_totali
                        self.label_posti_totali.setText(
                            f"{dettaglio_geometria} = {posti_totali} posti\n"
                            f"{differenza} post{'o vuoto' if differenza == 1 else 'i vuoti'} "
                            f"sar{'à tolto' if differenza == 1 else 'anno tolti'}"
                        )
                    elif posti_nominali < posti_totali:
                        differenza = posti_totali - posti_nominali
                        self.label_posti_totali.setText(
                            f"{dettaglio_geometria} = {posti_totali} posti\n"
                            f"{differenza} post{'o' if differenza == 1 else 'i'} "
                            f"sar{'à aggiunto' if differenza == 1 else 'anno aggiunti'}"
                        )
                    else:
                        self.label_posti_totali.setText(
                            f"{dettaglio_geometria} = {posti_totali} posti (PERFETTO!)"
                        )
                else:
                    self.label_posti_totali.setText(f"Posti totali: {posti_totali} (PERFETTO!)")

                self.posti_insufficienti = False

    def _cambia_posti_fila(self, delta):
        """Modifica il numero di posti per fila entro i limiti della modalità."""
        valore_attuale = int(self.input_posti_fila.text())

        if self.modalita_geometria == 'terzetti':
            passo, minimo, massimo = 3, 6, 9
        else:
            passo, minimo, massimo = 2, 4, 10

        direzione = 1 if delta > 0 else -1
        nuovo_valore = valore_attuale + direzione * passo

        if minimo <= nuovo_valore <= massimo:
            self.input_posti_fila.setText(str(nuovo_valore))

            self._aggiorna_stato_bottoni_posti()
            self._aggiorna_posti_totali()

            self._aggiorna_box_resto()

    def _aggiorna_stato_bottoni_posti(self):
        """Abilita o disabilita i comandi per cambiare i posti per fila."""
        valore = int(self.input_posti_fila.text())
        if self.modalita_geometria == 'terzetti':
            self.btn_posti_meno.setEnabled(valore > 6)
            self.btn_posti_piu.setEnabled(valore < 9)
        else:
            self.btn_posti_meno.setEnabled(valore > 4)
            self.btn_posti_piu.setEnabled(valore < 10)

    def _precompila_schema_per_modo(self):
        """Imposta i valori iniziali della geometria per la modalità selezionata."""
        if self.modalita_geometria == 'terzetti':

            self.input_posti_fila.setText("9")

            if self.studenti:
                file_necessarie = max(1, min(math.ceil(len(self.studenti) / 9), 6))
            else:
                file_necessarie = 3
            self.input_num_file.setText(str(file_necessarie))

            self._aggiorna_stato_bottoni_posti()

            self._aggiorna_posti_totali()
        else:

            self.btn_posti_meno.setEnabled(True)
            self.btn_posti_piu.setEnabled(True)
            self._auto_calcola_layout_aula()

    def _aggiorna_box_resto(self):
        """Aggiorna composizione, posizione e visibilità del blocco finale."""
        if not hasattr(self, 'group_dispari'):
            return

        if not self.studenti:
            self.group_dispari.setVisible(False)
            return

        n = len(self.studenti)
        num_fissi = sum(1 for s in self.studenti if s.nota_posizione == 'FISSO')

        if self.modalita_geometria != self._modo_box_resto_corrente:

            if self.radio_trio_prima.isChecked():
                posizione_attuale = 'prima'
            elif self.radio_trio_centro.isChecked():
                posizione_attuale = 'centro'
            else:
                posizione_attuale = 'ultima'
            self._memoria_posizione_resto[self._modo_box_resto_corrente] = \
                posizione_attuale

            ricordata = self._memoria_posizione_resto[self.modalita_geometria]
            if ricordata == 'prima':
                self.radio_trio_prima.setChecked(True)
            elif ricordata == 'centro':
                self.radio_trio_centro.setChecked(True)
            else:
                self.radio_trio_ultima.setChecked(True)

            self._modo_box_resto_corrente = self.modalita_geometria

        if self.modalita_geometria == 'terzetti':
            self._aggiorna_box_resto_terzetti(n, num_fissi > 0)
        else:
            self._aggiorna_box_resto_coppie(n, num_fissi)

    def _aggiorna_box_resto_coppie(self, n, num_fissi):
        """Aggiorna il blocco finale della modalità a coppie."""
        self.group_dispari.setTitle("GESTIONE NUMERO DISPARI")

        self.widget_composizione_resto.setVisible(False)

        posti = max(2, int(self.input_posti_fila.text()))
        self.input_num_file.setText(str(max(1, math.ceil(n / posti))))
        self._aggiorna_posti_totali()

        num_rimanenti = n - num_fissi
        if num_rimanenti % 2 == 1:
            self.group_dispari.setVisible(True)
            if num_fissi > 0:
                info = (f"Con {n} studenti ({num_fissi} 'FISSO', "
                        f"{num_rimanenti} rimanenti dispari), il banco da 3 sarà posizionato:")
            else:
                info = f"Con {n} studenti, il banco da 3 sarà posizionato:"

            self._mostra_posizioni_resto(True, True, True, info)
        else:
            self.group_dispari.setVisible(False)

    def _aggiorna_box_resto_terzetti(self, n, ha_fisso):
        """Aggiorna il blocco finale della modalità a terzetti."""
        self.group_dispari.setTitle("GESTIONE DEL RESTO")
        P = max(1, int(self.input_posti_fila.text()) // 3)
        resto = n % 3

        composizione_possibile = (resto == 2 and n >= 8)
        mostra_composizione = False
        if composizione_possibile:
            _, minf_coppia = self._terzetti_righe_e_minfila(n, P, ha_fisso, False)
            _, minf_quart  = self._terzetti_righe_e_minfila(n, P, ha_fisso, True)
            mostra_composizione = (minf_quart > minf_coppia)
        self.widget_composizione_resto.setVisible(mostra_composizione)

        if not mostra_composizione and self.radio_resto_quartetti.isChecked():
            self.radio_resto_coppia.blockSignals(True)
            self.radio_resto_quartetti.blockSignals(True)
            self.radio_resto_coppia.setChecked(True)
            self.radio_resto_coppia.blockSignals(False)
            self.radio_resto_quartetti.blockSignals(False)

        usa_due_quartetti = mostra_composizione and self.radio_resto_quartetti.isChecked()

        righe, _ = self._terzetti_righe_e_minfila(n, P, ha_fisso, usa_due_quartetti)
        self.input_num_file.setText(str(righe))
        self._aggiorna_posti_totali()

        if resto == 0:

            self.group_dispari.setVisible(False)
            return

        self.group_dispari.setVisible(True)
        if usa_due_quartetti:
            self._posizioni_due_quartetti(n, ha_fisso, righe)
        else:
            self._posizioni_blocco_singolo(n, ha_fisso, resto, righe)

    def _terzetti_righe_e_minfila(self, n, P, ha_fisso, due_quartetti):
        """Calcola numero di file e capienza minima della geometria a terzetti."""
        pref = 'due_quartetti' if due_quartetti else 'coppia'
        cfg = ConfigurazioneAula()
        cfg.crea_layout_terzetti(n, terzetti_per_fila=P, posizione_blocco_finale='ultima',
                                 ha_fisso=ha_fisso, preferenza_resto2=pref)

        per_fila = []
        for ri, riga in enumerate(cfg.griglia):
            if ri < 2:
                continue
            nb = sum(1 for p in riga
                     if p is not None and getattr(p, 'tipo', None) == 'banco')
            if nb > 0:
                per_fila.append(nb)
        righe = len(per_fila)
        min_fila = min(per_fila) if per_fila else 0
        return righe, min_fila

    def _terzetti_posti_per_fila(self, n, P, ha_fisso, due_quartetti):
        """Restituisce i posti effettivi presenti in ciascuna fila a terzetti."""
        pref = 'due_quartetti' if due_quartetti else 'coppia'
        cfg = ConfigurazioneAula()
        cfg.crea_layout_terzetti(n, terzetti_per_fila=P,
                                 posizione_blocco_finale='ultima',
                                 ha_fisso=ha_fisso, preferenza_resto2=pref)

        per_fila = []
        for ri, riga in enumerate(cfg.griglia):
            if ri < 2:
                continue
            nb = sum(1 for p in riga
                     if p is not None and getattr(p, 'tipo', None) == 'banco')
            if nb > 0:
                per_fila.append(nb)
        return per_fila

    def _posizioni_blocco_singolo(self, n, ha_fisso, resto, righe):
        """Restituisce le posizioni ammesse per un singolo blocco finale."""
        nome_banco = "banco da 4" if resto == 1 else "banco da 2"
        k = (n // 3 - 1) if resto == 1 else (n // 3)
        fisso_nel_resto = ha_fisso and k == 0
        if fisso_nel_resto:
            self._mostra_posizioni_resto(False, False, False,
                f"Il FISSO siede nel {nome_banco}, che va in prima fila.")
        elif ha_fisso:
            if righe <= 2:
                self._mostra_posizioni_resto(False, False, False,
                    f"Con il FISSO in prima fila, il {nome_banco} va nella 2ª fila.")
            else:
                self._mostra_posizioni_resto(False, True, True,
                    f"Il {nome_banco} sarà posizionato:")
        else:
            if righe <= 1:
                self._mostra_posizioni_resto(False, False, False,
                    f"Con una sola fila di banchi, il {nome_banco} va in quell'unica fila.")
            elif righe == 2:
                self._mostra_posizioni_resto(True, False, True,
                    f"Il {nome_banco} sarà posizionato:")
            else:
                self._mostra_posizioni_resto(True, True, True,
                    f"Il {nome_banco} sarà posizionato:")

    def _posizioni_due_quartetti(self, n, ha_fisso, righe):
        """Restituisce le posizioni ammesse per due quartetti finali."""
        k = (n - 8) // 3
        fisso_nel_resto = ha_fisso and k == 0
        if fisso_nel_resto:
            self._mostra_posizioni_resto(False, False, False,
                "I 2 quartetti occupano la colonna sinistra delle prime due "
                "file (il FISSO siede nel primo).")
        elif ha_fisso:
            if righe <= 3:
                self._mostra_posizioni_resto(False, False, False,
                    "Con il FISSO in prima fila, i 2 quartetti vanno nella "
                    "colonna sinistra di 2ª e 3ª fila.")
            else:
                self._mostra_posizioni_resto(False, True, True,
                    "I 2 quartetti saranno posizionati:")
        else:
            if righe <= 2:
                self._mostra_posizioni_resto(False, False, False,
                    "I 2 quartetti vanno nella colonna sinistra di entrambe le file.")
            elif righe == 3:
                self._mostra_posizioni_resto(True, False, True,
                    "I 2 quartetti saranno posizionati:")
            else:
                self._mostra_posizioni_resto(True, True, True,
                    "I 2 quartetti saranno posizionati:")

    def _mostra_posizioni_resto(self, mostra_davanti, mostra_in_mezzo,
                                 mostra_in_fondo, info_testo):
        """Mostra le posizioni ammesse e mantiene valida la selezione corrente."""
        self.label_info_dispari.setText(info_testo)
        self.radio_trio_prima.setVisible(mostra_davanti)
        self.radio_trio_centro.setVisible(mostra_in_mezzo)
        self.radio_trio_ultima.setVisible(mostra_in_fondo)

        spuntata_visibile = (
            (self.radio_trio_prima.isChecked() and mostra_davanti) or
            (self.radio_trio_centro.isChecked() and mostra_in_mezzo) or
            (self.radio_trio_ultima.isChecked() and mostra_in_fondo)
        )
        if not spuntata_visibile:

            self.radio_trio_ultima.setChecked(True)

    def _on_composizione_resto_cambiata(self, _checked=False):
        """Aggiorna la geometria quando cambia la composizione del blocco finale."""
        self._aggiorna_box_resto()

    def _forza_ridisegno_aula(self):
        """Completa subito il ridisegno della superficie Aula.

        I popup riepilogativi sono modali: senza un repaint sincrono, il viewport
        della QScrollArea può conservare per qualche istante i pixel della
        geometria precedente, soprattutto passando da coppie a terzetti. Il
        metodo aggiorna layout, widget e viewport prima di aprire il popup, senza
        accettare input dell’utente durante il breve ciclo di eventi.
        """
        self.layout_griglia_aula.invalidate()
        self.layout_griglia_aula.activate()
        self.widget_aula.updateGeometry()
        self.widget_aula.repaint()

        scroll_aula = getattr(self, "scroll_aula", None)
        if scroll_aula is not None:
            scroll_aula.viewport().repaint()
            scroll_aula.repaint()

        self.tab_aula.repaint()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        )

    def _resetta_tab_aula_report(self):
        """Rimuove dall’interfaccia l’assegnazione corrente."""

        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            widget = child.widget()
            if widget is not None:
                # setParent(None) rimuove subito il widget dalla superficie visibile;
                # deleteLater() ne completa poi la distruzione in sicurezza.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        self.text_report.clear()

        self.widget_hint_report.setVisible(False)

        self.btn_salva_progetto.setEnabled(False)
        self.btn_salva_progetto.setToolTip(
            "Disponibile dopo aver generato un'assegnazione."
        )
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "Disponibile dopo aver salvato un'assegnazione."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "Disponibile dopo aver salvato un'assegnazione."
        )

        self.ultimo_assegnatore = None

        self.dati_ultima_assegnazione_terzetti = None

        self.modo_ultima_assegnazione = None
        self.nome_assegnazione_corrente = None
        self.progressivo_assegnazione_corrente = None
        self.data_creazione_assegnazione_corrente = None
        self.indice_assegnazione_corrente = None

        self.configurazione_aula = None

        self._precedenti_altro_modo = 0
        self._statistiche_generali_terzetti_correnti = []

        self.assegnazione_non_salvata = False

        # La superficie vuota deve diventare visibile prima che inizi una nuova
        # elaborazione sincrona, altrimenti il viewport può mantenere il vecchio
        # fotogramma fino alla chiusura del popup successivo.
        self._forza_ridisegno_aula()

    def _verifica_assegnazione_prima_di_abbandonare(
        self,
        *,
        testo_azione: str,
        etichetta_distruttiva: str,
    ) -> bool:
        """Chiede come gestire un’assegnazione non salvata prima di abbandonarla."""
        if not self.assegnazione_non_salvata:
            return True

        dialog = crea_popup_semantico(
            self,
            "Assegnazione non salvata",
            "L'ultima assegnazione non è stata salvata nello Storico.",
            "triangle-alert",
            testo_informativo=(
                f"Se {testo_azione}, le vicinanze formate non verranno "
                "considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?"
            ),
            messaggio_in_grassetto=True,
        )

        btn_salva = dialog.addButton(
            "Salva assegnazione", QMessageBox.AcceptRole
        )
        btn_prosegui = dialog.addButton(
            etichetta_distruttiva, QMessageBox.DestructiveRole
        )
        btn_annulla = dialog.addButton(
            "Annulla", QMessageBox.RejectRole
        )
        applica_icona(btn_salva, "save", 18)
        applica_icona(btn_prosegui, "trash-2", 18)
        applica_stile_pulsante_popup(btn_prosegui, "distruttivo")
        applica_icona(btn_annulla, "x", 18)

        dialog.setDefaultButton(btn_salva)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()

        bottone = dialog.clickedButton()
        if bottone == btn_annulla:
            return False

        if bottone == btn_salva:
            self.salva_assegnazione()

            return not self.assegnazione_non_salvata

        return True

    def _verifica_prima_di_caricare(self) -> bool:
        """Protegge l’assegnazione corrente prima di caricare un altro file."""
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="selezioni una nuova classe adesso",
            etichetta_distruttiva="Prosegui senza salvare",
        )

    def _verifica_prima_di_chiudere_file(self) -> bool:
        """Protegge l’assegnazione corrente prima di chiudere il file."""
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="chiudi il file adesso",
            etichetta_distruttiva="Chiudi senza salvare",
        )

    def _reset_modalita_mensile(self):
        """Ripristina la modalità mensile."""
        if hasattr(self, 'radio_mensile'):
            self.radio_mensile.setChecked(True)
        if hasattr(self, 'spinbox_mesi'):
            self.spinbox_mesi.setValue(self.DEFAULT_MESI_ANNUALE)
        if hasattr(self, 'widget_mesi_annuale'):
            self.widget_mesi_annuale.setVisible(False)

    def _reset_modalita_geometria(self):
        """Ripristina la geometria e le scelte del blocco finale."""
        self.modalita_geometria = 'coppie'

        if hasattr(self, 'radio_geo_coppie'):
            self.radio_geo_coppie.blockSignals(True)
            self.radio_geo_terzetti.blockSignals(True)
            self.radio_geo_coppie.setChecked(True)
            self.radio_geo_coppie.blockSignals(False)
            self.radio_geo_terzetti.blockSignals(False)
            self._aggiorna_disponibilita_annuale()

        self._memoria_posizione_resto = dict(self.DEFAULT_POSIZIONE_RESTO)
        self._modo_box_resto_corrente = 'coppie'

        if hasattr(self, 'radio_resto_coppia'):
            self.radio_resto_coppia.setChecked(True)
        if hasattr(self, 'radio_trio_centro'):
            self.radio_trio_centro.setChecked(True)

    def _ripristina_default_operativi(self):
        """Ripristina i valori operativi iniziali per una nuova classe."""
        self._reset_modalita_mensile()
        self._reset_modalita_geometria()

        if hasattr(self, 'checkbox_genere_misto'):
            self.checkbox_genere_misto.setChecked(False)

        if hasattr(self, 'input_posti_fila'):
            self.input_posti_fila.setText(
                str(self.DEFAULT_POSTI_PER_FILA_COPPIE)
            )

        if self.studenti:
            self._auto_calcola_layout_aula()
        else:
            self.input_num_file.setText(
                str(self.DEFAULT_NUM_FILE_SENZA_CLASSE)
            )
            self._aggiorna_stato_bottoni_posti()
            self._aggiorna_posti_totali()

        self._aggiorna_box_resto()

    def _imposta_visibilita_configurazione(self, attivo: bool):
        """Mostra o nasconde i controlli disponibili nello stato corrente."""
        for widget in (self.group_aula, self.group_opzioni, self.group_modalita,
                       self.btn_avvia_assegnazione):
            widget.setVisible(attivo)
            widget.setEnabled(attivo)

    def _on_editor_file_cambiato(self):
        """Aggiorna la finestra principale quando l’Editor carica un file."""

        self.studenti = []
        self.file_origine_studenti = None

        self._ripristina_default_operativi()

        self._resetta_tab_aula_report()

        self.input_nome_classe.clear()

        self._imposta_visibilita_configurazione(False)

        if (self.editor_studenti.ha_studenti_caricati() and
                not self.editor_studenti.tutti_generi_impostati()):

            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"NUOVA CLASSE PRESENTE NELL'EDITOR!\n\n"
                f"MODIFICHE NECESSARIE: {len(mancanti)} gener{'e' if len(mancanti) == 1 else 'i'} da impostare)"
            )
        else:

            self.label_studenti_caricati.setText(
                "NUOVA CLASSE PRESENTE NELL'EDITOR!\n\n"
                "Clicca 'SALVA e CARICA' per abilitare l'assegnazione."
            )
        self._applica_stile_label_stato_classe("attenzione")

        self.assegnazione_non_salvata = False

        print("🔄 L'Editor ha caricato un nuovo file → dati pannello resettati")

        self.tab_widget.setCurrentIndex(0)

    def _on_editor_dati_modificati(self):
        """Aggiorna lo stato della classe dopo una modifica nell’Editor."""
        if not self.editor_studenti.ha_studenti_caricati():
            return

        if not self.editor_studenti.tutti_generi_impostati():
            return

        ha_vincoli_incompleti = bool(self.editor_studenti.get_vincoli_incompleti())
        ha_modifiche_non_salvate = self.editor_studenti._modifiche_non_salvate

        if ha_vincoli_incompleti or ha_modifiche_non_salvate:

            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"'{nome_file}' modificato nell'Editor!\n\n"
                f"Clicca 'SALVA e CARICA' per aggiornare."
            )
            self._applica_stile_label_stato_classe("attenzione")
        else:

            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"File '{nome_file}.txt' salvato e caricato\n\n"
                f"Pronto per l'ASSEGNAZIONE!"
            )
            self._applica_stile_label_stato_classe("successo")

    def _on_editor_genere_cambiato(self):
        """Aggiorna lo stato dei generi dopo una modifica nell’Editor."""
        if not self.editor_studenti.ha_studenti_caricati():
            return

        if self.editor_studenti.tutti_generi_impostati():

            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"'{nome_file}' pronto!\n\n"
                f"Clicca 'SALVA e CARICA' per procedere."
            )
            self._applica_stile_label_stato_classe("attenzione")
        else:

            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"Genere da completare ({len(mancanti)} rimast{'o' if len(mancanti) == 1 else 'i'})"
            )
            self._applica_stile_label_stato_classe("attenzione")

    def _on_editor_file_chiuso(self):
        """Azzera lo stato della classe quando l’Editor chiude il file."""

        self.studenti = []
        self.file_origine_studenti = None

        self._ripristina_default_operativi()

        self._resetta_tab_aula_report()

        self.input_nome_classe.clear()

        self._imposta_visibilita_configurazione(False)

        self.label_studenti_caricati.setText(
            "NESSUN FILE CARICATO.\n\n"
            "Vai in 'Editor studenti' e clicca su 'Seleziona classe'.\n"
        )
        self._applica_stile_label_stato_classe("neutro")

        self.assegnazione_non_salvata = False

    def _on_editor_file_salvato(self, percorso_file: str):
        """Carica nella finestra principale il file salvato dall’Editor."""

        self._carica_studenti_da_editor(percorso_file)

        nome_file = os.path.basename(percorso_file)
        self.label_studenti_caricati.setText(
            f"File '{nome_file}' salvato e caricato\n\n"
            f"Pronto per l'ASSEGNAZIONE!"
        )
        self._applica_stile_label_stato_classe("successo")

        self.label_status.setText("Classe pronta per l'assegnazione!")
        self.label_status.setStyleSheet(f"color: {C('testo_stato_ok')}; font-weight: bold;")
        QTimer.singleShot(10000, lambda: (
            self.label_status.setText("")
            if not self.timer_messaggi.isActive()
            else None
        ))

    def _carica_studenti_da_editor(self, file_path: str):
        """Crea gli oggetti Student dai dati già validati dall’Editor."""

        self._resetta_tab_aula_report()

        dati_studenti = self.editor_studenti.get_dati_tutti_studenti()

        if not dati_studenti:
            self._mostra_errore("File vuoto", "Il file selezionato non contiene studenti validi.")
            return

        studenti = []
        for dati in dati_studenti:

            studente = Student(
                cognome=dati["cognome"],
                nome=dati["nome"],
                sesso=dati["sesso"],
                nota_posizione=dati["posizione"]
            )

            for nome_completo, livello in dati["incompatibilita"].items():

                studente.aggiungi_incompatibilita(nome_completo, livello)

            for nome_completo, livello in dati["affinita"].items():
                studente.aggiungi_affinita(nome_completo, livello)

            studenti.append(studente)

        self._auto_salva_file_corretto()

        self.studenti = studenti
        self.file_origine_studenti = Path(file_path).name
        num_studenti = len(studenti)

        self.label_studenti_caricati.setText(
            f"Caricati {num_studenti} studenti da '{Path(file_path).name}'"
        )
        self._applica_stile_label_stato_classe("successo")

        self._imposta_visibilita_configurazione(True)

        self._ripristina_default_operativi()

        nome_file = Path(file_path).stem.replace("_", " ").title()

        self.input_nome_classe.setText(nome_file)

        self._controlla_classe_gia_elaborata(nome_file)

        self._aggiorna_posti_totali()

        self._aggiorna_info_storico()

        self.tab_widget.setCurrentIndex(0)

    def _auto_salva_file_corretto(self):
        """Salva le correzioni applicate dall’Editor senza bloccare i dati già caricati."""

        if not self.editor_studenti._correzioni_applicate:

            self.editor_studenti._modifiche_non_salvate = False
            return

        percorso = self.editor_studenti._percorso_file_caricato

        if not percorso:

            print("⚠️ Auto-save: nessun percorso file disponibile")
            return

        try:

            contenuto_corretto = self.editor_studenti._genera_txt()

            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(contenuto_corretto)

            self.editor_studenti._modifiche_non_salvate = False
            self.editor_studenti._correzioni_applicate = False

            nome_file = Path(percorso).name
            mostra_popup_semantico(
                self,
                "File salvato e pronto all'uso",
                "Il file è stato automaticamente salvato e caricato.",
                "circle-check",
                testo_informativo=(
                    f"File: {nome_file}\n"
                    f"Percorso: {percorso}\n\n"
                    "L'intera lista degli studenti è pronta per "
                    "l'assegnazione."
                ),
                messaggio_in_grassetto=True,
            )

            print(f"💾 Auto-save: file corretto salvato in '{percorso}'")

        except PermissionError:

            mostra_popup_semantico(
                self,
                "Salvataggio automatico non riuscito",
                "Il file non può essere sovrascritto.",
                "triangle-alert",
                testo_informativo=(
                    f"Il file potrebbe essere protetto:\n{percorso}\n\n"
                    "Le correzioni sono comunque attive per l'assegnazione "
                    "corrente. Puoi salvare manualmente dalla tab Editor "
                    "studenti usando «Preview file classe (.txt)»."
                ),
                messaggio_in_grassetto=True,
            )

        except Exception as e:

            print(f"⚠️ Auto-save fallito: {e}")
            mostra_popup_semantico(
                self,
                "Salvataggio automatico non riuscito",
                "Si è verificato un errore durante il salvataggio automatico.",
                "triangle-alert",
                testo_informativo=(
                    f"Errore: {e}\n\n"
                    "Le correzioni sono comunque attive per l'assegnazione "
                    "corrente."
                ),
                messaggio_in_grassetto=True,
            )

    def _on_stato_annuale(self, stato: dict):
        """Memorizza lo stato corrente comunicato dal worker annuale."""
        self._stato_annuale = stato
        self._boundary_time_annuale = time.monotonic()

    def _aggiorna_eta_annuale(self):
        """Aggiorna periodicamente stato ed attesa massima dell’elaborazione annuale."""

        if getattr(self, '_annullamento_richiesto', False):
            self._tick_annuale = getattr(self, '_tick_annuale', 0) + 1
            punti = "." * (1 + (self._tick_annuale % 3))
            self.label_status.setText(
                f"Annullamento in corso… attendo la fine del mese in corso{punti}"
            )
            return

        stato = getattr(self, '_stato_annuale', None)
        if stato is None:
            return
        ora = time.monotonic()
        elapsed = ora - self._t0_annuale

        rim_budget = max(0.0, BUDGET_STAGIONI_SEC - elapsed)
        eta_max = stato.get('eta_max')
        if eta_max is not None:
            rim_raffinato = max(0.0, eta_max - (ora - self._boundary_time_annuale))
            eta = min(rim_budget, rim_raffinato)
        else:
            eta = rim_budget

        self._tick_annuale = getattr(self, '_tick_annuale', 0) + 1
        punti = " ." * (1 + (self._tick_annuale % 3))

        tentativo = stato.get('tentativo', 1)
        mese = stato.get('mese', 0)
        num_mesi = stato.get('num_mesi', 0)
        best = stato.get('best')

        if mese <= 0:
            riga1 = f"Preparo il tentativo {tentativo} — primo mese in corso {punti}"
        else:
            riga1 = f"Preparo il tentativo {tentativo}, mese {mese} di {num_mesi}{punti}"

        righe = [riga1]
        if best is not None:
            righe.append(f"Il migliore finora ripete {best} coppie")
        righe.append(f"Attesa massima: {_formatta_durata(eta)}")
        self.label_status.setText("\n".join(righe))

    def _annulla_annuale(self):
        """Richiede l’arresto cooperativo dell’elaborazione annuale."""
        if hasattr(self, 'season_worker') and self.season_worker is not None:
            self.btn_annulla_annuale.setEnabled(False)

            self._annullamento_richiesto = True
            self.season_worker.richiedi_stop()

    def _esegui_assegnazione_terzetti(self, studente_fisso, ha_fisso):
        """Esegue un’assegnazione mensile a terzetti e prepara risultati e salvataggio."""

        if self.radio_annuale.isChecked():
            self._avvia_annuale_terzetti(studente_fisso, ha_fisso)
            return

        num_studenti = len(self.studenti)

        posti_per_fila = int(self.input_posti_fila.text())
        terzetti_per_fila = posti_per_fila // 3

        if self.radio_resto_quartetti.isChecked():
            preferenza_resto2 = 'due_quartetti'
        else:
            preferenza_resto2 = 'coppia'

        if self.radio_trio_prima.isChecked():
            posizione_blocco_finale = 'prima'
        elif self.radio_trio_centro.isChecked():
            posizione_blocco_finale = 'centro'
        elif self.radio_trio_ultima.isChecked():
            posizione_blocco_finale = 'ultima'
        else:
            posizione_blocco_finale = 'ultima'

        self.configurazione_aula = ConfigurazioneAula(
            f"Aula {self.input_nome_classe.text()}"
        )
        self.configurazione_aula.crea_layout_terzetti(
            num_studenti,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            ha_fisso=ha_fisso,
            preferenza_resto2=preferenza_resto2,
        )

        capienza_prima = (
            self.configurazione_aula
            .capienza_prima_fila_terzetti()
        )

        num_studenti_prima = sum(
            1
            for studente in self.studenti
            if studente.nota_posizione == 'PRIMA'
        )
        posti_prima_utilizzabili = max(
            0,
            capienza_prima['posti'] - (1 if ha_fisso else 0)
        )

        if num_studenti_prima > posti_prima_utilizzabili:
            self._mostra_errore(
                "Posizione PRIMA impossibile",
                f"La prima fila offre {posti_prima_utilizzabili} posti "
                f"utilizzabili, ma {num_studenti_prima} studenti hanno "
                f"posizione PRIMA.\n\n"
                f"Richieste in eccesso: "
                f"{num_studenti_prima - posti_prima_utilizzabili}.\n\n"
                "Apri «Editor studenti» e riduci le posizioni PRIMA, "
                "oppure aumenta i posti per fila."
            )
            return

        genere_misto = self.checkbox_genere_misto.isChecked()
        motore = MotoreVincoliConfigurato()
        motore.imposta_genere_misto_obbligatorio(genere_misto)

        _applica_penalita_storico_mese(motore, self.config_app, modo="terzetti")

        seed_principale = risolvi_seed_principale(None)
        print(
            f"🎲 Operazione mensile a terzetti — seed principale: "
            f"{seed_principale}"
        )
        gruppi, metadati_casualita = mt.calcola_miglior_mese_terzetti(
            self.studenti,

            genere_misto,

            config_app=self.config_app,

            preferenza_resto2=preferenza_resto2,

            resto_in_prima_fila=(posizione_blocco_finale == 'prima'),
            max_terzetti_prima_fila=capienza_prima['terzetti'],
            max_resti_prima_fila=capienza_prima['resti'],
            num_candidati=mt.NUM_CANDIDATI_TERZETTI,
            seed_base=seed_principale,
            contesto_casuale={
                "operazione": "mensile",
                "mese": 1,
            },
            restituisci_metadati=True,
        )

        if gruppi is None:
            self._mostra_popup_fallimento_dettagliato({
                "casualita": metadati_casualita,
                "cause_certe": [],
                "suggerimenti": [
                    "Verifica il numero di allievi, le incompatibilità di "
                    "livello 3, le posizioni PRIMA e la geometria scelta."
                ],
            })
            return

        report = self.configurazione_aula.piazza_gruppi_terzetti(gruppi)

        if not report.get('valido_prima', True):
            self._mostra_errore(
                "Errore interno di posizionamento",
                "La disposizione prodotta non rispetta il vincolo assoluto "
                "PRIMA ed è stata scartata.\n\n"
                "Nessun dato è stato salvato."
            )
            return

        self._aggiorna_visualizzazione_aula(self.configurazione_aula)

        self.data_creazione_assegnazione_corrente = _data_creazione_corrente()
        numero = _prossimo_progressivo_storico(
            self.config_app,
            self.file_origine_studenti,
            "mensile",
            "terzetti",
        )
        self.progressivo_assegnazione_corrente = numero
        self.nome_assegnazione_corrente = _nome_assegnazione_automatico(
            self.input_nome_classe.text() or "Classe",
            "mensile",
            "terzetti",
            numero,
        )

        testo_report, _riutilizzi_totali = \
            self.costruisci_testo_report_terzetti(
                gruppi,
                motore,
                metadati_casualita=metadati_casualita,
                nome_assegnazione=self.nome_assegnazione_corrente,
                data_creazione=self.data_creazione_assegnazione_corrente,
            )
        self.text_report.setPlainText(testo_report)

        evidenzia_riutilizzi(self.text_report)
        applica_formattazione_statistiche_generali(
            self.text_report,
            getattr(self, '_statistiche_generali_terzetti_correnti', []),
        )
        self.widget_hint_report.setVisible(False)

        self.tab_widget.setCurrentIndex(1)

        avvisi = report.get('avvisi', [])
        self._mostra_popup_riepilogo_terzetti(gruppi, motore, avvisi)

        self.dati_ultima_assegnazione_terzetti = {
            'gruppi': gruppi,
            'configurazione_aula': self.configurazione_aula,
            'studente_fisso': studente_fisso,
            'posizione_blocco_finale': posizione_blocco_finale,
            'preferenza_resto2': preferenza_resto2,
            'statistiche_generali': [
                dict(riga) for riga in getattr(
                    self, '_statistiche_generali_terzetti_correnti', [])
            ],
            'metadati_casualita': metadati_casualita,
        }

        self.modo_ultima_assegnazione = 'terzetti'

        self.assegnazione_non_salvata = True

        self.btn_salva_progetto.setEnabled(True)
        self.btn_salva_progetto.setToolTip(
            "Salva questa disposizione nello Storico."
        )
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(

            "Disponibile dopo il salvataggio dell'assegnazione."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(

            "Disponibile dopo il salvataggio dell'assegnazione."
        )

    def _avvia_annuale_terzetti(self, studente_fisso, ha_fisso):
        """Avvia in background la generazione annuale a terzetti."""

        num_studenti = len(self.studenti)
        posti_per_fila = int(self.input_posti_fila.text())
        terzetti_per_fila = posti_per_fila // 3
        if self.radio_resto_quartetti.isChecked():
            preferenza_resto2 = 'due_quartetti'
        else:
            preferenza_resto2 = 'coppia'
        if self.radio_trio_prima.isChecked():
            posizione_blocco_finale = 'prima'
        elif self.radio_trio_centro.isChecked():
            posizione_blocco_finale = 'centro'
        elif self.radio_trio_ultima.isChecked():
            posizione_blocco_finale = 'ultima'
        else:
            posizione_blocco_finale = 'ultima'

        num_mesi = self.spinbox_mesi.value()
        genere_misto = self.checkbox_genere_misto.isChecked()

        aula_capienza = ConfigurazioneAula(
            "Calcolo capienza annuale terzetti"
        )
        aula_capienza.crea_layout_terzetti(
            num_studenti,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            ha_fisso=ha_fisso,
            preferenza_resto2=preferenza_resto2,
        )
        capienza_prima = (
            aula_capienza.capienza_prima_fila_terzetti()
        )

        num_studenti_prima = sum(
            1
            for studente in self.studenti
            if studente.nota_posizione == 'PRIMA'
        )
        posti_prima_utilizzabili = max(
            0,
            capienza_prima['posti'] - (1 if ha_fisso else 0)
        )

        if num_studenti_prima > posti_prima_utilizzabili:
            self._mostra_errore(
                "Posizione PRIMA impossibile",
                f"La prima fila offre {posti_prima_utilizzabili} posti "
                f"utilizzabili, ma {num_studenti_prima} studenti hanno "
                f"posizione PRIMA.\n\n"
                f"Richieste in eccesso: "
                f"{num_studenti_prima - posti_prima_utilizzabili}.\n\n"
                "Apri «Editor studenti» e riduci le posizioni PRIMA, "
                "oppure aumenta i posti per fila."
            )
            return

        self._geometria_annuale_terzetti = {
            'terzetti_per_fila': terzetti_per_fila,
            'posizione_blocco_finale': posizione_blocco_finale,
            'ha_fisso': ha_fisso,
            'preferenza_resto2': preferenza_resto2,
            'max_terzetti_prima_fila': capienza_prima['terzetti'],
            'max_resti_prima_fila': capienza_prima['resti'],
        }

        self._imposta_modalita_elaborazione(True)

        self.assegnazione_non_salvata = False

        self.season_worker = SeasonWorkerThreadTerzetti(
            self.studenti,
            self.config_app,
            num_mesi,
            genere_misto,
            preferenza_resto2,
            posizione_blocco_finale == 'prima',
            max_terzetti_prima_fila=(
                capienza_prima['terzetti']
            ),
            max_resti_prima_fila=(
                capienza_prima['resti']
            ),
        )

        self.season_worker.status_updated.connect(self.label_status.setText)
        self.season_worker.stagione_completata.connect(
            self._stagione_completata_provvisorio_terzetti
        )
        self.season_worker.error_occurred.connect(self._elaborazione_fallita)
        self.season_worker.stato_annuale_updated.connect(self._on_stato_annuale)

        self.btn_annulla_annuale.setEnabled(True)
        self.btn_annulla_annuale.show()
        self._t0_annuale = time.monotonic()
        self._boundary_time_annuale = self._t0_annuale
        self._stato_annuale = {'tentativo': 1, 'mese': 0,
                               'num_mesi': num_mesi, 'best': None, 'eta_max': None}
        self._annullamento_richiesto = False
        self.label_status.setText("Elaborazione delle assegnazioni annuali…")
        if not hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale = QTimer(self)
            self.timer_eta_annuale.timeout.connect(self._aggiorna_eta_annuale)
        self.timer_eta_annuale.start(500)

        self.season_worker.start()

    def _stagione_completata_provvisorio_terzetti(self, risultato: dict):
        """Apre l’anteprima della stagione a terzetti appena generata."""

        if hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale.stop()
        self.btn_annulla_annuale.hide()
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)

        mesi = risultato.get('mesi', [])
        info = risultato.get('info', {})
        motivo_stop = info.get('motivo_stop', None)

        if motivo_stop == "annullato":
            mostra_popup_semantico(
                self,
                "Operazione annullata",
                "La preparazione annuale è stata annullata.",
                "info",
                testo_informativo=(
                    "Nulla è stato salvato: lo Storico è rimasto "
                    "esattamente com'era."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if not mesi:
            mostra_popup_semantico(
                self,
                "Nessuna assegnazione",
                "Non è stato preparato alcun mese.",
                "triangle-alert",
                testo_informativo="Nulla è stato salvato.",
                messaggio_in_grassetto=True,
            )
            return

        nome_classe = self.input_nome_classe.text() or "Classe"
        geo = getattr(self, '_geometria_annuale_terzetti', {})
        dialog = AnteprimaStagioneDialog(
            self,
            self.config_app,
            mesi,
            info,
            self.file_origine_studenti,
            nome_classe,
            modo='terzetti',
            terzetti_per_fila=geo.get('terzetti_per_fila'),
            posizione_blocco_finale=geo.get('posizione_blocco_finale'),
            ha_fisso=geo.get('ha_fisso', False),
            preferenza_resto2=geo.get('preferenza_resto2', 'coppia'),
        )
        dialog.exec()

        if dialog.accettato:
            self._aggiorna_info_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()
            self.tab_widget.setCurrentIndex(3)

    def avvia_assegnazione(self):
        """Valida le scelte e avvia il flusso mensile o annuale richiesto."""

        if not self.studenti:
            self._mostra_errore("Nessun dato", "Carica prima un file con gli studenti.")
            return

        if hasattr(self, 'editor_studenti') and self.editor_studenti.ha_studenti_caricati():
            vincoli_incompleti = self.editor_studenti.get_vincoli_incompleti()
            if vincoli_incompleti:
                elenco = "\n".join(vincoli_incompleti)
                mostra_popup_semantico(
                    self,
                    "Vincoli incompleti nell'Editor",
                    "Alcuni vincoli non hanno il livello impostato.",
                    "triangle-alert",
                    testo_informativo=(
                        f"{elenco}\n\n"
                        "Questi vincoli verrebbero ignorati dall'assegnazione.\n\n"
                        "Torna nell'Editor e, per ogni vincolo, seleziona il "
                        "livello di intensità oppure rimuovilo. Poi clicca "
                        "«SALVA e CARICA» prima di assegnare."
                    ),
                    messaggio_in_grassetto=True,
                )
                self.tab_widget.setCurrentIndex(0)
                return

        if hasattr(self, 'editor_studenti') and self.editor_studenti._modifiche_non_salvate:
            mostra_popup_semantico(
                self,
                "Modifiche non salvate nell'Editor",
                "Le modifiche dell'Editor non sono state salvate.",
                "triangle-alert",
                testo_informativo=(
                    "L'assegnazione utilizzerebbe i dati dell'ultimo salvataggio, "
                    "ignorando le modifiche recenti.\n\n"
                    "Torna nell'Editor e clicca «SALVA e CARICA» per aggiornare "
                    "i dati prima di procedere."
                ),
                messaggio_in_grassetto=True,
            )

            self.tab_widget.setCurrentIndex(0)
            return

        if hasattr(self, 'posti_insufficienti') and self.posti_insufficienti:
            mostra_popup_semantico(
                self,
                "Posti insufficienti",
                "Non ci sono abbastanza posti per tutti gli studenti.",
                "circle-x",
                testo_informativo=(
                    f"Studenti da sistemare: {len(self.studenti)}\n"
                    f"Posti disponibili: "
                    f"{int(self.input_num_file.text()) * int(self.input_posti_fila.text())}\n\n"
                    "Aumenta il numero di file di banchi oppure i posti per fila."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if self.assegnazione_non_salvata:
            dialog_avvia = crea_popup_semantico(
                self,
                "Assegnazione non salvata",
                "L'assegnazione corrente non è stata salvata nello Storico.",
                "triangle-alert",
                testo_informativo=(
                    "Se scegli di proseguire, verrà scartata definitivamente: "
                    "le schede Aula e Report saranno svuotate e non sarà più "
                    "possibile salvarla o includerla nelle rotazioni future.\n\n"
                    "Che cosa vuoi fare?"
                ),
                messaggio_in_grassetto=True,
            )

            btn_salva_avvia = dialog_avvia.addButton(
                "Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_prosegui_avvia = dialog_avvia.addButton(
                "Scarta e prosegui", QMessageBox.DestructiveRole
            )
            btn_annulla_avvia = dialog_avvia.addButton(
                "Annulla", QMessageBox.RejectRole
            )
            applica_icona(btn_salva_avvia, "save", 18)
            applica_icona(btn_prosegui_avvia, "trash-2", 18)
            applica_stile_pulsante_popup(
                btn_prosegui_avvia, "distruttivo"
            )
            applica_icona(btn_annulla_avvia, "x", 18)

            dialog_avvia.setDefaultButton(btn_salva_avvia)

            dialog_avvia.setEscapeButton(btn_annulla_avvia)

            dialog_avvia.exec()

            bottone_avvia = dialog_avvia.clickedButton()

            if bottone_avvia == btn_salva_avvia:

                self.salva_assegnazione()

                return

            elif bottone_avvia == btn_annulla_avvia:

                return


        # Una nuova elaborazione parte sempre da una superficie vuota: il docente
        # vede subito che il programma sta preparando un risultato differente.
        self._resetta_tab_aula_report()

        num_studenti = len(self.studenti)
        self.configurazione_aula = ConfigurazioneAula(f"Aula {self.input_nome_classe.text()}")

        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())

        studente_fisso = None
        num_fissi = 0
        for s in self.studenti:
            if s.nota_posizione == 'FISSO':
                num_fissi += 1
                studente_fisso = s

        if num_fissi > 1:
            self._mostra_errore(
                "ERRORE CONFIGURAZIONE!",
                f"Trovati {num_fissi} studenti con posizione 'FISSO'.\n\n"
                f"Al massimo 1 studente può avere posizione FISSO.\n"
                f"Correggi eliminando le posizioni 'FISSO' in eccesso."
            )
            return

        ha_fisso = (studente_fisso is not None)
        if ha_fisso:
            print(f"📌 Studente FISSO individuato: {studente_fisso.get_nome_completo()}")

        if getattr(self, 'modalita_geometria', 'coppie') == 'terzetti':
            self._esegui_assegnazione_terzetti(studente_fisso, ha_fisso)
            return

        num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti

        posizione_trio = None
        modalita_trio = 'centro'

        if num_rimanenti % 2 == 1:
            if self.radio_trio_prima.isChecked():
                posizione_trio = "prima"
                modalita_trio = "prima"
            elif self.radio_trio_ultima.isChecked():
                posizione_trio = "ultima"
                modalita_trio = "ultima"
            elif self.radio_trio_centro.isChecked():
                posizione_trio = "centro"
                modalita_trio = "centro"

        self.configurazione_aula.crea_layout_standard(
            num_studenti, num_file, posti_per_fila, posizione_trio, ha_fisso=ha_fisso
        )

        if num_studenti > self.configurazione_aula.posti_disponibili:
            self._mostra_errore(
                "Configurazione NON valida",
                f"Non ci sono abbastanza posti.\n"
                f"Studenti: {num_studenti}\n"
                f"Posti disponibili: {self.configurazione_aula.posti_disponibili}\n\n"
                f"Aumenta il numero di file o posti per fila."
            )
            return

        self._imposta_modalita_elaborazione(True)

        if self.radio_annuale.isChecked():

            num_mesi = self.spinbox_mesi.value()

            nome_classe_report = self.input_nome_classe.text()
            studenti_report = self.studenti

            cattura_report = lambda asg, uc, uv, foto, vicini: self.costruisci_testo_report(
                asg, nome_classe_report, studenti_report,
                ultimo_uso_coppie=uc, ultimo_uso_vicino=uv,
                coppie_gia_usate_esplicite=foto,
                vicini_fisso_espliciti=vicini
            )[0]

            self.season_worker = SeasonWorkerThread(
                self.studenti,
                self.configurazione_aula,
                self.config_app,
                num_mesi,
                modalita_trio,
                self.checkbox_genere_misto.isChecked(),
                studente_fisso,
                cattura_report=cattura_report
            )

            self.season_worker.status_updated.connect(self.label_status.setText)

            self.season_worker.stagione_completata.connect(self._stagione_completata_provvisorio)

            self.season_worker.error_occurred.connect(self._elaborazione_fallita)

            self.btn_annulla_annuale.setEnabled(True)
            self.btn_annulla_annuale.show()

            self.season_worker.stato_annuale_updated.connect(self._on_stato_annuale)
            self._t0_annuale = time.monotonic()
            self._boundary_time_annuale = self._t0_annuale
            self._stato_annuale = {'tentativo': 1, 'mese': 0,
                                   'num_mesi': num_mesi, 'best': None, 'eta_max': None}
            self._annullamento_richiesto = False
            self.label_status.setText("Elaborazione delle assegnazioni annuali…")
            if not hasattr(self, 'timer_eta_annuale'):
                self.timer_eta_annuale = QTimer(self)
                self.timer_eta_annuale.timeout.connect(self._aggiorna_eta_annuale)
            self.timer_eta_annuale.start(500)

            self.season_worker.start()

        else:

            self.indice_messaggio = 0
            self.timer_messaggi.start(2000)

            self.worker_thread = WorkerThread(
                self.studenti,
                self.configurazione_aula,
                self.config_app,
                modalita_trio,
                self.checkbox_genere_misto.isChecked(),
                studente_fisso
            )

            self.worker_thread.status_updated.connect(self.label_status.setText)
            self.worker_thread.completed.connect(self._elaborazione_completata)
            self.worker_thread.error_occurred.connect(self._elaborazione_fallita)

            self.worker_thread.start()

    def _imposta_modalita_elaborazione(self, in_elaborazione: bool):
        """Alterna l’interfaccia fra stato operativo e stato di elaborazione."""

        self.btn_avvia_assegnazione.setEnabled(not in_elaborazione)

        if in_elaborazione:
            self.label_status.setText("Elaborazione in corso...")
        else:
            self.label_status.setText("")

    def _elaborazione_completata(self, assegnatore: AssegnatorePosti):
        """Riceve una disposizione a coppie completata e ne mostra i risultati."""

        self.ultimo_assegnatore = assegnatore

        self.modo_ultima_assegnazione = 'coppie'
        self.dati_ultima_assegnazione_terzetti = None

        self.assegnazione_non_salvata = True

        self.timer_messaggi.stop()

        self._imposta_modalita_elaborazione(False)

        self.data_creazione_assegnazione_corrente = _data_creazione_corrente()
        numero = _prossimo_progressivo_storico(
            self.config_app,
            self.file_origine_studenti,
            "mensile",
            "coppie",
        )
        self.progressivo_assegnazione_corrente = numero
        self.nome_assegnazione_corrente = _nome_assegnazione_automatico(
            self.input_nome_classe.text() or "Classe",
            "mensile",
            "coppie",
            numero,
        )

        self._visualizza_risultati(assegnatore)

        self.btn_salva_progetto.setEnabled(True)

        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "SALVA prima l'assegnazione nello storico per abilitare l'export."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "SALVA prima l'assegnazione nello storico per abilitare l'export."
        )

        righe_statistiche = assegnatore.statistiche_generali
        ha_precedenti_altro_modo = self._precedenti_altro_modo > 0

        msg_box = crea_popup_semantico(
            self,
            "Assegnazione completata",
            "",
            "info" if ha_precedenti_altro_modo else "circle-check",
        )
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(
            "<b>Assegnazione completata con successo.</b><br><br>"
            "<b>Statistiche generali</b>"
        )
        msg_box.addButton(QMessageBox.Ok)
        _aggiungi_widget_popup(
            msg_box,
            _crea_widget_righe_statistiche(righe_statistiche),
        )

        if ha_precedenti_altro_modo:
            nota = QLabel(
                f'<span style="color: {C("testo_info")};">'
                f'<b>Nota informativa</b> — '
                f'{self._precedenti_altro_modo} vicinanze hanno precedenti '
                f'nella modalità terzetti. Le rotazioni dei due modi '
                f'restano indipendenti.</span>'
            )
            nota.setTextFormat(Qt.RichText)
            nota.setWordWrap(True)
            _aggiungi_widget_popup(msg_box, nota)

        msg_box.exec()

    def _mostra_popup_riepilogo_terzetti(self, gruppi, motore, avvisi=None):
        """Mostra il riepilogo strutturato dell’assegnazione a terzetti."""

        righe_statistiche = self._statistiche_generali_terzetti_correnti
        ha_precedenti_altro_modo = self._precedenti_altro_modo > 0

        msg_box = crea_popup_semantico(
            self,
            "Assegnazione completata",
            "",
            "info" if ha_precedenti_altro_modo else "circle-check",
        )
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(
            "<b>Assegnazione completata con successo.</b><br><br>"
            "<b>Statistiche generali</b>"
        )
        msg_box.addButton(QMessageBox.Ok)
        _aggiungi_widget_popup(
            msg_box,
            _crea_widget_righe_statistiche(righe_statistiche),
        )

        note = []
        if ha_precedenti_altro_modo:
            note.append(
                f'<span style="color: {C("testo_info")};">'
                f'<b>Nota informativa</b> — '
                f'{self._precedenti_altro_modo} vicinanze hanno precedenti '
                f'nella modalità coppie. Le rotazioni dei due modi '
                f'restano indipendenti.</span>'
            )
        if avvisi:
            note.append(
                f'<span style="color: {C("testo_ocra")}; font-weight: bold;">'
                f'Avvisi di capienza: {"<br>".join(avvisi)}</span>'
            )
        if note:
            etichetta_note = QLabel("<br><br>".join(note))
            etichetta_note.setTextFormat(Qt.RichText)
            etichetta_note.setWordWrap(True)
            _aggiungi_widget_popup(msg_box, etichetta_note)

        msg_box.exec()

    def _stagione_completata_provvisorio(self, risultato: dict):
        """Apre l’anteprima della stagione a coppie appena generata."""

        if hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale.stop()
        self.btn_annulla_annuale.hide()
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)

        mesi = risultato.get('mesi', [])
        info = risultato.get('info', {})
        motivo_stop = info.get('motivo_stop', None)

        if motivo_stop == "annullato":
            mostra_popup_semantico(
                self,
                "Operazione annullata",
                "La preparazione annuale è stata annullata.",
                "info",
                testo_informativo=(
                    "Nulla è stato salvato: lo Storico è rimasto "
                    "esattamente com'era."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if not mesi:
            mostra_popup_semantico(
                self,
                "Nessuna assegnazione",
                "Non è stato preparato alcun mese.",
                "triangle-alert",
                testo_informativo="Nulla è stato salvato.",
                messaggio_in_grassetto=True,
            )
            return

        nome_classe = self.input_nome_classe.text() or "Classe"
        dialog = AnteprimaStagioneDialog(
            self,
            self.config_app,
            mesi,
            info,
            self.file_origine_studenti,
            nome_classe
        )
        dialog.exec()

        if dialog.accettato:
            self._aggiorna_info_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()

            self.tab_widget.setCurrentIndex(3)

    def _elaborazione_fallita(self, messaggio_errore: str, report: dict = None):
        """Mostra il fallimento dell’elaborazione con gli eventuali dati diagnostici."""

        self.timer_messaggi.stop()

        if hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale.stop()

        self.btn_annulla_annuale.hide()
        self._imposta_modalita_elaborazione(False)

        if report:

            self._mostra_popup_fallimento_dettagliato(report)
        else:

            self._mostra_errore("Errore Assegnazione", messaggio_errore)

    def _mostra_popup_fallimento_dettagliato(self, report: dict):
        """Mostra analisi e suggerimenti del report diagnostico di fallimento."""
        msg_box = crea_popup_semantico(
            self,
            "Assegnazione non riuscita",
            "",
            "circle-x",
        )
        msg_box.setTextFormat(Qt.RichText)

        html_parti = []
        html_parti.append(
            "<b>L'algoritmo non è riuscito a completare una "
            "disposizione valida.</b><br><br>"
        )

        cause_certe = report.get("cause_certe", [])

        if cause_certe:
            html_parti.append(
                "<b>Causa certa individuata:</b><br>"
            )
            for causa in cause_certe:
                html_parti.append(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;• {causa}<br>"
                )
            html_parti.append("<br>")
        else:
            html_parti.append(
                "Non è possibile attribuire il fallimento a un solo "
                "vincolo: è probabilmente la loro combinazione a impedire "
                "una disposizione completa.<br><br>"
            )

        incomp = report.get("incompatibilita_assolute", [])
        if incomp:
            html_parti.append(
                f"<b>Incompatibilità assolute (livello 3):</b> {len(incomp)}<br>"
            )

            for coppia in incomp[:4]:
                html_parti.append(f"&nbsp;&nbsp;&nbsp;&nbsp;• {coppia}<br>")
            if len(incomp) > 4:
                html_parti.append(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;<i>... e altre {len(incomp) - 4}</i><br>"
                )
            html_parti.append("<br>")

        prima_fila = report.get(
            "studenti_prima_fila",
            []
        )
        info_prima = report.get("prima_fila", {})

        if info_prima.get("impossibile_per_capienza"):
            html_parti.append(
                f"<b>Posizione PRIMA impossibile:</b> "
                f"{info_prima.get('richieste', 0)} richieste, "
                f"ma soltanto "
                f"{info_prima.get('posti_utilizzabili', 0)} "
                f"posti utilizzabili nella prima fila.<br><br>"
            )
        elif prima_fila:
            html_parti.append(
                f"<b>Studenti con posizione PRIMA:</b> "
                f"{len(prima_fila)} su "
                f"{info_prima.get('posti_utilizzabili', '?')} "
                f"posti utilizzabili.<br><br>"
            )

        gm = report.get("genere_misto")

        bl = report.get("blacklist", {})
        if bl.get("coppie", 0) > 5:
            html_parti.append(
                f"<b>Blacklist:</b> {bl['coppie']} coppie già usate "
                f"in precedenti assegnazioni<br><br>"
            )

        suggerimenti = report.get("suggerimenti", [])
        if suggerimenti:
            html_parti.append("<b>Suggerimenti per risolvere:</b><br>")
            for i, sugg in enumerate(suggerimenti, 1):
                html_parti.append(f"&nbsp;&nbsp;{i}. {sugg}<br>")

        msg_box.setText("".join(html_parti))

        dettagli_parti = []
        dettagli_parti.append("=" * 50)
        dettagli_parti.append("REPORT DIAGNOSTICO COMPLETO")
        dettagli_parti.append("=" * 50)

        dettagli_parti.append("")
        dettagli_parti.append("INCOMPATIBILITÀ ASSOLUTE (livello 3):")
        if incomp:
            for coppia in incomp:
                dettagli_parti.append(f"  • {coppia}")
        else:
            dettagli_parti.append("  Nessuna")

        dettagli_parti.append("")
        dettagli_parti.append("POSIZIONE PRIMA:")
        dettagli_parti.append(
            f"  Richieste: "
            f"{info_prima.get('richieste', len(prima_fila))}"
        )
        dettagli_parti.append(
            f"  Posti utilizzabili nella prima fila: "
            f"{info_prima.get('posti_utilizzabili', 'N/D')}"
        )

        if info_prima.get("eccesso", 0) > 0:
            dettagli_parti.append(
                f"  Richieste in eccesso: "
                f"{info_prima['eccesso']}"
            )

        if prima_fila:
            dettagli_parti.append("  Studenti:")
            for nome in prima_fila:
                dettagli_parti.append(f"    • {nome}")
        else:
            dettagli_parti.append("  Nessuno")

        senza_vicini = report.get(
            "studenti_senza_vicini_compatibili",
            []
        )
        if senza_vicini:
            dettagli_parti.append("")
            dettagli_parti.append(
                "STUDENTI SENZA ALCUN VICINO COMPATIBILE:"
            )
            for nome in senza_vicini:
                dettagli_parti.append(f"  • {nome}")

        info_fisso = report.get("fisso", {})
        if info_fisso.get("presente"):
            dettagli_parti.append("")
            dettagli_parti.append("STUDENTE FISSO:")
            dettagli_parti.append(
                f"  Nome: {info_fisso.get('nome')}"
            )
            dettagli_parti.append(
                f"  Possibili vicini compatibili: "
                f"{len(info_fisso.get('possibili_vicini', []))}"
            )

        if gm:
            dettagli_parti.append("")
            dettagli_parti.append("GENERE MISTO:")
            dettagli_parti.append("  Flag attivo: Sì")
            dettagli_parti.append(f"  Maschi: {gm['maschi']}, Femmine: {gm['femmine']}")
            if gm["sbilanciamento"]:
                dettagli_parti.append("  Sbilanciamento rilevato")

        dettagli_parti.append("")
        dettagli_parti.append("BLACKLIST (storico rotazioni):")
        dettagli_parti.append(f"  Coppie in blacklist: {bl.get('coppie', 0)}")
        piu_usate = bl.get("piu_usate", [])
        if piu_usate:
            dettagli_parti.append("  Coppie più riutilizzate:")
            for cu in piu_usate:
                dettagli_parti.append(f"    - {cu}")

        dettagli_parti.append("")
        dettagli_parti.append("SUGGERIMENTI:")
        for i, sugg in enumerate(suggerimenti, 1):
            dettagli_parti.append(f"  {i}. {sugg}")

        dettagli_parti.append("")
        dettagli_parti.append("=" * 50)

        msg_box.setDetailedText("\n".join(dettagli_parti))
        prepara_area_dettagli_popup(
            msg_box,
            larghezza_minima=760,
            altezza_minima=320,
        )
        msg_box.addButton(QMessageBox.Ok)

        msg_box.exec()

    def _visualizza_risultati(self, assegnatore: AssegnatorePosti):
        """Aggiorna aula e report con l’assegnazione completata."""

        self._aggiorna_visualizzazione_aula(assegnatore.configurazione_aula)

        self._aggiorna_report_testuale(
            assegnatore,
            nome_assegnazione=self.nome_assegnazione_corrente,
            data_creazione=self.data_creazione_assegnazione_corrente,
        )

        self.widget_hint_report.setVisible(True)

        self.tab_widget.setCurrentIndex(1)

    def _aggiorna_visualizzazione_aula(self, configurazione_aula: ConfigurazioneAula):
        """Ridisegna la griglia dell’aula corrente."""

        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            widget = child.widget()
            if widget is not None:
                # Evita che widget in attesa di deleteLater() restino dipinti
                # sotto la nuova configurazione durante un popup modale.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        griglia_invertita = list(reversed(configurazione_aula.griglia))
        riga_display = 0
        for riga in griglia_invertita:

            ha_contenuto = any(posto.tipo != 'corridoio' for posto in riga)
            if not ha_contenuto:
                continue

            for col_idx, posto in enumerate(riga):

                if posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None
                                      or cella_precedente.tipo != posto.tipo)
                    if is_prima_cella:

                        widget_posto = self.crea_widget_posto(posto, merged=True)
                        self.layout_griglia_aula.addWidget(
                            widget_posto, riga_display, col_idx, 1, 2)

                else:

                    widget_posto = self.crea_widget_posto(posto)
                    self.layout_griglia_aula.addWidget(
                        widget_posto, riga_display, col_idx)

            riga_display += 1

        # Il riepilogo viene aperto subito dopo questo metodo. Si completa il
        # repaint ora, così il popup non congela nel viewport tracce del layout
        # precedente mentre la nuova geometria è già presente.
        self._forza_ridisegno_aula()

    def crea_widget_posto(self, posto, merged=False) -> QWidget:
        """Crea il widget grafico di un posto o di un arredo dell’aula."""

        widget = QLabel()

        larghezza_min = 250 if merged else 120
        widget.setMinimumSize(larghezza_min, 60)
        widget.setAlignment(Qt.AlignCenter)

        widget.setStyleSheet(f"border: 1px solid {C('banco_libero_bordo')}; margin: 1px;")

        if posto.tipo == 'banco':
            if posto.occupato_da:

                nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                widget.setText(nome_completo)
                widget.setWordWrap(True)
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

                applica_icona_etichetta(widget, "armchair", 28)
                widget.setStyleSheet(f"""
                    border: 2px dashed {C("banco_libero_bordo")};
                    background-color: {C("banco_libero_sf")};
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip("Posto libero")

        elif posto.tipo == 'cattedra':

            if merged:
                widget.setText("CATTEDRA")
            else:
                applica_icona_etichetta(widget, "school", 28)
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

            if merged:
                widget.setText("LIM")
            else:
                applica_icona_etichetta(widget, "monitor", 28)
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

            if merged:
                widget.setText("LAVAGNA")
            else:
                applica_icona_etichetta(widget, "presentation", 28)
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

        else:
            widget.setText("")
            widget.setStyleSheet("""
                border: none;
                background-color: transparent;
                margin: 1px;
            """)

        return widget

    def salva_assegnazione(self):
        """Salva l’ultima assegnazione completata nella modalità corretta."""

        # Decide il modo che ha prodotto il risultato, non il radio che l’utente può avere cambiato dopo.
        if self.modo_ultima_assegnazione == 'terzetti':
            self._salva_assegnazione_terzetti()
            return

        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        nome_assegnazione, ok = self._chiedi_nome_assegnazione()

        if ok and nome_assegnazione:

            self.nome_assegnazione_corrente = nome_assegnazione
            trio_presente = getattr(self.ultimo_assegnatore, 'trio_identificato', None)

            studente_fisso = getattr(self.ultimo_assegnatore, 'studente_fisso', None)
            gruppo_adiacente_fisso = getattr(self.ultimo_assegnatore, 'gruppo_adiacente_fisso', None)

            nome_adiacente_fisso = getattr(self.ultimo_assegnatore, 'nome_adiacente_fisso', None)

            self._aggiorna_riga_identificativa_report(nome_assegnazione)

            report_completo = self.text_report.toPlainText()

            self.config_app.aggiungi_assegnazione_storico(
                nome_assegnazione,
                self.ultimo_assegnatore.coppie_formate,
                trio_presente,
                self.ultimo_assegnatore.configurazione_aula,
                self.file_origine_studenti,
                report_completo,
                studente_fisso=studente_fisso,
                gruppo_adiacente_fisso=gruppo_adiacente_fisso,
                nome_adiacente_fisso=nome_adiacente_fisso,
                genere_misto=self.checkbox_genere_misto.isChecked(),
                statistiche_generali=getattr(
                    self.ultimo_assegnatore, 'statistiche_generali', []),
                metadati_casualita=(
                    self.ultimo_assegnatore.esporta_metadati_casualita()
                ),
                nome_classe=self.input_nome_classe.text() or "Classe",
                generazione="mensile",
                data_creazione=self.data_creazione_assegnazione_corrente,
                progressivo=self.progressivo_assegnazione_corrente,
                abbinamenti=_descrivi_abbinamenti_coppie(
                    self.ultimo_assegnatore
                ),
            )

            self.indice_assegnazione_corrente = (
                len(self.config_app.config_data["storico_assegnazioni"]) - 1
            )
            self._aggiorna_info_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()

            mostra_popup_semantico(
                self,
                "Assegnazione salvata",
                "L'assegnazione è stata salvata nello Storico.",
                "circle-check",
                testo_informativo=f"Nome: {nome_assegnazione}",
                messaggio_in_grassetto=True,
            )

            self.assegnazione_non_salvata = False

            self.btn_export_excel.setEnabled(True)
            self.btn_export_excel.setToolTip("Esporta questa assegnazione in formato Excel.")
            self.btn_export_report_txt.setEnabled(True)
            self.btn_export_report_txt.setToolTip("Esporta il Report testuale di questa assegnazione.")

    def _salva_assegnazione_terzetti(self):
        """Salva nello Storico l’ultima assegnazione a terzetti."""

        dati = self.dati_ultima_assegnazione_terzetti
        if not dati:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        nome_assegnazione, ok = self._chiedi_nome_assegnazione()
        if not (ok and nome_assegnazione):
            return

        self.nome_assegnazione_corrente = nome_assegnazione
        self._aggiorna_riga_identificativa_report(nome_assegnazione)
        report_completo = self.text_report.toPlainText()

        self.config_app.aggiungi_assegnazione_storico_terzetti(
            nome_assegnazione,
            dati['gruppi'],
            dati['configurazione_aula'],
            file_origine=self.file_origine_studenti,
            report_completo=report_completo,
            studente_fisso=dati['studente_fisso'],
            genere_misto=self.checkbox_genere_misto.isChecked(),
            posizione_blocco_finale=dati['posizione_blocco_finale'],
            preferenza_resto2=dati['preferenza_resto2'],
            statistiche_generali=dati.get('statistiche_generali', []),
            metadati_casualita=dati.get('metadati_casualita'),
            nome_classe=self.input_nome_classe.text() or "Classe",
            generazione="mensile",
            data_creazione=self.data_creazione_assegnazione_corrente,
            progressivo=self.progressivo_assegnazione_corrente,
            abbinamenti=_descrivi_abbinamenti_terzetti(dati['gruppi']),
        )

        self.indice_assegnazione_corrente = (
            len(self.config_app.config_data["storico_assegnazioni"]) - 1
        )
        self._aggiorna_info_storico()
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        mostra_popup_semantico(
            self,
            "Assegnazione salvata",
            "L'assegnazione è stata salvata nello Storico.",
            "circle-check",
            testo_informativo=f"Nome: {nome_assegnazione}",
            messaggio_in_grassetto=True,
        )

        self.assegnazione_non_salvata = False

        self.btn_export_report_txt.setEnabled(True)
        self.btn_export_report_txt.setToolTip(
            "Esporta il Report testuale di questa assegnazione.")

        self.btn_export_excel.setEnabled(True)
        self.btn_export_excel.setToolTip(
            "Esporta la piantina di questa assegnazione in Excel.")

    def _chiedi_nome_assegnazione(self) -> tuple:
        """Propone e acquisisce il nome modificabile dell'assegnazione."""

        from PySide6.QtWidgets import QInputDialog

        nome_suggerito = getattr(self, "nome_assegnazione_corrente", None)
        if not nome_suggerito:
            modo = self.modo_ultima_assegnazione or "coppie"
            numero = _prossimo_progressivo_storico(
                self.config_app,
                self.file_origine_studenti,
                "mensile",
                modo,
            )
            self.progressivo_assegnazione_corrente = numero
            nome_suggerito = _nome_assegnazione_automatico(
                self.input_nome_classe.text() or "Classe",
                "mensile",
                modo,
                numero,
            )

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Nome assegnazione")
        applica_icona_finestra(dialog, "save")
        dialog.setLabelText("Inserisci un nome per questa assegnazione:")
        dialog.setTextValue(nome_suggerito)
        dialog.resize(550, 150)

        ok = dialog.exec()
        return dialog.textValue(), ok

    def _cambia_tema(self):
        """Alterna il tema, aggiorna i widget e salva la preferenza."""

        nuovo_tema = "chiaro" if get_tema() == "scuro" else "scuro"

        imposta_tema(nuovo_tema)

        self.setup_stili()

        self._aggiorna_stili_widget()

        if hasattr(self, 'editor_studenti'):
            self.editor_studenti.aggiorna_tema()

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

        self._aggiorna_statistiche()

        self._aggiorna_tabella_storico()

        if nuovo_tema == "chiaro":
            self.btn_toggle_tema.setText("Tema scuro")
            applica_icona(self.btn_toggle_tema, "moon", 18)
        else:
            self.btn_toggle_tema.setText("Tema chiaro")
            applica_icona(self.btn_toggle_tema, "sun", 18)

        aggiorna_icone_applicazione()

        QTimer.singleShot(0, self._aggiorna_finestre_informative_aperte)

        self.config_app.config_data["tema"] = nuovo_tema
        self.config_app.salva_configurazione()

    def _aggiorna_finestre_informative_aperte(self):
        """Aggiorna col tema corrente le finestre informative già aperte."""
        aggiorna_tema_finestre_informative(self)

    def _mostra_crediti(self):
        """Apre crediti e licenza."""
        mostra_crediti(self, get_base_path())

    def _mostra_aiuto_configurazione_aula(self):
        """Apre lo schema di aiuto per la configurazione dell’aula."""
        mostra_aiuto_configurazione_aula(self)

    def _mostra_errore(self, titolo: str, messaggio: str):
        """Mostra un errore con il protocollo visivo comune."""
        mostra_popup_semantico(
            self,
            titolo,
            messaggio,
            "circle-x",
            messaggio_in_grassetto=True,
        )

    def _aggiorna_messaggio_elaborazione(self):
        """Ruota il messaggio mostrato durante l’elaborazione."""

        self.indice_messaggio = (self.indice_messaggio + 1) % len(self.messaggi_elaborazione)
        messaggio_corrente = self.messaggi_elaborazione[self.indice_messaggio]

        self.label_status.setText(messaggio_corrente)

    def _controlla_classe_gia_elaborata(self, nome_file_classe):
        """Collega la classe caricata al relativo Storico e alle rotazioni."""
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        classe_trovata = False

        if self.file_origine_studenti and storico:
            classe_trovata = any(
                assegnazione.get("file_origine") == self.file_origine_studenti
                for assegnazione in storico
            )

        if not classe_trovata and storico:
            match = self._cerca_classe_per_fingerprint()
            if match:
                file_vecchio, nomi_comuni, totale = match
                classe_trovata = self._chiedi_ricollegamento_storico(
                    file_vecchio,
                    nomi_comuni,
                    totale,
                )

        if classe_trovata:
            self.label_status.setText(
                "Classe riconosciuta: pronta per rotazione"
            )
            self.label_status.setStyleSheet(
                f"color: {C('testo_stato_ok')}; font-weight: bold;"
            )
            QTimer.singleShot(15000, lambda: (
                self.label_status.setText("")
                if not self.timer_messaggi.isActive()
                else None
            ))

    def _cerca_classe_per_fingerprint(self):
        """Cerca nello Storico una classe simile associata a un nome file diverso."""
        if not self.studenti or not self.file_origine_studenti:
            return None

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if not storico:
            return None

        nomi_caricati = set()
        for studente in self.studenti:
            nomi_caricati.add(studente.get_nome_completo())

        classi_storico = {}
        for assegnazione in storico:
            fo = assegnazione.get("file_origine", "")
            if fo and fo != self.file_origine_studenti:

                if fo not in classi_storico:
                    classi_storico[fo] = []
                classi_storico[fo].append(assegnazione)

        soglia_minima = 5
        miglior_match = None
        max_nomi_comuni = 0

        for file_origine_vecchio, assegnazioni in classi_storico.items():

            ultima = assegnazioni[-1]
            layout = ultima.get("layout", [])

            nomi_storico = set()
            for entry in layout:
                nome = entry.get("studente", "")
                if nome:
                    nomi_storico.add(nome)

            nomi_comuni = nomi_caricati & nomi_storico

            if len(nomi_comuni) >= soglia_minima and len(nomi_comuni) > max_nomi_comuni:
                max_nomi_comuni = len(nomi_comuni)
                miglior_match = (file_origine_vecchio, nomi_comuni, len(nomi_storico))

        return miglior_match

    def _chiedi_ricollegamento_storico(self, file_origine_vecchio, nomi_in_comune, totale_storico):
        """Propone di ricollegare lo Storico a un file classe rinominato."""

        num_comuni = len(nomi_in_comune)
        num_caricati = len(self.studenti)

        elenco_nomi = "\n".join(
            f"• {nome}" for nome in sorted(nomi_in_comune)
        )

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        num_assegnazioni = sum(
            1 for a in storico
            if a.get("file_origine") == file_origine_vecchio
        )

        dialog = crea_popup_semantico(
            self,
            "Classe riconosciuta",
            "Vuoi ricollegare questa classe allo Storico riconosciuto?",
            "history",
            testo_informativo=(
                "File appena caricato:\n"
                f"  {self.file_origine_studenti}\n\n"
                "Classe storica riconosciuta:\n"
                f"  {file_origine_vecchio}\n\n"
                f"Corrispondenza: {num_comuni} studenti in comune "
                f"su {num_caricati} caricati.\n"
                f"Assegnazioni da ricollegare: {num_assegnazioni}.\n\n"
                "Confermando, le assegnazioni precedenti verranno associate "
                "al nuovo file e la rotazione continuerà tenendo conto delle "
                "vicinanze già formate."
            ),
            testo_dettagliato=(
                f"Studenti presenti nell'ultima assegnazione storica: "
                f"{totale_storico}\n"
                f"Studenti riconosciuti in comune: {num_comuni}\n\n"
                f"{elenco_nomi}"
            ),
            messaggio_in_grassetto=True,
        )

        btn_collega = dialog.addButton(
            "Ricollega lo Storico", QMessageBox.AcceptRole
        )
        btn_no = dialog.addButton(
            "È una classe diversa", QMessageBox.RejectRole
        )
        applica_icona(btn_collega, "history", 18)
        applica_icona(btn_no, "x", 18)

        dialog.setDefaultButton(btn_collega)
        dialog.setEscapeButton(btn_no)
        dialog.exec()

        if dialog.clickedButton() != btn_collega:
            return False

        assegnazioni_aggiornate = 0

        nome_vecchio_stem = os.path.splitext(file_origine_vecchio)[0]
        nome_nuovo_stem = os.path.splitext(self.file_origine_studenti)[0]

        for assegnazione in storico:
            if assegnazione.get("file_origine") == file_origine_vecchio:
                assegnazione["file_origine"] = self.file_origine_studenti

                nome_originale = assegnazione.get("nome", "")
                if nome_vecchio_stem.lower() in nome_originale.lower():

                    idx = nome_originale.lower().find(nome_vecchio_stem.lower())
                    if idx >= 0:
                        assegnazione["nome"] = (
                            nome_originale[:idx]
                            + nome_nuovo_stem
                            + nome_originale[idx + len(nome_vecchio_stem):]
                        )

                assegnazioni_aggiornate += 1

        self.config_app.salva_configurazione()

        print(f"🔗 Storico ricollegato: '{file_origine_vecchio}' → "
              f"'{self.file_origine_studenti}' ({assegnazioni_aggiornate} assegnazioni)")

        self._aggiorna_tabella_storico()

        self._popola_filtro_classi()

        return True

    def _auto_calcola_layout_aula(self):
        """Calcola una geometria iniziale capace di contenere la classe."""

        posti_per_fila_default = self.DEFAULT_POSTI_PER_FILA_COPPIE
        self.input_posti_fila.setText(str(posti_per_fila_default))

        if self.studenti:
            num_studenti = len(self.studenti)
            file_necessarie = math.ceil(num_studenti / posti_per_fila_default)

            file_necessarie = max(1, min(file_necessarie, 6))
            self.input_num_file.setText(str(file_necessarie))
            print(f"   📐 Auto-calcolo aula: {num_studenti} studenti → "
                  f"{file_necessarie} file × {posti_per_fila_default} posti "
                  f"= {file_necessarie * posti_per_fila_default} banchi")
        else:

            self.input_num_file.setText("4")

        self._aggiorna_posti_totali()

    def closeEvent(self, event):
        """Protegge i dati non salvati durante la chiusura dell’applicazione."""

        worker_mensile = getattr(self, 'worker_thread', None)
        worker_annuale = getattr(self, 'season_worker', None)

        mensile_in_corso = (
            worker_mensile is not None
            and worker_mensile.isRunning()
        )
        annuale_in_corso = (
            worker_annuale is not None
            and worker_annuale.isRunning()
        )

        if mensile_in_corso:
            mostra_popup_semantico(
                self,
                "Elaborazione in corso",
                "L'assegnazione Mensile è ancora in corso.",
                "triangle-alert",
                testo_informativo=(
                    "Per evitare un'interruzione brusca, la finestra non può "
                    "essere chiusa finché il calcolo non è terminato."
                ),
                messaggio_in_grassetto=True,
            )
            event.ignore()
            return

        if annuale_in_corso:

            if getattr(self, '_annullamento_richiesto', False):
                mostra_popup_semantico(
                    self,
                    "Annullamento in corso",
                    "L'annullamento è già stato richiesto.",
                    "info",
                    testo_informativo=(
                        "Attendi la conclusione del mese attualmente in calcolo; "
                        "poi potrai chiudere il programma in sicurezza."
                    ),
                    messaggio_in_grassetto=True,
                )
            else:
                dialog = crea_popup_semantico(
                    self,
                    "Elaborazione Annuale in corso",
                    "La preparazione Annuale è ancora in corso.",
                    "triangle-alert",
                    testo_informativo=(
                        "La finestra non verrà chiusa mentre il worker è attivo. "
                        "Puoi restare nel programma oppure richiedere un "
                        "annullamento controllato."
                    ),
                    messaggio_in_grassetto=True,
                )

                btn_annulla_elaborazione = dialog.addButton(
                    "Annulla elaborazione",
                    QMessageBox.DestructiveRole
                )
                btn_resta = dialog.addButton(
                    "Resta nel programma",
                    QMessageBox.RejectRole
                )
                applica_icona(btn_annulla_elaborazione, "circle-stop", 18)
                applica_stile_pulsante_popup(
                    btn_annulla_elaborazione, "distruttivo"
                )
                dialog.setDefaultButton(btn_resta)
                dialog.setEscapeButton(btn_resta)
                dialog.exec()

                if dialog.clickedButton() == btn_annulla_elaborazione:
                    self._annulla_annuale()

            event.ignore()
            return

        if hasattr(self, 'editor_studenti'):
            if not self.editor_studenti.richiedi_conferma_chiusura():

                event.ignore()
                return

        if self.assegnazione_non_salvata:
            dialog_chiudi = crea_popup_semantico(
                self,
                "Assegnazione non salvata",
                "L'ultima assegnazione non è stata salvata nello Storico.",
                "triangle-alert",
                testo_informativo=(
                    "Se chiudi ora, le vicinanze formate non verranno considerate "
                    "nelle rotazioni future.\n\n"
                    "Che cosa vuoi fare?"
                ),
                messaggio_in_grassetto=True,
            )

            btn_salva_chiudi = dialog_chiudi.addButton(
                "Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_esci_chiudi = dialog_chiudi.addButton(
                "Chiudi senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_chiudi = dialog_chiudi.addButton(
                "Annulla", QMessageBox.RejectRole
            )
            applica_icona(btn_salva_chiudi, "save", 18)
            applica_icona(btn_esci_chiudi, "trash-2", 18)
            applica_stile_pulsante_popup(
                btn_esci_chiudi, "distruttivo"
            )
            applica_icona(btn_annulla_chiudi, "x", 18)

            dialog_chiudi.setDefaultButton(btn_salva_chiudi)

            dialog_chiudi.setEscapeButton(btn_annulla_chiudi)

            dialog_chiudi.exec()

            bottone_chiudi = dialog_chiudi.clickedButton()

            if bottone_chiudi == btn_salva_chiudi:

                self.salva_assegnazione()

                if self.assegnazione_non_salvata:
                    event.ignore()
                    return

            elif bottone_chiudi == btn_annulla_chiudi:

                event.ignore()
                return

        self.config_app.salva_configurazione()

        event.accept()

# Avvio dell’applicazione

def main():
    """Crea l’applicazione Qt e avvia l’interfaccia principale."""

    app = QApplication(sys.argv)

    carica_font_emoji()

    app.setDesktopFileName("postiperfetti")

    filtro_cursore = FiltroCursoreManina(app)
    app.installEventFilter(filtro_cursore)

    percorso_icona = os.path.join(
        get_base_path(),
        "dati",
        "icone",
        "postiperfetti.ico"
    )
    if os.path.exists(percorso_icona):
        app.setWindowIcon(QIcon(percorso_icona))

    finestra = FinestraPostiPerfetti()
    finestra.showMaximized()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

