# -*- coding: utf-8 -*-
"""Coordinate permanenti del Layout 6 × 5, indipendenti da Qt e dagli occupanti.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
RIGHE = 6
COLONNE = 5
PASSO_COLONNA = 4  # tre posti possibili e un corridoio fra blocchi
POSIZIONE_DOCENTE = (0, 2)


def posizione_blocco(blocco):
    if (type(blocco.riga) is not int or not 0 <= blocco.riga < RIGHE
            or type(blocco.colonna) is not int
            or blocco.colonna not in range(0, COLONNE * PASSO_COLONNA, PASSO_COLONNA)):
        raise ValueError(f"Il blocco {blocco.id} non occupa una posizione della griglia 6 × 5.")
    posizione = (blocco.riga, blocco.colonna // PASSO_COLONNA)
    if posizione == POSIZIONE_DOCENTE:
        raise ValueError("La posizione centrale in basso è riservata alla cattedra.")
    if type(blocco.capienza) is not int or blocco.capienza not in (2, 3):
        raise ValueError("La griglia ammette soltanto blocchi da 2 o 3 posti.")
    return posizione


def posizione_spazio(posizione):
    riga, colonna = posizione
    if (type(riga) is not int or not 0 <= riga < RIGHE
            or type(colonna) is not int
            or colonna not in range(0, COLONNE * PASSO_COLONNA, PASSO_COLONNA)):
        raise ValueError("Spazio fuori dalla griglia 6 × 5.")
    slot = (riga, colonna // PASSO_COLONNA)
    if slot == POSIZIONE_DOCENTE:
        raise ValueError("La posizione centrale in basso è riservata alla cattedra.")
    return slot


def valida_griglia_fissa(istantanea):
    occupate = set()
    for blocco in istantanea.blocchi:
        posizione = posizione_blocco(blocco)
        if posizione in occupate:
            raise ValueError("Due blocchi occupano lo stesso spazio della griglia.")
        occupate.add(posizione)
    for spazio in getattr(istantanea, "spazi", ()):
        posizione = posizione_spazio(spazio)
        if posizione in occupate:
            raise ValueError("Uno Spazio si sovrappone a un’altra posizione occupata.")
        occupate.add(posizione)


def nome_posizione(riga, colonna):
    return (f"Fianco cattedra · {'ABCDE'[colonna]}" if riga == 0
            else f"Fila {riga} - {'ABCDE'[colonna]}")

