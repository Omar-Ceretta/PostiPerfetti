# -*- coding: utf-8 -*-
"""Politica annuale protetta e riordino temporale di PostiPerfetti.

Il modulo non genera assegnazioni. Descrive i mesi già prodotti, confronta
stagioni complete con la politica S1/R12 e riordina i dieci mesi senza
modificare gruppi o posti.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from moduli.metrica_pulizia import (
    adiacenze_in_fila,
    adiacenze_partizione,
    coppia_ordinata,
    coppie_per_blacklist,
    estrai_gruppi,
    livello_affinita,
    livello_incompatibilita,
    nome_completo,
    peso_incompatibilita,
)

POLITICA_BASELINE = "C1"
POLITICA_PROTETTA = "S1_R12_GUARDIE"
RIORDINO_TEMPORALE = "R2_CINTURA_TEMPORALE"


def _adiacenza(studente_a, studente_b, *, tipo: str = "ordinaria") -> dict[str, Any]:
    nome_a = nome_completo(studente_a)
    nome_b = nome_completo(studente_b)
    if tipo == "fisso_vicino":
        chiave = (tipo, nome_b)
    else:
        chiave = (tipo,) + coppia_ordinata(nome_a, nome_b)
    return {
        "chiave": chiave,
        "studenti": (nome_a, nome_b),
        "incompatibilita": int(livello_incompatibilita(studente_a, studente_b)),
        "affinita": int(livello_affinita(studente_a, studente_b)),
    }


def descrivi_mese_coppie(assegnatore) -> dict[str, Any]:
    adiacenze = []
    for gruppo in estrai_gruppi(assegnatore):
        for studente_a, studente_b in adiacenze_in_fila(gruppo.membri):
            adiacenze.append(_adiacenza(studente_a, studente_b))

    fisso = getattr(assegnatore, "studente_fisso", None)
    gruppo_fisso = getattr(assegnatore, "gruppo_adiacente_fisso", None)
    vicino_fisso = getattr(assegnatore, "nome_adiacente_fisso", None)
    if fisso is not None and gruppo_fisso is not None and vicino_fisso:
        adiacenze.append(_adiacenza(fisso, gruppo_fisso[0], tipo="fisso_vicino"))

    return {
        "adiacenze": adiacenze,
        "blacklist": set(coppie_per_blacklist(assegnatore)),
        "vicino_fisso": vicino_fisso,
    }


def descrivi_mese_terzetti(mese: dict[str, Any]) -> dict[str, Any]:
    gruppi = mese["gruppi"]
    adiacenze = [
        _adiacenza(studente_a, studente_b)
        for studente_a, studente_b in adiacenze_partizione(gruppi)
    ]
    blacklist = {
        coppia_ordinata(nome_completo(a), nome_completo(b))
        for a, b in adiacenze_partizione(gruppi)
    }
    return {
        "adiacenze": adiacenze,
        "blacklist": blacklist,
        "vicino_fisso": None,
    }


def descrivi_stagione(mesi: list[Any], modalita: str) -> list[dict[str, Any]]:
    if modalita == "coppie":
        return [descrivi_mese_coppie(mese) for mese in mesi]
    if modalita == "terzetti":
        return [descrivi_mese_terzetti(mese) for mese in mesi]
    raise ValueError(f"Modalità annuale non riconosciuta: {modalita}")


def _metriche_vuote() -> dict[str, Any]:
    return {
        "riusi": 0,
        "incompatibilita_l1": 0,
        "incompatibilita_l2": 0,
        "incompatibilita_l3": 0,
        "affinita_l1": 0,
        "affinita_l2": 0,
        "affinita_l3": 0,
        "studenti_riusi": Counter(),
    }


def _stato_iniziale(blacklist_iniziale=None, vicini_fisso_iniziali=None):
    return {
        "visto": set(blacklist_iniziale or set()),
        "vicini_fisso": set(vicini_fisso_iniziali or set()),
        "metriche": _metriche_vuote(),
    }


def _copia_stato(stato):
    metriche = dict(stato["metriche"])
    metriche["studenti_riusi"] = Counter(stato["metriche"]["studenti_riusi"])
    return {
        "visto": set(stato["visto"]),
        "vicini_fisso": set(stato["vicini_fisso"]),
        "metriche": metriche,
    }


def _applica_mese(descrittore, stato, *, copia: bool):
    nuovo = _copia_stato(stato) if copia else stato
    visto_prima = stato["visto"]
    vicini_prima = stato["vicini_fisso"]
    metriche = nuovo["metriche"]

    for adiacenza in descrittore["adiacenze"]:
        chiave = adiacenza["chiave"]
        if chiave[0] == "fisso_vicino":
            ripetuta = chiave[1] in vicini_prima
        else:
            ripetuta = tuple(chiave[1:]) in visto_prima
        if ripetuta:
            metriche["riusi"] += 1
            for studente in adiacenza["studenti"]:
                metriche["studenti_riusi"][studente] += 1

        incompatibilita = adiacenza["incompatibilita"]
        affinita = adiacenza["affinita"]
        if incompatibilita:
            metriche[f"incompatibilita_l{incompatibilita}"] += 1
        if affinita:
            metriche[f"affinita_l{affinita}"] += 1

    nuovo["visto"].update(descrittore["blacklist"])
    if descrittore.get("vicino_fisso"):
        nuovo["vicini_fisso"].add(descrittore["vicino_fisso"])
    return nuovo


def _riassumi(metriche: dict[str, Any]) -> dict[str, int]:
    studenti_riusi = metriche["studenti_riusi"]
    affinita_totali = sum(metriche[f"affinita_l{livello}"] for livello in (1, 2, 3))
    return {
        "riusi": int(metriche["riusi"]),
        "incompatibilita_l1": int(metriche["incompatibilita_l1"]),
        "incompatibilita_l2": int(metriche["incompatibilita_l2"]),
        "incompatibilita_l3": int(metriche["incompatibilita_l3"]),
        "affinita_l1": int(metriche["affinita_l1"]),
        "affinita_l2": int(metriche["affinita_l2"]),
        "affinita_l3": int(metriche["affinita_l3"]),
        "affinita_totali": int(affinita_totali),
        "affinita_pesate": int(
            metriche["affinita_l1"]
            + 2 * metriche["affinita_l2"]
            + 3 * metriche["affinita_l3"]
        ),
        "massimo_individuale": int(max(studenti_riusi.values(), default=0)),
        "studenti_con_riuso": int(sum(v > 0 for v in studenti_riusi.values())),
    }


def metriche_ordine(
    descrittori: list[dict[str, Any]],
    ordine: Iterable[int] | None = None,
    *,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
) -> dict[str, int]:
    if ordine is None:
        ordine = range(1, len(descrittori) + 1)
    stato = _stato_iniziale(blacklist_iniziale, vicini_fisso_iniziali)
    for indice in ordine:
        stato = _applica_mese(descrittori[indice - 1], stato, copia=False)
    return _riassumi(stato["metriche"])


def chiave_r12(metriche: dict[str, int]):
    return (
        12 * metriche["riusi"]
        + 10 * metriche["incompatibilita_l2"]
        + 2 * metriche["incompatibilita_l1"]
        - metriche["affinita_pesate"],
        metriche["incompatibilita_l2"],
        metriche["massimo_individuale"],
        metriche["riusi"],
        metriche["incompatibilita_l1"],
        -metriche["affinita_pesate"],
    )


def _delta_metriche_mese(descrittore, stato) -> dict[str, int]:
    """Misura il solo contributo del mese rispetto allo stato precedente."""
    prima = _riassumi(stato["metriche"])
    dopo = _riassumi(
        _applica_mese(descrittore, stato, copia=True)["metriche"]
    )
    chiavi_additive = (
        "riusi",
        "incompatibilita_l1",
        "incompatibilita_l2",
        "incompatibilita_l3",
        "affinita_l1",
        "affinita_l2",
        "affinita_l3",
        "affinita_totali",
        "affinita_pesate",
    )
    return {chiave: int(dopo[chiave] - prima[chiave]) for chiave in chiavi_additive}


def _chiave_ordine_mese(descrittore, stato, politica: str):
    """Ordina lo sporco prima dei premi sociali.

    La metrica R12 serve a confrontare stagioni complete; non deve permettere
    alle affinità di compensare un'incompatibilità nella cronologia dell'anno.
    Perciò ripetizioni e incompatibilità sono prefissi rigidi, mentre le
    affinità intervengono soltanto come spareggio fra mesi ugualmente puliti.
    """
    delta = _delta_metriche_mese(descrittore, stato)
    incomp_pesate = peso_incompatibilita({
        1: delta["incompatibilita_l1"],
        2: delta["incompatibilita_l2"],
        3: delta["incompatibilita_l3"],
    })
    affinita = (
        delta["affinita_totali"]
        if politica == POLITICA_BASELINE
        else delta["affinita_pesate"]
    )
    return (delta["riusi"], incomp_pesate, -affinita)


def riordina_greedy(
    descrittori: list[dict[str, Any]],
    *,
    politica: str,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
):
    """Costruisce la cronologia mettendo in coda lo sporco inevitabile.

    La politica modifica soltanto lo spareggio positivo sulle affinità.
    Ripetizioni e incompatibilità conservano sempre precedenza assoluta.
    """
    rimanenti = list(enumerate(descrittori))
    stato = _stato_iniziale(blacklist_iniziale, vicini_fisso_iniziali)
    ordine = []
    while rimanenti:
        candidati = []
        for posizione, (indice_originale, descrittore) in enumerate(rimanenti):
            chiave = _chiave_ordine_mese(descrittore, stato, politica)
            candidati.append((chiave, indice_originale, posizione))
        _chiave, indice_originale, posizione = min(candidati)
        _indice, descrittore = rimanenti.pop(posizione)
        ordine.append(indice_originale + 1)
        stato = _applica_mese(descrittore, stato, copia=False)
    return ordine, _riassumi(stato["metriche"])


def metriche_temporali(
    descrittori: list[dict[str, Any]],
    ordine: list[int],
    *,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
):
    visto = set(blacklist_iniziale or set())
    vicini = set(vicini_fisso_iniziali or set())
    ultimo: dict[tuple[Any, ...], int] = {}
    gap = []
    riusi_mensili = []
    primo_mese = 0

    for posizione, indice in enumerate(ordine, start=1):
        descrittore = descrittori[indice - 1]
        riusi_del_mese = 0
        chiavi_del_mese = []
        for adiacenza in descrittore["adiacenze"]:
            chiave = adiacenza["chiave"]
            if chiave[0] == "fisso_vicino":
                ripetuta = chiave[1] in vicini
            else:
                ripetuta = tuple(chiave[1:]) in visto
            if ripetuta:
                riusi_del_mese += 1
                if primo_mese == 0:
                    primo_mese = posizione
                if chiave in ultimo:
                    gap.append(posizione - ultimo[chiave])
            chiavi_del_mese.append(chiave)

        for chiave in chiavi_del_mese:
            ultimo[chiave] = posizione
        visto.update(descrittore["blacklist"])
        if descrittore.get("vicino_fisso"):
            vicini.add(descrittore["vicino_fisso"])
        riusi_mensili.append(riusi_del_mese)

    return {
        "primo_mese_riuso": int(primo_mese),
        "mesi_con_riuso": int(sum(v > 0 for v in riusi_mensili)),
        "massimo_riusi_mese": int(max(riusi_mensili, default=0)),
        "gap_1": int(sum(d == 1 for d in gap)),
        "gap_le_2": int(sum(d <= 2 for d in gap)),
        "gap_le_3": int(sum(d <= 3 for d in gap)),
        "gap_medio": (sum(gap) / len(gap)) if gap else None,
    }


def primo_riuso_non_anticipato(candidato, baseline):
    primo_base = int(baseline["primo_mese_riuso"])
    primo_candidato = int(candidato["primo_mese_riuso"])
    if primo_base == 0:
        return primo_candidato == 0
    if primo_candidato == 0:
        return True
    return primo_candidato >= primo_base


def ammissibile_s1(metriche, temporali, metriche_base, temporali_base):
    return all((
        metriche["incompatibilita_l3"] <= metriche_base["incompatibilita_l3"],
        metriche["incompatibilita_l2"] <= metriche_base["incompatibilita_l2"],
        metriche["incompatibilita_l1"] <= metriche_base["incompatibilita_l1"],
        metriche["massimo_individuale"] <= metriche_base["massimo_individuale"],
        metriche["affinita_pesate"] >= metriche_base["affinita_pesate"],
        metriche["affinita_l3"] >= metriche_base["affinita_l3"],
        primo_riuso_non_anticipato(temporali, temporali_base),
        temporali["gap_1"] <= temporali_base["gap_1"],
        temporali["gap_le_2"] <= temporali_base["gap_le_2"],
        temporali["gap_le_3"] <= temporali_base["gap_le_3"],
    ))


def analizza_candidata(
    mesi,
    *,
    indice_stagione: int,
    modalita: str,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
):
    descrittori = descrivi_stagione(mesi, modalita)
    ordine, metriche = riordina_greedy(
        descrittori,
        politica=POLITICA_PROTETTA,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    temporali = metriche_temporali(
        descrittori,
        ordine,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    return {
        "indice": int(indice_stagione),
        "ordine": ordine,
        "metriche": metriche,
        "temporali": temporali,
        "chiave_r12": chiave_r12(metriche),
    }


def analizza_baseline(
    mesi,
    *,
    indice_stagione: int,
    modalita: str,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
):
    descrittori = descrivi_stagione(mesi, modalita)
    ordine, metriche = riordina_greedy(
        descrittori,
        politica=POLITICA_BASELINE,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    temporali = metriche_temporali(
        descrittori,
        ordine,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    return {
        "indice": int(indice_stagione),
        "ordine": ordine,
        "metriche": metriche,
        "temporali": temporali,
        "chiave_r12": chiave_r12(metriche),
    }


def seleziona_s1(candidati, baseline):
    ammissibili = [
        c for c in candidati
        if ammissibile_s1(
            c["metriche"], c["temporali"], baseline["metriche"], baseline["temporali"]
        )
    ]
    scelte = [(c["chiave_r12"], c["indice"], c, POLITICA_PROTETTA) for c in ammissibili]
    scelte.append((baseline["chiave_r12"], baseline["indice"], baseline, POLITICA_BASELINE))
    _chiave, _indice, scelta, politica = min(scelte, key=lambda x: (x[0], x[1]))
    risultato = dict(scelta)
    risultato["politica"] = politica
    return risultato


def _obiettivo_temporale(temporali):
    primo = int(temporali["primo_mese_riuso"])
    primo_normalizzato = 999 if primo == 0 else primo
    gap_medio = temporali["gap_medio"]
    return (
        int(temporali["gap_1"]),
        int(temporali["gap_le_2"]),
        int(temporali["gap_le_3"]),
        int(temporali["massimo_riusi_mese"]),
        -primo_normalizzato,
        -(float(gap_medio) if gap_medio is not None else 999.0),
    )


def _peso_incompatibilita_descrittore(descrittore) -> int:
    per_livello = {1: 0, 2: 0, 3: 0}
    for adiacenza in descrittore["adiacenze"]:
        livello = int(adiacenza["incompatibilita"])
        if livello in per_livello:
            per_livello[livello] += 1
    return int(peso_incompatibilita(per_livello))


def _profilo_incompatibilita(descrittori, ordine):
    """Restituisce lo sporco sociale mese per mese, dall'inizio alla coda."""
    return tuple(
        _peso_incompatibilita_descrittore(descrittori[indice - 1])
        for indice in ordine
    )


def riordino_temporale_protetto(
    descrittori,
    ordine_iniziale,
    *,
    blacklist_iniziale=None,
    vicini_fisso_iniziali=None,
):
    """Distanzia i riusi senza contraddire l'ordinamento per pulizia.

    Senza riusi il passaggio è intenzionalmente nullo. Con riusi presenti,
    ogni scambio deve migliorare le metriche temporali e non può anticipare
    il profilo mensile delle incompatibilità.
    """
    ordine = list(ordine_iniziale)
    temporali_base = metriche_temporali(
        descrittori,
        ordine,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    temporali = dict(temporali_base)

    if temporali_base["mesi_con_riuso"] == 0:
        return ordine, temporali

    obiettivo = _obiettivo_temporale(temporali)
    profilo_incompatibilita = _profilo_incompatibilita(descrittori, ordine)

    while True:
        candidati = []
        for i in range(len(ordine) - 1):
            for j in range(i + 1, len(ordine)):
                nuovo = list(ordine)
                nuovo[i], nuovo[j] = nuovo[j], nuovo[i]
                profilo_nuovo = _profilo_incompatibilita(descrittori, nuovo)
                if profilo_nuovo > profilo_incompatibilita:
                    continue
                temporali_nuovi = metriche_temporali(
                    descrittori,
                    nuovo,
                    blacklist_iniziale=blacklist_iniziale,
                    vicini_fisso_iniziali=vicini_fisso_iniziali,
                )
                if not primo_riuso_non_anticipato(temporali_nuovi, temporali_base):
                    continue
                if temporali_nuovi["massimo_riusi_mese"] > temporali_base["massimo_riusi_mese"]:
                    continue
                obiettivo_nuovo = _obiettivo_temporale(temporali_nuovi)
                if obiettivo_nuovo < obiettivo:
                    candidati.append((
                        obiettivo_nuovo,
                        profilo_nuovo,
                        tuple(nuovo),
                        nuovo,
                        temporali_nuovi,
                    ))
        if not candidati:
            return ordine, temporali
        (
            obiettivo,
            profilo_incompatibilita,
            _firma,
            ordine,
            temporali,
        ) = min(candidati)
