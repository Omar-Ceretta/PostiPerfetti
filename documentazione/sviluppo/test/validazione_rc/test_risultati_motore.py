from copy import deepcopy

import pytest

from strumenti.validazione_rc.esecuzione import (
    esegui_mensile_coppie_rc,
    esegui_mensile_terzetti_rc,
)
from strumenti.validazione_rc.generatori import genera_classe_sintetica
from strumenti.validazione_rc.risultati import verifica_aula_rc


def _classe(n, seed, *, fisso=False):
    return genera_classe_sintetica(
        n,
        seed=seed,
        famiglia="sparsa",
        con_fisso=fisso,
    )


@pytest.mark.parametrize(
    "n,fisso",
    [(12, False), (13, False), (17, True), (30, True)],
)
def test_controllore_indipendente_accetta_risultati_coppie_reali(n, fisso):
    classe = _classe(n, 8000 + n, fisso=fisso)
    esito = esegui_mensile_coppie_rc(classe, seed=20260806 + n)
    assert esito.successo
    assert esito.verifica is not None
    assert esito.verifica.metriche.studenti == n
    assert esito.verifica.metriche.incompatibilita_l3 == 0


@pytest.mark.parametrize(
    "n,fisso,preferenza",
    [
        (12, False, "coppia"),
        (14, False, "coppia"),
        (17, True, "coppia"),
        (20, True, "due_quartetti"),
    ],
)
def test_controllore_indipendente_accetta_risultati_terzetti_reali(n, fisso, preferenza):
    classe = _classe(n, 9000 + n, fisso=fisso)
    esito = esegui_mensile_terzetti_rc(
        classe,
        seed=303000 + n,
        preferenza_resto2=preferenza,
    )
    assert esito.successo
    assert esito.verifica is not None
    assert esito.verifica.metriche.studenti == n
    assert esito.verifica.metriche.incompatibilita_l3 == 0


def test_controllore_scopre_studente_mancante_senza_fidarsi_del_motore():
    classe = _classe(12, 1111)
    esito = esegui_mensile_coppie_rc(classe, seed=2222)
    assert esito.successo
    aula = deepcopy(esito.aula)
    for riga in aula.griglia:
        for posto in riga:
            if posto.occupato_da:
                posto.occupato_da = None
                verifica = verifica_aula_rc(classe, aula, modalita="coppie")
                assert not verifica.valido
                assert "RC_RIS_MANCANTI" in {v.codice for v in verifica.violazioni}
                return
    raise AssertionError("Nessun occupante trovato nel risultato di prova")


def test_controllore_scopre_fisso_spostato_dal_frontale_sinistro():
    classe = _classe(17, 3333, fisso=True)
    esito = esegui_mensile_coppie_rc(classe, seed=4444)
    assert esito.successo
    aula = deepcopy(esito.aula)
    fisso = classe.studente_fisso
    posizioni = []
    for riga in aula.griglia:
        for posto in riga:
            if posto.occupato_da:
                posizioni.append(posto)
    posto_fisso = next(p for p in posizioni if p.occupato_da.replace("_", " ") == fisso)
    altro = next(p for p in posizioni if p.riga == posto_fisso.riga and p is not posto_fisso)
    posto_fisso.occupato_da, altro.occupato_da = altro.occupato_da, posto_fisso.occupato_da
    verifica = verifica_aula_rc(classe, aula, modalita="coppie")
    assert not verifica.valido
    assert "RC_RIS_FISSO" in {v.codice for v in verifica.violazioni}


def _nomi_adiacenze_produttive_coppie(assegnatore):
    from moduli.metrica_pulizia import estrai_adiacenze
    return {
        tuple(sorted((a.get_nome_completo(), b.get_nome_completo())))
        for a, b in estrai_adiacenze(assegnatore)
    }


def _nomi_adiacenze_produttive_terzetti(gruppi):
    from moduli.metrica_pulizia import adiacenze_partizione
    return {
        tuple(sorted((a.get_nome_completo(), b.get_nome_completo())))
        for a, b in adiacenze_partizione(gruppi)
    }


@pytest.mark.parametrize("n,fisso", [(12, True), (13, True), (18, False), (29, False)])
def test_adiacenze_e_metriche_coppie_coincidono_con_ricalcolo_fisico(n, fisso):
    from moduli.metrica_pulizia import (
        conta_affinita_soddisfatte,
        conta_incompatibilita_per_livello,
    )
    classe = genera_classe_sintetica(n, seed=12000 + n, famiglia="media", con_fisso=fisso)
    esito = esegui_mensile_coppie_rc(classe, seed=700000 + n)
    assert esito.successo
    verifica = esito.verifica
    assert set(verifica.adiacenze) == _nomi_adiacenze_produttive_coppie(esito.risultato)
    prod_inc = conta_incompatibilita_per_livello(esito.risultato)
    assert prod_inc == {
        1: verifica.metriche.incompatibilita_l1,
        2: verifica.metriche.incompatibilita_l2,
        3: verifica.metriche.incompatibilita_l3,
    }
    assert conta_affinita_soddisfatte(esito.risultato) == verifica.metriche.affinita


@pytest.mark.parametrize(
    "n,fisso,preferenza",
    [(13, False, "coppia"), (14, True, "coppia"), (20, False, "due_quartetti"), (29, True, "coppia")],
)
def test_adiacenze_e_metriche_terzetti_coincidono_con_ricalcolo_fisico(n, fisso, preferenza):
    from moduli.metrica_pulizia import (
        conta_affinita_soddisfatte_terzetti,
        conta_incompatibilita_per_livello_terzetti,
    )
    classe = genera_classe_sintetica(n, seed=13000 + n, famiglia="media", con_fisso=fisso)
    esito = esegui_mensile_terzetti_rc(
        classe,
        seed=800000 + n,
        preferenza_resto2=preferenza,
    )
    assert esito.successo
    verifica = esito.verifica
    assert set(verifica.adiacenze) == _nomi_adiacenze_produttive_terzetti(esito.risultato)
    prod_inc = conta_incompatibilita_per_livello_terzetti(esito.risultato)
    assert prod_inc == {
        1: verifica.metriche.incompatibilita_l1,
        2: verifica.metriche.incompatibilita_l2,
        3: verifica.metriche.incompatibilita_l3,
    }
    assert conta_affinita_soddisfatte_terzetti(esito.risultato) == verifica.metriche.affinita
