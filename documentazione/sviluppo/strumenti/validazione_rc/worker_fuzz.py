# -*- coding: utf-8 -*-
"""Worker isolato per una singola verifica mensile fuzz RC."""
from __future__ import annotations
import argparse, json
from dataclasses import fields
from pathlib import Path

from .fuzzing import SpecFuzzRC, genera_classe_fuzz, verifica_mensile_differenziale


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a=p.parse_args(argv)
    raw=json.loads(a.spec.read_text(encoding='utf-8'))
    spec=SpecFuzzRC(**raw['spec'])
    classe=genera_classe_fuzz(spec)
    n, anomalie=verifica_mensile_differenziale(classe,spec,raw['modalita'])
    a.out.write_text(json.dumps({
        'verifiche':n,
        'anomalie':[{'id_caso':x.id_caso,'proprieta':x.proprieta,'dettaglio':x.dettaglio,'spec':x.spec} for x in anomalie],
    },ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
