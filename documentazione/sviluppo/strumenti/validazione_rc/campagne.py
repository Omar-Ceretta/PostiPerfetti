# -*- coding: utf-8 -*-
"""Campagne headless riproducibili del Cantiere Validazione RC."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .esecuzione import esegui_mensile_coppie_rc, esegui_mensile_terzetti_rc
from .generatori import genera_classe_sintetica


PROFILI_MENSILI = {
    "smoke": ("vuota", "sparsa", "media"),
}

# Le famiglie strutturali restano disponibili nel generatore. La loro campagna
# completa verrà eseguita nella Fase 3 in processi isolati con timeout per caso,
# così un input patologico non può bloccare l'intera matrice.
FAMIGLIE_STRUTTURALI = ("stella", "due_blocchi", "quasi_clique", "clique_sovrabbondante")


@dataclass(frozen=True, slots=True)
class CasoCampagnaRC:
    id_caso: str
    modalita: str
    studenti: int
    famiglia: str
    fisso: bool
    seed_classe: int
    seed_motore: int
    successo_motore: bool
    valido_osservatore: bool | None
    violazioni: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RapportoCampagnaRC:
    profilo: str
    casi: int
    successi: int
    fallimenti_motore: int
    risultati_invalidi: int
    dettaglio: tuple[CasoCampagnaRC, ...]

    @property
    def verde(self) -> bool:
        return self.risultati_invalidi == 0

    def come_dict(self) -> dict:
        return {
            "profilo": self.profilo,
            "casi": self.casi,
            "successi": self.successi,
            "fallimenti_motore": self.fallimenti_motore,
            "risultati_invalidi": self.risultati_invalidi,
            "verde": self.verde,
            "dettaglio": [asdict(caso) for caso in self.dettaglio],
        }


def esegui_campagna_mensile_sintetica(
    *,
    profilo: str = "smoke",
    seed_base: int = 20260806,
    num_candidati: int = 1,
) -> RapportoCampagnaRC:
    """Esegue tutte le taglie 12–30 per famiglie e condizioni del profilo.

    Un fallimento del motore non viene automaticamente classificato come bug:
    alcune classi possono essere realmente impossibili. Un risultato dichiarato
    riuscito ma respinto dall'osservatore indipendente è invece sempre rosso.
    """
    if profilo not in PROFILI_MENSILI:
        raise ValueError(f"Profilo sconosciuto: {profilo!r}")

    dettaglio: list[CasoCampagnaRC] = []
    indice = 0
    for famiglia in PROFILI_MENSILI[profilo]:
        for n in range(12, 31):
            for fisso in (False, True):
                for modalita in ("coppie", "terzetti"):
                    indice += 1
                    seed_classe = seed_base + indice * 17
                    seed_motore = seed_base + indice * 1009
                    classe = genera_classe_sintetica(
                        n,
                        seed=seed_classe,
                        famiglia=famiglia,
                        con_fisso=fisso,
                    )
                    if modalita == "coppie":
                        esito = esegui_mensile_coppie_rc(
                            classe,
                            seed=seed_motore,
                            num_candidati=num_candidati,
                        )
                    else:
                        esito = esegui_mensile_terzetti_rc(
                            classe,
                            seed=seed_motore,
                            num_candidati=num_candidati,
                        )
                    verifica = esito.verifica
                    dettaglio.append(
                        CasoCampagnaRC(
                            id_caso=f"{profilo}-{indice:04d}",
                            modalita=modalita,
                            studenti=n,
                            famiglia=famiglia,
                            fisso=fisso,
                            seed_classe=seed_classe,
                            seed_motore=seed_motore,
                            successo_motore=bool(esito.successo),
                            valido_osservatore=(verifica.valido if verifica is not None else None),
                            violazioni=tuple(
                                v.codice for v in (verifica.violazioni if verifica else ())
                            ),
                        )
                    )

    successi = sum(c.successo_motore for c in dettaglio)
    fallimenti = sum(not c.successo_motore and c.valido_osservatore is None for c in dettaglio)
    invalidi = sum(c.valido_osservatore is False for c in dettaglio)
    return RapportoCampagnaRC(
        profilo=profilo,
        casi=len(dettaglio),
        successi=successi,
        fallimenti_motore=fallimenti,
        risultati_invalidi=invalidi,
        dettaglio=tuple(dettaglio),
    )


def scrivi_rapporto_campagna(rapporto: RapportoCampagnaRC, destinazione: str | Path) -> None:
    destinazione = Path(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def esegui_campagna_mensile_corpus(
    protocollo_path: str | Path,
    archivio_corpus: str | Path,
    *,
    seed_base: int = 20260806,
    num_candidati: int = 1,
) -> RapportoCampagnaRC:
    """Esegue coppie e terzetti sui 38 file ufficiali attestati."""
    from .corpus import carica_classi_corpus_ufficiale

    dettaglio: list[CasoCampagnaRC] = []
    indice = 0
    for classe in carica_classi_corpus_ufficiale(protocollo_path, archivio_corpus):
        fisso = classe.studente_fisso is not None
        for modalita in ("coppie", "terzetti"):
            indice += 1
            seed_motore = seed_base + indice * 1009
            if modalita == "coppie":
                esito = esegui_mensile_coppie_rc(
                    classe,
                    seed=seed_motore,
                    num_candidati=num_candidati,
                )
            else:
                esito = esegui_mensile_terzetti_rc(
                    classe,
                    seed=seed_motore,
                    num_candidati=num_candidati,
                )
            verifica = esito.verifica
            dettaglio.append(
                CasoCampagnaRC(
                    id_caso=f"corpus-{indice:04d}",
                    modalita=modalita,
                    studenti=classe.numero_studenti,
                    famiglia="corpus_ufficiale",
                    fisso=fisso,
                    seed_classe=0,
                    seed_motore=seed_motore,
                    successo_motore=bool(esito.successo),
                    valido_osservatore=(verifica.valido if verifica is not None else None),
                    violazioni=tuple(v.codice for v in (verifica.violazioni if verifica else ())),
                )
            )

    successi = sum(c.successo_motore for c in dettaglio)
    fallimenti = sum(not c.successo_motore and c.valido_osservatore is None for c in dettaglio)
    invalidi = sum(c.valido_osservatore is False for c in dettaglio)
    return RapportoCampagnaRC(
        profilo="corpus_ufficiale",
        casi=len(dettaglio),
        successi=successi,
        fallimenti_motore=fallimenti,
        risultati_invalidi=invalidi,
        dettaglio=tuple(dettaglio),
    )
