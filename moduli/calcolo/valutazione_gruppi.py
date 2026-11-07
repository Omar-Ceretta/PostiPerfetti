# -*- coding: utf-8 -*-
"""Valutazione delle adiacenze e ricerca interna ai gruppi del Layout.

Le sole vicinanze sono consecutive. Le regole sono condivise con il motore
storico, che le importa per mantenere riproducibili i collaudi precedenti.
Il FISSO in un posto esplicito viene gestito da ``motore_blocchi``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
import itertools

# Budget della cascata di ricerca, condivisi senza modificare i valori storici.
NUM_RIPARTENZE_TENTATIVO_4 = 15
LIMITE_NODI_BACKTRACK = 100000

# Le immagini speculari hanno le stesse adiacenze e lo stesso punteggio.
OTTIMIZZA_SPECCHIATE = True

# Preferenza di fila incompatibile all'interno di un gruppo; resta soft.
PESO_PRIMA_ULTIMA = 50


def _incrementa_contatore(contatore, voce, quantita=1):
    """Incrementa Counter o TelemetriaRicerca senza imporre una dipendenza."""
    if contatore is None:
        return
    incrementa = getattr(contatore, "incrementa", None)
    if incrementa is not None:
        incrementa(voce, quantita)
    else:
        contatore[voce] += quantita


def _chiave_coppia(studente_a, studente_b):
    """Restituisce la chiave indipendente dall'ordine di due studenti.

    Il punteggio della coppia è simmetrico; gli ``id`` ordinati evitano chiavi
    diverse quando gli argomenti arrivano invertiti.
    """
    return tuple(sorted((id(studente_a), id(studente_b))))


def _penalita_prima_ultima(membri):
    """Restituisce la penalità per preferenze di fila inconciliabili.

    FISSO conta come posizione frontale. La penalità dipende dai membri, non
    dall'ordine interno del gruppo.
    """
    if PESO_PRIMA_ULTIMA == 0:
        return 0
    # FISSO è una posizione frontale come PRIMA.
    ha_front = any(getattr(s, 'nota_posizione', 'NORMALE') in ('PRIMA', 'FISSO')
                   for s in membri)
    ha_ultima = any(getattr(s, 'nota_posizione', 'NORMALE') == 'ULTIMA' for s in membri)
    return PESO_PRIMA_ULTIMA if (ha_front and ha_ultima) else 0


def valuta_gruppo(membri, punteggio, bloccata, contatori=None):
    """Trova l'ordine ammissibile col punteggio più alto.

    Valuta tutte le disposizioni di una coppia, un terzetto o un quartetto e
    somma i punteggi delle sole adiacenze consecutive. Scarta gli ordini con
    almeno un'adiacenza bloccata e restituisce ``None`` se nessun ordine è
    valido.

    Le coppie interne vengono precaricate e le disposizioni speculari vengono
    escluse, perché producono le stesse adiacenze. Se il gruppo contiene FISSO,
    questo occupa l'estremo sinistro.
    """
    misura = contatori is not None
    if misura:
        _incrementa_contatore(contatori, "gruppi_valutati")
    miglior_ordine = None
    miglior_punteggio = None
    membri = list(membri)
    n_membri = len(membri)

    # Il FISSO occupa l'estremo sinistro; il vincolo rompe già la simmetria.
    gruppo_ha_fisso = any(getattr(s, 'nota_posizione', 'NORMALE') == 'FISSO'
                          for s in membri)

    # Precarica blocco e punteggio di ogni coppia interna al gruppo.
    info_coppia = {}
    for i in range(n_membri):
        for j in range(i + 1, n_membri):
            k = _chiave_coppia(membri[i], membri[j])
            info_coppia[(i, j)] = (bloccata[k], punteggio[k])

    for perm in itertools.permutations(range(n_membri)):
        if misura:
            _incrementa_contatore(contatori, "orientamenti_generati")
        if gruppo_ha_fisso and getattr(membri[perm[0]], 'nota_posizione', 'NORMALE') != 'FISSO':
            continue
        # Una fila e la sua immagine speculare hanno le stesse adiacenze.
        if OTTIMIZZA_SPECCHIATE and not gruppo_ha_fisso and n_membri > 1:
            if perm[0] > perm[-1]:
                continue
        if misura:
            _incrementa_contatore(contatori, "orientamenti_valutati")
        somma = 0
        ammissibile = True
        for posizione in range(n_membri - 1):
            a = perm[posizione]
            b = perm[posizione + 1]
            blocc, punt = info_coppia[(a, b) if a < b else (b, a)]
            if blocc:
                ammissibile = False
                break
            somma += punt

        if not ammissibile:
            continue

        if miglior_punteggio is None or somma > miglior_punteggio:
            miglior_punteggio = somma
            miglior_ordine = [membri[i] for i in perm]

    if miglior_ordine is None:
        return None
    # La penalità di fila non cambia l'ordine, ma il valore del gruppo.
    return (miglior_ordine, miglior_punteggio - _penalita_prima_ultima(miglior_ordine))

def _punteggio_partizione(gruppi, punteggio):
    """Somma i punteggi delle adiacenze di una partizione.

    Il quarto tentativo usa il totale per confrontare le ripartenze.
    """
    totale = 0
    for gruppo in gruppi:
        membri = gruppo.membri
        for posizione in range(len(membri) - 1):
            k = _chiave_coppia(membri[posizione], membri[posizione + 1])
            totale += punteggio[k]
        # Include la stessa penalità di fila usata nella valutazione dei gruppi.
        totale -= _penalita_prima_ultima(membri)
    return totale
