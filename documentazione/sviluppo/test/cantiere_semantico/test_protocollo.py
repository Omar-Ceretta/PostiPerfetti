from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from strumenti.cantiere_semantico.protocollo import ErroreProtocollo, carica_protocollo


RADICE = Path(__file__).resolve().parents[4]
ESEMPIO = RADICE / "documentazione" / "sviluppo" / "dati_validazione" / "esempi" / "PROTOCOLLO_MINIMO.json"


def _dati_esempio() -> dict:
    return json.loads(ESEMPIO.read_text(encoding="utf-8"))


def _scrivi(tmp_path: Path, dati: dict) -> Path:
    percorso = tmp_path / "protocollo.json"
    percorso.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
    return percorso


def test_protocollo_minimo_valido():
    protocollo = carica_protocollo(ESEMPIO)
    assert protocollo.strategia == "C1"
    assert len(protocollo.coppie) == 1
    assert len(protocollo.run) == 2
    assert {run.condizione.value for run in protocollo.run} == {
        "senza_fisso",
        "con_fisso",
    }


def test_protocollo_rifiuta_chiavi_sconosciute(tmp_path: Path):
    dati = _dati_esempio()
    dati["campo_legacy"] = True
    with pytest.raises(ErroreProtocollo, match="chiavi sconosciute"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_pair_id_non_canonico(tmp_path: Path):
    dati = _dati_esempio()
    dati["coppie"][0]["pair_id"] = "pair_inventato"
    with pytest.raises(ErroreProtocollo, match="identificatore non canonico"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_run_id_non_canonico(tmp_path: Path):
    dati = _dati_esempio()
    dati["run"][0]["run_id"] = "run_inventato"
    with pytest.raises(ErroreProtocollo, match="identificatore non canonico"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_richiede_la_gemella_del_run(tmp_path: Path):
    dati = _dati_esempio()
    dati["run"] = dati["run"][:1]
    with pytest.raises(ErroreProtocollo, match="appaiamento incompleto"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_run_duplicato(tmp_path: Path):
    dati = _dati_esempio()
    dati["run"].append(copy.deepcopy(dati["run"][0]))
    with pytest.raises(ErroreProtocollo, match="run_id duplicati"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_file_della_condizione_errata(tmp_path: Path):
    dati = _dati_esempio()
    dati["run"][0]["file_classe"] = dati["coppie"][0]["file_con_fisso"]
    with pytest.raises(ErroreProtocollo, match="non coincide"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_versione_non_supportata(tmp_path: Path):
    dati = _dati_esempio()
    dati["versione"] = "9.9"
    with pytest.raises(ErroreProtocollo, match="non supportata"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_rifiuta_tipo_errato_senza_traceback_interno(tmp_path: Path):
    dati = _dati_esempio()
    dati["run"][0]["parametri_ricerca"]["budget_secondi"] = "dieci"
    with pytest.raises(ErroreProtocollo, match="int o float"):
        carica_protocollo(_scrivi(tmp_path, dati))


def test_protocollo_minimo_usa_lo_snapshot_vuoto_canonico():
    from strumenti.cantiere_semantico.snapshot import (
        crea_stato_iniziale_id,
        snapshot_da_file_configurazione,
    )

    snapshot = snapshot_da_file_configurazione(
        RADICE / "documentazione" / "sviluppo" / "dati_validazione" / "esempi" / "STATO_CONFIGURAZIONE_VUOTO.json"
    )
    stato_id = crea_stato_iniziale_id(snapshot)
    protocollo = carica_protocollo(ESEMPIO)
    assert {run.stato_iniziale_id for run in protocollo.run} == {stato_id}
