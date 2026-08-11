# -*- coding: utf-8 -*-

"""Interfaccia principale e coordinamento dei flussi di «PostiPerfetti».

Gestisce assegnazioni mensili e annuali, modalità a coppie e terzetti,
anteprime, salvataggio e integrazione dei moduli dell’applicazione.

Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3."""

import sys

# Necessario nelle build PyInstaller che usano multiprocessing con start
# method "spawn" (Windows e processi congelati). In esecuzione normale è
# innocuo; nella build frozen evita che i processi figli riavviino la GUI.
if __name__ == "__main__":
    import multiprocessing as _multiprocessing
    _multiprocessing.freeze_support()

sys.dont_write_bytecode = True
import os
from moduli.versione import VERSIONE

# Esperimento diagnostico, inattivo per impostazione predefinita.
# Consente di verificare se la responsività della GUI durante i calcoli
# CPU-bound dipende dalla frequenza con cui l'interprete cede il GIL.
_intervallo_switch = os.environ.get(
    "POSTIPERFETTI_PY_SWITCH_INTERVAL",
    "",
).strip()
if _intervallo_switch:
    try:
        _intervallo_switch_valore = float(_intervallo_switch)
        if not 0.0001 <= _intervallo_switch_valore <= 0.05:
            raise ValueError(
                "l'intervallo deve essere compreso fra 0.0001 e 0.05 s"
            )
        sys.setswitchinterval(_intervallo_switch_valore)
    except (TypeError, ValueError) as errore:
        print(
            "POSTIPERFETTI_PY_SWITCH_INTERVAL ignorato: "
            f"{errore}",
            file=sys.stderr,
        )

# Output e gestione degli errori
# In produzione stdout viene scartato; stderr resta disponibile per i traceback.
#
# La variabile d'ambiente POSTIPERFETTI_VERBOSE riapre stdout quando serve
# diagnosticare un problema da terminale, senza cambiare nulla per chi avvia
# il programma normalmente da icona o da menu.
#
#   Linux:   POSTIPERFETTI_VERBOSE=1 ~/PostiPerfetti/moduli/postiperfetti_launcher.py
#   Windows: set POSTIPERFETTI_VERBOSE=1  &&  PostiPerfetti.exe
_VERBOSE_RICHIESTO = os.environ.get(
    "POSTIPERFETTI_VERBOSE", ""
).strip().lower() in {"1", "true", "si", "sì", "yes", "on"}

MODALITA_SILENZIOSA = not _VERBOSE_RICHIESTO

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
            from moduli.percorsi import get_log_path
            percorso_log = get_log_path(
                "crash.log",
                crea_genitori=True,
            )
        except Exception:
            # Fallback estremo: se perfino il modulo dei percorsi non fosse
            # importabile, conserva il traceback accanto allo script.
            percorso_log = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "crash.log",
            )

        with open(percorso_log, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"CRASH {_dt.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Versione PostiPerfetti: {VERSIONE}\n")
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

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QIcon, QFontDatabase

from moduli.stato_sessione import StatoSessione

from moduli.tema import imposta_tema
from moduli.percorsi import get_resource_path, get_state_path
from moduli.watchdog_gui import avvia_watchdog_gui_da_ambiente

from moduli.utilita import (
    FiltroCursoreManina,
    adatta_finestra_allo_schermo,
)
from moduli.configurazione import ConfigurazioneApp

from moduli.statistiche import StatisticheMixin

from moduli.stili import StiliMixin
from moduli.pannelli_principali import PannelliPrincipaliMixin
from moduli.configurazione_aula_ui import ConfigurazioneAulaUIMixin
from moduli.risultato_corrente_ui import RisultatoCorrenteUIMixin
from moduli.sessione_classe_ui import SessioneClasseUIMixin
from moduli.flusso_mensile_ui import FlussoMensileUIMixin
from moduli.flusso_annuale_ui import FlussoAnnualeUIMixin
from moduli.salvataggio_mensile_ui import SalvataggioMensileUIMixin
from moduli.ciclo_vita_ui import CicloVitaUIMixin

from moduli.esportazione import EsportazioneMixin

from moduli.storico_ui import StoricoUIMixin


def _acquisisci_lock_istanza():
    """Impedisce a due processi di usare contemporaneamente lo stesso stato.

    Il lock resta attivo per l'intera vita dell'applicazione. Un eventuale
    lock lasciato da un processo terminato in modo anomalo viene riconosciuto
    da QLockFile tramite le informazioni del processo proprietario.
    """
    try:
        percorso_lock = get_state_path(
            "postiperfetti.lock",
            crea_genitori=True,
        )
    except OSError as errore:
        QMessageBox.critical(
            None,
            "PostiPerfetti — impossibile avviare",
            "Non è stato possibile preparare la protezione dello Storico.\n\n"
            "PostiPerfetti non verrà avviato, per evitare il rischio di "
            "scritture concorrenti o perdita di dati.\n\n"
            f"Dettaglio tecnico:\n{errore}",
        )
        return None

    lock = QLockFile(percorso_lock)

    # È un lock di lunga durata: non deve diventare «vecchio» soltanto
    # perché PostiPerfetti rimane aperto per molto tempo.
    lock.setStaleLockTime(0)

    # Una breve attesa evita falsi negativi durante due avvii quasi simultanei,
    # senza rendere percepibilmente più lento l'avvio normale.
    if lock.tryLock(250):
        return lock

    errore = lock.error()

    if errore == QLockFile.LockError.LockFailedError:
        QMessageBox.information(
            None,
            "PostiPerfetti è già aperto",
            "Un'altra istanza di PostiPerfetti risulta già in esecuzione.\n\n"
            "Per proteggere lo Storico e le rotazioni non è possibile "
            "aprire contemporaneamente due finestre che utilizzano gli "
            "stessi dati.\n\n"
            "Usa la finestra già aperta oppure chiudila prima di riavviare "
            "il programma.",
        )
        return None

    if errore == QLockFile.LockError.PermissionError:
        dettaglio = (
            "Non è possibile creare il file di protezione nella cartella "
            "dello stato. Controlla i permessi della directory."
        )
    else:
        dettaglio = (
            "Si è verificato un errore imprevisto durante la creazione del "
            "file di protezione."
        )

    QMessageBox.critical(
        None,
        "PostiPerfetti — impossibile avviare",
        "Non è stato possibile proteggere lo Storico da accessi concorrenti.\n\n"
        "PostiPerfetti non verrà avviato, per evitare il rischio di perdita "
        "di dati.\n\n"
        f"{dettaglio}\n\n"
        f"File di lock:\n{percorso_lock}",
    )
    return None


def carica_font_emoji():
    percorso = get_resource_path(
        "font",
        "NotoColorEmoji.ttf",
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




# Generazione mensile e annuale


# Worker di calcolo



# Anteprima e accettazione delle stagioni


# Interfaccia principale

class FinestraPostiPerfetti(
        QMainWindow, CicloVitaUIMixin,
        PannelliPrincipaliMixin, SessioneClasseUIMixin,
        ConfigurazioneAulaUIMixin, RisultatoCorrenteUIMixin,
        FlussoMensileUIMixin, FlussoAnnualeUIMixin,
        SalvataggioMensileUIMixin,
        StatisticheMixin, StiliMixin, EsportazioneMixin, StoricoUIMixin):
    """Coordina l’interfaccia principale e i flussi dell’applicazione."""

    DEFAULT_MESI_ANNUALE = 10
    DEFAULT_POSTI_PER_FILA_COPPIE = 6
    DEFAULT_NUM_FILE_SENZA_CLASSE = 4
    DEFAULT_POSIZIONE_RESTO = {
        'coppie': 'centro',
        'terzetti': 'ultima',
    }

    def closeEvent(self, event):
        """Inoltra la chiusura al gestore protettivo del mixin.

        ``QMainWindow`` precede ``CicloVitaUIMixin`` nella MRO; senza questo
        override esplicito, l'implementazione Qt omonima intercetta l'evento e
        la protezione di calcoli e dati non viene mai eseguita.
        """
        return CicloVitaUIMixin.closeEvent(self, event)

    def __init__(self):
        super().__init__()

        self.config_app = ConfigurazioneApp()
        self.config_app.carica_configurazione()

        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        self.sessione = StatoSessione()

        self._precedenti_altro_modo = 0

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

        self.config_app.gestore_file_assente = (
            self._chiedi_azione_file_config_assente
        )
        self.config_app.gestore_azzeramento_completato = (
            self._dopo_azzeramento_storico_e_rotazioni
        )

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





































# Avvio dell’applicazione

def main():
    """Crea l’applicazione Qt e avvia l’interfaccia principale."""

    app = QApplication(sys.argv)
    app.setApplicationName("PostiPerfetti")
    app.setApplicationVersion(VERSIONE)

    lock_istanza = _acquisisci_lock_istanza()
    if lock_istanza is None:
        return

    # In una chiusura normale il file viene rimosso esplicitamente.
    app.aboutToQuit.connect(lock_istanza.unlock)

    carica_font_emoji()

    app.setDesktopFileName("postiperfetti")

    filtro_cursore = FiltroCursoreManina(app)
    app.installEventFilter(filtro_cursore)

    percorso_icona = get_resource_path(
        "icone",
        "postiperfetti_icon.png",
    )
    if os.path.exists(percorso_icona):
        app.setWindowIcon(QIcon(percorso_icona))

    finestra = FinestraPostiPerfetti()
    finestra.showMaximized()

    watchdog_gui = avvia_watchdog_gui_da_ambiente(app, finestra)
    if watchdog_gui is not None:
        finestra._watchdog_gui = watchdog_gui
        app.aboutToQuit.connect(watchdog_gui.stop)
        QTimer.singleShot(0, watchdog_gui.start)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

