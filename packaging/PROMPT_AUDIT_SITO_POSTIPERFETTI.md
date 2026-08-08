# PROMPT DI RIPRESA — AUDIT SITO POSTIPERFETTI

Ciao Chat. In questa sessione voglio lavorare **esclusivamente sul sito web di PostiPerfetti**, che ti fornirò come archivio `.zip`.

Il sito è la “vetrina” pubblica del progetto e vorrei sottoporlo a un audit generale prima della pubblicazione definitiva.

Non voglio, in questa sessione, riprendere audit del codice Python del programma né iniziare il packaging Windows: entrambi hanno già un loro stato ben definito.  
**Prima completiamo e consolidiamo il sito. Solo dopo, in una sessione separata, passerò a Windows per costruire e collaudare l’EXE e l’installer.**

---

## 1. Contesto del progetto

**PostiPerfetti** è un software open-source in Python/PySide6 pensato principalmente per docenti.

Serve ad assegnare automaticamente i posti degli studenti in aula tenendo conto, fra le altre cose, di:

- incompatibilità fra studenti;
- affinità;
- preferenze di posizione;
- studenti da collocare in prima o ultima fila;
- posizione FISSO;
- preferenza per gruppi misti M/F;
- rotazione delle vicinanze nel tempo;
- assegnazioni mensili o annuali;
- disposizione a coppie o terzetti.

Il progetto è arrivato alla **R0.8**, ormai consolidata.

Il codice applicativo ha attraversato audit, refactoring, test di regressione, collaudi semantici, stress test e interventi sulla responsività della GUI.

La suite consolidata è:

```text
278 passed, 2 skipped
```

Per questa sessione considera quindi il **programma Python sostanzialmente congelato**: non voglio riaprire modifiche algoritmiche o architetturali salvo che il sito contenga affermazioni tecniche palesemente incoerenti con il software.

---

## 2. Stato del repository

La root di PostiPerfetti è stata recentemente ripulita e riorganizzata.

La documentazione pubblica è stata semplificata e resa più leggibile.

Fra i documenti principali vi sono ora:

```text
documentazione/
├── README.md
├── COME_FUNZIONA_POSTIPERFETTI.md
├── MAPPA_MODULI.md
├── INSTALLAZIONE_AVVIO_E_DISINSTALLAZIONE.md
└── sviluppo/
    ├── README.md
    ├── strumenti/
    ├── test/
    ├── strumenti_diagnostica/
    └── dati_validazione/
```

La filosofia è: **pochi documenti pubblici chiari**, con il laboratorio tecnico raccolto sotto `documentazione/sviluppo/`.

La documentazione “Come funziona” è stata riscritta per utenti non tecnici e descrive, fra le altre cose:

- i quattro Tentativi T1, T2, T3 e T4;
- vincoli assoluti e preferenze;
- ricerca con ritorno indietro;
- memoria delle vicinanze già usate;
- confronto fra più soluzioni;
- differenze Mensile/Annuale e coppie/terzetti;
- guardie di qualità dell’Annuale;
- alcune formule matematiche reali usate per valutare le soluzioni.

Non serve rimettere in discussione tutto questo nell’audit del sito.

---

## 3. Stato del packaging

### Linux

Il packaging Linux è già stato consolidato.

Esistono:

```text
packaging/linux/install.sh
packaging/linux/uninstall.sh
```

L’installer installa il runtime, preserva i dati dell’utente negli aggiornamenti e l’uninstaller conserva per impostazione predefinita:

```text
classi/
stato/
log/
```

salvo richiesta esplicita di eliminazione completa.

### Windows

Il packaging Windows è **già stato preparato da Linux ma NON ancora materialmente costruito o collaudato su Windows**.

In:

```text
packaging/windows/
```

sono stati predisposti:

```text
PostiPerfetti.spec
postiperfetti_setup.iss
version_info.txt
postiperfetti.ico
icon.svg
icon-512.png
info_pre_installazione.txt
info_dopo_installazione.txt
build_windows.ps1
COLLAUDO_WINDOWS.md
LEGGIMI.md
```

La scelta progettuale è:

- PyInstaller `onedir`;
- installazione Inno Setup per singolo utente;
- nessun UAC come impostazione ordinaria;
- dati `classi/`, `stato/`, `log/` preservati negli aggiornamenti;
- disinstallazione conservativa, con domanda esplicita prima di cancellare i dati.

È stata inoltre aggiunta al programma la chiamata a:

```python
multiprocessing.freeze_support()
```

necessaria per le build PyInstaller Windows che usano processi `spawn`.

**Non dobbiamo eseguire ora questa fase.**

Dopo il sito, farò reboot su Windows e dedicheremo una sessione specifica al packaging e al collaudo.

---

## 4. Versionamento

Per la nuova pubblicazione è stata scelta la numerazione:

```text
0.8.0
```

con futuro tag GitHub:

```text
v0.8.0
```

La vecchia Release/tag `v.2.0`, nata da una precedente gestione ingenua della numerazione, è stata eliminata.

Il nuovo tag `v0.8.0` NON deve ancora essere creato: verrà creato soltanto dopo il collaudo definitivo della distribuzione Windows.

---

## 5. Il sito

Il sito è statico ed è stato realizzato per presentare PostiPerfetti.

Non sono un web developer professionista: ho lavorato progressivamente su HTML, CSS e JavaScript con assistenza, quindi voglio una revisione **molto concreta del codice effettivo**, senza presumere che una soluzione sia corretta solo perché “sembra funzionare” sul mio computer.

In passato abbiamo già lavorato su alcuni aspetti del sito, fra cui:

- tema chiaro/scuro;
- immagini e mockup;
- lightbox;
- screenshot del programma;
- pulsante per copiare l’indirizzo email;
- grafica responsive;
- logo, icona e favicon;
- presentazione visuale del funzionamento di PostiPerfetti.

Il sito dovrebbe essere ormai vicino alla forma definitiva.

---

## 6. Eccezione importante: la Guida

La **Guida** del programma/sito non è ancora ultimata.

Gli screenshot definitivi verranno rifatti soltanto quando l’interfaccia grafica del programma sarà definitivamente congelata.

Perciò:

- non considerare l’assenza o incompletezza degli screenshot della Guida come un difetto del sito da correggere ora;
- non perdere tempo a perfezionare contenuti della Guida che dipendono da screenshot ancora da produrre;
- segnala pure eventuali problemi **strutturali** della sezione Guida (HTML, CSS, navigazione, accessibilità, responsive, percorsi, lightbox ecc.), ma non trattare come errore il fatto che alcuni contenuti siano provvisori o mancanti.

---

## 7. Cosa ti chiedo quando ti avrò inviato lo ZIP

Voglio una **revisione generale e sistematica dell’intero sito**.

Non limitarti all’estetica.

La priorità è verificare che la “vetrina” del progetto sia tecnicamente solida.

### A. Struttura generale

Controlla:

- struttura delle directory;
- organizzazione di HTML, CSS, JavaScript e asset;
- duplicazioni;
- file inutilizzati;
- asset orfani;
- riferimenti a file inesistenti;
- percorsi fragili;
- dipendenze implicite;
- eventuali residui di vecchie versioni;
- eventuali file che non dovrebbero essere pubblicati.

Se trovi file apparentemente inutilizzati, **verifica davvero le referenze prima di proporne la cancellazione**.

### B. HTML

Controlla almeno:

- HTML semanticamente corretto;
- gerarchia `h1` / `h2` / `h3`;
- landmark (`header`, `nav`, `main`, `footer`, ecc.);
- corretto uso di pulsanti e link;
- attributi `lang`;
- titoli pagina;
- meta tag importanti;
- immagini e attributi `alt`;
- form o controlli eventualmente presenti;
- elementi interattivi utilizzabili senza mouse;
- correttezza degli ID;
- link interni;
- anchor;
- eventuali duplicazioni di ID;
- markup obsoleto o fragile.

### C. CSS

Controlla:

- organizzazione e leggibilità;
- specificità eccessiva;
- `!important` evitabili;
- regole duplicate o contraddittorie;
- media query;
- responsive reale;
- dimensioni fisse problematiche;
- overflow;
- uso corretto di `rem`, `%`, `vw`, `clamp()`, flex e grid;
- immagini responsive;
- tipografia;
- spaziature;
- contrasto;
- focus visibile;
- stati hover/focus/active;
- tema chiaro/scuro;
- `prefers-color-scheme`, se pertinente;
- `prefers-reduced-motion`, se ci sono animazioni/transizioni significative.

Voglio sapere se il sito potrebbe rompersi o diventare scomodo su:

- monitor desktop;
- notebook;
- tablet;
- smartphone;
- schermi stretti;
- zoom browser elevato;
- font ingranditi.

### D. JavaScript

Questa è una parte particolarmente importante.

Controlla:

- errori potenziali;
- query DOM che presumono elementi sempre presenti;
- listener duplicati;
- race o dipendenze dall’ordine di caricamento;
- funzioni globali inutili;
- variabili non usate;
- gestione degli errori;
- compatibilità browser;
- uso fragile di `localStorage`;
- lightbox;
- cambio tema;
- copia negli appunti;
- navigazione;
- apertura/chiusura di elementi interattivi;
- tastiera;
- `Escape`;
- gestione del focus;
- comportamento senza JavaScript, quando sensato.

Evita refactoring “per gusto”: proponi modifiche solo quando aumentano davvero robustezza, chiarezza, compatibilità o manutenzione.

---

## 8. Accessibilità — priorità alta

Voglio che il sito sia utilizzabile anche da chi usa:

- tastiera;
- screen reader;
- zoom elevato;
- impostazioni di contrasto;
- riduzione delle animazioni;
- altri ausili.

Controlla quindi attentamente:

- ordine di tabulazione;
- focus visibile;
- focus trapping nelle lightbox/modali;
- restituzione del focus alla chiusura;
- `aria-label`, `aria-labelledby`, `aria-describedby` dove realmente necessari;
- evitare ARIA superflua quando basta HTML semantico;
- immagini decorative;
- testi alternativi;
- link comprensibili fuori contesto;
- pulsanti con nome accessibile;
- contrasto testo/sfondo;
- contrasto degli elementi UI;
- dimensione delle aree cliccabili;
- contenuti leggibili a 200% / 400%;
- eventuali problemi causati da `overflow:hidden`;
- struttura corretta per screen reader;
- skip link, se utile;
- comportamento di menu, lightbox e controlli da tastiera.

Quando serve verificare standard o compatibilità attuali, usa fonti autorevoli come **W3C/WAI, WHATWG o MDN** e distingui chiaramente ciò che deriva dal codice del sito da ciò che deriva dalle specifiche esterne.

---

## 9. Cross-browser e cross-device

Vorrei evitare un sito che funzioni soltanto sul mio Chrome/Fedora.

Valuta quindi possibili problemi con:

- Chrome / Chromium;
- Firefox;
- Edge;
- Safari;
- browser mobili Android;
- Safari iOS/iPadOS.

Non serve inseguire browser obsoleti, ma voglio una base moderna e ragionevolmente robusta.

Se una funzionalità richiede API non universalmente supportate, verifica:

- se esiste fallback;
- se il sito degrada bene;
- se l’assenza dell’API rompe una funzione essenziale.

---

## 10. Performance e caricamento

Controlla:

- immagini troppo pesanti;
- PNG/JPG/WebP/SVG e uso appropriato dei formati;
- immagini caricate inutilmente;
- lazy loading quando opportuno;
- dimensioni intrinseche delle immagini;
- rischio di layout shift;
- font;
- CSS/JS caricati;
- eventuali risorse duplicate;
- caching, nei limiti di un sito statico;
- uso ragionevole di script inline o esterni.

Non voglio micro-ottimizzazioni premature: concentrati sulle cose che possono avere un impatto reale.

---

## 11. SEO e condivisione

Il sito serve anche a far conoscere un software open-source per insegnanti.

Controlla quindi almeno:

- `<title>`;
- meta description;
- canonical, se necessario;
- favicon;
- Open Graph;
- Twitter/X card, se presenti o utili;
- struttura dei contenuti;
- heading;
- link al repository;
- eventuale `robots.txt`;
- eventuale `sitemap.xml`;
- eventuali structured data solo se realmente utili e corretti.

Non trasformare però il sito in un progetto SEO commerciale: resta una vetrina semplice, chiara e credibile.

---

## 12. Privacy e sicurezza

Il sito è statico e non dovrebbe raccogliere dati degli utenti.

Controlla:

- script di terze parti;
- tracker;
- analytics;
- risorse remote;
- link esterni;
- `target="_blank"` e relativi attributi;
- eventuali superfici XSS create dal JavaScript;
- uso di `innerHTML`;
- interpolazioni non sicure;
- dati personali lasciati accidentalmente negli asset o nei file;
- indirizzo email e modalità di contatto;
- eventuali dipendenze esterne non necessarie.

Se non ci sono cookie, analytics o raccolta dati, evidenzialo come un punto positivo.

---

## 13. Contenuti, linguaggio e presentazione

Dopo l’audit tecnico, voglio anche un parere editoriale e visuale.

Valuta:

- chiarezza dei testi;
- tono;
- eventuale prolissità;
- ripetizioni;
- termini troppo tecnici;
- gerarchia delle informazioni;
- CTA;
- chiarezza del messaggio iniziale;
- comprensibilità per un docente che non conosce ancora PostiPerfetti;
- equilibrio fra testo e immagini;
- eventuali sezioni troppo dense;
- leggibilità;
- coerenza del lessico;
- efficacia della home come “vetrina”.

Puoi suggerire modifiche di stile, copy e layout, ma **distingui sempre fra:**

1. problema tecnico;
2. problema di accessibilità;
3. miglioramento consigliato;
4. puro gusto personale.

Non voglio rifare il sito da zero se non ce n’è bisogno.

---

## 14. Metodo di lavoro che preferisco

Quando ti invierò lo ZIP:

1. **analizza prima l’intero contenuto**;
2. ricostruisci struttura e relazioni fra i file;
3. non giudicare un file isolatamente se dipende da CSS/JS condivisi;
4. non proporre cancellazioni basandoti soltanto sul nome;
5. individua prima problemi reali e regressioni potenziali;
6. assegna priorità.

Vorrei una classificazione indicativa del tipo:

```text
P0 — errore grave / sito rotto / accessibilità critica
P1 — problema importante da correggere prima della pubblicazione
P2 — miglioramento raccomandato
P3 — rifinitura facoltativa
```

Se non trovi P0 o P1, dillo chiaramente: **non inventare problemi per giustificare l’audit**.

---

## 15. Modifiche: non tutto insieme

Preferisco lavorare in modo controllato.

Quindi:

- prima fammi l’audit;
- mostrami cosa hai trovato;
- spiegami perché una modifica è utile;
- distingui modifiche necessarie da cosmetiche;
- poi procediamo con patch piccole e verificabili.

Non voglio una gigantesca riscrittura automatica prima di aver discusso i risultati.

Quando proponi una patch, deve essere chiaro:

- quali file modifica;
- perché;
- rischio;
- effetto atteso;
- come verificare il risultato.

---

## 16. Attenzione alla stabilità

Una regola importante:

> **“Funziona già” non è una ragione sufficiente per non migliorare qualcosa di fragile, ma “si potrebbe scrivere diversamente” non è una ragione sufficiente per toccarlo.**

In altre parole:

- correggi fragilità reali;
- evita refactoring ornamentali;
- privilegia compatibilità, semplicità e manutenzione;
- non introdurre framework o dipendenze pesanti se HTML/CSS/JS nativi bastano;
- non complicare un sito statico semplice.

---

## 17. Obiettivo finale della sessione

Alla fine vorrei poter considerare il sito:

- tecnicamente pulito;
- robusto;
- responsive;
- accessibile;
- compatibile con browser/device moderni;
- privo di errori evidenti;
- semanticamente corretto;
- leggero;
- coerente con la R0.8 del programma;
- adatto a essere pubblicato come vera vetrina di PostiPerfetti.

La Guida potrà restare temporaneamente incompleta nei contenuti/screenshot, purché la sua struttura tecnica sia sana.

---

## 18. Dopo il sito

Quando avremo finito questo audit:

1. tornerò su Windows;
2. costruiremo `PostiPerfetti.exe` con PyInstaller usando il `.spec` già predisposto;
3. collauderemo approfonditamente l’EXE, soprattutto i processi Mensile/Annuale;
4. installeremo/useremo Inno Setup;
5. genereremo `PostiPerfetti_Setup_0.8.0.exe`;
6. testeremo installazione, aggiornamento e disinstallazione;
7. solo alla fine creeremo il tag GitHub:

```text
v0.8.0
```

e la Release pubblica.

---

## Primo passo della nuova sessione

Dopo questo prompt ti invierò lo `.zip` del sito.

**Parti direttamente dall’analisi della struttura e del codice reale contenuto nello ZIP.**

Non chiedermi di descrivere nuovamente il sito se puoi ricavare l’informazione dai file.

Ricorda soltanto l’eccezione già indicata:

> **la Guida e i suoi screenshot non sono ancora definitivi.**

Per tutto il resto, considero il sito abbastanza maturo da essere sottoposto a un vero audit pre-pubblicazione.
