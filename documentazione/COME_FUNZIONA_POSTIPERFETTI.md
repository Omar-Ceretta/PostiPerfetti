# Come funziona «PostiPerfetti»

> **Versione di riferimento:** 0.8.0.
> 
> Questo documento spiega che cosa succede **dietro le quinte** quando «PostiPerfetti» calcola una disposizione.  
> L'obiettivo è mostrare, con un linguaggio accessibile, **quale percorso seguono i dati, quali regole vengono applicate e come il programma sceglie fra più soluzioni possibili**.

---

## 1. L'idea generale

««PostiPerfetti»» non prende semplicemente gli studenti in un elenco classe e li mescola.

Quando viene richiesta un'assegnazione, il programma tiene insieme informazioni di natura diversa:

- chi sono gli studenti;
- quali vicinanze sono preferibili o problematiche;
- chi deve stare in prima fila, in ultima fila o in posizione FISSO;
- se è richiesta una preferenza per gruppi di genere misto;
- quali vicinanze sono già state utilizzate in passato;
- quanti posti offre l'aula e come sono organizzati;
- se si stanno formando **coppie** oppure **terzetti**;
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

Le modalità **coppie** e **terzetti** possiedono memorie separate, perché una vicinanza nata in una modalità non deve modificare il comportamento dell'altra.

> Nel codice questa memoria delle vicinanze già usate viene indicata con il termine tecnico *blacklist*. Qui se ne parlerà con l'espressione **memoria dei riusi**.

### L'aula

Il programma costruisce anche la geometria fisica dell'aula: file, banchi disponibili, prima fila e spazio necessario per gli eventuali gruppi speciali.

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

Non esiste perciò un unico “lancio casuale” che decide tutto.

---

## 4. Prima regola: esistono vincoli assoluti e preferenze

«PostiPerfetti» distingue fra ciò che **non deve essere violato** e ciò che invece può essere progressivamente sacrificato quando una classe è particolarmente difficile da sistemare.

### Vincoli che restano assoluti

Durante tutti i tentativi restano NON negoziabili:

- incompatibilità di **livello 3** fra studenti adiacenti;
- posizione **PRIMA**;
- posizione **FISSO**, gestita con una logica dedicata;
- capienza e possibilità fisica di collocare i gruppi nell'aula.

Un'incompatibilità di livello 3 è quindi un vero veto: quella vicinanza non entra nella soluzione neppure nel tentativo più permissivo.

### Preferenze che possono essere allentate

Possono invece contribuire alla qualità della soluzione, senza essere per questo obbligatorie:

- incompatibilità di livello 1 e 2;
- affinità di livello 1, 2 e 3;
- preferenza ULTIMA;
- preferenza per gruppi di genere misto;
- desiderio di non riutilizzare vicinanze già viste.

È proprio su queste componenti che agiscono i quattro tentativi.

---

## 5. I quattro Tentativi: T1, T2, T3 e T4

I quattro tentativi non sono quattro algoritmi diversi.  
Sono **quattro configurazioni progressive dello stesso sistema di ricerca**.

| Tentativo | Che cosa cerca di conservare | Vicinanze già usate |
|---|---|---|
| **T1 — Tentativo 1** | Tiene conto di tutte le preferenze disponibili. | Escluse. |
| **T2 — Tentativo 2** | Rinuncia alle preferenze più deboli di livello 1. | Escluse. |
| **T3 — Tentativo 3** | Rinuncia anche alle preferenze intermedie; conserva ancora le più forti. | Escluse. |
| **T4 — Tentativo 4** | Mantiene soltanto i vincoli assoluti e fisici. | Ammesse solo se necessarie, ma fortemente penalizzate. |

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
Incompatibilità di livello 3, PRIMA, FISSO e geometria dell'aula continuano a valere.

---

## 6. Perché a volte T2 e T3 vengono saltati

Nei primi tre tentativi le vicinanze vietate in senso assoluto sono, di fatto, le stesse:

- incompatibilità di livello 3;
- vicinanze già utilizzate, che restano escluse.

T1, T2 e T3 cambiano soprattutto **quanto una possibilità è considerata desiderabile e in quale ordine viene provata**, non l'insieme fondamentale delle vicinanze ammissibili.

Perciò, se T1 ha esplorato **completamente** tutte le combinazioni consentite e ha dimostrato che nessuna disposizione completa esiste, ripetere la stessa esplorazione con T2 e T3 non potrebbe creare una soluzione nuova.

In quel caso il programma può passare direttamente a T4, dove cambia davvero la regola sui riusi.

Se invece T1 si è fermato perché ha raggiunto un limite protettivo della ricerca, non esiste una dimostrazione di impossibilità: T2 e T3 vengono ancora provati.

---

## 7. Come viene valutata una possibile vicinanza

Ogni possibile vicinanza riceve una valutazione costruita **per strati successivi**.

In termini semplici:

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

## 8. Per chi vuole andare più a fondo: il punteggio in forma matematica

Questa sezione ha lo scopo di mostrare in forma compatta come diverse informazioni vengono trasformate in un punteggio.

Per una possibile vicinanza fra due studenti \(a\) e \(b\), il punteggio locale può essere rappresentato schematicamente come:

\[
S_T(a,b)=I_T(a,b)+A_T(a,b)+G_T(a,b)+P_T(a,b)-500\,r(a,b)
\]

dove:

- \(T\) indica il Tentativo corrente;
- \(I_T\) rappresenta le penalità per incompatibilità ancora attive;
- \(A_T\) rappresenta i bonus per affinità ancora attive;
- \(G_T\) rappresenta l'eventuale bonus per il genere misto;
- \(P_T\) rappresenta le preferenze di posizione;
- \(r(a,b)\) è il numero di utilizzi precedenti di quella vicinanza.

Le incompatibilità e le affinità usano una scala crescente:

\[
m_1=1,\qquad m_2=4,\qquad m_3=20
\]

e, quando i rispettivi livelli sono attivi, i contributi di base seguono la forma:

\[
I_T(a,b)=-100\sum_{\ell \in L_I(T)}m_\ell\,n^I_\ell(a,b)
\]

\[
A_T(a,b)=+50\sum_{\ell \in L_A(T)}m_\ell\,n^A_\ell(a,b)
\]

Qui \(n^I_\ell\) e \(n^A_\ell\) indicano quante dichiarazioni di incompatibilità o affinità di livello \(\ell\) sono presenti fra i due studenti nelle due possibili direzioni.

Quando è richiesta la preferenza per il genere misto:

\[
G_T(a,b)=
\begin{cases}
100 & \text{se i due studenti appartengono a generi diversi}\\
0 & \text{altrimenti}
\end{cases}
\]

La componente relativa alla posizione può invece assumere, nei casi previsti, valori come:

\[
P_T(a,b)\in\{-50,\ 0,\ +10\}
\]

per distinguere, ad esempio, un conflitto fra richieste di fila, una situazione neutra o la compatibilità fra due richieste ULTIMA.

Questi valori **guidano l'ordine della ricerca**, ma non trasformano un divieto assoluto in una possibilità. Se esiste un'incompatibilità di livello 3, la vicinanza viene scartata indipendentemente dal punteggio.

Nei primi tre Tentativi, inoltre, una vicinanza già usata viene esclusa. Nel quarto diventa nuovamente disponibile ma resta penalizzata. Nella modalità a coppie T4 aggiunge anche un'ulteriore penalità proporzionale al numero dei riusi.

---

## 9. Dalle singole vicinanze alla disposizione completa: la ricerca con ritorno indietro

Avere molte coppie o terzetti “buoni” non basta. Gli stessi studenti non possono essere usati due volte e tutti devono trovare posto.

Il programma usa quindi una **ricerca con ritorno indietro**, chiamata in informatica *backtracking*.

In termini semplici:

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

Le vicinanze già utilizzate non vengono più escluse: diventano opzioni costose, da usare soltanto quando servono.

Inoltre T4 non si affida a un solo ordine di esplorazione. Per ogni soluzione candidata esegue **15 ripartenze** con ordini differenti.

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

La casualità serve quindi a esplorare strade diverse, non a rendere il programma imprevedibile: a parità di dati e seme numerico, il percorso può essere riprodotto.

---

## 12. Coppie: che cosa succede concretamente

Nella modalità a coppie il percorso, semplificato, è questo:

1. se esiste un FISSO, viene collocato nel posto previsto e tolto dagli studenti da raggruppare;
2. viene verificata la capienza;
3. se il numero degli studenti rimanenti è dispari, viene individuato un trio;
4. il motore cerca tutte le coppie necessarie;
5. la disposizione sociale viene tradotta in banchi reali;
6. vengono ricontrollate le condizioni fisiche, in particolare PRIMA;
7. vengono calcolate le informazioni statistiche del risultato.

Quindi la modalità “a coppie” può contenere **un trio di compensazione** quando il numero degli studenti da raggruppare è dispari.

---

## 13. Terzetti: gruppi ordinati, non semplici insiemi

Nella modalità a terzetti gli studenti di un gruppo sono disposti in fila.

Per esempio:

```text
[A] [B] [C]
```

le adiacenze reali sono:

```text
A—B
B—C
```

ma **A e C non sono considerati vicini**.

Per questo anche l'ordine interno di un terzetto o di un quartetto fa parte della soluzione.

A seconda del numero totale di studenti e delle opzioni scelte, il programma può costruire:

- terzetti;
- un'eventuale coppia finale;
- un quartetto;
- in alcuni casi, due quartetti.

Gli stessi quattro Tentativi vengono applicati alle adiacenze che compongono questi gruppi.

---

## 14. Come vengono confrontate le soluzioni complete

Il punteggio locale serve soprattutto a **guidare la ricerca**.

Quando invece esistono più disposizioni complete, «PostiPerfetti» usa una seconda valutazione, più importante, che stabilisce quale soluzione preferire.

Per una disposizione completa \(A\), la chiave di confronto è:

\[
K(A)=
\left(
R(A),\;
I_1(A)+10I_2(A)+1000I_3(A),\;
-F(A)
\right)
\]

dove:

- \(R(A)\) è il numero di vicinanze già utilizzate;
- \(I_1(A), I_2(A), I_3(A)\) sono le incompatibilità tollerate ai tre livelli;
- \(F(A)\) è il numero di affinità soddisfatte.

La chiave viene confrontata **da sinistra verso destra** e si cerca il valore più piccolo.

Questo produce una gerarchia molto precisa:

1. prima di tutto, **meno riusi**;
2. a parità di riusi, **meno incompatibilità**, con il livello 2 che pesa dieci volte il livello 1;
3. il peso 1000 del livello 3 funziona come sentinella: quel livello dovrebbe comunque essere impedito dai vincoli assoluti;
4. soltanto a parità dei criteri precedenti, vengono preferite **più affinità**.

Il segno meno davanti a \(F(A)\) serve proprio a trasformare “più affinità” in un valore matematicamente più piccolo.

In altre parole, molte affinità **non possono compensare** un numero maggiore di riusi o una situazione peggiore sul piano delle incompatibilità.

La stessa struttura viene usata per coppie e terzetti.

---

## 15. Confrontare più soluzioni invece di fermarsi alla prima

In alcune situazioni «PostiPerfetti» costruisce più soluzioni candidate e le confronta.

Nel codice questa tecnica è indicata come *best-of-N*: in termini semplici significa soltanto **“genera fino a N possibilità e scegli la migliore secondo la metrica”**.

Per il Mensile a coppie possono essere confrontate fino a **10 soluzioni candidate**.  
Per il Mensile a terzetti il valore predefinito è **3**.

Se una soluzione riesce entro T1, T2 o T3, la ricerca è deterministica e ulteriori candidati non aggiungerebbero nuove possibilità significative.

Quando invece si arriva a T4, le ripartenze a semi diversi possono esplorare strade differenti: in quel caso confrontare più candidati diventa utile.

---

## 16. Mensile: il percorso completo

### Mensile a coppie

```text
interfaccia grafica
 ↓
fotografia di studenti, aula e configurazione
 ↓
componente di calcolo dedicato
 ↓
ricerca delle coppie
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

### Mensile a terzetti

```text
interfaccia grafica
 ↓
fotografia degli input
 ↓
processo di calcolo separato
 ↓
motore dei terzetti
 ↓
T1–T4 + confronto fra più candidati
 ↓
risultato trasferito all'interfaccia
```

Il calcolo pesante viene quindi tenuto separato dalla finestra che l'utente sta utilizzando.

---

## 17. Annuale: un livello sopra il Mensile

L'Annuale non usa un algoritmo completamente diverso: costruisce una **sequenza di Mensili**.

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

La loro valutazione complessiva deriva dalla somma, componente per componente, delle chiavi dei singoli mesi:

\[
K_{\text{anno}}
=
\sum_{m=1}^{M} K(A_m)
\]

In forma esplicita:

\[
K_{\text{anno}}
=
\left(
\sum_m R(A_m),\;
\sum_m I(A_m),\;
-\sum_m F(A_m)
\right)
\]

Anche qui la priorità resta la stessa:

```text
riusi complessivi
       ↓
incompatibilità complessive
       ↓
affinità complessive
```

La ricerca può arrestarsi quando viene raggiunto un limite di tempo, un numero massimo di annate, una situazione di convergenza oppure quando l'utente annulla l'operazione.

---

## 19. Le guardie di qualità nella scelta Annuale

Dopo il primo confronto complessivo, «PostiPerfetti» applica un secondo livello di controllo.

Questa fase non crea nuove coppie o nuovi terzetti: confronta annate **già costruite**.

Il principio è quello delle **guardie di qualità**.

Una candidata non viene preferita soltanto perché migliora un singolo indicatore: deve prima dimostrare di **non peggiorare alcuni aspetti protetti** rispetto alla soluzione di riferimento.

Fra gli aspetti controllati rientrano:

- incompatibilità per livello;
- concentrazione dei riusi sugli stessi studenti;
- qualità delle affinità;
- momento in cui compare il primo riuso;
- distanza temporale fra riusi troppo ravvicinati.

Solo le annate che superano queste guardie vengono confrontate con criteri di dettaglio ulteriori.

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

Una volta scelta l'annata, «PostiPerfetti» può migliorare **l'ordine temporale** dei mesi già generati.

Quando alcuni riusi o alcune incompatibilità non assolute sono inevitabili, il programma prova — entro precise guardie di sicurezza — a **collocare più avanti nel calendario i mesi che contengono questi compromessi**, mantenendo il più possibile favorevole la parte iniziale dell'anno scolastico.

Un secondo passaggio cerca inoltre di aumentare la distanza fra riusi troppo ravvicinati.

Questa operazione è prudente:

- non crea nuovi gruppi;
- non modifica i posti all'interno di un mese;
- non può anticipare il primo riuso rispetto alla soluzione di riferimento;
- non può peggiorare la massima concentrazione dei riusi in un singolo mese;
- non può anticipare un mese con un profilo peggiore di incompatibilità.

Cambia quindi **quando** compare un mese già generato, non **come** quel mese è composto.

---

## 21. Perché il calcolo non deve bloccare la finestra

L'interfaccia grafica e il motore di calcolo sono separati intenzionalmente.

Le elaborazioni più pesanti non devono incidere nella reponsività di pulsanti, pannelli o altri elementi grafici della finestra mentre stanno calcolando.

Nella R0.8:

- il Mensile a coppie usa un componente di calcolo dedicato e una copia degli input;
- il Mensile a terzetti usa un processo Python separato;
- entrambi gli Annuali usano processi Python separati;
- un'infrastruttura specifica gestisce lo scambio dei risultati e la chiusura corretta dei processi.

Il motore riceve quindi una **fotografia** dei dati, lavora su quella e restituisce un risultato.

---

## 22. Dal risultato allo Storico

Quando il calcolo termina, il risultato torna all'interfaccia.

### Mensile

L'utente vede la disposizione e può salvarla. Solo in quel momento l'assegnazione entra nello Storico.

### Annuale

L'intera annata viene prima preparata e mostrata in anteprima.

Se viene accettata, tutti i mesi vengono preparati e salvati come un unico blocco.

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

## 23. Riassunto in dieci passaggi

Per descrivere il funzionamento in modo essenziale:

1. «PostiPerfetti» legge e valida la classe.
2. Recupera geometria, opzioni e Storico.
3. Crea una fotografia indipendente dei dati di partenza.
4. Valuta la qualità delle possibili vicinanze.
5. Esegue fino a quattro Tentativi progressivi senza mai violare i vincoli assoluti.
6. Usa una ricerca con ritorno indietro per costruire una disposizione completa.
7. Nel quarto Tentativo esplora più ripartenze controllate e riproducibili.
8. Confronta le soluzioni complete secondo una gerarchia: riusi, incompatibilità, affinità.
9. Nell'Annuale ripete il processo mese dopo mese e applica ulteriori guardie di qualità.
10. Solo dopo l'accettazione dell'utente aggiorna lo Storico reale.

Il principio di fondo è che «PostiPerfetti» non cerca semplicemente una disposizione **possibile**: prova prima a trovare quella che conserva meglio rotazione, compatibilità e preferenze, allentando le richieste non assolute soltanto quando è necessario.
