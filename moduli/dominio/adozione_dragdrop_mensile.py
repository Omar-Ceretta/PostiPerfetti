# -*- coding: utf-8 -*-
"""D3 — Converte una bozza Mensile approvata in dati per il flusso già esistente.

Niente Qt, processi, report o scritture. La validazione avviene sulla stessa
fotografia immutabile da cui proviene la proposta automatica.
"""

from __future__ import annotations

from dataclasses import replace

from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.disposizione_effettiva import da_risultato_personalizzata
from moduli.dominio.editing_disposizione import BozzaDisposizione
from moduli.dominio.metrica_pulizia import Gruppo


def prepara_risultato_editato(
    dati: dict, bozza: BozzaDisposizione, *,
    disposizione_all_apertura=None,
) -> dict:
    """Restituisce un risultato nuovo e completo, senza mutare *dati* o *bozza*.

    Blocca bozze di altri risultati (anche se validi) e ricostruisce da zero
    studenti, gruppi e collocazioni nell'ordine dei posti del Layout congelato.
    """
    if not isinstance(dati, dict) or not isinstance(bozza, BozzaDisposizione):
        raise ValueError('La proposta mensile o la bozza non è valida.')
    foto = dati.get('fotografia_generazione')
    if foto is None or foto is not bozza.fotografia:
        raise ValueError('La bozza appartiene a una generazione differente.')
    if dati.get('schema_identita') != foto.layout.schema.identita_semantica():
        raise ValueError('Identità del Layout non coerente con la generazione.')
    if not dati.get('collocazioni') or not dati.get('gruppi'):
        raise ValueError('Il risultato originale è incompleto.')
    originale = da_risultato_personalizzata(
        foto.layout.schema, dati['collocazioni'],
        istantanea_visuale=foto.layout.istantanea_visuale,
        genere_misto=foto.genere_misto,
    )
    # Per riaperture successive, la proposta di partenza può già essere stata
    # modificata. La bozza conserva comunque la disposizione Q21 originale.
    if disposizione_all_apertura is not None and originale != disposizione_all_apertura:
        raise ValueError('La proposta è cambiata mentre era aperto il Drag & Drop.')
    automatica = dati.get('disposizione_automatica', originale)
    if automatica != bozza.originale:
        raise ValueError('La proposta è cambiata mentre era aperto il Drag & Drop.')
    if bozza.corrente.occupazioni == originale.occupazioni:
        raise ValueError('Nessuna modifica manuale da adottare.')

    # Rileva manomissioni, errori di copertura e violazioni HARD prima di creare
    # un solo oggetto che possa essere inoltrato a Report/Storico.
    per_nome = {s.get_nome_completo(): s for s in foto.crea_studenti()}
    occupanti = dict(bozza.corrente.occupazioni)
    gruppi = []
    collocazioni = []
    for blocco in foto.layout.schema.blocchi:
        membri = tuple(per_nome[occupanti[p.id]] for p in blocco.posti)
        gruppo = Gruppo('coppia' if blocco.capienza == 2 else 'terzetto', membri)
        gruppi.append(gruppo)
        collocazioni.append(CollocazioneGruppoBlocco(gruppo, blocco))

    risultato = dict(dati)
    risultato['gruppi'] = tuple(gruppi)
    risultato['collocazioni'] = tuple(collocazioni)
    risultato['disposizione_automatica'] = automatica
    if bozza.corrente.occupazioni != automatica.occupazioni:
        risultato['modificata_manualmente'] = True
    else:
        risultato.pop('modificata_manualmente', None)
    # Il report/statistiche originali NON rappresentano più la proposta corrente.
    for chiave in ('report_completo', 'statistiche_generali', 'configurazione_aula'):
        risultato.pop(chiave, None)
    verificata = foto.verifica_risultato(risultato)
    if replace(
        verificata, modificata_manualmente=bozza.corrente.modificata_manualmente,
    ) != bozza.corrente:
        raise ValueError('La disposizione verificata non coincide con la bozza.')
    return risultato


def metadati_casualita_salvabili(dati: dict):
    """Non attribuisce alla disposizione manuale i metadati del solver Q21.

    I metadati originali restano nella proposta in memoria e possono essere
    consultati per diagnosi; soltanto la voce persistita ne viene privata.
    """
    if not isinstance(dati, dict):
        raise TypeError("La proposta mensile deve essere un dizionario.")
    if dati.get("modificata_manualmente"):
        return None
    return dati.get("metadati_casualita")
