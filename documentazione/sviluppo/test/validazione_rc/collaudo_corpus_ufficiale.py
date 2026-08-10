from pathlib import Path
import os

import pytest

from strumenti.validazione_rc.corpus import attesta_corpus_ufficiale


def _risorse_rc_esterne() -> tuple[Path, Path]:
    valore_corpus = os.environ.get("POSTIPERFETTI_CORPUS_RC", "").strip()
    if not valore_corpus:
        pytest.skip("corpus RC completo esterno: imposta POSTIPERFETTI_CORPUS_RC")
    corpus = Path(valore_corpus).expanduser().resolve()
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
    return protocollo, corpus


def test_corpus_ufficiale_19x2_e_nel_dominio_reale():
    protocollo, corpus = _risorse_rc_esterne()
    statistiche = attesta_corpus_ufficiale(protocollo, corpus)

    assert statistiche.coppie == 19
    assert statistiche.file_classe == 38
    assert 12 <= statistiche.minimo_studenti <= statistiche.massimo_studenti <= 30
    assert statistiche.classi_pari > 0
    assert statistiche.classi_dispari > 0
    assert statistiche.classi_con_prima > 0
    assert statistiche.classi_con_ultima > 0
    assert len(statistiche.firme_semantiche) == 38
    assert len({firma for _nome, firma in statistiche.firme_semantiche}) == 38
