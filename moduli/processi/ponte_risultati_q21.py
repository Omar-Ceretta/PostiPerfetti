# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""Gate I1: converte le righe *fisiche* Q21 nel contratto Annuale produttivo.

Nessun import dal laboratorio, nessun Qt, nessuna mutazione di ConfigApp.
La frontiera di uscita serve il percorso produttivo del Layout unico,
con durate da 1 a 10 mesi e frequenze storiche fotografate all'avvio.
La generazione e la selezione delle righe sono responsabilita' del motore.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.metrica_pulizia import (
    Gruppo, chiave_pulizia_terzetti, nome_completo,
)
from moduli.calcolo.motore_blocchi import aggiorna_frequenze_storico
from moduli.dominio.validazione_blocchi import valida_soluzione_blocchi


def _fotografa_frequenze(frequenze):
    if frequenze is None:
        return {}
    if not isinstance(frequenze, Mapping):
        raise TypeError("Lo Storico iniziale deve essere una mappa di frequenze.")
    copia = {}
    for chiave, volte in frequenze.items():
        if (not isinstance(chiave, (frozenset, tuple, list, set))
                or len(chiave) != 2
                or not all(isinstance(nome, str) and nome.strip() for nome in chiave)
                or len(set(chiave)) != 2
                or type(volte) is not int or volte < 1):
            raise ValueError("Una frequenza iniziale non e' una coppia valida.")
        canonica = frozenset(chiave)
        copia[canonica] = copia.get(canonica, 0) + volte
    return copia


def prepara_risultato_fisico_q21(
    righe_finali: Sequence[Sequence[int]],
    studenti: Sequence,
    schema,
    *,
    frequenze_storico: Mapping | None = None,
):
    """Restituisce ``mesi, chiavi`` nel formato Personalizzata produttivo.

    Le righe Q21 contengono indici di ``studenti`` concatenati nell'ordine dei
    blocchi di ``schema``. Preserva tale ordine (anche sul FISSO nel terzetto).
    Rifiuta righe mancanti, indici errati e violazioni HARD prima di produrre
    qualsiasi mese utilizzabile. Ricostruisce ``adiacenze_prima`` in sequenza,
    partendo dalle frequenze dello Storico *fotografato*, senza scriverlo.
    """
    studenti = tuple(studenti)
    if not isinstance(righe_finali, (list, tuple)) or not 1 <= len(righe_finali) <= 10:
        raise ValueError("L'Annuale deve contenere da 1 a 10 mesi completi.")
    blocchi = tuple(schema.blocchi)
    nomi = tuple(nome_completo(s) for s in studenti)
    n = len(studenti)
    if (n != sum(b.capienza for b in blocchi) or len(set(nomi)) != n):
        raise ValueError("Studenti e capienza dello schema non coincidono.")

    frequenze = _fotografa_frequenze(frequenze_storico)
    mesi, chiavi = [], []
    identita = schema.identita_semantica()
    for indice_mese, riga in enumerate(righe_finali, 1):
        if (not isinstance(riga, (list, tuple)) or len(riga) != n
                or any(type(i) is not int for i in riga)
                or set(riga) != set(range(n))):
            raise ValueError(f"Mese {indice_mese}: indici degli studenti incompleti o duplicati.")
        gruppi, collocazioni = [], []
        pos = 0
        for blocco in blocchi:
            membri = tuple(studenti[i] for i in riga[pos:pos + blocco.capienza])
            tipo = "coppia" if blocco.capienza == 2 else "terzetto"
            gruppo = Gruppo(tipo, membri)
            gruppi.append(gruppo)
            collocazioni.append(CollocazioneGruppoBlocco(gruppo, blocco))
            pos += blocco.capienza

        esito = valida_soluzione_blocchi(studenti, gruppi, schema, collocazioni)
        if not esito.valida:
            raise ValueError(
                f"Mese {indice_mese}: vincoli HARD violati: "
                + ", ".join(esito.errori_duri)
            )

        # Come la pipeline produttiva: il riuso e' binario nella chiave mensile,
        # mentre le frequenze crescono anche se la vicinanza era gia' nota.
        precedenti = {tuple(sorted(c)) for c, v in frequenze.items() if v > 0}
        mesi.append({
            "gruppi": gruppi,
            "collocazioni": tuple(collocazioni),
            "adiacenze_prima": precedenti,
            "metadati_casualita": {},
            "schema_identita": identita,
        })
        chiavi.append(chiave_pulizia_terzetti(gruppi, precedenti))
        frequenze = aggiorna_frequenze_storico(frequenze, gruppi)
    return mesi, chiavi
