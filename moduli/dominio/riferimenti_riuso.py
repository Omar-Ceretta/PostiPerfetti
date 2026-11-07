# -*- coding: utf-8 -*-
"""Riferimenti leggibili per i riusi nella proposta annuale a Layout unico.

Le coppie e la cronologia sono sempre derivate dagli abbinamenti fisici. Questo
modulo non muta lo Storico e non esegue generazioni o rifiniture.
"""
from moduli.dominio.metrica_pulizia import adiacenze_per_blacklist_terzetti
from moduli.persistenza.strato_storico import trova_quando_coppia_usata


def ultimi_usi_nell_annata(mesi, indice):
    """Restituisce l'ultimo mese precedente per coppia nell'ordine finale R2."""
    riferimenti = {}
    for numero, mese in enumerate(mesi[:indice], 1):
        for coppia in adiacenze_per_blacklist_terzetti(mese.get('gruppi') or []):
            riferimenti[tuple(sorted(coppia))] = f'mese {numero}'
    return riferimenti


def riferimento_riuso(coppia, config_app, ultimi_mesi=None):
    """Preferisce la proposta in memoria; altrimenti la voce dello Storico."""
    chiave = tuple(sorted(coppia))
    riferimento = (ultimi_mesi or {}).get(chiave)
    if riferimento:
        return f'ultimo uso: {riferimento}'
    if config_app is not None:
        riferimento = trova_quando_coppia_usata(set(chiave), config_app, 'personalizzata')
        if riferimento:
            for prefisso in ('usata in: ', 'ultima volta: ', 'in: '):
                if riferimento.startswith(prefisso):
                    riferimento = riferimento[len(prefisso):]
                    break
            for suffisso in (' [fisica]', ' [coppia]', ' [terzetto]', ' [quartetto]'):
                if riferimento.endswith(suffisso):
                    riferimento = riferimento[:-len(suffisso)]
                    break
            return f'ultimo uso: {riferimento}'
    return 'assegnazione precedente non identificabile'


def annota_note_riuso(note, coppia, adiacenze_gia_usate, config_app,
                       ultimi_mesi=None):
    """Aggiunge il riferimento SOLO alle coppie effettivamente riutilizzate."""
    note = list(note)
    chiave = tuple(sorted(coppia))
    if adiacenze_gia_usate is None or chiave not in adiacenze_gia_usate:
        return note
    riferimento = riferimento_riuso(chiave, config_app, ultimi_mesi)
    return [
        f'{nota} ({riferimento})'
        if 'Coppia già usata' in nota and 'ultimo uso:' not in nota
        else nota
        for nota in note
    ]
