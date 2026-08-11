"""Esecuzione headless della strategia produttiva C1.

Il modulo replica il coordinamento dei worker annuali senza importare Qt. Non
modifica motori, pesi, metriche o ordine delle scelte: invoca le stesse funzioni
pure di ``moduli.annuale`` e conserva in più la traccia del riordino finale.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .ambiente import (
    AmbienteRunIsolato,
    verifica_sorgente_immutata,
)
from .modelli import CondizioneRun, Modalita, StatoRun, TracciaMese
from .riordino import (
    ErroreRiordinoC1,
    riordina_coppie_con_traccia,
    riordina_terzetti_con_traccia,
)


class ErroreEsecuzioneC1(RuntimeError):
    """Segnala un contesto non compatibile con l'esecuzione produttiva C1."""


@dataclass(slots=True)
class EsitoC1:
    """Risultato runtime di I3, ancora precedente al modello semantico di I4."""

    run_id: str
    modalita: Modalita
    stato: StatoRun
    mesi_generazione: tuple[Any, ...]
    chiavi_generazione: tuple[tuple[int, int, int], ...]
    mesi_finali: tuple[Any, ...]
    chiavi_finali: tuple[tuple[int, int, int], ...]
    traccia_riordino: tuple[TracciaMese, ...]
    info: dict[str, Any] = field(default_factory=dict)
    report_fallimento: Any = None

    def __post_init__(self) -> None:
        self.run_id = str(self.run_id).strip()
        if not self.run_id:
            raise ValueError("run_id non può essere vuoto.")
        self.mesi_generazione = tuple(self.mesi_generazione)
        self.mesi_finali = tuple(self.mesi_finali)
        self.chiavi_generazione = tuple(
            _chiave_tecnica(chiave, "chiave_generazione")
            for chiave in self.chiavi_generazione
        )
        self.chiavi_finali = tuple(
            _chiave_tecnica(chiave, "chiave_finale")
            for chiave in self.chiavi_finali
        )
        self.traccia_riordino = tuple(self.traccia_riordino)
        self.info = copy.deepcopy(dict(self.info))

        if len(self.mesi_generazione) != len(self.chiavi_generazione):
            raise ValueError("Mesi e chiavi nell'ordine di generazione non coincidono.")
        if len(self.mesi_finali) != len(self.chiavi_finali):
            raise ValueError("Mesi e chiavi nell'ordine finale non coincidono.")
        if self.traccia_riordino and len(self.traccia_riordino) != len(self.mesi_finali):
            raise ValueError("La traccia non coincide con il numero dei mesi finali.")

    @property
    def completo(self) -> bool:
        return self.stato == StatoRun.COMPLETO


def _chiave_tecnica(valore: Any, contesto: str) -> tuple[int, int, int]:
    try:
        chiave = tuple(valore)
    except TypeError as errore:
        raise ErroreEsecuzioneC1(f"{contesto}: chiave non iterabile.") from errore
    if len(chiave) != 3 or any(
        isinstance(elemento, bool) or not isinstance(elemento, int)
        for elemento in chiave
    ):
        raise ErroreEsecuzioneC1(
            f"{contesto}: attesa una chiave di tre interi."
        )
    return chiave


def _verifica_strategia_c1() -> None:
    from moduli.strategie_ricerca import (
        STRATEGIA_PRODUZIONE,
        strategia_corrente,
    )

    corrente = strategia_corrente()
    if STRATEGIA_PRODUZIONE != "C1" or corrente != "C1":
        raise ErroreEsecuzioneC1(
            "L'osservatore R0.1 può eseguire soltanto C1; "
            f"produzione={STRATEGIA_PRODUZIONE!r}, corrente={corrente!r}."
        )


def _verifica_ambiente(ambiente: AmbienteRunIsolato, modalita: Modalita) -> None:
    if ambiente.run.modalita != modalita:
        raise ErroreEsecuzioneC1(
            f"Il run {ambiente.run.run_id} dichiara {ambiente.run.modalita.value}, "
            f"ma è stato inviato al runner {modalita.value}."
        )
    verifica_sorgente_immutata(ambiente.config_app, ambiente.firma_config_data)


def _verifica_fisso(ambiente: AmbienteRunIsolato, studente_fisso: Any) -> None:
    condizione = ambiente.run.condizione
    if condizione == CondizioneRun.CON_FISSO and studente_fisso is None:
        raise ErroreEsecuzioneC1("Un run con_fisso richiede lo studente FISSO.")
    if condizione == CondizioneRun.SENZA_FISSO and studente_fisso is not None:
        raise ErroreEsecuzioneC1("Un run senza_fisso non può ricevere uno studente FISSO.")


def _parametri_arresto(run: Any, *, terzetti: bool) -> tuple[float, int, int, int | None]:
    from moduli.annuale import (
        BUDGET_STAGIONI_SEC,
        BUDGET_STAGIONI_TERZETTI_SEC,
        K_CONVERGENZA,
        K_CONVERGENZA_TERZETTI,
        TETTO_STAGIONI,
        TETTO_STAGIONI_TERZETTI,
    )

    parametri = run.parametri_ricerca
    budget_default = BUDGET_STAGIONI_TERZETTI_SEC if terzetti else BUDGET_STAGIONI_SEC
    tetto_default = TETTO_STAGIONI_TERZETTI if terzetti else TETTO_STAGIONI
    convergenza_default = K_CONVERGENZA_TERZETTI if terzetti else K_CONVERGENZA
    budget = parametri.budget_secondi
    tetto = parametri.tetto_stagioni
    convergenza = parametri.convergenza
    return (
        float(budget_default if budget is None else budget),
        int(tetto_default if tetto is None else tetto),
        int(convergenza_default if convergenza is None else convergenza),
        parametri.numero_stagioni_fisso,
    )


def _stato_da_info(info: Mapping[str, Any], numero_mesi: int) -> StatoRun:
    motivo = info.get("motivo_stop")
    mesi = int(info.get("mesi_completi") or 0)
    if motivo == "annullato":
        return StatoRun.ANNULLATO
    if motivo == "mese_fallito":
        return StatoRun.FALLITO
    if mesi == numero_mesi:
        return StatoRun.COMPLETO
    return StatoRun.PARZIALE


def _aggiorna_contesto_coppie(mesi: tuple[Any, ...], info: Mapping[str, Any]) -> None:
    for assegnatore in mesi:
        contesto = getattr(assegnatore, "contesto_casuale", None)
        if not isinstance(contesto, dict):
            contesto = {}
            assegnatore.contesto_casuale = contesto
        contesto.update({
            "stagioni_generate": info.get("n_stagioni"),
            "stagione_vincente": info.get("indice_stagione_migliore"),
        })


def _aggiorna_contesto_terzetti(mesi: tuple[dict[str, Any], ...], info: Mapping[str, Any]) -> None:
    for mese in mesi:
        metadati = mese.get("metadati_casualita") or {}
        contesto = metadati.setdefault("contesto", {})
        contesto.update({
            "stagioni_generate": info.get("n_stagioni"),
            "stagione_vincente": info.get("indice_stagione_migliore"),
        })
        mese["metadati_casualita"] = metadati


def esegui_c1_coppie(
    ambiente: AmbienteRunIsolato,
    studenti: list[Any] | tuple[Any, ...],
    configurazione_aula: Any,
    *,
    studente_fisso: Any = None,
    modalita_trio: str | None = None,
    cattura_report: Callable[..., str] | None = None,
    progresso_mese: Callable[[int, int], None] | None = None,
    progresso_stagione: Callable[[dict[str, Any]], None] | None = None,
    deve_fermarsi: Callable[[], bool] | None = None,
    diagnostica: Any = None,
) -> EsitoC1:
    """Esegue l'Annuale a coppie con le stesse chiamate del worker produttivo."""
    _verifica_strategia_c1()
    _verifica_ambiente(ambiente, Modalita.COPPIE)
    _verifica_fisso(ambiente, studente_fisso)
    if configurazione_aula is None:
        raise ErroreEsecuzioneC1("Il runner a coppie richiede ConfigurazioneAula.")

    from moduli.annuale import genera_migliore_stagione, genera_una_stagione_gui

    run = ambiente.run
    modalita_trio_effettiva = (
        modalita_trio
        or run.parametri_aula.modalita_trio
        or "centro"
    )
    budget, tetto, convergenza, numero_stagioni_fisso = _parametri_arresto(
        run,
        terzetti=False,
    )
    report_fallimento: Any = None

    def _cattura_fallimento(report: Any) -> None:
        nonlocal report_fallimento
        report_fallimento = report

    def _stagione(
        indice_stagione: int,
        t0_globale: float,
        budget_secondi: float,
        stop: Callable[[], bool] | None,
    ):
        return genera_una_stagione_gui(
            studenti,
            configurazione_aula,
            ambiente.config_app,
            modalita_trio_effettiva,
            run.genere_misto_attivo,
            studente_fisso,
            run.numero_mesi,
            run.parametri_ricerca.numero_candidati,
            progresso=progresso_mese,
            t0_globale=t0_globale,
            budget_secondi=budget_secondi,
            deve_fermarsi=stop,
            on_fallimento=_cattura_fallimento,
            seed_principale=run.seed_principale,
            indice_stagione=indice_stagione,
            diagnostica=diagnostica,
        )

    mesi_raw, chiavi_raw, info_raw = genera_migliore_stagione(
        _stagione,
        run.numero_mesi,
        budget_secondi=budget,
        tetto=tetto,
        k_convergenza=convergenza,
        progresso=progresso_stagione,
        deve_fermarsi=deve_fermarsi,
        numero_stagioni_fisso=numero_stagioni_fisso,
    )
    mesi_generazione = tuple(mesi_raw)
    chiavi_generazione = tuple(
        _chiave_tecnica(chiave, "chiave_generazione")
        for chiave in chiavi_raw
    )
    info = copy.deepcopy(dict(info_raw))
    info["seed_principale"] = run.seed_principale
    info["modalita"] = Modalita.COPPIE.value
    _aggiorna_contesto_coppie(mesi_generazione, info)
    stato = _stato_da_info(info, run.numero_mesi)

    if info.get("motivo_stop") == "mese_fallito":
        mesi_finali = mesi_generazione
        chiavi_finali = chiavi_generazione
        traccia: tuple[TracciaMese, ...] = ()
    else:
        mesi_finali, chiavi_finali, traccia = riordina_coppie_con_traccia(
            mesi_generazione,
            chiavi_generazione,
            ambiente.config_app,
            cattura_report=cattura_report,
        )
        info["tot_ripetizioni"] = sum(
            assegnatore.riutilizzate_snapshot["totali"]
            for assegnatore in mesi_finali
        )

    verifica_sorgente_immutata(ambiente.config_app, ambiente.firma_config_data)
    return EsitoC1(
        run_id=run.run_id,
        modalita=Modalita.COPPIE,
        stato=stato,
        mesi_generazione=mesi_generazione,
        chiavi_generazione=chiavi_generazione,
        mesi_finali=mesi_finali,
        chiavi_finali=chiavi_finali,
        traccia_riordino=traccia,
        info=info,
        report_fallimento=report_fallimento,
    )


def _extra_intero_o_none(extra: Mapping[str, Any], nome: str) -> int | None:
    valore = extra.get(nome)
    if valore is None:
        return None
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ErroreEsecuzioneC1(f"parametri_aula.extra.{nome} deve essere un intero non negativo.")
    return valore


def esegui_c1_terzetti(
    ambiente: AmbienteRunIsolato,
    studenti: list[Any] | tuple[Any, ...],
    *,
    studente_fisso: Any = None,
    resto_in_prima_fila: bool | None = None,
    max_terzetti_prima_fila: int | None = None,
    max_resti_prima_fila: int | None = None,
    progresso_mese: Callable[[int, int], None] | None = None,
    progresso_stagione: Callable[[dict[str, Any]], None] | None = None,
    deve_fermarsi: Callable[[], bool] | None = None,
    diagnostica: Any = None,
) -> EsitoC1:
    """Esegue l'Annuale a terzetti senza Qt e conserva la traccia finale."""
    _verifica_strategia_c1()
    _verifica_ambiente(ambiente, Modalita.TERZETTI)
    _verifica_fisso(ambiente, studente_fisso)

    from moduli.annuale import (
        genera_migliore_stagione,
        genera_una_stagione_terzetti_gui,
    )

    run = ambiente.run
    extra = run.parametri_aula.extra
    if resto_in_prima_fila is None:
        valore_extra = extra.get("resto_in_prima_fila")
        if valore_extra is not None and not isinstance(valore_extra, bool):
            raise ErroreEsecuzioneC1(
                "parametri_aula.extra.resto_in_prima_fila deve essere booleano."
            )
        resto_in_prima_fila = (
            valore_extra
            if valore_extra is not None
            else run.parametri_aula.posizione_blocco_finale == "prima"
        )
    if not isinstance(resto_in_prima_fila, bool):
        raise ErroreEsecuzioneC1("resto_in_prima_fila deve essere booleano.")

    if max_terzetti_prima_fila is None:
        max_terzetti_prima_fila = _extra_intero_o_none(
            extra,
            "max_terzetti_prima_fila",
        )
    if max_resti_prima_fila is None:
        max_resti_prima_fila = _extra_intero_o_none(
            extra,
            "max_resti_prima_fila",
        )

    budget, tetto, convergenza, numero_stagioni_fisso = _parametri_arresto(
        run,
        terzetti=True,
    )
    report_fallimento: Any = None

    def _cattura_fallimento(report: Any) -> None:
        nonlocal report_fallimento
        report_fallimento = report

    def _stagione(
        indice_stagione: int,
        t0_globale: float,
        budget_secondi: float,
        stop: Callable[[], bool] | None,
    ):
        return genera_una_stagione_terzetti_gui(
            studenti,
            ambiente.config_app,
            run.genere_misto_attivo,
            run.parametri_aula.preferenza_resto2,
            resto_in_prima_fila,
            run.numero_mesi,
            max_terzetti_prima_fila=max_terzetti_prima_fila,
            max_resti_prima_fila=max_resti_prima_fila,
            num_candidati=run.parametri_ricerca.numero_candidati,
            progresso=progresso_mese,
            t0_globale=t0_globale,
            budget_secondi=budget_secondi,
            deve_fermarsi=stop,
            on_fallimento=_cattura_fallimento,
            seed_principale=run.seed_principale,
            indice_stagione=indice_stagione,
            diagnostica=diagnostica,
        )

    mesi_raw, chiavi_raw, info_raw = genera_migliore_stagione(
        _stagione,
        run.numero_mesi,
        budget_secondi=budget,
        tetto=tetto,
        k_convergenza=convergenza,
        progresso=progresso_stagione,
        deve_fermarsi=deve_fermarsi,
        numero_stagioni_fisso=numero_stagioni_fisso,
    )
    mesi_generazione = tuple(mesi_raw)
    chiavi_generazione = tuple(
        _chiave_tecnica(chiave, "chiave_generazione")
        for chiave in chiavi_raw
    )
    info = copy.deepcopy(dict(info_raw))
    info["seed_principale"] = run.seed_principale
    info["modalita"] = Modalita.TERZETTI.value
    _aggiorna_contesto_terzetti(mesi_generazione, info)
    stato = _stato_da_info(info, run.numero_mesi)

    if info.get("motivo_stop") == "mese_fallito":
        mesi_finali = mesi_generazione
        chiavi_finali = chiavi_generazione
        traccia: tuple[TracciaMese, ...] = ()
    else:
        mesi_finali, chiavi_finali, traccia = riordina_terzetti_con_traccia(
            mesi_generazione,
            chiavi_generazione,
            ambiente.config_app,
        )

    verifica_sorgente_immutata(ambiente.config_app, ambiente.firma_config_data)
    return EsitoC1(
        run_id=run.run_id,
        modalita=Modalita.TERZETTI,
        stato=stato,
        mesi_generazione=mesi_generazione,
        chiavi_generazione=chiavi_generazione,
        mesi_finali=mesi_finali,
        chiavi_finali=chiavi_finali,
        traccia_riordino=traccia,
        info=info,
        report_fallimento=report_fallimento,
    )


def esegui_c1(
    ambiente: AmbienteRunIsolato,
    studenti: list[Any] | tuple[Any, ...],
    *,
    configurazione_aula: Any = None,
    studente_fisso: Any = None,
    **opzioni: Any,
) -> EsitoC1:
    """Dispatch esplicito sulla modalità dichiarata dal protocollo."""
    if ambiente.run.modalita == Modalita.COPPIE:
        return esegui_c1_coppie(
            ambiente,
            studenti,
            configurazione_aula,
            studente_fisso=studente_fisso,
            **opzioni,
        )
    if configurazione_aula is not None:
        raise ErroreEsecuzioneC1(
            "La modalità terzetti non usa ConfigurazioneAula nel runner annuale."
        )
    return esegui_c1_terzetti(
        ambiente,
        studenti,
        studente_fisso=studente_fisso,
        **opzioni,
    )


__all__ = [
    "ErroreEsecuzioneC1",
    "ErroreRiordinoC1",
    "EsitoC1",
    "esegui_c1",
    "esegui_c1_coppie",
    "esegui_c1_terzetti",
]
