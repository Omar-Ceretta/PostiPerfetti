"""Interfaccia a riga di comando dell'osservatore semantico — I10."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ambiente import ErroreClassiAppaiate, carica_e_valida_coppia_classi
from .audit_finale import (
    ErroreAuditFinale,
    confronta_raccolte_riproducibili,
    pubblica_audit_finale,
)
from .confronto_appaiato import (
    ErroreConfrontoAppaiato,
    costruisci_confronto_appaiato,
    pubblica_confronto_appaiato,
    rendi_confronto_markdown,
    valida_dati_confronto,
)
from .protocollo import ErroreProtocollo, carica_protocollo
from .raccolta import ErroreRaccolta, pubblica_raccolta_da_output, valida_raccolta
from .serializzazione import firma_file_sha256, firma_json_sha256, leggi_json, scrivi_json_atomico
from .rendering_markdown import ErroreRenderingMarkdown, scrivi_rapporto_markdown
from .validazione import ErroreValidazioneOutput, valida_dati_annata
from .snapshot import (
    ErroreSnapshot,
    crea_stato_iniziale_id,
    snapshot_da_file_configurazione,
    scrivi_snapshot,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="postiperfetti-cantiere-semantico",
        description="Osservatore semantico C1 R0.1: fondazioni, cronologia e output validati.",
    )
    sotto = parser.add_subparsers(dest="comando", required=True)

    valida = sotto.add_parser("valida-protocollo", help="Valida un PROTOCOLLO.json.")
    valida.add_argument("percorso", type=Path)

    firma_file = sotto.add_parser("firma-file", help="Calcola SHA-256 di un file.")
    firma_file.add_argument("percorso", type=Path)

    firma_json = sotto.add_parser("firma-json", help="Calcola la firma JSON canonica.")
    firma_json.add_argument("percorso", type=Path)

    normalizza = sotto.add_parser("normalizza-json", help="Riscrive un JSON in forma canonica.")
    normalizza.add_argument("origine", type=Path)
    normalizza.add_argument("destinazione", type=Path)

    snapshot = sotto.add_parser(
        "snapshot-stato",
        help="Fotografa rotazioni e contatori da un JSON di configurazione.",
    )
    snapshot.add_argument("configurazione", type=Path)
    snapshot.add_argument("destinazione", type=Path)

    coppia = sotto.add_parser(
        "valida-coppia-classi",
        help="Controlla che la gemella differisca soltanto per il FISSO.",
    )
    coppia.add_argument("protocollo", type=Path)
    coppia.add_argument("pair_id")
    coppia.add_argument("radice_corpus", type=Path)

    valida_annata = sotto.add_parser(
        "valida-annata",
        help="Valida autonomamente un ANNATA.json.",
    )
    valida_annata.add_argument("percorso", type=Path)

    rendi_annata = sotto.add_parser(
        "rendi-annata",
        help="Genera ANNATA.md da un ANNATA.json valido.",
    )
    rendi_annata.add_argument("origine", type=Path)
    rendi_annata.add_argument("destinazione", type=Path)

    valida_confronto = sotto.add_parser(
        "valida-confronto",
        help="Valida autonomamente un CONFRONTO.json.",
    )
    valida_confronto.add_argument("percorso", type=Path)

    rendi_confronto = sotto.add_parser(
        "rendi-confronto",
        help="Genera CONFRONTO.md da un CONFRONTO.json valido.",
    )
    rendi_confronto.add_argument("origine", type=Path)
    rendi_confronto.add_argument("destinazione", type=Path)

    confronta = sotto.add_parser(
        "confronta-annate",
        help="Valida la coppia corpus e pubblica il confronto senza/con FISSO.",
    )
    confronta.add_argument("annata_senza_fisso", type=Path)
    confronta.add_argument("annata_con_fisso", type=Path)
    confronta.add_argument("protocollo", type=Path)
    confronta.add_argument("radice_corpus", type=Path)
    confronta.add_argument("destinazione", type=Path)

    raccolta = sotto.add_parser(
        "compone-raccolta",
        help="Compone indice, confronti, CSV, validazione e manifesto dai run già prodotti.",
    )
    raccolta.add_argument("protocollo", type=Path)
    raccolta.add_argument("radice_output_run", type=Path)
    raccolta.add_argument("radice_corpus", type=Path)
    raccolta.add_argument("destinazione", type=Path)

    valida_racc = sotto.add_parser(
        "valida-raccolta",
        help="Valida una raccolta completa e il suo manifesto.",
    )
    valida_racc.add_argument("directory", type=Path)

    audit = sotto.add_parser(
        "audit-finale",
        help="Verifica la conformità della raccolta al contratto R0.1.",
    )
    audit.add_argument("raccolta", type=Path)
    audit.add_argument("destinazione", type=Path)
    audit.add_argument("--consenti-incompleta", action="store_true")
    audit.add_argument("--richiedi-corpus-ufficiale", action="store_true")

    riproduci = sotto.add_parser(
        "confronta-riproducibilita",
        help="Confronta byte per byte i manifesti di due raccolte.",
    )
    riproduci.add_argument("prima", type=Path)
    riproduci.add_argument("seconda", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.comando == "valida-protocollo":
            protocollo = carica_protocollo(args.percorso)
            print(
                f"Protocollo valido: {protocollo.protocollo_id} | "
                f"{len(protocollo.coppie)} coppie | {len(protocollo.run)} run"
            )
            return 0
        if args.comando == "firma-file":
            print(firma_file_sha256(args.percorso))
            return 0
        if args.comando == "firma-json":
            print(firma_json_sha256(leggi_json(args.percorso)))
            return 0
        if args.comando == "normalizza-json":
            dati = leggi_json(args.origine)
            firma = scrivi_json_atomico(args.destinazione, dati)
            print(f"Scritto {args.destinazione} | firma canonica {firma}")
            return 0
        if args.comando == "snapshot-stato":
            snapshot = snapshot_da_file_configurazione(args.configurazione)
            firma_file = scrivi_snapshot(args.destinazione, snapshot)
            print(f"Snapshot scritto: {args.destinazione}")
            print(f"snapshot_sha256: {snapshot.sha256}")
            print(f"stato_iniziale_id: {crea_stato_iniziale_id(snapshot)}")
            print(f"firma_file_canonica: {firma_file}")
            return 0
        if args.comando == "valida-coppia-classi":
            protocollo = carica_protocollo(args.protocollo)
            specifica = next(
                (voce for voce in protocollo.coppie if voce.pair_id == args.pair_id),
                None,
            )
            if specifica is None:
                raise ErroreClassiAppaiate(
                    f"pair_id {args.pair_id!r} non presente nel protocollo."
                )
            esito = carica_e_valida_coppia_classi(
                specifica,
                args.radice_corpus,
            )
            print(
                f"Coppia valida: {esito.pair_id} | "
                f"{esito.numero_studenti} studenti | FISSO: {esito.studente_fisso}"
            )
            return 0
        if args.comando == "valida-annata":
            esito = valida_dati_annata(leggi_json(args.percorso))
            if esito.valido:
                print(f"ANNATA.json valido: {args.percorso}")
                return 0
            for problema in esito.problemi:
                percorso = f" [{problema.percorso}]" if problema.percorso else ""
                print(
                    f"{problema.gravita.value.upper()} {problema.codice}: "
                    f"{problema.messaggio}{percorso}",
                    file=sys.stderr,
                )
            return 2
        if args.comando == "rendi-annata":
            dati = leggi_json(args.origine)
            firma = scrivi_rapporto_markdown(args.destinazione, dati)
            print(f"Rapporto scritto: {args.destinazione}")
            print(f"sha256: {firma}")
            return 0
        if args.comando == "valida-confronto":
            esito = valida_dati_confronto(leggi_json(args.percorso))
            if esito.valido:
                print(f"CONFRONTO.json valido: {args.percorso}")
                return 0
            for problema in esito.problemi:
                print(f"ERRORE {problema.codice}: {problema.messaggio}", file=sys.stderr)
            return 2
        if args.comando == "rendi-confronto":
            dati = leggi_json(args.origine)
            testo = rendi_confronto_markdown(dati)
            from .serializzazione import scrivi_testo_atomico
            firma = scrivi_testo_atomico(args.destinazione, testo)
            print(f"Rapporto confronto scritto: {args.destinazione}")
            print(f"sha256: {firma}")
            return 0
        if args.comando == "confronta-annate":
            senza = leggi_json(args.annata_senza_fisso)
            con = leggi_json(args.annata_con_fisso)
            pair_id = senza.get("run", {}).get("pair_id")
            protocollo = carica_protocollo(args.protocollo)
            specifica = next((x for x in protocollo.coppie if x.pair_id == pair_id), None)
            if specifica is None:
                raise ErroreConfrontoAppaiato(
                    f"pair_id {pair_id!r} non presente nel protocollo."
                )
            attestazione = carica_e_valida_coppia_classi(specifica, args.radice_corpus)
            confronto = costruisci_confronto_appaiato(
                senza, con, attestazione_classi=attestazione
            )
            esito = pubblica_confronto_appaiato(confronto, args.destinazione)
            print(f"Confronto pubblicato: {esito.directory}")
            print(f"validita_appaiamento: {confronto.validita_appaiamento}")
            return 0 if confronto.validita_appaiamento else 2
        if args.comando == "compone-raccolta":
            esito = pubblica_raccolta_da_output(
                args.protocollo, args.radice_output_run, args.radice_corpus, args.destinazione
            )
            print(f"Raccolta pubblicata: {esito.directory}")
            print(f"run completi: {esito.run_completi}/{esito.run_attesi}")
            print(f"confronti validi: {esito.confronti_validi}")
            print(f"matrice completa: {esito.completa}")
            return 0
        if args.comando == "valida-raccolta":
            esito = valida_raccolta(args.directory, verifica_firme=True)
            if esito["valido"]:
                print(f"Raccolta valida: {args.directory}")
                print(f"matrice completa: {esito['completa']}")
                return 0
            for problema in esito["problemi"]:
                print(f"ERRORE {problema['codice']}: {problema['messaggio']}", file=sys.stderr)
            return 2
        if args.comando == "audit-finale":
            dati = pubblica_audit_finale(
                args.raccolta,
                args.destinazione,
                richiedi_completezza=not args.consenti_incompleta,
                richiedi_corpus_ufficiale=args.richiedi_corpus_ufficiale,
            )
            print(f"Audit pubblicato: {args.destinazione}")
            print(f"controlli: {dati['controlli_superati']}/{dati['controlli_totali']}")
            print(f"pronto_raccolta_reale: {dati['pronto_raccolta_reale']}")
            return 0 if dati["valido"] else 2
        if args.comando == "confronta-riproducibilita":
            valido, problemi = confronta_raccolte_riproducibili(args.prima, args.seconda)
            if valido:
                print("Raccolte riproducibili: manifesti identici")
                return 0
            for problema in problemi:
                print(f"ERRORE RIPRODUCIBILITA: {problema}", file=sys.stderr)
            return 2
    except (
        ErroreAuditFinale,
        ErroreClassiAppaiate,
        ErroreConfrontoAppaiato,
        ErroreProtocollo,
        ErroreRaccolta,
        ErroreSnapshot,
        ErroreRenderingMarkdown,
        ErroreValidazioneOutput,
        OSError,
        ValueError,
        TypeError,
    ) as errore:
        print(str(errore), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
