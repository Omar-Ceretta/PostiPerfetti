# Packaging Windows di «PostiPerfetti»

Questa cartella contiene la configurazione riproducibile per produrre la
distribuzione Windows di «PostiPerfetti».

## File principali

- `PostiPerfetti.spec` — configurazione PyInstaller **onedir**.
- `postiperfetti_setup.iss` — installer Inno Setup per singolo utente.
- i metadati Windows incorporati in `PostiPerfetti.exe` vengono generati durante la build dalla versione definita in `moduli/versione.py`.
- `postiperfetti.ico` — icona Windows multirisoluzione per EXE e Setup.
- `icon.svg` — master vettoriale dell'icona Windows.
- `icon-512.png` — sorgente raster usata per rigenerare il file `.ico`.
- `info_pre_installazione.txt` — pagina informativa prima dell'installazione.
- `info_dopo_installazione.txt` — avvio rapido mostrato a installazione conclusa.
- `build_windows.ps1` — automatizza build PyInstaller e, se disponibile, Inno Setup; legge automaticamente la versione da `moduli/versione.py` e la propaga sia all'EXE sia all'installer.

## Scelte architetturali

La build è `onedir`: l'utente vede un solo collegamento a `PostiPerfetti.exe`,
mentre le librerie vengono mantenute nella sottocartella `_internal` creata da
PyInstaller.

L'installer è **per utente**, senza privilegi amministrativi, e usa come
destinazione predefinita la cartella Programmi personale di Windows
(`{autopf}\PostiPerfetti`).

Le aree `classi/`, `stato/` e `log/` restano accanto all'eseguibile e sono
considerate dati dell'utente:

- non vengono eliminate durante un aggiornamento;
- non vengono rimosse dalla disinstallazione normale;
- l'uninstaller chiede esplicitamente se eliminarle definitivamente.

## Regola fondamentale per gli aggiornamenti

NON cambiare l'`AppId` presente in `postiperfetti_setup.iss` nelle versioni
future. È l'identità stabile con cui Inno Setup riconosce che una nuova release
è un aggiornamento della stessa applicazione.

## Dove si costruisce

PyInstaller non è un cross-compiler: la build Windows va prodotta **su Windows**.

## Toolchain di build

La build richiede:

- Python 3 a 64 bit, in una versione supportata da «PostiPerfetti»;
- le dipendenze definite in `requirements-build-windows.txt`;
- Inno Setup 6.6 o successivo.

`requirements-build-windows.txt` congela anche la versione di PyInstaller
utilizzata dalla build.

La versione effettiva di Python, PyInstaller e Inno Setup usata per una
Release ufficiale viene controllata e registrata dalla procedura
`CREA_RELEASE.cmd`.

### Repository autosufficiente

**Basta scaricare lo ZIP del repository pubblico su un PC Windows** con Python
3 a 64 bit e Inno Setup 6.6+ installati. Non è necessario copiare alcun
archivio, `tests/`, `strumenti/` o `requirements-dev.txt` da altri computer.
Le dipendenze Python vengono installate automaticamente da pip; è richiesta
una connessione Internet al primo allestimento dell'ambiente di build.

- `CREA_INSTALLER.cmd` costruisce EXE e Setup per le **prove pratiche**.
- `CREA_RELEASE.cmd COLLAUDO` verifica la pipeline di pubblicazione con
  artefatti espressamente contrassegnati come NON pubblicabili.
- `CREA_RELEASE.cmd` prepara gli artefatti della Release ufficiale quando
  il CHANGELOG contiene la data della versione e tutti i controlli passano.

La procedura Release verifica: presenza dei file pubblici essenziali,
compilabilità di tutti i sorgenti Python, versione e tag, Ruff (versione
congelata in `requirements-build-windows.txt`), versione Python/Inno Setup,
pulizia delle build precedenti, metadati EXE e Setup, SHA-256 e asset Linux.
Il controllo `verifica_sorgenti_release.py` è incluso in questa stessa cartella.

**Limite esplicito:** i controlli statici NON sostituiscono la suite completa
`pytest` dell'audit e non la eseguono. La Release non è certificata dal solo
superamento di questi controlli: vanno svolte le prove funzionali di
installazione, generazione, esportazione, aggiornamento e disinstallazione
previste per Windows e Linux. La suite completa rimane uno strumento di
sviluppo, non una dipendenza della distribuzione.

Non caricare su GitHub neppure gli ambienti virtuali o le cartelle `build/`,
`dist/`, `dist-installer/`, `dist-linux/` e `dist-release/`.
