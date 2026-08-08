# -*- coding: utf-8 -*-

import pytest

from moduli.file_classe import (
    ErroreValidazioneFileClasse,
    RigaFileClasse,
    prepara_file_base,
    prepara_file_completo,
    serializza_file_classe,
)
from moduli.lingua import forma_numerata, quantita


def test_forma_numerata_usa_il_singolare_solo_per_uno():
    assert forma_numerata(1, "coppia", "coppie") == "coppia"
    assert forma_numerata(0, "coppia", "coppie") == "coppie"
    assert forma_numerata(2, "coppia", "coppie") == "coppie"


def test_quantita_supporta_parole_irregolari():
    assert quantita(1, "studente", "studenti") == "1 studente"
    assert quantita(2, "studente", "studenti") == "2 studenti"
    assert quantita(1, "mese", "mesi") == "1 mese"


def test_serializzazione_file_classe_accorda_un_solo_studente():
    dati = [{
        "cognome": "Rossi",
        "nome": "Ada",
        "sesso": "F",
        "posizione": "NORMALE",
        "incompatibilita": {},
        "affinita": {},
    }]

    prima_riga = serializza_file_classe("Classe prova", dati).splitlines()[0]

    assert prima_riga == "# Classe: Classe prova (1 studente)"


def test_errore_file_base_accorda_un_solo_campo():
    with pytest.raises(ErroreValidazioneFileClasse) as errore:
        prepara_file_base([RigaFileClasse(7, "Rossi")])

    assert "ne è stato trovato 1" in str(errore.value)


def test_errore_file_completo_accorda_un_solo_campo():
    with pytest.raises(ErroreValidazioneFileClasse) as errore:
        prepara_file_completo([RigaFileClasse(3, "Rossi")])

    assert "trovato 1 campo" in str(errore.value)
