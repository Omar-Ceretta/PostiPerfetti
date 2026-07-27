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
        [[ICON:circle-check:17]] <b>«PostiPerfetti» aiuta il docente ad assegnare i posti in classe tenendo conto della geometria dell'aula, delle esigenze dei singoli studenti e delle vicinanze già sperimentate.</b><br><br>
        [[ICON:circle-check:17]] Il lavoro parte da un file <code>.txt</code> con <b>cognome, nome e genere</b>. Nell'Editor puoi aggiungere quattro tipi di indicazioni: <b>posizione</b>, eventuale <b>FISSO</b>, <b>incompatibilità</b> e <b>affinità</b>.<br><br>
        [[ICON:circle-check:17]] Puoi disporre gli studenti <b>a coppie</b> oppure <b>a terzetti</b>. Quando il numero della classe non consente gruppi tutti uguali, il programma costruisce automaticamente il blocco finale necessario: un trio nella modalità a coppie; una coppia, un quartetto o, quando disponibile, due quartetti nella modalità a terzetti.<br><br>
        [[ICON:history:17]] Lo <b>Storico</b> è la memoria delle rotazioni: soltanto le assegnazioni salvate vengono considerate nelle generazioni successive. Le modalità a coppie e a terzetti mantengono memorie separate.<br><br>
        [[ICON:circle-check:17]] <b>Il programma lavora interamente in locale e non invia in rete i dati delle classi.</b><br><br>
        [[ICON:info:17]] I comandi dell'interfaccia sono accompagnati da icone SVG. In questa guida sono richiamati con il loro testo effettivo, valido sia nel tema [[ICON:moon:17]] scuro sia nel tema [[ICON:sun:17]] chiaro.
        </p>

        <hr>
        <h3 class="sezione">[1] - PREPARA E CARICA LA CLASSE</h3>

        <p><b>1 ~ Crea un file .txt di base</b></p>
        <p>Nella tab <b>Editor studenti</b>, clicca su <b>"Apri cartella"</b>. Si aprirà la cartella <code>dati</code>, nella quale puoi creare un nuovo file di testo con il nome della classe, ad esempio <code>Classe1A.txt</code> oppure <code>Classe1A_2026-27.txt</code>.</p>
        <p>Inserisci uno studente per riga nel formato:</p>

        <table cellpadding="6" cellspacing="0" class="tabella tabella-compatta">
        <tr class="intestazione-tabella"><td><b>Esempio di file base</b></td></tr>
        <tr><td><code>Alighieri;Dante;M<br>Austen;Jane;F<br>Boccaccio;Giovanni;M<br>Brontë;Charlotte;F<br>Pasolini;Pier Paolo;M</code></td></tr>
        </table>

        <p>Usa <code>M</code> oppure <code>F</code> per il genere. <b>Non inserire spazi attorno ai punti e virgola</b>; sono invece ammessi gli spazi interni a nomi o cognomi composti. È consigliabile ordinare l'elenco alfabeticamente, ma l'Editor provvede comunque a riordinarlo senza cambiare gli altri dati.</p>

        <p class="riquadro riquadro-info">[[ICON:info:17]] L'Editor accetta anche un file base con due soli campi, <code>Cognome;Nome</code>, ma prima della Preview o del salvataggio richiederà di selezionare M o F per ogni studente. Per il primo utilizzo conviene quindi compilare subito tutti e tre i campi.</p>

        <p><b>2 ~ Seleziona il file</b></p>
        <p>Clicca su <b>"Seleziona classe"</b> e scegli il file appena creato. L'Editor riconosce:</p>
        <p>• il <b>formato BASE</b>, con 2 o 3 campi per riga;<br>
        • il <b>formato COMPLETO</b>, generato da «PostiPerfetti», con 6 campi per riga.</p>
        <p>Il formato completo conserva anche posizione, incompatibilità e affinità. Non serve compilarlo a mano: viene creato e aggiornato da <b>"SALVA e CARICA"</b>.</p>

        <p><b>3 ~ Controlli eseguiti durante il caricamento</b></p>
        <p>L'Editor verifica la struttura del file, gli studenti duplicati, i valori di genere e posizione, i nomi richiamati nei vincoli, i livelli 1-3 e la coerenza delle relazioni nelle due direzioni. Applica automaticamente soltanto le normalizzazioni sicure; se un dato è ambiguo, rifiuta il nuovo file e lascia intatta la classe già aperta.</p>

        <hr>
        <h3 class="sezione">[2] - IMPOSTA GLI STUDENTI E I VINCOLI</h3>

        <p><b>1 ~ Posizione</b></p>
        <p>Per ogni studente scegli una delle seguenti voci:</p>
        <p>• <code>NORMALE</code> = nessuna preferenza di fila;<br>
        • <code><span class="testo-errore"><b>PRIMA</b></span></code> = <span class="testo-errore"><b>obbligo di stare nella prima fila utilizzabile</b></span>;<br>
        • <code>ULTIMA</code> = preferenza per l'ultima fila occupata;<br>
        • <code><span class="testo-errore"><b>FISSO</b></span></code> = <span class="testo-errore"><b>posto stabile nel primo banco a sinistra della prima fila</b></span>.</p>

        <p><b>PRIMA, FISSO e incompatibilità di livello 3 sono vincoli assoluti.</b> ULTIMA è invece una preferenza: viene rispettata finché la combinazione complessiva lo consente.</p>

        <p class="riquadro riquadro-info">
        <b>[[ICON:armchair:18]] LO STUDENTE FISSO</b><br><br>
        La posizione <b>FISSO</b> è pensata per un allievo con BES o per altre esigenze che richiedano una collocazione stabile e vicina alla cattedra.<br><br>
        • Può esserci <b>al massimo un FISSO</b> per classe.<br>
        • Rimane sempre nel primo posto a sinistra della prima fila.<br>
        • L'algoritmo sceglie il vicino diretto valutando vincoli e utilizzi precedenti di quel ruolo.<br>
        • Nella scheda del FISSO, incompatibilità e affinità sono disabilitate. Per orientare la scelta del vicino, imposta il vincolo <b>nella scheda dell'altro studente</b>.<br><br>
        In modalità <b>a coppie</b>, accanto al FISSO viene collocata una coppia; l'eventuale trio dipende dal numero degli altri studenti. In modalità <b>a terzetti</b>, il FISSO appartiene al primo gruppo e occupa l'estremo sinistro.
        </p>

        <p><b>2 ~ Incompatibilità</b></p>
        <p>Clicca su <b>"Aggiungi INCOMPATIBILITÀ"</b>, scegli il compagno e poi seleziona l'intensità:</p>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Livello</b></td><td><b>Significato</b></td><td><b>Effetto</b></td></tr>
        <tr><td class="cella-centro"><b>1</b></td><td>Leggera</td><td>La vicinanza viene evitata se possibile</td></tr>
        <tr><td class="cella-centro"><b>2</b></td><td>Media</td><td>La vicinanza riceve una penalità più forte</td></tr>
        <tr><td class="cella-centro testo-errore"><b>3</b></td><td class="testo-errore"><b>ASSOLUTA</b></td><td class="testo-errore"><b>I due studenti non saranno mai adiacenti</b></td></tr>
        </table>

        <p><b>3 ~ Affinità</b></p>
        <p>Clicca su <b>"Aggiungi AFFINITÀ"</b>, scegli il compagno e poi seleziona l'intensità:</p>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Livello</b></td><td><b>Significato</b></td><td><b>Effetto</b></td></tr>
        <tr><td class="cella-centro"><b>1</b></td><td>Leggera</td><td>Piccolo incentivo alla vicinanza</td></tr>
        <tr><td class="cella-centro"><b>2</b></td><td>Buona</td><td>Incentivo significativo</td></tr>
        <tr><td class="cella-centro"><b>3</b></td><td><b>Forte</b></td><td><b>Forte preferenza, ma non obbligo assoluto</b></td></tr>
        </table>

        <p>Il promemoria <b>"Seleziona il livello"</b> compare una sola volta per le incompatibilità e una sola volta per le affinità nell'intera sessione. Il salvataggio viene comunque bloccato se resta una riga priva del compagno o del livello.</p>

        <p><b>4 ~ Bidirezionalità automatica</b></p>
        <p>Quando aggiungi, modifichi o rimuovi una relazione, l'Editor aggiorna automaticamente anche la scheda dell'altro studente. Non devi inserire due volte lo stesso vincolo.</p>

        <p class="riquadro riquadro-info">[[ICON:info:17]] <b>Nei terzetti e nei quartetti contano soltanto le adiacenze consecutive.</b> In un gruppo <code>A — B — C</code>, A è vicino a B e B è vicino a C; A e C non sono considerati adiacenti.</p>

        <p><b>5 ~ Strumenti di controllo dell'Editor</b></p>
        <p>• <b>"Espandi schede"</b>: mostra o comprime tutte le schede.<br>
        • <b>"Dettaglio vincoli"</b>: elenca tutte le relazioni, raggruppate per categoria.<br>
        • <b>"Preview file classe (.txt)"</b>: mostra il file completo che verrà salvato.<br>
        • <b>"SALVA e CARICA"</b>: aggiorna il file e abilita l'assegnazione.<br>
        • <b>"CHIUDI FILE"</b>: chiude la classe corrente, proteggendo le modifiche non salvate.</p>

        <p class="riquadro riquadro-info">[[ICON:save:17]] <b>Finché non usi "SALVA e CARICA", le modifiche dell'Editor non entrano nell'assegnazione.</b> Il pannello di sinistra rimane nascosto oppure segnala che il file deve essere aggiornato.</p>

        <hr>
        <h3 class="sezione">[3] - CONFIGURA L'AULA E LA ROTAZIONE</h3>

        <p>Dopo <b>"SALVA e CARICA"</b> compaiono nel pannello di sinistra i seguenti box.</p>

        <p><b>1 ~ STATO CLASSE</b></p>
        <p>Mostra nome del file, numero degli studenti e stato del caricamento. È un riepilogo di sola lettura.</p>

        <p><b>2 ~ CONFIGURAZIONE AULA</b></p>
        <p>Scegli la geometria:</p>
        <p>• <b>A coppie</b>: gruppi ordinari da 2, con eventuale trio;<br>
        • <b>A terzetti</b>: gruppi da 3 disposti in fila, con eventuale blocco finale.</p>
        <p>Il comando regolabile è <b>"Posti per fila"</b>:</p>
        <p>• a coppie: da 4 a 10, con variazioni di 2;<br>
        • a terzetti: 6 oppure 9, con variazioni di 3.</p>
        <p>Il valore <b>"File"</b> è di sola lettura: viene ricalcolato automaticamente in base alla classe, alla geometria e ai posti per fila. Anche <b>"Posti totali"</b> si aggiorna da solo e segnala posti insufficienti o banchi vuoti che verranno rimossi.</p>
        <p>Il pulsante [[ICON:circle-help:17]] accanto a "Posti totali" apre uno schema per distinguere correttamente file e posti per fila.</p>

        <p><b>3 ~ GESTIONE NUMERO DISPARI / GESTIONE DEL RESTO</b></p>
        <p>Il box compare soltanto quando serve.</p>
        <p><b>A coppie:</b> se i rimanenti sono dispari, viene formato un trio. Puoi scegliere, fra le posizioni ammesse, <b>Davanti</b>, <b>In mezzo</b> o <b>In fondo</b>.</p>
        <p><b>A terzetti:</b></p>
        <p>• resto 0: tutti gli studenti entrano nei terzetti;<br>
        • resto 1: viene formato un quartetto;<br>
        • resto 2: viene formata una coppia finale;<br>
        • quando l'opzione è disponibile, la coppia finale può essere sostituita da <b>2 quartetti</b>.</p>
        <p>Il programma mostra soltanto le posizioni compatibili con la geometria reale. Se esiste una sola collocazione valida, la imposta automaticamente e la spiega nel box.</p>

        <p><b>4 ~ GENERE MISTO</b></p>
        <p>La casella <b>"Preferisci coppie miste (M+F)"</b> assegna un forte bonus alle vicinanze M+F, ma non costituisce un divieto assoluto. Vale anche nei terzetti, sulle adiacenze consecutive interne ai gruppi.</p>

        <p><b>5 ~ MODALITÀ DI ASSEGNAZIONE</b></p>
        <p>Il box mostra un riepilogo dello Storico e permette di scegliere:</p>
        <p>• <b>Mensile (un mese)</b>;<br>
        • <b>Annuale (più mesi)</b>, da 1 a 10 mesi in coda allo Storico.</p>

        <p class="riquadro riquadro-info">
        [[ICON:history:18]] <b>COME FUNZIONA LA ROTAZIONE</b><br><br>
        Lo Storico viene consultato automaticamente. Nei tentativi più restrittivi le vicinanze già utilizzate vengono escluse; se le combinazioni nuove non bastano più, possono essere riutilizzate con una forte penalità e vengono segnalate nel Report.<br><br>
        Le rotazioni sono <b>separate per modalità</b>: le coppie influenzano le future assegnazioni a coppie; le adiacenze dei terzetti influenzano le future assegnazioni a terzetti. Un precedente nell'altra modalità può comparire nel Report come informazione, ma non penalizza la disposizione corrente.
        </p>

        <hr>
        <h3 class="sezione">[4] - GENERA: MENSILE O ANNUALE</h3>

        <p><b>1 ~ Controlli prima dell'avvio</b></p>
        <p>Quando premi <b>"ASSEGNA I POSTI!"</b>, il programma controlla che:</p>
        <p>• la classe sia stata salvata e caricata;<br>
        • non restino vincoli incompleti;<br>
        • non ci siano modifiche recenti non salvate nell'Editor;<br>
        • i posti siano sufficienti;<br>
        • non sia stato indicato più di un FISSO;<br>
        • le richieste PRIMA possano entrare nella prima fila disponibile.</p>

        <p><b>2 ~ Tentativi progressivi</b></p>
        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Tentativo</b></td><td><b>Strategia</b></td></tr>
        <tr><td class="cella-centro"><b>1</b></td><td>Tutti i vincoli attivi; niente vicinanze già utilizzate</td></tr>
        <tr><td class="cella-centro"><b>2</b></td><td>Riduce il peso di incompatibilità e affinità di livello 1</td></tr>
        <tr><td class="cella-centro"><b>3</b></td><td>Riduce anche il peso dei livelli 2 e della preferenza ULTIMA</td></tr>
        <tr><td class="cella-centro"><b>4</b></td><td>Mantiene i vincoli assoluti e ammette i riutilizzi con forte penalità</td></tr>
        </table>
        <p><b>Non vengono mai violati:</b> incompatibilità di livello 3, posizione PRIMA e posizione FISSO.</p>

        <p><b>3 ~ Modalità MENSILE</b></p>
        <p>Al termine si apre direttamente la tab <b>Aula</b> e compare un popup con le statistiche generali. La tab <b>Report</b> contiene il dettaglio della disposizione.</p>
        <p>Il pulsante <b>"Salva assegnazione"</b> diventa disponibile. Dopo il salvataggio si abilitano <b>"Esporta Excel"</b> e <b>"Esporta Report"</b>. Soltanto la disposizione salvata entra nelle rotazioni future.</p>

        <p><b>4 ~ Modalità ANNUALE</b></p>
        <p>Il programma prepara più mesi consecutivi e confronta diverse stagioni possibili. Puoi interrompere l'elaborazione con <b>"Annulla"</b>; l'arresto avviene in sicurezza al termine del mese in corso.</p>
        <p>Nell'anteprima, per ogni mese puoi leggere le statistiche, aprire <b>"Vedi disposizione"</b> e consultare il <b>"Report"</b>. Alla fine scegli:</p>
        <p>• <b>"Accetta e salva nello Storico"</b>: salva tutti i mesi in ordine;<br>
        • <b>"Scarta"</b>: non salva nulla e lascia lo Storico invariato.</p>
        <p>Se viene raggiunto il tempo massimo prima di completare tutti i mesi richiesti, l'anteprima segnala chiaramente che l'annata è parziale. Puoi comunque valutarla e decidere se conservarla.</p>

        <hr>
        <h3 class="sezione">[5] - AULA, REPORT, STORICO E STATISTICHE</h3>

        <p><b>[[ICON:school:18]] Tab Aula</b></p>
        <p>Mostra la piantina della classe. Il fondo dell'aula è in alto; LIM, cattedra e lavagna sono in basso.</p>
        <p>• <b>"Salva assegnazione"</b>: registra la disposizione nello Storico.<br>
        • <b>"Esporta Excel"</b>: crea un file <code>.xlsx</code> modificabile e stampabile.<br>
        • <b>"Esporta Report"</b>: salva in <code>.txt</code> il report completo.</p>
        <p>Le esportazioni vengono abilitate dopo il salvataggio nello Storico.</p>

        <p><b>[[ICON:file-text:18]] Tab Report</b></p>
        <p>Mostra statistiche generali, composizione dei gruppi, giudizio sulle singole vicinanze, affinità e incompatibilità rilevate, rispetto delle posizioni, eventuali riutilizzi e rappresentazione testuale dell'aula. Le righe relative ai riutilizzi vengono evidenziate in ocra.</p>

        <p><b>[[ICON:history:18]] Tab Storico</b></p>
        <p>La tabella mostra data, nome, composizione e azioni. Puoi:</p>
        <p>• rinominare una voce facendo doppio clic nella cella <b>Nome</b>;<br>
        • usare <b>"Dettagli"</b> per leggere ed esportare il Report;<br>
        • usare <b>"Layout"</b> per rivedere la piantina ed esportarla in Excel o in <code>.txt</code>;<br>
        • usare <b>"Elimina"</b> per rimuovere definitivamente l'assegnazione.</p>
        <p>Dopo un'eliminazione il programma ricostruisce le memorie di rotazione utilizzando soltanto le assegnazioni rimaste.</p>

        <p><b>[[ICON:chart-column:18]] Tab Statistiche</b></p>
        <p>Se lo Storico contiene più classi, seleziona prima quella da analizzare. La pagina comprende riepilogo generale, coppie più frequenti, statistiche sui trio, dettaglio per studente, presenze in prima fila e coppie mai formate.</p>
        <p>Il pulsante <b>"Esporta le Statistiche (.txt)"</b> salva l'intero riepilogo.</p>

        <hr>
        <h3 class="sezione">[6] - FLUSSO DI LAVORO CONSIGLIATO</h3>

        <p><b>[[ICON:circle-check:18]] Prima assegnazione dell'anno</b></p>
        <p>1. Crea e seleziona il file base.<br>
        2. Imposta soltanto i vincoli che hanno un significato didattico reale.<br>
        3. Controlla "Dettaglio vincoli" e "Preview file classe (.txt)".<br>
        4. Usa "SALVA e CARICA".<br>
        5. Scegli coppie o terzetti, posti per fila e gestione del blocco finale.<br>
        6. Scegli Mensile oppure Annuale.<br>
        7. Genera, controlla e salva nello Storico soltanto le disposizioni che userai davvero.<br>
        8. Esporta in Excel per la stampa oppure conserva il Report in formato testuale.</p>

        <p><b>[[ICON:history:18]] Assegnazioni successive</b></p>
        <p>• Mantieni nello Storico le assegnazioni realmente utilizzate: sono la memoria delle rotazioni.<br>
        • Elimina le disposizioni salvate ma poi non applicate in classe, prima di generarne di nuove.<br>
        • Se alterni coppie e terzetti, ricorda che le due memorie sono indipendenti.</p>

        <p class="riquadro riquadro-info">
        [[ICON:user-pen:18]] <b>Modifiche durante l'anno</b><br><br>
        Per cambiare posizione o vincoli, seleziona nuovamente il file nell'Editor, modifica e usa "SALVA e CARICA".<br><br>
        Per aggiungere o rimuovere uno studente, modifica manualmente il file <code>.txt</code> e selezionalo di nuovo. Se il file è stato rinominato, «PostiPerfetti» può riconoscere la classe dai nomi degli studenti e proporre il ricollegamento allo Storico esistente.
        </p>

        <hr>
        <h3 class="sezione">[[ICON:triangle-alert:20]] RISOLUZIONE DEI PROBLEMI</h3>

        <table cellpadding="6" cellspacing="0" class="tabella">
        <tr class="intestazione-tabella"><td><b>Problema</b></td><td><b>Che cosa fare</b></td></tr>
        <tr><td>[[ICON:file-x:17]] Errore durante il caricamento del .txt</td><td>Un file base deve avere 2 o 3 campi per riga; un file completo deve averne esattamente 6. Leggi il dettaglio del popup, correggi il file e selezionalo di nuovo.</td></tr>
        <tr><td>[[ICON:users:17]] Studenti con identico cognome e nome</td><td>Aggiungi un secondo nome o una sigla distintiva: il programma usa "Cognome Nome" come identificatore.</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Genere non impostato</td><td>Seleziona M o F per tutti gli studenti prima della Preview o di "SALVA e CARICA".</td></tr>
        <tr><td>[[ICON:triangle-alert:17]] Vincolo incompleto</td><td>Completa sia il compagno sia il livello, oppure usa "Rimuovi". Il salvataggio e l'assegnazione restano bloccati.</td></tr>
        <tr><td>[[ICON:circle-x:17]] Vincoli contraddittori o livelli diversi</td><td>Correggi le schede indicate: il programma non può decidere quale delle due versioni sia quella giusta.</td></tr>
        <tr><td>[[ICON:armchair:17]] Più di uno studente FISSO</td><td>Lascia FISSO a un solo studente e modifica la posizione degli altri.</td></tr>
        <tr><td>[[ICON:layout-grid:17]] Posti insufficienti</td><td>Aumenta "Posti per fila". Il numero di File viene ricalcolato automaticamente.</td></tr>
        <tr><td>[[ICON:circle-stop:17]] L'assegnazione fallisce</td><td>Controlla incompatibilità di livello 3, richieste PRIMA e geometria. A terzetti prova, quando disponibile, l'alternativa "1 coppia / 2 quartetti".</td></tr>
        <tr><td>[[ICON:history:17]] Compaiono vicinanze già utilizzate</td><td>Dopo molte assegnazioni le combinazioni nuove possono esaurirsi. Il Report indica i riutilizzi e l'algoritmo cerca di distribuirli nel modo più equilibrato possibile.</td></tr>
        <tr><td>[[ICON:history:17]] L'Annuale produce meno mesi del richiesto</td><td>È stata raggiunta la soglia massima di elaborazione. Valuta l'annata parziale nell'anteprima oppure scartala senza modificare lo Storico.</td></tr>
        <tr><td>[[ICON:file-down:17]] Esportazioni disabilitate in Aula</td><td>Salva prima l'assegnazione nello Storico: Excel e Report vengono abilitati dopo il salvataggio.</td></tr>
        <tr><td>[[ICON:armchair:17]] Vincoli disabilitati nella scheda del FISSO</td><td>È previsto: imposta la relazione nella scheda dell'altro studente.</td></tr>
        </table>

        <hr>
        <p class="pie-pagina">
        «PostiPerfetti» — Sviluppato in Python dal prof. Omar Ceretta<br>I.C. di Tombolo e Galliera Veneta (PD)<br>
        Licenza: GNU GPLv3</p>

"""

CREDITI_HTML_TEMPLATE = r"""
<div class="crediti-titolo"><h2>«PostiPerfetti»</h2></div>
<hr>
<p><b>Descrizione:</b><br>
Programma per l'assegnazione automatica dei posti in classe, con gestione di
vincoli, affinità, incompatibilità, rotazione allievi e storico assegnazioni.</p>
<p><b>Autore:</b><br>
Prof. Omar Ceretta<br>
I.C. di Tombolo e Galliera Veneta (PD)</p>
<p><b>Tecnologie:</b><br>
Python 3 · PySide6 (Qt) · XlsxWriter</p>
<hr>
<p><b>Licenza — GNU General Public License v3.0 (GPLv3)</b></p>
<p>[[ICON:circle-check:16]] Questo software è libero: puoi usarlo, copiarlo,
studiarlo e redistribuirlo liberamente.</p>
<p>[[ICON:circle-check:16]] Se lo modifichi e redistribuisci, sei tenuto a
mantenere l'attribuzione al creatore originale e a rendere pubblico il codice
sorgente delle tue modifiche con la stessa licenza GPLv3.</p>
<p>[[ICON:info:16]] Il software è distribuito <i>«così com'è»</i>, senza alcuna
garanzia espressa o implicita.</p>
<p>Pagina GitHub con il codice sorgente:<br>
<a href="https://github.com/Omar-Ceretta/PostiPerfetti">github.com/Omar-Ceretta/PostiPerfetti</a></p>

"""

AIUTO_AULA_HTML_TEMPLATE = r"""
<p>[[ICON:armchair:18]] <b>Posti per fila</b> = quanti posti possono essere disposti da sinistra a destra in una fila. È il valore che puoi modificare con i pulsanti − e +.</p>
<p>[[ICON:list-tree:18]] <b>File</b> = quante file di banchi servono dalla cattedra verso il fondo dell'aula. Questo valore è <b>di sola lettura</b> e viene ricalcolato automaticamente in base alla classe, alla geometria scelta e ai posti per fila.</p>
<p>[[ICON:info:18]] Nella modalità a coppie i posti per fila cambiano di 2; nella modalità a terzetti cambiano di 3. Il riepilogo "Posti totali" segnala subito eventuali insufficienze o banchi vuoti che verranno rimossi.</p>
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

def mostra_crediti(parent, base_path):
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

    percorso_icona = os.path.join(
        base_path, "dati", "icone", "postiperfetti_icon.png"
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
