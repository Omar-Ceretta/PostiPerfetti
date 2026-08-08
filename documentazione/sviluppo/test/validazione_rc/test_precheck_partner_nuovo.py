# -*- coding: utf-8 -*-

from __future__ import annotations

from moduli.diagnostica_ricerca import DiagnosticaRicerca
from moduli.generazione import calcola_miglior_mese
from moduli.metrica_pulizia import snapshot_blacklist
from strumenti.validazione_rc.annuale_rc import _aula_coppie
from strumenti.validazione_rc.esecuzione import configurazione_vuota_rc, _studenti_produttivi
from strumenti.validazione_rc.generatori import genera_classe_sintetica
from strumenti.validazione_rc.risultati import verifica_aula_rc


def test_studente_senza_partner_nuovo_salva_t1_t3_e_passa_subito_al_t4():
    classe = genera_classe_sintetica(
        19, seed=2026080651, famiglia="vuota", con_fisso=False
    )
    studenti, fisso = _studenti_produttivi(classe)
    isolato = studenti[0].get_nome_completo()
    config = configurazione_vuota_rc()
    config.config_data["coppie_da_evitare"] = [
        {
            "tipo": "coppia",
            "studenti": sorted((isolato, studente.get_nome_completo())),
            "volte_usata": 1,
        }
        for studente in studenti[1:]
    ]
    aula = _aula_coppie(classe, posti_per_fila=6, posizione_trio="centro")
    diagnostica = DiagnosticaRicerca(etichetta="rc-partner-nuovo")

    migliore, _ultimo = calcola_miglior_mese(
        studenti,
        aula,
        config,
        "centro",
        False,
        fisso,
        snapshot_blacklist(config),
        1,
        seed_principale=2026080652,
        contesto_casuale={"operazione": "regressione_partner_nuovo", "mese": 1},
        diagnostica=diagnostica,
    )
    assert migliore is not None
    assert verifica_aula_rc(
        classe,
        migliore.configurazione_aula,
        modalita="coppie",
        posizione_trio="centro",
    ).valido

    eventi = diagnostica.esporta()["eventi"]
    iniziati = [
        int(evento["dati"]["tentativo"])
        for evento in eventi
        if evento["tipo"] == "tentativo_inizio"
    ]
    precheck = [
        evento for evento in eventi
        if evento["tipo"] == "tentativo_impossibile_precheck"
    ]
    assert iniziati == [1, 4]
    assert precheck
    assert precheck[0]["dati"]["causa"] == "studente_senza_partner_nuovo"
