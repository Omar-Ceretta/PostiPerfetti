# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""Copia effimera dello Storico del Layout unico per la ricerca Q21.

La configurazione utente non viene scritta dal calcolo. Ogni stagione
aggiorna esclusivamente una copia delle frequenze fotografate all'avvio.
"""

from __future__ import annotations

from copy import deepcopy

from moduli.calcolo.ingresso_q21 import IngressoQ21
from moduli.persistenza.strato_storico import CHIAVE_BLACKLIST_PER_MODO


class ConfigCalcoloQ21:
    """Configurazione effimera con la sola blacklist Personalizzata.

    `copia_temporanea` rispetta il contratto del generatore produttivo:
    l'aggiornamento delle frequenze avviene solo sulla copia della stagione.
    """

    def __init__(self, ingresso: IngressoQ21):
        if not isinstance(ingresso, IngressoQ21):
            raise TypeError('Serve un IngressoQ21 fotografato.')
        if ingresso.fotografia.identita() != ingresso.identita_fotografia:
            raise ValueError('Fotografia Q21 alterata.')
        self.config_data = {
            'storico_assegnazioni': [],
            'coppie_da_evitare': [],
            CHIAVE_BLACKLIST_PER_MODO['terzetti']: [],
            CHIAVE_BLACKLIST_PER_MODO['personalizzata']: [
                dict(tipo='adiacenza', studenti=[a, b], volte_usata=n)
                for a, b, n in ingresso.frequenze_iniziali
            ],
        }

    def copia_temporanea(self):
        copia = object.__new__(type(self))
        copia.config_data = deepcopy(self.config_data)
        return copia
