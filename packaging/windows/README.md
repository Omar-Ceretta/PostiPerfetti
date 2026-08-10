# Packaging Windows — PostiPerfetti R0.8

Questa cartella contiene la configurazione riproducibile per produrre la
distribuzione Windows di «PostiPerfetti».

## File principali

- `PostiPerfetti.spec` — configurazione PyInstaller **onedir**.
- `postiperfetti_setup.iss` — installer Inno Setup per singolo utente.
- `version_info.txt` — metadati Windows incorporati in `PostiPerfetti.exe`.
- `postiperfetti.ico` — icona Windows multirisoluzione per EXE e Setup.
- `icon.svg` — master vettoriale dell'icona Windows.
- `icon-512.png` — sorgente raster usata per rigenerare il file `.ico`.
- `info_pre_installazione.txt` — pagina informativa prima dell'installazione.
- `info_dopo_installazione.txt` — avvio rapido mostrato a installazione conclusa.
- `build_windows.ps1` — automatizza build PyInstaller e, se disponibile, Inno Setup.

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
