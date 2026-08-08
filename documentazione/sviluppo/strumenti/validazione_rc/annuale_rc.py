# -*- coding: utf-8 -*-
"""Validazione RC dell'Annuale, dello Storico cumulativo e dei tentativi T1-T4."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
import io
import multiprocessing as mp
import pickle
from typing import Any

import moduli.motore_terzetti as mt
from moduli.annuale import (
    genera_migliore_stagione,
    genera_una_stagione_gui,
    genera_una_stagione_terzetti_gui,
    riordina_e_cattura_stagione_coppie,
    riordina_stagione_terzetti_gui,
)
from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie
from moduli.diagnostica_ricerca import DiagnosticaRicerca
from moduli.generazione import calcola_miglior_mese
from moduli.metrica_pulizia import (
    adiacenze_per_blacklist_terzetti,
    punteggio_stagione,
    snapshot_blacklist,
    snapshot_blacklist_terzetti,
    snapshot_vicini_fisso,
)
from moduli.politica_annuale import analizza_baseline, analizza_candidata, seleziona_s1
from moduli.processo_annuale import (
    esegui_annuale_coppie_in_processo,
    esegui_annuale_terzetti_in_processo,
)
from moduli.strato_storico import aggiorna_blacklist_terzetti

from .esecuzione import configurazione_vuota_rc, _studenti_produttivi
from .modelli import ClasseRC
from .risultati import VerificaRisultatoRC, verifica_aula_rc


@dataclass(frozen=True, slots=True)
class VerificaStagioneRC:
    modalita: str
    valida: bool
    mesi: int
    chiavi_dichiarate: tuple[tuple[int, int, int], ...]
    chiavi_indipendenti: tuple[tuple[int, int, int], ...]
    punteggio_dichiarato: tuple[int, int, int]
    punteggio_indipendente: tuple[int, int, int]
    firme_mesi: tuple[tuple[tuple[str, str], ...], ...]
    violazioni: tuple[str, ...]

    def come_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EsecuzioneAnnualeRC:
    modalita: str
    successo: bool
    mesi: tuple[Any, ...]
    chiavi: tuple[tuple[int, int, int], ...]
    info: dict[str, Any]
    verifica: VerificaStagioneRC | None
    firme_prima_riordino: tuple[tuple[tuple[str, str], ...], ...]


@dataclass(frozen=True, slots=True)
class TelemetriaTentativiRC:
    modalita: str
    successo: bool
    tentativi_iniziati: tuple[int, ...]
    tentativi_successo: tuple[int, ...]
    tentativi_saltati: tuple[int, ...]
    nodi_totali: int
    pruning_totali: int
    risultato_valido: bool | None

    def come_dict(self) -> dict[str, Any]:
        return asdict(self)


def _aula_coppie(classe: ClasseRC, *, posti_per_fila: int, posizione_trio: str) -> ConfigurazioneAula:
    ha_fisso = classe.studente_fisso is not None
    num_file = numero_minimo_file_coppie(
        classe.numero_studenti,
        posti_per_fila,
        posizione_trio=posizione_trio,
        ha_fisso=ha_fisso,
    )
    aula = ConfigurazioneAula("RC annuale coppie")
    aula.crea_layout_standard(
        classe.numero_studenti,
        num_file=num_file,
        posti_per_fila=posti_per_fila,
        posizione_trio=posizione_trio,
        ha_fisso=ha_fisso,
    )
    return aula


def _geometria_terzetti(
    classe: ClasseRC,
    *,
    terzetti_per_fila: int,
    posizione_blocco_finale: str,
    preferenza_resto2: str,
) -> tuple[ConfigurazioneAula, dict[str, Any]]:
    aula = ConfigurazioneAula("RC annuale terzetti")
    aula.crea_layout_terzetti(
        classe.numero_studenti,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        ha_fisso=classe.studente_fisso is not None,
        preferenza_resto2=preferenza_resto2,
    )
    capienza = aula.capienza_prima_fila_terzetti()
    return aula, {
        "resto_in_prima_fila": 0 in aula.file_blocchi_finali,
        "max_terzetti_prima_fila": capienza["terzetti"],
        "max_resti_prima_fila": capienza["resti"],
    }


def _firma_da_verifica(verifica: VerificaRisultatoRC) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(tuple(coppia) for coppia in verifica.adiacenze))


def _aula_da_mese_terzetti(
    classe: ClasseRC,
    mese: dict[str, Any],
    *,
    terzetti_per_fila: int,
    posizione_blocco_finale: str,
    preferenza_resto2: str,
) -> ConfigurazioneAula:
    aula, _geo = _geometria_terzetti(
        classe,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
    )
    esito = aula.piazza_gruppi_terzetti(mese["gruppi"])
    if not esito.get("valido_struttura", False) or not esito.get("valido_prima", False):
        raise AssertionError(f"Piazzamento terzetti non valido: {esito}")
    aula.rimuovi_banchi_vuoti()
    return aula


def _verifica_mesi(
    classe: ClasseRC,
    mesi: list[Any] | tuple[Any, ...],
    *,
    modalita: str,
    posizione_trio: str,
    terzetti_per_fila: int,
    posizione_blocco_finale: str,
    preferenza_resto2: str,
) -> tuple[list[VerificaRisultatoRC], list[ConfigurazioneAula]]:
    verifiche: list[VerificaRisultatoRC] = []
    aule: list[ConfigurazioneAula] = []
    for mese in mesi:
        if modalita == "coppie":
            aula = mese.configurazione_aula
            verifica = verifica_aula_rc(
                classe,
                aula,
                modalita="coppie",
                posizione_trio=posizione_trio,
            )
        else:
            aula = _aula_da_mese_terzetti(
                classe,
                mese,
                terzetti_per_fila=terzetti_per_fila,
                posizione_blocco_finale=posizione_blocco_finale,
                preferenza_resto2=preferenza_resto2,
            )
            verifica = verifica_aula_rc(
                classe,
                aula,
                modalita="terzetti",
                preferenza_resto2=preferenza_resto2,
            )
        verifiche.append(verifica)
        aule.append(aula)
    return verifiche, aule


def _chiavi_indipendenti(
    classe: ClasseRC,
    verifiche: list[VerificaRisultatoRC],
    *,
    modalita: str,
    blacklist_iniziale: set[tuple[str, str]] | None = None,
    vicini_fisso_iniziali: set[str] | None = None,
) -> tuple[tuple[int, int, int], ...]:
    viste = set(blacklist_iniziale or set())
    vicini_fisso = set(vicini_fisso_iniziali or set())
    fisso = classe.studente_fisso
    chiavi: list[tuple[int, int, int]] = []

    for verifica in verifiche:
        adiacenze = {tuple(sorted(c)) for c in verifica.adiacenze}
        vicino_fisso = None
        normali = set(adiacenze)
        if modalita == "coppie" and fisso is not None:
            adiacenze_fisso = [c for c in adiacenze if fisso in c]
            if len(adiacenze_fisso) != 1:
                raise AssertionError(
                    f"Il FISSO {fisso} deve avere una sola adiacenza fisica, trovate {adiacenze_fisso}."
                )
            coppia_fisso = adiacenze_fisso[0]
            vicino_fisso = coppia_fisso[0] if coppia_fisso[1] == fisso else coppia_fisso[1]
            normali.discard(coppia_fisso)

        ripetizioni = len(normali & viste)
        if vicino_fisso is not None and vicino_fisso in vicini_fisso:
            ripetizioni += 1
        metriche = verifica.metriche
        chiave = (
            int(ripetizioni),
            int(metriche.incompatibilita_pesate),
            -int(metriche.affinita),
        )
        chiavi.append(chiave)
        viste.update(normali if modalita == "coppie" else adiacenze)
        if vicino_fisso is not None:
            vicini_fisso.add(vicino_fisso)
    return tuple(chiavi)


def verifica_stagione_rc(
    classe: ClasseRC,
    mesi: list[Any] | tuple[Any, ...],
    chiavi: list[tuple[int, int, int]] | tuple[tuple[int, int, int], ...],
    info: dict[str, Any],
    *,
    modalita: str,
    posizione_trio: str = "centro",
    terzetti_per_fila: int = 3,
    posizione_blocco_finale: str = "ultima",
    preferenza_resto2: str = "coppia",
    blacklist_iniziale: set[tuple[str, str]] | None = None,
    vicini_fisso_iniziali: set[str] | None = None,
) -> VerificaStagioneRC:
    verifiche, _aule = _verifica_mesi(
        classe,
        mesi,
        modalita=modalita,
        posizione_trio=posizione_trio,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
    )
    violazioni: list[str] = []
    for indice, verifica in enumerate(verifiche, start=1):
        if not verifica.valido:
            violazioni.extend(f"mese {indice}: {v.codice}" for v in verifica.violazioni)

    chiavi_dichiarate = tuple(tuple(int(x) for x in chiave) for chiave in chiavi)
    chiavi_ind = _chiavi_indipendenti(
        classe,
        verifiche,
        modalita=modalita,
        blacklist_iniziale=blacklist_iniziale,
        vicini_fisso_iniziali=vicini_fisso_iniziali,
    )
    if chiavi_dichiarate != chiavi_ind:
        violazioni.append(
            f"chiavi divergenti: dichiarate={chiavi_dichiarate}, indipendenti={chiavi_ind}"
        )
    punteggio_dichiarato = tuple(int(x) for x in info.get("punteggio", punteggio_stagione(chiavi_dichiarate)))
    punteggio_ind = tuple(sum(c[pos] for c in chiavi_ind) for pos in range(3))
    if punteggio_dichiarato != punteggio_ind:
        violazioni.append(
            f"punteggio divergente: dichiarato={punteggio_dichiarato}, indipendente={punteggio_ind}"
        )
    if int(info.get("tot_ripetizioni", punteggio_dichiarato[0])) != punteggio_ind[0]:
        violazioni.append("tot_ripetizioni non coincide col ricalcolo indipendente")
    if len(mesi) != int(info.get("num_mesi_richiesti", len(mesi))):
        violazioni.append("numero di mesi finale diverso da quello richiesto")

    firme = tuple(_firma_da_verifica(v) for v in verifiche)
    return VerificaStagioneRC(
        modalita=modalita,
        valida=not violazioni,
        mesi=len(mesi),
        chiavi_dichiarate=chiavi_dichiarate,
        chiavi_indipendenti=chiavi_ind,
        punteggio_dichiarato=punteggio_dichiarato,
        punteggio_indipendente=punteggio_ind,
        firme_mesi=firme,
        violazioni=tuple(violazioni),
    )


def _genera_annuale_coppie(
    classe: ClasseRC,
    *,
    seed: int,
    num_mesi: int,
    numero_stagioni: int,
    num_candidati: int,
    genere_misto: bool,
    posti_per_fila: int,
    posizione_trio: str,
    config_app=None,
) -> tuple[list[Any], list[tuple[int, int, int]], dict[str, Any], tuple[Any, ...]]:
    studenti, fisso = _studenti_produttivi(classe)
    aula = _aula_coppie(classe, posti_per_fila=posti_per_fila, posizione_trio=posizione_trio)
    config = config_app or configurazione_vuota_rc()
    blacklist_iniziale = snapshot_blacklist(config)
    vicini_iniziali = snapshot_vicini_fisso(config)

    def stagione(indice, t0, budget, deve_fermarsi):
        return genera_una_stagione_gui(
            studenti, aula, config, posizione_trio, genere_misto, fisso,
            num_mesi, num_candidati,
            t0_globale=t0, budget_secondi=budget,
            deve_fermarsi=deve_fermarsi,
            seed_principale=seed, indice_stagione=indice,
        )

    def candidata(mesi, indice):
        return analizza_candidata(
            mesi, indice_stagione=indice, modalita="coppie",
            blacklist_iniziale=blacklist_iniziale,
            vicini_fisso_iniziali=vicini_iniziali,
        )

    def baseline(mesi, indice):
        return analizza_baseline(
            mesi, indice_stagione=indice, modalita="coppie",
            blacklist_iniziale=blacklist_iniziale,
            vicini_fisso_iniziali=vicini_iniziali,
        )

    def rigenera(indice, deve_fermarsi):
        return genera_una_stagione_gui(
            studenti, aula, config, posizione_trio, genere_misto, fisso,
            num_mesi, num_candidati,
            deve_fermarsi=deve_fermarsi,
            seed_principale=seed, indice_stagione=indice,
        )

    mesi, chiavi, info = genera_migliore_stagione(
        stagione,
        num_mesi,
        numero_stagioni_fisso=numero_stagioni,
        analizza_candidata=candidata,
        analizza_baseline=baseline,
        seleziona_stagione=seleziona_s1,
        rigenera_una_stagione=rigenera,
    )
    prima = tuple(mesi)
    mesi, chiavi = riordina_e_cattura_stagione_coppie(
        mesi, config, ordine_iniziale=info.get("ordine_stagione_preferito")
    )
    info = dict(info)
    info["punteggio"] = punteggio_stagione(chiavi)
    info["tot_ripetizioni"] = info["punteggio"][0]
    return mesi, chiavi, info, prima


def _genera_annuale_terzetti(
    classe: ClasseRC,
    *,
    seed: int,
    num_mesi: int,
    numero_stagioni: int,
    num_candidati: int,
    genere_misto: bool,
    terzetti_per_fila: int,
    posizione_blocco_finale: str,
    preferenza_resto2: str,
    config_app=None,
) -> tuple[list[Any], list[tuple[int, int, int]], dict[str, Any], tuple[Any, ...]]:
    studenti, _fisso = _studenti_produttivi(classe)
    _aula, geo = _geometria_terzetti(
        classe,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
    )
    config = config_app or configurazione_vuota_rc()
    blacklist_iniziale = snapshot_blacklist_terzetti(config)

    def stagione(indice, t0, budget, deve_fermarsi):
        return genera_una_stagione_terzetti_gui(
            studenti, config, genere_misto, preferenza_resto2,
            geo["resto_in_prima_fila"], num_mesi,
            max_terzetti_prima_fila=geo["max_terzetti_prima_fila"],
            max_resti_prima_fila=geo["max_resti_prima_fila"],
            num_candidati=num_candidati,
            t0_globale=t0, budget_secondi=budget,
            deve_fermarsi=deve_fermarsi,
            seed_principale=seed, indice_stagione=indice,
        )

    def candidata(mesi, indice):
        return analizza_candidata(
            mesi, indice_stagione=indice, modalita="terzetti",
            blacklist_iniziale=blacklist_iniziale,
        )

    def baseline(mesi, indice):
        return analizza_baseline(
            mesi, indice_stagione=indice, modalita="terzetti",
            blacklist_iniziale=blacklist_iniziale,
        )

    def rigenera(indice, deve_fermarsi):
        return genera_una_stagione_terzetti_gui(
            studenti, config, genere_misto, preferenza_resto2,
            geo["resto_in_prima_fila"], num_mesi,
            max_terzetti_prima_fila=geo["max_terzetti_prima_fila"],
            max_resti_prima_fila=geo["max_resti_prima_fila"],
            num_candidati=num_candidati,
            deve_fermarsi=deve_fermarsi,
            seed_principale=seed, indice_stagione=indice,
        )

    mesi, chiavi, info = genera_migliore_stagione(
        stagione,
        num_mesi,
        numero_stagioni_fisso=numero_stagioni,
        analizza_candidata=candidata,
        analizza_baseline=baseline,
        seleziona_stagione=seleziona_s1,
        rigenera_una_stagione=rigenera,
    )
    prima = tuple(mesi)
    mesi, chiavi = riordina_stagione_terzetti_gui(
        mesi, config, ordine_iniziale=info.get("ordine_stagione_preferito")
    )
    info = dict(info)
    info["punteggio"] = punteggio_stagione(chiavi)
    info["tot_ripetizioni"] = info["punteggio"][0]
    return mesi, chiavi, info, prima


def esegui_annuale_rc(
    classe: ClasseRC,
    *,
    modalita: str,
    seed: int,
    num_mesi: int = 6,
    numero_stagioni: int = 2,
    num_candidati: int | None = None,
    genere_misto: bool = False,
    posti_per_fila: int = 6,
    posizione_trio: str = "centro",
    terzetti_per_fila: int = 3,
    posizione_blocco_finale: str = "ultima",
    preferenza_resto2: str = "coppia",
    config_app=None,
) -> EsecuzioneAnnualeRC:
    config = config_app or configurazione_vuota_rc()
    blacklist_coppie = snapshot_blacklist(config)
    vicini_fisso = snapshot_vicini_fisso(config)
    blacklist_terzetti = snapshot_blacklist_terzetti(config)

    if modalita == "coppie":
        mesi, chiavi, info, prima = _genera_annuale_coppie(
            classe,
            seed=seed, num_mesi=num_mesi, numero_stagioni=numero_stagioni,
            num_candidati=(10 if num_candidati is None else num_candidati),
            genere_misto=genere_misto, posti_per_fila=posti_per_fila,
            posizione_trio=posizione_trio, config_app=config,
        )
    elif modalita == "terzetti":
        mesi, chiavi, info, prima = _genera_annuale_terzetti(
            classe,
            seed=seed, num_mesi=num_mesi, numero_stagioni=numero_stagioni,
            num_candidati=(3 if num_candidati is None else num_candidati),
            genere_misto=genere_misto, terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            preferenza_resto2=preferenza_resto2, config_app=config,
        )
    else:
        raise ValueError("modalita deve essere 'coppie' o 'terzetti'")

    successo = bool(mesi) and info.get("motivo_stop") not in {"mese_fallito", "annullato"}
    if not successo:
        return EsecuzioneAnnualeRC(modalita, False, tuple(mesi), tuple(chiavi), info, None, ())

    verifica = verifica_stagione_rc(
        classe, mesi, chiavi, info,
        modalita=modalita,
        posizione_trio=posizione_trio,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
        blacklist_iniziale=(blacklist_coppie if modalita == "coppie" else blacklist_terzetti),
        vicini_fisso_iniziali=(vicini_fisso if modalita == "coppie" else None),
    )
    verifiche_prima, _ = _verifica_mesi(
        classe, prima,
        modalita=modalita,
        posizione_trio=posizione_trio,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
    )
    firme_prima = tuple(_firma_da_verifica(v) for v in verifiche_prima)
    if sorted(firme_prima) != sorted(verifica.firme_mesi):
        verifica = VerificaStagioneRC(
            modalita=verifica.modalita,
            valida=False,
            mesi=verifica.mesi,
            chiavi_dichiarate=verifica.chiavi_dichiarate,
            chiavi_indipendenti=verifica.chiavi_indipendenti,
            punteggio_dichiarato=verifica.punteggio_dichiarato,
            punteggio_indipendente=verifica.punteggio_indipendente,
            firme_mesi=verifica.firme_mesi,
            violazioni=verifica.violazioni + ("il riordino ha modificato il multinsieme dei mesi",),
        )
    return EsecuzioneAnnualeRC(
        modalita, verifica.valida, tuple(mesi), tuple(chiavi), info, verifica, firme_prima
    )


def _figlio_annuale(target, payload, conn, evento):
    # Il runner RC osserva i payload IPC, non l'output diagnostico del motore.
    # Silenziare stdout/stderr del figlio evita che campagne di centinaia di casi
    # vengano rallentate o rese illeggibili da messaggi non strutturati.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        target(payload, conn, evento)


def esegui_annuale_processo_rc(
    classe: ClasseRC,
    *,
    modalita: str,
    seed: int,
    num_mesi: int = 4,
    numero_stagioni: int = 2,
    num_candidati: int | None = None,
    timeout_s: float = 30.0,
    genere_misto: bool = False,
    posti_per_fila: int = 6,
    posizione_trio: str = "centro",
    terzetti_per_fila: int = 3,
    posizione_blocco_finale: str = "ultima",
    preferenza_resto2: str = "coppia",
) -> EsecuzioneAnnualeRC:
    studenti, fisso = _studenti_produttivi(classe)
    config = configurazione_vuota_rc()
    if modalita == "coppie":
        aula = _aula_coppie(classe, posti_per_fila=posti_per_fila, posizione_trio=posizione_trio)
        richiesta = {
            "studenti": studenti,
            "configurazione_aula": aula,
            "config_app": config,
            "num_mesi": num_mesi,
            "modalita_trio": posizione_trio,
            "flag_genere_misto": genere_misto,
            "studente_fisso": fisso,
            "num_candidati": 10 if num_candidati is None else num_candidati,
            "seed_principale": seed,
            "numero_stagioni_fisso": numero_stagioni,
        }
        target = esegui_annuale_coppie_in_processo
    elif modalita == "terzetti":
        _aula, geo = _geometria_terzetti(
            classe,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            preferenza_resto2=preferenza_resto2,
        )
        richiesta = {
            "studenti": studenti,
            "config_app": config,
            "num_mesi": num_mesi,
            "genere_misto": genere_misto,
            "preferenza_resto2": preferenza_resto2,
            "resto_in_prima_fila": geo["resto_in_prima_fila"],
            "max_terzetti_prima_fila": geo["max_terzetti_prima_fila"],
            "max_resti_prima_fila": geo["max_resti_prima_fila"],
            "num_candidati": 3 if num_candidati is None else num_candidati,
            "seed_principale": seed,
            "numero_stagioni_fisso": numero_stagioni,
        }
        target = esegui_annuale_terzetti_in_processo
    else:
        raise ValueError("modalita non valida")

    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    evento = ctx.Event()
    processo = ctx.Process(target=_figlio_annuale, args=(target, pickle.dumps(richiesta), child, evento))
    processo.start()
    child.close()
    messaggio_finale = None
    try:
        while processo.is_alive() or parent.poll():
            if parent.poll(0.05):
                messaggio = parent.recv()
                if messaggio.get("tipo") in {"risultato", "errore", "eccezione"}:
                    messaggio_finale = messaggio
                    break
            processo.join(0.01)
            timeout_s -= 0.06
            if timeout_s <= 0:
                evento.set()
                processo.terminate()
                processo.join(2)
                raise TimeoutError("Annuale processo oltre il timeout RC")
    finally:
        if processo.is_alive():
            processo.terminate()
        processo.join(2)
        parent.close()

    if not messaggio_finale or messaggio_finale.get("tipo") != "risultato":
        return EsecuzioneAnnualeRC(modalita, False, (), (), {"messaggio": messaggio_finale}, None, ())
    risultato = messaggio_finale["risultato"]
    mesi = risultato["mesi"]
    chiavi = risultato["chiavi"]
    info = dict(risultato["info"])
    prima = tuple(mesi)
    if modalita == "coppie":
        mesi, chiavi = riordina_e_cattura_stagione_coppie(
            mesi, config, ordine_iniziale=info.get("ordine_stagione_preferito")
        )
        info["punteggio"] = punteggio_stagione(chiavi)
        info["tot_ripetizioni"] = info["punteggio"][0]
    verifica = verifica_stagione_rc(
        classe, mesi, chiavi, info,
        modalita=modalita,
        posizione_trio=posizione_trio,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        preferenza_resto2=preferenza_resto2,
    )
    return EsecuzioneAnnualeRC(
        modalita, verifica.valida, tuple(mesi), tuple(chiavi), info, verifica,
        tuple(_firma_da_verifica(v) for v in _verifica_mesi(
            classe, prima,
            modalita=modalita,
            posizione_trio=posizione_trio,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            preferenza_resto2=preferenza_resto2,
        )[0]),
    )


def satura_storico_rc(classe: ClasseRC, *, modalita: str):
    """Crea una fotografia di Storico in cui ogni adiacenza non assoluta è già usata."""
    config = configurazione_vuota_rc()
    nomi = [s.nome for s in classe.studenti]
    relazioni = []
    for i, a in enumerate(nomi):
        for b in nomi[i + 1:]:
            livello = max(
                classe.per_nome[a].incompatibilita_dict.get(b, 0),
                classe.per_nome[b].incompatibilita_dict.get(a, 0),
            )
            if livello < 3:
                relazioni.append((a, b))
    if modalita == "coppie":
        config.config_data["coppie_da_evitare"] = [
            {"tipo": "coppia", "studenti": [a, b], "volte_usata": 1}
            for a, b in relazioni
        ]
        if classe.studente_fisso is not None:
            config.config_data["studenti_vicino_fisso_contatore"] = {
                nome: 1 for nome in nomi if nome != classe.studente_fisso
            }
    elif modalita == "terzetti":
        config.config_data["adiacenze_terzetti_da_evitare"] = [
            {"tipo": "adiacenza", "studenti": [a, b], "volte_usata": 1}
            for a, b in relazioni
        ]
    else:
        raise ValueError("modalita non valida")
    return config


def telemetria_storico_saturo_rc(
    classe: ClasseRC,
    *,
    modalita: str,
    seed: int,
    num_candidati: int = 1,
) -> TelemetriaTentativiRC:
    studenti, fisso = _studenti_produttivi(classe)
    config = satura_storico_rc(classe, modalita=modalita)
    diag = DiagnosticaRicerca(etichetta=f"rc-{modalita}-storico-saturo")

    if modalita == "coppie":
        aula = _aula_coppie(classe, posti_per_fila=6, posizione_trio="centro")
        migliore, ultimo = calcola_miglior_mese(
            studenti, aula, config, "centro", False, fisso,
            coppie_gia_usate=snapshot_blacklist(config),
            num_candidati=num_candidati,
            seed_principale=seed,
            contesto_casuale={"operazione": "validazione_rc_t4", "mese": 1},
            diagnostica=diag,
        )
        risultato = migliore or ultimo
        verifica = None if migliore is None else verifica_aula_rc(
            classe, migliore.configurazione_aula, modalita="coppie", posizione_trio="centro"
        )
    else:
        aula, geo = _geometria_terzetti(
            classe, terzetti_per_fila=3,
            posizione_blocco_finale="ultima", preferenza_resto2="coppia"
        )
        gruppi, meta = mt.calcola_miglior_mese_terzetti(
            studenti, False, config_app=config,
            preferenza_resto2="coppia",
            resto_in_prima_fila=geo["resto_in_prima_fila"],
            max_terzetti_prima_fila=geo["max_terzetti_prima_fila"],
            max_resti_prima_fila=geo["max_resti_prima_fila"],
            num_candidati=num_candidati,
            seed_base=seed,
            contesto_casuale={"operazione": "validazione_rc_t4", "mese": 1},
            restituisci_metadati=True,
            diagnostica=diag,
        )
        risultato = gruppi or meta
        if gruppi is None:
            verifica = None
        else:
            esito = aula.piazza_gruppi_terzetti(gruppi)
            if esito.get("valido_struttura") and esito.get("valido_prima"):
                aula.rimuovi_banchi_vuoti()
                verifica = verifica_aula_rc(classe, aula, modalita="terzetti", preferenza_resto2="coppia")
            else:
                verifica = None

    dati = diag.esporta()
    iniziati = []
    successi = []
    saltati = []
    for evento in dati["eventi"]:
        tipo = evento["tipo"]
        d = evento["dati"]
        if tipo == "tentativo_inizio":
            iniziati.append(int(d["tentativo"]))
        elif tipo == "tentativo_fine" and d.get("successo"):
            successi.append(int(d["tentativo"]))
        elif tipo == "tentativo_saltato":
            saltati.append(int(d["tentativo"]))
    return TelemetriaTentativiRC(
        modalita=modalita,
        successo=verifica is not None and verifica.valido,
        tentativi_iniziati=tuple(iniziati),
        tentativi_successo=tuple(successi),
        tentativi_saltati=tuple(saltati),
        nodi_totali=int(dati["riepilogo"]["nodi_totali"]),
        pruning_totali=int(dati["riepilogo"]["pruning_totali"]),
        risultato_valido=(verifica.valido if verifica is not None else None),
    )

@dataclass(frozen=True, slots=True)
class VerificaAccumuloStoricoRC:
    modalita: str
    mesi_completati: int
    valido: bool
    differenze: tuple[str, ...]
    contatori_attesi: tuple[tuple[tuple[str, str], int], ...]
    contatori_reali: tuple[tuple[tuple[str, str], int], ...]
    vicini_fisso_attesi: tuple[tuple[str, int], ...] = ()
    vicini_fisso_reali: tuple[tuple[str, int], ...] = ()

    def come_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contatori_blacklist(config, *, modalita: str) -> dict[tuple[str, str], int]:
    chiave = "coppie_da_evitare" if modalita == "coppie" else "adiacenze_terzetti_da_evitare"
    risultato: dict[tuple[str, str], int] = {}
    for voce in config.config_data.get(chiave, []):
        studenti = voce.get("studenti", [])
        if len(studenti) != 2:
            continue
        coppia = tuple(sorted((studenti[0], studenti[1])))
        risultato[coppia] = int(voce.get("volte_usata", 0))
    return risultato


def verifica_accumulo_storico_rc(
    classe: ClasseRC,
    *,
    modalita: str,
    seed: int,
    num_mesi: int = 10,
    num_candidati: int = 1,
) -> VerificaAccumuloStoricoRC:
    """Confronta blacklist produttiva e conteggio fisico indipendente mese per mese."""
    studenti, fisso = _studenti_produttivi(classe)
    config = configurazione_vuota_rc()
    attesi: dict[tuple[str, str], int] = {}
    vicini_attesi: dict[str, int] = {}
    differenze: list[str] = []
    mesi_completati = 0

    if modalita == "coppie":
        aula = _aula_coppie(classe, posti_per_fila=6, posizione_trio="centro")
        for mese in range(1, num_mesi + 1):
            migliore, _ultimo = calcola_miglior_mese(
                studenti, aula, config, "centro", False, fisso,
                coppie_gia_usate=snapshot_blacklist(config),
                num_candidati=num_candidati,
                seed_principale=seed,
                contesto_casuale={"operazione": "validazione_rc_storico", "mese": mese},
            )
            if migliore is None:
                differenze.append(f"mese {mese}: motore non completato")
                break
            verifica = verifica_aula_rc(
                classe, migliore.configurazione_aula,
                modalita="coppie", posizione_trio="centro"
            )
            if not verifica.valido:
                differenze.extend(f"mese {mese}: {v.codice}" for v in verifica.violazioni)
                break
            adiacenze = {tuple(sorted(c)) for c in verifica.adiacenze}
            if fisso is not None:
                nome_fisso = fisso.get_nome_completo()
                ad_fisso = [c for c in adiacenze if nome_fisso in c]
                if len(ad_fisso) != 1:
                    differenze.append(f"mese {mese}: FISSO con {len(ad_fisso)} adiacenze")
                    break
                coppia_fisso = ad_fisso[0]
                vicino = coppia_fisso[0] if coppia_fisso[1] == nome_fisso else coppia_fisso[1]
                vicini_attesi[vicino] = vicini_attesi.get(vicino, 0) + 1
                adiacenze.remove(coppia_fisso)
            for coppia in adiacenze:
                attesi[coppia] = attesi.get(coppia, 0) + 1

            config._aggiorna_coppie_da_evitare(
                migliore.coppie_formate,
                getattr(migliore, "trio_identificato", None),
                studente_fisso=getattr(migliore, "studente_fisso", None),
                gruppo_adiacente_fisso=getattr(migliore, "gruppo_adiacente_fisso", None),
                nome_adiacente_fisso=getattr(migliore, "nome_adiacente_fisso", None),
            )
            mesi_completati += 1
            reali = _contatori_blacklist(config, modalita="coppie")
            vicini_reali = {
                nome: int(volte)
                for nome, volte in config.config_data.get("studenti_vicino_fisso_contatore", {}).items()
            }
            if reali != attesi:
                differenze.append(f"mese {mese}: blacklist coppie {reali} != {attesi}")
                break
            if vicini_reali != vicini_attesi:
                differenze.append(f"mese {mese}: contatore FISSO {vicini_reali} != {vicini_attesi}")
                break
    elif modalita == "terzetti":
        aula_base, geo = _geometria_terzetti(
            classe, terzetti_per_fila=3,
            posizione_blocco_finale="ultima", preferenza_resto2="coppia"
        )
        for mese in range(1, num_mesi + 1):
            gruppi, _meta = mt.calcola_miglior_mese_terzetti(
                studenti, False, config_app=config,
                preferenza_resto2="coppia",
                resto_in_prima_fila=geo["resto_in_prima_fila"],
                max_terzetti_prima_fila=geo["max_terzetti_prima_fila"],
                max_resti_prima_fila=geo["max_resti_prima_fila"],
                num_candidati=num_candidati,
                seed_base=seed,
                contesto_casuale={"operazione": "validazione_rc_storico", "mese": mese},
                restituisci_metadati=True,
            )
            if gruppi is None:
                differenze.append(f"mese {mese}: motore non completato")
                break
            aula, _ = _geometria_terzetti(
                classe, terzetti_per_fila=3,
                posizione_blocco_finale="ultima", preferenza_resto2="coppia"
            )
            esito = aula.piazza_gruppi_terzetti(gruppi)
            if not esito.get("valido_struttura") or not esito.get("valido_prima"):
                differenze.append(f"mese {mese}: piazzamento non valido")
                break
            aula.rimuovi_banchi_vuoti()
            verifica = verifica_aula_rc(classe, aula, modalita="terzetti", preferenza_resto2="coppia")
            if not verifica.valido:
                differenze.extend(f"mese {mese}: {v.codice}" for v in verifica.violazioni)
                break
            for coppia in {tuple(sorted(c)) for c in verifica.adiacenze}:
                attesi[coppia] = attesi.get(coppia, 0) + 1
            aggiorna_blacklist_terzetti(config, adiacenze_per_blacklist_terzetti(gruppi))
            mesi_completati += 1
            reali = _contatori_blacklist(config, modalita="terzetti")
            if reali != attesi:
                differenze.append(f"mese {mese}: blacklist terzetti {reali} != {attesi}")
                break
    else:
        raise ValueError("modalita non valida")

    reali_finali = _contatori_blacklist(config, modalita=modalita)
    vicini_reali_finali = {
        nome: int(volte)
        for nome, volte in config.config_data.get("studenti_vicino_fisso_contatore", {}).items()
    }
    return VerificaAccumuloStoricoRC(
        modalita=modalita,
        mesi_completati=mesi_completati,
        valido=not differenze and mesi_completati == num_mesi,
        differenze=tuple(differenze),
        contatori_attesi=tuple(sorted(attesi.items())),
        contatori_reali=tuple(sorted(reali_finali.items())),
        vicini_fisso_attesi=tuple(sorted(vicini_attesi.items())),
        vicini_fisso_reali=tuple(sorted(vicini_reali_finali.items())),
    )
