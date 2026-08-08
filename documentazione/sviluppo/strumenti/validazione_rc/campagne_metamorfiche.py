# -*- coding: utf-8 -*-
"""Campagne metamorfiche sul corpus reale della Validazione RC."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
import io
import json
from pathlib import Path
import time
from typing import Iterable

from .corpus import carica_classi_corpus_ufficiale
from .esecuzione import esegui_mensile_coppie_rc, esegui_mensile_terzetti_rc
from .metamorfico import (
    indebolisci_una_incompatibilita_assoluta,
    inverti_generi,
    permuta_ordine_relazioni,
    permuta_righe,
    rimuovi_un_vincolo_prima,
    rimuovi_una_affinita,
)


@dataclass(frozen=True, slots=True)
class CasoMetamorficoRC:
    id_caso: str
    classe: str
    modalita: str
    trasformazione: str
    seed: int
    stato: str
    dettaglio: dict


@dataclass(frozen=True, slots=True)
class RapportoMetamorficoRC:
    casi: int
    verdi: int
    anomalie: int
    durata_s: float
    dettaglio: tuple[CasoMetamorficoRC, ...]

    @property
    def verde(self) -> bool:
        return self.anomalie == 0

    def come_dict(self) -> dict:
        return {
            "campagna": "metamorfica_corpus",
            "casi": self.casi,
            "verdi": self.verdi,
            "anomalie": self.anomalie,
            "durata_s": self.durata_s,
            "verde": self.verde,
            "dettaglio": [asdict(caso) for caso in self.dettaglio],
        }


def _firma(esito):
    if not esito.successo or esito.verifica is None:
        return None
    return tuple(sorted(esito.verifica.adiacenze))


def _esegui(classe, modalita: str, *, seed: int, genere_misto: bool = False):
    funzione = (
        esegui_mensile_coppie_rc
        if modalita == "coppie"
        else esegui_mensile_terzetti_rc
    )
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return funzione(
            classe,
            seed=seed,
            genere_misto=genere_misto,
            num_candidati=1,
        )


def campagna_metamorfica_corpus(
    protocollo: str | Path,
    archivio: str | Path,
    *,
    semi: Iterable[int] = (810000,),
    permutazioni_righe: int = 3,
) -> RapportoMetamorficoRC:
    """Verifica equivalenze e monotonicità su tutte le classi ufficiali."""
    inizio = time.monotonic()
    classi = carica_classi_corpus_ufficiale(protocollo, archivio)
    casi: list[CasoMetamorficoRC] = []
    progressivo = 0

    for seed_base in semi:
        for indice_classe, classe in enumerate(classi):
            for modalita in ("coppie", "terzetti"):
                seed = int(seed_base) + indice_classe * 1009 + int(modalita == "terzetti")
                base = _esegui(classe, modalita, seed=seed)
                firma_base = _firma(base)

                # 1) L'ordine delle righe è solo rappresentazione: risultato esatto.
                for k in range(permutazioni_righe):
                    progressivo += 1
                    trasformata = permuta_righe(
                        classe, seed=seed_base + indice_classe * 97 + k + 1
                    )
                    esito = _esegui(trasformata, modalita, seed=seed)
                    verde = (
                        base.successo == esito.successo
                        and firma_base == _firma(esito)
                    )
                    casi.append(CasoMetamorficoRC(
                        f"meta-{progressivo:05d}", classe.nome, modalita,
                        "permuta_righe", seed, "verde" if verde else "anomalia",
                        {"successo_base": base.successo, "successo_trasformato": esito.successo,
                         "firma_identica": firma_base == _firma(esito)},
                    ))

                # 2) L'ordine testuale delle relazioni è rappresentazione pura.
                progressivo += 1
                relazioni = permuta_ordine_relazioni(classe, seed=seed + 333)
                esito_rel = _esegui(relazioni, modalita, seed=seed)
                verde = base.successo == esito_rel.successo and firma_base == _firma(esito_rel)
                casi.append(CasoMetamorficoRC(
                    f"meta-{progressivo:05d}", classe.nome, modalita,
                    "permuta_relazioni", seed, "verde" if verde else "anomalia",
                    {"firma_identica": firma_base == _firma(esito_rel)},
                ))

                # 3) M/F sono etichette simmetriche quando la preferenza mista è attiva.
                progressivo += 1
                base_misto = _esegui(classe, modalita, seed=seed + 17, genere_misto=True)
                invertita = inverti_generi(classe)
                esito_misto = _esegui(invertita, modalita, seed=seed + 17, genere_misto=True)
                verde = (
                    base_misto.successo == esito_misto.successo
                    and _firma(base_misto) == _firma(esito_misto)
                )
                casi.append(CasoMetamorficoRC(
                    f"meta-{progressivo:05d}", classe.nome, modalita,
                    "inverti_generi", seed + 17, "verde" if verde else "anomalia",
                    {"firma_identica": _firma(base_misto) == _firma(esito_misto)},
                ))

                # 4) Allentare un vincolo non può rendere irrisolvibile un caso già risolto.
                trasformazioni = (
                    ("rimuovi_affinita", rimuovi_una_affinita),
                    ("indebolisci_incompatibilita3", indebolisci_una_incompatibilita_assoluta),
                    ("rimuovi_prima", rimuovi_un_vincolo_prima),
                )
                for offset, (nome, funzione) in enumerate(trasformazioni, start=1):
                    trasformata = funzione(classe, seed=seed + 100 + offset)
                    if trasformata is None:
                        continue
                    progressivo += 1
                    esito = _esegui(trasformata, modalita, seed=seed)
                    verde = not base.successo or bool(
                        esito.successo and esito.verifica is not None and esito.verifica.valido
                    )
                    casi.append(CasoMetamorficoRC(
                        f"meta-{progressivo:05d}", classe.nome, modalita,
                        nome, seed, "verde" if verde else "anomalia",
                        {"successo_base": base.successo, "successo_trasformato": esito.successo},
                    ))

    anomalie = sum(caso.stato != "verde" for caso in casi)
    return RapportoMetamorficoRC(
        casi=len(casi),
        verdi=len(casi) - anomalie,
        anomalie=anomalie,
        durata_s=round(time.monotonic() - inizio, 6),
        dettaglio=tuple(casi),
    )


def scrivi_rapporto_metamorfico(rapporto: RapportoMetamorficoRC, destinazione: str | Path) -> None:
    path = Path(destinazione)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
