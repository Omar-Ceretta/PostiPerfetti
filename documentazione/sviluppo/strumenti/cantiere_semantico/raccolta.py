"""Raccolta protocollare completa degli output semantici — incrementi I9–I10.

Il modulo non modifica C1. Compone una raccolta a partire dagli output di run
I7 già prodotti, li rivalida, genera i confronti I8, le viste CSV, l'indice
globale, la validazione complessiva e il manifesto SHA-256.
"""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .ambiente import EsitoClassiAppaiate, carica_e_valida_coppia_classi
from .confronto_appaiato import (
    costruisci_confronto_appaiato,
    pubblica_confronto_appaiato,
    valida_dati_confronto,
)
from .modelli import ProtocolloRaccolta, SpecificaCoppiaCorpus, SpecificaRun, StatoRun
from .output_run import record_fallimento_da_eccezione, scrivi_fallimento_run
from .rendering_markdown import rendi_rapporto_markdown
from .protocollo import carica_protocollo
from .serializzazione import (
    firma_file_sha256,
    firma_json_sha256,
    leggi_json,
    rendi_json_stabile,
    scrivi_json_atomico,
    scrivi_testo_atomico,
)
from .validazione import valida_dati_annata


class ErroreRaccolta(RuntimeError):
    """Segnala una raccolta illeggibile, incoerente o non pubblicabile."""


@dataclass(frozen=True, slots=True)
class EsitoEsecuzioneMatrice:
    directory_run: str
    run_attesi: int
    run_prodotti: int
    run_falliti: int


@dataclass(frozen=True, slots=True)
class EsitoPubblicazioneRaccolta:
    directory: str
    indice_json: str
    validazione_json: str
    manifesto: str
    run_attesi: int
    run_completi: int
    confronti_validi: int
    completa: bool


def _run_json(run: SpecificaRun) -> dict[str, Any]:
    dati = rendi_json_stabile(run)
    if not isinstance(dati, dict):
        raise ErroreRaccolta("SpecificaRun non serializzabile come oggetto JSON.")
    return dati


def _protocollo_markdown(protocollo: ProtocolloRaccolta) -> str:
    righe = [
        f"# Protocollo della raccolta — {protocollo.titolo}",
        "",
        f"- **protocollo_id:** `{protocollo.protocollo_id}`",
        f"- **versione:** `{protocollo.versione}`",
        f"- **corpus:** `{protocollo.corpus_id}`",
        f"- **osservatore:** `{protocollo.osservatore_id}`",
        f"- **strategia:** `{protocollo.strategia}`",
        f"- **coppie corpus:** {len(protocollo.coppie)}",
        f"- **run attesi:** {len(protocollo.run)}",
        "",
        "## Matrice esplicita dei run",
        "",
        "| run_id | pair_id | condizione | modalità | seed | mesi | genere misto |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for run in protocollo.run:
        righe.append(
            f"| `{run.run_id}` | `{run.pair_id}` | {run.condizione.value} | "
            f"{run.modalita.value} | {run.seed_principale} | {run.numero_mesi} | "
            f"{'sì' if run.genere_misto_attivo else 'no'} |"
        )
    righe.extend([
        "",
        "> Il protocollo elenca tutti i run attesi. Run mancanti, falliti o invalidi "
        "restano visibili nell'indice globale.",
    ])
    return "\n".join(righe) + "\n"


def _firma_appaiamento_run(run: SpecificaRun) -> str:
    return firma_json_sha256({
        "pair_id": run.pair_id,
        "modalita": run.modalita.value,
        "seed_principale": run.seed_principale,
        "numero_mesi": run.numero_mesi,
        "genere_misto_attivo": run.genere_misto_attivo,
        "stato_iniziale_id": run.stato_iniziale_id,
        "parametri_ricerca": run.parametri_ricerca,
        "parametri_aula": run.parametri_aula,
    })


def _verifica_run_atteso(dati: Mapping[str, Any], run: SpecificaRun) -> list[str]:
    problemi: list[str] = []
    run_dati = dati.get("run")
    if not isinstance(run_dati, Mapping):
        return ["ANNATA.json non contiene l'oggetto run."]
    atteso = _run_json(run)
    per_confronto = (
        "run_id", "pair_id", "file_classe", "condizione", "modalita",
        "seed_principale", "numero_mesi", "genere_misto_attivo",
        "stato_iniziale_id", "parametri_ricerca", "parametri_aula",
    )
    for campo in per_confronto:
        if rendi_json_stabile(run_dati.get(campo)) != rendi_json_stabile(atteso.get(campo)):
            problemi.append(f"run.{campo} non coincide col protocollo.")
    return problemi


def _completa_output_run(directory: Path) -> None:
    """Garantisce che un run completo conservi JSON, Markdown e validazione."""
    annata_path = directory / "ANNATA.json"
    if not annata_path.is_file():
        return
    dati = leggi_json(annata_path)
    esito = valida_dati_annata(dati)
    validazione = {
        "run_id": (dati.get("run") or {}).get("run_id"),
        "fase": "rilettura_annata_json_raccolta_i10",
        "valido": esito.valido,
        "problemi": [rendi_json_stabile(p) for p in esito.problemi],
        "numero_errori": sum(p.gravita.value == "errore" for p in esito.problemi),
        "numero_avvisi": sum(p.gravita.value == "avviso" for p in esito.problemi),
    }
    scrivi_json_atomico(directory / "VALIDAZIONE.json", validazione)
    if esito.valido:
        scrivi_testo_atomico(directory / "ANNATA.md", rendi_rapporto_markdown(dati, valida=False))


def _copia_run_sorgente(sorgente: Path, destinazione: Path) -> None:
    if destinazione.exists():
        raise FileExistsError(f"Output run duplicato: {destinazione}")
    shutil.copytree(sorgente, destinazione)
    _completa_output_run(destinazione)


def _voce_run_mancante(run: SpecificaRun) -> dict[str, Any]:
    return {
        **_run_json(run),
        "stato": StatoRun.NON_ESEGUITO.value,
        "mesi_generati": 0,
        "motivo_esito": "Nessun output trovato per il run atteso.",
        "percorso_output": None,
        "sha256_annata_json": None,
        "problemi": [],
    }


def _leggi_run_sorgente(run: SpecificaRun, sorgente: Path) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    annata_path = sorgente / "ANNATA.json"
    fallimento_path = sorgente / "FALLIMENTO.json"
    base = _run_json(run)
    if annata_path.is_file():
        try:
            dati = leggi_json(annata_path)
            esito = valida_dati_annata(dati)
            problemi = [
                f"{p.codice}: {p.messaggio}" for p in esito.problemi
                if p.gravita.value == "errore"
            ]
            problemi.extend(_verifica_run_atteso(dati, run))
            stato_dichiarato = str(dati.get("stato", StatoRun.INVALIDO.value))
            stato = stato_dichiarato if esito.valido and not problemi else StatoRun.INVALIDO.value
            mesi = dati.get("mesi") if isinstance(dati.get("mesi"), list) else []
            voce = {
                **base,
                "stato": stato,
                "mesi_generati": len(mesi),
                "motivo_esito": None if stato == StatoRun.COMPLETO.value else "Output non completo o non valido.",
                "percorso_output": f"run/{run.run_id}",
                "sha256_annata_json": firma_file_sha256(annata_path),
                "problemi": problemi,
            }
            return voce, dati if stato == StatoRun.COMPLETO.value else None
        except Exception as errore:
            return ({
                **base,
                "stato": StatoRun.INVALIDO.value,
                "mesi_generati": 0,
                "motivo_esito": f"ANNATA.json illeggibile: {errore}",
                "percorso_output": f"run/{run.run_id}",
                "sha256_annata_json": None,
                "problemi": [str(errore)],
            }, None)
    if fallimento_path.is_file():
        try:
            dati = leggi_json(fallimento_path)
            stato = str(dati.get("stato", StatoRun.FALLITO.value))
            if stato not in {s.value for s in StatoRun if s != StatoRun.COMPLETO}:
                stato = StatoRun.INVALIDO.value
            return ({
                **base,
                "stato": stato,
                "mesi_generati": int(dati.get("mesi_completati") or 0),
                "motivo_esito": str(dati.get("messaggio") or "Fallimento registrato."),
                "percorso_output": f"run/{run.run_id}",
                "sha256_annata_json": None,
                "problemi": [],
            }, None)
        except Exception as errore:
            return ({
                **base,
                "stato": StatoRun.INVALIDO.value,
                "mesi_generati": 0,
                "motivo_esito": f"FALLIMENTO.json illeggibile: {errore}",
                "percorso_output": f"run/{run.run_id}",
                "sha256_annata_json": None,
                "problemi": [str(errore)],
            }, None)
    return _voce_run_mancante(run), None


def _scrivi_csv(percorso: Path, intestazioni: Sequence[str], righe: Sequence[Mapping[str, Any]]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with open(percorso, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(intestazioni), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for riga in righe:
            writer.writerow({chiave: _valore_csv(riga.get(chiave)) for chiave in intestazioni})


def _valore_csv(valore: Any) -> Any:
    if valore is None:
        return ""
    if isinstance(valore, bool):
        return "true" if valore else "false"
    if isinstance(valore, (list, tuple, dict)):
        import json
        return json.dumps(rendi_json_stabile(valore), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return valore


def _righe_csv_run(indice: Mapping[str, Any]) -> list[dict[str, Any]]:
    risultato = []
    for voce in indice["run"]:
        risultato.append({
            "run_id": voce["run_id"], "pair_id": voce["pair_id"],
            "condizione": voce["condizione"], "modalita": voce["modalita"],
            "seed_principale": voce["seed_principale"], "numero_mesi": voce["numero_mesi"],
            "genere_misto_attivo": voce["genere_misto_attivo"], "stato": voce["stato"],
            "mesi_generati": voce["mesi_generati"], "motivo_esito": voce["motivo_esito"],
            "percorso_output": voce["percorso_output"],
        })
    return risultato


def _righe_csv_annate(annate: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    mesi: list[dict[str, Any]] = []
    adiacenze: list[dict[str, Any]] = []
    studenti: list[dict[str, Any]] = []
    for run_id in sorted(annate):
        annata = annate[run_id]
        run = annata["run"]
        pair_id = run["pair_id"]
        comune = {
            "run_id": run_id, "pair_id": pair_id, "condizione": run["condizione"],
            "modalita": run["modalita"], "seed_principale": run["seed_principale"],
        }
        analisi_genere = {
            int(x["mese"]): x for x in (annata.get("genere_misto") or {}).get("mesi", [])
        }
        for mese in annata["mesi"]:
            r = mese["riepilogo"]
            gm = analisi_genere.get(int(mese["mese_finale"]), {})
            mesi.append({
                **comune, "mese_finale": mese["mese_finale"],
                "posizione_generazione": mese["posizione_generazione"],
                "riusi_totali": r["riusi_totali"], "prime_ripetizioni": r["prime_ripetizioni"],
                "seconde_ripetizioni": r["seconde_ripetizioni"],
                "terze_o_ulteriori": r["terze_o_ulteriori"],
                "incompatibilita_l1": r["incompatibilita_l1"],
                "incompatibilita_l2": r["incompatibilita_l2"],
                "incompatibilita_l3": r["incompatibilita_l3"],
                "affinita_l1": r["affinita_l1"], "affinita_l2": r["affinita_l2"],
                "affinita_l3": r["affinita_l3"],
                "adiacenze_miste_ottenute": gm.get("adiacenze_miste_ottenute", r.get("adiacenze_miste", 0)),
                "massimo_misto_geometrico": (gm.get("massimo_geometrico") or {}).get("valore"),
                "massimo_misto_ammissibile": (gm.get("massimo_ammissibile") or {}).get("valore"),
                "vicino_fisso": (mese.get("vicino_fisso") or {}).get("vicino"),
            })
            for evento in mese["adiacenze"]:
                ultimo = evento.get("ultimo_uso") or {}
                adiacenze.append({
                    **comune, "mese": evento["mese"], "event_id": evento["event_id"],
                    "studente_a": evento["studente_a"], "studente_b": evento["studente_b"],
                    "ruolo": evento["ruolo"], "canale_rotazione": evento["canale_rotazione"],
                    "coinvolge_fisso": evento["coinvolge_fisso"],
                    "incompatibilita_livello": evento["incompatibilita_livello"],
                    "affinita_livello": evento["affinita_livello"],
                    "adiacenza_mista": evento["adiacenza_mista"],
                    "usi_precedenti_totali": evento["usi_precedenti_totali"],
                    "numero_ripetizione": evento["numero_ripetizione"],
                    "ultimo_uso_origine": ultimo.get("origine"),
                    "ultimo_uso_mese": ultimo.get("mese_annata"),
                    "distanza_mesi": evento["distanza_mesi"],
                })
        for studente in annata["studenti"]:
            studenti.append({
                **comune, "studente": studente["studente"], "genere": studente["genere"],
                "posizione": studente["posizione"], "e_fisso": studente["e_fisso"],
                "riusi_coinvolgenti": studente["riusi_coinvolgenti"],
                "prime_ripetizioni": studente["prime_ripetizioni"],
                "seconde_ripetizioni": studente["seconde_ripetizioni"],
                "terze_o_ulteriori": studente["terze_o_ulteriori"],
                "mesi_con_riusi": studente["mesi_con_riusi"],
                "compagni_distinti": studente["compagni_distinti"],
                "incarichi_vicino_fisso": studente["incarichi_vicino_fisso"],
                "mesi_vicino_fisso": studente["mesi_vicino_fisso"],
            })
    return mesi, adiacenze, studenti


def _righe_csv_confronti(confronti: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    righe = []
    for confronto in confronti:
        valori = (confronto.get("annuale") or {}).get("valori", {})
        riga = {
            "confronto_id": confronto["confronto_id"], "pair_id": confronto["pair_id"],
            "run_senza_fisso": confronto["run_senza_fisso"]["run_id"],
            "run_con_fisso": confronto["run_con_fisso"]["run_id"],
            "validita_appaiamento": confronto["validita_appaiamento"],
        }
        for chiave in (
            "riusi_totali", "prime_ripetizioni", "seconde_ripetizioni",
            "terze_o_ulteriori", "incompatibilita_l1", "incompatibilita_l2",
            "affinita_l1", "affinita_l2", "affinita_l3",
            "adiacenze_miste_ottenute",
        ):
            riga[f"delta_{chiave}"] = (valori.get(chiave) or {}).get("delta")
        righe.append(riga)
    return righe


def _manifesto(directory: Path) -> str:
    righe: list[str] = []
    for percorso in sorted(p for p in directory.rglob("*") if p.is_file() and p.name != "MANIFEST_SHA256.txt"):
        relativo = percorso.relative_to(directory).as_posix()
        righe.append(f"{firma_file_sha256(percorso)}  {relativo}")
    return "\n".join(righe) + "\n"


def verifica_manifesto(directory: str | os.PathLike[str]) -> tuple[bool, tuple[str, ...]]:
    radice = Path(directory)
    manifesto = radice / "MANIFEST_SHA256.txt"
    if not manifesto.is_file():
        return False, ("MANIFEST_SHA256.txt assente.",)
    problemi: list[str] = []
    dichiarati: set[str] = set()
    for numero, riga in enumerate(manifesto.read_text(encoding="utf-8").splitlines(), 1):
        if not riga.strip():
            continue
        parti = riga.split("  ", 1)
        if len(parti) != 2:
            problemi.append(f"Riga {numero} del manifesto non valida.")
            continue
        atteso, relativo = parti
        dichiarati.add(relativo)
        percorso = radice / relativo
        if not percorso.is_file():
            problemi.append(f"File dichiarato assente: {relativo}.")
        elif firma_file_sha256(percorso) != atteso:
            problemi.append(f"Firma non coincidente: {relativo}.")
    effettivi = {
        p.relative_to(radice).as_posix() for p in radice.rglob("*")
        if p.is_file() and p.name != "MANIFEST_SHA256.txt"
    }
    for relativo in sorted(effettivi - dichiarati):
        problemi.append(f"File non dichiarato nel manifesto: {relativo}.")
    return not problemi, tuple(problemi)


def valida_raccolta(directory: str | os.PathLike[str], *, verifica_firme: bool = True) -> dict[str, Any]:
    radice = Path(directory)
    problemi: list[dict[str, str]] = []
    avvisi: list[dict[str, str]] = []
    try:
        protocollo = carica_protocollo(radice / "PROTOCOLLO.json")
    except Exception as errore:
        return {"valido": False, "completa": False, "problemi": [{"codice": "PROTOCOLLO", "messaggio": str(errore)}], "avvisi": []}
    try:
        indice = leggi_json(radice / "INDICE_RUN.json")
    except Exception as errore:
        return {"valido": False, "completa": False, "problemi": [{"codice": "INDICE", "messaggio": str(errore)}], "avvisi": []}
    voci = indice.get("run") if isinstance(indice, Mapping) else None
    if not isinstance(voci, list):
        problemi.append({"codice": "INDICE_RUN", "messaggio": "INDICE_RUN.json non contiene la lista run."})
        voci = []
    ids_attesi = [r.run_id for r in protocollo.run]
    ids_indice = [str(v.get("run_id")) for v in voci if isinstance(v, Mapping)]
    if ids_indice != ids_attesi:
        problemi.append({"codice": "MATRICE_RUN", "messaggio": "L'indice non coincide, in ordine e contenuto, col protocollo."})
    for voce in voci:
        if not isinstance(voce, Mapping):
            problemi.append({"codice": "VOCE_RUN", "messaggio": "Voce run non valida."})
            continue
        stato = voce.get("stato")
        run_id = voce.get("run_id")
        if stato == StatoRun.COMPLETO.value:
            directory_run = radice / "run" / str(run_id)
            percorso = directory_run / "ANNATA.json"
            markdown = directory_run / "ANNATA.md"
            validazione_run = directory_run / "VALIDAZIONE.json"
            if not percorso.is_file():
                problemi.append({"codice": "ANNATA_ASSENTE", "messaggio": f"{run_id}: ANNATA.json assente."})
            else:
                dati_annata = leggi_json(percorso)
                esito = valida_dati_annata(dati_annata)
                if not esito.valido:
                    problemi.append({"codice": "ANNATA_INVALIDA", "messaggio": f"{run_id}: ANNATA.json non valido."})
                if not markdown.is_file():
                    problemi.append({"codice": "RAPPORTO_ANNATA_ASSENTE", "messaggio": f"{run_id}: ANNATA.md assente."})
                elif markdown.read_text(encoding="utf-8") != rendi_rapporto_markdown(dati_annata, valida=False):
                    problemi.append({"codice": "RAPPORTO_ANNATA_DIVERGENTE", "messaggio": f"{run_id}: ANNATA.md non deriva dal JSON canonico."})
                if not validazione_run.is_file():
                    problemi.append({"codice": "VALIDAZIONE_RUN_ASSENTE", "messaggio": f"{run_id}: VALIDAZIONE.json assente."})
                else:
                    dati_validazione = leggi_json(validazione_run)
                    if dati_validazione.get("valido") is not True:
                        problemi.append({"codice": "VALIDAZIONE_RUN_NEGATIVA", "messaggio": f"{run_id}: VALIDAZIONE.json non attesta un output valido."})
        elif stato in {StatoRun.NON_ESEGUITO.value, StatoRun.FALLITO.value, StatoRun.PARZIALE.value, StatoRun.ANNULLATO.value}:
            avvisi.append({"codice": "RUN_NON_COMPLETO", "messaggio": f"{run_id}: stato {stato}."})
        elif stato == StatoRun.INVALIDO.value:
            problemi.append({"codice": "RUN_INVALIDO", "messaggio": f"{run_id}: output invalido."})
    for percorso in sorted((radice / "confronti").glob("*/*/CONFRONTO.json")) if (radice / "confronti").is_dir() else []:
        esito = valida_dati_confronto(leggi_json(percorso))
        if not esito.valido:
            problemi.append({"codice": "CONFRONTO_INVALIDO", "messaggio": percorso.relative_to(radice).as_posix()})
    for nome in ("RUN.csv", "MESI.csv", "ADIACENZE.csv", "STUDENTI_ANNATA.csv", "CONFRONTI.csv"):
        if not (radice / "tabelle" / nome).is_file():
            problemi.append({"codice": "CSV_ASSENTE", "messaggio": nome})
    if verifica_firme and (radice / "MANIFEST_SHA256.txt").is_file():
        valido_manifesto, errori_manifesto = verifica_manifesto(radice)
        if not valido_manifesto:
            problemi.extend({"codice": "MANIFESTO", "messaggio": x} for x in errori_manifesto)
    completa = all(v.get("stato") == StatoRun.COMPLETO.value for v in voci if isinstance(v, Mapping)) and len(voci) == len(protocollo.run)
    return {"valido": not problemi, "completa": completa, "problemi": problemi, "avvisi": avvisi}


def _validazione_markdown(dati: Mapping[str, Any]) -> str:
    righe = [
        "# Validazione complessiva della raccolta", "",
        f"- **strutturalmente valida:** {'sì' if dati['valido'] else 'no'}",
        f"- **matrice completa:** {'sì' if dati['completa'] else 'no'}",
        f"- **errori:** {len(dati['problemi'])}",
        f"- **avvisi:** {len(dati['avvisi'])}", "",
    ]
    if dati["problemi"]:
        righe.extend(["## Errori", ""] + [f"- `{p['codice']}` — {p['messaggio']}" for p in dati["problemi"]] + [""])
    if dati["avvisi"]:
        righe.extend(["## Avvisi", ""] + [f"- `{p['codice']}` — {p['messaggio']}" for p in dati["avvisi"]] + [""])
    if not dati["problemi"] and not dati["avvisi"]:
        righe.append("Nessun problema rilevato.")
    return "\n".join(righe) + "\n"



def esegui_matrice_protocollo(
    protocollo: ProtocolloRaccolta | str | os.PathLike[str],
    directory_run: str | os.PathLike[str],
    esecutore: Callable[[SpecificaRun, Path], None],
    *,
    consenti_sostituzione: bool = False,
) -> EsitoEsecuzioneMatrice:
    """Esegue in ordine tutti i run espliciti del protocollo.

    ``esecutore`` riceve la specifica e la directory finale del run e deve
    pubblicarvi ANNATA.json (normalmente tramite ``pubblica_output_run``).
    Ogni eccezione viene convertita in FALLIMENTO.json; l'esecuzione prosegue.
    """
    if not isinstance(protocollo, ProtocolloRaccolta):
        protocollo = carica_protocollo(protocollo)
    radice = Path(directory_run)
    radice.mkdir(parents=True, exist_ok=True)
    prodotti = falliti = 0
    for run in protocollo.run:
        destinazione = radice / run.run_id
        if destinazione.exists():
            if not consenti_sostituzione:
                raise FileExistsError(f"Output run già esistente: {destinazione}")
            shutil.rmtree(destinazione)
        try:
            esecutore(run, destinazione)
            if not (destinazione / "ANNATA.json").is_file():
                raise ErroreRaccolta(
                    f"{run.run_id}: l'esecutore non ha pubblicato ANNATA.json."
                )
            esito = valida_dati_annata(leggi_json(destinazione / "ANNATA.json"))
            if not esito.valido:
                raise ErroreRaccolta(f"{run.run_id}: ANNATA.json prodotto non valido.")
            prodotti += 1
        except Exception as errore:
            shutil.rmtree(destinazione, ignore_errors=True)
            record = record_fallimento_da_eccezione(
                run, fase="esecuzione_matrice_i9", errore=errore
            )
            scrivi_fallimento_run(destinazione, record)
            falliti += 1
    return EsitoEsecuzioneMatrice(
        directory_run=os.fspath(radice),
        run_attesi=len(protocollo.run),
        run_prodotti=prodotti,
        run_falliti=falliti,
    )

def pubblica_raccolta_da_output(
    protocollo: ProtocolloRaccolta | str | os.PathLike[str],
    radice_output_run: str | os.PathLike[str],
    radice_corpus: str | os.PathLike[str],
    destinazione: str | os.PathLike[str],
    *,
    attestatore: Callable[[SpecificaCoppiaCorpus, str | os.PathLike[str]], EsitoClassiAppaiate] | None = None,
    consenti_sostituzione: bool = False,
) -> EsitoPubblicazioneRaccolta:
    """Compone e pubblica l'intera raccolta a partire dagli output I7/I8 dei run."""
    if not isinstance(protocollo, ProtocolloRaccolta):
        protocollo = carica_protocollo(protocollo)
    sorgente = Path(radice_output_run)
    destinazione = Path(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if destinazione.exists() and not consenti_sostituzione:
        raise FileExistsError(f"La raccolta esiste già: {destinazione}")
    temporanea = Path(tempfile.mkdtemp(prefix=f".{destinazione.name}.", dir=destinazione.parent))
    backup: Path | None = None
    attestatore = attestatore or carica_e_valida_coppia_classi
    try:
        scrivi_json_atomico(temporanea / "PROTOCOLLO.json", protocollo)
        scrivi_testo_atomico(temporanea / "PROTOCOLLO.md", _protocollo_markdown(protocollo))
        (temporanea / "run").mkdir()
        voci: list[dict[str, Any]] = []
        annate: dict[str, Mapping[str, Any]] = {}
        for run in protocollo.run:
            src = sorgente / run.run_id
            if src.is_dir():
                _copia_run_sorgente(src, temporanea / "run" / run.run_id)
                voce, annata = _leggi_run_sorgente(run, src)
            else:
                voce, annata = _voce_run_mancante(run), None
            voci.append(voce)
            if annata is not None:
                annate[run.run_id] = annata

        conteggi = Counter(voce["stato"] for voce in voci)
        indice = {
            "protocollo_id": protocollo.protocollo_id,
            "run_attesi": len(protocollo.run),
            "run_eseguiti": sum(v["stato"] != StatoRun.NON_ESEGUITO.value for v in voci),
            "run_completi": conteggi[StatoRun.COMPLETO.value],
            "run_parziali": conteggi[StatoRun.PARZIALE.value],
            "run_falliti": conteggi[StatoRun.FALLITO.value],
            "run_annullati": conteggi[StatoRun.ANNULLATO.value],
            "run_non_eseguiti": conteggi[StatoRun.NON_ESEGUITO.value],
            "run_invalidi": conteggi[StatoRun.INVALIDO.value],
            "completa": conteggi[StatoRun.COMPLETO.value] == len(protocollo.run),
            "run": voci,
        }
        scrivi_json_atomico(temporanea / "INDICE_RUN.json", indice)

        confronti: list[Mapping[str, Any]] = []
        coppie = {c.pair_id: c for c in protocollo.coppie}
        gruppi: dict[str, list[SpecificaRun]] = defaultdict(list)
        for run in protocollo.run:
            gruppi[_firma_appaiamento_run(run)].append(run)
        for gruppo in gruppi.values():
            if len(gruppo) != 2 or {r.condizione.value for r in gruppo} != {"senza_fisso", "con_fisso"}:
                continue
            senza = next(r for r in gruppo if r.condizione.value == "senza_fisso")
            con = next(r for r in gruppo if r.condizione.value == "con_fisso")
            if senza.run_id not in annate or con.run_id not in annate:
                continue
            attestazione = None
            try:
                attestazione = attestatore(coppie[senza.pair_id], radice_corpus)
            except Exception:
                attestazione = None
            confronto = costruisci_confronto_appaiato(annate[senza.run_id], annate[con.run_id], attestazione_classi=attestazione)
            dest = temporanea / "confronti" / senza.pair_id / confronto.confronto_id
            pubblica_confronto_appaiato(confronto, dest)
            dati_confronto = leggi_json(dest / "CONFRONTO.json")
            confronti.append(dati_confronto)

        tabelle = temporanea / "tabelle"
        _scrivi_csv(tabelle / "RUN.csv", (
            "run_id", "pair_id", "condizione", "modalita", "seed_principale", "numero_mesi",
            "genere_misto_attivo", "stato", "mesi_generati", "motivo_esito", "percorso_output",
        ), _righe_csv_run(indice))
        righe_mesi, righe_adiacenze, righe_studenti = _righe_csv_annate(annate)
        _scrivi_csv(tabelle / "MESI.csv", (
            "run_id", "pair_id", "condizione", "modalita", "seed_principale", "mese_finale",
            "posizione_generazione", "riusi_totali", "prime_ripetizioni", "seconde_ripetizioni",
            "terze_o_ulteriori", "incompatibilita_l1", "incompatibilita_l2", "incompatibilita_l3",
            "affinita_l1", "affinita_l2", "affinita_l3", "adiacenze_miste_ottenute",
            "massimo_misto_geometrico", "massimo_misto_ammissibile", "vicino_fisso",
        ), righe_mesi)
        _scrivi_csv(tabelle / "ADIACENZE.csv", (
            "run_id", "pair_id", "condizione", "modalita", "seed_principale", "mese", "event_id",
            "studente_a", "studente_b", "ruolo", "canale_rotazione", "coinvolge_fisso",
            "incompatibilita_livello", "affinita_livello", "adiacenza_mista",
            "usi_precedenti_totali", "numero_ripetizione", "ultimo_uso_origine",
            "ultimo_uso_mese", "distanza_mesi",
        ), righe_adiacenze)
        _scrivi_csv(tabelle / "STUDENTI_ANNATA.csv", (
            "run_id", "pair_id", "condizione", "modalita", "seed_principale", "studente", "genere",
            "posizione", "e_fisso", "riusi_coinvolgenti", "prime_ripetizioni", "seconde_ripetizioni",
            "terze_o_ulteriori", "mesi_con_riusi", "compagni_distinti", "incarichi_vicino_fisso",
            "mesi_vicino_fisso",
        ), righe_studenti)
        _scrivi_csv(tabelle / "CONFRONTI.csv", (
            "confronto_id", "pair_id", "run_senza_fisso", "run_con_fisso", "validita_appaiamento",
            "delta_riusi_totali", "delta_prime_ripetizioni", "delta_seconde_ripetizioni",
            "delta_terze_o_ulteriori", "delta_incompatibilita_l1", "delta_incompatibilita_l2",
            "delta_affinita_l1", "delta_affinita_l2", "delta_affinita_l3",
            "delta_adiacenze_miste_ottenute",
        ), _righe_csv_confronti(confronti))

        validazione = valida_raccolta(temporanea, verifica_firme=False)
        validazione["protocollo_id"] = protocollo.protocollo_id
        validazione["confronti_prodotti"] = len(confronti)
        validazione["confronti_validi"] = sum(bool(c.get("validita_appaiamento")) for c in confronti)
        validazione["righe_csv"] = {
            "run": len(voci), "mesi": len(righe_mesi), "adiacenze": len(righe_adiacenze),
            "studenti_annata": len(righe_studenti), "confronti": len(confronti),
        }
        scrivi_json_atomico(temporanea / "VALIDAZIONE_OUTPUT.json", validazione)
        scrivi_testo_atomico(temporanea / "VALIDAZIONE_OUTPUT.md", _validazione_markdown(validazione))
        scrivi_testo_atomico(temporanea / "MANIFEST_SHA256.txt", _manifesto(temporanea))
        ok_manifesto, problemi_manifesto = verifica_manifesto(temporanea)
        if not ok_manifesto:
            raise ErroreRaccolta("Manifesto appena creato non valido: " + "; ".join(problemi_manifesto))
        if not validazione["valido"]:
            raise ErroreRaccolta("La raccolta non supera la validazione strutturale.")

        if destinazione.exists():
            backup = destinazione.with_name(f".{destinazione.name}.backup")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destinazione, backup)
        os.replace(temporanea, destinazione)
        if backup is not None:
            shutil.rmtree(backup)
        return EsitoPubblicazioneRaccolta(
            directory=os.fspath(destinazione),
            indice_json=os.fspath(destinazione / "INDICE_RUN.json"),
            validazione_json=os.fspath(destinazione / "VALIDAZIONE_OUTPUT.json"),
            manifesto=os.fspath(destinazione / "MANIFEST_SHA256.txt"),
            run_attesi=len(protocollo.run),
            run_completi=conteggi[StatoRun.COMPLETO.value],
            confronti_validi=sum(bool(c.get("validita_appaiamento")) for c in confronti),
            completa=bool(indice["completa"]),
        )
    except Exception:
        shutil.rmtree(temporanea, ignore_errors=True)
        if backup is not None and backup.exists() and not destinazione.exists():
            os.replace(backup, destinazione)
        raise


__all__ = [
    "ErroreRaccolta", "EsitoEsecuzioneMatrice", "EsitoPubblicazioneRaccolta",
    "esegui_matrice_protocollo", "pubblica_raccolta_da_output", "valida_raccolta", "verifica_manifesto",
]
