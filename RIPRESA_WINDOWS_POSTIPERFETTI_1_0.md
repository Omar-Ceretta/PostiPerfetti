# PostiPerfetti 1.0 — Ripresa audit/release da Windows

## Scopo della prossima sessione

Riprendere **senza riaprire l'audit da capo** e chiudere il collaudo Windows della pipeline di Release.

La parte funzionale dell'audit è sostanzialmente conclusa. La CI pubblica GitHub (`pytest`) è verde su Python **3.10, 3.11, 3.12, 3.13 e 3.14**.

**NON sono problemi da riaprire per la 1.0:**
- firma digitale Windows;
- email istituzionale dell'autore;
- crescita dello Storico (rinviata a una versione successiva).

---

# ATTENZIONE PRIORITARIA PER IL PROSSIMO CHATGPT

Prima di far eseguire qualsiasi build, **leggere i file Windows realmente presenti nella copia di lavoro dell'utente**.

Al termine della sessione precedente è emersa una possibile incoerenza nel repository pubblico: `crea_release_windows.ps1` appare aggiornato alla nuova pipeline, mentre alcune copie pubbliche di `crea_installer_windows.ps1` / `postiperfetti_setup.iss` sembrano ancora appartenere alla versione precedente (per esempio riferimenti a `version_info.txt` o versione `1.0` scritta direttamente nell'ISS).

Quindi:

1. NON presumere che i file Windows siano sincronizzati.
2. Controllare almeno:
   - `packaging/windows/crea_installer_windows.ps1`
   - `packaging/windows/build_windows.ps1`
   - `packaging/windows/postiperfetti_setup.iss`
   - `packaging/windows/PostiPerfetti.spec`
   - `packaging/windows/requirements-build-windows.txt`
   - `packaging/windows/CREA_RELEASE.cmd`
   - `packaging/windows/crea_release_windows.ps1`
   - `moduli/versione.py`
3. Il contratto corretto è:
   - `moduli/versione.py` = fonte unica della versione;
   - **nessun** `packaging/windows/version_info.txt` statico;
   - `postiperfetti_setup.iss` riceve la versione dall'esterno;
   - `requirements-build-windows.txt` congela PyInstaller;
   - `CREA_INSTALLER.cmd` = percorso rapido/iterativo;
   - `CREA_RELEASE.cmd` = percorso severo/finale.
4. Se c'è incoerenza, correggerla **prima** del collaudo.

Per ogni modifica a file esistenti, dare all'utente blocchi **CERCA / SOSTITUISCI CON** precisi.  
L'utente NON usa Git locale: niente `git status`, `git diff`, `commit`, `pull`, ecc.

---

# ISTRUZIONI PER OMAR — COSA FARE SU WINDOWS

## 1. Preparazione

Usare la copia **più aggiornata** di PostiPerfetti.

Servono:
- Python 64 bit, versione 3.10–3.14;
- Inno Setup 6.6 o successivo;
- connessione Internet per creare da zero l'ambiente di build.

Aprire la root `PostiPerfetti` in Esplora file.

Poi: **tasto destro in uno spazio vuoto → Apri nel Terminale / PowerShell**.

Non eseguire ancora la Release finale.

---

## 2. Primo comando: COLLAUDO della pipeline

Dalla **root del progetto**, in PowerShell:

```powershell
.\packaging\windows\CREA_RELEASE.cmd COLLAUDO
```

Questo è il comando principale della prossima sessione.

Se compare un errore:
- NON correggere a tentativi;
- copia dal terminale il blocco dell'errore, con qualche riga precedente;
- incollalo a ChatGPT.

Se termina bene, deve comparire una cartella simile a:

```text
dist-release\
└── COLLAUDO-v1.0\
    ├── ARTEFATTI_DI_COLLAUDO\
    │   ├── PostiPerfetti-1.0-setup.exe
    │   ├── PostiPerfetti-1.0-setup.exe.sha256
    │   ├── PostiPerfetti-1.0-linux.tar.gz
    │   ├── install.sh
    │   └── SHA256SUMS
    ├── MANIFEST_RELEASE.txt
    └── PUBBLICAZIONE_GITHUB.txt
```

Gli artefatti di `COLLAUDO` **NON vanno pubblicati**.

---

## 3. Qui arriva il primo “doppio clic”

Aprire:

```text
dist-release\COLLAUDO-v1.0\ARTEFATTI_DI_COLLAUDO\
```

e fare **doppio clic su `PostiPerfetti-1.0-setup.exe`**.

Installare normalmente PostiPerfetti.

Poi verificare almeno:
- avvio dal Menu Start;
- apertura della GUI;
- apertura cartella classi;
- salvataggio/apertura di un Report o Excel;
- presenza dei file-classe di esempio.

---

## 4. Qui arriva la prova “aprilo due volte”

Con PostiPerfetti già aperto, tentare di avviarlo **una seconda volta** dal Menu Start.

Atteso: la seconda istanza deve essere bloccata/avvisata; la prima deve restare funzionante.

Poi chiudere la prima istanza e verificare che un nuovo avvio normale riesca.

---

## 5. Controllare le versioni Windows

Controllare:

```text
dist\PostiPerfetti\PostiPerfetti.exe
dist-installer\PostiPerfetti-1.0-setup.exe
```

Per ciascuno:

**tasto destro → Proprietà → Dettagli**

Atteso:
- versione prodotto coerente con **1.0**;
- versione file coerente con **1.0.0.0**.

Se i valori sono diversi, fermarsi e riferire esattamente cosa compare.

---

## 6. Disinstallazione / reinstallazione

Dalla voce di disinstallazione di PostiPerfetti:

1. disinstallare scegliendo **NO** quando viene chiesto se eliminare i dati;
2. verificare che `classi`, `stato` e `log` siano rimasti;
3. reinstallare usando lo stesso `PostiPerfetti-1.0-setup.exe`;
4. verificare che i dati conservati siano ancora presenti.

A collaudo finito si può anche provare una disinstallazione scegliendo **SÌ** all'eliminazione dei dati di prova, per verificare il percorso completo.

---

## 7. Secondo comando: prova della guardia finale

Soltanto DOPO che `COLLAUDO` è completamente verde, dalla **root del progetto**:

```powershell
.\packaging\windows\CREA_RELEASE.cmd
```

Finché `CHANGELOG.md` contiene:

```text
1.0 — in preparazione
```

questa esecuzione **DEVE FALLIRE PRESTO** dicendo, in sostanza, che il Changelog non è ancora chiuso con una data.

Questo fallimento è VOLUTO: dimostra che la pipeline rifiuta una Release finale non ancora pronta.

**Non cambiare ancora il Changelog per aggirare la guardia.**

---

# STATO LINUX / GITHUB

Sono già presenti e non vanno riaperti:
  1. il controllo di `libEGL.so.1` nell'installer Linux, con gestione dei pacchetti per Debian/Ubuntu, Fedora, Arch e openSUSE;
  2. la GitHub Action `installer-linux.yml`, che verifica il contratto dell'installer su Ubuntu, Fedora, Arch e openSUSE.

La CI multi-distro controlla il contratto dell'installer e i pacchetti, ma non sostituisce il successivo collaudo dell'installer su sistemi Linux reali.

---

# QUANDO POSSIAMO DIRE “AUDIT CHIUSO”

Non dichiarare chiusa la release finché non sono verdi:

- CI pytest GitHub 3.10–3.14 — **GIÀ VERDE**;
- eventuale CI Linux multi-distro;
- `CREA_RELEASE.cmd COLLAUDO`;
- metadati reali EXE/Setup Windows;
- installazione e avvio Windows reali;
- blocco seconda istanza;
- disinstallazione conservativa + reinstallazione;
- prova che `CREA_RELEASE.cmd` finale rifiuti il Changelog ancora “in preparazione”.

Solo dopo si passerà alla vera pubblicazione 1.0:
- data reale nel `CHANGELOG.md`;
- `CREA_RELEASE.cmd` senza `COLLAUDO`;
- upload manuale degli asset indicati dalla pipeline;
- creazione Release/tag `v1.0` su GitHub;
- prova dell'`install.sh` ufficiale contro gli asset realmente pubblicati.

---

## Metodo di lavoro per il prossimo ChatGPT

Procedere **uno step alla volta**:

**ispezione → eventuale patch chirurgica → comando/prova esatta → risultato → CHIUSA.**

Non proporre refactoring laterali durante il collaudo.

Se un comando fallisce, analizzare quel fallimento prima di passare oltre.

Il prossimo obiettivo immediato è semplice:

> **far arrivare `CREA_RELEASE.cmd COLLAUDO` fino in fondo su Windows e collaudare davvero ciò che produce.**
