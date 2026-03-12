"""
tema.py — Sistema di gestione del tema colori (scuro/chiaro).

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
    },
}

# Tema attivo corrente: "scuro" o "chiaro".
# Modificato dal toggle nella toolbar (Fase 6).
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
