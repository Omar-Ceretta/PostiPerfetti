# PostiPerfetti 1.0 — Creazione e pubblicazione della Release definitiva

## SCOPO DI QUESTA SESSIONE

Questa è la sessione finale per **creare e pubblicare PostiPerfetti 1.0**.

NON riaprire audit generali, refactoring o controlli già conclusi.

L'obiettivo è:

> **produrre la Release definitiva 1.0 dalla copia finale del repository, pubblicarla su GitHub e verificare che gli asset pubblicati funzionino realmente.**

Procedere rigorosamente uno step alla volta:

**controllo finale → creazione Release → verifica artefatti → pubblicazione GitHub → prova installer pubblicato → CHIUSA.**

---

# STATO GIÀ VERIFICATO — NON RIAPRIRE

La pipeline Windows è stata collaudata realmente su Windows.

Sono già verdi:

- CI `pytest` GitHub su Python 3.10, 3.11, 3.12, 3.13 e 3.14;
- `CREA_RELEASE.cmd COLLAUDO`, concluso con successo;
- installazione Windows dell'installer prodotto dal COLLAUDO;
- avvio dell'applicazione dal Menu Start;
- apertura GUI e funzioni essenziali;
- file-classe di esempio presenti;
- salvataggio/apertura Report o Excel;
- blocco corretto della seconda istanza, con popup di avviso;
- disinstallatore funzionante nelle opzioni conserva/elimina dati;
- controllo della guardia finale:
  ```powershell
  .\packaging\windows\CREA_RELEASE.cmd
  ```
  è stato eseguito mentre il `CHANGELOG.md` conteneva ancora `1.0 — in preparazione` ed è **fallito correttamente**, come previsto.

Sono stati inoltre corretti e collaudati alcuni problemi emersi soltanto su Windows reale:

- `crea_release_windows.ps1`:
  - riferimenti `${Nome}:` corretti;
  - codifica UTF-8 con BOM per compatibilità con Windows PowerShell 5.1;
  - rilevamento della versione reale di Inno Setup tramite il preprocessore Inno (`PREPROCVER`), anziché affidarsi ai metadati PE `FileVersion/ProductVersion`, che sull'installazione reale risultavano `0.0.0.0`;
- `build_windows.ps1` convertito anch'esso in UTF-8 con BOM;
- `crea_installer_windows.ps1` era già UTF-8 con BOM;
- i `.cmd` non richiedevano modifiche.

NON annullare o sostituire queste correzioni.

---

# PREREQUISITI CHE OMAR AVRÀ GIÀ COMPLETATO PRIMA DI QUESTA SESSIONE

Quando questa sessione inizierà, assumere che siano già stati completati:

1. revisione definitiva di `README.md`;
2. revisione definitiva di `istruzioni.py`;
3. eventuali ultimissimi ritocchi destinati alla 1.0;
4. test reali dell'installer Linux almeno su:
   - Fedora;
   - Arch Linux;
   - openSUSE;
5. eventuali problemi emersi da tali test già risolti;
6. repository nella sua forma definitiva per la Release 1.0.

Se Omar segnala che uno di questi punti non è ancora concluso, NON creare ancora la Release definitiva.

---

# DUE CONTROLLI WINDOWS DA CONSIDERARE VERDI PRIMA DELLA RELEASE

Devono essere già stati verificati, oppure vanno verificati prima di procedere:

## Metadati Windows reali

Controllare:

```text
dist\PostiPerfetti\PostiPerfetti.exe
dist-installer\PostiPerfetti-1.0-setup.exe
```

Con:

**tasto destro → Proprietà → Dettagli**

Atteso:

- ProductVersion coerente con `1.0`;
- FileVersion coerente con `1.0.0.0`.

## Conservazione dati dopo reinstallazione

Verificare almeno una volta la sequenza:

1. installazione;
2. creazione/presenza di dati utente;
3. disinstallazione scegliendo di **mantenere i dati**;
4. reinstallazione;
5. verifica che i dati precedenti siano ancora presenti.

Se entrambi questi controlli sono già stati fatti e Omar lo conferma, considerarli CHIUSI senza ripeterli.

---

# CONTRATTO DELLA PIPELINE — NON MODIFICARE SENZA UNA RAGIONE CONCRETA

La struttura corretta è:

- `moduli/versione.py` = fonte unica della versione;
- nessun `packaging/windows/version_info.txt` statico;
- `postiperfetti_setup.iss` riceve la versione dall'esterno;
- `requirements-build-windows.txt` congela PyInstaller;
- `CREA_INSTALLER.cmd` = build Windows rapida/iterativa;
- `CREA_RELEASE.cmd` = pipeline severa per la Release ufficiale.

La Release definitiva deve produrre sia gli asset Windows sia quelli Linux.

Non proporre refactoring laterali in questa sessione.

---

# STEP 1 — CONTROLLO FINALE DELLA COPIA DEL REPOSITORY

Prima di creare la Release:

- lavorare sulla copia DEFINITIVA e aggiornata di PostiPerfetti;
- verificare che le correzioni Windows sopra indicate siano realmente presenti;
- verificare `moduli/versione.py`;
- verificare lo stato del `CHANGELOG.md`.

Non rifare un audit generale del progetto.

Se tutto è coerente, passare allo Step 2.

---

# STEP 2 — CHIUDERE IL CHANGELOG

Solo quando siamo davvero pronti a pubblicare, sostituire:

```text
1.0 — in preparazione
```

con la data reale della Release, nel formato già previsto dal progetto, per esempio:

```text
1.0 — 2026-08-XX
```

Usare ovviamente la data reale del giorno della pubblicazione.

Non anticipare questa modifica finché tutti i prerequisiti non sono verdi.

---

# STEP 3 — CREARE LA RELEASE DEFINITIVA

Su Windows, dalla root del progetto:

```powershell
.\packaging\windows\CREA_RELEASE.cmd
```

Questa volta:

- NON usare `COLLAUDO`;
- la pipeline deve arrivare fino in fondo;
- qualsiasi errore va analizzato prima di proseguire;
- NON correggere problemi a tentativi.

Se termina correttamente, individuare:

```text
dist-release\v1.0\
```

e in particolare:

```text
dist-release\v1.0\DA_CARICARE\
```

La pipeline deve aver raccolto lì gli asset destinati alla Release.

---

# STEP 4 — VERIFICARE GLI ARTEFATTI PRIMA DELL'UPLOAD

Prima di caricare qualsiasi cosa su GitHub, controllare che in `DA_CARICARE` siano presenti gli asset previsti, indicativamente:

```text
PostiPerfetti-1.0-setup.exe
PostiPerfetti-1.0-setup.exe.sha256
PostiPerfetti-1.0-linux.tar.gz
install.sh
SHA256SUMS
```

Verificare anche:

- `MANIFEST_RELEASE.txt`;
- `PUBBLICAZIONE_GITHUB.txt`.

Seguire le istruzioni prodotte dalla pipeline.

Ricordare:

- `PostiPerfetti-1.0-linux.tar.gz` è il pacchetto Linux di PostiPerfetti e va caricato come asset;
- i file `Source code (zip)` e `Source code (tar.gz)` che GitHub mostra automaticamente sono invece archivi del repository e NON sostituiscono `PostiPerfetti-1.0-linux.tar.gz`.

---

# STEP 5 — PUBBLICAZIONE SU GITHUB

Omar non usa Git da terminale.

NON proporre:

```text
git status
git add
git commit
git push
git tag
```

La pubblicazione verrà gestita tramite interfaccia GitHub.

Guidarlo passo passo nella creazione della Release:

- tag: `v1.0`;
- titolo coerente con PostiPerfetti 1.0;
- testo della Release basato sul `CHANGELOG.md`, se opportuno;
- upload manuale degli asset presenti in `DA_CARICARE`.

Non pubblicare asset provenienti da:

```text
build
dist
dist-installer
dist-linux
```

come sorgenti “a scelta”.

La fonte operativa per l'upload deve essere:

```text
dist-release\v1.0\DA_CARICARE
```

---

# STEP 6 — VERIFICA DELLA RELEASE PUBBLICA

Dopo che la Release GitHub `v1.0` è realmente pubblicata, NON dichiarare ancora concluso il lavoro.

Verificare almeno:

## Windows

Scaricare dalla Release pubblica:

```text
PostiPerfetti-1.0-setup.exe
```

e verificare che sia realmente scaricabile e installabile.

Non serve rifare l'intero collaudo funzionale già completato, salvo anomalie.

## Linux

Questa verifica è particolarmente importante.

Usare l'`install.sh` ufficialmente pubblicato nella Release e verificare che:

- punti realmente alla Release/tag `v1.0`;
- riesca a recuperare gli asset pubblicati;
- gli SHA-256 corrispondano;
- l'installazione parta dagli asset effettivamente presenti su GitHub.

Questa è la prova finale del percorso pubblico, non soltanto della copia locale.

---

# QUANDO DICHIARARE POSTIPERFETTI 1.0 RILASCIATO

Soltanto quando sono verdi:

- repository definitivo;
- README definitivo;
- istruzioni inline definitive;
- test installer Linux reali;
- metadati Windows;
- conservazione dati dopo reinstallazione;
- `CHANGELOG.md` chiuso con la data reale;
- `CREA_RELEASE.cmd` definitivo concluso con successo;
- asset corretti presenti su GitHub Release `v1.0`;
- installer Windows pubblico scaricabile;
- `install.sh` pubblico verificato contro gli asset realmente pubblicati.

A quel punto la Release 1.0 può essere considerata:

> **CREATA, PUBBLICATA E COLLAUDATA.**

---

# METODO DI LAVORO

Procedere sempre uno step alla volta.

Se uno step è verde, dichiararlo CHIUSO e passare al successivo.

Se fallisce:

1. fermarsi;
2. analizzare il problema concreto;
3. proporre una correzione chirurgica;
4. far ripetere soltanto la prova necessaria;
5. non aprire cantieri laterali.

Per modifiche a file esistenti, fornire sempre blocchi precisi:

**CERCA**

e

**SOSTITUISCI CON**

Omar non è programmatore: spiegare sempre in termini semplici cosa sta facendo la pipeline e perché, senza presupporre conoscenze tecniche.

L'obiettivo della sessione non è migliorare ulteriormente PostiPerfetti:

> **l'obiettivo è rilasciare correttamente PostiPerfetti 1.0.**