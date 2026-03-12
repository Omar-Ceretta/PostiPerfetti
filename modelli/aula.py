"""
Modulo per la gestione dell'aula e dei layout di disposizione banchi.
Contiene configurazioni predefinite e logica di posizionamento.
"""

import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

@dataclass
class PostoAula:
    """
    Rappresenta una singola posizione nell'aula.
    """
    riga: int          # Numero fila (0 = prima fila, verso cattedra)
    colonna: int       # Numero colonna
    tipo: str          # 'banco', 'corridoio', 'cattedra', 'lim', 'lavagna'
    occupato_da: Optional[str] = None  # Cognome studente se occupato

    def is_banco(self):
        """Verifica se questa posizione è un banco per studente."""
        return self.tipo == 'banco'

    def is_libero(self):
        """Verifica se questo banco è libero."""
        return self.is_banco() and self.occupato_da is None


class ConfigurazioneAula:
    """
    Gestisce la configurazione e il layout dell'aula.
    """

    def __init__(self, nome_config="Aula Standard"):
        self.nome_config = nome_config
        self.griglia = []  # Lista di liste: griglia[riga][colonna] = PostoAula
        self.num_righe = 0
        self.num_colonne = 0
        self.posti_disponibili = 0

        # Mappatura elementi fissi (cattedra, LIM, lavagna)
        self.elementi_fissi = {}

    def crea_layout_standard(self, num_studenti, num_file=None, posti_per_fila=None, posizione_trio=None):
        """
         Crea un layout standard per aula tradizionale.
        VERSIONE DINAMICA: Adatta il layout per gestire trio in numero dispari.

        Args:
            num_studenti (int): Numero di studenti da sistemare
            num_file (int, optional): Numero di file di banchi configurate
            posti_per_fila (int, optional): Posti per fila configurati
            posizione_trio (str, optional): "prima", "ultima", "centro", "auto" o None
        """
        print(f"Creando layout dinamico per {num_studenti} studenti...")

        # Configurazione default se parametri non forniti
        if num_file is None or posti_per_fila is None:
            studenti_per_fila = 6
            righe_banchi_necessarie = (num_studenti + studenti_per_fila - 1) // studenti_per_fila
            posti_per_fila = 6
            print(f"   Modalità legacy: {righe_banchi_necessarie} file da 6 posti")
        else:
            righe_banchi_necessarie = num_file
            studenti_per_fila = posti_per_fila
            print(f"   Modalità configurata: {num_file} file da {posti_per_fila} posti")

        # Determina se serve gestire trio
        ha_trio = (num_studenti % 2 == 1)
        fila_trio = None

        if ha_trio and posizione_trio:
            if posizione_trio == "prima":
                fila_trio = 0
                print(f"   Trio posizionato: PRIMA FILA")
            elif posizione_trio == "ultima":
                fila_trio = righe_banchi_necessarie - 1
                print(f"   Trio posizionato: ULTIMA FILA")
            elif posizione_trio == "centro":
                fila_trio = righe_banchi_necessarie // 2
                print(f"   Trio posizionato: CENTRO (fila {fila_trio + 1})")
            # Nota: Rimosso caso "auto" - non più supportato
            # Se posizione_trio non corrisponde a nessun caso, fila_trio resta None
            # e verrà gestito come errore nei controlli successivi

        # Calcola layout totale
        posti_totali = 0
        for fila_idx in range(righe_banchi_necessarie):
            if fila_trio is not None and fila_idx == fila_trio:
                posti_totali += posti_per_fila + 1  # Fila trio: +1 posto
            else:
                posti_totali += posti_per_fila       # Fila normale

        print(f"   Layout: {righe_banchi_necessarie} file")
        print(f"   Capacità totale: {posti_totali} posti")
        print(f"   Studenti da sistemare: {num_studenti}")

        # Struttura griglia
        self.num_righe = righe_banchi_necessarie + 2
        self.num_colonne = max(9, posti_per_fila + 3)  # Spazio per fila trio

        # Inizializza griglia vuota
        self.griglia = []
        for r in range(self.num_righe):
            riga = []
            for c in range(self.num_colonne):
                riga.append(PostoAula(r, c, 'corridoio'))
            self.griglia.append(riga)

        # PRIMA RIGA: Elementi fissi (arredi)
        # ALLINEAMENTO: Usa le stesse posizioni colonna dei banchi
        # così i corridoi tra gli arredi sono identici a quelli tra le coppie di banchi
        # Posizioni banchi: [0,1] corridoio [3,4] corridoio [6,7]
        # Posizioni arredi: [LIM,LIM] corridoio [CAT,CAT] corridoio [LAV,LAV]
        posizioni_arredi = [0, 1, 3, 4, 6, 7]  # Stesse posizioni delle coppie di banchi
        self.griglia[0][posizioni_arredi[0]] = PostoAula(0, posizioni_arredi[0], 'lim')
        self.griglia[0][posizioni_arredi[1]] = PostoAula(0, posizioni_arredi[1], 'lim')
        self.griglia[0][posizioni_arredi[2]] = PostoAula(0, posizioni_arredi[2], 'cattedra')
        self.griglia[0][posizioni_arredi[3]] = PostoAula(0, posizioni_arredi[3], 'cattedra')
        self.griglia[0][posizioni_arredi[4]] = PostoAula(0, posizioni_arredi[4], 'lavagna')
        self.griglia[0][posizioni_arredi[5]] = PostoAula(0, posizioni_arredi[5], 'lavagna')

        # RIGHE BANCHI: Crea layout adattivo
        posti_creati = 0
        for fila_idx in range(righe_banchi_necessarie):
            riga_griglia = fila_idx + 2  # Offset per elementi fissi

            if fila_trio is not None and fila_idx == fila_trio:
                # FILA CON TRIO: 7 banchi (2+3+2)
                posti_creati += self._crea_fila_con_trio(riga_griglia, fila_idx + 1)
            else:
                # FILA NORMALE: 6 banchi (2+2+2)
                posti_creati += self._crea_fila_normale(riga_griglia, fila_idx + 1, posti_per_fila)

        self.posti_disponibili = posti_creati
        print(f"✅ Layout creato: {self.posti_disponibili} posti totali")

    def _crea_fila_normale(self, riga_griglia, numero_fila, posti_necessari):
        """Crea una fila normale con esattamente i banchi necessari."""
        print(f"   Fila {numero_fila}: layout normale ({posti_necessari} posti)")

        # Layout: [A][B] - corridoio - [C][D] - corridoio - [E][F] - ecc.
        posizioni_banchi = [0, 1, 3, 4, 6, 7, 9, 10]  # Posizioni con corridoi

        posti_creati = 0
        for i in range(min(posti_necessari, len(posizioni_banchi))):
            col = posizioni_banchi[i]
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

    def _crea_fila_con_trio(self, riga_griglia, numero_fila):
        """Crea una fila con spazio per trio + 2 coppie."""
        print(f"   Fila {numero_fila}: layout trio (7 posti)")

        # Layout: [A][B] - corridoio - [TRIO1][TRIO2][TRIO3] - corridoio - [C][D]
        posizioni_banchi = [0, 1, 3, 4, 5, 7, 8]  # 7 posizioni per trio

        posti_creati = 0
        for col in posizioni_banchi:
            if col < self.num_colonne:
                self.griglia[riga_griglia][col] = PostoAula(riga_griglia, col, 'banco')
                posti_creati += 1

        return posti_creati

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

    def get_banchi_liberi(self):
        """
        Restituisce tutti i banchi ancora liberi.

        Returns:
            List[PostoAula]: Lista dei banchi non ancora occupati
        """
        banchi_liberi = []

        for riga in self.griglia:
            for posto in riga:
                if posto.is_libero():
                    banchi_liberi.append(posto)

        return banchi_liberi

    def assegna_studente_a_banco(self, cognome_studente, riga, colonna):
        """
        Assegna uno studente a un banco specifico.

        Args:
            cognome_studente (str): Cognome dello studente
            riga (int): Numero riga del banco
            colonna (int): Numero colonna del banco

        Returns:
            bool: True se assegnazione riuscita, False altrimenti
        """
        try:
            posto = self.griglia[riga][colonna]
            if posto.is_libero():
                posto.occupato_da = cognome_studente
                return True
            else:
                print(f"❌ Posto ({riga},{colonna}) non disponibile")
                return False
        except IndexError:
            print(f"❌ Posizione ({riga},{colonna}) non valida")
            return False

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

    def stampa_layout(self):
        """
        Stampa una rappresentazione testuale del layout dell'aula.
        """
        print(f"\n📐 LAYOUT AULA: {self.nome_config}")
        print("=" * 50)

        simboli = {
            'corridoio': '  ',
            'banco': '🪑',
            'cattedra': '🏫',
            'lim': '📺',
            'lavagna': '⬛'
        }

        for riga_idx, riga in enumerate(self.griglia):
            riga_str = f"Fila {riga_idx}: "
            for posto in riga:
                if posto.occupato_da:
                    # Banco occupato: mostra iniziali studente
                    iniziali = posto.occupato_da[:2].upper()
                    riga_str += f"[{iniziali}]"
                else:
                    # Usa simbolo per tipo posto
                    simbolo = simboli.get(posto.tipo, '??')
                    riga_str += f" {simbolo} "
            print(riga_str)

        print(f"\n📊 Posti totali: {self.posti_disponibili}")
        liberi = len(self.get_banchi_liberi())
        occupati = self.posti_disponibili - liberi
        print(f"📊 Occupati: {occupati}, Liberi: {liberi}")



