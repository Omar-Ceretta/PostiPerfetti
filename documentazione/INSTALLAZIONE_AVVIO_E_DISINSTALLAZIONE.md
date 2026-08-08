# 🖥️ «PostiPerfetti» — Installazione e avvio

---

<table border="0"><tr><td>
<img src="https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/dati/screenshot/windows11.png" width="64" />
</td><td>

## Installazione su Windows

</td></tr></table>

1. Scorri in fondo a questa pagina e - nella sezione  *Assets* - scarica "**`PostiPerfetti_Setup.exe`**" (se necessario, clicca prima su  ' ▶ Assets' per espandere l'elenco).
2. Fai doppio clic sul file scaricato.
3. Segui le istruzioni del programma di installazione.

### ❗ Nota sulla sicurezza (SmartScreen e antivirus)

Essendo un software open-source gratuito, il file non possiede una firma digitale a pagamento. Per questo motivo **Windows o il tuo antivirus potrebbero mostrare un avviso di protezione** (la schermata blu di SmartScreen).

<img src="https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/dati/screenshot/smartscreen.png" />

**Se appare l'avviso di Windows:**

1. Nella schermata blu, fai clic sulla scritta **«Ulteriori informazioni»**.
2. Comparirà un nuovo pulsante in basso: fai clic su **«Esegui comunque»**.
3. L'installazione partirà normalmente.

**Se il tuo antivirus blocca il file:**

1. Aggiungi il file alle eccezioni, **oppure**
2. Disattiva temporaneamente l'antivirus per la sola durata dell'installazione.

---

<table border="0"><tr><td>
<img src="https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/dati/screenshot/linux.png" width="64" />
</td><td>

## Installazione su Linux

</td></tr></table>

L'installazione su Linux è **automatica**: un unico script Bash scarica il programma da GitHub, lo installa nella cartella personale dell'utente e crea la relativa voce nel Menu applicazioni.

L'installer **non richiede privilegi di amministratore** e non esegue comandi tramite `sudo`. Se sul sistema manca uno dei prerequisiti necessari, tuttavia, la sua installazione tramite il gestore pacchetti della distribuzione potrebbe richiedere i normali privilegi amministrativi.

### Cosa serve

Lo script verifica automaticamente, prima di modificare qualsiasi file, la presenza di:

- **Python 3** e del supporto agli ambienti virtuali (`venv`);
- **tar**, per estrarre l'archivio scaricato;
- **rsync**, per installare e aggiornare in sicurezza i file del programma;
- **curl** oppure **wget**, per effettuare il download.

È consigliato **Python 3.10 o successivo**.

Per controllare la versione installata:

```bash
python3 --version
```

Se manca un componente necessario, l'installer si interrompe e indica il comando appropriato per installarlo sulle principali famiglie di distribuzioni Linux.

> **Nota per Debian, Ubuntu e derivate:** il supporto agli ambienti virtuali può essere distribuito separatamente. In tal caso è sufficiente installare:
>
> ```bash
> sudo apt install python3-venv
> ``

### Installazione

Apri un terminale e scarica lo script di installazione con **wget**:

```bash
wget https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/install.sh
bash install.sh
```

Se sul tuo sistema è disponibile `curl` anziché `wget`, puoi usare:

```bash
curl -fL -o install.sh https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/packaging/linux/install.sh
bash install.sh
```

Lo script scaricherà l'ultima versione di «PostiPerfetti» da GitHub e installerà i soli file necessari all'esecuzione del programma in:

```text
~/PostiPerfetti
```

Alla prima installazione verranno inoltre aggiunti due file-classe di esempio.

L'installer creerà infine la voce «PostiPerfetti» nel Menu applicazioni e installerà la relativa icona secondo gli standard freedesktop.org.

I file principali del programma e i dati dell'utente resteranno all'interno di `~/PostiPerfetti`. Alcuni piccoli file necessari all'integrazione con il desktop — la voce del Menu applicazioni e l'icona — vengono collocati nelle directory standard dell'ambiente desktop, normalmente sotto `~/.local/share`.

Tutti i file temporanei utilizzati per il download e l'estrazione vengono rimossi automaticamente al termine dell'installazione.

Il file `install.sh` scaricato manualmente rimane invece nella cartella dalla quale hai eseguito il comando e, dopo l'installazione, può essere eliminato senza problemi.

### Primo avvio

Al termine dell'installazione viene proposto di avviare subito «PostiPerfetti». Premendo semplicemente **Invio** alla richiesta `[S/n]` si conferma l'avvio.

La prima volta, il launcher prepara automaticamente l'ambiente Python del programma:

- crea l'ambiente virtuale privato `~/PostiPerfetti/.venv`;
- verifica le librerie necessarie;
- scarica e installa automaticamente quelle mancanti, fra cui PySide6 e XlsxWriter;
- avvia infine «PostiPerfetti».

È quindi necessaria una connessione a Internet durante **l'installazione o l'aggiornamento del programma** e quando il launcher deve creare o riparare l'ambiente virtuale. Una volta completata la preparazione, i normali avvii successivi non richiedono nuovi download.

### Avvii successivi

Troverai «PostiPerfetti» nel Menu delle applicazioni del tuo ambiente desktop e potrai avviarlo normalmente facendo clic sulla sua icona.

Se la voce non compare immediatamente dopo l'installazione, potrebbe essere necessario terminare la sessione utente e accedere nuovamente.

### Aggiornare il programma

Per aggiornare «PostiPerfetti» all'ultima versione disponibile, riesegui semplicemente gli stessi comandi utilizzati per l'installazione:

```bash
wget -O install.sh https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/packaging/linux/install.sh
bash install.sh
```

oppure, con `curl`:

```bash
curl -fL -o install.sh https://raw.githubusercontent.com/Omar-Ceretta/PostiPerfetti/main/packaging/linux/install.sh
bash install.sh
```

L'installer riconoscerà automaticamente l'installazione esistente e aggiornerà soltanto i file del programma.

Le classi create dall'utente, le impostazioni e gli altri dati personali **non verranno sovrascritti**.


### Disinstallare PostiPerfetti

L'installer aggiunge nella cartella del programma anche uno script di disinstallazione.

Per rimuovere PostiPerfetti apri un terminale ed esegui:

```bash
~/PostiPerfetti/uninstall.sh
```

La disinstallazione normale rimuove il programma, il suo ambiente virtuale, la voce nel Menu applicazioni e l'icona installata, ma **conserva le classi, le impostazioni e i log** presenti in:

```text
~/PostiPerfetti/classi
~/PostiPerfetti/stato
~/PostiPerfetti/log
```

In questo modo è possibile reinstallare successivamente il programma senza perdere i propri dati.

Per eliminare invece **completamente** PostiPerfetti, comprese classi, impostazioni e log, usa:

```bash
~/PostiPerfetti/uninstall.sh --purge
```

Prima di procedere viene richiesta una conferma esplicita.

> **Attenzione:** l'opzione `--purge` elimina definitivamente anche i dati personali di PostiPerfetti. Usala soltanto se non desideri conservarli.

---

<details>
<summary><b> 🔍 Per utenti ESPERTI: avvio manuale del launcher</b></summary>

<br>

È possibile anche scaricare manualmente l'intero sorgente e avviare direttamente il launcher, senza utilizzare lo script di installazione.

In alternativa ai comandi seguenti, il sorgente può essere scaricato dalla pagina principale del repository tramite **Code → Download ZIP**.

```bash
# Scarica l'ultima versione del codice
wget -O postiperfetti-main.tar.gz \
  https://github.com/Omar-Ceretta/PostiPerfetti/archive/refs/heads/main.tar.gz

# Estrai l'archivio
tar xzf postiperfetti-main.tar.gz

# Se ~/PostiPerfetti NON esiste già, rinomina e sposta la cartella
mv PostiPerfetti-main ~/PostiPerfetti
cd ~/PostiPerfetti

# Avvia il launcher
python3 moduli/postiperfetti_launcher.py
```

> **Attenzione:** i comandi precedenti presuppongono che `~/PostiPerfetti` non esista già. Per aggiornare un'installazione esistente è preferibile utilizzare lo script `install.sh`, che preserva automaticamente i dati dell'utente.

Il launcher verifica l'ambiente, crea `.venv` e installa le dipendenze mancanti prima di avviare il programma.

> **Nota:** con l'installazione manuale l'integrazione con il desktop NON viene effettuata automaticamente. Per aggiungere «PostiPerfetti» al Menu applicazioni occorre creare manualmente il relativo file `.desktop` e installare l'icona nel tema del sistema. L'icona sorgente si trova in `risorse/icone/postiperfetti_icon.png`.

</details>

---

## ❓ Risoluzione problemi (Linux)

▪️ **«python3» non trovato**

Python 3 non è installato oppure non è disponibile nel `PATH` del sistema. Installalo con il gestore pacchetti della tua distribuzione e ripeti l'installazione.

▪️ **Errore relativo a `venv` o `ensurepip`**

Il supporto agli ambienti virtuali Python non è disponibile. Su Debian, Ubuntu e derivate puoi installarlo con:

```bash
sudo apt install python3-venv
```

Quindi riesegui `install.sh`.

▪️ **«tar», «rsync», «curl» o «wget» non trovato**

Manca uno degli strumenti di sistema richiesti. L'installer indica automaticamente il comando di installazione appropriato per le principali famiglie di distribuzioni Linux.

È sufficiente avere **uno solo tra `curl` e `wget`**.

▪️ **Errore durante l'installazione di PySide6 o XlsxWriter**

Verifica innanzitutto che la connessione a Internet sia attiva e che Python sia aggiornato (`python3 --version`).

Puoi quindi chiudere e riavviare «PostiPerfetti»: il launcher controllerà nuovamente l'ambiente e proporrà di installare le dipendenze mancanti.

▪️ **Il programma si avvia ma la finestra è vuota o non risponde**

Chiudi completamente «PostiPerfetti» e riaprilo.

Se il problema persiste, puoi ricreare l'ambiente virtuale eliminando:

```text
~/PostiPerfetti/.venv
```

Al successivo avvio il launcher proporrà di ricrearlo e di reinstallare automaticamente le dipendenze necessarie. Questa operazione non elimina le classi o le impostazioni personali.
