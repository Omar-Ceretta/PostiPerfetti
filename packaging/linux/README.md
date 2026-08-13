# Packaging Linux di PostiPerfetti

Questa directory contiene gli strumenti specifici per l'installazione, la
disinstallazione e la preparazione degli asset Linux di **PostiPerfetti**.

I file presenti qui non costituiscono una pipeline di release separata da
quella Windows. La release ufficiale di PostiPerfetti è unica e comprende
contemporaneamente gli artefatti Windows e Linux.

La procedura generale di build/release viene avviata dagli strumenti in
`packaging/windows/`; durante tale procedura viene richiamato automaticamente
anche `crea_release_linux.py`, che prepara gli asset Linux destinati alla
medesima GitHub Release.

## File presenti

### `install.sh`

Installer Linux di PostiPerfetti.

La copia conservata nel repository è deliberatamente in modalità
**sviluppo/collaudo**. Scarica il sorgente corrente dal repository e permette
di verificare l'installazione prima della preparazione di una release.

In sintesi, lo script:

- deve essere eseguito come **utente normale**, non come `root`;
- rileva la famiglia della distribuzione Linux;
- controlla i prerequisiti nativi richiesti da Python, PySide6 e Qt;
- se necessario, propone l'installazione dei soli pacchetti mancanti;
- usa normalmente `sudo` per il package manager e può ricorrere a `su` nei
  sistemi in cui l'utente non dispone di `sudo` ma è disponibile l'account
  amministratore `root`;
- crea e verifica l'ambiente virtuale `.venv`;
- installa le dipendenze Python;
- controlla le dipendenze native del plugin Qt/XCB tramite `ldd`, quando
  disponibile;
- esegue un vero smoke test di `QApplication`;
- installa PostiPerfetti nella directory personale dell'utente;
- crea l'integrazione con il menu applicazioni secondo gli standard XDG /
  freedesktop.org.

La destinazione predefinita è:

```text
~/PostiPerfetti
```

Per i collaudi può essere cambiata senza modificare lo script:

```bash
POSTIPERFETTI_DEST=~/PostiPerfetti-test bash install.sh
```

È inoltre disponibile l'uso di una copia locale del repository:

```bash
POSTIPERFETTI_SORGENTE_LOCALE=/percorso/del/repository \
POSTIPERFETTI_DEST=~/PostiPerfetti-test \
bash install.sh
```

e, se si vuole evitare di modificare la voce del menu applicazioni durante un
test:

```bash
POSTIPERFETTI_INTEGRA_MENU=0 \
POSTIPERFETTI_DEST=~/PostiPerfetti-test \
bash install.sh
```

#### Modalità release

All'inizio di `install.sh` sono presenti quattro costanti che costituiscono il
contratto con `crea_release_linux.py`:

```bash
MODALITA_RELEASE=0
VERSIONE_RELEASE=""
URL_TARBALL="https://github.com/Omar-Ceretta/PostiPerfetti/archive/refs/heads/main.tar.gz"
SHA256_ATTESO=""
```

**Non vanno modificate manualmente per creare una release.**

`crea_release_linux.py` genera una copia dell'installer impostata in modalità
release, sostituendo automaticamente questi valori con versione, URL e SHA-256
dell'archivio ufficiale.

---

### `uninstall.sh`

Disinstaller Linux di PostiPerfetti.

Non richiede `sudo` e rimuove soltanto file appartenenti all'installazione
dell'utente.

Per impostazione predefinita elimina programma, ambiente virtuale e
integrazione desktop, ma **conserva i dati dell'utente**:

```text
classi/
stato/
log/
```

Uso normale:

```bash
bash uninstall.sh
```

Per eliminare anche classi, configurazione, storico e log:

```bash
bash uninstall.sh --purge
```

Per eseguire una disinstallazione senza domanda interattiva:

```bash
bash uninstall.sh --yes
```

Le opzioni possono essere combinate:

```bash
bash uninstall.sh --purge --yes
```

Come l'installer, accetta una destinazione esplicita:

```bash
POSTIPERFETTI_DEST=~/altra_cartella bash uninstall.sh
```

Lo script contiene guardie contro percorsi pericolosi, riconosce
l'installazione prima di rimuoverla e verifica che l'eventuale voce `.desktop`
appartenga davvero alla stessa installazione prima di cancellarla.

---

### `crea_release_linux.py`

Helper interno per la preparazione degli **asset Linux** della release.

Normalmente **non deve essere eseguito manualmente**: viene richiamato
automaticamente dalla pipeline generale di release avviata dagli strumenti
Windows.

Il suo compito è:

1. leggere versione e tag da `moduli/versione.py`;
2. creare l'archivio Linux:

   ```text
   PostiPerfetti-<versione>-linux.tar.gz
   ```

3. includere nel pacchetto il programma, i moduli, le risorse, i file-classe di
   esempio e `uninstall.sh`;
4. normalizzare permessi, timestamp e metadati dell'archivio;
5. calcolare lo SHA-256 del tarball;
6. generare da `install.sh` la copia ufficiale in modalità release;
7. generare `SHA256SUMS`.

Gli artefatti intermedi vengono scritti in:

```text
dist-linux/
├── PostiPerfetti-<versione>-linux.tar.gz
├── install.sh
└── SHA256SUMS
```

`dist-linux/` è quindi una **directory intermedia di build**, non una release
Linux indipendente.

La pipeline generale verifica questi file e li raccoglie insieme agli
artefatti Windows nella cartella finale destinata alla stessa GitHub Release.

Il comando diretto:

```bash
python packaging/linux/crea_release_linux.py
```

resta utile per sviluppo o diagnostica della sola fase Linux, ma non rappresenta
la normale procedura di pubblicazione.

## Regola pratica

Per il lavoro ordinario:

- si modifica e collauda `install.sh` / `uninstall.sh`;
- non si modifica a mano l'installer generato dentro `dist-linux/`;
- non si prepara separatamente una “release Linux”;
- quando si crea la release ufficiale, la pipeline generale produce e verifica
  nello stesso processo gli artefatti Windows e Linux.

In questo modo esiste una sola versione pubblicata di PostiPerfetti e i pacchetti
delle due piattaforme restano allineati allo stesso tag di release.
