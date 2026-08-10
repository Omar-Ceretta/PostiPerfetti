# -*- coding: utf-8 -*-
"""
Motore di assegnazione per la modalità a coppie.

Coordina la formazione dei gruppi, il posizionamento nell'aula e la diagnostica
dei fallimenti. Applica quattro tentativi progressivi: i primi tre sono
deterministici ed escludono i riusi; il quarto ammette ripartenze casuali
riproducibili e penalizza le coppie già utilizzate. Delega i punteggi a
``vincoli.py`` e la geometria a ``aula.py``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import time
from typing import List, Optional
from moduli.studenti import Student
from moduli.aula import ConfigurazioneAula

# Quando è disattivato, DEBUG_MOTORE evita anche il costo di costruzione dei messaggi.
from moduli.vincoli import MotoreVincoliConfigurato, DEBUG_MOTORE
from moduli.diagnostica_ricerca import messaggio_motore
from moduli.lingua import quantita


class AssegnatorePosti:
    """Coordina formazione dei gruppi, posizionamento e diagnostica."""

    def __init__(self, diagnostica=None):
        self.diagnostica = diagnostica
        self.motore_vincoli = MotoreVincoliConfigurato(diagnostica=diagnostica)
        self.configurazione_aula = None
        self.studenti = []
        self.coppie_formate = []
        self.studenti_singoli = []

        # Stato del blocco FISSO e del suo vicino diretto.
        self.studente_fisso = None
        self.gruppo_adiacente_fisso = None
        self.nome_adiacente_fisso = None

        # Unico conteggio statistico consumato a valle.
        self.stats = {'coppie_riutilizzate': 0}

        # La GUI usa questo dizionario per spiegare un fallimento.
        self.report_fallimento = None

        # Metadati sufficienti a riprodurre il candidato.
        self.seed_principale = None
        self.seed_candidato = None
        self.contesto_casuale = {}

        # Misure diagnostiche; non influenzano le scelte del motore.
        self.durate_tentativi = {}

    def imposta_contesto_casuale(self, seed_principale, seed_candidato,
                                 contesto=None) -> None:
        """Registra i seed dell'operazione e configura il generatore locale."""
        self.seed_principale = seed_principale
        self.seed_candidato = seed_candidato
        self.contesto_casuale = dict(contesto or {})
        self.motore_vincoli.imposta_seed_candidato(seed_candidato)

    def esporta_metadati_casualita(self) -> dict:
        """Restituisce i dati necessari a diagnosticare o riprodurre il caso."""
        motore = self.motore_vincoli
        return {
            "seed_principale": self.seed_principale,
            "modalita": "coppie",
            "contesto": dict(self.contesto_casuale),
            "seed_candidato": self.seed_candidato,
            "tentativo": getattr(motore, "tentativo_corrente", None),
            "chiamata_casuale": getattr(
                motore, "chiamata_casuale_vincente", None
            ),
            "ripartenza": getattr(motore, "ripartenza_vincente", None),
            "seed_ripartenza": getattr(
                motore, "seed_ripartenza_vincente", None
            ),
            "ripartenze_eseguite": getattr(
                motore, "ripartenze_eseguite", 0
            ),
        }

    def esporta_diagnostica(self) -> dict | None:
        """Restituisce la diagnostica strutturata, se esplicitamente attivata."""
        if self.diagnostica is None:
            return None
        return self.diagnostica.esporta()

    def esegui_assegnazione_completa(self, studenti: List[Student], configurazione_aula: ConfigurazioneAula, modalita_trio: str = 'auto', studente_fisso: Optional[Student] = None, tentativo_iniziale: int = 1) -> bool:
        """
        Esegue formazione dei gruppi, posizionamento e calcolo delle statistiche.

        L'eventuale studente FISSO viene collocato prima della cascata ed escluso
        dalla formazione delle coppie. Restituisce ``True`` soltanto quando tutti gli
        studenti rispettano anche i vincoli fisici del layout.
        """
        if self.diagnostica is not None:
            self.diagnostica.evento(
                "assegnazione_inizio",
                modalita="coppie",
                seed_principale=self.seed_principale,
                seed_candidato=self.seed_candidato,
                studenti=len(studenti),
                tentativo_iniziale=tentativo_iniziale,
            )
        messaggio_motore("🚀 INIZIO ASSEGNAZIONE AUTOMATICA")
        messaggio_motore("=" * 50)
        if self.seed_principale is not None:
            messaggio_motore(
                f"🎲 Seed principale: {self.seed_principale} | "
                f"seed candidato: {self.seed_candidato} | "
                f"contesto: {self.contesto_casuale}"
            )

        self.studenti = studenti
        self.configurazione_aula = configurazione_aula

        self.modalita_trio = modalita_trio

        # Il FISSO viene collocato prima che il motore lavori sui rimanenti.
        if studente_fisso is not None:
            messaggio_motore(f"\n📌 STEP 0: Gestione studente FISSO...")
            if not self._gestisci_studente_fisso(studente_fisso):
                return False
        else:
            self.studente_fisso = None
            self.gruppo_adiacente_fisso = None
            messaggio_motore(f"\n📌 STEP 0: Nessuno studente FISSO — flusso standard")

        if not self._verifica_capienza():

            self.report_fallimento = (
                self._costruisci_report_diagnostico()
            )
            return False

        messaggio_motore("\n📝 STEP 2: Formazione coppie ottimali...")

        if not self._forma_coppie_ottimali(tentativo_iniziale):
            return False

        messaggio_motore("\n📝 STEP 3: Assegnazione posizioni...")
        if not self._assegna_posizioni_intelligenti():

            if self.report_fallimento is None:
                self.report_fallimento = (
                    self._costruisci_report_diagnostico()
                )
            return False

        messaggio_motore("\n📊 STEP 4: Calcolo statistiche...")
        self._conta_coppie_riutilizzate()

        messaggio_motore("\n📊 STEP 5: Ottimizzazione layout...")
        self.configurazione_aula.rimuovi_banchi_vuoti()

        messaggio_motore("\n🎉 ASSEGNAZIONE COMPLETATA CON SUCCESSO!")
        if self.diagnostica is not None:
            self.diagnostica.evento(
                "assegnazione_fine",
                modalita="coppie",
                successo=True,
                tentativo=getattr(self.motore_vincoli, "tentativo_corrente", None),
                coppie=len(self.coppie_formate),
                trio=bool(getattr(self, "trio_identificato", None)),
            )
        return True

    def _verifica_capienza(self) -> bool:
        """Verifica che il layout disponga di un posto per ogni studente."""
        num_studenti = len(self.studenti)
        posti_disponibili = self.configurazione_aula.posti_disponibili

        messaggio_motore(f"👥 Studenti da sistemare: {num_studenti}")
        messaggio_motore(f"🪑 Posti disponibili: {posti_disponibili}")

        if num_studenti > posti_disponibili:
            messaggio_motore(f"❌ ERRORE: Non ci sono abbastanza posti!")
            messaggio_motore(f"   Servono {num_studenti - posti_disponibili} posti aggiuntivi")
            return False

        if num_studenti < posti_disponibili:
            messaggio_motore(f"ℹ️  INFO: Ci saranno {posti_disponibili - num_studenti} posti liberi")

        messaggio_motore("✅ Capienza verificata")
        return True

    def _forma_coppie_ottimali(self, tentativo_iniziale: int = 1) -> bool:
        """Forma coppie ed eventuale trio mediante quattro tentativi progressivi."""
        num_studenti = len(self.studenti)

        messaggio_motore(f"\n🔥 SISTEMA A CASCATA - PIPELINE FORMAZIONE COPPIE")
        messaggio_motore("=" * 60)
        messaggio_motore(f"📊 Studenti totali: {num_studenti}")
        messaggio_motore(f"🎯 PRIORITÀ: Formare NUOVE coppie (evitare blacklist)")

        self.gestisce_trio = (num_studenti % 2 == 1)

        if self.gestisce_trio:
            num_coppie = (num_studenti - 3) // 2
            messaggio_motore(f"🔢 Numero dispari: {num_coppie} coppie + 1 trio (3 studenti)")
        else:
            num_coppie = num_studenti // 2
            messaggio_motore(f"🔢 Numero pari: {num_coppie} coppie")

        self.trio_identificato = None

        self.durate_tentativi = {}

        tentativo_iniziale = max(1, min(4, tentativo_iniziale))

        # Un fallimento esaustivo al T1 prova impossibili anche T2 e T3:
        # hanno lo stesso grafo dei candidati e non consumano casualità.
        salta_t2_t3 = False

        for tentativo in range(tentativo_iniziale, 5):

            if salta_t2_t3 and tentativo in (2, 3):
                messaggio_motore(f"\n⏭️ TENTATIVO {tentativo} SALTATO (il T1 ha dimostrato l'inesistenza: ramo morto)")
                continue

            # Il cronometro comprende configurazione, ricerca e penalità.
            _t_inizio_tentativo = time.perf_counter()
            _t_inizio_tentativo_ns = time.perf_counter_ns()
            if self.diagnostica is not None:
                self.diagnostica.evento(
                    "tentativo_inizio",
                    modalita="coppie",
                    tentativo=tentativo,
                    seed_candidato=self.seed_candidato,
                )

            messaggio_motore(f"\n{'='*20} TENTATIVO {tentativo} {'='*20}")

            self.motore_vincoli.configura_per_tentativo(tentativo)

            if hasattr(self, 'config_app'):
                self._applica_penalita_blacklist_tentativo(tentativo)

            risultato_tentativo = self._prova_formazione_coppie_completa(num_coppie, tentativo)

            self.durate_tentativi[tentativo] = time.perf_counter() - _t_inizio_tentativo
            if self.diagnostica is not None:
                self.diagnostica.evento(
                    "tentativo_fine",
                    modalita="coppie",
                    tentativo=tentativo,
                    successo=bool(risultato_tentativo),
                    durata_ns=time.perf_counter_ns() - _t_inizio_tentativo_ns,
                    tetto_nodi=bool(getattr(
                        self.motore_vincoli, "tetto_nodi_scattato", False
                    )),
                )

            if risultato_tentativo:
                messaggio_motore(f"✅ SUCCESSO TENTATIVO {tentativo}!")
                return True
            else:
                messaggio_motore(f"❌ TENTATIVO {tentativo} FALLITO")

                # Il salto è ammesso solo se la ricerca non si è fermata al tetto.
                if tentativo == 1 and not getattr(self.motore_vincoli,
                                                  'tetto_nodi_scattato', True):
                    salta_t2_t3 = True

                if tentativo < 4:
                    self._mostra_motivi_fallimento_tentativo(tentativo)
                    messaggio_motore(f"🔄 Passando al tentativo {tentativo + 1}...")

        messaggio_motore(f"\n🚨 TUTTI I TENTATIVI FALLITI - GENERAZIONE REPORT DIAGNOSTICO")
        self._genera_report_fallimento_completo()
        return False

    def _calcola_max_coppie_prima_fila(
        self,
        trio_in_prima_fila: bool
    ) -> int:
        """
        Restituisce quante coppie entrano nella prima fila dopo avere riservato i
        posti del FISSO e dell'eventuale trio.
        """
        banchi_per_fila = (
            self.configurazione_aula.get_banchi_per_fila()
        )

        if not banchi_per_fila:
            return 0

        posti_riservati = 0

        if self.studente_fisso is not None:
            posti_riservati += 1

        if trio_in_prima_fila:
            posti_riservati += 3

        posti_per_coppie = max(
            0,
            len(banchi_per_fila[0]) - posti_riservati
        )

        return posti_per_coppie // 2

    def _prova_formazione_coppie_completa(
        self,
        num_coppie_target: int,
        tentativo: int
    ) -> bool:
        """Prova a formare tutti i gruppi richiesti con il tentativo corrente."""
        messaggio_motore(f"🔧 Tentativo formazione: {num_coppie_target} coppie", end="")
        if self.gestisce_trio:
            messaggio_motore(" + 1 trio")
        else:
            messaggio_motore("")

        studenti_per_coppie = self.studenti.copy()

        # Gli studenti PRIMA possono entrare nel trio solo se esso è frontale.
        trio_in_prima_fila = (
            self.gestisce_trio
            and getattr(
                self.configurazione_aula,
                'fila_trio',
                None
            ) == 0
        )

        max_coppie_prima_fila = (
            self._calcola_max_coppie_prima_fila(
                trio_in_prima_fila
            )
        )

        messaggio_motore(
            f"   🪑 Capienza assoluta PRIMA: "
            f"massimo {max_coppie_prima_fila} "
            f"gruppi-coppia frontali"
        )

        # Nei tentativi 1–3 la blacklist è un vincolo assoluto. Prima di
        # enumerare trii o avviare il backtracking, verifica una condizione
        # necessaria elementare: ogni studente deve avere almeno un altro
        # studente con cui possa condividere un'adiacenza. Un vertice isolato
        # non può appartenere né a una coppia né a un trio lineare; proseguire
        # esplorerebbe quindi soltanto rami matematicamente morti.
        if tentativo <= 3 and len(studenti_per_coppie) >= 2:
            ha_partner = {id(studente): False for studente in studenti_per_coppie}
            for indice, studente1 in enumerate(studenti_per_coppie):
                for studente2 in studenti_per_coppie[indice + 1:]:
                    info = self.motore_vincoli.calcola_punteggio_coppia(
                        studente1, studente2
                    )
                    if info.get('valutazione') not in ('VIETATA', 'BLACKLISTATA'):
                        ha_partner[id(studente1)] = True
                        ha_partner[id(studente2)] = True
            isolati = [
                studente.get_nome_completo()
                for studente in studenti_per_coppie
                if not ha_partner[id(studente)]
            ]
            if isolati:
                messaggio_motore(
                    "   ❌ Impossibile senza riusi: nessuna adiacenza nuova "
                    "disponibile per " + ", ".join(isolati)
                )
                if self.diagnostica is not None:
                    self.diagnostica.evento(
                        "tentativo_impossibile_precheck",
                        modalita="coppie",
                        tentativo=tentativo,
                        causa="studente_senza_partner_nuovo",
                        studenti=isolati,
                        seed_candidato=self.seed_candidato,
                    )
                return False

        # Prima di enumerare i trii, applica una condizione necessaria di
        # fattibilità sulle incompatibilità assolute. In un trio lineare possono
        # convivere al massimo due membri di una clique (ai due estremi); ogni
        # coppia può contenerne al massimo uno. Se la clique supera questa
        # capacità, nessuna scelta del trio potrà rendere accoppiabili i restanti.
        clique_assoluta = (
            self.motore_vincoli._clique_incompatibilita_per_potatura(
                studenti_per_coppie
            )
        )
        capacita_clique = num_coppie_target + (2 if self.gestisce_trio else 0)
        if len(clique_assoluta) > capacita_clique:
            messaggio_motore(
                f"   ❌ Impossibile: clique assoluta di {len(clique_assoluta)} "
                f"studenti, capacità massima dei gruppi={capacita_clique}"
            )
            return False

        if self.gestisce_trio:
            messaggio_motore(f"🔍 FASE 1: Identificazione trio ottimale...")

            if trio_in_prima_fila:
                studenti_no_trio = set()
            else:
                studenti_no_trio = {
                    s for s in self.studenti if s.nota_posizione == 'PRIMA'
                }
                if studenti_no_trio:
                    nomi = ', '.join(s.get_nome_completo() for s in studenti_no_trio)
                    messaggio_motore(f"   🔒 Trio NON in prima fila: escludo dal trio gli allievi PRIMA ({nomi})")

            self.trio_identificato = (
                self._identifica_trio_ottimale_configurato(
                    self.studenti,
                    tentativo,
                    studenti_no_trio=studenti_no_trio,
                    max_coppie_prima_fila=(
                        max_coppie_prima_fila
                    )
                )
            )

            if not self.trio_identificato:
                messaggio_motore(f"   ❌ Impossibile identificare trio valido nel tentativo {tentativo}")
                return False

            messaggio_motore(f"   ✅ Trio formato: {', '.join([s.get_nome_completo() for s in self.trio_identificato])}")

            if tentativo <= 3:
                coppie_virtuali_ripetute = self._conta_coppie_virtuali_ripetute_trio(self.trio_identificato)

                if coppie_virtuali_ripetute > 0:
                    messaggio_motore(f"   ❌ RIFIUTO TENTATIVO {tentativo}: trio con {coppie_virtuali_ripetute} coppie virtuali ripetute")
                    return False
                else:
                    messaggio_motore(f"   ✅ Trio qualità verificata: 0 coppie virtuali ripetute")

            for studente_trio in self.trio_identificato:
                studenti_per_coppie.remove(studente_trio)

            messaggio_motore(f"   📊 Studenti rimanenti per coppie: {len(studenti_per_coppie)}")

        messaggio_motore(f"🔧 FASE 2: Formazione {num_coppie_target} coppie...")

        if hasattr(self.motore_vincoli, 'tentativo_corrente'):
            self.motore_vincoli.tentativo_corrente = tentativo
            messaggio_motore(f"   📊 Comunicato tentativo {tentativo} al motore vincoli")

        coppie_candidate = (
            self.motore_vincoli.trova_migliori_coppie(
                studenti_per_coppie,
                num_coppie_target,
                max_coppie_prima_fila=(
                    max_coppie_prima_fila
                )
            )
        )

        messaggio_motore(f"   📥 Motore vincoli ha restituito {len(coppie_candidate)} coppie")

        if tentativo <= 3:
            coppie_blacklistate = 0
            for studente1, studente2, info in coppie_candidate:
                if info.get('valutazione') == 'BLACKLISTATA':
                    coppie_blacklistate += 1

            if coppie_blacklistate > 0:
                messaggio_motore(f"   ❌ RIFIUTO TENTATIVO {tentativo}: {coppie_blacklistate} coppie blacklistate")
                return False
            else:
                messaggio_motore(f"   ✅ Qualità verificata: 0 coppie blacklistate")

        if len(coppie_candidate) < num_coppie_target:
            messaggio_motore(f"   ❌ Insufficienti coppie valide: {len(coppie_candidate)}/{num_coppie_target}")
            return False

        studenti_in_coppie = len(coppie_candidate) * 2
        studenti_in_trio = 3 if self.gestisce_trio and self.trio_identificato else 0
        studenti_processati = studenti_in_coppie + studenti_in_trio

        if studenti_processati != len(self.studenti):
            messaggio_motore(f"   ❌ Errore conteggio: {studenti_processati}/{len(self.studenti)} studenti")
            return False

        self.coppie_formate = coppie_candidate
        self.studenti_singoli = []

        messaggio_motore(f"   ✅ Formazione completa riuscita!")
        messaggio_motore(f"   📊 Coppie: {len(self.coppie_formate)}, Trio: {1 if self.trio_identificato else 0}")

        return True

    def _conta_coppie_virtuali_ripetute_trio(self, trio):
        if not hasattr(self, 'config_app'):
            return 0

        studente1, studente2, studente3 = trio
        coppie_virtuali_attuali = [
            {studente1.get_nome_completo(), studente2.get_nome_completo()},
            {studente2.get_nome_completo(), studente3.get_nome_completo()}
        ]

        if DEBUG_MOTORE:
            messaggio_motore(f"   🔍 TRIO ATTUALE: {[s.get_nome_completo() for s in trio]}")
            messaggio_motore(f"   🔗 COPPIE VIRTUALI ATTUALI: {[list(c) for c in coppie_virtuali_attuali]}")

        coppie_da_evitare = self.config_app.config_data.get("coppie_da_evitare", [])

        # I trii sono già registrati come due coppie consecutive.
        tutte_coppie_usate = []
        if DEBUG_MOTORE:
            messaggio_motore(f"   📋 ANALISI BLACKLIST ({len(coppie_da_evitare)} elementi):")

        for idx, item in enumerate(coppie_da_evitare):
            if item.get("tipo") == "coppia":
                studenti = item.get("studenti", [])
                if len(studenti) == 2:
                    coppia = {studenti[0], studenti[1]}
                    tutte_coppie_usate.append(coppia)
                    if DEBUG_MOTORE:
                        messaggio_motore(f"      COPPIA {idx}: {list(coppia)}")

        coppie_ripetute = 0
        for i, coppia_virtuale in enumerate(coppie_virtuali_attuali, 1):
            if DEBUG_MOTORE:
                messaggio_motore(f"   🔍 CONTROLLO COPPIA VIRTUALE {i}: {list(coppia_virtuale)}")
            if coppia_virtuale in tutte_coppie_usate:
                if DEBUG_MOTORE:
                    messaggio_motore(f"      🚨 TROVATA nella blacklist!")
                coppie_ripetute += 1
            else:
                if DEBUG_MOTORE:
                    messaggio_motore(f"      ✅ NON trovata nella blacklist")

        if DEBUG_MOTORE:
            messaggio_motore(f"   📊 RISULTATO FINALE: {coppie_ripetute} ripetizioni")
        return coppie_ripetute

    def _identifica_trio_ottimale_configurato(
        self,
        studenti,
        tentativo,
        studenti_no_trio=None,
        max_coppie_prima_fila: int | None = None
    ):
        """
        Sceglie il trio e il suo ordine interno con i vincoli del tentativo corrente.

        Gli studenti esclusi dal trio restano disponibili per le coppie. Una terna è
        accettata soltanto se il migliore dei tre possibili centri lascia accoppiabili
        tutti gli studenti rimanenti.
        """
        import itertools

        if studenti_no_trio is None:
            studenti_no_trio = set()

        candidati_trio = [
            studente
            for studente in studenti
            if studente not in studenti_no_trio
        ]

        migliore_trio = None
        miglior_punteggio = float('-inf')
        trii_testati = 0

        # L'indice è comune a tutte le terne del tentativo.
        indice_bl = None
        if tentativo <= 3 and hasattr(self, 'config_app'):
            indice_bl = self._indice_blacklist_nomi()

        messaggio_motore(
            f"   🔍 Analizzando possibili trii "
            f"per tentativo {tentativo}..."
        )

        for trio_candidato in itertools.combinations(candidati_trio, 3):
            trii_testati += 1

            # Se il trio affianca il FISSO, almeno un membro deve essergli lecito.
            if (
                self.studente_fisso is not None
                and getattr(
                    self.configurazione_aula,
                    'fila_trio',
                    None
                ) == 0
                and all(
                    self.motore_vincoli._ha_incompatibilita_assoluta(
                        studente,
                        self.studente_fisso
                    )
                    for studente in trio_candidato
                )
            ):
                continue

            # Le disposizioni speculari hanno le stesse adiacenze: basta
            # provare i tre possibili studenti centrali.
            miglior_ordine_candidato = None
            miglior_punteggio_candidato = float('-inf')

            for indice_centro in (1, 0, 2):
                centro = trio_candidato[indice_centro]

                estremi = [
                    studente
                    for indice, studente in enumerate(trio_candidato)
                    if indice != indice_centro
                ]

                ordine = (
                    estremi[0],
                    centro,
                    estremi[1]
                )

                if not self._trio_rispetta_vincoli_assoluti(ordine):
                    continue

                # Nei primi tre tentativi entrambe le adiacenze devono essere nuove.
                if indice_bl is not None:
                    studente1, studente2, studente3 = ordine

                    coppia_12 = frozenset((
                        studente1.get_nome_completo(),
                        studente2.get_nome_completo()
                    ))
                    coppia_23 = frozenset((
                        studente2.get_nome_completo(),
                        studente3.get_nome_completo()
                    ))

                    if coppia_12 in indice_bl or coppia_23 in indice_bl:
                        continue

                punteggio_ordine = self._valuta_trio_configurato(ordine)

                if punteggio_ordine > miglior_punteggio_candidato:
                    miglior_punteggio_candidato = punteggio_ordine
                    miglior_ordine_candidato = ordine

            if miglior_ordine_candidato is None:
                continue

            punteggio_trio = miglior_punteggio_candidato

            if punteggio_trio <= miglior_punteggio:
                continue

            # L'accoppiabilità dei rimanenti dipende dalla terna, non dal suo ordine.
            studenti_rimanenti = [
                studente
                for studente in studenti
                if studente not in trio_candidato
            ]

            coppie_possibili = (
                self.motore_vincoli.trova_migliori_coppie(
                    studenti_rimanenti,
                    len(studenti_rimanenti) // 2,
                    max_coppie_prima_fila=(
                        max_coppie_prima_fila
                    )
                )
            )

            if len(coppie_possibili) < len(studenti_rimanenti) // 2:
                continue

            if punteggio_trio > miglior_punteggio:
                miglior_punteggio = punteggio_trio

                # L'ordine salvato è quello usato da layout, report e blacklist.
                migliore_trio = miglior_ordine_candidato

        messaggio_motore(f"   📊 Trii testati: {trii_testati}")

        if migliore_trio:
            messaggio_motore(
                f"   🎯 Trio ottimale trovato "
                f"(punteggio: {miglior_punteggio})"
            )
            return list(migliore_trio)

        messaggio_motore(
            f"   ❌ Nessun trio valido "
            f"per tentativo {tentativo}"
        )
        return None

    def _valuta_trio_configurato(self, trio):
        """Valuta le due adiacenze reali del trio e le penalità di rotazione."""
        punteggio_totale = 0
        studente1, studente2, studente3 = trio

        # Nel trio contano soltanto le adiacenze 1–2 e 2–3.
        coppie_adiacenti = [
            (studente1, studente2),
            (studente2, studente3)
        ]

        for s1, s2 in coppie_adiacenti:
            risultato = self.motore_vincoli.calcola_punteggio_coppia(s1, s2)
            punteggio_totale += risultato['punteggio_totale']

        if hasattr(self, 'config_app'):
            punteggio_totale -= self._calcola_penalita_trio_ripetuti(trio)

        if hasattr(self, 'config_app'):
            punteggio_totale -= self._calcola_penalita_coppie_virtuali_gia_usate(trio)

        return punteggio_totale

    def _calcola_penalita_trio_ripetuti(self, trio):
        """Penalizza i membri già impiegati nel trio in assegnazioni precedenti."""
        penalita_totale = 0
        contatori = self.config_app.config_data.get("studenti_trio_contatore", {})

        if DEBUG_MOTORE:
            messaggio_motore(f"   🎯 Controllo penalità trio ripetizioni:")

        for studente in trio:
            nome_studente = studente.get_nome_completo()
            volte_nel_trio = contatori.get(nome_studente, 0)

            if volte_nel_trio > 0:
                penalita_studente = volte_nel_trio * 500
                penalita_totale += penalita_studente
                if DEBUG_MOTORE:
                    messaggio_motore(f"      ⚠️ {nome_studente}: {volte_nel_trio} volte precedenti → penalità -{penalita_studente}")
            else:
                if DEBUG_MOTORE:
                    messaggio_motore(f"      ✅ {nome_studente}: mai nel trio → nessuna penalità")

        if penalita_totale > 0 and DEBUG_MOTORE:
            messaggio_motore(f"   📊 Penalità totale trio: -{penalita_totale}")

        return penalita_totale

    def _calcola_penalita_coppie_virtuali_gia_usate(self, trio):
        """Penalizza le due adiacenze del trio già usate come coppie ordinarie."""
        penalita_totale = 0
        studente1, studente2, studente3 = trio

        coppie_virtuali = [
            (studente1.get_nome_completo(), studente2.get_nome_completo()),
            (studente2.get_nome_completo(), studente3.get_nome_completo())
        ]

        indice = self._indice_blacklist_nomi()

        for nome1, nome2 in coppie_virtuali:

            volte_usata = indice.get(frozenset((nome1, nome2)))
            if volte_usata is not None:
                penalita = 300 * volte_usata
                penalita_totale += penalita
                if DEBUG_MOTORE:
                    messaggio_motore(f"   ⚠️ Coppia virtuale già usata come normale: {nome1} + {nome2} (penalità: -{penalita})")

        return penalita_totale

    def _indice_blacklist_nomi(self):
        """
        Restituisce l'indice ``coppia → volte_usata`` della blacklist a coppie.

        La cache viene rigenerata se cambia l'oggetto lista o la sua lunghezza. Le
        voci malformate sono ignorate e, in caso di duplicati, prevale la prima.
        """
        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        # Ogni candidato possiede un AssegnatorePosti nuovo; identità e
        # lunghezza della lista sono quindi sufficienti a validare la cache.
        cache = getattr(self, '_cache_indice_virtuali', None)
        if cache is None or cache[0] is not coppie_usate or cache[1] != len(coppie_usate):
            indice = {}
            for item in coppie_usate:
                studenti_voce = item.get("studenti", [])
                if len(studenti_voce) != 2:
                    continue
                chiave = frozenset((studenti_voce[0], studenti_voce[1]))
                if chiave not in indice:
                    indice[chiave] = item.get("volte_usata", 1)
            self._cache_indice_virtuali = (coppie_usate, len(coppie_usate), indice)
            cache = self._cache_indice_virtuali
        return cache[2]

    def _applica_penalita_blacklist_tentativo(self, tentativo):
        """Avvolge il calcolo dei punteggi con la regola blacklist del tentativo."""
        if not hasattr(self, 'config_app'):
            return

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            messaggio_motore("   📝 Nessuna blacklist presente")
            return

        messaggio_motore(f"   📋 Configurazione penalità blacklist per tentativo {tentativo}")

        # L'indice rende O(1) ogni ricerca e conserva la prima voce duplicata.
        indice_blacklist = {}
        for coppia_usata in coppie_usate:
            studenti_voce = coppia_usata.get("studenti", [])
            if len(studenti_voce) != 2:
                continue
            chiave_coppia = frozenset((studenti_voce[0], studenti_voce[1]))
            if chiave_coppia not in indice_blacklist:
                indice_blacklist[chiave_coppia] = coppia_usata

        # Strato esterno della catena descritta in
        # MotoreVincoli.calcola_punteggio_coppia.
        if not hasattr(self.motore_vincoli, '_calcola_punteggio_coppia_originale'):
            self.motore_vincoli._calcola_punteggio_coppia_originale = self.motore_vincoli.calcola_punteggio_coppia

        def calcola_con_penalita_blacklist_configurata(studente1: Student, studente2: Student) -> dict:

            risultato = self.motore_vincoli._calcola_punteggio_coppia_originale(studente1, studente2)

            if risultato['valutazione'] == 'VIETATA':
                return risultato

            penalita_blacklist = self._calcola_penalita_blacklist_per_tentativo(
                studente1, studente2, tentativo, indice_blacklist
            )

            if penalita_blacklist > 0:
                if self.motore_vincoli.blacklist_come_vincolo_assoluto and tentativo <= 3:

                    risultato['punteggio_totale'] = -999999 + tentativo
                    risultato['valutazione'] = 'BLACKLISTATA'
                    risultato['note'].append(f"COPPIA BLACKLISTATA (tentativo {tentativo})")
                else:

                    risultato['punteggio_totale'] -= penalita_blacklist

                    # Questa quota si somma alla penalità storica già applicata.
                    # Non viene aggiunta alle note visibili: il riutilizzo è già
                    # segnalato in modo uniforme nel Report e nelle statistiche.
                    # Esporre il dettaglio interno del quarto tentativo soltanto
                    # per alcune coppie renderebbe l'informazione intermittente e
                    # poco utile al docente, senza aumentare la trasparenza.

                    if risultato['punteggio_totale'] < -500:
                        risultato['valutazione'] = 'BLACKLISTATA_SOFT'

            return risultato

        self.motore_vincoli.calcola_punteggio_coppia = calcola_con_penalita_blacklist_configurata

    def _calcola_penalita_blacklist_per_tentativo(self, studente1, studente2, tentativo, indice_blacklist):
        """Restituisce la penalità della coppia mediante l'indice già costruito."""

        chiave_coppia = frozenset((studente1.get_nome_completo(),
                                   studente2.get_nome_completo()))

        coppia_usata = indice_blacklist.get(chiave_coppia)
        if coppia_usata is None:
            return 0

        volte_usata = coppia_usata.get("volte_usata", 1)

        if tentativo <= 3:
            return 999999
        else:
            return 200 * volte_usata

    def _mostra_motivi_fallimento_tentativo(self, tentativo):
        """Stampa una diagnosi sintetica del tentativo fallito."""
        messaggio_motore(f"📋 Analisi fallimento tentativo {tentativo}:")

        if tentativo == 1:
            messaggio_motore("   • Impossibile formare nuove coppie rispettando tutti i vincoli")
            messaggio_motore("   • Possibili cause: troppi vincoli incompatibilità/affinità o blacklist estesa")

        elif tentativo == 2:
            messaggio_motore("   • Fallimento anche rilassando vincoli deboli (incomp 1, affinità 1)")
            messaggio_motore("   • Restano attivi: incomp 2-3, affinità 2-3, posizione, genere misto")

        elif tentativo == 3:
            messaggio_motore("   • Fallimento anche rilassando vincoli medi")
            messaggio_motore("   • Restano attivi solo: incomp 3, posizione PRIMA, affinità 3, genere misto")

        self._mostra_diagnostica_vincoli_attivi()

    def _mostra_diagnostica_vincoli_attivi(self):
        """Stampa i vincoli ancora attivi nel tentativo corrente."""
        messaggio_motore("   🔍 Vincoli ancora attivi:")

        incomp_3_count = 0
        for studente in self.studenti:

            for nome_completo, livello in studente.incompatibilita.items():
                if livello == 3:
                    incomp_3_count += 1

        prima_fila_count = len([s for s in self.studenti if s.nota_posizione == 'PRIMA'])

        messaggio_motore(f"   • Incompatibilità assolute (livello 3): {incomp_3_count}")
        messaggio_motore(f"   • Richieste prima fila: {prima_fila_count}")

        if hasattr(self.motore_vincoli, 'genere_misto_obbligatorio') and self.motore_vincoli.genere_misto_obbligatorio:
            maschi = len([s for s in self.studenti if s.sesso == 'M'])
            femmine = len([s for s in self.studenti if s.sesso == 'F'])
            messaggio_motore(f"   • Genere misto obbligatorio: {maschi}M + {femmine}F")

    def _genera_report_fallimento_completo(self):
        """Stampa la diagnosi e prepara il corrispondente report strutturato."""
        messaggio_motore("\n" + "="*60)
        messaggio_motore("🚨 REPORT DIAGNOSTICO - ASSEGNAZIONE IMPOSSIBILE")
        messaggio_motore("="*60)

        messaggio_motore("\n📋 ANALISI VINCOLI ASSOLUTI:")
        self._analizza_vincoli_assoluti_dettagliato()

        messaggio_motore("\n📋 ANALISI BLACKLIST:")
        self._analizza_blacklist_dettagliato()

        messaggio_motore("\n💡 SUGGERIMENTI PER RISOLVERE:")
        self._genera_suggerimenti_risoluzione()

        if hasattr(self, 'modalita_rotazione') and self.modalita_rotazione:
            messaggio_motore("\n🔄 COPPIE RIUTILIZZABILI DISPONIBILI:")
            self._proponi_coppie_riutilizzabili()

        messaggio_motore("="*60)

        self.report_fallimento = self._costruisci_report_diagnostico()

    def _trova_gruppo_incompatibile_sovrabbondante(self, studenti):
        """Trova una causa certa di impossibilità dovuta alle sole incompatibilità.

        Per una classe pari senza studente FISSO, ogni coppia può contenere al
        massimo un membro di un gruppo i cui componenti siano tutti
        reciprocamente incompatibili al livello 3. Se il gruppo supera metà
        della classe, non esistono abbastanza compagni esterni distinti per
        separarne tutti i membri.

        Restituisce il gruppo massimo che dimostra l'impossibilità, oppure
        ``None``. Nei casi dispari o con FISSO non formula questa prova, perché
        la presenza del trio cambia la struttura degli abbinamenti.
        """
        studenti = list(studenti)
        numero_studenti = len(studenti)

        if (
            numero_studenti < 2
            or numero_studenti % 2 != 0
            or getattr(self, "studente_fisso", None) is not None
        ):
            return None

        adiacenze = []
        for indice, studente in enumerate(studenti):
            maschera = 0
            for altro_indice, altro in enumerate(studenti):
                if (
                    indice != altro_indice
                    and self.motore_vincoli._ha_incompatibilita_assoluta(
                        studente,
                        altro,
                    )
                ):
                    maschera |= 1 << altro_indice
            adiacenze.append(maschera)

        migliore = 0

        def espandi(gruppo, candidati):
            nonlocal migliore

            if gruppo.bit_count() + candidati.bit_count() <= migliore.bit_count():
                return

            if not candidati:
                if gruppo.bit_count() > migliore.bit_count():
                    migliore = gruppo
                return

            rimanenti = candidati
            while rimanenti:
                if gruppo.bit_count() + rimanenti.bit_count() <= migliore.bit_count():
                    break

                bit_vertice = rimanenti & -rimanenti
                indice_vertice = bit_vertice.bit_length() - 1
                rimanenti ^= bit_vertice

                espandi(
                    gruppo | bit_vertice,
                    rimanenti & adiacenze[indice_vertice],
                )

            if gruppo.bit_count() > migliore.bit_count():
                migliore = gruppo

        espandi(0, (1 << numero_studenti) - 1)

        dimensione = migliore.bit_count()
        if dimensione <= numero_studenti // 2:
            return None

        membri = [
            studenti[indice].get_nome_completo()
            for indice in range(numero_studenti)
            if migliore & (1 << indice)
        ]
        esterni = numero_studenti - dimensione

        return {
            "studenti": membri,
            "dimensione": dimensione,
            "studenti_esterni": esterni,
            "eccedenza": dimensione - esterni,
        }

    def _costruisci_report_diagnostico(self) -> dict:
        """
        Costruisce il report strutturato distinguendo cause certe, vincoli presenti e
        suggerimenti operativi.
        """
        report = {}

        # Dati disponibili anche se il fallimento precede il quarto tentativo.
        report["casualita"] = self.esporta_metadati_casualita()

        fisso = getattr(self, 'studente_fisso', None)

        studenti_completi = list(self.studenti)
        if fisso is not None and fisso not in studenti_completi:
            studenti_completi.append(fisso)

        # Incompatibilità assolute deduplicate.
        coppie_viste = set()
        incompatibilita_assolute = []

        for studente in studenti_completi:
            for nome_target, livello in studente.incompatibilita.items():
                if livello != 3:
                    continue

                chiave = tuple(sorted((
                    studente.get_nome_completo(),
                    nome_target
                )))

                if chiave in coppie_viste:
                    continue

                coppie_viste.add(chiave)
                incompatibilita_assolute.append(
                    f"{chiave[0]}  ↔  {chiave[1]}"
                )

        report["incompatibilita_assolute"] = (
            incompatibilita_assolute
        )

        # Capienza reale della prima fila, al netto del FISSO.
        studenti_prima = [
            studente
            for studente in studenti_completi
            if studente.nota_posizione == 'PRIMA'
        ]

        nomi_prima = [
            studente.get_nome_completo()
            for studente in studenti_prima
        ]

        banchi_per_fila = (
            self.configurazione_aula.get_banchi_per_fila()
            if self.configurazione_aula is not None
            else []
        )

        posti_prima_totali = (
            len(banchi_per_fila[0])
            if banchi_per_fila
            else 0
        )

        posti_prima_utilizzabili = max(
            0,
            posti_prima_totali
            - (1 if fisso is not None else 0)
        )

        eccesso_prima = max(
            0,
            len(studenti_prima) - posti_prima_utilizzabili
        )

        info_prima = {
            "studenti": nomi_prima,
            "richieste": len(studenti_prima),
            "posti_totali": posti_prima_totali,
            "posti_utilizzabili": posti_prima_utilizzabili,
            "eccesso": eccesso_prima,
            "impossibile_per_capienza": eccesso_prima > 0,
        }

        report["studenti_prima_fila"] = nomi_prima
        report["prima_fila"] = info_prima

        # Studenti privi di qualunque vicino lecito.
        senza_vicini_compatibili = []

        for studente in studenti_completi:
            if studente is fisso:
                continue
            altri = [
                altro
                for altro in studenti_completi
                if altro is not studente
            ]

            if not altri:
                continue

            ha_almeno_un_vicino = any(
                not self.motore_vincoli
                ._ha_incompatibilita_assoluta(
                    studente,
                    altro
                )
                for altro in altri
            )

            if not ha_almeno_un_vicino:
                senza_vicini_compatibili.append(
                    studente.get_nome_completo()
                )

        report["studenti_senza_vicini_compatibili"] = (
            senza_vicini_compatibili
        )

        # Gruppo troppo numeroso per essere separato in coppie. La prova è
        # distinta dal caso di un singolo studente senza vicini: qui ciascun
        # membro può avere compagni leciti, ma non ce ne sono abbastanza fuori
        # dal gruppo per abbinarli tutti.
        gruppo_incompatibile = (
            self._trova_gruppo_incompatibile_sovrabbondante(
                studenti_completi
            )
        )
        report["gruppo_incompatibile_sovrabbondante"] = (
            gruppo_incompatibile
        )

        # Possibili vicini diretti del FISSO.
        possibili_vicini_fisso = []

        if fisso is not None:
            possibili_vicini_fisso = [
                studente.get_nome_completo()
                for studente in studenti_completi
                if (
                    studente is not fisso
                    and not self.motore_vincoli
                    ._ha_incompatibilita_assoluta(
                        studente,
                        fisso
                    )
                )
            ]

        info_fisso = {
            "presente": fisso is not None,
            "nome": (
                fisso.get_nome_completo()
                if fisso is not None
                else None
            ),
            "possibili_vicini": possibili_vicini_fisso,
            "nessun_vicino_lecito": (
                fisso is not None
                and not possibili_vicini_fisso
            ),
        }

        report["fisso"] = info_fisso

        # Capienza complessiva del layout.
        posti_totali = (
            self.configurazione_aula.posti_disponibili
            if self.configurazione_aula is not None
            else 0
        )

        info_capienza = {
            "studenti": len(studenti_completi),
            "posti": posti_totali,
            "mancanti": max(
                0,
                len(studenti_completi) - posti_totali
            ),
        }

        report["capienza"] = info_capienza

        # La blacklist è informativa: nel quarto tentativo non è un veto.
        info_blacklist = {
            "coppie": 0,
            "piu_usate": []
        }

        if hasattr(self, 'config_app'):
            coppie_classe = (
                self._get_blacklist_classe_corrente()
            )
            info_blacklist["coppie"] = len(coppie_classe)

            ordinate = sorted(
                coppie_classe,
                key=lambda voce: voce.get(
                    "volte_usata",
                    0
                ),
                reverse=True
            )

            for coppia in ordinate[:5]:
                nomi = coppia.get("studenti", [])
                if len(nomi) >= 2:
                    info_blacklist["piu_usate"].append(
                        f"{nomi[0]} + {nomi[1]} "
                        f"({coppia.get('volte_usata', 0)}x)"
                    )

        report["blacklist"] = info_blacklist

        # Il genere misto è una preferenza soft e non può essere causa certa.
        if getattr(
            self.motore_vincoli,
            'genere_misto_obbligatorio',
            False
        ):
            maschi = sum(
                1
                for studente in studenti_completi
                if studente.sesso == 'M'
            )
            femmine = sum(
                1
                for studente in studenti_completi
                if studente.sesso == 'F'
            )

            report["genere_misto"] = {
                "maschi": maschi,
                "femmine": femmine,
                "preferenza_soft": True,
                "sbilanciamento": abs(maschi - femmine) > 1,
            }
        else:
            report["genere_misto"] = None

        # Un tetto raggiunto indica ricerca interrotta, non impossibilità provata.
        tetto_nodi = bool(getattr(
            self.motore_vincoli,
            'tetto_nodi_scattato',
            False
        ))

        report["tetto_nodi_scattato"] = tetto_nodi
        report["ricerca_incompleta"] = tetto_nodi

        # Cause direttamente dimostrate dai dati o dal layout.
        cause_certe = []

        if info_capienza["mancanti"] > 0:
            posti = info_capienza["posti"]
            studenti = info_capienza["studenti"]
            mancanti = info_capienza["mancanti"]
            verbo_mancare = "manca" if mancanti == 1 else "mancano"
            cause_certe.append(
                f"L'aula offre {quantita(posti, 'posto', 'posti')}, "
                f"ma la classe conta {quantita(studenti, 'studente', 'studenti')}: "
                f"{verbo_mancare} {quantita(mancanti, 'posto', 'posti')}."
            )

        if info_prima["impossibile_per_capienza"]:
            posti_prima = info_prima["posti_utilizzabili"]
            richieste_prima = info_prima["richieste"]
            eccesso_prima = info_prima["eccesso"]
            verbo_avere = "ha" if richieste_prima == 1 else "hanno"
            verbo_essere = "c'è" if eccesso_prima == 1 else "ci sono"
            cause_certe.append(
                "La prima fila offre "
                f"{quantita(posti_prima, 'posto utilizzabile', 'posti utilizzabili')}, "
                f"ma {quantita(richieste_prima, 'studente', 'studenti')} "
                f"{verbo_avere} posizione PRIMA: {verbo_essere} "
                f"{quantita(eccesso_prima, 'richiesta in eccesso', 'richieste in eccesso')}."
            )

        if senza_vicini_compatibili:
            if len(senza_vicini_compatibili) == 1:
                introduzione = (
                    "Il seguente studente ha incompatibilità di livello 3 "
                    "con ogni possibile vicino: "
                )
            else:
                introduzione = (
                    "I seguenti studenti hanno incompatibilità di livello 3 "
                    "con ogni possibile vicino: "
                )
            cause_certe.append(
                introduzione
                + ", ".join(senza_vicini_compatibili)
                + "."
            )

        if gruppo_incompatibile is not None:
            dimensione_gruppo = gruppo_incompatibile["dimensione"]
            studenti_esterni = gruppo_incompatibile["studenti_esterni"]
            esterni_testo = (
                "ma è disponibile soltanto 1 studente esterno"
                if studenti_esterni == 1
                else (
                    f"ma sono disponibili soltanto "
                    f"{studenti_esterni} studenti esterni"
                )
            )
            cause_certe.append(
                f"Un gruppo di {dimensione_gruppo} studenti è reciprocamente "
                "incompatibile al livello 3. Per separarli in coppie "
                f"servirebbero {dimensione_gruppo} compagni esterni distinti, "
                f"{esterni_testo}."
            )

        if info_fisso["nessun_vicino_lecito"]:
            cause_certe.append(
                f"Nessuno studente può essere collocato accanto al FISSO "
                f"{info_fisso['nome']} senza violare "
                f"un'incompatibilità di livello 3."
            )

        report["cause_certe"] = cause_certe

        # Suggerimenti derivati dalle cause e dai vincoli osservati.
        suggerimenti = []

        if info_capienza["mancanti"] > 0:
            suggerimenti.append(
                "Aumenta il numero di posti per fila "
                "nel pannello «Configurazione aula»."
            )

        if info_prima["impossibile_per_capienza"]:
            suggerimenti.append(
                "Apri «Editor studenti» e riduci il numero di posizioni "
                "PRIMA, oppure aumenta i posti disponibili nella prima fila."
            )

        if senza_vicini_compatibili:
            suggerimenti.append(
                "Nell'Editor studenti, controlla le incompatibilità "
                "di livello 3 degli allievi indicati e, quando pedagogicamente "
                "possibile, trasformane alcune in livello 2."
            )

        if gruppo_incompatibile is not None:
            suggerimenti.append(
                "Nell'Editor studenti, controlla le incompatibilità di "
                "livello 3 interne al gruppo indicato e, quando "
                "pedagogicamente possibile, trasformane alcune in livello 2."
            )

        if info_fisso["nessun_vicino_lecito"]:
            suggerimenti.append(
                "Nell'Editor studenti, controlla le incompatibilità "
                "impostate dagli altri studenti verso il FISSO e lascia "
                "almeno un possibile vicino compatibile."
            )

        if (
            incompatibilita_assolute
            and not senza_vicini_compatibili
            and gruppo_incompatibile is None
            and not info_fisso["nessun_vicino_lecito"]
        ):
            suggerimenti.append(
                "Le incompatibilità di livello 3, considerate nel loro "
                "insieme, possono impedire una suddivisione completa. "
                "Nell'Editor studenti verifica quali vincoli devono "
                "DAVVERO restare ASSOLUTI."
            )

        if tetto_nodi:
            suggerimenti.append(
                "La ricerca ha raggiunto il limite di sicurezza del "
                "backtracking. Prova nuovamente; se il problema persiste, "
                "semplifica alcuni vincoli assoluti (studente FISSO,"
                "incompatibilità di livello 3, posizione PRIMA)."
            )

        if not suggerimenti:
            suggerimenti.append(
                "Apri «Editor studenti» e controlla soprattutto le "
                "incompatibilità di livello 3 e le posizioni PRIMA: "
                "la loro combinazione non ha prodotto una disposizione completa."
            )

        report["suggerimenti"] = suggerimenti

        return report

    def _analizza_vincoli_assoluti_dettagliato(self):
        """Stampa i vincoli assoluti rilevanti per il fallimento."""

        incomp_assolute = []
        for studente in self.studenti:

            for nome_completo_target, livello in studente.incompatibilita.items():
                if livello == 3:
                    incomp_assolute.append(f"{studente.get_nome_completo()} ↔ {nome_completo_target}")

        if incomp_assolute:
            messaggio_motore(f"   • Incompatibilità ASSOLUTE trovate: {len(incomp_assolute)}")
            for incomp in incomp_assolute[:5]:
                messaggio_motore(f"     - {incomp}")
            if len(incomp_assolute) > 5:
                messaggio_motore(f"     ... e altre {len(incomp_assolute) - 5}")

        studenti_prima = [s for s in self.studenti if s.nota_posizione == 'PRIMA']
        if studenti_prima:
            messaggio_motore(f"   • Studenti che richiedono PRIMA fila: {len(studenti_prima)}")
            for s in studenti_prima:
                messaggio_motore(f"     - {s.get_nome_completo()}")

        if hasattr(self.motore_vincoli, 'genere_misto_obbligatorio') and self.motore_vincoli.genere_misto_obbligatorio:
            maschi = [s for s in self.studenti if s.sesso == 'M']
            femmine = [s for s in self.studenti if s.sesso == 'F']
            messaggio_motore(f"   • Genere misto obbligatorio: {len(maschi)} maschi, {len(femmine)} femmine")
            if abs(len(maschi) - len(femmine)) > 1:
                messaggio_motore(f"     ⚠️ Sbilanciamento: alcune coppie saranno necessariamente stesso genere")

    def _get_blacklist_classe_corrente(self):
        """Restituisce le sole coppie di blacklist appartenenti alla classe corrente."""
        if not hasattr(self, 'config_app') or not self.studenti:
            return []

        coppie_usate = self.config_app.config_data.get("coppie_da_evitare", [])
        if not coppie_usate:
            return []

        nomi_classe = {s.get_nome_completo() for s in self.studenti}

        blacklist_filtrata = []
        for coppia in coppie_usate:
            studenti = coppia.get("studenti", [])
            if len(studenti) == 2 and studenti[0] in nomi_classe and studenti[1] in nomi_classe:
                blacklist_filtrata.append(coppia)

        return blacklist_filtrata

    def _analizza_blacklist_dettagliato(self):
        """Stampa un riepilogo della blacklist della classe corrente."""
        if not hasattr(self, 'config_app'):
            messaggio_motore("   • Nessuna configurazione blacklist disponibile")
            return

        coppie_classe = self._get_blacklist_classe_corrente()
        if not coppie_classe:
            messaggio_motore("   • Blacklist vuota per questa classe - nessuna coppia usata in precedenza")
            return

        messaggio_motore(f"   • Coppie in blacklist (classe corrente): {len(coppie_classe)}")

        if coppie_classe:
            coppie_ordinate = sorted(coppie_classe, key=lambda x: x.get("volte_usata", 0), reverse=True)
            messaggio_motore("   • Coppie più riutilizzate:")
            for coppia in coppie_ordinate[:3]:
                studenti = coppia.get("studenti", [])
                nomi = f"{studenti[0]} + {studenti[1]}" if len(studenti) >= 2 else "???"
                volte = coppia.get("volte_usata", 0)
                messaggio_motore(f"     - {nomi} (usata {volte} volte)")

    def _genera_suggerimenti_risoluzione(self):
        """Stampa le principali azioni utili a rendere lecita l'assegnazione."""
        messaggio_motore("   1. 📝 MODIFICA FILE STUDENTI:")
        messaggio_motore("      • Riduci incompatibilità livello 3 (solo per casi estremi)")
        messaggio_motore("      • Converti alcune incompatibilità 3→2 o 2→1")
        messaggio_motore("      • Riduci richieste posizione 'PRIMA' se troppo numerose")

        messaggio_motore("   2. ⚙️ MODIFICA CONFIGURAZIONI:")
        messaggio_motore("      • Disattiva 'genere misto obbligatorio' se troppo restrittivo")
        messaggio_motore("      • Aumenta numero file o posti per fila se spazio insufficiente")

        messaggio_motore("   3. 🔄 MODALITÀ ROTAZIONE:")
        messaggio_motore("      • Considera di riutilizzare alcune coppie precedenti")
        messaggio_motore("      • Elimina assegnazioni vecchie dalla cronologia se non più rilevanti")

    def _proponi_coppie_riutilizzabili(self):
        """Elenca le coppie della classe meno utilizzate e quindi riusabili."""
        if not hasattr(self, 'config_app'):
            return

        coppie_classe = self._get_blacklist_classe_corrente()
        if not coppie_classe:
            messaggio_motore("   • Nessuna coppia disponibile per riutilizzo in questa classe")
            return

        coppie_ordinate = sorted(coppie_classe, key=lambda x: x.get("volte_usata", 0))

        messaggio_motore("   💡 Coppie riutilizzabili (meno utilizzate per prime):")
        for i, coppia in enumerate(coppie_ordinate[:8]):
            studenti = coppia.get("studenti", [])
            nomi = f"{studenti[0]} + {studenti[1]}" if len(studenti) >= 2 else "???"
            volte = coppia.get("volte_usata", 0)
            messaggio_motore(f"      {i+1}. {nomi} (usata {volte} volte)")

        if len(coppie_ordinate) > 8:
            messaggio_motore(f"      ... e altre {len(coppie_ordinate) - 8} coppie disponibili")

    def _assegna_posizioni_intelligenti(self) -> bool:
        """
        Colloca FISSO, eventuale trio, coppie e singoli nei banchi disponibili.

        La disposizione viene accettata solo dopo la verifica fisica di tutti gli
        studenti con posizione PRIMA.
        """
        banchi_per_fila = self.configurazione_aula.get_banchi_per_fila()

        if not banchi_per_fila:
            messaggio_motore("❌ ERRORE: Nessuna fila di banchi trovata nel layout!")
            return False

        messaggio_motore(f"🏫 Layout aula: {len(banchi_per_fila)} file di banchi")
        for idx, banchi_fila in enumerate(banchi_per_fila):
            messaggio_motore(f"   Fila {idx + 1}: {len(banchi_fila)} banchi")

        # Il trio può coincidere con il gruppo già collocato accanto al FISSO.
        trio_gia_piazzato = False

        if self.studente_fisso is not None:
            messaggio_motore(f"\n🎯 STEP 0.5: Selezione e piazzamento gruppo adiacente al FISSO...")

            # Conta la posizione fisica del trio, non la preferenza richiesta:
            # con una sola fila, anche «centro» o «ultima» coincidono con la prima.
            trio_in_prima_fila = (
                self.gestisce_trio
                and hasattr(self, 'trio_identificato')
                and self.trio_identificato
                and getattr(self.configurazione_aula, 'fila_trio', None) == 0
            )

            risultato = self._seleziona_gruppo_per_fisso(trio_in_prima_fila)

            if risultato is not None:
                tipo_gruppo, gruppo_ordinato = risultato

                if self._assegna_gruppo_adiacente_fisso(
                    gruppo_ordinato,
                    banchi_per_fila[0]
                ):
                    messaggio_motore(f"   ✅ Gruppo adiacente al FISSO piazzato con successo")

                    if tipo_gruppo == 'trio':
                        trio_gia_piazzato = True
                        messaggio_motore(
                            f"   📌 Il trio è stato piazzato accanto "
                            f"al FISSO in prima fila"
                        )
                else:

                    messaggio_motore(
                        f"   ❌ Impossibile piazzare il gruppo "
                        f"adiacente al FISSO"
                    )
                    return False
            else:

                messaggio_motore(
                    f"   ❌ Nessuno studente può sedere accanto al FISSO "
                    f"senza violare un'incompatibilità assoluta"
                )
                return False

        if (self.gestisce_trio and
            hasattr(self, 'trio_identificato') and
            self.trio_identificato and
            not trio_gia_piazzato):

            messaggio_motore(f"\n🎯 STEP 1: Assegnazione trio atomico...")
            modalita_trio = self._determina_modalita_trio_from_interface()

            if self._assegna_trio_atomico_corretto(self.trio_identificato, banchi_per_fila, modalita_trio):
                messaggio_motore(f"   ✅ Trio atomico assegnato con successo")
            else:
                messaggio_motore(f"   ❌ Impossibile assegnare trio atomico")
                return False

        messaggio_motore(f"\n🎯 STEP 2: Assegnazione coppie...")
        if not self._assegna_coppie_intelligenti(banchi_per_fila):
            return False

        if self.studenti_singoli:
            messaggio_motore(
                f"\n🎯 STEP 3: Assegnazione "
                f"{len(self.studenti_singoli)} "
                f"studenti singoli..."
            )
            self._assegna_studenti_singoli_rimanenti(
                banchi_per_fila
            )

        # Guardia fisica finale: nessun PRIMA può risultare fuori fila.
        if not self._verifica_vincolo_prima_fila_assoluto():
            return False

        return True

    def _verifica_vincolo_prima_fila_assoluto(self) -> bool:
        """Verifica sul layout popolato che tutti gli studenti PRIMA siano frontali."""
        studenti_prima = [
            studente
            for studente in self.studenti
            if studente.nota_posizione == 'PRIMA'
        ]

        if not studenti_prima:
            return True

        banchi_per_fila = (
            self.configurazione_aula.get_banchi_per_fila()
        )

        if not banchi_per_fila:
            return False

        occupanti_prima_fila = {
            banco.occupato_da
            for banco in banchi_per_fila[0]
            if banco.occupato_da is not None
        }

        mancanti = [
            studente.get_nome_completo()
            for studente in studenti_prima
            if (
                f"{studente.cognome}_{studente.nome}"
                not in occupanti_prima_fila
            )
        ]

        if mancanti:
            messaggio_motore(
                f"   ❌ VINCOLO PRIMA VIOLATO: "
                f"fuori dalla prima fila: "
                + ", ".join(mancanti)
            )
            return False

        messaggio_motore(
            f"   ✅ Vincolo PRIMA verificato: "
            f"{len(studenti_prima)} studenti "
            f"tutti in prima fila"
        )

        return True

    def _assegna_trio_atomico_corretto(self, trio_studenti, banchi_per_fila, modalita_trio):
        """
        Colloca il trio nella fila calcolata da ``ConfigurazioneAula``.

        La fila salvata nel layout è la fonte di verità: non viene ricalcolata dal
        motore, evitando disallineamenti fra geometria e assegnazione.
        """
        messaggio_motore(f"   🔍 Assegnazione trio: {[s.get_nome_completo() for s in trio_studenti]}")
        messaggio_motore(f"   📍 Modalità posizionamento: {modalita_trio}")

        # La geometria dell'aula è la fonte di verità per la fila del trio.
        fila_trio_da_layout = getattr(self.configurazione_aula, 'fila_trio', None)

        fila_target_idx = None

        if fila_trio_da_layout is not None:

            fila_target_idx = fila_trio_da_layout
            messaggio_motore(f"   🎯 Target da layout: FILA {fila_target_idx + 1} (modalità '{modalita_trio}')")
        elif modalita_trio == 'prima':
            fila_target_idx = 0
            messaggio_motore(f"   🎯 Target: PRIMA FILA (fallback)")
        elif modalita_trio == 'ultima':
            fila_target_idx = len(banchi_per_fila) - 1
            messaggio_motore(f"   🎯 Target: ULTIMA FILA (fallback)")
        elif modalita_trio == 'centro':
            fila_target_idx = len(banchi_per_fila) // 2
            messaggio_motore(f"   🎯 Target: CENTRO (fallback)")
        else:
            messaggio_motore(f"   ⚠️ Modalità '{modalita_trio}' non riconosciuta, uso PRIMA FILA")
            fila_target_idx = 0

        trio_contiene_prima = any(
            studente.nota_posizione == 'PRIMA'
            for studente in trio_studenti
        )

        if trio_contiene_prima and fila_target_idx != 0:
            messaggio_motore(
                f"   ❌ Il trio contiene studenti PRIMA "
                f"ma la sua fila target non è la prima"
            )
            return False

        if fila_target_idx is not None:
            if self._assegna_trio_in_fila_specifica(
                trio_studenti,
                banchi_per_fila[fila_target_idx],
                f"FILA {fila_target_idx + 1}"
            ):
                return True

        # Le altre file non possiedono tre banchi consecutivi: nessun fallback.
        messaggio_motore(f"   ❌ La fila target non può ospitare il trio "
              f"(3 banchi consecutivi non disponibili)")
        return False

    def _assegna_trio_in_fila_specifica(self, trio_studenti, banchi_fila, nome_fila):
        """Colloca il trio su tre banchi consecutivi della fila indicata."""
        banchi_liberi = [b for b in banchi_fila if b.is_libero()]

        if len(banchi_liberi) < 3:
            messaggio_motore(f"   ❌ {nome_fila}: solo {len(banchi_liberi)} banchi liberi (servono 3)")
            return False

        banchi_liberi.sort(key=lambda b: b.colonna)

        for i in range(len(banchi_liberi) - 2):
            banco1 = banchi_liberi[i]
            banco2 = banchi_liberi[i + 1]
            banco3 = banchi_liberi[i + 2]

            if (banco2.colonna == banco1.colonna + 1 and
                banco3.colonna == banco2.colonna + 1):

                banco1.occupato_da = f"{trio_studenti[0].cognome}_{trio_studenti[0].nome}"
                banco2.occupato_da = f"{trio_studenti[1].cognome}_{trio_studenti[1].nome}"
                banco3.occupato_da = f"{trio_studenti[2].cognome}_{trio_studenti[2].nome}"

                messaggio_motore(f"   ✅ TRIO in {nome_fila}: posizioni ({banco1.riga+1},{banco1.colonna+1}), ({banco2.riga+1},{banco2.colonna+1}), ({banco3.riga+1},{banco3.colonna+1})")
                messaggio_motore(f"      {trio_studenti[0].get_nome_completo()}")
                messaggio_motore(f"      {trio_studenti[1].get_nome_completo()}")
                messaggio_motore(f"      {trio_studenti[2].get_nome_completo()}")

                return True

        messaggio_motore(f"   ❌ {nome_fila}: non trovati 3 banchi consecutivi")
        return False

    def _assegna_coppie_intelligenti(self, banchi_per_fila):
        """Assegna le coppie ai banchi liberi rispettando la priorità di fila."""
        messaggio_motore(f"   👥 Assegnazione {len(self.coppie_formate)} coppie ai banchi rimanenti...")

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

        messaggio_motore(f"   📋 Categorizzazione:")
        messaggio_motore(f"      - Prima fila: {len(coppie_prima_fila)} coppie")
        messaggio_motore(f"      - Ultima fila: {len(coppie_ultima_fila)} coppie")
        messaggio_motore(f"      - Flessibili: {len(coppie_neutrale)} coppie")

        tutte_coppie = coppie_prima_fila + coppie_neutrale + coppie_ultima_fila

        coppie_assegnate = 0
        for fila_idx, banchi_fila in enumerate(banchi_per_fila):
            banchi_liberi = [b for b in banchi_fila if b.is_libero()]

            i = 0
            while i < len(banchi_liberi) - 1 and coppie_assegnate < len(tutte_coppie):
                banco1 = banchi_liberi[i]
                banco2 = banchi_liberi[i + 1]

                coppia = tutte_coppie[coppie_assegnate]
                studente1, studente2, info = coppia

                banco1.occupato_da = f"{studente1.cognome}_{studente1.nome}"
                banco2.occupato_da = f"{studente2.cognome}_{studente2.nome}"

                messaggio_motore(f"   ✅ Coppia {coppie_assegnate + 1}: FILA {fila_idx + 1}")
                messaggio_motore(f"      {studente1.get_nome_completo()} -> ({banco1.riga+1},{banco1.colonna+1})")
                messaggio_motore(f"      {studente2.get_nome_completo()} -> ({banco2.riga+1},{banco2.colonna+1})")

                coppie_assegnate += 1
                i += 2

        if coppie_assegnate < len(self.coppie_formate):
            messaggio_motore(f"   ⚠️  Assegnate solo {coppie_assegnate}/{len(self.coppie_formate)} coppie")
            return False

        messaggio_motore(f"   ✅ Tutte le {coppie_assegnate} coppie assegnate con successo")
        return True

    def _assegna_studenti_singoli_rimanenti(self, banchi_per_fila):
        """Colloca eventuali studenti singoli nei primi banchi ancora liberi."""
        banchi_liberi = []
        for fila in banchi_per_fila:
            for banco in fila:
                if banco.is_libero():
                    banchi_liberi.append(banco)

        messaggio_motore(f"   📊 Banchi liberi disponibili: {len(banchi_liberi)}")

        for studente in self.studenti_singoli:
            if banchi_liberi:
                banco = banchi_liberi.pop(0)
                banco.occupato_da = f"{studente.cognome}_{studente.nome}"
                messaggio_motore(f"   ✅ {studente.get_nome_completo()} -> ({banco.riga+1},{banco.colonna+1})")
            else:
                messaggio_motore(f"   ❌ Nessun banco libero per {studente.get_nome_completo()}")

    def _gestisci_studente_fisso(self, studente_fisso: 'Student') -> bool:
        """
        Colloca il FISSO nel primo banco a sinistra e lo esclude dai gruppi.

        Restituisce ``False`` soltanto se la prima fila non contiene alcun banco.
        """
        # Il primo banco a sinistra della prima fila è riservato al FISSO.
        self.studente_fisso = studente_fisso
        messaggio_motore(f"   📌 Studente FISSO: {studente_fisso.get_nome_completo()}")

        banchi_per_fila = self.configurazione_aula.get_banchi_per_fila()

        if not banchi_per_fila or not banchi_per_fila[0]:
            messaggio_motore(f"   ❌ ERRORE: Nessun banco trovato nella prima fila!")
            return False

        primo_banco = banchi_per_fila[0][0]
        identificatore = f"{studente_fisso.cognome}_{studente_fisso.nome}"
        primo_banco.occupato_da = identificatore

        messaggio_motore(f"   ✅ FISSO pre-assegnato a riga {primo_banco.riga}, colonna {primo_banco.colonna}")

        # Da questo punto la formazione dei gruppi opera sui soli rimanenti.
        studenti_prima = len(self.studenti)
        self.studenti = [s for s in self.studenti if s is not studente_fisso]
        studenti_dopo = len(self.studenti)

        if studenti_dopo == studenti_prima:

            messaggio_motore(f"   ⚠️ ATTENZIONE: studente FISSO non trovato nella lista studenti!")
            messaggio_motore(f"   Il FISSO è stato pre-assegnato ma non rimosso dalla lista")

        else:
            messaggio_motore(f"   📊 Studenti: {studenti_prima} → {studenti_dopo} (FISSO rimosso)")
            messaggio_motore(f"   📊 Rimanenti dispari: {'Sì (trio)' if studenti_dopo % 2 == 1 else 'No (solo coppie)'}")

        return True

    def _seleziona_gruppo_per_fisso(self, trio_in_prima_fila: bool):
        """
        Sceglie il gruppo e l'ordine migliori da collocare accanto al FISSO.

        Il primo membro del gruppo è il vicino diretto. Se il trio occupa la prima
        fila vengono valutati tutti i suoi ordini; altrimenti viene orientata la
        migliore coppia disponibile. Restituisce ``None`` se nessun vicino è lecito.
        """
        if not self.studente_fisso:
            return None

        fisso = self.studente_fisso
        migliore_risultato = None
        miglior_punteggio = float('-inf')

        # Con il trio frontale vengono valutati tutti e sei gli ordini.
        if trio_in_prima_fila and self.trio_identificato:

            from itertools import permutations

            messaggio_motore(
                f"   🔍 Trio destinato alla prima fila → "
                f"valuto tutti gli ordini possibili"
            )

            trio = self.trio_identificato
            migliore_chiave = None

            for ordine in permutations(trio):

                if not self._trio_rispetta_vincoli_assoluti(ordine):
                    continue

                studente_col1 = ordine[0]
                punteggio_fisso = self._calcola_punteggio_adiacente_fisso(
                    studente_col1,
                    fisso
                )

                if punteggio_fisso == float('-inf'):
                    continue

                risultato_12 = self.motore_vincoli.calcola_punteggio_coppia(
                    ordine[0],
                    ordine[1]
                )
                risultato_23 = self.motore_vincoli.calcola_punteggio_coppia(
                    ordine[1],
                    ordine[2]
                )

                valutazioni_non_ammesse = {"VIETATA", "BLACKLISTATA"}
                if (
                    risultato_12.get("valutazione") in valutazioni_non_ammesse
                    or risultato_23.get("valutazione") in valutazioni_non_ammesse
                ):
                    continue

                punteggio_interno = (
                    risultato_12.get("punteggio_totale", 0)
                    + risultato_23.get("punteggio_totale", 0)
                )

                # Prima qualità del vicino del FISSO, poi qualità interna.
                chiave = (punteggio_fisso, punteggio_interno)

                nomi_ordine = " – ".join(
                    studente.get_nome_completo()
                    for studente in ordine
                )
                messaggio_motore(
                    f"      Ordine {nomi_ordine}: "
                    f"FISSO={punteggio_fisso}, interno={punteggio_interno}"
                )

                if migliore_chiave is None or chiave > migliore_chiave:
                    migliore_chiave = chiave
                    migliore_risultato = ("trio", list(ordine))

            if migliore_risultato:
                trio_ordinato = migliore_risultato[1]
                nome_col1 = trio_ordinato[0].get_nome_completo()

                # Si conserva l'ordine realmente collocato nella piantina.
                self.trio_identificato = list(trio_ordinato)

                messaggio_motore(
                    f"   🎯 Selezionato: TRIO con {nome_col1} in col 1 "
                    f"(FISSO={migliore_chiave[0]}, "
                    f"interno={migliore_chiave[1]})"
                )
            else:
                messaggio_motore(
                    f"   ❌ Nessun ordine del trio è compatibile "
                    f"con il FISSO e con i vincoli assoluti"
                )

            return migliore_risultato

        messaggio_motore(
            f"   🔍 Valutazione coppie "
            f"per adiacenza al FISSO..."
        )

        banchi_prima_fila = (
            self.configurazione_aula
            .get_banchi_per_fila()[0]
        )

        banchi_liberi_prima = sum(
            1
            for banco in banchi_prima_fila
            if banco.is_libero()
        )

        slot_dopo_gruppo_adiacente = max(
            0,
            (banchi_liberi_prima - 2) // 2
        )

        coppie_prima_totali = sum(
            1
            for s1, s2, _info in self.coppie_formate
            if (
                s1.nota_posizione == 'PRIMA'
                or s2.nota_posizione == 'PRIMA'
            )
        )

        # La coppia adiacente deve contenere PRIMA quando gli slot restanti
        # non bastano a ospitare tutte le coppie frontali.
        richiede_coppia_prima = (
            coppie_prima_totali
            > slot_dopo_gruppo_adiacente
        )

        if richiede_coppia_prima:
            messaggio_motore(
                f"   🔒 La coppia adiacente deve contenere PRIMA: "
                f"{coppie_prima_totali} coppie PRIMA, "
                f"solo {slot_dopo_gruppo_adiacente} "
                f"slot frontali successivi"
            )

        indice_coppia_selezionata = None

        for idx, (s1, s2, info) in enumerate(self.coppie_formate):
            coppia_contiene_prima = (
                s1.nota_posizione == 'PRIMA'
                or s2.nota_posizione == 'PRIMA'
            )

            if (
                richiede_coppia_prima
                and not coppia_contiene_prima
            ):
                continue

            punteggio_s1 = self._calcola_punteggio_adiacente_fisso(s1, fisso)

            punteggio_s2 = self._calcola_punteggio_adiacente_fisso(s2, fisso)

            if punteggio_s1 >= punteggio_s2:
                punteggio = punteggio_s1
                coppia_orientata = (s1, s2, info)
            else:
                punteggio = punteggio_s2
                coppia_orientata = (s2, s1, info)

            messaggio_motore(f"      Coppia {idx+1}: {coppia_orientata[0].get_nome_completo()} in col 1 → {punteggio}")

            if punteggio > miglior_punteggio:
                miglior_punteggio = punteggio
                migliore_risultato = ('coppia', coppia_orientata)
                indice_coppia_selezionata = idx

        if migliore_risultato:
            nome_col1 = migliore_risultato[1][0].get_nome_completo()
            messaggio_motore(f"   🎯 Selezionata: COPPIA con {nome_col1} in col 1 (punteggio: {miglior_punteggio})")

            if indice_coppia_selezionata is not None:
                self.coppie_formate.pop(indice_coppia_selezionata)

                # La coppia è salvata già orientata: indice 0 = vicino diretto.
                self.gruppo_adiacente_fisso = migliore_risultato[1]
                messaggio_motore(f"   📋 Coppia rimossa da coppie_formate ({len(self.coppie_formate)} coppie rimaste)")

        return migliore_risultato

    def _calcola_punteggio_adiacente_fisso(self, studente: 'Student', fisso: 'Student') -> int | float:
        """
        Valuta un candidato al ruolo di vicino diretto del FISSO.

        Legge i vincoli del candidato verso il FISSO e applica la penalità per
        gli utilizzi precedenti nel ruolo. È sufficiente leggere questa direzione
        perché il caricamento rende bidirezionali i vincoli inequivocabili.
        Un'incompatibilità di livello 3 restituisce ``-inf``.
        """
        # I vincoli sono letti dal candidato verso il FISSO.
        punteggio = 0

        if fisso.get_nome_completo() in studente.affinita:
            livello = studente.affinita[fisso.get_nome_completo()]

            bonus = livello * 100
            punteggio += bonus
            messaggio_motore(f"         + Affinità livello {livello} → +{bonus}")

        if fisso.get_nome_completo() in studente.incompatibilita:
            livello = studente.incompatibilita[fisso.get_nome_completo()]
            if livello == 3:

                messaggio_motore(f"         🚫 Incompatibilità ASSOLUTA (livello 3) → VETO")
                return float('-inf')
            else:

                penalita = livello * 100
                punteggio -= penalita
                messaggio_motore(f"         - Incompatibilità livello {livello} → -{penalita}")

        # La rotazione evita di riutilizzare sempre lo stesso vicino.
        if hasattr(self, 'config_app'):
            contatori = self.config_app.config_data.get("studenti_vicino_fisso_contatore", {})
            nome_studente = studente.get_nome_completo()
            volte_in_col1 = contatori.get(nome_studente, 0)

            if volte_in_col1 > 0:

                penalita_rotazione = volte_in_col1 * 500
                punteggio -= penalita_rotazione
                messaggio_motore(f"         🔄 Rotazione: già {volte_in_col1}× in col 1 → -{penalita_rotazione}")

        return punteggio

    def _assegna_gruppo_adiacente_fisso(self, gruppo_ordinato, banchi_prima_fila) -> bool:
        """
        Colloca una coppia o un trio nei banchi consecutivi accanto al FISSO.

        Il primo membro occupa la colonna adiacente e diventa la fonte di verità per
        il contatore delle rotazioni del vicino del FISSO.
        """

        # Le coppie includono anche il dizionario informativo; i trii no.
        if isinstance(gruppo_ordinato, tuple) and len(gruppo_ordinato) == 3:

            studenti_da_piazzare = [gruppo_ordinato[0], gruppo_ordinato[1]]
        elif isinstance(gruppo_ordinato, list):

            studenti_da_piazzare = gruppo_ordinato
        else:
            messaggio_motore(f"   ❌ Formato gruppo non riconosciuto: {type(gruppo_ordinato)}")
            return False

        banchi_liberi = sorted(
            [b for b in banchi_prima_fila if b.is_libero()],
            key=lambda b: b.colonna
        )

        if len(banchi_liberi) < len(studenti_da_piazzare):
            messaggio_motore(f"   ❌ Non abbastanza banchi liberi in prima fila: "
                  f"{len(banchi_liberi)} liberi, servono {len(studenti_da_piazzare)}")
            return False

        # Cerca un segmento consecutivo abbastanza lungo nella prima fila.
        banchi_consecutivi = []
        for i, banco in enumerate(banchi_liberi):
            if i == 0:
                banchi_consecutivi.append(banco)
            elif banco.colonna == banchi_consecutivi[-1].colonna + 1:
                banchi_consecutivi.append(banco)
            else:

                banchi_consecutivi = [banco]

            if len(banchi_consecutivi) >= len(studenti_da_piazzare):
                break

        if len(banchi_consecutivi) < len(studenti_da_piazzare):
            messaggio_motore(f"   ❌ Non trovati {len(studenti_da_piazzare)} banchi consecutivi in prima fila")
            return False

        for i, studente in enumerate(studenti_da_piazzare):
            banco = banchi_consecutivi[i]
            banco.occupato_da = f"{studente.cognome}_{studente.nome}"
            ruolo = "adiacente diretto (col 1)" if i == 0 else f"col {banco.colonna}"
            messaggio_motore(f"   ✅ {studente.get_nome_completo()} → riga {banco.riga}, col {banco.colonna} ({ruolo})")

        # Fonte di verità per il contatore persistente del vicino del FISSO.
        self.nome_adiacente_fisso = studenti_da_piazzare[0].get_nome_completo()
        messaggio_motore(f"   📌 Adiacente diretto FISSO registrato: {self.nome_adiacente_fisso}")

        return True

    def _conta_coppie_riutilizzate(self):
        """Conta il solo dato statistico effettivamente consumato a valle."""
        self.stats['coppie_riutilizzate'] = sum(
            1
            for _s1, _s2, info in self.coppie_formate
            if info.get('valutazione') in (
                'RIUTILIZZATA',
                'BLACKLISTATA_SOFT',
            )
        )

    def _determina_modalita_trio_from_interface(self):
        """Restituisce la posizione del trio salvata all'avvio dell'assegnazione."""
        return getattr(self, 'modalita_trio', 'prima')

    def _trio_rispetta_vincoli_assoluti(self, trio_candidato):
        """Verifica le incompatibilità assolute nelle due adiacenze reali del trio."""
        studente1, studente2, studente3 = trio_candidato

        # Gli estremi non sono adiacenti: si controllano solo 1–2 e 2–3.
        coppie_interne = [(studente1, studente2), (studente2, studente3)]

        for s1, s2 in coppie_interne:
            if self.motore_vincoli._ha_incompatibilita_assoluta(s1, s2):
                if DEBUG_MOTORE:
                    messaggio_motore(f"   ❌ Trio scartato: incompatibilità assoluta {s1.cognome}-{s2.cognome}")
                return False

        return True
