# ⚙️ Come funziona «PostiPerfetti»

> **Versione di riferimento:** 2.0 (base di sviluppo con Layout unico).
> 
> Questo documento spiega che cosa succede **dietro le quinte** quando «PostiPerfetti» calcola una disposizione.  
> L'obiettivo è mostrare, con un linguaggio accessibile, **quale percorso seguono i dati, quali regole vengono applicate e come il programma sceglie fra più soluzioni possibili**.

---

## 1. L'idea generale

«PostiPerfetti» non prende semplicemente gli studenti da un elenco classe e li mescola.

Quando viene richiesta un'assegnazione, il programma tiene insieme informazioni di natura diversa:

- chi sono gli studenti;
- quali vicinanze sono preferibili o problematiche;
- chi deve stare in prima fila, in ultima fila o in posizione FISSO;
- se è richiesta una preferenza per gruppi di genere misto;
- quali vicinanze sono già state utilizzate in passato;
- quanti posti offre l'aula e come sono organizzati;
- come convivono i **banchi da due e da tre nel Layout unico**;
- se si sta generando un solo mese oppure un'intera annata.

Il percorso generale è questo:

```text
CLASSE
+ CONFIGURAZIONE
+ STORICO
+ GEOMETRIA DELL'AULA
+ OPZIONI DELL'UTENTE
        │
        ▼
preparazione dei dati
        │
        ▼
costruzione di possibili gruppi
        │
        ▼
Tentativo 1 → Tentativo 2 → Tentativo 3 → Tentativo 4
        │
        ▼
ricerca di una disposizione completa
        │
        ▼
valutazione della soluzione trovata
        │
        ▼
eventuale confronto con altre soluzioni
        │
        ▼
disposizione scelta
        │
        ▼
anteprima
        │
        ▼
salvataggio nello Storico
```

Nel codice i quattro tentativi sono abbreviati con **T1, T2, T3 e T4**: la **T sta per “Tentativo”**.

---

## 2. Da dove arrivano i dati

### La classe

Il programma legge il file della classe e ne controlla il contenuto.

Per ogni studente possono essere disponibili, fra le altre, queste informazioni:

- genere;
- posizione normale, PRIMA, ULTIMA o FISSO;
- affinità con altri studenti;
- incompatibilità con altri studenti.

Prima di iniziare la ricerca, i dati vengono inoltre portati in un ordine stabile, dal momento che l'ordine delle righe nel file non deve influenzare il risultato.

### Lo Storico

«PostiPerfetti» conserva le assegnazioni già salvate.

Da queste ricava una **memoria delle vicinanze precedenti**, utilizzata per favorire la rotazione e limitare il più possibile il ritorno degli stessi abbinamenti.

I banchi da due e da tre del **Layout unico** condividono la memoria delle adiacenze reali. I vecchi formati **coppie** e **terzetti** conservano invece memorie separate: le assegnazioni precedenti restano consultabili, senza trasferirne automaticamente le vicinanze alla generazione del Layout unico.

> Nel codice questa memoria delle vicinanze già usate viene indicata con il termine tecnico *blacklist*, interpretabile come una **memoria dei riusi**.

### L'aula

Il docente costruisce la geometria fisica dell'aula nella scheda **Layout**: banchi da due e da tre, spazi liberi, zone davanti e in fondo ed eventuale posto FISSO. Il programma ne ricava lo schema esatto di posti e gruppi richiesti.

Il motore deve quindi trovare non soltanto gruppi socialmente accettabili, ma anche una disposizione che possa essere realmente collocata nell'aula scelta.

---

## 3. Una soluzione candidata non è ancora il risultato finale

Durante la ricerca, «PostiPerfetti» può costruire più **soluzioni candidate**.

Una soluzione candidata è una disposizione completa che il programma è riuscito a ottenere rispettando le condizioni previste dal tentativo corrente.

Il programma può quindi:

1. costruire una soluzione;
2. verificarla;
3. costruirne altre, quando serve;
4. confrontarle;
5. scegliere quella preferibile.

Non esiste perciò un unico “lancio casuale” che decide tutto in modo randomico.

---

## 4. Prima regola: esistono vincoli assoluti e preferenze

«PostiPerfetti» distingue fra ciò che **non deve essere violato** e ciò che invece può essere progressivamente sacrificato quando una classe è particolarmente difficile da sistemare.

### Vincoli che restano assoluti

Durante tutti i tentativi restano NON negoziabili:

- incompatibilità di **livello 3** fra studenti adiacenti;
- posizione **PRIMA** nei banchi marcati come zona davanti;
- posizione **FISSO** nel posto-ancora scelto nel Layout, anche al centro di un terzetto;
- capienza e possibilità fisica di collocare i gruppi nell'aula.

Un'incompatibilità di livello 3 è quindi un vero veto: quella vicinanza non entra nella soluzione neppure nel tentativo più permissivo.

### Preferenze che possono essere allentate

Possono invece contribuire alla qualità della soluzione, senza essere per questo obbligatorie:

- incompatibilità di livello 1 e 2;
- affinità di livello 1, 2 e 3;
- preferenza ULTIMA;
- preferenza per gruppi di genere misto;
- desiderio di non riutilizzare vicinanze già viste.

È proprio su queste componenti che agiscono i quattro tentativi. Una preferenza attiva influisce sul punteggio e sull’ordine della ricerca: non diventa per questo un divieto. Un’incompatibilità di livello 1 o 2 può quindi comparire già in T1, mentre L3 resta sempre esclusa.

---

## 5. I quattro Tentativi: T1, T2, T3 e T4

I quattro tentativi non sono quattro algoritmi diversi.  
Sono **quattro configurazioni progressive dello stesso sistema di ricerca**.

| Tentativo | Che cosa cerca di conservare | Vicinanze già usate |
|---|---|---|
| **T1 — Tentativo 1** | Tiene conto di tutte le preferenze disponibili. | Escluse. |
| **T2 — Tentativo 2** | Rinuncia alle preferenze più deboli di livello 1. | Escluse. |
| **T3 — Tentativo 3** | Disattiva anche incompatibilità e affinità di livello 2 e il contributo ULTIMA nel punteggio di base; conserva affinità 3 e preferenza M/F. | Escluse. |
| **T4 — Tentativo 4** | Disattiva i contributi soft di base; mantiene vincoli assoluti e fisici e cerca con ripartenze differenti. | Ammesse e fortemente penalizzate secondo gli usi precedenti. |

In forma intuitiva:

```text
T1  prova a rispettare tutto il possibile
 │
 ▼
T2  allenta le preferenze più deboli
 │
 ▼
T3  allenta anche alcune preferenze intermedie
 │
 ▼
T4  cerca una soluzione possibile senza violare i vincoli assoluti
```

T4 **non significa “vale tutto”**.  
Incompatibilità di livello 3, posizione PRIMA, FISSO e geometria dell'aula sono rigorosamente mantenuti. Le preferenze disattivate nel punteggio di costruzione non vengono cancellate dai dati: la collocazione nei banchi e il confronto finale tornano a misurare ULTIMA, affinità, incompatibilità e vicinanze miste. Se un Tentativo trova una soluzione completa, quella cascata termina; il confronto fra ulteriori proposte è un livello distinto.

---

## 6. Perché a volte T2 e T3 vengono saltati

Nei primi tre tentativi le vicinanze vietate in senso assoluto sono, di fatto, le stesse:

- incompatibilità di livello 3;
- vicinanze già utilizzate, che restano escluse.

T1, T2 e T3 cambiano soprattutto **quanto una possibilità è considerata desiderabile e in quale ordine viene provata**, non l'insieme fondamentale delle vicinanze ammissibili.

Perciò, se T1 ha esplorato **completamente** tutte le combinazioni consentite e ha dimostrato che nessuna disposizione completa esiste, ripetere la stessa esplorazione con T2 e T3 non creerebbe alcuna soluzione nuova.

In quel caso il programma passa direttamente a T4, dove cambia davvero la regola sui riusi.

Se, invece, T1 si è fermato perché ha raggiunto il limite protettivo di nodi della ricerca, non esiste una dimostrazione di impossibilità: T2 e T3 vengono pertanto ancora provati. Il limite temporale dell’intera elaborazione è un controllo distinto.

---

## 7. Come viene valutata una possibile vicinanza

Ogni possibile vicinanza riceve una valutazione costruita **per strati successivi**.

In termini semplici, le considerazioni che fa l'algoritmo sono le seguenti:

```text
relazioni fra i due studenti
        │
        ▼
preferenze ancora attive nel Tentativo corrente
        │
        ▼
memoria delle vicinanze già usate
        │
        ▼
regola sui riusi propria di T1–T4
        │
        ▼
punteggio usato per guidare la ricerca
```

Il programma considera quindi, in momenti successivi:

1. incompatibilità e affinità dichiarate;
2. genere misto, quando richiesto;
3. preferenze di posizione;
4. tentativo in corso;
5. numero di volte in cui quella vicinanza è già comparsa.

L'incompatibilità di livello 3 viene esclusa **prima** di qualunque confronto numerico.

---

## 8. Per approfondire: il punteggio in forma matematica

Questa sezione ha lo scopo di mostrare in forma compatta come diverse informazioni vengono trasformate in un punteggio.

Per una possibile vicinanza fra due studenti $`a`$ e $`b`$, il punteggio locale può essere rappresentato schematicamente come:

```math
S_T(a,b)=I_T(a,b)+A_T(a,b)+G_T(a,b)+P_T(a,b)-500\,r(a,b)
```

dove:

- $`T`$ indica il Tentativo corrente;
- $`I_T`$ rappresenta le penalità per incompatibilità ancora attive;
- $`A_T`$ rappresenta i bonus per affinità ancora attive;
- $`G_T`$ rappresenta l'eventuale bonus per il genere misto;
- $`P_T`$ rappresenta le preferenze di posizione;
- $`r(a,b)`$ è il numero di utilizzi precedenti di quella vicinanza.

Le incompatibilità e le affinità usano una *scala crescente*:

```math
m_1=1,\qquad m_2=4,\qquad m_3=20
```

e, quando i rispettivi livelli sono attivi, i contributi di base seguono la forma:

```math
I_T(a,b)=-100\sum_{\ell \in L_I(T)}m_\ell\,n^I_\ell(a,b)
```

```math
A_T(a,b)=+50\sum_{\ell \in L_A(T)}m_\ell\,n^A_\ell(a,b)
```

Qui $`n^I_\ell`$ e $`n^A_\ell`$ indicano quante dichiarazioni di incompatibilità o affinità di livello $`\ell`$ sono presenti fra i due studenti nelle due possibili direzioni.

Quando è richiesta la preferenza per il genere misto:

```math
G_T(a,b)=
\begin{cases}
100 & \text{se i due studenti appartengono a generi diversi}\\
0 & \text{altrimenti}
\end{cases}
```

La componente relativa alla posizione può invece assumere, nei casi previsti, valori come:

```math
P_T(a,b)\in\{-50,\ 0,\ +10\}
```

per distinguere, ad esempio, un conflitto fra richieste di fila, una situazione neutra o la compatibilità fra due richieste ULTIMA.

Questi valori **guidano l'ordine della ricerca**, ma non trasformano un divieto assoluto in una possibilità. Se esiste un'incompatibilità di livello 3, la vicinanza viene scartata indipendentemente dal punteggio.

Nei primi tre Tentativi, inoltre, una vicinanza già usata viene esclusa. Nel quarto diventa nuovamente disponibile ma resta penalizzata. Il motore del Layout unico applica la penalità storica di $`500\,r(a,b)`$ mostrata nella formula; il precedente doppio strato della modalità a coppie non è il percorso operativo della 2.0.

---

## 9. Dalle singole vicinanze alla disposizione completa: la ricerca con "ritorno indietro"

Avere molte coppie o terzetti “buoni” non basta. Gli stessi studenti non possono essere usati due volte e tutti devono trovare posto.

Il programma usa quindi una **ricerca con ritorno indietro**, chiamata in informatica *backtracking*.

In termini semplici, l'algoritmo:

1. sceglie un gruppo promettente;
2. considera occupati i suoi membri;
3. prova a completare la disposizione con gli studenti rimasti;
4. se a un certo punto quella strada non può più essere completata, torna indietro;
5. prova un'alternativa.

```text
scelta A
 ├─ completa tutto? → sì → soluzione
 │
 └─ si blocca
      ↓
   torna indietro
      ↓
   prova scelta B
```

Il programma applica anche controlli anticipati che permettono di riconoscere alcuni vicoli ciechi prima di esplorarli inutilmente.

Esistono inoltre limiti protettivi al numero di possibilità esaminate. Raggiungere quel limite significa **“ricerca interrotta”**, non **“soluzione matematicamente inesistente”**.

---

## 10. Un'ottimizzazione invisibile: ricordare i vicoli ciechi

La ricerca può incontrare più volte la stessa situazione intermedia.

Quando una certa configurazione degli studenti rimasti è già stata esplorata completamente senza successo, il programma può **ricordarla** ed evitare di ripetere inutilmente lo stesso lavoro.

Questa ottimizzazione:

- non cambia i punteggi;
- non cambia i vincoli;
- non cambia le preferenze;
- non rende lecita una soluzione prima vietata;
- serve soltanto a evitare esplorazioni duplicate.

È quindi una tecnica di efficienza interna, utile a non sprecare tempo di computazione, non un nuovo “livello” di assegnazione.

---

## 11. Che cosa fa T4 di diverso

T4 introduce il vero cambio di regime.

Le vicinanze già utilizzate non vengono più escluse: diventano opzioni "costose", da usare solo quando servono.

Inoltre T4 non si affida a un unico ordine di esplorazione. Per ogni soluzione candidata esegue **15 ripartenze** con ordini differenti.

Questi ordini sono ottenuti attraverso un **seme numerico di casualità** (*seed*), in modo che la variazione sia controllata e riproducibile.

```text
stessa situazione iniziale
   ├─ ripartenza 1
   ├─ ripartenza 2
   ├─ ...
   └─ ripartenza 15
          │
          ▼
scegli la migliore soluzione trovata
```

La casualità serve quindi a esplorare strade diverse, non a rendere il programma imprevedibile: a parità di dati e seme numerico, il percorso di una stessa ricerca candidata può essere riprodotto. Il numero di proposte complete esplorate entro un budget di tempo può invece dipendere dalla macchina e dal carico; per confronti identici occorre fissare anche il campione di candidate.

---

## 12. Abbinamenti in banchi da due: che cosa succede concretamente

Nel Layout unico, quando prevalgono i banchi da due, il percorso semplificato è questo:

1. se esiste un FISSO, il suo posto-ancora resta parte dello schema e lo studente partecipa alla formazione dei gruppi;
2. viene verificata la corrispondenza fra numero degli studenti e posti disegnati;
3. lo schema stabilisce quante coppie e quanti terzetti devono essere formati;
4. il motore cerca tutti i gruppi necessari con la cascata T1–T4;
5. la disposizione sociale viene tradotta nei banchi reali del Layout;
6. vengono ricontrollate le condizioni fisiche, in particolare PRIMA e FISSO;
7. vengono calcolate le informazioni statistiche del risultato.

Un Layout prevalentemente a coppie può quindi contenere **un terzetto**, per esempio sette banchi da due e uno da tre per 17 studenti. Non è più un trio inserito automaticamente dal vecchio assegnatore: è un banco previsto nella geometria del docente.

---

## 13. Abbinamenti in banchi da tre: gruppi ordinati, non semplici insiemi

Nei banchi da tre del Layout unico gli studenti di un gruppo sono disposti in fila.

Per esempio:

```text
[A] [B] [C]
```

le adiacenze reali sono:

```text
A — B
B — C
```

poiché **A e C non sono considerati vicini**.

Per questo anche l'ordine interno di un terzetto fa parte della soluzione. Un FISSO centrale ha due vicini diretti; un FISSO a un estremo ne ha uno.

A seconda del Layout disegnato dal docente, il programma costruisce:

- tanti terzetti quanti sono i banchi da tre;
- tante coppie quanti sono i banchi da due;
- combinazioni di entrambi nello stesso schema.

Il nuovo editor non prevede quartetti né blocchi finali automatici. Le disposizioni storiche che li contengono restano leggibili ed esportabili.

Gli stessi quattro Tentativi vengono applicati alle adiacenze che compongono questi gruppi.

---

## 14. Come vengono confrontate le soluzioni complete

Il punteggio locale serve soprattutto a **guidare la ricerca**.

Quando invece esistono più disposizioni complete, «PostiPerfetti» usa una seconda valutazione, più importante, che stabilisce quale soluzione preferire.

Per una disposizione completa $`A`$, la chiave del **confronto preliminare C1** è:

```math
K(A)=
\left(
R(A),\;
I_1(A)+10I_2(A)+1000I_3(A),\;
-F(A)
\right)
```

dove:

- $`R(A)`$ è il numero di vicinanze già utilizzate;
- $`I_1(A), I_2(A), I_3(A)`$ sono le incompatibilità tollerate ai tre livelli;
- $`F(A)`$ è il numero di affinità soddisfatte.

La chiave viene confrontata **da sinistra verso destra** e si cerca il valore più piccolo.

In questo confronto preliminare si ottiene una gerarchia molto precisa:

1. prima di tutto, **meno riusi**;
2. a parità di riusi, **meno incompatibilità**, con il livello 2 che pesa dieci volte il livello 1;
3. il peso 1000 del livello 3 funziona come sentinella: quel livello dovrebbe comunque essere impedito dai vincoli assoluti;
4. soltanto a parità dei criteri precedenti, vengono preferite **più affinità**.

Il segno meno davanti a $`F(A)`$ serve proprio a trasformare “più affinità” in un valore matematicamente più piccolo.

In altre parole, **nel confronto preliminare C1** molte affinità non possono compensare un numero maggiore di riusi o una situazione peggiore sul piano delle incompatibilità.

La stessa struttura viene usata per i banchi da due e da tre. **La scelta finale della 2.0 non si esaurisce però in questa chiave**: il confronto protetto S1/R12 e le successive rifiniture sono descritti nelle sezioni 18 e 19.

---

## 15. Confrontare più soluzioni invece di fermarsi alla prima

In alcune situazioni «PostiPerfetti» costruisce più soluzioni candidate e le confronta.

Nel codice questa tecnica è indicata come *best-of-N*: in termini semplici significa soltanto **“genera fino a N possibilità e scegli la migliore secondo la metrica”**.

Nel generatore di un mese del Layout unico il valore predefinito è **3 candidate interne**, indipendentemente dalla prevalenza di banchi da due o da tre. Questo non significa che l’intera elaborazione Mensile si limiti a tre proposte: Q21 può richiamare più volte il generatore e confrontare numerose disposizioni complete.

Se una soluzione riesce entro T1, T2 o T3, il generatore interno termina senza ripetere la cascata per le altre candidate. Nelle successive proposte di Q21, la diversificazione Q2 può variare l’ordine fra gruppi a pari punteggio, senza cambiare punteggi o vincoli.

Quando invece si arriva a T4, le ripartenze a semi diversi possono esplorare strade differenti: in quel caso confrontare più candidati diventa utile.

---

## 16. Mensile: il percorso completo

### Preparazione e processo di calcolo

```text
interfaccia grafica
 ↓
fotografia di studenti, aula e configurazione
 ↓
processo di calcolo separato Q21
 ↓
ricerca dei gruppi da due e da tre
 ↓
T1–T4
 ↓
confronto delle soluzioni
 ↓
migliore candidata
 ↓
interfaccia grafica
 ↓
anteprima nella piantina
 ↓
eventuale salvataggio nello Storico
```

Il calcolo lavora su copie indipendenti degli input, così non modifica direttamente la sessione grafica mentre è in corso.

### Rientro all’interfaccia e adozione

```text
risultato completo e verificato
 ↓
controllo della fotografia di classe e Layout
 ↓
Disposizione, Report e statistiche della proposta
 ↓
adozione esplicita del docente
 ↓
salvataggio nello Storico
```

Il calcolo delle combinazioni viene quindi tenuto separato dalla finestra che l'utente sta utilizzando. I risultati tardivi o alterati vengono rifiutati: non devono essere applicati a una classe o a un Layout diversi da quelli fotografati all’avvio.

---

## 17. Annuale: un livello sopra il Mensile

L'Annuale non usa un algoritmo completamente diverso: costruisce una **sequenza di Mensili**. Nella 2.0 entrambi usano la stessa pipeline Q21; il Mensile è il caso di un solo mese e l’Annuale ne richiede da uno a dieci.

Per ogni annata candidata:

1. viene creata una copia temporanea della configurazione;
2. viene generato il primo mese;
3. le sue vicinanze entrano nella memoria temporanea;
4. il secondo mese viene quindi calcolato sapendo che cosa è già accaduto nel primo;
5. il processo continua fino al numero di mesi richiesto (10 al massimo).

```text
configurazione iniziale
       │
       ▼
     mese 1
       │ aggiorna memoria temporanea
       ▼
     mese 2
       │
       ▼
     mese 3
       │
      ...
       ▼
   annata completa
```

La configurazione reale dell'utente non viene modificata durante questa ricerca.

---

## 18. Come vengono confrontate le annate

Il programma può generare molte annate candidate.

La loro valutazione preliminare C1 deriva dalla somma, componente per componente, delle chiavi dei singoli mesi:

```math
K_{\text{anno}}
=
\sum_{m=1}^{M} K(A_m)
```

In forma esplicita:

```math
K_{\text{anno}}
=
\left(
\sum_m R(A_m),\;
\sum_m I(A_m),\;
-\sum_m F(A_m)
\right)
```

Anche qui, nel confronto preliminare, la priorità resta la stessa:

```text
riusi complessivi
       ↓
incompatibilità complessive
       ↓
affinità complessive
```

La ricerca può arrestarsi quando viene raggiunto un limite di tempo, un numero massimo di annate, una situazione di convergenza oppure quando l'utente annulla l'operazione.

Il budget predefinito è **600 secondi complessivi**, con **60 secondi riservati alle fasi finali**, sia per Mensile sia per Annuale: non è un tempo da consumare obbligatoriamente. La ricerca ordinaria ha inoltre un tetto di 5.000 proposte e può arrestarsi dopo 300 proposte senza miglioramento del riferimento preliminare. Un budget esaurito prima di ottenere un risultato completo e verificato può produrre un errore senza proposta: non esiste un recupero finale garantito di una candidata intermedia.

Dalla ricerca Q21 conserva una scelta di riferimento e poche alternative fisiche già costruite. Le rifiniture **Q5** cercano di ridurre i riusi; **Q12** cerca di migliorare ULTIMA; **Q15** prova a recuperare alternative interessanti entro le protezioni previste. La selezione **Q19** sceglie fra queste proposte, mentre **Q20** cerca ulteriori affinità senza perdere le qualità protette. Queste operazioni possono modificare i gruppi, a differenza del solo riordino temporale della sezione 20.

---

## 19. Le guardie di qualità nella scelta Annuale

Dopo il primo confronto complessivo, «PostiPerfetti» applica un secondo livello di controllo.

Questa fase non crea nuove coppie o nuovi terzetti: confronta annate **già costruite**.

Il principio è quello delle **guardie di qualità**.

Una candidata non viene preferita soltanto perché migliora un singolo indicatore: deve prima dimostrare di **non peggiorare alcuni aspetti protetti** rispetto alla soluzione di riferimento.

Fra gli aspetti controllati rientrano:

- incompatibilità per livello;
- concentrazione dei riusi sugli stessi studenti;
- qualità delle affinità, comprese quelle di livello 3;
- momento in cui compare il primo riuso;
- distanza temporale fra riusi troppo ravvicinati;
- profilo mensile delle incompatibilità e massimo dei riusi in un mese;
- soddisfazioni ULTIMA e, se richiesta, preferenza per vicinanze miste.

Solo le annate che superano queste guardie vengono confrontate con criteri di dettaglio ulteriori. Nella 2.0 gli stessi controlli contestuali si applicano anche al Mensile e possono partire da uno Storico già popolato.

Il primo componente del confronto R12 è:

```math
R12(A)=12R(A)+10I_2(A)+2I_1(A)-A_p(A)
```

dove $`A_p= A_1+2A_2+3A_3`$ è la somma ponderata delle affinità soddisfatte. Si cerca un valore più basso; a parità si confrontano ulteriori aspetti, fra cui L2, massimo individuale dei riusi e qualità temporale. Questa formula non autorizza a ignorare le guardie: una candidata viene confrontata solo se è ammissibile rispetto al riferimento.

La politica Q19 contiene una deroga precisa: può ammettere **una sola soddisfazione ULTIMA in meno**, soltanto se questo è l’unico peggioramento delle guardie, se il punteggio R12 migliora strettamente e se diminuisce almeno una fra incompatibilità L1 e L2. Le altre protezioni restano valide e il riferimento non cambia durante la selezione: la deroga non può essere concatenata per perdere più soddisfazioni ULTIMA.

In termini semplici:

```text
annate generate
      │
      ▼
soluzione di riferimento
      │
      ├─ candidata A → peggiora una guardia → scartata
      ├─ candidata B → supera le guardie
      └─ candidata C → supera le guardie
                         │
                         ▼
                confronto più dettagliato
                         │
                         ▼
                    annata scelta
```

---

## 20. Il riordino dei mesi non cambia i posti

Durante la valutazione e, con un ultimo controllo, una volta scelta l'annata, «PostiPerfetti» può migliorare **l'ordine temporale** dei mesi già generati.

Quando alcuni riusi o alcune incompatibilità non assolute sono inevitabili, il programma prova (entro precise guardie di sicurezza) a **collocare più avanti nel calendario i mesi che contengono questi compromessi**, mantenendo il più possibile favorevole la parte iniziale dell'anno scolastico.

Un secondo passaggio cerca inoltre di aumentare la distanza fra riusi troppo ravvicinati.

Questa operazione è prudente, in quanto:

- non crea nuovi gruppi;
- non modifica i posti all'interno di un mese;
- non può anticipare il primo riuso rispetto alla soluzione di riferimento;
- non può peggiorare la massima concentrazione dei riusi in un singolo mese;
- non può anticipare un mese con un profilo peggiore di incompatibilità.

Cambia quindi **quando** compare un mese già generato, non **come** quel mese è composto. Il riordino finale di presentazione I2g ammette inoltre soltanto scambi che conservano tutte le metriche temporali e complessive già ottenute, migliorando la successione della gravità mensile.

---

## 21. Perché il calcolo non deve bloccare la finestra

L'interfaccia grafica e il motore di calcolo sono stati intenzionalmente tenuti separati.

Le elaborazioni più pesanti vengono eseguite fuori dal processo della GUI, per preservare la responsività di pulsanti, pannelli o altri elementi grafici della finestra:

- il Mensile del Layout unico usa un processo Python separato;
- l’Annuale usa lo stesso motore Q21 in un processo separato;
- i ponti Qt inoltrano i messaggi alla finestra senza eseguire lì la ricerca;
- un'infrastruttura specifica gestisce lo scambio dei risultati e la chiusura corretta dei processi, anche dopo una richiesta di annullamento cui il figlio non risponde.

Il motore riceve quindi una **fotografia** dei dati, lavora su quella e restituisce alla fine un risultato.

---

## 22. Dal risultato allo Storico

Quando il calcolo termina, il risultato torna all'interfaccia.

### Mensile

L'utente vede la disposizione e può salvarla. Solo in quel momento l'assegnazione entra nello Storico.

### Annuale

L'intera annata viene prima preparata e poi mostrata "in anteprima".

Se viene accettata, tutti i mesi vengono preparati e salvati come un unico blocco. Se una registrazione o la scrittura finale fallisce, il batch viene annullato; il salvataggio mensile protegge allo stesso modo la memoria dalle registrazioni parziali.

Lo Storico diventa a sua volta una delle fonti utilizzate dalle assegnazioni successive.

Il percorso quindi si chiude:

```text
calcolo
  ↓
risultato
  ↓
accettazione
  ↓
Storico
  ↓
memoria delle vicinanze
  ↓
calcolo successivo
```

---

## 23. Riassunto del funzionamento in dieci passaggi

Questo "decalogo" descrive, in modo essenziale ma completo, come funziona «PostiPerfetti»:

1. Il programma legge e valida la classe.
2. Recupera geometria, opzioni e Storico.
3. Crea una fotografia indipendente dei dati di partenza.
4. Valuta la qualità delle possibili vicinanze.
5. Esegue fino a quattro Tentativi progressivi senza mai violare i vincoli assoluti.
6. Usa una ricerca con ritorno indietro per costruire una disposizione completa.
7. Nel quarto Tentativo esplora più ripartenze controllate e riproducibili.
8. Confronta le soluzioni complete con un riferimento preliminare e con selezione e rifiniture protette che misurano riusi, incompatibilità, affinità e preferenze.
9. Nell'Annuale ripete il processo mese dopo mese e controlla anche la distribuzione temporale; le guardie contestuali valgono anche per il Mensile.
10. Solo dopo l'accettazione dell'utente aggiorna lo Storico reale.

Il principio di fondo è che «PostiPerfetti» non cerca semplicemente una disposizione **possibile**: prova a trovare quelle che conservano meglio rotazione, compatibilità e preferenze, allentando le richieste non assolute solo quando è necessario.
