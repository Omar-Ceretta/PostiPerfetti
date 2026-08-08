# -*- coding: utf-8 -*-
"""Modelli immutabili e indipendenti dai motori di PostiPerfetti."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


MIN_STUDENTI_RC = 12
MAX_STUDENTI_RC = 30


class FamigliaSintetica(str, Enum):
    VUOTA = "vuota"
    SPARSA = "sparsa"
    MEDIA = "media"
    STELLA = "stella"
    DUE_BLOCCHI = "due_blocchi"
    QUASI_CLIQUE = "quasi_clique"
    CLIQUE_SOVRABBONDANTE = "clique_sovrabbondante"


@dataclass(frozen=True, slots=True)
class RelazioneRC:
    altro: str
    livello: int

    def __post_init__(self) -> None:
        if not str(self.altro).strip():
            raise ValueError("Il destinatario di una relazione non può essere vuoto.")
        if self.livello not in (1, 2, 3):
            raise ValueError("Il livello deve essere 1, 2 o 3.")


@dataclass(frozen=True, slots=True)
class StudenteRC:
    nome: str
    sesso: str
    posizione: str
    incompatibilita: tuple[RelazioneRC, ...] = ()
    affinita: tuple[RelazioneRC, ...] = ()

    def __post_init__(self) -> None:
        nome = str(self.nome).strip()
        if not nome:
            raise ValueError("Il nome completo non può essere vuoto.")
        if self.sesso not in {"M", "F"}:
            raise ValueError("Nel dominio RC il sesso deve essere M o F.")
        if self.posizione not in {"NORMALE", "PRIMA", "ULTIMA", "FISSO"}:
            raise ValueError("Posizione non valida nel dominio RC.")
        object.__setattr__(self, "nome", nome)
        object.__setattr__(
            self,
            "incompatibilita",
            tuple(sorted(self.incompatibilita, key=lambda r: (r.altro, r.livello))),
        )
        object.__setattr__(
            self,
            "affinita",
            tuple(sorted(self.affinita, key=lambda r: (r.altro, r.livello))),
        )

    @property
    def incompatibilita_dict(self) -> dict[str, int]:
        return {relazione.altro: relazione.livello for relazione in self.incompatibilita}

    @property
    def affinita_dict(self) -> dict[str, int]:
        return {relazione.altro: relazione.livello for relazione in self.affinita}


@dataclass(frozen=True, slots=True)
class ClasseRC:
    nome: str
    studenti: tuple[StudenteRC, ...]
    origine: str = "sintetica"
    seed: int | None = None
    famiglia: str | None = None

    def __post_init__(self) -> None:
        nome = str(self.nome).strip()
        if not nome:
            raise ValueError("Il nome della classe non può essere vuoto.")
        object.__setattr__(self, "nome", nome)
        object.__setattr__(self, "studenti", tuple(self.studenti))

    @property
    def numero_studenti(self) -> int:
        return len(self.studenti)

    @property
    def per_nome(self) -> dict[str, StudenteRC]:
        return {studente.nome: studente for studente in self.studenti}

    @property
    def studente_fisso(self) -> str | None:
        fissi = [s.nome for s in self.studenti if s.posizione == "FISSO"]
        return fissi[0] if len(fissi) == 1 else None


def classe_da_dati_validati(
    nome_classe: str,
    studenti_dati: Iterable[Mapping],
    *,
    origine: str,
    seed: int | None = None,
    famiglia: str | None = None,
) -> ClasseRC:
    """Converte l'output canonico del parser nel modello indipendente RC."""
    studenti = []
    for dati in studenti_dati:
        nome = f"{dati['cognome']} {dati['nome']}"
        studenti.append(
            StudenteRC(
                nome=nome,
                sesso=dati["sesso"],
                posizione=dati["posizione"],
                incompatibilita=tuple(
                    RelazioneRC(altro, int(livello))
                    for altro, livello in dati["incompatibilita"].items()
                ),
                affinita=tuple(
                    RelazioneRC(altro, int(livello))
                    for altro, livello in dati["affinita"].items()
                ),
            )
        )
    return ClasseRC(
        nome=nome_classe,
        studenti=tuple(studenti),
        origine=origine,
        seed=seed,
        famiglia=famiglia,
    )
