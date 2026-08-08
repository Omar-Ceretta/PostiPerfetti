from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from strumenti.cantiere_semantico.audit_finale import (
    audita_raccolta,
    confronta_firme_produzione,
    confronta_raccolte_riproducibili,
    firma_albero_produzione,
    pubblica_audit_finale,
)
from strumenti.cantiere_semantico.raccolta import pubblica_raccolta_da_output, valida_raccolta
from strumenti.cantiere_semantico.serializzazione import leggi_json

from .test_i9 import _attestatore, _protocollo_e_annate, _sorgente


def _raccolta(tmp_path: Path, nome: str = "raccolta") -> Path:
    protocollo, senza, con = _protocollo_e_annate()
    src = _sorgente(tmp_path / f"{nome}_sorgente", protocollo, senza, con)
    esito = pubblica_raccolta_da_output(
        protocollo, src, tmp_path / "corpus", tmp_path / nome,
        attestatore=_attestatore,
    )
    return Path(esito.directory)


def test_raccolta_conserva_output_completo_del_run(tmp_path: Path):
    radice = _raccolta(tmp_path)
    indice = leggi_json(radice / "INDICE_RUN.json")
    for voce in indice["run"]:
        run = radice / "run" / voce["run_id"]
        assert (run / "ANNATA.json").is_file()
        assert (run / "ANNATA.md").is_file()
        assert (run / "VALIDAZIONE.json").is_file()
        assert leggi_json(run / "VALIDAZIONE.json")["valido"] is True


def test_validazione_raccolta_rileva_markdown_assente(tmp_path: Path):
    radice = _raccolta(tmp_path)
    markdown = next((radice / "run").glob("*/ANNATA.md"))
    markdown.unlink()
    esito = valida_raccolta(radice, verifica_firme=False)
    assert esito["valido"] is False
    assert any(p["codice"] == "RAPPORTO_ANNATA_ASSENTE" for p in esito["problemi"])


def test_audit_finale_esempio_completo(tmp_path: Path):
    radice = _raccolta(tmp_path)
    dati = audita_raccolta(radice)
    assert dati["valido"] is True
    assert dati["pronto_raccolta_reale"] is True
    assert dati["numero_errori"] == 0


def test_audit_corpus_ufficiale_rifiuta_esempio_minimo(tmp_path: Path):
    radice = _raccolta(tmp_path)
    dati = audita_raccolta(radice, richiedi_corpus_ufficiale=True)
    assert dati["valido"] is False
    assert any(c["codice"] == "CORPUS_UFFICIALE" and not c["superato"] for c in dati["controlli"])


def test_pubblicazione_audit_scrive_json_e_markdown(tmp_path: Path):
    radice = _raccolta(tmp_path)
    destinazione = tmp_path / "audit"
    dati = pubblica_audit_finale(radice, destinazione)
    assert dati["valido"] is True
    assert (destinazione / "AUDIT_FINALE.json").is_file()
    assert (destinazione / "AUDIT_FINALE.md").is_file()


def test_firme_produzione_rilevano_modifica(tmp_path: Path):
    (tmp_path / "moduli").mkdir()
    (tmp_path / "moduli" / "a.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "postiperfetti.py").write_text("pass\n", encoding="utf-8")
    prima = firma_albero_produzione(tmp_path)
    (tmp_path / "moduli" / "a.py").write_text("x=2\n", encoding="utf-8")
    dopo = firma_albero_produzione(tmp_path)
    valido, problemi = confronta_firme_produzione(prima, dopo)
    assert valido is False
    assert problemi == ("File produttivo modificato: moduli/a.py",)


def test_due_raccolte_identiche_sono_riproducibili(tmp_path: Path):
    a = _raccolta(tmp_path, "a")
    b = _raccolta(tmp_path, "b")
    valido, problemi = confronta_raccolte_riproducibili(a, b)
    assert valido is True
    assert problemi == ()


def test_riproducibilita_rileva_manomissione(tmp_path: Path):
    a = _raccolta(tmp_path, "a")
    b = _raccolta(tmp_path, "b")
    csv = b / "tabelle" / "RUN.csv"
    csv.write_text(csv.read_text(encoding="utf-8") + "alterato\n", encoding="utf-8")
    valido, problemi = confronta_raccolte_riproducibili(a, b)
    assert valido is False
    assert problemi


def test_cli_audit_finale(tmp_path: Path, capsys):
    from strumenti.cantiere_semantico.cli import main
    radice = _raccolta(tmp_path)
    destinazione = tmp_path / "audit"
    assert main(["audit-finale", str(radice), str(destinazione)]) == 0
    assert "pronto_raccolta_reale: True" in capsys.readouterr().out


def test_riproducibilita_interprocesso(tmp_path: Path):
    radice_progetto = Path(__file__).resolve().parents[4]
    script = r'''
from pathlib import Path
import sys
from cantiere_semantico.test_i9 import _attestatore, _protocollo_e_annate, _sorgente
from strumenti.cantiere_semantico.raccolta import pubblica_raccolta_da_output
base = Path(sys.argv[1])
protocollo, senza, con = _protocollo_e_annate()
src = _sorgente(base / "sorgente", protocollo, senza, con)
pubblica_raccolta_da_output(protocollo, src, base / "corpus", base / "raccolta", attestatore=_attestatore)
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(radice_progetto), str(radice_progetto / "documentazione" / "sviluppo"), str(radice_progetto / "documentazione" / "sviluppo" / "test")))
    for nome in ("processo_a", "processo_b"):
        subprocess.run(
            [sys.executable, "-c", script, str(tmp_path / nome)],
            cwd=radice_progetto,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    valido, problemi = confronta_raccolte_riproducibili(
        tmp_path / "processo_a" / "raccolta",
        tmp_path / "processo_b" / "raccolta",
    )
    assert valido is True, problemi
