# -*- coding: utf-8 -*-
"""
tema.py — palette semantica dei temi scuro e chiaro.

Le stesse chiavi identificano gli stessi ruoli visivi nelle due palette. Il
resto del programma legge i colori tramite ``C()``, senza dipendere dai valori
esadecimali né dai componenti dell’interfaccia.

Parte di «PostiPerfetti». Autore: Omar Ceretta. Licenza: GNU GPLv3.
"""


# Ogni chiave deve comparire in entrambe le palette con lo stesso significato.
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
        "drag_target_bordo":     "#FF9800",

        # --- Testi ---
        "testo_principale":      "#ffffff",
        "testo_secondario":      "#cccccc",
        "testo_disabilitato":    "#666666",
        "testo_placeholder":     "#B0B0B0",
        "testo_grigio":          "#B0B0B0",

        # --- Bottoni generici ---
        "btn_sfondo":            "#404040",
        "btn_hover":             "#505050",
        "btn_premuto":           "#333333",
        "btn_disabilitato_sf":   "#2a2a2a",
        "btn_disabilitato_txt":  "#999999",

        # --- Bottoni specifici: pannello controlli ---

        "btn_indaco_bg":         "#5C6BC0",
        "btn_indaco_hover":      "#3F51B5",
        "btn_indaco_txt":        "#ffffff",
        "btn_indaco_bordo":      "#5C6BC0",

        "btn_tema_bg":           "#F57F17",
        "btn_tema_hover":        "#E65100",
        "btn_tema_txt":          "#ffffff",
        "btn_tema_bordo":        "#F57F17",

        "btn_crediti_bg":        "#546E7A",
        "btn_crediti_hover":     "#37474F",
        "btn_crediti_txt":       "#ffffff",
        "btn_crediti_bordo":     "#546E7A",

        # --- Bottone avvia assegnazione ---
        "btn_avvia_bg":          "#4CAF50",
        "btn_avvia_hover":       "#45a049",
        "btn_avvia_txt":         "#ffffff",
        "btn_avvia_bordo":       "#4CAF50",
        "btn_avvia_disabled_bg": "#cccccc",
        "btn_avvia_disabled_txt": "#4A4A4A",
        "btn_avvia_disabled_bordo": "#cccccc",

        # --- Bottoni pannello risultati ---

        "btn_salva_bg":          "#2E7D32",
        "btn_salva_hover":       "#1B5E20",
        "btn_salva_txt":         "#ffffff",
        "btn_salva_bordo":       "#2E7D32",

        "btn_excel_bg":          "#2196F3",
        "btn_excel_hover":       "#1976D2",
        "btn_excel_txt":         "#ffffff",
        "btn_excel_bordo":       "#2196F3",

        "btn_export_bg":         "#FF9800",
        "btn_export_hover":      "#F57C00",
        "btn_export_txt":        "#ffffff",
        "btn_export_bordo":      "#FF9800",

        "btn_statistiche_export_bg":    "#34495E",
        "btn_statistiche_export_hover": "#405A73",
        "btn_statistiche_export_txt":   "#EAF2F8",
        "btn_statistiche_export_bordo": "#5D7891",

        "btn_azione_disabled_bg":    "#9E9E9E",
        "btn_azione_disabled_txt":   "#616161",
        "btn_azione_disabled_bordo": "#9E9E9E",

        # --- Bottoni spinbox +/− (file di banchi, posti per fila) ---
        "btn_spinbox_bg":        "#505050",
        "btn_spinbox_txt":       "#ffffff",
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

        "label_attenzione_bg":     "#E65100",
        "label_attenzione_bordo":  "#FF9800",
        "label_attenzione_txt":    "#ffffff",


        "label_successo_bg":       "#254A2D",
        "label_successo_bordo":    "#4F7F59",
        "label_successo_txt":      "#E8F5E9",

        "testo_stato_ok":          "#66BB6A",


        "label_caricato_bg":       "#254A2D",
        "label_caricato_bordo":    "#4F7F59",
        "label_caricato_txt":      "#E8F5E9",


        "label_capienza_bg":       "#3B434B",
        "label_capienza_bordo":    "#66727D",
        "label_capienza_txt":      "#E5E7EB",


        "vincoli_riepilogo_bg":    "#454545",
        "vincoli_riepilogo_bordo": "#565656",

        # --- Editor: struttura generale ---
        "editor_scroll_sf":      "#2d2d2d",
        "editor_titolo_txt":     "#e0e0e0",
        "editor_info_txt":       "#bababa",
        "editor_sep":            "#555555",

        # --- Editor: bottone "Aggiungi incompatibilità" ---

        "editor_btn_incomp_sf":    "#5d4037",
        "editor_btn_incomp_txt":   "#ffccbc",
        "editor_btn_incomp_hover": "#6d4c41",

        # --- Editor: bottone "Aggiungi affinità" ---

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

        # --- Editor: ComboBox vincoli ---


        "combo_ph_bordo":             "#FF9800",
        "combo_ph_txt":               "#FFB74D",

        "combo_incomp_bordo":         "#A1887F",
        "combo_incomp_sf":            "#5D4037",
        "combo_incomp_txt":           "#FFF3EE",
        "combo_incomp_selezione_sf":  "#795548",

        "combo_aff_bordo":            "#66A56A",
        "combo_aff_sf":               "#1B5E20",
        "combo_aff_txt":              "#F1FFF3",
        "combo_aff_selezione_sf":     "#2E7D32",

        # --- Editor: ComboBox genere con placeholder "---" ---
        "genere_ph_bordo":       "#FF9800",
        "genere_ph_sf":          "#4a3000",


        "btn_primario_sf":       "#00695C",
        "btn_primario_hover":    "#004D40",
        "btn_primario_txt":      "#ffffff",

        # --- Editor: barra file e azioni di visualizzazione ---
        "editor_btn_cartella_bg":     "#00695C",
        "editor_btn_cartella_hover":  "#004D40",
        "editor_btn_cartella_txt":    "#FFFFFF",
        "editor_btn_cartella_bordo":  "#00897B",
        "editor_btn_classe_bg":       "#1565C0",
        "editor_btn_classe_hover":    "#0D47A1",
        "editor_btn_classe_txt":      "#FFFFFF",
        "editor_btn_classe_bordo":    "#1976D2",
        "editor_btn_neutro_bg":       "#45515A",
        "editor_btn_neutro_hover":    "#53616B",
        "editor_btn_neutro_txt":      "#F3F4F6",
        "editor_btn_neutro_bordo":    "#66727D",


        "testo_info":            "#4ECDC4",

        "testo_label_sec":       "#cccccc",

        # --- Bottoni generici per dialog e sotto-finestre ---

        "btn_rosso_bg":            "#d32f2f",
        "btn_rosso_hover":         "#b71c1c",

        "btn_blu_bg":              "#1565c0",
        "btn_blu_hover":           "#0d47a1",


        "testo_blu":               "#5B9BD5",

        "btn_grigio_bg":           "#757575",
        "btn_grigio_hover":        "#616161",

        "btn_viola_bg":            "#6a1b9a",
        "btn_viola_hover":         "#4a148c",

        "btn_arancione_bg":        "#E65100",
        "btn_arancione_hover":     "#BF360C",

        "btn_colore_disabled_sf":  "#616161",
        "btn_colore_disabled_txt": "#9e9e9e",
        # --- Storico: azioni della tabella e dei dialog ---


        "popup_btn_distruttivo_bg":    "#713737",
        "popup_btn_distruttivo_hover": "#5F2D2D",
        "popup_btn_distruttivo_txt":   "#FFFFFF",
        "popup_btn_distruttivo_bordo": "#9B5555",
        "storico_btn_elimina_bg":     "#D32F2F",
        "storico_btn_elimina_hover":  "#B71C1C",
        "storico_btn_elimina_txt":    "#FFFFFF",
        "storico_btn_elimina_bordo":  "#EF5350",
        "storico_btn_dettagli_bg":    "#1565C0",
        "storico_btn_dettagli_hover": "#0D47A1",
        "storico_btn_dettagli_txt":   "#FFFFFF",
        "storico_btn_dettagli_bordo": "#42A5F5",
        "storico_btn_layout_bg":      "#236B5B",
        "storico_btn_layout_hover":   "#174D42",
        "storico_btn_layout_txt":     "#F3F4F6",
        "storico_btn_layout_bordo":   "#4E9B89",
        "storico_btn_neutro_bg":      "#4B5563",
        "storico_btn_neutro_hover":   "#374151",
        "storico_btn_neutro_txt":     "#F3F4F6",
        "storico_btn_neutro_bordo":   "#66727D",

        # --- Testi semantici ---
        "testo_ocra":              "#CC8800",
        "testo_incomp":            "#FF6B6B",
        "testo_affinita":          "#66bb6a",
        "testo_arancione":         "#FF9800",
        "testo_negativo":          "#FF6B6B",
        "statistiche_titolo_sezione": "#90CAF9",
        "banner_formato_txt":      "#1a1a1a",

        # --- Finestre informative: Istruzioni, Crediti, Aiuto aula ---


        "istruzioni_documento_bg":    "#1B1F23",
        "istruzioni_card_bg":         "#30363D",
        "istruzioni_bordo":           "#56616C",
        "istruzioni_titolo":          "#8AB4F8",
        "istruzioni_sezione_bg":      "#263747",
        "istruzioni_sezione_bordo":   "#4F6B84",
        "istruzioni_info_bg":         "#243743",
        "istruzioni_info_bordo":      "#5B8EAD",
        "istruzioni_info_txt":        "#E5F3FB",
        "istruzioni_avviso_bg":       "#473922",
        "istruzioni_avviso_bordo":    "#C58B38",
        "istruzioni_avviso_txt":      "#FFF1D2",
        "istruzioni_tabella_header_bg":  "#3C4956",
        "istruzioni_tabella_header_txt": "#F5F7FA",
        "istruzioni_codice_bg":       "#181B1E",
        "istruzioni_codice_txt":      "#E6EDF3",
        "istruzioni_link":            "#90CAF9",
        "istruzioni_testo_secondario": "#AAB4BE",
        "istruzioni_testo_errore":    "#FF7B72",
        "istruzioni_testo_successo":  "#7EE787",
        "istruzioni_testo_avviso":    "#FFB454",
        "istruzioni_testo_ocra":      "#E0A94D",

        # --- Dialog Dettaglio vincoli ---
        "dettaglio_vincoli_bg":          "#1E1E1E",

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
        "drag_target_bordo":     "#FF9800",

        # --- Testi ---
        "testo_principale":      "#212121",
        "testo_secondario":      "#555555",
        "testo_disabilitato":    "#9e9e9e",
        "testo_placeholder":     "#6B7280",
        "testo_grigio":          "#666666",

        # --- Bottoni generici ---
        "btn_sfondo":            "#e0e0e0",
        "btn_hover":             "#bdbdbd",
        "btn_premuto":           "#9e9e9e",
        "btn_disabilitato_sf":   "#f5f5f5",
        "btn_disabilitato_txt":  "#666666",

        # --- Bottoni specifici: pannello controlli ---


        "btn_indaco_bg":         "#EEF0FF",
        "btn_indaco_hover":      "#E0E4FF",
        "btn_indaco_txt":        "#303F9F",
        "btn_indaco_bordo":      "#AAB2E8",

        "btn_tema_bg":           "#FFF4D6",
        "btn_tema_hover":        "#FFE7A3",
        "btn_tema_txt":          "#7A4E00",
        "btn_tema_bordo":        "#E3B341",

        "btn_crediti_bg":        "#EEF2F4",
        "btn_crediti_hover":     "#DDE5E9",
        "btn_crediti_txt":       "#37474F",
        "btn_crediti_bordo":     "#B0BEC5",

        # --- Bottone avvia assegnazione ---
        "btn_avvia_bg":          "#E6F4EA",
        "btn_avvia_hover":       "#D1EAD8",
        "btn_avvia_txt":         "#1B5E20",
        "btn_avvia_bordo":       "#81C784",
        "btn_avvia_disabled_bg": "#F1F3F5",
        "btn_avvia_disabled_txt": "#606870",
        "btn_avvia_disabled_bordo": "#D5DADF",

        # --- Bottoni pannello risultati ---

        "btn_salva_bg":          "#D3E8D5",
        "btn_salva_hover":       "#B9D8BC",
        "btn_salva_txt":         "#174D1C",
        "btn_salva_bordo":       "#5FA968",

        "btn_excel_bg":          "#E8F1FB",
        "btn_excel_hover":       "#D6E7F8",
        "btn_excel_txt":         "#0D47A1",
        "btn_excel_bordo":       "#90CAF9",

        "btn_export_bg":         "#FFF2E1",
        "btn_export_hover":      "#FFE3C1",
        "btn_export_txt":        "#8A4B00",
        "btn_export_bordo":      "#FFB74D",

        "btn_statistiche_export_bg":    "#E8F1FB",
        "btn_statistiche_export_hover": "#D6E7F8",
        "btn_statistiche_export_txt":   "#0D47A1",
        "btn_statistiche_export_bordo": "#90CAF9",

        "btn_azione_disabled_bg":    "#F1F3F5",
        "btn_azione_disabled_txt":   "#8A929A",
        "btn_azione_disabled_bordo": "#D5DADF",

        # --- Bottoni spinbox +/− (file di banchi, posti per fila) ---
        "btn_spinbox_bg":        "#E0E0E0",
        "btn_spinbox_txt":       "#212121",
        "btn_spinbox_bordo":     "#BDBDBD",
        "btn_meno_hover_bg":     "#EF5350",
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

        "label_attenzione_bg":     "#E65100",
        "label_attenzione_bordo":  "#FF9800",
        "label_attenzione_txt":    "#ffffff",

        "label_successo_bg":       "#E6F4EA",
        "label_successo_bordo":    "#81C784",
        "label_successo_txt":      "#1B5E20",

        "testo_stato_ok":          "#2E7D32",

        "label_caricato_bg":       "#E6F4EA",
        "label_caricato_bordo":    "#81C784",
        "label_caricato_txt":      "#1B5E20",

        "label_capienza_bg":       "#EEF2F4",
        "label_capienza_bordo":    "#C5CDD3",
        "label_capienza_txt":      "#374151",


        "vincoli_riepilogo_bg":    "#eaedf2",
        "vincoli_riepilogo_bordo": "#d6dae1",

        # --- Editor: struttura generale ---
        "editor_scroll_sf":      "#f0f0f0",
        "editor_titolo_txt":     "#212121",
        "editor_info_txt":       "#424242",
        "editor_sep":            "#cccccc",

        # --- Editor: bottone "Aggiungi incompatibilità" ---

        "editor_btn_incomp_sf":    "#ffccbc",
        "editor_btn_incomp_txt":   "#bf360c",
        "editor_btn_incomp_hover": "#ffab91",

        # --- Editor: bottone "Aggiungi affinità" ---

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


        "combo_ph_bordo":             "#FF9800",
        "combo_ph_txt":               "#E65100",

        "combo_incomp_bordo":         "#5D4037",
        "combo_incomp_sf":            "#FFCCBC",
        "combo_incomp_txt":           "#3E2723",
        "combo_incomp_selezione_sf":  "#FFAB91",

        "combo_aff_bordo":            "#1B5E20",
        "combo_aff_sf":               "#C8E6C9",
        "combo_aff_txt":              "#0E3D12",
        "combo_aff_selezione_sf":     "#A5D6A7",

        # --- Editor: ComboBox genere con placeholder "---" ---
        "genere_ph_bordo":       "#FF9800",
        "genere_ph_sf":          "#FFF8E1",


        "btn_primario_sf":       "#E6F4F1",
        "btn_primario_hover":    "#D2EAE4",
        "btn_primario_txt":      "#155E55",

        # --- Editor: barra file e azioni di visualizzazione ---
        "editor_btn_cartella_bg":     "#D2E8E3",
        "editor_btn_cartella_hover":  "#B9DCD4",
        "editor_btn_cartella_txt":    "#104F47",
        "editor_btn_cartella_bordo":  "#5FAE9F",
        "editor_btn_classe_bg":       "#E8F1FB",
        "editor_btn_classe_hover":    "#D6E7F8",
        "editor_btn_classe_txt":      "#0D47A1",
        "editor_btn_classe_bordo":    "#90CAF9",
        "editor_btn_neutro_bg":       "#EEF2F4",
        "editor_btn_neutro_hover":    "#DDE5E9",
        "editor_btn_neutro_txt":      "#37474F",
        "editor_btn_neutro_bordo":    "#B0BEC5",


        "testo_info":            "#1565C0",

        "testo_label_sec":       "#424242",

        # --- Bottoni generici per dialog e sotto-finestre ---
        "btn_rosso_bg":            "#d32f2f",
        "btn_rosso_hover":         "#b71c1c",
        "btn_blu_bg":              "#1565c0",
        "btn_blu_hover":           "#0d47a1",


        "testo_blu":               "#1565c0",
        "btn_grigio_bg":           "#757575",
        "btn_grigio_hover":        "#616161",
        "btn_viola_bg":            "#6a1b9a",
        "btn_viola_hover":         "#4a148c",
        "btn_arancione_bg":        "#E65100",
        "btn_arancione_hover":     "#BF360C",

        "btn_colore_disabled_sf":  "#BDBDBD",
        "btn_colore_disabled_txt": "#757575",
        # --- Storico: azioni della tabella e dei dialog ---


        "popup_btn_distruttivo_bg":    "#F7D6D6",
        "popup_btn_distruttivo_hover": "#EFC1C1",
        "popup_btn_distruttivo_txt":   "#8F1515",
        "popup_btn_distruttivo_bordo": "#D86A6A",
        "storico_btn_elimina_bg":     "#F7D6D6",
        "storico_btn_elimina_hover":  "#EFC1C1",
        "storico_btn_elimina_txt":    "#8F1515",
        "storico_btn_elimina_bordo":  "#D86A6A",
        "storico_btn_dettagli_bg":    "#E8F1FB",
        "storico_btn_dettagli_hover": "#D6E7F8",
        "storico_btn_dettagli_txt":   "#0D47A1",
        "storico_btn_dettagli_bordo": "#90CAF9",
        "storico_btn_layout_bg":      "#E6F4F1",
        "storico_btn_layout_hover":   "#D2EAE4",
        "storico_btn_layout_txt":     "#155E55",
        "storico_btn_layout_bordo":   "#80CBC4",
        "storico_btn_neutro_bg":      "#EEF2F4",
        "storico_btn_neutro_hover":   "#DDE5E9",
        "storico_btn_neutro_txt":     "#37474F",
        "storico_btn_neutro_bordo":   "#B0BEC5",

        # --- Testi semantici (scuriti per leggibilità su bianco) ---
        "testo_ocra":              "#8A5A00",
        "testo_incomp":            "#C62828",
        "testo_affinita":          "#2E7D32",
        "testo_arancione":         "#E65100",
        "testo_negativo":          "#D32F2F",
        "statistiche_titolo_sezione": "#1565C0",
        "banner_formato_txt":      "#1a1a1a",

        # --- Finestre informative: Istruzioni, Crediti, Aiuto aula ---


        "istruzioni_documento_bg":    "#E1E8F0",
        "istruzioni_card_bg":         "#F2F5F7",
        "istruzioni_bordo":           "#93A6B7",
        "istruzioni_titolo":          "#0D47A1",
        "istruzioni_sezione_bg":      "#C4D8E8",
        "istruzioni_sezione_bordo":   "#7FA1BD",
        "istruzioni_info_bg":         "#CBDDE8",
        "istruzioni_info_bordo":      "#5F91AF",
        "istruzioni_info_txt":        "#15384B",
        "istruzioni_avviso_bg":       "#FFF4E5",
        "istruzioni_avviso_bordo":    "#E6A24A",
        "istruzioni_avviso_txt":      "#6B3D00",
        "istruzioni_tabella_header_bg":  "#C8D7E3",
        "istruzioni_tabella_header_txt": "#17324D",
        "istruzioni_codice_bg":       "#DCE4EA",
        "istruzioni_codice_txt":      "#24313D",
        "istruzioni_link":            "#0D47A1",
        "istruzioni_testo_secondario": "#596570",
        "istruzioni_testo_errore":    "#B42318",
        "istruzioni_testo_successo":  "#1B5E20",
        "istruzioni_testo_avviso":    "#8A4500",
        "istruzioni_testo_ocra":      "#805A00",

        # --- Dialog Dettaglio vincoli ---
        "dettaglio_vincoli_bg":          "#EEF2F4",

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


# Nome della palette corrente.
TEMA_ATTIVO = "scuro"


def imposta_tema(nome: str):
    """Imposta il tema attivo se il nome è riconosciuto."""
    global TEMA_ATTIVO
    if nome in TEMI:
        TEMA_ATTIVO = nome


def get_tema() -> str:
    """Restituisce il nome del tema attivo."""
    return TEMA_ATTIVO


def C(nome_colore: str) -> str:
    """Restituisce il colore associato alla chiave nel tema attivo."""
    return TEMI[TEMA_ATTIVO][nome_colore]
