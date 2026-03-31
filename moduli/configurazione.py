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
    Gestione configurazione e storico.

    Contiene la classe ConfigurazioneApp che gestisce:
        • Caricamento/salvataggio del file JSON di configurazione
        • Storico assegnazioni (aggiunta, eliminazione, ricostruzione layout)
        • Blacklist coppie da evitare per le rotazioni
        • Contatori trio e studenti vicino al FISSO

    USO:
        from moduli.configurazione import ConfigurazioneApp
        config = ConfigurazioneApp()
        config.carica_configurazione()
"""

import os
import json
from datetime import datetime
from typing import List, Dict

# Importa get_base_path per trovare la cartella dati/
from moduli.utilita import get_base_path


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
            "studenti_vicino_fisso_contatore": {},  # Traccia quante volte ogni studente è stato in col 1 (adiacente al FISSO)
            "tema": "scuro"                 # Tema interfaccia: "scuro" o "chiaro"
        }

    # =================================================================
    # CARICAMENTO / SALVATAGGIO — File JSON di configurazione
    # =================================================================

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
        """
        Salva configurazione su file JSON con scrittura ATOMICA.

        Il file viene prima scritto in un file temporaneo (.tmp) nella
        stessa cartella, poi rinominato con os.replace() che è un'operazione
        atomica sui filesystem moderni (Linux, Windows NTFS, macOS).

        Questo protegge da corruzione del JSON in caso di:
        - Crash del programma durante la scrittura
        - Spegnimento improvviso del PC
        - Errori di disco durante il salvataggio

        Senza questa protezione, un'interruzione a metà scrittura
        produrrebbe un file JSON troncato → storico perso.
        """
        try:
            self.config_data["classe_info"]["ultima_modifica"] = datetime.now().isoformat()

            # Scrive prima in un file temporaneo (.tmp) nella stessa cartella.
            # Stessa cartella = stesso filesystem → os.replace() sarà atomico.
            file_temp = self.file_config + ".tmp"
            with open(file_temp, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            # Rinomina atomicamente: sostituisce il file originale in un colpo solo.
            # Se il .tmp è integro, il file finale sarà integro.
            # Se il .tmp è corrotto (crash durante la scrittura), il file
            # originale resta intatto perché os.replace() non è mai partito.
            os.replace(file_temp, self.file_config)

            print(f"💾 Configurazione salvata in {self.file_config}")
            return True
        except Exception as e:
            print(f"❌ Errore salvataggio configurazione: {e}")
            # Pulizia: se il .tmp è rimasto orfano, rimuovilo
            file_temp = self.file_config + ".tmp"
            if os.path.exists(file_temp):
                try:
                    os.remove(file_temp)
                except OSError:
                    pass  # Non critico: verrà sovrascritto al prossimo salvataggio
            return False

    # =================================================================
    # STORICO ASSEGNAZIONI — Aggiunta con layout completo
    # =================================================================

    def aggiungi_assegnazione_storico(self, nome_assegnazione: str, coppie: List[tuple], trio=None, configurazione_aula=None, file_origine=None, report_completo=None, studente_fisso=None, gruppo_adiacente_fisso=None, nome_adiacente_fisso=None, genere_misto=False):
        """
        Aggiunge una nuova assegnazione allo storico con layout completo.

        Args:
            studente_fisso: Oggetto Student con posizione FISSO (o None)
            gruppo_adiacente_fisso: Tupla (s1, s2, info) della coppia adiacente al FISSO (o None).
                NOTA: questa coppia è stata rimossa da coppie_formate durante l'assegnazione,
                quindi va gestita separatamente sia per il salvataggio che per la blacklist.
            nome_adiacente_fisso: Nome "Cognome Nome" dello studente in col 1 (adiacente diretto).
                Fonte di verità per il contatore. Funziona sia con coppia che con trio adiacente.
        """

        # Crea struttura base assegnazione
        nuova_assegnazione = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "ora": datetime.now().strftime("%H:%M"),
            "nome": nome_assegnazione,
            "file_origine": file_origine if file_origine else "Non specificato"
        }

        # Salva configurazione aula se disponibile
        if configurazione_aula:
            # Calcola num_studenti corretto: coppie*2 + trio(3) + fisso(1)
            num_studenti = len(coppie) * 2 + (3 if trio else 0) + (1 if studente_fisso else 0)
            # Se c'è un FISSO con coppia adiacente, quella coppia è fuori da 'coppie'
            # quindi vanno aggiunti i 2 studenti della coppia adiacente
            if gruppo_adiacente_fisso:
                num_studenti += 2

            nuova_assegnazione["configurazione_aula"] = {
                "num_file": configurazione_aula.num_righe - 2,  # -2 per elementi fissi
                "posti_per_fila": self._calcola_posti_per_fila(configurazione_aula),
                "modalita_trio": self._determina_modalita_trio_salvata(trio, configurazione_aula),
                "num_studenti": num_studenti,
                "num_righe": configurazione_aula.num_righe,  # Salva dimensioni esatte
                "num_colonne": configurazione_aula.num_colonne,
                # Salva metadati FISSO per ricostruzione layout
                "ha_fisso": studente_fisso is not None,
                "larghezza_blocco_sx": getattr(configurazione_aula, 'larghezza_blocco_sx', 2),
                # Salva preferenza genere misto (per-classe, non globale).
                # Al ricaricamento della stessa classe, il valore viene
                # ripristinato da _controlla_classe_gia_elaborata().
                "genere_misto": genere_misto
            }

            # Estrae layout completo (coordinate di ogni studente)
            nuova_assegnazione["layout"] = self._estrai_layout_da_configurazione(
                configurazione_aula, coppie, trio, studente_fisso=studente_fisso,
                gruppo_adiacente_fisso=gruppo_adiacente_fisso,
                nome_adiacente_fisso=nome_adiacente_fisso
            )

            # Salva report completo se disponibile
            if report_completo:
                nuova_assegnazione["report_completo"] = report_completo

        # Aggiungi allo storico
        self.config_data["storico_assegnazioni"].append(nuova_assegnazione)

        # Aggiorna sistema penalità per rotazione (coppie + trio + FISSO)
        self._aggiorna_coppie_da_evitare(
            coppie, trio, studente_fisso=studente_fisso,
            gruppo_adiacente_fisso=gruppo_adiacente_fisso,
            nome_adiacente_fisso=nome_adiacente_fisso
        )

        self.salva_configurazione()

    # =================================================================
    # CALCOLO POSTI PER FILA — Dalla configurazione aula
    # =================================================================

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

    # =================================================================
    # MODALITÀ TRIO — Determina posizione trio (prima/ultima/centro)
    # =================================================================

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

    # =================================================================
    # ESTRAZIONE LAYOUT — Coordinate di ogni studente dalla griglia
    # =================================================================

    def _estrai_layout_da_configurazione(self, configurazione_aula, coppie, trio,
                                         studente_fisso=None, gruppo_adiacente_fisso=None,
                                         nome_adiacente_fisso=None):
        """
        Estrae il layout completo con coordinate di ogni studente.

        Args:
            configurazione_aula: Oggetto ConfigurazioneAula
            coppie: Lista di tuple (studente1, studente2, info)
            trio: Lista di 3 studenti (o None)
            studente_fisso: Studente con posizione FISSO (o None)
            gruppo_adiacente_fisso: Coppia adiacente al FISSO (s1, s2, info) o None

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

        # Mappa per coppia adiacente al FISSO (era stata rimossa da coppie_formate)
        if gruppo_adiacente_fisso:
            s1_adj = gruppo_adiacente_fisso[0]
            s2_adj = gruppo_adiacente_fisso[1]
            info_adj = gruppo_adiacente_fisso[2] if len(gruppo_adiacente_fisso) > 2 else {}
            nome1_adj = s1_adj.get_nome_completo()
            nome2_adj = s2_adj.get_nome_completo()
            mappa_coppie[nome1_adj] = {"tipo": "coppia", "compagno": nome2_adj, "info": info_adj}
            mappa_coppie[nome2_adj] = {"tipo": "coppia", "compagno": nome1_adj, "info": info_adj}

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

        # Mappa per studente FISSO
        mappa_fisso = {}
        if studente_fisso:
            nome_fisso = studente_fisso.get_nome_completo()
            mappa_fisso[nome_fisso] = {
                "tipo": "fisso",
                "adiacente": nome_adiacente_fisso  # Fonte di verità (funziona per coppia E trio)
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

                    # Aggiunge info fisso, trio o coppia (in ordine di priorità)
                    if nome_completo in mappa_fisso:
                        info_studente.update(mappa_fisso[nome_completo])
                    elif nome_completo in mappa_trio:
                        info_studente.update(mappa_trio[nome_completo])
                    elif nome_completo in mappa_coppie:
                        info_studente.update(mappa_coppie[nome_completo])
                        # Salva anche il punteggio della coppia
                        info_studente["punteggio"] = mappa_coppie[nome_completo]["info"].get("punteggio_totale", 0)

                    layout.append(info_studente)

        return layout

    # =================================================================
    # RICOSTRUZIONE LAYOUT — Da storico a griglia visiva
    # =================================================================

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
            from moduli.aula import ConfigurazioneAula, PostoAula
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
                # ALLINEAMENTO: Usa le stesse posizioni colonna dei banchi.
                # Usa larghezza_blocco_sx salvata (nuove assegnazioni) oppure
                # calcola dalla parità studenti (assegnazioni vecchie senza FISSO).
                larghezza_sx_salvata = config_aula_data.get('larghezza_blocco_sx')
                if larghezza_sx_salvata:
                    larghezza_blocco = larghezza_sx_salvata
                else:
                    ha_trio_storico = (config_aula_data.get('num_studenti', 0) % 2 == 1)
                    larghezza_blocco = 3 if ha_trio_storico else 2

                # Usa il metodo centralizzato di ConfigurazioneAula per calcolare le posizioni
                posizioni_arredi = config_ricostruita._calcola_posizioni_fila_normale(larghezza_blocco)
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
                # FALLBACK: Se mancano dimensioni esatte, usa metodo standard
                print(f"   ⚠️ Dimensioni esatte non disponibili, uso metodo standard")
                config_ricostruita.crea_layout_standard(
                    num_studenti=config_aula_data['num_studenti'],
                    num_file=config_aula_data['num_file'],
                    posti_per_fila=config_aula_data['posti_per_fila'],
                    posizione_trio=config_aula_data.get('modalita_trio'),
                    ha_fisso=config_aula_data.get('ha_fisso', False)  # propaga flag FISSO
                )

            # Popola la griglia con gli studenti nelle posizioni salvate
            for studente_info in layout_data:
                nome_studente = studente_info["studente"]
                riga = studente_info["riga"]
                colonna = studente_info["colonna"]

                # Il nome arriva dal JSON già nel formato "Cognome Nome" leggibile.
                # Lo salviamo così com'è in occupato_da (senza riconvertire in ID).
                id_univoco = nome_studente

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

    # =================================================================
    # BLACKLIST COPPIE — Aggiornamento per sistema rotazione
    # =================================================================

    def _aggiorna_coppie_da_evitare(self, nuove_coppie: List[tuple], trio=None,
                                    studente_fisso=None, gruppo_adiacente_fisso=None,
                                    nome_adiacente_fisso=None):
        """
        Aggiorna il conteggio delle coppie già utilizzate nella blacklist.
        Formato unico: {"tipo": "coppia", "studenti": [nome1, nome2], "volte_usata": N}

        CON FISSO: gestisce anche la coppia adiacente (rimossa da coppie_formate)
        e aggiorna il contatore studenti_vicino_fisso_contatore.

        Args:
            nome_adiacente_fisso: Nome "Cognome Nome" dello studente in col 1.
                Fonte di verità per il contatore, funziona sia per coppia che trio.
        """
        print(f"🔍 DEBUG: Elaboro {len(nuove_coppie)} coppie e trio={trio is not None}, fisso={studente_fisso is not None}")
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

        # === GESTIONE COPPIA ADIACENTE AL FISSO ===
        # La coppia adiacente è stata rimossa da coppie_formate durante l'assegnazione,
        # quindi va aggiunta qui come coppia normale nella blacklist.
        if gruppo_adiacente_fisso:
            s1_fisso, s2_fisso = gruppo_adiacente_fisso[0], gruppo_adiacente_fisso[1]
            chiave_adiacente = tuple(sorted([s1_fisso.get_nome_completo(), s2_fisso.get_nome_completo()]))
            print(f"📌 DEBUG: Elaboro coppia adiacente al FISSO: {chiave_adiacente[0]} + {chiave_adiacente[1]}")

            if chiave_adiacente in coppie_esistenti:
                coppie_esistenti[chiave_adiacente]["volte_usata"] += 1
                print(f"   ✅ Coppia adiacente FISSO aggiornata (ora {coppie_esistenti[chiave_adiacente]['volte_usata']} volte)")
            else:
                nuova_voce = {
                    "tipo": "coppia",
                    "studenti": [chiave_adiacente[0], chiave_adiacente[1]],
                    "volte_usata": 1
                }
                self.config_data["coppie_da_evitare"].append(nuova_voce)
                coppie_esistenti[chiave_adiacente] = nuova_voce
                print(f"   🆕 Nuova coppia adiacente FISSO aggiunta in blacklist")

        # === AGGIORNAMENTO CONTATORE VICINO FISSO ===
        # Traccia SOLO lo studente in col 1 (adiacente diretto), NON tutto il gruppo.
        # Usa nome_adiacente_fisso come fonte di verità (impostato da
        # _assegna_gruppo_adiacente_fisso nell'algoritmo). Funziona sia quando
        # il gruppo adiacente è una coppia sia quando è un trio.
        if studente_fisso and nome_adiacente_fisso:
            # Inizializza contatore se non esiste nel config
            if "studenti_vicino_fisso_contatore" not in self.config_data:
                self.config_data["studenti_vicino_fisso_contatore"] = {}

            contatore = self.config_data["studenti_vicino_fisso_contatore"]
            if nome_adiacente_fisso not in contatore:
                contatore[nome_adiacente_fisso] = 0
            contatore[nome_adiacente_fisso] += 1
            print(f"   📌 Contatore vicino FISSO: {nome_adiacente_fisso} → {contatore[nome_adiacente_fisso]} volte")

    # =================================================================
    # RICOSTRUZIONE BLACKLIST — Da storico dopo eliminazione
    # =================================================================

    def _ricostruisci_blacklist_da_storico(self):
        """
        Ricostruisce completamente blacklist e contatori da storico assegnazioni.
        UTILIZZO: Dopo eliminazione assegnazione per garantire coerenza.

        LOGICA:
        1. Azzera blacklist e contatori (trio + vicino_fisso)
        2. Ri-elabora ogni assegnazione rimasta nello storico
        3. Ricostruisce blacklist da zero usando logica esistente
        """
        print(f"🔄 RICOSTRUZIONE BLACKLIST: Inizio elaborazione Storico...")

        # STEP 1: Azzera completamente blacklist e TUTTI i contatori
        self.config_data["coppie_da_evitare"] = []
        self.config_data["studenti_trio_contatore"] = {}
        self.config_data["studenti_vicino_fisso_contatore"] = {}
        print(f"   ✅ Blacklist e contatori (trio + vicino_fisso) azzerati")

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

            # ============================================================
            # Estrae coppie, trio e fisso dall'assegnazione.
            # Il formato CORRENTE salva i dati nel campo "layout" (ogni
            # studente con tipo/compagno/coordinate). Il vecchio campo
            # "abbinamenti" è usato solo come fallback per compatibilità.
            # ============================================================
            coppie_da_elaborare = []
            trio_da_elaborare = None
            studente_fisso_fittizio = None
            gruppo_adiacente_fittizio = None

            layout = assegnazione.get("layout", [])

            if layout:
                # === Legge dal campo "layout" ===
                # Ricostruisce coppie uniche (ogni coppia ha 2 voci nel layout)
                coppie_processate = set()
                trio_nomi = []

                for studente_info in layout:
                    tipo = studente_info.get("tipo")
                    nome = studente_info.get("studente", "")

                    if tipo == "coppia":
                        compagno = studente_info.get("compagno", "")
                        if nome and compagno:
                            chiave = tuple(sorted([nome, compagno]))
                            if chiave not in coppie_processate:
                                coppie_processate.add(chiave)
                                s1 = type('Student', (), {'get_nome_completo': lambda self, n=chiave[0]: n})()
                                s2 = type('Student', (), {'get_nome_completo': lambda self, n=chiave[1]: n})()
                                coppie_da_elaborare.append((s1, s2, {}))

                    elif tipo == "trio":
                        trio_nomi.append(nome)

                    elif tipo == "fisso":
                        nome_adiacente = studente_info.get("adiacente", "")
                        if nome:
                            studente_fisso_fittizio = type('Student', (), {
                                'get_nome_completo': lambda self, n=nome: n
                            })()
                        if nome_adiacente:
                            s_adj = type('Student', (), {
                                'get_nome_completo': lambda self, n=nome_adiacente: n
                            })()
                            s_dummy = type('Student', (), {
                                'get_nome_completo': lambda self: "RICOSTRUZIONE_DUMMY"
                            })()
                            gruppo_adiacente_fittizio = (s_adj, s_dummy, {})
                            print(f"      📌 FISSO ricostruito: {nome}, adiacente: {nome_adiacente}")

                # Ricostruisce trio se trovati 3 studenti di tipo "trio"
                if len(trio_nomi) == 3:
                    trio_fittizio = []
                    for nome_trio in trio_nomi:
                        s = type('Student', (), {'get_nome_completo': lambda self, n=nome_trio: n})()
                        trio_fittizio.append(s)
                    trio_da_elaborare = trio_fittizio

            # STEP 4: Applica la logica esistente per aggiornare blacklist
            # NOTA: per la ricostruzione, la coppia adiacente al FISSO è GIÀ inclusa
            # nelle coppie normali (è stata salvata come tipo "coppia" in abbinamenti).
            # Qui passiamo gruppo_adiacente_fittizio SOLO per aggiornare il contatore
            # vicino_fisso, NON per raddoppiare la coppia nella blacklist.
            if coppie_da_elaborare or trio_da_elaborare:
                self._aggiorna_coppie_da_evitare(coppie_da_elaborare, trio_da_elaborare)
                print(f"      ✅ Elaborati: {len(coppie_da_elaborare)} coppie" +
                      (f" + 1 trio" if trio_da_elaborare else ""))

            # Aggiorna contatore vicino_fisso separatamente
            # (la coppia è già nella blacklist come coppia normale)
            if studente_fisso_fittizio and gruppo_adiacente_fittizio:
                nome_adiacente = gruppo_adiacente_fittizio[0].get_nome_completo()
                if "studenti_vicino_fisso_contatore" not in self.config_data:
                    self.config_data["studenti_vicino_fisso_contatore"] = {}
                contatore = self.config_data["studenti_vicino_fisso_contatore"]
                if nome_adiacente not in contatore:
                    contatore[nome_adiacente] = 0
                contatore[nome_adiacente] += 1
                print(f"      📌 Contatore vicino FISSO ricostruito: {nome_adiacente} → {contatore[nome_adiacente]}")

        # STEP 5: Statistiche finali
        num_coppie_blacklist = len(self.config_data["coppie_da_evitare"])
        num_studenti_trio = len(self.config_data["studenti_trio_contatore"])
        num_studenti_vicino = len(self.config_data.get("studenti_vicino_fisso_contatore", {}))

        print(f"   📊 RICOSTRUZIONE COMPLETATA:")
        print(f"      • Coppie in blacklist: {num_coppie_blacklist}")
        print(f"      • Studenti con contatore trio: {num_studenti_trio}")
        print(f"      • Studenti con contatore vicino FISSO: {num_studenti_vicino}")
