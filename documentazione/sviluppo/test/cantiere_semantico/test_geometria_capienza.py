# -*- coding: utf-8 -*-

from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie


def _layout(n, file, posti, *, fisso=False, trio="centro"):
    aula = ConfigurazioneAula()
    aula.crea_layout_standard(
        n,
        file,
        posti,
        trio,
        ha_fisso=fisso,
    )
    return aula


def test_fila_speciale_rispetta_quattro_posti_nominali():
    trio = _layout(5, 1, 4, trio="prima")
    fisso_e_trio = _layout(6, 1, 4, fisso=True, trio="prima")

    assert trio.capienze_file_banchi() == (5,)
    assert fisso_e_trio.capienze_file_banchi() == (6,)


def test_fila_speciale_aggiunge_solo_i_posti_del_blocco_largo():
    trio = _layout(7, 1, 6, trio="prima")
    fisso_e_trio = _layout(8, 1, 6, fisso=True, trio="prima")

    assert trio.capienze_file_banchi() == (7,)
    assert fisso_e_trio.capienze_file_banchi() == (8,)


def test_numero_minimo_file_usa_la_capienza_reale_del_trio():
    assert numero_minimo_file_coppie(7, 6, posizione_trio="centro") == 1
    assert numero_minimo_file_coppie(
        8,
        6,
        posizione_trio="centro",
        ha_fisso=True,
    ) == 1
    assert numero_minimo_file_coppie(8, 6, posizione_trio="centro") == 2


def test_conteggio_per_fila_coincide_sempre_con_la_capienza():
    for n in range(2, 25):
        for posti in (4, 6, 8, 10):
            for fisso in (False, True):
                file = numero_minimo_file_coppie(
                    n,
                    posti,
                    posizione_trio="ultima",
                    ha_fisso=fisso,
                )
                aula = _layout(
                    n,
                    file,
                    posti,
                    fisso=fisso,
                    trio="ultima",
                )
                assert sum(aula.capienze_file_banchi()) == aula.posti_disponibili
                assert aula.posti_disponibili >= n
