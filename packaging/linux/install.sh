#!/usr/bin/env bash
# =====================================================================
# install.sh — Installer di «PostiPerfetti» per Linux
#
# Scarica il programma da GitHub, lo installa nella cartella personale
# dell'utente e crea icona e voce di menu secondo gli standard
# freedesktop.org (validi su KDE, GNOME, XFCE, COSMIC, ecc.).
#
# Lo script deve essere eseguito come utente normale, MAI con sudo.
# Se mancano prerequisiti di sistema, può chiedere esplicitamente
# l'autorizzazione a usare sudo soltanto per il gestore dei pacchetti.
# I file di PostiPerfetti restano sempre nella cartella dell'utente.
#
# L'installer prepara e verifica anche l'ambiente virtuale (.venv)
# e le dipendenze Python. Il launcher conserva il ruolo di controllo
# e autoriparazione per eventuali problemi successivi.
# =====================================================================


# =====================================================================
# BLOCCO 0 — Impostazioni di sicurezza, costanti e messaggistica
# =====================================================================

# Modalità di esecuzione rigorosa:
#   -e  interrompe lo script al primo comando che fallisce
#   -u  errore se si usa una variabile mai definita (evita i refusi)
#   -o pipefail  una pipe fallisce se fallisce QUALSIASI suo comando
set -euo pipefail

# ---------------------------------------------------------------------
# Modalità di distribuzione
# ---------------------------------------------------------------------
# Questo file nel repository resta deliberatamente un installer di
# SVILUPPO/COLLAUDO. Il generatore di release ne crea una copia nella
# quale queste quattro costanti vengono sostituite automaticamente.
#
# Non modificare a mano questi valori per preparare una release.
MODALITA_RELEASE=0
VERSIONE_RELEASE=""
URL_TARBALL="https://github.com/Omar-Ceretta/PostiPerfetti/archive/refs/heads/main.tar.gz"
SHA256_ATTESO=""

# Cartella di destinazione del programma.
# Di norma ~/PostiPerfetti, ma può essere cambiata all'avvio con:
#   POSTIPERFETTI_DEST=~/altra_cartella bash install.sh
# (indispensabile per collaudare senza toccare la cartella di sviluppo)
CARTELLA_DEST="${POSTIPERFETTI_DEST:-$HOME/PostiPerfetti}"

# Integrazione nel menu applicazioni. Per un collaudo completamente isolato
# si può evitare di riscrivere la voce .desktop e l'icona dell'utente con:
#   POSTIPERFETTI_INTEGRA_MENU=0 POSTIPERFETTI_DEST=... bash install.sh
INTEGRA_MENU="${POSTIPERFETTI_INTEGRA_MENU:-1}"

# Modalità di collaudo: se impostata, usa direttamente una copia locale
# del repository invece di scaricare l'archivio da GitHub.
# Non è usata nell'installazione normale dell'utente.
SORGENTE_LOCALE="${POSTIPERFETTI_SORGENTE_LOCALE:-}"

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


# Calcola SHA-256 usando Python, che è già un prerequisito obbligatorio
# dell'applicazione. Non introduciamo quindi sha256sum/shasum come
# ulteriore dipendenza di sistema.
calcola_sha256() {
    python3 - "$1" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

percorso = Path(sys.argv[1])
digest = sha256()

with percorso.open("rb") as file:
    for blocco in iter(lambda: file.read(1024 * 1024), b""):
        digest.update(blocco)

print(digest.hexdigest())
PY
}

case "$INTEGRA_MENU" in
    0|1) ;;
    *) errore_fatale "POSTIPERFETTI_INTEGRA_MENU accetta soltanto 0 oppure 1." ;;
esac

case "$MODALITA_RELEASE" in
    0|1) ;;
    *) errore_fatale "Configurazione interna non valida: MODALITA_RELEASE." ;;
esac

if [ "$MODALITA_RELEASE" = "1" ]; then
    if [ -z "$VERSIONE_RELEASE" ]; then
        errore_fatale "Installer di release privo della versione attesa."
    fi

    if [[ ! "$SHA256_ATTESO" =~ ^[0-9a-fA-F]{64}$ ]]; then
        errore_fatale "Installer di release privo di uno SHA-256 valido."
    fi

    # Una copia ufficiale di release non deve poter essere dirottata
    # tramite la modalità di collaudo locale.
    if [ -n "$SORGENTE_LOCALE" ]; then
        errore_fatale "POSTIPERFETTI_SORGENTE_LOCALE è una funzione di
     collaudo e non è disponibile nell'installer ufficiale di release."
    fi
fi


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

# Restituisce il pacchetto che fornisce Python 3 nella famiglia rilevata.
pacchetto_python() {
    case "$(famiglia_distro)" in
        debian|fedora|suse) printf 'python3' ;;
        arch)               printf 'python' ;;
        *)                  printf 'python3' ;;
    esac
}

# Su Debian/Ubuntu il supporto completo a venv è separato.
# Nelle altre famiglie supportate è fornito dal pacchetto Python.
pacchetto_venv() {
    case "$(famiglia_distro)" in
        debian) printf 'python3-venv' ;;
        fedora) printf 'python3' ;;
        arch)   printf 'python' ;;
        suse)   printf 'python3' ;;
        *)      printf 'python3' ;;
    esac
}

# Libreria richiesta dal plugin Qt/XCB.
pacchetto_xcb_cursor() {
    case "$(famiglia_distro)" in
        debian) printf 'libxcb-cursor0' ;;
        fedora) printf 'xcb-util-cursor' ;;
        arch)   printf 'xcb-util-cursor' ;;
        suse)   printf 'libxcb-cursor0' ;;
        *)      printf 'libxcb-cursor0' ;;
    esac
}

# Produce un comando leggibile da mostrare all'utente.
# I nomi ricevuti sono già quelli corretti per la famiglia corrente.
comando_installazione() {
    case "$(famiglia_distro)" in
        debian) printf 'sudo apt-get install %s' "$*" ;;
        fedora) printf 'sudo dnf install %s' "$*" ;;
        arch)   printf 'sudo pacman -S --needed %s' "$*" ;;
        suse)   printf 'sudo zypper install %s' "$*" ;;
        *)      printf 'installa manualmente i prerequisiti mancanti' ;;
    esac
}

# Installa in una sola operazione i pacchetti di sistema mancanti.
# Su Arch NON eseguiamo mai «pacman -Sy»: evitiamo di aggiornare soltanto
# il database dei pacchetti e lasciare il sistema in stato incoerente.
installa_pacchetti_sistema() {
    case "$(famiglia_distro)" in
        debian)
            sudo apt-get update &&
            sudo apt-get install -y "$@"
            ;;
        fedora)
            sudo dnf install -y "$@"
            ;;
        arch)
            sudo pacman -S --needed --noconfirm "$@"
            ;;
        suse)
            sudo zypper --non-interactive install "$@"
            ;;
        *)
            return 1
            ;;
    esac
}

# Verifica il contratto Python della release corrente.
# PySide6 6.11.1 richiede Python >= 3.10 e < 3.15.
python_versione_compatibile() {
    python3 -c '
import sys
raise SystemExit(
    0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 1
)
' >/dev/null 2>&1
}

# Non ci accontentiamo di «import venv» o «import ensurepip»:
# proviamo realmente a creare un piccolo ambiente virtuale, verifichiamo
# che contenga Python e pip e poi lo eliminiamo.
python_puo_creare_venv() {
    local prova_venv

    prova_venv="$(mktemp -d)" || return 1

    if python3 -m venv "$prova_venv/venv" >/dev/null 2>&1 \
            && "$prova_venv/venv/bin/python" -m pip --version \
                >/dev/null 2>&1; then
        rm -rf "$prova_venv"
        return 0
    fi

    rm -rf "$prova_venv"
    return 1
}

# Verifica la presenza della libreria nativa che ha causato il crash
# osservato su Linux Mint.
ha_libreria_xcb_cursor() {
    local ldconfig_cmd="" contenuto=""

    if command -v ldconfig >/dev/null 2>&1; then
        ldconfig_cmd="$(command -v ldconfig)"
    elif [ -x /usr/sbin/ldconfig ]; then
        ldconfig_cmd="/usr/sbin/ldconfig"
    elif [ -x /sbin/ldconfig ]; then
        ldconfig_cmd="/sbin/ldconfig"
    fi

    if [ -n "$ldconfig_cmd" ]; then
        contenuto="$("$ldconfig_cmd" -p 2>/dev/null || true)"
        if [[ "$contenuto" == *"libxcb-cursor.so.0"* ]]; then
            return 0
        fi
    fi

    # Ripiego per sistemi dove ldconfig non è disponibile nel modo atteso.
    if [ -n "$(find /usr/lib /usr/lib64 /lib /lib64 \
            -name 'libxcb-cursor.so.0' -print -quit 2>/dev/null)" ]; then
        return 0
    fi

    return 1
}

# Aggiunge un pacchetto all'elenco evitando duplicati.
aggiungi_pacchetto() {
    local nuovo="$1"
    local presente

    for presente in "${PACCHETTI_MANCANTI[@]}"; do
        if [ "$presente" = "$nuovo" ]; then
            return
        fi
    done

    PACCHETTI_MANCANTI+=("$nuovo")
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

# --- 1.2 Inventario dei prerequisiti di sistema ---------------------
# Prima raccogliamo TUTTE le mancanze; soltanto dopo chiediamo
# eventualmente il permesso di installarle.
PACCHETTI_MANCANTI=()
MANCANZE=()
PREREQUISITI_INSTALLATI=0

if ! command -v python3 >/dev/null 2>&1; then
    MANCANZE+=("Python 3")

    aggiungi_pacchetto "$(pacchetto_python)"

    # Su Debian il pacchetto venv è distinto: se Python manca del tutto,
    # predisponiamolo già nella stessa transazione.
    if [ "$(famiglia_distro)" = "debian" ]; then
        aggiungi_pacchetto "$(pacchetto_venv)"
    fi
else
    # Se Python c'è già ma è fuori dal contratto della release, non
    # tentiamo di sostituire automaticamente l'interprete di sistema.
    if ! python_versione_compatibile; then
        VERSIONE_PYTHON="$(python3 --version 2>&1)"
        errore_fatale "La versione di Python installata non è compatibile con questa release.
     Rilevata: $VERSIONE_PYTHON
     Richiesta: Python 3.10, 3.11, 3.12, 3.13 oppure 3.14.

     L'installer non sostituisce automaticamente il Python di sistema."
    fi

    if ! python_puo_creare_venv; then
        MANCANZE+=("supporto Python agli ambienti virtuali")
        aggiungi_pacchetto "$(pacchetto_venv)"
    fi
fi

if ! command -v tar >/dev/null 2>&1; then
    MANCANZE+=("tar")
    aggiungi_pacchetto "tar"
fi

if ! command -v rsync >/dev/null 2>&1; then
    MANCANZE+=("rsync")
    aggiungi_pacchetto "rsync"
fi

if [ -z "$SORGENTE_LOCALE" ] \
        && ! command -v curl >/dev/null 2>&1 \
        && ! command -v wget >/dev/null 2>&1; then
    MANCANZE+=("strumento di download")
    aggiungi_pacchetto "curl"
fi

if ! ha_libreria_xcb_cursor; then
    MANCANZE+=("libreria Qt/XCB per il cursore")
    aggiungi_pacchetto "$(pacchetto_xcb_cursor)"
fi

# --- 1.3 Installazione facoltativa delle sole mancanze ---------------
if [ "${#PACCHETTI_MANCANTI[@]}" -gt 0 ]; then
    msg_fase "Prerequisiti di sistema mancanti"

    for mancanza in "${MANCANZE[@]}"; do
        printf '  - %s\n' "$mancanza"
    done

    if [ "$(famiglia_distro)" = "ignota" ]; then
        errore_fatale "La distribuzione Linux non è stata riconosciuta.
     Non installerò pacchetti di sistema tentando di indovinare i nomi.
     Installa manualmente i prerequisiti elencati qui sopra e riesegui
     questo installer."
    fi

    msg_nota "Pacchetti proposti: ${PACCHETTI_MANCANTI[*]}"

    if ! command -v sudo >/dev/null 2>&1; then
        errore_fatale "Per installare automaticamente i prerequisiti serve «sudo».
     Puoi installarli manualmente con privilegi amministrativi:
       $(comando_installazione "${PACCHETTI_MANCANTI[@]}")"
    fi

    if [ ! -t 0 ]; then
        errore_fatale "Sono necessari pacchetti di sistema, ma l'installer
     non è in un terminale interattivo e non può chiederti il permesso.
     Rieseguilo da terminale."
    fi

    printf '\n'
    printf '  %sPosso installare automaticamente questi prerequisiti.%s\n' \
        "$C_TIT" "$C_END"
    printf '  Verrà richiesta la password di amministrazione da sudo.\n'
    printf '  Nessun altro file di sistema verrà modificato da PostiPerfetti.\n'
    printf '\n'
    printf '  %sProcedere? [S/n] %s' "$C_TIT" "$C_END"

    if ! read -r risposta_prerequisiti; then
        risposta_prerequisiti="n"
    fi

    case "$risposta_prerequisiti" in
        ""|s|S|si|SI|Si|sì|SÌ|Sì|y|Y|yes|YES|Yes)
            ;;
        *)
            errore_fatale "Installazione dei prerequisiti annullata.
     Puoi installarli manualmente con:
       $(comando_installazione "${PACCHETTI_MANCANTI[@]}")"
            ;;
    esac

    if ! sudo -v; then
        errore_fatale "Autorizzazione amministrativa non concessa.
     Nessuna modifica è stata eseguita da PostiPerfetti."
    fi

    msg_fase "Installazione dei prerequisiti di sistema"

    if ! installa_pacchetti_sistema "${PACCHETTI_MANCANTI[@]}"; then
        errore_fatale "Il gestore dei pacchetti non è riuscito a completare
     l'installazione dei prerequisiti.

     Controlla i messaggi qui sopra e riprova."
    fi

    PREREQUISITI_INSTALLATI=1
fi

# --- 1.4 Verifica reale DOPO l'eventuale installazione ---------------
# Non ci fidiamo soltanto del codice di uscita del package manager:
# verifichiamo le capacità che PostiPerfetti utilizzerà davvero.
if ! command -v python3 >/dev/null 2>&1; then
    errore_fatale "Python 3 risulta ancora non disponibile dopo il controllo dei prerequisiti."
fi
msg_ok "Python 3 presente"
msg_nota "$(python3 --version 2>&1)"

if ! python_versione_compatibile; then
    errore_fatale "La versione di Python disponibile non è compatibile.
     Serve una versione compresa tra Python 3.10 e Python 3.14."
fi
msg_ok "Versione di Python compatibile"

if ! python_puo_creare_venv; then
    errore_fatale "Python 3 non riesce a creare un ambiente virtuale
     completo di pip, anche dopo il controllo dei prerequisiti."
fi
msg_ok "Creazione reale di un ambiente virtuale: OK"

if ! command -v tar >/dev/null 2>&1; then
    errore_fatale "Il comando «tar» risulta ancora non disponibile."
fi
msg_ok "Strumento di estrazione «tar» presente"

if ! command -v rsync >/dev/null 2>&1; then
    errore_fatale "Il comando «rsync» risulta ancora non disponibile."
fi
msg_ok "Strumento di copia «rsync» presente"

if [ -n "$SORGENTE_LOCALE" ]; then
    SCARICATORE=""
    msg_ok "Modalità di collaudo con sorgente locale attiva"
elif command -v curl >/dev/null 2>&1; then
    SCARICATORE="curl"
    msg_ok "Strumento di download disponibile: $SCARICATORE"
elif command -v wget >/dev/null 2>&1; then
    SCARICATORE="wget"
    msg_ok "Strumento di download disponibile: $SCARICATORE"
else
    errore_fatale "Né «curl» né «wget» risultano disponibili."
fi

if ! ha_libreria_xcb_cursor; then
    errore_fatale "La libreria «libxcb-cursor.so.0» risulta ancora assente.
     Qt potrebbe non riuscire ad avviare l'interfaccia grafica."
fi
msg_ok "Libreria Qt/XCB «libxcb-cursor.so.0» presente"

# --- 1.6 Riepilogo di ciò che verrà fatto ---------------------------
msg_fase "Riepilogo"
msg_nota "Il programma sarà installato in: $CARTELLA_DEST"

if [ "$PREREQUISITI_INSTALLATI" = "1" ]; then
    msg_nota "Sono stati installati soltanto i prerequisiti di sistema mancanti."
    msg_nota "I file di PostiPerfetti saranno comunque scritti come utente normale."
else
    msg_nota "Tutti i prerequisiti di sistema erano già presenti: sudo non è stato usato."
fi


# =====================================================================
# BLOCCO 2 — Acquisizione del sorgente
# =====================================================================

if [ -n "$SORGENTE_LOCALE" ]; then
    msg_fase "Uso del sorgente locale di collaudo"

    if [ ! -d "$SORGENTE_LOCALE" ]; then
        errore_fatale "La cartella sorgente locale non esiste:
     $SORGENTE_LOCALE"
    fi

    CARTELLA_SORGENTE="$(
        cd -- "$SORGENTE_LOCALE" 2>/dev/null
        pwd -P
    )"

    if [ ! -f "$CARTELLA_SORGENTE/postiperfetti.py" ] \
            || [ ! -f "$CARTELLA_SORGENTE/requirements.txt" ] \
            || [ ! -d "$CARTELLA_SORGENTE/moduli" ] \
            || [ ! -d "$CARTELLA_SORGENTE/risorse" ]; then
        errore_fatale "La cartella indicata non sembra una radice valida
     del repository di «$NOME_APP»:
     $CARTELLA_SORGENTE"
    fi

    msg_ok "Sorgente locale verificato"
    msg_nota "Sorgente pronto in: $CARTELLA_SORGENTE"
else

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
trap 'rm -rf "$CARTELLA_TMP"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

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

# L'installer ufficiale di release conosce in anticipo l'impronta
# dell'asset che deve installare. Un download diverso, anche se fosse
# comunque un archivio tar.gz valido, viene rifiutato.
if [ "$MODALITA_RELEASE" = "1" ]; then
    msg_fase "Verifica dell'integrità del pacchetto"

    SHA256_OTTENUTO="$(calcola_sha256 "$ARCHIVIO_TMP")"

    if [ "$SHA256_OTTENUTO" != "$SHA256_ATTESO" ]; then
        errore_fatale "La verifica SHA-256 del pacchetto è fallita.

     Atteso:
       $SHA256_ATTESO

     Ricevuto:
       $SHA256_OTTENUTO

     Il pacchetto NON verrà estratto né installato.
     Riscarica l'installer dalla Release ufficiale."
    fi

    msg_ok "SHA-256 del pacchetto verificato"
fi

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

fi  # fine: sorgente locale / download remoto


# In una release verifichiamo due identità indipendenti:
#   1. i byte del pacchetto devono avere lo SHA-256 previsto;
#   2. il codice al suo interno deve dichiarare la versione prevista.
if [ "$MODALITA_RELEASE" = "1" ]; then
    FILE_VERSIONE_SORGENTE="$CARTELLA_SORGENTE/moduli/versione.py"

    if [ ! -f "$FILE_VERSIONE_SORGENTE" ]; then
        errore_fatale "Il pacchetto non contiene «moduli/versione.py»."
    fi

    if ! VERSIONE_SORGENTE="$(
        python3 - "$FILE_VERSIONE_SORGENTE" <<'PY'
import runpy
import sys

dati = runpy.run_path(sys.argv[1])
print(dati["VERSIONE"])
PY
    )"; then
        errore_fatale "Impossibile leggere la versione dal pacchetto."
    fi

    if [ "$VERSIONE_SORGENTE" != "$VERSIONE_RELEASE" ]; then
        errore_fatale "Il pacchetto non appartiene alla release attesa.

     Installer: $VERSIONE_RELEASE
     Pacchetto: $VERSIONE_SORGENTE

     L'installazione viene interrotta."
    fi

    msg_ok "Versione del pacchetto verificata: $VERSIONE_RELEASE"
fi


# =====================================================================
# BLOCCO 4 — Installazione, aggiornamento o reinstallazione
# =====================================================================

# Dopo una disinstallazione normale possono restare ESCLUSIVAMENTE le
# cartelle dati classi/, stato/ e log/. Una destinazione di questo tipo
# è una reinstallazione legittima e non deve essere scambiata per una
# cartella estranea.
#
# Per sicurezza:
#   - deve esserci almeno una delle tre cartelle;
#   - al primo livello non deve esserci nient'altro;
#   - le tre voci ammesse devono essere directory reali, non symlink.
destinazione_contiene_solo_dati_conservati() {
    local voce nome trovato=0

    [ -d "$CARTELLA_DEST" ] || return 1

    while IFS= read -r -d '' voce; do
        trovato=1
        nome="${voce##*/}"

        case "$nome" in
            classi|stato|log)
                if [ ! -d "$voce" ] || [ -L "$voce" ]; then
                    return 1
                fi
                ;;
            *)
                return 1
                ;;
        esac
    done < <(
        find "$CARTELLA_DEST" \
            -mindepth 1 \
            -maxdepth 1 \
            -print0 2>/dev/null
    )

    [ "$trovato" -eq 1 ]
}

# Proteggiamo sempre una cartella non riconosciuta: PostiPerfetti non
# deve sovrascrivere contenuti estranei soltanto perché l'utente ha
# scelto per errore quella destinazione.
if [ -d "$CARTELLA_DEST" ] && [ ! -f "$CARTELLA_DEST/postiperfetti.py" ]; then
    if find "$CARTELLA_DEST" \
            -mindepth 1 \
            -maxdepth 1 \
            -print -quit 2>/dev/null | grep -q .; then

        if ! destinazione_contiene_solo_dati_conservati; then
            errore_fatale "La cartella di destinazione esiste già e non sembra
     né un'installazione di «$NOME_APP», né una precedente
     installazione disinstallata conservando i dati:
     $CARTELLA_DEST

     Per sicurezza nessun contenuto verrà sovrascritto."
        fi
    fi
fi

# Distinguiamo tre casi:
#   aggiornamento              → il programma è già installato;
#   reinstallazione_con_dati   → il programma è stato rimosso ma sono
#                                rimasti classi/, stato/ e/o log/;
#   prima_installazione        → destinazione nuova o vuota.
if [ -f "$CARTELLA_DEST/postiperfetti.py" ]; then
    TIPO_INSTALLAZIONE="aggiornamento"
elif destinazione_contiene_solo_dati_conservati; then
    TIPO_INSTALLAZIONE="reinstallazione_con_dati"
else
    TIPO_INSTALLAZIONE="prima_installazione"
fi

case "$TIPO_INSTALLAZIONE" in
    aggiornamento)
        msg_fase "Aggiornamento dell'installazione esistente"
        msg_nota "Classi, impostazioni e log NON verranno toccati."
        ;;
    reinstallazione_con_dati)
        msg_fase "Reinstallazione con recupero dei dati conservati"
        msg_nota "Sono stati trovati dati di una precedente installazione."
        msg_nota "Classi, impostazioni e log precedenti saranno PRESERVATI."
        ;;
    prima_installazione)
        msg_fase "Installazione nella cartella personale"
        ;;
esac

# Creiamo la cartella di destinazione se non esiste ancora.
# ( -p non dà errore se la cartella c'è già )
mkdir -p "$CARTELLA_DEST"

# --- Che cosa copiare: LISTA POSITIVA dei contenuti "runtime" -------
# Principio di sicurezza: NON copiamo «tutto tranne alcune cose» (che
# rischia di portarsi dietro l'intera "officina" del progetto —
# packaging/, documentazione/, storico/, cache __pycache__, file .bak,
# la configurazione personale dello sviluppatore...). Diciamo invece
# in modo ESPLICITO che cosa deve finire sul computer dell'utente.
#
# Sono SOLO i file che servono a FAR GIRARE il programma:
#   postiperfetti.py  → il programma vero e proprio (punto d'avvio)
#   requirements.txt  → elenco congelato delle librerie runtime;
#                       l'installer lo usa per preparare il .venv e il
#                       launcher lo usa in seguito per eventuali riparazioni.
#                       Su Linux è NECESSARIO (non è come su Windows, dove
#                       PyInstaller impacchetta già tutto nell'.exe).
#   LICENSE           → testo della licenza GNU GPLv3
#   moduli/           → tutto il codice del programma
#   risorse/          → icone e font distribuiti con il programma
#
# NON copiamo MAI: classi/, stato/, log/ (territorio dell'utente),
# né un eventuale .venv del repository sorgente, né strumenti di sviluppo.
# Il .venv dell'installazione viene creato/verificato localmente più avanti.
# Così qualunque cosa "in più" ci sia nel repository viene ignorata.

# Cartelle di programma (contengono molti file) e singoli file: li
# elenchiamo qui, una volta sola, per non ripetere nomi sparsi nel codice.
CARTELLE_PROGRAMMA=(moduli risorse)
FILE_PROGRAMMA=(postiperfetti.py requirements.txt LICENSE)

# --- Sincronizzazione delle CARTELLE di programma -------------------
# Per le cartelle usiamo rsync con --delete e --delete-excluded: la destinazione
# diventa
# identica al sorgente, RIMUOVENDO i file che una versione nuova non
# contiene più (es. un modulo eliminato). Poiché sincronizziamo SOLO
# moduli/ e risorse/ (mai classi/, stato/, log/), i dati dell'utente
# non vengono mai sfiorati da --delete.
# Le esclusioni, insieme a --delete-excluded, impediscono che "sporcizia"
# di sviluppo entri o resti nella destinazione:
#   __pycache__/  → cache di Python, si rigenera da sé
#   *.bak*        → copie di backup dei sorgenti
# NB: la «/» finale dopo la cartella sorgente è ESSENZIALE: dice a
# rsync «copia il CONTENUTO della cartella», non la cartella stessa.
for cartella in "${CARTELLE_PROGRAMMA[@]}"; do
    if [ ! -d "$CARTELLA_SORGENTE/$cartella" ]; then
        errore_fatale "Cartella «$cartella» assente nell'archivio scaricato.
     Il pacchetto non sembra completo. Riprova più tardi."
    fi
    if ! rsync -a --delete --delete-excluded \
            --exclude='__pycache__/' \
            --exclude='*.bak*' \
            "$CARTELLA_SORGENTE/$cartella/" \
            "$CARTELLA_DEST/$cartella/"; then
        errore_fatale "Copia della cartella «$cartella» non riuscita.
     L'installazione è incompleta. Riprova."
    fi
done

# --- Copia dei SINGOLI FILE di programma ----------------------------
# I singoli file dichiarati sopra stanno nella radice: li copiamo
# (in aggiornamento la «-f» sovrascrive senza chiedere conferma).
for file in "${FILE_PROGRAMMA[@]}"; do
    if [ ! -f "$CARTELLA_SORGENTE/$file" ]; then
        errore_fatale "File «$file» assente nell'archivio scaricato.
     Il pacchetto non sembra completo. Riprova più tardi."
    fi
    cp -f "$CARTELLA_SORGENTE/$file" "$CARTELLA_DEST/$file"
done

# Il disinstaller è un'eccezione intenzionale alla lista positiva:
# nel repository vive dentro packaging/linux/, ma nell'installazione
# finale deve trovarsi direttamente accanto a postiperfetti.py.
#
# Accettiamo anche un futuro pacchetto release che lo contenga già
# nella radice, così questa logica non dovrà essere riscritta quando
# separeremo il pacchetto runtime dal repository completo.
if [ -f "$CARTELLA_SORGENTE/uninstall.sh" ]; then
    UNINSTALLER_SORGENTE="$CARTELLA_SORGENTE/uninstall.sh"
elif [ -f "$CARTELLA_SORGENTE/packaging/linux/uninstall.sh" ]; then
    UNINSTALLER_SORGENTE="$CARTELLA_SORGENTE/packaging/linux/uninstall.sh"
else
    errore_fatale "Il disinstaller Linux «uninstall.sh» è assente
     dal pacchetto scaricato. L'installazione non può essere
     considerata completa."
fi

UNINSTALLER_DEST="$CARTELLA_DEST/uninstall.sh"

if ! cp -f "$UNINSTALLER_SORGENTE" "$UNINSTALLER_DEST"; then
    errore_fatale "Copia di «uninstall.sh» non riuscita."
fi

if ! chmod +x "$UNINSTALLER_DEST"; then
    errore_fatale "Impossibile rendere eseguibile «uninstall.sh»."
fi

msg_ok "File del programma copiati (solo i contenuti necessari)"
msg_ok "Disinstaller installato e reso eseguibile"

# --- Prima installazione: semina i file-classe di ESEMPIO -----------
# Il programma crea da sé le cartelle classi/, stato/ e log/ al primo
# avvio: dopo l'installazione restano quindi VUOTE. Per non lasciare
# l'utente davanti a una cartella «classi/» deserta, alla PRIMA
# installazione vi depositiamo SOLO i due file-classe di esempio
# ufficiali (non le eventuali decine di file di prova che possono
# trovarsi nel repository di sviluppo).
# In AGGIORNAMENTO non facciamo nulla di tutto questo: le classi
# dell'utente sono intoccabili (non le tocchiamo né le sovrascriviamo).
if [ "$TIPO_INSTALLAZIONE" = "prima_installazione" ]; then
    # La cartella potrebbe non esistere ancora: la creiamo noi.
    mkdir -p "$CARTELLA_DEST/classi"
    for esempio in "Classe-BASE_esempio.txt" "Classe-COMPLETO_esempio.txt"; do
        if [ ! -f "$CARTELLA_SORGENTE/classi/$esempio" ]; then
            errore_fatale "File-classe di esempio «$esempio» assente nell'archivio scaricato.
     Il pacchetto non sembra completo. Riprova più tardi."
        fi
        cp -f "$CARTELLA_SORGENTE/classi/$esempio" "$CARTELLA_DEST/classi/$esempio"
    done
    msg_ok "File-classe di esempio copiati"
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
    errore_fatale "Launcher non trovato nel percorso atteso:
     $LAUNCHER
     L'installazione non può essere considerata completa."
fi

# =====================================================================
# BLOCCO 4-bis — Preparazione e verifica dell'ambiente Python
# =====================================================================

msg_fase "Preparazione dell'ambiente Python"

VENV_DEST="$CARTELLA_DEST/.venv"
PYTHON_VENV="$VENV_DEST/bin/python3"
REQUISITI_DEST="$CARTELLA_DEST/requirements.txt"


# Verifica che tutte le righe runtime di requirements.txt siano bloccate
# con «==» e che nell'ambiente siano installate ESATTAMENTE quelle versioni.
requirements_esatti() {
    local python_eseguibile="$1"
    local file_requirements="$2"

    "$python_eseguibile" - "$file_requirements" <<'PY'
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

percorso = Path(sys.argv[1])
errori = []

if not percorso.is_file():
    print(f"requirements.txt non trovato: {percorso}", file=sys.stderr)
    raise SystemExit(1)

for numero, riga_grezza in enumerate(
    percorso.read_text(encoding="utf-8").splitlines(),
    start=1,
):
    riga = riga_grezza.split("#", 1)[0].strip()

    if not riga:
        continue

    parti = riga.split("==")

    if len(parti) != 2:
        errori.append(
            f"riga {numero}: dipendenza non congelata con ==: {riga!r}"
        )
        continue

    nome = parti[0].strip()
    attesa = parti[1].strip()

    if not nome or not attesa:
        errori.append(
            f"riga {numero}: requisito non valido: {riga!r}"
        )
        continue

    try:
        installata = version(nome)
    except PackageNotFoundError:
        errori.append(f"{nome}: non installato")
        continue

    if installata != attesa:
        errori.append(
            f"{nome}: installata {installata}, richiesta {attesa}"
        )

if errori:
    for errore in errori:
        print(errore, file=sys.stderr)
    raise SystemExit(1)
PY
}


# Un venv non è considerato valido soltanto perché la directory esiste:
# il suo Python deve essere realmente eseguibile, compatibile e dotato di pip.
venv_funzionante() {
    [ -x "$PYTHON_VENV" ] || return 1

    "$PYTHON_VENV" -c '
import sys
raise SystemExit(
    0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 1
)
' >/dev/null 2>&1 || return 1

    "$PYTHON_VENV" -m pip --version >/dev/null 2>&1 || return 1

    return 0
}


if venv_funzionante; then
    msg_ok "Ambiente virtuale esistente e funzionante"
else
    if [ -e "$VENV_DEST" ]; then
        msg_nota "Il vecchio ambiente virtuale è assente o non utilizzabile."
        msg_nota "Verrà ricreato senza modificare classi, impostazioni o log."
        rm -rf -- "$VENV_DEST"
    else
        msg_nota "Creazione dell'ambiente virtuale..."
    fi

    if ! python3 -m venv "$VENV_DEST"; then
        errore_fatale "Creazione dell'ambiente virtuale non riuscita."
    fi

    if ! venv_funzionante; then
        errore_fatale "L'ambiente virtuale è stato creato, ma non risulta
     utilizzabile oppure non contiene pip."
    fi

    msg_ok "Ambiente virtuale creato"
fi


# Se l'ambiente soddisfa già ESATTAMENTE requirements.txt e pip non
# segnala conflitti, non tocchiamo nulla e non serve neppure la rete.
if requirements_esatti "$PYTHON_VENV" "$REQUISITI_DEST" \
        >/dev/null 2>&1 \
        && "$PYTHON_VENV" -m pip check >/dev/null 2>&1; then

    msg_ok "Dipendenze Python già esatte e coerenti"
else
    msg_nota "Installazione/aggiornamento delle dipendenze Python..."
    msg_nota "Questa operazione può richiedere qualche minuto."

    if ! "$PYTHON_VENV" -m pip install \
            --disable-pip-version-check \
            -r "$REQUISITI_DEST"; then
        errore_fatale "Installazione delle dipendenze Python non riuscita.
     Controlla la connessione a internet e i messaggi di pip qui sopra."
    fi

    if ! "$PYTHON_VENV" -m pip check; then
        errore_fatale "Le dipendenze Python sono state installate,
     ma pip segnala incompatibilità nell'ambiente."
    fi

    if ! requirements_esatti "$PYTHON_VENV" "$REQUISITI_DEST"; then
        errore_fatale "Le versioni installate non corrispondono
     esattamente a requirements.txt."
    fi

    msg_ok "Dipendenze Python installate e verificate"
fi


# Ultimo controllo funzionale Python: i due moduli runtime principali
# devono essere realmente importabili dal Python che eseguirà l'app.
if ! "$PYTHON_VENV" -c 'import PySide6, xlsxwriter' >/dev/null 2>&1; then
    errore_fatale "Le dipendenze risultano installate, ma almeno una
     non è importabile dal Python dell'ambiente virtuale."
fi

msg_ok "Import PySide6 e XlsxWriter: OK"


# =====================================================================
# BLOCCO 4-ter — Verifica del runtime grafico Qt
# =====================================================================

msg_fase "Verifica del runtime grafico Qt"


# Ricaviamo dalla stessa installazione PySide6 il percorso ufficiale
# dei plugin Qt. Evitiamo così percorsi hardcoded dipendenti da Python,
# architettura o versione della libreria.
if ! PLUGIN_QT_DIR="$(
    "$PYTHON_VENV" - <<'PY'
from PySide6.QtCore import QLibraryInfo

print(
    QLibraryInfo.path(
        QLibraryInfo.LibraryPath.PluginsPath
    )
)
PY
)"; then
    errore_fatale "Impossibile determinare la cartella dei plugin Qt."
fi

if [ -z "$PLUGIN_QT_DIR" ] || [ ! -d "$PLUGIN_QT_DIR" ]; then
    errore_fatale "Qt ha restituito una cartella dei plugin non valida:
     $PLUGIN_QT_DIR"
fi

msg_ok "Cartella dei plugin Qt individuata"
msg_nota "$PLUGIN_QT_DIR"


# XCB è il plugin Qt utilizzato per il supporto X11/XWayland.
# Controlliamo il vero file installato da PySide6.
PLUGIN_XCB="$PLUGIN_QT_DIR/platforms/libqxcb.so"

if [ ! -f "$PLUGIN_XCB" ]; then
    errore_fatale "Il plugin Qt/XCB «libqxcb.so» non è stato trovato:
     $PLUGIN_XCB

     L'installazione di PySide6 non può essere considerata completa."
fi

msg_ok "Plugin Qt/XCB «libqxcb.so» presente"


# Se ldd è disponibile, interroghiamo direttamente il plugin reale.
# In questo modo intercettiamo QUALUNQUE libreria dinamica richiesta
# che il sistema non riesca a risolvere, non soltanto libxcb-cursor.
if command -v ldd >/dev/null 2>&1; then
    OUTPUT_LDD="$(ldd "$PLUGIN_XCB" 2>&1 || true)"

    LIBRERIE_MANCANTI="$(
        printf '%s\n' "$OUTPUT_LDD" \
            | awk '/=> not found/ {print $1}' \
            | sort -u
    )"

    if [ -n "$LIBRERIE_MANCANTI" ]; then
        mkdir -p "$CARTELLA_DEST/log" 2>/dev/null || true

        LOG_QT="$CARTELLA_DEST/log/diagnostica_installazione_qt.log"

        {
            printf 'Diagnostica libqxcb.so\n'
            printf '=====================\n\n'
            printf 'Plugin: %s\n\n' "$PLUGIN_XCB"
            printf '%s\n' "$OUTPUT_LDD"
        } > "$LOG_QT" 2>/dev/null || true

        errore_fatale "Il plugin grafico Qt/XCB richiede librerie di sistema
     che non risultano disponibili:

$LIBRERIE_MANCANTI

     Diagnostica salvata in:
     $LOG_QT

     L'installazione viene interrotta prima dell'avvio, così il problema
     può essere corretto senza arrivare a un crash della GUI."
    fi

    msg_ok "Dipendenze native di «libqxcb.so»: tutte risolte"
else
    msg_nota "«ldd» non è disponibile: controllo statico delle librerie saltato."
    msg_nota "Verrà comunque eseguito il controllo funzionale di Qt."
fi


# Il semplice «import PySide6» non inizializza il sistema grafico.
# Creare QApplication, invece, obbliga Qt a caricare realmente il
# proprio plugin di piattaforma. Non mostriamo nessuna finestra.
smoke_test_qt() {
    "$PYTHON_VENV" -c '
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(["postiperfetti-smoke-test"])

widget = QWidget()
widget.resize(16, 16)

print(QGuiApplication.platformName())

widget.close()
app.quit()
'
}


OUTPUT_SMOKE_QT=""

# In una sessione desktop usiamo la piattaforma che Qt sceglierebbe
# davvero quando l'utente avvia PostiPerfetti.
if [ -n "${DISPLAY:-}" ] \
        || [ -n "${WAYLAND_DISPLAY:-}" ] \
        || [ -n "${QT_QPA_PLATFORM:-}" ]; then

    if OUTPUT_SMOKE_QT="$(smoke_test_qt 2>&1)"; then
        PIATTAFORMA_QT="$(
            printf '%s\n' "$OUTPUT_SMOKE_QT" \
                | tail -n 1 \
                | tr -d '\r'
        )"

        msg_ok "Avvio reale di QApplication: OK"
        msg_nota "Piattaforma Qt rilevata: $PIATTAFORMA_QT"
    else
        mkdir -p "$CARTELLA_DEST/log" 2>/dev/null || true

        LOG_QT="$CARTELLA_DEST/log/diagnostica_installazione_qt.log"

        {
            printf 'Smoke test QApplication fallito\n'
            printf '================================\n\n'
            printf '%s\n' "$OUTPUT_SMOKE_QT"
        } > "$LOG_QT" 2>/dev/null || true

        errore_fatale "Qt è installato, ma non riesce a inizializzare
     un'applicazione grafica nella sessione corrente.

     Diagnostica salvata in:
     $LOG_QT

     L'installazione non verrà dichiarata completata."
    fi

else
    # Installazione eseguita senza sessione grafica, per esempio via SSH:
    # possiamo provare il backend offscreen, ma non fingiamo di aver
    # collaudato il vero desktop dell'utente.
    if OUTPUT_SMOKE_QT="$(
        QT_QPA_PLATFORM=offscreen smoke_test_qt 2>&1
    )"; then
        msg_ok "Avvio di QApplication in modalità offscreen: OK"
        msg_nota "Nessuna sessione grafica rilevata:"
        msg_nota "il backend desktop reale non ha potuto essere collaudato."
    else
        mkdir -p "$CARTELLA_DEST/log" 2>/dev/null || true

        LOG_QT="$CARTELLA_DEST/log/diagnostica_installazione_qt.log"

        {
            printf 'Smoke test QApplication offscreen fallito\n'
            printf '========================================\n\n'
            printf '%s\n' "$OUTPUT_SMOKE_QT"
        } > "$LOG_QT" 2>/dev/null || true

        errore_fatale "Qt non riesce a inizializzare nemmeno
     un'applicazione grafica in modalità offscreen.

     Diagnostica salvata in:
     $LOG_QT"
    fi
fi


# Una precedente diagnosi fallita non deve continuare a sembrare attuale
# dopo che tutti i controlli Qt sono stati superati.
rm -f -- "$CARTELLA_DEST/log/diagnostica_installazione_qt.log" \
    2>/dev/null || true

msg_ok "Runtime grafico Qt verificato"


# =====================================================================
# BLOCCO 5 — Integrazione desktop (standard freedesktop.org)
# =====================================================================

if [ "$INTEGRA_MENU" = "1" ]; then
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
ICONA_SORGENTE="$CARTELLA_DEST/risorse/icone/postiperfetti_icon.png"

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
Exec="$LAUNCHER_REALE"
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
else
    FILE_DESKTOP=""
    msg_fase "Integrazione con il menu delle applicazioni"
    msg_nota "Saltata per richiesta di collaudo (POSTIPERFETTI_INTEGRA_MENU=0)."
fi


# =====================================================================
# BLOCCO 6 — Riepilogo finale e avvio facoltativo
# =====================================================================

msg_fase "Installazione completata"

# --- Riepilogo onesto di ciò che è stato fatto ----------------------
printf '\n'
case "$TIPO_INSTALLAZIONE" in
    aggiornamento)
        printf '  %s«%s» è stato aggiornato.%s\n' \
            "$C_TIT" "$NOME_APP" "$C_END"
        printf '  Classi, impostazioni e log sono rimasti intatti.\n'
        ;;
    reinstallazione_con_dati)
        printf '  %s«%s» è stato reinstallato.%s\n' \
            "$C_TIT" "$NOME_APP" "$C_END"
        printf '  I dati conservati dalla precedente installazione sono rimasti intatti.\n'
        ;;
    prima_installazione)
        printf '  %s«%s» è stato installato.%s\n' \
            "$C_TIT" "$NOME_APP" "$C_END"
        ;;
esac
printf '\n'
printf '  Programma installato in:  %s%s%s\n'   "$C_DET" "$CARTELLA_DEST" "$C_END"
if [ -n "$FILE_DESKTOP" ]; then
    printf '  Voce di menu creata in:   %s%s%s\n' "$C_DET" "$FILE_DESKTOP" "$C_END"
else
    printf '  Voce di menu:             %snon creata (modalità collaudo)%s\n' "$C_DET" "$C_END"
fi

# --- Nota onesta sulla comparsa nel menu ----------------------------
# Alcuni ambienti desktop aggiornano il menu solo al successivo
# accesso. Lo diciamo apertamente, così l'utente non si allarma se
# non vede subito l'icona.
if [ -n "$FILE_DESKTOP" ]; then
    printf '\n'
    printf '  %sPer avviare «%s»: cercalo nel menu delle applicazioni.%s\n' "$C_DET" "$NOME_APP" "$C_END"
    printf '  %sSe non compare subito, apparirà al prossimo accesso al sistema.%s\n' "$C_DET" "$C_END"
fi

# L'ambiente Python è già stato preparato e verificato dall'installer:
# il primo avvio non deve più eseguire alcuna installazione obbligatoria.

# --- Offerta di avvio immediato -------------------------------------
# Proponiamo di avviare ora, ma SOLO se siamo in un terminale
# interattivo (se lo script fosse eseguito da pipe, «read» fallirebbe).
# Rispettiamo la risposta: nessun avvio forzato.
if [ -t 0 ] && [ -f "$LAUNCHER" ]; then
    printf '\n'
    printf '  %sVuoi avviare «%s» adesso? [S/n] %s' "$C_TIT" "$NOME_APP" "$C_END"
    if ! read -r risposta; then
        risposta="n"
    fi
    case "$risposta" in
        # Stringa VUOTA (solo Invio) o esplicito sì → avvia.
        # La stringa vuota è ora il default, coerente con [S/n].
        ""|s|S|si|Si|sì|Sì|y|Y)
            printf '\n  Avvio in corso...\n'
            # L'ambiente è già stato preparato dall'installer.
            # Il launcher ne verifica comunque l'integrità e avvia la GUI,
            # che viene poi separata dal terminale.
            "$LAUNCHER"
            ;;
        *)
            printf '\n  Nessun problema: lo troverai nel menu quando vorrai.\n'
            ;;
    esac
fi

printf '\n'

# Fine dello script. Nessun «exit» esplicito: se siamo arrivati fin
# qui senza errori, lo stato di uscita è già 0 (successo).
