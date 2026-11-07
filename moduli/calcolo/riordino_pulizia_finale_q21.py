# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""I2g: riordino di *presentazione* dopo la scelta Q21 produttiva.

Non genera e non sceglie candidate, non altera Q21/R2. Ammette soltanto
scambi a parita' di TUTTE le metriche temporali e delle metriche annuali,
che migliorano strettamente la gravita' mensile delle disposizioni.
L'ordine cronologico e le fotografie dei precedenti vengono ricostruiti.
"""
from __future__ import annotations

from moduli.dominio.metrica_pulizia import punteggio_stagione
from moduli.processi.ponte_risultati_q21 import prepara_risultato_fisico_q21
from moduli.calcolo.politica_annuale import (
    _applica_mese, _delta_metriche_mese, _profilo_incompatibilita,
    _stato_iniziale, metriche_ordine, metriche_temporali,
)
from moduli.calcolo.valutazione_q21_contesto import ProblemaContestuale


def _profilo_gravita(descrittori, ordine, precedenti):
    """L3, L2, riusi, L1: a pari qualita' temporale, rinvia i mesi peggiori.

    L3 e' comunque proibita dai vincoli HARD; la si include per completezza
    della metrica. L2 precede i riusi per non anticipare incompatibilita'
    problematiche solo per risparmiare una ripetizione nel mese.
    """
    stato = _stato_iniziale(precedenti)
    profilo = []
    for indice in ordine:
        descrittore = descrittori[indice - 1]
        delta = _delta_metriche_mese(descrittore, stato)
        profilo.append((
            delta['incompatibilita_l3'],
            delta['incompatibilita_l2'],
            delta['riusi'],
            delta['incompatibilita_l1'],
        ))
        stato = _applica_mese(descrittore, stato, copia=False)
    return tuple(profilo)


def ordina_senza_perdere_qualita(descrittori, *, precedenti=()):
    """Restituisce l'ordine con severita' migliore *sul plateau R2*.

    Proibisce peggioramenti temporalmente invisibili alla sola chiave R2:
    confronta l'intero dizionario temporale, inclusi mesi_con_riuso e gap.
    Conserva inoltre la classifica cronologica delle incompatibilita' R2.
    Se nessuno scambio sicuro migliora la gravita', resta l'ordine originale.
    """
    ordine = list(range(1, len(descrittori) + 1))
    if len(ordine) < 2:
        return ordine
    precedenti = set(precedenti)
    metriche_base = metriche_ordine(
        descrittori, ordine, blacklist_iniziale=precedenti)
    temporali_base = metriche_temporali(
        descrittori, ordine, blacklist_iniziale=precedenti)
    incompatibilita_base = _profilo_incompatibilita(descrittori, ordine)
    gravita = _profilo_gravita(descrittori, ordine, precedenti)

    while True:
        opzioni = []
        for i in range(len(ordine) - 1):
            for j in range(i + 1, len(ordine)):
                proposta = ordine[:]
                proposta[i], proposta[j] = proposta[j], proposta[i]
                incompatibilita = _profilo_incompatibilita(descrittori, proposta)
                if incompatibilita > incompatibilita_base:
                    continue
                gravita_nuova = _profilo_gravita(descrittori, proposta, precedenti)
                if gravita_nuova >= gravita:
                    continue
                if metriche_temporali(
                        descrittori, proposta,
                        blacklist_iniziale=precedenti) != temporali_base:
                    continue
                if metriche_ordine(
                        descrittori, proposta,
                        blacklist_iniziale=precedenti) != metriche_base:
                    continue
                opzioni.append((gravita_nuova, incompatibilita,
                                tuple(proposta), proposta))
        if not opzioni:
            return ordine
        gravita, _incompatibilita, _firma, ordine = min(opzioni)


def riordina_risultato_per_presentazione(risultato, ingresso):
    """Adatta un esito completo senza alterare l'esito selezionato da Q21.

    Verifica prima e dopo con l'oracolo fisico; non cambia gli studenti in
    alcun banco, ne' la loro posizione fisica dentro il banco, ne' lo Storico.
    """
    mesi = risultato['mesi']
    if len(mesi) < 2:
        return risultato

    studenti = ingresso.crea_studenti()
    schema = ingresso.fotografia.layout.schema
    storico = ingresso.frequenze_storico()
    base = ProblemaContestuale(mesi, studenti, schema, frequenze_storico=storico)
    foto_base = base.verifica(base.iniziali)
    from moduli.calcolo.politica_annuale import descrivi_stagione
    ordine = ordina_senza_perdere_qualita(
        descrivi_stagione(mesi, 'personalizzata'),
        precedenti=base.storico)
    if ordine == list(range(1, len(mesi) + 1)):
        return risultato

    righe = [base.iniziali[i - 1] for i in ordine]
    foto_nuova = base.valuta(righe)
    if (foto_nuova.metriche != foto_base.metriche
            or foto_nuova.temporali != foto_base.temporali
            or foto_nuova.profilo > foto_base.profilo
            or foto_nuova.ultima != foto_base.ultima
            or foto_nuova.miste != foto_base.miste):
        raise ValueError('Riordino finale: perdita di qualita\' non ammessa.')
    nuovi_mesi, nuove_chiavi = prepara_risultato_fisico_q21(
        righe, studenti, schema, frequenze_storico=storico)
    verifica = ProblemaContestuale(
        nuovi_mesi, studenti, schema, frequenze_storico=storico)
    if verifica.verifica(verifica.iniziali) != foto_nuova:
        raise ValueError('Riordino finale: fotografia di uscita incoerente.')
    for mese in nuovi_mesi:
        ingresso.fotografia.verifica_risultato(mese)
    punteggio = punteggio_stagione(nuove_chiavi)
    if punteggio[0] != foto_base.metriche['riusi']:
        raise ValueError('Riordino finale: numero riusi discordante.')
    info = dict(risultato['info'])
    info.update(punteggio=punteggio, tot_ripetizioni=punteggio[0],
                riordino_pulizia_finale=True,
                ordine_pulizia_finale=tuple(ordine))
    return dict(risultato, mesi=nuovi_mesi, chiavi=nuove_chiavi, info=info)
