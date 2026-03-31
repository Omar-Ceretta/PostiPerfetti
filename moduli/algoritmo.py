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
    Algoritmo per l'assegnazione automatica dei posti.
    Combina vincoli sociali, preferenze di posizione e layout aula.
"""

from typing import List, Tuple, Optional
from moduli.studenti import Student
from moduli.aula import ConfigurazioneAula, PostoAula
from moduli.vincoli import MotoreVincoli, MotoreVincoliConfigurato


class AssegnatorePosti:
    """
    Coordina l'intero processo di assegnazione automatica dei posti.
    """

    def __init__(self):
        self.motore_vincoli = MotoreVincoliConfigurato()
        self.configurazione_aula = None
        self.studenti = []
        self.coppie_formate = []
        self.studenti_singoli = []  # Per gestire numeri dispari

        # === GESTIONE STUDENTE FISSO ===
        # Oggetto Student con nota_posizione="FISSO", o None se assente.
        # Viene impostato in STEP 0 di esegui_assegnazione_completa()
        # e usato da _seleziona_gruppo_per_fisso() per scegliere
        # il gruppo migliore da piazzare accanto a lui.
        self.studente_fisso = None
        # Coppia selezionata per stare accanto al FISSO (tuple o None)
        self.gruppo_adiacente_fisso = None
        # Nome dello studente effettivamente piazzato in col 1 (adiacente diretto)
        # Impostato in _assegna_gruppo_adiacente_fisso() DOPO l'assegnazione fisica.
        # Fonte di verità per il contatore studenti_vicino_fisso_contatore.
        self.nome_adiacente_fisso = None

        # Statistiche dell'assegnazione
        self.stats = {
            'vincoli_rispettati': 0,
            'vincoli_violati': 0,
            'coppie_ottimali': 0,
            'coppie_buone': 0,
            'coppie_accettabili': 0,
            'coppie_problematiche': 0,
            'coppie_critiche': 0
        }

        # Report diagnostico in caso di fallimento (None = nessun fallimento).
        # Viene popolato da _genera_report_fallimento_completo()
        # e letto dal WorkerThread per passarlo alla GUI tramite il segnale
        # error_occurred, così che il popup possa mostrare dettagli utili.
        self.report_fallimento = None

    def esegui_assegnazione_completa(self, studenti: List[Student], configurazione_aula: ConfigurazioneAula, modalita_trio: str = 'auto', studente_fisso: Optional[Student] = None) -> bool:
        """
        Esegue l'intero processo di assegnazione automatica.

        Args:
            studenti: Lista degli studenti da sistemare
            configurazione_aula: Layout dell'aula
            modalita_trio: Modalità posizionamento trio ('prima', 'ultima', 'centro')
            studente_fisso: Oggetto Student con nota_posizione="FISSO", o None.
                Se presente, verrà pre-assegnato al primo banco a sinistra
                in prima fila (col 0) e escluso dalla formazione coppie.

        Returns:
            bool: True se assegnazione completata con successo
        """
        print("🚀 INIZIO ASSEGNAZIONE AUTOMATICA")
        print("=" * 50)

        self.studenti = studenti
        self.configurazione_aula = configurazione_aula

        # Salva modalità trio per uso successivo
        self.modalita_trio = modalita_trio

        # ═══════════════════════════════════════════════════════════
        # STEP 0: Gestione studente con posizione FISSO
        # ═══════════════════════════════════════════════════════════
        # Se c'è uno studente FISSO:
        #   1. Lo pre-assegna al primo banco (prima fila, col 0)
        #   2. Lo rimuove dalla lista studenti
        #   3. Da qui in poi l'algoritmo lavora su N-1 studenti
        # Se NON c'è FISSO: prosegue normalmente (nessun impatto)
        if studente_fisso is not None:
            print(f"\n📌 STEP 0: Gestione studente FISSO...")
            if not self._gestisci_studente_fisso(studente_fisso):
                return False
        else:
            self.studente_fisso = None
            self.gruppo_adiacente_fisso = None
            print(f"\n📌 STEP 0: Nessuno studente FISSO — flusso standard")

        # STEP 1: Verifica compatibilità numero studenti/posti
        if not self._verifica_capienza():
            return False

        # STEP 2: Forma le coppie ottimali
        print("\n📝 STEP 2: Formazione coppie ottimali...")
        if not self._forma_coppie_ottimali():
            return False

        # STEP 3: Assegna posizioni in base alle preferenze
        print("\n📝 STEP 3: Assegnazione posizioni...")
        if not self._assegna_posizioni_intelligenti():
            return False

        # STEP 4: Genera statistiche finali
        print("\n📊 STEP 4: Calcolo statistiche...")
        self._calcola_statistiche_finali()

        # STEP 5: Pulizia banchi vuoti (rende layout più compatto)
        print("\n📊 STEP 5: Ottimizzazione layout...")
        self.configurazione_aula.rimuovi_banchi_vuoti()

        print("\n🎉 ASSEGNAZIONE COMPLETATA CON SUCCESSO!")
        return True

    def _verifica_capienza(self) -> bool:
        """
        Verifica che ci siano abbastanza posti per tutti gli studenti.
        """
        num_studenti = len(self.studenti)
        posti_disponibili = self.configurazione_aula.posti_disponibili

        print(f"👥 Studenti da sistemare: {num_studenti}")
        print(f"🪑 Posti disponibili: {posti_disponibili}")

        if num_studenti > posti_disponibili:
            print(f"❌ ERRORE: Non ci sono abbastanza posti!")
            print(f"   Servono {num_studenti - posti_disponibili} posti aggiuntivi")
            return False

        if num_studenti < posti_disponibili:
            print(f"ℹ️  INFO: Ci saranno {posti_disponibili - num_studenti} posti liberi")

        print("✅ Capienza verificata")
        return True

    def _forma_coppie_ottimali(self) -> bool:
        """
        Forma coppie ottimali con SISTEMA A CASCATA per massimizzare varietà rotazioni.
        4 tentativi progressivi con allentamento vincoli.
        """
        num_studenti = len(self.studenti)

        print(f"\n🔥 SISTEMA A CASCATA - PIPELINE FORMAZIONE COPPIE")
        print("=" * 60)
        print(f"📊 Studenti totali: {num_studenti}")
        print(f"🎯 PRIORITÀ: Formare NUOVE coppie (evitare blacklist)")

        # STEP 1: Determinazione logica trio
        self.gestisce_trio = (num_studenti % 2 == 1)

        if self.gestisce_trio:
            num_coppie = (num_studenti - 3) // 2
            print(f"🔢 Numero dispari: {num_coppie} coppie + 1 trio (3 studenti)")
        else:
            num_coppie = num_studenti // 2
            print(f"🔢 Numero pari: {num_coppie} coppie")

        # Inizializza trio_identificato a None per numeri pari
        self.trio_identificato = None

        # STEP 2: Sistema a cascata con 4 tentativi progressivi
        for tentativo in range(1, 5):  # Tentativo 1, 2, 3, 4
            print(f"\n{'='*20} TENTATIVO {tentativo} {'='*20}")

            # Configura motore vincoli per questo tentativo
            self.motore_vincoli.configura_per_tentativo(tentativo, self._get_info_blacklist())

            # Applica penalità blacklist sempre
            if hasattr(self, 'config_app'):
                self._applica_penalita_blacklist_tentativo(tentativo)

            # Prova formazione coppie con configurazione attuale
            risultato_tentativo = self._prova_formazione_coppie_completa(num_coppie, tentativo)

            if risultato_tentativo:
                print(f"✅ SUCCESSO TENTATIVO {tentativo}!")
                return True
            else:
                print(f"❌ TENTATIVO {tentativo} FALLITO")
                if tentativo < 4:
                    self._mostra_motivi_fallimento_tentativo(tentativo)
                    print(f"🔄 Passando al tentativo {tentativo + 1}...")

        # STEP 3: Se tutti i 4 tentativi falliscono
        print(f"\n🚨 TUTTI I TENTATIVI FALLITI - GENERAZIONE REPORT DIAGNOSTICO")
        self._genera_report_fallimento_completo()
        return False

    def _prova_formazione_coppie_completa(self, num_coppie_target: int, tentativo: int) -> bool:
        """
        Prova la formazione completa di coppie+trio per un tentativo specifico.

        Returns:
            bool: True se riesce a formare tutte le coppie necessarie
        """
        print(f"🔧 Tentativo formazione: {num_coppie_target} coppie", end="")
        if self.gestisce_trio:
            print(" + 1 trio")
        else:
            print("")

        # FASE 1: Identificazione trio se necessario
        studenti_per_coppie = self.studenti.copy()

        if self.gestisce_trio:
            print(f"🔍 FASE 1: Identificazione trio ottimale...")
            self.trio_identificato = self._identifica_trio_ottimale_configurato(self.studenti, tentativo)

            if not self.trio_identificato:
                print(f"   ❌ Impossibile identificare trio valido nel tentativo {tentativo}")
                return False

            print(f"   ✅ Trio formato: {', '.join([s.get_nome_completo() for s in self.trio_identificato])}")

            print(f"   🔍 DEBUG: Sto per controllare trio qualità, tentativo = {tentativo}")

            # CONTROLLO QUALITÀ TRIO: Rifiuta tentativi con coppie virtuali ripetute nei primi 3 tentativi
            if tentativo <= 3:
                coppie_virtuali_ripetute = self._conta_coppie_virtuali_ripetute_trio(self.trio_identificato)

                if coppie_virtuali_ripetute > 0:
                    print(f"   ❌ RIFIUTO TENTATIVO {tentativo}: trio con {coppie_virtuali_ripetute} coppie virtuali ripetute")
                    return False
                else:
                    print(f"   ✅ Trio qualità verificata: 0 coppie virtuali ripetute")

            # Rimuovi trio dai disponibili per coppie
            for studente_trio in self.trio_identificato:
                studenti_per_coppie.remove(studente_trio)

            print(f"   📊 Studenti rimanenti per coppie: {len(studenti_per_coppie)}")

        # FASE 2: Formazione coppie con studenti rimanenti
        print(f"🔧 FASE 2: Formazione {num_coppie_target} coppie...")

        # Comunica il tentativo corrente al motore vincoli per equità
        if hasattr(self.motore_vincoli, 'tentativo_corrente'):
            self.motore_vincoli.tentativo_corrente = tentativo
            print(f"   📊 Comunicato tentativo {tentativo} al motore vincoli")

        coppie_candidate = self.motore_vincoli.trova_migliori_coppie(
            studenti_per_coppie,
            num_coppie_target
        )

        print(f"   📥 Motore vincoli ha restituito {len(coppie_candidate)} coppie")

        # CONTROLLO QUALITÀ: Rifiuta tentativi con troppe coppie blacklistate nei primi 3 tentativi
        if tentativo <= 3:
            coppie_blacklistate = 0
            for studente1, studente2, info in coppie_candidate:
                if info.get('valutazione') == 'BLACKLISTATA':
                    coppie_blacklistate += 1

            if coppie_blacklistate > 0:
                print(f"   ❌ RIFIUTO TENTATIVO {tentativo}: {coppie_blacklistate} coppie blacklistate")
                return False
            else:
                print(f"   ✅ Qualità verificata: 0 coppie blacklistate")

        # VERIFICA: Abbiamo tutte le coppie necessarie?
        if len(coppie_candidate) < num_coppie_target:
            print(f"   ❌ Insufficienti coppie valide: {len(coppie_candidate)}/{num_coppie_target}")
            return False

        # FASE 3: Verifica conteggio finale
        studenti_in_coppie = len(coppie_candidate) * 2
        studenti_in_trio = 3 if self.gestisce_trio and self.trio_identificato else 0
        studenti_processati = studenti_in_coppie + studenti_in_trio

        if studenti_processati != len(self.studenti):
            print(f"   ❌ Errore conteggio: {studenti_processati}/{len(self.studenti)} studenti")
            return False

        # SUCCESSO: Salva risultati
        self.coppie_formate = coppie_candidate
        self.studenti_singoli = []  # Dovrebbe essere vuoto se tutto corretto

        print(f"   ✅ Formazione completa riuscita!")
        print(f"   📊 Coppie: {len(self.coppie_formate)}, Trio: {1 if self.trio_identificato else 0}")

        return True

    def _conta_coppie_virtuali_ripetute_trio(self, trio):
        if not hasattr(self, 'config_app'):
            return 0

        studente1, studente2, studente3 = trio
        coppie_virtuali_attuali = [
            {studente1.get_nome_completo(), studente2.get_nome_completo()},
            {studente2.get_nome_completo(), studente3.get_nome_completo()}
        ]

        print(f"   🔍 TRIO ATTUALE: {[s.get_nome_completo() for s in trio]}")
        print(f"   🔗 COPPIE VIRTUALI ATTUALI: {[list(c) for c in coppie_virtuali_attuali]}")

        coppie_da_evitare = self.config_app.config_data.get("coppie_da_evitare", [])

        # Estrai TUTTE le coppie dalla blacklist e stampa tutto
        tutte_coppie_usate = []
        print(f"   📋 ANALISI BLACKLIST ({len(coppie_da_evitare)} elementi):")

        for idx, item in enumerate(coppie_da_evitare):
            if item.get("tipo") == "trio":
                studenti_trio = item.get("studenti", [])
                if len(studenti_trio) == 3:
                    coppia1 = {studenti_trio[0], studenti_trio[1]}
                    coppia2 = {studenti_trio[1], studenti_trio[2]}
                    tutte_coppie_usate.append(coppia1)
                    tutte_coppie_usate.append(coppia2)
                    print(f"      TRIO {idx}: {studenti_trio} → coppie: {list(coppia1)}, {list(coppia2)}")
            elif item.get("tipo") == "coppia":
                studenti = item.get("studenti", [])
                if len(studenti) == 2:
                    coppia = {studenti[0], studenti[1]}
                    tutte_coppie_usate.append(coppia)
                    print(f"      COPPIA {idx}: {list(coppia)}")

        # Ora confronta
        coppie_ripetute = 0
        for i, coppia_virtuale in enumerate(coppie_virtuali_attuali, 1):
            print(f"   🔍 CONTROLLO COPPIA VIRTUALE {i}: {list(coppia_virtuale)}")
            if coppia_virtuale in tutte_coppie_usate:
                print(f"      🚨 TROVATA nella blacklist!")
                coppie_ripetute += 1
            else:
                print(f"      ✅ NON trovata nella blacklist")

        print(f"   📊 RISULTATO FINALE: {coppie_ripetute} ripetizioni")
        return coppie_ripetute

    def _identifica_trio_ottimale_configurato(self, studenti, tentativo):
        """
        Identifica trio ottimale usando la configurazione vincoli del tentativo corrente.
        """
        import itertools

        migliore_trio = None
        miglior_punteggio = float('-inf')
        trii_testati = 0

        print(f"   🔍 Analizzando possibili trii per tentativo {tentativo}...")

        for trio_candidato in itertools.combinations(studenti, 3):
            trii_testati += 1

            # Verifica vincoli assoluti (mai rilassabili)
            if not self._trio_rispetta_vincoli_assoluti(trio_candidato):
                continue

            # Valuta trio con configurazione tentativo corrente
            punteggio_trio = self._valuta_trio_configurato(trio_candidato)

            # Verifica che i rimanenti possano formare coppie
            studenti_rimanenti = [s for s in studenti if s not in trio_candidato]
            coppie_possibili = self.motore_vincoli.trova_migliori_coppie(
                studenti_rimanenti,
                len(studenti_rimanenti) // 2
            )

            if len(coppie_possibili) < len(studenti_rimanenti) // 2:
                continue  # Trio impedisce formazione coppie necessarie

            # Applica penalità blacklist se necessario
            if hasattr(self, 'modalita_rotazione') and self.modalita_rotazione:
                punteggio_finale = self._applica_penalita_trio_storico_configurato(
                    trio_candidato, punteggio_trio, tentativo
                )
            else:
                punteggio_finale = punteggio_trio

            if punteggio_finale > miglior_punteggio:
                miglior_punteggio = punteggio_finale
                migliore_trio = trio_candidato

        print(f"   📊 Trii testati: {trii_testati}")

        if migliore_trio:
            print(f"   🎯 Trio ottimale trovato (punteggio: {miglior_punteggio})")
            return list(migliore_trio)
        else:
            print(f"   ❌ Nessun trio valido per tentativo {tentativo}")
            return None

    def _valuta_trio_configurato(self, trio):
        """
        Valuta trio usando la configurazione vincoli corrente + penalizza studenti già usati.
        """
        punteggio_totale = 0
        studente1, studente2, studente3 = trio

        # Valuta SOLO coppie fisicamente adiacenti
        coppie_adiacenti = [
            (studente1, studente2),  # Posti 1-2
            (studente2, studente3)   # Posti 2-3
        ]

        for s1, s2 in coppie_adiacenti:
            risultato = self.motore_vincoli.calcola_punteggio_coppia(s1, s2)
            punteggio_totale += risultato['punteggio_totale']

        # Applica penalità per studenti già usati nel trio
        if hasattr(self, 'config_app'):
            punteggio_totale -= self._calcola_penalita_trio_ripetuti(trio)

        #  Controlla se le coppie virtuali del trio sono già in blacklist come coppie normali
        if hasattr(self, 'config_app'):
            punteggio_totale -= self._calcola_penalita_coppie_virtuali_gia_usate(trio)

        return punteggio_totale

    def _calcola_penalita_trio_ripetuti(self, trio):
        """
        Calcola penalità per studenti che sono già stati troppo spesso nel trio.

        Args:
            trio: Lista di 3 studenti

        Returns:
            int: Penalità totale da sottrarre al punteggio
        """
        penalita_totale = 0
        contatori = self.config_app.config_data.get("studenti_trio_contatore", {})

        print(f"   🎯 Controllo penalità trio ripetizioni:")

        for studente in trio:
            nome_studente = studente.get_nome_completo()
            volte_nel_trio = contatori.get(nome_studente, 0)

            # Penalità progressiva: 0 volte = no penalità, 1+ volte = penalità crescente
            if volte_nel_trio > 0:
                penalita_studente = volte_nel_trio * 500  # Penalità aumentata per trio ripetuti
                penalita_totale += penalita_studente
                print(f"      ⚠️ {nome_studente}: {volte_nel_trio} volte precedenti → penalità -{penalita_studente}")
            else:
                print(f"      ✅ {nome_studente}: mai nel trio → nessuna penalità")

        if penalita_totale > 0:
            print(f"   📊 Penalità totale trio: -{penalita_totale}")

        return penalita_totale

    def _calcola_penalita_coppie_virtuali_gia_usate(self, trio):
        """
        Calcola penalità se le coppie virtuali del trio sono già state usate come coppie normali.

        Args:
            trio: Lista di 3 studenti

        Returns:
            int: Penalità totale da sottrarre
        """
        penalita_totale = 0
        studente1, studente2, studente3 = trio

        # Le 2 coppie virtuali adiacenti nel trio
        coppie_virtuali = [
            (studente1.get_nome_completo(), studente2.get_nome_completo()),
            (studente2.get_nome_completo(), studente3.get_nome_completo())
        ]

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])

        for nome1, nome2 in coppie_virtuali:
            chiave_cercata = tuple(sorted([nome1, nome2]))

            # Cerca nella blacklist (formato unico)
            for item in coppie_usate:
                studenti = item.get("studenti", [])
                if len(studenti) == 2:
                    chiave_item = tuple(sorted(studenti))
                else:
                    continue

                if chiave_item == chiave_cercata:
                    volte_usata = item.get("volte_usata", 1)
                    penalita = 300 * volte_usata  # Penalità per coppia virtuale già usata come normale
                    penalita_totale += penalita
                    print(f"   ⚠️ Coppia virtuale già usata come normale: {nome1} + {nome2} (penalità: -{penalita})")
                    break

        return penalita_totale

    def _applica_penalita_blacklist_tentativo(self, tentativo):
        """
        Configura le penalità blacklist in base al tentativo corrente.
        """
        if not hasattr(self, 'config_app'):
            return

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            print("   📝 Nessuna blacklist presente")
            return

        print(f"   📋 Configurazione penalità blacklist per tentativo {tentativo}")

        # Salva metodo originale se non già salvato
        if not hasattr(self.motore_vincoli, '_calcola_punteggio_coppia_originale'):
            self.motore_vincoli._calcola_punteggio_coppia_originale = self.motore_vincoli.calcola_punteggio_coppia

        def calcola_con_penalita_blacklist_configurata(studente1: Student, studente2: Student) -> dict:
            # Calcola punteggio base con configurazione corrente
            risultato = self.motore_vincoli._calcola_punteggio_coppia_originale(studente1, studente2)

            # Se già vietata da vincoli assoluti, restituisci subito
            if risultato['valutazione'] == 'VIETATA':
                return risultato

            # Determina penalità blacklist per tentativo
            penalita_blacklist = self._calcola_penalita_blacklist_per_tentativo(
                studente1, studente2, tentativo, coppie_usate
            )

            if penalita_blacklist > 0:
                if self.motore_vincoli.blacklist_come_vincolo_assoluto and tentativo <= 3:
                    # Tentativi 1-3: Blacklist quasi-assoluta
                    risultato['punteggio_totale'] = -999999 + tentativo  # Leggera preferenza per tentativi alti
                    risultato['valutazione'] = 'BLACKLISTATA'
                    risultato['note'].append(f"COPPIA BLACKLISTATA (tentativo {tentativo})")
                else:
                    # Tentativo 4: Blacklist come penalità soft
                    risultato['punteggio_totale'] -= penalita_blacklist
                    risultato['note'].append(f"Penalità blacklist: -{penalita_blacklist}")

                    # Aggiorna valutazione se necessario
                    if risultato['punteggio_totale'] < -500:
                        risultato['valutazione'] = 'BLACKLISTATA_SOFT'

            return risultato

        # Sostituisce metodo temporaneamente
        self.motore_vincoli.calcola_punteggio_coppia = calcola_con_penalita_blacklist_configurata

    def _calcola_penalita_blacklist_per_tentativo(self, studente1, studente2, tentativo, coppie_usate):
        """
        Calcola la penalità blacklist appropriata per il tentativo corrente.
        """
        # Cerca coppia nella blacklist
        cognomi_attuali = {studente1.get_nome_completo(), studente2.get_nome_completo()}

        for coppia_usata in coppie_usate:
            # Estrae nomi dalla coppia in blacklist (formato unico)
            studenti = coppia_usata.get("studenti", [])
            if len(studenti) != 2:
                continue
            cognomi_blacklist = {studenti[0], studenti[1]}

            if cognomi_blacklist == cognomi_attuali:
                volte_usata = coppia_usata.get("volte_usata", 1)

                # Penalità progressive per tentativo
                if tentativo <= 3:
                    return 999999  # Quasi-assoluta per tentativi 1-3
                else:
                    return 200 * volte_usata  # Penalità soft per tentativo 4

        return 0  # Coppia non in blacklist

    def _applica_penalita_trio_storico_configurato(self, trio_candidato, punteggio_base, tentativo):
        """
        Le penalità trio sono gestite tramite le coppie virtuali nella blacklist normale.
        Questo metodo si limita a verificare che le coppie virtuali non siano già in blacklist.
        """
        if not hasattr(self, 'config_app'):
            return punteggio_base

        return punteggio_base

    def _mostra_motivi_fallimento_tentativo(self, tentativo):
        """
        Mostra all'utente i motivi specifici del fallimento del tentativo.
        """
        print(f"📋 Analisi fallimento tentativo {tentativo}:")

        if tentativo == 1:
            print("   • Impossibile formare nuove coppie rispettando tutti i vincoli")
            print("   • Possibili cause: troppi vincoli incompatibilità/affinità o blacklist estesa")

        elif tentativo == 2:
            print("   • Fallimento anche rilassando vincoli deboli (incomp 1, affinità 1)")
            print("   • Restano attivi: incomp 2-3, affinità 2-3, posizione, genere misto")

        elif tentativo == 3:
            print("   • Fallimento anche rilassando vincoli medi")
            print("   • Restano attivi solo: incomp 3, posizione PRIMA, affinità 3, genere misto")

        # Mostra diagnostica vincoli se disponibile
        self._mostra_diagnostica_vincoli_attivi()

    def _mostra_diagnostica_vincoli_attivi(self):
        """
        Mostra diagnostica dei vincoli ancora attivi nel tentativo corrente.
        """
        print("   🔍 Vincoli ancora attivi:")

        # Conta vincoli assoluti attivi
        incomp_3_count = 0
        for studente in self.studenti:
            # Le chiavi del dizionario ora sono "Cognome Nome" (nome completo)
            for nome_completo, livello in studente.incompatibilita.items():
                if livello == 3:
                    incomp_3_count += 1

        prima_fila_count = len([s for s in self.studenti if s.nota_posizione == 'PRIMA'])

        print(f"   • Incompatibilità assolute (livello 3): {incomp_3_count}")
        print(f"   • Richieste prima fila: {prima_fila_count}")

        if hasattr(self.motore_vincoli, 'genere_misto_obbligatorio') and self.motore_vincoli.genere_misto_obbligatorio:
            maschi = len([s for s in self.studenti if s.sesso == 'M'])
            femmine = len([s for s in self.studenti if s.sesso == 'F'])
            print(f"   • Genere misto obbligatorio: {maschi}M + {femmine}F")

    def _genera_report_fallimento_completo(self):
        """
        Genera report diagnostico completo quando tutti i tentativi falliscono.
        1) Stampa su terminale (per debug)
        2) Costruisce self.report_fallimento (dizionario strutturato per la GUI)
        """
        print("\n" + "="*60)
        print("🚨 REPORT DIAGNOSTICO - ASSEGNAZIONE IMPOSSIBILE")
        print("="*60)

        # SEZIONE 1: Analisi vincoli assoluti
        print("\n📋 ANALISI VINCOLI ASSOLUTI:")
        self._analizza_vincoli_assoluti_dettagliato()

        # SEZIONE 2: Analisi blacklist
        print("\n📋 ANALISI BLACKLIST:")
        self._analizza_blacklist_dettagliato()

        # SEZIONE 3: Suggerimenti risoluzione
        print("\n💡 SUGGERIMENTI PER RISOLVERE:")
        self._genera_suggerimenti_risoluzione()

        # SEZIONE 4: Proposta coppie riutilizzabili (se in modalità rotazione)
        if hasattr(self, 'modalita_rotazione') and self.modalita_rotazione:
            print("\n🔄 COPPIE RIUTILIZZABILI DISPONIBILI:")
            self._proponi_coppie_riutilizzabili()

        print("="*60)

        # === COSTRUZIONE REPORT STRUTTURATO PER LA GUI ===
        # Questo dizionario viene letto dal WorkerThread (postiperfetti.py)
        # per mostrare un popup dettagliato all'utente, anziché il generico
        # "vincoli irrisolvibili". Il WorkerThread lo passa tramite il
        # segnale error_occurred a _elaborazione_fallita().
        self.report_fallimento = self._costruisci_report_diagnostico()

    def _costruisci_report_diagnostico(self) -> dict:
        """
        Costruisce un dizionario strutturato con tutte le informazioni
        diagnostiche sul fallimento dell'assegnazione.

        Viene chiamato da _genera_report_fallimento_completo() e salvato
        in self.report_fallimento. Il WorkerThread lo legge e lo passa
        alla GUI tramite il segnale error_occurred(str, object).

        Returns:
            dict con chiavi:
                - incompatibilita_assolute: lista di stringhe "StudA ↔ StudB"
                  (deduplicate: "A↔B" e "B↔A" contano come una sola)
                - studenti_prima_fila: lista di nomi completi
                - genere_misto: dict con info su sbilanciamento (o None)
                - blacklist: dict con statistiche blacklist
                - suggerimenti: lista di stringhe con consigli pratici
        """
        report = {}

        # === 1. INCOMPATIBILITÀ ASSOLUTE (livello 3) ===
        # Deduplica: "A ↔ B" e "B ↔ A" sono la stessa cosa
        coppie_viste = set()
        incomp_assolute = []
        for studente in self.studenti:
            for nome_completo_target, livello in studente.incompatibilita.items():
                if livello == 3:
                    # Crea chiave ordinata per deduplicare
                    chiave = tuple(sorted([studente.get_nome_completo(), nome_completo_target]))
                    if chiave not in coppie_viste:
                        coppie_viste.add(chiave)
                        incomp_assolute.append(f"{chiave[0]}  ↔  {chiave[1]}")
        report["incompatibilita_assolute"] = incomp_assolute

        # === 2. STUDENTI CON POSIZIONE PRIMA FILA ===
        studenti_prima = [
            s.get_nome_completo() for s in self.studenti
            if s.nota_posizione == 'PRIMA'
        ]
        report["studenti_prima_fila"] = studenti_prima

        # === 3. GENERE MISTO ===
        # Segnala solo se il flag è attivo E c'è sbilanciamento
        if (hasattr(self.motore_vincoli, 'genere_misto_obbligatorio')
                and self.motore_vincoli.genere_misto_obbligatorio):
            maschi = len([s for s in self.studenti if s.sesso == 'M'])
            femmine = len([s for s in self.studenti if s.sesso == 'F'])
            report["genere_misto"] = {
                "maschi": maschi,
                "femmine": femmine,
                "sbilanciamento": abs(maschi - femmine) > 1
            }
        else:
            report["genere_misto"] = None

        # === 4. BLACKLIST (storico rotazioni) — solo classe corrente ===
        info_bl = {"coppie": 0, "trii": 0, "piu_usate": []}
        if hasattr(self, 'config_app'):
            # Usa la blacklist filtrata per la classe corrente,
            # così il report non mostra coppie di altre classi.
            coppie_classe = self._get_blacklist_classe_corrente()
            coppie_normali = [c for c in coppie_classe if c.get("tipo") != "trio"]
            trii_usati = [c for c in coppie_classe if c.get("tipo") == "trio"]
            info_bl["coppie"] = len(coppie_normali)
            info_bl["trii"] = len(trii_usati)
            # Le 5 coppie più usate (della classe corrente)
            if coppie_normali:
                ordinate = sorted(coppie_normali,
                                  key=lambda x: x.get("volte_usata", 0),
                                  reverse=True)
                for coppia in ordinate[:5]:
                    nomi = coppia.get("studenti", [])
                    if len(nomi) >= 2:
                        info_bl["piu_usate"].append(
                            f"{nomi[0]} + {nomi[1]} ({coppia.get('volte_usata', 0)}x)"
                        )
        report["blacklist"] = info_bl

        # === 5. SUGGERIMENTI PRATICI ===
        suggerimenti = []

        # Suggerimento basato sul numero di incompatibilità assolute
        if len(incomp_assolute) > 3:
            suggerimenti.append(
                "Ci sono molte incompatibilità ASSOLUTE (livello 3). "
                "Prova a convertirne alcune da livello 3 a livello 2 "
                "(forte ma non assoluto) nell'Editor."
            )
        elif len(incomp_assolute) > 0:
            suggerimenti.append(
                "Verifica se tutte le incompatibilità di livello 3 "
                "sono davvero necessarie, oppure se alcune possono "
                "essere ridotte a livello 2."
            )

        # Suggerimento per prima fila
        if len(studenti_prima) > 2:
            suggerimenti.append(
                f"Ci sono {len(studenti_prima)} studenti che richiedono "
                f"la PRIMA fila: potrebbe non esserci abbastanza spazio. "
                f"Valuta se alcuni possono passare a NORMALE."
            )

        # Suggerimento per genere misto
        if report["genere_misto"] and report["genere_misto"]["sbilanciamento"]:
            m = report["genere_misto"]["maschi"]
            f_count = report["genere_misto"]["femmine"]
            suggerimenti.append(
                f"Il flag 'Genere misto' è attivo ma c'è sbilanciamento "
                f"({m} maschi, {f_count} femmine). Prova a disattivarlo "
                f"se l'assegnazione continua a fallire."
            )

        # Suggerimento per blacklist piena (della classe corrente)
        if info_bl["coppie"] > 10:
            suggerimenti.append(
                f"La blacklist per questa classe contiene {info_bl['coppie']} coppie già usate. "
                f"Se la classe è piccola, potrebbe non essere possibile "
                f"formare abbinamenti del tutto nuovi. Prova a eliminare "
                f"le assegnazioni più vecchie dallo Storico."
            )

        # Suggerimento generico sempre presente
        suggerimenti.append(
            "In generale: meno vincoli assoluti = più possibilità "
            "per l'algoritmo di trovare una soluzione."
        )

        report["suggerimenti"] = suggerimenti

        return report

    def _analizza_vincoli_assoluti_dettagliato(self):
        """Analisi dettagliata dei vincoli assoluti che impediscono l'assegnazione"""
        # Incompatibilità livello 3
        incomp_assolute = []
        for studente in self.studenti:
            # Le chiavi del dizionario ora sono "Cognome Nome" (nome completo)
            for nome_completo_target, livello in studente.incompatibilita.items():
                if livello == 3:
                    incomp_assolute.append(f"{studente.get_nome_completo()} ↔ {nome_completo_target}")

        if incomp_assolute:
            print(f"   • Incompatibilità ASSOLUTE trovate: {len(incomp_assolute)}")
            for incomp in incomp_assolute[:5]:  # Mostra prime 5
                print(f"     - {incomp}")
            if len(incomp_assolute) > 5:
                print(f"     ... e altre {len(incomp_assolute) - 5}")

        # Posizione PRIMA vs capienza
        studenti_prima = [s for s in self.studenti if s.nota_posizione == 'PRIMA']
        if studenti_prima:
            print(f"   • Studenti che richiedono PRIMA fila: {len(studenti_prima)}")
            for s in studenti_prima:
                print(f"     - {s.get_nome_completo()}")
            # NOTA: la capienza della prima fila viene verificata implicitamente
            # dal sistema vincoli durante la formazione delle coppie.

        # Genere misto obbligatorio
        if hasattr(self.motore_vincoli, 'genere_misto_obbligatorio') and self.motore_vincoli.genere_misto_obbligatorio:
            maschi = [s for s in self.studenti if s.sesso == 'M']
            femmine = [s for s in self.studenti if s.sesso == 'F']
            print(f"   • Genere misto obbligatorio: {len(maschi)} maschi, {len(femmine)} femmine")
            if abs(len(maschi) - len(femmine)) > 1:
                print(f"     ⚠️ Sbilanciamento: alcune coppie saranno necessariamente stesso genere")

    def _get_blacklist_classe_corrente(self):
        """
        Filtra la blacklist globale (coppie_da_evitare) restituendo SOLO
        le coppie in cui ENTRAMBI gli studenti appartengono alla classe
        attualmente in elaborazione (self.studenti).

        Questo evita di mostrare nel report diagnostico coppie di altre classi.

        Returns:
            list: Sotto-lista di coppie_da_evitare filtrata per la classe corrente.
                  Lista vuota se config_app o studenti non sono disponibili.
        """
        if not hasattr(self, 'config_app') or not self.studenti:
            return []

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            return []

        # Set dei nomi completi della classe corrente per lookup O(1)
        nomi_classe = {s.get_nome_completo() for s in self.studenti}

        # Filtra: mantieni solo le coppie dove ENTRAMBI gli studenti
        # sono nella classe corrente
        blacklist_filtrata = []
        for coppia in coppie_usate:
            studenti = coppia.get("studenti", [])
            if len(studenti) == 2 and studenti[0] in nomi_classe and studenti[1] in nomi_classe:
                blacklist_filtrata.append(coppia)

        return blacklist_filtrata

    def _analizza_blacklist_dettagliato(self):
        """Analisi dettagliata della blacklist (solo classe corrente)."""
        if not hasattr(self, 'config_app'):
            print("   • Nessuna configurazione blacklist disponibile")
            return

        # Usa la blacklist filtrata per la classe corrente
        coppie_classe = self._get_blacklist_classe_corrente()
        if not coppie_classe:
            print("   • Blacklist vuota per questa classe - nessuna coppia usata in precedenza")
            return

        coppie_normali = [item for item in coppie_classe if item.get("tipo") != "trio"]
        trii_usati = [item for item in coppie_classe if item.get("tipo") == "trio"]

        print(f"   • Coppie in blacklist (classe corrente): {len(coppie_normali)}")
        print(f"   • Trii in blacklist (classe corrente): {len(trii_usati)}")

        # Mostra coppie più utilizzate
        if coppie_normali:
            coppie_ordinate = sorted(coppie_normali, key=lambda x: x.get("volte_usata", 0), reverse=True)
            print("   • Coppie più riutilizzate:")
            for coppia in coppie_ordinate[:3]:
                studenti = coppia.get("studenti", [])
                nomi = f"{studenti[0]} + {studenti[1]}" if len(studenti) >= 2 else "???"
                volte = coppia.get("volte_usata", 0)
                print(f"     - {nomi} (usata {volte} volte)")

    def _genera_suggerimenti_risoluzione(self):
        """Genera suggerimenti pratici per risolvere i problemi"""
        print("   1. 📝 MODIFICA FILE STUDENTI:")
        print("      • Riduci incompatibilità livello 3 (solo per casi estremi)")
        print("      • Converti alcune incompatibilità 3→2 o 2→1")
        print("      • Riduci richieste posizione 'PRIMA' se troppo numerose")

        print("   2. ⚙️ MODIFICA CONFIGURAZIONI:")
        print("      • Disattiva 'genere misto obbligatorio' se troppo restrittivo")
        print("      • Aumenta numero file o posti per fila se spazio insufficiente")

        print("   3. 🔄 MODALITÀ ROTAZIONE:")
        print("      • Considera di riutilizzare alcune coppie precedenti")
        print("      • Elimina assegnazioni vecchie dalla cronologia se non più rilevanti")

    def _proponi_coppie_riutilizzabili(self):
        """Propone coppie dalla blacklist (classe corrente) che potrebbero essere riutilizzate."""
        if not hasattr(self, 'config_app'):
            return

        # Usa la blacklist filtrata per la classe corrente
        coppie_classe = self._get_blacklist_classe_corrente()
        if not coppie_classe:
            print("   • Nessuna coppia disponibile per riutilizzo in questa classe")
            return

        # Filtra solo coppie normali (no trii)
        coppie_normali = [item for item in coppie_classe if item.get("tipo") != "trio"]

        # Ordina per numero utilizzi (meno utilizzate prima)
        coppie_ordinate = sorted(coppie_normali, key=lambda x: x.get("volte_usata", 0))

        print("   💡 Coppie riutilizzabili (meno utilizzate per prime):")
        for i, coppia in enumerate(coppie_ordinate[:8]):  # Mostra prime 8
            studenti = coppia.get("studenti", [])
            nomi = f"{studenti[0]} + {studenti[1]}" if len(studenti) >= 2 else "???"
            volte = coppia.get("volte_usata", 0)
            print(f"      {i+1}. {nomi} (usata {volte} volte)")

        if len(coppie_ordinate) > 8:
            print(f"      ... e altre {len(coppie_ordinate) - 8} coppie disponibili")

    def _get_info_blacklist(self):
        """Restituisce informazioni sulla blacklist per diagnostica"""
        if not hasattr(self, 'config_app'):
            return {}

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        return {
            'totale_coppie': len([item for item in coppie_usate if item.get("tipo") != "trio"]),
            'totale_trii': len([item for item in coppie_usate if item.get("tipo") == "trio"]),
            'coppie_usate': coppie_usate
        }

    def _assegna_posizioni_intelligenti(self) -> bool:
        """
        Assegna le posizioni fisiche considerando le preferenze di posizione.
        CON FISSO: gestisce pre-assegnazione FISSO + gruppo adiacente.

        Ordine di assegnazione:
        1. Se FISSO: seleziona e piazza il gruppo migliore accanto al FISSO
        2. Se trio presente E non già piazzato al punto 1: assegna trio atomico
        3. Assegna le coppie rimanenti
        4. Assegna eventuali studenti singoli
        """
        banchi_per_fila = self.configurazione_aula.get_banchi_per_fila()

        if not banchi_per_fila:
            print("❌ ERRORE: Nessuna fila di banchi trovata nel layout!")
            return False

        print(f"🏫 Layout aula: {len(banchi_per_fila)} file di banchi")
        for idx, banchi_fila in enumerate(banchi_per_fila):
            print(f"   Fila {idx + 1}: {len(banchi_fila)} banchi")

        # ───────────────────────────────────────────────────────
        # STEP 0.5: GRUPPO ADIACENTE AL FISSO (se presente)
        # ───────────────────────────────────────────────────────
        # Il FISSO è già pre-assegnato (col 0, prima fila) da STEP 0.
        # Qui selezioniamo il gruppo migliore da piazzare accanto a lui
        # e lo assegniamo nelle colonne adiacenti (col 1-2 o col 1-2-3).
        trio_gia_piazzato = False  # Flag: True se il trio è stato usato come gruppo adiacente

        if self.studente_fisso is not None:
            print(f"\n🎯 STEP 0.5: Selezione e piazzamento gruppo adiacente al FISSO...")

            # Determina se il trio va in prima fila (stessa fila del FISSO)
            modalita_trio = self._determina_modalita_trio_from_interface()
            trio_in_prima_fila = (self.gestisce_trio and
                                  hasattr(self, 'trio_identificato') and
                                  self.trio_identificato and
                                  modalita_trio == 'prima')

            # Seleziona il gruppo con la migliore compatibilità verso il FISSO
            risultato = self._seleziona_gruppo_per_fisso(trio_in_prima_fila)

            if risultato is not None:
                tipo_gruppo, gruppo_ordinato = risultato

                # Piazza il gruppo nei banchi adiacenti al FISSO (prima fila)
                if self._assegna_gruppo_adiacente_fisso(gruppo_ordinato, banchi_per_fila[0]):
                    print(f"   ✅ Gruppo adiacente al FISSO piazzato con successo")

                    # Se il gruppo piazzato era il trio → non serve piazzarlo di nuovo
                    if tipo_gruppo == 'trio':
                        trio_gia_piazzato = True
                        print(f"   📌 Il trio è stato piazzato accanto al FISSO in prima fila")
                else:
                    print(f"   ⚠️ Impossibile piazzare gruppo adiacente al FISSO")
                    # Non è un errore fatale: le coppie verranno assegnate normalmente
            else:
                print(f"   ⚠️ Nessun gruppo selezionato per il FISSO")

        # ───────────────────────────────────────────────────────
        # STEP 1: ASSEGNAZIONE TRIO ATOMICO (se presente e non già piazzato)
        # ───────────────────────────────────────────────────────
        if (self.gestisce_trio and
            hasattr(self, 'trio_identificato') and
            self.trio_identificato and
            not trio_gia_piazzato):

            print(f"\n🎯 STEP 1: Assegnazione trio atomico...")
            modalita_trio = self._determina_modalita_trio_from_interface()

            if self._assegna_trio_atomico_corretto(self.trio_identificato, banchi_per_fila, modalita_trio):
                print(f"   ✅ Trio atomico assegnato con successo")
            else:
                print(f"   ❌ Impossibile assegnare trio atomico")
                return False

        # ───────────────────────────────────────────────────────
        # STEP 2: ASSEGNAZIONE COPPIE nei banchi rimanenti
        # ───────────────────────────────────────────────────────
        print(f"\n🎯 STEP 2: Assegnazione coppie...")
        if not self._assegna_coppie_intelligenti(banchi_per_fila):
            return False

        # ───────────────────────────────────────────────────────
        # STEP 3: ASSEGNAZIONE STUDENTI SINGOLI (se rimasti)
        # ───────────────────────────────────────────────────────
        if self.studenti_singoli:
            print(f"\n🎯 STEP 3: Assegnazione {len(self.studenti_singoli)} studenti singoli...")
            self._assegna_studenti_singoli_rimanenti(banchi_per_fila)

        return True

    def _assegna_trio_atomico_corretto(self, trio_studenti, banchi_per_fila, modalita_trio):
        """
        Assegna il trio a 3 banchi consecutivi nella stessa fila.
        FONTE DI VERITÀ: legge fila_trio direttamente dalla ConfigurazioneAula,
        che l'ha già calcolata correttamente usando le file effettive in
        crea_layout_standard(). Questo evita di ricalcolare e rischiare
        disallineamenti tra layout fisico e assegnazione algoritmica.
        """
        print(f"   🔍 Assegnazione trio: {[s.get_nome_completo() for s in trio_studenti]}")
        print(f"   📍 Modalità posizionamento: {modalita_trio}")

        # === FONTE DI VERITÀ: fila_trio dal layout ===
        # aula.py ha già calcolato la fila corretta tenendo conto delle
        # file effettive (non quelle configurate). Leggiamo quel valore
        # anziché ricalcolarlo, così layout e algoritmo sono sempre coerenti.
        fila_trio_da_layout = getattr(self.configurazione_aula, 'fila_trio', None)

        # Determina fila target
        fila_target_idx = None

        if fila_trio_da_layout is not None:
            # Usa la fila già calcolata dal layout (fonte di verità)
            fila_target_idx = fila_trio_da_layout
            print(f"   🎯 Target da layout: FILA {fila_target_idx + 1} (modalità '{modalita_trio}')")
        elif modalita_trio == 'prima':
            fila_target_idx = 0
            print(f"   🎯 Target: PRIMA FILA (fallback)")
        elif modalita_trio == 'ultima':
            fila_target_idx = len(banchi_per_fila) - 1
            print(f"   🎯 Target: ULTIMA FILA (fallback)")
        elif modalita_trio == 'centro':
            fila_target_idx = len(banchi_per_fila) // 2
            print(f"   🎯 Target: CENTRO (fallback)")
        else:
            print(f"   ⚠️ Modalità '{modalita_trio}' non riconosciuta, uso PRIMA FILA")
            fila_target_idx = 0

        # Prova assegnazione nella fila target
        if fila_target_idx is not None:
            if self._assegna_trio_in_fila_specifica(trio_studenti, banchi_per_fila[fila_target_idx], f"FILA {fila_target_idx + 1}"):
                return True
            else:
                print(f"   ⚠️  Fila target occupata, provo altre file...")

        # Se modalità specifica fallisce o è 'auto', prova tutte le file
        for idx, fila in enumerate(banchi_per_fila):
            if fila_target_idx is None or idx != fila_target_idx:  # Evita di riprovare la fila già testata
                if self._assegna_trio_in_fila_specifica(trio_studenti, fila, f"FILA {idx + 1}"):
                    return True

        print(f"   ❌ Impossibile trovare 3 banchi consecutivi in nessuna fila")
        return False

    def _assegna_trio_in_fila_specifica(self, trio_studenti, banchi_fila, nome_fila):
        """
        Cerca di assegnare il trio a 3 banchi consecutivi in una fila specifica.
        """
        banchi_liberi = [b for b in banchi_fila if b.is_libero()]

        if len(banchi_liberi) < 3:
            print(f"   ❌ {nome_fila}: solo {len(banchi_liberi)} banchi liberi (servono 3)")
            return False

        # Ordina banchi per colonna per trovare consecutivi
        banchi_liberi.sort(key=lambda b: b.colonna)

        # Cerca 3 banchi consecutivi
        for i in range(len(banchi_liberi) - 2):
            banco1 = banchi_liberi[i]
            banco2 = banchi_liberi[i + 1]
            banco3 = banchi_liberi[i + 2]

            # Verifica consecutività
            if (banco2.colonna == banco1.colonna + 1 and
                banco3.colonna == banco2.colonna + 1):

                # ASSEGNAZIONE con identificatori univoci
                banco1.occupato_da = f"{trio_studenti[0].cognome}_{trio_studenti[0].nome}"
                banco2.occupato_da = f"{trio_studenti[1].cognome}_{trio_studenti[1].nome}"
                banco3.occupato_da = f"{trio_studenti[2].cognome}_{trio_studenti[2].nome}"

                print(f"   ✅ TRIO in {nome_fila}: posizioni ({banco1.riga+1},{banco1.colonna+1}), ({banco2.riga+1},{banco2.colonna+1}), ({banco3.riga+1},{banco3.colonna+1})")
                print(f"      {trio_studenti[0].get_nome_completo()}")
                print(f"      {trio_studenti[1].get_nome_completo()}")
                print(f"      {trio_studenti[2].get_nome_completo()}")

                return True

        print(f"   ❌ {nome_fila}: non trovati 3 banchi consecutivi")
        return False

    def _assegna_coppie_intelligenti(self, banchi_per_fila):
        """
        Assegna le coppie ai banchi rimanenti (dopo il trio).
        Considera solo banchi ancora liberi.
        """
        print(f"   👥 Assegnazione {len(self.coppie_formate)} coppie ai banchi rimanenti...")

        # Categorizza coppie per preferenza di posizione
        coppie_prima_fila = []
        coppie_ultima_fila = []
        coppie_neutrale = []

        for studente1, studente2, info in self.coppie_formate:
            pos1, pos2 = studente1.nota_posizione, studente2.nota_posizione

            if pos1 == 'PRIMA' or pos2 == 'PRIMA':
                coppie_prima_fila.append((studente1, studente2, info))
            elif pos1 == 'ULTIMA' or pos2 == 'ULTIMA':
                coppie_ultima_fila.append((studente1, studente2, info))
            else:
                coppie_neutrale.append((studente1, studente2, info))

        print(f"   📋 Categorizzazione:")
        print(f"      - Prima fila: {len(coppie_prima_fila)} coppie")
        print(f"      - Ultima fila: {len(coppie_ultima_fila)} coppie")
        print(f"      - Flessibili: {len(coppie_neutrale)} coppie")

        # Assegna coppie in ordine di priorità
        tutte_coppie = coppie_prima_fila + coppie_neutrale + coppie_ultima_fila

        coppie_assegnate = 0
        for fila_idx, banchi_fila in enumerate(banchi_per_fila):
            banchi_liberi = [b for b in banchi_fila if b.is_libero()]

            # Assegna coppie a coppie di banchi liberi
            i = 0
            while i < len(banchi_liberi) - 1 and coppie_assegnate < len(tutte_coppie):
                banco1 = banchi_liberi[i]
                banco2 = banchi_liberi[i + 1]

                # Prendi la prossima coppia da assegnare
                coppia = tutte_coppie[coppie_assegnate]
                studente1, studente2, info = coppia

                # Assegna con identificatori univoci
                banco1.occupato_da = f"{studente1.cognome}_{studente1.nome}"
                banco2.occupato_da = f"{studente2.cognome}_{studente2.nome}"

                print(f"   ✅ Coppia {coppie_assegnate + 1}: FILA {fila_idx + 1}")
                print(f"      {studente1.get_nome_completo()} -> ({banco1.riga+1},{banco1.colonna+1})")
                print(f"      {studente2.get_nome_completo()} -> ({banco2.riga+1},{banco2.colonna+1})")

                coppie_assegnate += 1
                i += 2  # Salta al prossimo paio di banchi

        if coppie_assegnate < len(self.coppie_formate):
            print(f"   ⚠️  Assegnate solo {coppie_assegnate}/{len(self.coppie_formate)} coppie")
            return False

        print(f"   ✅ Tutte le {coppie_assegnate} coppie assegnate con successo")
        return True

    def _assegna_studenti_singoli_rimanenti(self, banchi_per_fila):
        """
        Assegna eventuali studenti singoli rimasti ai banchi liberi.
        """
        banchi_liberi = []
        for fila in banchi_per_fila:
            for banco in fila:
                if banco.is_libero():
                    banchi_liberi.append(banco)

        print(f"   📊 Banchi liberi disponibili: {len(banchi_liberi)}")

        for studente in self.studenti_singoli:
            if banchi_liberi:
                banco = banchi_liberi.pop(0)
                banco.occupato_da = f"{studente.cognome}_{studente.nome}"
                print(f"   ✅ {studente.get_nome_completo()} -> ({banco.riga+1},{banco.colonna+1})")
            else:
                print(f"   ❌ Nessun banco libero per {studente.get_nome_completo()}")

    # =========================================================================
    # METODI PER LA GESTIONE STUDENTE FISSO (STEP 0)
    # =========================================================================

    def _gestisci_studente_fisso(self, studente_fisso: 'Student') -> bool:
        """
        STEP 0: Pre-assegna lo studente FISSO e lo rimuove dalla lista.

        Operazioni:
        1. Salva il riferimento allo studente FISSO
        2. Lo pre-assegna al primo banco (prima fila, colonna 0)
        3. Lo rimuove da self.studenti → da qui in poi l'algoritmo lavora su N-1

        Args:
            studente_fisso: Oggetto Student con nota_posizione="FISSO"

        Returns:
            bool: True se pre-assegnazione riuscita
        """
        self.studente_fisso = studente_fisso
        print(f"   📌 Studente FISSO: {studente_fisso.get_nome_completo()}")

        # === PRE-ASSEGNAZIONE AL PRIMO BANCO ===
        # Il FISSO va sempre nel primo banco a sinistra della prima fila.
        # Nel layout standard, la prima fila di banchi è alla riga 2
        # (riga 0 = arredi, riga 1 = vuota) e la colonna 0 è il primo banco.
        banchi_per_fila = self.configurazione_aula.get_banchi_per_fila()

        if not banchi_per_fila or not banchi_per_fila[0]:
            print(f"   ❌ ERRORE: Nessun banco trovato nella prima fila!")
            return False

        # Prendi il primo banco della prima fila (colonna più a sinistra)
        primo_banco = banchi_per_fila[0][0]
        identificatore = f"{studente_fisso.cognome}_{studente_fisso.nome}"
        primo_banco.occupato_da = identificatore

        print(f"   ✅ FISSO pre-assegnato a riga {primo_banco.riga}, colonna {primo_banco.colonna}")

        # === RIMOZIONE DALLA LISTA STUDENTI ===
        # Da qui in poi, _forma_coppie_ottimali lavorerà su N-1 studenti.
        # La logica trio (N-1 dispari/pari) funzionerà automaticamente.
        studenti_prima = len(self.studenti)
        self.studenti = [s for s in self.studenti if s is not studente_fisso]
        studenti_dopo = len(self.studenti)

        if studenti_dopo == studenti_prima:
            # Lo studente FISSO non era nella lista — errore
            print(f"   ⚠️ ATTENZIONE: studente FISSO non trovato nella lista studenti!")
            print(f"   Il FISSO è stato pre-assegnato ma non rimosso dalla lista")
            # Non è un errore fatale: procediamo comunque
        else:
            print(f"   📊 Studenti: {studenti_prima} → {studenti_dopo} (FISSO rimosso)")
            print(f"   📊 Rimanenti dispari: {'Sì (trio)' if studenti_dopo % 2 == 1 else 'No (solo coppie)'}")

        return True

    def _seleziona_gruppo_per_fisso(self, trio_in_prima_fila: bool):
        """
        Dopo la formazione coppie/trio, seleziona il gruppo migliore
        da piazzare accanto al FISSO in prima fila.

        Per ogni gruppo candidato, prova ogni membro nella posizione
        "colonna 1" (adiacente diretto al FISSO) e sceglie la
        combinazione con il punteggio più alto.

        Args:
            trio_in_prima_fila (bool): True se il trio è destinato
                alla prima fila (e quindi sarà il gruppo adiacente).

        Returns:
            tuple: ('coppia', (s1, s2, info)) oppure ('trio', [s1, s2, s3])
                dove s1 è lo studente che andrà in col 1 (adiacente al FISSO).
            None se nessun gruppo è disponibile.
        """
        if not self.studente_fisso:
            return None

        fisso = self.studente_fisso
        migliore_risultato = None
        miglior_punteggio = float('-inf')

        # ─── CASO A: Il trio va in prima fila → il trio È il gruppo adiacente ───
        if trio_in_prima_fila and self.trio_identificato:
            print(f"   🔍 Trio destinato alla prima fila → valuto come gruppo adiacente")
            trio = self.trio_identificato

            # Prova ogni membro del trio in posizione col 1 (adiacente al FISSO)
            for i, studente in enumerate(trio):
                punteggio = self._calcola_punteggio_adiacente_fisso(studente, fisso)
                print(f"      {studente.get_nome_completo()} in col 1: punteggio = {punteggio}")

                if punteggio > miglior_punteggio:
                    miglior_punteggio = punteggio
                    # Riordina il trio mettendo lo studente scelto in posizione 0 (col 1)
                    trio_riordinato = list(trio)
                    scelto = trio_riordinato.pop(i)
                    trio_riordinato.insert(0, scelto)
                    migliore_risultato = ('trio', trio_riordinato)

            if migliore_risultato:
                nome_col1 = migliore_risultato[1][0].get_nome_completo()
                print(f"   🎯 Selezionato: TRIO con {nome_col1} in col 1 (punteggio: {miglior_punteggio})")
            return migliore_risultato

        # ─── CASO B: Nessun trio in prima fila → scegli la coppia migliore ───
        print(f"   🔍 Valutazione coppie per adiacenza al FISSO...")

        # Indice della coppia selezionata (per rimuoverla dopo)
        indice_coppia_selezionata = None

        for idx, (s1, s2, info) in enumerate(self.coppie_formate):
            # Prova s1 in col 1
            punteggio_s1 = self._calcola_punteggio_adiacente_fisso(s1, fisso)
            # Prova s2 in col 1
            punteggio_s2 = self._calcola_punteggio_adiacente_fisso(s2, fisso)

            # Scegli l'orientamento migliore per questa coppia
            if punteggio_s1 >= punteggio_s2:
                punteggio = punteggio_s1
                coppia_orientata = (s1, s2, info)  # s1 in col 1
            else:
                punteggio = punteggio_s2
                coppia_orientata = (s2, s1, info)  # s2 in col 1

            print(f"      Coppia {idx+1}: {coppia_orientata[0].get_nome_completo()} in col 1 → {punteggio}")

            if punteggio > miglior_punteggio:
                miglior_punteggio = punteggio
                migliore_risultato = ('coppia', coppia_orientata)
                indice_coppia_selezionata = idx

        if migliore_risultato:
            nome_col1 = migliore_risultato[1][0].get_nome_completo()
            print(f"   🎯 Selezionata: COPPIA con {nome_col1} in col 1 (punteggio: {miglior_punteggio})")

            # Rimuovi la coppia selezionata da self.coppie_formate
            # (verrà piazzata manualmente accanto al FISSO, non con il flusso normale)
            if indice_coppia_selezionata is not None:
                self.coppie_formate.pop(indice_coppia_selezionata)
                # IMPORTANTE: salva la coppia ORIENTATA (posizione 0 = col 1),
                # non l'originale dal pop (che ha ordine arbitrario).
                # Questo garantisce che gruppo_adiacente_fisso[0] sia lo studente in col 1.
                self.gruppo_adiacente_fisso = migliore_risultato[1]  # coppia_orientata
                print(f"   📋 Coppia rimossa da coppie_formate ({len(self.coppie_formate)} coppie rimaste)")

        return migliore_risultato

    def _calcola_punteggio_adiacente_fisso(self, studente: 'Student', fisso: 'Student') -> int:
        """
        Calcola il punteggio di compatibilità di uno studente per occupare
        la colonna 1 (adiacente diretto al FISSO).

        IMPORTANTE: usa le affinità/incompatibilità dello STUDENTE verso il FISSO,
        perché il FISSO non ha vincoli propri (disabilitati nell'Editor).
        Per influenzare chi siede accanto al FISSO, l'insegnante imposta
        i vincoli SUGLI ALTRI studenti verso il FISSO.

        Args:
            studente: Lo studente candidato per col 1
            fisso: Lo studente con posizione FISSO

        Returns:
            int: Punteggio (positivo = compatibile, negativo = incompatibile,
                 -999999 = incompatibilità assoluta, veto)
        """
        punteggio = 0

        # === AFFINITÀ dello studente verso il FISSO ===
        # Chiave: "Cognome Nome" completo del FISSO nei dizionari dello studente
        # (per evitare ambiguità con cognomi omonimi)
        if fisso.get_nome_completo() in studente.affinita:
            livello = studente.affinita[fisso.get_nome_completo()]
            # Bonus proporzionale al livello (1=lieve, 2=forte, 3=fortissimo)
            bonus = livello * 100
            punteggio += bonus
            print(f"         + Affinità livello {livello} → +{bonus}")

        # === INCOMPATIBILITÀ dello studente verso il FISSO ===
        if fisso.get_nome_completo() in studente.incompatibilita:
            livello = studente.incompatibilita[fisso.get_nome_completo()]
            if livello == 3:
                # Incompatibilità ASSOLUTA → veto: questo studente NON può stare in col 1
                print(f"         🚫 Incompatibilità ASSOLUTA (livello 3) → VETO")
                return -999999
            else:
                # Incompatibilità soft → penalità proporzionale
                penalita = livello * 100
                punteggio -= penalita
                print(f"         - Incompatibilità livello {livello} → -{penalita}")

        # === PENALITÀ ROTAZIONE VICINO AL FISSO ===
        # Penalizza studenti che sono GIÀ stati in col 1 (adiacenti al FISSO)
        # nelle assegnazioni precedenti, per favorire la rotazione mensile.
        # Il contatore è in config_data["studenti_vicino_fisso_contatore"],
        # un dizionario { "Cognome Nome": numero_volte }.
        # Segue lo stesso pattern di studenti_trio_contatore.
        if hasattr(self, 'config_app'):
            contatori = self.config_app.config_data.get("studenti_vicino_fisso_contatore", {})
            nome_studente = studente.get_nome_completo()
            volte_in_col1 = contatori.get(nome_studente, 0)

            if volte_in_col1 > 0:
                # Penalità progressiva: ogni volta in più → penalità crescente
                # 500 punti per volta (stesso peso del contatore trio)
                penalita_rotazione = volte_in_col1 * 500
                punteggio -= penalita_rotazione
                print(f"         🔄 Rotazione: già {volte_in_col1}× in col 1 → -{penalita_rotazione}")

        return punteggio

    def _assegna_gruppo_adiacente_fisso(self, gruppo_ordinato, banchi_prima_fila) -> bool:
        """
        Assegna il gruppo selezionato (coppia o trio) ai banchi adiacenti
        al FISSO nella prima fila.

        Il FISSO è già in col 0. Il gruppo viene piazzato a partire da col 1:
        - Coppia: col 1, col 2
        - Trio: col 1, col 2, col 3

        Args:
            gruppo_ordinato: Lista di Student ordinati (posizione 0 = col 1).
                Per una coppia: [studente_col1, studente_col2]
                Per un trio: [studente_col1, studente_col2, studente_col3]
            banchi_prima_fila: Lista dei PostoAula della prima fila

        Returns:
            bool: True se assegnazione riuscita
        """
        # Estrai studenti dal gruppo
        # (il formato varia: coppia=(s1,s2,info), trio=[s1,s2,s3])
        if isinstance(gruppo_ordinato, tuple) and len(gruppo_ordinato) == 3:
            # È una coppia nel formato (s1, s2, info)
            studenti_da_piazzare = [gruppo_ordinato[0], gruppo_ordinato[1]]
        elif isinstance(gruppo_ordinato, list):
            # È un trio nel formato [s1, s2, s3]
            studenti_da_piazzare = gruppo_ordinato
        else:
            print(f"   ❌ Formato gruppo non riconosciuto: {type(gruppo_ordinato)}")
            return False

        # Trova i banchi liberi nella prima fila, ordinati per colonna
        banchi_liberi = sorted(
            [b for b in banchi_prima_fila if b.is_libero()],
            key=lambda b: b.colonna
        )

        if len(banchi_liberi) < len(studenti_da_piazzare):
            print(f"   ❌ Non abbastanza banchi liberi in prima fila: "
                  f"{len(banchi_liberi)} liberi, servono {len(studenti_da_piazzare)}")
            return False

        # Verifica che i banchi liberi siano consecutivi a partire da col 1
        # (il banco in col 0 è già occupato dal FISSO)
        banchi_consecutivi = []
        for i, banco in enumerate(banchi_liberi):
            if i == 0:
                banchi_consecutivi.append(banco)
            elif banco.colonna == banchi_consecutivi[-1].colonna + 1:
                banchi_consecutivi.append(banco)
            else:
                # Interruzione nella consecutività: ricomincia
                banchi_consecutivi = [banco]

            if len(banchi_consecutivi) >= len(studenti_da_piazzare):
                break

        if len(banchi_consecutivi) < len(studenti_da_piazzare):
            print(f"   ❌ Non trovati {len(studenti_da_piazzare)} banchi consecutivi in prima fila")
            return False

        # === ASSEGNAZIONE ===
        for i, studente in enumerate(studenti_da_piazzare):
            banco = banchi_consecutivi[i]
            banco.occupato_da = f"{studente.cognome}_{studente.nome}"
            ruolo = "adiacente diretto (col 1)" if i == 0 else f"col {banco.colonna}"
            print(f"   ✅ {studente.get_nome_completo()} → riga {banco.riga}, col {banco.colonna} ({ruolo})")

        # === SALVA IL NOME DELL'ADIACENTE DIRETTO (col 1) ===
        # Questo è la FONTE DI VERITÀ per il contatore studenti_vicino_fisso_contatore.
        # Viene letto in salva_assegnazione() per aggiornare il contatore.
        # Funziona sia per coppia che per trio adiacente al FISSO.
        self.nome_adiacente_fisso = studenti_da_piazzare[0].get_nome_completo()
        print(f"   📌 Adiacente diretto FISSO registrato: {self.nome_adiacente_fisso}")

        return True

    def _calcola_statistiche_finali(self):
        """
        Calcola e stampa le statistiche dell'assegnazione completata.
        """
        print("📊 STATISTICHE ASSEGNAZIONE")
        print("-" * 30)

        # Conta valutazioni delle coppie (con categoria separata per riutilizzate)
        # Le etichette corrispondono 1:1 a quelle assegnate da vincoli.py
        # nel report dettagliato di ogni coppia, per coerenza con l'utente.
        self.stats['coppie_riutilizzate'] = 0
        for _, _, info in self.coppie_formate:
            valutazione = info['valutazione']
            if valutazione == 'OTTIMA':
                self.stats['coppie_ottimali'] += 1
            elif valutazione == 'BUONA':
                self.stats['coppie_buone'] += 1
            elif valutazione == 'ACCETTABILE':
                self.stats['coppie_accettabili'] += 1
            elif valutazione in ['RIUTILIZZATA', 'BLACKLISTATA_SOFT']:
                # Riconosce sia RIUTILIZZATA che BLACKLISTATA_SOFT come coppie riutilizzate
                # BLACKLISTATA_SOFT viene usata nel tentativo 4 quando la blacklist diventa penalità soft
                self.stats['coppie_riutilizzate'] += 1
            elif valutazione == 'PROBLEMATICA':
                self.stats['coppie_problematiche'] += 1
            elif valutazione == 'CRITICA':
                self.stats['coppie_critiche'] += 1
            else:
                # Etichetta imprevista (sicurezza) → conta come problematica
                self.stats['coppie_problematiche'] += 1

        print(f"👥 Coppie totali: {len(self.coppie_formate)}")
        print(f"🌟 Coppie ottimali: {self.stats['coppie_ottimali']}")
        print(f"✅ Coppie accettabili: {self.stats['coppie_accettabili']}")
        print(f"⚠️ Coppie problematiche: {self.stats['coppie_problematiche']}")
        print(f"🔄 Coppie riutilizzate: {self.stats['coppie_riutilizzate']}")
        print(f"👤 Studenti singoli: {len(self.studenti_singoli)}")
        # Aggiungi statistiche trio se presente
        if hasattr(self, 'trio_identificato') and self.trio_identificato:
            print(f"👥 Trio formato: 1 ({len(self.trio_identificato)} studenti)")

        # Calcola percentuale di successo (ottimali + buone + accettabili)
        if self.coppie_formate:
            successo_percentuale = (
                (self.stats['coppie_ottimali'] + self.stats['coppie_buone'] + self.stats['coppie_accettabili']) /
                len(self.coppie_formate) * 100
            )
            print(f"📈 Tasso di successo: {successo_percentuale:.1f}%")

    def _valuta_trio(self, trio):
        """
        Valuta la qualità di un trio basandosi SOLO sulle coppie fisicamente adiacenti.
        Usato da esportazione.py per il report testuale.
        """
        punteggio_totale = 0
        studente1, studente2, studente3 = trio

        # Valuta SOLO le coppie fisicamente adiacenti nel trio [1-2-3]
        coppie_adiacenti = [
            (studente1, studente2),  # Posti 1-2
            (studente2, studente3)   # Posti 2-3
        ]
        # NOTA: studente1-studente3 NON sono adiacenti, non vanno valutati

        for s1, s2 in coppie_adiacenti:
            risultato = self.motore_vincoli.calcola_punteggio_coppia(s1, s2)
            punteggio_totale += risultato['punteggio_totale']

        return punteggio_totale

    def _determina_modalita_trio_from_interface(self):
        """
        Restituisce la modalità trio passata come parametro.
        Default: 'prima' se non specificato. NOTA: questo valore
        è deprecato e non verrà mai usato!
        """
        return getattr(self, 'modalita_trio', 'prima')

    def _trio_rispetta_vincoli_assoluti(self, trio_candidato):
        """
        Verifica se un trio rispetta tutti i vincoli assoluti.

        Args:
            trio_candidato: Tupla di 3 studenti

        Returns:
            bool: True se trio valido, False se viola vincoli assoluti
        """
        studente1, studente2, studente3 = trio_candidato

        # VINCOLO 1: Incompatibilità assolute (livello 3)
        coppie_interne = [(studente1, studente2), (studente1, studente3), (studente2, studente3)]

        for s1, s2 in coppie_interne:
            if self.motore_vincoli._ha_incompatibilita_assoluta(s1, s2):
                print(f"   ❌ Trio scartato: incompatibilità assoluta {s1.cognome}-{s2.cognome}")
                return False

        # VINCOLO 2: Genere misto - NON è un vincolo assoluto per il trio
        # È gestito come PREFERENZA nel calcolo punteggio coppie adiacenti
        # Il trio può avere coppie adiacenti dello stesso genere se necessario

        return True
