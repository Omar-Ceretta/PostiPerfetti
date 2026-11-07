# -*- coding: utf-8 -*-
# Parte di PostiPerfetti (GNU GPLv3).
"""Q2 congelato: riordina i soli pari punteggio in T1-T3, per chiamata.

Trasposizione letterale di confronto_qualita_q2.diversifica_pari_punteggio
senza intercettazione di funzioni globali. Non applicare a T4.
"""
from __future__ import annotations
import itertools
import random


def diversifica_pari_punteggio(indice, seed):
    """Riproduce la sequenza RNG Q2 anche fra le alternative di studenti diversi."""
    rng = random.Random(seed)
    nuovo = {}
    for studente, alternative in indice.items():
        ordinate = []
        for _, equivalenti in itertools.groupby(alternative, key=lambda voce: voce[1]):
            gruppo = list(equivalenti)
            rng.shuffle(gruppo)
            ordinate.extend(gruppo)
        nuovo[studente] = ordinate
    return nuovo
