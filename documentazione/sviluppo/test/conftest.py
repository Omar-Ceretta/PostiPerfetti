from __future__ import annotations

import sys
from pathlib import Path

# Test e strumenti sono archiviati sotto documentazione/, mentre il runtime
# resta nella root. Rendiamo entrambi importabili senza lasciare configurazioni
# di sviluppo nella radice pubblica del progetto.
RADICE = Path(__file__).resolve().parents[3]
for percorso in (RADICE / "documentazione" / "sviluppo", RADICE):
    testo = str(percorso)
    if testo not in sys.path:
        sys.path.insert(0, testo)


# ─────────────────────────────────────────────────────────────────────────
#  Controllo preliminare delle dipendenze runtime
#
#  Senza questo controllo, lanciare la suite in un interprete sprovvisto di
#  PySide6 produce un errore di *collection*: una traceback di importlib
#  lunga dieci righe che termina con «No module named 'PySide6'» e la suite
#  interrotta. Il messaggio è tecnicamente corretto ma dice la cosa
#  sbagliata: sembra un difetto del progetto, mentre è semplicemente
#  l'ambiente virtuale non attivo.
#
#  La suite continua a FALLIRE — le dipendenze in requirements.txt non sono
#  facoltative e saltare i test che le usano nasconderebbe regressioni vere.
#  Cambia soltanto il messaggio: una riga che dice cosa manca e come
#  rimediare, al posto della traceback.
#
#  L'elenco è letto da requirements.txt, che resta la fonte unica: se un
#  domani si aggiungesse una dipendenza, il controllo la coprirebbe da solo.
# ─────────────────────────────────────────────────────────────────────────

import re
from importlib.metadata import PackageNotFoundError, version as versione_installata

import pytest

REQUIREMENTS = RADICE / "requirements.txt"


def _dipendenze_richieste() -> list[tuple[str, str]]:
    """Legge (nome, versione attesa) da requirements.txt."""
    if not REQUIREMENTS.is_file():
        return []
    voci: list[tuple[str, str]] = []
    for riga in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        confronto = re.match(r"^([A-Za-z0-9._-]+)\s*==\s*([^\s;#]+)", riga)
        if confronto:
            voci.append((confronto.group(1), confronto.group(2)))
    return voci


def pytest_configure(config: pytest.Config) -> None:
    assenti: list[str] = []
    diverse: list[str] = []

    for nome, attesa in _dipendenze_richieste():
        try:
            presente = versione_installata(nome)
        except PackageNotFoundError:
            assenti.append(f"{nome}=={attesa}")
            continue
        if presente != attesa:
            diverse.append(f"{nome}: richiesta {attesa}, installata {presente}")

    if assenti:
        elenco = "\n  ".join(assenti)
        raise pytest.UsageError(
            "\n"
            "Dipendenze runtime mancanti in questo interprete Python:\n"
            f"  {elenco}\n"
            "\n"
            f"Interprete in uso: {sys.executable}\n"
            "\n"
            "Quasi sempre significa che l'ambiente virtuale non e' attivo.\n"
            "Dalla radice del progetto:\n"
            "\n"
            "  source .venv/bin/activate\n"
            "  pip install -r documentazione/sviluppo/requirements-dev.txt\n"
            "\n"
            "La suite non viene saltata di proposito: i test che usano queste\n"
            "librerie verificano comportamenti reali del programma, e farli\n"
            "passare in loro assenza nasconderebbe eventuali regressioni.\n"
        )

    if diverse:
        for avviso in diverse:
            config.issue_config_time_warning(
                pytest.PytestConfigWarning(
                    f"Versione diversa da quella congelata per la release — {avviso}"
                ),
                stacklevel=2,
            )
