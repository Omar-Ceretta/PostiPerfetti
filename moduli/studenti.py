# -*- coding: utf-8 -*-
"""Modello dati degli studenti di «PostiPerfetti».

Definisce anagrafica, posizione, affinità e incompatibilità e converte in
oggetti ``Student`` i dati già validati dal modulo ``file_classe``.
"""

import unicodedata


def chiave_ordinamento_studente(studente) -> str:
    """Restituisce una chiave alfabetica stabile e insensibile agli accenti.

    L'ordine delle righe del file classe non ha significato algoritmico. La
    chiave serve ai motori per canonicalizzare l'ingresso prima di qualunque
    scelta deterministica, evitando che una semplice permutazione del ``.txt``
    cambi il risultato a parità di classe e seed.
    """
    nome = studente.get_nome_completo()
    normalizzato = unicodedata.normalize("NFKD", nome).casefold()
    return "".join(
        carattere
        for carattere in normalizzato
        if not unicodedata.combining(carattere)
    )

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


def nome_completo_da_identificatore(identificatore) -> str:
    """Normalizza l'identificatore di una cella nel nome completo leggibile.

    I layout vivi usano ``Cognome_Nome``; quelli ricostruiti dallo Storico
    possono già contenere ``Cognome Nome``. Poiché l'underscore è vietato nei
    nomi caricati, il primo underscore è sempre il separatore interno.
    """
    if identificatore is None:
        return ""
    testo = str(identificatore)
    if "_" in testo:
        cognome, nome = testo.split("_", 1)
        return f"{cognome} {nome}"
    return testo


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


def crea_studenti_da_dati_validati(studenti_dati):
    """Costruisce il dominio ``Student`` da dati già validati.

    Il parsing dei file appartiene a ``file_classe.py``. Questa funzione non
    tollera o corregge righe: converte soltanto la struttura transazionale già
    approvata dall'Editor e dai test del formato.
    """
    studenti = []
    for dati in studenti_dati:
        studente = Student(
            cognome=dati["cognome"],
            nome=dati["nome"],
            sesso=dati["sesso"],
            nota_posizione=dati["posizione"],
        )
        for nome_completo, livello in dati["incompatibilita"].items():
            studente.aggiungi_incompatibilita(nome_completo, livello)
        for nome_completo, livello in dati["affinita"].items():
            studente.aggiungi_affinita(nome_completo, livello)
        studenti.append(studente)
    return studenti
