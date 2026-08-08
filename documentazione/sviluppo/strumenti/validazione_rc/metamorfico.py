# -*- coding: utf-8 -*-
"""Trasformazioni metamorfiche del dominio RC.

Le funzioni di questo modulo non chiamano i motori produttivi. Costruiscono
classi semanticamente equivalenti oppure classi con vincoli strettamente più
deboli, così il laboratorio può verificare proprietà che devono valere a
prescindere dalla singola disposizione trovata.
"""

from __future__ import annotations

import random

from .modelli import ClasseRC, RelazioneRC, StudenteRC


def _ricostruisci(
    classe: ClasseRC,
    *,
    sesso: dict[str, str] | None = None,
    posizione: dict[str, str] | None = None,
    incompatibilita: dict[str, dict[str, int]] | None = None,
    affinita: dict[str, dict[str, int]] | None = None,
    origine: str,
) -> ClasseRC:
    sesso = sesso or {}
    posizione = posizione or {}
    incompatibilita = incompatibilita or {}
    affinita = affinita or {}
    studenti = []
    for studente in classe.studenti:
        inc = incompatibilita.get(studente.nome, studente.incompatibilita_dict)
        aff = affinita.get(studente.nome, studente.affinita_dict)
        studenti.append(
            StudenteRC(
                nome=studente.nome,
                sesso=sesso.get(studente.nome, studente.sesso),
                posizione=posizione.get(studente.nome, studente.posizione),
                incompatibilita=tuple(RelazioneRC(nome, livello) for nome, livello in inc.items()),
                affinita=tuple(RelazioneRC(nome, livello) for nome, livello in aff.items()),
            )
        )
    return ClasseRC(
        nome=classe.nome,
        studenti=tuple(studenti),
        origine=f"{classe.origine}:{origine}",
        seed=classe.seed,
        famiglia=classe.famiglia,
    )


def permuta_righe(classe: ClasseRC, *, seed: int) -> ClasseRC:
    studenti = list(classe.studenti)
    random.Random(seed).shuffle(studenti)
    return ClasseRC(
        nome=classe.nome,
        studenti=tuple(studenti),
        origine=f"{classe.origine}:permuta_righe",
        seed=classe.seed,
        famiglia=classe.famiglia,
    )


def permuta_ordine_relazioni(classe: ClasseRC, *, seed: int) -> ClasseRC:
    rng = random.Random(seed)
    studenti = []
    for studente in classe.studenti:
        incompatibilita = list(studente.incompatibilita)
        affinita = list(studente.affinita)
        rng.shuffle(incompatibilita)
        rng.shuffle(affinita)
        studenti.append(
            StudenteRC(
                nome=studente.nome,
                sesso=studente.sesso,
                posizione=studente.posizione,
                incompatibilita=tuple(incompatibilita),
                affinita=tuple(affinita),
            )
        )
    return ClasseRC(
        nome=classe.nome,
        studenti=tuple(studenti),
        origine=f"{classe.origine}:permuta_relazioni",
        seed=classe.seed,
        famiglia=classe.famiglia,
    )


def inverti_generi(classe: ClasseRC) -> ClasseRC:
    """Scambia M↔F per tutti: con Genere misto la semantica resta identica."""
    return _ricostruisci(
        classe,
        sesso={s.nome: ("F" if s.sesso == "M" else "M") for s in classe.studenti},
        origine="inverti_generi",
    )


def rimuovi_una_affinita(classe: ClasseRC, *, seed: int = 0) -> ClasseRC | None:
    """Rimuove un arco di affinità reciproco; la fattibilità non può peggiorare."""
    archi = sorted({
        tuple(sorted((studente.nome, relazione.altro)))
        for studente in classe.studenti
        for relazione in studente.affinita
    })
    if not archi:
        return None
    arco = random.Random(seed).choice(archi)
    nuove = {s.nome: dict(s.affinita_dict) for s in classe.studenti}
    a, b = arco
    nuove[a].pop(b, None)
    nuove[b].pop(a, None)
    return _ricostruisci(classe, affinita=nuove, origine="rimuovi_affinita")


def indebolisci_una_incompatibilita_assoluta(
    classe: ClasseRC, *, seed: int = 0
) -> ClasseRC | None:
    """Trasforma un livello 3 reciproco in livello 2: allenta un vincolo duro."""
    archi = sorted({
        tuple(sorted((studente.nome, relazione.altro)))
        for studente in classe.studenti
        for relazione in studente.incompatibilita
        if relazione.livello == 3
    })
    if not archi:
        return None
    a, b = random.Random(seed).choice(archi)
    nuove = {s.nome: dict(s.incompatibilita_dict) for s in classe.studenti}
    nuove[a][b] = 2
    nuove[b][a] = 2
    return _ricostruisci(
        classe, incompatibilita=nuove, origine="indebolisci_incompatibilita3"
    )


def rimuovi_un_vincolo_prima(classe: ClasseRC, *, seed: int = 0) -> ClasseRC | None:
    """Rende NORMALE uno studente PRIMA: allenta un vincolo di posizione."""
    candidati = sorted(s.nome for s in classe.studenti if s.posizione == "PRIMA")
    if not candidati:
        return None
    target = random.Random(seed).choice(candidati)
    return _ricostruisci(
        classe,
        posizione={target: "NORMALE"},
        origine="rimuovi_prima",
    )
