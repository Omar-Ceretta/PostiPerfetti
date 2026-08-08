"""Caricamento rigoroso e validazione del protocollo esplicito dei run."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, TypeVar

from .identita import crea_pair_id, crea_run_id
from .modelli import (
    CondizioneRun,
    Modalita,
    ParametriAula,
    ParametriRicerca,
    ProtocolloRaccolta,
    PROTOCOLLO_VERSIONE,
    SpecificaCoppiaCorpus,
    SpecificaRun,
)
from .serializzazione import firma_json_sha256, leggi_json


class ErroreProtocollo(ValueError):
    """Raccoglie tutte le violazioni rilevate nel protocollo."""

    def __init__(self, errori: list[str] | tuple[str, ...]):
        self.errori = tuple(str(errore) for errore in errori)
        super().__init__("Protocollo non valido:\n- " + "\n- ".join(self.errori))


T = TypeVar("T")


def _oggetto(valore: Any, percorso: str) -> Mapping[str, Any]:
    if not isinstance(valore, Mapping):
        raise ErroreProtocollo([f"{percorso}: atteso un oggetto JSON."])
    return valore


def _lista(valore: Any, percorso: str) -> list[Any]:
    if not isinstance(valore, list):
        raise ErroreProtocollo([f"{percorso}: attesa una lista JSON."])
    return valore


def _chiavi_esatte(dati: Mapping[str, Any], ammesse: set[str], percorso: str) -> None:
    extra = set(dati) - ammesse
    mancanti = ammesse - set(dati)
    errori = []
    if extra:
        errori.append(f"{percorso}: chiavi sconosciute: {', '.join(sorted(extra))}.")
    if mancanti:
        errori.append(f"{percorso}: chiavi mancanti: {', '.join(sorted(mancanti))}.")
    if errori:
        raise ErroreProtocollo(errori)


def _testo(dati: Mapping[str, Any], chiave: str, percorso: str) -> str:
    valore = dati[chiave]
    if not isinstance(valore, str) or not valore.strip():
        raise ErroreProtocollo([f"{percorso}.{chiave}: attesa una stringa non vuota."])
    return valore.strip()


def _intero(dati: Mapping[str, Any], chiave: str, percorso: str) -> int:
    valore = dati[chiave]
    if isinstance(valore, bool) or not isinstance(valore, int):
        raise ErroreProtocollo([f"{percorso}.{chiave}: atteso un intero."])
    return valore


def _booleano(dati: Mapping[str, Any], chiave: str, percorso: str) -> bool:
    valore = dati[chiave]
    if not isinstance(valore, bool):
        raise ErroreProtocollo([f"{percorso}.{chiave}: atteso un booleano."])
    return valore


def _opzionale(
    dati: Mapping[str, Any],
    chiave: str,
    tipo: type[T] | tuple[type, ...],
    percorso: str,
) -> T | None:
    valore = dati[chiave]
    if valore is None:
        return None
    if tipo is int and isinstance(valore, bool):
        raise ErroreProtocollo([f"{percorso}.{chiave}: tipo non valido."])
    if not isinstance(valore, tipo):
        tipi = tipo if isinstance(tipo, tuple) else (tipo,)
        nomi = " o ".join(t.__name__ for t in tipi)
        raise ErroreProtocollo([f"{percorso}.{chiave}: atteso {nomi} o null."])
    return valore


def _enum(enum_cls: type[T], valore: Any, percorso: str) -> T:
    try:
        return enum_cls(valore)
    except (TypeError, ValueError) as errore:
        ammessi = ", ".join(voce.value for voce in enum_cls)  # type: ignore[attr-defined]
        raise ErroreProtocollo([f"{percorso}: valore non valido; ammessi: {ammessi}."]) from errore


def _parse_parametri_ricerca(dati_grezzi: Any, percorso: str) -> ParametriRicerca:
    dati = _oggetto(dati_grezzi, percorso)
    _chiavi_esatte(
        dati,
        {
            "numero_candidati",
            "numero_stagioni_fisso",
            "budget_secondi",
            "tetto_stagioni",
            "convergenza",
        },
        percorso,
    )
    try:
        return ParametriRicerca(
            numero_candidati=_intero(dati, "numero_candidati", percorso),
            numero_stagioni_fisso=_opzionale(
                dati, "numero_stagioni_fisso", int, percorso
            ),
            budget_secondi=_opzionale(dati, "budget_secondi", (int, float), percorso),  # type: ignore[arg-type]
            tetto_stagioni=_opzionale(dati, "tetto_stagioni", int, percorso),
            convergenza=_opzionale(dati, "convergenza", int, percorso),
        )
    except ValueError as errore:
        raise ErroreProtocollo([f"{percorso}: {errore}"]) from errore


def _parse_parametri_aula(dati_grezzi: Any, percorso: str) -> ParametriAula:
    dati = _oggetto(dati_grezzi, percorso)
    _chiavi_esatte(
        dati,
        {
            "numero_file",
            "posti_per_fila",
            "modalita_trio",
            "posizione_blocco_finale",
            "preferenza_resto2",
            "extra",
        },
        percorso,
    )
    extra = _oggetto(dati["extra"], f"{percorso}.extra")
    try:
        return ParametriAula(
            numero_file=_intero(dati, "numero_file", percorso),
            posti_per_fila=_intero(dati, "posti_per_fila", percorso),
            modalita_trio=_opzionale(dati, "modalita_trio", str, percorso),
            posizione_blocco_finale=_opzionale(
                dati, "posizione_blocco_finale", str, percorso
            ),
            preferenza_resto2=_testo(dati, "preferenza_resto2", percorso),
            extra=extra,
        )
    except ValueError as errore:
        raise ErroreProtocollo([f"{percorso}: {errore}"]) from errore


def _parse_coppia(dati_grezzi: Any, indice: int) -> SpecificaCoppiaCorpus:
    percorso = f"coppie[{indice}]"
    dati = _oggetto(dati_grezzi, percorso)
    _chiavi_esatte(
        dati,
        {
            "pair_id",
            "classe",
            "file_senza_fisso",
            "file_con_fisso",
            "studente_fisso",
            "posizione_base",
            "numero_studenti",
        },
        percorso,
    )
    try:
        coppia = SpecificaCoppiaCorpus(
            pair_id=_testo(dati, "pair_id", percorso),
            classe=_testo(dati, "classe", percorso),
            file_senza_fisso=_testo(dati, "file_senza_fisso", percorso),
            file_con_fisso=_testo(dati, "file_con_fisso", percorso),
            studente_fisso=_testo(dati, "studente_fisso", percorso),
            posizione_base=_testo(dati, "posizione_base", percorso),
            numero_studenti=_intero(dati, "numero_studenti", percorso),
        )
    except ValueError as errore:
        raise ErroreProtocollo([f"{percorso}: {errore}"]) from errore
    atteso = crea_pair_id(coppia.classe, coppia.studente_fisso)
    if coppia.pair_id != atteso:
        raise ErroreProtocollo([
            f"{percorso}.pair_id: identificatore non canonico; atteso {atteso}."
        ])
    return coppia


def _parse_run(dati_grezzi: Any, indice: int) -> SpecificaRun:
    percorso = f"run[{indice}]"
    dati = _oggetto(dati_grezzi, percorso)
    _chiavi_esatte(
        dati,
        {
            "run_id",
            "pair_id",
            "file_classe",
            "condizione",
            "modalita",
            "seed_principale",
            "numero_mesi",
            "genere_misto_attivo",
            "stato_iniziale_id",
            "parametri_ricerca",
            "parametri_aula",
            "metadati",
        },
        percorso,
    )
    parametri_ricerca = _parse_parametri_ricerca(
        dati["parametri_ricerca"], f"{percorso}.parametri_ricerca"
    )
    parametri_aula = _parse_parametri_aula(
        dati["parametri_aula"], f"{percorso}.parametri_aula"
    )
    metadati = _oggetto(dati["metadati"], f"{percorso}.metadati")
    try:
        run = SpecificaRun(
            run_id=_testo(dati, "run_id", percorso),
            pair_id=_testo(dati, "pair_id", percorso),
            file_classe=_testo(dati, "file_classe", percorso),
            condizione=_enum(
                CondizioneRun, dati["condizione"], f"{percorso}.condizione"
            ),
            modalita=_enum(Modalita, dati["modalita"], f"{percorso}.modalita"),
            seed_principale=_intero(dati, "seed_principale", percorso),
            numero_mesi=_intero(dati, "numero_mesi", percorso),
            genere_misto_attivo=_booleano(dati, "genere_misto_attivo", percorso),
            stato_iniziale_id=_testo(dati, "stato_iniziale_id", percorso),
            parametri_ricerca=parametri_ricerca,
            parametri_aula=parametri_aula,
            metadati=metadati,
        )
    except ValueError as errore:
        raise ErroreProtocollo([f"{percorso}: {errore}"]) from errore

    atteso = crea_run_id(
        run.pair_id,
        run.condizione.value,
        run.modalita.value,
        run.seed_principale,
        run.numero_mesi,
        run.genere_misto_attivo,
        run.stato_iniziale_id,
        run.parametri_ricerca,
        run.parametri_aula,
    )
    if run.run_id != atteso:
        raise ErroreProtocollo([
            f"{percorso}.run_id: identificatore non canonico; atteso {atteso}."
        ])
    return run


def protocollo_da_dati(dati_grezzi: Any) -> ProtocolloRaccolta:
    """Costruisce e valida un protocollo a partire da dati JSON già letti."""
    dati = _oggetto(dati_grezzi, "radice")
    _chiavi_esatte(
        dati,
        {
            "protocollo_id",
            "titolo",
            "versione",
            "data_approvazione",
            "corpus_id",
            "osservatore_id",
            "strategia",
            "richiede_appaiamento_completo",
            "coppie",
            "run",
            "metadati",
        },
        "radice",
    )
    coppie = tuple(
        _parse_coppia(voce, indice)
        for indice, voce in enumerate(_lista(dati["coppie"], "coppie"))
    )
    run = tuple(
        _parse_run(voce, indice)
        for indice, voce in enumerate(_lista(dati["run"], "run"))
    )
    metadati = _oggetto(dati["metadati"], "metadati")
    try:
        protocollo = ProtocolloRaccolta(
            protocollo_id=_testo(dati, "protocollo_id", "radice"),
            titolo=_testo(dati, "titolo", "radice"),
            versione=_testo(dati, "versione", "radice"),
            data_approvazione=_testo(dati, "data_approvazione", "radice"),
            corpus_id=_testo(dati, "corpus_id", "radice"),
            osservatore_id=_testo(dati, "osservatore_id", "radice"),
            strategia=_testo(dati, "strategia", "radice"),
            richiede_appaiamento_completo=_booleano(
                dati, "richiede_appaiamento_completo", "radice"
            ),
            coppie=coppie,
            run=run,
            metadati=metadati,
        )
    except ValueError as errore:
        raise ErroreProtocollo([str(errore)]) from errore
    return valida_protocollo(protocollo)


def valida_protocollo(protocollo: ProtocolloRaccolta) -> ProtocolloRaccolta:
    """Applica i vincoli incrociati e restituisce il protocollo se valido."""
    errori: list[str] = []
    if protocollo.versione != PROTOCOLLO_VERSIONE:
        errori.append(
            f"versione protocollo {protocollo.versione!r} non supportata; "
            f"attesa {PROTOCOLLO_VERSIONE!r}."
        )

    pair_ids = [coppia.pair_id for coppia in protocollo.coppie]
    duplicati_pair = sorted({voce for voce in pair_ids if pair_ids.count(voce) > 1})
    if duplicati_pair:
        errori.append(f"pair_id duplicati: {', '.join(duplicati_pair)}.")

    run_ids = [run.run_id for run in protocollo.run]
    duplicati_run = sorted({voce for voce in run_ids if run_ids.count(voce) > 1})
    if duplicati_run:
        errori.append(f"run_id duplicati: {', '.join(duplicati_run)}.")

    coppie_per_id = {coppia.pair_id: coppia for coppia in protocollo.coppie}
    pair_usati: set[str] = set()
    gruppi_appaiamento: dict[str, list[SpecificaRun]] = defaultdict(list)

    for run in protocollo.run:
        coppia = coppie_per_id.get(run.pair_id)
        if coppia is None:
            errori.append(f"{run.run_id}: pair_id sconosciuto {run.pair_id}.")
            continue
        pair_usati.add(run.pair_id)
        file_atteso = (
            coppia.file_senza_fisso
            if run.condizione == CondizioneRun.SENZA_FISSO
            else coppia.file_con_fisso
        )
        if Path(run.file_classe).as_posix() != Path(file_atteso).as_posix():
            errori.append(
                f"{run.run_id}: file {run.file_classe!r} non coincide con "
                f"quello previsto per {run.condizione.value}: {file_atteso!r}."
            )
        firma_appaiamento = firma_json_sha256({
            "pair_id": run.pair_id,
            "modalita": run.modalita,
            "seed_principale": run.seed_principale,
            "numero_mesi": run.numero_mesi,
            "genere_misto_attivo": run.genere_misto_attivo,
            "stato_iniziale_id": run.stato_iniziale_id,
            "parametri_ricerca": run.parametri_ricerca,
            "parametri_aula": run.parametri_aula,
        })
        gruppi_appaiamento[firma_appaiamento].append(run)

    non_usati = sorted(set(coppie_per_id) - pair_usati)
    if non_usati:
        errori.append(f"coppie corpus senza alcun run: {', '.join(non_usati)}.")

    if protocollo.richiede_appaiamento_completo:
        for firma, gruppo in gruppi_appaiamento.items():
            condizioni = [run.condizione for run in gruppo]
            if sorted(condizione.value for condizione in condizioni) != [
                CondizioneRun.CON_FISSO.value,
                CondizioneRun.SENZA_FISSO.value,
            ]:
                descrizione = ", ".join(run.run_id for run in gruppo)
                errori.append(
                    "gruppo di appaiamento incompleto o duplicato "
                    f"({firma[:12]}…): {descrizione}."
                )

    if errori:
        raise ErroreProtocollo(errori)
    return protocollo


def carica_protocollo(percorso: str | Path) -> ProtocolloRaccolta:
    """Legge un protocollo JSON UTF-8 e ne valida struttura e appaiamenti."""
    try:
        dati = leggi_json(percorso)
    except (OSError, ValueError) as errore:
        raise ErroreProtocollo([f"impossibile leggere {percorso}: {errore}"]) from errore
    return protocollo_da_dati(dati)
