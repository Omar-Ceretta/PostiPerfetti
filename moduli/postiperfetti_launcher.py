#!/usr/bin/env python3
"""
Launcher per «PostiPerfetti» — Script di avvio con verifica ambiente.

COSA FA QUESTO SCRIPT:
1. Verifica che l'ambiente virtuale (.venv) esista
2. Verifica che le dipendenze necessarie (PySide6, xlsxwriter) siano installate
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
# requirements.txt nella radice del progetto: fonte primaria delle
# dipendenze CON i vincoli di versione (es. PySide6>=6.11,<7).
# Se assente, si ripiega sui nomi elencati in DIPENDENZE (senza vincoli).
FILE_REQUIREMENTS = CARTELLA_PROGETTO / "requirements.txt"

# Dipendenze richieste: (nome_pacchetto_pip, nome_import_python)
DIPENDENZE = [
    ("PySide6", "PySide6"),
    ("XlsxWriter", "xlsxwriter"),
]


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

def ambiente_incompleto():
    """
    Dice se manca qualcosa per far girare l'app: il venv o una
    qualsiasi dipendenza. Verifica SILENZIOSA (non stampa nulla):
    serve solo a decidere, all'avvio, se occorre intervenire.

    Returns:
        True  se manca il venv OPPURE almeno una dipendenza
        False se è tutto a posto (l'app può partire subito)
    """
    # Se manca il venv, l'ambiente è certamente incompleto: inutile
    # controllare le dipendenze (girerebbero su un venv inesistente).
    if not (PYTHON_VENV.is_file() and PIP_VENV.is_file()):
        return True

    # Il venv c'è: controlliamo che ogni dipendenza sia importabile.
    for _, nome_import in DIPENDENZE:
        risultato = subprocess.run(
            [str(PYTHON_VENV), "-c", f"import {nome_import}"],
            capture_output=True   # silenzioso: non mostra nulla a schermo
        )
        if risultato.returncode != 0:
            return True   # una dipendenza manca → incompleto

    return False   # venv presente e tutte le dipendenze importabili

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
    successo = esegui_con_progresso(
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
    Installa le dipendenze nel venv.

    Strategia "fonte unica per le versioni":
    - se requirements.txt esiste, si installa con «pip install -r»,
      rispettando i VINCOLI DI VERSIONE lì definiti (es. PySide6<7).
      È il caso normale: le versioni sono dichiarate in UN solo posto.
    - se requirements.txt manca (installazione danneggiata), si ripiega
      sui nomi elencati in DIPENDENZE, SENZA vincoli di versione.

    Nota: qualunque manchi tra le dipendenze, reinstalliamo comunque
    l'intero requirements.txt. È corretto e più semplice: pip salta
    ciò che è già presente e installa solo il necessario.

    Args:
        mancanti: Lista di tuple (nome_pip, nome_import). Usata per il
                  messaggio e come fallback se requirements.txt manca.

    Returns:
        True se l'installazione è riuscita
    """
    nomi_pip = [nome for nome, _ in mancanti]
    elenco_nomi = ", ".join(nomi_pip)

    # Scegliamo il comando pip in base alla presenza di requirements.txt.
    # L'informazione sulla fonte va nel TITOLO: sarà esegui_con_progresso
    # a stamparlo una sola volta, evitando intestazioni doppie.
    # --disable-pip-version-check: sopprime l'avviso "a new release of pip
    # is available". È solo informativo e non riguarda PostiPerfetti; NON
    # aggiorna pip (che resterebbe soggetto a possibili incompatibilità
    # future), si limita a non stampare il notice.
    if FILE_REQUIREMENTS.is_file():
        # Fonte primaria: il file con i vincoli di versione.
        comando_pip = [str(PIP_VENV), "install", "--disable-pip-version-check",
                       "-r", str(FILE_REQUIREMENTS)]
        titolo = "Installazione dipendenze (da requirements.txt)..."
    else:
        # Fallback: nomi da DIPENDENZE, senza vincoli. Avvisiamo, perché
        # l'assenza del file è un'anomalia (installazione incompleta).
        print("⚠️  requirements.txt non trovato: uso l'elenco interno.")
        comando_pip = [str(PIP_VENV), "install", "--disable-pip-version-check"] + nomi_pip
        titolo = f"Installazione dipendenze ({elenco_nomi})..."

    successo = esegui_con_progresso(comando_pip, titolo=titolo)

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
    Avvia PostiPerfetti come processo INDIPENDENTE dal terminale.

    A differenza di os.execv (che rimpiazzava il launcher facendo
    ereditare all'app il terminale, così che chiudere il terminale
    uccidesse anche la GUI), qui generiamo l'app in una SESSIONE
    NUOVA e separata: il terminale può essere chiuso liberamente e
    la GUI resta viva.

    Strategia "sorveglia un istante, poi lascia andare":
    - avvia l'app staccata;
    - attende brevemente per intercettare un eventuale crash immediato
      (dipendenza rotta, errore di import): in tal caso stampa l'errore;
    - se dopo l'attesa l'app è ancora viva, esce lasciandola autonoma.
    """
    print(f"\n🚀 Avvio «PostiPerfetti»...")

    # start_new_session=True → equivale a setsid: nuova sessione,
    # scollegata dal terminale. È Python puro (libreria standard),
    # senza dipendere dal comando esterno «setsid».
    try:
        processo_app = subprocess.Popen(
            [str(PYTHON_VENV), str(FILE_PRINCIPALE)],
            start_new_session=True
        )
    except Exception as errore:
        # Se non riusciamo nemmeno ad avviare il processo, è un problema
        # serio (Python del venv mancante?): segnaliamolo e usciamo male.
        messaggio = f"Impossibile avviare il programma:\n{errore}"
        if in_terminale():
            print(f"\n❌ {messaggio}")
        else:
            mostra_dialogo("Errore — «PostiPerfetti»", messaggio, tipo="errore")
        sys.exit(1)

    # --- Sorveglianza breve: l'app crasha all'istante? ---------------
    # Attendiamo fino a ~2 secondi. Se il processo termina entro questo
    # tempo con un codice d'errore, quasi certamente è un crash di avvio
    # e vale la pena mostrarlo. Se resta vivo, l'avvio è riuscito.
    try:
        codice = processo_app.wait(timeout=2)
        # Se siamo qui, il processo è GIÀ terminato entro il timeout.
        if codice != 0:
            messaggio = (
                f"«PostiPerfetti» si è chiuso subito dopo l'avvio "
                f"(codice {codice}).\n"
                "Potrebbe esserci un problema con l'installazione."
            )
            if in_terminale():
                print(f"\n❌ {messaggio}")
            else:
                mostra_dialogo("Errore — «PostiPerfetti»", messaggio, tipo="errore")
            sys.exit(1)
        # codice == 0: l'app è partita e si è chiusa subito ma
        # regolarmente (raro, ma legittimo). Nulla da segnalare.
    except subprocess.TimeoutExpired:
        # Caso NORMALE: dopo 2 secondi l'app è ancora viva → avvio
        # riuscito. Il launcher ha finito: esce lasciando la GUI
        # indipendente, e il terminale torna libero.
        if in_terminale():
            print("   ✅ Programma avviato. Puoi chiudere questo terminale.")

    # Il launcher termina qui. La GUI, in sessione separata, prosegue.
    sys.exit(0)


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
                "Impossibile creare l'ambiente virtuale.\n\n"
                "Verifica che python3-venv sia installato:\n"
                "  sudo dnf install python3 python3-devel python3-pip\n\n"
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

        # Stessa logica del punto precedente: terminale → testo, menu → grafico.
        if in_terminale():
            print("\n⚠️  Dipendenze mancanti:")
            for nome, _ in mancanti:
                print(f"     • {nome}")
            print("   L'installazione richiede una connessione a internet.")
            risposta = chiedi_conferma_terminale("   Vuoi installarle adesso?")
        else:
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
            # Messaggio con DUE possibili cause: rete assente, oppure
            # versioni richieste non più disponibili/compatibili (caso
            # dell'"invecchiamento" dei vincoli in requirements.txt).
            testo_errore = (
                f"Impossibile installare le dipendenze: {nomi_mancanti}\n\n"
                "Possibili cause:\n"
                "  • assenza di connessione a internet;\n"
                "  • le versioni richieste non sono più disponibili\n"
                "    o compatibili con questo sistema.\n\n"
                "Puoi provare a installarle manualmente:\n"
                f"  {PIP_VENV} install -r {FILE_REQUIREMENTS}"
            )
            if in_terminale():
                print(f"\n❌ {testo_errore}")
            else:
                mostra_dialogo("Errore — «PostiPerfetti»", testo_errore, tipo="errore")
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
