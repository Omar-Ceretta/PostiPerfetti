# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Strategie della ricerca e prototipi sperimentali.

La strategia produttiva è ``C1``: nel solo backtracking a coppie memoizza gli
stati falliti già dimostrati, conservando ordine, casualità, tetto logico e
output della baseline ``A``. Nei terzetti ``C1`` equivale intenzionalmente ad
``A``. La baseline ``A`` e i prototipi ``B*`` restano selezionabili
esplicitamente dal laboratorio o tramite
``POSTIPERFETTI_STRATEGIA_RICERCA``. Nessuna funzione usa lo stato globale del
modulo :mod:`random`.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import os
from typing import Any, Callable, Iterable, Sequence, TypeVar


STRATEGIE = ("A", "B1", "B2", "B3", "B4", "C1")
STRATEGIA_PRODUZIONE = "C1"
VARIABILE_AMBIENTE = "POSTIPERFETTI_STRATEGIA_RICERCA"

_strategia_locale: ContextVar[str | None] = ContextVar(
    "postiperfetti_strategia_ricerca", default=None
)

T = TypeVar("T")


def normalizza_strategia(valore: str | None) -> str:
    """Converte etichette di benchmark e alias nella strategia effettiva."""
    testo = (valore or STRATEGIA_PRODUZIONE).strip().upper()
    for strategia in ("C1", "B4", "B3", "B2", "B1", "A"):
        if testo == strategia or testo.startswith(strategia + "_"):
            return strategia
    raise ValueError(
        f"Strategia di ricerca non valida: {valore!r}. "
        f"Valori ammessi: {', '.join(STRATEGIE)}"
    )


def strategia_corrente() -> str:
    """Restituisce la strategia attiva; in produzione il default è C1."""
    locale = _strategia_locale.get()
    if locale is not None:
        return locale
    return normalizza_strategia(
        os.environ.get(VARIABILE_AMBIENTE, STRATEGIA_PRODUZIONE)
    )


@contextmanager
def usa_strategia(valore: str | None):
    """Attiva una strategia nel solo contesto corrente e poi la ripristina."""
    strategia = normalizza_strategia(valore)
    token = _strategia_locale.set(strategia)
    try:
        yield strategia
    finally:
        _strategia_locale.reset(token)




def usa_memo_stati_falliti_coppie(strategia: str | None = None) -> bool:
    """Indica se è attiva la memoizzazione C1 del backtracking a coppie.

    C1 non modifica punteggi, ordinamenti o casualità. Conserva soltanto,
    dentro una singola invocazione di ricerca, gli stati già esplorati fino in
    fondo senza soluzione. La baseline A resta disponibile come oracolo
    esplicito per i collaudi.
    """
    return normalizza_strategia(strategia or strategia_corrente()) == "C1"

def _nome(studente: Any) -> str:
    metodo = getattr(studente, "get_nome_completo", None)
    return metodo() if callable(metodo) else str(studente)


def identita_coppia(voce: Sequence[Any]) -> tuple[str, str]:
    """Identità canonica di una voce coppia del motore."""
    return tuple(sorted((_nome(voce[0]), _nome(voce[1]))))


def identita_gruppo(voce: Sequence[Any]) -> tuple[str, ...]:
    """Identità orientata di una voce gruppo ``(membri, punteggio)``."""
    return tuple(_nome(studente) for studente in voce[0])


def profilo_posizioni(membri: Iterable[Any]) -> tuple[Any, ...]:
    """Impronta strutturale conservativa delle preferenze di fila."""
    posizioni = tuple(
        getattr(studente, "nota_posizione", "NORMALE") for studente in membri
    )
    return (
        len(posizioni),
        sum(posizione in ("PRIMA", "FISSO") for posizione in posizioni),
        sum(posizione == "ULTIMA" for posizione in posizioni),
        sum(posizione == "FISSO" for posizione in posizioni),
        next((indice for indice, posizione in enumerate(posizioni)
              if posizione == "FISSO"), None),
    )


def livello_relazione(a: Any, b: Any, attributo: str) -> int:
    """Massimo livello dichiarato nelle due direzioni per una relazione."""
    nome_a, nome_b = _nome(a), _nome(b)
    rel_a = getattr(a, attributo, {}) or {}
    rel_b = getattr(b, attributo, {}) or {}
    return max(int(rel_a.get(nome_b, 0)), int(rel_b.get(nome_a, 0)))


def chiave_stretta_coppia(voce: Sequence[Any], utilizzi: int) -> tuple[Any, ...]:
    """Chiave B2/B3: qualità, storia e impronta locale della coppia."""
    a, b, info = voce
    dettagli = info.get("dettagli", {})
    return (
        int(utilizzi),
        int(info.get("punteggio_totale", 0)),
        int(dettagli.get("incompatibilita", 0)),
        int(dettagli.get("affinita", 0)),
        int(dettagli.get("genere_misto", 0)),
        int(dettagli.get("posizione", 0)),
        livello_relazione(a, b, "incompatibilita"),
        livello_relazione(a, b, "affinita"),
        profilo_posizioni((a, b)),
    )


def chiave_stretta_gruppo(
    voce: Sequence[Any], frequenze: dict[frozenset[str], int]
) -> tuple[Any, ...]:
    """Chiave B2/B3 per un gruppo orientato di due, tre o quattro membri."""
    membri, punti = voce
    adiacenze = list(zip(membri, membri[1:]))
    profilo_storico = sorted(
        (
            int(frequenze.get(frozenset((_nome(a), _nome(b))), 0))
            for a, b in adiacenze
        ),
        reverse=True,
    )
    profilo_incompatibilita = sorted(
        (livello_relazione(a, b, "incompatibilita") for a, b in adiacenze),
        reverse=True,
    )
    profilo_affinita = sorted(
        (livello_relazione(a, b, "affinita") for a, b in adiacenze),
        reverse=True,
    )
    return (
        int(punti),
        len([frequenza for frequenza in profilo_storico if frequenza > 0]),
        tuple(profilo_storico),
        tuple(profilo_incompatibilita),
        tuple(profilo_affinita),
        profilo_posizioni(membri),
    )


def _offset_contesto(contesto: Any, ampiezza: int) -> int:
    if ampiezza <= 1:
        return 0
    digest = sha256(repr(contesto).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % ampiezza


def _trasforma_classe(
    classe: list[T], *, strategia: str, rng: Any, ripartenza: int,
    contesto: Any, chiave_stabile: Callable[[T], Any],
) -> list[T]:
    """Mescola o ruota una singola classe senza uscirne."""
    if len(classe) <= 1:
        return classe
    risultato = list(classe)
    if strategia in ("B1", "B2"):
        rng.shuffle(risultato)
        return risultato
    if strategia == "B3":
        risultato.sort(key=chiave_stabile)
        offset = (
            _offset_contesto(contesto, len(risultato))
            + max(0, int(ripartenza) - 1)
        ) % len(risultato)
        return risultato[offset:] + risultato[:offset]
    return risultato


def diversifica_classi_contigue(
    voci: Sequence[T], *, chiave_equivalenza: Callable[[T], Any],
    strategia: str, rng: Any, ripartenza: int, contesto: Any,
    chiave_stabile: Callable[[T], Any],
) -> list[T]:
    """Trasforma soltanto classi di equivalenza contigue.

    Le classi restano nello stesso ordine relativo. Questa scelta è volutamente
    prudente: B2/B3 non possono scavalcare una voce che differisce nella chiave
    stretta, anche quando il punteggio totale coincide.
    """
    if strategia == "A" or len(voci) <= 1:
        return list(voci)
    risultato: list[T] = []
    inizio = 0
    while inizio < len(voci):
        chiave = chiave_equivalenza(voci[inizio])
        fine = inizio + 1
        while fine < len(voci) and chiave_equivalenza(voci[fine]) == chiave:
            fine += 1
        risultato.extend(_trasforma_classe(
            list(voci[inizio:fine]),
            strategia=strategia,
            rng=rng,
            ripartenza=ripartenza,
            contesto=(contesto, chiave),
            chiave_stabile=chiave_stabile,
        ))
        inizio = fine
    return risultato


def ordina_coppie_t4(
    coppie_per_utilizzo: dict[int, list[Sequence[Any]]],
    gruppi_ordinati: Sequence[int], *, rng: Any, ripartenza: int,
    strategia: str | None = None, contesto: Any = None,
) -> list[Sequence[Any]]:
    """Costruisce l'ordine T4 delle coppie; C1 conserva quello di A."""
    scelta = normalizza_strategia(strategia or strategia_corrente())
    # B4 è selettiva: nelle coppie conserva integralmente la baseline A.
    if scelta in ("B4", "C1"):
        scelta = "A"
    risultato: list[Sequence[Any]] = []
    for utilizzi in gruppi_ordinati:
        gruppo = list(coppie_per_utilizzo[utilizzi])
        if scelta == "A":
            if utilizzi == 0:
                rng.shuffle(gruppo)
            else:
                gruppo.sort(
                    key=lambda voce: voce[2]["punteggio_totale"], reverse=True
                )
            risultato.extend(gruppo)
            continue

        # Tutti i prototipi B preservano il rango per punteggio anche nel gruppo
        # mai usato; solo i pareggi possono cambiare ordine.
        gruppo.sort(key=lambda voce: voce[2]["punteggio_totale"], reverse=True)
        if scelta == "B1":
            chiave = lambda voce: int(voce[2]["punteggio_totale"])
        else:
            chiave = lambda voce, u=utilizzi: chiave_stretta_coppia(voce, u)
        risultato.extend(diversifica_classi_contigue(
            gruppo,
            chiave_equivalenza=chiave,
            strategia=scelta,
            rng=rng,
            ripartenza=ripartenza,
            contesto=("coppie", contesto, utilizzi),
            chiave_stabile=identita_coppia,
        ))
    return risultato


def precalcola_chiavi_strette_terzetti(
    indice: dict[Any, Sequence[Sequence[Any]]],
    frequenze: dict[frozenset[str], int],
) -> dict[int, tuple[Any, ...]]:
    """Calcola una sola volta le chiavi B2/B3 condivise dalle ripartenze."""
    risultato: dict[int, tuple[Any, ...]] = {}
    for voci in indice.values():
        for voce in voci:
            chiave_id = id(voce)
            if chiave_id not in risultato:
                risultato[chiave_id] = chiave_stretta_gruppo(voce, frequenze)
    return risultato


def _identita_ancora(voci: Sequence[Sequence[Any]]) -> str:
    """Ricava un contesto stabile dall'intersezione dei membri delle voci."""
    if not voci:
        return "senza-alternative"
    comuni = set(identita_gruppo(voci[0]))
    for voce in voci[1:]:
        comuni.intersection_update(identita_gruppo(voce))
        if not comuni:
            break
    if comuni:
        return sorted(comuni)[0]
    digest = sha256(repr(sorted(identita_gruppo(v) for v in voci)).encode("utf-8"))
    return digest.hexdigest()[:16]


def diversifica_indice_terzetti(
    indice: dict[Any, Sequence[Sequence[Any]]], *, rng: Any,
    ripartenza: int, frequenze: dict[frozenset[str], int],
    strategia: str | None = None, contesto: Any = None,
    chiavi_strette: dict[int, tuple[Any, ...]] | None = None,
) -> dict[Any, list[Sequence[Any]]]:
    """Diversifica le liste per ancora senza alterare classi non equivalenti."""
    scelta = normalizza_strategia(strategia or strategia_corrente())
    # B4 applica la chiave stretta B2 soltanto alla modalità a terzetti.
    if scelta == "B4":
        scelta = "B2"
    elif scelta == "C1":
        scelta = "A"
    risultato: dict[Any, list[Sequence[Any]]] = {}
    for ancora, voci_originali in indice.items():
        voci = list(voci_originali)
        if scelta == "A":
            rng.shuffle(voci)
        else:
            # L'indice nasce già ordinato per punti decrescenti. Lo rendiamo
            # esplicito per resistere a future modifiche della costruzione.
            voci.sort(key=lambda voce: voce[1], reverse=True)
            if scelta == "B1":
                chiave = lambda voce: int(voce[1])
            else:
                cache = chiavi_strette or precalcola_chiavi_strette_terzetti(
                    {0: voci}, frequenze
                )
                chiave = lambda voce: cache[id(voce)]
            voci = diversifica_classi_contigue(
                voci,
                chiave_equivalenza=chiave,
                strategia=scelta,
                rng=rng,
                ripartenza=ripartenza,
                contesto=("terzetti", contesto, _identita_ancora(voci)),
                chiave_stabile=identita_gruppo,
            )
        risultato[ancora] = voci
    return risultato
