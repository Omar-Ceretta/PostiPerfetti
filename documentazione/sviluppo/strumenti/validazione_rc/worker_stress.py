# -*- coding: utf-8 -*-
"""Worker monouso della campagna RC isolata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

from .esecuzione import esegui_mensile_coppie_rc, esegui_mensile_terzetti_rc
from .generatori import genera_classe_sintetica
from .stress import CasoStressRC


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="postiperfetti-rc-worker-stress")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser


def _scrivi(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        caso = CasoStressRC(**raw)
        classe = genera_classe_sintetica(
            caso.studenti,
            seed=caso.seed_classe,
            famiglia=caso.famiglia,
            con_fisso=caso.fisso,
        )
        if caso.modalita == "coppie":
            esito = esegui_mensile_coppie_rc(
                classe,
                seed=caso.seed_motore,
                num_candidati=caso.num_candidati,
            )
        elif caso.modalita == "terzetti":
            esito = esegui_mensile_terzetti_rc(
                classe,
                seed=caso.seed_motore,
                num_candidati=caso.num_candidati,
            )
        else:
            raise ValueError(f"Modalità sconosciuta: {caso.modalita!r}")

        if esito.verifica is None:
            payload = {
                "stato": "fallimento_motore",
                "violazioni": [],
            }
        elif esito.verifica.valido:
            payload = {
                "stato": "successo_valido",
                "violazioni": [],
                "metriche": {
                    "studenti": esito.verifica.metriche.studenti,
                    "blocchi": list(esito.verifica.metriche.blocchi),
                    "adiacenze": esito.verifica.metriche.adiacenze,
                    "incompatibilita_l1": esito.verifica.metriche.incompatibilita_l1,
                    "incompatibilita_l2": esito.verifica.metriche.incompatibilita_l2,
                    "incompatibilita_l3": esito.verifica.metriche.incompatibilita_l3,
                    "affinita": esito.verifica.metriche.affinita,
                    "adiacenze_miste": esito.verifica.metriche.adiacenze_miste,
                },
            }
        else:
            payload = {
                "stato": "risultato_invalido",
                "violazioni": [v.codice for v in esito.verifica.violazioni],
                "messaggi": [v.messaggio for v in esito.verifica.violazioni],
            }
        _scrivi(args.out, payload)
        return 0
    except BaseException as exc:
        _scrivi(
            args.out,
            {
                "stato": "crash",
                "violazioni": [],
                "errore": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            },
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
