# -*- coding: utf-8 -*-
"""Oracoli esatti indipendenti, limitati ai sottodomini in cui sono affidabili.

L'oracolo coppie lavora su 12–30 studenti senza PRIMA/FISSO: considera soltanto
il veto assoluto di livello 3, cioè esattamente il grafo duro che deve restare
risolvibile al T4. Per classi dispari sceglie un trio lineare ammissibile e un
matching perfetto sul resto. Un budget esplicito restituisce ``sconosciuto``
invece di trasformare un limite computazionale in una falsa prova.
"""
from __future__ import annotations
from dataclasses import dataclass

from .modelli import ClasseRC


@dataclass(frozen=True, slots=True)
class EsitoOracoloCoppieRC:
    stato: str  # fattibile | impossibile | sconosciuto | fuori_dominio
    nodi: int
    coppie: tuple[tuple[str, str], ...] = ()
    trio: tuple[str, str, str] | None = None


def _grafo_liv3(classe: ClasseRC):
    nomi = tuple(s.nome for s in classe.studenti)
    vietate = set()
    for s in classe.studenti:
        for r in s.incompatibilita:
            if r.livello == 3:
                vietate.add(frozenset((s.nome, r.altro)))
    ammessi = {
        a: frozenset(b for b in nomi if b != a and frozenset((a,b)) not in vietate)
        for a in nomi
    }
    return nomi, ammessi


def oracolo_coppie_t4(classe: ClasseRC, *, limite_nodi: int = 250000) -> EsitoOracoloCoppieRC:
    if any(s.posizione != "NORMALE" for s in classe.studenti):
        return EsitoOracoloCoppieRC("fuori_dominio", 0)
    nomi, ammessi = _grafo_liv3(classe)
    nodi = [0]
    memo_impossibili: set[frozenset[str]] = set()

    def matching(restanti: frozenset[str]):
        nodi[0] += 1
        if nodi[0] > limite_nodi:
            raise RuntimeError("budget")
        if not restanti:
            return ()
        if restanti in memo_impossibili:
            return None
        # MRV: il vertice con meno partner residui riduce drasticamente i rami.
        a = min(restanti, key=lambda x: len(ammessi[x] & restanti))
        candidati = sorted(ammessi[a] & restanti)
        if not candidati:
            memo_impossibili.add(restanti)
            return None
        base = restanti - {a}
        for b in candidati:
            soluzione = matching(base - {b})
            if soluzione is not None:
                return ((a, b),) + soluzione
        memo_impossibili.add(restanti)
        return None

    try:
        if len(nomi) % 2 == 0:
            sol = matching(frozenset(nomi))
            return EsitoOracoloCoppieRC(
                "fattibile" if sol is not None else "impossibile", nodi[0], sol or ()
            )

        # Trio lineare: fra tre membri devono esistere almeno due archi ammessi
        # che condividano il membro centrale. Prova prima i trii più vincolati.
        ordinati = sorted(nomi, key=lambda x: len(ammessi[x]))
        for centro in ordinati:
            estremi = sorted(ammessi[centro])
            for i, a in enumerate(estremi):
                for b in estremi[i + 1:]:
                    trio = (a, centro, b)
                    restanti = frozenset(nomi) - set(trio)
                    sol = matching(restanti)
                    if sol is not None:
                        return EsitoOracoloCoppieRC("fattibile", nodi[0], sol, trio)
        return EsitoOracoloCoppieRC("impossibile", nodi[0])
    except RuntimeError:
        return EsitoOracoloCoppieRC("sconosciuto", nodi[0])
