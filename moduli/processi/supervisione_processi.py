# -*- coding: utf-8 -*-
"""Primitive pure per chiudere in modo finito i processi worker.

Il calcolo normale non riceve alcun timeout. Un limite viene applicato soltanto
quando il bridge ha gia' ricevuto un esito terminale oppure quando il canale IPC
non e' piu' utilizzabile: in entrambi i casi il processo figlio non puo' piu'
fornire lavoro utile alla GUI e non deve restare appeso indefinitamente.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EsitoChiusuraProcesso:
    """Descrive come si e' conclusa la fase di spegnimento di un worker."""

    avviato: bool
    uscita_forzata: bool
    kill_usato: bool
    ancora_vivo: bool


def _processo_avviato(processo) -> bool:
    """Riconosce anche in sicurezza un ``multiprocessing.Process`` non partito."""
    return processo is not None and getattr(processo, "pid", None) is not None


def finalizza_processo(
    processo,
    *,
    terminale_ricevuto: bool,
    canale_inutilizzabile: bool,
    tempo_grazia: float = 1.0,
) -> EsitoChiusuraProcesso:
    """Raccoglie un processo senza poter bloccare indefinitamente il bridge.

    Nessun timeout viene imposto al *calcolo*: questa funzione viene chiamata
    solo dopo che il loop IPC e' terminato. Se il figlio e' gia' morto, viene
    semplicemente raccolto. Se e' ancora vivo, puo' essere terminato soltanto
    quando il risultato terminale e' gia' stato consegnato oppure quando il
    canale IPC e' definitivamente perso.
    """
    if not _processo_avviato(processo):
        return EsitoChiusuraProcesso(False, False, False, False)

    grazia = max(0.0, float(tempo_grazia))

    try:
        vivo = bool(processo.is_alive())
    except Exception:
        vivo = False

    if not vivo:
        # Il figlio e' gia' concluso: join(0) serve soltanto a raccoglierlo.
        try:
            processo.join(timeout=0)
        except Exception:
            pass
        return EsitoChiusuraProcesso(True, False, False, False)

    if not (terminale_ricevuto or canale_inutilizzabile):
        # Stato difensivo: non uccidiamo mai un calcolo ancora legittimamente
        # in corso. Il chiamante non deve entrare qui durante il loop normale.
        return EsitoChiusuraProcesso(True, False, False, True)

    try:
        processo.join(timeout=grazia)
    except Exception:
        pass

    try:
        vivo = bool(processo.is_alive())
    except Exception:
        vivo = False
    if not vivo:
        return EsitoChiusuraProcesso(True, False, False, False)

    uscita_forzata = True
    try:
        processo.terminate()
    except Exception:
        pass
    try:
        processo.join(timeout=grazia)
    except Exception:
        pass

    try:
        vivo = bool(processo.is_alive())
    except Exception:
        vivo = False
    if not vivo:
        return EsitoChiusuraProcesso(True, uscita_forzata, False, False)

    kill_usato = False
    kill = getattr(processo, "kill", None)
    if callable(kill):
        kill_usato = True
        try:
            kill()
        except Exception:
            pass
        try:
            processo.join(timeout=grazia)
        except Exception:
            pass

    try:
        ancora_vivo = bool(processo.is_alive())
    except Exception:
        ancora_vivo = False
    return EsitoChiusuraProcesso(
        True,
        uscita_forzata,
        kill_usato,
        ancora_vivo,
    )
