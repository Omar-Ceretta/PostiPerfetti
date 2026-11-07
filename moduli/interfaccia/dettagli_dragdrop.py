# -*- coding: utf-8 -*-
"""Dettagli nominativi per l'editing post-generazione, riutilizzabili nell'Annuale.

Tutte le diagnosi derivano dalla fotografia congelata e dalle adiacenze
fisiche A–B / B–C; niente mutazioni del solver, dello Storico o del Layout.
Parte di «PostiPerfetti». Licenza GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass

from moduli.dominio.editing_disposizione import BozzaDisposizione, misura
from moduli.dominio.metrica_pulizia import livello_affinita, livello_incompatibilita


@dataclass(frozen=True, slots=True)
class DettaglioPeggioramento:
    titolo: str
    studenti: tuple[str, ...]


def _studenti(bozza: BozzaDisposizione):
    return {s.get_nome_completo(): s for s in bozza.fotografia.crea_studenti()}


def _adiacenze(bozza: BozzaDisposizione, disposizione, campo: str, studenti):
    coppie = disposizione.adiacenze_fisiche()
    if campo.startswith('incompatibilita_l'):
        livello = int(campo[-1])
        return {p for p in coppie if livello_incompatibilita(
            studenti[p[0]], studenti[p[1]]) == livello}
    if campo.startswith('affinita_l'):
        livello = int(campo[-1])
        return {p for p in coppie if livello_affinita(
            studenti[p[0]], studenti[p[1]]) == livello}
    if campo == 'riusi_storico':
        return disposizione.adiacenze_rotazioni() & bozza.storico
    if campo == 'adiacenze_miste':
        return {p for p in coppie if studenti[p[0]].sesso != studenti[p[1]].sesso}
    raise ValueError('Indicatore non basato su adiacenze: ' + campo)


def _in_ultima(disposizione, studenti):
    occupanti = dict(disposizione.occupazioni)
    return {occupanti[p.id] for b in disposizione.blocchi if b.zona_ultima
            for p in b.posti if studenti[occupanti[p.id]].nota_posizione == 'ULTIMA'}


def dettagli_peggioramenti(bozza: BozzaDisposizione) -> tuple[DettaglioPeggioramento, ...]:
    """Nomi dei soli peggioramenti netti attuali rispetto all'automatica.

    Una categoria peggiora se cambia il conteggio nel senso sfavorevole.
    All'interno di quella categoria si elencano le vicinanze realmente
    aggiunte/perse. Non si confonde il numero di nuove coppie col delta netto.
    """
    if not bozza.avvisi_rispetto_originale():
        return ()
    prima = misura(bozza.originale, bozza.fotografia, bozza.storico)
    dopo = misura(bozza.corrente, bozza.fotografia, bozza.storico)
    studenti = _studenti(bozza)
    campi = (
        ('riusi_storico', 'Vicinanze già usate nello Storico', True),
        ('incompatibilita_l2', 'Incompatibilità di livello 2', True),
        ('incompatibilita_l1', 'Incompatibilità di livello 1', True),
        ('affinita_l3', 'Affinità di livello 3 perse', False),
        ('affinita_l2', 'Affinità di livello 2 perse', False),
        ('affinita_l1', 'Affinità di livello 1 perse', False),
        ('ultima_in_zona', 'Studenti non più nella zona IN FONDO', False),
    )
    if bozza.fotografia.genere_misto:
        campi += (('adiacenze_miste', 'Vicinanze di genere misto perse', False),)
    dettagli = []
    for campo, titolo, peggiora_aumentando in campi:
        a, b = getattr(prima, campo), getattr(dopo, campo)
        if (b <= a if peggiora_aumentando else b >= a):
            continue
        if campo == 'ultima_in_zona':
            nomi = sorted(_in_ultima(bozza.originale, studenti)
                          - _in_ultima(bozza.corrente, studenti))
        else:
            originali = _adiacenze(bozza, bozza.originale, campo, studenti)
            attuali = _adiacenze(bozza, bozza.corrente, campo, studenti)
            coppie = attuali - originali if peggiora_aumentando else originali - attuali
            nomi = [f'{x} — {y}' for x, y in sorted(coppie)]
        dettagli.append(DettaglioPeggioramento(
            f'{titolo} ({abs(b - a)} {"in più" if peggiora_aumentando else "in meno"})',
            tuple(nomi),
        ))
    return tuple(dettagli)


def _occupazioni_tentate(bozza: BozzaDisposizione, origine: str, destinazione: str,
                           modo: str) -> dict[str, str] | None:
    """Calcola per diagnosi la mossa rifiutata senza creare una disposizione non valida."""
    occupanti = dict(bozza.corrente.occupazioni)
    if modo == 'studente':
        if origine not in occupanti or destinazione not in occupanti:
            return None
        occupanti[origine], occupanti[destinazione] = (
            occupanti[destinazione], occupanti[origine])
        return occupanti
    if modo == 'banco':
        blocchi = {b.id: b for b in bozza.corrente.blocchi}
        a, b = blocchi.get(origine), blocchi.get(destinazione)
        if a is None or b is None or a.capienza != b.capienza:
            return None
        for p, q in zip(a.posti, b.posti, strict=True):
            occupanti[p.id], occupanti[q.id] = occupanti[q.id], occupanti[p.id]
        return occupanti
    return None


def spiega_rifiuto_con_nomi(bozza: BozzaDisposizione, motivo: str,
                             origine: str, destinazione: str, modo: str) -> str | None:
    """Mostra solo responsabili verificabili del vincolo, mai ipotesi."""
    if 'FISSO' in motivo or 'fisso' in motivo.lower():
        fisso = bozza.corrente.studente_fisso
        if fisso:
            return f'{fisso} ha un posto FISSO e non può essere spostato.'
    occupanti = _occupazioni_tentate(bozza, origine, destinazione, modo)
    if occupanti is None:
        return None
    studenti = _studenti(bozza)
    if 'prima_fuori_zona' in motivo:
        nomi = sorted({occupanti[p.id] for b in bozza.corrente.blocchi
                       if not b.zona_prima for p in b.posti
                       if studenti[occupanti[p.id]].nota_posizione == 'PRIMA'})
        if nomi:
            if len(nomi) == 1:
                return (f'{nomi[0]} deve sedere in un blocco contrassegnato '
                        'come DAVANTI.')
            return (f'Gli studenti {", ".join(nomi)} devono sedere in blocchi '
                    'contrassegnati come DAVANTI.')
    if 'incompatibilita_liv3' in motivo:
        nuove = set()
        for blocco in bozza.corrente.blocchi:
            nomi = [occupanti[p.id] for p in blocco.posti]
            nuove.update(tuple(sorted((x, y))) for x, y in zip(nomi, nomi[1:]))
        introdotte = nuove - bozza.corrente.adiacenze_fisiche()
        conflitti = sorted(p for p in introdotte if livello_incompatibilita(
            studenti[p[0]], studenti[p[1]]) == 3)
        if conflitti:
            nomi = '; '.join(' e '.join(p) for p in conflitti[:3])
            aggiunta = f' (e altre {len(conflitti) - 3} coppie)' if len(conflitti) > 3 else ''
            return (f'Lo scambio metterebbe vicini {nomi}{aggiunta}, '
                    'con incompatibilità assoluta (livello 3).')
    return None
