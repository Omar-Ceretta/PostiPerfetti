# -*- coding: utf-8 -*-
"""Gate E3a — guardie fisiche post-generazione per Coppie e Terzetti.

Lavora sulla fotografia semantica E1, non sul motore, sui pixel o sulla
blacklist. Valida la disposizione *realmente occupata*, indipendentemente
 dalla posizione del FISSO nel proprio blocco.

Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass

from moduli.dominio.disposizione_effettiva import DisposizioneEffettiva
from moduli.dominio.metrica_pulizia import livello_incompatibilita


@dataclass(frozen=True, slots=True)
class VerificaDisposizioneStandard:
    """Fotografia delle adiacenze, comprese TUTTE quelle del FISSO."""

    adiacenze: tuple[tuple[str, str], ...]
    vicini_fisso: tuple[str, ...]


def verifica_disposizione_standard(
    disposizione: DisposizioneEffettiva,
    studenti,
    *,
    ancora_attesa: str | None = None,
) -> VerificaDisposizioneStandard:
    """Convalida le condizioni hard di una disposizione standard occupata.

    Sono bloccanti: FISSO non ancorato, occupanti mancanti o duplicati,
    incompatibilità L3 fra vicini, PRIMA fuori dalla prima fila. ULTIMA
    resta un vincolo soft e non viene vietata. La vicinanza FISSO è sempre
    misurata sulla geometria fisica: uno o due vicini diretti.

    L'ancora desiderata deve essere risolta dal catalogo E2 *prima* di
    chiamare la funzione: qui non si correggono ancore o geometrie.
    """
    if not isinstance(disposizione, DisposizioneEffettiva):
        raise TypeError("È richiesta una DisposizioneEffettiva valida.")
    if disposizione.modo not in {"coppie", "terzetti"}:
        raise ValueError("Verifica standard applicabile solo a Coppie e Terzetti.")

    studenti = tuple(studenti)
    per_nome = {studente.get_nome_completo(): studente for studente in studenti}
    if len(per_nome) != len(studenti):
        raise ValueError("La classe contiene nomi di studenti duplicati.")

    occupanti = dict(disposizione.occupazioni)
    nomi_occupanti = set(occupanti.values())
    if nomi_occupanti != set(per_nome):
        mancanti = sorted(set(per_nome) - nomi_occupanti)
        estranei = sorted(nomi_occupanti - set(per_nome))
        raise ValueError(
            f"Occupazioni non corrispondenti alla classe: "
            f"studenti mancanti={mancanti}; estranei={estranei}."
        )

    fissi = [s.get_nome_completo() for s in studenti
             if s.nota_posizione == "FISSO"]
    if len(fissi) > 1:
        raise ValueError("È consentito un solo studente FISSO.")
    fisso = fissi[0] if fissi else None
    if disposizione.studente_fisso != fisso:
        raise ValueError("Studente FISSO della classe diverso da quello nella disposizione.")
    if ancora_attesa is not None:
        if fisso is None:
            raise ValueError("Ancora richiesta senza studente FISSO.")
        if disposizione.ancora_fisso != ancora_attesa:
            raise ValueError("Il FISSO non si trova nel posto-ancora selezionato.")

    vicini_fisso: set[str] = set()
    adiacenze: set[tuple[str, str]] = set()
    max_profondita = max(blocco.profondita for blocco in disposizione.blocchi)
    for blocco in disposizione.blocchi:
        if blocco.zona_prima != (blocco.profondita == 0):
            raise ValueError("La zona PRIMA non coincide con la prima fila reale.")
        if blocco.zona_ultima != (blocco.profondita == max_profondita):
            raise ValueError("La zona ULTIMA non coincide con l'ultima fila reale.")
        membri = [occupanti[posto.id] for posto in blocco.posti]
        for nome in membri:
            if per_nome[nome].nota_posizione == "PRIMA" and not blocco.zona_prima:
                raise ValueError(f"Studente PRIMA fuori dalla prima fila: {nome}.")
        for nome_a, nome_b in zip(membri, membri[1:]):
            if livello_incompatibilita(per_nome[nome_a], per_nome[nome_b]) == 3:
                raise ValueError(
                    f"Incompatibilità L3 fra vicini: {nome_a} — {nome_b}."
                )
            adiacenze.add(tuple(sorted((nome_a, nome_b))))
            if nome_a == fisso:
                vicini_fisso.add(nome_b)
            elif nome_b == fisso:
                vicini_fisso.add(nome_a)

    if fisso is not None and not (1 <= len(vicini_fisso) <= 2):
        raise ValueError("Il FISSO deve avere uno o due vicini nel suo blocco.")

    return VerificaDisposizioneStandard(
        adiacenze=tuple(sorted(adiacenze)),
        vicini_fisso=tuple(sorted(vicini_fisso)),
    )
