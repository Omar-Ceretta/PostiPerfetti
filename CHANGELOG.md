# Changelog di «PostiPerfetti»

Questo documento raccoglie le modifiche rilevanti delle versioni pubbliche di «PostiPerfetti».
Il progetto entra nella propria storia di Release a partire dalla versione 0.8.0.

## 0.8.0 — in preparazione

### Affidabilità

- introdotta una fonte unica della versione dell'applicazione;
- aggiunto il blocco contro l'avvio contemporaneo di più istanze;
- rafforzata la validazione dei parametri geometrici delle disposizioni;
- impedita l'interpretazione come formula Excel dei testi inseriti
  dall'utente;
- aggiunti controlli e diagnostica per gli errori immediati di avvio.

### Linux

- riprogettato l'installer con controllo dei prerequisiti;
- aggiunto il supporto esplicito a Python 3.10–3.14;
- preparazione e verifica del `.venv` già durante l'installazione;
- verifica delle dipendenze native Qt e del plugin XCB;
- migliorata la diagnostica degli errori Qt;
- corretta la gestione di disinstallazione e successiva reinstallazione
  con dati conservati;
- protetta l'integrazione desktop appartenente ad altre installazioni;
- separata la modalità di collaudo dalla distribuzione ufficiale;
- introdotto un pacchetto Linux di Release con verifica SHA-256 e controllo
  della versione contenuta.

### Windows

- collegati i metadati di versione di eseguibile e installer alla fonte
  unica della versione;
- mantenuto un percorso rapido per le build iterative;
- preparata la separazione fra build di sviluppo e build ufficiale di
  Release.

### Test e qualità

- congelate le versioni delle dipendenze runtime;
- formalizzate le dipendenze di sviluppo;
- aggiunti regression test per versione, esportazione Excel, geometria e
  launcher Linux;
- separati dalla suite pubblica i collaudi opzionali che richiedono il
  corpus esterno di classi;
- aggiunto un workflow GitHub Actions per la suite Python 3.10–3.14;
- introdotti controlli Ruff mirati e corretti i rilievi individuati.

### Documentazione e privacy

- chiarito che il normale utilizzo dell'applicazione elabora i dati
  localmente, mentre installazione e riparazione possono richiedere la rete;
- documentata la conservazione locale non cifrata dei dati;
- aggiunte indicazioni per la gestione prudente di file-classe, Storico,
  Report, esportazioni e log;
- aggiornata la documentazione Linux alla nuova procedura di installazione;
- rimossa l'indicazione di disattivare temporaneamente l'antivirus su
  Windows;
- aggiunta una policy per le segnalazioni di sicurezza.
