from __future__ import annotations

import copy

import pytest

from strumenti.cantiere_semantico.esecuzione_c1 import (
    ErroreEsecuzioneC1,
    esegui_c1_coppie,
    esegui_c1_terzetti,
)
from strumenti.cantiere_semantico.modelli import Modalita, StatoRun
from .supporto_i3 import (
    configurazione_produttiva_vuota,
    crea_run,
    firma_coppie,
    firma_terzetti,
    studenti_semplici,
)


def _baseline_coppie(config, run, studenti, aula):
    from moduli.annuale import (
        genera_migliore_stagione,
        genera_una_stagione_gui,
        riordina_e_cattura_stagione_coppie,
    )

    def stagione(indice, t0, budget, stop):
        return genera_una_stagione_gui(
            studenti,
            aula,
            config,
            run.parametri_aula.modalita_trio,
            run.genere_misto_attivo,
            None,
            run.numero_mesi,
            run.parametri_ricerca.numero_candidati,
            t0_globale=t0,
            budget_secondi=budget,
            deve_fermarsi=stop,
            seed_principale=run.seed_principale,
            indice_stagione=indice,
        )

    mesi, chiavi, info = genera_migliore_stagione(
        stagione,
        run.numero_mesi,
        tetto=run.parametri_ricerca.tetto_stagioni,
        k_convergenza=run.parametri_ricerca.convergenza,
        numero_stagioni_fisso=run.parametri_ricerca.numero_stagioni_fisso,
    )
    info["seed_principale"] = run.seed_principale
    info["modalita"] = "coppie"
    for assegnatore in mesi:
        assegnatore.contesto_casuale.update({
            "stagioni_generate": info.get("n_stagioni"),
            "stagione_vincente": info.get("indice_stagione_migliore"),
        })
    mesi, chiavi = riordina_e_cattura_stagione_coppie(mesi, config)
    info["tot_ripetizioni"] = sum(
        assegnatore.riutilizzate_snapshot["totali"]
        for assegnatore in mesi
    )
    return mesi, tuple(chiavi), info


def _baseline_terzetti(config, run, studenti):
    from moduli.annuale import (
        genera_migliore_stagione,
        genera_una_stagione_terzetti_gui,
        riordina_stagione_terzetti_gui,
    )

    extra = run.parametri_aula.extra

    def stagione(indice, t0, budget, stop):
        return genera_una_stagione_terzetti_gui(
            studenti,
            config,
            run.genere_misto_attivo,
            run.parametri_aula.preferenza_resto2,
            extra["resto_in_prima_fila"],
            run.numero_mesi,
            max_terzetti_prima_fila=extra["max_terzetti_prima_fila"],
            max_resti_prima_fila=extra["max_resti_prima_fila"],
            num_candidati=run.parametri_ricerca.numero_candidati,
            t0_globale=t0,
            budget_secondi=budget,
            deve_fermarsi=stop,
            seed_principale=run.seed_principale,
            indice_stagione=indice,
        )

    mesi, chiavi, info = genera_migliore_stagione(
        stagione,
        run.numero_mesi,
        tetto=run.parametri_ricerca.tetto_stagioni,
        k_convergenza=run.parametri_ricerca.convergenza,
        numero_stagioni_fisso=run.parametri_ricerca.numero_stagioni_fisso,
    )
    info["seed_principale"] = run.seed_principale
    info["modalita"] = "terzetti"
    for mese in mesi:
        metadati = mese.get("metadati_casualita") or {}
        contesto = metadati.setdefault("contesto", {})
        contesto.update({
            "stagioni_generate": info.get("n_stagioni"),
            "stagione_vincente": info.get("indice_stagione_migliore"),
        })
        mese["metadati_casualita"] = metadati
    mesi, chiavi = riordina_stagione_terzetti_gui(mesi, config)
    return mesi, tuple(chiavi), info


def test_runner_coppie_pari_al_flusso_produttivo(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA", raising=False)
    monkeypatch.delenv("POSTIPERFETTI_STAGIONI", raising=False)
    monkeypatch.delenv("POSTIPERFETTI_SEED", raising=False)

    from moduli.aula import ConfigurazioneAula

    config_runner = configurazione_produttiva_vuota()
    config_baseline = configurazione_produttiva_vuota()
    run, ambiente = crea_run(config_runner, modalita=Modalita.COPPIE)
    studenti_runner = studenti_semplici(8)
    studenti_baseline = studenti_semplici(8)
    aula_runner = ConfigurazioneAula("I3 runner")
    aula_runner.crea_layout_standard(8, 2, 4, None, ha_fisso=False)
    aula_baseline = copy.deepcopy(aula_runner)

    esito = esegui_c1_coppie(
        ambiente,
        studenti_runner,
        aula_runner,
    )
    mesi_prod, chiavi_prod, info_prod = _baseline_coppie(
        config_baseline,
        run,
        studenti_baseline,
        aula_baseline,
    )

    assert esito.stato == StatoRun.COMPLETO
    assert firma_coppie(esito.mesi_finali) == firma_coppie(mesi_prod)
    assert esito.chiavi_finali == chiavi_prod
    for chiave in (
        "n_stagioni",
        "n_stagioni_complete",
        "punteggio",
        "tot_ripetizioni",
        "motivo_stop",
        "mesi_completi",
        "indice_stagione_migliore",
        "numero_stagioni_fisso",
        "seed_principale",
        "modalita",
    ):
        assert esito.info[chiave] == info_prod[chiave]
    assert sorted(t.posizione_generazione for t in esito.traccia_riordino) == [1, 2]
    assert [t.posizione_finale for t in esito.traccia_riordino] == [1, 2]


def test_runner_terzetti_pari_al_flusso_produttivo(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA", raising=False)
    monkeypatch.delenv("POSTIPERFETTI_STAGIONI", raising=False)
    monkeypatch.delenv("POSTIPERFETTI_SEED", raising=False)

    config_runner = configurazione_produttiva_vuota()
    config_baseline = configurazione_produttiva_vuota()
    run, ambiente = crea_run(config_runner, modalita=Modalita.TERZETTI)
    studenti_runner = studenti_semplici(6)
    studenti_baseline = studenti_semplici(6)

    esito = esegui_c1_terzetti(ambiente, studenti_runner)
    mesi_prod, chiavi_prod, info_prod = _baseline_terzetti(
        config_baseline,
        run,
        studenti_baseline,
    )

    assert esito.stato == StatoRun.COMPLETO
    assert firma_terzetti(esito.mesi_finali) == firma_terzetti(mesi_prod)
    assert esito.chiavi_finali == chiavi_prod
    for chiave in (
        "n_stagioni",
        "n_stagioni_complete",
        "punteggio",
        "tot_ripetizioni",
        "motivo_stop",
        "mesi_completi",
        "indice_stagione_migliore",
        "numero_stagioni_fisso",
        "seed_principale",
        "modalita",
    ):
        assert esito.info[chiave] == info_prod[chiave]
    assert sorted(t.posizione_generazione for t in esito.traccia_riordino) == [1, 2]


def test_runner_rifiuta_override_non_c1(monkeypatch):
    monkeypatch.setenv("POSTIPERFETTI_STRATEGIA_RICERCA", "A")
    from moduli.aula import ConfigurazioneAula

    config = configurazione_produttiva_vuota()
    _run, ambiente = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=1,
        numero_candidati=1,
        numero_stagioni=1,
    )
    aula = ConfigurazioneAula("override")
    aula.crea_layout_standard(4, 1, 4, None, ha_fisso=False)
    with pytest.raises(ErroreEsecuzioneC1, match="soltanto C1"):
        esegui_c1_coppie(ambiente, studenti_semplici(4), aula)


def test_runner_non_modifica_configurazione_isolata(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA", raising=False)
    from strumenti.cantiere_semantico.serializzazione import firma_json_sha256
    from moduli.aula import ConfigurazioneAula

    config = configurazione_produttiva_vuota()
    _run, ambiente = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=1,
        numero_candidati=1,
        numero_stagioni=1,
    )
    firma_prima = firma_json_sha256(ambiente.config_app.config_data)
    aula = ConfigurazioneAula("immutabile")
    aula.crea_layout_standard(4, 1, 4, None, ha_fisso=False)
    esegui_c1_coppie(ambiente, studenti_semplici(4), aula)
    assert firma_json_sha256(ambiente.config_app.config_data) == firma_prima
