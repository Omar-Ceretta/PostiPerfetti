# -*- coding: utf-8 -*-
"""Acquisizione facoltativa dell'ingresso IPC Q21 per replay locali.

Il formato pickle e' gia' quello del processo Q21. NON aprire acquisizioni
provenienti da sconosciuti: pickle non e' un formato dati sicuro da importare.
"""
from __future__ import annotations

import os
from pathlib import Path

VARIABILE_CATTURA = 'POSTIPERFETTI_Q21_CATTURA'


def cattura_payload_se_richiesto(payload: bytes) -> Path | None:
    """Salva solo su richiesta, mai sovrascrivendo, con permessi 0600."""
    destinazione = os.environ.get(VARIABILE_CATTURA)
    if not destinazione:
        return None
    if not isinstance(payload, bytes) or not payload:
        raise ValueError('Acquisizione Q21: payload IPC non valido.')
    percorso = Path(destinazione).expanduser().resolve()
    if not percorso.parent.is_dir():
        raise FileNotFoundError(f'Cartella di acquisizione inesistente: {percorso.parent}')
    fd = os.open(percorso, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        percorso.unlink(missing_ok=True)
        raise
    print(f'🔬 Fotografia Q21 acquisita (contiene dati della classe): {percorso}', flush=True)
    return percorso
