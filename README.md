[![PostiPerfetti](documentazione/immagini/github.png)](#)

# «PostiPerfetti»

**«PostiPerfetti» è un programma gratuito e open source che aiuta gli insegnanti ad assegnare e ruotare i posti in classe.**

Tiene conto della disposizione dei banchi, delle esigenze dei singoli studenti, di affinità e incompatibilità, delle preferenze di posizione e delle vicinanze già usate nelle assegnazioni precedenti. Gli studenti possono essere disposti **a coppie oppure a terzetti**, generando una singola disposizione o programmando più mesi insieme.

Le assegnazioni possono essere conservate nello **Storico**, analizzate tramite Report e Statistiche ed esportate in **Excel** o in formato testuale.

🌐 **Sito web e guida illustrata:** [www.postiperfetti.it](https://postiperfetti.it/)



> [!NOTE]
>
> A seconda delle tue preferenze, per usare l'interfaccia puoi selezionare un **🌙 Tema scuro** o un **☀️ Tema chiaro**, che apparirà come nei seguenti screenshot (clicca per allargare le immagini):
> 
> [![Tema scuro](documentazione/immagini/tema_scuro.png)](documentazione/immagini/tema_scuro.png)
> 
> [![Tema chiaro](documentazione/immagini/tema_chiaro.png)](documentazione/immagini/tema_chiaro.png)

------

## 📥 Download

📦 **[Scarica «PostiPerfetti» per Windows e GNU/Linux](https://github.com/Omar-Ceretta/PostiPerfetti/releases)**

📖 [Installazione, aggiornamento e disinstallazione](INSTALLAZIONE.md) — istruzioni passo per passo per Windows e GNU/Linux.

------
## ✨ Cosa può fare

«PostiPerfetti» permette di:

- disporre gli studenti **a coppie oppure a terzetti**, adattando la configurazione alla propria aula;
- indicare esigenze di **posizione** rispetto alla cattedra: PRIMA, ULTIMA e FISSO;
- definire **affinità e incompatibilità** fra studenti, con tre diversi livelli di importanza;
- favorire, se lo si desidera, **vicinanze miste Maschio + Femmina**;
- generare una singola disposizione con la modalità **Mensile**, oppure programmare fino a **10 mesi** con un'unica elaborazione in modalità **Annuale**;
- tenere conto delle vicinanze già sperimentate grazie allo **Storico** delle assegnazioni;
- controllare i risultati ottenuti tramite le schede **Aula, Report e Statistiche**;
- apportare, quando necessario, aggiustamenti manuali alla disposizione;
- esportare le disposizioni dei banchi in **Excel** e i Report in formato testuale.

------
## 🚀 Come funziona

1. **Crea il file della classe** con cognome, nome e genere degli studenti.
2. Nell'**Editor studenti**, aggiungi soltanto le indicazioni che ti servono: posizione, affinità e incompatibilità.
3. Clicca su **"SALVA e CARICA"** e configura l'aula scegliendo coppie o terzetti, il numero di posti per fila ed eventuale preferenza per vicinanze di genere misto.
4. Scegli **Mensile** per una singola disposizione oppure **Annuale** per generarne più di una.
5. Controlla il risultato e salva nello **Storico** soltanto le disposizioni che userai realmente in classe. Potrai poi esportarle e stamparle e, tramite le Statistiche, analizzare nel tempo le caratteristiche delle diverse rotazioni.

📖 Per tutti i passaggi, gli esempi e i video dimostrativi consulta la **[guida completa sul sito](https://postiperfetti.it/guida.html)**. La stessa applicazione contiene inoltre una guida offline accessibile dal pulsante **"Istruzioni"**.

------
## 🧭 Tre cose importanti da sapere

### 1. Vincoli assoluti e preferenze

Le **incompatibilità di livello 3** e le posizioni **PRIMA** e **FISSO** sono vincoli assoluti e non vengono mai violati dall'algoritmo del programma.

Gli altri criteri — incompatibilità di livello 1 e 2, affinità, posizione ULTIMA e preferenza per il genere misto — sono invece preferenze. Se non è possibile soddisfarle tutte contemporaneamente, «PostiPerfetti» le gestisce in modo progressivamente più flessibile per cercare una disposizione valida.

### 2. Lo Storico è la memoria delle rotazioni

Soltanto le assegnazioni **salvate nello Storico** vengono considerate nelle generazioni successive.

Per questo è importante conservare le disposizioni realmente utilizzate in classe, ed eliminare, invece, quelle eventualmente salvate ma poi non applicate.

### 3. Coppie e terzetti hanno memorie indipendenti

Le rotazioni **a coppie** e **a terzetti** vengono gestite separatamente. Una vicinanza già sperimentata nell'altra modalità può essere segnalata nel Report a titolo informativo, ma non influenza la generazione corrente.

------
## 🔐 Privacy e dati

**«PostiPerfetti» lavora in locale e non invia i dati delle classi a servizi remoti.**

I file delle classi, lo Storico e gli altri dati dell'utente restano sul computer e **non vengono cifrati dal programma**: devono quindi essere protetti come qualsiasi altro documento contenente dati personali.

Per maggiori informazioni consulta **[Dati locali, privacy e sicurezza](documentazione/DATI_PRIVACY_E_SICUREZZA.md)**.

------

## 📚 Altri documenti

| Documento | Cosa contiene |
|---|---|
| **[Installazione e avvio](documentazione/INSTALLAZIONE_AVVIO_E_DISINSTALLAZIONE.md)** | Installazione, aggiornamento e disinstallazione su Windows e Linux, passo per passo. |
| **[CHANGELOG](CHANGELOG.md)** | Le novità e le correzioni di ogni versione pubblicata. |
| **[SECURITY](SECURITY.md)** | Come segnalare un problema di sicurezza — e, soprattutto, **quali dati non allegare mai** a una segnalazione. |
| **[TERZE_PARTI](TERZE_PARTI.md)** | Le librerie, il carattere e le icone di altri autori usati dal programma, con le rispettive licenze. |
| **[LICENSE](LICENSE)** | Il testo completo della GNU GPL versione 3. |


😎 La documentazione tecnica più estesa (funzionamento dell'algoritmo, mappa dei moduli, trattamento dei dati) si trova nella cartella **[`documentazione/`](documentazione/)**.

------

![](risorse/icone/postiperfetti_icon.png)

**«PostiPerfetti»** — sviluppato dal prof. Omar Ceretta

Istituto Comprensivo di Tombolo e Galliera Veneta (PD)

**Tecnologie:** Python · PySide6 (Qt) · XlsxWriter

**Licenza:** [GNU GPLv3](LICENSE)
