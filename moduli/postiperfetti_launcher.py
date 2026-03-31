#!/usr/bin/env python3
"""
Launcher per «PostiPerfetti» — Script di avvio con verifica ambiente.

COSA FA QUESTO SCRIPT:
1. Verifica che l'ambiente virtuale (.venv) esista
2. Verifica che le dipendenze necessarie (PySide6, openpyxl) siano installate
3. Se manca qualcosa, mostra un dialogo grafico e offre di installare/riparare
4. Avvia l'applicazione principale con il Python del venv

NOTA: Questo script viene eseguito con il Python di SISTEMA (non del venv),
perché il venv potrebbe non esistere ancora. Una volta verificato tutto,
lancia l'app con il Python del venv.
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path


# === CONFIGURAZIONE ===
# Percorsi relativi alla cartella del progetto (parent di "moduli/")
CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent
CARTELLA_VENV = CARTELLA_PROGETTO / ".venv"
FILE_PRINCIPALE = CARTELLA_PROGETTO / "postiperfetti.py"
PYTHON_VENV = CARTELLA_VENV / "bin" / "python3"
PIP_VENV = CARTELLA_VENV / "bin" / "pip"

# Dipendenze richieste: (nome_pacchetto_pip, nome_import_python)
DIPENDENZE = [
    ("PySide6", "PySide6"),
    ("XlsxWriter", "xlsxwriter"),
]


# =====================================================================
# SEZIONE 1: Sistema di dialoghi cross-platform
# =====================================================================

def _dialogo_kdialog(titolo, messaggio, tipo="info", si_no=False):
    """
    Mostra un dialogo usando kdialog (nativo KDE Plasma).
    Returns: True/False per si_no, None per info/errore.
    """
    try:
        if si_no:
            # --yesno restituisce 0 = Sì, 1 = No
            risultato = subprocess.run(
                ["kdialog", "--title", titolo, "--yesno", messaggio],
                capture_output=True
            )
            return risultato.returncode == 0
        elif tipo == "errore":
            subprocess.run(
                ["kdialog", "--title", titolo, "--error", messaggio],
                capture_output=True
            )
        elif tipo == "info":
            subprocess.run(
                ["kdialog", "--title", titolo, "--msgbox", messaggio],
                capture_output=True
            )
        return None
    except FileNotFoundError:
        raise RuntimeError("kdialog non disponibile")


def _dialogo_zenity(titolo, messaggio, tipo="info", si_no=False):
    """
    Mostra un dialogo usando zenity (GTK, disponibile su molti sistemi Linux).
    Returns: True/False per si_no, None per info/errore.
    """
    try:
        if si_no:
            risultato = subprocess.run(
                ["zenity", "--question", "--title", titolo, "--text", messaggio,
                 "--width", "400"],
                capture_output=True
            )
            return risultato.returncode == 0
        elif tipo == "errore":
            subprocess.run(
                ["zenity", "--error", "--title", titolo, "--text", messaggio,
                 "--width", "400"],
                capture_output=True
            )
        elif tipo == "info":
            subprocess.run(
                ["zenity", "--info", "--title", titolo, "--text", messaggio,
                 "--width", "400"],
                capture_output=True
            )
        return None
    except FileNotFoundError:
        raise RuntimeError("zenity non disponibile")


def _dialogo_tkinter(titolo, messaggio, tipo="info", si_no=False):
    """
    Mostra un dialogo usando tkinter (incluso in Python standard).
    Returns: True/False per si_no, None per info/errore.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox

        # Crea finestra root nascosta (necessaria per i dialoghi)
        root = tk.Tk()
        root.withdraw()

        if si_no:
            risposta = messagebox.askyesno(titolo, messaggio)
            root.destroy()
            return risposta
        elif tipo == "errore":
            messagebox.showerror(titolo, messaggio)
        elif tipo == "info":
            messagebox.showinfo(titolo, messaggio)

        root.destroy()
        return None
    except Exception:
        raise RuntimeError("tkinter non disponibile")


def _dialogo_terminale(titolo, messaggio, tipo="info", si_no=False):
    """
    Fallback finale: dialogo via terminale.
    Returns: True/False per si_no, None per info/errore.
    """
    print(f"\n{'=' * 60}")
    print(f"  {titolo}")
    print(f"{'=' * 60}")
    print(f"\n{messaggio}\n")

    if si_no:
        while True:
            risposta = input("Vuoi procedere? (s/n): ").strip().lower()
            if risposta in ("s", "si", "sì", "y", "yes"):
                return True
            elif risposta in ("n", "no"):
                return False
            print("Rispondi con 's' o 'n'.")
    else:
        input("Premi Invio per continuare...")
    return None


def mostra_dialogo(titolo, messaggio, tipo="info", si_no=False):
    """
    Mostra un dialogo grafico usando il metodo migliore disponibile.

    Strategia a cascata:
    1. kdialog (nativo KDE — ideale per Plasma)
    2. zenity (GTK — comune su molti Linux)
    3. tkinter (Python standard — quasi sempre disponibile)
    4. terminale (fallback universale)

    Args:
        titolo: Titolo della finestra
        messaggio: Testo del messaggio
        tipo: "info" o "errore"
        si_no: Se True, mostra dialogo Sì/No e restituisce True/False

    Returns:
        True/False per dialoghi si_no, None altrimenti
    """
    # Lista di metodi da provare in ordine di preferenza
    metodi = [
        ("kdialog", _dialogo_kdialog),
        ("zenity", _dialogo_zenity),
        ("tkinter", _dialogo_tkinter),
        ("terminale", _dialogo_terminale),
    ]

    for nome_metodo, funzione in metodi:
        try:
            return funzione(titolo, messaggio, tipo, si_no)
        except RuntimeError:
            continue  # Prova il metodo successivo
        except Exception as e:
            print(f"⚠️  Errore con {nome_metodo}: {e}")
            continue

    # Se TUTTO fallisce (improbabile), esce con errore
    print(f"ERRORE CRITICO: {messaggio}")
    sys.exit(1)


# =====================================================================
# SEZIONE 2: Gestione progress bar per installazione
# =====================================================================

def mostra_progresso_kdialog(comando, titolo="Installazione in corso..."):
    """
    Esegue un comando mostrando una progress bar kdialog.
    Se kdialog non è disponibile, esegue normalmente nel terminale.

    Args:
        comando: Lista di stringhe per subprocess
        titolo: Titolo della finestra di progresso

    Returns:
        True se il comando è riuscito, False altrimenti
    """
    # Prova con kdialog --progressbar
    if shutil.which("kdialog"):
        try:
            # Apri progress bar indeterminata
            proc_dialog = subprocess.Popen(
                ["kdialog", "--title", titolo, "--progressbar", "Attendere...", "0"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # Leggi il riferimento DBus della progress bar
            dbus_ref = proc_dialog.stdout.readline().strip()

            # Esegui il comando reale
            risultato = subprocess.run(
                comando,
                capture_output=True, text=True
            )

            # Chiudi la progress bar via DBus (qdbus o qdbus6)
            qdbus_cmd = "qdbus6" if shutil.which("qdbus6") else "qdbus"
            if dbus_ref and shutil.which(qdbus_cmd):
                subprocess.run(
                    [qdbus_cmd, dbus_ref, "/ProgressDialog", "close"],
                    capture_output=True
                )

            return risultato.returncode == 0

        except Exception:
            pass  # Fallback sotto

    # Fallback: esegui nel terminale con output visibile
    print(f"\n⏳ {titolo}")
    risultato = subprocess.run(comando)
    return risultato.returncode == 0


# =====================================================================
# SEZIONE 3: Verifica e creazione ambiente virtuale
# =====================================================================

def venv_esiste():
    """
    Verifica che l'ambiente virtuale esista e sia funzionante.

    Returns:
        True se il venv esiste e contiene python3 e pip
    """
    return PYTHON_VENV.is_file() and PIP_VENV.is_file()


def crea_venv():
    """
    Crea l'ambiente virtuale da zero.

    Returns:
        True se la creazione è riuscita
    """
    print(f"📦 Creazione ambiente virtuale in {CARTELLA_VENV}...")

    # Rimuovi venv corrotto se esiste
    if CARTELLA_VENV.exists():
        print("   🗑️  Rimozione venv corrotto...")
        shutil.rmtree(CARTELLA_VENV)

    # Crea nuovo venv
    successo = mostra_progresso_kdialog(
        [sys.executable, "-m", "venv", str(CARTELLA_VENV)],
        titolo="Creazione ambiente virtuale..."
    )

    if successo:
        print("   ✅ Ambiente virtuale creato con successo")
    else:
        print("   ❌ Errore nella creazione del venv")

    return successo


# =====================================================================
# SEZIONE 4: Verifica e installazione dipendenze
# =====================================================================

def verifica_dipendenza(nome_import):
    """
    Verifica se un pacchetto Python è importabile nel venv.

    Args:
        nome_import: Nome del modulo da importare (es: "PySide6")

    Returns:
        True se il modulo è disponibile nel venv
    """
    risultato = subprocess.run(
        [str(PYTHON_VENV), "-c", f"import {nome_import}"],
        capture_output=True
    )
    return risultato.returncode == 0


def verifica_tutte_dipendenze():
    """
    Verifica tutte le dipendenze necessarie.

    Returns:
        Lista di tuple (nome_pip, nome_import) delle dipendenze mancanti
    """
    mancanti = []
    for nome_pip, nome_import in DIPENDENZE:
        if verifica_dipendenza(nome_import):
            print(f"   ✅ {nome_pip} — installato")
        else:
            print(f"   ❌ {nome_pip} — MANCANTE")
            mancanti.append((nome_pip, nome_import))
    return mancanti


def installa_dipendenze(mancanti):
    """
    Installa le dipendenze mancanti nel venv.

    Args:
        mancanti: Lista di tuple (nome_pip, nome_import) da installare

    Returns:
        True se l'installazione è riuscita
    """
    nomi_pip = [nome for nome, _ in mancanti]
    elenco_nomi = ", ".join(nomi_pip)

    print(f"📥 Installazione dipendenze: {elenco_nomi}...")

    successo = mostra_progresso_kdialog(
        [str(PIP_VENV), "install"] + nomi_pip,
        titolo=f"Installazione {elenco_nomi}..."
    )

    if successo:
        print(f"   ✅ Dipendenze installate con successo")
    else:
        print(f"   ❌ Errore nell'installazione")

    return successo


# =====================================================================
# SEZIONE 5: Avvio applicazione principale
# =====================================================================

def avvia_applicazione():
    """
    Avvia l'applicazione principale usando il Python del venv.
    Sostituisce il processo corrente (exec) per non lasciare
    il launcher in memoria.
    """
    print(f"\n🚀 Avvio «PostiPerfetti»...")
    print(f"   Python: {PYTHON_VENV}")
    print(f"   Script: {FILE_PRINCIPALE}")

    # os.execv sostituisce il processo corrente con l'app
    # così il launcher non resta in memoria
    os.execv(
        str(PYTHON_VENV),
        [str(PYTHON_VENV), str(FILE_PRINCIPALE)]
    )


# =====================================================================
# SEZIONE 6: Flusso principale
# =====================================================================

def main():
    """
    Flusso principale del launcher:
    1. Verifica che il file principale esista
    2. Verifica/crea il venv
    3. Verifica/installa le dipendenze
    4. Avvia l'applicazione
    """
    print("=" * 50)
    print("🎓 Launcher «PostiPerfetti»")
    print("=" * 50)
    print(f"📁 Cartella progetto: {CARTELLA_PROGETTO}")

    # --- STEP 1: Verifica che il file principale esista ---
    if not FILE_PRINCIPALE.is_file():
        mostra_dialogo(
            "Errore — «PostiPerfetti»",
            f"File principale non trovato:\n{FILE_PRINCIPALE}\n\n"
            f"Verifica che il progetto sia nella cartella corretta.",
            tipo="errore"
        )
        sys.exit(1)

    # --- STEP 2: Verifica ambiente virtuale ---
    print(f"\n🔍 Verifica ambiente virtuale...")

    if not venv_esiste():
        print("   ⚠️  Ambiente virtuale non trovato o corrotto")

        risposta = mostra_dialogo(
            "Ambiente virtuale mancante — «PostiPerfetti»",
            "L'ambiente virtuale (.venv) non è stato trovato "
            "o risulta corrotto.\n\n"
            "È necessario per eseguire l'applicazione.\n"
            "Vuoi crearlo adesso?\n\n"
            "(Richiede connessione a internet per scaricare le dipendenze)",
            si_no=True
        )

        if not risposta:
            print("   ⏹️  Operazione annullata dall'utente")
            sys.exit(0)

        # Crea il venv
        if not crea_venv():
            mostra_dialogo(
                "Errore — «PostiPerfetti»",
                "Impossibile creare l'ambiente virtuale.\n\n"
                "Verifica che python3-venv sia installato:\n"
                "  sudo pacman -S python\n\n"
                "Oppure prova a creare il venv manualmente:\n"
                f"  python3 -m venv {CARTELLA_VENV}",
                tipo="errore"
            )
            sys.exit(1)
    else:
        print("   ✅ Ambiente virtuale trovato")

    # --- STEP 3: Verifica dipendenze ---
    print(f"\n🔍 Verifica dipendenze...")
    mancanti = verifica_tutte_dipendenze()

    if mancanti:
        nomi_mancanti = ", ".join(nome for nome, _ in mancanti)

        risposta = mostra_dialogo(
            "Dipendenze mancanti — «PostiPerfetti»",
            f"Le seguenti dipendenze sono mancanti:\n\n"
            f"  • {chr(10) + '  • '.join(nome for nome, _ in mancanti)}\n\n"
            f"Vuoi installarle adesso?\n\n"
            f"(Richiede connessione a internet)",
            si_no=True
        )

        if not risposta:
            print("   ⏹️  Operazione annullata dall'utente")
            sys.exit(0)

        # Installa le dipendenze
        if not installa_dipendenze(mancanti):
            mostra_dialogo(
                "Errore — «PostiPerfetti»",
                f"Impossibile installare le dipendenze: {nomi_mancanti}\n\n"
                "Verifica la connessione a internet e riprova.\n\n"
                "Puoi anche installarle manualmente:\n"
                f"  {PIP_VENV} install {nomi_mancanti}",
                tipo="errore"
            )
            sys.exit(1)

        # Verifica post-installazione
        ancora_mancanti = verifica_tutte_dipendenze()
        if ancora_mancanti:
            nomi_ancora = ", ".join(nome for nome, _ in ancora_mancanti)
            mostra_dialogo(
                "Errore — «PostiPerfetti»",
                f"L'installazione si è completata ma queste dipendenze\n"
                f"risultano ancora mancanti:\n\n  {nomi_ancora}\n\n"
                f"Prova a installarle manualmente:\n"
                f"  {PIP_VENV} install {nomi_ancora}",
                tipo="errore"
            )
            sys.exit(1)

    # --- STEP 4: Tutto ok, avvia l'applicazione ---
    print("\n✅ Tutte le verifiche superate!")
    avvia_applicazione()


if __name__ == "__main__":
    main()
