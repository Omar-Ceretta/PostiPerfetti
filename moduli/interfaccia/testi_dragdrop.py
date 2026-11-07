# -*- coding: utf-8 -*-
"""Messaggi comprensibili per il docente; i codici del dominio restano invariati.

Nessuna dipendenza Qt: il modulo puo' essere verificato isolatamente.
Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""

from __future__ import annotations


ERRORI = {
    'prima_fuori_zona': 'Uno studente che deve stare davanti finirebbe in un banco non contrassegnato come DAVANTI.',
    'incompatibilita_liv3': 'Lo scambio metterebbe vicini due studenti con incompatibilità di livello 3.',
    'fisso_fuori_ancora': 'Lo studente con posto FISSO non può cambiare posto.',
    'fisso_blocco_errato': 'Lo studente con posto FISSO non può cambiare banco.',
    'fisso_indice_errato': 'Lo studente con posto FISSO deve mantenere il proprio posto nel banco.',
    'fisso_senza_ancora': 'Occorre assegnare un posto allo studente FISSO nel Layout.',
    'fissi_multipli': 'La classe contiene più studenti con posto FISSO.',
    'blocchi_collocati_duplicati': 'Uno o più banchi verrebbero usati due volte.',
    'blocchi_fuori_schema': 'Il banco indicato non appartiene al Layout.',
    'numero_studenti': 'Non tutti gli studenti avrebbero un posto.',
    'copertura_studenti': 'Uno studente risulterebbe assente o assegnato a più posti.',
    'numero_gruppi': 'Il numero dei gruppi non corrisponderebbe ai banchi.',
    'forma_gruppi': 'Il numero di posti in un banco non corrisponderebbe agli occupanti.',
    'numero_collocazioni': 'Non tutti i gruppi avrebbero un banco.',
    'gruppi_collocati_incoerenti': 'Gli occupanti dei banchi non sarebbero coerenti.',
    'numero_adiacenze': 'Il numero dei compagni vicini non sarebbe coerente.',
}


def spiega_rifiuto(motivo: str) -> str:
    """Mai esporre codici interni direttamente nella finestra del Drag & Drop."""
    if motivo.startswith('Vincoli obbligatori: '):
        codici = [x.strip() for x in motivo.partition(':')[2].split(',')]
        descrizioni = [ERRORI.get(c, 'La disposizione non rispetterebbe un vincolo obbligatorio.')
                       for c in codici if c]
        return ' '.join(dict.fromkeys(descrizioni))
    if 'FISSO' in motivo or 'fisso' in motivo.lower():
        return 'Lo studente con posto FISSO deve rimanere nel posto assegnato nel Layout.'
    if 'Geometria alterata:' in motivo:
        return 'Lo scambio modificherebbe la struttura dei banchi definita nel Layout.'
    if 'Banchi da 2 e 3:' in motivo:
        return 'Puoi scambiare gli occupanti di un intero blocco solo con quelli di un altro della stessa capienza: coppia con coppia, trio con trio.'
    if motivo == 'Il posto di partenza coincide con l’arrivo.' or motivo == "Il posto di partenza coincide con l'arrivo.":
        return 'Hai scelto lo stesso posto: trascina verso un altro studente.'
    if motivo == "Il banco di partenza coincide con l'arrivo.":
        return 'Hai scelto lo stesso banco: trascina verso un altro banco.'
    if 'inesistente' in motivo:
        return 'Il posto o banco selezionato non è più disponibile.'
    if motivo == 'Nessuna modifica da applicare.':
        return 'La disposizione rimarrebbe identica.'
    return 'Lo scambio non è consentito dalla disposizione o dai vincoli attuali.'


def spiega_avvisi(avvisi: tuple[str, ...]) -> str:
    """Riformula i peggioramenti senza alterarne i valori numerici."""
    sostituzioni = {
        'Riusi rispetto allo Storico': 'Coppie di vicini già presenti nello Storico',
        'Incompatibilità L2': 'Vicinanze con incompatibilità di livello 2',
        'Incompatibilità L1': 'Vicinanze con incompatibilità di livello 1',
        'Affinità L3': 'Vicinanze con affinità di livello 3',
        'Affinità L2': 'Vicinanze con affinità di livello 2',
        'Affinità L1': 'Vicinanze con affinità di livello 1',
        'Studenti ULTIMA nella zona': 'Studenti con preferenza IN FONDO accontentati',
        'Adiacenze di genere misto': 'Vicinanze fra studenti di genere diverso',
    }
    descrizioni = []
    for avviso in avvisi:
        testo = avviso
        for origine, destinazione in sostituzioni.items():
            if testo.startswith(origine + ':'):
                testo = destinazione + testo[len(origine):]
                break
        descrizioni.append(testo)
    return ' '.join(descrizioni)
