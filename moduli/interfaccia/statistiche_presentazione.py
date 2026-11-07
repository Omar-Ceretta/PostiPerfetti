# -*- coding: utf-8 -*-
"""Aggregazioni di sola presentazione per lo Storico con Layout unico.

Nessuna modifica alle voci persistenti: le vicinanze vengono mostrate per
coppia, indipendentemente dagli identificatori tecnici dei vecchi rami.
"""


def vicinanze_per_coppia(stats):
    aggregate = {}
    for dati in stats.get('coppie_frequenza', {}).values():
        coppia = tuple(dati['coppia'])
        voce = aggregate.setdefault(coppia, {
            'coppia': coppia, 'totale': 0, 'assegnazioni': [],
        })
        voce['totale'] += int(dati.get('count', 0))
        voce['assegnazioni'].extend(dati.get('assegnazioni', []))
    return sorted(aggregate.values(), key=lambda r: (
        -r['totale'], tuple(nome.casefold() for nome in r['coppia']),
    ))


def compagni_per_studente(compagni):
    aggregate = {}
    for dati in compagni.values():
        nome = dati['compagno']
        voce = aggregate.setdefault(nome, {
            'compagno': nome, 'count': 0, 'assegnazioni': [],
        })
        voce['count'] += int(dati.get('count', 0))
        voce['assegnazioni'].extend(dati.get('assegnazioni', []))
    return sorted(aggregate.values(), key=lambda r: (
        -r['count'], r['compagno'].casefold(),
    ))
