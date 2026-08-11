"""Audit finale dell'osservatore semantico annuale — incremento I10.

Il modulo non esegue né modifica C1. Verifica una raccolta già pubblicata,
controlla la conformità strutturale al contratto R0.1, confronta due raccolte
per la riproducibilità e firma l'albero dei moduli produttivi.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .protocollo import carica_protocollo
from .raccolta import valida_raccolta, verifica_manifesto
from .rendering_markdown import rendi_rapporto_markdown
from .serializzazione import (
    firma_file_sha256,
    firma_json_sha256,
    leggi_json,
    scrivi_json_atomico,
    scrivi_testo_atomico,
)
from .validazione import valida_dati_annata


class ErroreAuditFinale(RuntimeError):
    """Segnala un audit illeggibile o non pubblicabile."""


@dataclass(frozen=True, slots=True)
class ControlloAudit:
    codice: str
    descrizione: str
    superato: bool
    gravita: str = "errore"
    dettagli: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.gravita not in {"errore", "avviso"}:
            raise ValueError("gravita deve essere 'errore' o 'avviso'.")


_CAMPI_EVENTO = {
    "studente_a", "studente_b", "mese", "group_id", "ruolo",
    "canale_rotazione", "coinvolge_fisso", "incompatibilita_livello",
    "affinita_livello", "adiacenza_mista", "usi_precedenti_totali",
    "usi_precedenti_nell_annata", "e_riuso", "numero_ripetizione",
    "fascia_ripetizione", "ultimo_uso", "distanza_mesi",
}
_CAMPI_STUDENTE = {
    "studente", "genere", "posizione", "e_fisso", "riusi_coinvolgenti",
    "prime_ripetizioni", "seconde_ripetizioni", "terze_o_ulteriori",
    "mesi_con_riusi", "compagni_distinti", "incarichi_vicino_fisso",
    "mesi_vicino_fisso",
}
_CAMPI_RIEPILOGO = {
    "riusi_totali", "prime_ripetizioni", "seconde_ripetizioni",
    "terze_o_ulteriori", "incompatibilita_l1", "incompatibilita_l2",
    "incompatibilita_l3", "affinita_l1", "affinita_l2", "affinita_l3",
    "adiacenze_miste",
}
_CAMPI_GENERE_MESE = {
    "mese", "adiacenze_miste_ottenute", "adiacenze_stesso_genere",
    "massimo_geometrico", "massimo_ammissibile", "gruppi_non_pienamente_misti",
}
_OUTPUT_CSV = {
    "RUN.csv", "MESI.csv", "ADIACENZE.csv", "STUDENTI_ANNATA.csv",
    "CONFRONTI.csv",
}
_CHIAVI_PEDAGOGICHE_VIETATE = {
    "voto_annata", "giudizio_pedagogico", "indice_equita",
    "qualita_pedagogica", "classifica_annata",
}


def _controllo(codice: str, descrizione: str, superato: bool, *dettagli: str, gravita: str = "errore") -> ControlloAudit:
    return ControlloAudit(codice, descrizione, bool(superato), gravita, tuple(str(x) for x in dettagli if str(x)))


def _chiavi_ricorsive(valore: Any) -> set[str]:
    risultato: set[str] = set()
    if isinstance(valore, Mapping):
        for chiave, sotto in valore.items():
            risultato.add(str(chiave))
            risultato.update(_chiavi_ricorsive(sotto))
    elif isinstance(valore, list):
        for sotto in valore:
            risultato.update(_chiavi_ricorsive(sotto))
    return risultato


def firma_albero_produzione(radice_progetto: str | os.PathLike[str]) -> dict[str, str]:
    """Firma postiperfetti.py e tutti i moduli Python produttivi."""
    radice = Path(radice_progetto)
    percorsi: list[Path] = []
    principale = radice / "postiperfetti.py"
    if principale.is_file():
        percorsi.append(principale)
    moduli = radice / "moduli"
    if not moduli.is_dir():
        raise ErroreAuditFinale(f"Cartella moduli assente: {moduli}")
    percorsi.extend(sorted(moduli.rglob("*.py")))
    if not percorsi:
        raise ErroreAuditFinale("Nessun file produttivo trovato.")
    return {
        percorso.relative_to(radice).as_posix(): firma_file_sha256(percorso)
        for percorso in percorsi
    }


def confronta_firme_produzione(prima: Mapping[str, str], dopo: Mapping[str, str]) -> tuple[bool, tuple[str, ...]]:
    problemi: list[str] = []
    chiavi = sorted(set(prima) | set(dopo))
    for chiave in chiavi:
        if chiave not in prima:
            problemi.append(f"File produttivo aggiunto: {chiave}")
        elif chiave not in dopo:
            problemi.append(f"File produttivo rimosso: {chiave}")
        elif prima[chiave] != dopo[chiave]:
            problemi.append(f"File produttivo modificato: {chiave}")
    return not problemi, tuple(problemi)


def confronta_raccolte_riproducibili(prima: str | os.PathLike[str], seconda: str | os.PathLike[str]) -> tuple[bool, tuple[str, ...]]:
    """Confronta due raccolte attraverso tutti i file dichiarati nei manifesti."""
    a, b = Path(prima), Path(seconda)
    problemi: list[str] = []
    for radice, nome in ((a, "prima"), (b, "seconda")):
        valido, errori = verifica_manifesto(radice)
        if not valido:
            problemi.extend(f"{nome}: {errore}" for errore in errori)
    if problemi:
        return False, tuple(problemi)
    manifest_a = (a / "MANIFEST_SHA256.txt").read_text(encoding="utf-8")
    manifest_b = (b / "MANIFEST_SHA256.txt").read_text(encoding="utf-8")
    if manifest_a != manifest_b:
        problemi.append("I manifesti delle due raccolte non coincidono byte per byte.")
    return not problemi, tuple(problemi)


def _controlla_annata(percorso: Path) -> tuple[list[ControlloAudit], Mapping[str, Any] | None]:
    controlli: list[ControlloAudit] = []
    try:
        dati = leggi_json(percorso)
    except Exception as errore:
        return [_controllo("ANNATA_LEGGIBILE", "ANNATA.json leggibile", False, str(errore))], None
    esito = valida_dati_annata(dati)
    controlli.append(_controllo(
        "ANNATA_VALIDA", "ANNATA.json supera la validazione autonoma", esito.valido,
        *[f"{p.codice}: {p.messaggio}" for p in esito.problemi if p.gravita.value == "errore"],
    ))
    mesi = dati.get("mesi") if isinstance(dati, Mapping) else None
    eventi = [evento for mese in (mesi or []) if isinstance(mese, Mapping) for evento in (mese.get("adiacenze") or []) if isinstance(evento, Mapping)]
    mancanti_evento = sorted({campo for evento in eventi for campo in (_CAMPI_EVENTO - set(evento))})
    controlli.append(_controllo(
        "EVENTI_COMPLETI", "Gli eventi conservano identità, ruolo, livelli e cronologia", bool(eventi) and not mancanti_evento,
        *(f"Campo evento assente: {x}" for x in mancanti_evento),
    ))
    studenti = dati.get("studenti") if isinstance(dati.get("studenti"), list) else []
    mancanti_studente = sorted({campo for studente in studenti if isinstance(studente, Mapping) for campo in (_CAMPI_STUDENTE - set(studente))})
    controlli.append(_controllo(
        "STUDENTI_COMPLETI", "Il riepilogo per studente espone distribuzione dei riusi e FISSO", bool(studenti) and not mancanti_studente,
        *(f"Campo studente assente: {x}" for x in mancanti_studente),
    ))
    riepilogo = dati.get("riepilogo") if isinstance(dati.get("riepilogo"), Mapping) else {}
    mancanti_riepilogo = sorted(_CAMPI_RIEPILOGO - set(riepilogo))
    controlli.append(_controllo(
        "LIVELLI_SEPARATI", "Incompatibilità e affinità restano separate per livello", not mancanti_riepilogo,
        *(f"Campo riepilogo assente: {x}" for x in mancanti_riepilogo),
    ))
    genere = dati.get("genere_misto") if isinstance(dati.get("genere_misto"), Mapping) else {}
    analisi_mesi = genere.get("mesi") if isinstance(genere.get("mesi"), list) else []
    mancanti_genere = sorted({campo for mese in analisi_mesi if isinstance(mese, Mapping) for campo in (_CAMPI_GENERE_MESE - set(mese))})
    esatti = all(
        isinstance(mese, Mapping)
        and isinstance(mese.get("massimo_geometrico"), Mapping)
        and mese["massimo_geometrico"].get("esatto") is True
        and isinstance(mese.get("massimo_ammissibile"), Mapping)
        and mese["massimo_ammissibile"].get("esatto") is True
        for mese in analisi_mesi
    )
    controlli.append(_controllo(
        "GENERE_MISTO", "Flag, massimi esatti e risultato ottenuto sono presenti", bool(analisi_mesi) and not mancanti_genere and esatti,
        *(f"Campo genere assente: {x}" for x in mancanti_genere),
    ))
    ordine_ok = all(
        isinstance(mese, Mapping)
        and isinstance(mese.get("posizione_generazione"), int)
        and isinstance(mese.get("posizione_finale"), int)
        for mese in (mesi or [])
    )
    controlli.append(_controllo("TRACCIA_RIORDINO", "Ordine di generazione e ordine finale sono entrambi conservati", ordine_ok))
    run = dati.get("run") if isinstance(dati.get("run"), Mapping) else {}
    if run.get("condizione") == "con_fisso":
        fisso_ok = bool(dati.get("studente_fisso")) and all("vicino_fisso" in mese for mese in (mesi or []) if isinstance(mese, Mapping))
        controlli.append(_controllo("FISSO", "Cronologia e ruolo del vicino del FISSO sono osservabili", fisso_ok))
    vietate = sorted(_CHIAVI_PEDAGOGICHE_VIETATE & _chiavi_ricorsive(dati))
    controlli.append(_controllo(
        "NESSUN_GIUDIZIO_OPACO", "Non sono introdotti voti o indici pedagogici automatici", not vietate,
        *(f"Chiave vietata: {x}" for x in vietate),
    ))
    return controlli, dati


def audita_raccolta(
    directory: str | os.PathLike[str],
    *,
    richiedi_completezza: bool = True,
    richiedi_corpus_ufficiale: bool = False,
) -> dict[str, Any]:
    """Esegue l'audit contrattuale R0.1 su una raccolta pubblicata."""
    radice = Path(directory)
    controlli: list[ControlloAudit] = []
    validazione = valida_raccolta(radice, verifica_firme=True)
    controlli.append(_controllo(
        "RACCOLTA_STRUTTURALE", "La raccolta supera la validazione I9/I10", validazione.get("valido") is True,
        *[f"{p.get('codice')}: {p.get('messaggio')}" for p in validazione.get("problemi", [])],
    ))
    manifesto_valido, errori_manifesto = verifica_manifesto(radice)
    controlli.append(_controllo("MANIFESTO", "Il manifesto SHA-256 copre tutti i file", manifesto_valido, *errori_manifesto))
    output_base = {
        "PROTOCOLLO.json", "PROTOCOLLO.md", "INDICE_RUN.json",
        "VALIDAZIONE_OUTPUT.json", "VALIDAZIONE_OUTPUT.md", "MANIFEST_SHA256.txt",
    }
    mancanti_base = sorted(nome for nome in output_base if not (radice / nome).is_file())
    mancanti_csv = sorted(nome for nome in _OUTPUT_CSV if not (radice / "tabelle" / nome).is_file())
    controlli.append(_controllo(
        "OUTPUT_O1_O2_O5_O7", "Protocollo, indice, CSV, validazione e manifesto sono presenti",
        not mancanti_base and not mancanti_csv,
        *(f"Assente: {x}" for x in mancanti_base + [f"tabelle/{x}" for x in mancanti_csv]),
    ))
    try:
        protocollo = carica_protocollo(radice / "PROTOCOLLO.json")
    except Exception as errore:
        protocollo = None
        controlli.append(_controllo("PROTOCOLLO_R0_1", "Protocollo C1 leggibile e versionato", False, str(errore)))
    else:
        controlli.append(_controllo(
            "PROTOCOLLO_R0_1", "Protocollo C1 leggibile e versionato",
            protocollo.strategia == "C1" and bool(protocollo.versione),
        ))
        if richiedi_corpus_ufficiale:
            condizioni_per_pair: dict[str, set[str]] = {}
            for run in protocollo.run:
                condizioni_per_pair.setdefault(run.pair_id, set()).add(run.condizione.value)
            copertura_appaiata = (
                len(condizioni_per_pair) == 19
                and all(v == {"senza_fisso", "con_fisso"} for v in condizioni_per_pair.values())
            )
            controlli.append(_controllo(
                "CORPUS_UFFICIALE", "Il protocollo copre le 19 coppie ufficiali e 38 run appaiati",
                protocollo.corpus_id == "PostiPerfetti_CantiereSemantico_R0"
                and protocollo.richiede_appaiamento_completo is True
                and len(protocollo.coppie) == 19
                and len(protocollo.run) == 38
                and copertura_appaiata,
                f"corpus_id={protocollo.corpus_id}",
                f"coppie={len(protocollo.coppie)}", f"run={len(protocollo.run)}",
            ))
    indice = {}
    try:
        indice = leggi_json(radice / "INDICE_RUN.json")
    except Exception:
        pass
    voci = indice.get("run") if isinstance(indice, Mapping) and isinstance(indice.get("run"), list) else []
    complete = [voce for voce in voci if isinstance(voce, Mapping) and voce.get("stato") == "completo"]
    if richiedi_completezza:
        controlli.append(_controllo(
            "MATRICE_COMPLETA", "Tutti i run espliciti sono completi", validazione.get("completa") is True,
            f"run completi={len(complete)}/{len(voci)}",
        ))
    else:
        controlli.append(_controllo(
            "MATRICE_DICHIARATA", "La completezza o incompletezza è dichiarata senza occultamenti", isinstance(validazione.get("completa"), bool),
            gravita="avviso",
        ))
    for voce in complete:
        run_id = str(voce.get("run_id"))
        run_dir = radice / "run" / run_id
        annata = run_dir / "ANNATA.json"
        md = run_dir / "ANNATA.md"
        val = run_dir / "VALIDAZIONE.json"
        controlli.append(_controllo(
            f"OUTPUT_RUN_{run_id}", "Il run completo contiene JSON, Markdown e validazione",
            annata.is_file() and md.is_file() and val.is_file(),
        ))
        if annata.is_file():
            sotto, dati = _controlla_annata(annata)
            controlli.extend(sotto)
            if dati is not None and md.is_file():
                atteso = rendi_rapporto_markdown(dati, valida=False)
                controlli.append(_controllo(
                    f"RENDER_{run_id}", "ANNATA.md deriva esattamente dal JSON canonico",
                    md.read_text(encoding="utf-8") == atteso,
                ))
    confronti = sorted((radice / "confronti").glob("*/*/CONFRONTO.json")) if (radice / "confronti").is_dir() else []
    confronti_completi = all(
        (p.parent / "CONFRONTO.md").is_file() and (p.parent / "VALIDAZIONE.json").is_file()
        for p in confronti
    )
    attesi_confronti = 0
    if protocollo is not None and complete:
        gruppi: dict[str, set[str]] = {}
        for run in protocollo.run:
            firma = firma_json_sha256({
                "pair_id": run.pair_id,
                "modalita": run.modalita.value,
                "seed_principale": run.seed_principale,
                "numero_mesi": run.numero_mesi,
                "genere_misto_attivo": run.genere_misto_attivo,
                "stato_iniziale_id": run.stato_iniziale_id,
                "parametri_ricerca": run.parametri_ricerca,
                "parametri_aula": run.parametri_aula,
            })
            gruppi.setdefault(firma, set()).add(run.condizione.value)
        attesi_confronti = sum(v == {"senza_fisso", "con_fisso"} for v in gruppi.values())
    controlli.append(_controllo(
        "OUTPUT_O6", "I confronti appaiati hanno JSON, Markdown e validazione",
        confronti_completi and (not validazione.get("completa") or len(confronti) == attesi_confronti),
        f"confronti prodotti={len(confronti)}", f"attesi={attesi_confronti}",
    ))
    errori = [c for c in controlli if not c.superato and c.gravita == "errore"]
    avvisi = [c for c in controlli if not c.superato and c.gravita == "avviso"]
    valido = not errori
    pronto = valido and validazione.get("completa") is True
    return {
        "contratto": "R0.1",
        "valido": valido,
        "pronto_raccolta_reale": pronto,
        "richiede_completezza": richiedi_completezza,
        "richiede_corpus_ufficiale": richiedi_corpus_ufficiale,
        "controlli_superati": sum(c.superato for c in controlli),
        "controlli_totali": len(controlli),
        "numero_errori": len(errori),
        "numero_avvisi": len(avvisi),
        "controlli": [
            {
                "codice": c.codice,
                "descrizione": c.descrizione,
                "superato": c.superato,
                "gravita": c.gravita,
                "dettagli": list(c.dettagli),
            }
            for c in controlli
        ],
    }


def rendi_audit_markdown(dati: Mapping[str, Any]) -> str:
    righe = [
        "# Audit finale dell’osservatore semantico", "",
        f"- **contratto:** `{dati.get('contratto')}`",
        f"- **audit valido:** {'sì' if dati.get('valido') else 'no'}",
        f"- **pronto per la raccolta reale:** {'sì' if dati.get('pronto_raccolta_reale') else 'no'}",
        f"- **controlli superati:** {dati.get('controlli_superati')}/{dati.get('controlli_totali')}",
        f"- **errori:** {dati.get('numero_errori')}",
        f"- **avvisi:** {dati.get('numero_avvisi')}", "",
        "## Controlli", "",
        "| Esito | Codice | Controllo |", "|---|---|---|",
    ]
    for controllo in dati.get("controlli", []):
        esito = "OK" if controllo.get("superato") else ("AVVISO" if controllo.get("gravita") == "avviso" else "ERRORE")
        righe.append(f"| {esito} | `{controllo.get('codice')}` | {controllo.get('descrizione')} |")
        for dettaglio in controllo.get("dettagli") or []:
            righe.append(f"|  |  | {dettaglio} |")
    return "\n".join(righe) + "\n"


def pubblica_audit_finale(
    raccolta: str | os.PathLike[str],
    destinazione: str | os.PathLike[str],
    *,
    richiedi_completezza: bool = True,
    richiedi_corpus_ufficiale: bool = False,
) -> dict[str, Any]:
    destinazione = Path(destinazione)
    destinazione.mkdir(parents=True, exist_ok=False)
    dati = audita_raccolta(
        raccolta,
        richiedi_completezza=richiedi_completezza,
        richiedi_corpus_ufficiale=richiedi_corpus_ufficiale,
    )
    scrivi_json_atomico(destinazione / "AUDIT_FINALE.json", dati)
    scrivi_testo_atomico(destinazione / "AUDIT_FINALE.md", rendi_audit_markdown(dati))
    return dati


__all__ = [
    "ErroreAuditFinale", "ControlloAudit", "audita_raccolta",
    "pubblica_audit_finale", "rendi_audit_markdown",
    "firma_albero_produzione", "confronta_firme_produzione",
    "confronta_raccolte_riproducibili",
]
