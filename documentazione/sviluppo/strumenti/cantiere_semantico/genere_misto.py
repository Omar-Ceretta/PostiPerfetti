"""Calcolo esatto del massimo di adiacenze di genere misto.

Il modulo è puro: non modifica C1, non importa Qt e non usa punteggi produttivi.
Calcola separatamente:

* il massimo geometrico, determinato da generi, blocchi e posizione del FISSO;
* il massimo ammissibile, che aggiunge soltanto i divieti assoluti L3.

Le incompatibilità L1/L2, le affinità, lo Storico e le preferenze soft non
partecipano al calcolo.
"""
from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from itertools import combinations, permutations, product
from time import perf_counter
from typing import Any, Mapping, Sequence

from .adattatori_comuni import indice_studenti, livelli_relazione, nome_studente
from .modelli import (
    AnalisiGenereAnnuale,
    AnalisiGenereMese,
    AnnataCanonica,
    EsitoOttimoMisto,
    GruppoCanonico,
    GruppoNonPienamenteMisto,
    MeseCanonico,
)
from .serializzazione import firma_json_sha256


class ErroreGenereMisto(ValueError):
    """Segnala un template o un'anagrafica non analizzabili senza ambiguità."""


def _genere(studente: Any) -> str:
    valore = str(getattr(studente, "sesso", "")).strip().upper()
    if valore not in {"M", "F"}:
        raise ErroreGenereMisto(f"Genere non valido per {nome_studente(studente)}.")
    return valore


def _conta_miste_sequenza(sequenza: Sequence[str]) -> int:
    return sum(a != b for a, b in zip(sequenza, sequenza[1:]))


def _template_mese(
    mese: MeseCanonico,
    studenti: Sequence[Any],
    studente_fisso: str | None,
) -> tuple[tuple[tuple[int, int | None, str | None], ...], str]:
    indice = indice_studenti(studenti)
    coperti: list[str] = []
    specifiche: list[tuple[int, int | None, str | None]] = []
    gruppi_ordinati = sorted(
        mese.gruppi,
        key=lambda g: (
            g.fila if g.fila is not None else 10**9,
            g.posizione_nella_fila if g.posizione_nella_fila is not None else 10**9,
            g.group_id,
        ),
    )
    for gruppo in gruppi_ordinati:
        membri = tuple(gruppo.membri_ordinati)
        coperti.extend(membri)
        indice_fisso = None
        genere_fisso = None
        if studente_fisso is not None and studente_fisso in membri:
            indice_fisso = membri.index(studente_fisso)
            genere_fisso = _genere(indice[studente_fisso])
        specifiche.append((len(membri), indice_fisso, genere_fisso))

    attesi = set(indice)
    if len(coperti) != len(set(coperti)):
        raise ErroreGenereMisto("Uno studente compare in più gruppi del mese.")
    if set(coperti) != attesi:
        mancanti = sorted(attesi - set(coperti))
        eccedenti = sorted(set(coperti) - attesi)
        dettagli = []
        if mancanti:
            dettagli.append("mancanti: " + ", ".join(mancanti))
        if eccedenti:
            dettagli.append("eccedenti: " + ", ".join(eccedenti))
        raise ErroreGenereMisto("Il template non copre la classe (" + "; ".join(dettagli) + ").")
    if studente_fisso is not None:
        occorrenze = sum(1 for _, pos, _ in specifiche if pos is not None)
        if occorrenze != 1:
            raise ErroreGenereMisto("Il FISSO deve comparire in un solo gruppo.")

    firma = firma_json_sha256({
        "specifiche": specifiche,
        "generi": sorted((nome, _genere(studente)) for nome, studente in indice.items()),
        "fisso": studente_fisso,
    })
    return tuple(specifiche), firma


def _pattern_gruppo(
    dimensione: int,
    indice_fisso: int | None,
    genere_fisso: str | None,
) -> tuple[tuple[str, ...], ...]:
    risultato = []
    for valori in product(("M", "F"), repeat=dimensione):
        if indice_fisso is not None and valori[indice_fisso] != genere_fisso:
            continue
        risultato.append(tuple(valori))
    return tuple(risultato)


def calcola_massimo_geometrico(
    gruppi: Sequence[GruppoCanonico],
    studenti: Sequence[Any],
    *,
    studente_fisso: str | None = None,
) -> EsitoOttimoMisto:
    """Calcola esattamente il massimo imposto da generi e geometria."""
    inizio = perf_counter()
    indice = indice_studenti(studenti)
    maschi = sum(_genere(s) == "M" for s in indice.values())
    femmine = len(indice) - maschi

    # Costruisce un mese fittizio minimo per riusare il controllo del template.
    class _Mese:
        def __init__(self, gruppi):
            self.gruppi = tuple(gruppi)

    specifiche, _ = _template_mese(_Mese(gruppi), studenti, studente_fisso)  # type: ignore[arg-type]
    nodi = 0

    @lru_cache(maxsize=None)
    def risolvi(indice_gruppo: int, m_rimasti: int, f_rimaste: int):
        nonlocal nodi
        nodi += 1
        if indice_gruppo == len(specifiche):
            return (0, ()) if m_rimasti == 0 and f_rimaste == 0 else None
        dimensione, posizione_fisso, genere_fisso = specifiche[indice_gruppo]
        migliore = None
        for pattern in _pattern_gruppo(dimensione, posizione_fisso, genere_fisso):
            m_usati = pattern.count("M")
            f_usate = dimensione - m_usati
            if m_usati > m_rimasti or f_usate > f_rimaste:
                continue
            coda = risolvi(indice_gruppo + 1, m_rimasti - m_usati, f_rimaste - f_usate)
            if coda is None:
                continue
            valore = _conta_miste_sequenza(pattern) + coda[0]
            testimone = (pattern,) + coda[1]
            candidato = (valore, testimone)
            if migliore is None or candidato[0] > migliore[0] or (
                candidato[0] == migliore[0] and candidato[1] < migliore[1]
            ):
                migliore = candidato
        return migliore

    esito = risolvi(0, maschi, femmine)
    if esito is None:
        raise ErroreGenereMisto("Il template geometrico non può contenere tutti gli studenti.")
    return EsitoOttimoMisto(
        valore=esito[0],
        esatto=True,
        nodi_visitati=nodi,
        durata_secondi=perf_counter() - inizio,
        testimone=esito[1],
    )


def _miglior_ordine_sottoinsieme(
    sottoinsieme: tuple[int, ...],
    generi: tuple[str, ...],
    l3_mask: tuple[int, ...],
    nomi: tuple[str, ...],
    *,
    fisso: int | None = None,
    posizione_fisso: int | None = None,
) -> tuple[int, tuple[int, ...]] | None:
    migliore: tuple[int, tuple[int, ...]] | None = None
    for ordine in permutations(sottoinsieme):
        if fisso is not None and ordine[posizione_fisso] != fisso:
            continue
        # Un cammino e il suo inverso sono equivalenti, salvo il FISSO pinzato.
        if fisso is None and ordine > tuple(reversed(ordine)):
            continue
        valido = True
        valore = 0
        for a, b in zip(ordine, ordine[1:]):
            if l3_mask[a] & (1 << b):
                valido = False
                break
            valore += generi[a] != generi[b]
        if not valido:
            continue
        candidato = (valore, ordine)
        if migliore is None or valore > migliore[0] or (
            valore == migliore[0]
            and tuple(nomi[i] for i in ordine) < tuple(nomi[i] for i in migliore[1])
        ):
            migliore = candidato
    return migliore


def calcola_massimo_ammissibile(
    gruppi: Sequence[GruppoCanonico],
    studenti: Sequence[Any],
    *,
    studente_fisso: str | None = None,
) -> EsitoOttimoMisto:
    """Calcola esattamente il massimo rispettando esclusivamente gli L3."""
    inizio = perf_counter()
    indice_nomi = indice_studenti(studenti)
    nomi = tuple(sorted(indice_nomi))
    oggetti = tuple(indice_nomi[nome] for nome in nomi)
    n = len(nomi)
    generi = tuple(_genere(s) for s in oggetti)
    nome_a_indice = {nome: i for i, nome in enumerate(nomi)}

    class _Mese:
        def __init__(self, gruppi):
            self.gruppi = tuple(gruppi)

    specifiche, _ = _template_mese(_Mese(gruppi), studenti, studente_fisso)  # type: ignore[arg-type]
    dimensioni_ordinarie: list[int] = []
    specifica_fisso: tuple[int, int] | None = None
    for dimensione, posizione_fisso, _ in specifiche:
        if posizione_fisso is None:
            dimensioni_ordinarie.append(dimensione)
        else:
            if specifica_fisso is not None:
                raise ErroreGenereMisto("Più gruppi contengono il FISSO.")
            specifica_fisso = (dimensione, posizione_fisso)

    if any(k not in {2, 3, 4} for k in dimensioni_ordinarie):
        raise ErroreGenereMisto("I6 supporta gruppi lineari di dimensione 2, 3 o 4.")

    l3 = [0] * n
    for i, a in enumerate(oggetti):
        for j in range(i + 1, n):
            inc, _ = livelli_relazione(a, oggetti[j])
            if inc == 3:
                l3[i] |= 1 << j
                l3[j] |= 1 << i
    l3_mask = tuple(l3)
    nodi = 0

    # Miglior cammino valido per ciascun sottoinsieme ordinario.
    candidati_per_dimensione: dict[int, dict[int, tuple[int, tuple[int, ...]]]] = {}
    candidati_per_studente: dict[int, dict[int, list[tuple[int, int, tuple[int, ...]]]]] = {}
    for dimensione in sorted(set(dimensioni_ordinarie)):
        per_mask: dict[int, tuple[int, tuple[int, ...]]] = {}
        per_studente = {i: [] for i in range(n)}
        for sottoinsieme in combinations(range(n), dimensione):
            migliore = _miglior_ordine_sottoinsieme(
                sottoinsieme, generi, l3_mask, nomi
            )
            if migliore is None:
                continue
            mask = sum(1 << i for i in sottoinsieme)
            per_mask[mask] = migliore
            for i in sottoinsieme:
                per_studente[i].append((mask, migliore[0], migliore[1]))
        for lista in per_studente.values():
            lista.sort(key=lambda x: (-x[1], tuple(nomi[i] for i in x[2])))
        candidati_per_dimensione[dimensione] = per_mask
        candidati_per_studente[dimensione] = per_studente

    @lru_cache(maxsize=None)
    def limite_geometrico_ordinario(maschi: int, c2: int, c3: int, c4: int) -> int:
        specs = (2,) * c2 + (3,) * c3 + (4,) * c4

        @lru_cache(maxsize=None)
        def dp(pos: int, m: int):
            if pos == len(specs):
                return 0 if m == 0 else -10**6
            k = specs[pos]
            best = -10**6
            for pattern in product(("M", "F"), repeat=k):
                usati = pattern.count("M")
                if usati <= m:
                    best = max(best, _conta_miste_sequenza(pattern) + dp(pos + 1, m - usati))
            return best

        return dp(0, maschi)

    c2 = dimensioni_ordinarie.count(2)
    c3 = dimensioni_ordinarie.count(3)
    c4 = dimensioni_ordinarie.count(4)

    @lru_cache(maxsize=None)
    def risolvi_ordinari(rem: int, n2: int, n3: int, n4: int):
        nonlocal nodi
        nodi += 1
        if rem == 0:
            return (0, ()) if n2 == n3 == n4 == 0 else None
        if n2 + n3 + n4 == 0:
            return None
        if rem.bit_count() != 2 * n2 + 3 * n3 + 4 * n4:
            return None

        maschi_rimasti = sum(1 for i in range(n) if rem & (1 << i) and generi[i] == "M")
        limite_stato = limite_geometrico_ordinario(maschi_rimasti, n2, n3, n4)
        if limite_stato < 0:
            return None

        dimensioni_disponibili = []
        if n2:
            dimensioni_disponibili.append(2)
        if n3:
            dimensioni_disponibili.append(3)
        if n4:
            dimensioni_disponibili.append(4)

        # MRV: lo studente con meno gruppi ancora ammissibili.
        pivot = None
        opzioni_pivot: list[tuple[int, int, tuple[int, ...], int]] | None = None
        for i in range(n):
            if not (rem & (1 << i)):
                continue
            opzioni = []
            for k in dimensioni_disponibili:
                for mask, valore, ordine in candidati_per_studente[k][i]:
                    if mask & rem == mask:
                        opzioni.append((mask, valore, ordine, k))
            if not opzioni:
                return None
            if opzioni_pivot is None or len(opzioni) < len(opzioni_pivot):
                pivot = i
                opzioni_pivot = opzioni
                if len(opzioni) == 1:
                    break
        assert pivot is not None and opzioni_pivot is not None
        opzioni_pivot.sort(key=lambda x: (-x[1], x[3], tuple(nomi[i] for i in x[2])))

        migliore = None
        for mask, valore, ordine, k in opzioni_pivot:
            nn2, nn3, nn4 = n2, n3, n4
            if k == 2:
                nn2 -= 1
            elif k == 3:
                nn3 -= 1
            else:
                nn4 -= 1
            rem2 = rem ^ mask
            maschi2 = sum(1 for i in range(n) if rem2 & (1 << i) and generi[i] == "M")
            upper = valore + limite_geometrico_ordinario(maschi2, nn2, nn3, nn4)
            if migliore is not None and upper <= migliore[0]:
                continue
            coda = risolvi_ordinari(rem2, nn2, nn3, nn4)
            if coda is None:
                continue
            totale = valore + coda[0]
            testimone = (tuple(nomi[i] for i in ordine),) + coda[1]
            candidato = (totale, testimone)
            if migliore is None or totale > migliore[0] or (
                totale == migliore[0] and testimone < migliore[1]
            ):
                migliore = candidato
                if totale == limite_stato:
                    return migliore
        return migliore

    pieno = (1 << n) - 1
    migliore_totale = None

    if specifica_fisso is None:
        migliore_totale = risolvi_ordinari(pieno, c2, c3, c4)
    else:
        if studente_fisso is None or studente_fisso not in nome_a_indice:
            raise ErroreGenereMisto("Studente FISSO non disponibile nell'anagrafica.")
        fisso = nome_a_indice[studente_fisso]
        dimensione_fisso, posizione_fisso = specifica_fisso
        altri = [i for i in range(n) if i != fisso]
        candidati_fisso = []
        for scelti in combinations(altri, dimensione_fisso - 1):
            sottoinsieme = tuple(sorted((fisso, *scelti)))
            candidato = _miglior_ordine_sottoinsieme(
                sottoinsieme,
                generi,
                l3_mask,
                nomi,
                fisso=fisso,
                posizione_fisso=posizione_fisso,
            )
            if candidato is None:
                continue
            mask = sum(1 << i for i in sottoinsieme)
            candidati_fisso.append((mask, candidato[0], candidato[1]))
        candidati_fisso.sort(key=lambda x: (-x[1], tuple(nomi[i] for i in x[2])))

        # Limite geometrico globale, usato per arrestare appena raggiunto.
        class _Mese2:
            def __init__(self, gruppi):
                self.gruppi = tuple(gruppi)
        limite_globale = calcola_massimo_geometrico(
            gruppi, studenti, studente_fisso=studente_fisso
        ).valore

        for mask, valore, ordine in candidati_fisso:
            rem = pieno ^ mask
            maschi_rimasti = sum(1 for i in range(n) if rem & (1 << i) and generi[i] == "M")
            upper = valore + limite_geometrico_ordinario(maschi_rimasti, c2, c3, c4)
            if migliore_totale is not None and upper <= migliore_totale[0]:
                continue
            coda = risolvi_ordinari(rem, c2, c3, c4)
            if coda is None:
                continue
            totale = valore + coda[0]
            testimone = (tuple(nomi[i] for i in ordine),) + coda[1]
            candidato = (totale, testimone)
            if migliore_totale is None or totale > migliore_totale[0] or (
                totale == migliore_totale[0] and testimone < migliore_totale[1]
            ):
                migliore_totale = candidato
                if totale == limite_globale:
                    break

    if migliore_totale is None:
        raise ErroreGenereMisto(
            "Nessuna copertura completa rispetta la geometria e le incompatibilità L3."
        )
    return EsitoOttimoMisto(
        valore=migliore_totale[0],
        esatto=True,
        nodi_visitati=nodi,
        durata_secondi=perf_counter() - inizio,
        testimone=migliore_totale[1],
    )


def _gruppi_non_misti(
    mese: MeseCanonico,
    studenti: Mapping[str, Any],
) -> tuple[GruppoNonPienamenteMisto, ...]:
    risultato = []
    for gruppo in mese.gruppi:
        generi = tuple(_genere(studenti[nome]) for nome in gruppo.membri_ordinati)
        stesso = sum(a == b for a, b in zip(generi, generi[1:]))
        if stesso:
            risultato.append(
                GruppoNonPienamenteMisto(
                    group_id=gruppo.group_id,
                    tipo=gruppo.tipo,
                    membri=gruppo.membri_ordinati,
                    adiacenze_stesso_genere=stesso,
                    motivo="non_determinato",
                )
            )
    return tuple(risultato)


def costruisci_analisi_genere_misto(
    annata: AnnataCanonica,
    studenti: Sequence[Any],
) -> AnalisiGenereAnnuale:
    """Costruisce l'analisi annuale, riusando i massimi per template identici."""
    indice = indice_studenti(studenti)
    if set(indice) != {voce.studente for voce in annata.studenti}:
        raise ErroreGenereMisto("L'anagrafica non coincide con l'AnnataCanonica.")

    cache: dict[str, tuple[EsitoOttimoMisto, EsitoOttimoMisto]] = {}
    mesi = []
    for mese in annata.mesi:
        _, firma = _template_mese(mese, studenti, annata.studente_fisso)
        if firma not in cache:
            geometrico = calcola_massimo_geometrico(
                mese.gruppi, studenti, studente_fisso=annata.studente_fisso
            )
            ammissibile = calcola_massimo_ammissibile(
                mese.gruppi, studenti, studente_fisso=annata.studente_fisso
            )
            cache[firma] = geometrico, ammissibile
        geometrico, ammissibile = cache[firma]
        mesi.append(
            AnalisiGenereMese(
                mese=mese.mese_finale,
                firma_template=firma,
                massimo_geometrico=geometrico,
                massimo_ammissibile=ammissibile,
                adiacenze_miste_ottenute=mese.riepilogo.adiacenze_miste,
                adiacenze_stesso_genere=mese.riepilogo.adiacenze_stesso_genere,
                gruppi_non_pienamente_misti=_gruppi_non_misti(mese, indice),
            )
        )
    return AnalisiGenereAnnuale(
        flag_attivo=annata.run.genere_misto_attivo,
        mesi=tuple(mesi),
        massimo_geometrico_totale=sum(x.massimo_geometrico.valore for x in mesi),
        massimo_ammissibile_totale=sum(x.massimo_ammissibile.valore for x in mesi),
        adiacenze_miste_ottenute_totali=sum(x.adiacenze_miste_ottenute for x in mesi),
    )


def arricchisci_annata_genere_misto(
    annata: AnnataCanonica,
    studenti: Sequence[Any],
) -> AnnataCanonica:
    """Restituisce una nuova annata immutabile con la sezione I6 compilata."""
    analisi = costruisci_analisi_genere_misto(annata, studenti)
    return replace(annata, genere_misto=analisi)


__all__ = [
    "ErroreGenereMisto",
    "arricchisci_annata_genere_misto",
    "calcola_massimo_ammissibile",
    "calcola_massimo_geometrico",
    "costruisci_analisi_genere_misto",
]
