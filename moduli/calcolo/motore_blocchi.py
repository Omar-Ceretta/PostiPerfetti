# -*- coding: utf-8 -*-
"""Motore del Layout unico per geometrie d'aula a blocchi 2/3.

Conserva la cascata T1–T4, i punteggi di
``MotoreVincoliConfigurato``, l'ordine interno dei gruppi, la blacklist per
adiacenza, la casualità locale riproducibile, il best-of-N, il tetto nodi e la
diagnostica strutturata.

La geometria impone il multinsieme esatto delle taglie dei gruppi. PRIMA è
un vincolo fisico sulla zona semantica ``zona_prima``; FISSO è ancorato a uno
specifico posto dello schema. ULTIMA resta una preferenza soft ottimizzata dal
matcher finale. Nessuna di queste proprietà viene dedotta dalla sola profondità.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from time import perf_counter_ns
from typing import Any, Iterable, Mapping, Sequence
import itertools

from moduli.casualita import crea_generatore, deriva_seed, risolvi_seed_principale
from moduli.processi.diagnostica_ricerca import firma_indice_gruppi, messaggio_motore
from moduli.dominio.metrica_pulizia import (
    Gruppo,
    TIPO_COPPIA,
    TIPO_TERZETTO,
    adiacenze_partizione,
    chiave_pulizia_terzetti,
    conta_affinita_soddisfatte_terzetti,
    conta_incompatibilita_per_livello_terzetti,
    livello_incompatibilita,
    nome_completo,
)
from moduli.calcolo.valutazione_gruppi import (
    LIMITE_NODI_BACKTRACK,
    NUM_RIPARTENZE_TENTATIVO_4,
    _penalita_prima_ultima,
    _punteggio_partizione,
    valuta_gruppo,
)
from moduli.calcolo.matcher_blocchi import (
    CollocazioneGruppoBlocco,
    abbina_gruppi_a_blocchi,
    verifica_fattibilita_matching,
    verifica_fattibilita_parziale_matching,
)
from moduli.dominio.schema_blocchi_semantico import SchemaBlocchiSemantico
from moduli.calcolo.strategie_ricerca import (
    diversifica_indice_terzetti,
    precalcola_chiavi_strette_terzetti,
    strategia_corrente,
)
from moduli.dominio.studenti import chiave_ordinamento_studente
from moduli.dominio.vincoli import MotoreVincoliConfigurato


PENALITA_RIUSO_STORICO = 500
NUM_CANDIDATI_BLOCCHI = 3


def _incrementa(contatore: Any, voce: str, quantita: int = 1) -> None:
    if contatore is None:
        return
    metodo = getattr(contatore, "incrementa", None)
    if callable(metodo):
        metodo(voce, quantita)
    else:
        contatore[voce] += quantita


def _chiave_coppia_id(a: Any, b: Any) -> tuple[int, int]:
    return tuple(sorted((id(a), id(b))))


def _chiave_nomi(a: Any, b: Any) -> frozenset[str]:
    return frozenset((nome_completo(a), nome_completo(b)))


def _normalizza_frequenze(
    frequenze: Mapping[Any, int] | None,
) -> dict[frozenset[str], int]:
    risultato: dict[frozenset[str], int] = {}
    if not frequenze:
        return risultato
    for chiave, valore in frequenze.items():
        if isinstance(chiave, frozenset):
            nomi = list(chiave)
        elif isinstance(chiave, (tuple, list, set)):
            nomi = list(chiave)
        else:
            raise ValueError(
                "Le chiavi dello storico devono contenere esattamente due nomi."
            )
        if len(nomi) != 2:
            raise ValueError(
                "Le chiavi dello storico devono contenere esattamente due nomi."
            )
        if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
            raise ValueError("Le frequenze storiche devono essere interi >= 0.")
        frequenza = valore
        if frequenza:
            risultato[frozenset((str(nomi[0]), str(nomi[1])))] = frequenza
    return risultato


def _tipo_per_taglia(taglia: int) -> str:
    if taglia == 2:
        return TIPO_COPPIA
    if taglia == 3:
        return TIPO_TERZETTO
    raise ValueError(f"Taglia di gruppo non supportata: {taglia}.")


def _contiene_fisso(membri: Sequence[Any]) -> bool:
    return any(
        getattr(membro, "nota_posizione", "NORMALE") == "FISSO"
        for membro in membri
    )


def _valuta_gruppo_blocchi(
    membri: Sequence[Any],
    punteggio: Mapping[tuple[int, int], int],
    bloccata: Mapping[tuple[int, int], bool],
    *,
    indice_fisso_ancora: int | None,
    contatori: Any = None,
) -> tuple[list[Any], int] | None:
    """Valuta un gruppo rispettando l'indice fisico dell'eventuale FISSO.

    Senza FISSO usa la valutazione comune delle adiacenze consecutive. Con FISSO, invece, la posizione interna non è più implicitamente
    l'estremo sinistro: deve coincidere con l'indice del posto-ancora dichiarato
    nello schema semantico.
    """
    membri = list(membri)
    posizioni_fisso = [
        i for i, studente in enumerate(membri)
        if getattr(studente, "nota_posizione", "NORMALE") == "FISSO"
    ]
    if not posizioni_fisso:
        return valuta_gruppo(membri, punteggio, bloccata, contatori=contatori)
    if len(posizioni_fisso) != 1 or indice_fisso_ancora is None:
        return None
    if not 0 <= indice_fisso_ancora < len(membri):
        return None

    _incrementa(contatori, "gruppi_valutati")
    n_membri = len(membri)
    info_coppia: dict[tuple[int, int], tuple[bool, int]] = {}
    for i in range(n_membri):
        for j in range(i + 1, n_membri):
            chiave = _chiave_coppia_id(membri[i], membri[j])
            info_coppia[(i, j)] = (bool(bloccata[chiave]), int(punteggio[chiave]))

    miglior_ordine: list[Any] | None = None
    miglior_punteggio: int | None = None
    for perm in itertools.permutations(range(n_membri)):
        _incrementa(contatori, "orientamenti_generati")
        posizione_fisso = next(
            posizione
            for posizione, indice_originale in enumerate(perm)
            if indice_originale == posizioni_fisso[0]
        )
        if posizione_fisso != indice_fisso_ancora:
            continue
        # Con un posto-ancora esplicito non si eliminano specchiate: un ordine
        # speculare può collocare il FISSO in un posto fisico differente.
        _incrementa(contatori, "orientamenti_valutati")
        somma = 0
        ammissibile = True
        for posizione in range(n_membri - 1):
            a = perm[posizione]
            b = perm[posizione + 1]
            chiave = (a, b) if a < b else (b, a)
            e_bloccata, punti = info_coppia[chiave]
            if e_bloccata:
                ammissibile = False
                break
            somma += punti
        if not ammissibile:
            continue
        if miglior_punteggio is None or somma > miglior_punteggio:
            miglior_punteggio = somma
            miglior_ordine = [membri[i] for i in perm]

    if miglior_ordine is None or miglior_punteggio is None:
        return None
    return (
        miglior_ordine,
        miglior_punteggio - _penalita_prima_ultima(miglior_ordine),
    )


def _firma_gruppi_parziali(gruppi: Sequence[Gruppo]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Firma canonica necessaria alla memoizzazione geometry-aware."""
    return tuple(sorted(
        (
            gruppo.tipo,
            tuple(nome_completo(membro) for membro in gruppo.membri),
        )
        for gruppo in gruppi
    ))


def _firma_geometrica_parziale(
    gruppi: Sequence[Gruppo],
) -> tuple[tuple[int, bool, tuple[int, ...]], ...]:
    """Multinsieme dei soli requisiti hard del matcher, con molteplicità.

    A schema invariato, capienza, presenza di PRIMA e indici FISSO determinano
    i blocchi compatibili. ULTIMA è ottimizzata soltanto dopo la partizione.
    Nomi, genere e adiacenze restano nei gruppi e nell'indice: non sono usati
    per confondere studenti rimasti diversi nella memoizzazione U6d.
    """
    profili = []
    for gruppo in gruppi:
        note = tuple(
            str(getattr(s, "nota_posizione", "NORMALE")).strip().upper()
            for s in gruppo.membri
        )
        profili.append((
            len(gruppo.membri),
            "PRIMA" in note,
            tuple(i for i, nota in enumerate(note) if nota == "FISSO"),
        ))
    return tuple(sorted(profili))


def _rappresenta_partizione(gruppi: Sequence[Gruppo] | None) -> Any:
    if gruppi is None:
        return None
    return [
        (gruppo.tipo, [nome_completo(membro) for membro in gruppo.membri])
        for gruppo in gruppi
    ]


def _calcola_punteggi_coppie(
    motore: MotoreVincoliConfigurato,
    studenti: Sequence[Any],
    frequenze: Mapping[frozenset[str], int],
    *,
    storico_blocca: bool,
    contatori: Any = None,
) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], bool]]:
    """Calcola punteggi e blocchi con la stessa semantica storica dei terzetti."""
    punteggio: dict[tuple[int, int], int] = {}
    bloccata: dict[tuple[int, int], bool] = {}
    for i in range(len(studenti)):
        for j in range(i + 1, len(studenti)):
            a, b = studenti[i], studenti[j]
            risultato = motore.calcola_punteggio_coppia(a, b)
            _incrementa(contatori, "coppie_valutate")
            chiave_id = _chiave_coppia_id(a, b)
            usi = int(frequenze.get(_chiave_nomi(a, b), 0))
            e_liv3 = livello_incompatibilita(a, b) == 3
            if e_liv3:
                _incrementa(contatori, "coppie_liv3")
            if usi:
                _incrementa(contatori, "coppie_storiche")
                if storico_blocca:
                    _incrementa(contatori, "coppie_bloccate_storico")
            punteggio[chiave_id] = int(risultato["punteggio_totale"]) - (
                PENALITA_RIUSO_STORICO * usi
            )
            bloccata[chiave_id] = e_liv3 or (storico_blocca and usi > 0)
    return punteggio, bloccata


def _genera_gruppi_ammissibili(
    studenti: Sequence[Any],
    taglie_presenti: Iterable[int],
    punteggio: Mapping[tuple[int, int], int],
    bloccata: Mapping[tuple[int, int], bool],
    *,
    indice_fisso_ancora: int | None = None,
    contatori: Any = None,
) -> dict[int, list[tuple[list[Any], int]]]:
    """Indicizza per studente tutti i gruppi ammissibili delle taglie richieste."""
    indice: dict[int, list[tuple[list[Any], int]]] = {id(s): [] for s in studenti}
    for taglia in sorted(set(int(t) for t in taglie_presenti)):
        for combinazione in itertools.combinations(studenti, taglia):
            _incrementa(contatori, f"combinazioni_{taglia}_considerate")
            valutazione = _valuta_gruppo_blocchi(
                list(combinazione),
                punteggio,
                bloccata,
                indice_fisso_ancora=indice_fisso_ancora,
                contatori=contatori,
            )
            if valutazione is None:
                continue
            membri_ordinati, punti = valutazione
            _incrementa(contatori, f"gruppi_{taglia}_ammissibili")
            voce = (membri_ordinati, int(punti))
            for studente in combinazione:
                indice[id(studente)].append(voce)

    for alternative in indice.values():
        alternative.sort(key=lambda voce: voce[1], reverse=True)
    return indice


def _registra_esito_matching_parziale(telemetria: Any, esito: Any) -> None:
    if telemetria is None:
        return
    telemetria.incrementa("matching_parziale_chiamate")
    telemetria.incrementa(
        "matching_parziale_visite_archi",
        int(esito.diagnostica.visite_archi_fattibilita),
    )
    if not esito.fattibile:
        telemetria.incrementa("matching_parziale_fallimenti")
        for errore in esito.errori_duri:
            telemetria.incrementa(f"matching_fallimento:{errore}")



def _matching_parziale_cached(
    gruppi: tuple[Gruppo, ...],
    schema: SchemaBlocchiSemantico,
    *,
    fisso_atteso: bool,
    telemetria: Any = None,
    cache: dict[Any, bool] | None = None,
) -> bool:
    """Cache di sola fattibilità, locale a una ricerca con schema invariato.

    Il matcher hard dipende da capienza, presenza di PRIMA e indici FISSO.
    Nomi, ULTIMA e ordine fra gruppi non cambiano l'esistenza del matching.
    Il matcher finale resta completo: collocazioni e spareggi non sono cached.
    Le note sono rilette a ogni chiamata, anche per studenti mutabili.
    """
    chiave = None
    if cache is not None:
        chiave = (_firma_geometrica_parziale(gruppi), bool(fisso_atteso))
        if chiave in cache:
            if telemetria is not None:
                telemetria.incrementa("matching_parziale_cache_hit")
            return bool(cache[chiave])
    esito = verifica_fattibilita_parziale_matching(
        gruppi,
        schema,
        fisso_atteso=fisso_atteso,
    )
    _registra_esito_matching_parziale(telemetria, esito)
    ok = bool(esito.fattibile)
    if cache is not None and chiave is not None:
        cache[chiave] = ok
    return ok


def _dominio_geometrico_studente(
    studente: Any,
    disponibili_id: set[int],
    indice: Mapping[int, Sequence[tuple[list[Any], int]]],
    rimanenti_per_taglia: Mapping[int, int],
    schema: SchemaBlocchiSemantico,
    *,
    gruppi_scelti: tuple[Gruppo, ...],
    fisso_atteso: bool,
    telemetria: Any = None,
    cache_matching: dict[Any, bool] | None = None,
) -> list[tuple[list[Any], int]]:
    out: list[tuple[list[Any], int]] = []
    for membri_ordinati, punti in indice.get(id(studente), ()):
        taglia = len(membri_ordinati)
        if rimanenti_per_taglia.get(taglia, 0) <= 0:
            continue
        if not all(id(membro) in disponibili_id for membro in membri_ordinati):
            continue
        gruppo = Gruppo(_tipo_per_taglia(taglia), membri_ordinati)
        if _matching_parziale_cached(
            gruppi_scelti + (gruppo,),
            schema,
            fisso_atteso=fisso_atteso,
            telemetria=telemetria,
            cache=cache_matching,
        ):
            out.append((membri_ordinati, int(punti)))
    return out


def _forward_check_geometrico_blocchi(
    disponibili: list[Any],
    disponibili_id: set[int],
    indice: Mapping[int, Sequence[tuple[list[Any], int]]],
    rimanenti_per_taglia: Mapping[int, int],
    schema: SchemaBlocchiSemantico,
    *,
    gruppi_scelti: tuple[Gruppo, ...],
    fisso_atteso: bool,
    telemetria: Any = None,
    cache_matching: dict[Any, bool] | None = None,
) -> bool:
    for studente in disponibili:
        if telemetria is not None:
            telemetria.incrementa("fcg_student_checks")
        if not _dominio_geometrico_studente(
            studente,
            disponibili_id,
            indice,
            rimanenti_per_taglia,
            schema,
            gruppi_scelti=gruppi_scelti,
            fisso_atteso=fisso_atteso,
            telemetria=telemetria,
            cache_matching=cache_matching,
        ):
            if telemetria is not None:
                telemetria.incrementa("fcg_fallimenti")
            return False
    return True


def _backtrack_blocchi_mrvg(
    disponibili: list[Any],
    disponibili_id: set[int],
    indice: Mapping[int, Sequence[tuple[list[Any], int]]],
    rimanenti_per_taglia: dict[int, int],
    schema: SchemaBlocchiSemantico,
    *,
    gruppi_scelti: tuple[Gruppo, ...] = (),
    fisso_atteso: bool = False,
    contatore_nodi: list[int] | None = None,
    limite_nodi: int | None = None,
    profondita: int = 0,
    telemetria: Any = None,
    stati_falliti: set[Any] | None = None,
    ordine_stabile: Mapping[int, int] | None = None,
    cache_matching: dict[Any, bool] | None = None,
    tie_seed: int | None = None,
) -> list[Gruppo] | None:
    """Rescue T1–T3: MRV sui domini ancora geometricamente compatibili.

    Non rilassa alcun vincolo e non altera i punteggi dei gruppi; cambia solo
    la variabile (studente) scelta quando l'ordine produttivo è impantanato.
    """
    if limite_nodi is None:
        limite_nodi = LIMITE_NODI_BACKTRACK
    if ordine_stabile is None:
        ordine_stabile = {id(s): i for i, s in enumerate(disponibili)}
    if cache_matching is None:
        cache_matching = {}

    if limite_nodi is None:
        limite_nodi = LIMITE_NODI_BACKTRACK

    chiave_stato = None
    if stati_falliti is not None:
        chiave_stato = (
            frozenset(disponibili_id),
            tuple(sorted(rimanenti_per_taglia.items())),
            _firma_gruppi_parziali(gruppi_scelti),
        )
        if chiave_stato in stati_falliti:
            if telemetria is not None:
                telemetria.potatura("memo_stato_fallito")
                telemetria.incrementa("memo_hit")
            return None

    if contatore_nodi is not None:
        contatore_nodi[0] += 1
        if telemetria is not None:
            telemetria.nodo(profondita)
        if contatore_nodi[0] > int(limite_nodi):
            if telemetria is not None:
                telemetria.potatura("tetto_nodi")
            return None

    if sum(k * v for k, v in rimanenti_per_taglia.items()) != len(disponibili):
        if telemetria is not None:
            telemetria.potatura("forma_residua_incoerente")
        return None
    if not disponibili:
        if any(rimanenti_per_taglia.values()):
            return None
        esito = verifica_fattibilita_matching(gruppi_scelti, schema)
        return [] if esito.fattibile else None

    fisso = next(
        (s for s in disponibili if getattr(s, "nota_posizione", "NORMALE") == "FISSO"),
        None,
    )
    candidati_studenti = [fisso] if fisso is not None else disponibili
    migliore_studente = None
    migliore_dominio = None
    migliore_chiave = None
    for studente in candidati_studenti:
        dominio = _dominio_geometrico_studente(
            studente,
            disponibili_id,
            indice,
            rimanenti_per_taglia,
            schema,
            gruppi_scelti=gruppi_scelti,
            fisso_atteso=fisso_atteso,
            telemetria=telemetria,
            cache_matching=cache_matching,
        )
        if telemetria is not None:
            telemetria.incrementa("mrvg_domain_eval")
        if tie_seed is None:
            spareggio_studente = int(ordine_stabile.get(id(studente), 10**9))
        else:
            spareggio_studente = int(deriva_seed(
                tie_seed,
                "mrvg_studente",
                profondita,
                nome_completo(studente),
            ))
        chiave = (len(dominio), spareggio_studente)
        if migliore_chiave is None or chiave < migliore_chiave:
            migliore_chiave = chiave
            migliore_studente = studente
            migliore_dominio = dominio
            if chiave[0] == 0:
                break

    if migliore_studente is None or not migliore_dominio:
        if telemetria is not None:
            telemetria.potatura("mrvg_dominio_vuoto")
        if stati_falliti is not None and chiave_stato is not None:
            stati_falliti.add(chiave_stato)
        return None

    dominio_iterabile = migliore_dominio
    if tie_seed is not None:
        dominio_iterabile = sorted(
            migliore_dominio,
            key=lambda voce: (
                -int(voce[1]),
                int(deriva_seed(
                    tie_seed,
                    "mrvg_gruppo",
                    profondita,
                    tuple(nome_completo(m) for m in voce[0]),
                )),
            ),
        )

    for membri_ordinati, _punti in dominio_iterabile:
        taglia = len(membri_ordinati)
        if telemetria is not None:
            telemetria.decisione(
                f"mrvg_gruppo_{taglia}",
                tuple(nome_completo(m) for m in membri_ordinati),
                profondita,
            )
        usati = {id(m) for m in membri_ordinati}
        gruppo = Gruppo(_tipo_per_taglia(taglia), membri_ordinati)
        nuovi_gruppi = gruppi_scelti + (gruppo,)
        nuovi_id = disponibili_id - usati
        nuovi_disp = [s for s in disponibili if id(s) in nuovi_id]
        nuovi_rim = dict(rimanenti_per_taglia)
        nuovi_rim[taglia] -= 1
        risultato = _backtrack_blocchi_mrvg(
            nuovi_disp,
            nuovi_id,
            indice,
            nuovi_rim,
            schema,
            gruppi_scelti=nuovi_gruppi,
            fisso_atteso=fisso_atteso,
            contatore_nodi=contatore_nodi,
            limite_nodi=limite_nodi,
            profondita=profondita + 1,
            telemetria=telemetria,
            stati_falliti=stati_falliti,
            ordine_stabile=ordine_stabile,
            cache_matching=cache_matching,
            tie_seed=tie_seed,
        )
        if risultato is not None:
            return [gruppo] + risultato
        if telemetria is not None:
            telemetria.backtrack()
        if contatore_nodi is not None and contatore_nodi[0] > int(limite_nodi):
            return None

    if stati_falliti is not None and chiave_stato is not None:
        stati_falliti.add(chiave_stato)
        if telemetria is not None:
            telemetria.incrementa("memo_store")
    return None


def _backtrack_blocchi(
    disponibili: list[Any],
    disponibili_id: set[int],
    indice: Mapping[int, Sequence[tuple[list[Any], int]]],
    rimanenti_per_taglia: dict[int, int],
    schema: SchemaBlocchiSemantico,
    *,
    gruppi_scelti: tuple[Gruppo, ...] = (),
    fisso_atteso: bool = False,
    contatore_nodi: list[int] | None = None,
    limite_nodi: int | None = None,
    profondita: int = 0,
    telemetria: Any = None,
    stati_falliti: set[Any] | None = None,
    fcg_soglia_backtrack: int | None = None,
    fcg_massimo_attivazioni: int | None = None,
    fcg_stato: dict[str, Any] | None = None,
    cache_matching: dict[Any, bool] | None = None,
    memo_geometrica: bool = False,
 ) -> list[Gruppo] | None:
    if limite_nodi is None:
        limite_nodi = LIMITE_NODI_BACKTRACK
    if cache_matching is None:
        cache_matching = (
            fcg_stato.setdefault("matcher_cache", {})
            if fcg_stato is not None else {}
        )
    chiave_stato = None
    if stati_falliti is not None:
        chiave_stato = (
            frozenset(disponibili_id),
            tuple(sorted(rimanenti_per_taglia.items())),
            (_firma_geometrica_parziale(gruppi_scelti), bool(fisso_atteso))
            if memo_geometrica else _firma_gruppi_parziali(gruppi_scelti),
        )
        if chiave_stato in stati_falliti:
            if telemetria is not None:
                telemetria.potatura("memo_stato_fallito")
                telemetria.incrementa("memo_hit")
            return None

    if contatore_nodi is not None:
        contatore_nodi[0] += 1
        if telemetria is not None:
            telemetria.nodo(profondita)
        if contatore_nodi[0] > int(limite_nodi):
            if telemetria is not None:
                telemetria.potatura("tetto_nodi")
            return None

    posti_da_blocchi = sum(
        taglia * quanti for taglia, quanti in rimanenti_per_taglia.items()
    )
    if posti_da_blocchi != len(disponibili):
        if telemetria is not None:
            telemetria.potatura("forma_residua_incoerente")
        return None

    if not disponibili:
        if any(rimanenti_per_taglia.values()):
            if telemetria is not None:
                telemetria.potatura("blocchi_residui")
            return None
        esito_finale = verifica_fattibilita_matching(gruppi_scelti, schema)
        if telemetria is not None:
            telemetria.incrementa("matching_finale_chiamate")
            telemetria.incrementa(
                "matching_finale_visite_archi",
                int(esito_finale.diagnostica.visite_archi_fattibilita),
            )
        if not esito_finale.fattibile:
            if telemetria is not None:
                telemetria.potatura("matching_geometrico_finale")
                telemetria.incrementa("matching_finale_fallimenti")
                for errore in esito_finale.errori_duri:
                    telemetria.incrementa(f"matching_fallimento:{errore}")
            return None
        return []

    ancora = disponibili[0]
    alternative = indice.get(id(ancora), ())

    for membri_ordinati, _punti in alternative:
        taglia = len(membri_ordinati)
        if rimanenti_per_taglia.get(taglia, 0) <= 0:
            if telemetria is not None:
                telemetria.potatura("taglia_esaurita")
            continue
        if not all(id(membro) in disponibili_id for membro in membri_ordinati):
            if telemetria is not None:
                telemetria.potatura("membri_non_disponibili")
            continue

        gruppo = Gruppo(_tipo_per_taglia(taglia), membri_ordinati)
        nuovi_gruppi = gruppi_scelti + (gruppo,)
        if not _matching_parziale_cached(
            nuovi_gruppi,
            schema,
            fisso_atteso=fisso_atteso,
            telemetria=telemetria,
            cache=cache_matching,
        ):
            if telemetria is not None:
                telemetria.potatura("matching_geometrico_parziale")
            continue

        if telemetria is not None:
            telemetria.decisione(
                f"gruppo_{taglia}",
                tuple(nome_completo(membro) for membro in membri_ordinati),
                profondita,
            )

        usati = {id(membro) for membro in membri_ordinati}
        nuovi_disponibili = [s for s in disponibili if id(s) not in usati]
        nuovi_disponibili_id = disponibili_id - usati
        nuovi_rimanenti = dict(rimanenti_per_taglia)
        nuovi_rimanenti[taglia] -= 1

        if (
            fcg_soglia_backtrack is not None
            and fcg_stato is not None
            and int(fcg_stato.get("backtrack", 0)) >= int(fcg_soglia_backtrack)
            and (
                fcg_massimo_attivazioni is None
                or int(fcg_stato.get("attivazioni", 0)) < int(fcg_massimo_attivazioni)
            )
        ):
            fcg_stato["attivazioni"] = int(fcg_stato.get("attivazioni", 0)) + 1
            if telemetria is not None:
                telemetria.incrementa("fcg_attivazioni")
            if not _forward_check_geometrico_blocchi(
                nuovi_disponibili,
                nuovi_disponibili_id,
                indice,
                nuovi_rimanenti,
                schema,
                gruppi_scelti=nuovi_gruppi,
                fisso_atteso=fisso_atteso,
                telemetria=telemetria,
                cache_matching=fcg_stato.get("matcher_cache"),
            ):
                if telemetria is not None:
                    telemetria.potatura("forward_check_geometrico")
                    telemetria.incrementa("prune_fcg")
                continue

        risultato = _backtrack_blocchi(
            nuovi_disponibili,
            nuovi_disponibili_id,
            indice,
            nuovi_rimanenti,
            schema,
            gruppi_scelti=nuovi_gruppi,
            fisso_atteso=fisso_atteso,
            contatore_nodi=contatore_nodi,
            limite_nodi=limite_nodi,
            profondita=profondita + 1,
            telemetria=telemetria,
            stati_falliti=stati_falliti,
            fcg_soglia_backtrack=fcg_soglia_backtrack,
            fcg_massimo_attivazioni=fcg_massimo_attivazioni,
            fcg_stato=fcg_stato,
            cache_matching=cache_matching,
            memo_geometrica=memo_geometrica,
        )
        if risultato is not None:
            return [gruppo] + risultato
        if fcg_stato is not None:
            fcg_stato["backtrack"] = int(fcg_stato.get("backtrack", 0)) + 1
        if telemetria is not None:
            telemetria.backtrack()
        # Il contatore è monotono: dopo il tetto nessun ramo ulteriore può
        # riuscire. Non proseguire con matching e tentativi già condannati.
        if contatore_nodi is not None and contatore_nodi[0] > int(limite_nodi):
            return None

    if (
        stati_falliti is not None
        and chiave_stato is not None
        and (contatore_nodi is None or contatore_nodi[0] <= int(limite_nodi))
    ):
        stati_falliti.add(chiave_stato)
        if telemetria is not None:
            telemetria.incrementa("memo_store")
    return None


def _valida_studenti_e_schema(
    studenti: Sequence[Any],
    schema: SchemaBlocchiSemantico,
) -> None:
    schema.valida_numero_studenti(len(studenti))
    fissi = [
        studente
        for studente in studenti
        if getattr(studente, "nota_posizione", "NORMALE") == "FISSO"
    ]
    if len(fissi) > 1:
        raise ValueError("La modalità mista ammette al massimo uno studente FISSO.")
    if fissi and schema.posto_ancora_fisso is None:
        raise ValueError(
            "La classe contiene FISSO ma lo schema non dichiara un posto-ancora."
        )


def partiziona_in_blocchi(
    motore_vincoli: MotoreVincoliConfigurato,
    studenti: Sequence[Any],
    schema: SchemaBlocchiSemantico,
    *,
    frequenze_storico: Mapping[Any, int] | None = None,
    tentativo_iniziale: int = 1,
    solo_tentativo: int | None = None,
    seed: int | str | None = None,
    diagnostica: Any = None,
    ricerca_ibrida: bool = False,
    soglia_rescue_mrvg: int = 1024,
    fcg_soglia_backtrack: int = 128,
    fcg_massimo_attivazioni: int = 128,
    diversifica_rescue_mrvg: bool = False,
    memo_geometrica: bool = False,
    backend_ricerca: str = "nativo",
    diversifica_q2: bool = False,
) -> list[Gruppo] | None:
    """Partiziona gli studenti secondo la forma esatta dello schema a blocchi."""
    _valida_studenti_e_schema(studenti, schema)
    if backend_ricerca not in ("nativo", "q17"):
        raise ValueError("Backend di ricerca Blocchi sconosciuto.")
    if backend_ricerca == "q17":
        if ricerca_ibrida or diagnostica is not None or getattr(motore_vincoli, "diagnostica", None) is not None:
            raise ValueError("Q17 richiede ricerca deterministica senza diagnostica per nodo.")
        # La memo geometrica e' parte integrante del protocollo Q17.
        memo_geometrica = True
        from moduli.calcolo import ricerca_q17_contesto as accelerato
        backtrack_t123 = accelerato.backtrack_q8b
        backtrack_t4 = accelerato.backtrack_q17
    else:
        backtrack_t123 = _backtrack_blocchi
        backtrack_t4 = _backtrack_blocchi
    diagnostica = diagnostica or getattr(motore_vincoli, "diagnostica", None)
    if diagnostica is not None:
        motore_vincoli.diagnostica = diagnostica
    if int(soglia_rescue_mrvg) < 1:
        raise ValueError("soglia_rescue_mrvg deve essere >= 1.")
    if int(fcg_soglia_backtrack) < 0:
        raise ValueError("fcg_soglia_backtrack deve essere >= 0.")
    if int(fcg_massimo_attivazioni) < 1:
        raise ValueError("fcg_massimo_attivazioni deve essere >= 1.")

    studenti = sorted(studenti, key=chiave_ordinamento_studente)
    indice_fisso = next(
        (
            i for i, studente in enumerate(studenti)
            if getattr(studente, "nota_posizione", "NORMALE") == "FISSO"
        ),
        None,
    )
    if indice_fisso is not None and indice_fisso != 0:
        studenti.insert(0, studenti.pop(indice_fisso))

    frequenze = _normalizza_frequenze(frequenze_storico)
    seed_candidato = risolvi_seed_principale(seed)
    motore_vincoli.seed_candidato = seed_candidato
    motore_vincoli.ripartenza_vincente = None
    motore_vincoli.seed_ripartenza_vincente = None
    motore_vincoli.ripartenze_eseguite = 0
    motore_vincoli.rescue_mrvg_usato = False
    motore_vincoli.rescue_mrvg_vincente = False
    motore_vincoli.nodi_prima_rescue = None
    motore_vincoli.nodi_rescue_mrvg = None
    motore_vincoli.rescue_mrvg_diversificato = bool(diversifica_rescue_mrvg)

    if solo_tentativo is not None:
        if solo_tentativo not in (1, 2, 3, 4):
            raise ValueError("solo_tentativo deve essere compreso fra 1 e 4.")
        tentativi = [solo_tentativo]
    else:
        tentativi = list(range(max(1, int(tentativo_iniziale)), 5))

    forma = schema.conteggio_per_capienza()
    taglie_presenti = [taglia for taglia, quanti in forma.items() if quanti > 0]
    salta_t2_t3 = False

    if diagnostica is not None:
        diagnostica.evento(
            "schema_blocchi",
            modalita="mista",
            seed_candidato=seed_candidato,
            forma_per_profondita=schema.forma_per_profondita(),
            conteggio_per_capienza=forma,
            zona_prima_per_capienza=schema.conteggio_prima_per_capienza(),
            zona_ultima_per_capienza=schema.conteggio_ultima_per_capienza(),
            ancora_fisso=(
                {
                    "blocco": schema.blocco_ancora_fisso.id,
                    "posto": schema.posto_ancora_fisso.id,
                    "indice": schema.posto_ancora_fisso.indice,
                }
                if schema.blocco_ancora_fisso is not None
                else None
            ),
            identita_semantica=schema.identita_semantica(),
        )

    for tentativo in tentativi:
        if salta_t2_t3 and tentativo in (2, 3):
            if diagnostica is not None:
                diagnostica.evento(
                    "tentativo_saltato",
                    modalita="mista",
                    tentativo=tentativo,
                    causa="T1_esaurito_senza_tetto",
                    seed_candidato=seed_candidato,
                )
            continue

        motore_vincoli.configura_per_tentativo(tentativo)
        inizio_tentativo = perf_counter_ns()
        if diagnostica is not None:
            diagnostica.evento(
                "tentativo_inizio",
                modalita="mista",
                tentativo=tentativo,
                seed_candidato=seed_candidato,
            )

        contatori_preparazione = Counter() if diagnostica is not None else None
        inizio_preparazione = perf_counter_ns()
        punteggio, bloccata = _calcola_punteggi_coppie(
            motore_vincoli,
            studenti,
            frequenze,
            storico_blocca=(tentativo <= 3),
            contatori=contatori_preparazione,
        )
        indice = _genera_gruppi_ammissibili(
            studenti,
            taglie_presenti,
            punteggio,
            bloccata,
            indice_fisso_ancora=(
                schema.posto_ancora_fisso.indice
                if schema.posto_ancora_fisso is not None
                else None
            ),
            contatori=contatori_preparazione,
        )
        if diversifica_q2 and tentativo < 4:
            # Q2 congelato: stesso RNG e stessa scansione ordinata di gruppi.
            # Non modifica punteggi, gruppi, orientamenti o tentativo T4.
            from moduli.calcolo.diversificazione_q2 import diversifica_pari_punteggio
            indice = diversifica_pari_punteggio(indice, seed_candidato)

        if diagnostica is not None:
            diagnostica.evento(
                "preparazione_tentativo",
                modalita="mista",
                tentativo=tentativo,
                durata_ns=perf_counter_ns() - inizio_preparazione,
                contatori=dict(contatori_preparazione or {}),
                alternative_per_ancora={
                    nome_completo(studente): {
                        str(taglia): sum(1 for membri, _ in indice[id(studente)] if len(membri) == taglia)
                        for taglia in taglie_presenti
                    }
                    for studente in studenti
                },
            )

        if tentativo < 4:
            # Percorso legacy identico quando ricerca_ibrida=False.
            if not ricerca_ibrida:
                contatore_nodi = [0]
                telemetria = None
                if diagnostica is not None:
                    telemetria = diagnostica.nuova_ricerca(
                        firma_ordine=firma_indice_gruppi(indice, studenti),
                        modalita="mista",
                        tentativo=tentativo,
                        strategia_ricerca="deterministica",
                        seed_candidato=seed_candidato,
                        forma_per_profondita=schema.forma_per_profondita(),
                    )
                stati_falliti: set[Any] = set()
                soluzione = backtrack_t123(
                    list(studenti),
                    {id(s) for s in studenti},
                    indice,
                    dict(forma),
                    schema,
                    fisso_atteso=indice_fisso is not None,
                    contatore_nodi=contatore_nodi,
                    limite_nodi=LIMITE_NODI_BACKTRACK,
                    telemetria=telemetria,
                    stati_falliti=stati_falliti,
                    memo_geometrica=bool(memo_geometrica),
                )
                ha_tetto = contatore_nodi[0] > LIMITE_NODI_BACKTRACK
                motore_vincoli.tetto_nodi_scattato = bool(ha_tetto)
                if telemetria is not None:
                    telemetria.finalizza(
                        successo=soluzione is not None,
                        soluzione=_rappresenta_partizione(soluzione),
                        punteggio=(
                            _punteggio_partizione(soluzione, punteggio)
                            if soluzione is not None else None
                        ),
                        tetto_nodi=ha_tetto,
                        dati={
                            "nodi_contatore_storico": contatore_nodi[0],
                            "stati_falliti": len(stati_falliti),
                        },
                    )
            else:
                # Fase 1: stesso ordine produttivo, ma budget breve. FCG è safe
                # e limitato: se trova la soluzione, l'ordine dei rami validi
                # resta quello legacy.
                limite_prima_fase = min(
                    int(soglia_rescue_mrvg),
                    int(LIMITE_NODI_BACKTRACK),
                )
                contatore_nodi = [0]
                telemetria = None
                if diagnostica is not None:
                    telemetria = diagnostica.nuova_ricerca(
                        firma_ordine=firma_indice_gruppi(indice, studenti),
                        modalita="mista",
                        tentativo=tentativo,
                        strategia_ricerca="deterministica_fcg_bounded",
                        seed_candidato=seed_candidato,
                        forma_per_profondita=schema.forma_per_profondita(),
                    )
                stati_falliti: set[Any] = set()
                fcg_stato = {
                    "backtrack": 0,
                    "attivazioni": 0,
                    "matcher_cache": {},
                }
                soluzione = backtrack_t123(
                    list(studenti),
                    {id(s) for s in studenti},
                    indice,
                    dict(forma),
                    schema,
                    fisso_atteso=indice_fisso is not None,
                    contatore_nodi=contatore_nodi,
                    limite_nodi=limite_prima_fase,
                    telemetria=telemetria,
                    stati_falliti=stati_falliti,
                    fcg_soglia_backtrack=int(fcg_soglia_backtrack),
                    fcg_massimo_attivazioni=int(fcg_massimo_attivazioni),
                    fcg_stato=fcg_stato,
                    memo_geometrica=bool(memo_geometrica),
                )
                soft_tetto = contatore_nodi[0] > limite_prima_fase
                motore_vincoli.nodi_prima_rescue = int(contatore_nodi[0])
                if telemetria is not None:
                    telemetria.finalizza(
                        successo=soluzione is not None,
                        soluzione=_rappresenta_partizione(soluzione),
                        punteggio=(
                            _punteggio_partizione(soluzione, punteggio)
                            if soluzione is not None else None
                        ),
                        tetto_nodi=soft_tetto,
                        dati={
                            "soft_tetto_rescue": soft_tetto,
                            "nodi_contatore_storico": contatore_nodi[0],
                            "stati_falliti": len(stati_falliti),
                            "fcg_attivazioni": int(fcg_stato.get("attivazioni", 0)),
                        },
                    )

                ha_tetto = False
                if soluzione is None and soft_tetto:
                    motore_vincoli.rescue_mrvg_usato = True
                    contatore_rescue = [0]
                    telemetria_rescue = None
                    if diagnostica is not None:
                        telemetria_rescue = diagnostica.nuova_ricerca(
                            firma_ordine=firma_indice_gruppi(indice, studenti),
                            modalita="mista",
                            tentativo=tentativo,
                            strategia_ricerca=(
                                "MRVG_rescue_diversificato"
                                if diversifica_rescue_mrvg else "MRVG_rescue"
                            ),
                            seed_candidato=seed_candidato,
                            forma_per_profondita=schema.forma_per_profondita(),
                        )
                    stati_rescue: set[Any] = set()
                    soluzione = _backtrack_blocchi_mrvg(
                        list(studenti),
                        {id(s) for s in studenti},
                        indice,
                        dict(forma),
                        schema,
                        fisso_atteso=indice_fisso is not None,
                        contatore_nodi=contatore_rescue,
                        limite_nodi=LIMITE_NODI_BACKTRACK,
                        telemetria=telemetria_rescue,
                        stati_falliti=stati_rescue,
                        ordine_stabile={id(s): i for i, s in enumerate(studenti)},
                        cache_matching={},
                        tie_seed=(
                            deriva_seed(seed_candidato, "mrvg_rescue", "tie")
                            if diversifica_rescue_mrvg else None
                        ),
                    )
                    ha_tetto = contatore_rescue[0] > LIMITE_NODI_BACKTRACK
                    motore_vincoli.nodi_rescue_mrvg = int(contatore_rescue[0])
                    motore_vincoli.rescue_mrvg_vincente = soluzione is not None
                    if telemetria_rescue is not None:
                        telemetria_rescue.finalizza(
                            successo=soluzione is not None,
                            soluzione=_rappresenta_partizione(soluzione),
                            punteggio=(
                                _punteggio_partizione(soluzione, punteggio)
                                if soluzione is not None else None
                            ),
                            tetto_nodi=ha_tetto,
                            dati={
                                "nodi_contatore_storico": contatore_rescue[0],
                                "stati_falliti": len(stati_rescue),
                            },
                        )
                elif soluzione is None:
                    # Prima fase esaurita senza soft cap: prova completa, quindi
                    # nessuna ragione di cambiare ordine.
                    ha_tetto = False

                motore_vincoli.tetto_nodi_scattato = bool(ha_tetto)

            if diagnostica is not None:
                diagnostica.evento(
                    "tentativo_fine",
                    modalita="mista",
                    tentativo=tentativo,
                    successo=soluzione is not None,
                    durata_ns=perf_counter_ns() - inizio_tentativo,
                    tetto_nodi=ha_tetto,
                    rescue_mrvg_usato=bool(getattr(motore_vincoli, "rescue_mrvg_usato", False)),
                    rescue_mrvg_vincente=bool(getattr(motore_vincoli, "rescue_mrvg_vincente", False)),
                )
            if soluzione is not None:
                return soluzione
            if tentativo == 1 and not ha_tetto:
                salta_t2_t3 = True
            continue

        migliore_soluzione = None
        migliore_punteggio = None
        tentativo_ha_tetto = False
        strategia = strategia_corrente()
        chiavi_strette = (
            precalcola_chiavi_strette_terzetti(indice, frequenze)
            if strategia in ("B2", "B3", "B4") else None
        )

        for indice_ripartenza in range(NUM_RIPARTENZE_TENTATIVO_4):
            numero_ripartenza = indice_ripartenza + 1
            seed_ripartenza = deriva_seed(
                seed_candidato,
                "mista",
                "ripartenza",
                numero_ripartenza,
            )
            rng = crea_generatore(seed_ripartenza)
            motore_vincoli.ripartenze_eseguite = numero_ripartenza
            indice_diversificato = diversifica_indice_terzetti(
                indice,
                rng=rng,
                ripartenza=numero_ripartenza,
                frequenze=frequenze,
                strategia=strategia,
                contesto=("mista", seed_candidato, schema.forma_per_profondita()),
                chiavi_strette=chiavi_strette,
            )
            contatore_nodi = [0]
            telemetria = None
            if diagnostica is not None:
                telemetria = diagnostica.nuova_ricerca(
                    firma_ordine=firma_indice_gruppi(indice_diversificato, studenti),
                    modalita="mista",
                    tentativo=4,
                    strategia_ricerca=strategia,
                    seed_candidato=seed_candidato,
                    ripartenza=numero_ripartenza,
                    seed_ripartenza=seed_ripartenza,
                    forma_per_profondita=schema.forma_per_profondita(),
                )
            stati_falliti: set[Any] = set()
            soluzione = backtrack_t4(
                list(studenti),
                {id(s) for s in studenti},
                indice_diversificato,
                dict(forma),
                schema,
                fisso_atteso=indice_fisso is not None,
                contatore_nodi=contatore_nodi,
                telemetria=telemetria,
                stati_falliti=stati_falliti,
                memo_geometrica=bool(memo_geometrica),
            )
            ha_tetto = contatore_nodi[0] > LIMITE_NODI_BACKTRACK
            tentativo_ha_tetto = tentativo_ha_tetto or ha_tetto
            punti = (
                _punteggio_partizione(soluzione, punteggio)
                if soluzione is not None else None
            )
            if telemetria is not None:
                telemetria.finalizza(
                    successo=soluzione is not None,
                    soluzione=_rappresenta_partizione(soluzione),
                    punteggio=punti,
                    tetto_nodi=ha_tetto,
                    dati={
                        "nodi_contatore_storico": contatore_nodi[0],
                        "stati_falliti": len(stati_falliti),
                    },
                )
            if soluzione is None:
                continue
            if migliore_punteggio is None or int(punti) > migliore_punteggio:
                migliore_punteggio = int(punti)
                migliore_soluzione = soluzione
                motore_vincoli.ripartenza_vincente = numero_ripartenza
                motore_vincoli.seed_ripartenza_vincente = seed_ripartenza

        motore_vincoli.tetto_nodi_scattato = bool(tentativo_ha_tetto)
        if diagnostica is not None:
            diagnostica.evento(
                "tentativo_fine",
                modalita="mista",
                tentativo=4,
                successo=migliore_soluzione is not None,
                durata_ns=perf_counter_ns() - inizio_tentativo,
                tetto_nodi=tentativo_ha_tetto,
                ripartenza_vincente=motore_vincoli.ripartenza_vincente,
                punteggio_vincente=migliore_punteggio,
            )
        if migliore_soluzione is not None:
            return migliore_soluzione

    return None


def colloca_gruppi_su_schema(
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
) -> tuple[CollocazioneGruppoBlocco, ...]:
    """Colloca i gruppi con il matcher semantico del Gate B.

    Tutti i vincoli duri vengono ricontrollati. Fra le collocazioni valide il
    matcher massimizza esclusivamente il soft ULTIMA e applica il tie-break
    canonico definito nel Gate B.
    """
    esito = abbina_gruppi_a_blocchi(gruppi, schema)
    if not esito.successo:
        dettagli = ", ".join(esito.errori_duri) or "matching impossibile"
        raise ValueError(f"Partizione non collocabile nello schema semantico: {dettagli}.")
    return tuple(sorted(
        esito.collocazioni,
        key=lambda c: (c.blocco.profondita, c.blocco.colonna, c.blocco.id),
    ))


def _metadati_candidato(
    motore: MotoreVincoliConfigurato,
    *,
    seed_principale: int,
    seed_candidato: int,
    indice_candidato: int,
    contesto: Mapping[str, Any],
    successo: bool,
) -> dict[str, Any]:
    return {
        "seed_principale": seed_principale,
        "modalita": "mista",
        "contesto": {**dict(contesto), "candidato": indice_candidato},
        "seed_candidato": seed_candidato,
        "tentativo": getattr(motore, "tentativo_corrente", None),
        "ripartenza": getattr(motore, "ripartenza_vincente", None),
        "seed_ripartenza": getattr(motore, "seed_ripartenza_vincente", None),
        "ripartenze_eseguite": getattr(motore, "ripartenze_eseguite", 0),
        "successo": bool(successo),
        "tetto_nodi_scattato": bool(getattr(motore, "tetto_nodi_scattato", False)),
        "rescue_mrvg_usato": bool(getattr(motore, "rescue_mrvg_usato", False)),
        "rescue_mrvg_vincente": bool(getattr(motore, "rescue_mrvg_vincente", False)),
        "nodi_prima_rescue": getattr(motore, "nodi_prima_rescue", None),
        "nodi_rescue_mrvg": getattr(motore, "nodi_rescue_mrvg", None),
        "rescue_mrvg_diversificato": bool(
            getattr(motore, "rescue_mrvg_diversificato", False)
        ),
    }


def calcola_miglior_mese_blocchi(
    studenti: Sequence[Any],
    schema: SchemaBlocchiSemantico,
    genere_misto: bool,
    *,
    frequenze_storico: Mapping[Any, int] | None = None,
    num_candidati: int = NUM_CANDIDATI_BLOCCHI,
    seed_base: int | str | None = None,
    contesto_casuale: Mapping[str, Any] | None = None,
    restituisci_metadati: bool = False,
    diagnostica: Any = None,
    solo_t4: bool = False,
    ricerca_ibrida: bool = False,
    soglia_rescue_mrvg: int = 1024,
    fcg_soglia_backtrack: int = 128,
    fcg_massimo_attivazioni: int = 128,
    diversifica_rescue_mrvg: bool = False,
    memo_geometrica: bool = False,
    backend_ricerca: str = "nativo",
    diversifica_q2: bool = False,
) -> Any:
    """Genera e confronta più candidati per lo stesso schema di blocchi.

    ``solo_t4`` è un ingresso sperimentale usato dal runner fork Gate E.2:
    consente di riusare una cascata T1–T3 già calcolata sullo stesso snapshot
    storico e di diversificare soltanto i candidati T4. Il default resta False
    e quindi non altera il percorso ordinario del motore.
    """
    _valida_studenti_e_schema(studenti, schema)
    frequenze = _normalizza_frequenze(frequenze_storico)
    adiacenze_gia_usate = {
        tuple(sorted(chiave)) for chiave, volte in frequenze.items() if volte > 0
    }
    seed_principale = risolvi_seed_principale(seed_base)
    contesto = dict(contesto_casuale or {})

    migliore = None
    migliore_chiave = None
    migliore_matching = None
    migliori_metadati = None
    ultimi_metadati = None

    for indice_candidato in range(1, max(1, int(num_candidati)) + 1):
        motore = MotoreVincoliConfigurato(diagnostica=diagnostica)
        motore.imposta_genere_misto_obbligatorio(bool(genere_misto))
        seed_candidato = deriva_seed(
            seed_principale,
            "modalita", "mista",
            "schema", schema.identita_semantica(),
            "contesto", contesto,
            "candidato", indice_candidato,
        )
        inizio = perf_counter_ns()
        # T1–T3 sono completamente deterministici e non dipendono dal seed
        # candidato. Se siamo arrivati al candidato 2+, il primo candidato ha
        # già dimostrato che nessuno di T1–T3 ha prodotto una soluzione;
        # ripeterli moltiplicherebbe solo il costo. I candidati aggiuntivi
        # servono esclusivamente a diversificare T4.
        candidato_solo_t4 = bool(solo_t4) or indice_candidato > 1

        if diagnostica is not None:
            diagnostica.evento(
                "candidato_inizio",
                modalita="mista",
                candidato=indice_candidato,
                seed_principale=seed_principale,
                seed_candidato=seed_candidato,
                contesto=contesto,
                solo_t4=candidato_solo_t4,
            )
            with diagnostica.attiva():
                gruppi = partiziona_in_blocchi(
                    motore,
                    studenti,
                    schema,
                    frequenze_storico=frequenze,
                    solo_tentativo=4 if candidato_solo_t4 else None,
                    seed=seed_candidato,
                    diagnostica=diagnostica,
                    ricerca_ibrida=bool(ricerca_ibrida),
                    soglia_rescue_mrvg=int(soglia_rescue_mrvg),
                    fcg_soglia_backtrack=int(fcg_soglia_backtrack),
                    fcg_massimo_attivazioni=int(fcg_massimo_attivazioni),
                    diversifica_rescue_mrvg=bool(diversifica_rescue_mrvg),
                    memo_geometrica=bool(memo_geometrica),
                    backend_ricerca=backend_ricerca,
                    diversifica_q2=diversifica_q2,
                )
            diagnostica.evento(
                "candidato_fine",
                modalita="mista",
                candidato=indice_candidato,
                seed_candidato=seed_candidato,
                successo=gruppi is not None,
                durata_ns=perf_counter_ns() - inizio,
                tentativo=getattr(motore, "tentativo_corrente", None),
            )
        else:
            gruppi = partiziona_in_blocchi(
                motore,
                studenti,
                schema,
                frequenze_storico=frequenze,
                solo_tentativo=4 if candidato_solo_t4 else None,
                seed=seed_candidato,
                ricerca_ibrida=bool(ricerca_ibrida),
                soglia_rescue_mrvg=int(soglia_rescue_mrvg),
                fcg_soglia_backtrack=int(fcg_soglia_backtrack),
                fcg_massimo_attivazioni=int(fcg_massimo_attivazioni),
                diversifica_rescue_mrvg=bool(diversifica_rescue_mrvg),
                memo_geometrica=bool(memo_geometrica),
                backend_ricerca=backend_ricerca,
                diversifica_q2=diversifica_q2,
            )

        metadati = _metadati_candidato(
            motore,
            seed_principale=seed_principale,
            seed_candidato=seed_candidato,
            indice_candidato=indice_candidato,
            contesto=contesto,
            successo=gruppi is not None,
        )
        ultimi_metadati = metadati
        if gruppi is None:
            continue

        esito_matching = abbina_gruppi_a_blocchi(gruppi, schema)
        if not esito_matching.successo:
            # Difesa forte: il backtracking Gate C dovrebbe avere già escluso
            # ogni partizione geometricamente impossibile.
            if diagnostica is not None:
                diagnostica.evento(
                    "incoerenza_matching_finale",
                    modalita="mista",
                    candidato=indice_candidato,
                    errori=list(esito_matching.errori_duri),
                    matcher=esito_matching.diagnostica.come_dict(),
                )
            continue
        collocazioni = tuple(sorted(
            esito_matching.collocazioni,
            key=lambda c: (c.blocco.profondita, c.blocco.colonna, c.blocco.id),
        ))
        metadati = dict(metadati)
        metadati["matching"] = esito_matching.come_dict()
        chiave = chiave_pulizia_terzetti(gruppi, adiacenze_gia_usate)
        if diagnostica is not None:
            frequenze_riuso = []
            for a, b in adiacenze_partizione(gruppi):
                utilizzi = frequenze.get(_chiave_nomi(a, b), 0)
                if utilizzi > 0:
                    frequenze_riuso.append(utilizzi)
            diagnostica.evento(
                "qualita_candidato",
                modalita="mista",
                candidato=indice_candidato,
                seed_candidato=seed_candidato,
                tentativo=getattr(motore, "tentativo_corrente", None),
                chiave=chiave,
                incompatibilita_per_livello=conta_incompatibilita_per_livello_terzetti(gruppi),
                affinita=conta_affinita_soddisfatte_terzetti(gruppi),
                frequenze_riuso=frequenze_riuso,
                collocazioni=[
                    {
                        "blocco": c.blocco.id,
                        "profondita": c.blocco.profondita,
                        "zona_prima": c.blocco.zona_prima,
                        "zona_ultima": c.blocco.zona_ultima,
                        "posti": [posto.id for posto in c.blocco.posti],
                        "gruppo": [nome_completo(m) for m in c.gruppo.membri],
                    }
                    for c in collocazioni
                ],
                matching=esito_matching.diagnostica.come_dict(),
                ultima_totali=esito_matching.ultima_totali,
                ultima_soddisfatti=esito_matching.ultima_soddisfatti,
                ultima_percentuale=esito_matching.ultima_percentuale,
            )
        if migliore_chiave is None or chiave < migliore_chiave:
            migliore = gruppi
            migliore_chiave = chiave
            migliore_matching = esito_matching
            migliori_metadati = metadati

        if getattr(motore, "tentativo_corrente", 4) <= 3:
            break

    metadati_finali = migliori_metadati or ultimi_metadati or {
        "seed_principale": seed_principale,
        "modalita": "mista",
        "contesto": contesto,
        "successo": False,
    }
    metadati_finali = dict(metadati_finali)
    metadati_finali["chiave_vincente"] = migliore_chiave
    metadati_finali["schema"] = schema.forma_per_profondita()
    metadati_finali["schema_semantico"] = schema.identita_semantica()
    if migliore_matching is not None:
        metadati_finali["ultima_totali"] = migliore_matching.ultima_totali
        metadati_finali["ultima_soddisfatti"] = migliore_matching.ultima_soddisfatti
        metadati_finali["ultima_percentuale"] = migliore_matching.ultima_percentuale

    messaggio_motore(
        f"🎲 Mista: seed principale={seed_principale}, "
        f"tentativo={metadati_finali.get('tentativo')}, "
        f"ripartenza={metadati_finali.get('ripartenza')}"
    )
    if diagnostica is not None:
        diagnostica.evento(
            "best_of_n_fine",
            modalita="mista",
            successo=migliore is not None,
            chiave_vincente=migliore_chiave,
            seed_candidato=metadati_finali.get("seed_candidato"),
            tentativo=metadati_finali.get("tentativo"),
            ripartenza=metadati_finali.get("ripartenza"),
            ultima_totali=metadati_finali.get("ultima_totali"),
            ultima_soddisfatti=metadati_finali.get("ultima_soddisfatti"),
        )

    if restituisci_metadati:
        return migliore, metadati_finali
    return migliore


def aggiorna_frequenze_storico(
    frequenze: Mapping[Any, int] | None,
    gruppi: Sequence[Gruppo],
) -> dict[frozenset[str], int]:
    """Restituisce una nuova fotografia storica dopo una partizione."""
    risultato = _normalizza_frequenze(frequenze)
    for a, b in adiacenze_partizione(gruppi):
        chiave = _chiave_nomi(a, b)
        risultato[chiave] = risultato.get(chiave, 0) + 1
    return risultato
