#!/usr/bin/env python3
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""
Launcher per «PostiPerfetti» — Script di avvio con verifica ambiente.

COSA FA QUESTO SCRIPT:
1. Verifica che l'ambiente virtuale (.venv) sia realmente utilizzabile
2. Verifica Python, requirements, versioni esatte, pip e import runtime
3. Se l'ambiente si è danneggiato dopo l'installazione, offre di ripararlo
4. Avvia l'applicazione principale con il Python del venv

NOTA: Questo script viene eseguito con il Python di SISTEMA (non del venv),
perché il venv potrebbe non esistere ancora. Una volta verificato tutto,
lancia l'app con il Python del venv.
"""

import sys
import os
import subprocess
import shutil
import tempfile
from pathlib import Path


# === CONFIGURAZIONE ===
# Percorsi relativi alla cartella del progetto (parent di "moduli/")
CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent
CARTELLA_VENV = CARTELLA_PROGETTO / ".venv"
FILE_PRINCIPALE = CARTELLA_PROGETTO / "postiperfetti.py"
PYTHON_VENV = CARTELLA_VENV / "bin" / "python3"

# Fonte unica delle dipendenze runtime e delle loro versioni.
# In una release valida ogni requisito deve essere congelato con «==».
# Se il file manca o non rispetta questo contratto, il launcher NON
# inventa dipendenze alternative: considera l'installazione danneggiata.
FILE_REQUIREMENTS = CARTELLA_PROGETTO / "requirements.txt"


# =====================================================================
# SEZIONE 0: Rilevamento del contesto di esecuzione
# =====================================================================

def in_terminale():
    """
    Indica se il launcher è attaccato a un terminale interattivo.

    True  → siamo in un terminale (l'utente ci ha lanciato da console,
            oppure ci siamo rilanciati noi dentro un terminale).
            In questo caso il feedback e le domande vanno nel TERMINALE.
    False → nessun terminale (avvio dal menu delle applicazioni con
            Terminal=false). Qui NON possiamo scrivere a schermo.

    Usa os.isatty() sul descrittore dello standard input: è nella
    libreria standard di Python, non dipende da alcun desktop e
    funziona identico su ogni sistema Linux.
    """
    try:
        return os.isatty(sys.stdin.fileno())
    except Exception:
        # In casi limite (stdin non disponibile) assumiamo "no terminale":
        # è l'ipotesi prudente, che evita di scrivere dove nessuno legge.
        return False


# =====================================================================
# SEZIONE 1: Sistema di dialoghi cross-platform
# =====================================================================

def chiedi_conferma_terminale(domanda):
    """
    Pone una domanda Sì/No direttamente nel terminale.

    Da usare SOLO quando in_terminale() è True: mostra la domanda
    testualmente e attende la risposta dell'utente, senza alcun
    dialogo grafico. Universale, senza dipendenze esterne.

    Il default (solo Invio) è "Sì" [S/n], coerente con l'installer:
    l'azione più probabile (procedere) è a portata di un tasto.

    Returns: True se l'utente conferma, False altrimenti.
    """
    try:
        # input() attende la risposta; strip() toglie spazi, lower()
        # rende indifferente maiuscolo/minuscolo.
        risposta = input(f"{domanda} [S/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Se l'utente preme Ctrl-D o Ctrl-C, interpretiamo come "No":
        # nel dubbio non procediamo con operazioni che scaricano da rete.
        print()  # a capo pulito dopo l'interruzione
        return False
    # Stringa vuota (solo Invio) o un "sì" esplicito → conferma.
    return risposta in ("", "s", "si", "sì", "y", "yes")


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

def esegui_con_progresso(comando, titolo="Installazione in corso..."):
    """
    Esegue un comando (es. pip) mostrandone l'output IN DIRETTA nel
    terminale, incorniciato tra due messaggi chiari e rassicuranti.

    Perché così (Opzione C):
    - l'output di pip scorre a schermo → l'utente VEDE che il lavoro
      procede (niente sensazione di blocco durante il download, lungo,
      di PySide6);
    - i due messaggi di cornice spiegano cosa sta succedendo, così il
      testo tecnico di pip non spaventa chi non è programmatore;
    - NESSUNA finestra grafica (kdialog eliminato): niente più notifiche
      appese, niente dipendenza da qdbus, comportamento identico su ogni
      desktop. Il flusso garantisce sempre un terminale (Passo C).

    Nota: NON usiamo capture_output. Lasciando che pip scriva
    direttamente nel terminale, un eventuale errore (rete che cade)
    appare da sé sotto gli occhi dell'utente, senza doverlo ricatturare.

    Args:
        comando: Lista di stringhe per subprocess
        titolo: Etichetta dell'operazione (mostrata nella cornice)

    Returns:
        True se il comando è riuscito (codice 0), False altrimenti
    """
    # --- Messaggio di apertura: prepara e rassicura -----------------
    print()
    print(f"📥 {titolo}")
    print("   Sto scaricando e installando le librerie necessarie.")
    print("   Può richiedere qualche minuto: è del tutto normale.")
    print("   Qui sotto vedrai scorrere del testo tecnico — lascialo lavorare.")
    print("   " + "─" * 55)

    # --- Esecuzione con output IN DIRETTA ---------------------------
    # Senza capture_output, stdout/stderr di pip vanno al terminale.
    # subprocess.run BLOCCA fino al termine: quando pip finisce, prosegue.
    try:
        risultato = subprocess.run(comando)
        successo = (risultato.returncode == 0)
    except Exception as errore:
        print(f"   ⚠️  Errore nell'avvio del comando: {errore}")
        successo = False

    # --- Messaggio di chiusura --------------------------------------
    print("   " + "─" * 55)
    if successo:
        print("   ✅ Operazione completata.")
    else:
        print("   ❌ L'operazione non è riuscita (vedi i messaggi qui sopra).")

    return successo


# =====================================================================
# SEZIONE 3: Verifica e creazione ambiente virtuale
# =====================================================================

def versione_python_compatibile(eseguibile):
    """Verifica il contratto Python della release: >= 3.10 e < 3.15."""
    try:
        risultato = subprocess.run(
            [
                str(eseguibile),
                "-c",
                (
                    "import sys; "
                    "raise SystemExit("
                    "0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 1"
                    ")"
                ),
            ],
            capture_output=True,
        )
    except OSError:
        return False

    return risultato.returncode == 0


def venv_funzionante():
    """Verifica che il venv sia realmente eseguibile e dotato di pip."""
    if not PYTHON_VENV.is_file():
        return False

    if not versione_python_compatibile(PYTHON_VENV):
        return False

    try:
        risultato = subprocess.run(
            [str(PYTHON_VENV), "-m", "pip", "--version"],
            capture_output=True,
        )
    except OSError:
        return False

    return risultato.returncode == 0


def leggi_requirements_bloccati():
    """Legge requirements.txt imponendo il formato «pacchetto==versione».

    Returns:
        (requisiti, errori)

        requisiti:
            lista di tuple (nome_pacchetto, versione_attesa)

        errori:
            lista di descrizioni; vuota se il file rispetta il contratto
    """
    if not FILE_REQUIREMENTS.is_file():
        return [], [
            f"requirements.txt non trovato: {FILE_REQUIREMENTS}"
        ]

    requisiti = []
    errori = []

    try:
        righe = FILE_REQUIREMENTS.read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as errore:
        return [], [
            f"impossibile leggere requirements.txt: {errore}"
        ]

    for numero, riga_grezza in enumerate(righe, start=1):
        riga = riga_grezza.split("#", 1)[0].strip()

        if not riga:
            continue

        parti = riga.split("==")

        if len(parti) != 2:
            errori.append(
                f"riga {numero}: requisito non congelato con ==: {riga!r}"
            )
            continue

        nome = parti[0].strip()
        versione_attesa = parti[1].strip()

        if not nome or not versione_attesa:
            errori.append(
                f"riga {numero}: requisito non valido: {riga!r}"
            )
            continue

        requisiti.append((nome, versione_attesa))

    if not requisiti and not errori:
        errori.append(
            "requirements.txt non contiene dipendenze runtime"
        )

    return requisiti, errori


def problemi_ambiente():
    """Restituisce i problemi che impediscono un avvio affidabile.

    La verifica è silenziosa ed è usata anche per decidere se il launcher
    debba aprire un terminale per eseguire una riparazione.
    """
    requisiti, errori_requirements = leggi_requirements_bloccati()

    if errori_requirements:
        return errori_requirements

    if not venv_funzionante():
        return [
            "ambiente virtuale assente, corrotto oppure con una "
            "versione di Python non compatibile"
        ]

    problemi = []

    # importlib.metadata interroga le versioni realmente installate nel venv.
    script_versione = (
        "from importlib.metadata import PackageNotFoundError, version; "
        "import sys; "
        "nome, attesa = sys.argv[1], sys.argv[2]; "
        "\ntry:\n"
        "    installata = version(nome)\n"
        "except PackageNotFoundError:\n"
        "    raise SystemExit(2)\n"
        "raise SystemExit(0 if installata == attesa else 1)"
    )

    for nome, versione_attesa in requisiti:
        try:
            risultato = subprocess.run(
                [
                    str(PYTHON_VENV),
                    "-c",
                    script_versione,
                    nome,
                    versione_attesa,
                ],
                capture_output=True,
            )
        except OSError:
            problemi.append(
                f"{nome}: impossibile interrogare il Python del venv"
            )
            continue

        if risultato.returncode == 2:
            problemi.append(
                f"{nome}: non installato "
                f"(richiesta versione {versione_attesa})"
            )
        elif risultato.returncode != 0:
            # Recuperiamo la versione effettiva per dare una diagnosi utile.
            try:
                versione_reale = subprocess.run(
                    [
                        str(PYTHON_VENV),
                        "-c",
                        (
                            "from importlib.metadata import version; "
                            "import sys; print(version(sys.argv[1]))"
                        ),
                        nome,
                    ],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            except OSError:
                versione_reale = "sconosciuta"

            problemi.append(
                f"{nome}: installata {versione_reale or 'sconosciuta'}, "
                f"richiesta {versione_attesa}"
            )

    # pip check individua dipendenze interne mancanti o incompatibili.
    try:
        controllo_pip = subprocess.run(
            [str(PYTHON_VENV), "-m", "pip", "check"],
            capture_output=True,
            text=True,
        )
    except OSError:
        controllo_pip = None

    if controllo_pip is None:
        problemi.append("impossibile eseguire «pip check»")
    elif controllo_pip.returncode != 0:
        dettaglio = (
            controllo_pip.stdout.strip()
            or controllo_pip.stderr.strip()
            or "incompatibilità non specificata"
        )
        problemi.append(
            f"pip segnala dipendenze incoerenti: {dettaglio}"
        )

    # Ultimo controllo funzionale: i moduli usati direttamente
    # dall'applicazione devono essere realmente importabili.
    try:
        controllo_import = subprocess.run(
            [
                str(PYTHON_VENV),
                "-c",
                "import PySide6, xlsxwriter",
            ],
            capture_output=True,
            text=True,
        )
    except OSError:
        controllo_import = None

    if controllo_import is None:
        problemi.append(
            "impossibile verificare gli import runtime"
        )
    elif controllo_import.returncode != 0:
        problemi.append(
            "PySide6 o XlsxWriter non risultano importabili"
        )

    return problemi


def ambiente_incompleto():
    """True se l'ambiente richiede una riparazione."""
    return bool(problemi_ambiente())


def venv_esiste():
    """True soltanto se il venv è realmente utilizzabile."""
    return venv_funzionante()


def crea_venv():
    """Ricrea da zero l'ambiente virtuale.

    Usa il Python di sistema che sta eseguendo il launcher, ma soltanto
    se appartiene all'intervallo supportato dalla release.
    """
    print(f"📦 Creazione ambiente virtuale in {CARTELLA_VENV}...")

    if not versione_python_compatibile(sys.executable):
        versione = (
            f"{sys.version_info.major}."
            f"{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        print(
            "   ❌ Il Python di sistema non è compatibile "
            f"con questa release: {versione}"
        )
        print("   Sono supportate le versioni Python da 3.10 a 3.14.")
        return False

    # Solo dopo aver verificato che possiamo ricrearlo eliminiamo
    # un eventuale ambiente già danneggiato.
    if CARTELLA_VENV.exists():
        print("   🗑️  Rimozione venv non utilizzabile...")
        try:
            shutil.rmtree(CARTELLA_VENV)
        except OSError as errore:
            print(f"   ❌ Impossibile rimuovere il vecchio venv: {errore}")
            return False

    successo = esegui_con_progresso(
        [sys.executable, "-m", "venv", str(CARTELLA_VENV)],
        titolo="Creazione ambiente virtuale...",
    )

    if not successo:
        print("   ❌ Errore nella creazione del venv")
        return False

    if not venv_funzionante():
        print(
            "   ❌ Il venv è stato creato, ma Python o pip "
            "non risultano utilizzabili"
        )
        return False

    print("   ✅ Ambiente virtuale creato con successo")
    return True


# =====================================================================
# SEZIONE 4: Verifica e riparazione delle dipendenze
# =====================================================================

def installa_dipendenze():
    """Riconcilia il venv con requirements.txt.

    requirements.txt è obbligatorio e deve contenere esclusivamente
    dipendenze runtime congelate con «==». Non esiste alcun fallback
    non versionato.
    """
    requisiti, errori = leggi_requirements_bloccati()

    if errori:
        print("   ❌ requirements.txt non è utilizzabile:")
        for errore in errori:
            print(f"      • {errore}")
        return False

    elenco = ", ".join(
        f"{nome}=={versione}"
        for nome, versione in requisiti
    )

    print(f"   Versioni richieste: {elenco}")

    comando_pip = [
        str(PYTHON_VENV),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(FILE_REQUIREMENTS),
    ]

    successo = esegui_con_progresso(
        comando_pip,
        titolo="Riparazione dipendenze da requirements.txt...",
    )

    if not successo:
        print("   ❌ Errore nell'installazione delle dipendenze")
        return False

    problemi = problemi_ambiente()

    if problemi:
        print(
            "   ❌ La riparazione si è conclusa, "
            "ma l'ambiente non è ancora coerente:"
        )
        for problema in problemi:
            print(f"      • {problema}")
        return False

    print("   ✅ Dipendenze installate e verificate")
    return True


# =====================================================================
# SEZIONE 5: Avvio applicazione principale
# =====================================================================

def avvia_applicazione():
    """Avvia PostiPerfetti come processo indipendente.

    Per circa due secondi cattura stderr in un file temporaneo, così un
    eventuale crash immediato di Python, Qt o di una libreria nativa
    conserva la vera diagnostica.

    Se l'applicazione resta viva, il file temporaneo viene eliminato e
    non viene conservato alcun log di avvio permanente.
    """
    print("\n🚀 Avvio «PostiPerfetti»...")

    cartella_log = CARTELLA_PROGETTO / "log"
    file_diagnostica = cartella_log / "diagnostica_avvio.log"

    try:
        cartella_log.mkdir(parents=True, exist_ok=True)
    except OSError:
        # L'impossibilità di creare il log non deve, da sola,
        # impedire l'avvio dell'applicazione.
        pass

    # Una vecchia diagnosi non deve essere scambiata per il problema
    # dell'avvio corrente.
    try:
        file_diagnostica.unlink(missing_ok=True)
    except OSError:
        pass

    try:
        stderr_temporaneo = tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".postiperfetti-avvio-",
            suffix=".log",
            dir=cartella_log if cartella_log.is_dir() else None,
            delete=False,
        )
    except OSError:
        stderr_temporaneo = tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=".postiperfetti-avvio-",
            suffix=".log",
            delete=False,
        )

    percorso_temporaneo = Path(stderr_temporaneo.name)

    try:
        processo_app = subprocess.Popen(
            [str(PYTHON_VENV), str(FILE_PRINCIPALE)],
            start_new_session=True,
            stderr=stderr_temporaneo,
        )
    except Exception as errore:
        stderr_temporaneo.close()

        try:
            percorso_temporaneo.unlink(missing_ok=True)
        except OSError:
            pass

        messaggio = f"Impossibile avviare il programma:\n{errore}"

        if in_terminale():
            print(f"\n❌ {messaggio}")
        else:
            mostra_dialogo(
                "Errore — «PostiPerfetti»",
                messaggio,
                tipo="errore",
            )

        sys.exit(1)

    try:
        codice = processo_app.wait(timeout=2)

    except subprocess.TimeoutExpired:
        # Caso normale: dopo due secondi l'applicazione è ancora viva.
        #
        # Chiudiamo la nostra copia del descrittore e cancelliamo il nome
        # del file temporaneo. Su Linux il processo figlio può continuare
        # a usare il descrittore già aperto, ma non resta alcun file di
        # diagnostica visibile sul disco dopo un avvio riuscito.
        stderr_temporaneo.close()

        try:
            percorso_temporaneo.unlink(missing_ok=True)
        except OSError:
            pass

        if in_terminale():
            print(
                "   ✅ Programma avviato. "
                "Puoi chiudere questo terminale."
            )

        sys.exit(0)

    # Se arriviamo qui, il processo si è già chiuso entro i due secondi.
    stderr_temporaneo.close()

    try:
        dati_stderr = percorso_temporaneo.read_bytes()
    except OSError:
        dati_stderr = b""

    try:
        percorso_temporaneo.unlink(missing_ok=True)
    except OSError:
        pass

    # Un'uscita immediata ma regolare non è un crash.
    if codice == 0:
        sys.exit(0)

    # Limitiamo la diagnostica a 64 KiB: ci interessano gli errori
    # dell'avvio, non creare un sistema generale di logging.
    limite = 64 * 1024
    stderr_troncato = len(dati_stderr) > limite

    if stderr_troncato:
        dati_stderr = dati_stderr[-limite:]

    dettaglio_stderr = dati_stderr.decode(
        "utf-8",
        errors="replace",
    ).strip()

    if codice < 0:
        descrizione_uscita = (
            f"terminazione tramite segnale {-codice}"
        )
    else:
        descrizione_uscita = f"codice di uscita {codice}"

    righe_log = [
        "Diagnostica avvio «PostiPerfetti»",
        "=================================",
        "",
        f"Esito: {descrizione_uscita}",
        "",
        "--- stderr iniziale ---",
    ]

    if stderr_troncato:
        righe_log.extend([
            "(output molto lungo: conservati soltanto gli ultimi 64 KiB)",
            "",
        ])

    righe_log.append(
        dettaglio_stderr
        if dettaglio_stderr
        else "(nessun messaggio ricevuto su stderr)"
    )

    testo_log = "\n".join(righe_log) + "\n"

    log_salvato = False

    try:
        cartella_log.mkdir(parents=True, exist_ok=True)
        file_diagnostica.write_text(
            testo_log,
            encoding="utf-8",
        )
        log_salvato = True
    except OSError:
        pass

    messaggio = (
        "«PostiPerfetti» si è chiuso subito dopo l'avvio "
        f"({descrizione_uscita}).\n\n"
        "Il problema può dipendere dall'ambiente Python, da Qt "
        "o da una libreria di sistema."
    )

    if log_salvato:
        messaggio += (
            "\n\nLa diagnostica tecnica è stata salvata in:\n"
            f"{file_diagnostica}"
        )

    # Nel terminale mostriamo anche stderr direttamente: è utile durante
    # installazione e collaudo e non richiede all'utente di aprire il log.
    if in_terminale():
        print(f"\n❌ {messaggio}")

        if dettaglio_stderr:
            print("\n--- Dettaglio tecnico ---")
            print(dettaglio_stderr)
            print("-------------------------")
    else:
        # Nel popup evitiamo muri di testo tecnico: indichiamo il log.
        mostra_dialogo(
            "Errore di avvio — «PostiPerfetti»",
            messaggio,
            tipo="errore",
        )

    sys.exit(1)


# =====================================================================
# SEZIONE 5-bis: Auto-rilancio in un terminale (avvio da menu con
#                ambiente da preparare)
# =====================================================================

# Emulatori di terminale da tentare, in ordine di preferenza.
# Ogni voce: (comando, argomento_che_precede_il_comando_da_eseguire).
# La maggior parte usa "-e", konsole compreso; li elenchiamo dai più
# diffusi ai più generici, con xterm come minimo comune denominatore.
TERMINALI = [
    ("konsole",         "-e"),   # KDE Plasma
    ("gnome-terminal",  "--"),   # GNOME (usa "--", non "-e")
    ("xfce4-terminal",  "-e"),   # XFCE
    ("mate-terminal",   "-e"),   # MATE
    ("tilix",           "-e"),   # vari
    ("alacritty",       "-e"),   # tiling / moderni
    ("kitty",           None),   # kitty esegue il comando senza flag
    ("foot",            None),   # Wayland minimalista, come kitty
    ("xterm",           "-e"),   # fallback universale X11
]


def rilancia_in_terminale():
    """
    Riavvia QUESTO launcher dentro un emulatore di terminale.

    Serve quando il launcher è stato avviato dal menu (nessun terminale)
    ma l'ambiente va preparato: apriamo un terminale in cui l'utente
    veda i messaggi testuali e possa rispondere alle domande.

    La copia rilanciata riceve la variabile-sentinella
    POSTIPERFETTI_RILANCIATO=1: la vede, capisce di essere già la
    copia "in terminale" e NON tenterà mai di rilanciarsi di nuovo
    (protezione contro un ciclo infinito).

    Returns:
        True  se un terminale è stato aperto (questa copia deve uscire)
        False se nessun terminale era disponibile (gestire altrimenti)
    """
    # Comando che il terminale dovrà eseguire: reinvochiamo questo
    # stesso file con lo stesso Python di sistema che ci sta eseguendo.
    comando_launcher = [sys.executable, str(Path(__file__).resolve())]

    # Prepariamo l'ambiente per la copia figlia, con la sentinella.
    ambiente = os.environ.copy()
    ambiente["POSTIPERFETTI_RILANCIATO"] = "1"

    # Proviamo i terminali in ordine, fermandoci al primo che parte.
    for nome_terminale, flag in TERMINALI:
        if not shutil.which(nome_terminale):
            continue   # non installato: passa al successivo

        # Costruiamo la riga di comando del terminale.
        if flag is None:
            riga = [nome_terminale] + comando_launcher
        else:
            riga = [nome_terminale, flag] + comando_launcher

        try:
            # start_new_session: il terminale vive indipendente da noi.
            subprocess.Popen(riga, start_new_session=True, env=ambiente)
            return True   # aperto: la copia attuale può uscire
        except Exception:
            continue   # questo terminale ha fallito: prova il prossimo

    # Nessun terminale disponibile.
    return False

def main():
    """
    Flusso principale del launcher:
    1. Verifica che il file principale esista
    2. Verifica/crea il venv
    3. Verifica/installa le dipendenze
    4. Avvia l'applicazione
    """
    # === PASSO C: se lanciato dal menu (niente terminale) e l'ambiente
    #     va preparato, ci rilanciamo in un terminale e usciamo. ===
    # Tre condizioni, TUTTE necessarie perché scatti il rilancio:
    #   1. non siamo in un terminale (avvio da menu);
    #   2. l'ambiente è incompleto (serve creare venv / installare);
    #   3. non siamo GIÀ una copia rilanciata (sentinella anti-loop).
    # Nel caso quotidiano (menu + ambiente a posto) la condizione 2 è
    # falsa: il rilancio NON avviene e il launcher prosegue normale.
    gia_rilanciato = os.environ.get("POSTIPERFETTI_RILANCIATO") == "1"

    if (not in_terminale()) and ambiente_incompleto() and (not gia_rilanciato):
        if rilancia_in_terminale():
            # Terminale aperto: il lavoro prosegue nella copia figlia.
            # Questa copia (senza terminale) ha esaurito il suo compito.
            sys.exit(0)
        else:
            # Nessun terminale disponibile: ultimo ripiego, un dialogo
            # grafico che spiega come procedere manualmente.
            mostra_dialogo(
                "Preparazione necessaria — «PostiPerfetti»",
                "Al primo avvio «PostiPerfetti» deve preparare il proprio "
                "ambiente, ma non è stato possibile aprire un terminale.\n\n"
                "Apri un terminale ed esegui questo comando:\n\n"
                f"  {sys.executable} {Path(__file__).resolve()}\n\n"
                "Il programma completerà da solo la preparazione.",
                tipo="errore"
            )
            sys.exit(1)

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

        # In terminale: domanda testuale. Senza terminale: dialogo grafico.
        if in_terminale():
            print("\n⚠️  L'ambiente virtuale (.venv) non è stato trovato o è corrotto.")
            print("   È necessario per eseguire il programma e richiede una")
            print("   connessione a internet per scaricare le dipendenze.")
            risposta = chiedi_conferma_terminale("   Vuoi crearlo adesso?")
        else:
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
                "Impossibile creare un ambiente virtuale compatibile.\n\n"
                "Questa release richiede Python 3.10, 3.11, 3.12, "
                "3.13 oppure 3.14 e il supporto al modulo «venv».\n\n"
                "Se PostiPerfetti era già stato installato correttamente, "
                "riesegui l'installer Linux: verificherà anche i "
                "prerequisiti di sistema.",
                tipo="errore",
            )
            sys.exit(1)
    else:
        print("   ✅ Ambiente virtuale trovato")

        # --- STEP 3: Verifica rigorosa dell'ambiente runtime ---
    print("\n🔍 Verifica dipendenze e versioni...")
    problemi = problemi_ambiente()

    if problemi:
        print("\n⚠️  L'ambiente Python richiede una riparazione:")
        for problema in problemi:
            print(f"     • {problema}")

        requisiti, errori_requirements = leggi_requirements_bloccati()

        # requirements.txt è parte del programma, non qualcosa che il
        # launcher possa ricostruire dalla rete o da un elenco interno.
        if errori_requirements:
            testo_errore = (
                "L'installazione di «PostiPerfetti» risulta incompleta "
                "o danneggiata:\n\n"
                + "\n".join(
                    f"  • {errore}"
                    for errore in errori_requirements
                )
                + "\n\nRiesegui l'installer Linux per ripristinare "
                "i file ufficiali del programma."
            )

            if in_terminale():
                print(f"\n❌ {testo_errore}")
            else:
                mostra_dialogo(
                    "Installazione danneggiata — «PostiPerfetti»",
                    testo_errore,
                    tipo="errore",
                )

            sys.exit(1)

        if in_terminale():
            print(
                "\n   La riparazione può richiedere una connessione "
                "a internet."
            )
            risposta = chiedi_conferma_terminale(
                "   Vuoi riparare l'ambiente adesso?"
            )
        else:
            risposta = mostra_dialogo(
                "Riparazione ambiente — «PostiPerfetti»",
                "L'ambiente Python di «PostiPerfetti» non corrisponde "
                "alla configurazione prevista dalla release.\n\n"
                "Vuoi ripararlo adesso?\n\n"
                "Se occorre scaricare nuovamente qualche componente, "
                "sarà necessaria una connessione a internet.",
                si_no=True,
            )

        if not risposta:
            print("   ⏹️  Operazione annullata dall'utente")
            sys.exit(0)

        if not installa_dipendenze():
            testo_errore = (
                "Non è stato possibile ripristinare correttamente "
                "l'ambiente Python di «PostiPerfetti».\n\n"
                "Riesegui l'installer Linux: effettuerà anche i "
                "controlli sui prerequisiti di sistema e sul runtime Qt."
            )

            if in_terminale():
                print(f"\n❌ {testo_errore}")
            else:
                mostra_dialogo(
                    "Errore — «PostiPerfetti»",
                    testo_errore,
                    tipo="errore",
                )

            sys.exit(1)

    else:
        print("   ✅ Versioni richieste presenti")
        print("   ✅ Dipendenze Python coerenti")
        print("   ✅ Import runtime verificati")

    # --- STEP 4: Tutto ok, avvia l'applicazione ---
    print("\n✅ Tutte le verifiche superate!")
    avvia_applicazione()


if __name__ == "__main__":
    main()
