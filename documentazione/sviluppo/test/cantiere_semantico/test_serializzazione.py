from __future__ import annotations

import json
from pathlib import Path

import pytest

from strumenti.cantiere_semantico.identita import (
    chiave_adiacenza,
    crea_identificatore,
)
from strumenti.cantiere_semantico.serializzazione import (
    firma_file_sha256,
    firma_json_sha256,
    leggi_json,
    serializza_json,
    scrivi_json_atomico,
)


def test_json_stabile_indipendente_dall_ordine_dei_mapping():
    a = {"b": 2, "a": {"y": 2, "x": 1}}
    b = {"a": {"x": 1, "y": 2}, "b": 2}
    assert firma_json_sha256(a) == firma_json_sha256(b)
    assert serializza_json(a) == serializza_json(b)


def test_insiemi_serializzati_in_ordine_stabile():
    primo = {"valori": {"z", "a", "m"}}
    secondo = {"valori": {"m", "z", "a"}}
    assert serializza_json(primo) == serializza_json(secondo)


def test_nan_e_infinito_sono_rifiutati():
    with pytest.raises(ValueError, match="NaN"):
        serializza_json({"x": float("nan")})
    with pytest.raises(ValueError, match="NaN"):
        serializza_json({"x": float("inf")})


def test_scrittura_atomica_e_firme(tmp_path: Path):
    destinazione = tmp_path / "sotto" / "output.json"
    contenuto = {"classe": "Èlite", "mesi": [1, 2, 3]}
    firma = scrivi_json_atomico(destinazione, contenuto)
    assert destinazione.exists()
    assert leggi_json(destinazione) == contenuto
    assert firma == firma_json_sha256(contenuto)
    assert firma_file_sha256(destinazione) != ""
    residui = list(destinazione.parent.glob("*.tmp"))
    assert residui == []


def test_identificatore_stabile_e_sensibile_ai_componenti():
    uno = crea_identificatore("run", {"seed": 7, "modo": "coppie"})
    due = crea_identificatore("run", {"modo": "coppie", "seed": 7})
    tre = crea_identificatore("run", {"modo": "coppie", "seed": 8})
    assert uno == due
    assert uno != tre
    assert uno.startswith("run_")


def test_prefisso_identificatore_validato():
    with pytest.raises(ValueError, match="prefisso"):
        crea_identificatore("Run!", 1)


def test_chiave_adiacenza_non_orientata():
    assert chiave_adiacenza("Rossi Anna", "Bianchi Luca") == (
        "Bianchi Luca",
        "Rossi Anna",
    )
    assert chiave_adiacenza("Bianchi Luca", "Rossi Anna") == (
        "Bianchi Luca",
        "Rossi Anna",
    )


def test_json_prodotto_e_json_standard():
    testo = serializza_json({"b": 2, "a": 1})
    assert testo.endswith("\n")
    assert json.loads(testo) == {"a": 1, "b": 2}
