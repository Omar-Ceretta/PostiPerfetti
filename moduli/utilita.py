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
    Funzioni di utilità globali.

    Contiene strumenti riutilizzabili in tutto il progetto:
    • get_base_path()                    → Percorso base compatibile con PyInstaller
    • pulisci_nome_file()                → Sanifica stringhe per nomi file cross-platform
    • apri_file_con_applicazione_default() → Apre un file con l'app di sistema
    • mostra_popup_file_salvato()        → Popup di conferma salvataggio con "Apri"
    • abbrevia_nome_assegnazione()       → Abbrevia nomi assegnazione per UI compatta
    • crea_bottone()                     → Factory per bottoni QPushButton con stile uniforme
    • FiltroCursoreManina                → Filtro eventi per cursore "manina" sui bottoni
"""

import sys
import os
import platform
import subprocess

from PySide6.QtWidgets import QMessageBox, QPushButton
from PySide6.QtCore import Qt, QObject, QEvent

# =============================================================================
# PERCORSO BASE — Compatibilità con PyInstaller
# =============================================================================

def get_base_path():
    """
    Restituisce il percorso base del progetto, compatibile con PyInstaller.

    Quando il programma gira come .exe (PyInstaller --onefile), __file__
    punta a una cartella TEMPORANEA di estrazione, non dove si trova il .exe.
    Serve usare sys.executable per trovare la cartella reale.

    Returns:
        str: Percorso assoluto della cartella dove si trova il .exe o lo script
    """
    if getattr(sys, 'frozen', False):
        # Modalità .exe (PyInstaller): la cartella è accanto al .exe
        return os.path.dirname(sys.executable)
    else:
        # Modalità script: la cartella è dove si trova il file PRINCIPALE .py
        # Nota: usiamo __file__ di QUESTO modulo e risaliamo di un livello
        # perché utilita.py si trova in moduli/, mentre il progetto è nella
        # cartella genitore. In alternativa si potrebbe usare il file principale,
        # ma con PyInstaller frozen=True il percorso è comunque corretto.
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# PULIZIA NOMI FILE — Cross-platform (Linux/Windows/macOS)
# =============================================================================

def pulisci_nome_file(nome: str) -> str:
    """
    Pulisce una stringa per renderla un nome file valido cross-platform.
    Rimuove/sostituisce caratteri non validi in Windows, Linux, macOS.

    Args:
        nome: Stringa da pulire

    Returns:
        Stringa sicura per nome file
    """
    # Caratteri non validi cross-platform: / \ : * ? " < > |
    caratteri_vietati = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']

    nome_pulito = nome
    for char in caratteri_vietati:
        nome_pulito = nome_pulito.replace(char, '-')

    # Sostituisci spazi multipli con underscore singolo
    while '  ' in nome_pulito:
        nome_pulito = nome_pulito.replace('  ', ' ')

    # Sostituisci spazi con underscore
    nome_pulito = nome_pulito.replace(' ', '_')

    # Rimuovi underscore/trattini multipli consecutivi
    while '__' in nome_pulito:
        nome_pulito = nome_pulito.replace('__', '_')
    while '--' in nome_pulito:
        nome_pulito = nome_pulito.replace('--', '-')

    # Rimuovi caratteri all'inizio/fine
    nome_pulito = nome_pulito.strip('_-')

    return nome_pulito

# =============================================================================
# APERTURA FILE — Con l'applicazione predefinita del sistema operativo
# =============================================================================

def apri_file_con_applicazione_default(file_path: str) -> bool:
    """
    Apre un file con l'applicazione predefinita del sistema operativo.
    Gestisce Linux, Windows e macOS in modo cross-platform.

    Args:
        file_path: Percorso completo del file da aprire

    Returns:
        bool: True se apertura riuscita, False se errore
    """

    try:
        sistema = platform.system()

        if sistema == 'Linux':
            # Linux: usa xdg-open
            subprocess.run(['xdg-open', file_path], check=False)
            return True

        elif sistema == 'Windows':
            # Windows: usa os.startfile
            os.startfile(file_path)
            return True

        elif sistema == 'Darwin':  # macOS
            # macOS: usa open
            subprocess.run(['open', file_path], check=False)
            return True

        else:
            print(f"⚠️ Sistema operativo non riconosciuto: {sistema}")
            return False

    except Exception as e:
        print(f"❌ Errore apertura file: {e}")
        return False

# =============================================================================
# POPUP SALVATAGGIO — Conferma con bottone "Apri"
# =============================================================================

def mostra_popup_file_salvato(parent, titolo: str, messaggio: str, file_path: str):
    """
    Mostra un popup di conferma salvataggio con bottone "Apri" per aprire il file.
    Pattern riutilizzato in tutti i punti dove si salva un file (Excel, TXT, statistiche).

    Args:
        parent: Widget genitore per il popup (QWidget, QDialog, QMainWindow)
        titolo: Titolo della finestra popup (es: "Export completato")
        messaggio: Testo principale (es: "✅ File Excel salvato con successo!")
        file_path: Percorso completo del file salvato
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(titolo)
    msg_box.setText(messaggio)
    msg_box.setInformativeText(f"Percorso:\n{file_path}")
    msg_box.setIcon(QMessageBox.Information)

    # Bottone "Apri" (custom) + Bottone "OK" (standard)
    btn_apri = msg_box.addButton("📂 Apri", QMessageBox.ActionRole)
    msg_box.addButton(QMessageBox.Ok)

    msg_box.exec()

    # Se ha cliccato "Apri", apri il file con l'app predefinita del sistema
    if msg_box.clickedButton() == btn_apri:
        if not apri_file_con_applicazione_default(file_path):
            QMessageBox.warning(
                parent,
                "Errore Apertura",
                "⚠️ Impossibile aprire il file automaticamente.\n"
                "Aprilo manualmente dal percorso mostrato."
            )

# =============================================================================
# ABBREVIAZIONE NOMI ASSEGNAZIONE — Per visualizzazione compatta nell'UI
# =============================================================================

def abbrevia_nome_assegnazione(nome_completo: str, data_assegnazione: str = "") -> str:
    """
    Abbrevia il nome di un'assegnazione per visualizzazione compatta.

    Args:
        nome_completo: Nome completo dell'assegnazione
        data_assegnazione: Data in formato "YYYY-MM-DD"

    Returns:
        str: Nome abbreviato con data

    Esempi:
        "3A - Prima assegnazione 05/10/2025" → "Prima ass. 05/10"
        "3A - Rotazione mensile numero 3..." → "Rot. mensile 3... 08/12"
    """
    # Rimuovi prefisso classe comune (es: "3A - ")
    nome = nome_completo
    if " - " in nome:
        nome = nome.split(" - ", 1)[1]

    # Abbreviazioni comuni
    abbreviazioni = {
        "Prima assegnazione": "Prima ass.",
        "Rotazione": "Rot.",
        "mensile": "mens.",
        "numero": "n.",
        "dell'anno": "",
        "scolastico": "scol."
    }

    for originale, abbreviato in abbreviazioni.items():
        nome = nome.replace(originale, abbreviato)

    # Tronca se troppo lungo (max 30 caratteri)
    if len(nome) > 30:
        nome = nome[:27] + "..."

    # Estrai data breve (solo giorno/mese)
    data_breve = ""
    if data_assegnazione:
        try:
            # Formato "YYYY-MM-DD" → "DD/MM"
            parti = data_assegnazione.split("-")
            if len(parti) == 3:
                data_breve = f"{parti[2]}/{parti[1]}"
        except (ValueError, IndexError):
            data_breve = data_assegnazione[-5:]  # Fallback: ultimi 5 caratteri

    # Ritorna solo nome abbreviato (senza data aggiuntiva)
    return nome.strip()

# =============================================================================
# FACTORY BOTTONI — Crea bottoni standard con stile coerente
# =============================================================================

def crea_bottone(testo, colore_bg, colore_hover, tooltip="", altezza_min=None,
                 colore_disabled_bg=None, colore_disabled_txt=None,
                 font_size=13, border_radius=6, padding="10px 20px"):
    """
    Factory per creare bottoni QPushButton con stile uniforme.

    Elimina la ripetizione del pattern "crea → setStyleSheet → setToolTip"
    Ogni bottone prodotto ha:
    - Colore di sfondo e hover personalizzabili
    - Testo bianco, grassetto
    - Bordi arrotondati
    - (Opzionale) Stile per stato disabilitato
    - (Opzionale) Altezza minima

    NOTA: Questa factory è pensata per i bottoni "standard" (rettangolari,
    con testo). I bottoni speciali (rotondi come "?" e "💬", oppure i +/−
    con bordi custom) restano definiti inline perché hanno troppi
    parametri specifici che renderebbero la factory troppo complessa.

    Args:
        testo:               Testo del bottone (può includere emoji)
        colore_bg:           Colore di sfondo (es: "#4CAF50")
        colore_hover:        Colore di sfondo al passaggio del mouse
        tooltip:             Testo del tooltip (default: nessuno)
        altezza_min:         Altezza minima in pixel (None = nessun vincolo)
        colore_disabled_bg:  Colore sfondo quando disabilitato (None = nessuno stile disabled)
        colore_disabled_txt: Colore testo quando disabilitato (None = nessuno stile disabled)
        font_size:           Dimensione font in px (default: 13)
        border_radius:       Raggio bordi in px (default: 6)
        padding:             Padding CSS (default: "10px 20px")

    Returns:
        QPushButton: Bottone configurato e pronto per l'uso

    Esempio d'uso:
        btn = crea_bottone("💾 Salva", "#2E7D32", "#1B5E20",
                           tooltip="Salva il progetto",
                           altezza_min=45,
                           colore_disabled_bg="#9E9E9E",
                           colore_disabled_txt="#616161")
        btn.clicked.connect(self.salva)
        layout.addWidget(btn)
    """
    btn = QPushButton(testo)

    # Altezza minima: impostata solo se specificata (i bottoni piccoli non la usano)
    if altezza_min is not None:
        btn.setMinimumHeight(altezza_min)

    # --- Costruzione dello stylesheet ---
    # Parte base: sempre presente
    stile = f"""
        QPushButton {{
            background-color: {colore_bg};
            color: white;
            font-size: {font_size}px;
            font-weight: bold;
            border-radius: {border_radius}px;
            padding: {padding};
        }}
        QPushButton:hover {{
            background-color: {colore_hover};
        }}"""

    # Parte disabled: aggiunta solo se i colori sono specificati
    if colore_disabled_bg and colore_disabled_txt:
        stile += f"""
        QPushButton:disabled {{
            background-color: {colore_disabled_bg};
            color: {colore_disabled_txt};
        }}"""

    btn.setStyleSheet(stile)

    # Tooltip: impostato solo se fornito (stringa non vuota)
    if tooltip:
        btn.setToolTip(tooltip)

    return btn

# ─────────────────────────────────────────────────────────────────
# FILTRO CURSORE "MANINA" — UX: il cursore diventa una manina
# quando passa sopra un pulsante attivo (standard in tutte le app).
# Funziona automaticamente per TUTTI i QPushButton dell'applicazione,
# inclusi quelli creati dinamicamente in dialog e popup.
# Cross-platform: Qt gestisce PointingHandCursor su Linux, Windows, macOS.
# ─────────────────────────────────────────────────────────────────
class FiltroCursoreManina(QObject):
    """
    Filtro eventi globale installato su QApplication.
    Quando il mouse entra in un QPushButton abilitato,
    il cursore diventa una "manina" (pointing hand).
    Restituisce sempre False → non blocca mai nessun evento.
    """
    def eventFilter(self, obj, event):
        # Reagisce solo all'evento "mouse entra nel widget"
        if event.type() == QEvent.Type.Enter and isinstance(obj, QPushButton):
            if obj.isEnabled():
                # Pulsante attivo → cursore "manina"
                obj.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                # Pulsante disabilitato → cursore freccia normale
                obj.setCursor(Qt.CursorShape.ArrowCursor)
        # False = non intercettiamo l'evento, lo lasciamo proseguire normalmente
        return False
