# -*- coding: utf-8 -*-
"""Motore annuale eseguibile in un processo Python separato.

Il modulo è deliberatamente privo di import Qt. Riceve una fotografia già
serializzata degli input, esegue i medesimi percorsi R0.8 dei worker annuali
a coppie e a terzetti e comunica soltanto messaggi serializzabili al processo
principale.
"""

from __future__ import annotations

import pickle
import traceback

from moduli.annuale import (
    BUDGET_STAGIONI_TERZETTI_SEC,
    K_CONVERGENZA_TERZETTI,
    TETTO_STAGIONI_TERZETTI,
    genera_migliore_stagione,
    genera_una_stagione_gui,
    genera_una_stagione_terzetti_gui,
    riordina_stagione_terzetti_gui,
)
from moduli.lingua import forma_numerata
from moduli.metrica_pulizia import (
    punteggio_stagione,
    snapshot_blacklist,
    snapshot_blacklist_terzetti,
    snapshot_vicini_fisso,
)
from moduli.vincoli import MotoreVincoliConfigurato
from moduli.politica_annuale import (
    analizza_baseline,
    analizza_candidata,
    seleziona_s1,
)


def esegui_annuale_coppie_in_processo(
    payload_serializzato: bytes,
    connessione,
    evento_stop,
) -> None:
    """Esegue l'Annuale a coppie e invia progresso/esito sul canale ricevuto."""

    def invia(tipo: str, **dati) -> None:
        connessione.send({"tipo": tipo, **dati})

    try:
        richiesta = pickle.loads(payload_serializzato)
        studenti = richiesta["studenti"]
        configurazione_aula = richiesta["configurazione_aula"]
        config_app = richiesta["config_app"]
        num_mesi = richiesta["num_mesi"]
        modalita_trio = richiesta["modalita_trio"]
        flag_genere_misto = richiesta["flag_genere_misto"]
        studente_fisso = richiesta["studente_fisso"]
        num_candidati = richiesta["num_candidati"]
        seed_principale = richiesta["seed_principale"]

        stagione_corrente = 1
        ultimo_best = None
        ultima_eta = None
        report_fallimento_annuale = None

        def emetti_stato(mese):
            invia(
                "stato",
                stato={
                    "tentativo": stagione_corrente,
                    "mese": mese,
                    "num_mesi": num_mesi,
                    "best": ultimo_best,
                    "eta_max": ultima_eta,
                },
            )

        def progresso_mese(mese, _num_mesi):
            emetti_stato(mese)

        def progresso(info):
            nonlocal stagione_corrente, ultimo_best, ultima_eta
            if info["motivo_stop"] is not None:
                return
            ultimo_best = info["tot_ripetizioni"]
            ultima_eta = info["eta_max"]
            stagione_corrente = info["n_stagioni"] + 1
            emetti_stato(0)

        def cattura_fallimento_annuale(report):
            nonlocal report_fallimento_annuale
            report_fallimento_annuale = report

        def stagione_coppie(
            indice_stagione,
            t0_globale,
            budget_secondi,
            deve_fermarsi,
        ):
            return genera_una_stagione_gui(
                studenti,
                configurazione_aula,
                config_app,
                modalita_trio,
                flag_genere_misto,
                studente_fisso,
                num_mesi,
                num_candidati,
                progresso=progresso_mese,
                t0_globale=t0_globale,
                budget_secondi=budget_secondi,
                deve_fermarsi=deve_fermarsi,
                on_fallimento=cattura_fallimento_annuale,
                seed_principale=seed_principale,
                indice_stagione=indice_stagione,
            )

        blacklist_iniziale = snapshot_blacklist(config_app)
        vicini_fisso_iniziali = snapshot_vicini_fisso(config_app)

        def analizza_candidata_coppie(mesi, indice):
            return analizza_candidata(
                mesi,
                indice_stagione=indice,
                modalita="coppie",
                blacklist_iniziale=blacklist_iniziale,
                vicini_fisso_iniziali=vicini_fisso_iniziali,
            )

        def analizza_baseline_coppie(mesi, indice):
            return analizza_baseline(
                mesi,
                indice_stagione=indice,
                modalita="coppie",
                blacklist_iniziale=blacklist_iniziale,
                vicini_fisso_iniziali=vicini_fisso_iniziali,
            )

        def rigenera_stagione_coppie(indice, deve_fermarsi):
            return genera_una_stagione_gui(
                studenti,
                configurazione_aula,
                config_app,
                modalita_trio,
                flag_genere_misto,
                studente_fisso,
                num_mesi,
                num_candidati,
                progresso=None,
                t0_globale=None,
                budget_secondi=None,
                deve_fermarsi=deve_fermarsi,
                on_fallimento=None,
                seed_principale=seed_principale,
                indice_stagione=indice,
            )

        migliori_mesi, migliori_chiavi, info = genera_migliore_stagione(
            stagione_coppie,
            num_mesi,
            progresso=progresso,
            deve_fermarsi=evento_stop.is_set,
            numero_stagioni_fisso=richiesta["numero_stagioni_fisso"],
            analizza_candidata=analizza_candidata_coppie,
            analizza_baseline=analizza_baseline_coppie,
            seleziona_stagione=seleziona_s1,
            rigenera_una_stagione=rigenera_stagione_coppie,
        )

        info["seed_principale"] = seed_principale
        info["modalita"] = "coppie"
        for assegnatore in migliori_mesi:
            assegnatore.contesto_casuale.update({
                "stagioni_generate": info.get("n_stagioni"),
                "stagione_vincente": info.get("indice_stagione_migliore"),
            })

        if info["motivo_stop"] == "mese_fallito":
            generati = len(migliori_mesi) if migliori_mesi else 0
            invia(
                "errore",
                messaggio=(
                    "Non è stato possibile completare una disposizione "
                    "valida per uno dei mesi ("
                    f"{forma_numerata(generati, 'completato 1 mese', f'completati {generati} mesi')} "
                    f"su {num_mesi})."
                ),
                report=report_fallimento_annuale,
            )
            return

        # Il motore installa durante il tentativo una closure locale come
        # wrapper del punteggio blacklist. Serve soltanto durante il calcolo e
        # non è serializzabile con pickle; prima del trasferimento ripristiniamo
        # il metodo di classe originale, senza cambiare i dati del risultato.
        for assegnatore in migliori_mesi:
            motore = getattr(assegnatore, "motore_vincoli", None)
            if motore is None:
                continue
            motore.calcola_punteggio_coppia = (
                MotoreVincoliConfigurato.calcola_punteggio_coppia.__get__(
                    motore,
                    MotoreVincoliConfigurato,
                )
            )
            for attributo_transitorio in (
                "_calcola_punteggio_coppia_originale",
                "_penalita_storico_applicata",
            ):
                if hasattr(motore, attributo_transitorio):
                    delattr(motore, attributo_transitorio)

        # Il riordino finale e la costruzione dei report restano nel processo
        # GUI: il callback storico della R0.8 è legato alla finestra e non deve
        # attraversare il confine di processo.
        info["_risultato_grezzo_processo"] = True
        risultato = {
            "mesi": migliori_mesi,
            "chiavi": migliori_chiavi,
            "info": info,
        }
        # Produce un errore leggibile qui, anziché un EOF ambiguo nel bridge,
        # qualora un futuro attributo del dominio diventi non serializzabile.
        pickle.dumps(risultato, protocol=pickle.HIGHEST_PROTOCOL)
        invia("risultato", risultato=risultato)
    except BaseException as errore:  # il figlio deve sempre comunicare l'esito
        try:
            invia(
                "eccezione",
                messaggio=(
                    "Errore nel processo Annuale: "
                    f"{errore.__class__.__name__}: {errore}"
                ),
                traceback=traceback.format_exc(),
            )
        except BaseException:
            pass
    finally:
        try:
            connessione.close()
        except BaseException:
            pass


def esegui_annuale_terzetti_in_processo(
    payload_serializzato: bytes,
    connessione,
    evento_stop,
) -> None:
    """Esegue l'Annuale a terzetti e invia progresso/esito sul canale ricevuto."""

    def invia(tipo: str, **dati) -> None:
        connessione.send({"tipo": tipo, **dati})

    try:
        richiesta = pickle.loads(payload_serializzato)
        studenti = richiesta["studenti"]
        config_app = richiesta["config_app"]
        num_mesi = richiesta["num_mesi"]
        genere_misto = richiesta["genere_misto"]
        preferenza_resto2 = richiesta["preferenza_resto2"]
        resto_in_prima_fila = richiesta["resto_in_prima_fila"]
        max_terzetti_prima_fila = richiesta["max_terzetti_prima_fila"]
        max_resti_prima_fila = richiesta["max_resti_prima_fila"]
        num_candidati = richiesta["num_candidati"]
        seed_principale = richiesta["seed_principale"]

        stagione_corrente = 1
        ultimo_best = None
        ultima_eta = None
        report_fallimento_annuale = None

        def emetti_stato(mese):
            invia(
                "stato",
                stato={
                    "tentativo": stagione_corrente,
                    "mese": mese,
                    "num_mesi": num_mesi,
                    "best": ultimo_best,
                    "eta_max": ultima_eta,
                },
            )

        def progresso_mese(mese, _num_mesi):
            emetti_stato(mese)

        def progresso(info):
            nonlocal stagione_corrente, ultimo_best, ultima_eta
            if info["motivo_stop"] is not None:
                return
            ultimo_best = info["tot_ripetizioni"]
            ultima_eta = info["eta_max"]
            stagione_corrente = info["n_stagioni"] + 1
            emetti_stato(0)

        def cattura_fallimento_annuale(report):
            nonlocal report_fallimento_annuale
            report_fallimento_annuale = report

        def stagione_terzetti(
            indice_stagione,
            t0_globale,
            budget_secondi,
            deve_fermarsi,
        ):
            return genera_una_stagione_terzetti_gui(
                studenti,
                config_app,
                genere_misto,
                preferenza_resto2,
                resto_in_prima_fila,
                num_mesi,
                max_terzetti_prima_fila=max_terzetti_prima_fila,
                max_resti_prima_fila=max_resti_prima_fila,
                num_candidati=num_candidati,
                progresso=progresso_mese,
                t0_globale=t0_globale,
                budget_secondi=budget_secondi,
                deve_fermarsi=deve_fermarsi,
                on_fallimento=cattura_fallimento_annuale,
                seed_principale=seed_principale,
                indice_stagione=indice_stagione,
            )

        blacklist_iniziale = snapshot_blacklist_terzetti(config_app)

        def analizza_candidata_terzetti(mesi, indice):
            return analizza_candidata(
                mesi,
                indice_stagione=indice,
                modalita="terzetti",
                blacklist_iniziale=blacklist_iniziale,
            )

        def analizza_baseline_terzetti(mesi, indice):
            return analizza_baseline(
                mesi,
                indice_stagione=indice,
                modalita="terzetti",
                blacklist_iniziale=blacklist_iniziale,
            )

        def rigenera_stagione_terzetti(indice, deve_fermarsi):
            return genera_una_stagione_terzetti_gui(
                studenti,
                config_app,
                genere_misto,
                preferenza_resto2,
                resto_in_prima_fila,
                num_mesi,
                max_terzetti_prima_fila=max_terzetti_prima_fila,
                max_resti_prima_fila=max_resti_prima_fila,
                num_candidati=num_candidati,
                progresso=None,
                t0_globale=None,
                budget_secondi=None,
                deve_fermarsi=deve_fermarsi,
                on_fallimento=None,
                seed_principale=seed_principale,
                indice_stagione=indice,
            )

        migliori_mesi, migliori_chiavi, info = genera_migliore_stagione(
            stagione_terzetti,
            num_mesi,
            budget_secondi=BUDGET_STAGIONI_TERZETTI_SEC,
            tetto=TETTO_STAGIONI_TERZETTI,
            k_convergenza=K_CONVERGENZA_TERZETTI,
            progresso=progresso,
            deve_fermarsi=evento_stop.is_set,
            numero_stagioni_fisso=richiesta["numero_stagioni_fisso"],
            analizza_candidata=analizza_candidata_terzetti,
            analizza_baseline=analizza_baseline_terzetti,
            seleziona_stagione=seleziona_s1,
            rigenera_una_stagione=rigenera_stagione_terzetti,
        )

        info["seed_principale"] = seed_principale
        info["modalita"] = "terzetti"
        for mese in migliori_mesi:
            metadati = mese.get("metadati_casualita") or {}
            contesto = metadati.setdefault("contesto", {})
            contesto.update({
                "stagioni_generate": info.get("n_stagioni"),
                "stagione_vincente": info.get("indice_stagione_migliore"),
            })
            mese["metadati_casualita"] = metadati

        if info["motivo_stop"] == "mese_fallito":
            generati = len(migliori_mesi) if migliori_mesi else 0
            invia(
                "errore",
                messaggio=(
                    "Non è stata trovata una disposizione valida per uno "
                    "dei mesi "
                    "("
                    f"{forma_numerata(generati, 'completato 1 mese', f'completati {generati} mesi')} "
                    f"su {num_mesi})."
                ),
                report=report_fallimento_annuale,
            )
            return

        migliori_mesi, migliori_chiavi = riordina_stagione_terzetti_gui(
            migliori_mesi,
            config_app,
            ordine_iniziale=info.get("ordine_stagione_preferito"),
        )
        info["punteggio"] = punteggio_stagione(migliori_chiavi)
        info["tot_ripetizioni"] = info["punteggio"][0]
        info["riordino_temporale"] = True
        risultato = {
            "mesi": migliori_mesi,
            "chiavi": migliori_chiavi,
            "info": info,
        }
        pickle.dumps(risultato, protocol=pickle.HIGHEST_PROTOCOL)
        invia("risultato", risultato=risultato)
    except BaseException as errore:
        try:
            invia(
                "eccezione",
                messaggio=(
                    "Errore nel processo Annuale a terzetti: "
                    f"{errore.__class__.__name__}: {errore}"
                ),
                traceback=traceback.format_exc(),
            )
        except BaseException:
            pass
    finally:
        try:
            connessione.close()
        except BaseException:
            pass

