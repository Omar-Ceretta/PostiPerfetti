# Collaudo del packaging Windows — PostiPerfetti R0.8

Eseguire questi passaggi **sulla partizione Windows**, dopo aver sincronizzato o
clonato la root corrente del repository.

## A. Test del sorgente su Windows

1. Installare Python 3 a 64 bit.
2. Aprire PowerShell nella root di `PostiPerfetti`.
3. Creare un ambiente di prova oppure usare `packaging/windows/build_windows.ps1`.
4. Avviare almeno una volta il programma da sorgente.
5. Verificare:
   - apertura di una classe BASE e COMPLETA;
   - Mensile a coppie;
   - Mensile a terzetti;
   - Annuale a coppie;
   - Annuale a terzetti;
   - salvataggio nello Storico;
   - esportazione Excel;
   - tema chiaro/scuro;
   - chiusura durante/alla fine di un calcolo.

## B. Build PyInstaller

Da PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\windows\build_windows.ps1 -SoloExe
```

Il risultato atteso è:

```text
dist\PostiPerfetti\
├── PostiPerfetti.exe
└── _internal\
```

## C. Collaudo dell'EXE prima dell'installer

Avviare:

```powershell
.\dist\PostiPerfetti\PostiPerfetti.exe
```

Ripetere almeno i quattro flussi di calcolo:

- Mensile / coppie;
- Mensile / terzetti;
- Annuale / coppie;
- Annuale / terzetti.

Questa fase è fondamentale perché esercita i processi `multiprocessing` della
build congelata.

Controllare inoltre che:

- non compaia alcuna finestra console;
- l'icona sia corretta nella finestra e nella barra delle applicazioni;
- `classi/`, `stato/` e `log/` vengano creati accanto all'EXE quando necessario;
- la guida e tutte le icone/risorse si aprano correttamente;
- un file Excel venga esportato senza errori.

## D. Build Inno Setup

Installare **Inno Setup 7**.

Poi, dalla root:

```powershell
.\packaging\windows\build_windows.ps1
```

L'installer atteso sarà:

```text
dist-installer\PostiPerfetti_Setup_0.8.0.exe
```

## E. Collaudo dell'installer

Su un account Windows normale:

1. installare senza avviare PowerShell come amministratore;
2. verificare che non venga richiesto UAC;
3. controllare collegamento Menu Start e, se selezionato, Desktop;
4. aprire `PostiPerfetti`;
5. modificare una classe di esempio;
6. generare e salvare almeno un'assegnazione;
7. eseguire nuovamente il Setup come aggiornamento;
8. verificare che classe modificata, `stato/` e `log/` siano rimasti intatti;
9. disinstallare scegliendo **No** alla cancellazione dei dati;
10. verificare che `classi/`, `stato/`, `log/` siano rimasti;
11. reinstallare e verificare che i dati vengano ritrovati;
12. disinstallare nuovamente scegliendo **Sì** alla cancellazione dei dati;
13. verificare che le tre directory siano state eliminate.

Solo dopo questi passaggi il file Setup può essere considerato pronto per una
Release pubblica.

## F. Firma digitale

Non usare un certificato self-signed per una release destinata ad altri utenti:
non crea una catena di fiducia riconosciuta da Windows e non risolve realmente
gli avvisi SmartScreen.

La firma con un certificato pubblico di code signing può essere aggiunta in una
fase successiva senza cambiare l'architettura del packaging.
