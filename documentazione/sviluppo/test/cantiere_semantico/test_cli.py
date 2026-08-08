from __future__ import annotations

from pathlib import Path

from strumenti.cantiere_semantico.cli import main


RADICE = Path(__file__).resolve().parents[4]


def test_cli_valida_protocollo(capsys):
    esito = main(["valida-protocollo", str(RADICE / "documentazione" / "sviluppo" / "dati_validazione" / "esempi" / "PROTOCOLLO_MINIMO.json")])
    catturato = capsys.readouterr()
    assert esito == 0
    assert "Protocollo valido" in catturato.out


def test_cli_crea_snapshot(tmp_path, capsys):
    import json

    configurazione = tmp_path / "config.json"
    destinazione = tmp_path / "snapshot.json"
    configurazione.write_text(
        json.dumps({
            "storico_assegnazioni": [],
            "coppie_da_evitare": [],
            "adiacenze_terzetti_da_evitare": [],
            "studenti_trio_contatore": {},
            "studenti_vicino_fisso_contatore": {},
            "tema": "scuro",
        }),
        encoding="utf-8",
    )
    esito = main(["snapshot-stato", str(configurazione), str(destinazione)])
    catturato = capsys.readouterr()
    assert esito == 0
    assert destinazione.exists()
    assert "stato_iniziale_id:" in catturato.out
