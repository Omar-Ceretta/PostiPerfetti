# -*- coding: utf-8 -*-
"""Identità di versione di «PostiPerfetti».

Questo modulo è la fonte unica della versione dell'applicazione.
Packaging, build e interfaccia devono ricavare la propria versione da qui:
non va duplicata manualmente in altri file.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import re


VERSIONE = "0.8.0"

_PATTERN_VERSIONE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)

if not _PATTERN_VERSIONE.fullmatch(VERSIONE):
    raise RuntimeError(
        "VERSIONE deve usare il formato MAJOR.MINOR.PATCH, "
        f"ricevuto: {VERSIONE!r}"
    )


VERSIONE_PARTI = tuple(
    int(parte) for parte in VERSIONE.split(".")
)

VERSIONE_WINDOWS = (
    *VERSIONE_PARTI,
    0,
)

TAG_RELEASE = f"v{VERSIONE}"
