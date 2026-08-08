"""Ambienti isolati e validazione delle classi appaiate.

Le funzioni lavorano per duck typing: in produzione ricevono una
``ConfigurazioneApp`` già caricata; nei test usano contenitori minimi. Non
chiamano metodi di salvataggio e non importano Qt.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .modelli import CondizioneRun, SnapshotRotazioni, SpecificaCoppiaCorpus, SpecificaRun
from .serializzazione import firma_json_sha256
from .snapshot import crea_snapshot_rotazioni, crea_stato_iniziale_id


class ErroreAmbienteIsolato(ValueError):
    """Segnala una copia non indipendente o uno stato iniziale incoerente."""


class ErroreClassiAppaiate(ValueError):
    """Segnala differenze non autorizzate fra classe base e gemella col FISSO."""


@dataclass(slots=True)
class AmbienteRunIsolato:
    run: SpecificaRun
    config_app: Any
    snapshot: SnapshotRotazioni
    stato_iniziale_id: str
    firma_config_data: str


@dataclass(slots=True)
class AmbientiAppaiati:
    senza_fisso: AmbienteRunIsolato
    con_fisso: AmbienteRunIsolato
    snapshot: SnapshotRotazioni
    stato_iniziale_id: str


@dataclass(frozen=True, slots=True)
class EsitoClassiAppaiate:
    pair_id: str
    studente_fisso: str
    numero_studenti: int
    firma_senza_fisso: str
    firma_con_fisso: str
    differenza_autorizzata: str = "posizione dello studente designato: posizione_base → FISSO"



def _firma_config_data(config_data: Any) -> str:
    if not isinstance(config_data, Mapping):
        raise ErroreAmbienteIsolato("config_app.config_data deve essere un mapping JSON.")
    return firma_json_sha256(config_data)



def _identita_mutabili(valore: Any, visitati: set[int] | None = None) -> set[int]:
    """Raccoglie le identità di contenitori mutabili raggiungibili."""
    if visitati is None:
        visitati = set()
    identificatore = id(valore)
    if identificatore in visitati:
        return set()
    visitati.add(identificatore)

    risultato: set[int] = set()
    if isinstance(valore, dict):
        risultato.add(identificatore)
        for chiave, contenuto in valore.items():
            risultato.update(_identita_mutabili(chiave, visitati))
            risultato.update(_identita_mutabili(contenuto, visitati))
    elif isinstance(valore, list):
        risultato.add(identificatore)
        for elemento in valore:
            risultato.update(_identita_mutabili(elemento, visitati))
    elif isinstance(valore, set):
        risultato.add(identificatore)
        for elemento in valore:
            risultato.update(_identita_mutabili(elemento, visitati))
    elif isinstance(valore, tuple):
        for elemento in valore:
            risultato.update(_identita_mutabili(elemento, visitati))
    return risultato



def _verifica_nessuna_condivisione_mutabile(
    primo: Any,
    secondo: Any,
    descrizione: str,
) -> None:
    condivise = _identita_mutabili(primo).intersection(_identita_mutabili(secondo))
    if condivise:
        raise ErroreAmbienteIsolato(
            f"{descrizione}: rilevati {len(condivise)} contenitori mutabili condivisi."
        )



def _copia_configurazione(config_app_sorgente: Any) -> Any:
    metodo = getattr(config_app_sorgente, "copia_temporanea", None)
    if not callable(metodo):
        raise ErroreAmbienteIsolato(
            "La configurazione sorgente non espone copia_temporanea()."
        )
    copia = metodo()
    if copia is config_app_sorgente:
        raise ErroreAmbienteIsolato("copia_temporanea() ha restituito l'oggetto sorgente.")
    if not hasattr(copia, "config_data"):
        raise ErroreAmbienteIsolato("La copia temporanea non possiede config_data.")
    return copia



def prepara_ambiente_run(
    config_app_sorgente: Any,
    run: SpecificaRun,
    *,
    snapshot: SnapshotRotazioni | None = None,
) -> AmbienteRunIsolato:
    """Crea una copia privata e verifica che rappresenti lo stato dichiarato."""
    if not hasattr(config_app_sorgente, "config_data"):
        raise ErroreAmbienteIsolato("La configurazione sorgente non possiede config_data.")

    snapshot_effettivo = snapshot or crea_snapshot_rotazioni(config_app_sorgente.config_data)
    stato_id = crea_stato_iniziale_id(snapshot_effettivo)
    if run.stato_iniziale_id != stato_id:
        raise ErroreAmbienteIsolato(
            f"{run.run_id}: stato iniziale dichiarato {run.stato_iniziale_id!r}, "
            f"ma lo snapshot effettivo è {stato_id!r}."
        )

    firma_sorgente = _firma_config_data(config_app_sorgente.config_data)
    copia = _copia_configurazione(config_app_sorgente)
    firma_copia = _firma_config_data(copia.config_data)
    if firma_copia != firma_sorgente:
        raise ErroreAmbienteIsolato(
            f"{run.run_id}: la copia temporanea non coincide con lo stato sorgente."
        )
    _verifica_nessuna_condivisione_mutabile(
        config_app_sorgente.config_data,
        copia.config_data,
        f"{run.run_id}: sorgente e copia",
    )

    snapshot_copia = crea_snapshot_rotazioni(copia.config_data)
    if snapshot_copia.sha256 != snapshot_effettivo.sha256:
        raise ErroreAmbienteIsolato(
            f"{run.run_id}: la copia possiede uno snapshot differente dalla sorgente."
        )

    for attributo in (
        "gestore_file_assente",
        "gestore_azzeramento_completato",
    ):
        if hasattr(copia, attributo) and getattr(copia, attributo) is not None:
            raise ErroreAmbienteIsolato(
                f"{run.run_id}: la copia conserva il callback {attributo}."
            )

    return AmbienteRunIsolato(
        run=run,
        config_app=copia,
        snapshot=snapshot_effettivo,
        stato_iniziale_id=stato_id,
        firma_config_data=firma_copia,
    )



def prepara_ambienti_appaiati(
    config_app_sorgente: Any,
    run_senza_fisso: SpecificaRun,
    run_con_fisso: SpecificaRun,
) -> AmbientiAppaiati:
    """Crea due copie indipendenti dello stesso identico stato iniziale."""
    condizioni = {run_senza_fisso.condizione, run_con_fisso.condizione}
    if condizioni != {CondizioneRun.SENZA_FISSO, CondizioneRun.CON_FISSO}:
        raise ErroreAmbienteIsolato(
            "La coppia di run deve contenere una condizione senza_fisso e una con_fisso."
        )
    if run_senza_fisso.condizione != CondizioneRun.SENZA_FISSO:
        run_senza_fisso, run_con_fisso = run_con_fisso, run_senza_fisso
    if run_senza_fisso.chiave_appaiamento() != run_con_fisso.chiave_appaiamento():
        raise ErroreAmbienteIsolato(
            "I due run non condividono tutti i parametri obbligatori dell'appaiamento."
        )

    firma_prima = _firma_config_data(config_app_sorgente.config_data)
    snapshot = crea_snapshot_rotazioni(config_app_sorgente.config_data)
    senza = prepara_ambiente_run(config_app_sorgente, run_senza_fisso, snapshot=snapshot)
    con = prepara_ambiente_run(config_app_sorgente, run_con_fisso, snapshot=snapshot)

    _verifica_nessuna_condivisione_mutabile(
        senza.config_app.config_data,
        con.config_app.config_data,
        "copie dei run appaiati",
    )
    firma_dopo = _firma_config_data(config_app_sorgente.config_data)
    if firma_prima != firma_dopo:
        raise ErroreAmbienteIsolato(
            "La preparazione degli ambienti ha modificato la configurazione sorgente."
        )

    return AmbientiAppaiati(
        senza_fisso=senza,
        con_fisso=con,
        snapshot=snapshot,
        stato_iniziale_id=crea_stato_iniziale_id(snapshot),
    )



def verifica_sorgente_immutata(config_app_sorgente: Any, firma_attesa: str) -> None:
    firma_attuale = _firma_config_data(config_app_sorgente.config_data)
    if firma_attuale != firma_attesa:
        raise ErroreAmbienteIsolato(
            f"La configurazione sorgente è cambiata: {firma_attuale} != {firma_attesa}."
        )



def _studenti_canonici(dati_file: Mapping[str, Any], contesto: str) -> dict[str, dict[str, Any]]:
    studenti_raw = dati_file.get("studenti")
    if isinstance(studenti_raw, (str, bytes)) or not isinstance(studenti_raw, Sequence):
        raise ErroreClassiAppaiate(f"{contesto}: manca la lista validata degli studenti.")
    risultato: dict[str, dict[str, Any]] = {}
    for indice, voce_raw in enumerate(studenti_raw, start=1):
        if not isinstance(voce_raw, Mapping):
            raise ErroreClassiAppaiate(f"{contesto}.studenti[{indice}]: voce non valida.")
        campi = {
            "cognome",
            "nome",
            "sesso",
            "posizione",
            "incompatibilita",
            "affinita",
        }
        mancanti = sorted(campi - set(voce_raw))
        if mancanti:
            raise ErroreClassiAppaiate(
                f"{contesto}.studenti[{indice}]: mancano {', '.join(mancanti)}."
            )
        nome = " ".join(
            f"{str(voce_raw['cognome']).strip()} {str(voce_raw['nome']).strip()}".split()
        )
        if not nome:
            raise ErroreClassiAppaiate(f"{contesto}.studenti[{indice}]: identità vuota.")
        if nome in risultato:
            raise ErroreClassiAppaiate(f"{contesto}: studente duplicato {nome!r}.")
        risultato[nome] = {
            "cognome": str(voce_raw["cognome"]).strip(),
            "nome": str(voce_raw["nome"]).strip(),
            "sesso": str(voce_raw["sesso"]).strip(),
            "posizione": str(voce_raw["posizione"]).strip().upper(),
            "incompatibilita": dict(voce_raw["incompatibilita"]),
            "affinita": dict(voce_raw["affinita"]),
        }
    return risultato



def valida_dati_classi_appaiate(
    specifica: SpecificaCoppiaCorpus,
    dati_senza_fisso: Mapping[str, Any],
    dati_con_fisso: Mapping[str, Any],
) -> EsitoClassiAppaiate:
    """Verifica che l'unica differenza sia la posizione del FISSO designato."""
    senza = _studenti_canonici(dati_senza_fisso, "senza_fisso")
    con = _studenti_canonici(dati_con_fisso, "con_fisso")
    if len(senza) != specifica.numero_studenti or len(con) != specifica.numero_studenti:
        raise ErroreClassiAppaiate(
            f"{specifica.pair_id}: attesi {specifica.numero_studenti} studenti; "
            f"trovati {len(senza)} e {len(con)}."
        )
    if set(senza) != set(con):
        mancanti = sorted(set(senza) - set(con))
        aggiunti = sorted(set(con) - set(senza))
        raise ErroreClassiAppaiate(
            f"{specifica.pair_id}: identità diverse; mancanti={mancanti}, aggiunti={aggiunti}."
        )
    if specifica.studente_fisso not in senza:
        raise ErroreClassiAppaiate(
            f"{specifica.pair_id}: lo studente FISSO {specifica.studente_fisso!r} non esiste."
        )

    differenze: list[str] = []
    for nome in sorted(senza):
        base = senza[nome]
        gemella = con[nome]
        for campo in ("cognome", "nome", "sesso", "incompatibilita", "affinita"):
            if base[campo] != gemella[campo]:
                differenze.append(f"{nome}: campo {campo}")
        if nome == specifica.studente_fisso:
            if base["posizione"] != specifica.posizione_base:
                differenze.append(
                    f"{nome}: posizione base {base['posizione']!r}, "
                    f"attesa {specifica.posizione_base!r}"
                )
            if gemella["posizione"] != "FISSO":
                differenze.append(
                    f"{nome}: posizione gemella {gemella['posizione']!r}, attesa 'FISSO'"
                )
        elif base["posizione"] != gemella["posizione"]:
            differenze.append(f"{nome}: posizione modificata senza autorizzazione")

    fissi_senza = sorted(nome for nome, voce in senza.items() if voce["posizione"] == "FISSO")
    fissi_con = sorted(nome for nome, voce in con.items() if voce["posizione"] == "FISSO")
    if fissi_senza:
        differenze.append(f"classe base contiene già FISSO: {fissi_senza}")
    if fissi_con != [specifica.studente_fisso]:
        differenze.append(f"classe gemella ha FISSO non canonici: {fissi_con}")

    if differenze:
        raise ErroreClassiAppaiate(
            f"{specifica.pair_id}: differenze non autorizzate: " + "; ".join(differenze)
        )

    return EsitoClassiAppaiate(
        pair_id=specifica.pair_id,
        studente_fisso=specifica.studente_fisso,
        numero_studenti=specifica.numero_studenti,
        firma_senza_fisso=firma_json_sha256(senza),
        firma_con_fisso=firma_json_sha256(con),
    )



def _percorso_sicuro(radice: Path, relativo: str) -> Path:
    radice_risolta = radice.resolve()
    percorso = (radice_risolta / relativo).resolve()
    try:
        percorso.relative_to(radice_risolta)
    except ValueError as errore:
        raise ErroreClassiAppaiate(
            f"Il percorso {relativo!r} esce dalla radice del corpus."
        ) from errore
    return percorso



def carica_e_valida_coppia_classi(
    specifica: SpecificaCoppiaCorpus,
    radice_corpus: str | Path,
    *,
    caricatore: Callable[[Path], Mapping[str, Any]] | None = None,
) -> EsitoClassiAppaiate:
    """Carica i due file con il parser produttivo, senza modificarli."""
    if caricatore is None:
        try:
            from moduli.file_classe import carica_file_classe
        except ImportError as errore:
            raise ErroreClassiAppaiate(
                "Impossibile importare moduli.file_classe dal progetto PostiPerfetti."
            ) from errore
        caricatore = carica_file_classe

    radice = Path(radice_corpus)
    percorso_senza = _percorso_sicuro(radice, specifica.file_senza_fisso)
    percorso_con = _percorso_sicuro(radice, specifica.file_con_fisso)
    dati_senza = caricatore(percorso_senza)
    dati_con = caricatore(percorso_con)
    return valida_dati_classi_appaiate(specifica, dati_senza, dati_con)
