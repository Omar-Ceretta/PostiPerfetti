
# 🖥️ «PostiPerfetti» - INSTALLAZIONE E AVVIO

## 🐧 Utenti Linux

### Launcher automatico

Il progetto include un **launcher** che verifica l'ambiente, installa le dipendenze mancanti e avvia il programma in automatico. Si trova nella cartella `modelli/`.

#### 1. Verifica che Python sia installato

Apri un terminale e digita:

```bash
python3 --version
```

Python è preinstallato sulla maggior parte delle distribuzioni Linux. Se manca, installalo con il gestore pacchetti della tua distribuzione:

```bash
# Debian / Ubuntu / Tuxedo OS / Linux Mint / Pop OS / Zorin OS
sudo apt install python3 python3-venv python3-pip

# Arch / Manjaro / EndeavourOS
sudo pacman -S python

# Fedora / Nobara
sudo dnf install python3 python3-pip
```

#### 2. Avvia il launcher

Spostati nella cartella del progetto e lancia:

```bash
cd ~/PostiPerfetti
python3 modelli/postiperfetti_launcher.py
```

Al primo avvio il launcher:
- **Crea automaticamente** l'ambiente virtuale (`.venv`)
- **Scarica e installa** le dipendenze necessarie (PySide6, openpyxl)
- **Avvia** il programma

Ti verrà chiesta conferma tramite un popup grafico prima di ogni operazione. È necessaria una connessione a Internet per il primo avvio.

Le volte successive il launcher rileverà che tutto è già installato e avvierà il programma istantaneamente.


> **Suggerimento:** su molti Desktop Environmentpuoi puoi creare un collegamento sul Desktop per avviare il programma con un doppio clic. Fai clic destro sul Desktop → "Crea nuovo" → "Collegamento ad applicazione", e nel campo "Comando" inserisci:
> `python3 /home/TUO_UTENTE/PostiPerfetti/modelli/postiperfetti_launcher.py`

---

## ❓ Risoluzione problemi

**"python" o "python3" non trovato:** Python non è installato o non è nel PATH di sistema. Su Windows, reinstalla Python da [python.org](https://www.python.org/downloads/) assicurandoti di spuntare "Add Python to PATH". Su Linux, installalo con il gestore pacchetti (vedi sopra).

**Errore "No module named venv":** Su Debian/Ubuntu potrebbe mancare il modulo venv. Installalo con:
```bash
sudo apt install python3-venv
```

**Errore durante l'installazione di PySide6:** Verifica di avere una connessione a Internet attiva e che la versione di Python sia 3.10 o superiore (`python3 --version`).

**Il programma si avvia ma la finestra è vuota o non risponde:** Prova a chiudere e riaprire. Se il problema persiste, elimina la cartella `.venv` e ripeti la procedura di installazione delle dipendenze.
