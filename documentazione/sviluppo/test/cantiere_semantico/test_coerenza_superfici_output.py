from pathlib import Path

import pytest

from moduli.stato_mensile import StatoMensile


RADICE = Path(__file__).resolve().parents[4]


class _Assegnatore:
    pass


def _stato_pronto():
    stato = StatoMensile()
    stato.prepara_coppie(
        _Assegnatore(),
        nome="2A - Mensile Coppie - 01",
        progressivo=1,
        data_creazione="06/08/2026 18:00",
        file_origine="/classi/2A.txt",
        nome_classe="2A",
        genere_misto=False,
    )
    return stato


def test_export_richiede_la_voce_corrente_salvata_nello_storico():
    stato = _stato_pronto()

    with pytest.raises(RuntimeError, match="salvata nello Storico"):
        stato.nome_per_export()

    stato.segna_salvata(3)
    assert stato.nome_per_export() == "2A - Mensile Coppie - 01"


def test_eliminare_la_voce_corrente_disabilita_anche_il_contesto_export():
    stato = _stato_pronto()
    stato.segna_salvata(0)
    stato.scollega_dallo_storico()

    with pytest.raises(RuntimeError, match="salvata nello Storico"):
        stato.nome_per_export()


def test_export_corrente_non_ripiega_sull_ultima_voce_dello_storico():
    sorgente = (RADICE / "moduli" / "esportazione.py").read_text(
        encoding="utf-8"
    )

    assert "nome_per_export()" in sorgente
    assert 'ultima.get("nome"' not in sorgente


def test_storico_e_anteprima_non_mascherano_report_mancanti_del_formato_corrente():
    storico = (RADICE / "moduli" / "storico_ui.py").read_text(
        encoding="utf-8"
    )
    anteprima = (RADICE / "moduli" / "anteprima_annuale.py").read_text(
        encoding="utf-8"
    )

    assert 'self.dati_assegnazione["report_completo"]' in storico
    assert "Report non disponibile per questa assegnazione." not in storico
    assert "Il mese Annuale non contiene il Report previsto." in anteprima


def test_messaggio_finale_annuale_elenca_le_stesse_azioni_per_entrambi_i_modi():
    sorgente = (RADICE / "moduli" / "anteprima_annuale.py").read_text(
        encoding="utf-8"
    )
    frase = (
        '"Puoi consultare le assegnazioni, rinominarle, esportarle "\n'
        '                "o eliminarle dalla scheda Storico."'
    )

    assert sorgente.count(frase) == 2
    assert "o stamparle dalla scheda Storico" not in sorgente
