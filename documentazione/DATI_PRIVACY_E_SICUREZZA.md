# 🔐 «PostiPerfetti» — Dati locali, privacy e sicurezza

«PostiPerfetti» è progettato per lavorare localmente con i dati necessari all'assegnazione dei posti in classe.

Questa pagina descrive quali informazioni vengono conservate dal programma e fornisce alcune indicazioni pratiche per gestirle in modo consapevole.

Non costituisce un'informativa privacy dell'Istituto scolastico e non sostituisce le disposizioni del Titolare del trattamento, del Responsabile della protezione dei dati (RPD/DPO) o le procedure interne della Scuola.

---

## 1. Quali dati utilizza «PostiPerfetti»

I file-classe possono contenere dati identificativi degli studenti, come cognome e nome, oltre alle informazioni necessarie al funzionamento del programma: genere, posizione nell'aula, affinità, incompatibilità e altri vincoli configurati dal docente.

Alcune di queste informazioni possono riflettere dinamiche della classe, esigenze educative o scelte organizzative del docente e devono quindi essere gestite con particolare attenzione.

È opportuno inserire nel programma soltanto le informazioni effettivamente necessarie all'assegnazione dei posti.

---

## 2. Dove vengono conservati i dati

«PostiPerfetti» mantiene i propri dati nella cartella locale dell'installazione.

In particolare:

- `classi/` contiene i file `.txt` delle classi creati o modificati dal docente;
- `stato/` contiene la configurazione persistente, lo Storico delle
  assegnazioni e il relativo backup;
- `log/` può contenere diagnostica tecnica relativa a errori o problemi dell'applicazione.

Le esportazioni Excel (`.xlsx`) e i Report (`.txt`) vengono salvati nel percorso scelto dal docente e possono a loro volta contenere nomi degli studenti, disposizioni e informazioni sui relativi abbinamenti.

Tali file sono - come si dice - "in chiaro" poiché non vengono cifrati da «PostiPerfetti».

---

## 3. Utilizzo della rete

Durante il normale utilizzo delle funzioni di assegnazione, «PostiPerfetti» elabora localmente i dati della classe e non li invia a servizi remoti.

La rete è invece impiegata per operazioni tecniche, che non richiedono l'invio dei dati delle classi. Ad esempio:

- installazione o aggiornamento del programma;
- download delle dipendenze Python;
- riparazione dell'ambiente software quando una dipendenza deve essere reinstallata.

Queste operazioni si collegano ai servizi del repository impiegati per distribuire il programma.

---

## 4. Proteggere i file locali

Il fatto che un dato rimanga in locale, sul computer, non lo rende automaticamente inaccessibile ad altre persone.

È quindi opportuno usare «PostiPerfetti» su un dispositivo e con un account conformi alle regole del proprio Istituto, proteggere l'accesso al Sistema Operativo e prestare attenzione a eventuali copie, dispositivi rimovibili, backup e cartelle sincronizzate automaticamente con servizi cloud.

File-classe, esportazioni, Report e copie dello Storico non dovrebbero essere condivisi o trasferiti attraverso strumenti non autorizzati dall'Istituto.

Le eventuali misure di protezione del dispositivo, comprese cifratura del disco, gestione degli account e backup, appartengono al Sistema Operativo o all'infrastruttura della Scuola e non sono implementate da «PostiPerfetti».

---

## 5. Conservazione e cancellazione

I dati dovrebbero essere conservati soltanto per il tempo necessario alle finalità per cui vengono utilizzati e secondo le regole stabilite dall'Istituto.

Il docente può eliminare singoli file-classe, esportazioni e Report quando non sono più necessari.

La normale disinstallazione di «PostiPerfetti» conserva intenzionalmente i dati dell'utente per consentire una successiva reinstallazione.

Per eliminare anche classi, impostazioni, Storico e log è disponibile la disinstallazione completa (`--purge` su Linux); su Windows il programma di disinstallazione chiede esplicitamente se conservare o eliminare anche i dati dell'utente. 

📋 Per i dettagli **consulta la guida** **[Installazione, avvio e disinstallazione](INSTALLAZIONE_AVVIO_E_DISINSTALLAZIONE.md)**.


---

## 6. ⚖️ Responsabilità dell'utilizzo

«PostiPerfetti» è uno strumento software: non determina da solo se un trattamento di dati sia appropriato per uno specifico Istituto o contesto.

L'utente deve attenersi alle procedure della propria Scuola e alle indicazioni del Titolare del trattamento e del Responsabile della protezione dei dati (RPD/DPO).

In caso di dubbio sull'utilizzo di particolari informazioni degli studenti, sulla loro conservazione o sugli strumenti sui quali è consentito salvarle, è opportuno rivolgersi ai referenti privacy del proprio Istituto.
