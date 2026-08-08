# -*- coding: utf-8 -*-
"""CLI iniziale del Cantiere Validazione RC."""

from __future__ import annotations

import argparse
from pathlib import Path

from moduli.file_classe import serializza_file_classe

from .campagne import (
    PROFILI_MENSILI, esegui_campagna_mensile_corpus,
    esegui_campagna_mensile_sintetica, scrivi_rapporto_campagna,
)
from .corpus import attesta_corpus_ufficiale, scrivi_rapporto_corpus
from .campagne_annuali import (
    campagna_annuale_corpus,
    campagna_differenziale_processi,
    campagna_t4_saturo,
    campagna_storico_corpus,
    scrivi_rapporto_fase4,
)
from .generatori import dati_validati_da_classe, genera_classe_sintetica
from .gate_rc import esegui_gate_rc, scrivi_rapporto_gate
from .campagne_metamorfiche import (
    campagna_metamorfica_corpus,
    scrivi_rapporto_metamorfico,
)
from .mutazioni import esegui_mutation_testing, scrivi_rapporto_mutazioni
from .fuzzing import campagna_fuzz_rc, campagna_oracolo_coppie_rc, scrivi_rapporto_fuzz
from .modelli import FamigliaSintetica
from .stati_gui import campagna_stati_gui_fault_rc, scrivi_rapporto_gui_rc
from .stress import FAMIGLIE_STRESS, PROFILI_RICERCA, PROFILI_STRESS, esegui_campagna_stress, scrivi_rapporto_stress


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="postiperfetti-validazione-rc")
    sotto = parser.add_subparsers(dest="comando", required=True)

    attesta = sotto.add_parser("attesta-corpus", help="Valida il corpus ufficiale 19×2.")
    attesta.add_argument("protocollo", type=Path)
    attesta.add_argument("archivio", type=Path)
    attesta.add_argument("--rapporto", type=Path)

    genera = sotto.add_parser("genera-classe", help="Genera un caso sintetico 12–30.")
    genera.add_argument("destinazione", type=Path)
    genera.add_argument("--studenti", type=int, required=True)
    genera.add_argument("--seed", type=int, required=True)
    genera.add_argument("--famiglia", choices=[f.value for f in FamigliaSintetica], required=True)
    genera.add_argument("--fisso", action="store_true")

    campagna = sotto.add_parser(
        "campagna-mensile",
        help="Esegue una matrice sintetica 12–30 contro i motori reali.",
    )
    campagna.add_argument("--profilo", choices=sorted(PROFILI_MENSILI), default="smoke")
    campagna.add_argument("--seed-base", type=int, default=20260806)
    campagna.add_argument("--candidati", type=int, default=1)
    campagna.add_argument("--rapporto", type=Path)

    corpus = sotto.add_parser(
        "campagna-corpus",
        help="Esegue coppie e terzetti sui 38 file ufficiali attestati.",
    )
    corpus.add_argument("protocollo", type=Path)
    corpus.add_argument("archivio", type=Path)
    corpus.add_argument("--seed-base", type=int, default=20260806)
    corpus.add_argument("--candidati", type=int, default=1)
    corpus.add_argument("--rapporto", type=Path)

    stress = sotto.add_parser(
        "campagna-stress",
        help="Esegue casi strutturali 12–30 in processi isolati con timeout per caso.",
    )
    stress.add_argument("--profilo", choices=sorted(PROFILI_STRESS), default="pilot")
    stress.add_argument("--seed-base", type=int, default=20260806)
    stress.add_argument("--ricerca", choices=sorted(PROFILI_RICERCA), default="produzione")
    stress.add_argument("--semi-per-combinazione", type=int, default=1)
    stress.add_argument("--timeout", type=float, default=3.0)
    stress.add_argument("--parallelismo", type=int, default=4)
    stress.add_argument("--famiglia", action="append", choices=list(FAMIGLIE_STRESS))
    stress.add_argument("--min-studenti", type=int)
    stress.add_argument("--max-studenti", type=int)
    stress.add_argument("--checkpoint", type=Path)
    stress.add_argument("--riprendi", action="store_true")
    stress.add_argument("--reperti-dir", type=Path)
    stress.add_argument("--rapporto", type=Path)

    annuale = sotto.add_parser(
        "campagna-annuale",
        help="Valida Annuale e riordini sul corpus ufficiale con uno o più seed.",
    )
    annuale.add_argument("protocollo", type=Path)
    annuale.add_argument("archivio", type=Path)
    annuale.add_argument("--seed", type=int, action="append")
    annuale.add_argument("--mesi", type=int, default=4)
    annuale.add_argument("--stagioni", type=int, default=1)
    annuale.add_argument("--produzione", action="store_true")
    annuale.add_argument("--rapporto", type=Path)

    processi = sotto.add_parser(
        "campagna-processi-annuale",
        help="Confronta Annuale diretto e processo separato sul corpus ufficiale.",
    )
    processi.add_argument("protocollo", type=Path)
    processi.add_argument("archivio", type=Path)
    processi.add_argument("--seed-base", type=int, default=310000)
    processi.add_argument("--mesi", type=int, default=3)
    processi.add_argument("--stagioni", type=int, default=2)
    processi.add_argument("--indice", type=int, action="append")
    processi.add_argument("--rapporto", type=Path)

    t4 = sotto.add_parser(
        "campagna-t4",
        help="Forza uno Storico saturo e verifica il fallback T4 su 12–30 studenti.",
    )
    t4.add_argument("--seed-base", type=int, default=600000)
    t4.add_argument("--min-studenti", type=int, default=12)
    t4.add_argument("--max-studenti", type=int, default=30)
    t4.add_argument("--rapporto", type=Path)

    storico = sotto.add_parser(
        "campagna-storico",
        help="Confronta i contatori cumulativi con le adiacenze fisiche del corpus.",
    )
    storico.add_argument("protocollo", type=Path)
    storico.add_argument("archivio", type=Path)
    storico.add_argument("--seed-base", type=int, default=700000)
    storico.add_argument("--mesi", type=int, default=10)
    storico.add_argument("--indice", type=int, action="append")
    storico.add_argument("--rapporto", type=Path)

    metamorfica = sotto.add_parser(
        "campagna-metamorfica",
        help="Applica trasformazioni semanticamente equivalenti o più permissive al corpus.",
    )
    metamorfica.add_argument("protocollo", type=Path)
    metamorfica.add_argument("archivio", type=Path)
    metamorfica.add_argument("--seed", type=int, action="append")
    metamorfica.add_argument("--permutazioni-righe", type=int, default=3)
    metamorfica.add_argument("--rapporto", type=Path)

    mutazioni = sotto.add_parser(
        "mutation-test",
        help="Esegue mutazioni mirate in copie temporanee e verifica i test sentinella.",
    )
    mutazioni.add_argument("--root", type=Path, default=Path.cwd())
    mutazioni.add_argument("--timeout", type=float, default=12.0)
    mutazioni.add_argument("--id", action="append")
    mutazioni.add_argument("--rapporto", type=Path)

    fuzz = sotto.add_parser(
        "campagna-fuzz",
        help="Property/differential fuzzing 12–30 con riduzione automatica dei rossi.",
    )
    fuzz.add_argument("--seed-base", type=int, default=20260807)
    fuzz.add_argument("--casi-filtri", type=int, default=2000)
    fuzz.add_argument("--casi-mensili", type=int, default=300)
    fuzz.add_argument("--reperti-dir", type=Path)
    fuzz.add_argument("--timeout-mensile", type=float, default=4.0)
    fuzz.add_argument("--parallelismo", type=int, default=4)
    fuzz.add_argument("--rapporto", type=Path)

    oracle = sotto.add_parser(
        "campagna-oracolo-coppie",
        help="Confronta il motore coppie con un oracolo esatto T4 nel dominio 12–30.",
    )
    oracle.add_argument("--seed-base", type=int, default=606000)
    oracle.add_argument("--casi", type=int, default=400)
    oracle.add_argument("--estremo", action="store_true")
    oracle.add_argument("--limite-nodi", type=int, default=150000)
    oracle.add_argument("--rapporto", type=Path)

    gate = sotto.add_parser(
        "gate-rc",
        help="Esegue il gate finale PRECHECK o FULL per la promozione a Release Candidate.",
    )
    gate.add_argument("--root", type=Path, default=Path.cwd())
    gate.add_argument("--profilo", choices=("precheck", "full"), default="precheck")
    gate.add_argument("--output-dir", type=Path, required=True)
    gate.add_argument("--qt", action="store_true", help="Esegue lo smoke Qt anche nel PRECHECK.")
    gate.add_argument("--riprendi", action="store_true", help="Riusa i rapporti FULL già verdi se il manifest è identico.")

    gui = sotto.add_parser(
        "campagna-gui-stati",
        help="Macchina a stati + fault injection headless su GUI, persistenza e processi.",
    )
    gui.add_argument("--root", type=Path, default=Path.cwd())
    gui.add_argument("--rapporto", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.comando == "attesta-corpus":
        statistiche = attesta_corpus_ufficiale(args.protocollo, args.archivio)
        if args.rapporto:
            scrivi_rapporto_corpus(statistiche, args.rapporto)
        print(
            f"Corpus RC valido: {statistiche.coppie} coppie, "
            f"{statistiche.file_classe} file, "
            f"{statistiche.minimo_studenti}-{statistiche.massimo_studenti} studenti."
        )
        return 0
    if args.comando == "genera-classe":
        classe = genera_classe_sintetica(
            args.studenti,
            seed=args.seed,
            famiglia=args.famiglia,
            con_fisso=args.fisso,
        )
        contenuto = serializza_file_classe(classe.nome, dati_validati_da_classe(classe))
        args.destinazione.parent.mkdir(parents=True, exist_ok=True)
        args.destinazione.write_text(contenuto + "\n", encoding="utf-8")
        print(f"Classe scritta: {args.destinazione}")
        return 0
    if args.comando == "campagna-mensile":
        rapporto = esegui_campagna_mensile_sintetica(
            profilo=args.profilo,
            seed_base=args.seed_base,
            num_candidati=args.candidati,
        )
        if args.rapporto:
            scrivi_rapporto_campagna(rapporto, args.rapporto)
        print(
            f"Campagna {rapporto.profilo}: {rapporto.casi} casi, "
            f"{rapporto.successi} successi, "
            f"{rapporto.fallimenti_motore} fallimenti da qualificare, "
            f"{rapporto.risultati_invalidi} risultati invalidi."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-corpus":
        rapporto = esegui_campagna_mensile_corpus(
            args.protocollo,
            args.archivio,
            seed_base=args.seed_base,
            num_candidati=args.candidati,
        )
        if args.rapporto:
            scrivi_rapporto_campagna(rapporto, args.rapporto)
        print(
            f"Campagna corpus: {rapporto.casi} casi, "
            f"{rapporto.successi} successi, "
            f"{rapporto.fallimenti_motore} fallimenti da qualificare, "
            f"{rapporto.risultati_invalidi} risultati invalidi."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-annuale":
        rapporto = campagna_annuale_corpus(
            args.protocollo, args.archivio,
            semi=tuple(args.seed or [20260806]),
            num_mesi=args.mesi, numero_stagioni=args.stagioni,
            produzione=args.produzione,
        )
        if args.rapporto:
            scrivi_rapporto_fase4(rapporto, args.rapporto)
        print(
            f"Annuale corpus: {rapporto.casi} casi, {rapporto.verdi} verdi, "
            f"{rapporto.anomalie} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-processi-annuale":
        rapporto = campagna_differenziale_processi(
            args.protocollo, args.archivio, seed_base=args.seed_base,
            num_mesi=args.mesi, numero_stagioni=args.stagioni,
            indici=args.indice,
        )
        if args.rapporto:
            scrivi_rapporto_fase4(rapporto, args.rapporto)
        print(
            f"Differenziale processi: {rapporto.casi} casi, "
            f"{rapporto.verdi} verdi, {rapporto.anomalie} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-t4":
        rapporto = campagna_t4_saturo(
            seed_base=args.seed_base,
            minimo_studenti=args.min_studenti, massimo_studenti=args.max_studenti,
        )
        if args.rapporto:
            scrivi_rapporto_fase4(rapporto, args.rapporto)
        print(
            f"Fallback T4: {rapporto.casi} casi, {rapporto.verdi} verdi, "
            f"{rapporto.anomalie} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-storico":
        rapporto = campagna_storico_corpus(
            args.protocollo, args.archivio, seed_base=args.seed_base,
            num_mesi=args.mesi, indici=args.indice,
        )
        if args.rapporto:
            scrivi_rapporto_fase4(rapporto, args.rapporto)
        print(
            f"Storico cumulativo: {rapporto.casi} casi, {rapporto.verdi} verdi, "
            f"{rapporto.anomalie} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-metamorfica":
        rapporto = campagna_metamorfica_corpus(
            args.protocollo, args.archivio,
            semi=tuple(args.seed or (810000,)),
            permutazioni_righe=args.permutazioni_righe,
        )
        if args.rapporto:
            scrivi_rapporto_metamorfico(rapporto, args.rapporto)
        print(
            f"Metamorfica corpus: {rapporto.casi} casi, "
            f"{rapporto.verdi} verdi, {rapporto.anomalie} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "mutation-test":
        rapporto = esegui_mutation_testing(
            args.root, timeout_s=args.timeout, ids=args.id,
        )
        if args.rapporto:
            scrivi_rapporto_mutazioni(rapporto, args.rapporto)
        print(
            f"Mutation testing: {rapporto.uccisi}/{rapporto.mutanti} uccisi, "
            f"{rapporto.sopravvissuti} sopravvissuti, "
            f"score={rapporto.score:.1f}%."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-fuzz":
        rapporto = campagna_fuzz_rc(
            seed_base=args.seed_base, casi_filtri=args.casi_filtri,
            casi_mensili=args.casi_mensili, reperti_dir=args.reperti_dir,
            timeout_mensile_s=args.timeout_mensile, parallelismo=args.parallelismo,
            radice_progetto=Path.cwd(),
        )
        if args.rapporto:
            scrivi_rapporto_fuzz(rapporto, args.rapporto)
        print(
            f"Fuzz RC: {rapporto.casi_filtri} classi filtro, "
            f"{rapporto.coppie_valutate} coppie T1–T4, "
            f"{rapporto.verifiche_mensili} verifiche mensili, "
            f"{rapporto.timeout_mensili} timeout, {rapporto.crash_mensili} crash, "
            f"{len(rapporto.anomalie)} anomalie."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-oracolo-coppie":
        rapporto = campagna_oracolo_coppie_rc(
            seed_base=args.seed_base, casi=args.casi, estremo=args.estremo,
            limite_nodi=args.limite_nodi,
        )
        if args.rapporto:
            args.rapporto.parent.mkdir(parents=True, exist_ok=True)
            import json
            args.rapporto.write_text(json.dumps(rapporto, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"Oracolo coppie: {rapporto['casi']} casi, "
            f"{rapporto['oracolo'].get('fattibile',0)} fattibili, "
            f"{rapporto['oracolo'].get('impossibile',0)} impossibili, "
            f"{len(rapporto['anomalie'])} anomalie."
        )
        return 0 if rapporto["verde"] else 1
    if args.comando == "gate-rc":
        rapporto = esegui_gate_rc(
            args.root, args.output_dir, profilo=args.profilo,
            qt=(True if args.qt else None), riprendi=args.riprendi,
        )
        scrivi_rapporto_gate(rapporto, args.output_dir)
        print(
            f"Gate RC {rapporto.profilo}: {rapporto.passati} PASS, "
            f"{rapporto.falliti} FAIL, {rapporto.saltati} SKIP — {rapporto.verdetto}."
        )
        if rapporto.verdetto == "RC_BLOCKED":
            return 1
        return 0
    if args.comando == "campagna-gui-stati":
        rapporto = campagna_stati_gui_fault_rc(args.root)
        if args.rapporto:
            scrivi_rapporto_gui_rc(rapporto, args.rapporto)
        print(
            f"GUI/stati/fault: {rapporto.controlli} controlli, "
            f"{rapporto.verdi} verdi, {rapporto.rossi} rossi."
        )
        return 0 if rapporto.verde else 1
    if args.comando == "campagna-stress":
        rapporto = esegui_campagna_stress(
            profilo=args.profilo,
            seed_base=args.seed_base,
            profilo_ricerca=args.ricerca,
            semi_per_combinazione=args.semi_per_combinazione,
            timeout_s=args.timeout,
            parallelismo=args.parallelismo,
            radice_progetto=Path.cwd(),
            reperti_dir=args.reperti_dir,
            famiglie=tuple(args.famiglia) if args.famiglia else None,
            minimo_studenti=args.min_studenti,
            massimo_studenti=args.max_studenti,
            checkpoint_path=args.checkpoint,
            riprendi=args.riprendi,
        )
        if args.rapporto:
            scrivi_rapporto_stress(rapporto, args.rapporto)
        print(
            f"Stress {rapporto.profilo}/{rapporto.profilo_ricerca}: {rapporto.casi} casi, "
            f"{rapporto.successi_validi} successi validi, "
            f"{rapporto.fallimenti_motore} fallimenti motore, "
            f"{rapporto.timeout} timeout, "
            f"{rapporto.crash} crash, "
            f"{rapporto.risultati_invalidi} risultati invalidi."
        )
        return 0 if rapporto.verde_correttezza else 1
    raise AssertionError("Comando non gestito")
