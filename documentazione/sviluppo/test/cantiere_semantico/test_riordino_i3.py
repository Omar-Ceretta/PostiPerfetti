from __future__ import annotations

from types import SimpleNamespace

import pytest

from strumenti.cantiere_semantico.modelli import TracciaMese
from strumenti.cantiere_semantico.riordino import (
    ErroreRiordinoC1,
    riordina_coppie_con_traccia,
    riordina_terzetti_con_traccia,
)


class AssegnatoreMinimo:
    def __init__(self, coppie):
        self.coppie_formate = [(a, b, {}) for a, b in coppie]
        self.trio_identificato = None
        self.studente_fisso = None
        self.gruppo_adiacente_fisso = None
        self.nome_adiacente_fisso = None


def _studenti():
    from moduli.studenti import Student

    return [Student(lettera, "Test", "M") for lettera in "ABCD"]


def test_traccia_mese_normalizza_fotografie():
    traccia = TracciaMese(
        posizione_generazione=2,
        posizione_finale=1,
        chiave_generazione=(1, 0, 0),
        chiave_finale=(0, 0, 0),
        foto_rotazioni_precedenti=(("B", "A"),),
        vicini_fisso_precedenti=("Z", "C"),
    )
    assert traccia.foto_rotazioni_precedenti == (("A", "B"),)
    assert traccia.vicini_fisso_precedenti == ("C", "Z")


def test_riordino_coppie_conserva_indice_originale():
    a, b, c, d = _studenti()
    primo = AssegnatoreMinimo([(a, b), (c, d)])
    secondo = AssegnatoreMinimo([(a, c), (b, d)])
    config = SimpleNamespace(config_data={
        "coppie_da_evitare": [
            {"tipo": "coppia", "studenti": ["A Test", "B Test"], "volte_usata": 1}
        ],
        "studenti_vicino_fisso_contatore": {},
    })

    finali, chiavi, traccia = riordina_coppie_con_traccia(
        [primo, secondo],
        [(1, 0, 0), (0, 0, 0)],
        config,
    )

    assert finali == (secondo, primo)
    assert chiavi == ((0, 0, 0), (1, 0, 0))
    assert [voce.posizione_generazione for voce in traccia] == [2, 1]
    assert [voce.posizione_finale for voce in traccia] == [1, 2]
    assert traccia[0].foto_rotazioni_precedenti == (("A Test", "B Test"),)


def test_riordino_terzetti_conserva_foto_e_indice():
    from moduli.metrica_pulizia import Gruppo, TIPO_TERZETTO

    a, b, c, d = _studenti()
    e = type(a)("E", "Test", "F")
    f = type(a)("F", "Test", "F")
    mese1 = {"gruppi": [Gruppo(TIPO_TERZETTO, [a, b, c]), Gruppo(TIPO_TERZETTO, [d, e, f])]}
    mese2 = {"gruppi": [Gruppo(TIPO_TERZETTO, [a, d, b]), Gruppo(TIPO_TERZETTO, [c, e, f])]}
    config = SimpleNamespace(config_data={
        "adiacenze_terzetti_da_evitare": [
            {"tipo": "adiacenza", "studenti": ["A Test", "B Test"], "volte_usata": 1}
        ]
    })

    finali, chiavi, traccia = riordina_terzetti_con_traccia(
        [mese1, mese2],
        [(1, 0, 0), (0, 0, 0)],
        config,
    )

    assert len(finali) == 2
    assert sorted(voce.posizione_generazione for voce in traccia) == [1, 2]
    assert traccia[0].posizione_finale == 1
    assert set(finali[0]["adiacenze_prima"]) == set(traccia[0].foto_rotazioni_precedenti)


def test_riordino_rifiuta_lunghezze_incoerenti():
    with pytest.raises(ErroreRiordinoC1):
        riordina_coppie_con_traccia([], [(0, 0, 0)], SimpleNamespace(config_data={}))


def test_riordino_coppie_traccia_separatamente_i_vicini_del_fisso():
    from moduli.studenti import Student

    fisso = Student("Fisso", "Test", "M", "FISSO")
    a = Student("A", "Test", "F")
    b = Student("B", "Test", "M")
    c = Student("C", "Test", "F")
    d = Student("D", "Test", "M")

    primo = AssegnatoreMinimo([(a, b)])
    primo.studente_fisso = fisso
    primo.gruppo_adiacente_fisso = [c, d]
    primo.nome_adiacente_fisso = c.get_nome_completo()

    secondo = AssegnatoreMinimo([(a, c)])
    secondo.studente_fisso = fisso
    secondo.gruppo_adiacente_fisso = [d, b]
    secondo.nome_adiacente_fisso = d.get_nome_completo()

    config = SimpleNamespace(config_data={
        "coppie_da_evitare": [],
        "studenti_vicino_fisso_contatore": {c.get_nome_completo(): 1},
    })

    finali, _chiavi, traccia = riordina_coppie_con_traccia(
        [primo, secondo],
        [(1, 0, 0), (0, 0, 0)],
        config,
    )

    assert finali[0] is secondo
    assert traccia[0].vicini_fisso_precedenti == (c.get_nome_completo(),)
    assert traccia[1].vicini_fisso_precedenti == tuple(sorted((
        c.get_nome_completo(),
        d.get_nome_completo(),
    )))
