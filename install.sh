#!/usr/bin/env bash
# =============================================================
# install.sh — Installer di «PostiPerfetti» per Linux.
# Scarica il sorgente da GitHub, lo installa in ~/PostiPerfetti,
# integra icona e voce di menu. MAI richiesti privilegi di root.
# =============================================================

# BLOCCO 0 — Impostazioni di sicurezza e costanti
#   set -euo pipefail (lo script si ferma al primo errore, niente
#   variabili non definite, niente errori mascherati nelle pipe)
#   URL_TARBALL="https://github.com/Omar-Ceretta/PostiPerfetti/archive/refs/heads/main.tar.gz"
#   (nessuna VERSIONE: si scarica sempre lo stato attuale del ramo
#   principale — modello "rilascio unico, aggiornato per sovrascrittura")
#   CARTELLA_DEST="$HOME/PostiPerfetti"

# BLOCCO 1 — Controlli preliminari (nessuna modifica al sistema)
#   • python3 presente? (indispensabile al launcher)
#   • wget O curl presente? tar presente?
#   • Se manca qualcosa: messaggio chiaro con il comando di
#     installazione per Ubuntu/Fedora/Arch, e uscita pulita.

# BLOCCO 2 — Download in cartella temporanea
#   • mktemp -d + trap di pulizia: la cartella temporanea viene
#     rimossa SEMPRE, anche se lo script fallisce a metà
#   • scarica il tarball e ne verifica l'esito

# BLOCCO 3 — Estrazione e individuazione del sorgente
#   • tar xzf nell'area temporanea
#   • individua dinamicamente la cartella di primo livello

# BLOCCO 4 — Installazione o aggiornamento in ~/PostiPerfetti
#   • prima installazione: copia tutto
#   • cartella già esistente (AGGIORNAMENTO): copia tutto TRANNE
#     dati/ — le classi e la configurazione dell'utente restano
#     intatte e non vengono MAI sovrascritte (il .venv esistente
#     resta anch'esso al suo posto)
#   • chmod +x sul launcher (gli archivi non conservano i permessi)

# BLOCCO 5 — Integrazione desktop (standard freedesktop)
#   • icona (256×256, verificata) →
#     ~/.local/share/icons/hicolor/256x256/apps/postiperfetti.png
#     sorgente: dati/icone/postiperfetti_icon.png
#   • genera il .desktop con i percorsi REALI calcolati →
#     ~/.local/share/applications/postiperfetti.desktop
#   • refresh dei database: update-desktop-database,
#     gtk-update-icon-cache, kbuildsycoca6 — ciascuno eseguito
#     SOLO se presente sul sistema, in silenzio se assente

# BLOCCO 6 — Riepilogo e avvio facoltativo
#   • riepilogo onesto di ciò che è stato fatto
#   • offre di avviare subito il programma: al primo avvio sarà
#     il launcher a creare venv e dipendenze, coi suoi dialoghi
#   • nota: "se l'icona non compare subito nel menu, apparirà
#     al prossimo accesso" (verità sulle cache dei desktop pigri)
