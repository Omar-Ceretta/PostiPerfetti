# -*- coding: utf-8 -*-
"""Campagne RC su Annuale, processi, Storico cumulativo e fallback T4."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
import io
import json
from pathlib import Path
import time
from typing import Iterable

from .annuale_rc import (
    esegui_annuale_processo_rc,
    esegui_annuale_rc,
    telemetria_storico_saturo_rc,
    verifica_accumulo_storico_rc,
)
from .corpus import carica_classi_corpus_ufficiale
from .generatori import genera_classe_sintetica


@dataclass(frozen=True, slots=True)
class CasoFase4RC:
    id_caso: str
    modalita: str
    classe: str
    studenti: int
    fisso: bool
    seed: int
    stato: str
    durata_s: float
    dettaglio: dict


@dataclass(frozen=True, slots=True)
class RapportoFase4RC:
    campagna: str
    casi: int
    verdi: int
    anomalie: int
    durata_s: float
    dettaglio: tuple[CasoFase4RC, ...]

    @property
    def verde(self) -> bool:
        return self.anomalie == 0

    def come_dict(self) -> dict:
        return {
            "campagna": self.campagna,
            "casi": self.casi,
            "verdi": self.verdi,
            "anomalie": self.anomalie,
            "durata_s": self.durata_s,
            "verde": self.verde,
            "dettaglio": [asdict(caso) for caso in self.dettaglio],
        }


def _rapporto(nome: str, inizio: float, casi: list[CasoFase4RC]) -> RapportoFase4RC:
    anomalie = sum(caso.stato != "verde" for caso in casi)
    return RapportoFase4RC(
        campagna=nome,
        casi=len(casi),
        verdi=len(casi) - anomalie,
        anomalie=anomalie,
        durata_s=round(time.monotonic() - inizio, 6),
        dettaglio=tuple(casi),
    )


def campagna_annuale_corpus(
    protocollo: str | Path,
    archivio: str | Path,
    *,
    semi: Iterable[int] = (20260806,),
    num_mesi: int = 4,
    numero_stagioni: int = 1,
    produzione: bool = False,
) -> RapportoFase4RC:
    classi = carica_classi_corpus_ufficiale(protocollo, archivio)
    casi: list[CasoFase4RC] = []
    inizio = time.monotonic()
    indice = 0
    for seed_base in semi:
        for classe in classi:
            for modalita in ("coppie", "terzetti"):
                indice += 1
                seed = int(seed_base) + indice * 1009
                t0 = time.monotonic()
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    esito = esegui_annuale_rc(
                    classe,
                    modalita=modalita,
                    seed=seed,
                    num_mesi=num_mesi,
                    numero_stagioni=numero_stagioni,
                    num_candidati=None if produzione else 1,
                )
                stato = "verde" if esito.successo else "anomalia"
                casi.append(CasoFase4RC(
                    id_caso=f"annuale-{indice:05d}",
                    modalita=modalita,
                    classe=classe.nome,
                    studenti=classe.numero_studenti,
                    fisso=classe.studente_fisso is not None,
                    seed=seed,
                    stato=stato,
                    durata_s=round(time.monotonic() - t0, 6),
                    dettaglio={
                        "origine": classe.origine,
                        "punteggio": list(esito.info.get("punteggio", ())),
                        "politica": esito.info.get("politica_annuale"),
                        "stagione": esito.info.get("indice_stagione_migliore"),
                        "violazioni": list(esito.verifica.violazioni if esito.verifica else ()),
                    },
                ))
    return _rapporto("annuale_corpus", inizio, casi)


def campagna_differenziale_processi(
    protocollo: str | Path,
    archivio: str | Path,
    *,
    seed_base: int = 310000,
    num_mesi: int = 3,
    numero_stagioni: int = 2,
    indici: Iterable[int] | None = None,
) -> RapportoFase4RC:
    classi = carica_classi_corpus_ufficiale(protocollo, archivio)
    scelti = set(indici) if indici is not None else set(range(len(classi)))
    casi: list[CasoFase4RC] = []
    inizio = time.monotonic()
    indice = 0
    for indice_classe, classe in enumerate(classi):
        if indice_classe not in scelti:
            continue
        for modalita in ("coppie", "terzetti"):
            indice += 1
            seed = seed_base + indice * 101
            t0 = time.monotonic()
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                diretto = esegui_annuale_rc(
                classe, modalita=modalita, seed=seed,
                num_mesi=num_mesi, numero_stagioni=numero_stagioni,
                num_candidati=1,
            )
                processo = esegui_annuale_processo_rc(
                classe, modalita=modalita, seed=seed,
                num_mesi=num_mesi, numero_stagioni=numero_stagioni,
                num_candidati=1, timeout_s=30,
            )
            firme_uguali = bool(
                diretto.verifica and processo.verifica
                and diretto.verifica.firme_mesi == processo.verifica.firme_mesi
            )
            punteggio_uguale = bool(
                diretto.verifica and processo.verifica
                and diretto.verifica.punteggio_indipendente
                == processo.verifica.punteggio_indipendente
            )
            metadati_uguali = (
                diretto.info.get("indice_stagione_migliore")
                == processo.info.get("indice_stagione_migliore")
                and diretto.info.get("politica_annuale")
                == processo.info.get("politica_annuale")
            )
            verde = (
                diretto.successo == processo.successo
                and (not diretto.successo or (firme_uguali and punteggio_uguale and metadati_uguali))
            )
            casi.append(CasoFase4RC(
                id_caso=f"processo-{indice:04d}",
                modalita=modalita,
                classe=classe.nome,
                studenti=classe.numero_studenti,
                fisso=classe.studente_fisso is not None,
                seed=seed,
                stato="verde" if verde else "anomalia",
                durata_s=round(time.monotonic() - t0, 6),
                dettaglio={
                    "origine": classe.origine,
                    "firme_uguali": firme_uguali,
                    "punteggio_uguale": punteggio_uguale,
                    "metadati_uguali": metadati_uguali,
                    "successo_diretto": diretto.successo,
                    "successo_processo": processo.successo,
                },
            ))
    return _rapporto("differenziale_processi", inizio, casi)


def campagna_t4_saturo(
    *,
    seed_base: int = 600000,
    minimo_studenti: int = 12,
    massimo_studenti: int = 30,
) -> RapportoFase4RC:
    casi: list[CasoFase4RC] = []
    inizio = time.monotonic()
    indice = 0
    for n in range(minimo_studenti, massimo_studenti + 1):
        for fisso in (False, True):
            classe = genera_classe_sintetica(
                n, seed=seed_base + n * 17 + int(fisso),
                famiglia="vuota", con_fisso=fisso,
            )
            for modalita in ("coppie", "terzetti"):
                indice += 1
                seed = seed_base + indice * 1009
                t0 = time.monotonic()
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    telemetria = telemetria_storico_saturo_rc(
                    classe, modalita=modalita, seed=seed, num_candidati=1
                )
                verde = (
                    telemetria.successo
                    and telemetria.risultato_valido is True
                    and telemetria.tentativi_iniziati == (1, 4)
                    and telemetria.tentativi_successo == (4,)
                )
                casi.append(CasoFase4RC(
                    id_caso=f"t4-{indice:04d}",
                    modalita=modalita,
                    classe=classe.nome,
                    studenti=n,
                    fisso=fisso,
                    seed=seed,
                    stato="verde" if verde else "anomalia",
                    durata_s=round(time.monotonic() - t0, 6),
                    dettaglio=telemetria.come_dict(),
                ))
    return _rapporto("t4_storico_saturo", inizio, casi)


def campagna_storico_corpus(
    protocollo: str | Path,
    archivio: str | Path,
    *,
    seed_base: int = 700000,
    num_mesi: int = 10,
    indici: Iterable[int] | None = None,
) -> RapportoFase4RC:
    classi = carica_classi_corpus_ufficiale(protocollo, archivio)
    scelti = set(indici) if indici is not None else set(range(len(classi)))
    casi: list[CasoFase4RC] = []
    inizio = time.monotonic()
    indice_caso = 0
    for indice_classe, classe in enumerate(classi):
        if indice_classe not in scelti:
            continue
        for modalita in ("coppie", "terzetti"):
            indice_caso += 1
            seed = seed_base + indice_classe * 101 + int(modalita == "terzetti")
            t0 = time.monotonic()
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                verifica = verifica_accumulo_storico_rc(
                classe, modalita=modalita, seed=seed,
                num_mesi=num_mesi, num_candidati=1,
            )
            casi.append(CasoFase4RC(
                id_caso=f"storico-{indice_classe:02d}-{modalita}",
                modalita=modalita,
                classe=classe.nome,
                studenti=classe.numero_studenti,
                fisso=classe.studente_fisso is not None,
                seed=seed,
                stato="verde" if verifica.valido else "anomalia",
                durata_s=round(time.monotonic() - t0, 6),
                dettaglio={
                    "origine": classe.origine,
                    "mesi_completati": verifica.mesi_completati,
                    "differenze": list(verifica.differenze),
                },
            ))
    return _rapporto("storico_cumulativo", inizio, casi)


def scrivi_rapporto_fase4(rapporto: RapportoFase4RC, destinazione: str | Path) -> None:
    path = Path(destinazione)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
