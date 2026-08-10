# Mappa dei moduli di «PostiPerfetti»

> **Versione di riferimento:** 0.8.0.
> 
> Questo documento descrive in modo sintetico l'organizzazione interna di «PostiPerfetti».  
> Non è una documentazione delle singole funzioni: serve a capire **quali parti compongono il programma e quale responsabilità ha ciascuna**.

## 1. Vista d'insieme

Il programma è organizzato per responsabilità separate. In forma molto semplificata:

```text
AVVIO E INTERFACCIA
        │
        ▼
SESSIONE, CLASSE E CONFIGURAZIONE
        │
        ▼
PREPARAZIONE DEL CALCOLO
        │
        ▼
MOTORI DI RICERCA
(coppie / terzetti)
        │
        ▼
VALUTAZIONE E SELEZIONE
        │
        ▼
ANTEPRIMA, STORICO, REPORT ED ESPORTAZIONI
```

La directory `moduli/` contiene **51 file Python**: 50 moduli operativi più `__init__.py`, che identifica esplicitamente la directory come package Python.  
A questi si aggiunge `postiperfetti.py`, nella root del progetto, che compone l'applicazione principale.

---

## 2. Avvio, composizione e percorsi

| File / modulo | A cosa serve |
|---|---|
| `postiperfetti.py` | È il punto di ingresso dell'applicazione. Crea la finestra principale, compone i vari mixin dell'interfaccia, imposta la gestione dei crash e avvia Qt. |
| `moduli/__init__.py` | File vuoto che identifica `moduli/` come package Python. Non contiene logica applicativa. |
| `postiperfetti_launcher.py` | Launcher Linux: prepara e controlla l'ambiente virtuale, verifica le dipendenze e avvia il programma. |
| `percorsi.py` | Definisce in modo centralizzato dove si trovano `risorse/`, `classi/`, `stato/`, `log/` e i file esportati. |

---

## 3. Modello dati, classi e stato della sessione

| Modulo | A cosa serve |
|---|---|
| `studenti.py` | Definisce il modello `Student` e le chiavi stabili usate per identificare e ordinare gli studenti. |
| `file_classe.py` | Legge, valida e scrive i file `.txt` delle classi nei formati supportati. Controlla nomi, genere, posizioni, affinità e incompatibilità. |
| `configurazione.py` | Gestisce `configurazione.json`, lo Storico, le blacklist di rotazione, i backup e il salvataggio sicuro dello stato. |
| `stato_sessione.py` | Raccoglie lo stato operativo della sessione corrente: classe caricata, aula, risultato mensile e stato annuale. |
| `stato_mensile.py` | Tiene traccia del ciclo di vita dell'ultima assegnazione mensile: assente, da salvare, salvata. |
| `stato_annuale.py` | Tiene traccia delle fasi dell'elaborazione annuale e delle informazioni mostrate durante l'attesa. |

---

## 4. Aula e geometria

| Modulo | A cosa serve |
|---|---|
| `aula.py` | Costruisce la geometria dell'aula, i banchi e le file. Gestisce i layout per coppie e terzetti, il FISSO e gli eventuali blocchi finali. |
| `configurazione_aula_ui.py` | Collega i controlli grafici dell'aula alla configurazione effettivamente usata dal motore. |
| `risultato_corrente_ui.py` | Disegna nella finestra principale la disposizione appena calcolata. |

---

## 5. Motore a coppie

| Modulo | A cosa serve |
|---|---|
| `vincoli.py` | Calcola la qualità di ogni possibile vicinanza e contiene il backtracking che cerca una formazione completa di coppie. Implementa la cascata T1–T4. |
| `algoritmo.py` | Coordina l'intera assegnazione a coppie: FISSO, eventuale trio, formazione delle coppie, regola della blacklist, collocazione fisica e diagnosi dei fallimenti. |
| `generazione.py` | Costruisce un candidato mensile completo e, quando serve, confronta più candidati con il meccanismo best-of-N. |
| `strato_storico.py` | Applica la memoria delle vicinanze già usate: penalità di rotazione, indicazione di quando una coppia era già comparsa e aggiornamento delle adiacenze a terzetti. |
| `metrica_pulizia.py` | Misura quanto un candidato è “pulito”: prima i riusi, poi le incompatibilità tollerate, infine le affinità soddisfatte. La stessa logica è condivisa con i terzetti. |

---

## 6. Motore a terzetti

| Modulo | A cosa serve |
|---|---|
| `motore_terzetti.py` | Suddivide gli studenti in terzetti e nell'eventuale blocco finale (coppia, quartetto o due quartetti). Valuta anche l'ordine interno dei membri e usa la stessa cascata T1–T4. |
| `aula.py` | Oltre alla modalità a coppie, traduce i gruppi del motore a terzetti in posizioni fisiche nell'aula. |
| `metrica_pulizia.py` | Valuta le sole adiacenze reali: in un gruppo in fila contano i vicini consecutivi, non gli estremi lontani. |

---

## 7. Casualità riproducibile e strategie di ricerca

| Modulo | A cosa serve |
|---|---|
| `casualita.py` | Gestisce i seed e crea generatori casuali locali e riproducibili. Permette di ottenere gli stessi risultati a parità di input e seed. |
| `strategie_ricerca.py` | Contiene la strategia produttiva `C1` e alcune strategie sperimentali usate nei collaudi. `C1` accelera il backtracking a coppie ricordando gli stati già dimostrati falliti senza cambiare l'ordine o il significato della ricerca. |
| `diagnostica_ricerca.py` | Raccoglie telemetria dettagliata della ricerca quando la diagnostica è esplicitamente attivata. Non modifica le scelte del motore. |

> **Da non confondere:** T1–T4 sono i quattro livelli della cascata di assegnazione; `C1` è invece una strategia interna di ricerca. Sono due concetti diversi.

---

## 8. Generazione annuale e politica di selezione

| Modulo | A cosa serve |
|---|---|
| `annuale.py` | Genera intere annate, confronta più stagioni candidate e coordina il riordino finale dei mesi. Non contiene codice grafico. |
| `politica_annuale.py` | Analizza stagioni già generate, applica la politica protetta S1/R12 e migliora la distanza temporale fra i riusi senza modificare i gruppi. |
| `risultati_annuali.py` | Trasforma il risultato annuale in mesi pronti per l'anteprima e salva l'intera annata nello Storico con un'unica operazione atomica. |
| `anteprima_annuale.py` | Finestra che permette di scorrere i mesi dell'annata, accettarla, scartarla ed eventualmente salvarla. |

---

## 9. Calcolo in background e comunicazione con la GUI

| Modulo | A cosa serve |
|---|---|
| `flusso_mensile_ui.py` | Coordina dalla GUI l'avvio e la conclusione del calcolo mensile, sia a coppie sia a terzetti. |
| `worker_mensile.py` | Ponte Qt verso il processo separato usato dal Mensile a terzetti. |
| `processo_mensile.py` | Esegue il calcolo mensile a terzetti in un processo Python separato e restituisce un risultato serializzabile. |
| `flusso_annuale_ui.py` | Coordina dalla GUI avvio, progresso, annullamento, risultato e apertura dell'anteprima annuale. |
| `worker_annuale.py` | Ponti Qt che avviano l'Annuale a coppie o a terzetti in processi separati. |
| `processo_annuale.py` | Esegue il motore annuale vero e proprio fuori dal processo della GUI. |
| `ponte_processo.py` | Infrastruttura comune: serializza una fotografia degli input, avvia il processo figlio e inoltra i messaggi alla GUI. |
| `supervisione_processi.py` | Chiude e raccoglie in modo finito i processi di calcolo quando hanno terminato o il canale di comunicazione non è più utilizzabile. |

Il Mensile a coppie usa invece un `QThread` dedicato definito in `flusso_mensile_ui.py`; lavora su copie degli input e non modifica direttamente gli oggetti vivi della sessione grafica.

---

## 10. Salvataggio, Storico, report ed esportazioni

| Modulo | A cosa serve |
|---|---|
| `salvataggio_mensile_ui.py` | Registra nello Storico il risultato mensile accettato dall'utente. |
| `storico_ui.py` | Mostra e gestisce lo Storico: consultazione, ricostruzione dei layout, eliminazione ed esportazione. |
| `esportazione.py` | Costruisce report testuali e file Excel/TXT delle assegnazioni. |
| `statistiche.py` | Calcola e mostra statistiche storiche per classe e ne gestisce l'esportazione. |
| `statistiche_generali.py` | Produce le statistiche riassuntive comuni a coppie e terzetti in una forma strutturata. |
| `righe_statistiche.py` | Decide quali righe statistiche meritano di essere evidenziate nei riepiloghi. |
| `widget_statistiche.py` | Trasforma le righe statistiche strutturate in widget Qt. |

---

## 11. Interfaccia e ciclo di vita

| Modulo | A cosa serve |
|---|---|
| `ciclo_vita_ui.py` | Coordina inizializzazione, cambio tema, chiusura protetta e comportamento generale della finestra principale. |
| `pannelli_principali.py` | Costruisce i pannelli e i principali controlli della finestra. |
| `sessione_classe_ui.py` | Gestisce apertura, cambio e chiusura della classe e protegge i risultati non ancora salvati. |
| `editor_studenti.py` | Editor grafico dei file-classe: studenti, genere, posizione, affinità e incompatibilità. |
| `istruzioni.py` | Contiene le finestre informative, la guida e i crediti mostrati dall'applicazione. |
| `tema.py` | Definisce la palette semantica dei temi chiaro e scuro. |
| `stili.py` | Costruisce e applica gli stylesheet Qt dell'interfaccia. |
| `utilita.py` | Raccolta di servizi condivisi per finestre, icone, popup, conteggi, report e adattamento allo schermo. |
| `lingua.py` | Piccoli helper per plurali e testi dinamici dell'interfaccia. |

---

## 12. Diagnostica della GUI

| Modulo | A cosa serve |
|---|---|
| `profilo_gui.py` | Misura, solo quando richiesto, la durata di operazioni sincrone della GUI. |
| `watchdog_gui.py` | Sorveglia l'event loop e registra eventuali blocchi o rallentamenti della GUI quando la diagnostica è attivata. |

Questi moduli sono strumenti di osservazione: **non determinano l'assegnazione dei posti**.

---

## 13. Il percorso più importante, in una riga

Per orientarsi nel codice senza leggere tutto, il percorso principale può essere ricordato così:

```text
file_classe.py
    ↓
studenti.py + configurazione.py
    ↓
flusso_mensile_ui.py / flusso_annuale_ui.py
    ↓
generazione.py / motore_terzetti.py / annuale.py
    ↓
vincoli.py + algoritmo.py + metrica_pulizia.py + strato_storico.py
    ↓
aula.py
    ↓
risultato corrente / anteprima
    ↓
salvataggio_mensile_ui.py / risultati_annuali.py
    ↓
configurazione.py → Storico
```

Non tutti i moduli vengono attraversati in ogni operazione: il programma sceglie il ramo appropriato in base a **Mensile o Annuale** e **coppie o terzetti**.

---

## 14. Una chiave di lettura della struttura

La suddivisione in molti file non indica che il programma esegua decine di passaggi indipendenti. Al contrario, serve a separare responsabilità diverse:

- i moduli dei **dati** non devono conoscere la GUI;
- i moduli del **motore** devono poter essere collaudati senza aprire finestre;
- i moduli della **GUI** preparano input e mostrano risultati, senza reinventare l'algoritmo;
- i moduli di **persistenza** controllano salvataggi, Storico e recupero;
- i moduli di **diagnostica** osservano il comportamento senza modificarlo.

Questa separazione rende più semplice capire, verificare e mantenere «PostiPerfetti» senza concentrare tutto il programma in un unico file.
