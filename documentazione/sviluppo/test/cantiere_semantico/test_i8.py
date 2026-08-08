from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from strumenti.cantiere_semantico.aggregati import costruisci_annata_canonica
from strumenti.cantiere_semantico.ambiente import EsitoClassiAppaiate
from strumenti.cantiere_semantico.confronto_appaiato import (
    costruisci_confronto_appaiato,
    pubblica_confronto_appaiato,
    rendi_confronto_markdown,
    valida_dati_confronto,
)
from strumenti.cantiere_semantico.cronologia import costruisci_cronologia
from strumenti.cantiere_semantico.esecuzione_c1 import EsitoC1
from strumenti.cantiere_semantico.identita import crea_confronto_id
from strumenti.cantiere_semantico.modelli import CondizioneRun, Modalita, StatoRun, TracciaMese
from strumenti.cantiere_semantico.serializzazione import leggi_json, rendi_json_stabile, scrivi_json_atomico
from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni

from .supporto_i3 import configurazione_produttiva_vuota, crea_run
from .test_i5 import _mese


def _studenti(*, con_fisso: bool):
    from moduli.studenti import Student

    return [
        Student("A", "Test", "M", "FISSO" if con_fisso else "NORMALE"),
        Student("B", "Test", "F"),
        Student("C", "Test", "M"),
        Student("D", "Test", "F"),
    ]


def _esito(run, numero_mesi: int) -> EsitoC1:
    raw = tuple(object() for _ in range(numero_mesi))
    chiavi = tuple((0, 0, 0) for _ in range(numero_mesi))
    tracce = tuple(TracciaMese(i, i, (0, 0, 0), (0, 0, 0)) for i in range(1, numero_mesi + 1))
    return EsitoC1(
        run.run_id,
        run.modalita,
        StatoRun.COMPLETO,
        raw,
        chiavi,
        raw,
        chiavi,
        tracce,
        {
            "n_stagioni": 1,
            "n_stagioni_complete": 1,
            "punteggio": (0, 0, 0),
            "motivo_stop": "test_i8",
            "indice_stagione_migliore": 1,
        },
    )


def _annate_appaiate():
    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run_s, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
        condizione=CondizioneRun.SENZA_FISSO,
    )
    run_c, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
        condizione=CondizioneRun.CON_FISSO,
    )
    run_s = replace(run_s, file_classe="corpus/senza_fisso/Test.txt")
    run_c = replace(run_c, file_classe="corpus/con_fisso/Test+fisso.txt")

    studenti_s = _studenti(con_fisso=False)
    studenti_c = _studenti(con_fisso=True)
    mesi_s = (
        _mese(run_s, 1, (("A Test", "B Test"), ("C Test", "D Test"))),
        _mese(run_s, 2, (("A Test", "C Test"), ("B Test", "D Test"))),
    )
    mesi_c = (
        _mese(run_c, 1, (("A Test", "B Test"), ("C Test", "D Test")), fisso="A Test"),
        _mese(run_c, 2, (("A Test", "B Test"), ("C Test", "D Test")), fisso="A Test"),
    )
    cron_s = costruisci_cronologia(run_s, snapshot, mesi_s)
    cron_c = costruisci_cronologia(run_c, snapshot, mesi_c)
    annata_s = costruisci_annata_canonica(
        _esito(run_s, 2), cron_s, run_s, snapshot, studenti_s, classe="Test"
    )
    annata_c = costruisci_annata_canonica(
        _esito(run_c, 2),
        cron_c,
        run_c,
        snapshot,
        studenti_c,
        classe="Test",
        studente_fisso=studenti_c[0],
    )
    attestazione = EsitoClassiAppaiate(
        pair_id=run_s.pair_id,
        studente_fisso="A Test",
        numero_studenti=4,
        firma_senza_fisso="a" * 64,
        firma_con_fisso="b" * 64,
    )
    return rendi_json_stabile(annata_s), rendi_json_stabile(annata_c), attestazione


def test_costruisce_confronto_appaiato_valido():
    senza, con, attestazione = _annate_appaiate()
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    dati = rendi_json_stabile(confronto)
    assert confronto.validita_appaiamento is True
    assert confronto.confronto_id == crea_confronto_id(senza["run"]["run_id"], con["run"]["run_id"])
    assert len(confronto.mesi) == 2
    assert dati["annuale"]["valori"]["riusi_totali"]["delta"] == 2
    assert dati["annuale"]["studenti_con_cambiamento"]
    assert valida_dati_confronto(dati).valido is True


def test_normalizza_lordine_degli_input():
    senza, con, attestazione = _annate_appaiate()
    a = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    b = costruisci_confronto_appaiato(con, senza, attestazione_classi=attestazione)
    assert rendi_json_stabile(a) == rendi_json_stabile(b)


def test_adiacenze_concrete_sono_distinte_per_mese():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    primo = dati["mesi"][0]
    secondo = dati["mesi"][1]
    assert len(primo["adiacenze_comuni"]) == 2
    assert secondo["conteggi_adiacenze"] == {
        "comuni": 0,
        "solo_senza_fisso": 2,
        "solo_con_fisso": 2,
    }
    assert {tuple(x["studenti"]) for x in secondo["adiacenze_solo_con_fisso"]} == {
        ("A Test", "B Test"),
        ("C Test", "D Test"),
    }


def test_manca_attestazione_appaiamento_invalido_senza_differenze():
    senza, con, _ = _annate_appaiate()
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=None)
    dati = rendi_json_stabile(confronto)
    assert confronto.validita_appaiamento is False
    assert {p.codice for p in confronto.problemi_appaiamento} == {"ATTESTAZIONE_ASSENTE"}
    assert dati["mesi"] == []
    assert dati["annuale"] == {}
    assert valida_dati_confronto(dati).valido is True


def test_parametro_diverso_rende_invalido_lappaiamento():
    senza, con, attestazione = _annate_appaiate()
    con = deepcopy(con)
    con["run"]["seed_principale"] += 1
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    assert confronto.validita_appaiamento is False
    assert "PARAMETRO_SEED_PRINCIPALE" in {p.codice for p in confronto.problemi_appaiamento}


def test_posizione_non_autorizzata_rende_invalido_lappaiamento():
    senza, con, attestazione = _annate_appaiate()
    con = deepcopy(con)
    voce = next(x for x in con["studenti"] if x["studente"] == "B Test")
    voce["posizione"] = "PRIMA"
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    assert confronto.validita_appaiamento is False
    assert "POSIZIONE_NON_AUTORIZZATA" in {p.codice for p in confronto.problemi_appaiamento}


def test_validatore_rifiuta_delta_manomesso():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    dati["annuale"]["valori"]["riusi_totali"]["delta"] += 1
    esito = valida_dati_confronto(dati)
    assert esito.valido is False
    assert "TRIPLA_DELTA" in {p.codice for p in esito.problemi}


def test_validatore_rifiuta_categorie_adiacenze_sovrapposte():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    dati["mesi"][1]["adiacenze_solo_con_fisso"].append(
        deepcopy(dati["mesi"][1]["adiacenze_solo_senza_fisso"][0])
    )
    esito = valida_dati_confronto(dati)
    assert esito.valido is False
    assert "ADIACENZE_SOVRAPPOSTE" in {p.codice for p in esito.problemi}


def test_markdown_dichiara_il_limite_non_causale():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    testo = rendi_confronto_markdown(dati)
    assert "## 6. Limite interpretativo" in testo
    assert "Non dichiara automaticamente" in testo
    assert "Δ con−senza" in testo


def test_markdown_invalido_non_produce_differenze():
    senza, con, _ = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=None))
    testo = rendi_confronto_markdown(dati)
    assert "Appaiamento non valido" in testo
    assert "Differenze annuali" not in testo


def test_pubblicazione_transazionale_del_confronto(tmp_path: Path):
    senza, con, attestazione = _annate_appaiate()
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    esito = pubblica_confronto_appaiato(confronto, tmp_path / "confronto")
    assert Path(esito.confronto_json).is_file()
    assert Path(esito.confronto_markdown).is_file()
    assert Path(esito.validazione_json).is_file()
    dati = leggi_json(esito.confronto_json)
    assert valida_dati_confronto(dati).valido is True
    assert leggi_json(esito.validazione_json)["valido"] is True


def test_pubblicazione_non_sovrascrive_senza_consenso(tmp_path: Path):
    senza, con, attestazione = _annate_appaiate()
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    destinazione = tmp_path / "confronto"
    pubblica_confronto_appaiato(confronto, destinazione)
    with pytest.raises(FileExistsError):
        pubblica_confronto_appaiato(confronto, destinazione)


def test_cli_valida_e_rende_confronto(tmp_path: Path, capsys):
    from strumenti.cantiere_semantico.cli import main

    senza, con, attestazione = _annate_appaiate()
    confronto = costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione)
    origine = tmp_path / "CONFRONTO.json"
    destinazione = tmp_path / "CONFRONTO.md"
    scrivi_json_atomico(origine, confronto)
    assert main(["valida-confronto", str(origine)]) == 0
    assert "CONFRONTO.json valido" in capsys.readouterr().out
    assert main(["rendi-confronto", str(origine), str(destinazione)]) == 0
    assert destinazione.is_file()
    assert "Rapporto confronto scritto" in capsys.readouterr().out


def test_cli_rifiuta_confronto_manomesso(tmp_path: Path, capsys):
    from strumenti.cantiere_semantico.cli import main

    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    dati["annuale"]["valori"]["riusi_totali"]["delta"] = 999
    origine = tmp_path / "CONFRONTO_ROTTO.json"
    scrivi_json_atomico(origine, dati)
    assert main(["valida-confronto", str(origine)]) == 2
    assert "TRIPLA_DELTA" in capsys.readouterr().err


def test_validatore_rifiuta_conteggio_adiacenze_manomesso():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    dati["mesi"][0]["conteggi_adiacenze"]["comuni"] += 1
    esito = valida_dati_confronto(dati)
    assert esito.valido is False
    assert "CONTEGGI_ADIACENZE" in {p.codice for p in esito.problemi}


def test_validatore_rifiuta_totale_annuale_non_derivato_dai_mesi():
    senza, con, attestazione = _annate_appaiate()
    dati = rendi_json_stabile(costruisci_confronto_appaiato(senza, con, attestazione_classi=attestazione))
    voce = dati["annuale"]["valori"]["affinita_l1"]
    voce["senza_fisso"] += 1
    voce["delta"] = voce["con_fisso"] - voce["senza_fisso"]
    esito = valida_dati_confronto(dati)
    assert esito.valido is False
    assert "TOTALE_ANNUALE" in {p.codice for p in esito.problemi}
