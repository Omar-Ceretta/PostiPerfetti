# -*- coding: utf-8 -*-
"""Piccoli helper puri per i testi dinamici dell'interfaccia.

Le funzioni centralizzano gli accordi più comuni senza tentare di dedurre
automaticamente il plurale italiano: ogni chiamante fornisce esplicitamente
le due forme, così anche parole irregolari restano corrette.
"""

from __future__ import annotations


def forma_numerata(numero, singolare: str, plurale: str) -> str:
    """Restituisce ``singolare`` soltanto quando ``numero`` vale esattamente 1."""
    return singolare if int(numero) == 1 else plurale


def quantita(numero, singolare: str, plurale: str) -> str:
    """Compone una quantità con il sostantivo correttamente accordato."""
    return f"{numero} {forma_numerata(numero, singolare, plurale)}"
