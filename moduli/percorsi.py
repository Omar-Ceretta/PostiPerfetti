# -*- coding: utf-8 -*-
"""Percorsi locali e visibili di «PostiPerfetti».

Tutti i file usati dall'applicazione restano dentro la directory scelta per
l'installazione o, durante lo sviluppo, dentro la radice del progetto.

La struttura corrente è intenzionalmente netta e non implementa migrazioni,
fallback o compatibilità con organizzazioni precedenti::

    risorse/   icone, font e altri file distribuiti con il programma
    classi/    file .txt creati o modificati dal docente
    stato/     configurazione JSON e backup
    log/       diagnostica tecnica, incluso crash.log

Nessun percorso predefinito usa cartelle di profilo nascoste come
``~/.local/share`` o ``%APPDATA%``. In una build PyInstaller le risorse possono
essere lette dalla radice del bundle; classi, stato e log restano invece
accanto all'eseguibile, nella cartella scelta dall'utente.

Gli override d'ambiente servono esclusivamente allo sviluppo e ai collaudi:

``POSTIPERFETTI_INSTALL_ROOT``
    directory che contiene ``classi/``, ``stato/`` e ``log/``;
``POSTIPERFETTI_RESOURCE_ROOT``
    radice che contiene la cartella ``risorse/``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

VARIABILE_RADICE_INSTALLAZIONE = "POSTIPERFETTI_INSTALL_ROOT"
VARIABILE_RADICE_RISORSE = "POSTIPERFETTI_RESOURCE_ROOT"

CARTELLA_RISORSE = "risorse"
CARTELLA_CLASSI = "classi"
CARTELLA_STATO = "stato"
CARTELLA_LOG = "log"


def _radice_progetto_sorgente() -> Path:
    """Restituisce la radice del progetto partendo da ``moduli/percorsi.py``."""
    return Path(__file__).resolve().parents[1]


def _radice_installazione() -> Path:
    """Restituisce la cartella visibile scelta per l'installazione."""
    override = os.environ.get(VARIABILE_RADICE_INSTALLAZIONE)
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return _radice_progetto_sorgente()


def _radice_risorse() -> Path:
    """Individua la radice che contiene la cartella ``risorse/``."""
    override = os.environ.get(VARIABILE_RADICE_RISORSE)
    if override:
        return Path(override).expanduser().resolve()

    radice_bundle = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and radice_bundle:
        return Path(radice_bundle).resolve()

    return _radice_installazione()


def get_installation_path(*parti: str | os.PathLike[str]) -> str:
    """Restituisce un percorso dentro la directory locale d'installazione."""
    return os.fspath(_radice_installazione().joinpath(*parti))


def get_export_path(nome_file: str | os.PathLike[str]) -> str:
    """Propone un file di esportazione nella radice dell'installazione.

    Il nome viene ridotto alla sola componente finale: questa funzione prepara
    esclusivamente il percorso iniziale di ``QFileDialog`` e non deve permettere
    a un nome suggerito di uscire dalla cartella visibile di PostiPerfetti.
    """
    nome = Path(nome_file).name
    return get_installation_path(nome)


def get_resource_path(*parti: str | os.PathLike[str]) -> str:
    """Restituisce un percorso dentro le risorse distribuite con l'app."""
    return os.fspath(
        _radice_risorse().joinpath(CARTELLA_RISORSE, *parti)
    )


def get_user_data_path(
    *parti: str | os.PathLike[str],
    crea_genitori: bool = False,
) -> str:
    """Restituisce un percorso modificabile dentro l'installazione scelta."""
    base = _radice_installazione()
    base.mkdir(parents=True, exist_ok=True)
    percorso = base.joinpath(*parti)
    if crea_genitori and parti:
        percorso.parent.mkdir(parents=True, exist_ok=True)
    return os.fspath(percorso)


def _percorso_area(
    area: str,
    *parti: str | os.PathLike[str],
    crea_genitori: bool = False,
) -> str:
    """Costruisce un percorso in una delle aree locali dell'applicazione."""
    base = Path(get_user_data_path(area))
    base.mkdir(parents=True, exist_ok=True)
    percorso = base.joinpath(*parti)
    if crea_genitori and parti:
        percorso.parent.mkdir(parents=True, exist_ok=True)
    return os.fspath(percorso)


def get_classi_path(
    *parti: str | os.PathLike[str],
    crea_genitori: bool = False,
) -> str:
    """Restituisce un percorso nella cartella visibile dei file-classe."""
    return _percorso_area(
        CARTELLA_CLASSI, *parti, crea_genitori=crea_genitori
    )


def get_state_path(
    *parti: str | os.PathLike[str],
    crea_genitori: bool = False,
) -> str:
    """Restituisce un percorso nella cartella locale dello stato applicativo."""
    return _percorso_area(
        CARTELLA_STATO, *parti, crea_genitori=crea_genitori
    )


def get_log_path(
    *parti: str | os.PathLike[str],
    crea_genitori: bool = False,
) -> str:
    """Restituisce un percorso nella cartella locale della diagnostica."""
    return _percorso_area(
        CARTELLA_LOG, *parti, crea_genitori=crea_genitori
    )


def inizializza_struttura_dati_utente() -> str:
    """Crea ``classi/``, ``stato/`` e ``log/`` nella radice locale."""
    radice = Path(get_user_data_path())
    for nome in (CARTELLA_CLASSI, CARTELLA_STATO, CARTELLA_LOG):
        (radice / nome).mkdir(parents=True, exist_ok=True)
    return os.fspath(radice)


def inizializza_cartella_classi() -> str:
    """Prepara la struttura locale e restituisce la cartella delle classi."""
    inizializza_struttura_dati_utente()
    return get_classi_path()
