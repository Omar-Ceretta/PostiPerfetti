from pathlib import Path

import strumenti.validazione_rc.gate_rc as gate_rc
from strumenti.validazione_rc.gate_rc import (
    EsitoGate,
    RapportoGateRC,
    manifest_codice,
    residui_sorgente,
    scrivi_rapporto_gate,
    STRESS_STRUTTURALE_TIMEOUT_S,
    _parallelismo_stress,
)


def test_manifest_ignora_cache_ma_rileva_modifica_sorgente(tmp_path: Path):
    (tmp_path / "moduli").mkdir()
    sorgente = tmp_path / "moduli" / "x.py"
    sorgente.write_text("X = 1\n", encoding="utf-8")
    h1, _ = manifest_codice(tmp_path)
    cache = tmp_path / "moduli" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"volatile")
    h2, _ = manifest_codice(tmp_path)
    assert h1 == h2
    sorgente.write_text("X = 2\n", encoding="utf-8")
    h3, _ = manifest_codice(tmp_path)
    assert h3 != h1


def test_residui_sorgente_rileva_orig_rej_e_originale(tmp_path: Path):
    (tmp_path / "moduli").mkdir()
    for nome in ("a.py.orig", "b.py.rej", "c_ORIGINALE.py"):
        (tmp_path / "moduli" / nome).write_text("", encoding="utf-8")
    assert residui_sorgente(tmp_path) == [
        "moduli/a.py.orig", "moduli/b.py.rej", "moduli/c_ORIGINALE.py"
    ]


def test_rapporto_gate_scrive_verdetto_e_manifest(tmp_path: Path):
    rapporto = RapportoGateRC(
        profilo="full", root="/x", iniziato_utc="a", concluso_utc="b",
        manifest_prima="abc", manifest_dopo="abc", manifest_stabile=True,
        esiti=(EsitoGate("x", "controllo", True, "PASS", 0.1, 0, ("python",)),),
        verdetto="RC_ELIGIBLE",
    )
    scrivi_rapporto_gate(rapporto, tmp_path)
    assert "RC_ELIGIBLE" in (tmp_path / "GATE_RC.md").read_text(encoding="utf-8")
    assert '"manifest_stabile": true' in (tmp_path / "GATE_RC.json").read_text(encoding="utf-8")


def test_stress_strutturale_limita_parallelismo_e_timeout(monkeypatch):
    monkeypatch.setattr("strumenti.validazione_rc.gate_rc.os.cpu_count", lambda: 16)
    assert _parallelismo_stress() == 4
    monkeypatch.setattr("strumenti.validazione_rc.gate_rc.os.cpu_count", lambda: 2)
    assert _parallelismo_stress() == 2
    monkeypatch.setattr("strumenti.validazione_rc.gate_rc.os.cpu_count", lambda: None)
    assert _parallelismo_stress() == 1
    assert STRESS_STRUTTURALE_TIMEOUT_S == 15


def test_full_usa_limiti_stress_hardware_neutri(monkeypatch, tmp_path: Path):
    chiamate = []

    def finta_esegui(**kwargs):
        chiamate.append(kwargs)
        return EsitoGate(
            kwargs["id_step"], kwargs["descrizione"], kwargs.get("obbligatorio", True),
            "PASS", 0.0, 0, tuple(kwargs["args"]),
        )

    monkeypatch.setattr(gate_rc, "_esegui", finta_esegui)
    monkeypatch.setattr(gate_rc.os, "cpu_count", lambda: 16)
    esiti = []
    gate_rc._aggiungi_full(tmp_path, tmp_path, esiti, riprendi=False)
    stress = next(c for c in chiamate if c["id_step"] == "stress-strutturale")
    args = stress["args"]
    assert args[args.index("--timeout") + 1] == "15"
    assert args[args.index("--parallelismo") + 1] == "4"
