#!/usr/bin/env bash
# =====================================================================
# install.sh — Installer di «PostiPerfetti» per Linux
#
# Scarica il programma da GitHub, lo installa nella cartella personale
# dell'utente e crea icona e voce di menu secondo gli standard
# freedesktop.org (validi su KDE, GNOME, XFCE, COSMIC, ecc.).
#
# NON richiede MAI privilegi di amministratore (niente sudo):
# scrive esclusivamente dentro la cartella personale dell'utente.
#
# L'ambiente virtuale (.venv) e le dipendenze NON sono compito di
# questo script: se ne occupa il launcher al primo avvio del programma.
# =====================================================================


# =====================================================================
# BLOCCO 0 — Impostazioni di sicurezza, costanti e messaggistica
# =====================================================================

# Modalità di esecuzione rigorosa:
#   -e  interrompe lo script al primo comando che fallisce
#   -u  errore se si usa una variabile mai definita (evita i refusi)
#   -o pipefail  una pipe fallisce se fallisce QUALSIASI suo comando
set -euo pipefail

# Indirizzo dell'archivio: stato attuale del ramo principale su GitHub.
# Non esistono versioni multiple: c'è sempre e solo l'ultima.
URL_TARBALL="https://github.com/Omar-Ceretta/PostiPerfetti/archive/refs/heads/main.tar.gz"

# Cartella di destinazione del programma.
# Di norma ~/PostiPerfetti, ma può essere cambiata all'avvio con:
#   POSTIPERFETTI_DEST=~/altra_cartella bash install.sh
# (indispensabile per collaudare senza toccare la cartella di sviluppo)
CARTELLA_DEST="${POSTIPERFETTI_DEST:-$HOME/PostiPerfetti}"

# Nome leggibile del programma, usato nei messaggi
NOME_APP="PostiPerfetti"


# --- Colori dei messaggi -------------------------------------------
# Scala blu / grigio / rosso, senza verde: resta leggibile a chiunque.
# Ogni messaggio è comunque riconoscibile dal SIMBOLO, anche in assenza
# di colore (terminali spartani, output rediretto su file).
if [ -t 1 ]; then                 # -t 1 = stiamo scrivendo su un vero terminale
    C_TIT=$'\e[1;34m'             # blu acceso: titoli e fasi
    C_DET=$'\e[2m'                # grigio tenue: dettagli secondari
    C_ERR=$'\e[1;31m'             # rosso: errori
    C_END=$'\e[0m'                # ripristina il colore normale
else
    C_TIT=""; C_DET=""; C_ERR=""; C_END=""
fi

# Titolo di fase (es. "Controllo dei prerequisiti")
msg_fase() { printf '\n%s==>%s %s\n' "$C_TIT" "$C_END" "$*"; }

# Esito positivo di un singolo controllo
msg_ok() { printf '  %s✔%s %s\n' "$C_TIT" "$C_END" "$*"; }

# Informazione secondaria, di contorno
msg_nota() { printf '  %s%s%s\n' "$C_DET" "$*" "$C_END"; }

# Errore non recuperabile: stampa su stderr e TERMINA lo script
errore_fatale() {
    printf '\n  %s✘ %s%s\n\n' "$C_ERR" "$*" "$C_END" >&2
    exit 1
}


# --- Riconoscimento della famiglia di distribuzione -----------------
# Serve solo per suggerire all'utente il comando GIUSTO in caso di
# pacchetti mancanti. Legge /etc/os-release, standard su ogni Linux.
famiglia_distro() {
    local id="" like=""
    if [ -r /etc/os-release ]; then
        # Lettura in sotto-shell: non inquina le variabili dello script
        id=$(. /etc/os-release 2>/dev/null; printf '%s' "${ID:-}")
        like=$(. /etc/os-release 2>/dev/null; printf '%s' "${ID_LIKE:-}")
    fi
    case " $id $like " in
        *debian*|*ubuntu*)        printf 'debian' ;;
        *fedora*|*rhel*|*centos*) printf 'fedora' ;;
        *arch*)                   printf 'arch'   ;;
        *suse*)                   printf 'suse'   ;;
        *)                        printf 'ignota' ;;
    esac
}

# Compone il comando di installazione adatto alla distribuzione.
# Argomenti: $1 nome pacchetto su Debian/Ubuntu
#            $2 su Fedora    $3 su Arch    $4 su openSUSE
comando_installazione() {
    case "$(famiglia_distro)" in
        debian) printf 'sudo apt install %s'     "$1" ;;
        fedora) printf 'sudo dnf install %s'     "$2" ;;
        arch)   printf 'sudo pacman -S %s'       "$3" ;;
        suse)   printf 'sudo zypper install %s'  "$4" ;;
        *)      printf 'installa il pacchetto «%s» con il gestore della tua distribuzione' "$1" ;;
    esac
}


# =====================================================================
# BLOCCO 1 — Controlli preliminari (NESSUNA modifica al sistema)
# =====================================================================

printf '\n%s=====================================%s\n'   "$C_TIT" "$C_END"
printf '%s  Installazione di «%s»%s\n'   "$C_TIT" "$NOME_APP" "$C_END"
printf '%s=====================================%s\n'     "$C_TIT" "$C_END"

msg_fase "Controllo dei prerequisiti"

# --- 1.1 Lo script NON deve girare come amministratore -------------
# Con sudo, $HOME diventerebbe /root: il programma finirebbe in una
# cartella inaccessibile all'utente e le icone non comparirebbero.
if [ "$(id -u)" -eq 0 ]; then
    errore_fatale "Non eseguire questo installer con sudo o come root.
     «$NOME_APP» si installa nella tua cartella personale.
     Riprova con:  bash install.sh"
fi
msg_ok "Esecuzione come utente normale"

# --- 1.2 Python 3 deve essere presente ------------------------------
# Serve al launcher per creare il .venv e avviare il programma.
if ! command -v python3 >/dev/null 2>&1; then
    errore_fatale "Python 3 non è installato.
     Installalo con:
       $(comando_installazione 'python3 python3-venv' 'python3' 'python' 'python3')"
fi
msg_ok "Python 3 presente"
msg_nota "$(python3 --version 2>&1)"

# --- 1.3 Python deve poter creare ambienti virtuali -----------------
# Su Debian/Ubuntu il modulo «ensurepip» sta in un pacchetto separato
# (python3-venv): senza di esso la creazione del .venv fallirebbe più
# tardi, con un errore incomprensibile. Meglio accorgersene ADESSO.
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    errore_fatale "Python 3 non può creare ambienti virtuali (modulo «venv» incompleto).
     Installa il componente mancante con:
       $(comando_installazione 'python3-venv' 'python3' 'python' 'python3')"
fi
msg_ok "Supporto agli ambienti virtuali disponibile"

# --- 1.4-bis «rsync» per copiare il programma in modo sicuro --------
# Serve al BLOCCO 4 per sincronizzare i file preservando la cartella
# «dati/» dell'utente (le sue classi e la configurazione) e il «.venv».
# È lo strumento che rende la copia leggibile e a prova di errore.
if ! command -v rsync >/dev/null 2>&1; then
    errore_fatale "Il comando «rsync» non è disponibile.
     Installalo con:
       $(comando_installazione 'rsync' 'rsync' 'rsync' 'rsync')"
fi
msg_ok "Strumento di copia «rsync» presente"

# --- 1.5 Uno strumento per scaricare: curl OPPURE wget --------------
# Ne basta uno. Memorizziamo quale, così il BLOCCO 2 saprà quale usare.
if command -v curl >/dev/null 2>&1; then
    SCARICATORE="curl"
elif command -v wget >/dev/null 2>&1; then
    SCARICATORE="wget"
else
    errore_fatale "Serve «curl» oppure «wget» per scaricare il programma.
     Installane uno con:
       $(comando_installazione 'curl' 'curl' 'curl' 'curl')"
fi
msg_ok "Strumento di download disponibile: $SCARICATORE"

# --- 1.6 Riepilogo di ciò che verrà fatto ---------------------------
msg_fase "Riepilogo"
msg_nota "Il programma sarà installato in: $CARTELLA_DEST"
msg_nota "Nessuna modifica richiede privilegi di amministratore."


# =====================================================================
# BLOCCO 2 — Download dell'archivio in cartella temporanea
# =====================================================================

msg_fase "Scaricamento di «$NOME_APP»"

# Creiamo una cartella temporanea dedicata. mktemp -d garantisce un
# nome unico e non prevedibile: nessun conflitto con altri file.
CARTELLA_TMP="$(mktemp -d)"

# --- Pulizia automatica garantita -----------------------------------
# La «trap» registra un comando che verrà eseguito all'USCITA dallo
# script, QUALUNQUE ne sia la causa: fine regolare, errore (set -e),
# o interruzione da tastiera (Ctrl-C). Così la cartella temporanea
# non resta MAI abbandonata sul disco.
#   EXIT = uscita normale o per errore    INT/TERM = interruzioni
trap 'rm -rf "$CARTELLA_TMP"' EXIT INT TERM

msg_nota "Area temporanea: $CARTELLA_TMP"

# Percorso del file che stiamo per scaricare
ARCHIVIO_TMP="$CARTELLA_TMP/postiperfetti.tar.gz"

# --- Download vero e proprio ----------------------------------------
# Usiamo lo strumento individuato al BLOCCO 1 ($SCARICATORE).
# Le opzioni chiedono a entrambi di FALLIRE in modo pulito sugli
# errori del server (es. 404), invece di salvare una pagina d'errore
# spacciandola per archivio.
if [ "$SCARICATORE" = "curl" ]; then
    # -f  fallisce sugli errori HTTP (404, 403...)   -L  segue i redirect
    # -o  scrive sul file indicato    --retry  ritenta su rete instabile
    if ! curl -fL --retry 3 -o "$ARCHIVIO_TMP" "$URL_TARBALL"; then
        errore_fatale "Download non riuscito da:
     $URL_TARBALL
     Verifica la connessione a internet.
     Se il problema persiste, il programma potrebbe essere
     temporaneamente non disponibile."
    fi
else
    # wget:  -O  file di destinazione    --tries  numero di tentativi
    if ! wget --tries=3 -O "$ARCHIVIO_TMP" "$URL_TARBALL"; then
        errore_fatale "Download non riuscito da:
     $URL_TARBALL
     Verifica la connessione a internet.
     Se il problema persiste, il programma potrebbe essere
     temporaneamente non disponibile."
    fi
fi

# --- Controllo di sanità: l'archivio non deve essere vuoto ----------
# Se il file esiste ma ha dimensione zero, qualcosa è andato storto
# in modo silenzioso: meglio fermarsi ora che estrarre il nulla.
# ( -s = «esiste ed è più grande di zero byte» )
if [ ! -s "$ARCHIVIO_TMP" ]; then
    errore_fatale "L'archivio scaricato è vuoto o danneggiato.
     Riprova più tardi."
fi

msg_ok "Programma scaricato correttamente"


# =====================================================================
# BLOCCO 3 — Estrazione e individuazione della cartella sorgente
# =====================================================================

msg_fase "Estrazione dei file"

# Estraiamo l'archivio DENTRO la cartella temporanea.
#   x = estrai   z = decomprimi gzip   f = dal file indicato
#   -C = nella cartella indicata
if ! tar xzf "$ARCHIVIO_TMP" -C "$CARTELLA_TMP"; then
    errore_fatale "Impossibile estrarre l'archivio: file danneggiato.
     Riprova a eseguire l'installazione."
fi

# --- Individuazione dinamica della cartella del sorgente ------------
# GitHub crea una cartella tipo «PostiPerfetti-main», ma non diamo
# per scontato quel nome: cerchiamo l'UNICA sottocartella presente
# nell'area temporanea (l'archivio, oltre ad essa, non contiene altro
# se non il .tar.gz che abbiamo scaricato noi).
# Il ciclo scorre le sole directory e si ferma alla prima trovata.
CARTELLA_SORGENTE=""
for d in "$CARTELLA_TMP"/*/; do
    if [ -d "$d" ]; then
        CARTELLA_SORGENTE="${d%/}"   # rimuove la «/» finale dal percorso
        break
    fi
done

# --- Verifica che l'estratto sia davvero PostiPerfetti --------------
# Controlliamo la presenza del file principale: è la prova che
# l'archivio contiene ciò che ci aspettiamo, e non altro.
if [ -z "$CARTELLA_SORGENTE" ] || [ ! -f "$CARTELLA_SORGENTE/postiperfetti.py" ]; then
    errore_fatale "L'archivio scaricato non contiene i file attesi di «$NOME_APP».
     L'installazione non può proseguire."
fi

msg_ok "File estratti e verificati"
msg_nota "Sorgente pronto in: $CARTELLA_SORGENTE"


# =====================================================================
# BLOCCO 4 — Installazione o aggiornamento in $CARTELLA_DEST
# =====================================================================

# Distinguiamo i due scenari osservando se la destinazione contiene
# GIÀ un'installazione (cerchiamo il file principale come prova).
# Questo determina come trattare la cartella «dati/» dell'utente.
if [ -f "$CARTELLA_DEST/postiperfetti.py" ]; then
    TIPO_INSTALLAZIONE="aggiornamento"
else
    TIPO_INSTALLAZIONE="prima_installazione"
fi

if [ "$TIPO_INSTALLAZIONE" = "aggiornamento" ]; then
    msg_fase "Aggiornamento dell'installazione esistente"
    msg_nota "I tuoi dati personali (classi e impostazioni) NON verranno toccati."
else
    msg_fase "Installazione nella cartella personale"
fi

# Creiamo la cartella di destinazione se non esiste ancora.
# ( -p non dà errore se la cartella c'è già )
mkdir -p "$CARTELLA_DEST"

# --- Elenco delle esclusioni dalla sincronizzazione -----------------
# Questi percorsi, se già presenti nella destinazione, NON vengono mai
# sovrascritti né cancellati da rsync. Sono il territorio dell'utente
# e ciò che va ricostruito localmente:
#   dati/   → classi, configurazione, backup dell'utente
#   .venv/  → ambiente virtuale (lo ricrea il launcher al 1° avvio)
ESCLUSIONI=(
    "--exclude=dati/"
    "--exclude=.venv/"
)

# --- Sincronizzazione del programma ---------------------------------
# Opzioni di rsync:
#   -a  modalità archivio: copia ricorsiva conservando permessi e date
#   --delete  rende la destinazione identica al sorgente, RIMUOVENDO
#             i file che nel sorgente non esistono più (es. un modulo
#             eliminato in una versione nuova). Grazie alle esclusioni,
#             «dati/» e «.venv/» sono immuni da questa rimozione.
# NB: la «/» finale dopo la cartella sorgente è ESSENZIALE: dice a
# rsync «copia il CONTENUTO di questa cartella», non la cartella stessa.
if ! rsync -a --delete "${ESCLUSIONI[@]}" "$CARTELLA_SORGENTE/" "$CARTELLA_DEST/"; then
    errore_fatale "Copia dei file non riuscita.
     L'installazione è incompleta. Riprova."
fi

msg_ok "File del programma copiati"

# --- Prima installazione: la cartella «dati/» va creata da zero -----
# In aggiornamento «dati/» è esclusa e resta com'è (corretto).
# Alla prima installazione, però, l'esclusione impedisce a rsync di
# copiarla: dobbiamo portarla noi, UNA VOLTA, con i file di base
# (esempi di classe, ecc.). Se per qualsiasi motivo «dati/» esiste
# già, NON la tocchiamo — la sicurezza dei dati viene prima di tutto.
if [ "$TIPO_INSTALLAZIONE" = "prima_installazione" ]; then
    if [ ! -d "$CARTELLA_DEST/dati" ] && [ -d "$CARTELLA_SORGENTE/dati" ]; then
        # -a conserva la struttura; copiamo il CONTENUTO di dati/
        cp -a "$CARTELLA_SORGENTE/dati" "$CARTELLA_DEST/"
        msg_ok "File di base copiati (esempi e risorse)"
    fi
fi

# --- Permesso di esecuzione sul launcher ----------------------------
# Gli archivi .tar.gz di GitHub NON conservano in modo affidabile il
# bit di esecuzione: lo reimpostiamo esplicitamente, altrimenti la
# voce di menu (BLOCCO 5) non riuscirebbe ad avviare il programma.
LAUNCHER="$CARTELLA_DEST/moduli/postiperfetti_launcher.py"
if [ -f "$LAUNCHER" ]; then
    chmod +x "$LAUNCHER"
    msg_ok "Launcher reso eseguibile"
else
    # Non è fatale qui, ma è un'anomalia che vale la pena segnalare:
    # senza launcher, il BLOCCO 5 non avrebbe cosa avviare.
    msg_nota "Attenzione: launcher non trovato nel percorso atteso."
fi


# =====================================================================
# BLOCCO 5 — Integrazione desktop (standard freedesktop.org)
# =====================================================================

msg_fase "Integrazione con il menu delle applicazioni"

# --- Cartelle di destinazione secondo lo standard XDG ---------------
# $XDG_DATA_HOME è la sede standard dei dati utente; se non è definita
# (come spesso accade), lo standard prescrive il fallback ~/.local/share.
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"

# Cartella dei file .desktop e cartella dell'icona 256x256 (dimensione
# reale del nostro PNG, verificata a suo tempo con «file»).
DIR_APPLICAZIONI="$DATA_HOME/applications"
DIR_ICONA="$DATA_HOME/icons/hicolor/256x256/apps"

# Percorso finale del file .desktop e dell'icona installata.
# Il nome «postiperfetti» DEVE coincidere con l'app_id impostato nel
# codice (setDesktopFileName) e con il valore Icon= del .desktop:
# è la catena che lega finestra, voce di menu e icona.
FILE_DESKTOP="$DIR_APPLICAZIONI/postiperfetti.desktop"
ICONA_INSTALLATA="$DIR_ICONA/postiperfetti.png"

# Percorsi REALI calcolati da questa installazione, che finiranno
# dentro il .desktop. Sono assoluti e dipendono da $CARTELLA_DEST.
LAUNCHER_REALE="$CARTELLA_DEST/moduli/postiperfetti_launcher.py"
ICONA_SORGENTE="$CARTELLA_DEST/dati/icone/postiperfetti_icon.png"

# --- Installazione dell'icona nel tema hicolor ----------------------
# Copiamo il PNG RINOMINANDOLO in «postiperfetti.png»: il nome del file
# icona (senza estensione) è ciò che il .desktop cerca nel tema.
if [ -f "$ICONA_SORGENTE" ]; then
    mkdir -p "$DIR_ICONA"
    cp -f "$ICONA_SORGENTE" "$ICONA_INSTALLATA"
    msg_ok "Icona installata"
else
    # Non è fatale: il programma funziona comunque, resta solo senza
    # icona nel menu. Meglio avvisare che interrompere l'installazione.
    msg_nota "Icona non trovata nel sorgente: la voce di menu userà l'icona generica."
fi

# --- Generazione del file .desktop ----------------------------------
# Lo scriviamo con un «here-document» (<<EOF): tutto ciò che sta tra
# <<EOF e EOF finisce nel file. Le variabili vengono espanse, così i
# percorsi reali di QUESTA installazione entrano nel file.
mkdir -p "$DIR_APPLICAZIONI"

cat > "$FILE_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=PostiPerfetti
GenericName=Assegnazione posti in classe
Comment=Assegna automaticamente i posti degli allievi con rotazione mensile
Exec=$LAUNCHER_REALE
Path=$CARTELLA_DEST
Icon=postiperfetti
StartupWMClass=postiperfetti.py
Terminal=false
Categories=Education;Qt;
EOF

msg_ok "Voce di menu creata"

# --- Validazione formale del .desktop (se lo strumento è presente) --
# desktop-file-validate non stampa nulla se il file è corretto.
# È una verifica di qualità, non un requisito: la saltiamo se assente.
if command -v desktop-file-validate >/dev/null 2>&1; then
    if ! desktop-file-validate "$FILE_DESKTOP" 2>/dev/null; then
        msg_nota "Il file di menu presenta avvisi formali, ma dovrebbe funzionare."
    fi
fi

# --- Aggiornamento dei database di sistema --------------------------
# Ogni ambiente desktop ha i suoi strumenti di refresh. Li eseguiamo
# SOLO se presenti, in silenzio: se mancano, i file sono comunque al
# posto giusto e verranno riconosciuti al successivo accesso.
#   >/dev/null 2>&1  silenzia sia l'output normale sia gli errori
#   || true          impedisce che un refresh fallito fermi lo script
#                    (grazie a «set -e» un errore qui interromperebbe tutto)

# Registro delle applicazioni (menu)
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DIR_APPLICAZIONI" >/dev/null 2>&1 || true
fi

# Cache delle icone del tema hicolor
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

# Cache dei servizi di KDE (presente solo su Plasma)
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

msg_ok "Database delle applicazioni aggiornati"


# =====================================================================
# BLOCCO 6 — Riepilogo finale e avvio facoltativo
# =====================================================================

msg_fase "Installazione completata"

# --- Riepilogo onesto di ciò che è stato fatto ----------------------
printf '\n'
if [ "$TIPO_INSTALLAZIONE" = "aggiornamento" ]; then
    printf '  %s«%s» è stato aggiornato.%s\n' "$C_TIT" "$NOME_APP" "$C_END"
    printf '  I tuoi dati personali (classi e impostazioni) sono rimasti intatti.\n'
else
    printf '  %s«%s» è stato installato.%s\n' "$C_TIT" "$NOME_APP" "$C_END"
fi
printf '\n'
printf '  Programma installato in:  %s%s%s\n'   "$C_DET" "$CARTELLA_DEST" "$C_END"
printf '  Voce di menu creata in:   %s%s%s\n'   "$C_DET" "$FILE_DESKTOP"  "$C_END"

# --- Nota onesta sulla comparsa nel menu ----------------------------
# Alcuni ambienti desktop aggiornano il menu solo al successivo
# accesso. Lo diciamo apertamente, così l'utente non si allarma se
# non vede subito l'icona.
printf '\n'
printf '  %sPer avviare «%s»: cercalo nel menu delle applicazioni.%s\n' "$C_DET" "$NOME_APP" "$C_END"
printf '  %sSe non compare subito, apparirà al prossimo accesso al sistema.%s\n' "$C_DET" "$C_END"

# --- Nota sul primo avvio (solo alla prima installazione) -----------
# Il .venv e le dipendenze non sono compito dell'installer: al primo
# avvio ci pensa il launcher. Preveniamo la sorpresa dei popup.
if [ "$TIPO_INSTALLAZIONE" = "prima_installazione" ]; then
    printf '\n'
    printf '  %sNota: al PRIMO avvio, il programma preparerà il proprio\n' "$C_DET"
    printf '  ambiente e scaricherà i componenti necessari (serve una\n'
    printf '  connessione a internet). Le volte successive partirà subito.%s\n' "$C_END"
fi

# --- Offerta di avvio immediato -------------------------------------
# Proponiamo di avviare ora, ma SOLO se siamo in un terminale
# interattivo (se lo script fosse eseguito da pipe, «read» fallirebbe).
# Rispettiamo la risposta: nessun avvio forzato.
if [ -t 0 ] && [ -f "$LAUNCHER" ]; then
    printf '\n'
    printf '  %sVuoi avviare «%s» adesso? [S/n] %s' "$C_TIT" "$NOME_APP" "$C_END"
    read -r risposta
    case "$risposta" in
        # Stringa VUOTA (solo Invio) o esplicito sì → avvia.
        # La stringa vuota è ora il default, coerente con [S/n].
        ""|s|S|si|Si|sì|Sì|y|Y)
            printf '\n  Avvio in corso...\n'
            # Avvio staccato dal terminale: il programma resta aperto
            # anche se chiudi questa finestra. «setsid» crea una nuova
            # sessione; l'output viene scartato per non sporcare il terminale.
            setsid "$LAUNCHER" >/dev/null 2>&1 &
            ;;
        *)
            printf '\n  Nessun problema: lo troverai nel menu quando vorrai.\n'
            ;;
    esac
fi

printf '\n'

# Fine dello script. Nessun «exit» esplicito: se siamo arrivati fin
# qui senza errori, lo stato di uscita è già 0 (successo).
