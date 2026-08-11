# -*- coding: utf-8 -*-
"""Riduzione deterministica di controesempi RC.

Il riduttore non conosce il bug: riceve un predicato e tenta, nell'ordine, di
rimuovere relazioni, preferenze di posizione e studenti mantenendo sempre il
dominio reale (almeno 12 allievi) e la riproducibilità del predicato.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .invarianti import valida_classe_rc
from .modelli import ClasseRC, StudenteRC


@dataclass(frozen=True, slots=True)
class EsitoRiduzioneRC:
    originale_studenti: int
    finale_studenti: int
    originale_relazioni: int
    finale_relazioni: int
    passi_accettati: int
    classe: ClasseRC


def _numero_relazioni(classe: ClasseRC) -> int:
    # Le relazioni RC sono reciproche: conta una volta ogni arco.
    return sum(len(s.incompatibilita) + len(s.affinita) for s in classe.studenti) // 2


def _ricostruisci(classe: ClasseRC, studenti: list[StudenteRC]) -> ClasseRC:
    nomi = {s.nome for s in studenti}
    puliti = []
    for s in studenti:
        puliti.append(StudenteRC(
            nome=s.nome, sesso=s.sesso, posizione=s.posizione,
            incompatibilita=tuple(r for r in s.incompatibilita if r.altro in nomi),
            affinita=tuple(r for r in s.affinita if r.altro in nomi),
        ))
    nuova = ClasseRC(nome=classe.nome + "-ridotta", studenti=tuple(puliti),
                     origine="riduzione_rc", seed=classe.seed, famiglia=classe.famiglia)
    valida_classe_rc(nuova)
    return nuova


def _rimuovi_arco(classe: ClasseRC, a: str, b: str, attributo: str) -> ClasseRC:
    nuovi = []
    for s in classe.studenti:
        inc = s.incompatibilita
        aff = s.affinita
        if attributo == "incompatibilita":
            inc = tuple(r for r in inc if not (s.nome in {a,b} and r.altro in {a,b}))
        else:
            aff = tuple(r for r in aff if not (s.nome in {a,b} and r.altro in {a,b}))
        nuovi.append(StudenteRC(s.nome, s.sesso, s.posizione, inc, aff))
    return _ricostruisci(classe, nuovi)


def riduci_classe_rc(classe: ClasseRC, predicato: Callable[[ClasseRC], bool], *, minimo_studenti: int = 12) -> EsitoRiduzioneRC:
    valida_classe_rc(classe)
    if not predicato(classe):
        raise ValueError("Il predicato non è vero sulla classe iniziale.")
    corrente = classe
    passi = 0
    originali_rel = _numero_relazioni(classe)

    # 1. Elimina prima gli archi, perché producono controesempi più leggibili.
    cambiato = True
    while cambiato:
        cambiato = False
        archi = []
        for s in corrente.studenti:
            for r in s.affinita:
                if s.nome < r.altro:
                    archi.append(("affinita", s.nome, r.altro))
            for r in s.incompatibilita:
                if s.nome < r.altro:
                    archi.append(("incompatibilita", s.nome, r.altro))
        for tipo, a, b in archi:
            candidata = _rimuovi_arco(corrente, a, b, tipo)
            if predicato(candidata):
                corrente = candidata; passi += 1; cambiato = True; break

    # 2. Rilassa posizioni non necessarie, compreso FISSO se il difetto persiste.
    for nome in [s.nome for s in corrente.studenti]:
        s = corrente.per_nome[nome]
        if s.posizione == "NORMALE":
            continue
        nuovi = [
            StudenteRC(x.nome, x.sesso, "NORMALE" if x.nome == nome else x.posizione,
                       x.incompatibilita, x.affinita)
            for x in corrente.studenti
        ]
        candidata = _ricostruisci(corrente, nuovi)
        if predicato(candidata):
            corrente = candidata; passi += 1

    # 3. Delta reduction sugli studenti, senza uscire dal dominio 12–30.
    cambiato = True
    while cambiato and corrente.numero_studenti > minimo_studenti:
        cambiato = False
        for nome in [s.nome for s in corrente.studenti]:
            if corrente.numero_studenti - 1 < minimo_studenti:
                break
            candidata = _ricostruisci(corrente, [s for s in corrente.studenti if s.nome != nome])
            if predicato(candidata):
                corrente = candidata; passi += 1; cambiato = True; break

    return EsitoRiduzioneRC(
        originale_studenti=classe.numero_studenti,
        finale_studenti=corrente.numero_studenti,
        originale_relazioni=originali_rel,
        finale_relazioni=_numero_relazioni(corrente),
        passi_accettati=passi,
        classe=corrente,
    )
