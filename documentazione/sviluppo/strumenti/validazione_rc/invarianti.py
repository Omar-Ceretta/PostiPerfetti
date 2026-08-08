# -*- coding: utf-8 -*-
"""Invarianti del dominio RC, indipendenti dai motori produttivi."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

from .modelli import ClasseRC, MAX_STUDENTI_RC, MIN_STUDENTI_RC


@dataclass(frozen=True, slots=True)
class ViolazioneInvariante:
    codice: str
    messaggio: str


class ErroreInvariantiRC(ValueError):
    def __init__(self, violazioni: Iterable[ViolazioneInvariante]):
        self.violazioni = tuple(violazioni)
        super().__init__("\n".join(f"{v.codice}: {v.messaggio}" for v in self.violazioni))


def _relazioni(studente, attributo: str) -> dict[str, int]:
    return {
        relazione.altro: relazione.livello
        for relazione in getattr(studente, attributo)
    }


def valida_classe_rc(classe: ClasseRC, *, solleva: bool = True) -> tuple[ViolazioneInvariante, ...]:
    """Verifica il contratto corrente delle classi ammesse alla campagna RC."""
    violazioni: list[ViolazioneInvariante] = []
    n = classe.numero_studenti
    if not MIN_STUDENTI_RC <= n <= MAX_STUDENTI_RC:
        violazioni.append(
            ViolazioneInvariante(
                "RC_DIMENSIONE",
                f"La classe contiene {n} studenti; il dominio RC è {MIN_STUDENTI_RC}-{MAX_STUDENTI_RC}.",
            )
        )

    nomi = [s.nome for s in classe.studenti]
    if len(nomi) != len(set(nomi)):
        violazioni.append(ViolazioneInvariante("RC_IDENTITA_DUPLICATE", "I nomi non sono univoci."))

    fissi = [s.nome for s in classe.studenti if s.posizione == "FISSO"]
    if len(fissi) > 1:
        violazioni.append(
            ViolazioneInvariante("RC_FISSO_MULTIPLO", f"Sono presenti {len(fissi)} studenti FISSO.")
        )

    insieme_nomi = set(nomi)
    per_nome = classe.per_nome
    for studente in classe.studenti:
        incompatibilita = _relazioni(studente, "incompatibilita")
        affinita = _relazioni(studente, "affinita")
        if studente.nome in incompatibilita or studente.nome in affinita:
            violazioni.append(
                ViolazioneInvariante(
                    "RC_AUTO_RELAZIONE",
                    f"{studente.nome} contiene una relazione verso se stesso.",
                )
            )
        sovrapposte = set(incompatibilita).intersection(affinita)
        if sovrapposte:
            violazioni.append(
                ViolazioneInvariante(
                    "RC_RELAZIONE_CONTRADDITTORIA",
                    f"{studente.nome}: relazioni sia positive sia negative verso {sorted(sovrapposte)}.",
                )
            )
        for tipo, relazioni in (("incompatibilita", incompatibilita), ("affinita", affinita)):
            for altro, livello in relazioni.items():
                if altro not in insieme_nomi:
                    violazioni.append(
                        ViolazioneInvariante(
                            "RC_RIFERIMENTO_ESTERNO",
                            f"{studente.nome}: {tipo} verso studente assente {altro!r}.",
                        )
                    )
                    continue
                opposta = _relazioni(per_nome[altro], tipo)
                if opposta.get(studente.nome) != livello:
                    violazioni.append(
                        ViolazioneInvariante(
                            "RC_RELAZIONE_NON_RECIPROCA",
                            f"{studente.nome} ↔ {altro}: {tipo} non reciproca allo stesso livello.",
                        )
                    )

    risultato = tuple(violazioni)
    if risultato and solleva:
        raise ErroreInvariantiRC(risultato)
    return risultato


def firma_semantica_classe(classe: ClasseRC) -> str:
    """Firma stabile del significato, indipendente dall'ordine di righe e dizionari."""
    valida_classe_rc(classe)
    payload = {
        "nome": classe.nome,
        "studenti": [
            {
                "nome": studente.nome,
                "sesso": studente.sesso,
                "posizione": studente.posizione,
                "incompatibilita": [
                    [rel.altro, rel.livello] for rel in studente.incompatibilita
                ],
                "affinita": [
                    [rel.altro, rel.livello] for rel in studente.affinita
                ],
            }
            for studente in sorted(classe.studenti, key=lambda s: s.nome)
        ],
    }
    dati = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(dati.encode("utf-8")).hexdigest()
