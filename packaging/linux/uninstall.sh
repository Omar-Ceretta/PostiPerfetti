#!/usr/bin/env bash
# =====================================================================
# uninstall.sh — Disinstaller di «PostiPerfetti» per Linux
#
# Rimuove i file del programma e l'integrazione desktop SENZA usare sudo.
# Per impostazione predefinita conserva i dati dell'utente:
#   classi/  stato/  log/
#
# Per eliminare anche questi dati:
#   bash uninstall.sh --purge
#
# La cartella di installazione può essere cambiata come nell'installer:
#   POSTIPERFETTI_DEST=~/altra_cartella bash uninstall.sh
# =====================================================================

set -euo pipefail

NOME_APP="PostiPerfetti"

# Se POSTIPERFETTI_DEST è stato fornito esplicitamente, ha sempre
# precedenza. Altrimenti, quando questo script è la copia INSTALLATA
# accanto a postiperfetti.py, ricava automaticamente la propria radice.
# La copia sorgente dentro packaging/linux/ continua invece a usare
# ~/PostiPerfetti come destinazione predefinita.
SCRIPT_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1
    pwd -P
)"

if [ -n "${POSTIPERFETTI_DEST:-}" ]; then
    CARTELLA_DEST="$POSTIPERFETTI_DEST"
elif [ -f "$SCRIPT_DIR/postiperfetti.py" ]; then
    CARTELLA_DEST="$SCRIPT_DIR"
else
    CARTELLA_DEST="$HOME/PostiPerfetti"
fi

PURGE=0
ASSUMI_SI=0

if [ -t 1 ]; then
    C_TIT=$'\e[1;34m'
    C_DET=$'\e[2m'
    C_ERR=$'\e[1;31m'
    C_END=$'\e[0m'
else
    C_TIT=""; C_DET=""; C_ERR=""; C_END=""
fi

msg_fase() { printf '\n%s==>%s %s\n' "$C_TIT" "$C_END" "$*"; }
msg_ok()   { printf '  %s✔%s %s\n' "$C_TIT" "$C_END" "$*"; }
msg_nota() { printf '  %s%s%s\n' "$C_DET" "$*" "$C_END"; }
errore_fatale() {
    printf '\n  %s✘ %s%s\n\n' "$C_ERR" "$*" "$C_END" >&2
    exit 1
}

uso() {
    cat <<EOF
Uso:
  bash uninstall.sh [--purge] [--yes]

Opzioni:
  --purge   elimina anche i dati dell'utente in classi/, stato/ e log/
  --yes     non chiede conferma interattiva
  -h, --help
            mostra questo aiuto

Variabile facoltativa:
  POSTIPERFETTI_DEST=/percorso
            indica un'installazione diversa da ~/PostiPerfetti
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --purge)
            PURGE=1
            ;;
        --yes|-y)
            ASSUMI_SI=1
            ;;
        -h|--help)
            uso
            exit 0
            ;;
        *)
            errore_fatale "Opzione non riconosciuta: $1
     Usa: bash uninstall.sh --help"
            ;;
    esac
    shift
done

if [ "$(id -u)" -eq 0 ]; then
    errore_fatale "Non eseguire questo disinstaller con sudo o come root.
     «$NOME_APP» è installato nella cartella personale dell'utente."
fi

# Protezioni minime contro destinazioni pericolose o vuote.
if [ -z "$CARTELLA_DEST" ] || [ "$CARTELLA_DEST" = "/" ] || [ "$CARTELLA_DEST" = "$HOME" ]; then
    errore_fatale "Percorso di installazione non valido o troppo pericoloso:
     $CARTELLA_DEST"
fi

# Riconosciamo l'installazione tramite due elementi specifici del programma.
# Basta che ne esista almeno uno: così il disinstaller può ripulire anche
# un'installazione parzialmente danneggiata.
if [ ! -f "$CARTELLA_DEST/postiperfetti.py" ] && \
   [ ! -f "$CARTELLA_DEST/moduli/postiperfetti_launcher.py" ]; then
    errore_fatale "Non trovo un'installazione riconoscibile di «$NOME_APP» in:
     $CARTELLA_DEST

     Nessun file è stato rimosso."
fi

printf '\n%s=====================================%s\n' "$C_TIT" "$C_END"
printf '%s  Disinstallazione di «%s»%s\n' "$C_TIT" "$NOME_APP" "$C_END"
printf '%s=====================================%s\n' "$C_TIT" "$C_END"

msg_nota "Installazione individuata in: $CARTELLA_DEST"

if [ "$PURGE" -eq 1 ]; then
    msg_nota "Modalità PURGE: saranno eliminati anche classi, impostazioni e log."
else
    msg_nota "Classi, impostazioni e log verranno CONSERVATI."
fi

if [ "$ASSUMI_SI" -ne 1 ]; then
    if [ ! -t 0 ]; then
        errore_fatale "La conferma interattiva non è disponibile.
     Rilancia con --yes se vuoi procedere senza domanda."
    fi

    printf '\n  %sProcedere con la disinstallazione? [s/N] %s' "$C_TIT" "$C_END"
    read -r risposta || risposta=""
    case "$risposta" in
        s|S|si|Si|sì|Sì|y|Y)
            ;;
        *)
            printf '\n  Operazione annullata. Nessun file è stato rimosso.\n\n'
            exit 0
            ;;
    esac
fi

msg_fase "Rimozione dell'integrazione desktop"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DIR_APPLICAZIONI="$DATA_HOME/applications"
DIR_ICONA="$DATA_HOME/icons/hicolor/256x256/apps"
FILE_DESKTOP="$DIR_APPLICAZIONI/postiperfetti.desktop"
ICONA_INSTALLATA="$DIR_ICONA/postiperfetti.png"

# Un solo nome .desktop e una sola icona sono condivisi dall'utente.
# Prima di cancellarli verifichiamo quindi che la voce di menu punti
# DAVVERO all'installazione che stiamo rimuovendo.
EXEC_ATTESO="Exec=\"$CARTELLA_DEST/moduli/postiperfetti_launcher.py\""
PATH_ATTESO="Path=$CARTELLA_DEST"
INTEGRAZIONE_RIMOSSA=0

if [ -f "$FILE_DESKTOP" ] \
        && grep -Fqx -- "$EXEC_ATTESO" "$FILE_DESKTOP" \
        && grep -Fqx -- "$PATH_ATTESO" "$FILE_DESKTOP"; then

    rm -f -- "$FILE_DESKTOP" "$ICONA_INSTALLATA"
    INTEGRAZIONE_RIMOSSA=1
    msg_ok "Voce di menu e icona appartenenti a questa installazione rimosse"
else
    if [ -f "$FILE_DESKTOP" ]; then
        msg_nota "La voce di menu esistente appartiene a un'altra installazione:"
        msg_nota "  $FILE_DESKTOP"
        msg_nota "Non verrà modificata."
    else
        msg_nota "Nessuna voce di menu appartenente a questa installazione da rimuovere."
    fi

    if [ -f "$ICONA_INSTALLATA" ]; then
        msg_nota "L'icona condivisa viene conservata per sicurezza."
    fi
fi

# Aggiorniamo le cache soltanto se abbiamo davvero rimosso
# l'integrazione desktop di questa installazione.
if [ "$INTEGRAZIONE_RIMOSSA" -eq 1 ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DIR_APPLICAZIONI" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
    fi
    if command -v kbuildsycoca6 >/dev/null 2>&1; then
        kbuildsycoca6 >/dev/null 2>&1 || true
    fi
fi

msg_fase "Rimozione dei file del programma"

# Lista positiva: cancelliamo solo ciò che appartiene sicuramente
# all'installazione di PostiPerfetti. Eventuali file estranei lasciati
# per errore nella stessa cartella non vengono toccati.
rm -rf -- \
    "$CARTELLA_DEST/moduli" \
    "$CARTELLA_DEST/risorse" \
    "$CARTELLA_DEST/.venv" \
    "$CARTELLA_DEST/__pycache__"

rm -f -- \
    "$CARTELLA_DEST/postiperfetti.py" \
    "$CARTELLA_DEST/requirements.txt" \
    "$CARTELLA_DEST/LICENSE" \
    "$CARTELLA_DEST/uninstall.sh"

msg_ok "Programma e ambiente virtuale rimossi"

if [ "$PURGE" -eq 1 ]; then
    msg_fase "Rimozione dei dati dell'utente"
    rm -rf -- \
        "$CARTELLA_DEST/classi" \
        "$CARTELLA_DEST/stato" \
        "$CARTELLA_DEST/log"
    msg_ok "Classi, impostazioni e log rimossi"
else
    printf '\n'
    msg_nota "Dati conservati:"
    [ -d "$CARTELLA_DEST/classi" ] && msg_nota "  $CARTELLA_DEST/classi"
    [ -d "$CARTELLA_DEST/stato" ]  && msg_nota "  $CARTELLA_DEST/stato"
    [ -d "$CARTELLA_DEST/log" ]    && msg_nota "  $CARTELLA_DEST/log"
fi

# Rimuoviamo la directory principale solo se è rimasta davvero vuota.
# Se contiene dati conservati o file estranei, rmdir fallisce senza danni.
rmdir "$CARTELLA_DEST" 2>/dev/null || true

printf '\n%s=====================================%s\n' "$C_TIT" "$C_END"
printf '%s  Disinstallazione completata%s\n' "$C_TIT" "$C_END"
printf '%s=====================================%s\n' "$C_TIT" "$C_END"

if [ "$PURGE" -eq 0 ] && [ -d "$CARTELLA_DEST" ]; then
    printf '\n'
    msg_nota "La cartella $CARTELLA_DEST è stata mantenuta perché contiene"
    msg_nota "i dati dell'utente o altri file non appartenenti al programma."
fi

printf '\n'
