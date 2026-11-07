# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""Contatori leggeri per fasi Q21: niente thread, polling o hook globali."""
from __future__ import annotations

from collections import defaultdict
from time import monotonic


def memoria_linux_kib():
    """RSS istantanea e high-water mark del processo, NON delta di heap.

    La misura e' puntuale: un picco tra due campioni potrebbe sfuggire.
    Restituisce None fuori da Linux o se /proc non e' disponibile.
    """
    try:
        with open('/proc/self/status', encoding='ascii') as f:
            valori = {}
            for linea in f:
                chiave, _, resto = linea.partition(':')
                if chiave in ('VmRSS', 'VmHWM'):
                    pezzi = resto.strip().split()
                    if len(pezzi) == 2 and pezzi[1] == 'kB':
                        valori[chiave] = int(pezzi[0])
        if 'VmRSS' in valori and 'VmHWM' in valori:
            return {'rss_kib': valori['VmRSS'], 'hwm_kib': valori['VmHWM']}
    except (OSError, ValueError):
        pass
    return None


class ProfiloPipelineQ21:
    def __init__(self):
        self.inizio = monotonic()
        self.tempi = defaultdict(float)
        self.chiamate = defaultdict(int)
        self.campioni = []
        self.campiona('inizio_pipeline')

    def campiona(self, fase):
        campione = memoria_linux_kib()
        if campione is not None:
            self.campioni.append(dict(fase=fase, tempo_s=round(monotonic()-self.inizio, 5), **campione))

    def misura(self, nome, funzione, *args, **kwargs):
        t = monotonic()
        try:
            return funzione(*args, **kwargs)
        finally:
            self.tempi[nome] += monotonic() - t
            self.chiamate[nome] += 1

    def resoconto(self):
        self.campiona('fine_pipeline')
        totale = monotonic() - self.inizio
        ripartito = sum(self.tempi.values())
        return dict(tempo_totale_s=round(totale, 6),
                    fasi_secondi={k:round(v, 6) for k,v in sorted(self.tempi.items())},
                    chiamate=dict(sorted(self.chiamate.items())),
                    tempo_non_attribuito_s=round(max(0., totale-ripartito), 6),
                    memoria_linux_campionata=self.campioni,
                    nota_memoria='VmRSS e VmHWM del processo ai soli confini delle fasi; non isolano l’heap algoritmico dal corpus già caricato.')
