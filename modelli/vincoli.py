"""
Modulo per la gestione dei vincoli e il calcolo dei punteggi di compatibilità.
Sistema di scoring per determinare la qualità delle assegnazioni.
"""

from typing import List, Dict, Tuple, Optional
from modelli.studenti import Student


class MotoreVincoli:
    """
    Calcola i punteggi di compatibilità tra studenti e gestisce tutti i vincoli.
    """

    def __init__(self):
        # SISTEMA VINCOLI: Solo per vincoli "soft" (non assoluti)
        self.PESO_INCOMPATIBILITA = 100  # Per livelli 1-2 (non assoluti)
        self.PESO_AFFINITA = 50         # Per livelli 1-3 (tutti soft)
        self.PESO_GENERE_MISTO = 10     # Solo bonus quando flag disattivo
        self.PESO_POSIZIONE_ULTIMA = 10  # Solo per preferenza "ULTIMA"

        # VINCOLI ASSOLUTI: Gestiti con logica separata, NON con pesi
        # - Incompatibilità livello 3: esclusione totale coppia
        # - Posizione "PRIMA": verifica capienza assoluta
        # - Genere misto obbligatorio: esclusione coppie stesso genere (se possibile)

        # NUOVA SCALA 1-3: Moltiplicatori semplificati
        self.MOLTIPLICATORI = {
            1: 1,    # Neutrale - nessun effetto particolare
            2: 4,    # Forte - preferenza/evitamento significativo
            3: 20    # ASSOLUTO - vincolo inviolabile
        }

        # NUOVO: Flag per genere misto obbligatorio
        self.genere_misto_obbligatorio = False  # Settabile dall'interfaccia

    def calcola_punteggio_coppia(self, studente1: Student, studente2: Student) -> Dict:
        """
        Calcola il punteggio di compatibilità tra due studenti.

        Args:
            studente1, studente2: I due studenti da valutare

        Returns:
            Dict: Dizionario con punteggio totale e dettagli dei sub-punteggi
        """
        risultato = {
            'punteggio_totale': 0,
            'dettagli': {
                'incompatibilita': 0,
                'affinita': 0,
                'genere_misto': 0,
                'posizione': 0
            },
            'valutazione': 'NEUTRALE',  # OTTIMA, BUONA, NEUTRALE, PROBLEMATICA, VIETATA
            'note': []
        }

        # 1. CONTROLLO VINCOLI ASSOLUTI (esclusione preventiva)
        # INCOMPATIBILITÀ LIVELLO 3: Coppia completamente vietata
        if self._ha_incompatibilita_assoluta(studente1, studente2):
            risultato['punteggio_totale'] = -999999
            risultato['valutazione'] = 'VIETATA'
            risultato['note'].append('INCOMPATIBILITÀ ASSOLUTA (livello 3)')
            return risultato

        # NOTA: Genere misto NON è più un vincolo assoluto (rimosso controllo)
        # Ora è gestito come PREFERENZA FORTE nel metodo _calcola_genere_misto_soft()

        # 2. CALCOLO VINCOLI SOFT (solo per coppie non vietate)
        punteggio_incomp = self._calcola_incompatibilita_soft(studente1, studente2)
        risultato['dettagli']['incompatibilita'] = punteggio_incomp

        # 3. CALCOLO AFFINITÀ (tutti i livelli 1-3 sono soft)
        punteggio_aff = self._calcola_affinita(studente1, studente2)
        risultato['dettagli']['affinita'] = punteggio_aff

        # 4. BONUS GENERE MISTO (solo quando flag disattivo)
        punteggio_genere = self._calcola_genere_misto_soft(studente1, studente2)
        risultato['dettagli']['genere_misto'] = punteggio_genere

        # 5. VINCOLI POSIZIONE SOFT (solo "ULTIMA", "PRIMA" gestita separatamente)
        punteggio_pos = self._calcola_posizione_soft(studente1, studente2)
        risultato['dettagli']['posizione'] = punteggio_pos

        # CALCOLO PUNTEGGIO TOTALE
        risultato['punteggio_totale'] = (
            punteggio_incomp +
            punteggio_aff +
            punteggio_genere +
            punteggio_pos
        )

        # VALUTAZIONE QUALITATIVA (aggiornata per nuova scala 1-3)
        if risultato['punteggio_totale'] >= 200:
            risultato['valutazione'] = 'OTTIMA'     # Affinità forte (livello 2-3)
        elif risultato['punteggio_totale'] >= 50:
            risultato['valutazione'] = 'BUONA'      # Affinità leggera o neutralità
        elif risultato['punteggio_totale'] >= -50:
            risultato['valutazione'] = 'NEUTRALE'   # Vicino a zero, equilibrata
        elif risultato['punteggio_totale'] >= -200:
            risultato['valutazione'] = 'PROBLEMATICA'  # Incompatibilità leggera
        else:
            risultato['valutazione'] = 'CRITICA'    # Incompatibilità forte (livello 2)

        # Aggiungi note informative
        self._aggiungi_note_dettagliate(risultato, studente1, studente2)

        return risultato

    def _ha_incompatibilita_assoluta(self, studente1: Student, studente2: Student) -> bool:
        """
        Verifica se due studenti hanno incompatibilità assoluta (livello 3).

        Returns:
            bool: True se la coppia è assolutamente vietata
        """
        # Controlla incompatibilità di studente1 verso studente2
        if studente2.cognome in studente1.incompatibilita:
            if studente1.incompatibilita[studente2.cognome] == 3:
                return True

        # Controlla incompatibilità di studente2 verso studente1
        if studente1.cognome in studente2.incompatibilita:
            if studente2.incompatibilita[studente1.cognome] == 3:
                return True

        return False

    def _calcola_incompatibilita_soft(self, studente1: Student, studente2: Student) -> int:
        """
        Calcola penalità per incompatibilità non assolute (livelli 1-2).

        Returns:
            int: Punteggio negativo per incompatibilità soft
        """
        punteggio = 0

        # Controlla incompatibilità di studente1 verso studente2
        if studente2.cognome in studente1.incompatibilita:
            livello = studente1.incompatibilita[studente2.cognome]
            if livello in [1, 2]:  # Solo livelli soft
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        # Controlla incompatibilità di studente2 verso studente1
        if studente1.cognome in studente2.incompatibilita:
            livello = studente2.incompatibilita[studente1.cognome]
            if livello in [1, 2]:  # Solo livelli soft
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        return punteggio

    def _calcola_affinita(self, studente1: Student, studente2: Student) -> int:
        """
        Calcola il punteggio per affinità tra due studenti.
        Punteggio POSITIVO = bonus per affinità
        """
        punteggio = 0

        # Controlla affinità di studente1 verso studente2
        if studente2.cognome in studente1.affinita:
            livello = studente1.affinita[studente2.cognome]
            bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
            punteggio += bonus

        # Controlla affinità di studente2 verso studente1
        if studente1.cognome in studente2.affinita:
            livello = studente2.affinita[studente1.cognome]
            bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
            punteggio += bonus

        return punteggio

    def _calcola_genere_misto_soft(self, studente1: Student, studente2: Student) -> int:
        """
        Calcola bonus per preferenza genere misto.
        NON è più un vincolo assoluto, ma una PREFERENZA FORTE.

        Returns:
            int: Bonus per coppie miste se flag attivo
        """
        # Se flag disattivo: nessun bonus (neutrale rispetto al genere)
        if not self.genere_misto_obbligatorio:
            return 0

        # Se flag attivo: bonus FORTE per coppie miste
        # Nota: +100 è un bonus significativo ma NON vieta coppie stesso genere
        # Questo permette flessibilità con classi sbilanciate e blacklist estese
        if studente1.sesso != studente2.sesso:
            return 100  # Bonus forte (prima era +10)
        else:
            return 0  # Nessun bonus, ma neanche penalità (coppie stesso genere accettate)

    def _calcola_posizione_soft(self, studente1: Student, studente2: Student) -> int:
        """
        Calcola compatibilità posizioni SOFT (solo "ULTIMA", non "PRIMA").
        NOTA: Posizione "PRIMA" è vincolo assoluto, gestito separatamente.

        Returns:
            int: Bonus/penalità per preferenze posizione soft
        """
        pos1 = studente1.nota_posizione
        pos2 = studente2.nota_posizione

        # PRIMA è vincolo assoluto - non calcolato qui
        # Gestiamo solo compatibilità ULTIMA vs altre

        # Entrambi vogliono ULTIMA = piccolo bonus
        if pos1 == 'ULTIMA' and pos2 == 'ULTIMA':
            return self.PESO_POSIZIONE_ULTIMA

        # Uno vuole ULTIMA, altro NORMALE = neutrale (nessun conflitto)
        if (pos1 == 'ULTIMA' and pos2 == 'NORMALE') or (pos1 == 'NORMALE' and pos2 == 'ULTIMA'):
            return 0

        # NORMALE + NORMALE = neutrale
        if pos1 == 'NORMALE' and pos2 == 'NORMALE':
            return 0

        # Tutti gli altri casi = neutrale (inclusi quelli con PRIMA)
        return 0

    def _aggiungi_note_dettagliate(self, risultato: Dict, studente1: Student, studente2: Student):
        """
        Aggiunge note descrittive dettagliate per spiegare il punteggio (scala 1-3).
        """
        note = risultato['note']

        # Note AFFINITÀ con livelli specifici
        if risultato['dettagli']['affinita'] > 0:
            # Determina livelli affinità per note più precise
            aff1 = studente1.affinita.get(studente2.cognome, 0)
            aff2 = studente2.affinita.get(studente1.cognome, 0)
            if aff1 >= 3 or aff2 >= 3:
                note.append(f"Affinità FORTE tra {studente1.cognome}-{studente2.cognome}")
            elif aff1 >= 2 or aff2 >= 2:
                note.append(f"Affinità buona tra {studente1.cognome}-{studente2.cognome}")
            else:
                note.append(f"Affinità leggera tra {studente1.cognome}-{studente2.cognome}")

        # Note INCOMPATIBILITÀ SOFT con livelli specifici
        if risultato['dettagli']['incompatibilita'] < 0:
            incomp1 = studente1.incompatibilita.get(studente2.cognome, 0)
            incomp2 = studente2.incompatibilita.get(studente1.cognome, 0)
            max_incomp = max(incomp1, incomp2)
            if max_incomp >= 2:
                note.append(f"Incompatibilità FORTE tra {studente1.cognome}-{studente2.cognome}")
            else:
                note.append(f"Incompatibilità leggera tra {studente1.cognome}-{studente2.cognome}")

        # Note GENERE MISTO (solo quando flag disattivo)
        if risultato['dettagli']['genere_misto'] > 0:
            note.append(f"Bonus varietà: coppia mista {studente1.sesso}/{studente2.sesso}")

        # Note POSIZIONE (solo per "ULTIMA")
        if risultato['dettagli']['posizione'] > 0:
            note.append(f"Entrambi preferiscono ultima fila")

        # Note SPECIALI per posizione "PRIMA" (informativa)
        if studente1.nota_posizione == 'PRIMA' or studente2.nota_posizione == 'PRIMA':
            nomi_prima = []
            if studente1.nota_posizione == 'PRIMA':
                nomi_prima.append(studente1.cognome)
            if studente2.nota_posizione == 'PRIMA':
                nomi_prima.append(studente2.cognome)
            note.append(f"PRIMA FILA richiesta: {', '.join(nomi_prima)}")

    def trova_migliori_coppie(self, studenti: List[Student], num_coppie_desiderate: int = None) -> List[Tuple]:
            """
            Trova le migliori coppie possibili per la lista di studenti fornita.

            Args:
                studenti: Lista di studenti da abbinare
                num_coppie_desiderate: Numero massimo di coppie da formare (opzionale)

            Returns:
                List[Tuple]: Lista di tuple (studente1, studente2, punteggio_info)
            """
            if not studenti:
                return []

            # DEBUG INVASIVO - IMPOSSIBILE DA PERDERE
            #with open("debug_chiamate.txt", "a") as f:
                #f.write(f"CHIAMATA #{len(studenti)} - tentativo: {getattr(self, 'tentativo_corrente', 'N/A')}\n")

            #print(f"🔍 CHIAMATA #{len(studenti)}: trova_migliori_coppie - tentativo: {getattr(self, 'tentativo_corrente', 'N/A')}")

            if num_coppie_desiderate is None:
                num_coppie_desiderate = len(studenti) // 2

            # VERIFICA VINCOLI ASSOLUTI DI SISTEMA prima di iniziare
            if not self._verifica_vincoli_sistema_possibili(studenti):
                print("⚠️ ATTENZIONE: Alcuni vincoli assoluti potrebbero essere impossibili da rispettare")

            print(f"🧮 Calcolando coppie ottimali per {len(studenti)} studenti...")
            print(f"🎯 Target: {num_coppie_desiderate} coppie")

            # Calcola tutti i punteggi possibili
            tutti_punteggi = []

            for i in range(len(studenti)):
                for j in range(i + 1, len(studenti)):
                    studente1 = studenti[i]
                    studente2 = studenti[j]

                    punteggio_info = self.calcola_punteggio_coppia(studente1, studente2)

                    # Escludi coppie vietate
                    if punteggio_info['valutazione'] != 'VIETATA':
                        tutti_punteggi.append((studente1, studente2, punteggio_info))

            if hasattr(self, 'tentativo_corrente') and self.tentativo_corrente == 4:
                print(f"   ⚖️ TENTATIVO 4: MULTI-TENTATIVO con minimizzazione ripetizioni")
                import random

                # STRATEGIA: Prova 15 ordini diversi delle coppie mai usate
                # e tiene la soluzione con meno ripetizioni totali.
                # Questo evita che la prima scelta "blocchi" sempre gli stessi studenti.

                # Separa coppie per numero di utilizzi
                coppie_per_utilizzo = {}
                for coppia_info in tutti_punteggi:
                    utilizzi = self._conta_utilizzi_coppia(coppia_info[0], coppia_info[1])
                    if utilizzi not in coppie_per_utilizzo:
                        coppie_per_utilizzo[utilizzi] = []
                    coppie_per_utilizzo[utilizzi].append(coppia_info)

                # Ordina i gruppi di utilizzo: 0, 1, 2, 3...
                gruppi_ordinati = sorted(coppie_per_utilizzo.keys())

                print(f"   📊 Distribuzione coppie per utilizzo:")
                for gruppo in gruppi_ordinati:
                    print(f"      Usate {gruppo} volte: {len(coppie_per_utilizzo[gruppo])} coppie")

                # Prova 15 ordini diversi e tieni la soluzione migliore
                NUM_TENTATIVI_RANDOM = 15
                miglior_soluzione = None
                miglior_punteggio_totale = float('-inf')

                for tentativo_random in range(NUM_TENTATIVI_RANDOM):
                    # Costruisci lista ordinata: mai usate (shuffled) + usate 1 volta + usate 2 volte...
                    lista_tentativo = []
                    for gruppo in gruppi_ordinati:
                        coppie_gruppo = coppie_per_utilizzo[gruppo].copy()
                        if gruppo == 0:
                            # Mescola casualmente le coppie mai usate per esplorare percorsi diversi
                            random.shuffle(coppie_gruppo)
                        else:
                            # Per coppie già usate, ordina per punteggio decrescente
                            coppie_gruppo.sort(key=lambda x: x[2]['punteggio_totale'], reverse=True)
                        lista_tentativo.extend(coppie_gruppo)

                    # Prova backtracking con questo ordine
                    soluzione = self._trova_coppie_con_backtracking(
                        studenti=studenti,
                        num_coppie_target=num_coppie_desiderate,
                        tutti_punteggi=lista_tentativo
                    )

                    if soluzione:
                        # Calcola punteggio totale della soluzione (somma di tutti i punteggi)
                        punteggio_soluzione = sum(
                            info['punteggio_totale'] for _, _, info in soluzione
                        )

                        # Conta quante coppie sono riutilizzate
                        coppie_riutilizzate = sum(
                            1 for s1, s2, _ in soluzione
                            if self._conta_utilizzi_coppia(s1, s2) > 0
                        )

                        print(f"   🔄 Tentativo random {tentativo_random + 1}/{NUM_TENTATIVI_RANDOM}: "
                              f"punteggio={punteggio_soluzione}, riutilizzate={coppie_riutilizzate}")

                        if punteggio_soluzione > miglior_punteggio_totale:
                            miglior_punteggio_totale = punteggio_soluzione
                            miglior_soluzione = soluzione
                            print(f"      ⭐ Nuova migliore soluzione!")

                if miglior_soluzione:
                    print(f"   ✅ Migliore soluzione trovata con punteggio: {miglior_punteggio_totale}")
                    return miglior_soluzione
                else:
                    print(f"   ❌ Nessuna soluzione trovata in {NUM_TENTATIVI_RANDOM} tentativi")
                    return []
            else:
                # TENTATIVI 1-3: Ordinamento normale solo per punteggio
                tutti_punteggi.sort(key=lambda x: x[2]['punteggio_totale'], reverse=True)

            # 🔄 USA BACKTRACKING invece di greedy per trovare soluzione garantita
            print(f"   🔄 Usando algoritmo BACKTRACKING per garantire soluzione se esiste...")

            coppie_selezionate = self._trova_coppie_con_backtracking(
                studenti=studenti,
                num_coppie_target=num_coppie_desiderate,
                tutti_punteggi=tutti_punteggi
            )

            # Se backtracking fallisce, ritorna lista vuota
            if coppie_selezionate is None:
                print(f"   ❌ BACKTRACKING: Nessuna soluzione trovata")
                return []

            print(f"✅ Trovate {len(coppie_selezionate)} coppie ottimali")
            return coppie_selezionate

    def _conta_utilizzi_coppia(self, studente1, studente2):
        """
        Conta quante volte una coppia è stata utilizzata in precedenza.

        Args:
            studente1, studente2: I due studenti della coppia

        Returns:
            int: Numero di utilizzi precedenti (0 se mai usata)
        """
        if not hasattr(self, '_config_app_ref') or not self._config_app_ref:
            return 0

        coppie_usate = self._config_app_ref.config_data.get("coppie_da_evitare", [])
        nomi_coppia = {studente1.get_nome_completo(), studente2.get_nome_completo()}

        for coppia_usata in coppie_usate:
            # Estrae nomi dalla coppia in blacklist (formato unico)
            studenti = coppia_usata.get("studenti", [])
            if len(studenti) != 2:
                continue
            coppia_blacklist = {studenti[0], studenti[1]}

            if coppia_blacklist == nomi_coppia:
                return coppia_usata.get("volte_usata", 0)

        return 0  # Coppia mai usata

    def stampa_report_coppie(self, coppie_trovate: List[Tuple]):
        """
        Stampa un report dettagliato delle coppie trovate.
        """
        print(f"\n📊 REPORT COPPIE TROVATE")
        print("=" * 60)

        for idx, (studente1, studente2, info) in enumerate(coppie_trovate, 1):
            print(f"\n👥 COPPIA {idx}: {studente1.get_nome_completo()} + {studente2.get_nome_completo()}")
            print(f"   Punteggio: {info['punteggio_totale']} - Valutazione: {info['valutazione']}")

            # Dettagli punteggi
            dettagli = info['dettagli']
            if dettagli['incompatibilita'] != 0:
                print(f"   🚫 Incompatibilità: {dettagli['incompatibilita']}")
            if dettagli['affinita'] != 0:
                print(f"   ✅ Affinità: {dettagli['affinita']}")
            if dettagli['genere_misto'] != 0:
                print(f"   ⚖️  Genere misto: {dettagli['genere_misto']}")
            if dettagli['posizione'] != 0:
                print(f"   📍 Posizione: {dettagli['posizione']}")

            # Note aggiuntive
            if info['note']:
                for nota in info['note']:
                    print(f"   💬 {nota}")

        print("=" * 60)

    def _trova_coppie_con_backtracking(self, studenti: List[Student], num_coppie_target: int,
                                        tutti_punteggi: List[Tuple]) -> Optional[List[Tuple]]:
        """
        Trova coppie usando algoritmo di BACKTRACKING per garantire soluzione se esiste.

        COME FUNZIONA:
        1. Prova a formare una coppia dalla lista ordinata per punteggio
        2. Marca gli studenti come "usati"
        3. RICORSIONE: prova a formare le coppie rimanenti
        4. Se fallisce → BACKTRACK: annulla la coppia e prova la successiva
        5. Se riesce → ritorna la soluzione trovata

        Args:
            studenti: Lista di studenti da abbinare
            num_coppie_target: Numero di coppie da formare
            tutti_punteggi: Lista di tuple (studente1, studente2, info_punteggio)
                           già ordinata per punteggio decrescente

        Returns:
            Lista di coppie trovate, oppure None se impossibile
        """
        print(f"   🔄 BACKTRACKING: Cerco {num_coppie_target} coppie tra {len(studenti)} studenti")

        # Crea set di studenti disponibili (per lookup veloce)
        studenti_disponibili = {s.get_nome_completo(): s for s in studenti}

        # Chiama funzione ricorsiva
        risultato = self._backtrack_ricorsivo(
            coppie_formate=[],
            studenti_disponibili=studenti_disponibili,
            tutti_punteggi=tutti_punteggi,
            num_target=num_coppie_target,
            profondita=0
        )

        if risultato:
            print(f"   ✅ BACKTRACKING: Soluzione trovata con {len(risultato)} coppie")
        else:
            print(f"   ❌ BACKTRACKING: Nessuna soluzione possibile")

        return risultato

    def _backtrack_ricorsivo(self, coppie_formate: List[Tuple],
                            studenti_disponibili: Dict[str, Student],
                            tutti_punteggi: List[Tuple],
                            num_target: int,
                            profondita: int) -> Optional[List[Tuple]]:
        """
        Funzione ricorsiva per il backtracking.

        LOGICA RICORSIVA:
        - Caso base: se abbiamo formato tutte le coppie necessarie → SUCCESSO
        - Caso ricorsivo: prova ogni coppia possibile e ricorri sui rimanenti
        - Backtrack automatico: se una scelta fallisce, il loop prova la successiva

        Args:
            coppie_formate: Coppie già formate finora (stack della ricorsione)
            studenti_disponibili: Dict di studenti ancora disponibili {cognome: Student}
            tutti_punteggi: Tutte le coppie possibili ordinate per punteggio
            num_target: Numero totale di coppie da formare
            profondita: Livello di ricorsione corrente (per debug)

        Returns:
            Lista completa di coppie se trovata, None se vicolo cieco
        """
        # CASO BASE: Abbiamo formato tutte le coppie necessarie!
        if len(coppie_formate) == num_target:
            print(f"{'  ' * profondita}   ✅ Soluzione completa trovata a profondità {profondita}")
            return coppie_formate

        # CONTROLLO MATEMATICO: Verifica che ci siano abbastanza studenti rimanenti
        # Se servono N coppie, servono almeno N*2 studenti disponibili
        coppie_rimanenti = num_target - len(coppie_formate)
        studenti_necessari = coppie_rimanenti * 2

        if len(studenti_disponibili) < studenti_necessari:
            # Non ci sono abbastanza studenti per formare le coppie rimanenti
            # Questo è un vicolo cieco matematicamente impossibile → backtrack immediato
            if profondita <= 3:
                print(f"{'  ' * profondita}   ⚠️ IMPOSSIBILE: servono {studenti_necessari} studenti "
                      f"per {coppie_rimanenti} coppie, ma ne rimangono solo {len(studenti_disponibili)}")
            return None

        # Debug: mostra progresso ogni 2 livelli per non intasare output
        if profondita % 2 == 0:
            print(f"{'  ' * profondita}   🔍 Livello {profondita}: {len(coppie_formate)}/{num_target} coppie formate, "
                  f"{len(studenti_disponibili)} studenti disponibili")

        # CASO RICORSIVO: Prova ogni coppia possibile con studenti disponibili
        tentativi_livello = 0
        for studente1, studente2, info_punteggio in tutti_punteggi:

            # Verifica che entrambi gli studenti siano ancora disponibili
            if studente1.get_nome_completo() in studenti_disponibili and studente2.get_nome_completo() in studenti_disponibili:
                tentativi_livello += 1

                # Debug dettagliato solo ai primi livelli
                if profondita <= 2:
                    print(f"{'  ' * profondita}   🔄 Tentativo {tentativi_livello}: "
                          f"{studente1.get_nome_completo()} + {studente2.get_nome_completo()} "
                          f"(punteggio: {info_punteggio['punteggio_totale']})")

                # PROVA questa coppia: rimuovi studenti dai disponibili
                nuovi_disponibili = studenti_disponibili.copy()
                del nuovi_disponibili[studente1.get_nome_completo()]
                del nuovi_disponibili[studente2.get_nome_completo()]

                # Aggiungi coppia al risultato parziale
                nuove_coppie = coppie_formate + [(studente1, studente2, info_punteggio)]

                # RICORSIONE: Prova a completare con studenti rimanenti
                risultato = self._backtrack_ricorsivo(
                    coppie_formate=nuove_coppie,
                    studenti_disponibili=nuovi_disponibili,
                    tutti_punteggi=tutti_punteggi,
                    num_target=num_target,
                    profondita=profondita + 1
                )

                # Se la ricorsione ha trovato una soluzione → propagala in su!
                if risultato is not None:
                    return risultato

                # Se arriviamo qui, questa coppia porta a un VICOLO CIECO
                # Il BACKTRACK è automatico: il loop continua e prova la coppia successiva
                if profondita <= 2:
                    print(f"{'  ' * profondita}   ❌ Coppia porta a vicolo cieco, backtrack...")

        # Se arriviamo qui, nessuna coppia disponibile ha portato a soluzione
        if profondita % 2 == 0:
            print(f"{'  ' * profondita}   ⬅️ Backtrack al livello {profondita - 1}")

        return None  # Ritorna None per triggerare backtrack nel livello superiore

    def imposta_genere_misto_obbligatorio(self, attivo: bool):
        """
        Imposta il flag per preferire coppie miste.
        NOTA: Non è più "obbligatorio" ma una PREFERENZA FORTE (+100 punti bonus).

        Args:
            attivo (bool): True = preferenza forte per coppie M+F, False = neutrale
        """
        self.genere_misto_obbligatorio = attivo
        # Nota: variabile mantiene nome originale per retrocompatibilità
        print(f"🎯 Preferenza genere misto: {'ATTIVA (+100 bonus)' if attivo else 'DISATTIVA (neutrale)'}")

    def _verifica_vincoli_sistema_possibili(self, studenti: List[Student]) -> bool:
        """
        Verifica se i vincoli assoluti di sistema sono matematicamente possibili.

        Args:
            studenti: Lista di tutti gli studenti da sistemare

        Returns:
            bool: True se vincoli rispettabili, False se impossibili
        """
        vincoli_ok = True

        # VERIFICA 1: Posizione "PRIMA" - conteggio studenti che la richiedono
        studenti_prima_fila = [s for s in studenti if s.nota_posizione == 'PRIMA']
        num_richieste_prima = len(studenti_prima_fila)

        if num_richieste_prima > 0:
            print(f"🔍 Verifica vincoli: {num_richieste_prima} studenti richiedono PRIMA fila")
            # NOTA: Verifica effettiva capienza sarà fatta in algoritmo.py con layout aula

        # VERIFICA 2: Genere misto obbligatorio - bilanciamento M/F
        if self.genere_misto_obbligatorio:
            maschi = [s for s in studenti if s.sesso == 'M']
            femmine = [s for s in studenti if s.sesso == 'F']
            num_maschi = len(maschi)
            num_femmine = len(femmine)

            print(f"🔍 Verifica genere misto: {num_maschi}M + {num_femmine}F")

            # Se un genere ha 0 studenti, impossibile fare solo coppie miste
            if num_maschi == 0 or num_femmine == 0:
                print(f"⚠️  ATTENZIONE: Genere misto impossibile (un genere assente)")
                vincoli_ok = False

            # Se differenza troppo grande, alcune coppie saranno stesso genere
            differenza = abs(num_maschi - num_femmine)
            if differenza > 1:
                print(f"⚠️  ATTENZIONE: {differenza} studenti dovranno formare coppie stesso genere")

        # VERIFICA 3: Incompatibilità assolute che renderebbero impossibili le coppie
        num_incomp_assolute = 0
        for s1 in studenti:
            for cognome, livello in s1.incompatibilita.items():
                if livello == 3:
                    num_incomp_assolute += 1

        if num_incomp_assolute > 0:
            print(f"🔍 Trovate {num_incomp_assolute} incompatibilità assolute (livello 3)")

        return vincoli_ok

class MotoreVincoliConfigurato(MotoreVincoli):
    """
    Estensione di MotoreVincoli che permette di configurare temporaneamente
    quali vincoli applicare per implementare il sistema a cascata.
    """

    def __init__(self):
        super().__init__()

        # Configurazione vincoli per tentativo corrente
        self.tentativo_corrente = 1
        self.blacklist_come_vincolo_assoluto = True

        # Controllo vincoli per livello (True = applica vincolo)
        self.applica_incompatibilita_1 = True
        self.applica_incompatibilita_2 = True
        self.applica_affinita_1 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

        # Vincoli SEMPRE attivi (mai rilassabili)
        # - incompatibilità 3 (sempre assoluta)
        # - posizione PRIMA (sempre assoluta)

    def configura_per_tentativo(self, numero_tentativo: int, info_blacklist=None):
        """
        Configura il motore per un tentativo specifico del sistema a cascata.

        Args:
            numero_tentativo (int): 1-4, progressione allentamento vincoli
            info_blacklist: Informazioni sulla blacklist per diagnostica
        """
        self.tentativo_corrente = numero_tentativo
        print(f"\n🔧 TENTATIVO {numero_tentativo}: Configurazione vincoli")

        if numero_tentativo == 1:
            # TENTATIVO 1: Tutti vincoli + blacklist FORTISSIMA
            self._configura_tentativo_1()

        elif numero_tentativo == 2:
            # TENTATIVO 2: Allenta vincoli DEBOLI (incomp 1, affinità 1)
            self._configura_tentativo_2()

        elif numero_tentativo == 3:
            # TENTATIVO 3: Allenta vincoli MEDI (incomp 2, affinità 2, ultima)
            self._configura_tentativo_3()

        elif numero_tentativo == 4:
            # TENTATIVO 4: Allenta TUTTO tranne assoluti (affinità 3, genere misto)
            self._configura_tentativo_4()

        else:
            raise ValueError(f"Tentativo {numero_tentativo} non valido (1-4)")

    def _configura_tentativo_1(self):
        """Tentativo 1: Configurazione standard + blacklist fortissima"""
        # Tutti i vincoli attivi
        self.applica_incompatibilita_1 = True
        self.applica_incompatibilita_2 = True
        self.applica_affinita_1 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

        # Blacklist come vincolo quasi-assoluto
        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Tutti vincoli attivi + blacklist FORTISSIMA")

    def _configura_tentativo_2(self):
        """Tentativo 2: Allenta vincoli deboli (incomp 1, affinità 1)"""
        # Disattiva vincoli DEBOLI
        self.applica_incompatibilita_1 = False  # Non penalizza più incomp livello 1
        self.applica_affinita_1 = False         # Non premia più affinità livello 1

        # Mantiene vincoli medi e forti
        self.applica_incompatibilita_2 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

        # Blacklist ancora molto forte
        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Disattivati: incompatibilità 1, affinità 1")

    def _configura_tentativo_3(self):
        """Tentativo 3: Allenta vincoli medi (incomp 2, affinità 2, ultima)"""
        # Disattiva vincoli DEBOLI (già disattivati) + MEDI
        self.applica_incompatibilita_1 = False
        self.applica_incompatibilita_2 = False  # NUOVO: disattiva incomp livello 2
        self.applica_affinita_1 = False
        self.applica_affinita_2 = False         # NUOVO: disattiva affinità livello 2
        self.applica_posizione_ultima = False   # NUOVO: ignora preferenza "ULTIMA"

        # Mantiene solo vincoli FORTI
        self.applica_affinita_3 = True
        self.applica_genere_misto_soft = True

        # Blacklist ancora forte ma meno assoluta
        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Disattivati: incompatibilità 1-2, affinità 1-2, posizione ULTIMA")

    def _configura_tentativo_4(self):
        """Tentativo 4: Allenta TUTTO tranne vincoli assoluti"""
        # Disattiva TUTTI i vincoli soft
        self.applica_incompatibilita_1 = False
        self.applica_incompatibilita_2 = False
        self.applica_affinita_1 = False
        self.applica_affinita_2 = False
        self.applica_affinita_3 = False         # NUOVO: disattiva anche affinità 3
        self.applica_posizione_ultima = False
        self.applica_genere_misto_soft = False  # NUOVO: disattiva genere misto

        # Blacklist diventa soft (penalità invece che blocco)
        self.blacklist_come_vincolo_assoluto = False

        print("   🚨 DISATTIVATO TUTTO tranne: incompatibilità 3, posizione PRIMA")
        print("   ⚠️  Blacklist ridotta a penalità soft")

    def calcola_punteggio_coppia(self, studente1: Student, studente2: Student) -> Dict:
        """
        Override che rispetta la configurazione del tentativo corrente.
        """
        # Chiama metodo padre per calcolo base
        risultato = super().calcola_punteggio_coppia(studente1, studente2)

        # Se coppia già vietata da vincoli assoluti, restituisci subito
        if risultato['valutazione'] == 'VIETATA':
            return risultato

        # MODIFICA PUNTEGGI in base alla configurazione tentativo
        self._applica_configurazione_tentativo(risultato, studente1, studente2)

        return risultato

    def _applica_configurazione_tentativo(self, risultato: Dict, studente1: Student, studente2: Student):
        """
        Modifica i punteggi in base alla configurazione del tentativo corrente.
        """
        dettagli = risultato['dettagli']

        # RIMUOVI contributi vincoli disattivati
        if not self.applica_incompatibilita_1 or not self.applica_incompatibilita_2:
            dettagli['incompatibilita'] = self._ricalcola_incompatibilita_configurata(studente1, studente2)

        if not self.applica_affinita_1 or not self.applica_affinita_2 or not self.applica_affinita_3:
            dettagli['affinita'] = self._ricalcola_affinita_configurata(studente1, studente2)

        if not self.applica_posizione_ultima:
            dettagli['posizione'] = 0  # Ignora preferenze posizione ULTIMA

        if not self.applica_genere_misto_soft:
            dettagli['genere_misto'] = 0  # Ignora bonus genere misto

        # RICALCOLA punteggio totale
        risultato['punteggio_totale'] = (
            dettagli['incompatibilita'] +
            dettagli['affinita'] +
            dettagli['genere_misto'] +
            dettagli['posizione']
        )

        # AGGIORNA valutazione
        self._aggiorna_valutazione_configurata(risultato)

    def _ricalcola_incompatibilita_configurata(self, studente1: Student, studente2: Student) -> int:
        """Ricalcola incompatibilità rispettando configurazione tentativo"""
        punteggio = 0

        # Controlla studente1 -> studente2
        if studente2.cognome in studente1.incompatibilita:
            livello = studente1.incompatibilita[studente2.cognome]
            if self._livello_incompatibilita_attivo(livello):
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        # Controlla studente2 -> studente1
        if studente1.cognome in studente2.incompatibilita:
            livello = studente2.incompatibilita[studente1.cognome]
            if self._livello_incompatibilita_attivo(livello):
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        return punteggio

    def _ricalcola_affinita_configurata(self, studente1: Student, studente2: Student) -> int:
        """Ricalcola affinità rispettando configurazione tentativo"""
        punteggio = 0

        # Controlla studente1 -> studente2
        if studente2.cognome in studente1.affinita:
            livello = studente1.affinita[studente2.cognome]
            if self._livello_affinita_attivo(livello):
                bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
                punteggio += bonus

        # Controlla studente2 -> studente1
        if studente1.cognome in studente2.affinita:
            livello = studente2.affinita[studente1.cognome]
            if self._livello_affinita_attivo(livello):
                bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
                punteggio += bonus

        return punteggio

    def _livello_incompatibilita_attivo(self, livello: int) -> bool:
        """Verifica se un livello di incompatibilità è attivo nel tentativo corrente"""
        if livello == 1:
            return self.applica_incompatibilita_1
        elif livello == 2:
            return self.applica_incompatibilita_2
        elif livello == 3:
            return True  # Incompatibilità 3 SEMPRE attiva (vincolo assoluto)
        return False

    def _livello_affinita_attivo(self, livello: int) -> bool:
        """Verifica se un livello di affinità è attivo nel tentativo corrente"""
        if livello == 1:
            return self.applica_affinita_1
        elif livello == 2:
            return self.applica_affinita_2
        elif livello == 3:
            return self.applica_affinita_3
        return False

    def _aggiorna_valutazione_configurata(self, risultato: Dict):
        """Aggiorna la valutazione qualitativa considerando configurazione"""
        punteggio = risultato['punteggio_totale']

        # Soglie adattate per tentativi permissivi
        if punteggio >= 200:
            risultato['valutazione'] = 'OTTIMA'
        elif punteggio >= 50:
            risultato['valutazione'] = 'BUONA'
        elif punteggio >= -50:
            risultato['valutazione'] = 'NEUTRALE'
        elif punteggio >= -200:
            risultato['valutazione'] = 'PROBLEMATICA'
        else:
            risultato['valutazione'] = 'CRITICA'

        # Nota speciale per tentativi con vincoli rilassati
        if self.tentativo_corrente > 1:
            risultato['note'].append(f"Valutazione TENTATIVO {self.tentativo_corrente} (vincoli rilassati)")
