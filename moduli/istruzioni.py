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
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontDatabase, QPalette, QPixmap, QTextDocument
)

from moduli.tema import C
from moduli.percorsi import get_resource_path
from moduli.versione import VERSIONE
from moduli.utilita import (
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
        [[ICON:circle-check:17]] Il lavoro parte da un file <code>.txt</code> con <b>cognome, nome e genere</b> degli allievi. Nella scheda "Editor studenti" puoi inserire quattro tipi di indicazioni: <b>posizione</b>, eventuale <b>FISSO</b>, <b>incompatibilità</b> e <b>affinità</b>.<br><br>
        [[ICON:circle-check:17]] Puoi disporre gli studenti <b>a coppie</b> oppure <b>a terzetti</b>. Quando il numero della classe non consente gruppi tutti uguali, il programma costruisce automaticamente il blocco finale necessario: un trio nella modalità a coppie; una coppia, un quartetto o, quando disponibile, due quartetti nella modalità a terzetti.<br><br>
        [[ICON:history:17]] Lo <b>Storico</b> è la memoria delle rotazioni: soltanto le assegnazioni salvate vengono considerate nelle generazioni successive. Le modalità a coppie e a terzetti mantengono memorie separate.<br><br>
        [[ICON:circle-check:17]] <b>Durante l'uso, il programma lavora in locale e non invia in rete i dati delle classi.</b>
        </p>

        <hr>
        <h3 class="sezione">[1] - PREPARA E SELEZIONA LA CLASSE</h3>

        <p><b>1 ~ Crea un file .txt di base</b></p>
        <p>Nella scheda "<b>Editor studenti</b>", clicca su "<b>Apri cartella</b>". Il tuo file manager ti mostrerà la cartella che contiene le classi, dove troverai due file di esempio:<br>
        • <code>Classe-BASE_esempio.txt</code>, che mostra il semplice formato da usare per creare una nuova classe;<br>
        • <code>Classe-COMPLETO_esempio.txt</code>, che mostra come apparirà il file dopo aver aggiunto posizione e vincoli tramite l'Editor.<br><br>
        Per creare la tua classe, usa come modello il file <b>BASE</b>, oppure crea un nuovo file di testo con il nome che preferisci (ad es. "<code>Classe 1A.txt</code>" o "<code>Classe 1A - 2026-27.txt</code>").</p>
        <p class="riquadro riquadro-info">[[ICON:info:17]] Nota per Windows: l'estensione ".txt" potrebbe essere nascosta, quindi è possibile che il file ti appaia semplicemente come "Classe 1A". È normale.<br>
        Usa un normale editor di testo, non un programma di videoscrittura come Microsoft Word o LibreOffice Writer.</p>
        <p>Inserisci uno studente per riga, nel formato:</p>

        <table cellpadding="6" cellspacing="0" class="tabella tabella-compatta">
        <tr class="intestazione-tabella"><td><b>Esempio di file base</b></td></tr>
        <tr><td><code>Alighieri;Dante;M<br>Brontë;Charlotte;F<br>D'Annunzio;Gabriele;M<br>García Márquez;Gabriel;M<br>Ortese;Anna Maria;F</code></td></tr>
        </table>

        <p>Usa "<code>M</code>" oppure "<code>F</code>" per il genere e separa i tre dati con un punto e virgola, come nell'esempio. Sono ammessi gli spazi all'interno di nomi o cognomi composti. <b>Non usare il carattere underscore (<code>_</code>)</b> per unire le parti di un nome o di un cognome: usa uno spazio o un trattino. Non è necessario ordinare gli studenti: l'Editor provvederà da solo a mostrarli in ordine alfabetico.</p>

        <p class="riquadro riquadro-info">[[ICON:info:17]] L'Editor accetta anche un file base con due soli campi, "<code>Cognome;Nome</code>", ma prima del salvataggio richiederà di selezionare "M" o "F" per ogni studente. Per il primo utilizzo conviene quindi compilare subito tutti e tre i campi.</p>

        <p><b>2 ~ Seleziona la classe</b></p>
        <p>Clicca su "<b>Seleziona classe</b>" e scegli il file <code>.txt</code>.</p>
        <p>Se carichi un file <b>BASE</b>, un messaggio ti ricorderà che, per ogni allievo, puoi modificare la "posizione" e impostare eventuali "affinità" e "incompatibilità" con altri compagni. Se invece riapri un file <b>COMPLETO</b> già salvato da «PostiPerfetti», ritroverai anche le impostazioni inserite in precedenza.</p>
        <p>Non devi compilare manualmente il formato COMPLETO: viene creato e aggiornato dal programma quando premerai su <b>"SALVA e CARICA"</b>.</p>

        <p><b>3 ~ Controlli automatici</b></p>
        <p>Quando selezioni una classe, l'Editor controlla che il file sia leggibile e coerente. Le piccole irregolarità che possono essere sistemate senza ambiguità vengono gestite automaticamente; se invece trova un problema che richiede una tua scelta, ti indica che cosa va corretto prima di caricare il file.</p>

        <hr>
        <h3 class="sezione">[2] - IMPOSTA GLI STUDENTI E I VINCOLI</h3>

        <p><b>1 ~ Posizione</b></p>
        <p>Per ogni studente puoi scegliere una delle seguenti voci:</p>
        <p>• <code>NORMALE</code> = nessuna preferenza rispetto alla fila;<br>
        • <code><span class="testo-errore"><b>PRIMA</b></span></code> = <span class="testo-errore"><b>deve stare nella prima fila</b></span> (utile ad es. per allievi più propensi a distrarsi, con difficoltà di vista o altri bisogni particolari);<br>
        • <code>ULTIMA</code> = preferenza per stare verso il fondo dell'aula (utile ad es. per allievi di alta statura o per altre esigenze);<br>
        • <code><span class="testo-errore"><b>FISSO</b></span></code> = <span class="testo-errore"><b>posto stabile nel primo banco a sinistra della prima fila</b></span>.</p>

        <p><b>PRIMA e FISSO sono vincoli assoluti: non vengono mai ignorati.</b> ULTIMA è invece una preferenza: il programma cerca di rispettarla, ma può rinunciarvi quando è necessario per trovare una disposizione valida.</p>

        <p class="riquadro riquadro-info">
        <b>[[ICON:armchair:18]] LO STUDENTE FISSO</b><br><br>
        La posizione <b>FISSO</b> è pensata soprattutto per un allievo che abbia bisogno di mantenere un posto stabile nel tempo.<br><br>
        • Può esserci <b>al massimo un FISSO</b> per classe.<br>
        • Occupa sempre il <b>primo posto a sinistra della prima fila</b>.<br>
        • Il compagno vicino può cambiare nelle diverse assegnazioni: il programma lo sceglie tenendo conto dei vincoli e delle vicinanze già sperimentate. In tutte le disposizioni il vicino diretto del FISSO avrà a sua volta un altro compagno al banco adiacente, in modo da non restare isolato se l'allievo FISSO dovesse temporaneamente uscire dall'aula.<br>
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

        <p class="riquadro riquadro-info">[[ICON:info:17]] <b>Nei terzetti e nei quartetti il programma considera vicini soltanto gli studenti seduti uno accanto all'altro.</b> Ad esempio, in "<code>Anna — Luca — Marco</code>", Anna è vicina a Luca e Luca è vicino a Marco; Anna e Marco, invece, non sono considerati vicini.</p>

        <p><b>5 ~ Strumenti dell'Editor</b></p>
        <p>Puoi usare alcuni strumenti facoltativi per controllare più facilmente il lavoro svolto:<br>
        • <b>"Espandi schede"</b>: mostra o comprime tutte le schede degli studenti;<br>
        • <b>"Dettaglio vincoli"</b>: raccoglie in un'unica vista tutte le incompatibilità, affinità e posizioni inserite;<br>
        • <b>"Anteprima file classe (.txt)"</b>: mostra come apparirà il file completo dopo il salvataggio.</p>

        <p>Il pulsante <b>"CHIUDI FILE"</b> chiude invece la classe aperta, avvisandoti se ci sono modifiche che non hai ancora salvato.</p>

        <p class="riquadro riquadro-info">[[ICON:save:17]] <b>Quando hai terminato le modifiche, usa "SALVA e CARICA".</b> Il programma aggiorna il file della classe e rende operative le nuove impostazioni. <b>Finché non lo fai, le modifiche dell'Editor non vengono usate nelle assegnazioni.</b></p>

        <hr>
        <h3 class="sezione">[3] - SALVA E CONFIGURA LE ASSEGNAZIONI</h3>

        <p>Dopo aver cliccato su <b>"SALVA e CARICA"</b>, compariranno nel pannello di sinistra i seguenti box:</p>

        <p><b>1 ~ STATO CLASSE</b></p>
        <p>Mostra nome del file, numero degli studenti e stato del caricamento. È un riepilogo di sola lettura.</p>

        <p><b>2 ~ CONFIGURAZIONE AULA</b></p>
        <p>Scegli come vuoi disporre gli studenti:</p>
        <p>• <b>A coppie</b>: gruppi di 2 studenti;<br>
        • <b>A terzetti</b>: gruppi di 3 studenti.</p>

        <p>Con <b>"Posti per fila"</b> stabilisci quanti posti può contenere ogni fila dell'aula:<br>
        • a coppie: da 4 a 10 posti, con variazioni di 2;<br>
        • a terzetti: 6 oppure 9 posti.</p>

        <p>Il numero delle <b>"File"</b> e i <b>"Posti totali"</b> si aggiornano da soli; eventuali posti eccedenti verranno rimossi automaticamente.</p>

        <p>Se hai dubbi sulla differenza fra <b>File</b> e <b>Posti per fila</b>, clicca sul pulsante [[ICON:circle-help:17]] accanto a "Posti totali" per vedere uno schema dell'aula.</p>

        <p><b>3 ~ GESTIONE NUMERO DISPARI / GESTIONE DEL RESTO</b></p>
        <p>Questo box compare soltanto quando il numero degli studenti richiede un gruppo diverso da quello previsto dalla modalità scelta.</p>

        <p><b>A coppie</b>, quando serve viene formato un trio. Puoi scegliere dove collocarlo tra le posizioni "<b>Davanti</b>", "<b>In mezzo</b>" o "<b>In fondo</b>".</p>

        <p><b>A terzetti</b>, se non è possibile formare soltanto gruppi da tre, «PostiPerfetti» crea automaticamente il gruppo necessario: un <b>quartetto</b> oppure una <b>coppia</b>. In alcuni casi, al posto della coppia, puoi scegliere di formare <b>2 quartetti</b>.</p>

        <p>Vengono mostrate soltanto le collocazioni compatibili con la disposizione dell'aula. Se ne esiste una sola, il programma la sceglie automaticamente e te lo indica nel box.</p>

        <p><b>4 ~ GENERE MISTO</b></p>
        <p>A coppie trovi l'opzione <b>"Preferisci coppie miste (M+F)"</b>; a terzetti diventa <b>"Preferisci vicinanze miste (M+F)"</b>. Se la attivi, il programma favorisce le combinazioni "maschio + femmina", ma <b>non le rende obbligatorie</b>.</p>

        <p><b>5 ~ MODALITÀ DI ASSEGNAZIONE</b></p>
        <p>Il box mostra un riepilogo delle assegnazioni eventualmente salvate nello Storico e permette di scegliere:</p>
        <p>• <b>Mensile (un mese)</b>: genera una sola disposizione;<br>
        • <b>Annuale (più mesi)</b>: genera da 1 a 10 disposizioni consecutive e le presenta insieme in un'anteprima.</p>

        <p class="riquadro riquadro-info">
        [[ICON:history:18]] <b>COME FUNZIONA LA ROTAZIONE</b><br><br>
        Lo Storico viene consultato automaticamente. Nei tentativi più restrittivi le vicinanze già utilizzate vengono escluse; se le combinazioni nuove non bastano più, possono essere riutilizzate con una forte penalità e vengono segnalate nel Report.<br><br>
        Le rotazioni sono <b>separate per modalità</b>: le coppie influenzano le future assegnazioni a coppie; le adiacenze dei terzetti influenzano le future assegnazioni a terzetti. Un precedente nell'altra modalità può comparire nel Report come informazione, ma non influenza la disposizione corrente.
        </p>

        <hr>
        <h3 class="sezione">[4] - GENERA CON "MENSILE" O "ANNUALE"</h3>

        <p><b>1 ~ Controlli prima dell'avvio</b></p>
        <p>Quando premi <b>"ASSEGNA I POSTI!"</b>, il programma controlla che:</p>
        <p>• la classe sia stata salvata e caricata;<br>
        • non restino relazioni di affinità/incompatibilità incomplete;<br>
        • non ci siano modifiche non salvate nell'Editor;<br>
        • non sia stato indicato più di un FISSO;<br>
        • la prima fila possa ospitare tutti gli studenti con posizione PRIMA.</p>
        <p>Se trova un problema, l'elaborazione non parte e un messaggio ti indica che cosa correggere.</p>

        <p><b>2 ~ Se non trova subito una soluzione</b></p>
        <p>«PostiPerfetti» effettua automaticamente più tentativi. Parte cercando di rispettare tutti i criteri impostati e di non ripetere vicinanze già presenti nello Storico. Se non trova una soluzione, allenta progressivamente soltanto i criteri non assoluti: prima quelli di livello 1, poi quelli di livello 2 e la posizione ULTIMA. Solo nell'ultimo tentativo può mettere da parte anche le affinità di livello 3 e la preferenza per il genere misto, ammettendo se necessario alcune vicinanze già utilizzate (che vengono segnalate nel Report).</p>

        <p class="riquadro riquadro-info">[[ICON:shield-check:17]] <b>Restano sempre vincoli assoluti (= non vengono mai violati):</b> le incompatibilità di livello 3 e le posizioni PRIMA e FISSO.</p>

        <p><b>3 ~ Modalità MENSILE</b></p>
        <p>Genera una sola disposizione. Al termine si apre direttamente la scheda <b>Aula</b> e compare un popup con le statistiche generali. Nella scheda <b>Report</b> trovi il dettaglio dell'assegnazione.</p>
        <p>Se vuoi conservarla, usa il pulsante <b>"Salva assegnazione"</b>. Dopo il salvataggio si abilitano <b>"Esporta Excel"</b> e <b>"Esporta Report"</b>. Soltanto le disposizioni salvate nello Storico vengono considerate nelle rotazioni future.</p>

        <p><b>4 ~ Modalità ANNUALE</b></p>
        <p>Il programma genera più mesi consecutivi, prova diverse annate complete e confronta i risultati per scegliere quella più equilibrata. Nella valutazione tiene conto soprattutto delle vicinanze già utilizzate e delle incompatibilità, considerando anche le affinità; inoltre cerca, quando necessario, di distanziare nel tempo i riutilizzi.</p>
        <p>Puoi interrompere l'elaborazione con <b>"Annulla"</b>.</p>
        <p>Nell'anteprima, per ogni mese puoi leggere le statistiche, aprire <b>"Vedi disposizione"</b> e consultare il <b>"Report"</b>. Alla fine scegli:</p>
        <p>• <b>"Accetta e salva nello Storico"</b>: salva tutti i mesi in ordine;<br>
        • <b>"Scarta tutto"</b>: non salva nulla e lascia lo Storico invariato.</p>
        <p>Se viene raggiunto il tempo massimo (ossia 10 minuti) prima di completare tutti i mesi richiesti, l'anteprima segnala chiaramente che l'annata è parziale. Puoi comunque valutarla e decidere se conservarla.</p>

        <hr>
        <h3 class="sezione">[5] - GESTISCI I RISULTATI</h3>

        <p><b>[[ICON:school:18]] Scheda Aula</b></p>
        <p>Mostra la piantina della classe. Il fondo dell'aula è in alto; LIM, cattedra e lavagna sono in basso.</p>
        <p>Nella modalità <b>Mensile</b>, per conservare la disposizione, usa "<b>Salva assegnazione</b>": soltanto dopo il salvataggio entrerà nello Storico e sarà presa in considerazione nelle rotazioni future.</p>
        <p>Puoi inoltre usare:<br>
        • "<b>Esporta Excel</b>": crea un file <code>.xlsx</code> modificabile e stampabile (con MS Excel oppure con LibreOffice Calc);<br>
        • "<b>Esporta Report</b>": salva in <code>.txt</code> il report completo.</p>
        <p>Le esportazioni vengono abilitate dopo il salvataggio nello Storico.</p>

        <p><b>[[ICON:file-text:18]] Scheda Report</b></p>
        <p>Spiega nel dettaglio come è stata costruita la disposizione: mostra le statistiche generali, la composizione dei gruppi, la valutazione delle singole vicinanze, le affinità e incompatibilità rilevate, il rispetto delle posizioni, gli eventuali riutilizzi e una rappresentazione testuale dell'aula. Le righe relative alle vicinanze già utilizzate vengono evidenziate in ocra.</p>

        <p><b>[[ICON:history:18]] Scheda Storico</b></p>
        <p>Conserva tutte le assegnazioni salvate. La tabella mostra data, nome, composizione e azioni. Puoi:</p>
        <p>• rinominare una voce facendo doppio clic nella cella <b>Nome</b>;<br>
        • usare <b>"Dettagli"</b> per leggere ed esportare il Report;<br>
        • usare <b>"Layout"</b> per rivedere la piantina, esportarla in Excel oppure salvare il Report in <code>.txt</code>;<br>
        • usare <b>"Elimina"</b> per rimuovere definitivamente l'assegnazione.</p>

        <p class="riquadro riquadro-info">[[ICON:history:17]] <b>Per mantenere corretta la memoria delle rotazioni, conserva nello Storico soltanto le disposizioni effettivamente usate in classe.</b> Se ne hai salvata una ma poi hai deciso di non applicarla, eliminala prima di generarne di nuove. Dopo un'eliminazione il programma ricostruisce automaticamente le rotazioni usando solo le assegnazioni rimaste.</p>

        <p><b>[[ICON:chart-column:18]] Scheda Statistiche</b></p>
        <p>Comprende tutto ciò che è accaduto nelle assegnazioni salvate nello Storico. Se sono presenti più classi, seleziona prima quella che vuoi controllare. Troverai il riepilogo generale, le coppie più frequenti, le statistiche sui terzetti, il dettaglio di quali compagni di banco ha avuto ogni studente, le presenze in prima fila e le coppie mai formate.</p>
        <p>Il pulsante <b>"Esporta le Statistiche (.txt)"</b> salva l'intero riepilogo in un file di testo.</p>

        <hr>
        <h3 class="sezione">[6] - DURANTE L'ANNO</h3>

        <p><b>[[ICON:square-pen:18]] Modifica posizione o vincoli</b></p>
        <p>Se durante l'anno vuoi cambiare "posizione", "affinità" o "incompatibilità" per qualche allievo, seleziona di nuovo il file della classe nell'Editor, modifica le schede interessate e clicca su <b>"SALVA e CARICA"</b>. Le nuove impostazioni verranno usate a partire dalle assegnazioni successive.</p>

        <p><b>[[ICON:user-cog:18]] Aggiungi o rimuovi uno studente</b></p>
        <p>Apri manualmente il file di testo della classe, aggiungi o elimina la riga dello studente e seleziona di nuovo il file nell'Editor. Se aggiungi uno studente, completa poi nell'Editor eventuali posizione e vincoli e clicca su <b>"SALVA e CARICA"</b>.</p>

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
        <tr><td>[[ICON:file-x:17]] Errore durante il caricamento del file della classe (.txt)</td><td>Un file BASE deve avere 2 o 3 campi per riga; un file COMPLETO deve averne esattamente 6. Leggi il dettaglio del popup, che indica la riga e il problema da correggere, quindi selezionalo di nuovo.</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Caratteri non ammessi nei nomi</td><td>Nei nomi e cognomi non usare underscore (<code>_</code>), punto e virgola (<code>;</code>), virgola (<code>,</code>), due punti (<code>:</code>) o cancelletto (<code>#</code>). Usa normalmente lettere, spazi, apostrofi o trattini.</td></tr>
        <tr><td>[[ICON:file-x:17]] Problema di codifica del file</td><td>Se il popup segnala un problema di codifica, apri il file con un editor di testo, salvalo con codifica "Unicode UTF-8" e selezionalo di nuovo.</td></tr>
        <tr><td>[[ICON:users:17]] Studenti Cognome e Nome identici</td><td>Aggiungi un nome o una sigla distintiva, ad es. "Giovanni Bianchi (biondo)" oppure "Giovanni Bianchi2".</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Genere non impostato</td><td>Seleziona "M" o "F" per tutti gli studenti prima di cliccare su "SALVA e CARICA".</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Relazione di "incompatibilità"/"affinità" incompleta</td><td>Completala inserendo sia il compagno sia il livello di "incompatibilità"/"affinità", oppure cancellala cliccando su "Rimuovi". Il salvataggio e l'assegnazione restano bloccati finché non sistemi l'impostazione del vincolo.</td></tr>
        <tr><td>[[ICON:circle-x:17]] Relazioni contraddittorie o livelli diversi</td><td>Correggi le schede indicate: se ad es. "Rossi" ha affinità 1 con "Bianchi", ma "Bianchi" ha affinità 3 con "Rossi", il programma non può decidere quale delle due versioni sia quella giusta.</td></tr>
        <tr><td>[[ICON:armchair:17]] Più di uno studente FISSO</td><td>Lascia la posizione "FISSO" a un solo studente e modifica quella degli altri.</td></tr>
        <tr><td>[[ICON:circle-stop:17]] L'assegnazione fallisce</td><td>Controlla soprattutto la quantità delle incompatibilità di livello 3 e il numero di studenti con posizione PRIMA rispetto ai posti disponibili per fila. A terzetti prova, quando disponibile, l'alternativa fra una coppia e due quartetti.</td></tr>
        <tr><td>[[ICON:history:17]] Compaiono vicinanze già utilizzate</td><td>Dopo molte assegnazioni le combinazioni nuove possono esaurirsi. Il Report segnala chiaramente i riutilizzi: significa che, con la configurazione e i vincoli correnti, il programma ha dovuto ammettere alcune vicinanze già impiegate.</td></tr>
        <tr><td>[[ICON:history:17]] L'Annuale produce meno mesi di quanti richiesti</td><td>È stata raggiunta la soglia massima di elaborazione (10 minuti) prima di completare tutti i mesi richiesti. Puoi valutarla e accettarla oppure scartarla senza modificare lo Storico.</td></tr>
        <tr><td>[[ICON:file-down:17]] Esportazioni disabilitate nella scheda Aula</td><td>Salva prima l'assegnazione nello Storico: le esportazioni dell'Excel e del Report vengono abilitate solo dopo il salvataggio.</td></tr>
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

AIUTO_AULA_HTML_TEMPLATE = r"""
<p>[[ICON:armchair:18]] <b>Posti per fila</b> = quanti posti possono essere disposti da sinistra a destra in una fila. È il valore che puoi modificare con i pulsanti − e +.</p>
<p>[[ICON:list-tree:18]] <b>File</b> = quante file di banchi servono dalla cattedra verso il fondo dell'aula. Questo valore è <b>di sola lettura</b> e viene ricalcolato automaticamente in base alla classe, alla geometria scelta e ai posti per fila.</p>
<p>[[ICON:info:18]] Nella modalità a coppie i posti per fila cambiano di 2; nella modalità a terzetti cambiano di 3. Il riepilogo "Posti totali" mostra la capienza effettiva della disposizione; gli eventuali posti non necessari vengono rimossi automaticamente.</p>
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

def mostra_aiuto_configurazione_aula(parent):
    """Spiega visivamente file di banchi e posti per fila."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Come configurare l'aula")
    applica_icona_finestra(dialog, "circle-help")
    adatta_finestra_allo_schermo(
        dialog,
        larghezza_ideale=650,
        altezza_ideale=500,
        larghezza_minima=520,
        altezza_minima=420,
    )

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(18, 16, 18, 16)

    label_titolo = QLabel("Come si contano file e posti", dialog)
    label_titolo.setStyleSheet(
        f"font-size: 15px; font-weight: bold; "
        f"color: {C('istruzioni_titolo')};"
    )
    layout.addWidget(label_titolo)

    schema = (
        "   ┌──────────────────────────────────────────────────┐\n"
        "   │  [banco][banco] [banco][banco]  ← FILA 4         │\n"
        "   │  [banco][banco] [banco][banco]  ← FILA 3         │\n"
        "   │  [banco][banco] [banco][banco]  ← FILA 2         │\n"
        "   │  [banco][banco] [banco][banco]  ← FILA 1         │\n"
        "   │     ↑      ↑       ↑      ↑                      │\n"
        "   │  posto1 posto2   posto3 posto4   (posti per fila)│\n"
        "   ├──────────────────────────────────────────────────┤\n"
        "   │              LAVAGNA / CATTEDRA / LIM            │\n"
        "   └──────────────────────────────────────────────────┘"
    )

    label_schema = QLabel(schema, dialog)
    font_mono = QFontDatabase.systemFont(
        QFontDatabase.SystemFont.FixedFont
    )
    font_mono.setPointSize(10)
    label_schema.setFont(font_mono)
    label_schema.setStyleSheet(f"""
        background-color: {C('istruzioni_card_bg')};
        color: {C('testo_principale')};
        border: 1px solid {C('istruzioni_bordo')};
        border-radius: 6px;
        padding: 12px;
    """)
    layout.addWidget(label_schema)

    spiegazione = QTextBrowser(dialog)
    # Il testo breve mantiene un'altezza contenuta nel dialogo.
    spiegazione.setMinimumHeight(112)
    spiegazione.setMaximumHeight(165)
    spiegazione.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    spiegazione.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    _applica_stile_documento(spiegazione)
    _aggiorna_documento(spiegazione, AIUTO_AULA_HTML_TEMPLATE)
    layout.addWidget(spiegazione)

    btn_chiudi = QPushButton("Chiudi", dialog)
    applica_icona(btn_chiudi, "x", 18)
    btn_chiudi.setMinimumHeight(36)
    _applica_stile_chiudi(btn_chiudi)
    btn_chiudi.clicked.connect(dialog.close)
    layout.addWidget(btn_chiudi)

    _applica_stile_dialogo(dialog)
    dialog.exec()
