# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest

from strumenti.validazione_rc.annuale_rc import (
    esegui_annuale_processo_rc,
    esegui_annuale_rc,
    telemetria_storico_saturo_rc,
    verifica_accumulo_storico_rc,
)
from strumenti.validazione_rc.generatori import genera_classe_sintetica


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_annuale_ricalcola_metriche_e_preserva_esattamente_i_mesi(modalita):
    classe = genera_classe_sintetica(
        17, seed=2026080601, famiglia="sparsa", con_fisso=True
    )
    esito = esegui_annuale_rc(
        classe,
        modalita=modalita,
        seed=2026080602,
        num_mesi=4,
        numero_stagioni=2,
        num_candidati=1,
    )
    assert esito.successo
    assert esito.verifica is not None and esito.verifica.valida
    assert esito.verifica.chiavi_dichiarate == esito.verifica.chiavi_indipendenti
    assert esito.verifica.punteggio_dichiarato == esito.verifica.punteggio_indipendente
    assert sorted(esito.firme_prima_riordino) == sorted(esito.verifica.firme_mesi)


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_annuale_diretto_e_processo_producono_lo_stesso_esito(modalita):
    classe = genera_classe_sintetica(
        14, seed=2026080611, famiglia="media", con_fisso=False
    )
    diretto = esegui_annuale_rc(
        classe,
        modalita=modalita,
        seed=2026080612,
        num_mesi=3,
        numero_stagioni=2,
        num_candidati=1,
    )
    processo = esegui_annuale_processo_rc(
        classe,
        modalita=modalita,
        seed=2026080612,
        num_mesi=3,
        numero_stagioni=2,
        num_candidati=1,
        timeout_s=20,
    )
    assert diretto.successo and processo.successo
    assert diretto.verifica is not None and processo.verifica is not None
    assert diretto.verifica.firme_mesi == processo.verifica.firme_mesi
    assert diretto.verifica.punteggio_indipendente == processo.verifica.punteggio_indipendente
    assert diretto.info["indice_stagione_migliore"] == processo.info["indice_stagione_migliore"]
    assert diretto.info["politica_annuale"] == processo.info["politica_annuale"]


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_storico_saturo_porta_al_t4_senza_esplorare_t2_t3(modalita):
    classe = genera_classe_sintetica(
        12, seed=2026080621, famiglia="vuota", con_fisso=False
    )
    telemetria = telemetria_storico_saturo_rc(
        classe, modalita=modalita, seed=2026080622, num_candidati=1
    )
    assert telemetria.successo
    assert telemetria.risultato_valido is True
    assert telemetria.tentativi_iniziati == (1, 4)
    assert telemetria.tentativi_successo == (4,)


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_blacklist_cumulativa_coincide_con_le_adiacenze_fisiche(modalita):
    classe = genera_classe_sintetica(
        14, seed=2026080631, famiglia="sparsa", con_fisso=True
    )
    verifica = verifica_accumulo_storico_rc(
        classe,
        modalita=modalita,
        seed=2026080632,
        num_mesi=5,
        num_candidati=1,
    )
    assert verifica.valido, verifica.differenze
    assert verifica.mesi_completati == 5
    assert verifica.contatori_reali == verifica.contatori_attesi
    if modalita == "coppie":
        assert verifica.vicini_fisso_reali == verifica.vicini_fisso_attesi


def test_stesso_seed_annuale_produce_la_stessa_firma():
    classe = genera_classe_sintetica(
        18, seed=2026080641, famiglia="media", con_fisso=False
    )
    a = esegui_annuale_rc(
        classe, modalita="coppie", seed=2026080642,
        num_mesi=4, numero_stagioni=2, num_candidati=1,
    )
    b = esegui_annuale_rc(
        classe, modalita="coppie", seed=2026080642,
        num_mesi=4, numero_stagioni=2, num_candidati=1,
    )
    assert a.successo and b.successo
    assert a.verifica is not None and b.verifica is not None
    assert a.verifica.firme_mesi == b.verifica.firme_mesi
    assert a.verifica.punteggio_indipendente == b.verifica.punteggio_indipendente
