# -*- coding: utf-8 -*-
"""
Modello dati degli studenti e caricamento delle classi da file.

Definisce anagrafica, posizione, affinità e incompatibilità di ogni studente.
"""

def chiave_identita_studente(cognome: str, nome: str) -> str:
    """Restituisce una chiave normalizzata per rilevare omonimi completi."""
    cognome_normalizzato = " ".join(
        str(cognome).strip().split()
    )
    nome_normalizzato = " ".join(
        str(nome).strip().split()
    )

    return (
        f"{cognome_normalizzato} {nome_normalizzato}"
        .casefold()
    )


class Student:
    """Rappresenta uno studente con anagrafica, posizione e vincoli sociali."""

    def __init__(self, cognome: str, nome: str, sesso: str, nota_posizione: str = "NORMALE") -> None:
        self.cognome = cognome.strip()
        self.nome = nome.strip()
        self.sesso = sesso.strip().upper()
        self.nota_posizione = nota_posizione.strip().upper()

        # I vincoli usano il nome completo; gli omonimi sono rifiutati al caricamento.
        self.incompatibilita: dict[str, int] = {}
        self.affinita: dict[str, int] = {}

    def aggiungi_incompatibilita(self, nome_completo_studente: str, livello: int) -> None:
        """Registra il livello di incompatibilità con un altro studente."""
        self.incompatibilita[nome_completo_studente.strip()] = int(livello)

    def aggiungi_affinita(self, nome_completo_studente: str, livello: int) -> None:
        """Registra il livello di affinità con un altro studente."""
        self.affinita[nome_completo_studente.strip()] = int(livello)

    def get_nome_completo(self) -> str:
        """Restituisce «Cognome Nome», memorizzandolo dopo il primo calcolo."""
        # La cache è pigra perché il nome è immutabile ma richiesto molto spesso dal motore.
        cache = getattr(self, '_nome_completo_cache', None)
        if cache is None:
            cache = f"{self.cognome} {self.nome}"
            self._nome_completo_cache = cache
        return cache

    def __str__(self) -> str:
        """Restituisce una rappresentazione leggibile per la diagnostica."""
        return f"{self.get_nome_completo()} ({self.sesso}) - Pos: {self.nota_posizione}"

def _risolvi_riferimento_completo(riferimento: str, tutti_studenti: list) -> Student:
    """Trova lo studente indicato da un nome completo, anche se composto."""
    if ' ' not in riferimento:
        return None

    # Prova più separazioni per gestire cognomi e nomi composti.
    possibili_interpretazioni = []

    parti = riferimento.split(' ', 1)
    if len(parti) == 2:
        possibili_interpretazioni.append((parti[0].strip(), parti[1].strip()))

    parti_complete = riferimento.split(' ')
    if len(parti_complete) >= 3:
        cognome_composto = ' '.join(parti_complete[:2])
        nome_composto = ' '.join(parti_complete[2:])
        possibili_interpretazioni.append((cognome_composto.strip(), nome_composto.strip()))

        cognome_semplice = parti_complete[0]
        nome_esteso = ' '.join(parti_complete[1:])
        possibili_interpretazioni.append((cognome_semplice.strip(), nome_esteso.strip()))

    if len(parti_complete) >= 4:
        cognome_lungo = ' '.join(parti_complete[:3])
        nome_finale = ' '.join(parti_complete[3:])
        possibili_interpretazioni.append((cognome_lungo.strip(), nome_finale.strip()))

    for cognome_target, nome_target in possibili_interpretazioni:
        for studente, _, _ in tutti_studenti:
            if studente.cognome == cognome_target and studente.nome == nome_target:
                return studente

    return None

def carica_studenti_da_file(percorso_file):
    """
    Carica gli studenti da un file completo a sei campi.
    
    Le righe e i singoli vincoli malformati vengono ignorati; gli omonimi completi
    rendono invece ambiguo il modello e provocano un errore.
    """
    studenti = []
    studenti_temporanei = []

    try:
        # Prima crea tutti gli studenti; soltanto dopo risolve i riferimenti dei vincoli.
        with open(percorso_file, 'r', encoding='utf-8') as file:
            for riga in file:
                riga = riga.strip()
                if not riga or riga.startswith('#'):
                    continue

                try:
                    parti = riga.split(';')

                    if len(parti) != 6:
                        raise ValueError(f"Formato errato: attese 6 colonne, trovate {len(parti)}")

                    cognome, nome, sesso, nota_pos, incomp_str, aff_str = parti

                    studente = Student(cognome, nome, sesso, nota_pos)

                    studenti_temporanei.append((studente, incomp_str, aff_str))

                except Exception:
                    continue

        # Gli omonimi completi renderebbero ambigui vincoli, motore e Storico.
        conteggi_identita = {}
        nomi_visualizzati = {}

        for studente, _incomp, _aff in studenti_temporanei:
            chiave = chiave_identita_studente(
                studente.cognome,
                studente.nome
            )

            nomi_visualizzati.setdefault(
                chiave,
                studente.get_nome_completo()
            )
            conteggi_identita[chiave] = (
                conteggi_identita.get(chiave, 0) + 1
            )

        duplicati = [
            (
                nomi_visualizzati[chiave],
                occorrenze
            )
            for chiave, occorrenze
            in conteggi_identita.items()
            if occorrenze > 1
        ]

        if duplicati:
            dettagli = ", ".join(
                f"{nome} ({occorrenze} occorrenze)"
                for nome, occorrenze in sorted(duplicati)
            )
            raise ValueError(
                "Il file contiene studenti con identico "
                f"cognome e nome: {dettagli}. "
                "Aggiungi un secondo nome o una sigla distintiva."
            )

        for studente, incomp_str, aff_str in studenti_temporanei:

            if incomp_str.strip():
                for coppia in incomp_str.split(','):
                    # Un vincolo malformato viene ignorato senza scartare l’intero file.
                    pezzi = coppia.split(':')
                    if len(pezzi) != 2:
                        continue
                    riferimento, livello_str = pezzi
                    riferimento = riferimento.strip()
                    try:
                        livello = int(livello_str)
                    except ValueError:
                        continue
                    if not 1 <= livello <= 3:
                        continue

                    studente_target = _risolvi_riferimento_completo(riferimento, studenti_temporanei)
                    if studente_target:
                        studente.aggiungi_incompatibilita(studente_target.get_nome_completo(), livello)

            if aff_str.strip():
                for coppia in aff_str.split(','):
                    # Applica la stessa tolleranza usata per le incompatibilità.
                    pezzi = coppia.split(':')
                    if len(pezzi) != 2:
                        continue
                    riferimento, livello_str = pezzi
                    riferimento = riferimento.strip()
                    try:
                        livello = int(livello_str)
                    except ValueError:
                        continue
                    if not 1 <= livello <= 3:
                        continue

                    studente_target = _risolvi_riferimento_completo(riferimento, studenti_temporanei)
                    if studente_target:
                        studente.aggiungi_affinita(studente_target.get_nome_completo(), livello)

            studenti.append(studente)

    except FileNotFoundError:
        return []

    return studenti

