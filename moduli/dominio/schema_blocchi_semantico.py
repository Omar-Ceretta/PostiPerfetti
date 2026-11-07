# -*- coding: utf-8 -*-
"""Geometria semantica a blocchi per la modalità Mista sperimentale.

Gate B del cantiere M1.4. Il modulo è deliberatamente puro: non importa Qt,
non conosce lo storico e non assegna studenti. Descrive soltanto blocchi, posti,
profondità e zone didattiche PRIMA/ULTIMA, oltre all'eventuale ancora FISSO.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


CAPIENZE_BLOCCO_SUPPORTATE = frozenset({2, 3})


def _intero_non_negativo(nome: str, valore: object) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ValueError(f"{nome} deve essere un intero non negativo.")
    return valore


@dataclass(frozen=True, slots=True, order=True)
class PostoAulaSemanticoSpec:
    """Un posto fisico ordinato all'interno di un blocco."""

    indice: int
    id: str
    ancora_fisso: bool = False

    def __post_init__(self) -> None:
        _intero_non_negativo("indice", self.indice)
        identificatore = str(self.id).strip()
        if not identificatore:
            raise ValueError("L'id del posto non può essere vuoto.")
        object.__setattr__(self, "id", identificatore)
        if not isinstance(self.ancora_fisso, bool):
            raise ValueError("ancora_fisso deve essere booleano.")


@dataclass(frozen=True, slots=True)
class BloccoAulaSemanticoSpec:
    """Blocco fisico con semantica spaziale esplicita.

    ``profondita`` misura la distanza logica dalla zona docente (0 = fascia più
    vicina). ``zona_prima`` e ``zona_ultima`` sono invece proprietà esplicite:
    non vengono dedotte automaticamente dalla profondità.
    """

    id: str
    capienza: int
    profondita: int
    colonna: int
    zona_prima: bool
    zona_ultima: bool
    posti: tuple[PostoAulaSemanticoSpec, ...]

    def __post_init__(self) -> None:
        identificatore = str(self.id).strip()
        if not identificatore:
            raise ValueError("L'id del blocco non può essere vuoto.")
        object.__setattr__(self, "id", identificatore)

        if self.capienza not in CAPIENZE_BLOCCO_SUPPORTATE:
            ammesse = ", ".join(str(v) for v in sorted(CAPIENZE_BLOCCO_SUPPORTATE))
            raise ValueError(
                f"capienza non supportata: {self.capienza!r}; ammesse: {ammesse}."
            )
        _intero_non_negativo("profondita", self.profondita)
        _intero_non_negativo("colonna", self.colonna)
        if not isinstance(self.zona_prima, bool) or not isinstance(self.zona_ultima, bool):
            raise ValueError("zona_prima e zona_ultima devono essere booleani.")

        posti = tuple(sorted(self.posti, key=lambda posto: posto.indice))
        object.__setattr__(self, "posti", posti)
        if len(posti) != self.capienza:
            raise ValueError(
                f"Il blocco {self.id!r} dichiara capienza {self.capienza} "
                f"ma contiene {len(posti)} posti."
            )
        indici = [posto.indice for posto in posti]
        if indici != list(range(self.capienza)):
            raise ValueError(
                f"Gli indici dei posti del blocco {self.id!r} devono essere "
                f"0..{self.capienza - 1}: trovati {indici}."
            )
        ids = [posto.id for posto in posti]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Id posto duplicato nel blocco {self.id!r}.")

        ancore = [posto for posto in posti if posto.ancora_fisso]
        if len(ancore) > 1:
            raise ValueError(
                f"Il blocco {self.id!r} contiene più di un posto ancora FISSO."
            )

    @property
    def colonna_finale(self) -> int:
        return self.colonna + self.capienza - 1

    @property
    def posto_ancora_fisso(self) -> PostoAulaSemanticoSpec | None:
        return next((posto for posto in self.posti if posto.ancora_fisso), None)


@dataclass(frozen=True, slots=True)
class SchemaBlocchiSemantico:
    """Descrizione immutabile e validata della geometria semantica."""

    blocchi: tuple[BloccoAulaSemanticoSpec, ...]

    def __post_init__(self) -> None:
        if not self.blocchi:
            raise ValueError("Lo schema d'aula deve contenere almeno un blocco.")

        blocchi = tuple(sorted(self.blocchi, key=lambda b: (b.profondita, b.colonna, b.id)))
        object.__setattr__(self, "blocchi", blocchi)

        ids_blocchi = [blocco.id for blocco in blocchi]
        if len(set(ids_blocchi)) != len(ids_blocchi):
            raise ValueError("Gli id dei blocchi devono essere unici nello schema.")

        ids_posti = [posto.id for blocco in blocchi for posto in blocco.posti]
        if len(set(ids_posti)) != len(ids_posti):
            raise ValueError("Gli id dei posti devono essere unici nello schema.")

        profondita_presenti = sorted({blocco.profondita for blocco in blocchi})
        attese = list(range(profondita_presenti[-1] + 1))
        if profondita_presenti != attese:
            raise ValueError(
                "Le profondità devono essere consecutive e partire da 0: "
                f"trovate {profondita_presenti}."
            )

        per_profondita: dict[int, list[BloccoAulaSemanticoSpec]] = {}
        for blocco in blocchi:
            per_profondita.setdefault(blocco.profondita, []).append(blocco)
        for profondita, elementi in per_profondita.items():
            ordinati = sorted(elementi, key=lambda b: (b.colonna, b.id))
            precedente: BloccoAulaSemanticoSpec | None = None
            for blocco in ordinati:
                if precedente is not None and blocco.colonna <= precedente.colonna_finale:
                    raise ValueError(
                        "I blocchi della stessa profondità non possono sovrapporsi: "
                        f"profondità {profondita}, {precedente.id!r} e {blocco.id!r}."
                    )
                precedente = blocco

        ancore = [
            (blocco, posto)
            for blocco in blocchi
            for posto in blocco.posti
            if posto.ancora_fisso
        ]
        if len(ancore) > 1:
            raise ValueError("Lo schema può contenere al massimo un'ancora FISSO.")

    @property
    def numero_blocchi(self) -> int:
        return len(self.blocchi)

    @property
    def posti_totali(self) -> int:
        return sum(blocco.capienza for blocco in self.blocchi)

    @property
    def profondita_massima(self) -> int:
        return max(blocco.profondita for blocco in self.blocchi)

    @property
    def blocchi_prima(self) -> tuple[BloccoAulaSemanticoSpec, ...]:
        return tuple(blocco for blocco in self.blocchi if blocco.zona_prima)

    @property
    def blocchi_ultima(self) -> tuple[BloccoAulaSemanticoSpec, ...]:
        return tuple(blocco for blocco in self.blocchi if blocco.zona_ultima)

    @property
    def blocco_ancora_fisso(self) -> BloccoAulaSemanticoSpec | None:
        return next(
            (blocco for blocco in self.blocchi if blocco.posto_ancora_fisso is not None),
            None,
        )

    @property
    def posto_ancora_fisso(self) -> PostoAulaSemanticoSpec | None:
        blocco = self.blocco_ancora_fisso
        return None if blocco is None else blocco.posto_ancora_fisso

    def conteggio_per_capienza(self) -> dict[int, int]:
        return _conteggio(self.blocchi)

    def conteggio_prima_per_capienza(self) -> dict[int, int]:
        return _conteggio(self.blocchi_prima)

    def conteggio_ultima_per_capienza(self) -> dict[int, int]:
        return _conteggio(self.blocchi_ultima)

    def forma_per_profondita(self) -> tuple[tuple[int, ...], ...]:
        """Restituisce le capienze dei blocchi ordinate per profondità/colonna."""
        risultato: list[tuple[int, ...]] = []
        for profondita in range(self.profondita_massima + 1):
            risultato.append(tuple(
                blocco.capienza
                for blocco in self.blocchi
                if blocco.profondita == profondita
            ))
        return tuple(risultato)

    def identita_semantica(self) -> tuple[tuple[object, ...], ...]:
        """Identità stabile completa, adatta a seed, firme e diagnostica."""
        return tuple(
            (
                blocco.id,
                blocco.capienza,
                blocco.profondita,
                blocco.colonna,
                blocco.zona_prima,
                blocco.zona_ultima,
                tuple(
                    (posto.id, posto.indice, posto.ancora_fisso)
                    for posto in blocco.posti
                ),
            )
            for blocco in self.blocchi
        )

    def valida_numero_studenti(self, numero_studenti: int) -> None:
        if isinstance(numero_studenti, bool) or not isinstance(numero_studenti, int):
            raise ValueError("numero_studenti deve essere un intero.")
        if numero_studenti != self.posti_totali:
            raise ValueError(
                "Numero studenti incompatibile con lo schema: "
                f"studenti={numero_studenti}, posti={self.posti_totali}."
            )


def _conteggio(blocchi: tuple[BloccoAulaSemanticoSpec, ...]) -> dict[int, int]:
    contatore = Counter(blocco.capienza for blocco in blocchi)
    return {
        taglia: int(contatore.get(taglia, 0))
        for taglia in sorted(CAPIENZE_BLOCCO_SUPPORTATE)
    }


def _posti(prefisso: str, capienza: int, *, ancora_indice: int | None = None) -> tuple[PostoAulaSemanticoSpec, ...]:
    if len(prefisso) != capienza:
        raise ValueError("Il prefisso dei posti deve avere un carattere per posto nei factory di test.")
    return tuple(
        PostoAulaSemanticoSpec(
            indice=i,
            id=prefisso[i],
            ancora_fisso=(i == ancora_indice),
        )
        for i in range(capienza)
    )


def schema_aula_omar_24_semantico() -> SchemaBlocchiSemantico:
    """Caso campione reale: zona docente in basso e FISSO ancorabile in O."""
    return SchemaBlocchiSemantico((
        # prof. 0: a fianco degli arredi, ma didatticamente PRIMA
        BloccoAulaSemanticoSpec("V-W-Z", 3, 0, 8, True, False, _posti("VWZ", 3)),
        # prof. 1: davanti al docente, anch'essa tutta zona PRIMA
        BloccoAulaSemanticoSpec("O-P", 2, 1, 0, True, False, _posti("OP", 2, ancora_indice=0)),
        BloccoAulaSemanticoSpec("Q-R", 2, 1, 4, True, False, _posti("QR", 2)),
        BloccoAulaSemanticoSpec("S-T-U", 3, 1, 8, True, False, _posti("STU", 3)),
        # prof. 2: zona neutra
        BloccoAulaSemanticoSpec("H-I", 2, 2, 0, False, False, _posti("HI", 2)),
        BloccoAulaSemanticoSpec("J-K-L", 3, 2, 4, False, False, _posti("JKL", 3)),
        BloccoAulaSemanticoSpec("M-N", 2, 2, 9, False, False, _posti("MN", 2)),
        # prof. 3: fondo reale, zona ULTIMA
        BloccoAulaSemanticoSpec("A-B", 2, 3, 0, False, True, _posti("AB", 2)),
        BloccoAulaSemanticoSpec("C-D", 2, 3, 4, False, True, _posti("CD", 2)),
        BloccoAulaSemanticoSpec("E-F-G", 3, 3, 8, False, True, _posti("EFG", 3)),
    ))


def schema_aula_omar_24_fisso_in_trio() -> SchemaBlocchiSemantico:
    """Variante di contratto: FISSO ancorato in O dentro un terzetto O-P-Q."""
    return SchemaBlocchiSemantico((
        BloccoAulaSemanticoSpec("V-W-Z", 3, 0, 8, True, False, _posti("VWZ", 3)),
        BloccoAulaSemanticoSpec("O-P-Q", 3, 1, 0, True, False, _posti("OPQ", 3, ancora_indice=0)),
        BloccoAulaSemanticoSpec("R-S", 2, 1, 5, True, False, _posti("RS", 2)),
        BloccoAulaSemanticoSpec("T-U", 2, 1, 9, True, False, _posti("TU", 2)),
        BloccoAulaSemanticoSpec("H-I", 2, 2, 0, False, False, _posti("HI", 2)),
        BloccoAulaSemanticoSpec("J-K-L", 3, 2, 4, False, False, _posti("JKL", 3)),
        BloccoAulaSemanticoSpec("M-N", 2, 2, 9, False, False, _posti("MN", 2)),
        BloccoAulaSemanticoSpec("A-B", 2, 3, 0, False, True, _posti("AB", 2)),
        BloccoAulaSemanticoSpec("C-D", 2, 3, 4, False, True, _posti("CD", 2)),
        BloccoAulaSemanticoSpec("E-F-G", 3, 3, 8, False, True, _posti("EFG", 3)),
    ))
