# -*- coding: utf-8 -*-
"""Generatori deterministici di classi sintetiche realistiche 12–30."""

from __future__ import annotations

import random

from .invarianti import valida_classe_rc
from .modelli import ClasseRC, FamigliaSintetica, RelazioneRC, StudenteRC


def _nomi(numero: int) -> list[str]:
    return [f"RC{i:02d} Studente" for i in range(1, numero + 1)]


def _aggiungi_relazione(mappa: list[dict[str, int]], i: int, j: int, livello: int) -> None:
    if i == j:
        raise ValueError("Relazione riflessiva non ammessa.")
    mappa[i][j] = livello
    mappa[j][i] = livello


def _archi_casuali(rng: random.Random, numero: int, densita: float) -> list[tuple[int, int]]:
    archi = []
    for i in range(numero):
        for j in range(i + 1, numero):
            if rng.random() < densita:
                archi.append((i, j))
    rng.shuffle(archi)
    return archi


def genera_classe_sintetica(
    numero_studenti: int,
    *,
    seed: int,
    famiglia: FamigliaSintetica | str,
    con_fisso: bool = False,
) -> ClasseRC:
    """Genera una classe canonica, reciproca e riproducibile nel dominio RC."""
    famiglia = FamigliaSintetica(famiglia)
    if not 12 <= numero_studenti <= 30:
        raise ValueError("numero_studenti deve essere compreso fra 12 e 30.")
    rng = random.Random(seed)
    nomi = _nomi(numero_studenti)
    incompatibilita: list[dict[int, int]] = [dict() for _ in nomi]
    affinita: list[dict[int, int]] = [dict() for _ in nomi]

    if famiglia == FamigliaSintetica.SPARSA:
        for i, j in _archi_casuali(rng, numero_studenti, 0.035):
            _aggiungi_relazione(incompatibilita, i, j, rng.choice((1, 2, 3)))
    elif famiglia == FamigliaSintetica.MEDIA:
        for i, j in _archi_casuali(rng, numero_studenti, 0.10):
            _aggiungi_relazione(incompatibilita, i, j, rng.choices((1, 2, 3), (5, 3, 1))[0])
    elif famiglia == FamigliaSintetica.STELLA:
        centro = 0
        ampiezza = max(3, numero_studenti // 2)
        for j in range(1, ampiezza + 1):
            _aggiungi_relazione(incompatibilita, centro, j, 3 if j % 3 == 0 else 2)
    elif famiglia == FamigliaSintetica.DUE_BLOCCHI:
        meta = numero_studenti // 2
        for i in range(meta):
            for j in range(meta, numero_studenti):
                if rng.random() < 0.18:
                    _aggiungi_relazione(incompatibilita, i, j, rng.choice((2, 3)))
    elif famiglia in {FamigliaSintetica.QUASI_CLIQUE, FamigliaSintetica.CLIQUE_SOVRABBONDANTE}:
        dimensione = numero_studenti // 2
        if famiglia == FamigliaSintetica.CLIQUE_SOVRABBONDANTE:
            dimensione += 1
        for i in range(dimensione):
            for j in range(i + 1, dimensione):
                if famiglia == FamigliaSintetica.QUASI_CLIQUE and (i, j) == (0, dimensione - 1):
                    continue
                _aggiungi_relazione(incompatibilita, i, j, 3)

    # Affinità indipendenti, ma mai sovrapposte alle incompatibilità.
    densita_affinita = 0.0 if famiglia == FamigliaSintetica.VUOTA else 0.06
    for i, j in _archi_casuali(rng, numero_studenti, densita_affinita):
        if j not in incompatibilita[i]:
            _aggiungi_relazione(affinita, i, j, rng.choice((1, 2, 3)))

    # Posizioni realistiche: pochi PRIMA, qualche ULTIMA, un FISSO opzionale.
    posizioni = ["NORMALE"] * numero_studenti
    numero_prima = min(3, max(0, numero_studenti // 10))
    candidati = list(range(numero_studenti))
    rng.shuffle(candidati)
    for indice in candidati[:numero_prima]:
        posizioni[indice] = "PRIMA"
    if numero_studenti >= 14:
        for indice in candidati[numero_prima:numero_prima + 2]:
            if posizioni[indice] == "NORMALE":
                posizioni[indice] = "ULTIMA"
    if con_fisso:
        fisso = next(indice for indice in candidati if posizioni[indice] != "PRIMA")
        posizioni[fisso] = "FISSO"

    studenti = []
    for i, nome in enumerate(nomi):
        studenti.append(
            StudenteRC(
                nome=nome,
                sesso="F" if i % 2 == 0 else "M",
                posizione=posizioni[i],
                incompatibilita=tuple(
                    RelazioneRC(nomi[j], livello)
                    for j, livello in incompatibilita[i].items()
                ),
                affinita=tuple(
                    RelazioneRC(nomi[j], livello)
                    for j, livello in affinita[i].items()
                ),
            )
        )

    classe = ClasseRC(
        nome=f"RC-{famiglia.value}-{numero_studenti}-{seed}",
        studenti=tuple(studenti),
        origine="generatore_rc",
        seed=seed,
        famiglia=famiglia.value,
    )
    valida_classe_rc(classe)
    return classe


def dati_validati_da_classe(classe: ClasseRC) -> list[dict]:
    """Converte il modello indipendente nella struttura canonica del writer."""
    risultato = []
    for studente in classe.studenti:
        cognome, nome = studente.nome.split(" ", 1)
        risultato.append({
            "cognome": cognome,
            "nome": nome,
            "sesso": studente.sesso,
            "posizione": studente.posizione,
            "incompatibilita": studente.incompatibilita_dict,
            "affinita": studente.affinita_dict,
        })
    return risultato
