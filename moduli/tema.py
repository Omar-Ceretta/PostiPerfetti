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
    Sistema di gestione del tema colori (scuro/chiaro).
    Questo modulo è importato da assegnazione-posti.py e da editor_studenti.py.
    Tenerlo separato evita circular import e centralizza la gestione del tema.
"""

# =============================================================================
# DIZIONARIO SEMANTICO DEI COLORI
# =============================================================================
# Ogni chiave descrive il RUOLO del colore (non il suo aspetto).
# Ogni voce ha due versioni: "scuro" (default) e "chiaro".
# Usare sempre C("nome") per accedere ai colori — mai valori hex diretti.
# =============================================================================

TEMI = {

    # ─── TEMA SCURO (default) ─────────────────────────────────────────────
    "scuro": {

        # --- Sfondi principali ---
        "sfondo_principale":     "#2b2b2b",
        "sfondo_pannello":       "#353535",
        "sfondo_input":          "#404040",
        "sfondo_input_alt":      "#505050",
        "sfondo_testo_area":     "#1e1e1e",
        "sfondo_scroll":         "#2d2d2d",
        "sfondo_tab_normale":    "#404040",
        "sfondo_header_tabella": "#404040",

        # --- Bordi ---
        "bordo_normale":         "#555555",
        "bordo_leggero":         "#666666",
        "bordo_focus":           "#4CAF50",

        # --- Testi ---
        "testo_principale":      "#ffffff",
        "testo_secondario":      "#cccccc",
        "testo_disabilitato":    "#666666",
        "testo_placeholder":     "#888888",
        "testo_grigio":          "gray",

        # --- Bottoni generici ---
        "btn_sfondo":            "#404040",
        "btn_hover":             "#505050",
        "btn_premuto":           "#333333",
        "btn_disabilitato_sf":   "#2a2a2a",
        "btn_disabilitato_txt":  "#666666",

        # --- Bottoni specifici: pannello controlli ---
        # Indaco (usato da Istruzioni e bottone ?)
        "btn_indaco_bg":         "#5C6BC0",
        "btn_indaco_hover":      "#3F51B5",
        # Ambra (toggle tema scuro/chiaro)
        "btn_tema_bg":           "#F57F17",
        "btn_tema_hover":        "#E65100",
        "btn_tema_txt":          "#ffffff",
        # Grigio-blu (bottone crediti 💬)
        "btn_crediti_bg":        "#546E7A",
        "btn_crediti_hover":     "#37474F",

        # --- Bottone avvia assegnazione ---
        "btn_avvia_bg":          "#4CAF50",
        "btn_avvia_hover":       "#45a049",
        "btn_avvia_disabled_bg": "#cccccc",
        "btn_avvia_disabled_txt": "#666666",

        # --- Bottoni pannello risultati ---
        # Salva assegnazione (verde scuro)
        "btn_salva_bg":          "#2E7D32",
        "btn_salva_hover":       "#1B5E20",
        # Esporta Excel (azzurro)
        "btn_excel_bg":          "#2196F3",
        "btn_excel_hover":       "#1976D2",
        # Esporta TXT / Statistiche (arancione)
        "btn_export_bg":         "#FF9800",
        "btn_export_hover":      "#F57C00",
        # Stato disabilitato condiviso (salva, excel, txt)
        "btn_azione_disabled_bg":  "#9E9E9E",
        "btn_azione_disabled_txt": "#616161",

        # --- Bottoni spinbox +/− (file di banchi, posti per fila) ---
        "btn_spinbox_bg":        "#505050",
        "btn_spinbox_txt":       "#ffffff",   # Bianco su sfondo scuro
        "btn_spinbox_bordo":     "#666666",
        "btn_meno_hover_bg":     "#f44336",
        "btn_meno_hover_bordo":  "#c62828",
        "btn_piu_hover_bg":      "#4CAF50",
        "btn_piu_hover_bordo":   "#2E7D32",

        # --- Accento verde ---
        "accento":               "#4CAF50",
        "accento_hover":         "#45a049",
        "accento_scuro":         "#2E7D32",
        "accento_molto_scuro":   "#1B5E20",

        # --- Griglia aula ---
        "banco_occupato_sf":     "#E8F5E8",
        "banco_occupato_bordo":  "#4CAF50",
        "banco_occupato_txt":    "#2b2b2b",
        "banco_libero_sf":       "#f9f9f9",
        "banco_libero_bordo":    "#cccccc",
        "cattedra_sf":           "#FFF3E0",
        "cattedra_bordo":        "#FF9800",
        "lim_sf":                "#E3F2FD",
        "lim_bordo":             "#2196F3",
        "lavagna_sf":            "#EFEBE9",
        "lavagna_bordo":         "#795548",

        # --- Label di stato (pannello sinistro) ---
        # Attenzione: sfondo arancione scuro (genere da completare, file in Editor)
        "label_attenzione_bg":     "#E65100",
        "label_attenzione_bordo":  "#FF9800",
        "label_attenzione_txt":    "#ffffff",
        # Successo: sfondo verde scuro (classe pronta per assegnazione)
        "label_successo_bg":       "#2E7D32",
        "label_successo_bordo":    "#4CAF50",
        "label_successo_txt":      "#ffffff",
        # Testo stato OK: verde per label_status in basso a sinistra
        "testo_stato_ok":          "#66BB6A",
        # Caricato: sfondo ocra (studenti caricati e pronti per assegnazione)
        "label_caricato_bg":       "#B8860B",
        "label_caricato_bordo":    "#DAA520",
        "label_caricato_txt":      "#ffffff",

        # --- Editor: struttura generale ---
        "editor_scroll_sf":      "#2d2d2d",
        "editor_titolo_txt":     "#e0e0e0",
        "editor_info_txt":       "#bababa",
        "editor_sep":            "#555555",

        # --- Editor: bottone "Aggiungi incompatibilità" ---
        # Tema scuro: sfondo marrone scuro, testo arancio tenue
        "editor_btn_incomp_sf":    "#5d4037",
        "editor_btn_incomp_txt":   "#ffccbc",
        "editor_btn_incomp_hover": "#6d4c41",

        # --- Editor: bottone "Aggiungi affinità" ---
        # Tema scuro: sfondo verde molto scuro, testo verde tenue
        "editor_btn_aff_sf":       "#1b5e20",
        "editor_btn_aff_txt":      "#c8e6c9",
        "editor_btn_aff_hover":    "#2e7d32",

        # --- Editor: schede studente per genere ---
        "scheda_M_bordo":        "#42A5F5",
        "scheda_M_titolo_sf":    "#1565C0",
        "scheda_M_titolo_txt":   "#E3F2FD",
        "scheda_M_sf":           "#2C3E50",
        "scheda_F_bordo":        "#EC407A",
        "scheda_F_titolo_sf":    "#AD1457",
        "scheda_F_titolo_txt":   "#FCE4EC",
        "scheda_F_sf":           "#3E2C3E",
        "scheda_X_bordo":        "#FF9800",
        "scheda_X_titolo_sf":    "#E65100",
        "scheda_X_titolo_txt":   "#FFF3E0",
        "scheda_X_sf":           "#3E3428",

        # --- Editor: ComboBox vincoli (placeholder vs valore valido) ---
        "combo_ph_bordo":        "#FF9800",
        "combo_ph_sf":           "#3e3529",
        "combo_ph_txt":          "#FFB74D",
        "combo_ok_bordo":        "#555555",
        "combo_ok_sf":           "#404040",
        "combo_ok_txt":          "#e0e0e0",

        # --- Editor: ComboBox genere con placeholder "---" ---
        "genere_ph_bordo":       "#FF9800",
        "genere_ph_sf":          "#4a3000",

        # Bottone azione primaria (carica file, avvia flussi)
        "btn_primario_sf":       "#00695C",  # Verde-teal scuro
        "btn_primario_hover":    "#004D40",  # Verde-teal molto scuro
        "btn_primario_txt":      "#ffffff",

        # Colore testo "informativo/accentato"
        "testo_info":            "#4ECDC4",
        # Colore testo secondario leggibile: grigio chiaro sul scuro
        "testo_label_sec":       "#cccccc",

        # --- Bottoni generici per dialog e sotto-finestre ---
        # Rosso (elimina, rimuovi)
        "btn_rosso_bg":            "#d32f2f",
        "btn_rosso_hover":         "#b71c1c",
        # Blu scuro (dettagli, salva report)
        "btn_blu_bg":              "#1565c0",
        "btn_blu_hover":           "#0d47a1",
        # Grigio (chiudi, neutro)
        "btn_grigio_bg":           "#757575",
        "btn_grigio_hover":        "#616161",
        # Viola (aggiungi vincolo nell'editor)
        "btn_viola_bg":            "#6a1b9a",
        "btn_viola_hover":         "#4a148c",
        # Arancione (azione attenzione nell'editor)
        "btn_arancione_bg":        "#E65100",
        "btn_arancione_hover":     "#BF360C",
        # Stato disabilitato per bottoni colorati
        "btn_colore_disabled_sf":  "#616161",
        "btn_colore_disabled_txt": "#9e9e9e",

        # --- Testi semantici ---
        "testo_ocra":              "#CC8800",   # Evidenziazione coppie riutilizzate
        "testo_incomp":            "#ef5350",   # Label incompatibilità (editor)
        "testo_affinita":          "#66bb6a",   # Label affinità (editor)
        "testo_arancione":         "#FF9800",   # Avvisi, trio, prima fila
        "testo_negativo":          "#FF6B6B",   # Coppie mai formate (statistiche)
        "banner_formato_txt":      "#1a1a1a",   # Testo su banner arancione

        # --- Label errore (posti insufficienti) ---
        "label_errore_bg":         "#FF4444",
        "label_errore_bordo":      "#CC0000",

        # --- Selezione ComboBox ---
        "selezione_testo":         "#ffffff",

        # --- Editor: errore caricamento ---
        "errore_bordo":            "#E53935",
        "errore_titolo_sf":        "#B71C1C",
        "errore_titolo_txt":       "#FFFFFF",

        # --- Editor: anteprima file ---
        "anteprima_sf":            "#1e1e1e",
        "anteprima_txt":           "#d4d4d4",
        "testo_info_grigio":       "#9e9e9e",
    },

    # ─── TEMA CHIARO ──────────────────────────────────────────────────────
    "chiaro": {

        # --- Sfondi principali ---
        "sfondo_principale":     "#f0f2f5",
        "sfondo_pannello":       "#ffffff",
        "sfondo_input":          "#ffffff",
        "sfondo_input_alt":      "#e8e8e8",
        "sfondo_testo_area":     "#fafafa",
        "sfondo_scroll":         "#f0f0f0",
        "sfondo_tab_normale":    "#e0e0e0",
        "sfondo_header_tabella": "#e8e8e8",

        # --- Bordi ---
        "bordo_normale":         "#cccccc",
        "bordo_leggero":         "#bbbbbb",
        "bordo_focus":           "#2E7D32",

        # --- Testi ---
        "testo_principale":      "#212121",
        "testo_secondario":      "#555555",
        "testo_disabilitato":    "#9e9e9e",
        "testo_placeholder":     "#9e9e9e",
        "testo_grigio":          "#757575",

        # --- Bottoni generici ---
        "btn_sfondo":            "#e0e0e0",
        "btn_hover":             "#bdbdbd",
        "btn_premuto":           "#9e9e9e",
        "btn_disabilitato_sf":   "#f5f5f5",
        "btn_disabilitato_txt":  "#9e9e9e",

        # --- Bottoni specifici: pannello controlli ---
        # Indaco (usato da Istruzioni e bottone ?)
        # Su sfondo chiaro: stessi colori saturi funzionano bene
        "btn_indaco_bg":         "#5C6BC0",
        "btn_indaco_hover":      "#3949AB",   # Leggermente più scuro per visibilità hover
        # Ambra (toggle tema scuro/chiaro)
        "btn_tema_bg":           "#F57F17",
        "btn_tema_hover":        "#E65100",
        "btn_tema_txt":          "#1a1a1a",
        # Grigio-blu (bottone crediti 💬)
        "btn_crediti_bg":        "#607D8B",   # Leggermente più chiaro per contrasto su bianco
        "btn_crediti_hover":     "#455A64",

        # --- Bottone avvia assegnazione ---
        "btn_avvia_bg":          "#43A047",   # Verde leggermente più scuro su bianco
        "btn_avvia_hover":       "#388E3C",
        "btn_avvia_disabled_bg": "#E0E0E0",   # Più scuro di #ccc per non confondersi col bianco
        "btn_avvia_disabled_txt": "#9E9E9E",

        # --- Bottoni pannello risultati ---
        # Salva assegnazione (verde scuro — stesso, buon contrasto su bianco)
        "btn_salva_bg":          "#2E7D32",
        "btn_salva_hover":       "#1B5E20",
        # Esporta Excel (azzurro)
        "btn_excel_bg":          "#1E88E5",   # Leggermente più scuro per leggibilità
        "btn_excel_hover":       "#1565C0",
        # Esporta TXT / Statistiche (arancione)
        "btn_export_bg":         "#FB8C00",   # Leggermente più scuro su sfondo chiaro
        "btn_export_hover":      "#EF6C00",
        # Stato disabilitato condiviso (salva, excel, txt)
        "btn_azione_disabled_bg":  "#BDBDBD",  # Più visibile su sfondo bianco
        "btn_azione_disabled_txt": "#757575",

        # --- Bottoni spinbox +/− (file di banchi, posti per fila) ---
        "btn_spinbox_bg":        "#E0E0E0",   # Grigio chiaro (vs #505050 del tema scuro)
        "btn_spinbox_txt":       "#212121",   # Testo scuro su sfondo chiaro
        "btn_spinbox_bordo":     "#BDBDBD",   # Bordo più chiaro
        "btn_meno_hover_bg":     "#EF5350",   # Rosso leggermente più chiaro
        "btn_meno_hover_bordo":  "#D32F2F",
        "btn_piu_hover_bg":      "#4CAF50",
        "btn_piu_hover_bordo":   "#2E7D32",

        # --- Accento verde ---
        "accento":               "#4CAF50",
        "accento_hover":         "#45a049",
        "accento_scuro":         "#2E7D32",
        "accento_molto_scuro":   "#1B5E20",

        # --- Griglia aula ---
        "banco_occupato_sf":     "#C8E6C9",
        "banco_occupato_bordo":  "#388E3C",
        "banco_occupato_txt":    "#1a1a1a",
        "banco_libero_sf":       "#eeeeee",
        "banco_libero_bordo":    "#aaaaaa",
        "cattedra_sf":           "#FFE0B2",
        "cattedra_bordo":        "#EF6C00",
        "lim_sf":                "#BBDEFB",
        "lim_bordo":             "#1565C0",
        "lavagna_sf":            "#D7CCC8",
        "lavagna_bordo":         "#4E342E",

        # --- Label di stato (pannello sinistro) ---
        # Attenzione: sfondo arancione scuro (genere da completare, file in Editor)
        "label_attenzione_bg":     "#E65100",
        "label_attenzione_bordo":  "#FF9800",
        "label_attenzione_txt":    "#ffffff",
        # Successo: sfondo verde scuro (classe pronta per assegnazione)
        "label_successo_bg":       "#2E7D32",
        "label_successo_bordo":    "#4CAF50",
        "label_successo_txt":      "#ffffff",
        # Testo stato OK: verde per label_status in basso a sinistra
        "testo_stato_ok":          "#4CAF50",
        # Caricato: sfondo ocra (studenti caricati e pronti per assegnazione)
        "label_caricato_bg":       "#B8860B",
        "label_caricato_bordo":    "#DAA520",
        "label_caricato_txt":      "#ffffff",

        # --- Editor: struttura generale ---
        "editor_scroll_sf":      "#f0f0f0",
        "editor_titolo_txt":     "#212121",
        "editor_info_txt":       "#424242",
        "editor_sep":            "#cccccc",

        # --- Editor: bottone "Aggiungi incompatibilità" ---
        # Tema chiaro: sfondo arancio tenue, testo marrone scuro
        "editor_btn_incomp_sf":    "#ffccbc",
        "editor_btn_incomp_txt":   "#bf360c",
        "editor_btn_incomp_hover": "#ffab91",

        # --- Editor: bottone "Aggiungi affinità" ---
        # Tema chiaro: sfondo verde tenue, testo verde scuro
        "editor_btn_aff_sf":       "#c8e6c9",
        "editor_btn_aff_txt":      "#1b5e20",
        "editor_btn_aff_hover":    "#a5d6a7",

        # --- Editor: schede studente per genere ---
        "scheda_M_bordo":        "#1565C0",
        "scheda_M_titolo_sf":    "#1565C0",
        "scheda_M_titolo_txt":   "#ffffff",
        "scheda_M_sf":           "#E3F2FD",
        "scheda_F_bordo":        "#C2185B",
        "scheda_F_titolo_sf":    "#AD1457",
        "scheda_F_titolo_txt":   "#ffffff",
        "scheda_F_sf":           "#FCE4EC",
        "scheda_X_bordo":        "#E65100",
        "scheda_X_titolo_sf":    "#E65100",
        "scheda_X_titolo_txt":   "#ffffff",
        "scheda_X_sf":           "#FFF3E0",

        # --- Editor: ComboBox vincoli ---
        "combo_ph_bordo":        "#FF9800",
        "combo_ph_sf":           "#FFF8E1",
        "combo_ph_txt":          "#E65100",
        "combo_ok_bordo":        "#cccccc",
        "combo_ok_sf":           "#ffffff",
        "combo_ok_txt":          "#212121",

        # --- Editor: ComboBox genere con placeholder "---" ---
        "genere_ph_bordo":       "#FF9800",
        "genere_ph_sf":          "#FFF8E1",

        # Bottone azione primaria
        "btn_primario_sf":       "#00897B",  # Verde-teal medio
        "btn_primario_hover":    "#00695C",  # Verde-teal scuro
        "btn_primario_txt":      "#ffffff",

        # Sul tema chiaro: blu scuro leggibile al posto del turchese
        "testo_info":            "#1565C0",
        # Testo secondario leggibile sul bianco
        "testo_label_sec":       "#424242",

        # --- Bottoni generici per dialog e sotto-finestre ---
        "btn_rosso_bg":            "#d32f2f",
        "btn_rosso_hover":         "#b71c1c",
        "btn_blu_bg":              "#1565c0",
        "btn_blu_hover":           "#0d47a1",
        "btn_grigio_bg":           "#757575",
        "btn_grigio_hover":        "#616161",
        "btn_viola_bg":            "#6a1b9a",
        "btn_viola_hover":         "#4a148c",
        "btn_arancione_bg":        "#E65100",
        "btn_arancione_hover":     "#BF360C",
        # Disabled più chiaro per sfondo bianco
        "btn_colore_disabled_sf":  "#BDBDBD",
        "btn_colore_disabled_txt": "#757575",

        # --- Testi semantici (scuriti per leggibilità su bianco) ---
        "testo_ocra":              "#CC8800",
        "testo_incomp":            "#D32F2F",   # Rosso più scuro su bianco
        "testo_affinita":          "#2E7D32",   # Verde più scuro su bianco
        "testo_arancione":         "#E65100",   # Arancione più scuro su bianco
        "testo_negativo":          "#D32F2F",   # Rosso più scuro su bianco
        "banner_formato_txt":      "#1a1a1a",

        # --- Label errore ---
        "label_errore_bg":         "#FF4444",
        "label_errore_bordo":      "#CC0000",

        # --- Selezione ---
        "selezione_testo":         "#ffffff",

        # --- Editor: errore caricamento ---
        "errore_bordo":            "#E53935",
        "errore_titolo_sf":        "#B71C1C",
        "errore_titolo_txt":       "#FFFFFF",

        # --- Editor: anteprima (invertita rispetto al tema scuro) ---
        "anteprima_sf":            "#fafafa",
        "anteprima_txt":           "#1a1a1a",
        "testo_info_grigio":       "#757575",
    },
}

# Tema attivo corrente: "scuro" o "chiaro".
# Modificato dal toggle nella toolbar.
# Salvato e caricato da config.json.
TEMA_ATTIVO = "scuro"


def imposta_tema(nome: str):
    """
    Cambia il tema attivo. Chiamare prima di ridisegnare i widget.
    Args:
        nome: "scuro" o "chiaro"
    """
    global TEMA_ATTIVO
    if nome in TEMI:
        TEMA_ATTIVO = nome


def get_tema() -> str:
    """Restituisce il nome del tema attivo ("scuro" o "chiaro")."""
    return TEMA_ATTIVO


def C(nome_colore: str) -> str:
    """
    Restituisce il colore del tema attivo per la chiave semantica indicata.

    Uso:  C("sfondo_principale")  →  "#2b2b2b"  (tema scuro)
                                   →  "#f0f2f5"  (tema chiaro)
    """
    return TEMI[TEMA_ATTIVO][nome_colore]
