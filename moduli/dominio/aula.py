# -*- coding: utf-8 -*-
"""
Definisce la geometria dell'aula e genera i layout dei banchi.

``PostoAula`` rappresenta una cella della griglia; ``ConfigurazioneAula``
costruisce le disposizioni a coppie o a terzetti e conserva i metadati usati
da interfaccia, Storico ed esportazioni.

Il blocco più largo a sinistra — coppia, trio, FISSO con coppia o FISSO con
trio — determina l'allineamento verticale delle altre file e degli arredi.

Parte di «PostiPerfetti». Autore: Omar Ceretta. Licenza: GNU GPLv3.
"""

import math
from dataclasses import dataclass


PREFERENZE_RESTO2_VALIDE = frozenset({
    'coppia',
    'due_quartetti',
})


def valida_preferenza_resto2(preferenza_resto2):
    """Valida la strategia usata quando il numero di studenti dà resto 2."""
    if preferenza_resto2 not in PREFERENZE_RESTO2_VALIDE:
        raise ValueError(
            "preferenza_resto2 non valida: "
            f"{preferenza_resto2!r}. "
            "Valori ammessi: 'coppia', 'due_quartetti'."
        )


def pianifica_blocco_finale_terzetti(num_rimanenti,
                                     preferenza_resto2='coppia'):
    """Restituisce terzetti pieni e blocchi finali della modalità terzetti.

    È la fonte unica condivisa da geometria e motore. Ogni blocco finale è una
    coppia ``(larghezza, tipo)`` con tipo ``coppia`` o ``quartetto``.
    """
    valida_preferenza_resto2(preferenza_resto2)

    resto = num_rimanenti % 3
    if resto == 1:
        return (num_rimanenti // 3 - 1, [(4, 'quartetto')])
    if resto == 2:
        if preferenza_resto2 == 'due_quartetti' and num_rimanenti >= 8:
            return ((num_rimanenti - 8) // 3,
                    [(4, 'quartetto'), (4, 'quartetto')])
        return (num_rimanenti // 3, [(2, 'coppia')])
    return (num_rimanenti // 3, [])


def numero_minimo_file_coppie(
    num_studenti: int,
    posti_per_fila: int,
    *,
    posizione_trio: str = "centro",
    ha_fisso: bool = False,
    massimo_file: int = 6,
) -> int:
    """Calcola le file minime usando la stessa geometria del motore."""
    if num_studenti < 1:
        return 1
    for numero_file in range(1, massimo_file + 1):
        aula = ConfigurazioneAula("Calcolo file minime")
        aula.crea_layout_standard(
            num_studenti,
            numero_file,
            posti_per_fila,
            posizione_trio,
            ha_fisso=ha_fisso,
        )
        if aula.posti_disponibili >= num_studenti:
            return numero_file
    return massimo_file


@dataclass
class PostoAula:
    """Rappresenta una cella della griglia dell'aula."""
    riga: int          # Numero fila (0 = riga arredi, 2+ = file banchi)
    colonna: int       # Numero colonna nella griglia
    tipo: str          # 'banco', 'corridoio', 'cattedra', 'lim', 'lavagna'
    occupato_da: str | None = None  # "Cognome_Nome" se occupato

    def is_banco(self) -> bool:
        """Verifica se questa posizione è un banco per studente."""
        return self.tipo == 'banco'

    def is_libero(self) -> bool:
        """Verifica se questo banco è libero."""
        return self.is_banco() and self.occupato_da is None


class ConfigurazioneAula:
    """Costruisce e descrive il layout dei posti nell'aula."""

    def __init__(self, nome_config="Aula Standard") -> None:
        self.nome_config = nome_config
        self.griglia = []           # griglia[riga][colonna] = PostoAula
        self.num_righe = 0
        self.num_colonne = 0
        self.posti_disponibili = 0

        # Mappatura elementi fissi (cattedra, LIM, lavagna)
        self.elementi_fissi = {}

        # === METADATI LAYOUT ===
        # Salvati per uso successivo da postiperfetti.py
        # (ricostruzione storico, export Excel, ecc.)
        self.larghezza_blocco_sx = 2  # 2=standard, 3=trio/FISSO+coppia, 4=FISSO+trio
        self.ha_fisso = False         # True se layout include studente FISSO
        self.ha_trio = False          # True se numero rimanenti è dispari
        self.fila_trio = None         # Indice della fila con il trio (0-based, None se assente)

        # === METADATI MODALITÀ TERZETTI ===
        # Riempiti da crea_layout_terzetti(); nel modo a coppie restano ai valori
        # predefiniti. Servono al rendering e alla ricostruzione dallo Storico.
        self.modalita = 'coppie'        # 'coppie' (default) | 'terzetti'
        self.tipo_blocco_finale = None  # (terzetti) None | 'coppia' | 'quartetto'
        self.fila_blocco_finale = None  # (terzetti) fila del blocco finale (0-based)
        self.file_blocchi_finali = []   # (terzetti) tutte le file del resto (0-based)
        self.terzetti_per_fila = 3      # (terzetti) blocchi-terzetto per fila
        self.num_terzetti = 0           # (terzetti) quanti terzetti "pieni"
        self.coord_fisso = None         # (terzetti) (riga,col) del banco FISSO o None

    # =========================================================================
    # CREAZIONE LAYOUT PRINCIPALE
    # =========================================================================

    def crea_layout_standard(self, num_studenti, num_file=None, posti_per_fila=None,
                              posizione_trio=None, ha_fisso=False) -> None:
        """Crea il layout a coppie, con eventuale trio e studente FISSO.

        Il FISSO occupa il primo posto a sinistra della prima fila. Il trio si
        forma quando gli studenti rimanenti sono dispari e viene collocato nella
        posizione richiesta da ``posizione_trio``.
        """
        # === CONFIGURAZIONE FILE E POSTI ===
        # Se i parametri non sono forniti, calcola automaticamente
        if num_file is None or posti_per_fila is None:
            studenti_per_fila = 6
            righe_banchi_necessarie = (num_studenti + studenti_per_fila - 1) // studenti_per_fila
            posti_per_fila = 6
        else:
            righe_banchi_necessarie = num_file
            studenti_per_fila = posti_per_fila

        # === LOGICA TRIO ===
        # Se c'è un FISSO, i "rimanenti" sono N-1; altrimenti N
        # Il trio si forma quando i rimanenti sono dispari
        num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti
        ha_trio = (num_rimanenti % 2 == 1)

        # Salva metadati per uso esterno
        self.ha_fisso = ha_fisso
        self.ha_trio = ha_trio

        # === DETERMINA FILA DEL TRIO ===
        # IMPORTANTE: Usa le file EFFETTIVAMENTE NECESSARIE, non quelle configurate.
        # Se l'utente configura 4 file ma ne servono solo 3 (es: 16 studenti / 6 posti),
        # il "centro" e l'"ultima" devono basarsi su 3 file, non su 4.
        # Altrimenti il trio finisce in una posizione che dopo la pulizia dei banchi
        # vuoti diventa l'ultima fila, indipendentemente dalla scelta dell'utente.
        file_effettive = math.ceil(num_studenti / studenti_per_fila)
        # Non superare le file configurate (se l'utente ne ha messe meno del necessario)
        file_effettive = max(1, min(file_effettive, righe_banchi_necessarie))

        fila_trio = None

        if ha_trio:
            posizioni_valide = {"prima", "centro", "ultima"}
            if posizione_trio not in posizioni_valide:
                raise ValueError(
                    "posizione_trio non valida: "
                    f"{posizione_trio!r}. "
                    "Valori ammessi: 'prima', 'centro', 'ultima'."
                )

            if posizione_trio == "prima":
                fila_trio = 0
            elif posizione_trio == "ultima":
                # Usa file_effettive: l'ultima fila reale, non l'ultima configurata
                fila_trio = file_effettive - 1
            else:  # posizione_trio == "centro"
                # Usa file_effettive: il centro reale, non il centro delle configurate
                fila_trio = file_effettive // 2

        self.fila_trio = fila_trio

        # === DETERMINA LARGHEZZA BLOCCO SINISTRO ===
        # Questo valore chiave determina l'allineamento di TUTTO il layout:
        # - 2: standard (solo coppie, nessun corridoio extra)
        # - 3: trio a sinistra OPPURE FISSO + coppia (doppio corridoio)
        # - 4: FISSO + trio nella stessa fila, prima fila (triplo corridoio)
        #
        # Il principio è: la fila "più larga" determina l'allineamento
        # di tutte le altre file e degli arredi.

        # Caso speciale: FISSO presente E trio nella prima fila (stessa fila del FISSO)
        fisso_con_trio_in_prima = ha_fisso and ha_trio and fila_trio == 0

        if fisso_con_trio_in_prima:
            # Caso più largo: [FISSO][T1][T2][T3] = 4 banchi a sinistra
            larghezza_blocco_sx = 4
        elif ha_trio or ha_fisso:
            # Trio a sinistra [T1][T2][T3] OPPURE FISSO + coppia [FI][A1][A2]
            # Entrambi producono 3 banchi a sinistra → stesso layout di griglia
            larghezza_blocco_sx = 3
        else:
            # Tutto standard: solo coppie da 2
            larghezza_blocco_sx = 2

        self.larghezza_blocco_sx = larghezza_blocco_sx

        # === DIMENSIONI GRIGLIA ===
        # Le colonne necessarie dipendono dal numero di blocchi-coppia:
        #   blocco_sx + corridoio(1) + [2 colonne + 1 corridoio] × (blocchi-2)
        #   + 2 colonne del blocco finale.
        # Ogni blocco oltre il terzo aggiunge tre colonne alla griglia.
        num_blocchi_coppia = max(3, posti_per_fila // 2)
        self.num_colonne = (
            larghezza_blocco_sx + 1
            + (num_blocchi_coppia - 2) * 3
            + 2
        )
        # Righe = file_banchi + 2 (riga 0 = arredi, riga 1 = spazio vuoto)
        self.num_righe = righe_banchi_necessarie + 2

        # === INIZIALIZZA GRIGLIA VUOTA ===
        # Ogni cella parte come 'corridoio' (spazio vuoto)
        self.griglia = []
        for r in range(self.num_righe):
            riga = []
            for c in range(self.num_colonne):
                riga.append(PostoAula(r, c, 'corridoio'))
            self.griglia.append(riga)

        # === RIGA 0: ARREDI (LIM, Cattedra, Lavagna) ===
        # Gli arredi usano le stesse posizioni colonna delle file normali,
        # così i corridoi sono perfettamente allineati verticalmente.
        # Gli arredi seguono i blocchi di banchi: LIM a sinistra, cattedra
        # al centro e lavagna a destra, anche nelle file da 8 o 10 posti.
        posizioni_arredi = self._calcola_posizioni_fila_normale(
            larghezza_blocco_sx, posti_per_fila)
        # Raggruppo le posizioni in blocchi-coppia: [(c1,c2), (c3,c4), ...]
        blocchi_arredi = [
            (posizioni_arredi[i], posizioni_arredi[i + 1])
            for i in range(0, len(posizioni_arredi), 2)
        ]
        blocco_lim = blocchi_arredi[0]                              # primo blocco
        blocco_cattedra = blocchi_arredi[len(blocchi_arredi) // 2]  # blocco centrale
        blocco_lavagna = blocchi_arredi[-1]                         # ultimo blocco
        for col in blocco_lim:
            self.griglia[0][col] = PostoAula(0, col, 'lim')
        for col in blocco_cattedra:
            self.griglia[0][col] = PostoAula(0, col, 'cattedra')
        for col in blocco_lavagna:
            self.griglia[0][col] = PostoAula(0, col, 'lavagna')

        # === RIGHE BANCHI ===
        # Ogni fila viene creata con il metodo appropriato:
        # - Prima fila con FISSO → _crea_fila_con_trio (se FISSO+coppia)
        #                        → _crea_fila_con_fisso_e_trio (se FISSO+trio)
        # - Fila con trio (senza FISSO in quella fila) → _crea_fila_con_trio
        # - Tutte le altre → _crea_fila_normale
        posti_creati = 0
        for fila_idx in range(righe_banchi_necessarie):
            riga_griglia = fila_idx + 2  # Offset: riga 0=arredi, riga 1=vuota

            if ha_fisso and fila_idx == 0:
                # ——— PRIMA FILA CON FISSO ———
                if fisso_con_trio_in_prima:
                    # FISSO + trio: 8 banchi [FI][T1][T2][T3] C [A1][A2] C [B1][B2]
                    # Passa i posti configurati: con 8/10 la fila FISSO+trio
                    # riceve anche il 4°/5° blocco-coppia.
                    posti_creati += self._crea_fila_con_fisso_e_trio(
                        riga_griglia, fila_idx + 1, posti_per_fila)
                else:
                    # FISSO + coppia: 7 banchi [FI][A1][A2] C [B1][B2] C [C1][C2]
                    # NB: il layout griglia è IDENTICO a quello del trio a sinistra!
                    # La differenza è solo chi occupa i banchi (FISSO vs T1)
                    posti_creati += self._crea_fila_con_trio(
                        riga_griglia, fila_idx + 1, posti_per_fila)

            elif fila_trio is not None and fila_idx == fila_trio:
                # ——— FILA CON TRIO (trio a sinistra, no FISSO in questa fila) ———
                posti_creati += self._crea_fila_con_trio(
                    riga_griglia, fila_idx + 1, posti_per_fila)

            else:
                # ——— FILA NORMALE (solo coppie, allineata al blocco sinistro) ———
                posti_creati += self._crea_fila_normale(
                    riga_griglia, fila_idx + 1, posti_per_fila, larghezza_blocco_sx)

        self.posti_disponibili = posti_creati

    # =========================================================================
    # CREAZIONE LAYOUT TERZETTI  (modalità "a terzetti", parallela alle coppie)
    # =========================================================================

    def crea_layout_terzetti(self, num_studenti, terzetti_per_fila=3,
                              posizione_blocco_finale=None, ha_fisso=False,
                              preferenza_resto2='coppia') -> None:
        """Crea il layout a terzetti con l'eventuale blocco finale.

        Il resto della divisione per tre produce una coppia, un quartetto oppure
        nessun blocco aggiuntivo, così nessuno resta isolato. Con l'opzione
        ``due_quartetti`` il resto di due studenti viene assorbito da due quartetti.

        Il blocco più largo determina l'allineamento di tutte le file e degli
        arredi. Il FISSO rimane membro del primo gruppo e ``ha_fisso`` viene
        conservato nei metadati del layout.

        Nei dati la prima fila ha indice 2; il renderer capovolge la griglia per
        mostrarla correttamente dalla prospettiva della cattedra.
        """
        posizioni_valide = {None, 'prima', 'centro', 'ultima'}
        if posizione_blocco_finale not in posizioni_valide:
            raise ValueError(
                "posizione_blocco_finale non valida: "
                f"{posizione_blocco_finale!r}. "
                "Valori ammessi: None, 'prima', 'centro', 'ultima'."
            )

        # === 1) FORMA DELLA PARTIZIONE (regola del resto) =====================
        # Tutti gli studenti siedono in gruppi -> num_rimanenti = N. (ha_fisso NON
        # riduce il conteggio: a terzetti il FISSO è MEMBRO di un terzetto.)
        num_rimanenti = num_studenti

        # Regola unica condivisa con il motore a terzetti.
        k_terzetti, blocchi_finali = pianifica_blocco_finale_terzetti(
            num_rimanenti, preferenza_resto2
        )

        num_blocchi_finali = len(blocchi_finali)
        num_blocchi = k_terzetti + num_blocchi_finali

        # Tipo "rappresentativo" del resto (per W e metadati): 'quartetto' se ce
        # n'è almeno uno (più largo), altrimenti 'coppia', altrimenti None.
        tipi_finali = {t for (_w, t) in blocchi_finali}
        if 'quartetto' in tipi_finali:
            tipo_blocco_finale = 'quartetto'
        elif 'coppia' in tipi_finali:
            tipo_blocco_finale = 'coppia'
        else:
            tipo_blocco_finale = None

        # === 2) FILE NECESSARIE ==============================================
        P = max(1, terzetti_per_fila)         # slot (blocchi) per fila
        righe_banchi = max(1, math.ceil(num_blocchi / P))

        # === FISSO: collocazione del resto rispetto al FISSO =================
        # FISSO in un TERZETTO (k>=1): il front-left (prima fila, slot 0) è suo,
        # i blocchi finali vanno in file NON frontali. Se NON ci sono terzetti
        # (degenere), il FISSO siede nel PRIMO blocco finale, che va front-left.
        fisso_nel_resto = (ha_fisso and k_terzetti == 0)

        # Ogni blocco finale occupa lo SLOT 0 di una fila DISTINTA: servono quindi
        # 'num_blocchi_finali' file con uno slot-0 dedicato. Col FISSO in un
        # terzetto, la prima fila è sua → quelle file vanno OLTRE la prima (+1).
        if num_blocchi_finali > 0:
            minimo_file = num_blocchi_finali
            if ha_fisso and not fisso_nel_resto:
                minimo_file = num_blocchi_finali + 1   # la prima fila è del FISSO
            righe_banchi = max(righe_banchi, minimo_file)

        # === 3) QUALI FILE OSPITANO I BLOCCHI FINALI (slot 0) ================
        # file_finali = file (0-based) con un blocco finale in slot 0, una per
        # blocco. La posizione richiesta (prima/centro/ultima) sceglie DOVE.
        file_finali = []
        if num_blocchi_finali == 1:
            # Un solo blocco finale (coppia o quartetto singolo): logica storica.
            if fisso_nel_resto:
                fila = 0                          # il FISSO è nel resto: front-left
            else:
                scelta = posizione_blocco_finale or "ultima"   # default sicuro
                if ha_fisso and scelta == "prima":
                    scelta = "ultima"             # difesa: il front-left è del FISSO
                if scelta == "prima":
                    fila = 0
                elif scelta == "centro":
                    fila = righe_banchi // 2
                else:  # scelta == "ultima"
                    fila = righe_banchi - 1
                fila = max(0, min(fila, righe_banchi - 1))
                if ha_fisso and fila == 0:        # mai in prima fila col FISSO
                    fila = righe_banchi - 1
            file_finali = [fila]
        elif num_blocchi_finali == 2:
            # DUE quartetti: slot 0 di DUE file CONSECUTIVE (impilati a sinistra).
            # La posizione sceglie la fila d'INIZIO della coppia; clamp ai limiti;
            # col FISSO la coppia non include la prima fila (è del suo terzetto),
            # salvo il degenere FISSO-nel-resto.
            if fisso_nel_resto:
                inizio = 0                        # il FISSO è in un quartetto: front
            else:
                scelta = posizione_blocco_finale or "ultima"
                if ha_fisso and scelta == "prima":
                    scelta = "ultima"
                if scelta == "prima":
                    inizio = 0
                elif scelta == "centro":
                    inizio = (righe_banchi - 2) // 2
                else:  # scelta == "ultima"
                    inizio = righe_banchi - 2
                inizio = max(0, min(inizio, righe_banchi - 2))
                if ha_fisso and inizio == 0:      # libera la prima fila per il FISSO
                    inizio = min(1, righe_banchi - 2)
            file_finali = [inizio, inizio + 1]

        # Mappa fila -> larghezza del blocco finale che vi sta in slot 0.
        slot0_finale = {}
        for fila, (larghezza, _tipo) in zip(file_finali, blocchi_finali):
            slot0_finale[fila] = larghezza

        # === 4) LARGHEZZA DEL BLOCCO SINISTRO PIÙ LARGO (W) ==================
        # Solo il quartetto (4) è più largo di un terzetto (3); la coppia (2) non
        # allarga. W governa colonne e allineamento arredi.
        W = 4 if tipo_blocco_finale == 'quartetto' else 3

        # === 5) METADATI PER RENDERING E STORICO ===============================
        self.modalita = 'terzetti'
        self.terzetti_per_fila = P
        self.larghezza_blocco_sx = W          # riuso: "blocco più largo presente"
        self.tipo_blocco_finale = tipo_blocco_finale
        self.fila_blocco_finale = file_finali[0] if file_finali else None
        self.file_blocchi_finali = list(file_finali)   # tutte le file del resto
        self.num_terzetti = k_terzetti
        self.ha_fisso = ha_fisso              # True se c'è un FISSO
        self.ha_trio = False                  # concetto del modo a coppie: non qui
        self.fila_trio = None
        # Banco del FISSO = front-left = prima fila di banchi (riga 2), colonna 0.
        self.coord_fisso = (2, 0) if ha_fisso else None

        # === 6) DIMENSIONI GRIGLIA ===========================================
        self.num_colonne = self._colonna_inizio_slot(P - 1, W) + 3
        self.num_righe = righe_banchi + 2     # riga 0 = arredi, riga 1 = spaziatore

        self.griglia = []
        for r in range(self.num_righe):
            riga = [PostoAula(r, c, 'corridoio') for c in range(self.num_colonne)]
            self.griglia.append(riga)

        # === 7) RIGA 0: ARREDI (LIM, Cattedra, Lavagna) ======================
        nomi_arredi = ['lim', 'cattedra', 'lavagna']
        for j, nome in enumerate(nomi_arredi):
            if j >= P:
                break                          # con meno di 3 slot non entrano tutti
            c0 = self._colonna_inizio_slot(j, W)
            self.griglia[0][c0] = PostoAula(0, c0, nome)
            self.griglia[0][c0 + 1] = PostoAula(0, c0 + 1, nome)

        # === 8) POSA DEI BLOCCHI (terzetti + blocchi finali) =================
        # Row-major: lo slot 0 di una fila in 'slot0_finale' ospita un blocco
        # finale (coppia/quartetto); gli altri slot ospitano terzetti finché ce
        # ne sono; gli slot in eccesso restano corridoio.
        terzetti_da_posare = k_terzetti
        posti_creati = 0
        for fila in range(righe_banchi):
            riga_griglia = fila + 2           # offset arredi (0) + spaziatore (1)
            for slot in range(P):
                if slot == 0 and fila in slot0_finale:
                    larghezza = slot0_finale[fila]      # blocco finale qui
                elif terzetti_da_posare > 0:
                    larghezza = 3                       # un terzetto
                    terzetti_da_posare -= 1
                else:
                    continue                            # slot vuoto: corridoio
                c0 = self._colonna_inizio_slot(slot, W)
                posti_creati += self._posa_blocco(riga_griglia, c0, larghezza)

        self.posti_disponibili = posti_creati

    def _colonna_inizio_slot(self, slot, larghezza_blocco_sx) -> int:
        """Restituisce la colonna iniziale di uno slot per terzetti.

        Lo slot sinistro parte da zero e riserva la larghezza del blocco più
        grande. Gli slot successivi occupano tre colonne, separate da un corridoio.
        """
        if slot <= 0:
            return 0
        return larghezza_blocco_sx + 1 + (slot - 1) * 4

    def _posa_blocco(self, riga_griglia, col_inizio, larghezza) -> int:
        """Crea banchi consecutivi e restituisce quanti rientrano nella griglia."""
        creati = 0
        for k in range(larghezza):
            col = col_inizio + k
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                creati += 1
        return creati

    # =========================================================================
    # CALCOLO POSIZIONI COLONNA
    # =========================================================================

    def _calcola_posizioni_fila_normale(self, larghezza_blocco_sx,
                                        posti_per_fila=6) -> list[int]:
        """Calcola le colonne dei banchi nelle file normali e degli arredi.

        La coppia sinistra occupa le colonne 0 e 1. Gli eventuali corridoi
        aggiuntivi compensano la larghezza del blocco speciale; ogni coppia
        successiva è preceduta da un corridoio. La formula copre da 4 a 10 posti.
        """
        # Una larghezza imprevista non deve rompere il layout: valori inferiori
        # a 2 vengono riportati alla larghezza minima di una coppia.
        if larghezza_blocco_sx < 2:
            print(f"   ⚠️ larghezza_blocco_sx={larghezza_blocco_sx} non prevista, uso 2")
            larghezza_blocco_sx = 2

        # Si calcolano almeno tre blocchi perché gli arredi usano sempre le
        # prime sei posizioni; la fila crea poi soltanto i banchi necessari.
        num_blocchi = max(3, posti_per_fila // 2)

        # Blocco 1: coppia sinistra, sempre in colonne 0-1.
        posizioni = [0, 1]

        # Blocchi dal 2° in poi: formula generale (vedi docstring).
        for blocco in range(2, num_blocchi + 1):
            inizio = larghezza_blocco_sx + 1 + (blocco - 2) * 3
            posizioni.extend([inizio, inizio + 1])

        return posizioni

    # =========================================================================
    # CREAZIONE FILE SPECIFICHE
    # =========================================================================

    def _crea_fila_normale(self, riga_griglia, numero_fila, posti_necessari,
                            larghezza_blocco_sx=2) -> int:
        """Crea una fila di coppie allineata al blocco sinistro più largo."""

        # Ottieni le 6 posizioni colonna per file normali
        # Passa anche i posti richiesti: con 8/10 la lista include il 4°/5° blocco.
        posizioni_banchi = self._calcola_posizioni_fila_normale(
            larghezza_blocco_sx, posti_necessari)

        posti_creati = 0
        for i in range(min(posti_necessari, len(posizioni_banchi))):
            col = posizioni_banchi[i]
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    def _crea_fila_con_trio(self, riga_griglia, numero_fila,
                            posti_per_fila=6) -> int:
        """Crea un blocco sinistro da tre posti seguito da coppie.

        La stessa geometria serve sia al trio sia al FISSO con una coppia:
        cambia chi occupa i posti, non la posizione dei banchi.
        """
        # Blocco sinistro da 3 banchi consecutivi (trio oppure FISSO+coppia).
        posizioni_banchi = [0, 1, 2]

        # Blocchi-coppia successivi: stesso numero di blocchi delle file
        # normali (num_blocchi = max(2, posti//2)), stesso allineamento del
        # blocco sinistro da 3: il blocco k (k >= 2) inizia alla colonna
        # 3 + 1 + (k-2)*3 = 4, 7, 10, 13...
        num_blocchi = max(2, posti_per_fila // 2)
        for blocco in range(2, num_blocchi + 1):
            inizio = 4 + (blocco - 2) * 3
            posizioni_banchi.extend([inizio, inizio + 1])

        posti_creati = 0
        for col in posizioni_banchi:
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    def _crea_fila_con_fisso_e_trio(self, riga_griglia, numero_fila,
                                    posti_per_fila=6) -> int:
        """Crea il blocco sinistro FISSO più trio, seguito da coppie.

        Questa geometria si usa quando il trio occupa la prima fila insieme
        allo studente FISSO.
        """
        # Blocco sinistro da 4 banchi consecutivi: FISSO + i 3 del trio.
        posizioni_banchi = [0, 1, 2, 3]

        # Blocchi-coppia successivi, allineati al blocco sinistro da 4:
        # il blocco k (k >= 2) inizia alla colonna 4 + 1 + (k-2)*3 = 5, 8, 11, 14...
        num_blocchi = max(2, posti_per_fila // 2)
        for blocco in range(2, num_blocchi + 1):
            inizio = 5 + (blocco - 2) * 3
            posizioni_banchi.extend([inizio, inizio + 1])

        posti_creati = 0
        for col in posizioni_banchi:
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    # =========================================================================
    # INTERROGAZIONE LAYOUT
    # =========================================================================

    def get_banchi_per_fila(self) -> list[list[PostoAula]]:
        """Restituisce i banchi organizzati dalla prima all'ultima fila."""
        banchi_per_fila = []

        for riga_idx in range(self.num_righe):
            banchi_fila = []
            for posto in self.griglia[riga_idx]:
                if posto.is_banco():
                    banchi_fila.append(posto)

            if banchi_fila:  # Se ci sono banchi in questa fila
                banchi_per_fila.append(banchi_fila)

        return banchi_per_fila

    def capienze_file_banchi(self) -> tuple[int, ...]:
        """Restituisce il numero effettivo di posti in ciascuna fila."""
        return tuple(len(fila) for fila in self.get_banchi_per_fila())

    # =========================================================================
    # PULIZIA
    # =========================================================================

    def rimuovi_banchi_vuoti(self) -> None:
        """Trasforma in corridoi i banchi rimasti vuoti dopo l'assegnazione."""
        # Ogni banco vuoto (non occupato) diventa corridoio.
        for riga in self.griglia:
            for posto in riga:
                if posto.tipo == 'banco' and posto.occupato_da is None:
                    posto.tipo = 'corridoio'

        # Conta i banchi rimasti (gli occupati) e aggiorna i posti disponibili.
        banchi_dopo = 0
        for riga in self.griglia:
            for posto in riga:
                if posto.tipo == 'banco':
                    banchi_dopo += 1
        self.posti_disponibili = banchi_dopo

    # =========================================================================
    # RAGGRUPPAMENTO DEI BANCHI
    # =========================================================================

    def _raggruppa_banchi_in_blocchi(self, riga) -> list:
        """Raggruppa i banchi consecutivi di una riga; i corridoi separano i blocchi."""
        blocchi = []
        blocco_corrente = []
        colonna_precedente = None

        for posto in riga:
            if posto.tipo == 'banco':
                # Continuità di colonna col banco precedente -> stesso blocco
                if colonna_precedente is not None and posto.colonna == colonna_precedente + 1:
                    blocco_corrente.append(posto)
                else:
                    # Discontinuità -> chiudo il blocco aperto e ne apro uno nuovo
                    if blocco_corrente:
                        blocchi.append(blocco_corrente)
                    blocco_corrente = [posto]
                colonna_precedente = posto.colonna
            else:
                # Non è un banco -> chiude il blocco eventualmente aperto
                if blocco_corrente:
                    blocchi.append(blocco_corrente)
                    blocco_corrente = []
                colonna_precedente = None

        # Chiudo l'ultimo blocco rimasto aperto a fine riga
        if blocco_corrente:
            blocchi.append(blocco_corrente)

        return blocchi

    # =========================================================================
    # PIAZZAMENTO DEI GRUPPI SUI BANCHI
    # =========================================================================

    def capienza_prima_fila_terzetti(self) -> dict:
        """Restituisce la capienza della prima fila per terzetti e blocchi finali.

        I due valori restano separati perché ogni gruppo può occupare soltanto
        un blocco della propria dimensione.
        """
        if self.modalita != 'terzetti':
            return {
                'terzetti': 0,
                'resti': 0,
                'posti': 0,
                'dimensioni_resti': [],
            }

        prima_riga_banchi = None
        for indice_riga, riga in enumerate(self.griglia):
            if indice_riga < 2:
                continue
            blocchi = self._raggruppa_banchi_in_blocchi(riga)
            if blocchi:
                prima_riga_banchi = blocchi
                break

        if prima_riga_banchi is None:
            return {
                'terzetti': 0,
                'resti': 0,
                'posti': 0,
                'dimensioni_resti': [],
            }

        blocchi_terzetto = [
            blocco for blocco in prima_riga_banchi
            if len(blocco) == 3
        ]
        blocchi_resto = [
            blocco for blocco in prima_riga_banchi
            if len(blocco) != 3
        ]

        return {
            'terzetti': len(blocchi_terzetto),
            'resti': len(blocchi_resto),
            'posti': sum(len(blocco) for blocco in prima_riga_banchi),
            'dimensioni_resti': [len(blocco) for blocco in blocchi_resto],
        }

    def _siedi(self, blocco, membri):
        """Colloca i membri da sinistra a destra e salva il loro identificativo."""
        for posto, studente in zip(blocco, membri):
            posto.occupato_da = f"{studente.cognome}_{studente.nome}"

    def piazza_gruppi_terzetti(self, gruppi) -> dict:
        """Colloca nei banchi i gruppi prodotti dal motore di partizione.

        I blocchi finali occupano gli spazi della stessa dimensione. I terzetti
        vengono ordinati per priorità FISSO, PRIMA, neutri e ULTIMA, mentre i
        blocchi vengono ordinati dalla prima all'ultima fila e da sinistra a
        destra. La guardia finale segnala eventuali studenti PRIMA rimasti fuori
        dalla capienza frontale.
        """
        # 1) Raccogli i blocchi della griglia, separando i resto dai terzetti.
        #    Possono esserci PIÙ blocchi-resto (2 quartetti), non più uno solo.
        blocchi_terzetto = []          # liste di PostoAula, una per terzetto
        blocchi_resto = []             # tutti i blocchi NON da 3 (coppia/quartetto)
        for riga in self.griglia:
            for blocco in self._raggruppa_banchi_in_blocchi(riga):
                if len(blocco) == 3:
                    blocchi_terzetto.append(blocco)
                else:
                    blocchi_resto.append(blocco)

        # 2) Separa i gruppi: i resto (≠3 membri) e i terzetti.
        gruppi_terzetto = [g for g in gruppi if len(g.membri) == 3]
        gruppi_resto = [g for g in gruppi if len(g.membri) != 3]

        # Guardia strutturale: ``zip`` troncherebbe in silenzio se il motore e
        # la geometria producessero quantità o dimensioni diverse per i blocchi
        # finali. Il controllo avviene prima di sedere chiunque, così una futura
        # regressione non può lasciare una disposizione parziale apparentemente
        # valida.
        dimensioni_gruppi_resto = sorted(len(g.membri) for g in gruppi_resto)
        dimensioni_blocchi_resto = sorted(len(b) for b in blocchi_resto)
        if dimensioni_gruppi_resto != dimensioni_blocchi_resto:
            messaggio = (
                "Errore interno: i gruppi finali prodotti dal motore "
                f"{dimensioni_gruppi_resto} non corrispondono ai blocchi "
                f"fisici dell'aula {dimensioni_blocchi_resto}. "
                "L'assegnazione deve essere scartata."
            )
            print(f"   ⚠️ piazza_gruppi_terzetti: {messaggio}")
            return {
                'avvisi': [messaggio],
                'prima_fuori_capienza': 0,
                'valido_prima': True,
                'valido_struttura': False,
            }

        # 3) Colloca i resto nei blocchi dedicati. Se un resto contiene il FISSO
        #    (coppia col FISSO, o caso degenere 2 quartetti), quel gruppo va nel
        #    blocco più FRONTALE: ordino i gruppi col FISSO per primo e i blocchi
        #    per posizione (riga crescente = front first), poi accoppio.
        def _priorita_resto(gruppo):
            note = [
                getattr(m, 'nota_posizione', 'NORMALE')
                for m in gruppo.membri
            ]
            if 'FISSO' in note:
                return 0
            if 'PRIMA' in note:
                return 1
            return 2

        gruppi_resto.sort(key=_priorita_resto)
        blocchi_resto.sort(key=lambda b: (b[0].riga, b[0].colonna))

        # Associa ogni gruppo al primo blocco frontale della stessa dimensione.
        # Oggi i due blocchi-resto possibili sono entrambi quartetti; la scelta
        # per dimensione rende però esplicito l'invariante e protegge evoluzioni
        # future con resti di taglia diversa.
        blocchi_disponibili = list(blocchi_resto)
        abbinamenti_resto = []
        for gruppo in gruppi_resto:
            indice_blocco = next(
                i for i, blocco in enumerate(blocchi_disponibili)
                if len(blocco) == len(gruppo.membri)
            )
            blocco = blocchi_disponibili.pop(indice_blocco)
            abbinamenti_resto.append((gruppo, blocco))

        for gruppo, blocco in abbinamenti_resto:
            self._siedi(blocco, gruppo.membri)

        # 4) Ordina i terzetti per priorità (FISSO, PRIMA, neutri, ULTIMA).
        def priorita(gruppo):
            note = [getattr(m, 'nota_posizione', 'NORMALE') for m in gruppo.membri]
            if 'FISSO' in note:
                return 0
            if 'PRIMA' in note:
                return 1
            if 'ULTIMA' in note:
                return 3
            return 2
        gruppi_terzetto = sorted(gruppi_terzetto, key=priorita)

        # 5) Ordina i blocchi-terzetto per posizione: riga crescente (front
        #    first), poi colonna crescente (sinistra prima).
        blocchi_terzetto.sort(key=lambda b: (b[0].riga, b[0].colonna))

        # 6) Accoppia gruppi e blocchi e siedi i membri.
        n = min(len(gruppi_terzetto), len(blocchi_terzetto))
        if len(gruppi_terzetto) != len(blocchi_terzetto):
            # Difensivo: non dovrebbe mai accadere (stessa regola del resto in
            # geometria e motore); meglio saperlo che sedere a metà in silenzio.
            print(f"   ⚠️ piazza_gruppi_terzetti: {len(gruppi_terzetto)} terzetti "
                  f"ma {len(blocchi_terzetto)} blocchi (uso {n}).")
        for gruppo, blocco in zip(gruppi_terzetto[:n], blocchi_terzetto[:n]):
            self._siedi(blocco, gruppo.membri)

        # 7) GUARDIA FINALE DEL VINCOLO ASSOLUTO PRIMA.
        # Il motore deve avere già escluso ogni partizione non collocabile.
        # Questo controllo resta come rete difensiva contro regressioni future.
        PRIMA_RIGA = 2
        prima_fuori = 0

        for gruppo, blocco in zip(
                gruppi_terzetto[:n],
                blocchi_terzetto[:n]):
            note = [
                getattr(m, 'nota_posizione', 'NORMALE')
                for m in gruppo.membri
            ]
            if 'PRIMA' in note and blocco[0].riga != PRIMA_RIGA:
                prima_fuori += 1

        for gruppo, blocco in abbinamenti_resto:
            note = [
                getattr(m, 'nota_posizione', 'NORMALE')
                for m in gruppo.membri
            ]
            if 'PRIMA' in note and blocco[0].riga != PRIMA_RIGA:
                prima_fuori += 1

        valido_prima = (prima_fuori == 0)
        avvisi = []

        if not valido_prima:
            avvisi.append(
                "Errore interno: una partizione ha collocato gruppi con "
                "studenti PRIMA fuori dalla prima fila. L'assegnazione "
                "deve essere scartata."
            )

        return {
            'avvisi': avvisi,
            'prima_fuori_capienza': prima_fuori,
            'valido_prima': valido_prima,
            'valido_struttura': True,
        }

