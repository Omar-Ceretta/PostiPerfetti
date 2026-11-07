# -*- coding: utf-8 -*-
"""Matcher puro gruppo → blocco per la modalità Mista sperimentale.

Gate B del contratto M1.4. Non genera gruppi e non conosce storico, T1–T4,
punteggi sociali o Qt. Riceve una partizione già formata e verifica se può
essere collocata nello schema semantico. Se richiesto, costruisce una
collocazione deterministica che massimizza il numero di studenti ULTIMA
collocati nella relativa zona, senza rendere ULTIMA un vincolo duro.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Sequence

from moduli.dominio.metrica_pulizia import Gruppo, nome_completo
from moduli.dominio.schema_blocchi_semantico import (
    BloccoAulaSemanticoSpec,
    PostoAulaSemanticoSpec,
    SchemaBlocchiSemantico,
)


NOTA_NORMALE = "NORMALE"
NOTA_PRIMA = "PRIMA"
NOTA_ULTIMA = "ULTIMA"
NOTA_FISSO = "FISSO"


@dataclass(frozen=True, slots=True)
class CollocazioneGruppoBlocco:
    """Assegnazione di un gruppo ordinato a un blocco fisico."""

    gruppo: Gruppo
    blocco: BloccoAulaSemanticoSpec

    @property
    def occupazioni(self) -> tuple[tuple[PostoAulaSemanticoSpec, Any], ...]:
        return tuple(zip(self.blocco.posti, self.gruppo.membri, strict=True))


@dataclass(frozen=True, slots=True)
class DiagnosticaMatcherBlocchi:
    """Telemetria del solo problema di matching geometrico."""

    gruppi: int
    blocchi: int
    archi_compatibili: int
    gruppi_senza_candidati: int
    visite_archi_fattibilita: int
    augmentazioni_fattibilita: int
    stati_ottimizzazione: int
    cache_hit_ottimizzazione: int
    compatibilita_respinte_per_causa: tuple[tuple[str, int], ...]

    def come_dict(self) -> dict[str, Any]:
        return {
            "gruppi": self.gruppi,
            "blocchi": self.blocchi,
            "archi_compatibili": self.archi_compatibili,
            "gruppi_senza_candidati": self.gruppi_senza_candidati,
            "visite_archi_fattibilita": self.visite_archi_fattibilita,
            "augmentazioni_fattibilita": self.augmentazioni_fattibilita,
            "stati_ottimizzazione": self.stati_ottimizzazione,
            "cache_hit_ottimizzazione": self.cache_hit_ottimizzazione,
            "compatibilita_respinte_per_causa": dict(self.compatibilita_respinte_per_causa),
        }


@dataclass(frozen=True, slots=True)
class EsitoFattibilitaMatching:
    fattibile: bool
    errori_duri: tuple[str, ...]
    diagnostica: DiagnosticaMatcherBlocchi


@dataclass(frozen=True, slots=True)
class EsitoMatchingBlocchi:
    successo: bool
    collocazioni: tuple[CollocazioneGruppoBlocco, ...]
    errori_duri: tuple[str, ...]
    ultima_totali: int
    ultima_soddisfatti: int
    diagnostica: DiagnosticaMatcherBlocchi

    @property
    def ultima_percentuale(self) -> float:
        if not self.ultima_totali:
            return 100.0
        return self.ultima_soddisfatti * 100.0 / self.ultima_totali

    def come_dict(self) -> dict[str, Any]:
        return {
            "successo": self.successo,
            "errori_duri": list(self.errori_duri),
            "ultima_totali": self.ultima_totali,
            "ultima_soddisfatti": self.ultima_soddisfatti,
            "ultima_percentuale": self.ultima_percentuale,
            "collocazioni": [
                {
                    "gruppo": [nome_completo(s) for s in c.gruppo.membri],
                    "blocco": c.blocco.id,
                    "posti": [posto.id for posto in c.blocco.posti],
                }
                for c in self.collocazioni
            ],
            "diagnostica": self.diagnostica.come_dict(),
        }


@dataclass(frozen=True, slots=True)
class _Preparazione:
    gruppi: tuple[Gruppo, ...]
    blocchi: tuple[BloccoAulaSemanticoSpec, ...]
    candidati: tuple[tuple[int, ...], ...]
    errori_duri: tuple[str, ...]
    respinte: tuple[tuple[str, int], ...]


def _nota(studente: Any) -> str:
    return str(getattr(studente, "nota_posizione", NOTA_NORMALE)).strip().upper()


def _firma_gruppo(gruppo: Gruppo) -> tuple[str, ...]:
    return tuple(nome_completo(studente) for studente in gruppo.membri)


def _compatibilita_hard(
    gruppo: Gruppo,
    blocco: BloccoAulaSemanticoSpec,
    *,
    fisso_presente: bool,
    schema: SchemaBlocchiSemantico,
) -> tuple[bool, str | None]:
    if len(gruppo.membri) != blocco.capienza:
        return False, "capienza"

    note = [_nota(studente) for studente in gruppo.membri]
    contiene_prima = NOTA_PRIMA in note
    posizioni_fisso = tuple(i for i, nota in enumerate(note) if nota == NOTA_FISSO)
    blocco_ancora = schema.blocco_ancora_fisso
    posto_ancora = None if blocco_ancora is None else blocco_ancora.posto_ancora_fisso
    return _compatibilita_precalcolata(
        len(gruppo.membri), contiene_prima, posizioni_fisso, blocco,
        fisso_presente=fisso_presente, blocco_ancora=blocco_ancora,
        posto_ancora=posto_ancora,
    )


def _compatibilita_precalcolata(
    capienza: int, contiene_prima: bool, posizioni_fisso: tuple[int, ...],
    blocco: BloccoAulaSemanticoSpec, *, fisso_presente: bool,
    blocco_ancora: BloccoAulaSemanticoSpec | None,
    posto_ancora: PostoAulaSemanticoSpec | None,
) -> tuple[bool, str | None]:
    """U6a: stessa decisione HARD, con dati letti una volta per preparazione.

    Nessuna cache globale degli studenti mutabili; ogni invocazione del matcher
    rilegge note e schema. Conserva anche l'ordine delle cause di rifiuto.
    """
    if capienza != blocco.capienza:
        return False, "capienza"

    if contiene_prima and not blocco.zona_prima:
        return False, "prima_fuori_zona"

    if posizioni_fisso:
        if len(posizioni_fisso) != 1:
            return False, "fissi_nello_stesso_gruppo"
        if blocco_ancora is None or posto_ancora is None:
            return False, "fisso_senza_ancora"
        if blocco.id != blocco_ancora.id:
            return False, "fisso_blocco_errato"
        if posizioni_fisso[0] != posto_ancora.indice:
            return False, "fisso_indice_errato"
    elif fisso_presente and blocco_ancora is not None and blocco.id == blocco_ancora.id:
        # Se un FISSO esiste nella partizione, il suo blocco-ancora non può
        # essere consumato da un gruppo diverso.
        return False, "blocco_ancora_riservato"

    return True, None


def _prepara(
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
    *,
    richiedi_forma_completa: bool = True,
    fisso_atteso: bool | None = None,
) -> _Preparazione:
    gruppi_input = tuple(gruppi)
    note_gruppi = tuple(tuple(_nota(s) for s in g.membri) for g in gruppi_input)
    blocco_ancora = schema.blocco_ancora_fisso
    posto_ancora = None if blocco_ancora is None else blocco_ancora.posto_ancora_fisso
    errori: list[str] = []

    if richiedi_forma_completa and len(gruppi_input) != schema.numero_blocchi:
        errori.append("numero_gruppi")
    elif not richiedi_forma_completa and len(gruppi_input) > schema.numero_blocchi:
        errori.append("numero_gruppi")

    taglie_gruppi = Counter(len(gruppo.membri) for gruppo in gruppi_input)
    taglie_schema = schema.conteggio_per_capienza()
    if richiedi_forma_completa:
        forma_errata = (
            int(taglie_gruppi.get(2, 0)) != int(taglie_schema.get(2, 0))
            or int(taglie_gruppi.get(3, 0)) != int(taglie_schema.get(3, 0))
            or any(taglia not in (2, 3) for taglia in taglie_gruppi)
        )
    else:
        forma_errata = (
            int(taglie_gruppi.get(2, 0)) > int(taglie_schema.get(2, 0))
            or int(taglie_gruppi.get(3, 0)) > int(taglie_schema.get(3, 0))
            or any(taglia not in (2, 3) for taglia in taglie_gruppi)
        )
    if forma_errata:
        errori.append("forma_gruppi")

    fissi = [s for g, note in zip(gruppi_input, note_gruppi)
             for s, nota in zip(g.membri, note) if nota == NOTA_FISSO]
    if len(fissi) > 1:
        errori.append("fissi_multipli")
    if fissi and blocco_ancora is None:
        errori.append("fisso_senza_ancora")

    if fisso_atteso is None:
        fisso_riservato = len(fissi) == 1
    else:
        fisso_riservato = bool(fisso_atteso)
        if fissi and not fisso_riservato:
            errori.append("fisso_inatteso")
    if fisso_riservato and blocco_ancora is None:
        errori.append("fisso_senza_ancora")

    # Canonicalizzazione: l'ordine di ingresso dei gruppi non deve avere
    # significato per il matcher. L'ordine interno del gruppo resta invece parte
    # della soluzione e quindi della firma.
    ordine = sorted(range(len(gruppi_input)), key=lambda i: _firma_gruppo(gruppi_input[i]))
    gruppi_ordinati = tuple(gruppi_input[i] for i in ordine)
    blocchi_ordinati = tuple(sorted(schema.blocchi, key=lambda b: b.id))

    respinte: Counter[str] = Counter()
    candidati: list[tuple[int, ...]] = []
    for i in ordine:
        gruppo = gruppi_input[i]
        note = note_gruppi[i]
        contiene_prima = NOTA_PRIMA in note
        posizioni_fisso = tuple(i for i, nota in enumerate(note) if nota == NOTA_FISSO)
        capienza = len(gruppo.membri)
        indici: list[int] = []
        for indice, blocco in enumerate(blocchi_ordinati):
            ok, causa = _compatibilita_precalcolata(
                capienza, contiene_prima, posizioni_fisso, blocco,
                fisso_presente=fisso_riservato, blocco_ancora=blocco_ancora,
                posto_ancora=posto_ancora,
            )
            if ok:
                indici.append(indice)
            elif causa is not None:
                respinte[causa] += 1
        candidati.append(tuple(indici))

    gruppi_senza = sum(1 for elementi in candidati if not elementi)
    if gruppi_senza:
        errori.append("gruppo_senza_blocchi_compatibili")

    return _Preparazione(
        gruppi=gruppi_ordinati,
        blocchi=blocchi_ordinati,
        candidati=tuple(candidati),
        errori_duri=tuple(dict.fromkeys(errori)),
        respinte=tuple(sorted(respinte.items())),
    )


def _massimo_matching(prep: _Preparazione) -> tuple[bool, int, int]:
    """Matching bipartito massimo per il solo controllo hard di fattibilità."""
    if prep.errori_duri:
        return False, 0, 0

    # I gruppi più vincolati vengono tentati per primi, senza dipendere
    # dall'ordine di ingresso originario.
    ordine = sorted(
        range(len(prep.gruppi)),
        key=lambda i: (len(prep.candidati[i]), _firma_gruppo(prep.gruppi[i])),
    )
    proprietario: dict[int, int] = {}
    visite_archi = 0
    augmentazioni = 0

    def assegna(indice_gruppo: int, visitati: set[int]) -> bool:
        nonlocal visite_archi
        for indice_blocco in prep.candidati[indice_gruppo]:
            visite_archi += 1
            if indice_blocco in visitati:
                continue
            visitati.add(indice_blocco)
            precedente = proprietario.get(indice_blocco)
            if precedente is None or assegna(precedente, visitati):
                proprietario[indice_blocco] = indice_gruppo
                return True
        return False

    for indice_gruppo in ordine:
        if not assegna(indice_gruppo, set()):
            return False, visite_archi, augmentazioni
        augmentazioni += 1

    return True, visite_archi, augmentazioni


def verifica_fattibilita_parziale_matching(
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
    *,
    fisso_atteso: bool = False,
) -> EsitoFattibilitaMatching:
    """Controlla se i gruppi già scelti possono occupare blocchi distinti.

    Non pretende che la partizione sia completa. Se ``fisso_atteso`` è vero,
    il blocco-ancora viene riservato anche quando il gruppo del FISSO non è
    ancora stato formato: ciò rende il pruning sicuro durante il backtracking.
    """
    prep = _prepara(
        gruppi,
        schema,
        richiedi_forma_completa=False,
        fisso_atteso=fisso_atteso,
    )
    fattibile, visite, augmentazioni = _massimo_matching(prep)
    errori = list(prep.errori_duri)
    if not fattibile and not errori:
        errori.append("matching_hard_impossibile")

    diagnostica = DiagnosticaMatcherBlocchi(
        gruppi=len(prep.gruppi),
        blocchi=len(prep.blocchi),
        archi_compatibili=sum(len(c) for c in prep.candidati),
        gruppi_senza_candidati=sum(1 for c in prep.candidati if not c),
        visite_archi_fattibilita=visite,
        augmentazioni_fattibilita=augmentazioni,
        stati_ottimizzazione=0,
        cache_hit_ottimizzazione=0,
        compatibilita_respinte_per_causa=prep.respinte,
    )
    return EsitoFattibilitaMatching(
        fattibile=fattibile,
        errori_duri=tuple(errori),
        diagnostica=diagnostica,
    )


def verifica_fattibilita_matching(
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
) -> EsitoFattibilitaMatching:
    """Risposta economica sì/no utilizzabile in futuro come pruning geometrico."""
    prep = _prepara(gruppi, schema)
    fattibile, visite, augmentazioni = _massimo_matching(prep)
    errori = list(prep.errori_duri)
    if not fattibile and not errori:
        errori.append("matching_hard_impossibile")

    diagnostica = DiagnosticaMatcherBlocchi(
        gruppi=len(prep.gruppi),
        blocchi=len(prep.blocchi),
        archi_compatibili=sum(len(c) for c in prep.candidati),
        gruppi_senza_candidati=sum(1 for c in prep.candidati if not c),
        visite_archi_fattibilita=visite,
        augmentazioni_fattibilita=augmentazioni,
        stati_ottimizzazione=0,
        cache_hit_ottimizzazione=0,
        compatibilita_respinte_per_causa=prep.respinte,
    )
    return EsitoFattibilitaMatching(
        fattibile=fattibile,
        errori_duri=tuple(errori),
        diagnostica=diagnostica,
    )


def abbina_gruppi_a_blocchi(
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
) -> EsitoMatchingBlocchi:
    """Trova la migliore collocazione hard-valida rispetto al soft ULTIMA.

    La funzione massimizza il numero di studenti ULTIMA collocati in blocchi
    ``zona_ultima``. A parità usa una firma canonica gruppo→blocco, rendendo il
    risultato indipendente dalla permutazione dei gruppi in ingresso.
    """
    prep = _prepara(gruppi, schema)
    fattibile, visite, augmentazioni = _massimo_matching(prep)
    errori = list(prep.errori_duri)
    if not fattibile:
        if not errori:
            errori.append("matching_hard_impossibile")
        diagnostica = DiagnosticaMatcherBlocchi(
            gruppi=len(prep.gruppi),
            blocchi=len(prep.blocchi),
            archi_compatibili=sum(len(c) for c in prep.candidati),
            gruppi_senza_candidati=sum(1 for c in prep.candidati if not c),
            visite_archi_fattibilita=visite,
            augmentazioni_fattibilita=augmentazioni,
            stati_ottimizzazione=0,
            cache_hit_ottimizzazione=0,
            compatibilita_respinte_per_causa=prep.respinte,
        )
        return EsitoMatchingBlocchi(
            successo=False,
            collocazioni=(),
            errori_duri=tuple(errori),
            ultima_totali=sum(
                1 for g in prep.gruppi for s in g.membri if _nota(s) == NOTA_ULTIMA
            ),
            ultima_soddisfatti=0,
            diagnostica=diagnostica,
        )

    # Punteggio additivo del solo soft ULTIMA.
    pesi_ultima = tuple(
        sum(1 for studente in gruppo.membri if _nota(studente) == NOTA_ULTIMA)
        for gruppo in prep.gruppi
    )

    stati = 0

    @lru_cache(maxsize=None)
    def risolvi(indice_gruppo: int, maschera_usati: int) -> tuple[int, tuple[int, ...]] | None:
        nonlocal stati
        stati += 1
        if indice_gruppo == len(prep.gruppi):
            return 0, ()

        migliore: tuple[int, tuple[int, ...]] | None = None
        for indice_blocco in prep.candidati[indice_gruppo]:
            bit = 1 << indice_blocco
            if maschera_usati & bit:
                continue
            coda = risolvi(indice_gruppo + 1, maschera_usati | bit)
            if coda is None:
                continue
            blocco = prep.blocchi[indice_blocco]
            incremento = pesi_ultima[indice_gruppo] if blocco.zona_ultima else 0
            candidato = (incremento + coda[0], (indice_blocco,) + coda[1])
            if migliore is None:
                migliore = candidato
                continue
            if candidato[0] > migliore[0]:
                migliore = candidato
                continue
            if candidato[0] == migliore[0]:
                chiave_candidato = tuple(prep.blocchi[i].id for i in candidato[1])
                chiave_migliore = tuple(prep.blocchi[i].id for i in migliore[1])
                if chiave_candidato < chiave_migliore:
                    migliore = candidato
        return migliore

    migliore = risolvi(0, 0)
    if migliore is None:  # difesa: il matching hard aveva già certificato fattibilità
        errori.append("incoerenza_matcher")
        collocazioni: tuple[CollocazioneGruppoBlocco, ...] = ()
        ultima_soddisfatti = 0
    else:
        ultima_soddisfatti = migliore[0]
        collocazioni = tuple(
            CollocazioneGruppoBlocco(gruppo, prep.blocchi[indice_blocco])
            for gruppo, indice_blocco in zip(prep.gruppi, migliore[1], strict=True)
        )

    info_cache = risolvi.cache_info()
    diagnostica = DiagnosticaMatcherBlocchi(
        gruppi=len(prep.gruppi),
        blocchi=len(prep.blocchi),
        archi_compatibili=sum(len(c) for c in prep.candidati),
        gruppi_senza_candidati=sum(1 for c in prep.candidati if not c),
        visite_archi_fattibilita=visite,
        augmentazioni_fattibilita=augmentazioni,
        stati_ottimizzazione=stati,
        cache_hit_ottimizzazione=info_cache.hits,
        compatibilita_respinte_per_causa=prep.respinte,
    )
    return EsitoMatchingBlocchi(
        successo=not errori,
        collocazioni=collocazioni,
        errori_duri=tuple(errori),
        ultima_totali=sum(pesi_ultima),
        ultima_soddisfatti=ultima_soddisfatti,
        diagnostica=diagnostica,
    )
