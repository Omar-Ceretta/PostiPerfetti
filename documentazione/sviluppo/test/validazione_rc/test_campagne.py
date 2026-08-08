from strumenti.validazione_rc.campagne import esegui_campagna_mensile_sintetica


def test_campagna_mensile_smoke_copre_intero_dominio_e_non_accetta_risultati_invalidi():
    rapporto = esegui_campagna_mensile_sintetica(
        profilo="smoke",
        seed_base=123456,
        num_candidati=1,
    )
    assert rapporto.casi == 3 * 19 * 2 * 2
    assert rapporto.risultati_invalidi == 0
    assert {c.studenti for c in rapporto.dettaglio} == set(range(12, 31))
    assert {c.modalita for c in rapporto.dettaglio} == {"coppie", "terzetti"}
    assert {c.fisso for c in rapporto.dettaglio} == {False, True}


def test_campagna_corpus_ufficiale_38x2_non_produce_risultati_invalidi():
    import os
    from pathlib import Path
    import pytest
    from strumenti.validazione_rc.campagne import esegui_campagna_mensile_corpus

    valore = os.environ.get("POSTIPERFETTI_CORPUS_RC", "").strip()
    if not valore:
        pytest.skip("corpus RC completo esterno: imposta POSTIPERFETTI_CORPUS_RC")
    corpus = Path(valore).expanduser().resolve()
    if not corpus.is_file():
        pytest.skip(f"corpus RC esterno non trovato: {corpus}")
    valore_protocollo = os.environ.get("POSTIPERFETTI_PROTOCOLLO_RC", "").strip()
    protocollo = (
        Path(valore_protocollo).expanduser().resolve()
        if valore_protocollo
        else corpus.parent / "PROTOCOLLO_PREFLIGHT_CORPUS_R0_1.json"
    )
    if not protocollo.is_file():
        pytest.skip(f"protocollo RC esterno non trovato: {protocollo}")

    rapporto = esegui_campagna_mensile_corpus(
        protocollo,
        corpus,
        seed_base=654321,
        num_candidati=1,
    )
    assert rapporto.casi == 76
    assert rapporto.successi == 76
    assert rapporto.fallimenti_motore == 0
    assert rapporto.risultati_invalidi == 0
