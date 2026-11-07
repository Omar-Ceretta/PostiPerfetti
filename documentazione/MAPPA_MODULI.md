# ⭄ Mappa dei moduli di «PostiPerfetti»

> **Versione di riferimento:** 2.0.
> 
> Questo documento descrive in modo sintetico l'organizzazione interna di «PostiPerfetti».  
> Serve a capire **quali parti compongono il programma e quale responsabilità ha ciascuna**.

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
MOTORE DEL LAYOUT UNICO
(banchi da due e da tre)
        │
        ▼
VALUTAZIONE E SELEZIONE
        │
        ▼
ANTEPRIMA, STORICO, REPORT ED ESPORTAZIONI
```

La directory `moduli/` contiene **109 file Python**: 103 moduli operativi e 6 file `__init__.py`, che identificano il package e i cinque sottopacchetti. Le responsabilità sono raccolte in `interfaccia/`, `dominio/`, `calcolo/`, `processi/` e `persistenza/`; versione, percorsi, casualità, lingua e launcher restano direttamente in `moduli/`.  
A questi si aggiunge `postiperfetti.py`, nella root del progetto, che rappresenta l'applicazione principale.

---

## 2. Avvio, composizione e percorsi

| File / modulo | A cosa serve |
|---|---|
| `postiperfetti.py` | È il punto di ingresso dell'applicazione. Crea la finestra principale, compone i vari mixin dell'interfaccia, imposta la gestione dei crash e avvia Qt. |
| `moduli/__init__.py` | Identifica `moduli/` come package Python. Non contiene logica applicativa. |
| `moduli/postiperfetti_launcher.py` | Launcher Linux: prepara e controlla l'ambiente virtuale, verifica le dipendenze e avvia il programma. |
| `moduli/percorsi.py` | Definisce in modo centralizzato dove si trovano `risorse/`, `classi/`, `stato/`, `log/` e i file esportati. |
| `moduli/versione.py` | È la fonte unica della versione dell'applicazione. Espone il numero in formato `MAJOR.MINOR`, ne verifica la forma all'avvio, e ne deriva le varianti richieste altrove: la quaterna usata dai metadati dell'eseguibile Windows e il tag della Release. Packaging, installer e interfaccia leggono da qui: la versione non va mai riscritta a mano in un secondo file. |

---

## 3. Modello dati, classi e stato della sessione

| Modulo | A cosa serve |
|---|---|
| `moduli/dominio/studenti.py` | Definisce il modello `Student` e le chiavi stabili usate per identificare e ordinare gli studenti. |
| `moduli/persistenza/file_classe.py` | Legge, valida e scrive i file `.txt` delle classi nei formati supportati. Controlla nomi, genere, posizioni, affinità e incompatibilità. |
| `moduli/persistenza/configurazione.py` | Coordina lettura, recupero e salvataggio sicuro di `postiperfetti_configurazione.json`. Espone i comandi di modifica; delega schema, ricostruzione e operazioni sui dati a servizi senza GUI. |
| `moduli/dominio/stato_sessione.py` | Raccoglie lo stato operativo della sessione corrente: classe caricata, aula, risultato mensile e stato annuale. |
| `moduli/dominio/stato_mensile.py` | Tiene traccia del ciclo di vita dell'ultima assegnazione mensile: assente, da salvare, salvata. |
| `moduli/dominio/stato_annuale.py` | Tiene traccia delle fasi dell'elaborazione annuale e delle informazioni mostrate durante l'attesa. |
| `moduli/calcolo/ingresso_q21.py` | Definisce il contratto immutabile degli input Q21: studenti, geometria, Storico, opzioni, semi e limiti. |
| `moduli/dominio/fotografia_generazione_layout.py` | Fotografa classe e Layout all’avvio e controlla che il risultato appartenga ancora alla sessione corrente. |
| `moduli/persistenza/schema_configurazione.py` | Definisce schema, valori iniziali e validazione della configurazione in memoria, senza aprire file. |
| `moduli/persistenza/validazione_storico.py` | Valida record correnti e formati storici, metadati, copertura e coerenza delle geometrie. |

---

## 4. Aula e geometria

| Modulo | A cosa serve |
|---|---|
| `moduli/dominio/aula.py` | Costruisce e interpreta la geometria dell'aula, i banchi e le file. Conserva anche i lettori delle vecchie geometrie per consultare lo Storico; la generazione corrente usa il Layout unico. |
| `moduli/interfaccia/configurazione_aula_ui.py` | Collega i controlli grafici dell'aula alla configurazione effettivamente usata dal motore. |
| `moduli/interfaccia/risultato_corrente_ui.py` | Disegna nella finestra principale la disposizione appena calcolata. |
| `moduli/dominio/aula_personalizzata.py` | Modello puro dei banchi, degli spazi e delle marcature del Layout. |
| `moduli/dominio/layout_unico.py` | Definisce i contratti e le verifiche dei Layout con banchi da due e da tre. |
| `moduli/dominio/schema_blocchi_semantico.py` | Descrive posti, blocchi e zone fisiche senza dipendenze Qt. |
| `moduli/dominio/griglia_layout_fissa.py` | Definisce le coordinate permanenti della griglia 6 × 5. |
| `moduli/dominio/presentazione_aula_personalizzata.py` | Normalizza la piantina per mostrarla, senza modificarne la geometria semantica. |
| `moduli/interfaccia/editor_aula_personalizzata.py` | Editor Qt del Layout, con bozze e controlli sulla geometria. |
| `moduli/interfaccia/canvas_layout_aula.py` | Gestisce selezione degli spazi, inserimento e spostamento dei banchi nel Layout. |
| `moduli/interfaccia/vista_layout_fisso.py` | Dispone in modo responsive le posizioni permanenti della griglia. |
| `moduli/interfaccia/arredi_visualizzazione.py` | Disegna la zona docente con la stessa convenzione nelle diverse viste. |

---

## 5. Motore dei gruppi nel Layout unico

| Modulo | A cosa serve |
|---|---|
| `moduli/dominio/vincoli.py` | Calcola la qualità di ogni possibile vicinanza e definisce i parametri della cascata T1–T4. Conserva anche il backtracking storico a coppie; la ricerca del Layout unico è in `moduli/calcolo/motore_blocchi.py`. |
| `moduli/calcolo/motore_blocchi.py` | Coordina la formazione di gruppi da due e da tre con T1–T4, blacklist, FISSO e geometria del Layout. Usa il backend Q17 e consegna i gruppi al matcher fisico. |
| `moduli/calcolo/valutazione_gruppi.py` | Valuta i gruppi ordinati, le adiacenze e le preferenze usate nella ricerca; il best-of-N mensile è coordinato da `moduli/calcolo/motore_blocchi.py`. |
| `moduli/persistenza/strato_storico.py` | Applica la memoria delle vicinanze già usate: penalità di rotazione, indicazione di quando una coppia era già comparsa e aggiornamento delle adiacenze a terzetti. |
| `moduli/dominio/metrica_pulizia.py` | Misura quanto un candidato è “pulito”: prima i riusi, poi le incompatibilità tollerate, infine le affinità soddisfatte. Questa chiave preliminare è condivisa dai gruppi da due e da tre; non esaurisce la selezione finale Q21. |
| `moduli/calcolo/ricerca_q17_contesto.py` | Backend di ricerca esplicito per il Layout unico, locale alla chiamata e senza modifiche globali. |
| `moduli/calcolo/config_calcolo_q21.py` | Fornisce una copia effimera dello Storico, aggiornata fra mesi candidati senza scrivere lo stato dell’utente. |

---

## 6. Gruppi ordinati e collocazione fisica

| Modulo | A cosa serve |
|---|---|
| `moduli/calcolo/matcher_blocchi.py` | Colloca i gruppi ordinati nei banchi reali, rispettando PRIMA e FISSO e cercando di soddisfare ULTIMA. Le capienze generate sono due e tre; i quartetti restano soltanto nei lettori storici. |
| `moduli/dominio/layout_risultato_personalizzata.py` | Traduce le collocazioni del motore nella piantina effettiva del Layout unico. |
| `moduli/dominio/metrica_pulizia.py` | Valuta le sole adiacenze reali: in un gruppo in fila contano i vicini consecutivi, non gli estremi lontani. |
| `moduli/dominio/disposizione_effettiva.py` | Fotografia semantica della disposizione risultante, usata dai controlli e dagli adattatori. |
| `moduli/dominio/editing_disposizione.py` | Gestisce gli scambi di studenti e occupanti di blocchi della stessa capienza, verifica i vincoli obbligatori e conserva le mosse annullabili senza scrivere lo Storico. |
| `moduli/dominio/adozione_dragdrop_mensile.py` | Verifica e ricostruisce la proposta Mensile dopo l'editing; distingue i posti modificati dal ritorno alla disposizione automatica e gestisce i metadati salvabili. |
| `moduli/dominio/validazione_blocchi.py` | Verifica indipendentemente unicità degli studenti, adiacenze, L3, PRIMA, FISSO e collocazioni nei blocchi. |
| `moduli/dominio/verifica_disposizione_standard.py` | Conserva le guardie fisiche dei formati standard precedenti, necessari alla compatibilità. |

---

## 7. Casualità riproducibile e strategie di ricerca

| Modulo | A cosa serve |
|---|---|
| `moduli/casualita.py` | Gestisce i seed e crea generatori casuali locali e riproducibili. Una stessa candidata è riproducibile con gli stessi input e seed; il numero di proposte esplorate entro un limite di tempo può variare con la macchina. |
| `moduli/calcolo/strategie_ricerca.py` | Contiene la strategia produttiva `C1` e alcune strategie sperimentali usate nei collaudi. `C1` accelera il backtracking a coppie ricordando gli stati già dimostrati falliti senza cambiare l'ordine o il significato della ricerca. |
| `moduli/processi/diagnostica_ricerca.py` | Raccoglie telemetria dettagliata della ricerca quando la diagnostica è esplicitamente attivata. Non modifica le scelte del motore. |
| `moduli/calcolo/diversificazione_q2.py` | Diversifica fra proposte i soli gruppi a pari punteggio di T1–T3, con semi locali. |

> **Da non confondere:** T1–T4 sono i quattro livelli della cascata di assegnazione; `C1` è invece una strategia interna di ricerca. Sono due concetti diversi. Inoltre il nome C1 è usato per il confronto preliminare delle candidate descritto in `COME_FUNZIONA.md`: non va confuso con questa strategia di ricerca.

---

## 8. Generazione annuale e politica di selezione

| Modulo | A cosa serve |
|---|---|
| `moduli/calcolo/annuale.py` | Genera sequenze di mesi, confronta più stagioni candidate e coordina il riordino dei mesi. È usato dalla pipeline Q21 condivisa anche dal Mensile. Non contiene codice grafico. |
| `moduli/calcolo/politica_annuale.py` | Analizza stagioni già generate, applica la politica protetta S1/R12 e migliora la distanza temporale fra i riusi senza modificare i gruppi. |
| `moduli/persistenza/risultati_annuali.py` | Trasforma il risultato annuale in mesi pronti per l'anteprima e salva l'intera annata nello Storico con un'unica operazione atomica. |
| `moduli/interfaccia/anteprima_annuale.py` | Finestra che permette di scorrere i mesi dell'annata, accettarla, scartarla ed eventualmente salvarla. |
| `moduli/dominio/editing_annuale.py` | Mantiene la bozza dei mesi, ricalcola cronologicamente i riusi dopo ogni modifica e gestisce annullamento globale, ripristino e indicatori dei mesi realmente modificati. |
| `moduli/calcolo/pipeline_q21_contesto.py` | Coordina la ricerca e le rifiniture comuni: un mese per Mensile, da uno a dieci per Annuale. |
| `moduli/calcolo/archivio_candidate_q21.py` | Conserva temporaneamente candidate fisiche già generate, per confrontarle senza rigenerarle. |
| `moduli/calcolo/valutazione_q21_contesto.py` | Misura le candidate con Storico e durate variabili e applica le guardie contestuali. |
| `moduli/calcolo/pianificazione_q21_contesto.py` | Pianifica le alternative fisiche e le rifiniture Q10/Q11/Q12 entro il budget. |
| `moduli/calcolo/riparazione_q5_q12_contesto.py` | Cerca miglioramenti dei riusi e di ULTIMA senza violare le protezioni previste. |
| `moduli/calcolo/recupero_q15_contesto.py` | Tenta di recuperare alternative interessanti inizialmente escluse dalle guardie. |
| `moduli/calcolo/selezione_q19_contesto.py` | Seleziona le finaliste fisiche con S1/R12, incluso il caso limitato di deroga ULTIMA. |
| `moduli/calcolo/rifinitura_q20_contesto.py` | Cerca ulteriori affinità nel vicinato della candidata selezionata, rispettando le protezioni. |
| `moduli/calcolo/riordino_pulizia_finale_q21.py` | Riordina i mesi per la presentazione finale conservando tutte le metriche già ottenute. |

---

## 9. Calcolo in background e comunicazione con la GUI

| Modulo | A cosa serve |
|---|---|
| `moduli/interfaccia/flusso_mensile_ui.py` | Coordina dalla GUI avvio e conclusione del calcolo mensile sul Layout unico. |
| `moduli/processi/worker_mensile.py` | Ponte Qt verso il processo separato usato dal Mensile Q21. |
| `moduli/processi/contratto_mensile_q21.py` | Converte e verifica l’uscita Q21 di un solo mese prima del rientro alla GUI. |
| `moduli/interfaccia/flusso_annuale_ui.py` | Coordina dalla GUI avvio, progresso, annullamento, risultato e apertura dell'anteprima annuale. |
| `moduli/processi/worker_annuale.py` | Ponte Qt che avvia l’Annuale Q21 in un processo separato. |
| `moduli/processi/processo_q21_contesto.py` | Esegue la pipeline Q21 fuori dal processo della GUI, con ingresso fotografato, durata, budget e messaggi serializzabili. È la frontiera condivisa da Mensile e Annuale. |
| `moduli/processi/ponte_processo.py` | Infrastruttura comune: serializza una fotografia degli input, avvia il processo figlio e inoltra i messaggi alla GUI. |
| `moduli/processi/supervisione_processi.py` | Chiude e raccoglie in modo finito i processi di calcolo quando hanno terminato o il canale di comunicazione non è più utilizzabile. |
| `moduli/processi/ponte_risultati_q21.py` | Converte i risultati fisici Q21 nel contratto di anteprima e persistenza. |

Mensile e Annuale usano entrambi processi separati. I ponti Qt inoltrano i messaggi e lavorano su fotografie degli input: non eseguono la ricerca sugli oggetti vivi della sessione grafica.

---

## 10. Salvataggio, Storico, report ed esportazioni

| Modulo | A cosa serve |
|---|---|
| `moduli/interfaccia/salvataggio_mensile_ui.py` | Registra nello Storico il risultato mensile accettato dall'utente. |
| `moduli/interfaccia/storico_ui.py` | Mostra e gestisce lo Storico: consultazione, ricostruzione dei layout, eliminazione ed esportazione. |
| `moduli/interfaccia/esportazione.py` | Costruisce report testuali e file Excel/TXT delle assegnazioni. |
| `moduli/interfaccia/statistiche.py` | Calcola e mostra statistiche storiche per classe e ne gestisce l'esportazione. |
| `moduli/interfaccia/statistiche_generali.py` | Produce le statistiche riassuntive in una forma strutturata, comprese le disposizioni del Layout unico e quelle storiche. |
| `moduli/persistenza/righe_statistiche.py` | Decide quali righe statistiche meritano di essere evidenziate nei riepiloghi. |
| `moduli/interfaccia/widget_statistiche.py` | Trasforma le righe statistiche strutturate in widget Qt. |
| `moduli/persistenza/persistenza_aula_personalizzata.py` | Salva e recupera le bozze del Layout per la classe, separatamente dalle disposizioni adottate. |
| `moduli/persistenza/storico_fisico_standard.py` | Serializza e ricostruisce le disposizioni fisiche dei formati storici. |
| `moduli/persistenza/report_personalizzata.py` | Prepara i contenuti dei report per il Layout e le relative coordinate. |
| `moduli/interfaccia/statistiche_presentazione.py` | Aggrega i dati dello Storico per la sola presentazione del Layout unico. |
| `moduli/dominio/riferimenti_riuso.py` | Prepara riferimenti leggibili alle precedenti vicinanze nella proposta annuale. |
| `moduli/persistenza/lettura_storico.py` | Ricostruisce le piantine nei quattro formati supportati, senza scrivere lo stato. |
| `moduli/persistenza/rotazioni_storico.py` | Deriva blacklist e contatori dallo Storico senza mutare la lista di origine. |
| `moduli/persistenza/operazioni_storico.py` | Prepara copie rinominate o con una voce eliminata e relative rotazioni; la facciata gestisce la scrittura transazionale. |

---

## 11. Interfaccia e ciclo di vita

| Modulo | A cosa serve |
|---|---|
| `moduli/interfaccia/ciclo_vita_ui.py` | Coordina inizializzazione, cambio tema, chiusura protetta e comportamento generale della finestra principale. |
| `moduli/interfaccia/pannelli_principali.py` | Costruisce i pannelli e i principali controlli della finestra. |
| `moduli/interfaccia/sessione_classe_ui.py` | Gestisce apertura, cambio e chiusura della classe e protegge i risultati non ancora salvati. |
| `moduli/interfaccia/editor_studenti.py` | Coordina l’Editor dei file-classe. Espone proprietà e comandi pubblici per file, modifiche pendenti e protezioni; usa componenti e dialoghi separati. |
| `moduli/interfaccia/istruzioni.py` | Contiene le finestre informative, la guida e i crediti mostrati dall'applicazione. |
| `moduli/interfaccia/tema.py` | Definisce la palette semantica dei temi chiaro e scuro. |
| `moduli/interfaccia/stili.py` | Costruisce e applica gli stylesheet Qt dell'interfaccia. |
| `moduli/interfaccia/utilita.py` | Raccolta di servizi condivisi per finestre, icone, popup, conteggi, report e adattamento allo schermo. |
| `moduli/lingua.py` | Piccoli helper per plurali e testi dinamici dell'interfaccia. |
| `moduli/interfaccia/controlli_editor.py` | Righe dei vincoli, placeholder e selettori protetti: segnalano modifiche senza conoscere la finestra principale. |
| `moduli/interfaccia/scheda_studente.py` | Widget di uno studente, con dati visuali e segnali di relazione, genere, posizione ed eliminazione. |
| `moduli/interfaccia/dialoghi_editor.py` | Dialoghi e selezione/validazione del file prima dell’adozione nella sessione dell’Editor. |
| `moduli/interfaccia/dialogo_dragdrop_prova.py` | Finestra di modifica dei posti condivisa da Mensile e Annuale, con trascinamento, CTRL, annullamento e conferma della bozza. |
| `moduli/interfaccia/dettagli_dragdrop.py` | Prepara il confronto leggibile delle preferenze, con i nomi degli studenti coinvolti nei peggioramenti. |
| `moduli/interfaccia/testi_dragdrop.py` | Traduce gli esiti e i vincoli delle mosse in messaggi comprensibili per il docente. |
| `moduli/interfaccia/stili_editor.py` | Costruisce il foglio di stile dei componenti dal tema corrente, senza gestire lo stato del file. |

---

## 12. Diagnostica della GUI

| Modulo | A cosa serve |
|---|---|
| `moduli/processi/profilo_gui.py` | Misura, solo quando richiesto, la durata di operazioni sincrone della GUI. |
| `moduli/processi/watchdog_gui.py` | Sorveglia l'event loop e registra eventuali blocchi o rallentamenti della GUI quando la diagnostica è attivata. |
| `moduli/processi/cattura_q21_diagnostica.py` | Acquisisce facoltativamente gli input Q21 per riproduzioni diagnostiche locali. |
| `moduli/processi/diagnostica_personalizzata.py` | Spiega i fallimenti di assegnazione del Layout senza dipendere dalla GUI. |
| `moduli/processi/diagnostica_fallimento_layout.py` | Analizza le restrizioni di L3, PRIMA e FISSO quando la generazione fallisce e prepara indicazioni riferite al Layout e agli studenti. |
| `moduli/calcolo/profilo_pipeline_q21.py` | Conta il lavoro delle fasi Q21 senza thread, polling o modifiche globali. |

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
pipeline_q21_contesto.py → annuale.py → motore_blocchi.py
    ↓
vincoli.py + valutazione_gruppi.py + metrica_pulizia.py + strato_storico.py
    ↓
matcher_blocchi.py + layout_risultato_personalizzata.py
    ↓
risultato corrente / anteprima
    ↓
salvataggio_mensile_ui.py / risultati_annuali.py
    ↓
configurazione.py → Storico
```

Non tutti i moduli vengono attraversati in ogni operazione: **Mensile e Annuale** condividono il percorso Q21, con durata diversa, e lo schema decide quanti banchi da due e da tre formare. I lettori delle vecchie modalità servono alla compatibilità dello Storico. I precedenti generatori e i laboratori restano nell’archivio di sviluppo separato.

---

## 14. Una chiave di lettura della struttura

La suddivisione in molti file serve a separare, all'interno di un unico flusso di lavoro, responsabilità diverse:

- i moduli dei **dati** non devono conoscere la GUI;
- i moduli del **motore** devono poter essere collaudati senza aprire finestre;
- i moduli della **GUI** preparano input e mostrano risultati, senza reinventare l'algoritmo;
- i moduli di **persistenza** controllano salvataggi, Storico e recupero;
- i moduli di **diagnostica** osservano il comportamento senza modificarlo.

Questa suddivisione rende più semplice capire, verificare e mantenere «PostiPerfetti» senza concentrare tutto il programma in un unico file.
