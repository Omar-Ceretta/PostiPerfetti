"""
«PostiPerfetti» — Interfaccia grafica (PySide6) per l'assegnazione
automatica dei posti degli allievi in una classe scolastica.
Sviluppato dal prof. Omar Ceretta con Python.
- I.C. di Tombolo e Galliera Veneta (PD) -
"""

import sys
# Disabilita la creazione delle cartelle __pycache__ e dei file .pyc
sys.dont_write_bytecode = True
import os

# Protezione cross-platform: su Windows in modalità "windowed" (PyInstaller --windowed),
# sys.stdout e sys.stderr sono None → ogni print() causerebbe un crash.
# Redirigiamo a devnull per renderle innocue.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

import json
import platform


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
        # Modalità script: la cartella è dove si trova questo file .py
        return os.path.dirname(os.path.abspath(__file__))
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QFileDialog, QTextEdit,
    QSpinBox, QSlider, QGroupBox, QRadioButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QProgressBar,
    QMessageBox, QSplitter, QScrollArea, QComboBox, QLineEdit,
    QDialog, QDialogButtonBox, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject, QEvent
from PySide6.QtGui import QFont, QPixmap, QPalette, QColor, QIcon

# Import delle classi
from modelli.studenti import Student
from modelli.aula import ConfigurazioneAula
from algoritmo.algoritmo import AssegnatorePosti
from modelli.vincoli import MotoreVincoli
# Import dell'editor grafico studenti (nella cartella modelli/)
from modelli.editor_studenti import EditorStudentiWidget
# Importa il sistema di gestione tema (colori scuro/chiaro)
from modelli.tema import TEMI, TEMA_ATTIVO, C, imposta_tema, get_tema

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

def mostra_popup_file_salvato(parent, titolo: str, messaggio: str, file_path: str):
    """
    Mostra un popup di conferma salvataggio con bottone "Apri" per aprire il file.
    Pattern riutilizzato in tutti i punti dove si salva un file (Excel, TXT, statistiche).

    Args:
        parent: Widget genitore per il popup (QWidget, QDialog, QMainWindow)
        titolo: Titolo della finestra popup (es: "Export Completato")
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


class ConfigurazioneApp:
    """
    Gestisce la configurazione dell'applicazione e la memoria storica.
    """

    def __init__(self):
        # Il file di configurazione si trova nella cartella dati/
        # che viene creata automaticamente se non esiste
        cartella_dati = os.path.join(get_base_path(), "dati")
        os.makedirs(cartella_dati, exist_ok=True)
        self.file_config = os.path.join(cartella_dati, "postiperfetti_configurazione.json")
        self.config_data = self._carica_configurazione_default()

    def _carica_configurazione_default(self) -> Dict:
        """Configurazione di default se non esiste file."""
        return {
            "classe_info": {
                "nome_classe": "",
                "ultima_modifica": ""
            },
            "configurazione_aula": {
                "num_file": 4, # Default: 4 file di banchi (più comune nelle aule)
                "posti_per_fila": 6,
                "layout_type": "standard"
            },
            "opzioni_vincoli": {
                "genere_misto_obbligatorio": False
            },
            "storico_assegnazioni": [],
            "coppie_da_evitare": [],
            "studenti_trio_contatore": {},  # Traccia quante volte ogni studente è stato nel trio
            "tema": "scuro"                 # Tema interfaccia: "scuro" o "chiaro"
        }

    def carica_configurazione(self) -> bool:
        """Carica configurazione da file JSON."""
        try:
            if os.path.exists(self.file_config):
                with open(self.file_config, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                print(f"✅ Configurazione caricata da {self.file_config}")
                return True
            else:
                print(f"ℹ️  File configurazione non trovato, uso default")
                return False
        except Exception as e:
            print(f"⚠️  Errore caricamento configurazione: {e}")
            return False

    def salva_configurazione(self) -> bool:
        """Salva configurazione su file JSON."""
        try:
            self.config_data["classe_info"]["ultima_modifica"] = datetime.now().isoformat()

            with open(self.file_config, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Configurazione salvata in {self.file_config}")
            return True
        except Exception as e:
            print(f"❌ Errore salvataggio configurazione: {e}")
            return False

    def aggiungi_assegnazione_storico(self, nome_assegnazione: str, coppie: List[tuple], trio=None, configurazione_aula=None, file_origine=None, report_completo=None):
        """Aggiunge una nuova assegnazione allo storico con layout completo."""

        # Crea struttura base assegnazione
        nuova_assegnazione = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "ora": datetime.now().strftime("%H:%M"),
            "nome": nome_assegnazione,
            "file_origine": file_origine if file_origine else "Non specificato"
        }

        # Salva configurazione aula se disponibile
        if configurazione_aula:
            nuova_assegnazione["configurazione_aula"] = {
                "num_file": configurazione_aula.num_righe - 2,  # -2 per elementi fissi
                "posti_per_fila": self._calcola_posti_per_fila(configurazione_aula),
                "modalita_trio": self._determina_modalita_trio_salvata(trio, configurazione_aula),
                "num_studenti": len(coppie) * 2 + (3 if trio else 0),
                "num_righe": configurazione_aula.num_righe,  # Salva dimensioni esatte
                "num_colonne": configurazione_aula.num_colonne
            }

            # Estrae layout completo (coordinate di ogni studente)
            nuova_assegnazione["layout"] = self._estrai_layout_da_configurazione(configurazione_aula, coppie, trio)

            # Salva report completo se disponibile
            if report_completo:
                nuova_assegnazione["report_completo"] = report_completo
        else:
            # Se non c'è configurazione, salva solo abbinamenti
            nuova_assegnazione["abbinamenti"] = self._crea_lista_abbinamenti(coppie, trio)

        # Aggiungi allo storico
        self.config_data["storico_assegnazioni"].append(nuova_assegnazione)

        # Aggiorna sistema penalità per rotazione (coppie + trio)
        self._aggiorna_coppie_da_evitare(coppie, trio)

        self.salva_configurazione()

    def _calcola_posti_per_fila(self, configurazione_aula):
        """
        Calcola il numero di posti per fila dalla configurazione aula.

        Args:
            configurazione_aula: Oggetto ConfigurazioneAula

        Returns:
            int: Numero di posti per fila (banchi in una singola fila)
        """
        # Conta i banchi nella prima fila di banchi (riga 2, dopo elementi fissi)
        if len(configurazione_aula.griglia) > 2:
            prima_fila_banchi = configurazione_aula.griglia[2]
            posti_contati = sum(1 for posto in prima_fila_banchi if posto.tipo == 'banco')
            return posti_contati

        # Fallback: ritorna 6 se non riesce a calcolare
        return 6

    def _determina_modalita_trio_salvata(self, trio, configurazione_aula):
        """
        Determina in quale posizione è stato piazzato il trio (prima/ultima/centro).

        Args:
            trio: Lista di 3 studenti (o None se numero pari)
            configurazione_aula: Oggetto ConfigurazioneAula

        Returns:
            str: "prima", "ultima", "centro" o None se numero pari
        """
        if not trio:
            return None

        # Cerca il trio nella griglia per determinare in quale fila è stato messo
        trio_nomi = {f"{s.cognome}_{s.nome}" for s in trio}

        banchi_per_fila = configurazione_aula.get_banchi_per_fila()

        for idx_fila, banchi_fila in enumerate(banchi_per_fila):
            # Conta quanti studenti del trio sono in questa fila
            studenti_trio_in_fila = 0
            for banco in banchi_fila:
                if banco.occupato_da and banco.occupato_da in trio_nomi:
                    studenti_trio_in_fila += 1

            # Se tutti e 3 i membri del trio sono in questa fila
            if studenti_trio_in_fila == 3:
                # Determina se è prima, ultima o centro
                if idx_fila == 0:
                    return "prima"
                elif idx_fila == len(banchi_per_fila) - 1:
                    return "ultima"
                else:
                    return "centro"

        # Fallback: non dovrebbe mai succedere
        return "auto"

    def _estrai_layout_da_configurazione(self, configurazione_aula, coppie, trio):
        """
        Estrae il layout completo con coordinate di ogni studente.

        Args:
            configurazione_aula: Oggetto ConfigurazioneAula
            coppie: Lista di tuple (studente1, studente2, info)
            trio: Lista di 3 studenti (o None)

        Returns:
            list: Lista di dict con posizione e info di ogni studente
        """
        layout = []

        # Mappa per identificare i compagni
        mappa_coppie = {}
        for studente1, studente2, info in coppie:
            nome1 = studente1.get_nome_completo()
            nome2 = studente2.get_nome_completo()
            mappa_coppie[nome1] = {"tipo": "coppia", "compagno": nome2, "info": info}
            mappa_coppie[nome2] = {"tipo": "coppia", "compagno": nome1, "info": info}

        # Mappa per trio
        mappa_trio = {}
        if trio:
            nomi_trio = [s.get_nome_completo() for s in trio]
            for idx, studente in enumerate(trio):
                nome = studente.get_nome_completo()
                posizione = ["primo", "centrale", "terzo"][idx]
                mappa_trio[nome] = {
                    "tipo": "trio",
                    "posizione_trio": posizione,
                    "compagni_trio": [n for n in nomi_trio if n != nome]
                }

        # Estrae coordinate da griglia
        for riga_idx, riga in enumerate(configurazione_aula.griglia):
            for col_idx, posto in enumerate(riga):
                if posto.tipo == 'banco' and posto.occupato_da:
                    # Converte ID "Cognome_Nome" in "Cognome Nome"
                    nome_completo = posto.occupato_da.replace('_', ' ')

                    # Determina tipo abbinamento
                    info_studente = {
                        "studente": nome_completo,
                        "riga": riga_idx,
                        "colonna": col_idx
                    }

                    # Aggiunge info coppia o trio
                    if nome_completo in mappa_trio:
                        info_studente.update(mappa_trio[nome_completo])
                    elif nome_completo in mappa_coppie:
                        info_studente.update(mappa_coppie[nome_completo])
                        # Salva anche il punteggio della coppia
                        info_studente["punteggio"] = mappa_coppie[nome_completo]["info"]["punteggio_totale"]

                    layout.append(info_studente)

        return layout

    def ricostruisci_layout_da_storico(self, indice_assegnazione):
        """
        Ricostruisce il layout completo di un'assegnazione storica.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione nello storico (0-based)

        Returns:
            tuple: (ConfigurazioneAula ricostruita, dict dati_assegnazione) oppure (None, None) se errore
        """
        try:
            # Verifica indice valido
            storico = self.config_data.get("storico_assegnazioni", [])
            if indice_assegnazione < 0 or indice_assegnazione >= len(storico):
                print(f"❌ Indice {indice_assegnazione} non valido (storico ha {len(storico)} elementi)")
                return None, None

            # Ottiene dati assegnazione
            assegnazione = storico[indice_assegnazione]

            # Verifica che abbia il layout
            if "layout" not in assegnazione or "configurazione_aula" not in assegnazione:
                print(f"⚠️ Assegnazione '{assegnazione.get('nome', 'Senza nome')}' in formato vecchio - impossibile ricostruire layout")
                return None, None

            config_aula_data = assegnazione["configurazione_aula"]
            layout_data = assegnazione["layout"]

            print(f"🔄 Ricostruzione layout: {assegnazione.get('nome', 'Senza nome')}")
            print(f"   📊 Configurazione: {config_aula_data['num_file']} file x {config_aula_data['posti_per_fila']} posti")
            print(f"   👥 Studenti: {config_aula_data['num_studenti']}")

            # Crea nuova configurazione aula vuota
            from modelli.aula import ConfigurazioneAula, PostoAula
            config_ricostruita = ConfigurazioneAula(f"Layout {assegnazione.get('nome', 'Storico')}")

            # Usa le dimensioni ESATTE salvate (non ricalcolare)
            num_righe_salvate = config_aula_data.get('num_righe')
            num_colonne_salvate = config_aula_data.get('num_colonne')

            if num_righe_salvate and num_colonne_salvate:
                # Ricostruisce griglia con dimensioni esatte
                print(f"   🎯 Usando dimensioni esatte: {num_righe_salvate} righe × {num_colonne_salvate} colonne")

                config_ricostruita.num_righe = num_righe_salvate
                config_ricostruita.num_colonne = num_colonne_salvate

                # Inizializza griglia vuota con dimensioni esatte
                config_ricostruita.griglia = []
                for r in range(num_righe_salvate):
                    riga = []
                    for c in range(num_colonne_salvate):
                        riga.append(PostoAula(r, c, 'corridoio'))
                    config_ricostruita.griglia.append(riga)

                # Ricrea elementi fissi (LIM, cattedra, lavagna) nella prima riga
                # ALLINEAMENTO: Usa le stesse posizioni colonna dei banchi
                # così i corridoi tra gli arredi sono identici a quelli tra le coppie
                # Posizioni banchi: [0,1] corridoio [3,4] corridoio [6,7]
                posizioni_arredi = [0, 1, 3, 4, 6, 7]
                config_ricostruita.griglia[0][posizioni_arredi[0]] = PostoAula(0, posizioni_arredi[0], 'lim')
                config_ricostruita.griglia[0][posizioni_arredi[1]] = PostoAula(0, posizioni_arredi[1], 'lim')
                config_ricostruita.griglia[0][posizioni_arredi[2]] = PostoAula(0, posizioni_arredi[2], 'cattedra')
                config_ricostruita.griglia[0][posizioni_arredi[3]] = PostoAula(0, posizioni_arredi[3], 'cattedra')
                config_ricostruita.griglia[0][posizioni_arredi[4]] = PostoAula(0, posizioni_arredi[4], 'lavagna')
                config_ricostruita.griglia[0][posizioni_arredi[5]] = PostoAula(0, posizioni_arredi[5], 'lavagna')

                # Ricrea TUTTI i banchi dalle posizioni salvate nel layout
                # (verranno popolati con studenti subito dopo)
                for studente_info in layout_data:
                    riga = studente_info["riga"]
                    colonna = studente_info["colonna"]

                    # Crea banco in questa posizione se non esiste già
                    if riga < num_righe_salvate and colonna < num_colonne_salvate:
                        if config_ricostruita.griglia[riga][colonna].tipo == 'corridoio':
                            config_ricostruita.griglia[riga][colonna] = PostoAula(riga, colonna, 'banco')

                # Conta posti disponibili
                posti_contati = 0
                for riga in config_ricostruita.griglia:
                    for posto in riga:
                        if posto.tipo == 'banco':
                            posti_contati += 1

                config_ricostruita.posti_disponibili = posti_contati
                print(f"   ✅ Griglia ricostruita: {posti_contati} banchi totali")

            else:
                # FALLBACK: Se mancano dimensioni esatte, usa metodo vecchio
                print(f"   ⚠️ Dimensioni esatte non disponibili, uso metodo standard")
                config_ricostruita.crea_layout_standard(
                    num_studenti=config_aula_data['num_studenti'],
                    num_file=config_aula_data['num_file'],
                    posti_per_fila=config_aula_data['posti_per_fila'],
                    posizione_trio=config_aula_data.get('modalita_trio')
                )

            # Popola la griglia con gli studenti nelle posizioni salvate
            for studente_info in layout_data:
                nome_studente = studente_info["studente"]
                riga = studente_info["riga"]
                colonna = studente_info["colonna"]

                # Converte "Cognome Nome" in "Cognome_Nome" (formato ID univoco)
                id_univoco = nome_studente.replace(' ', '_')

                # Assegna studente al banco
                if riga < len(config_ricostruita.griglia) and colonna < len(config_ricostruita.griglia[riga]):
                    posto = config_ricostruita.griglia[riga][colonna]
                    if posto.tipo == 'banco':
                        posto.occupato_da = id_univoco
                    else:
                        print(f"⚠️ Posizione ({riga},{colonna}) non è un banco per {nome_studente}")
                else:
                    print(f"⚠️ Posizione ({riga},{colonna}) fuori range per {nome_studente}")

            print(f"✅ Layout ricostruito con successo!")

            # Restituisce configurazione ricostruita + dati originali assegnazione
            return config_ricostruita, assegnazione

        except Exception as e:
            print(f"❌ Errore ricostruzione layout: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def _crea_lista_abbinamenti(self, coppie: List[tuple], trio=None) -> List[dict]:
        """
        Crea la lista unificata di abbinamenti (coppie + trio) per il salvataggio JSON.

        Args:
            coppie: Lista delle coppie formate
            trio: Trio identificato (se presente)

        Returns:
            Lista di abbinamenti nel formato JSON
        """
        abbinamenti = []

        # Aggiungi tutte le coppie
        for coppia in coppie:
            abbinamenti.append({
                "tipo": "coppia",
                "studenti": [coppia[0].get_nome_completo(), coppia[1].get_nome_completo()]
            })

        # Aggiungi il trio se presente
        if trio and len(trio) == 3:
            abbinamenti.append({
                "tipo": "trio",
                "studenti": [studente.get_nome_completo() for studente in trio]
            })

        return abbinamenti

    def _aggiorna_coppie_da_evitare(self, nuove_coppie: List[tuple], trio=None):
        """
        Aggiorna il conteggio delle coppie già utilizzate nella blacklist.
        Formato unico: {"tipo": "coppia", "studenti": [nome1, nome2], "volte_usata": N}
        """
        print(f"🔍 DEBUG: Elaboro {len(nuove_coppie)} coppie e trio={trio is not None}")
        print(f"🔍 DEBUG: Elementi esistenti in coppie_da_evitare: {len(self.config_data['coppie_da_evitare'])}")

        # Crea mappa indicizzata delle coppie esistenti per ricerca veloce
        # chiave = tuple(sorted([nome1, nome2])), valore = riferimento al dict nella lista
        coppie_esistenti = {}
        for item in self.config_data["coppie_da_evitare"]:
            studenti = item.get("studenti", [])
            if len(studenti) == 2:
                chiave = tuple(sorted(studenti))
                coppie_esistenti[chiave] = item

        print(f"🔍 DEBUG: Coppie esistenti trovate: {len(coppie_esistenti)}")

        # Elabora tutte le coppie normali
        for studente1, studente2, _ in nuove_coppie:
            chiave = tuple(sorted([studente1.get_nome_completo(), studente2.get_nome_completo()]))

            if chiave in coppie_esistenti:
                # Coppia già nota: incrementa contatore
                coppie_esistenti[chiave]["volte_usata"] += 1
            else:
                # Nuova coppia: aggiungi in formato unico
                nuova_voce = {
                    "tipo": "coppia",
                    "studenti": [chiave[0], chiave[1]],
                    "volte_usata": 1
                }
                self.config_data["coppie_da_evitare"].append(nuova_voce)
                coppie_esistenti[chiave] = nuova_voce  # Aggiorna mappa per lookup successivi

        # Elabora il trio se presente: salva come 2 coppie virtuali adiacenti
        if trio and len(trio) == 3:
            print(f"🔄 DEBUG: Elaboro trio come coppie virtuali: {[s.get_nome_completo() for s in trio]}")

            studente1, studente2, studente3 = trio

            # Le coppie virtuali sono quelle fisicamente adiacenti: [1-2] e [2-3]
            coppie_virtuali = [
                (studente1.get_nome_completo(), studente2.get_nome_completo()),
                (studente2.get_nome_completo(), studente3.get_nome_completo())
            ]

            for idx, (nome1, nome2) in enumerate(coppie_virtuali, 1):
                chiave = tuple(sorted([nome1, nome2]))
                print(f"   📝 Coppia virtuale {idx}: {chiave[0]} + {chiave[1]}")

                if chiave in coppie_esistenti:
                    # Coppia virtuale già esistente: incrementa contatore
                    coppie_esistenti[chiave]["volte_usata"] += 1
                    print(f"   ✅ Aggiornata: {chiave[0]} + {chiave[1]} (ora {coppie_esistenti[chiave]['volte_usata']} volte)")
                else:
                    # Nuova coppia virtuale: aggiungi con origine "trio"
                    nuova_voce = {
                        "tipo": "coppia",
                        "studenti": [chiave[0], chiave[1]],
                        "origine": "trio",
                        "volte_usata": 1
                    }
                    self.config_data["coppie_da_evitare"].append(nuova_voce)
                    coppie_esistenti[chiave] = nuova_voce
                    print(f"   🆕 Nuova coppia virtuale aggiunta: {chiave[0]} + {chiave[1]}")

            # Aggiorna contatore trio per rotazione equa (UNA SOLA VOLTA, FUORI DAL LOOP)
            for studente in trio:
                nome_studente = studente.get_nome_completo()
                if nome_studente not in self.config_data["studenti_trio_contatore"]:
                    self.config_data["studenti_trio_contatore"][nome_studente] = 0

                self.config_data["studenti_trio_contatore"][nome_studente] += 1
                print(f"   📊 {nome_studente}: ora {self.config_data['studenti_trio_contatore'][nome_studente]} volte nel trio")

    def _ricostruisci_blacklist_da_storico(self):
        """
        Ricostruisce completamente blacklist e contatori da storico assegnazioni.
        UTILIZZO: Dopo eliminazione assegnazione per garantire coerenza.

        LOGICA:
        1. Azzera blacklist e contatori trio esistenti
        2. Ri-elabora ogni assegnazione rimasta nello storico
        3. Ricostruisce blacklist da zero usando logica esistente
        """
        print(f"🔄 RICOSTRUZIONE BLACKLIST: Inizio elaborazione storico...")

        # STEP 1: Azzera completamente blacklist e contatori
        self.config_data["coppie_da_evitare"] = []
        self.config_data["studenti_trio_contatore"] = {}
        print(f"   ✅ Blacklist e contatori azzerati")

        # STEP 2: Ottiene storico assegnazioni rimaste
        storico_rimasto = self.config_data["storico_assegnazioni"]
        num_assegnazioni = len(storico_rimasto)

        if num_assegnazioni == 0:
            print(f"   ℹ️ Storico vuoto - blacklist rimane vuota")
            return

        print(f"   📋 Elaborazione {num_assegnazioni} assegnazioni rimaste...")

        # STEP 3: Ri-elabora ogni assegnazione per ricostruire blacklist
        for idx, assegnazione in enumerate(storico_rimasto, 1):
            nome_assegnazione = assegnazione.get("nome", f"Assegnazione {idx}")
            print(f"   🔄 Elaboro: {nome_assegnazione}")

            # Estrae abbinamenti dall'assegnazione
            abbinamenti = assegnazione.get("abbinamenti", [])

            # Converte abbinamenti in coppie e trio per elaborazione
            coppie_da_elaborare = []
            trio_da_elaborare = None

            for abbinamento in abbinamenti:
                if abbinamento.get("tipo") == "coppia":
                    studenti = abbinamento.get("studenti", [])
                    if len(studenti) == 2:
                        # Crea oggetti Student fittizi per riutilizzare logica esistente
                        s1 = type('Student', (), {'get_nome_completo': lambda self, nome=studenti[0]: nome})()
                        s2 = type('Student', (), {'get_nome_completo': lambda self, nome=studenti[1]: nome})()
                        coppie_da_elaborare.append((s1, s2, {}))

                elif abbinamento.get("tipo") == "trio":
                    studenti_trio = abbinamento.get("studenti", [])
                    if len(studenti_trio) == 3:
                        # Crea oggetti Student fittizi per trio
                        trio_fittizio = []
                        for nome in studenti_trio:
                            s = type('Student', (), {'get_nome_completo': lambda self, n=nome: n})()
                            trio_fittizio.append(s)
                        trio_da_elaborare = trio_fittizio
            # STEP 4: Applica la logica esistente per aggiornare blacklist
            if coppie_da_elaborare or trio_da_elaborare:
                self._aggiorna_coppie_da_evitare(coppie_da_elaborare, trio_da_elaborare)
                print(f"      ✅ Elaborati: {len(coppie_da_elaborare)} coppie" +
                      (f" + 1 trio" if trio_da_elaborare else ""))

        # STEP 5: Statistiche finali
        num_coppie_blacklist = len(self.config_data["coppie_da_evitare"])
        num_studenti_trio = len(self.config_data["studenti_trio_contatore"])

        print(f"   📊 RICOSTRUZIONE COMPLETATA:")
        print(f"      • Coppie in blacklist: {num_coppie_blacklist}")
        print(f"      • Studenti con contatore trio: {num_studenti_trio}")

class PopupLayoutStorico(QDialog):
    """
    Finestra popup per visualizzare il layout di un'assegnazione storica.
    Mostra la griglia dell'aula con studenti posizionati + bottoni export.
    """

    def __init__(self, parent, config_app, indice_assegnazione):
        """
        Inizializza il popup.

        Args:
            parent: Finestra parent (FinestraPostiPerfetti)
            config_app: Oggetto ConfigurazioneApp
            indice_assegnazione: Indice dell'assegnazione nello storico
        """
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.indice_assegnazione = indice_assegnazione

        # Ricostruisce il layout
        self.config_ricostruita, self.dati_assegnazione = self.config_app.ricostruisci_layout_da_storico(indice_assegnazione)

        if not self.config_ricostruita or not self.dati_assegnazione:
            # Mostra errore e chiudi popup
            QMessageBox.warning(
                parent,
                "Errore Ricostruzione",
                "❌ Impossibile ricostruire il layout.\n\n"
                "Possibili cause:\n"
                "• Assegnazione in formato vecchio (senza coordinate)\n"
                "• Dati JSON corrotti\n\n"
                "Questa assegnazione non può essere visualizzata."
            )
            self.reject()  # Chiude il popup
            return

        # Setup interfaccia
        self._setup_ui()
        self._applica_stile()

    def _setup_ui(self):
        """Crea l'interfaccia del popup."""
        # Configurazione finestra
        nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione Storico')
        data_assegnazione = self.dati_assegnazione.get('data', 'N/A')

        self.setWindowTitle(f"🔍 Layout Assegnazione - {nome_assegnazione} - {data_assegnazione}")
        self.setMinimumSize(1250, 750)
        self.resize(1150, 750)  # Imposta anche dimensione iniziale

        # Layout principale verticale
        layout_principale = QVBoxLayout(self)

        # === HEADER: Informazioni assegnazione ===
        header_widget = self._crea_header()
        layout_principale.addWidget(header_widget)

        # === GRIGLIA AULA (scrollabile) ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        widget_griglia = QWidget()
        self.layout_griglia = QGridLayout(widget_griglia)

        # Popola la griglia con il layout ricostruito
        self._popola_griglia_aula()

        scroll_area.setWidget(widget_griglia)
        layout_principale.addWidget(scroll_area)

        # === FOOTER: Bottoni export ===
        footer_widget = self._crea_footer()
        layout_principale.addWidget(footer_widget)

    def _crea_header(self):
        """Crea il widget header con info assegnazione."""
        header = QGroupBox("📋 Informazioni Assegnazione")
        layout = QVBoxLayout(header)

        # Nome assegnazione
        label_nome = QLabel(f"<b>Nome:</b> {self.dati_assegnazione.get('nome', 'N/A')}")
        label_nome.setStyleSheet("font-size: 13px;")
        layout.addWidget(label_nome)

        # Data e ora
        data = self.dati_assegnazione.get('data', 'N/A')
        ora = self.dati_assegnazione.get('ora', 'N/A')
        label_data = QLabel(f"<b>Data/Ora:</b> {data} - {ora}")
        layout.addWidget(label_data)

        # File origine
        file_origine = self.dati_assegnazione.get('file_origine', 'Non specificato')
        label_file = QLabel(f"<b>File origine:</b> {file_origine}")
        layout.addWidget(label_file)

        # Configurazione aula
        config_aula = self.dati_assegnazione.get('configurazione_aula', {})
        num_file = config_aula.get('num_file', '?')
        posti_fila = config_aula.get('posti_per_fila', '?')
        num_studenti = config_aula.get('num_studenti', '?')
        label_config = QLabel(f"<b>Configurazione:</b> {num_file} file × {posti_fila} posti - {num_studenti} studenti")
        layout.addWidget(label_config)

        return header

    def _crea_footer(self):
        """Crea il widget footer con bottoni export."""
        footer = QWidget()
        layout = QHBoxLayout(footer)

        # Bottone Export Excel
        btn_excel = QPushButton("📊 Esporta Excel")
        btn_excel.setMinimumHeight(45)
        btn_excel.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_excel.clicked.connect(self._esporta_excel)
        layout.addWidget(btn_excel)

        # Bottone Export Report TXT
        btn_report = QPushButton("📋 Salva Report TXT")
        btn_report.setMinimumHeight(45)
        btn_report.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        btn_report.clicked.connect(self._salva_report_txt)
        layout.addWidget(btn_report)

        # Bottone Chiudi
        btn_chiudi = QPushButton("❌ Chiudi")
        btn_chiudi.setMinimumHeight(45)
        btn_chiudi.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        btn_chiudi.clicked.connect(self.close)
        layout.addWidget(btn_chiudi)

        return footer

    def _popola_griglia_aula(self):
        """Popola la griglia con il layout ricostruito."""
        # Pulisce layout esistente
        while self.layout_griglia.count():
            child = self.layout_griglia.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Ricrea griglia dal layout ricostruito - ORDINE INVERTITO
        # Arredi (LIM, CAT, LAV) in basso, ultima fila banchi in alto
        griglia_invertita = list(reversed(self.config_ricostruita.griglia))
        for riga_idx, riga in enumerate(griglia_invertita):
            for col_idx, posto in enumerate(riga):
                # Riutilizza il metodo esistente dalla finestra principale
                widget_posto = self.parent_window._crea_widget_posto(posto)
                self.layout_griglia.addWidget(widget_posto, riga_idx, col_idx)

    def _applica_stile(self):
        """Applica il tema attivo al popup layout storico."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {C("bordo_normale")};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: {C("sfondo_pannello")};
                color: {C("testo_principale")};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QLabel {{
                color: {C("testo_principale")};
            }}
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_pannello")};
            }}
        """)

    def _esporta_excel(self):
        """Esporta il layout ricostruito in formato Excel."""
        try:
            # Suggerisce nome file basato su nome assegnazione salvato
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            data = self.dati_assegnazione.get('data', '').replace('-', '')
            ora = self.dati_assegnazione.get('ora', '').replace(':', '')
            nome_suggerito = f"{nome_pulito}_{data}_{ora}.xlsx"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Esporta Layout in Excel",
                nome_suggerito,
                "File Excel (*.xlsx);;Tutti i file (*)"
            )

            if file_path:
                # Crea file Excel riutilizzando metodo esistente
                # NOTA: Il metodo _crea_file_excel della parent window richiede un AssegnatorePosti
                # ma noi abbiamo solo ConfigurazioneAula - dobbiamo creare un oggetto fittizio

                # Crea AssegnatorePosti fittizio con dati ricostruiti
                assegnatore_fittizio = self._crea_assegnatore_fittizio()

                # Chiama metodo esistente per creare Excel
                self.parent_window._crea_file_excel(file_path, assegnatore_fittizio)

                mostra_popup_file_salvato(self, "Export Completato", "✅ File Excel salvato con successo!", file_path)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore Export",
                f"❌ Errore durante l'export Excel:\n{str(e)}"
            )

    def _salva_report_txt(self):
        """Salva il report testuale dell'assegnazione."""
        try:
            # Suggerisce nome file basato su nome assegnazione salvato
            nome_assegnazione = self.dati_assegnazione.get('nome', 'Assegnazione')
            nome_pulito = pulisci_nome_file(nome_assegnazione)
            data = self.dati_assegnazione.get('data', '').replace('-', '')
            ora = self.dati_assegnazione.get('ora', '').replace(':', '')
            nome_suggerito = f"{nome_pulito}_{data}_{ora}.txt"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva Report TXT",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                # Genera report testuale
                report = self._genera_report_testuale()

                # Salva su file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report)

                mostra_popup_file_salvato(self, "Report Salvato", "✅ Report TXT salvato con successo!", file_path)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore Salvataggio",
                f"❌ Errore durante il salvataggio:\n{str(e)}"
            )

    def _crea_assegnatore_fittizio(self):
        """
        Crea un oggetto AssegnatorePosti fittizio per riutilizzare _crea_file_excel.
        Estrae le informazioni dal layout ricostruito.
        """
        from algoritmo.algoritmo import AssegnatorePosti

        assegnatore = AssegnatorePosti()
        assegnatore.configurazione_aula = self.config_ricostruita

        # Estrae coppie e trio dal layout salvato
        layout_data = self.dati_assegnazione.get('layout', [])

        # Ricostruisce coppie (serve per statistiche Excel)
        coppie_ricostruite = []
        trio_ricostruito = None

        # Mappa studenti per tipo abbinamento
        studenti_per_tipo = {}
        for studente_info in layout_data:
            nome = studente_info['studente']
            studenti_per_tipo[nome] = studente_info

        # Ricostruisce coppie
        coppie_processate = set()
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'coppia':
                compagno = info.get('compagno')
                # Evita duplicati (coppia A-B = coppia B-A)
                coppia_key = tuple(sorted([nome_studente, compagno]))
                if coppia_key not in coppie_processate:
                    coppie_processate.add(coppia_key)

                    # Crea oggetti Student fittizi
                    from modelli.studenti import Student
                    parti1 = nome_studente.split(' ', 1)
                    parti2 = compagno.split(' ', 1)

                    s1 = Student(parti1[0], parti1[1] if len(parti1) > 1 else '', 'M')
                    s2 = Student(parti2[0], parti2[1] if len(parti2) > 1 else '', 'F')

                    # Info punteggio (se disponibile)
                    punteggio = info.get('punteggio', 0)
                    info_coppia = {
                        'punteggio_totale': punteggio,
                        'valutazione': 'STORICO',
                        'note': []
                    }

                    coppie_ricostruite.append((s1, s2, info_coppia))

        # Ricostruisce trio se presente
        trio_nomi = []
        for nome_studente, info in studenti_per_tipo.items():
            if info.get('tipo') == 'trio':
                trio_nomi.append(nome_studente)

        if len(trio_nomi) == 3:
            from modelli.studenti import Student
            trio_studenti = []
            for nome in sorted(trio_nomi):  # Ordina per avere sempre stesso ordine
                parti = nome.split(' ', 1)
                s = Student(parti[0], parti[1] if len(parti) > 1 else '', 'M')
                trio_studenti.append(s)
            trio_ricostruito = trio_studenti

        assegnatore.coppie_formate = coppie_ricostruite
        assegnatore.trio_identificato = trio_ricostruito
        assegnatore.studenti_singoli = []

        # Statistiche fittizie (non abbiamo i dati originali)
        assegnatore.stats = {
            'coppie_ottimali': 0,
            'coppie_accettabili': len(coppie_ricostruite),
            'coppie_problematiche': 0,
            'coppie_riutilizzate': 0
        }

        return assegnatore

    def _genera_report_testuale(self):
        """Genera il report testuale completo dell'assegnazione."""
        # Usa il report completo salvato se disponibile
        if "report_completo" in self.dati_assegnazione:
            return self.dati_assegnazione["report_completo"]

        # FALLBACK: Genera report basilare dal layout
        report = []

        # Header
        report.append("═" * 70)
        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("═" * 70)

        # Informazioni base
        report.append(f"Classe: {self.dati_assegnazione.get('nome', 'N/A')}")
        report.append(f"File origine: {self.dati_assegnazione.get('file_origine', 'Non specificato')}")
        report.append(f"Data/Ora: {self.dati_assegnazione.get('data', 'N/A')} {self.dati_assegnazione.get('ora', 'N/A')}")

        # Configurazione aula
        config = self.dati_assegnazione.get('configurazione_aula', {})
        report.append(f"Studenti elaborati: {config.get('num_studenti', 'N/A')}")
        report.append("")

        # Layout salvato
        layout_data = self.dati_assegnazione.get('layout', [])

        # Conta tipi abbinamenti
        num_coppie = len([s for s in layout_data if s.get('tipo') == 'coppia']) // 2
        num_trio = len([s for s in layout_data if s.get('tipo') == 'trio'])

        report.append("📊 STATISTICHE GENERALI")
        report.append("─" * 70)
        report.append(f"Coppie totali: {num_coppie}")
        if num_trio > 0:
            report.append(f"Trio formato: 1 ({num_trio} studenti)")
        report.append("")

        # Lista abbinamenti
        report.append("💥 ABBINAMENTI FORMATI")
        report.append("─" * 70)

        # Coppie
        coppie_mostrate = set()
        idx_coppia = 1
        for studente_info in layout_data:
            if studente_info.get('tipo') == 'coppia':
                nome = studente_info['studente']
                compagno = studente_info.get('compagno', '?')
                coppia_key = tuple(sorted([nome, compagno]))

                if coppia_key not in coppie_mostrate:
                    coppie_mostrate.add(coppia_key)
                    punteggio = studente_info.get('punteggio', 'N/A')
                    report.append(f"{idx_coppia:2d}. {nome} + {compagno}")
                    report.append(f"    Punteggio: {punteggio}")
                    report.append("")
                    idx_coppia += 1

        # Trio
        if num_trio > 0:
            trio_studenti = [s['studente'] for s in layout_data if s.get('tipo') == 'trio']
            if len(trio_studenti) == 3:
                report.append("💥 TRIO FORMATO")
                report.append("─" * 70)
                report.append(f"Trio: {' + '.join(trio_studenti)}")
                report.append("")

        report.append("═" * 70)

        return "\n".join(report)

class WorkerThread(QThread):
    """
    Thread separato per eseguire l'algoritmo di assegnazione senza bloccare l'interfaccia.
    """

    # Signals per comunicare con l'interfaccia principale
    progress_updated = Signal(int)  # Percentuale di completamento
    status_updated = Signal(str)    # Messaggio di stato
    completed = Signal(object)      # Risultato finale (AssegnatorePosti)
    error_occurred = Signal(str)    # Messaggio di errore

    def __init__(self, studenti, configurazione_aula, config_app, modalita_rotazione=False, modalita_trio='auto', flag_genere_misto=False):
        super().__init__()
        self.studenti = studenti
        self.configurazione_aula = configurazione_aula
        self.config_app = config_app
        self.modalita_rotazione = modalita_rotazione  # Flag rotazione per penalità storico
        self.modalita_trio = modalita_trio             # Posizione trio: 'prima', 'ultima', 'centro'
        self.flag_genere_misto = flag_genere_misto     # Flag genere misto dal checkbox

    def run(self):
        """Esegue l'assegnazione in background."""
        try:
            self.status_updated.emit("🔄 Inizializzazione algoritmo...")
            self.progress_updated.emit(10)

            # Crea l'assegnatore con configurazione personalizzata
            assegnatore = AssegnatorePosti()

            # Passa parametri necessari all'assegnatore per penalità storico
            assegnatore.config_app = self.config_app
            assegnatore.modalita_rotazione = self.modalita_rotazione
            print(f"🔧 Assegnatore configurato: rotazione={self.modalita_rotazione}")

            # NUOVO SISTEMA: Pesi fissi, solo flag genere misto configurabile
            motore = assegnatore.motore_vincoli
            # I pesi sono ora fissi in MotoreVincoli, non più configurabili
            # Imposta flag genere misto obbligatorio dal checkbox
            motore.imposta_genere_misto_obbligatorio(self.flag_genere_misto)

            # NUOVO: Passa riferimento configurazione per equità tentativo 4
            motore._config_app_ref = self.config_app
            print(f"🔧 Motore vincoli configurato con riferimento config per equità")

            # APPLICA PENALITÀ STORICO SOLO SE ROTAZIONE MENSILE
            if self.modalita_rotazione:  # Nuovo parametro da aggiungere
                self._applica_penalita_storico(motore)
            else:
                print("🆕 Modalità 'Prima assegnazione': storico ignorato")

            self.status_updated.emit("🧮 Calcolo coppie ottimali...")
            self.progress_updated.emit(30)

            self.status_updated.emit("📍 Assegnazione posizioni...")
            self.progress_updated.emit(60)

            # Esegue l'assegnazione completa
            successo = assegnatore.esegui_assegnazione_completa(
                self.studenti,
                self.configurazione_aula,
                self.modalita_trio  # USA LA VARIABILE DI ISTANZA
            )

            self.progress_updated.emit(90)

            if successo:
                self.status_updated.emit("✅ Assegnazione completata!")
                self.progress_updated.emit(100)
                self.completed.emit(assegnatore)
            else:
                self.error_occurred.emit("Assegnazione fallita - vincoli irrisolvibili")

        except Exception as e:
            self.error_occurred.emit(f"Errore durante l'assegnazione: {str(e)}")

    def _applica_penalita_storico(self, motore_vincoli: MotoreVincoli):
        """
        Modifica il motore vincoli per penalizzare coppie già utilizzate.
        """
        coppie_usate = self.config_app.config_data["coppie_da_evitare"]

        if not coppie_usate:
            return  # Nessuno storico, niente da fare

        # Salva il metodo originale
        calcola_originale = motore_vincoli.calcola_punteggio_coppia

        def calcola_con_penalita_storico(studente1: Student, studente2: Student) -> Dict:
            # Calcola punteggio normale
            risultato = calcola_originale(studente1, studente2)

            # Cerca se questa coppia è già stata usata
            for coppia_usata in coppie_usate:
                # Estrae nomi dalla coppia in blacklist (formato unico)
                studenti = coppia_usata.get("studenti", [])
                if len(studenti) != 2:
                    continue  # Salta voci malformate
                cognomi_coppia = {studenti[0], studenti[1]}

                # Confronta con la coppia attuale usando nomi completi
                cognomi_attuali = {studente1.get_nome_completo(), studente2.get_nome_completo()}

                if cognomi_coppia == cognomi_attuali:
                    volte_usata = coppia_usata["volte_usata"]
                    penalita = 500 * volte_usata  # Penalità aumentata per scoraggiare riutilizzo

                    # Trova QUANDO è stata usata (cerca nelle assegnazioni storiche)
                    info_quando = self._trova_quando_coppia_usata(cognomi_attuali)

                    risultato["punteggio_totale"] -= penalita
                    if info_quando:
                        risultato["note"].append(f"Coppia già usata {volte_usata} volte (penalità: -{penalita}) - {info_quando}")
                    else:
                        risultato["note"].append(f"Coppia già usata {volte_usata} volte (penalità: -{penalita})")

                    # Aggiusta valutazione
                    if risultato["punteggio_totale"] < 0:
                        risultato["valutazione"] = "RIUTILIZZATA"
                    break

            return risultato

        # Sostituisce il metodo con la versione che include le penalità
        motore_vincoli.calcola_punteggio_coppia = calcola_con_penalita_storico

    def _trova_quando_coppia_usata(self, cognomi_coppia):
        """
        Trova quando una coppia è stata usata nelle assegnazioni precedenti.

        Args:
            cognomi_coppia: Set con i nomi completi dei due studenti

        Returns:
            str: Informazione su quando è stata usata (es: "ultima volta: Assegnazione 21/09/2025")
        """
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        # Cerca nell'ordine cronologico inverso (più recenti per primi)
        assegnazioni_trovate = []

        for assegnazione in reversed(storico):
            nome_assegnazione = assegnazione.get("nome", "Assegnazione senza nome")
            data_assegnazione = assegnazione.get("data", "")
            abbinamenti = assegnazione.get("abbinamenti", [])

            # Cerca la coppia negli abbinamenti (sia coppie normali che trio)
            for abbinamento in abbinamenti:
                trovata_in_abbinamento = False

                # Cerca nelle coppie normali
                if abbinamento.get("tipo") == "coppia":
                    studenti_abbinamento = set(abbinamento.get("studenti", []))
                    if studenti_abbinamento == cognomi_coppia:
                        assegnazioni_trovate.append(f"{nome_assegnazione} ({data_assegnazione})")
                        trovata_in_abbinamento = True

                # NUOVO: Cerca nei trio (coppie virtuali adiacenti)
                elif abbinamento.get("tipo") == "trio":
                    studenti_trio = abbinamento.get("studenti", [])
                    if len(studenti_trio) == 3:
                        # Le 2 coppie virtuali adiacenti nel trio
                        coppia_virtuale_1 = set([studenti_trio[0], studenti_trio[1]])
                        coppia_virtuale_2 = set([studenti_trio[1], studenti_trio[2]])

                        if cognomi_coppia == coppia_virtuale_1 or cognomi_coppia == coppia_virtuale_2:
                            assegnazioni_trovate.append(f"{nome_assegnazione} ({data_assegnazione}) [trio]")
                            trovata_in_abbinamento = True

                if trovata_in_abbinamento:
                    break  # Trovata in questa assegnazione, passa alla prossima

        if assegnazioni_trovate:
            if len(assegnazioni_trovate) == 1:
                return f"usata in: {assegnazioni_trovate[0]}"
            else:
                return f"ultima volta: {assegnazioni_trovate[0]}"

        return None  # Non trovata (non dovrebbe succedere se penalità applicata)

class FinestraPostiPerfetti(QMainWindow):
    """
    Finestra principale dell'applicazione.
    """

    def __init__(self):
        super().__init__()

        # Configurazione dell'applicazione
        self.config_app = ConfigurazioneApp()
        self.config_app.carica_configurazione()

        # Dati dell'applicazione
        self.studenti = []
        self.configurazione_aula = None
        self.ultimo_assegnatore = None
        self.file_origine_studenti = None  # Nome del file .txt caricato

        # Flag per tracking posti insufficienti
        self.posti_insufficienti = False

        # Flag per tracking assegnazione non salvata nello storico
        # Diventa True dopo un'elaborazione completata, torna False dopo il salvataggio
        self.assegnazione_non_salvata = False

        # Sistema messaggi rotativi per feedback elaborazione
        self.timer_messaggi = QTimer()
        self.timer_messaggi.timeout.connect(self._aggiorna_messaggio_elaborazione)
        self.indice_messaggio = 0
        self.messaggi_elaborazione = [
            "🔄 Elaborazione in corso...",
            "🧮 Calcolo coppie ottimali...",
            "🔍 Verifica vincoli...",
            "⚡ Ottimizzazione assegnazione...",
            "🎯 Ricerca soluzione migliore...",
            "🔄 Elaborazione in corso..."
        ]

        # Setup interfaccia
        self.setWindowTitle("«PostiPerfetti» — v2.0")
        self.setMinimumSize(1300, 850)
        # Apre la finestra massimizzata per una migliore visualizzazione
        self.showMaximized()
        self.setup_ui()
        self.setup_stili()

        # Carica dati iniziali se disponibili
        self._carica_dati_iniziali()

        # Applica gli stili inline al tema attivo (caricato da config o default scuro)
        self._aggiorna_stili_widget()

    def setup_ui(self):
        """Crea l'interfaccia utente principale."""

        # Widget centrale con layout principale
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout principale orizzontale
        main_layout = QHBoxLayout(central_widget)

        # PANNELLO SINISTRO: Controlli e configurazione
        left_panel = self._crea_pannello_controlli()
        main_layout.addWidget(left_panel, 1)  # 1/4 dello spazio

        # PANNELLO DESTRO: Visualizzazione risultati
        right_panel = self._crea_pannello_risultati()
        main_layout.addWidget(right_panel, 4)  # 3/4 dello spazio

    def _crea_pannello_controlli(self) -> QWidget:
        """Crea il pannello sinistro con tutti i controlli, dentro una QScrollArea
        per adattarsi anche a schermi piccoli (notebook 13")."""

        # === SCROLL AREA: contenitore esterno scrollabile ===
        # Su schermi grandi: nessuna scrollbar visibile, aspetto identico a prima.
        # Su schermi piccoli (13"): appare la scrollbar verticale invece di
        # schiacciare/tagliare i widget.
        self.scroll_pannello_sx = QScrollArea()
        self.scroll_pannello_sx.setWidgetResizable(True)
        # Scrollbar orizzontale: MAI (il pannello non deve allargarsi)
        self.scroll_pannello_sx.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Scrollbar verticale: solo se il contenuto non entra nello schermo
        self.scroll_pannello_sx.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Bordo invisibile: la scroll area non deve aggiungere cornici visive
        self.scroll_pannello_sx.setFrameShape(QFrame.NoFrame)
        # Larghezza minima: impedisce al pannello destro di "mangiare" il sinistro
        # quando la finestra viene ridimensionata. 360px è sufficiente per contenere
        # tutti i pulsanti, label e il box vincoli con font 12pt.
        # CONFIGURABILE: aumenta se i contenuti risultano ancora tagliati,
        # riduci (min ~300) se vuoi permettere finestre più strette.
        self.scroll_pannello_sx.setMinimumWidth(460)

        # Widget interno che contiene tutti i controlli
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # === FONT PIÙ GRANDE PER TUTTO IL PANNELLO SINISTRO ===
        # Impostazione globale: tutti i widget figli ereditano questo font
        font_pannello = QFont()
        font_pannello.setPointSize(12)  # Font base più grande (default ~9-10)
        panel.setFont(font_pannello)

        # === ICONA DEL PROGRAMMA ===
        # Inserita in cima al pannello sinistro, sopra i bottoni Istruzioni/Tema.
        # Usare QLabel con QPixmap è il metodo più stabile in PySide6 per mostrare immagini.
        icona_label = QLabel()
        icona_path = os.path.join(get_base_path(), "modelli", "postiperfetti_logo.png")
        if os.path.exists(icona_path):
            pixmap = QPixmap(icona_path)
            # Dimensione massima del logo — ridotta per compatibilità con schermi 13".
            # Il valore precedente (324×163) era più largo del pannello stesso su notebook!
            # CONFIGURABILE: modifica questi valori per ingrandire/rimpicciolire il logo
            LOGO_LARGHEZZA_MAX = 220  # pixel — larghezza massima
            LOGO_ALTEZZA_MAX = 110    # pixel — altezza massima
            pixmap = pixmap.scaled(LOGO_LARGHEZZA_MAX, LOGO_ALTEZZA_MAX,
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icona_label.setPixmap(pixmap)
        else:
            # Fallback silenzioso: se il file non c'è (es. distribuzione incompleta)
            # non mostra nulla e non causa errori.
            icona_label.setText("🪑")
            icona_label.setStyleSheet("font-size: 40px;")

        # Centra orizzontalmente l'icona nel pannello
        icona_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icona_label)

        # Piccolo spazio tra icona e bottoni (ridotto per schermi compatti)
        layout.addSpacing(10)

        # ─────────────────────────────────────────────────
        # SPAZIATURA TRA I BOX — VALORE REGOLABILE
        # Modifica questo valore per aumentare/diminuire
        # lo spazio tra un gruppo e l'altro nel pannello.
        # Valori consigliati: 6 (compatto), 8 (normale), 12 (ampio)
        SPAZIO_TRA_BOX = 8
        # ─────────────────────────────────────────────────

        # === RIGA IN CIMA: Istruzioni + Toggle tema affiancati ===
        riga_cima = QHBoxLayout()

        # Bottone Istruzioni
        self.btn_istruzioni = QPushButton("📖 Istruzioni")
        self.btn_istruzioni.setStyleSheet("""
            QPushButton {
                background-color: #5C6BC0;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #3F51B5;
            }
        """)
        self.btn_istruzioni.setToolTip("Mostra la guida completa all'uso del programma")
        self.btn_istruzioni.clicked.connect(self._mostra_istruzioni)
        # stretch 2 → occupa circa 2/3 della riga
        riga_cima.addWidget(self.btn_istruzioni, 2)

        # Bottone toggle tema: colore ambra/ocra per distinguerlo da Istruzioni.
        # stretch 1 = occupa ~1/3 della riga (Istruzioni ha stretch 2 = ~2/3)
        self.btn_toggle_tema = QPushButton("☀️ Chiaro")
        self.btn_toggle_tema.setStyleSheet("""
            QPushButton {
                background-color: #F57F17;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 8px;
            }
            QPushButton:hover {
                background-color: #E65100;
            }
        """)
        self.btn_toggle_tema.setToolTip("Alterna tra tema scuro e tema chiaro")
        self.btn_toggle_tema.clicked.connect(self._cambia_tema)
        # stretch 1 → occupa circa 1/3 della riga
        riga_cima.addWidget(self.btn_toggle_tema, 1)

        # Bottone "Info / Crediti": piccolo bottone rotondo per mostrare
        # informazioni sul programma, l'autore e la licenza.
        self.btn_crediti = QPushButton("ℹ️")
        self.btn_crediti.setFixedSize(42, 42)
        self.btn_crediti.setToolTip("Informazioni e crediti")
        self.btn_crediti.setStyleSheet("""
            QPushButton {
                background-color: #546E7A;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 21px;
                border: none;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #37474F;
            }
        """)
        self.btn_crediti.clicked.connect(self._mostra_crediti)
        riga_cima.addWidget(self.btn_crediti, 0)  # stretch 0 → dimensione fissa

        layout.addLayout(riga_cima)

        # Spazio tra pulsante Istruzioni e primo box
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === SEZIONE 1: CARICAMENTO DATI ===
        group_dati = QGroupBox("📂 CARICAMENTO DATI")
        layout_dati = QVBoxLayout(group_dati)

        # Nome classe (read-only: si popola automaticamente dal nome del file .txt)
        self.input_nome_classe = QLineEdit()
        self.input_nome_classe.setPlaceholderText("<si compila automaticamente>")
        self.input_nome_classe.setReadOnly(True)
        self.input_nome_classe.setStyleSheet("""
            QLineEdit {
                background-color: #353535;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
        """)
        layout_dati.addWidget(QLabel("Nome classe:"))
        layout_dati.addWidget(self.input_nome_classe)

        # Caricamento file studenti
        btn_carica_studenti = QPushButton("📁 Seleziona file classe (.txt)")
        btn_carica_studenti.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_primario_sf")};
                color: {C("btn_primario_txt")};
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 16px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {C("btn_primario_hover")};
            }}
        """)
        btn_carica_studenti.setToolTip("Apri il file .txt di una classe")
        btn_carica_studenti.clicked.connect(self.carica_file_studenti)
        layout_dati.addWidget(btn_carica_studenti)

        self.label_studenti_caricati = QLabel("Nessun file caricato")
        self.label_studenti_caricati.setStyleSheet("color: gray; font-style: italic;")
        # Word wrap: il testo lungo (es. "Nuova classe nell'Editor — Clicca...")
        # va a capo automaticamente invece di allargare il pannello sinistro
        self.label_studenti_caricati.setWordWrap(True)
        layout_dati.addWidget(self.label_studenti_caricati)

        layout.addWidget(group_dati)
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === SEZIONE 2: CONFIGURAZIONE AULA ===
        group_aula = QGroupBox("🏫 CONFIGURAZIONE AULA")
        layout_aula = QVBoxLayout(group_aula)
        layout_aula.setSpacing(6)

        # --- RIGA 1: File di banchi (centrata) ---
        riga_file = QHBoxLayout()
        riga_file.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        riga_file.addWidget(QLabel(" File di banchi: "))
        riga_file.addSpacing(8)

        # === NUMERO DI FILE - Widget personalizzato con bottoni visibili ===
        # Container per campo + bottoni (larghezza limitata per non sprecare spazio)
        container_file = QWidget()
        container_file.setMaximumWidth(130)  # — [campo] + bastano ~130px
        layout_file = QHBoxLayout(container_file)
        layout_file.setContentsMargins(0, 0, 0, 0)
        layout_file.setSpacing(4)

        # Campo numero (read-only, centrato)
        # Valore iniziale: SEMPRE il default (4 file), indipendentemente
        # dall'ultimo valore salvato in config.json. Il numero di file
        # è un parametro operativo che dipende dalla classe/aula corrente,
        # non una preferenza persistente come il tema.
        NUM_FILE_DEFAULT = 4  # Configurabile: default ragionevole per la maggior parte delle aule
        self.input_num_file = QLineEdit()
        self.input_num_file.setText(str(NUM_FILE_DEFAULT))
        self.input_num_file.setReadOnly(True)
        self.input_num_file.setAlignment(Qt.AlignCenter)
        self.input_num_file.setMaximumWidth(50)
        self.input_num_file.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: white;
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        # Bottone - (diminuisci)
        self.btn_file_meno = QPushButton("−")  # Unicode minus sign (più largo)
        self.btn_file_meno.setMaximumWidth(30)
        self.btn_file_meno.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #f44336;
                border: 1px solid #c62828;
            }
        """)
        self.btn_file_meno.setToolTip("Riduci il numero di file di banchi")
        self.btn_file_meno.clicked.connect(lambda: self._cambia_num_file(-1))

        # Bottone + (aumenta)
        self.btn_file_piu = QPushButton("+")
        self.btn_file_piu.setMaximumWidth(30)
        self.btn_file_piu.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
                border: 1px solid #2E7D32;
            }
        """)
        self.btn_file_piu.setToolTip("Aggiungi una fila di banchi")
        self.btn_file_piu.clicked.connect(lambda: self._cambia_num_file(+1))

        # Assembla il widget
        layout_file.addWidget(self.btn_file_meno)
        layout_file.addWidget(self.input_num_file)
        layout_file.addWidget(self.btn_file_piu)

        riga_file.addWidget(container_file)
        riga_file.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_file)

        # --- RIGA 2: Posti per fila (centrata) ---
        riga_posti_fila = QHBoxLayout()
        riga_posti_fila.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        riga_posti_fila.addWidget(QLabel(" Posti per fila: "))
        riga_posti_fila.addSpacing(8)

        # === POSTI PER FILA - Widget personalizzato (solo valori PARI) ===

        # Container per campo + bottoni (larghezza limitata per non sprecare spazio)
        container_posti = QWidget()
        container_posti.setMaximumWidth(130)  # — [campo] + bastano ~130px
        layout_posti = QHBoxLayout(container_posti)
        layout_posti.setContentsMargins(0, 0, 0, 0)
        layout_posti.setSpacing(4)

        # Campo numero (read-only, centrato)
        # Valore iniziale: SEMPRE il default (6 posti), stessa logica di num_file.
        # Deve essere PARI (i banchi sono da 2), quindi 6 è il valore più comune.
        POSTI_PER_FILA_DEFAULT = 6  # Configurabile: deve essere pari (banchi da 2)
        self.input_posti_fila = QLineEdit()
        self.input_posti_fila.setText(str(POSTI_PER_FILA_DEFAULT))
        self.input_posti_fila.setReadOnly(True)
        self.input_posti_fila.setAlignment(Qt.AlignCenter)
        self.input_posti_fila.setMaximumWidth(50)
        self.input_posti_fila.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: white;
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }
        """)

        # Bottone - (diminuisci di 2)
        self.btn_posti_meno = QPushButton("−")
        self.btn_posti_meno.setMaximumWidth(30)
        self.btn_posti_meno.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #f44336;
                border: 1px solid #c62828;
            }
        """)
        self.btn_posti_meno.setToolTip("Riduci i posti per fila (di 2 alla volta)")
        self.btn_posti_meno.clicked.connect(lambda: self._cambia_posti_fila(-2))

        # Bottone + (aumenta di 2)
        self.btn_posti_piu = QPushButton("+")
        self.btn_posti_piu.setMaximumWidth(30)
        self.btn_posti_piu.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
                border: 1px solid #2E7D32;
            }
        """)
        self.btn_posti_piu.setToolTip("Aggiungi 2 posti per fila")
        self.btn_posti_piu.clicked.connect(lambda: self._cambia_posti_fila(+2))

        # Assembla il widget
        layout_posti.addWidget(self.btn_posti_meno)
        layout_posti.addWidget(self.input_posti_fila)
        layout_posti.addWidget(self.btn_posti_piu)

        riga_posti_fila.addWidget(container_posti)
        riga_posti_fila.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_posti_fila)

        # --- RIGA 3: Posti totali + bottone aiuto (centrata) ---
        riga_posti = QHBoxLayout()
        riga_posti.addStretch()  # Spazio elastico a sinistra → centra il contenuto
        self.label_posti_totali = QLabel("Posti totali: 24")
        riga_posti.addWidget(self.label_posti_totali)
        riga_posti.addSpacing(6)

        # Bottone "?" per spiegare visivamente il layout dell'aula
        btn_aiuto_aula = QPushButton("?")
        btn_aiuto_aula.setFixedSize(24, 24)
        btn_aiuto_aula.setToolTip("Clicca per capire come contare file e posti")
        btn_aiuto_aula.setStyleSheet("""
            QPushButton {
                background-color: #5C6BC0;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 12px;
                border: none;
                padding: 0px;
            }
            QPushButton:hover { background-color: #3F51B5; }
        """)
        btn_aiuto_aula.clicked.connect(self._mostra_aiuto_configurazione_aula)
        riga_posti.addWidget(btn_aiuto_aula)
        riga_posti.addStretch()  # Spazio elastico a destra → centra il contenuto
        layout_aula.addLayout(riga_posti)

        layout.addWidget(group_aula)
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === GESTIONE NUMERO DISPARI ===
        self.group_dispari = QGroupBox("GESTIONE NUMERO DISPARI")
        layout_dispari = QVBoxLayout(self.group_dispari)

        # Info label
        self.label_info_dispari = QLabel("Se il numero di studenti è dispari, il banco da 3 sarà posizionato:")
        self.label_info_dispari.setStyleSheet(f"color: {C('testo_info')}; font-size: 12px; font-style: italic;")
        layout_dispari.addWidget(self.label_info_dispari)

        # Radio buttons per posizione trio
        # NOTA: Rimossa opzione "Automatico" perché non offre vantaggi reali
        # L'algoritmo forma sempre le stesse coppie indipendentemente dalla posizione fisica del trio
        self.radio_trio_prima = QRadioButton("Inizio (prima fila)")
        self.radio_trio_prima.setChecked(True)  # Default: prima fila (scelta più comune)
        self.radio_trio_ultima = QRadioButton("Fine (ultima fila)")
        self.radio_trio_centro = QRadioButton("Centro aula")

        layout_dispari.addWidget(self.radio_trio_prima)
        layout_dispari.addWidget(self.radio_trio_ultima)
        layout_dispari.addWidget(self.radio_trio_centro)

        # Inizialmente nascosto
        self.group_dispari.setVisible(False)

        layout.addWidget(self.group_dispari)
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === SEZIONE 3: OPZIONI AVANZATE ===
        group_opzioni = QGroupBox("⚙️ OPZIONI VINCOLI")
        layout_opzioni = QVBoxLayout(group_opzioni)

        # Checkbox per preferenza genere misto
        # NOTA: Ora è una PREFERENZA FORTE, non più un vincolo assoluto
        # Questo permette di gestire classi sbilanciate e migliora le performance
        self.checkbox_genere_misto = QCheckBox("Preferisci coppie miste (M+F)")
        self.checkbox_genere_misto.setToolTip(
            "Se attivo, dà forte preferenza alle coppie miste.\n"
            "NON vieta coppie stesso genere se necessario per varietà rotazioni."
        )
        layout_opzioni.addWidget(self.checkbox_genere_misto)

        # Info sui vincoli fissi
        self.label_info_vincoli = QLabel("""
        🎯 IL PROGRAMMA OBBEDISCE A QUESTI VINCOLI AUTOMATICI:
        
          - Incompatibilità "livello 3": ASSOLUTA (alunni mai in coppia)
          - Posizione "PRIMA": OBBLIGATORIA (se posti disponibili)
          - "Coppie miste": vincolo FORTE ma NON assoluto
          - Affinità "livello 3": vincolo FORTE ma NON assoluto
                """)
        self.label_info_vincoli.setStyleSheet(f"color: {C('testo_label_sec')}; font-size: 13px; font-style: italic;")
        layout_opzioni.addWidget(self.label_info_vincoli)

        layout.addWidget(group_opzioni)
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === SEZIONE 4: MODALITÀ ASSEGNAZIONE ===
        group_modalita = QGroupBox("🔄 MODALITÀ ASSEGNAZIONE")
        layout_modalita = QVBoxLayout(group_modalita)

        self.radio_prima_volta = QRadioButton("Prima assegnazione dell'anno")
        self.radio_prima_volta.setToolTip("Usa questa modalità all'inizio dell'anno scolastico")
        self.radio_prima_volta.setChecked(True)
        layout_modalita.addWidget(self.radio_prima_volta)

        self.radio_rotazione = QRadioButton("Rotazione mensile (evitando coppie già formate)")
        self.radio_rotazione.setToolTip("Crea nuovi abbinamenti evitando le coppie delle assegnazioni precedenti")
        layout_modalita.addWidget(self.radio_rotazione)

        # Info storico
        self.label_storico = QLabel("Storico: nessuna assegnazione precedente")
        self.label_storico.setStyleSheet("color: gray; font-size: 12px; font-style: italic;")
        layout_modalita.addWidget(self.label_storico)

        layout.addWidget(group_modalita)
        layout.addSpacing(SPAZIO_TRA_BOX)

        # === BOTTONE PRINCIPALE ===
        self.btn_avvia_assegnazione = QPushButton("🚀 Avvia assegnazione automatica")
        self.btn_avvia_assegnazione.setMinimumHeight(50)
        self.btn_avvia_assegnazione.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.btn_avvia_assegnazione.setToolTip(
            "Calcola la disposizione ottimale dei posti\n"
            "rispettando vincoli, affinità e rotazioni precedenti"
        )
        self.btn_avvia_assegnazione.clicked.connect(self.avvia_assegnazione)
        self.btn_avvia_assegnazione.setEnabled(False)  # Disabilitato finché non si caricano dati

        layout.addWidget(self.btn_avvia_assegnazione)

        # Status label
        self.label_status = QLabel("")
        self.label_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_status)

        # Inserisce il widget dei controlli nella scroll area.
        # Su schermi grandi il contenuto entra tutto → nessuna scrollbar.
        # Su schermi piccoli → appare scrollbar verticale automatica.
        self.scroll_pannello_sx.setWidget(panel)

        return self.scroll_pannello_sx

    def _crea_pannello_risultati(self) -> QWidget:
        """Crea il pannello destro per visualizzare i risultati."""

        # Tab widget principale per organizzare i risultati
        self.tab_widget = QTabWidget()

        # === TAB 1: VISUALIZZAZIONE AULA ===
        self.tab_aula = QWidget()
        layout_aula = QVBoxLayout(self.tab_aula)

        # Area scrollabile per la visualizzazione dell'aula
        scroll_aula = QScrollArea()
        self.widget_aula = QWidget()
        self.layout_griglia_aula = QGridLayout(self.widget_aula)
        scroll_aula.setWidget(self.widget_aula)
        scroll_aula.setWidgetResizable(True)
        layout_aula.addWidget(scroll_aula)

        # Controlli per export - RIORGANIZZATI con nuovo bottone Report TXT
        controls_export = QHBoxLayout()

        # 1. SALVA ASSEGNAZIONE (verde scuro - azione primaria)
        self.btn_salva_progetto = QPushButton("💾 Salva assegnazione")
        self.btn_salva_progetto.setMinimumHeight(45)
        self.btn_salva_progetto.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1B5E20;
            }
            QPushButton:disabled {
                background-color: #9E9E9E;
                color: #616161;
            }
        """)
        self.btn_salva_progetto.setToolTip(
            "Salva l'assegnazione nello storico.\n"
            "Indispensabile per le rotazioni future!"
        )
        self.btn_salva_progetto.clicked.connect(self.salva_assegnazione)
        self.btn_salva_progetto.setEnabled(False)
        controls_export.addWidget(self.btn_salva_progetto)

        # 2. ESPORTA EXCEL (azzurro - export visuale)
        self.btn_export_excel = QPushButton("📊 Esporta Excel")
        self.btn_export_excel.setMinimumHeight(45)
        self.btn_export_excel.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #9E9E9E;
                color: #616161;
            }
        """)
        self.btn_export_excel.clicked.connect(self.esporta_excel)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "Salva prima l'assegnazione nello Storico per abilitare l'export."
        )
        controls_export.addWidget(self.btn_export_excel)

        # 3. ESPORTA REPORT TXT (arancione - export testuale) ⭐ NUOVO
        self.btn_export_report_txt = QPushButton("📋 Esporta report .txt")
        self.btn_export_report_txt.setMinimumHeight(45)
        self.btn_export_report_txt.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #9E9E9E;
                color: #616161;
            }
        """)
        self.btn_export_report_txt.clicked.connect(self.esporta_report_txt)
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "Salva prima l'assegnazione nello Storico per abilitare l'export."
        )
        controls_export.addWidget(self.btn_export_report_txt)

        controls_export.addStretch()
        layout_aula.addLayout(controls_export)

        self.tab_widget.addTab(self.tab_aula, "🏫 Aula")

        # === TAB 2: REPORT DETTAGLIATO ===
        self.tab_report = QWidget()
        layout_report = QVBoxLayout(self.tab_report)

        self.text_report = QTextEdit()
        self.text_report.setReadOnly(True)
        # Font monospazio cross-platform: "Consolas" (Windows) con fallback
        # automatico Qt al monospazio del sistema (Linux/macOS)
        font_report = QFont()
        font_report.setFamily("Consolas")
        font_report.setPointSize(9)
        font_report.setStyleHint(QFont.Monospace)
        self.text_report.setFont(font_report)
        layout_report.addWidget(self.text_report)

        self.tab_widget.addTab(self.tab_report, "📊 Report")

        # === TAB 3: STORICO ASSEGNAZIONI ===
        self.tab_storico = QWidget()
        layout_storico = QVBoxLayout(self.tab_storico)

        self.tabella_storico = QTableWidget()
        self.tabella_storico.setColumnCount(4)
        self.tabella_storico.setHorizontalHeaderLabels(["Data", "Nome", "Abbinamenti", "Azioni"])
        # Salva automaticamente se il docente rinomina un'assegnazione (colonna Nome)
        self.tabella_storico.cellChanged.connect(self._on_storico_nome_modificato)
        layout_storico.addWidget(self.tabella_storico)

        self.tab_widget.addTab(self.tab_storico, "📚 Storico")

        # === TAB 4: STATISTICHE AGGREGATE ===
        self.tab_statistiche = QWidget()
        layout_statistiche = QVBoxLayout(self.tab_statistiche)

        # Header con filtro classe
        header_stats = QHBoxLayout()

        label_filtro = QLabel("📊 Visualizza statistiche per:")
        label_filtro.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_stats.addWidget(label_filtro)

        self.filtro_classe_combo = QComboBox()
        self.filtro_classe_combo.setMinimumWidth(400)
        self.filtro_classe_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                font-size: 12px;
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: #404040;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
                background-color: #505050;
            }
            QComboBox QAbstractItemView {
                background-color: #404040;
                selection-background-color: #4CAF50;
            }
        """)
        self.filtro_classe_combo.currentIndexChanged.connect(self._aggiorna_statistiche)
        header_stats.addWidget(self.filtro_classe_combo)

        header_stats.addStretch()
        layout_statistiche.addLayout(header_stats)

        # Area scrollabile per statistiche
        scroll_stats = QScrollArea()
        scroll_stats.setWidgetResizable(True)

        self.widget_statistiche = QWidget()
        self.layout_statistiche_content = QVBoxLayout(self.widget_statistiche)

        scroll_stats.setWidget(self.widget_statistiche)
        layout_statistiche.addWidget(scroll_stats)

        # Bottone export statistiche
        btn_export_stats = QPushButton("📋 Esporta le statistiche in un file .txt")
        btn_export_stats.setMinimumHeight(45)
        btn_export_stats.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        btn_export_stats.setToolTip("Salva le statistiche dettagliate in un file di testo")
        btn_export_stats.clicked.connect(self._esporta_statistiche_txt)
        layout_statistiche.addWidget(btn_export_stats)

        self.tab_widget.addTab(self.tab_statistiche, "📊 Statistiche")

        # === TAB 5: EDITOR STUDENTI ===
        self.editor_studenti = EditorStudentiWidget()
        self.tab_widget.addTab(self.editor_studenti, "✏️ Editor studenti")

        # --- TOOLTIP sulle linguette delle tab ---
        self.tab_widget.setTabToolTip(0, "Visualizza la disposizione grafica dei banchi nell'aula")
        self.tab_widget.setTabToolTip(1, "Leggi il report dettagliato dell'assegnazione")
        self.tab_widget.setTabToolTip(2, "Consulta e gestisci lo storico delle assegnazioni passate")
        self.tab_widget.setTabToolTip(3, "Analizza le statistiche sulle coppie e le rotazioni")
        self.tab_widget.setTabToolTip(4, "Modifica genere, posizione e vincoli degli studenti")

        # Cursore "manina" sulle etichette delle tab: coerente con tutti
        # gli altri elementi cliccabili dell'interfaccia (pulsanti, ecc.)
        self.tab_widget.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        # Connetti il segnale: quando l'Editor carica un nuovo file
        # (tramite il suo bottone "Carica classe da modificare (.txt)"), resetta
        # i dati del pannello principale per evitare mescolanza tra classi.
        self.editor_studenti.file_cambiato_signal.connect(self._on_editor_file_cambiato)

        # Connetti il segnale: quando il docente cambia un genere nell'Editor,
        # aggiorna la label "Genere da completare" nel pannello sinistro
        self.editor_studenti.genere_cambiato_signal.connect(self._on_editor_genere_cambiato)

        # Connetti il segnale: quando l'Editor CHIUDE il file corrente
        # (bottone "Chiudi file"), riporta la label nel pannello sinistro
        # allo stato iniziale "Nessun file caricato"
        self.editor_studenti.file_chiuso_signal.connect(self._on_editor_file_chiuso)

        # === BOTTONE ISTRUZIONI spostato nel pannello sinistro ===
        # (Non più nell'angolo delle tab — ora è in cima al pannello controlli)

        return self.tab_widget

    def _mostra_istruzioni(self):
        """Mostra le istruzioni d'uso in una finestra dedicata."""

        dialog = QDialog(self)
        dialog.setWindowTitle("📖 Istruzioni")
        dialog.setMinimumSize(950, 750)
        dialog.resize(950, 750)

        layout = QVBoxLayout(dialog)

        # Contenuto istruzioni in HTML per formattazione ricca
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Segoe UI", 11))

        istruzioni_html = """
        <h2 style="color: #4CAF50;">📖 «PostiPerfetti» - Guida all'uso 📖</h2>
        <hr>

        <h3 style="color: #64B5F6;">1️⃣ PREPARAZIONE DEL FILE STUDENTI TRAMITE "✏️ Editor studenti"</h3>
        <p style="background-color: #2E3B2E; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>«PostiPerfetti» è un programma gratuito e 'open source' che utilizza uno speciale algoritmo per aiutare il docente Coordinatore (o qualsiasi insegnante ne abbia la necessità) ad assegnare agli studenti il proprio posto in classe.<br><br>
        Per funzionare, esso richiede solamente la creazione di un <b>file .txt</b> con i dati essenziali degli alunni (cognome, nome, genere). Tramite alcune funzioni molto intuitive sarà poi possibile aggiungere una serie di informazioni e vincoli ('affinità' e 'incompatibilità' fra allievi, loro 'posizione' rispetto alla cattedra, eventuale preferenza per 'coppie miste (M+F)') per ottenere <b>UNA DISTRIBUZIONE DEGLI ALLIEVI QUANTO PIÙ IN LINEA CON I DESIDERATA DELL'INSEGNANTE</b>.<br><br>
        A seconda delle preferenze, per usare l'interfaccia è possibile selezionare un '🌙 Tema scuro' o un '☀️ Tema chiaro'.<br><br>
        <b>«PostiPerfetti» non ha alcun accesso alla rete, pertanto non invia nessun dato a terzi</b>. Lavorando esclusivamente in locale, ogni informazione è mantenuta al sicuro all'interno del pc del docente.<br></p>

        <p><b>COME USARE L'EDITOR, passo per passo:</b></p>

        <p><b>① Prepara un file base:</b><br>
        Vai all'interno della cartella "dati" del programma e, con un qualsiasi editor di testo, <b>crea un nuovo file .txt con il nome della tua classe</b> (ad es. "Classe1A.txt", oppure "Classe1A_2026-27.txt").</p>
        <p>Dentro inserisci solo <code>"Cognome;Nome;Genere"</code> (= M/F) di ogni studente, <b>uno per riga, in ordine alfabetico</b>. Separa i tre elementi con due punti e virgola (";") e non usare spazi, come in questo esempio:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0; width: 50%;">
        <tr style="background-color: #404040; color: #ffffff;"><td><b>Esempio di file base</b></td></tr>
        <tr><td><code>Alighieri;Dante;M<br>Austen;Jane;F<br>Boccaccio;Giovanni;M<br>Brontë;Charlotte;F<br>Calvino;Italo;M</code></td></tr>
        </table>

        <p><b>② Carica il file nell'Editor:</b><br>
        Clicca sulla tab <b>"✏️ Editor studenti"</b> e poi sul pulsante <b>"📝 Carica classe da modificare (.txt)"</b>, scegliendo il file che hai creato. L'applicazione riconoscerà automaticamente il formato base e creerà una scheda per ogni allievo che hai inserito.</p>

        <p><b>③ Imposta la POSIZIONE:</b><br>
        Per ogni studente, usa il <b>menu a tendina</b> per selezionarne la posizione:<br>
        • <code>NORMALE</code> = nessuna preferenza,<br>
        • <code><span style="color: #EF5350;"><b>PRIMA</b></span></code> = <span style="color: #EF5350;"><b>OBBLIGO di stare in prima fila</b></span> (utile ad es. per gli allievi più propensi a distrarsi, con difficoltà di vista o altri bisogni particolari)<br>
        • <code>ULTIMA</code> = preferenza per l'ultima fila (utile ad es. per allievi di alta statura o per altre esigenze)</p>

        <p><b>④ Aggiungi le INCOMPATIBILITÀ:</b><br>
        Se è il caso di tenere separati alcuni allievi (che in banco assieme rischierebbero di distrarsi o disturbare), è consigliabile stabilire tra loro una "incompatibilità".<br>
        Clicca su <b>"➕ Aggiungi INCOMPATIBILITÀ"</b> nella scheda dello studente. Apparirà una riga con:<br>
        • Un <b>menu a tendina</b> con tutti gli altri studenti della classe — seleziona il compagno.<br>
        • Un <b>menu livello</b> — scegli il grado di incompatibilità:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #404040; color: #ffffff;">
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
        <p>NOTA: <b>Puoi aggiungere più incompatibilità per lo stesso studente</b>, cliccando
        di nuovo il bottone ➕.</p>

        <p><b>⑤ Aggiungi le AFFINITÀ:</b><br>
        Se è il caso di tenere uniti certi allievi, per promuoverne la collaborazione, l'integrazione o per altre ragioni, è utile stabilire tra loro una "affinità".<br>
        Segui la stessa procedura delle incompatibilità, usando <b>"➕ Aggiungi AFFINITÀ"</b>.<br>
        I livelli indicano quanto è desiderabile che i due studenti stiano vicini:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #404040; color: #ffffff;">
            <td><b>Livello</b></td><td><b>Significato</b></td>
        </tr>
        <tr><td style="text-align: center;"><b>1</b></td><td>Affinità leggera (piccolo bonus)</td></tr>
        <tr><td style="text-align: center;"><b>2</b></td><td>Affinità buona (bonus significativo)</td></tr>
        <tr><td style="text-align: center; color: #66BB6A;"><b>3</b></td>
            <td><span style="color: #66BB6A;"><b>Affinità forte — l'algoritmo cercherà di metterli vicini</b></span></td></tr>
        </table>
        <p>NOTA: <b>Puoi aggiungere più affinità per lo stesso studente</b>, cliccando
        di nuovo il bottone ➕.</p>

        <p><b>⑥ BIDIREZIONALITÀ automatica:</b><br>
        <span style="color: #4CAF50; font-weight: bold;">Non devi preoccuparti di ripetere i vincoli.</span>
        Se imposti "D'Annunzio Gabriele incompatibile con Deledda Grazia (livello 3)", l'Editor aggiungerà
        <b>automaticamente</b> "Deledda Grazia incompatibile con D'Annunzio Gabriele (livello 3)".
        Lo stesso vale per le affinità, per le modifiche di livello e per le rimozioni.</p>

        <p><b>⑦ Rimuovere un vincolo:</b><br>
        Clicca il bottone <b>"Rimuovi"</b> accanto al vincolo da eliminare. Il vincolo speculare
        sull'altro studente verrà rimosso automaticamente.</p>

        <p><b>⑧ Verifica e salva:</b><br>
        • Clicca su <b>"👁️ Preview file generato"</b> per vedere un'anteprima del file .txt che verrà creato.<br>
        • Clicca su <b>"💾 Esporta file completo"</b> per salvare il file .txt definitivo della classe.<br>
        • Puoi <b>sovrascrivere il file .txt della classe</b>, oppure dargli un altro nome (ad es. 'Classe1A_09-2026.txt', oppure "Classe1A_definitivo.txt').</p>

        <p style="background-color: #2E3B2E; color: #ffffff; padding: 10px; border-radius: 6px; border-left: 4px solid #4CAF50;"><br>
        <b>💡 NOTA BENE:</b><br>
        Se in futuro vorrai rimuovere, aggiungere o cambiare dei vincoli, basterà ricaricare nell'Editor il file .txt completo della classe. Le schede verranno popolate automaticamente con tutti i dati esistenti di ciascun allievo, pronte per essere modificate.<br>
        Se invece dovrai aggiungere o rimuovere un allievo, dovrai aprire il file .txt della classe e cancellarne la riga, oppure aggiungerlo (con <code>Cognome;Nome;Genere</code>) nella posizione alfabeticamente corretta.<br></p>

        <hr>
        <h3 style="color: #64B5F6;">2️⃣ CARICAMENTO E CONFIGURAZIONE</h3>

        <p><b>Passo 1 — Carica il file:</b> Clicca sul pulsante <b>"📂 Seleziona file classe (.txt)"</b> presente nel pannello a sinistra. Se fai questa operazione con un file già caricato nell'Editor, un 'popup' ti chiederà se vuoi utilizzare quel file (scegli "Usa i dati dall'Editor") oppure se desideri caricarne uno diverso (scegli "Carica un nuovo file"). Dopo il caricamento, il programma mostrerà il numero di studenti caricati.</p>

        <p><b>Passo 2 — Configura le opzioni:</b></p>
        <p>• <b>"Configurazione aula"</b>: verrai avvertito in caso di 'posti insufficienti', e ti basterà aumentare il numero di 'File di banchi' o di 'Posti per fila'.<br>
        • <b>"Gestione numero dispari"</b>: se gli studenti sono in numero dispari, scegli in quale fila andrà posizionato il trio (3 studenti allo stesso banco): 'prima', 'ultima' o 'centrale'.<br>
        • <b>"Preferisci coppie miste (M+F)": se questo flag è attivato, l'algoritmo preferirà coppie maschio-femmina</b> (non è un obbligo assoluto, ma un bonus forte).<br>
        • <b>"Rotazione mensile"</b>: quando si salva la prima assegnazione, questo flag si attiverà in automatico dalla seconda assegnazione in poi. L'algoritmo eviterà il più possibile di ripetere coppie già formate nelle assegnazioni precedenti.<br></p>

        <hr>
        <h3 style="color: #64B5F6;">3️⃣ AVVIO DELL'ASSEGNAZIONE</h3>

        <p>Clicca su <b>"🚀 Avvia assegnazione automatica"</b>.<br>
        <b>L'algoritmo lavorerà in 4 tentativi progressivi, rispettando SEMPRE i vincoli "ASSOLUTI" (= 'posizione PRIMA' e 'incompatibilità 3') e facendo il possibile per NON RIPETERE COPPIE GIÀ FORMATE.</b></p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #404040; color: #ffffff;">
            <td><b>Tentativo</b></td><td><b>Strategia</b></td>
        </tr>
        <tr><td>1</td><td>Tutti i vincoli attivi, nessuna coppia ripetuta</td></tr>
        <tr><td>2</td><td>Vincoli deboli (livello 1) rilassati</td></tr>
        <tr><td>3</td><td>Vincoli medi (livello 2) rilassati</td></tr>
        <tr><td>4</td><td>Solo vincoli ASSOLUTI, coppie ripetute ammesse con penalità progressiva</td></tr>
        </table>

        <p>Al termine dell'elaborazione apparirà un <b>POPUP di riepilogo</b> con le statistiche degli abbinamenti creati.<br>
        💡 Eventuali <b>coppie riutilizzate</b> saranno evidenziate in <span style="color: #CC8800; font-weight: bold;">colore ocra</span>.<br><br>
        <b>NOTA:</b> Tutte le modifiche ai file e ogni assegnazione salvata vengono memorizzate all'interno del file "postiperfetti_configurazione.json". Questo file non deve essere aperto o modificato direttamente. Solo nel caso in cui si desideri cancellare l'intero Storico delle assegnazioni può essere eliminato, e verrà ricreato "da zero" dal programma in occasione della prima nuova assegnazione.</p>

        <hr>
        <h3 style="color: #64B5F6;">4️⃣ VISUALIZZAZIONE DEI RISULTATI</h3>

        <p>🍀 La <b>Tab "🏫 AULA":</b> mostrerà la disposizione grafica dell'aula. Gli arredi (LIM, cattedra,
        lavagna) sono in basso, le file di banchi salgono verso l'alto. Da qui potrai agire sui pulsanti:</p>
        <p>• <b>💾 Salva assegnazione</b>: salva la distribuzione degli allievi appena ottenuta nello Storico del programma, per consultarla in futuro e per memorizzare le coppie formate.<br>
        • <b>📊 Esporta Excel</b>: genera un file .xlsx liberamente modificabile, con un layout ottimizzato per la stampa in A4.<br>
        • <b>📋 Esporta report .txt</b>: salva il report testuale completo con le caratteristiche degli abbinamenti effettuati.</p>

        <p>🍀 La <b>Tab "📊 REPORT":</b> mostra il report testuale dettagliato con tutte le coppie formate,
        i punteggi, le note sui vincoli e il layout dell'aula in formato testo.
        Le coppie riutilizzate sono evidenziate in <span style="color: #CC8800; font-weight: bold;">colore ocra</span>.</p>

        <p>🍀 La <b>Tab "📚 STORICO":</b> elenca tutte le assegnazioni salvate. Volendo, puoi <b>modificare il 'Nome' di ogni assegnazione</b> facendo doppio clic su di essa. Per ciascuna inoltre potrai agire sui pulsanti:</p>
        <p>• <b>📋 Dettagli</b>: visualizza il report completo dell'assegnazione.<br>
        • <b>🔍 Layout</b>: apre il layout grafico con la possibilità di esportare in Excel.<br>
        • <b>🗑️ Elimina</b>: rimuove l'assegnazione dallo Storico (consentendo di 'ri-abbinare' in futuro gli studenti che erano stati messi assieme in quella assegnazione).<br></p>

        <p>🍀 La <b>Tab "📊 STATISTICHE":</b> analizza l'intero Storico della classe (o di più classi) mostrando le coppie più frequenti, gli studenti più spesso in prima fila e le coppie mai formate.
        Utile per verificare l'equità e le caratteristiche delle rotazioni succedutesi nel tempo.</p>

        <hr>
        <h3 style="color: #64B5F6;">5️⃣ FLUSSO DI LAVORO CONSIGLIATO</h3>

        <p><b>Prima assegnazione dell'anno (settembre):</b>
        <p>1. <b>Prepara tramite "✏️ Editor studenti" il file .txt della classe</b> con tutti i dati necessari.<br>
        2. <b>Seleziona il file della classe</b>. Il programma imposterà in automatico la "Prima assegnazione".<br>
        3. Aggiungi se necessario 'File di banchi' e/o 'Posti per fila'.<br>
        4. Assegna se necessario la posizione del 'trio' e l'eventuale preferenza per le 'coppie miste'.<br>
        5. <b>Avvia l'assegnazione, salvala nello Storico ed esportala in Excel.</b><br>
        6. <b>Apri e modifica se necessario il foglio Excel, stampalo e posizionalo in classe.</b></p>

        <p><b>Assegnazioni successive (ottobre → giugno):</b>
        <p>1. Mantieni lo stesso file .txt della classe (o ricaricalo se hai aperto una nuova sessione del programma).<br>
        2. «PostiPerfetti» attiverà in automatico il flag della "Rotazione mensile".<br>
        3. <b>Avvia tutte le assegnazioni necessarie, RICORDANDOTI DI SALVARE OGNUNA NELLO STORICO</b>, ed esportale di volta in volta in Excel per la stampa.<br>
        <b>NOTA</b> = nel caso tu non abbia salvato in tempo i file Excel delle varie assegnazioni, potrai sempre farlo in un secondo momento, accedendo alla tab "📚 STORICO" e cliccando su "🔍 Layout".</p>

        <p><b>Modifica dei vincoli in corso d'anno:</b><br>
        Se le dinamiche della classe dovessero cambiare, modifica con "✏️ Editor studenti" il file .txt della classe aggiornando incompatibilità e affinità, poi salvalo.</p>

        <hr>
        <h3 style="color: #64B5F6;">⚠️ RISOLUZIONE PROBLEMI</h3>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; margin: 8px 0;">
        <tr style="background-color: #404040; color: #ffffff;">
            <td><b>Problema</b></td><td><b>Soluzione</b></td>
        </tr>
        <tr>
            <td>Popup di segnalazione errore al caricamento del .txt</td>
            <td>Il programma verifica che la sintassi di ogni riga sia corretta e propone in automatico gli aggiustamenti necessari, avvisando con un 'popup'. È consigliabile, in questi casi, rivedere la correttezza dei dati degli allievi nella tab "✏️ Editor studenti"</td>
        </tr>
        <tr>
            <td>Studente "non trovato" nei vincoli</td>
            <td>Il nome nei vincoli deve corrispondere <b>esattamente</b> a Cognome + Nome
            (es: <code>Pasolini Pier Paolo</code>, non <code>Pasolini Pier</code>).</td>
        </tr>
        <tr>
            <td>❗ TROPPE COPPIE RIUTILIZZATE</td>
            <td>Con molti vincoli di incompatibilità (livello 3), le combinazioni possibili si riducono.
            <b>Valuta se qualche vincolo di livello 3 può diventare livello 2.</b></td>
        </tr>
        <tr>
            <td>‼️ L'ASSEGNAZIONE FALLISCE IN TUTTI I TENTATIVI</td>
            <td>I vincoli assoluti creano una situazione matematicamente impossibile da risolvere. <b>Riduci il numero
            di incompatibilità di 'livello 3', di posizione 'PRIMA' oppure rimuovi il vincolo di 'genere misto'.</b></td>
        </tr>
        </table>

        <hr>
        <p style="color: #888888; font-size: 13px; text-align: center;">
        «PostiPerfetti» — Sviluppato in Python dal prof. Omar Ceretta<br>I.C. di Tombolo e Galliera Veneta (PADOVA)</p>
        """

        text_edit.setHtml(istruzioni_html)
        layout.addWidget(text_edit)

        # Bottone Chiudi
        btn_chiudi = QPushButton("✅ Chiudi")
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.setStyleSheet("""
            QPushButton {
                background-color: #5C6BC0;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #3F51B5;
            }
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

        dialog.exec()

    def setup_stili(self):
        """
        Applica il tema attivo all'interfaccia principale.
        I colori vengono letti dal dizionario TEMI tramite la funzione C(),
        quindi basta cambiare TEMA_ATTIVO per aggiornare l'intera interfaccia.
        """

        # Costruisce lo stylesheet completo usando i colori del tema attivo.
        # Ogni C("nome") restituisce il colore corretto per scuro o chiaro.
        stylesheet = f"""
            /* === FINESTRA PRINCIPALE === */
            QMainWindow {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            QWidget {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            /* === GRUPPI E CONTAINER === */
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {C("bordo_normale")};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: {C("sfondo_pannello")};
                color: {C("testo_principale")};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}

            /* === TAB WIDGET === */
            QTabWidget::pane {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_pannello")};
            }}

            QTabBar::tab {{
                background: {C("sfondo_tab_normale")};
                border: 1px solid {C("bordo_normale")};
                padding: 10px 18px;
                margin-right: 2px;
                border-radius: 4px 4px 0px 0px;
                color: {C("testo_secondario")};
            }}

            QTabBar::tab:selected {{
                background: {C("accento")};
                color: #ffffff;
                font-weight: bold;
                border-bottom-color: {C("accento")};
            }}

            QTabBar::tab:hover:!selected {{
                background: {C("btn_hover")};
                color: {C("testo_principale")};
            }}

            /* === BOTTONI === */
            QPushButton {{
                padding: 10px 16px;
                border-radius: 6px;
                border: 1px solid {C("bordo_leggero")};
                background-color: {C("btn_sfondo")};
                color: {C("testo_principale")};
                font-weight: bold;
            }}

            QPushButton:hover {{
                background-color: {C("btn_hover")};
                border: 1px solid {C("bordo_normale")};
            }}

            QPushButton:pressed {{
                background-color: {C("btn_premuto")};
            }}

            QPushButton:disabled {{
                background-color: {C("btn_disabilitato_sf")};
                color: {C("btn_disabilitato_txt")};
                border: 1px solid {C("bordo_normale")};
            }}

            /* === INPUT FIELDS === */
            QLineEdit, QSpinBox, QComboBox {{
                padding: 8px 12px;
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
            }}

            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 2px solid {C("bordo_focus")};
                background-color: {C("sfondo_input")};
            }}

            QLineEdit::placeholder {{
                color: {C("testo_placeholder")};
            }}

            /* === SLIDER === */
            QSlider::groove:horizontal {{
                border: 1px solid {C("bordo_normale")};
                height: 6px;
                background: {C("sfondo_input")};
                margin: 2px 0;
                border-radius: 3px;
            }}

            QSlider::handle:horizontal {{
                background: {C("accento")};
                border: 2px solid {C("accento_scuro")};
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}

            QSlider::handle:horizontal:hover {{
                background: {C("accento_hover")};
            }}

            QSlider::sub-page:horizontal {{
                background: {C("accento")};
                border-radius: 3px;
            }}

            /* === RADIO BUTTON === */
            QRadioButton {{
                color: {C("testo_principale")};
                spacing: 8px;
            }}

            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid {C("bordo_leggero")};
                background-color: {C("sfondo_input")};
            }}

            QRadioButton::indicator:checked {{
                background-color: {C("accento")};
                border: 2px solid {C("accento_scuro")};
            }}

            QRadioButton::indicator:hover {{
                border: 2px solid {C("accento")};
            }}

            /* === CHECKBOX === */
            QCheckBox {{
                color: {C("testo_principale")};
                spacing: 8px;
            }}

            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {C("bordo_leggero")};
                border-radius: 3px;
                background-color: {C("sfondo_input")};
            }}

            QCheckBox::indicator:checked {{
                background-color: {C("accento")};
                border: 2px solid {C("accento_scuro")};
                font-weight: bold;
            }}

            /* === PROGRESS BAR === */
            QProgressBar {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                text-align: center;
                font-weight: bold;
            }}

            QProgressBar::chunk {{
                background-color: {C("accento")};
                border-radius: 4px;
            }}

            /* === TEXT EDIT === */
            QTextEdit {{
                border: 2px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_testo_area")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
            }}

            /* === TABLE === */
            QTableWidget {{
                gridline-color: {C("bordo_normale")};
                background-color: {C("sfondo_pannello")};
                alternate-background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
            }}

            QTableWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {C("bordo_normale")};
            }}

            QTableWidget::item:selected {{
                background-color: {C("accento")};
                color: #ffffff;
            }}

            QHeaderView::section {{
                background-color: {C("sfondo_header_tabella")};
                color: {C("testo_principale")};
                padding: 8px;
                border: 1px solid {C("bordo_normale")};
                font-weight: bold;
            }}

            /* === LABEL === */
            QLabel {{
                color: {C("testo_principale")};
            }}

            /* === SCROLL BAR === */
            QScrollBar:vertical {{
                background: {C("sfondo_input")};
                width: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical {{
                background: {C("bordo_leggero")};
                min-height: 20px;
                border-radius: 6px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: {C("accento")};
            }}

            QScrollBar:horizontal {{
                background: {C("sfondo_input")};
                height: 12px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal {{
                background: {C("bordo_leggero")};
                min-width: 20px;
                border-radius: 6px;
            }}

            QScrollBar::handle:horizontal:hover {{
                background: {C("accento")};
            }}

            /* === SPIN BOX === */
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                background-color: {C("sfondo_input_alt")};
                border: 1px solid {C("bordo_leggero")};
            }}

            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {C("accento")};
            }}

            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
            }}

            /* === COMBO BOX === */
            QComboBox::drop-down {{
                border: none;
                width: 20px;
                background-color: {C("sfondo_input_alt")};
            }}

            QComboBox::down-arrow {{
                width: 8px;
                height: 8px;
                background: {C("testo_principale")};
            }}

            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
                border: 1px solid {C("bordo_leggero")};
            }}
        """

        # Applica il tema all'intera finestra principale.
        # Tutti i widget figli ereditano questi stili salvo override locali.
        self.setStyleSheet(stylesheet)

    def _carica_dati_iniziali(self):
        """Carica dati iniziali dalla configurazione salvata."""

        # Carica e applica il tema salvato (scuro o chiaro)
        # Deve avvenire PRIMA di qualsiasi aggiornamento dell'interfaccia
        tema_salvato = self.config_app.config_data.get("tema", "scuro")
        imposta_tema(tema_salvato)

        # Aggiorna l'etichetta del toggle in base al tema caricato
        if tema_salvato == "chiaro":
            self.btn_toggle_tema.setText("🌙 Scuro")
        else:
            self.btn_toggle_tema.setText("☀️ Chiaro")

        # Riapplica lo stylesheet globale col tema appena caricato
        self.setup_stili()

        # Genere misto: carica preferenza salvata
        genere_misto_salvato = self.config_app.config_data["opzioni_vincoli"]["genere_misto_obbligatorio"]
        self.checkbox_genere_misto.setChecked(genere_misto_salvato)

        # FIX: La label storico NON deve mostrare dati all'avvio —
        # ha senso solo dopo che il docente ha caricato un file studenti.
        # _aggiorna_info_storico() viene chiamata da carica_file_studenti()
        # al momento opportuno. Qui impostiamo solo il testo neutro iniziale.
        self.label_storico.setText("Storico: nessun file caricato")
        self.label_storico.setStyleSheet(
            f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;"
        )

        self._aggiorna_posti_totali()

        # Popola filtro statistiche
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        # Popola la tabella dello Storico con le assegnazioni precedenti.
        # Il docente potrebbe voler consultare o esportare assegnazioni
        # già fatte senza dover prima ricaricare una classe.
        self._aggiorna_tabella_storico()

    def _aggiorna_posti_totali(self):
        """Aggiorna il calcolo dei posti totali."""
        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())
        posti_totali = num_file * posti_per_fila

        self.label_posti_totali.setText(f"Posti totali: {posti_totali}")

        # Controlla compatibilità con studenti caricati
        if self.studenti:
            num_studenti = len(self.studenti)
            if num_studenti > posti_totali:
                # WARNING EVIDENTE: Sfondo rosso lampeggiante + testo grande
                self.label_posti_totali.setStyleSheet("""
                    background-color: #FF4444;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 8px;
                    border: 3px solid #CC0000;
                    border-radius: 6px;
                """)
                self.label_posti_totali.setText(f"🚨 POSTI INSUFFICIENTI! 🚨\nServono: {num_studenti} | Disponibili: {posti_totali}")

                # Salva stato per controllo successivo
                self.posti_insufficienti = True
            elif num_studenti < posti_totali:
                # Sfondo ocra/ambra per rendere l'informazione ben visibile
                self.label_posti_totali.setStyleSheet("""
                    background-color: #B8860B;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 6px 8px;
                    border-radius: 5px;
                    border: 1px solid #DAA520;
                """)
                posti_liberi = posti_totali - num_studenti
                self.label_posti_totali.setText(
                    f"✅ Posti totali: {posti_totali}\n"
                    f"({posti_liberi} post{'o vuoto' if posti_liberi == 1 else 'i vuoti'}: sar{'à tolto' if posti_liberi == 1 else 'anno tolti'} in automatico)"
                )
                # Reset flag posti insufficienti
                self.posti_insufficienti = False
            else:
                # Sfondo ocra/ambra per rendere l'informazione ben visibile
                self.label_posti_totali.setStyleSheet("""
                    background-color: #B8860B;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 6px 8px;
                    border-radius: 5px;
                    border: 1px solid #DAA520;
                """)
                self.label_posti_totali.setText(f"🎯 Posti totali: {posti_totali} (PERFETTO!)")
                # Reset flag posti insufficienti
                self.posti_insufficienti = False

    def _cambia_num_file(self, delta):
        """
        Cambia il numero di file di banchi.

        Args:
            delta: +1 per aumentare, -1 per diminuire
        """
        valore_attuale = int(self.input_num_file.text())
        nuovo_valore = valore_attuale + delta

        # Limiti: min 1, max 6
        if 1 <= nuovo_valore <= 6:
            self.input_num_file.setText(str(nuovo_valore))
            self._aggiorna_posti_totali()

    def _cambia_posti_fila(self, delta):
        """
        Cambia il numero di posti per fila (solo valori PARI).

        Args:
            delta: +2 per aumentare, -2 per diminuire
        """
        valore_attuale = int(self.input_posti_fila.text())
        nuovo_valore = valore_attuale + delta

        # Limiti: min 2, max 12 (solo pari)
        if 2 <= nuovo_valore <= 12:
            self.input_posti_fila.setText(str(nuovo_valore))
            self._aggiorna_posti_totali()

    def _aggiorna_visibilita_dispari(self):
        """Mostra/nasconde controlli per numero dispari."""
        if hasattr(self, 'group_dispari'):  # Controlla che il gruppo esista
            if self.studenti and len(self.studenti) % 2 == 1:
                self.group_dispari.setVisible(True)
                self.label_info_dispari.setText(f"Con {len(self.studenti)} studenti, il banco da 3 sarà posizionato:")
            else:
                self.group_dispari.setVisible(False)

    def _aggiorna_info_storico(self):
        """Aggiorna le informazioni sullo storico delle assegnazioni."""
        storico = self.config_app.config_data["storico_assegnazioni"]
        num_assegnazioni = len(storico)

        if num_assegnazioni == 0:
            self.label_storico.setText("Storico: nessuna assegnazione precedente")
            self.radio_prima_volta.setChecked(True)
            self.radio_rotazione.setEnabled(False)
        else:
            ultima_data = storico[-1]["data"] if storico else "N/A"
            self.label_storico.setText(f"Storico: {num_assegnazioni} assegnazioni (ultima: {ultima_data})")
            self.radio_rotazione.setEnabled(True)

        # Aggiorna anche la tabella dello storico
        self._aggiorna_tabella_storico()

    def _aggiorna_tabella_storico(self):
        """Aggiorna la tabella dello storico nelle tab."""
        storico = self.config_app.config_data["storico_assegnazioni"]

        # Blocca il segnale cellChanged durante il popolamento
        # per evitare che scatti per ogni setItem()
        self.tabella_storico.blockSignals(True)

        self.tabella_storico.setRowCount(len(storico))

        for row, assegnazione in enumerate(storico):
            # Colonna "Data" — NON editabile (solo visualizzazione)
            item_data = QTableWidgetItem(f"{assegnazione['data']} {assegnazione['ora']}")
            item_data.setFlags(item_data.flags() & ~Qt.ItemIsEditable)
            self.tabella_storico.setItem(row, 0, item_data)

            # Colonna "Nome" — editabile (il docente può rinominarla)
            self.tabella_storico.setItem(row, 1, QTableWidgetItem(assegnazione['nome']))

            # Conta abbinamenti dal campo "layout" (NUOVO FORMATO)
            layout = assegnazione.get('layout', [])

            if layout:
                # Conta coppie (ogni coppia ha 2 studenti nel layout)
                studenti_coppia = [s for s in layout if s.get('tipo') == 'coppia']
                num_coppie = len(studenti_coppia) // 2  # Diviso 2 perché ogni coppia = 2 studenti

                # Conta trio (3 studenti nel layout)
                studenti_trio = [s for s in layout if s.get('tipo') == 'trio']
                num_trio = 1 if len(studenti_trio) == 3 else 0

                if num_trio > 0:
                    testo_abbinamenti = f"{num_coppie} coppie + {num_trio} trio"
                else:
                    testo_abbinamenti = f"{num_coppie} coppie"
            else:
                # Assegnazione senza layout (non dovrebbe succedere con nuovo formato)
                testo_abbinamenti = "Formato non supportato"

            # Colonna "Abbinamenti" — NON editabile (dato calcolato)
            item_abbinamenti = QTableWidgetItem(testo_abbinamenti)
            item_abbinamenti.setFlags(item_abbinamenti.flags() & ~Qt.ItemIsEditable)
            self.tabella_storico.setItem(row, 2, item_abbinamenti)

            # Container per bottoni azioni multiple
            widget_azioni = QWidget()
            layout_azioni = QHBoxLayout(widget_azioni)
            layout_azioni.setContentsMargins(2, 2, 2, 2)

            # Bottone Elimina - dimensioni e colori ottimizzati
            btn_elimina = QPushButton("🗑 Elimina")
            btn_elimina.setToolTip("Rimuove definitivamente questa assegnazione dallo storico")
            btn_elimina.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_elimina.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_elimina.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)
            btn_elimina.clicked.connect(lambda checked, idx=row: self._elimina_assegnazione(idx))
            layout_azioni.addWidget(btn_elimina)

            # Bottone Dettagli - dimensioni e colori ottimizzati
            btn_dettagli = QPushButton("👁 Dettagli")
            btn_dettagli.setToolTip("Visualizza il report completo di questa assegnazione")
            btn_dettagli.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_dettagli.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_dettagli.setStyleSheet("""
                QPushButton {
                    background-color: #1976d2;
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #0d47a1;
                }
            """)
            btn_dettagli.clicked.connect(lambda checked, idx=row: self._visualizza_dettagli_assegnazione(idx))
            layout_azioni.addWidget(btn_dettagli)

            # Bottone Visualizza Layout - dimensioni e colori ottimizzati
            btn_layout = QPushButton("🔍 Layout")
            btn_layout.setToolTip("Visualizza il layout grafico di questa assegnazione")
            btn_layout.setMinimumHeight(35)  # Altezza sufficiente per il testo
            btn_layout.setMinimumWidth(110)   # Larghezza sufficiente per il testo
            btn_layout.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            btn_layout.clicked.connect(lambda checked, idx=row: self._visualizza_layout_storico(idx))
            layout_azioni.addWidget(btn_layout)

            layout_azioni.addStretch()  # Spinge i bottoni a sinistra
            self.tabella_storico.setCellWidget(row, 3, widget_azioni)

        self.tabella_storico.resizeColumnsToContents()
        # Altezza righe calcolata automaticamente in base al contenuto.
        # Usiamo setMinimumSectionSize (non setDefaultSectionSize) per
        # garantire un minimo leggibile, ma lasciando a Qt la libertà
        # di espandere la riga se il DPI scaling lo richiede.
        self.tabella_storico.verticalHeader().setMinimumSectionSize(50)
        self.tabella_storico.resizeRowsToContents()

        # Sblocca il segnale cellChanged (popolamento completato)
        self.tabella_storico.blockSignals(False)

    def _on_storico_nome_modificato(self, row, column):
        """
        Salva la modifica quando il docente rinomina un'assegnazione
        nella colonna "Nome" dello Storico.

        Args:
            row: riga modificata
            column: colonna modificata (solo colonna 1 = Nome è editabile)
        """
        # Solo la colonna "Nome" (indice 1) è editabile
        if column != 1:
            return

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        if row < 0 or row >= len(storico):
            return

        # Legge il nuovo testo dalla cella
        item = self.tabella_storico.item(row, column)
        if item:
            nuovo_nome = item.text().strip()
            if nuovo_nome:
                storico[row]["nome"] = nuovo_nome
                self.config_app.salva_configurazione()
                print(f"📝 Storico: assegnazione {row} rinominata → '{nuovo_nome}'")

    def _popola_filtro_classi(self):
        """
        Popola il dropdown filtro con tutte le classi presenti nello storico.
        """
        self.filtro_classe_combo.clear()

        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            # Nessuna assegnazione - mostra messaggio
            self.filtro_classe_combo.addItem("📭 Nessuna assegnazione salvata", None)
            return

        # Trova tutti i file_origine unici
        classi_trovate = {}  # {file_origine: conteggio_assegnazioni}

        for assegnazione in storico:
            file_origine = assegnazione.get('file_origine', 'File non specificato')
            if file_origine not in classi_trovate:
                classi_trovate[file_origine] = 0
            classi_trovate[file_origine] += 1

        # Ordina per nome file
        classi_ordinate = sorted(classi_trovate.items())

        # Aggiungi opzione "Tutte le classi" (se più di una classe)
        if len(classi_ordinate) > 1:
            totale_assegnazioni = sum(classi_trovate.values())
            self.filtro_classe_combo.addItem(
                f"📚 Tutte le classi ({totale_assegnazioni} assegnazioni totali)",
                None  # userData = None significa "tutte"
            )

        # Aggiungi ogni classe trovata
        for file_origine, count in classi_ordinate:
            # Estrae solo nome file (senza path)
            nome_file = os.path.basename(file_origine) if file_origine else "File non specificato"
            self.filtro_classe_combo.addItem(
                f"📁 {nome_file} ({count} assegnazioni)",
                file_origine  # userData = file_origine per filtrare
            )

        print(f"📊 Filtro classi popolato: {len(classi_ordinate)} classi trovate")

        # Applica stile del tema attivo al combo filtro.
        # Va fatto qui (e non solo nel global stylesheet) perché il combo
        # viene ripopolato dinamicamente: senza questo, al cambio tema
        # il dropdown mantiene i colori vecchi finché non viene ricreato.
        self.filtro_classe_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                padding: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
                selection-color: #ffffff;
                border: 1px solid {C("bordo_leggero")};
            }}
        """)

    def _aggiorna_statistiche(self):
        """
        Calcola e mostra le statistiche filtrate per la classe selezionata.
        """
        print("📊 Aggiornamento statistiche...")

        # Ottiene il filtro selezionato
        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        if file_origine_filtro is None:
            print("   📚 Mostrando statistiche per TUTTE le classi")
            nome_filtro = "Tutte le classi"
        else:
            nome_file = os.path.basename(file_origine_filtro)
            print(f"   📁 Mostrando statistiche per: {nome_file}")
            nome_filtro = nome_file

        # Pulisce layout esistente
        while self.layout_statistiche_content.count():
            child = self.layout_statistiche_content.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Filtra assegnazioni per classe
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            # Nessuna assegnazione - mostra messaggio
            label = QLabel("📭 Nessuna assegnazione salvata.\n\nEsegui almeno una assegnazione e salvala per vedere le statistiche.")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 14px; color: #888888; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        assegnazioni_filtrate = []
        for assegnazione in storico:
            if file_origine_filtro is None or assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            # Nessuna assegnazione per questo filtro
            label = QLabel(f"📭 Nessuna assegnazione per: {nome_filtro}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 14px; color: #888888; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        print(f"   ✅ {len(assegnazioni_filtrate)} assegnazioni filtrate")

        # Calcola tutte le statistiche
        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        # Mostra le statistiche
        self._mostra_statistiche_complete(stats, nome_filtro)

    def _esporta_statistiche_txt(self):
        """
        Esporta le statistiche complete in formato TXT.
        """
        # Verifica che ci siano statistiche da esportare
        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            QMessageBox.warning(self, "Nessuna statistica", "Seleziona una classe per esportare le statistiche.")
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        if file_origine_filtro is None:
            nome_filtro = "Tutte_le_classi"
        else:
            nome_filtro = pulisci_nome_file(os.path.basename(file_origine_filtro))

        # Filtra assegnazioni
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        assegnazioni_filtrate = []
        for assegnazione in storico:
            if file_origine_filtro is None or assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            QMessageBox.warning(self, "Nessuna assegnazione", "Nessuna assegnazione disponibile per l'export.")
            return

        # Calcola statistiche
        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        # Genera contenuto TXT
        contenuto_txt = self._genera_testo_statistiche(stats, nome_filtro)

        # Dialog salvataggio
        data_ora = datetime.now().strftime('%Y%m%d_%H%M')
        nome_suggerito = f"Statistiche_{nome_filtro}_{data_ora}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta statistiche .txt",
            nome_suggerito,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if file_path:
            try:
                # Salva file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(contenuto_txt)

                mostra_popup_file_salvato(self, "Export completato", "✅ Statistiche salvate con successo!", file_path)

            except Exception as e:
                QMessageBox.critical(self, "Errore Export", f"Errore durante il salvataggio:\n{str(e)}")

    def _genera_testo_statistiche(self, stats, nome_filtro):
        """
        Genera il contenuto testuale completo delle statistiche.

        Args:
            stats: Dizionario con statistiche calcolate
            nome_filtro: Nome classe filtrata

        Returns:
            str: Testo formattato pronto per il file
        """
        linee = []

        # Header
        linee.append("=" * 80)
        linee.append("📊 STATISTICHE ASSEGNAZIONI POSTI")
        linee.append("=" * 80)
        linee.append("")

        # === SEZIONE 1: RIEPILOGO ===
        linee.append("📋 RIEPILOGO GENERALE")
        linee.append("-" * 80)
        linee.append(f"Classe: {nome_filtro}")
        linee.append(f"Assegnazioni totali: {stats['num_assegnazioni']}")
        if stats['prima_data']:
            linee.append(f"Periodo: dal {stats['prima_data']} al {stats['ultima_data']}")
        linee.append(f"Studenti coinvolti: {len(stats['studenti_unici'])}")
        linee.append("")

        # === SEZIONE 2: COPPIE PIÙ FREQUENTI ===
        linee.append("👥 COPPIE PIÙ FREQUENTI (Top 10)")
        linee.append("-" * 80)

        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"{idx:2d}. {nome1} + {nome2} ({count} volte)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"    → {asseg_str}")
        else:
            linee.append("Nessuna coppia registrata")

        linee.append("")

        # === SEZIONE 3: STATISTICHE TRIO ===
        if stats['trio_frequenza']:
            linee.append("🎯 STATISTICHE TRIO")
            linee.append("-" * 80)

            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({count} volte nel trio)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"  → {asseg_str}")

            linee.append("")

        # === SEZIONE 4: DETTAGLIO PER STUDENTE (tutti) ===
        linee.append("🔍 DETTAGLIO PER STUDENTE")
        linee.append("-" * 80)

        for nome_studente in sorted(stats['studenti_unici']):
            dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
            compagni = dettagli.get('compagni', {})

            linee.append(f"\n{nome_studente}: {stats['num_assegnazioni']} assegnazioni totali")

            # Trio
            if nome_studente in stats['trio_frequenza']:
                dati_trio = stats['trio_frequenza'][nome_studente]
                count_trio = dati_trio['count']
                asseg_trio = dati_trio['assegnazioni']

                linee.append(f"  🎯 Nel trio: {count_trio} volte")
                if asseg_trio:
                    if len(asseg_trio) <= 5:
                        asseg_str = ", ".join(asseg_trio)
                    else:
                        asseg_str = ", ".join(asseg_trio[:5]) + f" (e altre {len(asseg_trio)-5})"
                    linee.append(f"     → {asseg_str}")

            # Compagni
            if compagni:
                compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)
                linee.append(f"  Abbinato con:")

                for compagno, dati in compagni_ordinati:
                    count = dati['count']
                    assegnazioni = dati['assegnazioni']

                    linee.append(f"    • {compagno} ({count} volte)")

                    if assegnazioni:
                        if len(assegnazioni) <= 5:
                            asseg_str = ", ".join(assegnazioni)
                        else:
                            asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                        linee.append(f"       → {asseg_str}")

            # Mai abbinati
            tutti_studenti = stats['studenti_unici']
            mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

            if mai_abbinati:
                linee.append(f"  Mai stato con ({len(mai_abbinati)}): {', '.join(sorted(mai_abbinati))}")

        linee.append("")

        # === SEZIONE 5: POSIZIONI PRIMA FILA ===
        if stats['posizioni_prima_fila']:
            linee.append("📍 STUDENTI IN PRIMA FILA")
            linee.append("-" * 80)

            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({count} volte)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"  → {asseg_str}")

            # Mai in prima fila
            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                linee.append(f"\nMai in prima fila ({len(mai_prima)}): {', '.join(sorted(mai_prima))}")

            linee.append("")

        # === SEZIONE 6: COPPIE MAI FORMATE ===
        linee.append("🚫 COPPIE MAI FORMATE")
        linee.append("-" * 80)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            linee.append(f"Trovate {len(coppie_mai_formate)} coppie mai formate:")
            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:50], 1):  # Max 50 per non esagerare
                linee.append(f"{idx:2d}. {nome1} - {nome2}")

            if len(coppie_mai_formate) > 50:
                linee.append(f"... e altre {len(coppie_mai_formate) - 50} coppie")
        else:
            linee.append("✅ Tutti gli studenti sono stati abbinati almeno una volta con tutti gli altri!")

        linee.append("")
        linee.append("=" * 80)
        linee.append(f"Report generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        linee.append("=" * 80)

        return "\n".join(linee)

    def _calcola_tutte_statistiche(self, assegnazioni_filtrate, nome_filtro):
        """
        Calcola tutte le statistiche dalle assegnazioni filtrate.
        VERSIONE 2.0: Traccia anche in quali assegnazioni sono avvenuti gli abbinamenti.

        Returns:
            dict: Dizionario con tutte le statistiche calcolate
        """
        print(f"   🔢 Calcolo statistiche per {len(assegnazioni_filtrate)} assegnazioni...")

        stats = {
            'nome_filtro': nome_filtro,
            'num_assegnazioni': len(assegnazioni_filtrate),
            'prima_data': None,
            'ultima_data': None,
            'studenti_unici': set(),
            'coppie_frequenza': {},  # {(nome1, nome2): {'count': N, 'assegnazioni': [lista]}}
            'trio_frequenza': {},    # {nome: {'count': N, 'assegnazioni': [lista]}}
            'dettaglio_studenti': {},  # {nome: {compagni: {nome_compagno: {'count': N, 'assegnazioni': [lista]}}}}
            'posizioni_prima_fila': {}  # {nome: {'count': N, 'assegnazioni': [lista]}}
        }

        # Date prima/ultima assegnazione
        if assegnazioni_filtrate:
            stats['prima_data'] = assegnazioni_filtrate[0].get('data', 'N/A')
            stats['ultima_data'] = assegnazioni_filtrate[-1].get('data', 'N/A')

        # Analizza ogni assegnazione
        for assegnazione in assegnazioni_filtrate:
            layout = assegnazione.get('layout', [])
            nome_assegnazione = assegnazione.get('nome', 'Senza nome')
            data_assegnazione = assegnazione.get('data', '')

            # Nome abbreviato per visualizzazione
            nome_abbr = abbrevia_nome_assegnazione(nome_assegnazione, data_assegnazione)

            # Analizza layout per estrarre dati
            for studente_info in layout:
                nome = studente_info['studente']
                tipo = studente_info.get('tipo')

                # Aggiungi a studenti unici
                stats['studenti_unici'].add(nome)

                # Inizializza dettaglio studente se nuovo
                if nome not in stats['dettaglio_studenti']:
                    stats['dettaglio_studenti'][nome] = {'compagni': {}}

                # ANALISI COPPIE
                if tipo == 'coppia':
                    compagno = studente_info.get('compagno')
                    if compagno:
                        # Frequenza coppie (chiave ordinata per evitare duplicati)
                        chiave_coppia = tuple(sorted([nome, compagno]))

                        if chiave_coppia not in stats['coppie_frequenza']:
                            stats['coppie_frequenza'][chiave_coppia] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        # Incrementa count solo se non già contato in questa assegnazione
                        if nome_abbr not in stats['coppie_frequenza'][chiave_coppia]['assegnazioni']:
                            stats['coppie_frequenza'][chiave_coppia]['count'] += 1
                            stats['coppie_frequenza'][chiave_coppia]['assegnazioni'].append(nome_abbr)

                        # Dettaglio per studente
                        if compagno not in stats['dettaglio_studenti'][nome]['compagni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['count'] += 1
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni'].append(nome_abbr)

                # ANALISI TRIO
                elif tipo == 'trio':
                    if nome not in stats['trio_frequenza']:
                        stats['trio_frequenza'][nome] = {
                            'count': 0,
                            'assegnazioni': []
                        }

                    if nome_abbr not in stats['trio_frequenza'][nome]['assegnazioni']:
                        stats['trio_frequenza'][nome]['count'] += 1
                        stats['trio_frequenza'][nome]['assegnazioni'].append(nome_abbr)

                    # Anche per trio, conta i compagni (coppie virtuali adiacenti)
                    compagno = studente_info.get('compagno')
                    if compagno:
                        if compagno not in stats['dettaglio_studenti'][nome]['compagni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['count'] += 1
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni'].append(nome_abbr)

                # ANALISI POSIZIONI (solo se non è trio)
                if tipo == 'coppia':
                    riga = studente_info.get('riga', -1)

                    # Prima fila = riga 2 (dopo elementi fissi)
                    if riga == 2:
                        if nome not in stats['posizioni_prima_fila']:
                            stats['posizioni_prima_fila'][nome] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['posizioni_prima_fila'][nome]['assegnazioni']:
                            stats['posizioni_prima_fila'][nome]['count'] += 1
                            stats['posizioni_prima_fila'][nome]['assegnazioni'].append(nome_abbr)

        print(f"   ✅ Statistiche calcolate: {len(stats['studenti_unici'])} studenti, {len(stats['coppie_frequenza'])} coppie uniche")

        return stats

    def _mostra_statistiche_complete(self, stats, nome_filtro):
        """
        Mostra tutte le statistiche calcolate nell'interfaccia.

        Args:
            stats: Dizionario con statistiche calcolate
            nome_filtro: Nome classe filtrata
        """
        # === SEZIONE 1: RIEPILOGO GENERALE ===
        group_riepilogo = QGroupBox("📋 RIEPILOGO GENERALE")
        group_riepilogo.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_riepilogo = QVBoxLayout(group_riepilogo)

        label_filtro = QLabel(f"<b>Classe:</b> {nome_filtro}")
        layout_riepilogo.addWidget(label_filtro)

        label_assegnazioni = QLabel(f"<b>Assegnazioni totali:</b> {stats['num_assegnazioni']}")
        layout_riepilogo.addWidget(label_assegnazioni)

        if stats['prima_data']:
            label_date = QLabel(f"<b>Periodo:</b> dal {stats['prima_data']} al {stats['ultima_data']}")
            layout_riepilogo.addWidget(label_date)

        label_studenti = QLabel(f"<b>Studenti coinvolti:</b> {len(stats['studenti_unici'])}")
        layout_riepilogo.addWidget(label_studenti)

        self.layout_statistiche_content.addWidget(group_riepilogo)

        # === SEZIONE 2: COPPIE PIÙ FREQUENTI (Top 10) ===
        group_coppie = QGroupBox("👥 COPPIE PIÙ FREQUENTI (Top 10)")
        group_coppie.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_coppie = QVBoxLayout(group_coppie)

        # Ordina coppie per frequenza (ora x[1] è un dict con 'count')
        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale con conteggio
                label_coppia = QLabel(f"{idx:2d}. {nome1} + {nome2} ({count} volte)")
                label_coppia.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_coppie.addWidget(label_coppia)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"     → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_coppie.addWidget(label_asseg)
        else:
            label_vuoto = QLabel("Nessuna coppia registrata")
            label_vuoto.setStyleSheet("color: #888888; font-style: italic; padding-left: 10px;")
            layout_coppie.addWidget(label_vuoto)

        self.layout_statistiche_content.addWidget(group_coppie)

        # === SEZIONE 3: STATISTICHE TRIO ===
        if stats['trio_frequenza']:
            group_trio = QGroupBox("🎯 STATISTICHE TRIO")
            group_trio.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
            layout_trio = QVBoxLayout(group_trio)

            # Ordina per frequenza (ora x[1] è un dict con 'count')
            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale
                label_trio = QLabel(f"• {nome} ({count} volte nel trio)")
                label_trio.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_trio.addWidget(label_trio)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_trio.addWidget(label_asseg)

            self.layout_statistiche_content.addWidget(group_trio)

        # === SEZIONE 4: DETTAGLIO PER STUDENTE (con dropdown) ===
        group_dettaglio = QGroupBox("🔍 DETTAGLIO PER STUDENTE")
        group_dettaglio.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_dettaglio = QVBoxLayout(group_dettaglio)

        # Label istruzione
        label_istruzione = QLabel("Seleziona uno studente per vedere con chi è stato abbinato:")
        label_istruzione.setStyleSheet(f"font-style: italic; color: {C('testo_info')};")
        layout_dettaglio.addWidget(label_istruzione)

        # Dropdown studenti
        combo_studenti = QComboBox()
        combo_studenti.addItem("-- Seleziona uno studente --", None)
        for nome in sorted(stats['studenti_unici']):
            combo_studenti.addItem(nome, nome)
        combo_studenti.setStyleSheet(f"""
            QComboBox {{
                padding: 6px;
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
            }}
            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
                selection-color: #ffffff;
                border: 1px solid {C("bordo_leggero")};
            }}
        """)
        layout_dettaglio.addWidget(combo_studenti)

        # Area risultati dettaglio studente
        self.area_dettaglio_studente = QWidget()
        layout_area_dettaglio = QVBoxLayout(self.area_dettaglio_studente)
        layout_dettaglio.addWidget(self.area_dettaglio_studente)

        # Connetti dropdown per mostrare dettagli
        combo_studenti.currentIndexChanged.connect(
            lambda: self._mostra_dettaglio_studente(
                combo_studenti.currentData(),
                stats
            )
        )

        self.layout_statistiche_content.addWidget(group_dettaglio)

        # === SEZIONE 5: POSIZIONI PRIMA FILA ===
        if stats['posizioni_prima_fila']:
            group_prima = QGroupBox("📍 STUDENTI IN PRIMA FILA")
            group_prima.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
            layout_prima = QVBoxLayout(group_prima)

            # Ordina per frequenza (ora x[1] è un dict con 'count')
            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale
                label_pos = QLabel(f"• {nome} ({count} volte)")
                label_pos.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_prima.addWidget(label_pos)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_prima.addWidget(label_asseg)

            # Identifica chi NON è mai stato in prima fila
            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                label_mai = QLabel(f"\n<b>Mai in prima fila ({len(mai_prima)}):</b>")
                layout_prima.addWidget(label_mai)

                for nome in sorted(mai_prima):
                    label_nome = QLabel(f"  • {nome}")
                    label_nome.setStyleSheet("color: #FF9800; padding-left: 20px;")
                    layout_prima.addWidget(label_nome)

            self.layout_statistiche_content.addWidget(group_prima)

        # === SEZIONE 6: COPPIE MAI FORMATE ===
        group_mai = QGroupBox("🚫 COPPIE MAI FORMATE")
        group_mai.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_mai = QVBoxLayout(group_mai)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            # Limita a 20 per non intasare
            label_info = QLabel(f"Trovate {len(coppie_mai_formate)} coppie mai formate (mostrando le prime 20):")
            label_info.setStyleSheet("font-style: italic;")
            layout_mai.addWidget(label_info)

            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:20], 1):
                label_coppia_mai = QLabel(f"{idx:2d}. {nome1} - {nome2}")
                label_coppia_mai.setStyleSheet("padding-left: 10px; color: #FF6B6B;")
                layout_mai.addWidget(label_coppia_mai)
        else:
            label_completo = QLabel("✅ Tutti gli studenti sono stati abbinati almeno una volta con tutti gli altri!")
            label_completo.setStyleSheet("color: #4CAF50; padding-left: 10px;")
            layout_mai.addWidget(label_completo)

        self.layout_statistiche_content.addWidget(group_mai)

        # Spacer finale
        self.layout_statistiche_content.addStretch()

    def _mostra_dettaglio_studente(self, nome_studente, stats):
        """
        Mostra i dettagli di abbinamento per uno studente specifico.
        VERSIONE 2.0: Include lista assegnazioni per ogni abbinamento.
        """
        # Pulisce area dettaglio
        while self.area_dettaglio_studente.layout().count():
            child = self.area_dettaglio_studente.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not nome_studente:
            return

        # Ottiene dati studente
        dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
        compagni = dettagli.get('compagni', {})

        if not compagni:
            label_vuoto = QLabel("Nessun dato disponibile per questo studente")
            label_vuoto.setStyleSheet("color: #888888; font-style: italic;")
            self.area_dettaglio_studente.layout().addWidget(label_vuoto)
            return

        # Header
        label_header = QLabel(f"<b>{nome_studente}:</b> {stats['num_assegnazioni']} assegnazioni totali")
        label_header.setStyleSheet("font-size: 13px; margin-top: 10px;")
        self.area_dettaglio_studente.layout().addWidget(label_header)

        # È stato nel trio?
        if nome_studente in stats['trio_frequenza']:
            dati_trio = stats['trio_frequenza'][nome_studente]
            count_trio = dati_trio['count']
            asseg_trio = dati_trio['assegnazioni']

            label_trio_info = QLabel(f"  🎯 Nel trio: {count_trio} volte")
            label_trio_info.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.area_dettaglio_studente.layout().addWidget(label_trio_info)

            # Mostra assegnazioni trio (max 5)
            if asseg_trio:
                if len(asseg_trio) <= 5:
                    asseg_str = ", ".join(asseg_trio)
                else:
                    asseg_str = ", ".join(asseg_trio[:5]) + f" (e altre {len(asseg_trio)-5})"

                label_trio_asseg = QLabel(f"     → {asseg_str}")
                label_trio_asseg.setStyleSheet("padding-left: 20px; color: #FF9800; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_trio_asseg)

        # Compagni ordinati per frequenza (ora x[1] è un dict)
        compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)

        label_compagni = QLabel(f"<b>Abbinato con:</b>")
        label_compagni.setStyleSheet("margin-top: 5px;")
        self.area_dettaglio_studente.layout().addWidget(label_compagni)

        for compagno, dati in compagni_ordinati:
            count = dati['count']
            assegnazioni = dati['assegnazioni']

            # Label principale
            label_comp = QLabel(f"  • {compagno} ({count} volte)")
            label_comp.setStyleSheet("font-weight: bold;")
            self.area_dettaglio_studente.layout().addWidget(label_comp)

            # Mostra assegnazioni (max 5)
            if assegnazioni:
                if len(assegnazioni) <= 5:
                    asseg_str = ", ".join(assegnazioni)
                else:
                    asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                label_asseg = QLabel(f"     → {asseg_str}")
                label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_asseg)

        # Chi non ha mai avuto come compagno
        tutti_studenti = stats['studenti_unici']
        mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

        if mai_abbinati:
            label_mai = QLabel(f"\n<b>Mai stato con ({len(mai_abbinati)}):</b>")
            label_mai.setStyleSheet("color: #FF6B6B;")
            self.area_dettaglio_studente.layout().addWidget(label_mai)

            for nome in sorted(mai_abbinati):
                label_nome_mai = QLabel(f"  • {nome}")
                label_nome_mai.setStyleSheet("color: #FF6B6B;")
                self.area_dettaglio_studente.layout().addWidget(label_nome_mai)

    def _trova_coppie_mai_formate(self, stats):
        """
        Trova tutte le coppie di studenti che non sono mai stati abbinati.

        Returns:
            list: Lista di tuple (nome1, nome2) di coppie mai formate
        """
        studenti = list(stats['studenti_unici'])
        coppie_formate = set(stats['coppie_frequenza'].keys())

        coppie_mai = []

        # Genera tutte le coppie possibili
        for i in range(len(studenti)):
            for j in range(i + 1, len(studenti)):
                coppia = tuple(sorted([studenti[i], studenti[j]]))
                if coppia not in coppie_formate:
                    coppie_mai.append(coppia)

        return coppie_mai

    def _elimina_assegnazione(self, indice_assegnazione: int):
        """
        Elimina un'assegnazione dallo storico dopo conferma dell'utente.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione da eliminare
        """
        try:
            # Ottiene i dati dell'assegnazione da eliminare
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]
                nome_assegnazione = assegnazione.get("nome", "Senza nome")
                data_assegnazione = assegnazione.get("data", "N/A")

                # Conta coppie e trio dagli abbinamenti
                abbinamenti = assegnazione.get("abbinamenti", [])
                num_coppie = len([a for a in abbinamenti if a.get("tipo") == "coppia"])
                num_trio = len([a for a in abbinamenti if a.get("tipo") == "trio"])

                # Crea messaggio dettagliato
                messaggio_abbinamenti = f"👥 Coppie: {num_coppie}"
                if num_trio > 0:
                    messaggio_abbinamenti += f" | Trio: {num_trio}"

                # Chiede conferma all'utente
                risposta = QMessageBox.question(
                    self,
                    "Conferma eliminazione",
                    f"Sei sicuro di voler eliminare questa assegnazione?\n\n"
                    f"📅 Data: {data_assegnazione}\n"
                    f"📝 Nome: {nome_assegnazione}\n"
                    f"{messaggio_abbinamenti}\n\n"
                    f"⚠️ Questa azione non può essere annullata!",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No  # Pulsante predefinito: No (sicurezza)
                )

                if risposta == QMessageBox.Yes:
                    # Rimuove l'assegnazione dallo storico
                    del self.config_app.config_data["storico_assegnazioni"][indice_assegnazione]

                    # NUOVO: Ricostruisce blacklist per coerenza dopo eliminazione
                    print(f"🔄 Eliminazione assegnazione: avvio ricostruzione blacklist...")
                    self.config_app._ricostruisci_blacklist_da_storico()
                    print(f"✅ Blacklist ricostruita - coerenza garantita")

                    # Salva immediatamente la configurazione aggiornata
                    self.config_app.salva_configurazione()

                    # Aggiorna l'interfaccia
                    self._aggiorna_info_storico()  # Aggiorna contatore e stato

                    # Messaggio di conferma
                    QMessageBox.information(
                        self,
                        "Eliminazione completata",
                        f"✅ Assegnazione '{nome_assegnazione}' eliminata con successo."
                    )

                    # Disabilita i bottoni export: l'assegnazione a cui si
                    # riferivano potrebbe essere quella appena eliminata,
                    # e il nome suggerito per il file verrebbe preso da
                    # una voce diversa dello storico (fuorviante).
                    # Il docente può riesportare dopo aver salvato di nuovo.
                    self.btn_export_excel.setEnabled(False)
                    self.btn_export_excel.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )
                    self.btn_export_report_txt.setEnabled(False)
                    self.btn_export_report_txt.setToolTip(
                        "Salva prima l'assegnazione nello Storico per abilitare l'export."
                    )

            else:
                # Errore: indice non valido
                QMessageBox.warning(
                    self,
                    "Errore",
                    "Impossibile eliminare: assegnazione non trovata."
                )

        except Exception as e:
            # Gestione errori imprevisti
            QMessageBox.critical(
                self,
                "Errore eliminazione",
                f"Si è verificato un errore durante l'eliminazione:\n{str(e)}"
            )

    def _visualizza_dettagli_assegnazione(self, indice_assegnazione: int):
        """
        Visualizza i dettagli completi di un'assegnazione storica in una finestra separata.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione da visualizzare
        """
        try:
            # Ottiene i dati dell'assegnazione
            storico = self.config_app.config_data["storico_assegnazioni"]

            if 0 <= indice_assegnazione < len(storico):
                assegnazione = storico[indice_assegnazione]

                # Usa il report completo salvato se disponibile
                if "report_completo" in assegnazione:
                    dettagli = assegnazione["report_completo"]
                else:
                    # Fallback: genera report basilare dal layout
                    dettagli = self._genera_report_da_layout(assegnazione)

                # Crea dialog custom ridimensionabile
                dialog = QDialog(self)
                dialog.setWindowTitle(f"📋 Dettagli assegnazione - {assegnazione.get('nome', 'Senza nome')}")
                dialog.setMinimumSize(1100, 800)  # Larghezza maggiore per titolo completo
                dialog.resize(1150, 800)  # Dimensione iniziale

                # Layout verticale
                layout = QVBoxLayout(dialog)

                # TextEdit in sola lettura per il report
                text_edit = QTextEdit()
                text_edit.setPlainText(dettagli)
                text_edit.setReadOnly(True)
                # Usa una famiglia di font monospace con fallback cross-platform
                # "Consolas" → Windows | "Courier New" → macOS | "DejaVu Sans Mono" → Linux
                font_mono = QFont()
                font_mono.setFamily("Consolas")           # Tentativo 1: Windows
                font_mono.setStyleHint(QFont.Monospace)   # Fallback automatico Qt al monospace del sistema
                font_mono.setPointSize(10)
                text_edit.setFont(font_mono)
                layout.addWidget(text_edit)

                # === EVIDENZIAZIONE COPPIE RIUTILIZZATE ===
                from PySide6.QtGui import QTextCharFormat, QTextCursor

                # Formato ocra/giallo grassetto
                formato_ocra = QTextCharFormat()
                formato_ocra.setForeground(QColor("#CC8800"))
                formato_ocra.setFontWeight(QFont.Bold)

                # Pattern da evidenziare
                patterns_da_evidenziare = ["Coppia già usata", "BLACKLISTATA_SOFT", "RIUTILIZZATA"]

                for pattern in patterns_da_evidenziare:
                    cursore = text_edit.textCursor()
                    cursore.movePosition(QTextCursor.Start)
                    text_edit.setTextCursor(cursore)

                    while True:
                        cursore = text_edit.document().find(pattern, cursore)
                        if cursore.isNull():
                            break
                        # Seleziona l'intera riga e applica formato ocra
                        cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                        cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                        cursore.setCharFormat(formato_ocra)

                # Riporta il cursore all'inizio
                cursore_iniziale = text_edit.textCursor()
                cursore_iniziale.movePosition(QTextCursor.Start)
                text_edit.setTextCursor(cursore_iniziale)

                # Bottone Chiudi
                btn_chiudi = QPushButton("✅ Chiudi")
                btn_chiudi.setMinimumHeight(40)
                btn_chiudi.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                        border-radius: 6px;
                        padding: 8px 20px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)
                btn_chiudi.clicked.connect(dialog.close)
                layout.addWidget(btn_chiudi)

                # Applica tema attivo al dialog dettagli
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

                # Mostra dialog
                dialog.exec()

            else:
                QMessageBox.warning(self, "Errore", "Assegnazione non trovata.")

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nella visualizzazione:\n{str(e)}")

    def _genera_report_da_layout(self, assegnazione: dict) -> str:
        """
        Genera un report basilare dal campo 'layout' (fallback se manca report_completo).

        Args:
            assegnazione (dict): Dati dell'assegnazione

        Returns:
            str: Report formattato
        """
        report = []

        # Header
        report.append(f"📋 DETTAGLI ASSEGNAZIONE")
        report.append("=" * 40)
        report.append(f"📝 Nome: {assegnazione.get('nome', 'Senza nome')}")
        report.append(f"📅 Data: {assegnazione.get('data', 'N/A')}")
        report.append(f"🕐 Ora: {assegnazione.get('ora', 'N/A')}")
        report.append(f"📁 File origine: {assegnazione.get('file_origine', 'Non specificato')}")

        # Layout
        layout = assegnazione.get('layout', [])

        if layout:
            # Conta coppie e trio
            studenti_coppia = [s for s in layout if s.get('tipo') == 'coppia']
            studenti_trio = [s for s in layout if s.get('tipo') == 'trio']

            num_coppie = len(studenti_coppia) // 2
            num_trio = 1 if len(studenti_trio) == 3 else 0

            report.append(f"👥 Coppie: {num_coppie}")
            if num_trio > 0:
                report.append(f"👥 Trio: {num_trio}")
            report.append("")

            # Lista abbinamenti
            report.append("💫 ABBINAMENTI FORMATI:")
            report.append("-" * 20)

            # Mostra coppie
            coppie_mostrate = set()
            idx = 1
            for studente_info in layout:
                if studente_info.get('tipo') == 'coppia':
                    nome = studente_info['studente']
                    compagno = studente_info.get('compagno', '?')
                    coppia_key = tuple(sorted([nome, compagno]))

                    if coppia_key not in coppie_mostrate:
                        coppie_mostrate.add(coppia_key)
                        report.append(f"{idx:2d}. {nome} + {compagno}")
                        idx += 1

            # Mostra trio
            if num_trio > 0:
                trio_studenti = [s['studente'] for s in layout if s.get('tipo') == 'trio']
                if len(trio_studenti) == 3:
                    report.append("")
                    report.append(f"TRIO: {' + '.join(trio_studenti)}")
        else:
            report.append("")
            report.append("⚠️ Nessun layout disponibile")

        return "\n".join(report)

    def _visualizza_layout_storico(self, indice_assegnazione):
        """
        Apre il popup per visualizzare il layout grafico di un'assegnazione storica.

        Args:
            indice_assegnazione (int): Indice dell'assegnazione nello storico
        """
        try:
            # Crea e mostra il popup
            popup = PopupLayoutStorico(self, self.config_app, indice_assegnazione)
            popup.exec()  # Mostra come dialog modale

        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore Visualizzazione",
                f"❌ Errore durante l'apertura del layout:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def _resetta_tab_aula_report(self):
        """
        Pulisce le tab Aula e Report quando si cambia classe o si chiude
        un file, eliminando i dati stantii dell'assegnazione precedente.

        Viene chiamato da:
        - _on_editor_file_cambiato() → quando l'Editor carica un nuovo file
        - _on_editor_file_chiuso() → quando l'Editor chiude il file corrente
        - _carica_studenti_da_editor() → quando il pannello principale carica nuovi dati

        Effetti:
        - Svuota la griglia visuale dell'aula (tab Aula)
        - Svuota il report testuale (tab Report)
        - Disabilita i bottoni di salvataggio e export
        """
        # --- Pulisci la griglia dell'aula ---
        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # --- Pulisci il report testuale ---
        self.text_report.clear()

        # --- Disabilita i bottoni (nessuna assegnazione attiva) ---
        self.btn_salva_progetto.setEnabled(False)
        self.btn_export_excel.setEnabled(False)
        self.btn_export_report_txt.setEnabled(False)

    def _on_editor_file_cambiato(self):
        """
        Slot chiamato quando l'Editor carica un nuovo file tramite il suo
        bottone "Carica classe da modificare (.txt)".

        Resetta i dati del pannello principale (self.studenti) per evitare
        che restino in memoria gli studenti di una classe precedente
        mentre l'Editor mostra una classe diversa.

        Il docente dovrà usare "Seleziona file classe (.txt)" per ri-caricare
        i dati dall'Editor nel pannello principale.
        """
        # Resetta gli studenti caricati
        self.studenti = []
        self.file_origine_studenti = None

        # Pulisci Aula e Report (dati stantii dell'assegnazione precedente)
        self._resetta_tab_aula_report()

        # Resetta il nome classe (si ripopolerà dal nuovo file)
        self.input_nome_classe.clear()

        # Disabilita il bottone di assegnazione (non ci sono più dati pronti)
        self.btn_avvia_assegnazione.setEnabled(False)

        # NON resettare lo schema aula qui. Il ripristino avverrà quando
        # il docente cliccherà "Seleziona file classe": _controlla_classe_gia_elaborata
        # ripristinerà lo schema dallo storico se la classe è già nota,
        # oppure metterà i default se è una classe nuova.

        # Aggiorna la label in base allo stato del file appena caricato nell'Editor:
        # - Se ci sono generi mancanti → avvisa che servono modifiche
        # - Se il file è già completo → invita a caricare nel pannello principale
        if (self.editor_studenti.ha_studenti_caricati() and
                not self.editor_studenti.tutti_generi_impostati()):
            # Ci sono generi da completare: indica chiaramente che servono modifiche
            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"⚠️ Nuova classe caricata nell'Editor — MODIFICHE NECESSARIE\n"
                f"({len(mancanti)} gener{'e' if len(mancanti) == 1 else 'i'} da impostare)"
            )
        else:
            # File già completo: invita semplicemente a caricare
            self.label_studenti_caricati.setText(
                "⚠️ Nuova classe caricata nell'Editor\n"
                f"— Clicca '📁 Seleziona file classe (.txt)' per caricarla"
            )
        self.label_studenti_caricati.setStyleSheet("""
            background-color: #E65100;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid #FF9800;
        """)

        # Resetta il flag di assegnazione non salvata
        self.assegnazione_non_salvata = False

        print("🔄 L'Editor ha caricato un nuovo file → dati pannello resettati")

        # Mostra la tab Editor per dare conferma visiva del caricamento
        self.tab_widget.setCurrentIndex(4)  # Tab "✏️ Editor studenti"

    def _on_editor_genere_cambiato(self):
        """
        Slot chiamato quando il docente cambia il genere di uno studente
        nell'Editor. Aggiorna la label nel pannello sinistro in tempo reale.

        Se tutti i generi sono ora impostati, la label diventa verde
        e invita il docente a cliccare "Carica classe da modificare (.txt)" per procedere.
        Se restano generi da completare, la label resta arancione.
        """
        if not self.editor_studenti.ha_studenti_caricati():
            return  # Editor vuoto, niente da fare

        if self.editor_studenti.tutti_generi_impostati():
            # Tutti i generi impostati → pronto per il caricamento
            nome_file = self.editor_studenti._nome_file_caricato or ""
            self.label_studenti_caricati.setText(
                f"✅ '{nome_file}' pronto — Clicca '📁 Seleziona file classe (.txt)' per caricare"
            )
            self.label_studenti_caricati.setStyleSheet("""
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid #4CAF50;
            """)
        else:
            # Restano generi da completare → conta quanti mancano
            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                f"⏳ Genere da completare ({len(mancanti)} rimast{'o' if len(mancanti) == 1 else 'i'})"
            )
            self.label_studenti_caricati.setStyleSheet("""
                background-color: #E65100;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 8px;
                border-radius: 5px;
                border: 1px solid #FF9800;
            """)

    def _on_editor_file_chiuso(self):
        """
        Slot chiamato quando l'Editor chiude il file corrente
        (bottone "Chiudi file" o chiusura confermata).

        Riporta la label del pannello sinistro allo stato iniziale
        e resetta i dati caricati, così non resta nessun messaggio
        ambiguo che suggerisca che un file sia ancora in memoria.
        """
        # Resetta gli studenti caricati nel pannello principale
        self.studenti = []
        self.file_origine_studenti = None

        # Pulisci Aula e Report (dati stantii dell'assegnazione precedente)
        self._resetta_tab_aula_report()

        # Resetta il nome classe
        self.input_nome_classe.clear()

        # Disabilita il bottone di assegnazione
        self.btn_avvia_assegnazione.setEnabled(False)

        # Riporta la label allo stato iniziale (identico a quando si apre il programma)
        self.label_studenti_caricati.setText("Nessun file caricato")
        self.label_studenti_caricati.setStyleSheet("color: gray; font-style: italic;")

        # Ripristina lo schema aula ai default (nessuna classe caricata → default)
        self.input_num_file.setText("4")
        self.input_posti_fila.setText("6")
        self._aggiorna_posti_totali()

        # Resetta il flag di assegnazione non salvata
        self.assegnazione_non_salvata = False

    def carica_file_studenti(self):
        """
        Apre dialog per caricare il file degli studenti.

        FLUSSO UNIFICATO: il file viene caricato nell'Editor (che è l'unico
        punto di validazione), in modo da garantire:
        - Rilevamento automatico del formato (base o completo)
        - Check coerenza bidirezionale dei vincoli
        - Validazione genere (placeholder se mancante)
        - Gestione corretta di righe con formato errato

        Se l'Editor non trova problemi, gli studenti vengono caricati
        automaticamente e il docente resta nel pannello principale.
        Se ci sono problemi (es: genere da impostare), viene portato
        nella tab Editor per correggerli.
        """

        # === GUARDIA: Assegnazione non salvata nello storico? ===
        # Se il docente ha eseguito un'assegnazione ma non l'ha ancora
        # salvata, caricare una nuova classe cancellerebbe i risultati.
        # Questo controllo è lo stesso pattern usato in closeEvent().
        if self.assegnazione_non_salvata:
            dialog_ass = QMessageBox(self)
            dialog_ass.setWindowTitle("⚠️ Assegnazione non salvata")
            dialog_ass.setIcon(QMessageBox.Warning)
            dialog_ass.setText(
                "L'ultima assegnazione NON è stata salvata nello storico.\n\n"
                "Se carichi una nuova classe adesso, i risultati\n"
                "dell'assegnazione corrente andranno PERSI e le coppie\n"
                "formate non verranno considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?"
            )

            btn_salva_ass = dialog_ass.addButton(
                "💾 Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_prosegui = dialog_ass.addButton(
                "🚪 Prosegui senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_ass = dialog_ass.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            dialog_ass.setDefaultButton(btn_salva_ass)
            # X della finestra e tasto Esc = Annulla (nessuna azione)
            dialog_ass.setEscapeButton(btn_annulla_ass)

            dialog_ass.exec()

            bottone_ass = dialog_ass.clickedButton()

            if bottone_ass == btn_annulla_ass:
                # Annulla: il docente resta dov'era, nessuna azione
                return

            if bottone_ass == btn_salva_ass:
                # Il docente vuole salvare l'assegnazione prima di procedere
                self.salva_assegnazione()
                # Se dopo il salvataggio il flag è ancora True,
                # il docente ha annullato il salvataggio → blocca tutto
                if self.assegnazione_non_salvata:
                    return

            # Se "Prosegui senza salvare" → continua col caricamento

        # === CHECK RAPIDO: L'Editor ha già dati corretti pronti? ===
        # Se il docente era stato mandato nell'Editor a correggere
        # il genere e ha completato, può usare quei dati direttamente
        # senza dover esportare e ricaricare il file.
        if (self.editor_studenti.ha_studenti_caricati() and
                self.editor_studenti.tutti_generi_impostati()):
            # L'Editor ha dati completi e validi: chiedi se usarli
            nome_file_editor = self.editor_studenti._nome_file_caricato or "sconosciuto"
            # --- Popup a 3 bottoni: Usa Editor / Carica nuovo / Annulla ---
            # Usa QMessageBox custom invece di .question() per avere 3 bottoni
            # e per fare in modo che la X della finestra = "Annulla" (non "No").
            dialog_dati = QMessageBox(self)
            dialog_dati.setWindowTitle("📋 Dati già pronti nell'Editor")
            dialog_dati.setIcon(QMessageBox.Question)
            dialog_dati.setText(
                f"👉 La tab 'Editor studenti' contiene la classe '{nome_file_editor}'.\n"
                f"Se scegli di usare questi dati, potrai iniziare le assegnazioni\n"
                f"dei posti per gli allievi di '{nome_file_editor}'\n\n"
                f"👉 Se scegli di caricare un NUOVO file, le modifiche eventualmente\n"
                f"effettuate nell'Editor per questa classe (vincoli, genere, posizione)\n"
                f"andranno PERSE se non le hai salvate con 'Salva file CLASSE completo (.txt)'.\n\n"
                f"Che cosa vuoi fare?"
            )

            # Crea i 3 bottoni personalizzati
            btn_usa_editor = dialog_dati.addButton(
                "✅ Usa i dati dall'Editor", QMessageBox.AcceptRole
            )
            btn_nuovo_file = dialog_dati.addButton(
                "📂 Carica un nuovo file", QMessageBox.DestructiveRole
            )
            btn_annulla_dati = dialog_dati.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            # Il bottone di default (premendo Invio) è "Usa Editor" (scelta sicura)
            dialog_dati.setDefaultButton(btn_usa_editor)
            # Se il docente chiude con la X, equivale ad "Annulla" (nessuna azione)
            dialog_dati.setEscapeButton(btn_annulla_dati)

            dialog_dati.exec()

            bottone_scelto = dialog_dati.clickedButton()

            if bottone_scelto == btn_annulla_dati:
                # Annulla: non fa nulla, il docente resta dov'era
                return

            if bottone_scelto == btn_usa_editor:
                # Il docente ha corretto i dati nell'Editor → segna come correzione
                # per garantire l'auto-salvataggio del file aggiornato
                self.editor_studenti._correzioni_applicate = True
                # Usa il percorso originale del file (salvato dall'Editor)
                file_path_editor = self.editor_studenti._percorso_file_caricato
                if not file_path_editor:
                    # Fallback: costruisci percorso dalla cartella dati
                    nome_file = self.editor_studenti._nome_file_caricato
                    file_path_editor = os.path.join(
                        self.editor_studenti._get_cartella_dati(),
                        f"{nome_file}.txt"
                    )
                self._carica_studenti_da_editor(file_path_editor)
                return

        # === FLUSSO NORMALE: Apri dialog e seleziona file ===
        # Apri direttamente nella cartella dati/ (cross-platform, compatibile PyInstaller)
        cartella_dati = self.editor_studenti._get_cartella_dati()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona file classe (.txt)",
            cartella_dati,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if not file_path:
            return  # L'utente ha annullato

        try:
            # === PASSO 1: Carica il file nell'Editor ===
            # L'Editor gestisce: auto-rilevamento formato, parsing,
            # check coerenza bidirezionale, genere placeholder
            caricamento_ok = self.editor_studenti.carica_file_da_percorso(file_path)

            if not caricamento_ok:
                return  # Caricamento fallito (errore file o annullato)

            # === PASSO 2: Verifica se ci sono problemi pendenti ===

            # 2a) Controlla se tutti i generi sono impostati
            if not self.editor_studenti.tutti_generi_impostati():
                # Pulisci Aula e Report: se c'era un'assegnazione precedente
                # di un'altra classe, quei dati stantii resterebbero visibili
                # mentre il docente lavora nell'Editor per completare i generi.
                self._resetta_tab_aula_report()

                # Ci sono studenti senza genere → porta il docente nell'Editor
                studenti_da_correggere = self.editor_studenti.get_nomi_studenti_senza_genere()
                elenco = "\n".join(f"  • {nome}" for nome in studenti_da_correggere[:10])
                if len(studenti_da_correggere) > 10:
                    elenco += f"\n  ... e altri {len(studenti_da_correggere) - 10}"

                QMessageBox.information(
                    self,
                    "📝 Genere da impostare",
                    f"Il file è stato caricato nell'Editor Studenti.\n\n"
                    f"I seguenti studenti hanno il genere da selezionare:\n\n"
                    f"{elenco}\n\n"
                    f"💡 Imposta M o F per ogni studente, poi torna\n"
                    f"a cliccare '📁 Seleziona file classe (.txt)':\n"
                    f"il programma userà automaticamente i dati corretti."
                )

                # Switcha alla tab Editor per permettere la correzione
                # Cerca l'indice della tab Editor
                for i in range(self.tab_widget.count()):
                    if "Editor" in self.tab_widget.tabText(i):
                        self.tab_widget.setCurrentIndex(i)
                        break

                # Aggiorna la label per indicare che il file è in lavorazione
                self.label_studenti_caricati.setText(
                    f"⏳ File caricato nell'Editor — Genere da completare"
                )
                self.label_studenti_caricati.setStyleSheet("""
                    background-color: #E65100;
                    color: white;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 6px 8px;
                    border-radius: 5px;
                    border: 1px solid #FF9800;
                """)
                return

            # === PASSO 3: Tutto OK → Crea gli oggetti Student dall'Editor ===
            self._carica_studenti_da_editor(file_path)

        except Exception as e:
            self._mostra_errore(
                "Errore caricamento",
                f"Errore nel caricamento del file:\n{str(e)}"
            )

    def _carica_studenti_da_editor(self, file_path: str):
        """
        Legge i dati dall'Editor e crea gli oggetti Student.
        Chiamato quando l'Editor ha completato il caricamento senza problemi.

        Questo metodo sostituisce il vecchio carica_studenti_da_file():
        invece di leggere dal file .txt, prende i dati già validati
        dall'Editor, garantendo coerenza e completezza.

        Args:
            file_path: Percorso del file (per salvare il nome e auto-rilevamento)
        """
        # Pulisci Aula e Report della classe precedente.
        # La nuova classe richiederà una nuova assegnazione,
        # quindi i risultati vecchi non hanno più senso.
        self._resetta_tab_aula_report()
        # Recupera i dati strutturati da TUTTE le schede dell'Editor
        dati_studenti = self.editor_studenti.get_dati_tutti_studenti()

        if not dati_studenti:
            self._mostra_errore("File vuoto", "Il file selezionato non contiene studenti validi.")
            return

        # === Conversione dati Editor → oggetti Student ===
        # L'Editor restituisce dict con chiavi:
        #   cognome, nome, sesso, posizione, incompatibilità, affinità
        # L'algoritmo ha bisogno di oggetti Student con i medesimi attributi

        # MAPPA DI LOOKUP: "Cognome Nome" → cognome reale
        # Serve per gestire correttamente cognomi composti (es: "De Rossi")
        # L'Editor usa "Cognome Nome" come chiave nei vincoli,
        # ma Student.aggiungi_incompatibilita vuole solo il cognome
        mappa_cognomi = {}
        for dati in dati_studenti:
            nome_completo = f"{dati['cognome']} {dati['nome']}"
            mappa_cognomi[nome_completo] = dati["cognome"]

        studenti = []
        for dati in dati_studenti:
            # Crea lo studente base
            studente = Student(
                cognome=dati["cognome"],
                nome=dati["nome"],
                sesso=dati["sesso"],
                nota_posizione=dati["posizione"]
            )

            # Aggiunge le incompatibilità
            # Nell'Editor: dict {"Cognome Nome": livello}
            # Nello Student: dict {cognome: livello} (solo cognome come chiave)
            for nome_completo, livello in dati["incompatibilita"].items():
                # Cerca il cognome reale nella mappa (gestisce cognomi composti)
                cognome_target = mappa_cognomi.get(nome_completo)
                if cognome_target:
                    studente.aggiungi_incompatibilita(cognome_target, livello)
                else:
                    # Fallback: usa la prima parola (non dovrebbe mai servire)
                    print(f"⚠️ Vincolo incompatibilità con '{nome_completo}' non trovato nella mappa")
                    parti = nome_completo.split(' ', 1)
                    studente.aggiungi_incompatibilita(parti[0], livello)

            # Aggiunge le affinità (stessa logica)
            for nome_completo, livello in dati["affinita"].items():
                cognome_target = mappa_cognomi.get(nome_completo)
                if cognome_target:
                    studente.aggiungi_affinita(cognome_target, livello)
                else:
                    print(f"⚠️ Vincolo affinità con '{nome_completo}' non trovato nella mappa")
                    parti = nome_completo.split(' ', 1)
                    studente.aggiungi_affinita(parti[0], livello)

            studenti.append(studente)

        # === AUTO-SALVATAGGIO del file corretto ===
        # Se l'Editor ha applicato correzioni (vincoli bidirezionali aggiunti,
        # conversione da formato base a completo), sovrascrive il file originale
        # con la versione corretta. Questo evita che il docente debba gestire
        # manualmente un file con problemi noti.
        self._auto_salva_file_corretto()

        # === Aggiorna lo stato dell'applicazione ===
        self.studenti = studenti
        self.file_origine_studenti = Path(file_path).name
        num_studenti = len(studenti)

        # Aggiorna interfaccia con sfondo ocra per evidenziare l'informazione
        self.label_studenti_caricati.setText(
            f"✅ Caricati {num_studenti} studenti da '{Path(file_path).name}'"
        )
        self.label_studenti_caricati.setStyleSheet("""
            background-color: #B8860B;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid #DAA520;
        """)

        # Abilita il bottone di assegnazione
        self.btn_avvia_assegnazione.setEnabled(True)

        # Aggiorna visibilità controlli numero dispari
        self._aggiorna_visibilita_dispari()

        # Estrae il nome file per auto-rilevamento classe
        nome_file = Path(file_path).stem.replace("_", " ").title()

        # Aggiorna nome classe dal file (il campo è read-only)
        self.input_nome_classe.setText(nome_file)

        # AUTO-RILEVAMENTO: Se classe già elaborata, attiva rotazione
        # e RIPRISTINA LO SCHEMA AULA dallo storico (num_file, posti_per_fila).
        # Deve avvenire PRIMA di _aggiorna_posti_totali, altrimenti il calcolo
        # userebbe lo schema default 4x6 invece di quello salvato.
        self._controlla_classe_gia_elaborata(nome_file)

        # Aggiorna calcolo posti (ora con lo schema corretto, ripristinato sopra)
        self._aggiorna_posti_totali()

        # Aggiorna la label storico ORA che sappiamo quale classe è caricata.
        # Non viene fatto all'avvio (nessun file ancora caricato),
        # ma solo qui, dopo che il docente ha selezionato il file .txt.
        self._aggiorna_info_storico()

        # Mostra la tab Editor per dare al docente conferma visiva
        # che la classe è stata caricata (la tab Aula sarebbe vuota
        # finché non si esegue un'assegnazione, e potrebbe confondere).
        self.tab_widget.setCurrentIndex(4)  # Tab "✏️ Editor studenti"

    def _auto_salva_file_corretto(self):
        """
        Salva automaticamente il file .txt corretto dall'Editor.

        Viene chiamato dopo che l'Editor ha applicato correzioni:
        - Vincoli bidirezionali aggiunti
        - Conversione da formato base a formato completo a 6 campi
        - Genere/posizione completati dal docente

        Il file originale viene sovrascritto con la versione corretta.
        Se il salvataggio fallisce (es: file read-only), mostra un avviso
        ma NON blocca il flusso (i dati in memoria sono già corretti).
        """
        # Verifica se ci sono correzioni da salvare
        if not self.editor_studenti._correzioni_applicate:
            # Nessuna correzione: il file su disco era già perfetto.
            # Resetta il flag "modifiche non salvate" perché non c'è nulla
            # da salvare → evita il popup alla chiusura del programma.
            self.editor_studenti._modifiche_non_salvate = False
            return

        # Recupera il percorso del file originale
        percorso = self.editor_studenti._percorso_file_caricato

        if not percorso:
            # Nessun percorso (non dovrebbe mai succedere), skip silenzioso
            print("⚠️ Auto-save: nessun percorso file disponibile")
            return

        try:
            # Genera il contenuto corretto dall'Editor (formato completo a 6 campi)
            contenuto_corretto = self.editor_studenti._genera_txt()

            # Sovrascrive il file originale
            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(contenuto_corretto)

            # Segna che le modifiche sono state salvate
            self.editor_studenti._modifiche_non_salvate = False
            self.editor_studenti._correzioni_applicate = False

            # === POPUP VISIBILE per informare il docente ===
            nome_file = Path(percorso).name
            QMessageBox.information(
                self,
                "💾 File salvato e pronto all'uso",
                f"Il file è stato automaticamente salvato e caricato:\n\n"
                f"📄 {nome_file}\n"
                f"📁 {percorso}\n\n"
                f"👍 ORA L'INTERA LISTA DEGLI STUDENTI (con i rispettivi\n"
                f"vincoli) È CARICATA E PRONTA PER L'«ASSEGNAZIONE»!"
            )

            print(f"💾 Auto-save: file corretto salvato in '{percorso}'")

        except PermissionError:
            # File read-only o protetto: avvisa ma non bloccare
            QMessageBox.warning(
                self,
                "⚠️ Salvataggio automatico non riuscito",
                f"Il file non può essere sovrascritto (potrebbe essere protetto):\n"
                f"{percorso}\n\n"
                f"Le correzioni sono comunque attive per l'assegnazione corrente.\n"
                f"💡 Puoi salvare manualmente dalla tab 'Editor' con\n"
                f"'💾 Esporta file completo (.txt)'."
            )

        except Exception as e:
            # Altro errore: avvisa ma non bloccare
            print(f"⚠️ Auto-save fallito: {e}")
            QMessageBox.warning(
                self,
                "⚠️ Salvataggio automatico non riuscito",
                f"Errore nel salvataggio automatico:\n{e}\n\n"
                f"Le correzioni sono comunque attive per l'assegnazione corrente."
            )

    def avvia_assegnazione(self):
        """Avvia il processo di assegnazione automatica."""

        if not self.studenti:
            self._mostra_errore("Nessun dato", "Carica prima un file con gli studenti.")
            return

        # CONTROLLO POSTI INSUFFICIENTI: Blocca assegnazione con popup
        if hasattr(self, 'posti_insufficienti') and self.posti_insufficienti:
            risposta = QMessageBox.critical(
                self,
                "🚨 POSTI INSUFFICIENTI",
                f"IMPOSSIBILE PROCEDERE!\n\n"
                f"👥 Studenti da sistemare: {len(self.studenti)}\n"
                f"🪑 Posti disponibili: {int(self.input_num_file.text()) * int(self.input_posti_fila.text())}\n\n"
                f"💡 SOLUZIONI:\n"
                f"• Aumenta il numero di file di banchi\n"
                f"• Aumenta i posti per fila",
                QMessageBox.Ok
            )
            return

        # CONTROLLO ASSEGNAZIONE NON SALVATA: Avvisa il collega prima di sovrascrivere
        if self.assegnazione_non_salvata:
            dialog_avvia = QMessageBox(self)
            dialog_avvia.setWindowTitle("⚠️ Assegnazione non salvata")
            dialog_avvia.setIcon(QMessageBox.Warning)
            dialog_avvia.setText(
                "L'assegnazione corrente NON è stata salvata nello storico.\n\n"
                "Se procedi con una nuova elaborazione, le coppie formate\n"
                "non verranno considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?"
            )

            btn_salva_avvia = dialog_avvia.addButton(
                "💾 Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_prosegui_avvia = dialog_avvia.addButton(
                "🔄 Prosegui senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_avvia = dialog_avvia.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            dialog_avvia.setDefaultButton(btn_salva_avvia)
            # X della finestra e tasto Esc = Annulla
            dialog_avvia.setEscapeButton(btn_annulla_avvia)

            dialog_avvia.exec()

            bottone_avvia = dialog_avvia.clickedButton()

            if bottone_avvia == btn_salva_avvia:
                # Il collega vuole salvare prima → apri dialogo salvataggio
                self.salva_assegnazione()
                # Dopo il salvataggio (riuscito o annullato) torniamo al controllo dell'utente.
                # Se vuole lanciare una nuova elaborazione, cliccherà di nuovo "Avvia".
                return

            elif bottone_avvia == btn_annulla_avvia:
                # Annulla → non fare nulla
                return

            # Se "Prosegui senza salvare" → prosegui con la nuova elaborazione

        # Salva nome classe in configurazione
        self.config_app.config_data["classe_info"]["nome_classe"] = self.input_nome_classe.text()

        # Aggiorna configurazione aula
        self.config_app.config_data["configurazione_aula"]["num_file"] = int(self.input_num_file.text())
        self.config_app.config_data["configurazione_aula"]["posti_per_fila"] = int(self.input_posti_fila.text())

        # NUOVO SISTEMA: Salva opzioni vincoli (non più pesi configurabili)
        self.config_app.config_data["opzioni_vincoli"]["genere_misto_obbligatorio"] = self.checkbox_genere_misto.isChecked()

        # Crea configurazione aula
        num_studenti = len(self.studenti)
        self.configurazione_aula = ConfigurazioneAula(f"Aula {self.input_nome_classe.text()}")

        # Usa configurazione personalizzata
        num_file = int(self.input_num_file.text())
        posti_per_fila = int(self.input_posti_fila.text())

        # Determina posizione trio dai radio button
        # Ora solo 3 opzioni: prima, ultima, centro (rimosso "auto")
        posizione_trio = None
        modalita_trio = 'prima'  # Default se niente selezionato

        if num_studenti % 2 == 1:  # Solo se numero dispari
            if self.radio_trio_prima.isChecked():
                posizione_trio = "prima"
                modalita_trio = "prima"
            elif self.radio_trio_ultima.isChecked():
                posizione_trio = "ultima"
                modalita_trio = "ultima"
            elif self.radio_trio_centro.isChecked():
                posizione_trio = "centro"
                modalita_trio = "centro"
            # Nota: Rimosso caso "auto" - ora default è sempre "prima"

        self.configurazione_aula.crea_layout_standard(num_studenti, num_file, posti_per_fila, posizione_trio)

        # Verifica compatibilita
        if num_studenti > self.configurazione_aula.posti_disponibili:
            self._mostra_errore(
                "Configurazione Invalida",
                f"Non ci sono abbastanza posti!\n"
                f"Studenti: {num_studenti}\n"
                f"Posti disponibili: {self.configurazione_aula.posti_disponibili}\n\n"
                f"Aumenta il numero di file o posti per fila."
            )
            return

        # Determina modalita rotazione
        modalita_rotazione = self.radio_rotazione.isChecked()

        # Disabilita controlli durante elaborazione
        self._imposta_modalita_elaborazione(True)

        # Avvia timer messaggi rotativi (cambia messaggio ogni 2 secondi)
        self.indice_messaggio = 0  # Reset indice
        self.timer_messaggi.start(2000)  # 2000 ms = 2 secondi

        # Avvia thread di elaborazione
        self.worker_thread = WorkerThread(
            self.studenti,
            self.configurazione_aula,
            self.config_app,
            modalita_rotazione,
            modalita_trio,
            self.checkbox_genere_misto.isChecked()
        )

        self.worker_thread.status_updated.connect(self.label_status.setText)
        self.worker_thread.completed.connect(self._elaborazione_completata)
        self.worker_thread.error_occurred.connect(self._elaborazione_fallita)

        self.worker_thread.start()

    def _imposta_modalita_elaborazione(self, in_elaborazione: bool):
        """Imposta l'interfaccia in modalità elaborazione o normale."""

        self.btn_avvia_assegnazione.setEnabled(not in_elaborazione)

        if in_elaborazione:
            self.label_status.setText("🔄 Elaborazione in corso...")
        else:
            self.label_status.setText("")

    def _elaborazione_completata(self, assegnatore: AssegnatorePosti):
        """Chiamata quando l'elaborazione è completata con successo."""

        self.ultimo_assegnatore = assegnatore

        # Segna che c'è un'assegnazione non ancora salvata nello storico
        self.assegnazione_non_salvata = True

        # Ferma timer messaggi rotativi
        self.timer_messaggi.stop()

        # Ripristina interfaccia
        self._imposta_modalita_elaborazione(False)

        # Mostra risultati
        self._visualizza_risultati(assegnatore)

        # Abilita il salvataggio: l'utente deve prima salvare
        # prima di poter esportare (garantisce naming coerente)
        self.btn_salva_progetto.setEnabled(True)

        # I bottoni export rimangono disabilitati finché non si salva.
        # I tooltip spiegano il motivo all'utente.
        self.btn_export_excel.setEnabled(False)
        self.btn_export_excel.setToolTip(
            "Salva prima l'assegnazione nello storico per abilitare l'export."
        )
        self.btn_export_report_txt.setEnabled(False)
        self.btn_export_report_txt.setToolTip(
            "Salva prima l'assegnazione nello storico per abilitare l'export."
        )

        # Prepara messaggio con trio se presente
        messaggio_trio = ""
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            messaggio_trio = f"\n• Trio formato: 1 ({len(assegnatore.trio_identificato)} studenti)"

        # Messaggio di successo con coppie riutilizzate evidenziate in giallo/ocra
        num_riutilizzate = assegnatore.stats['coppie_riutilizzate']

        # Riga coppie riutilizzate: evidenziata in ocra se > 0, normale se 0
        if num_riutilizzate > 0:
            riga_riutilizzate = (
                f'<span style="color: #CC8800; font-weight: bold;">'
                f'⚠️ Coppie riutilizzate: {num_riutilizzate}</span>'
            )
        else:
            riga_riutilizzate = f"• Coppie riutilizzate: {num_riutilizzate}"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Assegnazione Completata")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setTextFormat(Qt.RichText)  # Abilita HTML nel testo
        msg_box.setText(
            f"✅ Assegnazione completata con successo!<br><br>"
            f"📊 <b>Statistiche:</b><br>"
            f"• Coppie totali: {len(assegnatore.coppie_formate)}<br>"
            f"• Coppie ottimali: {assegnatore.stats['coppie_ottimali']}<br>"
            f"• Coppie accettabili: {assegnatore.stats['coppie_accettabili']}<br>"
            f"• Coppie problematiche: {assegnatore.stats['coppie_problematiche']}<br>"
            f"{riga_riutilizzate}<br>"
            f"• Studenti singoli: {len(assegnatore.studenti_singoli)}{messaggio_trio}"
        )
        msg_box.exec()

    def _elaborazione_fallita(self, messaggio_errore: str):
        """Chiamata quando l'elaborazione fallisce."""

        # Ferma timer messaggi rotativi
        self.timer_messaggi.stop()

        self._imposta_modalita_elaborazione(False)
        self._mostra_errore("Errore Assegnazione", messaggio_errore)

    def _visualizza_risultati(self, assegnatore: AssegnatorePosti):
        """Visualizza i risultati dell'assegnazione nell'interfaccia."""

        # Aggiorna visualizzazione aula
        self._aggiorna_visualizzazione_aula(assegnatore.configurazione_aula)

        # Aggiorna report testuale
        self._aggiorna_report_testuale(assegnatore)

        # Seleziona tab aula per mostrare risultato
        self.tab_widget.setCurrentIndex(0)

    def _aggiorna_visualizzazione_aula(self, configurazione_aula: ConfigurazioneAula):
        """Aggiorna la griglia visuale dell'aula."""

        # Pulisce layout esistente
        while self.layout_griglia_aula.count():
            child = self.layout_griglia_aula.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Ricrea griglia aula - ORDINE INVERTITO
        # Le file vengono rovesciate: arredi (LIM, CAT, LAV) in basso,
        # ultima fila di banchi in alto (visione "dalla cattedra")
        griglia_invertita = list(reversed(configurazione_aula.griglia))
        for riga_idx, riga in enumerate(griglia_invertita):
            for col_idx, posto in enumerate(riga):

                widget_posto = self._crea_widget_posto(posto)
                self.layout_griglia_aula.addWidget(widget_posto, riga_idx, col_idx)

    def _crea_widget_posto(self, posto) -> QWidget:
        """
        Crea un widget per rappresentare un singolo posto nell'aula.
        VERSIONE CORRETTA: Gestisce identificatori univoci e mostra nomi completi.
        """

        widget = QLabel()
        widget.setMinimumSize(120, 60)  # Aumentata larghezza per nomi completi
        widget.setAlignment(Qt.AlignCenter)
        widget.setStyleSheet("border: 1px solid #ccc; margin: 1px;")

        if posto.tipo == 'banco':
            if posto.occupato_da:
                # Banco occupato - usa nome completo
                nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                widget.setText(nome_completo)
                widget.setStyleSheet(f"""
                    border: 2px solid {C("banco_occupato_bordo")};
                    background-color: {C("banco_occupato_sf")};
                    color: {C("banco_occupato_txt")};
                    font-weight: bold;
                    font-size: 11px;
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip(f"Studente: {nome_completo}")
            else:
                # Banco libero
                widget.setText("🪑")
                widget.setStyleSheet("""
                    border: 2px dashed #ccc;
                    background-color: #f9f9f9;
                    margin: 1px;
                    border-radius: 4px;
                """)
                widget.setToolTip("Posto libero")

        elif posto.tipo == 'cattedra':
            widget.setText("🏫")
            widget.setStyleSheet("""
                border: 2px solid #FF9800;
                background-color: #FFF3E0;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("Cattedra")

        elif posto.tipo == 'lim':
            widget.setText("📺")
            widget.setStyleSheet("""
                border: 2px solid #2196F3;
                background-color: #E3F2FD;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("LIM")

        elif posto.tipo == 'lavagna':
            widget.setText("⬛")
            widget.setStyleSheet("""
                border: 2px solid #795548;
                background-color: #EFEBE9;
                margin: 1px;
                border-radius: 4px;
            """)
            widget.setToolTip("Lavagna")

        else:  # corridoio
            widget.setText("")
            widget.setStyleSheet("""
                border: none;
                background-color: transparent;
                margin: 1px;
            """)

        return widget

    def _estrai_nome_completo_da_id(self, id_univoco: str) -> str:
        """
        Estrae il nome completo dall'identificatore univoco "cognome_nome".
        VERSIONE NUOVA: Gestisce i nuovi ID univoci e restituisce nome completo.

        Args:
            id_univoco: ID nel formato "Cognome_Nome" (es: "Colombo_Giulio Maria")

        Returns:
            Nome completo formattato (es: "Colombo Giulio Maria")
        """
        # Se l'ID non contiene '_', è un vecchio formato (solo cognome) - fallback
        if '_' not in id_univoco:
            print(f"⚠️  ID vecchio formato senza '_': '{id_univoco}', uso come-è")
            return id_univoco

        try:
            # Estrae cognome e nome dall'ID univoco
            cognome, nome = id_univoco.split('_', 1)

            # Restituisce nome completo formattato
            nome_completo = f"{cognome} {nome}"
            return nome_completo

        except Exception as e:
            print(f"❌ Errore parsing ID '{id_univoco}': {e}")
            # Fallback: sostituisce _ con spazio
            return id_univoco.replace('_', ' ')

    def _calcola_riga_excel_con_corridoi(self, start_row: int, riga_idx: int, configurazione) -> int:
        """
        Calcola la riga Excel aggiungendo spazio tra file di banchi.

        LOGICA:
        - Riga 0 (elementi fissi): posizione normale
        - Riga 1 (spazio): posizione normale
        - Riga 2+ (file banchi): +1 riga extra per ogni fila per creare corridoi

        Args:
            start_row: Riga di partenza nell'Excel
            riga_idx: Indice riga nella griglia aula
            configurazione: Layout aula per identificare file banchi

        Returns:
            int: Riga Excel finale con corridoi
        """
        # Elementi fissi (cattedra, LIM, lavagna) - nessun corridoio extra
        if riga_idx <= 1:
            return start_row + riga_idx

        # File di banchi - aggiungi corridoio dopo ogni fila
        # riga_idx=2 → Excel: start_row + 3 (2 + 1 corridoio)
        # riga_idx=3 → Excel: start_row + 5 (3 + 2 corridoi)
        # riga_idx=4 → Excel: start_row + 7 (4 + 3 corridoi)
        num_file_precedenti = riga_idx - 2  # Quante file di banchi ci sono prima di questa
        corridoi_extra = num_file_precedenti + 1  # +1 corridoio per ogni fila precedente + questa

        return start_row + riga_idx + corridoi_extra

    def _aggiorna_report_testuale(self, assegnatore: AssegnatorePosti):
        """Aggiorna il report testuale con dettagli dell'assegnazione."""

        report = []

        # Header
        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("=" * 60)
        report.append(f"Classe: {self.input_nome_classe.text()}")
        report.append(f"Data/Ora: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        report.append(f"Studenti elaborati: {len(self.studenti)}")
        report.append("")

        # Statistiche generali - ora allineate con terminale e popup
        report.append("📊 STATISTICHE GENERALI")
        report.append("-" * 30)
        report.append(f"Coppie totali: {len(assegnatore.coppie_formate)}")
        report.append(f"Coppie ottimali: {assegnatore.stats['coppie_ottimali']}")
        report.append(f"Coppie accettabili: {assegnatore.stats['coppie_accettabili']}")
        report.append(f"Coppie problematiche: {assegnatore.stats['coppie_problematiche']}")
        report.append(f"Coppie riutilizzate: {assegnatore.stats['coppie_riutilizzate']}")
        report.append(f"Studenti singoli: {len(assegnatore.studenti_singoli)}")
        # Aggiungi informazioni sul trio se presente
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            report.append(f"Trio formato: 1 ({len(assegnatore.trio_identificato)} studenti)")
        report.append("")

        # Dettaglio trio se presente
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            report.append("👥 TRIO FORMATO")
            report.append("-" * 30)

            trio = assegnatore.trio_identificato
            punteggio_trio = assegnatore._valuta_trio(trio)

            # Valuta ogni coppia interna al trio
            nomi_trio = [s.get_nome_completo() for s in trio]
            report.append(f"Trio: {' + '.join(nomi_trio)}")
            report.append(f"Punteggio totale: {punteggio_trio}")

            # Analizza SOLO le 2 coppie fisicamente adiacenti nel trio
            coppie_adiacenti = [(trio[0], trio[1]), (trio[1], trio[2])]  # Solo 1-2 e 2-3
            for i, (s1, s2) in enumerate(coppie_adiacenti, 1):
                risultato = assegnatore.motore_vincoli.calcola_punteggio_coppia(s1, s2)
                report.append(f"  Coppia adiacente {i}: {s1.get_nome_completo()} + {s2.get_nome_completo()}")
                report.append(f"    Punteggio: {risultato['punteggio_totale']} - {risultato['valutazione']}")

                if risultato['note']:
                    for nota in risultato['note']:
                        report.append(f"    • {nota}")

            # Nota informativa sulla coppia non adiacente
            report.append(f"  NOTA: {trio[0].get_nome_completo()} e {trio[2].get_nome_completo()} non sono adiacenti (separati da {trio[1].get_nome_completo()})")

            report.append("")

        # Dettaglio coppie formate
        report.append("👥 COPPIE FORMATE")
        report.append("-" * 30)

        for idx, (studente1, studente2, info) in enumerate(assegnatore.coppie_formate, 1):
            report.append(f"{idx:2d}. {studente1.get_nome_completo()} + {studente2.get_nome_completo()}")
            report.append(f"    Punteggio: {info['punteggio_totale']} - {info['valutazione']}")

            if info['note']:
                for nota in info['note']:
                    report.append(f"    • {nota}")

            report.append("")

        # Studenti singoli se ce ne sono
        if assegnatore.studenti_singoli:
            report.append("👤 STUDENTI SINGOLI")
            report.append("-" * 30)

            for studente in assegnatore.studenti_singoli:
                report.append(f"• {studente.get_nome_completo()} ({studente.nota_posizione})")

            report.append("")

        # Layout aula testuale
        report.append("🏫 LAYOUT AULA")
        report.append("-" * 30)

        # Usa il metodo della configurazione aula per il layout testuale
        # ORDINE INVERTITO: arredi in basso, ultima fila banchi in alto
        griglia_invertita = list(reversed(assegnatore.configurazione_aula.griglia))
        # Contatore file banchi: numera dal basso (fila 1 = più vicina alla cattedra)
        num_file_banchi = sum(1 for riga in griglia_invertita
                             if any(p.tipo == 'banco' for p in riga))
        contatore_fila = num_file_banchi  # Parte dal numero più alto

        for riga in griglia_invertita:
            # Determina se questa riga contiene banchi o arredi
            ha_banchi = any(p.tipo == 'banco' for p in riga)
            ha_arredi = any(p.tipo in ('cattedra', 'lim', 'lavagna') for p in riga)

            if ha_banchi:
                # Riga di banchi: usa contatore decrescente (ultima fila = numero più alto)
                riga_str = f"Fila {contatore_fila:2d}: "
                contatore_fila -= 1
            elif ha_arredi:
                # Riga arredi: etichetta speciale
                riga_str = f"Fila  0: "
            else:
                continue  # Salta righe vuote (solo corridoi)

            for posto in riga:
                if posto.occupato_da:
                    nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                    riga_str += f"[{nome_completo}] "
                elif posto.tipo == 'banco':
                    riga_str += " 🪑 "
                elif posto.tipo == 'cattedra':
                    riga_str += " 🏫 "
                elif posto.tipo == 'lim':
                    riga_str += " 📺 "
                elif posto.tipo == 'lavagna':
                    riga_str += " ⬛ "
                else:
                    riga_str += "   "

            report.append(riga_str)

        # Aggiorna il widget di testo
        self.text_report.setPlainText("\n".join(report))

        # === EVIDENZIAZIONE COPPIE RIUTILIZZATE ===
        # Cerca nel report le righe relative a coppie riutilizzate e le colora in ocra/giallo
        from PySide6.QtGui import QTextCharFormat, QTextCursor

        # Formato ocra/giallo grassetto per evidenziare le righe critiche
        formato_ocra = QTextCharFormat()
        formato_ocra.setForeground(QColor("#CC8800"))  # Colore ocra
        formato_ocra.setFontWeight(QFont.Bold)

        # Pattern da evidenziare: "Coppia già usata" nelle note delle coppie
        cursore = self.text_report.textCursor()
        patterns_da_evidenziare = ["Coppia già usata", "BLACKLISTATA_SOFT", "RIUTILIZZATA"]

        for pattern in patterns_da_evidenziare:
            # Riporta il cursore all'inizio per ogni pattern
            cursore.movePosition(QTextCursor.Start)
            self.text_report.setTextCursor(cursore)

            # Cerca tutte le occorrenze del pattern nel testo
            while True:
                # Usa la funzione di ricerca del QTextEdit
                cursore = self.text_report.document().find(pattern, cursore)
                if cursore.isNull():
                    break  # Nessuna altra occorrenza trovata

                # Seleziona l'INTERA RIGA che contiene il pattern
                cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

                # Applica il formato ocra alla riga intera
                cursore.setCharFormat(formato_ocra)

        # Riporta il cursore all'inizio del documento (evita scroll in fondo)
        cursore_iniziale = self.text_report.textCursor()
        cursore_iniziale.movePosition(QTextCursor.Start)
        self.text_report.setTextCursor(cursore_iniziale)

    def esporta_excel(self):
        """Esporta i risultati in formato Excel (.xlsx)."""

        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun Risultato", "Esegui prima un'assegnazione.")
            return

        # A questo punto il salvataggio è garantito: prendiamo il nome
        # esattamente dall'ultima assegnazione salvata nello storico.
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        ultima = storico[-1] if storico else {}
        nome_base = ultima.get("nome", self.input_nome_classe.text())

        nome_pulito = pulisci_nome_file(nome_base)
        nome_suggerito = f"{nome_pulito}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva file Excel",
            nome_suggerito,
            "File Excel (*.xlsx);;Tutti i file (*)"
        )

        if file_path:
            try:
                self._crea_file_excel(file_path, self.ultimo_assegnatore)

                mostra_popup_file_salvato(self, "Export Completato", "✅ File Excel salvato con successo!", file_path)

            except Exception as e:
                self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    def esporta_report_txt(self):
        """Esporta il report testuale dell'assegnazione corrente in formato TXT."""
        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun Risultato", "Esegui prima un'assegnazione.")
            return

        try:
            # Nome dall'ultima assegnazione salvata (salvataggio garantito)
            storico = self.config_app.config_data.get("storico_assegnazioni", [])
            ultima = storico[-1] if storico else {}
            nome_base = ultima.get("nome", self.input_nome_classe.text())

            nome_pulito = pulisci_nome_file(nome_base)
            nome_suggerito = f"{nome_pulito}.txt"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Esporta Report TXT",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                # Usa il report già generato nel tab Report
                report_completo = self.text_report.toPlainText()

                # Salva su file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_completo)

                mostra_popup_file_salvato(self, "Export Completato", "✅ Report TXT salvato con successo!", file_path)

        except Exception as e:
            self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    def _crea_file_excel(self, file_path: str, assegnatore: AssegnatorePosti):
        """
        Crea il file Excel con il layout dell'aula.
        Usa xlsxwriter per compatibilità nativa con Excel 2019+
        (openpyxl genera XML privo degli attributi applyFill/applyBorder
        che Excel richiede, causando bordi e colori invisibili).

        NOTA: xlsxwriter usa indici 0-based (riga 0 = prima riga, colonna 0 = A).
        """
        import xlsxwriter

        wb = xlsxwriter.Workbook(file_path)
        ws = wb.add_worksheet("PostiPerfetti")

        # === DEFINIZIONE FORMATI (vanno creati una volta, poi riusati) ===

        # Header titolo e data
        fmt_titolo = wb.add_format({"bold": True, "font_size": 16})
        fmt_data = wb.add_format({"font_size": 11})

        # Banco occupato: sfondo verde chiaro + bordo medio + grassetto
        fmt_banco_occupato = wb.add_format({
            "bold": True,
            "font_size": 9,
            "bg_color": "#C8E6C9",
            "border": 2,  # 2 = medium (compatibile con tutte le versioni Excel)
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,  # A capo automatico per nomi lunghi
        })

        # Banco libero: sfondo grigio chiaro + bordo medio
        fmt_banco_libero = wb.add_format({
            "bg_color": "#F5F5F5",
            "border": 2,
            "align": "center",
            "valign": "vcenter",
        })

        # Arredi: sfondo colorato + grassetto + centrato (uno per tipo)
        fmt_lim = wb.add_format({
            "bold": True,
            "bg_color": "#BBDEFB",
            "align": "center",
            "valign": "vcenter",
        })
        fmt_cattedra = wb.add_format({
            "bold": True,
            "bg_color": "#FFE0B2",
            "align": "center",
            "valign": "vcenter",
        })
        fmt_lavagna = wb.add_format({
            "bold": True,
            "bg_color": "#D7CCC8",
            "align": "center",
            "valign": "vcenter",
        })

        # Mappa tipo arredo → (formato, etichetta)
        mappa_arredi = {
            "lim": (fmt_lim, "LIM"),
            "cattedra": (fmt_cattedra, "CATTEDRA"),
            "lavagna": (fmt_lavagna, "LAVAGNA"),
        }

        # === HEADER (B2, B3 in notazione umana → riga 1, col 1 in 0-based) ===
        ws.write(1, 1, f"«PostiPerfetti» - {self.input_nome_classe.text()}", fmt_titolo)
        ws.write(2, 1, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_data)

        # === LAYOUT AULA ===
        configurazione = assegnatore.configurazione_aula

        # Griglia invertita: arredi in basso, ultima fila banchi in alto
        griglia_invertita = list(reversed(configurazione.griglia))

        # Filtra solo le righe con contenuto (banchi o arredi, no righe vuote)
        righe_con_contenuto = [
            riga for riga in griglia_invertita
            if any(p.tipo != 'corridoio' for p in riga)
        ]

        # Traccia le colonne con contenuto per ottimizzare le larghezze
        colonne_con_contenuto = set()
        # Traccia la riga degli arredi per l'unione celle
        riga_excel_arredi = None

        # start_row = 4 (0-based, equivale alla riga 5 in Excel)
        excel_row = 4

        for riga in righe_con_contenuto:
            # Imposta altezza riga (35 pixel) per tutti i banchi e arredi
            ws.set_row(excel_row, 35)

            for col_idx, posto in enumerate(riga):
                # +1 per lasciare colonna A vuota (margine stampa, 0-based)
                excel_col = col_idx + 1

                if posto.tipo == 'banco':
                    # --- BANCHI ---
                    if posto.occupato_da:
                        nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                        ws.write(excel_row, excel_col, nome_completo, fmt_banco_occupato)
                    else:
                        ws.write(excel_row, excel_col, "🪑", fmt_banco_libero)

                    colonne_con_contenuto.add(excel_col)

                elif posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    # --- ARREDI ---
                    # Gli arredi vengono gestiti a coppie: le posizioni nella
                    # griglia sono [0,1], [3,4], [6,7]. Scriviamo il merge
                    # SOLO quando incontriamo la prima cella della coppia
                    # (col_idx 0, 3, 6). La seconda cella è coperta dal merge.
                    is_prima_cella = col_idx in (0, 3, 6)

                    if is_prima_cella:
                        fmt_arredo, etichetta = mappa_arredi[posto.tipo]
                        # merge_range(riga_inizio, col_inizio, riga_fine, col_fine, testo, formato)
                        ws.merge_range(
                            excel_row, excel_col,
                            excel_row, excel_col + 1,
                            etichetta, fmt_arredo
                        )

                    riga_excel_arredi = excel_row
                    colonne_con_contenuto.add(excel_col)

            # Dopo ogni riga con contenuto, salta una riga per il corridoio visivo
            excel_row += 2

        # === OTTIMIZZAZIONE LARGHEZZA COLONNE ===

        # Colonna A (indice 0): margine stretto per stampa
        ws.set_column(0, 0, 2)

        # Imposta larghezze: colonne con contenuto = 18, corridoi = 3
        if colonne_con_contenuto:
            max_col = max(colonne_con_contenuto)
            for col_num in range(1, max_col + 2):  # +2 per sicurezza
                if col_num in colonne_con_contenuto:
                    ws.set_column(col_num, col_num, 18)
                else:
                    ws.set_column(col_num, col_num, 3)

        # === CONFIGURAZIONE STAMPA A4 ===
        # Orientamento orizzontale per sfruttare la larghezza del foglio
        ws.set_landscape()
        ws.set_paper(9)  # 9 = A4

        # Adatta tutto il contenuto a una singola pagina
        ws.fit_to_pages(1, 1)  # (larghezza, altezza) in numero di pagine

        # Margini ridotti per massimizzare lo spazio utile (in pollici)
        ws.set_margins(left=0.4, right=0.4, top=0.4, bottom=0.4)
        ws.set_header("", {"margin": 0.2})
        ws.set_footer("", {"margin": 0.2})

        # Fine generazione Excel
        wb.close()

    def salva_assegnazione(self):
        """Salva l'assegnazione corrente nello storico."""

        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun Risultato", "Esegui prima un'assegnazione.")
            return

        # Dialog per nome assegnazione
        nome_assegnazione, ok = self._chiedi_nome_assegnazione()

        if ok and nome_assegnazione:

            # Salva nello storico (coppie + trio se presente)
            trio_presente = getattr(self.ultimo_assegnatore, 'trio_identificato', None)
            # Genera report completo PRIMA di salvare
            report_completo = self.text_report.toPlainText()

            self.config_app.aggiungi_assegnazione_storico(
                nome_assegnazione,
                self.ultimo_assegnatore.coppie_formate,
                trio_presente,
                self.ultimo_assegnatore.configurazione_aula,  # Passa configurazione aula
                self.file_origine_studenti,  # Passa nome file origine
                report_completo  # Passa report completo
            )

            # Aggiorna interfaccia
            self._aggiorna_info_storico()  # Aggiorna contatore e stato
            self._popola_filtro_classi()  # Aggiorna filtro statistiche
            self._aggiorna_statistiche()  # Ricalcola statistiche

            QMessageBox.information(
                self,
                "Assegnazione Salvata",
                f"✅ Assegnazione '{nome_assegnazione}' salvata nello storico."
            )

            # Segna che l'assegnazione è stata salvata
            self.assegnazione_non_salvata = False

            # Abilita i bottoni export ora che l'assegnazione è salvata.
            # Il nome del file esportato corrisponderà esattamente al nome
            # dell'assegnazione nello storico.
            self.btn_export_excel.setEnabled(True)
            self.btn_export_excel.setToolTip("Esporta questa assegnazione in formato Excel.")
            self.btn_export_report_txt.setEnabled(True)
            self.btn_export_report_txt.setToolTip("Esporta il report testuale di questa assegnazione.")

            # Auto-switch a "Rotazione mensile" per le assegnazioni successive
            self.radio_rotazione.setChecked(True)

    def _chiedi_nome_assegnazione(self) -> tuple:
        """Chiede il nome per l'assegnazione da salvare."""

        from PySide6.QtWidgets import QInputDialog

        # Recupera il nome classe dal campo (popolato dal file .txt)
        nome_classe = self.input_nome_classe.text() or "Classe"

        # Calcola numero progressivo basato sullo storico esistente
        # Conta quante assegnazioni esistono già per questa classe
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        # Filtra le assegnazioni che contengono parole significative del nome classe
        parole_classe = [p.lower() for p in nome_classe.split() if len(p) > 1]
        conteggio = 0
        for assegnazione in storico:
            nome_ass = assegnazione.get("nome", "").lower()
            # Controlla se il nome dell'assegnazione contiene parole della classe
            if any(parola in nome_ass for parola in parole_classe):
                conteggio += 1

        # Numero progressivo = assegnazioni esistenti + 1
        numero_progressivo = conteggio + 1
        numero_str = f"{numero_progressivo:02d}"  # Formato "01", "02", ecc.

        # Data corrente in formato compatto
        data_oggi = datetime.now().strftime('%d/%m/%Y')

        # Nome suggerito: "Classe 3A - Assegnazione 01 - 07/03/2026"
        nome_suggerito = f"{nome_classe} - Assegnazione {numero_str} - {data_oggi}"

        # Crea un QInputDialog personalizzato per avere il controllo sulla larghezza.
        # Il getText() statico non permette di impostare le dimensioni,
        # e con nomi lunghi tipo "Classe 3A - Assegnazione 01 - 07/03/2026"
        # il campo risulta troppo stretto per leggere il testo completo.
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Nome Assegnazione")
        dialog.setLabelText("Inserisci un nome per questa assegnazione:")
        dialog.setTextValue(nome_suggerito)
        dialog.resize(550, 150)  # Larghezza generosa per nomi lunghi

        ok = dialog.exec()
        return dialog.textValue(), ok

    def _cambia_tema(self):
        """
        Alterna tra tema scuro e tema chiaro.
        Aggiorna tutti i widget visibili e salva la preferenza in config.json.
        """
        # Determina il nuovo tema (opposto a quello attuale)
        nuovo_tema = "chiaro" if get_tema() == "scuro" else "scuro"

        # Aggiorna la variabile globale nel modulo tema
        imposta_tema(nuovo_tema)

        # Aggiorna lo stylesheet globale della finestra principale
        self.setup_stili()

        # Aggiorna i widget con stili inline (non coperti dal stylesheet globale)
        self._aggiorna_stili_widget()

        # Aggiorna l'editor studenti (schede, separatori, bottoni)
        if hasattr(self, 'editor_studenti'):
            self.editor_studenti.aggiorna_tema()

        # Aggiorna i combo dinamici (statistiche e filtro classi)
        # che non ereditano automaticamente il nuovo tema
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        # Aggiorna l'etichetta del bottone toggle
        # (mostra sempre il tema verso cui si può passare)
        if nuovo_tema == "chiaro":
            self.btn_toggle_tema.setText("🌙 Scuro")
        else:
            self.btn_toggle_tema.setText("☀️ Chiaro")

        # Salva la preferenza in config.json
        self.config_app.config_data["tema"] = nuovo_tema
        self.config_app.salva_configurazione()

    def _mostra_crediti(self):
        """
        Mostra una finestra con le informazioni sul programma,
        l'autore, la versione e la licenza GNU GPLv3.
        """
        dialog = QDialog(self)
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
        percorso_icona = os.path.join(get_base_path(), "modelli", "postiperfetti_icon.png")
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
            incompatibilità, rotazione mensile e storico assegnazioni.
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
            Questo software è libero: puoi usarlo, copiarlo, studiarlo
            e redistribuirlo liberamente.<br><br>
            Se modifichi il programma e lo redistribuisci, sei tenuto
            a rendere pubblico il codice sorgente delle tue modifiche
            con la stessa licenza GPLv3.<br><br>
            Il software è distribuito <i>«così com'è»</i>, senza alcuna
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

    def _aggiorna_stili_widget(self):
        """
        Riapplica gli stili inline ai widget che non ereditano
        automaticamente dallo stylesheet globale della finestra.
        Chiamato sia all'avvio (per caricare il tema salvato)
        sia al cambio tema.
        """
        # --- Campo nome classe (read-only: sfondo leggermente diverso) ---
        self.input_nome_classe.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C("sfondo_pannello")};
                color: {C("testo_secondario")};
                border: 1px solid {C("bordo_normale")};
            }}
        """)

        # --- Campi numerici file/posti e bottoni +/− ---
        stile_campo_numero = f"""
            QLineEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                font-weight: bold;
            }}
        """
        stile_btn_meno = f"""
            QPushButton {{
                background-color: {C("sfondo_input_alt")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_leggero")};
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: #f44336;
                border: 1px solid #c62828;
            }}
        """
        stile_btn_piu = f"""
            QPushButton {{
                background-color: {C("sfondo_input_alt")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_leggero")};
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {C("accento")};
                border: 1px solid {C("accento_scuro")};
            }}
        """
        self.input_num_file.setStyleSheet(stile_campo_numero)
        self.btn_file_meno.setStyleSheet(stile_btn_meno)
        self.btn_file_piu.setStyleSheet(stile_btn_piu)
        self.input_posti_fila.setStyleSheet(stile_campo_numero)
        self.btn_posti_meno.setStyleSheet(stile_btn_meno)
        self.btn_posti_piu.setStyleSheet(stile_btn_piu)

        # --- Box vincoli automatici ---
        if hasattr(self, 'label_info_vincoli'):
            self.label_info_vincoli.setStyleSheet(
                f"color: {C('testo_label_sec')}; font-size: 13px; font-style: italic;"
            )

        # --- Label storico (se non ci sono dati, rimane grigia) ---
        num_storico = len(self.config_app.config_data.get("storico_assegnazioni", []))
        if num_storico == 0:
            self.label_storico.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 12px; font-style: italic;"
            )

    def _mostra_aiuto_configurazione_aula(self):
        """
        Mostra un popup con schema ASCII che spiega visivamente
        cosa si intende per 'file di banchi' e 'posti per fila'.
        """
        dialog = QDialog(self)
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
            "Se il numero di studenti è dispari, una delle file ospiterà un trio."
        )
        spiegazione.setWordWrap(True)
        spiegazione.setStyleSheet(
            f"color: {C('testo_principale')}; font-size: 14px; line-height: 1.5;"
        )
        layout.addWidget(spiegazione)

        # Bottone chiudi
        btn_chiudi = QPushButton("✅ Chiudi")
        btn_chiudi.setMinimumHeight(36)
        btn_chiudi.setStyleSheet("""
            QPushButton {
                background-color: #5C6BC0;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #3F51B5; }
        """)
        btn_chiudi.clicked.connect(dialog.close)
        layout.addWidget(btn_chiudi)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
            }}
        """)

        dialog.exec()

    def _mostra_errore(self, titolo: str, messaggio: str):
        """Mostra un messaggio di errore."""
        QMessageBox.warning(self, titolo, messaggio)

    def _aggiorna_messaggio_elaborazione(self):
        """
        Aggiorna il messaggio di elaborazione in modo rotativo.
        Chiamato automaticamente dal timer ogni 2 secondi.
        """
        # Cambia al messaggio successivo nella lista
        self.indice_messaggio = (self.indice_messaggio + 1) % len(self.messaggi_elaborazione)
        messaggio_corrente = self.messaggi_elaborazione[self.indice_messaggio]

        # Aggiorna la label di status
        self.label_status.setText(messaggio_corrente)

    def _controlla_classe_gia_elaborata(self, nome_file_classe):
        """
        Controlla se la classe è già stata elaborata in precedenza.
        Se SÌ: attiva automaticamente genere misto + rotazione mensile.

        Args:
            nome_file_classe (str): Nome derivato dal file (es: "Classe_3A")
        """
        # Pulisce il nome file per confronto (rimuove estensioni, underscore)
        nome_classe_pulito = nome_file_classe.replace("_", " ").replace(".txt", "").lower().strip()

        # Controlla se esiste già una configurazione per questa classe
        nome_classe_salvato = self.config_app.config_data.get("classe_info", {}).get("nome_classe", "").lower().strip()
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        # Classe trovata se: nome salvato corrisponde OR ci sono assegnazioni nello storico
        classe_trovata = False

        # Controlla corrispondenza nome classe
        if nome_classe_salvato and nome_classe_pulito in nome_classe_salvato:
            classe_trovata = True

        # Se nome non corrisponde, controlla nello storico se ci sono assegnazioni di questa specifica classe
        if not classe_trovata and len(storico) > 0:
            for assegnazione in storico:
                nome_assegnazione = assegnazione.get("nome", "").lower()
                # Cerca parole significative del nome classe nel nome assegnazione
                parole_classe = [p for p in nome_classe_pulito.split() if len(p) > 3]  # Solo parole lunghe
                if any(parola in nome_assegnazione for parola in parole_classe):
                    classe_trovata = True
                    break

        if classe_trovata:
            # CLASSE GIÀ ELABORATA: Auto-configura per rotazione
            self.radio_rotazione.setChecked(True)

            # --- RIPRISTINO SCHEMA AULA dall'ultima assegnazione della classe ---
            # Cerca l'assegnazione più recente che corrisponde a questa classe
            # e ripristina num_file e posti_per_fila, così il docente non deve
            # reimpostarli ogni volta che ricarica la stessa classe.
            for assegnazione in reversed(storico):
                config_aula_salvata = assegnazione.get("configurazione_aula", {})
                nome_ass = assegnazione.get("nome", "").lower()
                # Verifica che l'assegnazione appartenga a questa classe.
                # Usa il nome classe INTERO (es: "2b", "classe 3a") per il match,
                # NON parole singole con filtro lunghezza — i nomi come "2B" o "3A"
                # hanno solo 2 caratteri e verrebbero esclusi da filtri tipo len > 3.
                if nome_classe_pulito and nome_classe_pulito in nome_ass:
                    # Trovata! Ripristina i valori dello schema aula
                    num_file_salvato = config_aula_salvata.get("num_file")
                    posti_salvati = config_aula_salvata.get("posti_per_fila")
                    if num_file_salvato is not None:
                        self.input_num_file.setText(str(num_file_salvato))
                    if posti_salvati is not None:
                        self.input_posti_fila.setText(str(posti_salvati))
                    # Aggiorna il conteggio posti totali nella label
                    self._aggiorna_posti_totali()
                    break  # Basta l'ultima assegnazione

            # Mostra notifica all'utente
            self.label_status.setText("🔄 Classe riconosciuta - Auto-configurata per rotazione")
            self.label_status.setStyleSheet("color: #4CAF50; font-weight: bold;")

            # Rimuovi messaggio dopo 15 secondi, MA solo se nel frattempo
            # non è partita un'elaborazione (che usa label_status per i
            # suoi messaggi rotativi — cancellarla sarebbe confusionario).
            QTimer.singleShot(15000, lambda: (
                self.label_status.setText("")
                if not self.timer_messaggi.isActive()
                else None
            ))
        else:
            # NUOVA CLASSE: Mantieni configurazione per prima assegnazione
            self.checkbox_genere_misto.setChecked(False)
            self.radio_prima_volta.setChecked(True)

            # Ripristina i default dello schema aula, nel caso il docente
            # avesse caricato prima una classe diversa con schema diverso
            self.input_num_file.setText("4")
            self.input_posti_fila.setText("6")
            self._aggiorna_posti_totali()

    def closeEvent(self, event):
        """Gestisce la chiusura dell'applicazione."""

        # Controlla se l'editor studenti ha modifiche non salvate
        # Se sì, mostra il popup di conferma (salva/esci/annulla)
        if hasattr(self, 'editor_studenti'):
            if not self.editor_studenti.richiedi_conferma_chiusura():
                # L'utente ha annullato → blocca la chiusura
                event.ignore()
                return

        # Controlla se c'è un'assegnazione non salvata nello storico
        if self.assegnazione_non_salvata:
            dialog_chiudi = QMessageBox(self)
            dialog_chiudi.setWindowTitle("⚠️ Assegnazione non salvata")
            dialog_chiudi.setIcon(QMessageBox.Warning)
            dialog_chiudi.setText(
                "L'ultima assegnazione NON è stata salvata nello Storico.\n\n"
                "Se chiudi ora, le coppie formate non verranno\n"
                "considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?"
            )

            btn_salva_chiudi = dialog_chiudi.addButton(
                "💾 Salva assegnazione", QMessageBox.AcceptRole
            )
            btn_esci_chiudi = dialog_chiudi.addButton(
                "🚪 Chiudi senza salvare", QMessageBox.DestructiveRole
            )
            btn_annulla_chiudi = dialog_chiudi.addButton(
                "↩️ Annulla", QMessageBox.RejectRole
            )

            dialog_chiudi.setDefaultButton(btn_salva_chiudi)
            # X della finestra e tasto Esc = Annulla (blocca la chiusura)
            dialog_chiudi.setEscapeButton(btn_annulla_chiudi)

            dialog_chiudi.exec()

            bottone_chiudi = dialog_chiudi.clickedButton()

            if bottone_chiudi == btn_salva_chiudi:
                # Il collega vuole salvare prima di chiudere
                self.salva_assegnazione()
                # Se dopo il salvataggio il flag è ancora True, ha annullato
                if self.assegnazione_non_salvata:
                    event.ignore()  # Annullato → blocca la chiusura
                    return

            elif bottone_chiudi == btn_annulla_chiudi:
                # Annulla → blocca la chiusura
                event.ignore()
                return

            # Se "Chiudi senza salvare" → procedi con la chiusura

        # Salva configurazione prima di chiudere
        self.config_app.salva_configurazione()

        event.accept()


def main():
    """Funzione principale per avviare l'applicazione GUI."""

    app = QApplication(sys.argv)

    # Imposta stile e icona dell'applicazione
    app.setApplicationName("PostiPerfetti")
    app.setApplicationVersion("2.0")

    # Installa il filtro globale per il cursore "manina" sui pulsanti.
    # Deve essere creato PRIMA della finestra, così cattura tutti i pulsanti
    # fin dalla loro creazione (inclusi quelli nei dialog dinamici).
    filtro_cursore = FiltroCursoreManina(app)
    app.installEventFilter(filtro_cursore)

    # Imposta l'icona dell'applicazione (visibile nella taskbar e nella barra del titolo)
    percorso_icona = os.path.join(get_base_path(), "modelli", "postiperfetti.ico")
    if os.path.exists(percorso_icona):
        app.setWindowIcon(QIcon(percorso_icona))

    # Crea e mostra finestra principale
    finestra = FinestraPostiPerfetti()
    finestra.show()

    # Avvia loop eventi
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
