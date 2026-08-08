from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from strumenti.validazione_rc.mutazioni import esegui_mutation_testing


def test_mutation_runner_uccide_un_mutante_senza_toccare_la_root():
    root = Path(__file__).resolve().parents[4]
    bersaglio = root / "moduli" / "metrica_pulizia.py"
    prima = sha256(bersaglio.read_bytes()).hexdigest()

    rapporto = esegui_mutation_testing(
        root,
        timeout_s=6.0,
        ids=["M01_PESO_L2"],
    )

    dopo = sha256(bersaglio.read_bytes()).hexdigest()
    assert rapporto.mutanti == 1
    assert rapporto.uccisi == 1
    assert rapporto.sopravvissuti == 0
    assert rapporto.errori == 0
    assert rapporto.verde
    assert prima == dopo
