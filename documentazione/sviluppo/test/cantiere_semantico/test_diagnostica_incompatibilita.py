# -*- coding: utf-8 -*-

from moduli.algoritmo import AssegnatorePosti
from moduli.studenti import Student


def _crea_studenti(numero):
    return [
        Student(f"Cognome{indice}", f"Nome{indice}", "M")
        for indice in range(numero)
    ]


def _rendi_reciprocamente_incompatibili(studenti):
    for indice, studente in enumerate(studenti):
        for altro in studenti[indice + 1:]:
            studente.aggiungi_incompatibilita(
                altro.get_nome_completo(),
                3,
            )


def test_rileva_gruppo_incompatibile_piu_grande_della_meta():
    studenti = _crea_studenti(10)
    _rendi_reciprocamente_incompatibili(studenti[:6])

    assegnatore = AssegnatorePosti()
    gruppo = assegnatore._trova_gruppo_incompatibile_sovrabbondante(
        studenti
    )

    assert gruppo is not None
    assert gruppo["dimensione"] == 6
    assert gruppo["studenti_esterni"] == 4
    assert set(gruppo["studenti"]) == {
        studente.get_nome_completo()
        for studente in studenti[:6]
    }


def test_non_attribuisce_causa_certa_a_gruppo_di_meta_classe():
    studenti = _crea_studenti(10)
    _rendi_reciprocamente_incompatibili(studenti[:5])

    assegnatore = AssegnatorePosti()

    assert (
        assegnatore._trova_gruppo_incompatibile_sovrabbondante(
            studenti
        )
        is None
    )


def test_non_applica_la_prova_al_caso_dispari_con_trio():
    studenti = _crea_studenti(9)
    _rendi_reciprocamente_incompatibili(studenti[:6])

    assegnatore = AssegnatorePosti()

    assert (
        assegnatore._trova_gruppo_incompatibile_sovrabbondante(
            studenti
        )
        is None
    )
