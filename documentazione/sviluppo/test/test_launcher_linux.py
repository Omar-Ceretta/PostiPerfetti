# -*- coding: utf-8 -*-
"""Regression test del launcher Linux di «PostiPerfetti».

Protegge il contratto introdotto durante l'audit della release:
- requirements.txt obbligatorio e congelato con «==»;
- versioni installate esattamente corrispondenti;
- niente fallback di installazione non versionato;
- rilevazione di un ambiente incoerente;
- conservazione di stderr in caso di crash immediato;
- nessun log permanente dopo un avvio riuscito.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta.
Licenza: GNU GPLv3.
"""

from __future__ import annotations

from types import SimpleNamespace
import subprocess

import pytest

from moduli import postiperfetti_launcher as launcher


def _risultato(
    returncode=0,
    stdout="",
    stderr="",
):
    """Costruisce il minimo risultato compatibile con subprocess.run()."""
    return SimpleNamespace(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ============================================================================
# requirements.txt
# ============================================================================

def test_requirements_bloccati_validi(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# Runtime\n"
        "PySide6==6.11.1\n"
        "\n"
        "XlsxWriter==3.2.9  # esportazione\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )

    requisiti, errori = launcher.leggi_requirements_bloccati()

    assert errori == []
    assert requisiti == [
        ("PySide6", "6.11.1"),
        ("XlsxWriter", "3.2.9"),
    ]


def test_requirements_mancante_e_un_errore(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements-assente.txt"

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )

    requisiti, errori = launcher.leggi_requirements_bloccati()

    assert requisiti == []
    assert errori
    assert "non trovato" in errori[0]


@pytest.mark.parametrize(
    "contenuto",
    [
        "PySide6>=6.11,<7\n",
        "PySide6\n",
        "XlsxWriter~=3.2\n",
    ],
)
def test_requirements_non_congelato_viene_rifiutato(
    tmp_path,
    monkeypatch,
    contenuto,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        contenuto,
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )

    _, errori = launcher.leggi_requirements_bloccati()

    assert errori
    assert any(
        "non congelato con ==" in errore
        for errore in errori
    )


def test_requirements_vuoto_viene_rifiutato(
    tmp_path,
    monkeypatch,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "# Nessuna dipendenza\n\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )

    requisiti, errori = launcher.leggi_requirements_bloccati()

    assert requisiti == []
    assert errori
    assert "non contiene dipendenze runtime" in errori[0]


# ============================================================================
# verifica dell'ambiente
# ============================================================================

def test_ambiente_corretto_non_segnala_problemi(
    tmp_path,
    monkeypatch,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "PySide6==6.11.1\n"
        "XlsxWriter==3.2.9\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )
    monkeypatch.setattr(
        launcher,
        "PYTHON_VENV",
        tmp_path / "python3",
    )
    monkeypatch.setattr(
        launcher,
        "venv_funzionante",
        lambda: True,
    )

    def run_finto(comando, **kwargs):
        return _risultato()

    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        run_finto,
    )

    assert launcher.problemi_ambiente() == []
    assert launcher.ambiente_incompleto() is False


def test_versione_installata_diversa_viene_rilevata(
    tmp_path,
    monkeypatch,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "PySide6==6.11.1\n"
        "XlsxWriter==3.2.8\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )
    monkeypatch.setattr(
        launcher,
        "PYTHON_VENV",
        tmp_path / "python3",
    )
    monkeypatch.setattr(
        launcher,
        "venv_funzionante",
        lambda: True,
    )

    def run_finto(comando, **kwargs):
        # Verifica delle versioni:
        # python -c SCRIPT nome versione_attesa
        if (
            len(comando) >= 5
            and comando[-2] == "XlsxWriter"
            and comando[-1] == "3.2.8"
        ):
            return _risultato(returncode=1)

        # Seconda interrogazione richiesta dal launcher per conoscere
        # la versione realmente installata.
        if (
            len(comando) >= 4
            and comando[-1] == "XlsxWriter"
        ):
            return _risultato(
                stdout="3.2.9\n",
            )

        return _risultato()

    monkeypatch.setattr(
        launcher.subprocess,
        "run",
        run_finto,
    )

    problemi = launcher.problemi_ambiente()

    assert any(
        "XlsxWriter" in problema
        and "3.2.9" in problema
        and "3.2.8" in problema
        for problema in problemi
    )

    assert launcher.ambiente_incompleto() is True


def test_venv_non_funzionante_viene_rilevato(
    tmp_path,
    monkeypatch,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "PySide6==6.11.1\n"
        "XlsxWriter==3.2.9\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )
    monkeypatch.setattr(
        launcher,
        "venv_funzionante",
        lambda: False,
    )

    problemi = launcher.problemi_ambiente()

    assert problemi
    assert "ambiente virtuale" in problemi[0]


# ============================================================================
# riparazione: requirements.txt resta l'unica fonte
# ============================================================================

def test_riparazione_usa_solo_requirements_txt(
    tmp_path,
    monkeypatch,
):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "PySide6==6.11.1\n"
        "XlsxWriter==3.2.9\n",
        encoding="utf-8",
    )

    python_venv = tmp_path / "python3"

    monkeypatch.setattr(
        launcher,
        "FILE_REQUIREMENTS",
        requirements,
    )
    monkeypatch.setattr(
        launcher,
        "PYTHON_VENV",
        python_venv,
    )

    comando_eseguito = []

    def progresso_finto(comando, titolo=""):
        comando_eseguito.extend(comando)
        return True

    monkeypatch.setattr(
        launcher,
        "esegui_con_progresso",
        progresso_finto,
    )
    monkeypatch.setattr(
        launcher,
        "problemi_ambiente",
        lambda: [],
    )

    assert launcher.installa_dipendenze() is True

    assert comando_eseguito == [
        str(python_venv),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(requirements),
    ]

    # Guardia esplicita contro il vecchio fallback:
    # i pacchetti non devono essere inseriti direttamente nel comando.
    assert "PySide6" not in comando_eseguito
    assert "XlsxWriter" not in comando_eseguito


# ============================================================================
# diagnostica del crash immediato
# ============================================================================

def test_crash_immediato_salva_stderr(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        launcher,
        "CARTELLA_PROGETTO",
        tmp_path,
    )
    monkeypatch.setattr(
        launcher,
        "PYTHON_VENV",
        tmp_path / ".venv" / "bin" / "python3",
    )
    monkeypatch.setattr(
        launcher,
        "FILE_PRINCIPALE",
        tmp_path / "postiperfetti.py",
    )
    monkeypatch.setattr(
        launcher,
        "in_terminale",
        lambda: True,
    )

    class ProcessoCrash:
        def __init__(self, stderr):
            self.stderr = stderr
            self.stderr.write(
                b'qt.qpa.plugin: Could not load '
                b'the Qt platform plugin "xcb"\n'
            )
            self.stderr.flush()

        def wait(self, timeout):
            return 42

    def popen_finto(
        comando,
        start_new_session,
        stderr,
    ):
        return ProcessoCrash(stderr)

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        popen_finto,
    )

    with pytest.raises(SystemExit) as uscita:
        launcher.avvia_applicazione()

    assert uscita.value.code == 1

    log = tmp_path / "log" / "diagnostica_avvio.log"

    assert log.is_file()

    testo = log.read_text(encoding="utf-8")

    assert "codice di uscita 42" in testo
    assert 'Qt platform plugin "xcb"' in testo


def test_avvio_riuscito_non_lascia_log(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        launcher,
        "CARTELLA_PROGETTO",
        tmp_path,
    )
    monkeypatch.setattr(
        launcher,
        "PYTHON_VENV",
        tmp_path / ".venv" / "bin" / "python3",
    )
    monkeypatch.setattr(
        launcher,
        "FILE_PRINCIPALE",
        tmp_path / "postiperfetti.py",
    )
    monkeypatch.setattr(
        launcher,
        "in_terminale",
        lambda: True,
    )

    log = tmp_path / "log" / "diagnostica_avvio.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        "vecchia diagnostica",
        encoding="utf-8",
    )

    class ProcessoVivo:
        def wait(self, timeout):
            raise subprocess.TimeoutExpired(
                cmd="postiperfetti",
                timeout=timeout,
            )

    def popen_finto(
        comando,
        start_new_session,
        stderr,
    ):
        return ProcessoVivo()

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        popen_finto,
    )

    with pytest.raises(SystemExit) as uscita:
        launcher.avvia_applicazione()

    assert uscita.value.code == 0
    assert not log.exists()
