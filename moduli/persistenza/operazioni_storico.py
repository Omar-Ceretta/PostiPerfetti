# -*- coding: utf-8 -*-
"""Comandi sullo Storico: producono una nuova configurazione, senza I/O o Qt.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
from copy import deepcopy

from moduli.persistenza.report_personalizzata import sostituisci_nome_assegnazione_report
from moduli.persistenza.rotazioni_storico import ricostruisci_rotazioni


def _valida_indice(dati, indice):
    if type(indice) is not int or not 0 <= indice < len(dati["storico_assegnazioni"]):
        raise ValueError("Indice dello Storico non valido.")


def rinomina_assegnazione(dati, indice, nome):
    """Restituisce una copia con nome e testata del Report allineati."""
    _valida_indice(dati, indice)
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError("Il nome dell'assegnazione non può essere vuoto.")
    nuova = deepcopy(dati)
    voce = nuova["storico_assegnazioni"][indice]
    voce["nome"] = nome.strip()
    if voce.get("report_completo"):
        voce["report_completo"] = sostituisci_nome_assegnazione_report(
            voce["report_completo"], nome.strip(),
        )
    return nuova


def elimina_assegnazione(dati, indice):
    """Elimina dalla copia e ricostruisce soltanto le rotazioni residue."""
    _valida_indice(dati, indice)
    nuova = deepcopy(dati)
    del nuova["storico_assegnazioni"][indice]
    nuova.update(ricostruisci_rotazioni(nuova["storico_assegnazioni"]))
    return nuova
