# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""Gate I2c: uscita mensile sicura dalla pipeline Q21 condivisa.

Non genera, seleziona o rifinisce: limita a un mese il risultato gia'
verificato dal processo Q21 e non promuove esiti parziali/annullati.
"""
from __future__ import annotations

from moduli.persistenza.risultati_annuali import (
    EsitoRisultatoAnnuale, classifica_risultato_annuale,
)


def estrai_mese_q21(risultato, fotografia, *, adiacenze_attese=None):
    """Restituisce un mese nel contratto fisico Mensile del Layout unico."""
    classificato = classifica_risultato_annuale(risultato)
    if (classificato.esito != EsitoRisultatoAnnuale.PRONTO
            or len(classificato.mesi) != 1
            or len(risultato.get('chiavi') or ()) != 1):
        raise ValueError('Mensile Q21 non completo o annullato: nessun mese applicabile.')
    schema_id = fotografia.layout.schema.identita_semantica()
    if classificato.info.get('schema_identita') != schema_id:
        raise ValueError('Mensile Q21: identita del Layout non corrispondente.')
    mese = classificato.mesi[0]
    if not isinstance(mese, dict) or mese.get('schema_identita') != schema_id:
        raise ValueError('Mensile Q21: fotografia del mese non coerente.')
    fotografia.verifica_risultato(mese)
    # In assenza della fotografia, un Report mensile potrebbe dichiarare
    # zero riusi pur con adiacenze precedenti presenti nello Storico.
    precedenti = mese.get('adiacenze_prima')
    if (not isinstance(precedenti, set)
            or any(not isinstance(coppia, tuple) or len(coppia) != 2
                   or not all(isinstance(nome, str) and nome.strip() for nome in coppia)
                   or coppia[0] >= coppia[1] for coppia in precedenti)):
        raise ValueError('Mensile Q21: fotografia dei precedenti mancante o non valida.')
    if adiacenze_attese is not None and precedenti != adiacenze_attese:
        raise ValueError('Mensile Q21: precedenti diversi da quelli fotografati all’avvio.')
    if (not mese.get('gruppi') or not mese.get('collocazioni')
            or len(mese['gruppi']) != len(mese['collocazioni'])):
        raise ValueError('Mensile Q21: gruppi e collocazioni incompleti.')
    return mese
