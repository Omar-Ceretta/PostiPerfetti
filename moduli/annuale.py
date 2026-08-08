# -*- coding: utf-8 -*-
"""Motore annuale puro di «PostiPerfetti».

Questo modulo genera, confronta e riordina stagioni senza conoscere widget,
segnali o finestre. I worker Qt vivono in ``worker_annuale.py``; la finestra
principale si limita ad avviarli e a riceverne i risultati.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import time

import moduli.motore_terzetti as mt

from moduli.casualita import (
    risolvi_numero_stagioni_riproduzione,
    risolvi_seed_principale,
)
from moduli.generazione import NUM_CANDIDATI, calcola_miglior_mese
from moduli.metrica_pulizia import (
    adiacenze_per_blacklist_terzetti,
    chiave_pulizia,
    chiave_pulizia_terzetti,
    conta_riutilizzate_con_foto,
    coppie_per_blacklist,
    punteggio_stagione,
    riordina_stagione_per_pulizia,
    riordina_stagione_per_pulizia_terzetti,
    snapshot_blacklist,
    snapshot_blacklist_terzetti,
    snapshot_vicini_fisso,
)
from moduli.strato_storico import aggiorna_blacklist_terzetti

from moduli.politica_annuale import (
    descrivi_stagione,
    riordino_temporale_protetto,
)


BUDGET_STAGIONI_SEC = 600
TETTO_STAGIONI = 5000
K_CONVERGENZA = 300

BUDGET_STAGIONI_TERZETTI_SEC = 600
TETTO_STAGIONI_TERZETTI = 5000
K_CONVERGENZA_TERZETTI = 300


def genera_una_stagione_gui(
    studenti,
    configurazione_aula,
    config_app,
    modalita_trio,
    flag_genere_misto,
    studente_fisso,
    num_mesi,
    num_candidati=NUM_CANDIDATI,
    progresso=None,
    t0_globale=None,
    budget_secondi=None,
    deve_fermarsi=None,
    on_fallimento=None,
    seed_principale=None,
    indice_stagione=1,
    diagnostica=None,
):
    """Genera una stagione a coppie su una configurazione temporanea."""
    seed_principale = risolvi_seed_principale(seed_principale)
    config_temp = config_app.copia_temporanea()

    mesi = []
    chiavi = []
    stop_mese = None
    ultima_durata = 0.0

    for mese in range(1, num_mesi + 1):
        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if t0_globale is not None and budget_secondi is not None:
            elapsed = time.monotonic() - t0_globale
            proiezione = elapsed + (ultima_durata if mese > 1 else 0.0)
            if proiezione >= budget_secondi:
                stop_mese = "budget"
                break

        t_inizio_mese = time.monotonic()
        coppie_gia_usate = snapshot_blacklist(config_temp)
        vicini_fisso_gia_usati = snapshot_vicini_fisso(config_temp)

        def _budget_scaduto():
            if t0_globale is None or budget_secondi is None:
                return False
            return (time.monotonic() - t0_globale) >= budget_secondi

        def _stop_mese_corrente():
            if deve_fermarsi is not None and deve_fermarsi():
                return True
            return _budget_scaduto()

        miglior, ultimo = calcola_miglior_mese(
            studenti,
            configurazione_aula,
            config_temp,
            modalita_trio,
            flag_genere_misto,
            studente_fisso,
            coppie_gia_usate,
            num_candidati,
            deve_fermarsi=_stop_mese_corrente,
            seed_principale=seed_principale,
            contesto_casuale={
                "operazione": "annuale",
                "stagione": indice_stagione,
                "mese": mese,
            },
            diagnostica=diagnostica,
        )

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break
        if _budget_scaduto():
            stop_mese = "budget"
            break

        if miglior is None:
            if on_fallimento is not None:
                on_fallimento(getattr(ultimo, "report_fallimento", None))
            stop_mese = "mese_fallito"
            break

        mesi.append(miglior)
        chiavi.append(chiave_pulizia(
            miglior,
            coppie_gia_usate,
            vicini_fisso_gia_usati,
        ))

        config_temp._aggiorna_coppie_da_evitare(
            miglior.coppie_formate,
            getattr(miglior, "trio_identificato", None),
            studente_fisso=getattr(miglior, "studente_fisso", None),
            gruppo_adiacente_fisso=getattr(
                miglior,
                "gruppo_adiacente_fisso",
                None,
            ),
            nome_adiacente_fisso=getattr(
                miglior,
                "nome_adiacente_fisso",
                None,
            ),
        )

        ultima_durata = time.monotonic() - t_inizio_mese
        if progresso is not None:
            progresso(mese, num_mesi)

    return mesi, chiavi, config_temp, stop_mese


def genera_una_stagione_terzetti_gui(
    studenti,
    config_app,
    genere_misto,
    preferenza_resto2,
    resto_in_prima_fila,
    num_mesi,
    max_terzetti_prima_fila=None,
    max_resti_prima_fila=None,
    num_candidati=None,
    progresso=None,
    t0_globale=None,
    budget_secondi=None,
    deve_fermarsi=None,
    on_fallimento=None,
    seed_principale=None,
    indice_stagione=1,
    diagnostica=None,
):
    """Genera una stagione a terzetti su una configurazione temporanea."""
    if num_candidati is None:
        num_candidati = mt.NUM_CANDIDATI_TERZETTI

    seed_principale = risolvi_seed_principale(seed_principale)
    config_temp = config_app.copia_temporanea()

    mesi = []
    chiavi = []
    stop_mese = None
    ultima_durata = 0.0

    for mese in range(1, num_mesi + 1):
        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if t0_globale is not None and budget_secondi is not None:
            elapsed = time.monotonic() - t0_globale
            proiezione = elapsed + (ultima_durata if mese > 1 else 0.0)
            if proiezione >= budget_secondi:
                stop_mese = "budget"
                break

        t_inizio_mese = time.monotonic()
        adiacenze_prima = snapshot_blacklist_terzetti(config_temp)

        gruppi, metadati_casualita = mt.calcola_miglior_mese_terzetti(
            studenti,
            genere_misto,
            config_app=config_temp,
            preferenza_resto2=preferenza_resto2,
            resto_in_prima_fila=resto_in_prima_fila,
            max_terzetti_prima_fila=max_terzetti_prima_fila,
            max_resti_prima_fila=max_resti_prima_fila,
            num_candidati=num_candidati,
            seed_base=seed_principale,
            contesto_casuale={
                "operazione": "annuale",
                "stagione": indice_stagione,
                "mese": mese,
            },
            restituisci_metadati=True,
            diagnostica=diagnostica,
        )

        if deve_fermarsi is not None and deve_fermarsi():
            stop_mese = "annullato"
            break

        if gruppi is None:
            if on_fallimento is not None:
                on_fallimento(
                    metadati_casualita.get("report_fallimento")
                    or mt.costruisci_report_fallimento_terzetti(
                        studenti,
                        genere_misto=genere_misto,
                        config_app=config_temp,
                        preferenza_resto2=preferenza_resto2,
                        resto_in_prima_fila=resto_in_prima_fila,
                        max_terzetti_prima_fila=max_terzetti_prima_fila,
                        max_resti_prima_fila=max_resti_prima_fila,
                        metadati_casualita=metadati_casualita,
                    )
                )
            stop_mese = "mese_fallito"
            break

        mesi.append({
            "gruppi": gruppi,
            "adiacenze_prima": adiacenze_prima,
            "metadati_casualita": metadati_casualita,
        })
        chiavi.append(chiave_pulizia_terzetti(gruppi, adiacenze_prima))

        aggiorna_blacklist_terzetti(
            config_temp,
            adiacenze_per_blacklist_terzetti(gruppi),
        )

        ultima_durata = time.monotonic() - t_inizio_mese
        if progresso is not None:
            progresso(mese, num_mesi)

    return mesi, chiavi, config_temp, stop_mese


def formatta_durata(secondi) -> str:
    """Formatta una durata in secondi come stringa breve per l'interfaccia."""
    secondi = int(round(secondi))
    ore, resto = divmod(secondi, 3600)
    minuti, secondi_residui = divmod(resto, 60)
    if ore > 0:
        return f"{ore}h {minuti:02d}m"
    if minuti > 0:
        return f"{minuti}m {secondi_residui:02d}s"
    return f"{secondi_residui}s"



def genera_migliore_stagione(
    genera_una_stagione,
    num_mesi,
    budget_secondi=BUDGET_STAGIONI_SEC,
    tetto=TETTO_STAGIONI,
    k_convergenza=K_CONVERGENZA,
    progresso=None,
    deve_fermarsi=None,
    numero_stagioni_fisso=None,
    analizza_candidata=None,
    analizza_baseline=None,
    seleziona_stagione=None,
    rigenera_una_stagione=None,
):
    """Seleziona la migliore stagione con gli arresti previsti dal progetto."""
    numero_stagioni_fisso = risolvi_numero_stagioni_riproduzione(
        numero_stagioni_fisso
    )
    budget_generatore = (
        float("inf")
        if numero_stagioni_fisso is not None
        else budget_secondi
    )
    t0 = time.monotonic()

    def _genera_una(indice_stagione):
        return genera_una_stagione(
            indice_stagione,
            t0,
            budget_generatore,
            deve_fermarsi,
        )

    migliori_mesi, migliori_chiavi, _config_temp, stop_prima = _genera_una(1)
    miglior_punteggio = punteggio_stagione(migliori_chiavi)
    riepiloghi_candidati = []
    if stop_prima is None and analizza_candidata is not None:
        riepiloghi_candidati.append(analizza_candidata(migliori_mesi, 1))
    n_stagioni = 1
    n_stagioni_complete = 1 if stop_prima is None else 0
    indice_stagione_migliore = 1
    senza_migliorare = 0
    durata_media = time.monotonic() - t0
    motivo_stop = None

    def _emetti(motivo):
        if progresso is None:
            return
        elapsed = time.monotonic() - t0
        if numero_stagioni_fisso is not None:
            eta_max = max(
                0,
                numero_stagioni_fisso - n_stagioni,
            ) * durata_media
        else:
            eta_a_budget = max(0.0, budget_secondi - elapsed)
            eta_a_tetto = max(0, tetto - n_stagioni) * durata_media
            eta_max = min(eta_a_budget, eta_a_tetto)
        progresso({
            "n_stagioni": n_stagioni,
            "tot_ripetizioni": miglior_punteggio[0],
            "elapsed": elapsed,
            "eta_max": eta_max,
            "k": durata_media,
            "motivo_stop": motivo,
        })

    if stop_prima == "annullato":
        motivo_stop = "annullato"
        _emetti(motivo_stop)
    elif stop_prima == "mese_fallito":
        motivo_stop = "mese_fallito"
        _emetti(motivo_stop)
    elif stop_prima == "budget":
        motivo_stop = "budget (1ª annata parziale)"
        _emetti(motivo_stop)
    else:
        _emetti(None)
        while True:
            if deve_fermarsi is not None and deve_fermarsi():
                motivo_stop = "annullato"
                break

            elapsed = time.monotonic() - t0
            if numero_stagioni_fisso is not None:
                if n_stagioni >= numero_stagioni_fisso:
                    motivo_stop = "riproduzione"
                    break
            else:
                if elapsed + durata_media > budget_secondi:
                    motivo_stop = "budget"
                    break
                if n_stagioni >= tetto:
                    motivo_stop = "tetto"
                    break
                if senza_migliorare >= k_convergenza:
                    motivo_stop = "convergenza"
                    break

            indice_stagione = n_stagioni + 1
            mesi_i, chiavi_i, _config_temp, stop_i = _genera_una(
                indice_stagione
            )

            if stop_i == "annullato":
                motivo_stop = "annullato"
                break
            if stop_i == "budget":
                motivo_stop = "budget"
                break

            n_stagioni += 1
            if stop_i is None:
                n_stagioni_complete += 1
                if analizza_candidata is not None:
                    riepiloghi_candidati.append(
                        analizza_candidata(mesi_i, indice_stagione)
                    )
                punteggio_i = punteggio_stagione(chiavi_i)
                if punteggio_i < miglior_punteggio:
                    miglior_punteggio = punteggio_i
                    migliori_mesi, migliori_chiavi = mesi_i, chiavi_i
                    indice_stagione_migliore = indice_stagione
                    senza_migliorare = 0
                else:
                    senza_migliorare += 1
            else:
                senza_migliorare += 1

            durata_media = (time.monotonic() - t0) / n_stagioni
            _emetti(None)

        _emetti(motivo_stop)

    politica_annuale = "C1"
    ordine_stagione_preferito = None
    indice_stagione_c1 = indice_stagione_migliore
    if (
        migliori_mesi
        and analizza_baseline is not None
        and seleziona_stagione is not None
        and riepiloghi_candidati
        and motivo_stop not in ("annullato", "mese_fallito")
    ):
        riepilogo_base = analizza_baseline(
            migliori_mesi,
            indice_stagione_migliore,
        )
        scelta = seleziona_stagione(
            riepiloghi_candidati,
            riepilogo_base,
        )
        indice_scelto = int(scelta["indice"])
        politica_annuale = scelta.get("politica", "C1")
        ordine_stagione_preferito = list(scelta.get("ordine") or [])

        if indice_scelto != indice_stagione_migliore:
            # Le stagioni sono deterministiche rispetto a seed e indice.
            # Rigeneriamo soltanto la candidata finale, evitando di trattenere
            # in memoria migliaia di annate complete.
            if rigenera_una_stagione is None:
                mesi_scelti, chiavi_scelte, _config_scelta, stop_scelta = (
                    genera_una_stagione(
                        indice_scelto,
                        time.monotonic(),
                        float("inf"),
                        deve_fermarsi,
                    )
                )
            else:
                mesi_scelti, chiavi_scelte, _config_scelta, stop_scelta = (
                    rigenera_una_stagione(indice_scelto, deve_fermarsi)
                )
            if stop_scelta is None and len(mesi_scelti) == num_mesi:
                migliori_mesi = mesi_scelti
                migliori_chiavi = chiavi_scelte
                indice_stagione_migliore = indice_scelto
                metriche_scelte = scelta.get("metriche") or {}
                miglior_punteggio = (
                    int(metriche_scelte.get("riusi", 0)),
                    int(metriche_scelte.get("incompatibilita_l1", 0))
                    + 10 * int(metriche_scelte.get("incompatibilita_l2", 0))
                    + 1000 * int(metriche_scelte.get("incompatibilita_l3", 0)),
                    -int(metriche_scelte.get("affinita_totali", 0)),
                )
            else:
                politica_annuale = "C1"
                ordine_stagione_preferito = list(riepilogo_base.get("ordine") or [])
        else:
            if politica_annuale == "C1":
                ordine_stagione_preferito = list(
                    riepilogo_base.get("ordine") or []
                )

    info = {
        "n_stagioni": n_stagioni,
        "n_stagioni_complete": n_stagioni_complete,
        "punteggio": miglior_punteggio,
        "tot_ripetizioni": miglior_punteggio[0],
        "motivo_stop": motivo_stop,
        "elapsed": time.monotonic() - t0,
        "k": durata_media,
        "mesi_completi": len(migliori_mesi),
        "num_mesi_richiesti": num_mesi,
        "indice_stagione_migliore": indice_stagione_migliore,
        "numero_stagioni_fisso": numero_stagioni_fisso,
        "indice_stagione_c1": indice_stagione_c1,
        "politica_annuale": politica_annuale,
        "ordine_stagione_preferito": ordine_stagione_preferito,
    }
    return migliori_mesi, migliori_chiavi, info


def riordina_e_cattura_stagione_coppie(
    mesi,
    config_app,
    cattura_report=None,
    ordine_iniziale=None,
):
    """Riordina una stagione a coppie e ricostruisce foto e report.

    L'ordine iniziale mette in coda ripetizioni e incompatibilità. Un secondo
    passaggio locale interviene solo in presenza di riusi e li distanzia senza
    anticipare né il primo riuso né il profilo delle incompatibilità.
    """
    foto_iniziale = snapshot_blacklist(config_app)
    contatore_vicini = config_app.config_data.get(
        "studenti_vicino_fisso_contatore",
        {},
    )
    vicini_visti = {
        nome
        for nome, volte in contatore_vicini.items()
        if volte >= 1
    }

    if ordine_iniziale is None:
        ordine_c1 = riordina_stagione_per_pulizia(
            mesi,
            foto_iniziale,
            vicini_visti,
        )
        ordine_iniziale = [indice + 1 for indice, _asg, _chiave, _foto in ordine_c1]

    descrittori = descrivi_stagione(mesi, "coppie")
    ordine_finale, _temporali = riordino_temporale_protetto(
        descrittori,
        list(ordine_iniziale),
        blacklist_iniziale=foto_iniziale,
        vicini_fisso_iniziali=vicini_visti,
    )

    blacklist_cumulata = set(foto_iniziale)
    vicini_cumulati = set(vicini_visti)
    ordine_nuovo = []
    for indice in ordine_finale:
        assegnatore = mesi[indice - 1]
        chiave_nuova = chiave_pulizia(
            assegnatore,
            blacklist_cumulata,
            vicini_cumulati,
        )
        ordine_nuovo.append((indice - 1, assegnatore, chiave_nuova, set(blacklist_cumulata)))
        blacklist_cumulata |= coppie_per_blacklist(assegnatore)
        nome_vicino = getattr(assegnatore, "nome_adiacente_fisso", None)
        if nome_vicino:
            vicini_cumulati.add(nome_vicino)

    ultimo_uso_coppie = {}
    ultimo_uso_vicino = {}
    mesi_riordinati = []
    chiavi_nuove = []

    vicini_report = set(vicini_visti)
    for _indice_originale, assegnatore, chiave_nuova, foto in ordine_nuovo:
        assegnatore.riutilizzate_snapshot = conta_riutilizzate_con_foto(
            assegnatore,
            foto,
            vicini_report,
        )

        if cattura_report is not None:
            assegnatore.report_testo = cattura_report(
                assegnatore,
                ultimo_uso_coppie,
                ultimo_uso_vicino,
                foto,
                set(vicini_report),
            )

        etichetta_mese = f"mese {len(mesi_riordinati) + 1}"
        for studente_a, studente_b, _info in assegnatore.coppie_formate:
            chiave = tuple(sorted([
                studente_a.get_nome_completo(),
                studente_b.get_nome_completo(),
            ]))
            ultimo_uso_coppie[chiave] = etichetta_mese

        trio = getattr(assegnatore, "trio_identificato", None)
        if trio and len(trio) == 3:
            for studente_a, studente_b in ((trio[0], trio[1]), (trio[1], trio[2])):
                chiave = tuple(sorted([
                    studente_a.get_nome_completo(),
                    studente_b.get_nome_completo(),
                ]))
                ultimo_uso_coppie[chiave] = etichetta_mese

        gruppo = getattr(assegnatore, "gruppo_adiacente_fisso", None)
        if gruppo and len(gruppo) >= 2:
            chiave = tuple(sorted([
                gruppo[0].get_nome_completo(),
                gruppo[1].get_nome_completo(),
            ]))
            ultimo_uso_coppie[chiave] = etichetta_mese

        nome_vicino = getattr(assegnatore, "nome_adiacente_fisso", None)
        if nome_vicino:
            ultimo_uso_vicino[nome_vicino] = etichetta_mese
            vicini_report.add(nome_vicino)

        mesi_riordinati.append(assegnatore)
        chiavi_nuove.append(chiave_nuova)

    return mesi_riordinati, chiavi_nuove


def riordina_stagione_terzetti_gui(
    mesi,
    config_app,
    ordine_iniziale=None,
):
    """Riordina la stagione a terzetti con la cintura temporale."""
    foto_iniziale = snapshot_blacklist_terzetti(config_app)
    if ordine_iniziale is None:
        ordine_c1 = riordina_stagione_per_pulizia_terzetti(
            mesi,
            foto_iniziale,
        )
        ordine_iniziale = [indice + 1 for indice, _mese, _chiave in ordine_c1]

    descrittori = descrivi_stagione(mesi, "terzetti")
    ordine_finale, _temporali = riordino_temporale_protetto(
        descrittori,
        list(ordine_iniziale),
        blacklist_iniziale=foto_iniziale,
    )

    blacklist_cumulata = set(foto_iniziale)
    mesi_riordinati = []
    chiavi_riordinate = []
    for indice in ordine_finale:
        mese = mesi[indice - 1]
        mese_nuovo = dict(mese)
        mese_nuovo["adiacenze_prima"] = set(blacklist_cumulata)
        chiave = chiave_pulizia_terzetti(mese["gruppi"], blacklist_cumulata)
        mesi_riordinati.append(mese_nuovo)
        chiavi_riordinate.append(chiave)
        blacklist_cumulata |= adiacenze_per_blacklist_terzetti(mese["gruppi"])

    return mesi_riordinati, chiavi_riordinate

