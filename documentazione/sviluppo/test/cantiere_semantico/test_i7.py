from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from strumenti.cantiere_semantico.cli import main
from strumenti.cantiere_semantico.modelli import StatoRun
from strumenti.cantiere_semantico.output_run import (
    pubblica_output_run,
    record_fallimento_da_eccezione,
    scrivi_fallimento_run,
)
from strumenti.cantiere_semantico.rendering_markdown import (
    ErroreRenderingMarkdown,
    rendi_rapporto_markdown,
)
from strumenti.cantiere_semantico.serializzazione import leggi_json, rendi_json_stabile, scrivi_json_atomico
from strumenti.cantiere_semantico.validazione import valida_annata, valida_dati_annata

from .test_i6 import _annata_sintetica


def _dati_validi():
    return rendi_json_stabile(_annata_sintetica(flag=True))


def test_annata_i7_valida_in_memoria_e_da_json():
    annata = _annata_sintetica(flag=True)
    assert annata.versioni.osservatore == "1.0.0"
    assert valida_annata(annata).valido is True
    assert valida_dati_annata(rendi_json_stabile(annata)).valido is True


def test_validatore_rifiuta_un_totale_mensile_manomesso():
    dati = deepcopy(_dati_validi())
    dati["mesi"][0]["riepilogo"]["riusi_totali"] += 1
    esito = valida_dati_annata(dati)
    assert esito.valido is False
    assert "RIEPILOGO_MENSILE_INCOERENTE" in {p.codice for p in esito.problemi}


def test_validatore_rifiuta_studente_duplicato_e_mancante():
    dati = deepcopy(_dati_validi())
    dati["mesi"][0]["gruppi"][0]["membri_ordinati"][1] = dati["mesi"][0]["gruppi"][0]["membri_ordinati"][0]
    esito = valida_dati_annata(dati)
    codici = {p.codice for p in esito.problemi}
    assert esito.valido is False
    assert "GRUPPO_DUPLICATO_INTERNO" in codici
    assert "STUDENTI_MANCANTI" in codici


def test_validatore_rifiuta_l3_anche_con_totali_manomessi():
    dati = deepcopy(_dati_validi())
    evento = dati["mesi"][0]["adiacenze"][0]
    evento["incompatibilita_livello"] = 3
    evento["affinita_livello"] = 0
    dati["mesi"][0]["riepilogo"]["incompatibilita_l3"] = 1
    dati["riepilogo"]["incompatibilita_l3"] = 1
    esito = valida_dati_annata(dati)
    assert esito.valido is False
    assert "INCOMPATIBILITA_L3" in {p.codice for p in esito.problemi}
    assert "RIEPILOGO_L3" in {p.codice for p in esito.problemi}


def test_validatore_rifiuta_cronologia_non_coerente():
    dati = deepcopy(_dati_validi())
    dati["cronologia_adiacenze"][0]["mesi_occorrenza"] = [2]
    esito = valida_dati_annata(dati)
    assert esito.valido is False
    assert "CRONOLOGIA_MESI" in {p.codice for p in esito.problemi}


def test_renderer_contiene_le_dodici_sezioni_contrattuali():
    testo = rendi_rapporto_markdown(_dati_validi())
    for titolo in (
        "## 1. Identità e condizioni del run",
        "## 2. Esito e controlli di validità",
        "## 3. Bilancio descrittivo dell’annata",
        "## 4. Andamento mese per mese",
        "## 5. Cronologia delle adiacenze riutilizzate",
        "## 6. Incompatibilità concrete L1 e L2",
        "## 7. Affinità concrete L1, L2 e L3",
        "## 8. Distribuzione dei riusi fra gli studenti",
        "## 9. Genere misto",
        "## 10. FISSO",
        "## 11. Diagnostica tecnica C1",
        "## 12. Note sui dati nulli o non calcolabili",
    ):
        assert titolo in testo
    assert "non attribuisce automaticamente" in testo


def test_renderer_rifiuta_json_invalido():
    dati = deepcopy(_dati_validi())
    dati["versioni"]["strategia"] = "B4"
    with pytest.raises(ErroreRenderingMarkdown):
        rendi_rapporto_markdown(dati)


def test_pubblicazione_transazionale_scrive_tre_file_autosufficienti(tmp_path: Path):
    annata = _annata_sintetica(flag=True)
    destinazione = tmp_path / annata.run.run_id
    esito = pubblica_output_run(annata, destinazione)
    assert Path(esito.annata_json).is_file()
    assert Path(esito.annata_markdown).is_file()
    assert Path(esito.validazione_json).is_file()
    dati = leggi_json(esito.annata_json)
    assert valida_dati_annata(dati).valido is True
    validazione = leggi_json(esito.validazione_json)
    assert validazione["valido"] is True
    assert validazione["numero_errori"] == 0
    assert "# PostiPerfetti" in Path(esito.annata_markdown).read_text(encoding="utf-8")


def test_pubblicazione_non_sovrascrive_senza_consenso(tmp_path: Path):
    annata = _annata_sintetica(flag=False)
    destinazione = tmp_path / "run"
    pubblica_output_run(annata, destinazione)
    with pytest.raises(FileExistsError):
        pubblica_output_run(annata, destinazione)


def test_pubblicazione_fallita_non_lascia_directory_finale(tmp_path: Path, monkeypatch):
    from strumenti.cantiere_semantico import output_run

    annata = _annata_sintetica(flag=True)
    destinazione = tmp_path / "run_rotto"

    def esplode(*_args, **_kwargs):
        raise RuntimeError("renderer guasto")

    monkeypatch.setattr(output_run, "rendi_rapporto_markdown", esplode)
    with pytest.raises(RuntimeError, match="renderer guasto"):
        output_run.pubblica_output_run(annata, destinazione)
    assert not destinazione.exists()
    assert not list(tmp_path.glob(".run_rotto.*"))


def test_fallimento_strutturato_viene_scritto_e_riletto(tmp_path: Path):
    annata = _annata_sintetica(flag=False)
    try:
        raise ValueError("nessuna stagione completa")
    except ValueError as errore:
        record = record_fallimento_da_eccezione(
            annata.run,
            fase="esecuzione_c1",
            errore=errore,
            stato=StatoRun.FALLITO,
            mesi_completati=1,
            data_registrazione_utc="2026-08-01T20:30:00+00:00",
        )
    directory = tmp_path / "fallimento"
    firma = scrivi_fallimento_run(directory, record)
    dati = leggi_json(directory / "FALLIMENTO.json")
    assert len(firma) == 64
    assert dati["run_id"] == annata.run.run_id
    assert dati["stato"] == "fallito"
    assert dati["fase"] == "esecuzione_c1"
    assert dati["mesi_completati"] == 1
    assert "ValueError" in dati["traceback_tecnico"]


def test_cli_valida_e_rende_annata(tmp_path: Path, capsys):
    origine = tmp_path / "ANNATA.json"
    destinazione = tmp_path / "ANNATA.md"
    scrivi_json_atomico(origine, _annata_sintetica(flag=True))
    assert main(["valida-annata", str(origine)]) == 0
    assert "ANNATA.json valido" in capsys.readouterr().out
    assert main(["rendi-annata", str(origine), str(destinazione)]) == 0
    assert destinazione.is_file()
    assert "Rapporto scritto" in capsys.readouterr().out
