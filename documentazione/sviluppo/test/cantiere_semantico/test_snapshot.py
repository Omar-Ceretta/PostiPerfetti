from __future__ import annotations

import copy

import pytest

from strumenti.cantiere_semantico.modelli import CanaleRotazione
from strumenti.cantiere_semantico.snapshot import (
    ErroreSnapshot,
    crea_snapshot_rotazioni,
    crea_stato_iniziale_id,
    verifica_snapshot,
)


def _config() -> dict:
    return {
        "storico_assegnazioni": [
            {
                "nome": "Settembre",
                "data_creazione": "2026-09-01",
                "progressivo": 1,
                "modo": "coppie",
                "layout": [
                    {"tipo": "coppia", "studente": "A Uno", "compagno": "B Due"},
                    {"tipo": "fisso", "studente": "F Fisso", "adiacente": "C Tre"},
                ],
            },
            {
                "nome": "Ottobre",
                "data_creazione": "2026-10-01",
                "progressivo": 2,
                "modo": "terzetti",
                "gruppi": [
                    {"tipo": "terzetto", "membri": ["A Uno", "C Tre", "D Quattro"]}
                ],
            },
            {
                "nome": "Novembre",
                "data_creazione": "2026-11-01",
                "progressivo": 3,
                "modo": "coppie",
                "layout": [
                    {"tipo": "coppia", "studente": "B Due", "compagno": "A Uno"}
                ],
            },
        ],
        "coppie_da_evitare": [
            {"tipo": "coppia", "studenti": ["B Due", "A Uno"], "volte_usata": 2}
        ],
        "adiacenze_terzetti_da_evitare": [
            {"tipo": "adiacenza", "studenti": ["C Tre", "A Uno"], "volte_usata": 1},
            {"tipo": "adiacenza", "studenti": ["C Tre", "D Quattro"], "volte_usata": 1},
        ],
        "studenti_vicino_fisso_contatore": {"C Tre": 1, "Mai Usato": 0},
        "studenti_trio_contatore": {},
        "tema": "scuro",
    }


def test_snapshot_conserva_contatori_canali_e_ultimo_riferimento():
    snapshot = crea_snapshot_rotazioni(_config())
    verifica_snapshot(snapshot)
    assert snapshot.coppie[0].studenti == ("A Uno", "B Due")
    assert snapshot.coppie[0].usi_precedenti == 2
    assert snapshot.coppie[0].canale == CanaleRotazione.COPPIE
    assert snapshot.coppie[0].ultimo_riferimento_disponibile.startswith("Novembre")
    assert [voce.studenti for voce in snapshot.terzetti] == [
        ("A Uno", "C Tre"),
        ("C Tre", "D Quattro"),
    ]
    assert snapshot.vicini_fisso[0].studente == "C Tre"
    assert snapshot.vicini_fisso[0].ultimo_riferimento_disponibile.startswith("Settembre")
    assert snapshot.vicini_fisso[1].studente == "Mai Usato"
    assert snapshot.vicini_fisso[1].usi_precedenti == 0


def test_snapshot_non_modifica_la_sorgente():
    dati = _config()
    prima = copy.deepcopy(dati)
    crea_snapshot_rotazioni(dati)
    assert dati == prima


def test_snapshot_ha_firma_indipendente_dall_ordine_delle_blacklist():
    uno = _config()
    due = copy.deepcopy(uno)
    due["adiacenze_terzetti_da_evitare"].reverse()
    assert crea_snapshot_rotazioni(uno).sha256 == crea_snapshot_rotazioni(due).sha256


def test_snapshot_cambia_se_cambia_un_contatore():
    uno = _config()
    due = copy.deepcopy(uno)
    due["coppie_da_evitare"][0]["volte_usata"] = 3
    assert crea_snapshot_rotazioni(uno).sha256 != crea_snapshot_rotazioni(due).sha256


def test_snapshot_rifiuta_duplicati():
    dati = _config()
    dati["coppie_da_evitare"].append(copy.deepcopy(dati["coppie_da_evitare"][0]))
    with pytest.raises(ErroreSnapshot, match="duplicata"):
        crea_snapshot_rotazioni(dati)


def test_snapshot_rifiuta_chiavi_mancanti():
    dati = _config()
    del dati["studenti_vicino_fisso_contatore"]
    with pytest.raises(ErroreSnapshot, match="mancano"):
        crea_snapshot_rotazioni(dati)


def test_stato_iniziale_id_e_stabile():
    snapshot = crea_snapshot_rotazioni(_config())
    assert crea_stato_iniziale_id(snapshot) == crea_stato_iniziale_id(snapshot)
    assert crea_stato_iniziale_id(snapshot).startswith("stato_")
