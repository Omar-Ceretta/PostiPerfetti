"""
Algoritmo principale per l'assegnazione automatica dei posti.
Combina vincoli sociali, preferenze di posizione e layout aula.
"""

from typing import List, Tuple, Optional
from modelli.studenti import Student
from modelli.aula import ConfigurazioneAula, PostoAula
from modelli.vincoli import MotoreVincoli, MotoreVincoliConfigurato


class AssegnatorePosti:
    """
    Coordina l'intero processo di assegnazione automatica dei posti.
    """

    def __init__(self):
        self.motore_vincoli = MotoreVincoliConfigurato()  # Usa versione configurabile
        self.configurazione_aula = None
        self.studenti = []
        self.coppie_formate = []
        self.studenti_singoli = []  # Per gestire numeri dispari

        # Statistiche dell'assegnazione
        self.stats = {
            'vincoli_rispettati': 0,
            'vincoli_violati': 0,
            'coppie_ottimali': 0,
            'coppie_accettabili': 0,
            'coppie_problematiche': 0
        }

    def esegui_assegnazione_completa(self, studenti: List[Student], configurazione_aula: ConfigurazioneAula, modalita_trio: str = 'auto') -> bool:
        """
        Esegue l'intero processo di assegnazione automatica.

        Args:
            studenti: Lista degli studenti da sistemare
            configurazione_aula: Layout dell'aula
            modalita_trio: Modalità posizionamento trio ('prima', 'ultima', 'centro', 'auto')

        Returns:
            bool: True se assegnazione completata con successo
        """
        print("🚀 INIZIO ASSEGNAZIONE AUTOMATICA")
        print("=" * 50)

        self.studenti = studenti
        self.configurazione_aula = configurazione_aula

        # Salva modalità trio per uso successivo
        self.modalita_trio = modalita_trio

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
        VERSIONE AVANZATA: 4 tentativi progressivi con allentamento vincoli.
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

        # NUOVO: Inizializza trio_identificato a None per numeri pari
        self.trio_identificato = None

        # STEP 2: Sistema a cascata con 4 tentativi progressivi
        for tentativo in range(1, 5):  # Tentativo 1, 2, 3, 4
            print(f"\n{'='*20} TENTATIVO {tentativo} {'='*20}")

            # Configura motore vincoli per questo tentativo
            self.motore_vincoli.configura_per_tentativo(tentativo, self._get_info_blacklist())

            # Applica penalità blacklist sempre (fix bug rotazione)
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

        # NUOVO: Comunica il tentativo corrente al motore vincoli per equità
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
        """
        VERSIONE DEBUG COMPLETA per capire perché non funziona
        """
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

        # NUOVO: Applica penalità per studenti già usati nel trio
        if hasattr(self, 'config_app'):
            punteggio_totale -= self._calcola_penalita_trio_ripetuti(trio)

        # NUOVO: Controlla se le coppie virtuali del trio sono già in blacklist come coppie normali
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
        NUOVO SISTEMA: Le penalità trio sono gestite tramite le coppie virtuali nella blacklist normale.
        Questo metodo ora si limita a verificare che le coppie virtuali non siano già in blacklist.
        """
        if not hasattr(self, 'config_app'):
            return punteggio_base

        # Non applichiamo più penalità qui - tutto gestito tramite coppie virtuali
        # Il controllo è già fatto in _conta_coppie_virtuali_ripetute_trio
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
            for cognome, livello in studente.incompatibilita.items():
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

    def _analizza_vincoli_assoluti_dettagliato(self):
        """Analisi dettagliata dei vincoli assoluti che impediscono l'assegnazione"""
        # Incompatibilità livello 3
        incomp_assolute = []
        for studente in self.studenti:
            for cognome, livello in studente.incompatibilita.items():
                if livello == 3:
                    incomp_assolute.append(f"{studente.cognome} ↔ {cognome}")

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
            # TODO: Verificare capienza effettiva prima fila dall'aula

        # Genere misto obbligatorio
        if hasattr(self.motore_vincoli, 'genere_misto_obbligatorio') and self.motore_vincoli.genere_misto_obbligatorio:
            maschi = [s for s in self.studenti if s.sesso == 'M']
            femmine = [s for s in self.studenti if s.sesso == 'F']
            print(f"   • Genere misto obbligatorio: {len(maschi)} maschi, {len(femmine)} femmine")
            if abs(len(maschi) - len(femmine)) > 1:
                print(f"     ⚠️ Sbilanciamento: alcune coppie saranno necessariamente stesso genere")

    def _analizza_blacklist_dettagliato(self):
        """Analisi dettagliata della blacklist"""
        if not hasattr(self, 'config_app'):
            print("   • Nessuna configurazione blacklist disponibile")
            return

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            print("   • Blacklist vuota - nessuna coppia usata in precedenza")
            return

        coppie_normali = [item for item in coppie_usate if item.get("tipo") != "trio"]
        trii_usati = [item for item in coppie_usate if item.get("tipo") == "trio"]

        print(f"   • Coppie in blacklist: {len(coppie_normali)}")
        print(f"   • Trii in blacklist: {len(trii_usati)}")

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
        """Propone coppie dalla blacklist che potrebbero essere riutilizzate"""
        if not hasattr(self, 'config_app'):
            return

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            print("   • Nessuna coppia disponibile per riutilizzo")
            return

        # Filtra solo coppie normali (no trii)
        coppie_normali = [item for item in coppie_usate if item.get("tipo") != "trio"]

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
        VERSIONE CORRETTA: Gestisce trio atomico PRIMA delle coppie.
        """
        banchi_per_fila = self.configurazione_aula.get_banchi_per_fila()

        if not banchi_per_fila:
            print("❌ ERRORE: Nessuna fila di banchi trovata nel layout!")
            return False

        print(f"🏫 Layout aula: {len(banchi_per_fila)} file di banchi")
        for idx, banchi_fila in enumerate(banchi_per_fila):
            print(f"   Fila {idx + 1}: {len(banchi_fila)} banchi")

        # STEP 1: ASSEGNAZIONE TRIO ATOMICO (PRIORITÀ MASSIMA)
        if self.gestisce_trio and hasattr(self, 'trio_identificato') and self.trio_identificato:
            print(f"\n🎯 STEP 1: Assegnazione trio atomico...")
            modalita_trio = self._determina_modalita_trio_from_interface()

            if self._assegna_trio_atomico_corretto(self.trio_identificato, banchi_per_fila, modalita_trio):
                print(f"   ✅ Trio atomico assegnato con successo")
            else:
                print(f"   ❌ Impossibile assegnare trio atomico")
                return False

        # STEP 2: ASSEGNAZIONE COPPIE nei banchi rimanenti
        print(f"\n🎯 STEP 2: Assegnazione coppie...")
        if not self._assegna_coppie_intelligenti(banchi_per_fila):
            return False

        # STEP 3: ASSEGNAZIONE STUDENTI SINGOLI (se rimasti)
        if self.studenti_singoli:
            print(f"\n🎯 STEP 3: Assegnazione {len(self.studenti_singoli)} studenti singoli...")
            self._assegna_studenti_singoli_rimanenti(banchi_per_fila)

        return True

    def _assegna_trio_atomico_corretto(self, trio_studenti, banchi_per_fila, modalita_trio):
        """
        Assegna il trio a 3 banchi consecutivi nella stessa fila.
        VERSIONE CORRETTA: Gestisce correttamente tutte le modalità.
        """
        print(f"   🔍 Assegnazione trio: {[s.get_nome_completo() for s in trio_studenti]}")
        print(f"   📍 Modalità posizionamento: {modalita_trio}")

        # Determina fila target
        fila_target_idx = None

        if modalita_trio == 'prima':
            fila_target_idx = 0
            print(f"   🎯 Target: PRIMA FILA")
        elif modalita_trio == 'ultima':
            fila_target_idx = len(banchi_per_fila) - 1
            print(f"   🎯 Target: ULTIMA FILA")
        elif modalita_trio == 'centro':
            fila_target_idx = len(banchi_per_fila) // 2
            print(f"   🎯 Target: CENTRO (fila {fila_target_idx + 1})")
        else:
            # Fallback: se modalità non riconosciuta, usa prima fila
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
        VERSIONE CORRETTA: Logica di ricerca banchi consecutivi riparata.
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

                # ASSEGNAZIONE CORRETTA con identificatori univoci
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
        VERSIONE CORRETTA: Considera solo banchi ancora liberi.
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

    def _calcola_statistiche_finali(self):
        """
        Calcola e stampa le statistiche dell'assegnazione completata.
        """
        print("📊 STATISTICHE ASSEGNAZIONE")
        print("-" * 30)

        # Conta valutazioni delle coppie (con categoria separata per riutilizzate)
        self.stats['coppie_riutilizzate'] = 0  # Nuova categoria
        for _, _, info in self.coppie_formate:
            valutazione = info['valutazione']
            if valutazione == 'OTTIMA':
                self.stats['coppie_ottimali'] += 1
            elif valutazione in ['BUONA', 'NEUTRALE']:
                self.stats['coppie_accettabili'] += 1
            elif valutazione in ['RIUTILIZZATA', 'BLACKLISTATA_SOFT']:
                # FIX: Riconosce sia RIUTILIZZATA che BLACKLISTATA_SOFT come coppie riutilizzate
                # BLACKLISTATA_SOFT viene usata nel tentativo 4 quando la blacklist diventa penalità soft
                self.stats['coppie_riutilizzate'] += 1
            else:
                self.stats['coppie_problematiche'] += 1  # Solo incompatibilità vere

        print(f"👥 Coppie totali: {len(self.coppie_formate)}")
        print(f"🌟 Coppie ottimali: {self.stats['coppie_ottimali']}")
        print(f"✅ Coppie accettabili: {self.stats['coppie_accettabili']}")
        print(f"⚠️ Coppie problematiche: {self.stats['coppie_problematiche']}")
        print(f"🔄 Coppie riutilizzate: {self.stats['coppie_riutilizzate']}")
        print(f"👤 Studenti singoli: {len(self.studenti_singoli)}")
        # Aggiungi statistiche trio se presente
        if hasattr(self, 'trio_identificato') and self.trio_identificato:
            print(f"👥 Trio formato: 1 ({len(self.trio_identificato)} studenti)")

        # Calcola percentuale di successo
        if self.coppie_formate:
            successo_percentuale = (
                (self.stats['coppie_ottimali'] + self.stats['coppie_accettabili']) /
                len(self.coppie_formate) * 100
            )
            print(f"📈 Tasso di successo: {successo_percentuale:.1f}%")

    def get_assegnazione_finale(self) -> ConfigurazioneAula:
        """
        Restituisce la configurazione finale dell'aula con tutti gli studenti assegnati.
        """
        return self.configurazione_aula

    def _valuta_trio(self, trio):
        """
        Valuta la qualità di un trio basandosi SOLO sulle coppie fisicamente adiacenti.
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
        Default: 'prima' se non specificato (opzione "auto" rimossa).
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

        # VINCOLO 2: Genere misto - NON è più un vincolo assoluto per il trio
        # Ora è gestito come PREFERENZA nel calcolo punteggio coppie adiacenti
        # Il trio può avere coppie adiacenti dello stesso genere se necessario

        return True
