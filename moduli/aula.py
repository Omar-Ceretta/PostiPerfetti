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
    Modulo per la gestione dell'aula e dei layout di disposizione banchi.
    Contiene configurazioni predefinite e logica di posizionamento.

    ══════════════════════════════════════════════════════════════════
    PRINCIPIO "BLOCCO SINISTRO UNIFICATO"
    ══════════════════════════════════════════════════════════════════
    Il trio e/o il FISSO occupano sempre il BLOCCO SINISTRO della fila.
    Le file normali e gli arredi si allineano con corridoi extra a destra
    del blocco sinistro, così che le coppie centrali e destre risultino
    sempre alla stessa altezza (colonna) in tutte le file.

    ┌─────────────────────┬───────────┬─────────────────┬─────────────┐
    │ Situazione          │ Blocco sx │ Corridoi extra  │ num_colonne │
    ├─────────────────────┼───────────┼─────────────────┼─────────────┤
    │ N pari, no FISSO    │ 2 (coppia)│ nessuno         │ 8           │
    │ N dispari / FISSO+C │ 3 (trio)  │ doppio (col 2-3)│ 9           │
    │ FISSO + trio        │ 4         │ triplo (col 2-4)│ 10          │
    └─────────────────────┴───────────┴─────────────────┴─────────────┘

    Posizioni colonna per ogni caso:
    larghezza 2: [0,1]    C    [3,4]    C    [6,7]     → 8 colonne
    larghezza 3: [0,1]   CC    [4,5]    C    [7,8]     → 9 colonne
    larghezza 4: [0,1]  CCC    [5,6]    C    [8,9]     → 10 colonne

    Fila trio (larghezza 3):         [0,1,2]  C  [4,5]  C  [7,8]
    Fila FISSO+coppia (larghezza 3): [0,1,2]  C  [4,5]  C  [7,8]  (identico!)
    Fila FISSO+trio (larghezza 4):   [0,1,2,3] C [5,6]  C  [8,9]
    ══════════════════════════════════════════════════════════════════
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict


@dataclass
class PostoAula:
    """
    Rappresenta una singola posizione nell'aula.
    Ogni cella della griglia è un PostoAula con un tipo specifico.
    """
    riga: int          # Numero fila (0 = riga arredi, 2+ = file banchi)
    colonna: int       # Numero colonna nella griglia
    tipo: str          # 'banco', 'corridoio', 'cattedra', 'lim', 'lavagna'
    occupato_da: Optional[str] = None  # "Cognome_Nome" se occupato

    def is_banco(self):
        """Verifica se questa posizione è un banco per studente."""
        return self.tipo == 'banco'

    def is_libero(self):
        """Verifica se questo banco è libero."""
        return self.is_banco() and self.occupato_da is None


class ConfigurazioneAula:
    """
    Gestisce la configurazione e il layout dell'aula.
    Crea la griglia di PostoAula in base al numero di studenti,
    alla presenza di un trio e/o di uno studente FISSO.
    """

    def __init__(self, nome_config="Aula Standard"):
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

    # =========================================================================
    # CREAZIONE LAYOUT PRINCIPALE
    # =========================================================================

    def crea_layout_standard(self, num_studenti, num_file=None, posti_per_fila=None,
                              posizione_trio=None, ha_fisso=False):
        """
        Crea un layout standard per aula tradizionale.
        VERSIONE BLOCCO SINISTRO: trio sempre a sinistra, supporto FISSO.

        Args:
            num_studenti (int): Numero TOTALE di studenti (incluso eventuale FISSO)
            num_file (int, optional): Numero di file di banchi configurate
            posti_per_fila (int, optional): Posti per fila configurati (default 6)
            posizione_trio (str, optional): "prima", "ultima", "centro" o None
            ha_fisso (bool): True se c'è uno studente con posizione FISSO

        Note:
            Quando ha_fisso=True, il FISSO occupa sempre il primo banco a sinistra
            della PRIMA fila. I rimanenti N-1 studenti vengono distribuiti normalmente.
            Se N-1 è dispari, si forma un trio posizionato secondo posizione_trio.
        """
        print(f"Creando layout dinamico per {num_studenti} studenti...")
        if ha_fisso:
            print(f"   🎯 Studente FISSO presente → rimanenti: {num_studenti - 1}")

        # === CONFIGURAZIONE FILE E POSTI ===
        # Se i parametri non sono forniti, calcola automaticamente
        if num_file is None or posti_per_fila is None:
            studenti_per_fila = 6
            righe_banchi_necessarie = (num_studenti + studenti_per_fila - 1) // studenti_per_fila
            posti_per_fila = 6
            print(f"   Modalità legacy: {righe_banchi_necessarie} file da 6 posti")
        else:
            righe_banchi_necessarie = num_file
            studenti_per_fila = posti_per_fila
            print(f"   Modalità configurata: {num_file} file da {posti_per_fila} posti")

        # === LOGICA TRIO ===
        # Se c'è un FISSO, i "rimanenti" sono N-1; altrimenti N
        # Il trio si forma quando i rimanenti sono dispari
        num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti
        ha_trio = (num_rimanenti % 2 == 1)

        # Salva metadati per uso esterno
        self.ha_fisso = ha_fisso
        self.ha_trio = ha_trio

        if ha_trio:
            print(f"   📐 Trio necessario (rimanenti dispari: {num_rimanenti})")
        else:
            print(f"   📐 Solo coppie (rimanenti pari: {num_rimanenti})")

        # === DETERMINA FILA DEL TRIO ===
        # IMPORTANTE: Usa le file EFFETTIVAMENTE NECESSARIE, non quelle configurate.
        # Se l'utente configura 4 file ma ne servono solo 3 (es: 16 studenti / 6 posti),
        # il "centro" e l'"ultima" devono basarsi su 3 file, non su 4.
        # Altrimenti il trio finisce in una posizione che dopo la pulizia dei banchi
        # vuoti diventa l'ultima fila, indipendentemente dalla scelta dell'utente.
        file_effettive = math.ceil(num_studenti / studenti_per_fila)
        # Non superare le file configurate (se l'utente ne ha messe meno del necessario)
        file_effettive = max(1, min(file_effettive, righe_banchi_necessarie))
        print(f"   📊 File configurate: {righe_banchi_necessarie}, File effettive: {file_effettive}")

        fila_trio = None
        if ha_trio and posizione_trio:
            if posizione_trio == "prima":
                fila_trio = 0
                print(f"   Trio posizionato: PRIMA FILA")
            elif posizione_trio == "ultima":
                # Usa file_effettive: l'ultima fila reale, non l'ultima configurata
                fila_trio = file_effettive - 1
                print(f"   Trio posizionato: ULTIMA FILA (fila {fila_trio + 1} di {file_effettive} effettive)")
            elif posizione_trio == "centro":
                # Usa file_effettive: il centro reale, non il centro delle configurate
                fila_trio = file_effettive // 2
                print(f"   Trio posizionato: CENTRO (fila {fila_trio + 1} di {file_effettive} effettive)")

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
            print(f"   📐 Layout: FISSO + trio in prima fila (blocco sx = 4)")
        elif ha_trio or ha_fisso:
            # Trio a sinistra [T1][T2][T3] OPPURE FISSO + coppia [FI][A1][A2]
            # Entrambi producono 3 banchi a sinistra → stesso layout di griglia
            larghezza_blocco_sx = 3
            if ha_fisso and ha_trio:
                print(f"   📐 Layout: FISSO + coppia in prima fila, trio altrove (blocco sx = 3)")
            elif ha_fisso:
                print(f"   📐 Layout: FISSO + coppia in prima fila (blocco sx = 3)")
            else:
                print(f"   📐 Layout: trio a sinistra (blocco sx = 3)")
        else:
            # Tutto standard: solo coppie da 2
            larghezza_blocco_sx = 2
            print(f"   📐 Layout: standard solo coppie (blocco sx = 2)")

        self.larghezza_blocco_sx = larghezza_blocco_sx

        # === DIMENSIONI GRIGLIA ===
        # Numero colonne = blocco_sx + corridoio(1) + coppia(2) + corridoio(1) + coppia(2)
        # Esempio: blocco 3 → 3 + 1 + 2 + 1 + 2 = 9 colonne
        self.num_colonne = larghezza_blocco_sx + 1 + 2 + 1 + 2
        # Righe = file_banchi + 2 (riga 0 = arredi, riga 1 = spazio vuoto)
        self.num_righe = righe_banchi_necessarie + 2

        print(f"   Griglia: {self.num_righe} righe × {self.num_colonne} colonne")

        # === INIZIALIZZA GRIGLIA VUOTA ===
        # Ogni cella parte come 'corridoio' (spazio vuoto)
        self.griglia = []
        for r in range(self.num_righe):
            riga = []
            for c in range(self.num_colonne):
                riga.append(PostoAula(r, c, 'corridoio'))
            self.griglia.append(riga)

        # === RIGA 0: ARREDI (LIM, Cattedra, Lavagna) ===
        # Gli arredi usano le stesse posizioni colonna delle file normali
        # così i corridoi sono perfettamente allineati verticalmente
        posizioni_arredi = self._calcola_posizioni_fila_normale(larghezza_blocco_sx)
        # posizioni_arredi ha 6 elementi: [sx1, sx2, centro1, centro2, dx1, dx2]
        self.griglia[0][posizioni_arredi[0]] = PostoAula(0, posizioni_arredi[0], 'lim')
        self.griglia[0][posizioni_arredi[1]] = PostoAula(0, posizioni_arredi[1], 'lim')
        self.griglia[0][posizioni_arredi[2]] = PostoAula(0, posizioni_arredi[2], 'cattedra')
        self.griglia[0][posizioni_arredi[3]] = PostoAula(0, posizioni_arredi[3], 'cattedra')
        self.griglia[0][posizioni_arredi[4]] = PostoAula(0, posizioni_arredi[4], 'lavagna')
        self.griglia[0][posizioni_arredi[5]] = PostoAula(0, posizioni_arredi[5], 'lavagna')

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
                    posti_creati += self._crea_fila_con_fisso_e_trio(
                        riga_griglia, fila_idx + 1)
                else:
                    # FISSO + coppia: 7 banchi [FI][A1][A2] C [B1][B2] C [C1][C2]
                    # NB: il layout griglia è IDENTICO a quello del trio a sinistra!
                    # La differenza è solo chi occupa i banchi (FISSO vs T1)
                    posti_creati += self._crea_fila_con_trio(
                        riga_griglia, fila_idx + 1)

            elif fila_trio is not None and fila_idx == fila_trio:
                # ——— FILA CON TRIO (trio a sinistra, no FISSO in questa fila) ———
                posti_creati += self._crea_fila_con_trio(
                    riga_griglia, fila_idx + 1)

            else:
                # ——— FILA NORMALE (solo coppie, allineata al blocco sinistro) ———
                posti_creati += self._crea_fila_normale(
                    riga_griglia, fila_idx + 1, posti_per_fila, larghezza_blocco_sx)

        self.posti_disponibili = posti_creati

        print(f"   Layout: {righe_banchi_necessarie} file di banchi")
        print(f"   Capacità totale: {posti_creati} posti")
        print(f"   Studenti da sistemare: {num_studenti}")
        print(f"✅ Layout creato: {self.posti_disponibili} posti totali")

    # =========================================================================
    # CALCOLO POSIZIONI COLONNA
    # =========================================================================

    def _calcola_posizioni_fila_normale(self, larghezza_blocco_sx):
        """
        Calcola le 6 posizioni colonna per file normali e arredi,
        allineate al blocco sinistro più largo presente nel layout.

        Il principio è: la coppia sinistra (2 banchi) sta sempre
        in colonne 0-1. I corridoi extra si inseriscono DOPO la coppia
        sinistra, prima della coppia centrale.

        Args:
            larghezza_blocco_sx (int): Larghezza del blocco sinistro più largo
                2 = standard, 3 = trio/FISSO+coppia, 4 = FISSO+trio

        Returns:
            list: 6 posizioni colonna [sx1, sx2, centro1, centro2, dx1, dx2]

        Esempio visuale (larghezza 3):
            col: 0  1  2  3  4  5  6  7  8
                [A][B] .  . [C][D] . [E][F]
                 ↑  ↑        ↑  ↑     ↑  ↑
              coppia sx    coppia C  coppia dx
              (col 2-3 = doppio corridoio per allinearsi al trio/FISSO+coppia)
        """
        if larghezza_blocco_sx == 2:
            # Standard: [0,1] C [3,4] C [6,7] — nessun corridoio extra
            return [0, 1, 3, 4, 6, 7]

        elif larghezza_blocco_sx == 3:
            # Doppio corridoio (col 2-3): [0,1] CC [4,5] C [7,8]
            return [0, 1, 4, 5, 7, 8]

        elif larghezza_blocco_sx == 4:
            # Triplo corridoio (col 2-3-4): [0,1] CCC [5,6] C [8,9]
            return [0, 1, 5, 6, 8, 9]

        else:
            # Fallback sicuro: layout standard
            print(f"   ⚠️ larghezza_blocco_sx={larghezza_blocco_sx} non prevista, uso standard")
            return [0, 1, 3, 4, 6, 7]

    # =========================================================================
    # CREAZIONE FILE SPECIFICHE
    # =========================================================================

    def _crea_fila_normale(self, riga_griglia, numero_fila, posti_necessari,
                            larghezza_blocco_sx=2):
        """
        Crea una fila normale con sole coppie, allineata al blocco sinistro.

        I banchi vengono posizionati nelle colonne calcolate da
        _calcola_posizioni_fila_normale(), che inserisce i corridoi extra
        necessari per l'allineamento verticale.

        Args:
            riga_griglia (int): Indice riga nella griglia (0-based)
            numero_fila (int): Numero fila per log (1-based, solo estetico)
            posti_necessari (int): Quanti banchi creare (default 6)
            larghezza_blocco_sx (int): Per calcolare l'allineamento corridoi
        """
        print(f"   Fila {numero_fila}: layout normale ({posti_necessari} posti)")

        # Ottieni le 6 posizioni colonna per file normali
        posizioni_banchi = self._calcola_posizioni_fila_normale(larghezza_blocco_sx)

        posti_creati = 0
        for i in range(min(posti_necessari, len(posizioni_banchi))):
            col = posizioni_banchi[i]
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    def _crea_fila_con_trio(self, riga_griglia, numero_fila):
        """
        Crea una fila con TRIO A SINISTRA + 2 coppie normali.

        Layout: [T1][T2][T3]  __  [A1][A2]  __  [B1][B2]   = 7 posti
        Colonne:  0   1   2   3    4   5    6    7   8

        NOTA IMPORTANTE: questo metodo viene usato anche per la fila
        FISSO + coppia, perché il layout di griglia è IDENTICO:
          [FI][A1][A2]  __  [B1][B2]  __  [C1][C2]
        La differenza è solo CHI occupa i banchi, non DOVE sono i banchi.

        Args:
            riga_griglia (int): Indice riga nella griglia
            numero_fila (int): Numero fila per log (1-based)
        """
        print(f"   Fila {numero_fila}: layout trio/blocco-3 (7 posti)")

        # 3 banchi consecutivi a sinistra + corridoio + 2 + corridoio + 2
        posizioni_banchi = [0, 1, 2, 4, 5, 7, 8]

        posti_creati = 0
        for col in posizioni_banchi:
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    def _crea_fila_con_fisso_e_trio(self, riga_griglia, numero_fila):
        """
        Crea una fila con FISSO + TRIO a sinistra + 2 coppie normali.

        Layout: [FI][T1][T2][T3]  __  [A1][A2]  __  [B1][B2]   = 8 posti
        Colonne:  0   1   2   3   4    5   6    7    8   9

        Usata SOLO quando:
        - C'è uno studente FISSO (ha_fisso=True)
        - I rimanenti N-1 sono dispari (ha_trio=True)
        - Il trio è posizionato in PRIMA FILA (posizione_trio="prima")

        Args:
            riga_griglia (int): Indice riga nella griglia
            numero_fila (int): Numero fila per log (1-based)
        """
        print(f"   Fila {numero_fila}: layout FISSO+trio (8 posti)")

        # 4 banchi consecutivi a sinistra + corridoio + 2 + corridoio + 2
        posizioni_banchi = [0, 1, 2, 3, 5, 6, 8, 9]

        posti_creati = 0
        for col in posizioni_banchi:
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    # =========================================================================
    # INTERROGAZIONE LAYOUT
    # =========================================================================

    def get_banchi_per_fila(self):
        """
        Restituisce i banchi organizzati per fila (dalla prima all'ultima).

        Returns:
            List[List[PostoAula]]: Lista di file, ogni fila contiene i banchi di quella riga
        """
        banchi_per_fila = []

        for riga_idx in range(self.num_righe):
            banchi_fila = []
            for posto in self.griglia[riga_idx]:
                if posto.is_banco():
                    banchi_fila.append(posto)

            if banchi_fila:  # Se ci sono banchi in questa fila
                banchi_per_fila.append(banchi_fila)

        return banchi_per_fila

    # =========================================================================
    # PULIZIA
    # =========================================================================

    def rimuovi_banchi_vuoti(self):
        """
        Rimuove tutti i banchi vuoti dalla griglia dopo l'assegnazione.
        Mantiene solo i banchi effettivamente occupati + elementi fissi (LIM, cattedra, lavagna).

        IMPORTANTE: Chiamare SOLO dopo aver completato l'assegnazione degli studenti.
        """
        print(f"\n🧹 PULIZIA BANCHI VUOTI...")

        banchi_prima = 0
        banchi_dopo = 0

        # Conta banchi prima della pulizia
        for riga in self.griglia:
            for posto in riga:
                if posto.tipo == 'banco':
                    banchi_prima += 1

        # Scansiona tutta la griglia
        for riga in self.griglia:
            for posto in riga:
                # Se è un banco vuoto (non occupato) → diventa corridoio
                if posto.tipo == 'banco' and posto.occupato_da is None:
                    posto.tipo = 'corridoio'

        # Conta banchi dopo la pulizia
        for riga in self.griglia:
            for posto in riga:
                if posto.tipo == 'banco':
                    banchi_dopo += 1

        # Aggiorna posti disponibili
        self.posti_disponibili = banchi_dopo

        banchi_rimossi = banchi_prima - banchi_dopo

        print(f"   📊 Banchi prima: {banchi_prima}")
        print(f"   📊 Banchi dopo: {banchi_dopo}")
        print(f"   🗑️ Banchi rimossi: {banchi_rimossi}")
        print(f"   ✅ Pulizia completata!")

