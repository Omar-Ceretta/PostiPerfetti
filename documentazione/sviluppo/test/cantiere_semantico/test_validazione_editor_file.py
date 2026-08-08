# -*- coding: utf-8 -*-

import pytest

from moduli.file_classe import (
    ErroreValidazioneFileClasse,
    RigaFileClasse,
    prepara_file_completo,
    serializza_file_classe,
    valida_dati_canonici_classe,
)


def _studente(cognome, nome, *, sesso="M", posizione="NORMALE"):
    return {
        "cognome": cognome,
        "nome": nome,
        "sesso": sesso,
        "posizione": posizione,
        "incompatibilita": {},
        "affinita": {},
    }


def test_file_rifiuta_caratteri_riservati_nei_nomi():
    riga = RigaFileClasse(1, "Ros,si;Ada;F;NORMALE;;")

    with pytest.raises(ErroreValidazioneFileClasse, match="caratteri riservati"):
        prepara_file_completo([riga])


def test_validazione_canonica_rifiuta_vincolo_non_bidirezionale():
    ada = _studente("Rossi", "Ada", sesso="F")
    luca = _studente("Bianchi", "Luca")
    ada["incompatibilita"]["Bianchi Luca"] = 3

    with pytest.raises(ErroreValidazioneFileClasse, match="non bidirezionale"):
        valida_dati_canonici_classe([ada, luca])


def test_validazione_canonica_rifiuta_due_studenti_fissi():
    studenti = [
        _studente("Rossi", "Ada", sesso="F", posizione="FISSO"),
        _studente("Bianchi", "Luca", posizione="FISSO"),
    ]

    with pytest.raises(ErroreValidazioneFileClasse, match="un solo studente"):
        valida_dati_canonici_classe(studenti)


def test_serializzazione_rifiuta_classe_vuota_e_dati_non_canonici():
    with pytest.raises(ErroreValidazioneFileClasse, match="almeno uno studente"):
        serializza_file_classe("Vuota", [])

    studente = _studente("Rossi", "Ada", sesso="f")
    with pytest.raises(ErroreValidazioneFileClasse, match="non canonico"):
        serializza_file_classe("Classe", [studente])
