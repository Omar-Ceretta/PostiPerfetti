from __future__ import annotations

import pytest

configurazione = pytest.importorskip("moduli.configurazione")

from strumenti.cantiere_semantico.ambiente import prepara_ambienti_appaiati
from strumenti.cantiere_semantico.modelli import (
    CondizioneRun,
    Modalita,
    ParametriAula,
    ParametriRicerca,
    SpecificaRun,
)
from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni, crea_stato_iniziale_id


def _configurazione_reale_senza_accesso_al_disco():
    classe = configurazione.ConfigurazioneApp
    oggetto = classe.__new__(classe)
    oggetto.config_data = {
        "storico_assegnazioni": [],
        "coppie_da_evitare": [
            {"tipo": "coppia", "studenti": ["A Uno", "B Due"], "volte_usata": 2}
        ],
        "adiacenze_terzetti_da_evitare": [],
        "studenti_trio_contatore": {},
        "studenti_vicino_fisso_contatore": {"C Tre": 1},
        "tema": "scuro",
    }
    oggetto.avviso_recupero = None
    oggetto.gestore_file_assente = lambda *_: None
    oggetto.gestore_azzeramento_completato = lambda *_: None
    oggetto.ultimo_esito_salvataggio = None
    oggetto.file_config = "non_usato.json"
    oggetto.file_backup = "non_usato.backup.json"
    oggetto._file_config_presente_nella_sessione = False
    return oggetto


def _run(condizione: CondizioneRun, stato_id: str) -> SpecificaRun:
    return SpecificaRun(
        run_id=f"run_smoke_{condizione.value}",
        pair_id="pair_smoke",
        file_classe=f"{condizione.value}.txt",
        condizione=condizione,
        modalita=Modalita.COPPIE,
        seed_principale=1,
        numero_mesi=2,
        genere_misto_attivo=False,
        stato_iniziale_id=stato_id,
        parametri_ricerca=ParametriRicerca(
            numero_candidati=2,
            numero_stagioni_fisso=1,
        ),
        parametri_aula=ParametriAula(2, 4),
    )


def test_copia_temporanea_produttiva_e_realmente_isolata():
    sorgente = _configurazione_reale_senza_accesso_al_disco()
    stato_id = crea_stato_iniziale_id(crea_snapshot_rotazioni(sorgente.config_data))
    ambienti = prepara_ambienti_appaiati(
        sorgente,
        _run(CondizioneRun.SENZA_FISSO, stato_id),
        _run(CondizioneRun.CON_FISSO, stato_id),
    )
    ambienti.senza_fisso.config_app.config_data["coppie_da_evitare"][0]["volte_usata"] = 99
    assert sorgente.config_data["coppie_da_evitare"][0]["volte_usata"] == 2
    assert ambienti.con_fisso.config_app.config_data["coppie_da_evitare"][0]["volte_usata"] == 2
