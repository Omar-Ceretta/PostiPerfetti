from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import pytest

from strumenti.cantiere_semantico.ambiente import EsitoClassiAppaiate
from strumenti.cantiere_semantico.identita import crea_pair_id, crea_run_id
from strumenti.cantiere_semantico.modelli import (
    CondizioneRun,
    ProtocolloRaccolta,
    SpecificaCoppiaCorpus,
    SpecificaRun,
)
from strumenti.cantiere_semantico.raccolta import (
    ErroreRaccolta,
    pubblica_raccolta_da_output,
    valida_raccolta,
    verifica_manifesto,
)
from strumenti.cantiere_semantico.serializzazione import leggi_json, rendi_json_stabile, scrivi_json_atomico

RADICE = Path(__file__).resolve().parents[4]
ESEMPI = RADICE / "documentazione" / "sviluppo" / "dati_validazione" / "esempi"


def _sostituisci_run_id(valore, vecchio: str, nuovo: str):
    if isinstance(valore, dict):
        return {k: _sostituisci_run_id(v, vecchio, nuovo) for k, v in valore.items()}
    if isinstance(valore, list):
        return [_sostituisci_run_id(v, vecchio, nuovo) for v in valore]
    return nuovo if valore == vecchio else valore


def _protocollo_e_annate():
    senza = leggi_json(ESEMPI / "ANNATA_SENZA_FISSO_ESEMPIO.json")
    con = leggi_json(ESEMPI / "ANNATA_CON_FISSO_ESEMPIO.json")
    pair_id = crea_pair_id("Test", "A Test")
    coppia = SpecificaCoppiaCorpus(
        pair_id=pair_id,
        classe="Test",
        file_senza_fisso="senza/Test.txt",
        file_con_fisso="con/Test+fisso.txt",
        studente_fisso="A Test",
        posizione_base="NORMALE",
        numero_studenti=4,
    )
    runs = []
    annate = []
    for dati, condizione, file_classe in (
        (senza, CondizioneRun.SENZA_FISSO, coppia.file_senza_fisso),
        (con, CondizioneRun.CON_FISSO, coppia.file_con_fisso),
    ):
        r0 = dati["run"]
        from strumenti.cantiere_semantico.modelli import ParametriAula, ParametriRicerca, Modalita
        pr = ParametriRicerca(**r0["parametri_ricerca"])
        pa = ParametriAula(**r0["parametri_aula"])
        run_id = crea_run_id(
            pair_id, condizione.value, r0["modalita"], r0["seed_principale"],
            len(dati["mesi"]), r0["genere_misto_attivo"], r0["stato_iniziale_id"], pr, pa,
        )
        run = SpecificaRun(
            run_id=run_id, pair_id=pair_id, file_classe=file_classe,
            condizione=condizione, modalita=Modalita(r0["modalita"]),
            seed_principale=r0["seed_principale"], numero_mesi=len(dati["mesi"]),
            genere_misto_attivo=r0["genere_misto_attivo"],
            stato_iniziale_id=r0["stato_iniziale_id"],
            parametri_ricerca=pr, parametri_aula=pa, metadati={"test": "I9"},
        )
        vecchio = r0["run_id"]
        dati = _sostituisci_run_id(dati, vecchio, run_id)
        dati["run"] = rendi_json_stabile(run)
        runs.append(run)
        annate.append(dati)
    protocollo = ProtocolloRaccolta(
        protocollo_id="protocollo_test_i9", titolo="Test I9", versione="0.1",
        data_approvazione="2026-08-01", corpus_id="corpus_test",
        osservatore_id="osservatore_semantico_r0_1", strategia="C1",
        richiede_appaiamento_completo=True, coppie=(coppia,), run=tuple(runs),
    )
    return protocollo, annate[0], annate[1]


def _attestatore(specifica, _radice):
    return EsitoClassiAppaiate(
        pair_id=specifica.pair_id,
        studente_fisso=specifica.studente_fisso,
        numero_studenti=specifica.numero_studenti,
        firma_senza_fisso="a" * 64,
        firma_con_fisso="b" * 64,
    )


def _sorgente(tmp_path: Path, protocollo, senza, con, *, includi_con=True):
    src = tmp_path / "run_src"
    for run, dati in zip(protocollo.run, (senza, con)):
        if run.condizione == CondizioneRun.CON_FISSO and not includi_con:
            continue
        cartella = src / run.run_id
        cartella.mkdir(parents=True)
        scrivi_json_atomico(cartella / "ANNATA.json", dati)
    return src


def test_pubblica_raccolta_completa(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    esito = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "raccolta", attestatore=_attestatore)
    assert esito.completa is True
    assert esito.run_completi == 2
    assert esito.confronti_validi == 1
    radice = Path(esito.directory)
    assert (radice / "PROTOCOLLO.json").is_file()
    assert (radice / "INDICE_RUN.json").is_file()
    assert (radice / "tabelle" / "ADIACENZE.csv").is_file()
    assert len(list((radice / "confronti").glob("*/*/CONFRONTO.json"))) == 1
    validazione = valida_raccolta(radice)
    assert validazione["valido"] is True
    assert validazione["completa"] is True
    assert verifica_manifesto(radice)[0] is True


def test_raccolta_incompleta_resta_strutturalmente_valida(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con, includi_con=False)
    esito = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "raccolta", attestatore=_attestatore)
    assert esito.completa is False
    assert esito.run_completi == 1
    assert esito.confronti_validi == 0
    dati = leggi_json(esito.indice_json)
    assert dati["run_non_eseguiti"] == 1
    validazione = valida_raccolta(esito.directory)
    assert validazione["valido"] is True
    assert validazione["completa"] is False
    assert validazione["avvisi"]


def test_annata_manomessa_impedisce_la_pubblicazione(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    senza["riepilogo"]["riusi_totali"] += 1
    src = _sorgente(tmp_path, protocollo, senza, con)
    destinazione = tmp_path / "raccolta"
    with pytest.raises(ErroreRaccolta):
        pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", destinazione, attestatore=_attestatore)
    assert not destinazione.exists()


def test_manifesto_rileva_manomissione(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    esito = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "raccolta", attestatore=_attestatore)
    percorso = Path(esito.directory) / "tabelle" / "RUN.csv"
    percorso.write_text(percorso.read_text(encoding="utf-8") + "manomissione\n", encoding="utf-8")
    valido, problemi = verifica_manifesto(esito.directory)
    assert valido is False
    assert any("Firma non coincidente" in p for p in problemi)


def test_non_sovrascrive_senza_consenso(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    destinazione = tmp_path / "raccolta"
    pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", destinazione, attestatore=_attestatore)
    with pytest.raises(FileExistsError):
        pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", destinazione, attestatore=_attestatore)


def test_csv_hanno_le_righe_attese(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    esito = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "raccolta", attestatore=_attestatore)
    radice = Path(esito.directory) / "tabelle"
    with open(radice / "RUN.csv", encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == 2
    with open(radice / "MESI.csv", encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == 4
    with open(radice / "STUDENTI_ANNATA.csv", encoding="utf-8", newline="") as f:
        assert len(list(csv.DictReader(f))) == 8


def test_due_pubblicazioni_hanno_contenuto_deterministico(tmp_path: Path):
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    a = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "a", attestatore=_attestatore)
    b = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "b", attestatore=_attestatore)
    ma = (Path(a.directory) / "MANIFEST_SHA256.txt").read_text(encoding="utf-8")
    mb = (Path(b.directory) / "MANIFEST_SHA256.txt").read_text(encoding="utf-8")
    assert ma == mb


def test_cli_valida_raccolta(tmp_path: Path, capsys):
    from strumenti.cantiere_semantico.cli import main
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path, protocollo, senza, con)
    esito = pubblica_raccolta_da_output(protocollo, src, tmp_path / "corpus", tmp_path / "raccolta", attestatore=_attestatore)
    assert main(["valida-raccolta", esito.directory]) == 0
    assert "Raccolta valida" in capsys.readouterr().out


def test_esecuzione_matrice_registra_successi_e_fallimenti(tmp_path: Path):
    from strumenti.cantiere_semantico.raccolta import esegui_matrice_protocollo
    protocollo, senza, con = _protocollo_e_annate()
    per_id = {
        protocollo.run[0].run_id: senza,
        protocollo.run[1].run_id: con,
    }

    def esecutore(run, destinazione):
        if run.condizione == CondizioneRun.CON_FISSO:
            raise RuntimeError("fallimento intenzionale")
        destinazione.mkdir(parents=True)
        scrivi_json_atomico(destinazione / "ANNATA.json", per_id[run.run_id])

    esito = esegui_matrice_protocollo(protocollo, tmp_path / "run", esecutore)
    assert esito.run_attesi == 2
    assert esito.run_prodotti == 1
    assert esito.run_falliti == 1
    assert (tmp_path / "run" / protocollo.run[0].run_id / "ANNATA.json").is_file()
    fallimento = tmp_path / "run" / protocollo.run[1].run_id / "FALLIMENTO.json"
    assert fallimento.is_file()
    assert leggi_json(fallimento)["fase"] == "esecuzione_matrice_i9"
