# -*- coding: utf-8 -*-
"""
istruzioni.py — finestre informative di «PostiPerfetti».

Mostra la guida d'uso, i crediti e lo schema per configurare l'aula. I
contenuti rich text seguono il tema attivo e incorporano le icone Lucide; la
guida già aperta viene rigenerata conservando il punto di lettura.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import os
import re

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QTextBrowser, QLabel,
    QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt, QUrl, QSize, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPalette, QPixmap, QTextDocument

from moduli.interfaccia.tema import C
from moduli.percorsi import get_resource_path
from moduli.versione import VERSIONE
from moduli.interfaccia.utilita import (
    adatta_finestra_allo_schermo,
    applica_icona,
    applica_icona_finestra,
    carica_icona,
)


_TOKEN_ICONA = re.compile(r"\[\[ICON:([a-z0-9-]+):(\d+)\]\]")

ISTRUZIONI_HTML_TEMPLATE = r"""
        <h2 class="titolo">[[ICON:book-open:28]] «PostiPerfetti»</h2>
        <hr>

        <p class="riquadro riquadro-info">
        [[ICON:circle-check:17]] <b>«PostiPerfetti» aiuta l'insegnante ad assegnare i posti in classe tenendo conto di come sono disposti i banchi, delle esigenze dei singoli studenti e delle vicinanze già usate nelle assegnazioni precedenti.</b><br><br>
        [[ICON:circle-check:17]] Il lavoro parte da un file <code>.txt</code> con almeno <b>cognome e nome</b> degli allievi; il genere può essere già indicato nel file oppure completato nell'Editor. Dopo il caricamento, dalla scheda <b>"Editor studenti"</b> puoi anche <b>aggiungere o eliminare studenti</b> e gestire <b>genere, posizione, FISSO, incompatibilità e affinità</b>.<br><br>
        [[ICON:circle-check:17]] Nella scheda <b>Layout</b> costruisci la tua aula reale usando banchi da <b>2</b> e da <b>3</b> posti, scegliendo zone e spazi liberi. <b>Mensile e Annuale usano lo stesso Layout.</b> Il motore assegna i posti rispettando questa geometria.<br><br>
        [[ICON:history:17]] Lo <b>Storico</b> è la memoria delle rotazioni: soltanto le assegnazioni salvate vengono considerate nelle generazioni successive. <b>Mensile e Annuale consultano la stessa memoria delle vicinanze salvate.</b><br><br>
        [[ICON:circle-check:17]] <b>Durante l'uso, il programma lavora in locale e non invia in rete i dati delle classi.</b>
        </p>

        <hr>
        <h3 class="sezione">[1] - PREPARA E SELEZIONA LA CLASSE</h3>

        <p><b>1 ~ Crea un file .txt di base</b></p>
        <p>Nella scheda "<b>Editor studenti</b>", clicca su "<b>Apri cartella</b>". Il tuo file manager ti mostrerà la cartella che contiene le classi, dove troverai due file di esempio:<br>
        • <code>Classe-BASE_esempio.txt</code>, che mostra il semplice formato da usare per creare una nuova classe;<br>
        • <code>Classe-COMPLETO_esempio.txt</code>, che mostra come apparirà il file dopo aver aggiunto posizione e vincoli tramite l'Editor.<br><br>
        Per creare la tua classe, usa come modello il file <b>BASE</b>, oppure crea un nuovo file di testo con il nome che preferisci (ad es. "<code>Classe 1A.txt</code>" o "<code>Classe 1A - 2026-27.txt</code>").</p>
        <p class="riquadro riquadro-info">[[ICON:info:17]] Nota per Windows: l'estensione ".txt" potrebbe essere nascosta, quindi è possibile che il file ti appaia semplicemente come "Classe 1A". Va bene così.<br>
        Usa un semplice editor di testo (come "Blocco note"), non un programma di videoscrittura come Microsoft Word o LibreOffice Writer.</p>
        <p>Inserisci uno studente per riga, nel formato:</p>

        <table cellpadding="6" cellspacing="0" class="tabella tabella-compatta">
        <tr class="intestazione-tabella"><td><b>Esempio di file base</b></td></tr>
        <tr><td><code>Alighieri;Dante;M<br>Brontë;Charlotte;F<br>D'Annunzio;Gabriele;M<br>García Márquez;Gabriel;M<br>Ortese;Anna Maria;F</code></td></tr>
        </table>

        <p>Usa "<code>M</code>" oppure "<code>F</code>" per il genere e separa i tre dati con un punto e virgola, come nell'esempio. Sono ammessi gli spazi all'interno di nomi o cognomi composti. Nei nomi e cognomi non usare i caratteri riservati <code>_</code>, <code>;</code>, <code>,</code> e <code>:</code>; inoltre il cognome non può iniziare con <code>#</code>, perché la riga verrebbe interpretata come commento. Usa normalmente lettere, spazi, apostrofi o trattini. Non è necessario ordinare gli studenti: l'Editor provvederà da solo a mostrarli in ordine alfabetico.</p>

        <p class="riquadro riquadro-info">[[ICON:info:17]] L'Editor accetta anche un file base con due soli campi, "<code>Cognome;Nome</code>", ma prima del salvataggio richiederà di selezionare "M" o "F" per ogni studente. Per il primo utilizzo conviene quindi compilare subito tutti e tre i campi.</p>

        <p><b>2 ~ Seleziona la classe</b></p>
        <p>Clicca su "<b>Seleziona classe</b>" e scegli il file che hai appena creato.</p>
        <p>Se carichi un file <b>BASE</b>, un messaggio ti ricorderà che, per ogni allievo, puoi modificare la "posizione" e impostare eventuali "affinità" e "incompatibilità" con altri compagni. Se invece riapri un file <b>COMPLETO</b> già salvato da «PostiPerfetti», ritroverai anche le impostazioni inserite in precedenza.</p>
        <p>Non devi compilare manualmente il formato COMPLETO: viene creato e aggiornato dal programma quando premerai su <b>"SALVA e CARICA"</b>.</p>

        <p><b>3 ~ Controlli automatici</b></p>
        <p>Quando selezioni una classe, l'Editor controlla che il file sia leggibile e coerente. Le piccole irregolarità che possono essere sistemate senza ambiguità vengono gestite automaticamente; se invece trova un problema che richiede una tua scelta, ti indica che cosa va corretto prima di caricare il file.</p>

        <hr>
        <h3 class="sezione">[2] - IMPOSTA LA POSIZIONE E I VINCOLI</h3>

        <p><b>1 ~ Posizione</b></p>
        <p>Per ogni studente puoi scegliere una delle seguenti voci:</p>
        <p>• <code>NORMALE</code> = nessuna preferenza rispetto alla zona dell'aula;<br>
        • <code><span class="testo-errore"><b>PRIMA</b></span></code> = <span class="testo-errore"><b>deve stare in uno dei banchi marcati DAVANTI nel Layout</b></span> (utile ad es. per allievi più propensi a distrarsi, con difficoltà di vista o altri bisogni particolari);<br>
        • <code>ULTIMA</code> = preferenza per stare verso il fondo dell'aula (utile ad es. per allievi di alta statura o per altre esigenze);<br>
        • <code><span class="testo-errore"><b>FISSO</b></span></code> = <span class="testo-errore"><b>posto fisico stabile</b></span>: occupa il singolo posto scelto dal docente nel Layout.</p>

        <p><b>PRIMA e FISSO sono vincoli assoluti: non vengono mai ignorati.</b> ULTIMA è invece una preferenza: il programma cerca di rispettarla, ma può rinunciarvi quando è necessario per trovare una disposizione valida.</p>

        <p class="riquadro riquadro-info">
        <b>[[ICON:armchair:18]] LO STUDENTE FISSO</b><br><br>
        La posizione <b>FISSO</b> è pensata soprattutto per allievi con Bisogni Educativi Speciali o altre esigenze che richiedono una collocazione stabile e costante nel tempo.<br><br>
        • Può esserci <b>al massimo un FISSO</b> per classe.<br>
        • Nel <b>Layout</b> scegli graficamente il singolo posto riservato al FISSO: può trovarsi in un banco da 2 o da 3, in zona DAVANTI, neutra oppure IN FONDO. <b>FISSO non implica automaticamente DAVANTI.</b><br>
        • I compagni adiacenti possono cambiare nelle diverse assegnazioni: il programma li sceglie tenendo conto dei vincoli e delle vicinanze già sperimentate. <b>Se il FISSO occupa il posto centrale di un banco da 3, ha due vicini diretti: entrambe le vicinanze contano nelle rotazioni.</b><br>
        • Nella scheda del FISSO, incompatibilità e affinità sono disabilitate. Se, ad esempio, vuoi favorire la vicinanza con un determinato allievo, imposta <b>nella scheda di quell'allievo</b> un'affinità di livello 3 con il FISSO.
        </p>

        <p><b>2 ~ Incompatibilità</b></p>
        <p>Clicca su <b>"Aggiungi INCOMPATIBILITÀ"</b>, scegli il compagno e poi seleziona il livello:</p>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Livello</b></td><td><b>Come viene considerato</b></td></tr>
        <tr><td class="cella-centro"><b>1</b></td><td>Meglio non vicini, ma accettabile se necessario</td></tr>
        <tr><td class="cella-centro"><b>2</b></td><td>Da evitare con maggior forza</td></tr>
        <tr><td class="cella-centro testo-errore"><b>3</b></td><td class="testo-errore"><b>Mai vicini: vincolo assoluto</b></td></tr>
        </table>

        <p><b>3 ~ Affinità</b></p>
        <p>Clicca su <b>"Aggiungi AFFINITÀ"</b>, scegli il compagno e poi seleziona il livello:</p>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Livello</b></td><td><b>Come viene considerato</b></td></tr>
        <tr><td class="cella-centro"><b>1</b></td><td>Lieve preferenza per stare vicini</td></tr>
        <tr><td class="cella-centro"><b>2</b></td><td>Preferenza più marcata</td></tr>
        <tr><td class="cella-centro"><b>3</b></td><td><b>Forte preferenza, ma non obbligo assoluto</b></td></tr>
        </table>

        <p>Puoi aggiungere più "incompatibilità" e/o "affinità" per lo stesso studente. Dopo aver scelto il compagno, <b>seleziona sempre anche il livello</b>. Se una relazione resta incompleta, il programma ti chiederà di completarla prima di salvare.</p>

        <p><b>4 ~ Modifica e rimozione dei vincoli</b></p>
        <p>Ogni relazione è <b>bidirezionale</b>: quando aggiungi o modifichi un vincolo, l'Editor aggiorna automaticamente anche la scheda dell'altro studente. Non devi quindi inserirlo due volte. Per eliminarlo, clicca su "<b>Rimuovi</b>" in una delle due schede: verrà rimosso automaticamente anche dall'altra.</p>

        <p class="riquadro riquadro-info">[[ICON:info:17]] <b>Nei banchi da 3 posti il programma considera vicini soltanto gli studenti seduti uno accanto all'altro.</b> Vale anche per un banco da 3 costruito nel Layout. Ad esempio, in "<code>Anna + Luca + Marco</code>", Anna è vicina a Luca e Luca è vicino a Marco; Anna e Marco, invece, non sono considerati vicini.</p>

        <p><b>5 ~ Gestione studenti e strumenti dell'Editor</b></p>
        <p>Quando una classe è aperta puoi gestire l'elenco direttamente dalla GUI:<br>
        • <b>"Aggiungi studente"</b>: chiede cognome, nome e genere. Il nuovo studente viene inserito con posizione <code>NORMALE</code> e senza vincoli; completa poi le eventuali impostazioni e usa <b>"SALVA e CARICA"</b>;<br>
        • <b>"Elimina studente"</b>: è presente nella scheda di ciascun allievo. Prima di procedere chiede conferma e rimuove automaticamente dalle altre schede i vincoli che lo riguardano. <b>Le assegnazioni già salvate nello Storico non vengono riscritte.</b></p>

        <p>Puoi inoltre usare alcuni strumenti per controllare più facilmente il lavoro svolto:<br>
        • <b>"Espandi schede"</b> / <b>"Comprimi schede"</b>: apre o richiude insieme tutte le schede degli studenti;<br>
        • <b>"Dettaglio vincoli"</b>: raccoglie in un'unica vista tutte le incompatibilità, affinità e posizioni inserite;<br>
        • <b>"Anteprima file classe (.txt)"</b>: mostra come apparirà il file completo dopo il salvataggio.</p>

        <p>Il pulsante <b>"CHIUDI FILE"</b> chiude la classe aperta. Se esiste un'assegnazione Mensile non ancora salvata, prima ti chiede se <b>salvarla, chiudere senza salvarla o annullare</b>; se nell'Editor ci sono modifiche non salvate, ti offre invece <b>"Salva ed esci"</b>, <b>"Esci senza salvare"</b> oppure <b>"Annulla"</b>. Le stesse protezioni vengono applicate anche quando chiudi l'intero programma.</p>

        <p class="riquadro riquadro-info">[[ICON:save:17]] <b>Quando hai terminato le modifiche, usa "SALVA e CARICA".</b> Il programma aggiorna il file della classe e rende operative le nuove impostazioni. <b>Finché non lo fai, le modifiche dell'Editor non vengono usate nelle assegnazioni.</b></p>

        <p>Se è presente una proposta <b>Mensile non ancora salvata</b>, prima di aggiornare il file-classe il programma ti chiede come procedere: <b>"Salva assegnazione"</b> conserva la disposizione nello Storico, <b>"Prosegui senza salvare"</b> permette di abbandonarla, <b>"Annulla"</b> lascia aperta la proposta e non scrive il file-classe. Se annulli o non riesci a completare il salvataggio dell'assegnazione, il ricaricamento non prosegue.</p>

        <hr>
        <h3 class="sezione">[3] - SALVA E CONFIGURA LE ASSEGNAZIONI</h3>

        <p>Dopo aver cliccato su <b>"SALVA e CARICA"</b>, compariranno nel pannello di sinistra i seguenti box:</p>

        <p><b>1 ~ STATO CLASSE</b></p>
        <p>Mostra nome del file, numero degli studenti e stato del caricamento. È un riepilogo di sola lettura.</p>

        <p><b>2 ~ CONFIGURAZIONE AULA E LAYOUT</b></p>
        <p>Il box <b>Configurazione aula</b> riepiloga i dati. Per disporre i banchi apri la scheda <b>Layout</b>, dopo l'Editor studenti.</p>
        <p>La griglia permette di aggiungere <b>blocchi da 2</b>, <b>blocchi da 3</b> e <b>spazi liberi</b>. Con un clic sul riquadro apri il menu, scegli o sposta il blocco, oppure lo elimini. I corridoi e gli spazi liberi fanno parte della piantina reale; la cattedra è in basso.</p>
        <p>Per ogni banco puoi indicare la zona <b>DAVANTI</b>, <b>NEUTRA</b> oppure <b>IN FONDO</b>. Le zone sono etichette esplicite: non si deducono dalla semplice posizione grafica del banco.</p>
        <p>Se nella classe è presente un <b>FISSO</b>, scegli graficamente il singolo posto riservato allo studente. <b>FISSO non implica automaticamente DAVANTI.</b></p>
        <p>Prima della generazione il programma verifica che i posti coprano gli studenti, che le zone soddisfino le richieste PRIMA e che l'eventuale FISSO abbia un posto valido.</p>
        <p>Se uno o più studenti preferiscono la posizione <b>ULTIMA</b> ma non ci sono abbastanza posti <b>IN FONDO</b>, riceverai un avviso prima di avviare il Mensile o l'Annuale. Potrai tornare al Layout oppure continuare ugualmente: ULTIMA è una preferenza, non un vincolo assoluto.</p>

        <p><b>3 ~ GENERE MISTO</b></p>
        <p>L'opzione <b>"Preferisci vicinanze miste (M+F)"</b> favorisce le adiacenze tra studenti di genere diverso, senza renderle obbligatorie.</p>

        <p><b>4 ~ TIPO DI ASSEGNAZIONE</b></p>
        <p>Il box mostra un riepilogo delle assegnazioni eventualmente salvate nello Storico e permette di scegliere:</p>
        <p>• <b>Mensile (un mese)</b>: genera una sola disposizione;<br>
        • <b>Annuale (più mesi)</b>: genera da 1 a 10 disposizioni consecutive e le presenta insieme in un'anteprima.</p>

        <p class="riquadro riquadro-info">
        [[ICON:history:18]] <b>COME FUNZIONA LA ROTAZIONE</b><br><br>
        Lo Storico viene consultato automaticamente. Nei tentativi più restrittivi le vicinanze già utilizzate vengono escluse; se le combinazioni nuove non bastano più, possono essere riutilizzate con una forte penalità e vengono segnalate nel Report.<br><br>
        Il <b>Layout unico</b> usa un solo Storico per la classe: le vicinanze effettivamente salvate vengono considerate nelle generazioni mensili e annuali successive, anche se nel frattempo modifichi la geometria dei banchi.
        </p>

        <hr>
        <h3 class="sezione">[4] - GENERA CON "MENSILE" O "ANNUALE"</h3>

        <p><b>1 ~ Controlli prima dell'avvio</b></p>
        <p>Quando premi <b>"ASSEGNA I POSTI!"</b>, il programma controlla che:</p>
        <p>• la classe sia stata salvata e caricata;<br>
        • non restino relazioni di affinità/incompatibilità incomplete;<br>
        • non ci siano modifiche non salvate nell'Editor;<br>
        • non sia stato indicato più di un FISSO;<br>
        • nel Layout, i posti costruiti coincidano con gli studenti, le zone DAVANTI/IN FONDO siano coerenti con le richieste di posizione e l'eventuale FISSO abbia un posto assegnato.</p>
        <p>Se trova un problema, l'elaborazione non parte e un messaggio ti indica che cosa correggere.</p>

        <p><b>2 ~ Se non trova subito una soluzione</b></p>
        <p>«PostiPerfetti» effettua automaticamente più tentativi. Parte cercando di rispettare tutti i criteri impostati e di non ripetere vicinanze già presenti nello Storico. Se non trova una soluzione, allenta progressivamente soltanto i criteri non assoluti: prima quelli di livello 1, poi quelli di livello 2 e la posizione ULTIMA. Solo nell'ultimo tentativo può mettere da parte anche le affinità di livello 3 e la preferenza per il genere misto, ammettendo se necessario alcune vicinanze già utilizzate (che vengono segnalate nel Report).</p>

        <p class="riquadro riquadro-info">[[ICON:shield-check:17]] <b>Restano sempre vincoli assoluti (= non vengono mai violati):</b> le incompatibilità di livello 3 e le posizioni PRIMA e FISSO.</p>

        <p><b>3 ~ Modalità MENSILE</b></p>
        <p>Genera una sola disposizione. Al termine si apre direttamente la scheda <b>Disposizione</b> e compare un popup con le statistiche generali. Nella scheda <b>Report</b> trovi il dettaglio dell'assegnazione.</p>
        <p>Se vuoi conservarla, usa il pulsante <b>"Salva assegnazione"</b>. Dopo il salvataggio si abilitano <b>"Esporta Excel"</b> e <b>"Esporta report"</b>. Soltanto le disposizioni salvate nello Storico vengono considerate nelle rotazioni future. Se provi ad avviare una nuova assegnazione, selezionare un'altra classe, chiudere il file o uscire dal programma mentre il risultato Mensile è ancora da salvare, «PostiPerfetti» ti chiede prima se salvarlo, scartarlo consapevolmente o annullare l'operazione.</p>

        <p><b>4 ~ Modalità ANNUALE</b></p>
        <p>Il programma genera i mesi richiesti e, <b>finché il tempo disponibile lo consente</b>, prova e confronta più annate candidate per scegliere quella più equilibrata. Nella valutazione tiene conto soprattutto delle vicinanze già utilizzate e delle incompatibilità, considerando anche le affinità; inoltre cerca, quando necessario, di distanziare nel tempo i riutilizzi. Non è garantito che riesca a produrre più annate complete prima dello stop: nei casi difficili può anche fermarsi dopo la prima candidata utile.</p>
        <p>Puoi interrompere l'elaborazione con <b>"Annulla"</b>.</p>
        <p>Nell'anteprima, per ogni mese puoi leggere le statistiche, aprire <b>"Disposizione"</b> e consultare il <b>"Report"</b>. Alla fine scegli:</p>
        <p>• <b>"Accetta e salva nello Storico"</b>: salva tutti i mesi in ordine;<br>
        • <b>"Scarta"</b>: apre una conferma; scegliendo poi <b>"Scarta tutto"</b> non viene salvato nessun mese e lo Storico resta invariato.</p>
        <p>Se chiudi l'anteprima con la <b>X</b> prima di aver scelto, compare la stessa conferma: puoi annullare la chiusura oppure scartare consapevolmente l'intera annata.</p>
        <p>Se la ricerca non riesce a completare l'annata richiesta, non viene presentata una proposta parziale come pronta da salvare. Il processo segnala il problema senza modificare lo Storico.</p>

        <p class="riquadro riquadro-avviso">[[ICON:triangle-alert:17]] <b>Nota sulla geometria del Layout.</b> Riprodurre più fedelmente l'aula reale riduce, in alcuni casi, la libertà combinatoria del programma. Una geometria molto vincolante può quindi richiedere più compromessi soprattutto negli ultimi mesi dell'anno oppure impedire di completare tutti i mesi entro il tempo massimo. I vincoli assoluti restano comunque rispettati: In caso di risultato incompleto il programma segnala la mancata generazione e non lo inserisce nello Storico.</p>

        <hr>
        <h3 class="sezione">[5] - GESTISCI I RISULTATI</h3>

        <p><b>[[ICON:eye:18]] Scheda Disposizione</b></p>
        <p>Mostra la piantina della classe. Il fondo dell'aula è in alto; LIM, cattedra e lavagna sono in basso.</p>
        <p>I banchi occupati da femmine sono rosa tenue; il posto FISSO è evidenziato in rosso nelle viste dell'assegnazione. Nell'Excel il FISSO non riceve marcature speciali: resta soltanto il colore dell'occupante. Le vecchie voci dello Storico prive del genere conservano il colore precedente.</p>
        <p>Nella modalità <b>Mensile</b>, per conservare la disposizione, usa "<b>Salva assegnazione</b>": soltanto dopo il salvataggio entrerà nello Storico e sarà presa in considerazione nelle rotazioni future.</p>
        <p>Puoi inoltre usare:<br>
        • "<b>Esporta Excel</b>": crea un file <code>.xlsx</code> modificabile e stampabile (con MS Excel oppure con LibreOffice Calc);<br>
        • "<b>Esporta report</b>": salva in <code>.txt</code> il report completo.</p>
        <p>Le esportazioni vengono abilitate dopo il salvataggio nello Storico.</p>

        <p><b>[[ICON:move:18]] Modifica i posti con il trascinamento (Drag &amp; Drop)</b></p>
        <p>Prima di salvare una proposta <b>Mensile</b>, clicca su <b>"Modifica posti"</b>. Si apre una finestra nella quale puoi provare gli scambi, confrontarne gli effetti e decidere se adottarli. Nel caso <b>Annuale</b>, lo stesso pulsante è disponibile per ciascun mese dell'anteprima; dopo una modifica diventa <b>"Modifica/ripristina posti"</b>.</p>
        <p>• Per <b>scambiare due studenti</b>, trascina il nome di uno sul posto dell'altro.<br>
        • Per <b>scambiare gli occupanti di due blocchi</b>, tieni premuto <b>CTRL</b> durante il trascinamento. I blocchi devono avere la stessa capienza: due posti con due, oppure tre con tre.<br>
        • Se lo scambio viola un'incompatibilità <b>L3</b>, la posizione <b>PRIMA</b> o il posto <b>FISSO</b>, viene rifiutato e la disposizione resta invariata.</p>
        <p>Le preferenze funzionano diversamente dai vincoli obbligatori. Uno scambio può aumentare i riusi o le incompatibilità L1/L2, ridurre le affinità soddisfatte, le vicinanze miste oppure gli studenti ULTIMA collocati IN FONDO. In questi casi compare <b>"Peggioramenti presenti"</b>: puoi usare <b>"Mostra dettagli"</b> per leggere quali studenti sono coinvolti e decidere consapevolmente se mantenere la modifica.</p>
        <p><b>"Annulla ultima mossa"</b> torna indietro di uno scambio; <b>"Ripristina disposizione automatica"</b> recupera i posti della proposta generata dal programma. Con <b>"Adotta modifiche"</b> confermi la bozza; con <b>"Scarta modifiche"</b> esci lasciando la proposta com'era all'apertura della finestra. Se, attraverso gli scambi, torni esattamente ai posti presenti all'apertura, il pulsante di adozione si disabilita perché non ci sono cambiamenti da applicare.</p>
        <p class="riquadro riquadro-info">[[ICON:save:17]] <b>Adottare le modifiche non significa ancora salvarle nello Storico.</b> Nel Mensile devi poi premere <b>"Salva assegnazione"</b>; nell'Annuale devi confermare l'intera proposta con <b>"Accetta e salva nello Storico"</b>. Se avevi già adottato una modifica e in seguito torni alla disposizione automatica, puoi confermare questo ritorno: la proposta non viene più indicata come modificata manualmente.</p>
        <p><b>Nell'Annuale gli effetti si valutano in ordine di mese.</b> Per esempio, una nuova vicinanza introdotta al mese 2 può diventare un riuso nel mese 7. Il programma aggiorna report e indicatori dei mesi successivi, senza spostarne automaticamente gli studenti. L'indicatore con la mano segnala soltanto i mesi i cui posti differiscono dalla proposta automatica.</p>
        <p>Nell'anteprima Annuale, <b>"Annulla ultima modifica"</b> annulla l'ultima modifica confermata anche quando riguarda un mese diverso da quello appena consultato. <b>"Ripristina tutti i mesi"</b> riporta l'intera annata alla proposta automatica. Fino all'accettazione finale lavori su una bozza: queste operazioni non modificano lo Storico.</p>

        <p><b>[[ICON:file-text:18]] Scheda Report</b></p>
        <p>Spiega nel dettaglio come è stata costruita la disposizione: mostra le statistiche generali, la composizione dei gruppi, la valutazione delle singole vicinanze, le affinità e incompatibilità rilevate, il rispetto delle posizioni, gli eventuali riutilizzi e una rappresentazione testuale dell'aula. Le righe relative alle vicinanze già utilizzate vengono evidenziate in ocra.</p>

        <p><b>[[ICON:history:18]] Scheda Storico</b></p>
        <p>Conserva tutte le assegnazioni salvate. La tabella mostra data, nome, composizione e azioni. Puoi:</p>
        <p>• rinominare una voce facendo doppio clic nella cella <b>Nome</b>;<br>
        • cliccare sull'intestazione <b>Nome</b> per ordinare A–Z o Z–A, oppure su <b>Data creazione</b> per ordinare dalle date meno recenti alle più recenti e viceversa; le frecce sono sempre visibili. L'ordinamento riguarda la visualizzazione e non cambia la memoria delle rotazioni;<br>
        • usare <b>"Dettagli"</b> per leggere ed esportare il Report;<br>
        • usare <b>"Layout"</b> per rivedere la piantina, esportarla in Excel oppure salvare il Report in <code>.txt</code>;<br>
        • usare <b>"Elimina"</b> per rimuovere definitivamente l'assegnazione.</p>

        <p class="riquadro riquadro-info">[[ICON:history:17]] <b>Per mantenere corretta la memoria delle rotazioni, conserva nello Storico soltanto le disposizioni effettivamente usate in classe.</b> Se ne hai salvata una ma poi hai deciso di non applicarla, eliminala prima di generarne di nuove. Dopo un'eliminazione il programma ricostruisce automaticamente le rotazioni usando solo le assegnazioni rimaste.</p>

        <p><b>[[ICON:chart-column:18]] Scheda Statistiche</b></p>
        <p>Comprende tutto ciò che è accaduto nelle assegnazioni salvate nello Storico. Se sono presenti più classi, seleziona prima quella che vuoi controllare. Troverai il riepilogo generale, le vicinanze più frequenti con le assegnazioni in cui si sono verificate, le <b>statistiche sui trii</b>, il dettaglio dei vicini di ogni studente, le presenze nella zona anteriore e le vicinanze mai registrate.</p>
        <p>Il pulsante <b>"Esporta statistiche"</b> salva l'intero riepilogo in un file di testo.</p>

        <hr>
        <h3 class="sezione">[6] - DURANTE L'ANNO</h3>

        <p><b>[[ICON:square-pen:18]] Modifica posizione o vincoli</b></p>
        <p>Se durante l'anno vuoi cambiare "posizione", "affinità" o "incompatibilità" per qualche allievo, apri la classe nell'Editor (oppure usa quella già aperta), modifica le schede interessate e clicca su <b>"SALVA e CARICA"</b>. Le nuove impostazioni verranno usate a partire dalle assegnazioni successive.</p>

        <p><b>[[ICON:user-cog:18]] Aggiungi o rimuovi uno studente</b></p>
        <p>Non serve modificare a mano il file <code>.txt</code>. Apri la classe nell'Editor e usa <b>"Aggiungi studente"</b> oppure <b>"Elimina studente"</b> nella scheda dell'allievo. L'aggiunta crea uno studente <code>NORMALE</code> senza vincoli; l'eliminazione pulisce automaticamente dalle altre schede i vincoli che lo riguardano. Al termine usa <b>"SALVA e CARICA"</b>. Le vecchie assegnazioni già presenti nello Storico restano inalterate.</p>

        <p class="riquadro riquadro-info">
        [[ICON:history:18]] <b>Se rinomini il file della classe</b><br><br>
        «PostiPerfetti» può riconoscere la classe dai nomi degli studenti e proporti di ricollegarla allo Storico esistente, così da non perdere la memoria delle rotazioni precedenti.
        </p>

        <p><b>[[ICON:history:18]] Mantieni coerente lo Storico</b></p>
        <p>Conserva nello Storico soltanto le disposizioni effettivamente usate in classe. Se ne hai salvata una ma poi non l'hai applicata, eliminala prima di generarne di nuove. Le rotazioni vengono generate tenendo conto delle assegnazioni salvate.</p>

        <hr>
        <h3 class="sezione">[[ICON:triangle-alert:20]] RISOLUZIONE DEI PROBLEMI</h3>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Problema</b></td><td><b>Che cosa fare</b></td></tr>
        <tr><td>[[ICON:file-x:17]] Errore durante il caricamento del file della classe (.txt)</td><td>Sono ammesse righe BASE con 2 o 3 campi (<code>Cognome;Nome[;M/F]</code>) e righe COMPLETE con 6 campi. Se un file contiene dati completi, eventuali righe BASE presenti nello stesso file vengono accettate e completate nell'Editor; con <b>"SALVA e CARICA"</b> il file sarà poi riscritto nel formato completo canonico. Altri numeri di campi vengono rifiutati: leggi il dettaglio del popup, che indica la riga da controllare.</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Caratteri non ammessi nei nomi</td><td>Nei nomi e cognomi non usare underscore (<code>_</code>), punto e virgola (<code>;</code>), virgola (<code>,</code>) o due punti (<code>:</code>). Il carattere <code>#</code> non è vietato in assoluto, ma <b>il cognome non può iniziare con #</b>, perché l'intera riga verrebbe letta come commento. Usa normalmente lettere, spazi, apostrofi o trattini.</td></tr>
        <tr><td>[[ICON:file-x:17]] Problema di codifica del file</td><td>Se il file è UTF-16 o UTF-32 riconosciuto con certezza, «PostiPerfetti» propone <b>"Crea copia UTF-8 e carica"</b>, lasciando intatto l'originale. Se rileva una codifica occidentale precedente (Windows-1252/Latin-1), puoi scegliere <b>"Carica e controlla"</b>: verifica accenti e caratteri speciali e il successivo <b>"SALVA e CARICA"</b> convertirà il file in UTF-8. Solo quando la conversione automatica non è possibile devi aprire il file in un editor di testo, salvarlo manualmente come UTF-8 e selezionarlo di nuovo.</td></tr>
        <tr><td>[[ICON:users:17]] Studenti Cognome e Nome identici</td><td>Aggiungi un nome o una sigla distintiva, ad es. "Giovanni Bianchi (biondo)" oppure "Giovanni Bianchi2".</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Genere non impostato</td><td>Seleziona "M" o "F" per tutti gli studenti prima di cliccare su "SALVA e CARICA".</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Relazione di "incompatibilità"/"affinità" incompleta</td><td>Completala inserendo sia il compagno sia il livello di "incompatibilità"/"affinità", oppure cancellala cliccando su "Rimuovi". Il salvataggio e l'assegnazione restano bloccati finché non sistemi l'impostazione del vincolo.</td></tr>
        <tr><td>[[ICON:circle-x:17]] Relazioni contraddittorie o livelli diversi</td><td>Correggi le schede indicate: se ad es. "Rossi" ha affinità 1 con "Bianchi", ma "Bianchi" ha affinità 3 con "Rossi", il programma non può decidere quale delle due versioni sia quella giusta.</td></tr>
        <tr><td>[[ICON:armchair:17]] Più di uno studente FISSO</td><td>Lascia la posizione "FISSO" a un solo studente e modifica quella degli altri.</td></tr>
        <tr><td>[[ICON:circle-stop:17]] L'assegnazione fallisce</td><td>Controlla soprattutto la quantità delle incompatibilità di livello 3 e il numero di studenti con posizione PRIMA rispetto ai posti disponibili. Controlla che i posti del Layout, le zone DAVANTI/IN FONDO e il posto FISSO siano coerenti con la classe.</td></tr>
        <tr><td>[[ICON:history:17]] Compaiono vicinanze già utilizzate</td><td>Dopo molte assegnazioni le combinazioni nuove possono esaurirsi. Il Report segnala chiaramente i riutilizzi: significa che, con la configurazione e i vincoli correnti, il programma ha dovuto ammettere alcune vicinanze già impiegate.</td></tr>
        <tr><td>[[ICON:history:17]] L'Annuale produce meno mesi di quanti richiesti</td><td>Il budget massimo dell'elaborazione Annuale è di 10 minuti. Se non completa tutti i mesi richiesti, l'assegnazione non viene proposta per il salvataggio e lo Storico resta invariato.</td></tr>
        <tr><td>[[ICON:file-down:17]] Esportazioni disabilitate nella scheda Disposizione</td><td>Salva prima l'assegnazione nello Storico: le esportazioni dell'Excel e del Report vengono abilitate solo dopo il salvataggio.</td></tr>
        <tr><td>[[ICON:armchair:17]] Relazioni disabilitate nella scheda del FISSO</td><td>È normale: devi impostare le relazioni di "incompatibilità"/"affinità" nelle schede degli altri studenti.</td></tr>
        </table>

        <hr>
        <p class="pie-pagina">
        «PostiPerfetti» — Versione [[VERSIONE]]<br>
        Sviluppato in Python dal prof. Omar Ceretta<br>
        I.C. di Tombolo e Galliera Veneta (PD)<br>
        Licenza: GNU GPLv3</p>

"""

CREDITI_HTML_TEMPLATE = r"""
<div class="crediti-titolo"><h2>«PostiPerfetti»</h2></div>
<p class="cella-centro"><b>Versione [[VERSIONE]]</b></p>
<hr>
<p><b>Descrizione:</b><br>
Programma per l'assegnazione automatica dei posti in classe, con gestione di affinità, 
incompatibilità, posizione, genere misto, rotazione allievi e storico assegnazioni.</p>
<p><b>Autore:</b><br>
Prof. Omar Ceretta<br>
I.C. di Tombolo e Galliera Veneta (PD)</p>
<p><b>Tecnologie:</b><br>
Python 3 · PySide6 (Qt) · XlsxWriter</p>
<hr>
<p><b>Componenti di terze parti</b></p>
<p>«PostiPerfetti» include componenti realizzati da altri autori:</p>
<p>[[ICON:circle-check:16]] <b>PySide6 (Qt for Python)</b> — © The Qt Company e
Qt Project. Licenza LGPL v3.<br>
Codice sorgente: <a href="https://download.qt.io/">download.qt.io</a></p>
<p>[[ICON:circle-check:16]] <b>XlsxWriter</b> — © John McNamara. Licenza BSD a
2 clausole.<br>
Il software è fornito «così com'è» dai suoi autori, che declinano ogni
garanzia e ogni responsabilità per danni derivanti dal suo utilizzo.<br>
Codice sorgente: <a href="https://github.com/jmcnamara/XlsxWriter">github.com/jmcnamara/XlsxWriter</a></p>
<p>[[ICON:circle-check:16]] <b>Noto Color Emoji</b> — © Google Inc. Licenza SIL
Open Font License 1.1. Testo completo nel file <code>risorse/font/LICENSE</code>.</p>
<p>[[ICON:circle-check:16]] <b>Lucide Icons</b> — © Lucide Icons and
Contributors, derivato da Feather Icons © Cole Bemis. Licenza ISC. Testo
completo nel file <code>risorse/icone/lucide/LICENSE</code>.</p>
<hr>
<p><b>Licenza — GNU General Public License v3.0 (GPLv3)</b></p>
<p>[[ICON:circle-check:16]] Questo software è libero: puoi usarlo, copiarlo,
studiarlo e redistribuirlo liberamente.</p>
<p>[[ICON:circle-check:16]] Se lo modifichi e redistribuisci, sei tenuto a
mantenere l'attribuzione al creatore originale e a rendere pubblico il codice
sorgente delle tue modifiche con la stessa licenza GPLv3.</p>
<p>[[ICON:info:16]] Il software è distribuito <i>«così com'è»</i>, senza alcuna
garanzia espressa o implicita.</p>
<hr>
<p>Pagina GitHub con il codice sorgente:<br>
<a href="https://github.com/Omar-Ceretta/PostiPerfetti">github.com/Omar-Ceretta/PostiPerfetti</a></p>
<p>Sito web:<br>
<a href="https://postiperfetti.it/">postiperfetti.it/</a></p>

"""


def _css_documento() -> str:
    """Foglio stile condiviso dai documenti informativi rich text."""
    return f"""
        body {{
            background-color: {C('istruzioni_documento_bg')};
            color: {C('testo_principale')};
            font-size: 11pt;
        }}
        p {{ margin-top: 6px; margin-bottom: 8px; }}
        h2.titolo, div.crediti-titolo h2 {{
            color: {C('istruzioni_titolo')};
            text-align: center;
            margin-top: 4px;
            margin-bottom: 8px;
        }}
        h3.sezione {{
            color: {C('istruzioni_titolo')};
            background-color: {C('istruzioni_sezione_bg')};
            border: 1px solid {C('istruzioni_sezione_bordo')};
            padding: 8px;
            margin-top: 18px;
            margin-bottom: 10px;
            text-align: center;
        }}
        hr {{
            color: {C('istruzioni_bordo')};
            background-color: {C('istruzioni_bordo')};
            height: 1px;
        }}
        .riquadro {{
            padding: 10px;
            margin-top: 9px;
            margin-bottom: 10px;
        }}
        .riquadro-info {{
            background-color: {C('istruzioni_info_bg')};
            color: {C('istruzioni_info_txt')};
            border: 1px solid {C('istruzioni_info_bordo')};
            border-left: 4px solid {C('istruzioni_info_bordo')};
        }}
        .riquadro-avviso {{
            background-color: {C('istruzioni_avviso_bg')};
            color: {C('istruzioni_avviso_txt')};
            border: 1px solid {C('istruzioni_avviso_bordo')};
            border-left: 4px solid {C('istruzioni_avviso_bordo')};
        }}
        table.tabella {{
            border-collapse: collapse;
            margin-top: 8px;
            margin-bottom: 10px;
            background-color: {C('istruzioni_card_bg')};
        }}
        table.tabella-compatta {{ width: 56%; }}
        table.tabella td {{
            border: 1px solid {C('istruzioni_bordo')};
            padding: 6px;
            background-color: {C('istruzioni_card_bg')};
            color: {C('testo_principale')};
        }}
        table.tabella tr.intestazione-tabella td {{
            background-color: {C('istruzioni_tabella_header_bg')};
            color: {C('istruzioni_tabella_header_txt')};
        }}
        code {{
            background-color: {C('istruzioni_codice_bg')};
            color: {C('istruzioni_codice_txt')};
            padding: 1px 3px;
        }}
        a {{ color: {C('istruzioni_link')}; }}
        .testo-errore {{ color: {C('istruzioni_testo_errore')}; }}
        .testo-successo {{ color: {C('istruzioni_testo_successo')}; }}
        .testo-avviso {{ color: {C('istruzioni_testo_avviso')}; }}
        .testo-info {{ color: {C('istruzioni_titolo')}; }}
        .testo-ocra {{ color: {C('istruzioni_testo_ocra')}; }}
        .forte {{ font-weight: bold; }}
        .cella-centro {{ text-align: center; }}
        .pie-pagina {{
            color: {C('istruzioni_testo_secondario')};
            font-size: 10pt;
            text-align: center;
        }}
    """


def _html_con_icone(documento: QTextDocument, template: str) -> str:
    """Sostituisce i token con immagini Lucide registrate nel documento."""
    def sostituisci(match: re.Match) -> str:
        nome = match.group(1)
        dimensione = int(match.group(2))
        url_testo = f"postiperfetti-icon-{nome}-{dimensione}"
        url = QUrl(url_testo)
        pixmap = carica_icona(nome).pixmap(QSize(dimensione, dimensione))
        documento.addResource(QTextDocument.ResourceType.ImageResource, url, pixmap)
        return (
            f'<img src="{url_testo}" width="{dimensione}" '
            f'height="{dimensione}" style="vertical-align: middle;">'
        )

    return _TOKEN_ICONA.sub(sostituisci, template)


def _sincronizza_sfondo_documento(widget: QTextEdit) -> None:
    """Sincronizza palette e sfondo di widget, viewport e documento.

    Alcuni stili Qt conservano nel viewport il precedente ``QPalette.Base``;
    aggiornare tutti i livelli evita residui grafici al cambio di tema.
    """
    sfondo = QColor(C('istruzioni_documento_bg'))
    testo = QColor(C('testo_principale'))
    selezione = QColor(C('accento'))
    testo_selezione = QColor(C('selezione_testo'))

    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Base, sfondo)
    palette.setColor(QPalette.ColorRole.Text, testo)
    palette.setColor(QPalette.ColorRole.Highlight, selezione)
    palette.setColor(QPalette.ColorRole.HighlightedText, testo_selezione)
    widget.setBackgroundRole(QPalette.ColorRole.Base)
    widget.setPalette(palette)

    viewport = widget.viewport()
    viewport.setBackgroundRole(QPalette.ColorRole.Base)
    viewport.setAutoFillBackground(True)
    viewport.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    viewport.setPalette(palette)
    viewport.setStyleSheet(
        f"background-color: {C('istruzioni_documento_bg')}; "
        f"color: {C('testo_principale')};"
    )

    frame_radice = widget.document().rootFrame()
    formato = frame_radice.frameFormat()
    formato.setBackground(QBrush(sfondo))
    frame_radice.setFrameFormat(formato)

    widget.update()
    viewport.update()


def _aggiorna_documento(widget: QTextEdit, template: str,
                         conserva_scroll: bool = False) -> None:
    """Rigenera tema e icone, conservando facoltativamente lo scorrimento."""
    template = template.replace("[[VERSIONE]]", VERSIONE)
    barra = widget.verticalScrollBar()
    massimo_precedente = barra.maximum()
    rapporto = (
        barra.value() / massimo_precedente
        if conserva_scroll and massimo_precedente > 0
        else 0.0
    )

    documento = widget.document()
    documento.setDefaultStyleSheet(_css_documento())
    widget.setHtml(_html_con_icone(documento, template))
    _sincronizza_sfondo_documento(widget)

    if conserva_scroll:
        def ripristina() -> None:
            try:
                barra.setValue(round(rapporto * barra.maximum()))
            except RuntimeError:
                pass
        QTimer.singleShot(0, ripristina)


def _applica_stile_documento(widget: QTextEdit) -> None:
    widget.setStyleSheet(f"""
        QTextEdit, QTextBrowser {{
            background-color: {C('istruzioni_documento_bg')};
            color: {C('testo_principale')};
            border: 1px solid {C('istruzioni_bordo')};
            border-radius: 7px;
            padding: 10px;
            selection-background-color: {C('accento')};
            selection-color: {C('selezione_testo')};
        }}
    """)
    _sincronizza_sfondo_documento(widget)


def _applica_stile_dialogo(dialog: QDialog) -> None:
    sfondo = QColor(C('sfondo_principale'))
    testo = QColor(C('testo_principale'))

    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, sfondo)
    palette.setColor(QPalette.ColorRole.WindowText, testo)
    dialog.setBackgroundRole(QPalette.ColorRole.Window)
    dialog.setPalette(palette)
    dialog.setAutoFillBackground(True)
    dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {C('sfondo_principale')};
            color: {C('testo_principale')};
        }}
        QLabel {{ color: {C('testo_principale')}; }}
    """)
    dialog.update()


def _applica_stile_chiudi(pulsante: QPushButton) -> None:
    pulsante.setStyleSheet(f"""
        QPushButton {{
            background-color: {C('btn_indaco_bg')};
            color: {C('btn_indaco_txt')};
            border: 1px solid {C('btn_indaco_bordo')};
            font-size: 13px;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 20px;
        }}
        QPushButton:hover {{
            background-color: {C('btn_indaco_hover')};
        }}
    """)


def aggiorna_tema_finestre_informative(parent) -> None:
    """Aggiorna la guida non modale se è aperta durante il cambio tema."""
    dialog = getattr(parent, '_dialog_istruzioni', None)
    if dialog is None:
        return
    try:
        callback = getattr(dialog, '_aggiorna_tema_istruzioni', None)
        if dialog.isVisible() and callable(callback):
            callback(conserva_scroll=True)
    except RuntimeError:
        parent._dialog_istruzioni = None


# Guida d'uso

def mostra_istruzioni(parent):
    """Mostra la guida non modale e impedisce finestre duplicate."""
    dialog_esistente = getattr(parent, '_dialog_istruzioni', None)
    if dialog_esistente is not None:
        try:
            if dialog_esistente.isVisible():
                dialog_esistente.raise_()
                dialog_esistente.activateWindow()
                return
        except RuntimeError:
            parent._dialog_istruzioni = None

    dialog = QDialog(parent)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    parent._dialog_istruzioni = dialog
    dialog.setWindowTitle("ISTRUZIONI")
    applica_icona_finestra(dialog, "book-open")
    adatta_finestra_allo_schermo(
        dialog,
        larghezza_ideale=950,
        altezza_ideale=750,
        larghezza_minima=700,
        altezza_minima=480,
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)

    font_documento = QFont(parent.font())
    font_documento.setPointSize(11)

    def crea_documento_istruzioni() -> QTextEdit:
        """Crea un viewport nuovo, senza cache grafiche del tema precedente."""
        documento = QTextEdit(dialog)
        documento.setObjectName("documentoIstruzioni")
        documento.setReadOnly(True)
        documento.setFont(font_documento)
        return documento

    text_edit = crea_documento_istruzioni()
    layout.addWidget(text_edit)

    btn_chiudi = QPushButton("Chiudi", dialog)
    applica_icona(btn_chiudi, "x", 18)
    btn_chiudi.setMinimumHeight(40)
    btn_chiudi.clicked.connect(dialog.close)
    layout.addWidget(btn_chiudi)

    def aggiorna(conserva_scroll: bool = False) -> None:
        nonlocal text_edit

        rapporto_scroll = 0.0
        if conserva_scroll:
            barra_vecchia = text_edit.verticalScrollBar()
            if barra_vecchia.maximum() > 0:
                rapporto_scroll = barra_vecchia.value() / barra_vecchia.maximum()

            # Alcuni stili Qt/KDE trattengono il vecchio viewport: sostituire
            # il QTextEdit evita residui grafici senza chiudere il dialogo.
            precedente = text_edit
            precedente.setObjectName("documentoIstruzioniObsoleto")
            text_edit = crea_documento_istruzioni()
            layout.replaceWidget(precedente, text_edit)
            precedente.hide()
            precedente.deleteLater()

        _applica_stile_dialogo(dialog)
        _applica_stile_documento(text_edit)
        _applica_stile_chiudi(btn_chiudi)
        _aggiorna_documento(
            text_edit,
            ISTRUZIONI_HTML_TEMPLATE,
            conserva_scroll=False,
        )

        if conserva_scroll:
            def ripristina_scroll() -> None:
                try:
                    barra_nuova = text_edit.verticalScrollBar()
                    barra_nuova.setValue(
                        round(rapporto_scroll * barra_nuova.maximum())
                    )
                except RuntimeError:
                    pass
            QTimer.singleShot(0, ripristina_scroll)

        # Espone tema e generazione come proprietà diagnostiche del dialogo.
        dialog.setProperty(
            "postiperfettiTemaIstruzioni",
            C("istruzioni_documento_bg"),
        )
        generazione = int(
            dialog.property("postiperfettiGenerazioneIstruzioni") or 0
        ) + 1
        dialog.setProperty("postiperfettiGenerazioneIstruzioni", generazione)

    dialog._aggiorna_tema_istruzioni = aggiorna

    def pulisci_riferimento(*_args) -> None:
        if getattr(parent, '_dialog_istruzioni', None) is dialog:
            parent._dialog_istruzioni = None

    dialog.destroyed.connect(pulisci_riferimento)
    aggiorna()
    dialog.show()


# Crediti e licenza

def mostra_crediti(parent):
    """Mostra informazioni sul programma, autore e licenza GNU GPLv3."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Informazioni su «PostiPerfetti»")
    applica_icona_finestra(dialog, "info")
    adatta_finestra_allo_schermo(
        dialog,
        larghezza_ideale=620,
        altezza_ideale=620,
        larghezza_minima=500,
        altezza_minima=460,
    )

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(24, 20, 24, 20)

    percorso_icona = get_resource_path(
        "icone",
        "postiperfetti_icon.png",
    )
    if os.path.exists(percorso_icona):
        label_icona = QLabel(dialog)
        pixmap = QPixmap(percorso_icona)
        label_icona.setPixmap(pixmap.scaled(
            80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
        label_icona.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_icona)

    browser = QTextBrowser(dialog)
    browser.setOpenExternalLinks(True)
    browser.setMinimumHeight(350)
    _applica_stile_documento(browser)
    _aggiorna_documento(browser, CREDITI_HTML_TEMPLATE)
    layout.addWidget(browser)

    bottoni = QDialogButtonBox(QDialogButtonBox.Close, dialog)
    btn_chiudi = bottoni.button(QDialogButtonBox.Close)
    if btn_chiudi is not None:
        btn_chiudi.setText("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        _applica_stile_chiudi(btn_chiudi)
    bottoni.rejected.connect(dialog.close)
    layout.addWidget(bottoni)

    _applica_stile_dialogo(dialog)
    dialog.exec()


# Aiuto per configurare l'aula

