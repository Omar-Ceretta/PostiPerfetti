    # =================================================================
"""
    «PostiPerfetti» v. 2.0 — Programma per l'assegnazione automatica
    dei posti degli allievi in una classe scolastica,
    con gestione di vincoli, affinità, incompatibilità,
    rotazione allievi e storico assegnazioni.

    Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD)
    Licenza: GNU GPLv3

    ▣ Questo software è libero: puoi usarlo, copiarlo, studiarlo
    e redistribuirlo liberamente.
    ▣ Se lo modifichi e redistribuisci, sei tenuto a mantenere
    l'attribuzione al creatore originale e a rendere pubblico
    il codice sorgente delle tue modifiche con la stessa licenza GPLv3.
    ▣ Questo programma è distribuito «così com'è», senza alcuna
    garanzia espressa o implicita.
"""
    # =================================================================
"""
    Finestre informative di «PostiPerfetti».

    Contiene le tre finestre di aiuto/informazioni dell'applicazione:
    • mostra_istruzioni()                  → Guida d'uso completa (HTML)
    • mostra_crediti()                     → Crediti, versione, licenza GPLv3
    • mostra_aiuto_configurazione_aula()   → Schema visivo dell'aula

    Ogni funzione riceve come primo parametro il widget "parent" (la finestra
    principale), usato come genitore Qt per i dialog.
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QLabel,
    QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

# Importa la funzione C() per leggere i colori del tema attivo
from moduli.tema import C


# =============================================================================
# ISTRUZIONI D'USO — Guida completa in HTML
# =============================================================================

def mostra_istruzioni(parent):
    """
    Mostra le istruzioni d'uso in una finestra NON-MODALE.
    La finestra resta aperta mentre l'utente lavora sull'Editor
    o su qualsiasi altra parte del programma.
    Se la finestra è già aperta, la porta semplicemente in primo piano.

    Args:
        parent: Widget genitore (FinestraPostiPerfetti) — serve sia come
                parent Qt per il dialog, sia per memorizzare il riferimento
                al dialog aperto (attributo _dialog_istruzioni).
    """

    # === CONTROLLO DUPLICATI ===
    # Se il dialog esiste già ed è aperto, lo porta in primo piano
    # invece di crearne uno nuovo (evita finestre duplicate).
    if hasattr(parent, '_dialog_istruzioni') and parent._dialog_istruzioni is not None:
        if parent._dialog_istruzioni.isVisible():
            # La finestra è già aperta → portala in primo piano
            parent._dialog_istruzioni.raise_()
            parent._dialog_istruzioni.activateWindow()
            return

    # === CREAZIONE DEL DIALOG ===
    # Salvato come attributo di istanza sul parent (parent._dialog_istruzioni)
    # per evitare che Python lo distrugga quando esce dallo scope.
    parent._dialog_istruzioni = QDialog(parent)
    dialog = parent._dialog_istruzioni  # alias breve per leggibilità
    dialog.setWindowTitle("📖 ISTRUZIONI 📖")
    dialog.setMinimumSize(950, 750)
    dialog.resize(950, 750)

    layout = QVBoxLayout(dialog)

    # Contenuto istruzioni in HTML per formattazione ricca
    text_edit = QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setFont(QFont("Segoe UI", 11))

    # ---------------------------------------------------------------
    # HTML completo delle istruzioni — suddiviso in 5 sezioni:
    # [1] Guida al primo utilizzo
    # [2] Caricamento e configurazione
    # [3] Avvio dell'assegnazione
    # [4] Visualizzazione dei risultati
    # [5] Flusso di lavoro consigliato
    # + tabella risoluzione problemi
    # ---------------------------------------------------------------
    istruzioni_html = """
        <h2 style="color: #4CAF50; text-align: center;">📖 «PostiPerfetti» 📖</h2>
        <hr>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>✅ <b>«PostiPerfetti» è un programma gratuito e <i>open source</i> che utilizza uno speciale algoritmo per aiutare il docente Coordinatore (o qualsiasi insegnante ne abbia la necessità) ad assegnare agli studenti il proprio posto in classe.</b><br><br>
        ✅ Per funzionare, esso <b>richiede la creazione di un file .txt con i dati essenziali degli alunni (<i>cognome</i>, <i>nome</i>, <i>genere</i>)</b>. Tramite alcune funzioni intuitive sarà poi possibile aggiungere una serie di informazioni e vincoli ('affinità' e 'incompatibilità' fra allievi, loro 'posizione' rispetto alla cattedra, eventuale preferenza per 'coppie miste M+F') per ottenere <b>UNA DISTRIBUZIONE DEGLI ALLIEVI QUANTO PIÙ IN LINEA CON I DESIDERATA DELL'INSEGNANTE</b>.<br><br>
        ✅ Gli allievi verranno distribuiti "a due a due" in modo automatizzato, in un numero di coppie e di file di banchi personalizzabile secondo le esigenze. <b>Le assegnazioni richiedono in genere da qualche secondo a due/tre minuti</b> (a seconda del numero e della rigidità dei "vincoli" che si sono predisposti).<br><br>
        ✅ <b>«PostiPerfetti» non ha alcun accesso alla rete, pertanto non invia nessun dato a terzi</b>. Lavorando esclusivamente in locale, ogni informazione è mantenuta al sicuro all'interno del pc del docente.<br><br>
        💡 A seconda delle preferenze, per usare l'interfaccia puoi selezionare un '🌚 TEMA SCURO' o un '☀️ TEMA CHIARO'.<br></p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">[1] - GUIDA AL PRIMO UTILIZZO</h3>

        <p><b>1 ~ Prepara un file .txt di base</b></p>
        <p>Clicca sul pulsante "📂 Apri cartella". Si aprirà la cartella che contiene le classi. Con un qualsiasi editor di testo, <b>crea un nuovo file .txt con il nome della tua classe</b> (ad es. <code>"Classe1A.txt"</code>, oppure <code>"Classe1A_2026-27.txt"</code>).</p>
        <p><b>Dentro scrivi solo <code>"Cognome;Nome;Genere"</code></b> (= M/F) <b>di ogni studente, uno per riga, in ordine alfabetico</b>. Separa i tre elementi con due punti e virgola (";") e non usare spazi, come in questo esempio:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0; width: 50%;">
        <tr style="background-color: #3A5240; color: #ffffff;"><td><b>Esempio di file base</b></td></tr>
        <tr><td><code>Alighieri;Dante;M<br>Austen;Jane;F<br>Boccaccio;Giovanni;M<br>Brontë;Charlotte;F<br>Calvino;Italo;M</code><br><i>eccetera..</i></td></tr>
        </table><br>

        <p><b>2 ~ Imposta la POSIZIONE</b></p>
        <p>Per ogni studente, <b>usa il menu a tendina per selezionarne la <i>posizione</i></b>:</p>
        <p>• <code>NORMALE</code> = nessuna preferenza,<br>
        • <code><span style="color: #EF5350;"><b>PRIMA</b></span></code> = <span style="color: #EF5350;"><b>OBBLIGO di stare in prima fila</b></span> (utile ad es. per gli allievi più propensi a distrarsi, con difficoltà di vista o altri bisogni particolari),<br>
        • <code>ULTIMA</code> = preferenza per l'ultima fila (utile ad es. per allievi di alta statura o per altre esigenze),<br>
        • <code><span style="color: #E53935;"><b>🔴 FISSO</b></span></code> = <span style="color: #E53935;"><b>posizione fissa in prima fila, nel primo banco a sinistra</b></span>.</p>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>
        <b>🔴 LA POSIZIONE "FISSO" (studenti con Bisogni Educativi Speciali)</b><br><br>
        La posizione <b>FISSO</b> è pensata per allievi con <b>BES</b> o altre esigenze particolari che richiedono una collocazione stabile, vicina alla cattedra e costante nel tempo.<br><br>
        <b>Come funziona:</b><br>
        • Lo studente FISSO viene <b>sempre assegnato al primo banco a sinistra della prima fila</b>, vicino alla cattedra. La sua posizione non cambia da una rotazione all'altra.<br>
        • <b>L'algoritmo sceglie automaticamente il compagno migliore</b> da affiancargli, selezionando quello con la massima compatibilità. Il compagno affiancato avrà a sua volta un altro compagno al banco adiacente: in questo modo, se l'allievo BES dovesse temporaneamente uscire dall'aula, il compagno non resta isolato. Ad ogni nuova rotazione, <b>il compagno accanto al FISSO cambia</b>, garantendo equità e varietà nei turni.<br><br>
        <b>• NOTA 1: è possibile designare al massimo 1 studente FISSO</b> per classe.<br><br>
        <b>• NOTA 2: Senza studente FISSO, la gestione del 'trio' (banco da 3) si attiva quando gli studenti sono in numero dispari</b> (es. 17, 19, 21...). <b>Con uno studente FISSO, la logica si inverte</b>: il FISSO occupa 1 posto da solo e i rimanenti N−1 vengono distribuiti in coppie. Il 'trio' si forma quindi quando la classe è in <b>numero pari</b> (16, 18, 20...).<br><br>
        <b>• NOTA 3:</b> quando uno studente è impostato come FISSO, le sezioni "Incompatibilità" e "Affinità" nella sua scheda vengono <b>disabilitate</b>. Per influenzare chi gli siederà accanto, è sufficiente impostare i vincoli <b>sugli altri studenti</b> (ad es. impostando una "<i>Affinità di livello 3</i>" nelle schede dei compagni desiderati).<br></p><br>

        <p><b>3 ~ Aggiungi le INCOMPATIBILITÀ</b></p>
        <b>Se è il caso di tenere SEPARATI alcuni allievi</b> (che in banco assieme rischierebbero di distrarsi o disturbare), <b>è consigliabile stabilire tra loro una "incompatibilità"</b>.</p>
        <p>Clicca su <b>"➕ Aggiungi INCOMPATIBILITÀ"</b> nella scheda dello studente. Apparirà una riga con:<br>
        • Un <b>menu a tendina</b> con tutti gli altri studenti della classe ⇾ seleziona il compagno.<br>
        • Un <b>menu livello</b> ⇾ scegli uno fra questi 3 gradi di incompatibilità:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #3A5240; color: #ffffff;">
            <td><b>Livello</b></td><td><b>Significato</b></td><td><b>Quando usarlo</b></td>
        </tr>
        <tr><td style="text-align: center;"><b>1</b></td><td>Incompatibilità leggera</td>
            <td>Meglio se non vicini, ma accettabile se necessario</td></tr>
        <tr><td style="text-align: center;"><b>2</b></td><td>Incompatibilità media</td>
            <td>Evitare se possibile, penalità significativa</td></tr>
        <tr><td style="text-align: center; color: #EF5350;"><b>3</b></td>
            <td><span style="color: #EF5350;"><b>Incompatibilità ASSOLUTA</b></span></td>
            <td><span style="color: #EF5350;"><b>MAI vicini — vincolo inviolabile</b></span></td></tr>
        </table>
        <p>💡 NOTA: <b>Puoi aggiungere più incompatibilità per lo stesso studente</b>, cliccando di nuovo il bottone ➕.</p><br>

        <p><b>4 ~ Aggiungi le AFFINITÀ</b></p>
        <p><b>Se è il caso di tenere UNITI certi allievi</b> (per "bilanciarne" i livelli e promuovere la collaborazione, per facilitare l'integrazione o altre ragioni), <b>è utile stabilire tra loro una "affinità"</b>.</p>
        <p>Segui la stessa procedura delle incompatibilità, usando <b>"➕ Aggiungi AFFINITÀ"</b>.<br>
        I 3 livelli indicano quanto è desiderabile che i due studenti stiano vicini:</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #3A5240; color: #ffffff;">
            <td><b>Livello</b></td><td><b>Significato</b></td><td><b>Quando usarlo</b></td>
        </tr>
        <tr><td style="text-align: center;"><b>1</b></td><td>Affinità leggera</td>
            <td>Per dare un piccolo bonus alla vicinanza</td></tr>
        <tr><td style="text-align: center;"><b>2</b></td><td>Affinità buona</td>
            <td>Per dare un bonus più significativo alla vicinanza</td></tr>
        <tr><td style="text-align: center; color: #4CAF50;"><b>3</b></td>
            <td><span style="color: #4CAF50;"><b>Affinità forte</b></span></td>
            <td><span style="color: #4CAF50;"><b>Per far sì che l'algoritmo cerchi di metterli vicini</b></span></td></tr>
        </table>
        <p>💡 NOTA: <b>Puoi aggiungere più affinità per lo stesso studente</b>, cliccando di nuovo il bottone ➕.</p><br>

        <p><b>5 ~ BIDIREZIONALITÀ automatica</b></p>
        <p><span style="color: #4CAF50; font-weight: bold;">Non devi preoccuparti di ripetere i vincoli.</span> Se imposti "D'Annunzio Gabriele incompatibile con Deledda Grazia (livello 3)", l'Editor aggiungerà <b>automaticamente</b> "Deledda Grazia incompatibile con D'Annunzio Gabriele (livello 3)". Lo stesso vale per le affinità, per le modifiche di livello e per le rimozioni.</p><br>

        <p><b>6 ~ Rimuovere un vincolo</b></p>
        <p>Clicca il bottone <b>"Rimuovi"</b> accanto al vincolo da eliminare. Il vincolo speculare sull'altro studente verrà rimosso automaticamente.</p><br>

        <p><b>7 ~ Verifica e salva</b></p>
        <p>• Clicca su <b>"👁️ Preview file classe (.txt)"</b> per vedere un'anteprima del file .txt che verrà creato.<br>
        • Clicca su <b>"💾 SALVA e CARICA classe"</b> per salvare il file .txt della classe.<br>
        • La classe verrà caricata nel programma, <b>pronta per avviare le assegnazioni</b>.</p><br>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>
        <b>⚙️ Modifica dei vincoli in corso d'anno</b><br><br>
        Se in futuro vorrai rimuovere, aggiungere o cambiare dei vincoli, basterà ricaricare nell'Editor il file .txt della classe con il pulsante <b>"📝 Seleziona classe"</b>. Le schede verranno popolate automaticamente con tutti i dati esistenti di ciascun allievo, pronte per essere modificate.<br>
        Se invece bisognasse rimuovere o aggiungere un allievo (per trasferimento, cambio sezione, bocciatura...), dovrai aprire manualmente il file .txt della classe e cancellarne la riga, oppure aggiungerlo (con <code>Cognome;Nome;Genere</code>) nella posizione alfabeticamente corretta.<br></p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">[2] - CARICAMENTO E CONFIGURAZIONE</h3>

        <p>🔷 <b>Passo 1 — Carica il file:</b></p>
        <p>• Una volta preparato il tuo file con tutti i vincoli, sei già pronto al "Passo 2".<br>Se invece vuoi effettuare le assegnazioni per un'altra classe, clicca sul pulsante <b>"📝 Seleziona classe"</b> presente nella tab "✏️ Editor studenti". Il programma mostrerà il numero di studenti caricati e <b>configurerà automaticamente il numero di file di banchi</b> necessarie.</p><br>

        <p>🔷 <b>Passo 2 — Configura le opzioni:</b></p>
        <p>I box <b>"Configurazione aula"</b>, <b>"Opzioni vincoli"</b> e <b>"Rotazione automatica"</b> diventano attivi solo dopo aver caricato una classe con "💾 SALVA e CARICA classe".</p>
        <p>• <b>"Configurazione aula"</b>: il programma calcola automaticamente il numero minimo di file necessarie per la tua classe. Puoi comunque modificarlo manualmente con i pulsanti + e −. Verrai avvertito in caso di 'posti insufficienti'.<br>
        • <b>"Gestione numero dispari"</b>: se è necessario un banco da 3 (trio), potrai <b>scegliere in quale fila posizionarlo</b>: 'prima', 'ultima' o 'centrale'. <b>Nota:</b> con uno studente FISSO, il trio si attiva quando la classe è in numero pari. Se decidi di disporlo in posizione 'prima', troverai in prima fila 4 allievi raggruppati (= l'allievo FISSO + il 'trio'); se invece lo disporrai in posizione 'centrale' o 'ultima', troverai in prima fila 3 allievi raggruppati (= l'allievo FISSO + una coppia) e il trio in posizione 'centrale' o 'ultima'.<br>
        • <b>"Preferisci coppie miste (M+F)"</b>: se attivi questo flag, <b>l'algoritmo preferirà coppie maschio-femmina</b> (non è un obbligo assoluto, ma un bonus forte).<br>
        • <b>"Rotazione automatica"</b>: l'algoritmo consulta <b>sempre</b> lo Storico delle assegnazioni salvate per evitare di ripetere coppie già formate. Alla prima assegnazione dell'anno, lo Storico è vuoto e quindi non ha effetto; dalle assegnazioni successive in poi, le coppie precedenti vengono automaticamente evitate.</p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">[3] - AVVIO DELL'ASSEGNAZIONE</h3>

        <p>Clicca su <b>"🚀 Assegna i posti!"</b>.</p>
        <p><b>L'algoritmo lavorerà in 4 tentativi progressivi, rispettando SEMPRE i vincoli "ASSOLUTI" (= 'posizione PRIMA', 'posizione FISSO' e 'incompatibilità 3') e facendo il possibile per NON RIPETERE COPPIE GIÀ FORMATE.</b></p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #3A5240; color: #ffffff;">
            <td><b>Tentativo</b></td><td><b>Strategia</b></td>
        </tr>
        <tr><td>1</td><td>Tutti i vincoli attivi, nessuna coppia ripetuta</td></tr>
        <tr><td>2</td><td>Vincoli deboli (livello 1) rilassati</td></tr>
        <tr><td>3</td><td>Vincoli medi (livello 2) rilassati</td></tr>
        <tr><td>4</td><td>Solo vincoli ASSOLUTI, coppie ripetute ammesse con penalità progressiva</td></tr>
        </table>

        <p>• 💬 Al termine dell'elaborazione apparirà un <b>POPUP di riepilogo</b> con le statistiche degli abbinamenti creati.</p>
        <p>• ❗ Eventuali <b>coppie riutilizzate</b> saranno evidenziate in <span style="color: #CC8800; font-weight: bold;">colore ocra</span>.</p><br>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>
        <b>⚙️ File di configurazione</b><br><br>
        Tutte le modifiche ai file e ogni assegnazione salvata vengono memorizzate all'interno del file "postiperfetti_configurazione.json". Questo file NON deve essere aperto o modificato direttamente. Solo nel caso in cui si desideri cancellare l'intero "Storico" delle assegnazioni può essere eliminato, e verrà ricreato <i>da zero</i> dal programma in occasione della prima nuova assegnazione.<br></p>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #E53935;"><br>
        💡 <b>Se rinomini un file .txt</b>, il programma lo riconoscerà automaticamente tramite i nomi degli studenti.<br></p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">[4] - VISUALIZZAZIONE DEI RISULTATI</h3>

        <p>🍀 La <b>Tab "🏫 AULA":</b> mostra la disposizione grafica dell'aula. Gli arredi (LIM, cattedra,
        lavagna) sono in basso, le file di banchi salgono verso l'alto. Da qui potrai agire sui pulsanti:</p>
        <p>• <b>💾 Salva assegnazione</b>: salva la distribuzione degli allievi appena ottenuta nello "Storico" del programma, per consultarla in futuro e per memorizzare le coppie formate.<br>
        • <b>📊 Esporta Excel</b>: genera <b>un file .xlsx liberamente modificabile a seconda delle proprie esigenze</b>, con un layout ottimizzato per la stampa in A4.<br>
        • <b>📋 Esporta report .txt</b>: salva il report testuale completo con le caratteristiche degli abbinamenti effettuati.<br></p>

        <p>🍀 La <b>Tab "📊 REPORT":</b> mostra il report testuale dettagliato con tutte le coppie formate,
        i punteggi, le note sui vincoli e il layout dell'aula in formato testo. <b>Le coppie eventualmente riutilizzate sono evidenziate in</b> <span style="color: #CC8800; font-weight: bold;">colore ocra</span>.<br></p>

        <p>🍀 La <b>Tab "📚 STORICO":</b> elenca tutte le assegnazioni salvate. Volendo, puoi <b>modificare il 'Nome' di ogni assegnazione</b> facendo doppio clic su di essa. Per ciascuna inoltre potrai agire sui pulsanti:</p>
        <p>• <b>📋 Dettagli</b>: visualizza il report completo dell'assegnazione, che si può anche esportare.<br>
        • <b>🔍 Layout</b>: apre il layout grafico con la possibilità di esportare in Excel.<br>
        • <b>🗑️ Elimina</b>: rimuove l'assegnazione dallo "Storico" (consentendo di 'ri-abbinare' in futuro gli studenti che erano stati messi assieme in quella assegnazione).<br></p>

        <p>🍀 La <b>Tab "📊 STATISTICHE":</b> analizza l'intero "Storico" della classe (o di più classi) mostrando le coppie più frequenti, gli studenti più spesso in prima fila e le coppie mai formate. Utile per verificare l'equità e le caratteristiche delle rotazioni succedutesi nel tempo.</p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">[5] - FLUSSO DI LAVORO CONSIGLIATO</h3>

        <p>🔷 <b>Prima assegnazione dell'anno (settembre):</b>
        <p>1. <b>Prepara tramite "✏️ Editor studenti" il file .txt della classe</b> con tutti i dati necessari (inclusa l'eventuale posizione FISSO per studenti BES).<br>
        2. <b>Seleziona il file della classe</b> con "💾 SALVA e CARICA classe". Il programma <b>calcolerà il numero di file di banchi necessarie</b>.<br>
        3. Verifica la configurazione aula e, se necessario, modifica 'File di banchi' e/o 'Posti per fila'.<br>
        4. Assegna se necessario la posizione del 'trio' e l'<b>eventuale preferenza per le 'coppie miste'</b>.<br>
        5. <b>Avvia l'assegnazione, salvala nello "Storico" ed esportala in Excel.</b><br>
        6. <b>Apri e modifica se necessario il foglio Excel, stampalo e posizionalo in classe.</b></p><br>

        <p>🔷 <b>Assegnazioni successive (ottobre → giugno):</b>
        <p>1. Mantieni lo stesso file .txt della classe (o ricaricalo se hai aperto una nuova sessione del programma).<br>
        2. La rotazione è <b>automatica</b>: «PostiPerfetti» consulta lo Storico per evitare coppie già formate.<br>
        3. <b>Avvia tutte le assegnazioni necessarie, RICORDANDOTI DI SALVARLE</b> nello "Storico", ed esportale di volta in volta in Excel per un'eventuale modifica e la stampa.</p>
        <p><b>NOTA</b> = nel caso tu non abbia salvato in tempo i file Excel delle varie assegnazioni, potrai sempre farlo in un secondo momento, accedendo alla tab "📚 STORICO" e cliccando su "🔍 Layout".</p><br>

        <p style="background-color: #3A5240; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>
        ⚙️ <b>Modifica dei vincoli in corso d'anno</b><br><br>
        Se le dinamiche della classe dovessero cambiare, modifica con "✏️ Editor studenti" il file .txt della classe - aggiornando 'posizione', 'incompatibilità' e 'affinità' - e poi salvalo.<br></p>

        <hr>
        <h3 style="color: #5B9BD5; text-align: center;">⚠️ RISOLUZIONE DEI PROBLEMI</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #3A5240; color: #ffffff;">
            <td><b>Problema</b></td><td><b>Soluzione</b></td>
        </tr>
        <tr>
            <td>💬 Popup che segnala errore al caricamento del .txt</td>
            <td>Il programma verifica che la sintassi di ogni riga sia corretta e propone in automatico gli aggiustamenti necessari, avvisando con un 'popup'. È consigliabile, in questi casi, rivedere la correttezza dei dati degli allievi nella tab "✏️ Editor studenti"</td>
        </tr>
        <tr>
            <td>🚫 Studente "non trovato" nei vincoli</td>
            <td>Il nome nei vincoli deve corrispondere <b>esattamente</b> a Cognome + Nome (es: <code>Pasolini Pier Paolo</code>, non <code>Pasolini Pier</code>).</td>
        </tr>
        <tr>
            <td>❗ TROPPE COPPIE RIUTILIZZATE</td>
            <td>Con molti vincoli di incompatibilità (livello 3), le combinazioni possibili si riducono. <b>Valuta se qualche vincolo di livello 3 può diventare livello 2.</b></td>
        </tr>
        <tr>
            <td>‼️ L'ASSEGNAZIONE FALLISCE IN TUTTI I TENTATIVI</td>
            <td>I vincoli assoluti creano una situazione matematicamente impossibile da risolvere. <b>Riduci il numero di incompatibilità di 'livello 3', di posizione 'PRIMA' oppure rimuovi il vincolo di 'genere misto'.</b></td>
        </tr>
        <tr>
            <td>🔴 Impossibile impostare vincoli per studente FISSO</td>
            <td>È normale: la scheda dello studente FISSO disabilita incompatibilità e affinità. Per influenzare chi gli siederà accanto, imposta i vincoli <b>nella scheda degli altri studenti</b>.</td>
        </tr>
        </table>

        <hr>
        <p style="color: #999999; font-size: 13px; text-align: center;">
        «PostiPerfetti» — Sviluppato in Python dal prof. Omar Ceretta<br>🇮🇹 I.C. di Tombolo e Galliera Veneta (PADOVA) 🇮🇹<br>
        Licenza: GNU GPLv3</p>
        """

    text_edit.setHtml(istruzioni_html)
    layout.addWidget(text_edit)

    # Bottone Chiudi
    btn_chiudi = QPushButton("✅ Chiudi")
    btn_chiudi.setMinimumHeight(40)
    btn_chiudi.setStyleSheet(f"""
        QPushButton {{
            background-color: {C("btn_indaco_bg")};
            color: white;
            font-size: 13px;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 20px;
        }}
        QPushButton:hover {{
            background-color: {C("btn_indaco_hover")};
        }}
    """)
    btn_chiudi.clicked.connect(dialog.close)
    layout.addWidget(btn_chiudi)

    # Applica tema attivo al dialog istruzioni
    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {C("sfondo_principale")};
            color: {C("testo_principale")};
        }}
        QTextEdit {{
            border: 2px solid {C("bordo_normale")};
            border-radius: 6px;
            background-color: {C("sfondo_testo_area")};
            color: {C("testo_principale")};
            padding: 10px;
        }}
    """)

    # Mostra la finestra in modalità NON-MODALE:
    # show() invece di exec() permette all'utente di continuare
    # a lavorare sul programma mentre le istruzioni restano aperte.
    dialog.show()


# =============================================================================
# CREDITI — Informazioni, versione, licenza GPLv3
# =============================================================================

def mostra_crediti(parent, base_path):
    """
    Mostra una finestra con le informazioni sul programma,
    l'autore, la versione e la licenza GNU GPLv3.

    Args:
        parent: Widget genitore (FinestraPostiPerfetti)
        base_path: Percorso base del progetto (da get_base_path()),
                   usato per trovare l'icona PNG. Passato come parametro
                   per evitare import circolari col file principale.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("ℹ️ Informazioni su «PostiPerfetti»")
    dialog.setMinimumWidth(520)
    dialog.setMaximumWidth(620)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.setContentsMargins(24, 20, 24, 20)

    # --- Icona PostiPerfetti centrata ---
    # CONFIGURABILE: distanza in pixel tra l'icona e il titolo sottostante
    SPAZIO_ICONA_TITOLO = 1  # ← modifica questo valore per aumentare/ridurre la distanza

    # Carica l'immagine PNG dalla cartella del programma
    percorso_icona = os.path.join(base_path, "moduli", "postiperfetti_icon.png")
    if os.path.exists(percorso_icona):
        label_icona = QLabel()
        pixmap = QPixmap(percorso_icona)
        # CONFIGURABILE: dimensione dell'icona nel popup (in pixel)
        DIMENSIONE_ICONA = 80  # ← modifica questo valore per ingrandire/rimpicciolire
        label_icona.setPixmap(pixmap.scaled(
            DIMENSIONE_ICONA, DIMENSIONE_ICONA,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))
        label_icona.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_icona)
        layout.addSpacing(SPAZIO_ICONA_TITOLO)

    # --- Contenuto HTML con crediti, licenza e link ---
    crediti_html = """
        <div style="text-align: center;">
            <h2 style="color: #4CAF50; margin-top: 0px; margin-bottom: 2px;">«PostiPerfetti»</h2>
            <p style="color: #888; font-size: 13px; margin-top: 0;">Versione 2.0</p>
        </div>

        <hr style="border: 1px solid #555;">

        <p style="font-size: 13px;">
            <b>Descrizione:</b><br>
            Programma per l'assegnazione automatica dei posti
            in classe, con gestione di vincoli, affinità,
            incompatibilità, rotazione allievi e storico assegnazioni.
        </p>

        <p style="font-size: 13px;">
            <b>Autore:</b><br>
            Prof. Omar Ceretta<br>
            I.C. di Tombolo e Galliera Veneta (PD)
        </p>

        <p style="font-size: 13px;">
            <b>Tecnologie:</b><br>
            Python 3 · PySide6 (Qt) · XlsxWriter
        </p>

        <hr style="border: 1px solid #555;">

        <p style="font-size: 12px;">
            <b>Licenza — GNU General Public License v3.0 (GPLv3)</b><br><br>
            ▣ Questo software è libero: puoi usarlo, copiarlo, studiarlo
            e redistribuirlo liberamente.<br><br>
            ▣ Se lo modifichi e redistribuisci, sei tenuto a mantenere l'attribuzione al creatore originale e a rendere pubblico il codice sorgente delle tue modifiche con la stessa licenza GPLv3.<br><br>
            ▣ Il software è distribuito <i>«così com'è»</i>, senza alcuna
            garanzia espressa o implicita.<br><br>
            Pagina GitHub con il codice sorgente:
            <a href="https://github.com/Omar-Ceretta/PostiPerfetti"
               style="color: #4FC3F7;">
               github.com/Omar-Ceretta/PostiPerfetti</a>
        </p>
        """

    label_crediti = QLabel(crediti_html)
    label_crediti.setWordWrap(True)
    label_crediti.setOpenExternalLinks(True)  # I link si aprono nel browser
    label_crediti.setStyleSheet("padding: 4px;")
    layout.addWidget(label_crediti)

    # --- Bottone Chiudi ---
    bottoni = QDialogButtonBox(QDialogButtonBox.Close)
    bottoni.rejected.connect(dialog.close)
    layout.addWidget(bottoni)

    dialog.exec()


# =============================================================================
# AIUTO CONFIGURAZIONE AULA — Schema visivo ASCII
# =============================================================================

def mostra_aiuto_configurazione_aula(parent):
    """
    Mostra un popup con schema ASCII che spiega visivamente
    cosa si intende per 'file di banchi' e 'posti per fila'.

    Args:
        parent: Widget genitore (FinestraPostiPerfetti)
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("❓ Come configurare l'aula")
    dialog.setMinimumWidth(520)
    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)

    # Titolo
    label_titolo = QLabel("📐 Come si contano file e posti")
    label_titolo.setStyleSheet(
        f"font-size: 15px; font-weight: bold; color: {C('testo_principale')};"
    )
    layout.addWidget(label_titolo)

    # Schema ASCII dell'aula
    # La cattedra è in basso, le file si contano partendo da lì
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

    label_schema = QLabel(schema)
    font_mono = QFont()
    font_mono.setFamily("Courier New")
    font_mono.setStyleHint(QFont.Monospace)
    font_mono.setPointSize(10)
    label_schema.setFont(font_mono)
    label_schema.setStyleSheet(f"""
        background-color: {C("sfondo_testo_area")};
        color: {C("testo_principale")};
        border: 1px solid {C("bordo_normale")};
        border-radius: 6px;
        padding: 12px;
    """)
    layout.addWidget(label_schema)

    # Spiegazione testuale
    spiegazione = QLabel(
        "<b>📏 File di banchi</b> = quante file ci sono, contando "
        "dalla cattedra verso il fondo dell'aula. Nell'esempio sopra: <b>4 file</b>.<br><br>"
        "<b>🪑 Posti per fila</b> = quanti banchi ci sono in ogni fila, "
        "contati da sinistra a destra. Nell'esempio sopra: <b>4 posti per fila</b> (= 2 coppie di alunni seduti fianco a fianco).<br><br>"
        "<b>💡 Nota:</b> i posti devono essere in numero <b>pari</b> "
        "perché gli studenti siedono a coppie. "
        "Se il numero di studenti è dispari, una delle file ospiterà un trio,"
        "che si può decidere di disporre in 1a fila, in ultima o al centro."
    )
    spiegazione.setWordWrap(True)
    spiegazione.setStyleSheet(
        f"color: {C('testo_principale')}; font-size: 14px; line-height: 1.5;"
    )
    layout.addWidget(spiegazione)

    # Bottone chiudi
    btn_chiudi = QPushButton("✅ Chiudi")
    btn_chiudi.setMinimumHeight(36)
    btn_chiudi.setStyleSheet(f"""
        QPushButton {{
            background-color: {C("btn_indaco_bg")};
            color: white;
            font-weight: bold;
            border-radius: 6px;
            padding: 8px 20px;
        }}
        QPushButton:hover {{ background-color: {C("btn_indaco_hover")}; }}
    """)
    btn_chiudi.clicked.connect(dialog.close)
    layout.addWidget(btn_chiudi)

    dialog.setStyleSheet(f"""
        QDialog {{
            background-color: {C("sfondo_principale")};
        }}
    """)

    dialog.exec()
