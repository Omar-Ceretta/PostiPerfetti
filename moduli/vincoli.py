# -*- coding: utf-8 -*-
"""vincoli.py — punteggi di compatibilità e ricerca delle coppie.

Calcola la qualità degli abbinamenti e cerca una disposizione completa con
backtracking. I vincoli assoluti non vengono mai rilassati; quelli soft sono
applicati secondo una cascata di quattro tentativi. Il quarto usa ripartenze
casuali locali e riproducibili.

Con algoritmo.py costituisce il motore della modalità a coppie.
"""

from typing import List, Dict, Tuple, Optional
from moduli.studenti import Student
from moduli.casualita import crea_generatore, deriva_seed, risolvi_seed_principale

# I messaggi ricorsivi sono disattivati per evitare il costo di formattazione
# nei percorsi caldi. Il flag modifica soltanto la diagnostica.
DEBUG_BACKTRACKING = False

# Il limite impedisce che una blacklist quasi satura produca una ricerca
# combinatoria senza fine. Se scatta, il tentativo si arrende senza dichiarare
# che la soluzione non esista.
LIMITE_NODI_BACKTRACK_COPPIE = 200000

# La cronaca generale del motore è separata dai messaggi ricorsivi perché la
# stessa ricerca può essere invocata migliaia di volte durante la scelta del trio.
DEBUG_MOTORE = False

class MotoreVincoli:
    """Calcola i punteggi di compatibilità e cerca le coppie ammissibili."""

    def __init__(self):
        # I livelli 1 e 2 sono soft; il livello 3 viene escluso prima del punteggio.
        self.PESO_INCOMPATIBILITA = 100
        self.PESO_AFFINITA = 50
        self.PESO_POSIZIONE_ULTIMA = 10

        # Una coppia PRIMA/FISSO + ULTIMA non può soddisfare entrambe le
        # preferenze di fila; la penalità serve soltanto come spareggio.
        self.PESO_PRIMA_ULTIMA = 50

        self.MOLTIPLICATORI = {
            1: 1,
            2: 4,
            3: 20
        }

        self.genere_misto_obbligatorio = False

        # Ogni candidato usa casualità locale: nessuna operazione modifica
        # lo stato globale del modulo random.
        self.seed_candidato = None
        self._contatore_chiamate_casuali = 0
        self.chiamata_casuale_vincente = None
        self.ripartenza_vincente = None
        self.seed_ripartenza_vincente = None
        self.ripartenze_eseguite = 0

    def imposta_seed_candidato(self, seed_candidato) -> None:
        """Imposta il seed locale del candidato e azzera la diagnostica casuale."""
        self.seed_candidato = risolvi_seed_principale(seed_candidato)
        self._contatore_chiamate_casuali = 0
        self.chiamata_casuale_vincente = None
        self.ripartenza_vincente = None
        self.seed_ripartenza_vincente = None
        self.ripartenze_eseguite = 0

    def calcola_punteggio_coppia(self, studente1: Student, studente2: Student) -> Dict:
        """Calcola punteggio, valutazione e note per una coppia.

        La catena di punteggio ha tre strati:
        1. questo metodo applica i vincoli di base e produce il risultato grezzo;
        2. ``MotoreVincoliConfigurato`` rilassa i contributi soft del tentativo;
        3. i wrapper runtime applicano storico e blacklist.

        In produzione i wrapper storico e blacklist sono impilati. Nei tentativi
        1-3 una coppia già usata è esclusa; nel quarto riceve entrambe le penalità
        e resta selezionabile. Il comportamento sostiene sia la rotazione sia la
        corretta segnalazione dei riutilizzi.
        """
        risultato = {
            'punteggio_totale': 0,
            'dettagli': {
                'incompatibilita': 0,
                'affinita': 0,
                'genere_misto': 0,
                'posizione': 0
            },
            'valutazione': 'ACCETTABILE',
            'note': []
        }

        # L'incompatibilità di livello 3 è un veto e non entra nella cascata.
        if self._ha_incompatibilita_assoluta(studente1, studente2):
            risultato['punteggio_totale'] = -999999
            risultato['valutazione'] = 'VIETATA'
            risultato['note'].append('INCOMPATIBILITÀ ASSOLUTA (livello 3)')
            return risultato

        punteggio_incomp = self._calcola_incompatibilita_soft(studente1, studente2)
        risultato['dettagli']['incompatibilita'] = punteggio_incomp

        punteggio_aff = self._calcola_affinita(studente1, studente2)
        risultato['dettagli']['affinita'] = punteggio_aff

        punteggio_genere = self._calcola_genere_misto_soft(studente1, studente2)
        risultato['dettagli']['genere_misto'] = punteggio_genere

        punteggio_pos = self._calcola_posizione_soft(studente1, studente2)
        risultato['dettagli']['posizione'] = punteggio_pos

        risultato['punteggio_totale'] = (
            punteggio_incomp +
            punteggio_aff +
            punteggio_genere +
            punteggio_pos
        )

        if risultato['punteggio_totale'] >= 200:
            risultato['valutazione'] = 'OTTIMA'
        elif risultato['punteggio_totale'] >= 50:
            risultato['valutazione'] = 'BUONA'
        elif risultato['punteggio_totale'] >= -50:
            risultato['valutazione'] = 'ACCETTABILE'
        elif risultato['punteggio_totale'] >= -200:
            risultato['valutazione'] = 'PROBLEMATICA'
        else:
            risultato['valutazione'] = 'CRITICA'

        self._aggiungi_note_dettagliate(risultato, studente1, studente2)

        return risultato

    def _ha_incompatibilita_assoluta(self, studente1: Student, studente2: Student) -> bool:
        """Restituisce True se fra i due studenti esiste un livello 3."""

        if studente2.get_nome_completo() in studente1.incompatibilita:
            if studente1.incompatibilita[studente2.get_nome_completo()] == 3:
                return True

        if studente1.get_nome_completo() in studente2.incompatibilita:
            if studente2.incompatibilita[studente1.get_nome_completo()] == 3:
                return True

        return False

    def _calcola_incompatibilita_soft(self, studente1: Student, studente2: Student) -> int:
        """Calcola la penalità delle incompatibilità di livello 1 e 2."""
        punteggio = 0

        if studente2.get_nome_completo() in studente1.incompatibilita:
            livello = studente1.incompatibilita[studente2.get_nome_completo()]
            if livello in [1, 2]:
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        if studente1.get_nome_completo() in studente2.incompatibilita:
            livello = studente2.incompatibilita[studente1.get_nome_completo()]
            if livello in [1, 2]:
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        return punteggio

    def _calcola_affinita(self, studente1: Student, studente2: Student) -> int:
        """Calcola il bonus delle affinità dichiarate nelle due direzioni."""
        punteggio = 0

        if studente2.get_nome_completo() in studente1.affinita:
            livello = studente1.affinita[studente2.get_nome_completo()]
            bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
            punteggio += bonus

        if studente1.get_nome_completo() in studente2.affinita:
            livello = studente2.affinita[studente1.get_nome_completo()]
            bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
            punteggio += bonus

        return punteggio

    def _calcola_genere_misto_soft(self, studente1: Student, studente2: Student) -> int:
        """Premia le coppie miste quando la relativa preferenza è attiva."""

        if not self.genere_misto_obbligatorio:
            return 0

        if studente1.sesso != studente2.sesso:
            return 100
        else:
            return 0

    def _calcola_posizione_soft(self, studente1: Student, studente2: Student) -> int:
        """Valuta le preferenze di fila che non costituiscono un veto assoluto."""
        pos1 = studente1.nota_posizione
        pos2 = studente2.nota_posizione

        # PRIMA e FISSO appartengono al fronte dell'aula; ULTIMA richiede il fondo.
        ha_front = pos1 in ('PRIMA', 'FISSO') or pos2 in ('PRIMA', 'FISSO')
        ha_ultima = pos1 == 'ULTIMA' or pos2 == 'ULTIMA'
        if ha_front and ha_ultima:
            return -self.PESO_PRIMA_ULTIMA

        if pos1 == 'ULTIMA' and pos2 == 'ULTIMA':
            return self.PESO_POSIZIONE_ULTIMA

        if (pos1 == 'ULTIMA' and pos2 == 'NORMALE') or (pos1 == 'NORMALE' and pos2 == 'ULTIMA'):
            return 0

        if pos1 == 'NORMALE' and pos2 == 'NORMALE':
            return 0

        return 0

    def _aggiungi_note_dettagliate(self, risultato: Dict, studente1: Student, studente2: Student):
        """Aggiunge al risultato le note leggibili usate da report e statistiche."""
        note = risultato['note']

        if risultato['dettagli']['affinita'] > 0:
            aff1 = studente1.affinita.get(studente2.get_nome_completo(), 0)
            aff2 = studente2.affinita.get(studente1.get_nome_completo(), 0)

            max_aff = max(aff1, aff2)
            note.append(f"Affinità di livello {max_aff} tra {studente1.get_nome_completo()}-{studente2.get_nome_completo()}")

        if risultato['dettagli']['incompatibilita'] < 0:
            incomp1 = studente1.incompatibilita.get(studente2.get_nome_completo(), 0)
            incomp2 = studente2.incompatibilita.get(studente1.get_nome_completo(), 0)

            max_incomp = max(incomp1, incomp2)
            note.append(f"Incompatibilità di livello {max_incomp} tra {studente1.get_nome_completo()}-{studente2.get_nome_completo()}")

        if risultato['dettagli']['genere_misto'] > 0:
            note.append(f"Coppia mista {studente1.sesso}/{studente2.sesso}")

        if risultato['dettagli']['posizione'] > 0:
            note.append(f"Entrambi preferiscono ultima fila")

        if risultato['dettagli']['posizione'] < 0:
            note.append("Conflitto di fila: un allievo va davanti, l'altro in fondo")

        if studente1.nota_posizione == 'PRIMA' or studente2.nota_posizione == 'PRIMA':
            nomi_prima = []
            if studente1.nota_posizione == 'PRIMA':
                nomi_prima.append(studente1.get_nome_completo())
            if studente2.nota_posizione == 'PRIMA':
                nomi_prima.append(studente2.get_nome_completo())
            note.append(f"PRIMA FILA richiesta: {', '.join(nomi_prima)}")

    def trova_migliori_coppie(
        self,
        studenti: List[Student],
        num_coppie_desiderate: int = None,
        max_coppie_prima_fila: int | None = None
    ) -> List[Tuple]:
            """Cerca il numero richiesto di coppie con backtracking.

            Nei primi tre tentativi considera soltanto coppie lecite e mai usate. Nel
            quarto prova più ordini casuali riproducibili e conserva la soluzione col
            punteggio totale più alto.
            """
            if not studenti:
                return []

            if num_coppie_desiderate is None:
                num_coppie_desiderate = len(studenti) // 2

            if not self._verifica_vincoli_sistema_possibili(studenti):
                if DEBUG_MOTORE:
                    print("⚠️ ATTENZIONE: alcuni vincoli assoluti potrebbero essere impossibili da rispettare")

            if DEBUG_MOTORE:
                print(f"🧮 Calcolando coppie ottimali per {len(studenti)} studenti...")
                print(f"🎯 Target: {num_coppie_desiderate} coppie")

            tutti_punteggi = []

            for i in range(len(studenti)):
                for j in range(i + 1, len(studenti)):
                    studente1 = studenti[i]
                    studente2 = studenti[j]

                    punteggio_info = self.calcola_punteggio_coppia(studente1, studente2)

                    # Nei tentativi 1-3 le coppie blacklistate sono escluse dal
                    # grafo; nel quarto restano candidate con penalità soft.
                    if punteggio_info['valutazione'] not in ('VIETATA', 'BLACKLISTATA'):
                        tutti_punteggi.append((studente1, studente2, punteggio_info))

            if hasattr(self, 'tentativo_corrente') and self.tentativo_corrente == 4:
                if DEBUG_MOTORE:
                    print(f"   ⚖️ TENTATIVO 4: MULTI-TENTATIVO con minimizzazione ripetizioni")

                # L'indice distingue le molte ricerche casuali dello stesso candidato,
                # in particolare quelle eseguite mentre viene valutato il trio.
                self._contatore_chiamate_casuali += 1
                indice_chiamata = self._contatore_chiamate_casuali
                seed_candidato = risolvi_seed_principale(self.seed_candidato)
                self.seed_candidato = seed_candidato

                coppie_per_utilizzo = {}
                for coppia_info in tutti_punteggi:
                    utilizzi = self._conta_utilizzi_coppia(coppia_info[0], coppia_info[1])
                    if utilizzi not in coppie_per_utilizzo:
                        coppie_per_utilizzo[utilizzi] = []
                    coppie_per_utilizzo[utilizzi].append(coppia_info)

                gruppi_ordinati = sorted(coppie_per_utilizzo.keys())

                if DEBUG_MOTORE:
                    print(f"   📊 Distribuzione coppie per utilizzo:")
                    for gruppo in gruppi_ordinati:
                        print(f"      Usate {gruppo} volte: {len(coppie_per_utilizzo[gruppo])} coppie")

                NUM_TENTATIVI_RANDOM = 15
                miglior_soluzione = None
                miglior_punteggio_totale = float('-inf')

                for tentativo_random in range(NUM_TENTATIVI_RANDOM):
                    numero_ripartenza = tentativo_random + 1
                    seed_ripartenza = deriva_seed(
                        seed_candidato,
                        "coppie",
                        "chiamata", indice_chiamata,
                        "ripartenza", numero_ripartenza,
                    )
                    rng = crea_generatore(seed_ripartenza)
                    self.ripartenze_eseguite = numero_ripartenza

                    lista_tentativo = []
                    for gruppo in gruppi_ordinati:
                        coppie_gruppo = coppie_per_utilizzo[gruppo].copy()
                        if gruppo == 0:
                            rng.shuffle(coppie_gruppo)
                        else:
                            coppie_gruppo.sort(key=lambda x: x[2]['punteggio_totale'], reverse=True)
                        lista_tentativo.extend(coppie_gruppo)

                    soluzione = self._trova_coppie_con_backtracking(
                        studenti=studenti,
                        num_coppie_target=num_coppie_desiderate,
                        tutti_punteggi=lista_tentativo,
                        max_coppie_prima_fila=max_coppie_prima_fila
                    )

                    if soluzione:
                        punteggio_soluzione = sum(
                            info['punteggio_totale'] for _, _, info in soluzione
                        )

                        if DEBUG_MOTORE:
                            coppie_riutilizzate = sum(
                                1 for s1, s2, _ in soluzione
                                if self._conta_utilizzi_coppia(s1, s2) > 0
                            )
                            print(f"   🔄 Tentativo random {tentativo_random + 1}/{NUM_TENTATIVI_RANDOM}: "
                                  f"punteggio={punteggio_soluzione}, riutilizzate={coppie_riutilizzate}")

                        if punteggio_soluzione > miglior_punteggio_totale:
                            miglior_punteggio_totale = punteggio_soluzione
                            miglior_soluzione = soluzione
                            self.chiamata_casuale_vincente = indice_chiamata
                            self.ripartenza_vincente = numero_ripartenza
                            self.seed_ripartenza_vincente = seed_ripartenza
                            if DEBUG_MOTORE:
                                print(f"      ⭐ Nuova migliore soluzione!")

                if miglior_soluzione:
                    if DEBUG_MOTORE:
                        print(f"   ✅ Migliore soluzione trovata con punteggio: {miglior_punteggio_totale}")
                    return miglior_soluzione
                else:
                    if DEBUG_MOTORE:
                        print(f"   ❌ Nessuna soluzione trovata in {NUM_TENTATIVI_RANDOM} tentativi")
                    return []
            else:
                tutti_punteggi.sort(key=lambda x: x[2]['punteggio_totale'], reverse=True)

            if DEBUG_MOTORE:
                print(f"   🔄 Usando algoritmo BACKTRACKING per garantire soluzione se esiste...")

            coppie_selezionate = self._trova_coppie_con_backtracking(
                studenti=studenti,
                num_coppie_target=num_coppie_desiderate,
                tutti_punteggi=tutti_punteggi,
                max_coppie_prima_fila=max_coppie_prima_fila
            )

            if coppie_selezionate is None:
                if DEBUG_MOTORE:
                    print(f"   ❌ BACKTRACKING: Nessuna soluzione trovata")
                return []

            if DEBUG_MOTORE:
                print(f"✅ Trovate {len(coppie_selezionate)} coppie ottimali")
            return coppie_selezionate

    def _conta_utilizzi_coppia(self, studente1, studente2):
        """Restituisce il numero di utilizzi storici della coppia."""

        if not hasattr(self, '_config_app_ref') or not self._config_app_ref:
            return 0

        coppie_usate = self._config_app_ref.config_data.get("coppie_da_evitare", [])

        # La blacklist non cambia durante un'assegnazione: un indice per coppia
        # evita scansioni lineari ripetute nelle quindici ripartenze.
        cache = getattr(self, '_cache_utilizzi', None)
        if cache is None or cache[0] is not coppie_usate or cache[1] != len(coppie_usate):
            indice = {}
            for coppia_usata in coppie_usate:
                studenti = coppia_usata.get("studenti", [])
                if len(studenti) != 2:
                    continue
                chiave = frozenset((studenti[0], studenti[1]))

                # La prima occorrenza replica il comportamento della precedente
                # scansione; una voce priva di contatore vale almeno un utilizzo.
                if chiave not in indice:
                    indice[chiave] = coppia_usata.get("volte_usata", 1)

            self._cache_utilizzi = (coppie_usate, len(coppie_usate), indice)
            cache = self._cache_utilizzi

        nomi_coppia = frozenset((studente1.get_nome_completo(), studente2.get_nome_completo()))
        return cache[2].get(nomi_coppia, 0)

    def _trova_coppie_con_backtracking(
        self,
        studenti: List[Student],
        num_coppie_target: int,
        tutti_punteggi: List[Tuple],
        max_coppie_prima_fila: int | None = None
    ) -> Optional[List[Tuple]]:
        """Avvia una ricerca completa delle coppie ammissibili.

        Ogni invocazione dispone di un proprio budget di nodi; ``None`` indica che
        nessuna soluzione è stata trovata entro i limiti della ricerca.
        """
        if DEBUG_MOTORE:
            print(f"   🔄 BACKTRACKING: Cerco {num_coppie_target} coppie tra {len(studenti)} studenti")

        studenti_disponibili = {s.get_nome_completo(): s for s in studenti}

        # La lista funge da contatore mutabile condiviso da tutta la ricorsione.
        contatore_nodi = [0]

        risultato = self._backtrack_ricorsivo(
            coppie_formate=[],
            studenti_disponibili=studenti_disponibili,
            tutti_punteggi=tutti_punteggi,
            num_target=num_coppie_target,
            profondita=0,
            contatore_nodi=contatore_nodi,
            max_coppie_prima_fila=max_coppie_prima_fila,
            coppie_prima_usate=0
        )

        # Il superamento del budget segnala un abbandono, non una prova di
        # inesistenza; algoritmo.py userà questa distinzione nella cascata.
        if contatore_nodi[0] > LIMITE_NODI_BACKTRACK_COPPIE:
            self.tetto_nodi_scattato = True
            if DEBUG_MOTORE:
                print(f"   ⛔ TETTO-NODI raggiunto ({contatore_nodi[0]} nodi): tentativo arreso")

        if DEBUG_MOTORE:
            if risultato:
                print(f"   ✅ BACKTRACKING: Soluzione trovata con {len(risultato)} coppie")
            else:
                print(f"   ❌ BACKTRACKING: Nessuna soluzione possibile")

        return risultato

    def _backtrack_ricorsivo(
        self,
        coppie_formate: List[Tuple],
        studenti_disponibili: Dict[str, Student],
        tutti_punteggi: List[Tuple],
        num_target: int,
        profondita: int,
        contatore_nodi: Optional[List[int]] = None,
        max_coppie_prima_fila: int | None = None,
        coppie_prima_usate: int = 0
    ) -> Optional[List[Tuple]]:
        """Completa ricorsivamente le coppie e torna indietro dai vicoli ciechi.

        La potatura considera sia il numero di studenti rimasti sia la capienza dei
        gruppi di prima fila.
        """

        # Il caso base precede il controllo del budget: una soluzione trovata
        # esattamente sul limite viene comunque accettata.
        if len(coppie_formate) == num_target:
            if DEBUG_BACKTRACKING:
                print(f"{'  ' * profondita}   ✅ Soluzione completa trovata a profondità {profondita}")
            return coppie_formate

        if contatore_nodi is not None:
            contatore_nodi[0] += 1
            if contatore_nodi[0] > LIMITE_NODI_BACKTRACK_COPPIE:
                return None

        coppie_rimanenti = num_target - len(coppie_formate)
        studenti_necessari = coppie_rimanenti * 2

        if len(studenti_disponibili) < studenti_necessari:
            if DEBUG_BACKTRACKING and profondita <= 3:
                print(f"{'  ' * profondita}   ⚠️ IMPOSSIBILE: servono {studenti_necessari} studenti "
                      f"per {coppie_rimanenti} coppie, ma ne rimangono solo {len(studenti_disponibili)}")
            return None

        # Ogni coppia che contiene almeno un PRIMA consuma un gruppo frontale.
        # Il minimo teorico consente di potare subito i rami senza capienza.
        if max_coppie_prima_fila is not None:
            slot_prima_rimanenti = (
                max_coppie_prima_fila - coppie_prima_usate
            )

            if slot_prima_rimanenti < 0:
                return None

            studenti_prima_rimanenti = sum(
                1
                for studente in studenti_disponibili.values()
                if studente.nota_posizione == 'PRIMA'
            )

            gruppi_minimi_necessari = (
                studenti_prima_rimanenti + 1
            ) // 2

            if gruppi_minimi_necessari > slot_prima_rimanenti:
                return None

        if DEBUG_BACKTRACKING and profondita % 2 == 0:
            print(f"{'  ' * profondita}   🔍 Livello {profondita}: {len(coppie_formate)}/{num_target} coppie formate, "
                  f"{len(studenti_disponibili)} studenti disponibili")

        tentativi_livello = 0
        for studente1, studente2, info_punteggio in tutti_punteggi:
            if studente1.get_nome_completo() in studenti_disponibili and studente2.get_nome_completo() in studenti_disponibili:
                tentativi_livello += 1

                if DEBUG_BACKTRACKING and profondita <= 2:
                    print(f"{'  ' * profondita}   🔄 Tentativo {tentativi_livello}: "
                          f"{studente1.get_nome_completo()} + {studente2.get_nome_completo()} "
                          f"(punteggio: {info_punteggio['punteggio_totale']})")

                coppia_richiede_prima = (
                    studente1.nota_posizione == 'PRIMA'
                    or studente2.nota_posizione == 'PRIMA'
                )

                nuove_coppie_prima_usate = (
                    coppie_prima_usate
                    + (1 if coppia_richiede_prima else 0)
                )

                if (
                    max_coppie_prima_fila is not None
                    and nuove_coppie_prima_usate
                    > max_coppie_prima_fila
                ):
                    continue

                nuovi_disponibili = studenti_disponibili.copy()
                del nuovi_disponibili[studente1.get_nome_completo()]
                del nuovi_disponibili[studente2.get_nome_completo()]

                nuove_coppie = coppie_formate + [(studente1, studente2, info_punteggio)]

                risultato = self._backtrack_ricorsivo(
                    coppie_formate=nuove_coppie,
                    studenti_disponibili=nuovi_disponibili,
                    tutti_punteggi=tutti_punteggi,
                    num_target=num_target,
                    profondita=profondita + 1,
                    contatore_nodi=contatore_nodi,
                    max_coppie_prima_fila=max_coppie_prima_fila,
                    coppie_prima_usate=nuove_coppie_prima_usate
                )

                if risultato is not None:
                    return risultato

                if DEBUG_BACKTRACKING and profondita <= 2:
                    print(f"{'  ' * profondita}   ❌ Coppia porta a vicolo cieco, backtrack...")

        if DEBUG_BACKTRACKING and profondita % 2 == 0:
            print(f"{'  ' * profondita}   ⬅️ Backtrack al livello {profondita - 1}")

        return None

    def imposta_genere_misto_obbligatorio(self, attivo: bool):
        """Attiva o disattiva il bonus per le coppie miste."""
        self.genere_misto_obbligatorio = attivo

        print(f"🎯 Preferenza genere misto: {'ATTIVA (+100 bonus)' if attivo else 'DISATTIVA (neutrale)'}")

    def _verifica_vincoli_sistema_possibili(self, studenti: List[Student]) -> bool:
        """Esegue controlli preliminari sui vincoli di sistema."""
        vincoli_ok = True

        studenti_prima_fila = [s for s in studenti if s.nota_posizione == 'PRIMA']
        num_richieste_prima = len(studenti_prima_fila)

        if num_richieste_prima > 0 and DEBUG_MOTORE:
            print(f"🔍 Verifica vincoli: {num_richieste_prima} studenti richiedono PRIMA fila")

        if self.genere_misto_obbligatorio:
            maschi = [s for s in studenti if s.sesso == 'M']
            femmine = [s for s in studenti if s.sesso == 'F']
            num_maschi = len(maschi)
            num_femmine = len(femmine)

            if DEBUG_MOTORE:
                print(f"🔍 Verifica genere misto: {num_maschi}M + {num_femmine}F")

            if num_maschi == 0 or num_femmine == 0:
                if DEBUG_MOTORE:
                    print(f"⚠️  ATTENZIONE: Genere misto impossibile (un genere assente)")
                vincoli_ok = False

            differenza = abs(num_maschi - num_femmine)
            if differenza > 1 and DEBUG_MOTORE:
                print(f"⚠️  ATTENZIONE: {differenza} studenti dovranno formare coppie stesso genere")

        num_incomp_assolute = 0
        for s1 in studenti:
            for nome_completo, livello in s1.incompatibilita.items():
                if livello == 3:
                    num_incomp_assolute += 1

        if num_incomp_assolute > 0 and DEBUG_MOTORE:
            print(f"🔍 Trovate {num_incomp_assolute} incompatibilità assolute (livello 3)")

        return vincoli_ok

class MotoreVincoliConfigurato(MotoreVincoli):
    """Applica la cascata dei tentativi e memorizza i punteggi del tentativo corrente."""

    def __init__(self):
        super().__init__()

        # La cache vale soltanto entro un tentativo e non include i wrapper
        # di blacklist o storico applicati successivamente.
        self._cache_punteggi = {}

        self.tentativo_corrente = 1
        self.blacklist_come_vincolo_assoluto = True

        self.applica_incompatibilita_1 = True
        self.applica_incompatibilita_2 = True
        self.applica_affinita_1 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

    def configura_per_tentativo(self, numero_tentativo: int):
        """Configura i vincoli soft applicati nel tentativo indicato."""
        self.tentativo_corrente = numero_tentativo

        self._cache_punteggi = {}

        # Se una ricerca supera il budget, il fallimento del tentativo non è
        # una dimostrazione matematica e la cascata non può saltare i successivi.
        self.tetto_nodi_scattato = False

        print(f"\n🔧 TENTATIVO {numero_tentativo}: Configurazione vincoli")

        if numero_tentativo == 1:
            self._configura_tentativo_1()

        elif numero_tentativo == 2:
            self._configura_tentativo_2()

        elif numero_tentativo == 3:
            self._configura_tentativo_3()

        elif numero_tentativo == 4:
            self._configura_tentativo_4()

        else:
            raise ValueError(f"Tentativo {numero_tentativo} non valido (1-4)")

    def _configura_tentativo_1(self):
        """Attiva tutti i vincoli soft e blocca le coppie già usate."""

        self.applica_incompatibilita_1 = True
        self.applica_incompatibilita_2 = True
        self.applica_affinita_1 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Tutti vincoli attivi + blacklist FORTISSIMA")

    def _configura_tentativo_2(self):
        """Disattiva incompatibilità e affinità di livello 1."""

        self.applica_incompatibilita_1 = False
        self.applica_affinita_1 = False

        self.applica_incompatibilita_2 = True
        self.applica_affinita_2 = True
        self.applica_affinita_3 = True
        self.applica_posizione_ultima = True
        self.applica_genere_misto_soft = True

        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Disattivati: incompatibilità 1, affinità 1")

    def _configura_tentativo_3(self):
        """Disattiva i vincoli medi e la preferenza ULTIMA."""

        self.applica_incompatibilita_1 = False
        self.applica_incompatibilita_2 = False
        self.applica_affinita_1 = False
        self.applica_affinita_2 = False
        self.applica_posizione_ultima = False

        self.applica_affinita_3 = True
        self.applica_genere_misto_soft = True

        self.blacklist_come_vincolo_assoluto = True

        print("   📉 Disattivati: incompatibilità 1-2, affinità 1-2, posizione ULTIMA")

    def _configura_tentativo_4(self):
        """Mantiene soltanto i vincoli assoluti e rende soft la blacklist."""

        self.applica_incompatibilita_1 = False
        self.applica_incompatibilita_2 = False
        self.applica_affinita_1 = False
        self.applica_affinita_2 = False
        self.applica_affinita_3 = False
        self.applica_posizione_ultima = False
        self.applica_genere_misto_soft = False

        self.blacklist_come_vincolo_assoluto = False

        print("   🚨 DISATTIVATO TUTTO tranne: incompatibilità 3, posizione PRIMA")
        print("   📌 Posizione FISSO: invariata (gestita separatamente)")
        print("   ⚠️  Blacklist ridotta a penalità soft")

    def calcola_punteggio_coppia(self, studente1: Student, studente2: Student) -> Dict:
        """Calcola il punteggio secondo la configurazione del tentativo.

        La cache contiene soltanto lo strato configurato, non le penalità applicate
        dai wrapper successivi. Ogni risultato viene quindi restituito in copia.
        """

        # La chiave conserva l'ordine perché le note includono i nomi e il genere
        # nello stesso ordine degli argomenti, pur avendo punteggi simmetrici.
        chiave_cache = (id(studente1), id(studente2))
        memorizzato = self._cache_punteggi.get(chiave_cache)
        if memorizzato is not None:
            return self._copia_risultato(memorizzato)

        risultato = super().calcola_punteggio_coppia(studente1, studente2)

        if risultato['valutazione'] != 'VIETATA':
            self._applica_configurazione_tentativo(risultato, studente1, studente2)

        # I wrapper successivi modificano il dizionario: la cache conserva
        # l'originale configurato e ogni chiamante riceve una copia.
        self._cache_punteggi[chiave_cache] = risultato
        return self._copia_risultato(risultato)

    @staticmethod
    def _copia_risultato(risultato: Dict) -> Dict:
        """Copia le parti mutabili del risultato conservato in cache."""
        return {
            'punteggio_totale': risultato['punteggio_totale'],
            'dettagli': dict(risultato['dettagli']),
            'valutazione': risultato['valutazione'],
            'note': list(risultato['note']),
        }

    def _applica_configurazione_tentativo(self, risultato: Dict, studente1: Student, studente2: Student):
        """Rimuove i contributi disattivati e aggiorna la valutazione."""
        dettagli = risultato['dettagli']

        if not self.applica_incompatibilita_1 or not self.applica_incompatibilita_2:
            dettagli['incompatibilita'] = self._ricalcola_incompatibilita_configurata(studente1, studente2)

        if not self.applica_affinita_1 or not self.applica_affinita_2 or not self.applica_affinita_3:
            dettagli['affinita'] = self._ricalcola_affinita_configurata(studente1, studente2)

        if not self.applica_posizione_ultima:
            dettagli['posizione'] = 0

        if not self.applica_genere_misto_soft:
            dettagli['genere_misto'] = 0

        risultato['punteggio_totale'] = (
            dettagli['incompatibilita'] +
            dettagli['affinita'] +
            dettagli['genere_misto'] +
            dettagli['posizione']
        )

        self._aggiorna_valutazione_configurata(risultato, studente1, studente2)

    def _ricalcola_incompatibilita_configurata(self, studente1: Student, studente2: Student) -> int:
        """Ricalcola le incompatibilità ancora attive."""
        punteggio = 0

        if studente2.get_nome_completo() in studente1.incompatibilita:
            livello = studente1.incompatibilita[studente2.get_nome_completo()]
            if self._livello_incompatibilita_attivo(livello):
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        if studente1.get_nome_completo() in studente2.incompatibilita:
            livello = studente2.incompatibilita[studente1.get_nome_completo()]
            if self._livello_incompatibilita_attivo(livello):
                penalita = self.PESO_INCOMPATIBILITA * self.MOLTIPLICATORI[livello]
                punteggio -= penalita

        return punteggio

    def _ricalcola_affinita_configurata(self, studente1: Student, studente2: Student) -> int:
        """Ricalcola le affinità ancora attive."""
        punteggio = 0

        if studente2.get_nome_completo() in studente1.affinita:
            livello = studente1.affinita[studente2.get_nome_completo()]
            if self._livello_affinita_attivo(livello):
                bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
                punteggio += bonus

        if studente1.get_nome_completo() in studente2.affinita:
            livello = studente2.affinita[studente1.get_nome_completo()]
            if self._livello_affinita_attivo(livello):
                bonus = self.PESO_AFFINITA * self.MOLTIPLICATORI[livello]
                punteggio += bonus

        return punteggio

    def _livello_incompatibilita_attivo(self, livello: int) -> bool:
        """Verifica se il livello di incompatibilità è attivo."""
        if livello == 1:
            return self.applica_incompatibilita_1
        elif livello == 2:
            return self.applica_incompatibilita_2
        elif livello == 3:
            return True
        return False

    def _livello_affinita_attivo(self, livello: int) -> bool:
        """Verifica se il livello di affinità è attivo."""
        if livello == 1:
            return self.applica_affinita_1
        elif livello == 2:
            return self.applica_affinita_2
        elif livello == 3:
            return self.applica_affinita_3
        return False

    def _livello_incompatibilita_reale(self, studente1: Student, studente2: Student) -> int:
        """Legge il massimo livello di incompatibilità direttamente dagli studenti.

        Il dato reale resta disponibile anche quando un tentativo permissivo azzera
        la penalità usata per scegliere la disposizione.
        """
        a_vs_b = studente1.incompatibilita.get(studente2.get_nome_completo(), 0)
        b_vs_a = studente2.incompatibilita.get(studente1.get_nome_completo(), 0)
        return max(a_vs_b, b_vs_a)

    def _aggiorna_valutazione_configurata(self, risultato: Dict,
                                          studente1: Student = None,
                                          studente2: Student = None):
        """Aggiorna l’etichetta qualitativa senza nascondere incompatibilità tollerate."""
        punteggio = risultato['punteggio_totale']

        if punteggio >= 200:
            risultato['valutazione'] = 'OTTIMA'
        elif punteggio >= 50:
            risultato['valutazione'] = 'BUONA'
        elif punteggio >= -50:
            risultato['valutazione'] = 'ACCETTABILE'
        elif punteggio >= -200:
            risultato['valutazione'] = 'PROBLEMATICA'
        else:
            risultato['valutazione'] = 'CRITICA'

        # Un tentativo permissivo può azzerare la penalità per scegliere, ma
        # l'etichetta mostrata all'utente deve continuare a dichiarare il vincolo.
        if studente1 is not None and studente2 is not None:
            livello_reale = self._livello_incompatibilita_reale(studente1, studente2)
            if livello_reale == 2:
                risultato['valutazione'] = 'CRITICA'
            elif livello_reale == 1:
                if risultato['valutazione'] != 'CRITICA':
                    risultato['valutazione'] = 'PROBLEMATICA'

        if self.tentativo_corrente > 1:
            risultato['note'].append(f"Valutazione TENTATIVO {self.tentativo_corrente} (vincoli rilassati)")
