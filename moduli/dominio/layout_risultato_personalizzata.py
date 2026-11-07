# -*- coding: utf-8 -*-
"""Adattatore puro fra collocazioni del motore e piantina Personalizzata.

Non importa Qt. Verifica che la fotografia visuale congelata all'avvio e le
collocazioni restituite dal matcher descrivano esattamente gli stessi blocchi e
posti, poi espone l'occupazione per posto al renderer GUI.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections.abc import Sequence

from moduli.dominio.aula_personalizzata import IstantaneaVisualeAulaPersonalizzata
from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.metrica_pulizia import nome_completo


def occupazioni_personalizzata(
    collocazioni: Sequence[CollocazioneGruppoBlocco],
) -> dict[tuple[str, int], str]:
    """Restituisce ``(id blocco, indice posto) -> nome`` senza perdere ordine."""
    risultato: dict[tuple[str, int], str] = {}
    for collocazione in collocazioni:
        for posto, studente in collocazione.occupazioni:
            chiave = (collocazione.blocco.id, posto.indice)
            if chiave in risultato:
                raise ValueError(f"Posto Personalizzato occupato due volte: {chiave!r}.")
            risultato[chiave] = nome_completo(studente)
    return risultato


def valida_layout_risultato_personalizzata(
    istantanea: IstantaneaVisualeAulaPersonalizzata,
    collocazioni: Sequence[CollocazioneGruppoBlocco],
) -> dict[tuple[str, int], str]:
    """Valida che collocazioni e fotografia visuale descrivano gli stessi posti."""
    if not isinstance(istantanea, IstantaneaVisualeAulaPersonalizzata):
        raise TypeError("istantanea deve essere IstantaneaVisualeAulaPersonalizzata.")

    ids_blocchi_layout = {blocco.id for blocco in istantanea.blocchi}
    ids_blocchi_collocati = {c.blocco.id for c in collocazioni}
    if ids_blocchi_layout != ids_blocchi_collocati:
        mancanti = sorted(ids_blocchi_layout - ids_blocchi_collocati)
        inattesi = sorted(ids_blocchi_collocati - ids_blocchi_layout)
        raise ValueError(
            "Collocazioni non coerenti con l'aula Personalizzata: "
            f"mancanti={mancanti}, inattesi={inattesi}."
        )

    occupazioni = occupazioni_personalizzata(collocazioni)
    posti_layout = {
        (blocco.id, indice)
        for blocco in istantanea.blocchi
        for indice in range(blocco.capienza)
    }
    if set(occupazioni) != posti_layout:
        raise ValueError(
            "Le collocazioni Personalizzata non occupano esattamente tutti i posti."
        )
    return occupazioni

