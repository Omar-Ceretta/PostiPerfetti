from __future__ import annotations

import copy

import pytest

from strumenti.cantiere_semantico.ambiente import (
    ErroreAmbienteIsolato,
    ErroreClassiAppaiate,
    prepara_ambienti_appaiati,
    valida_dati_classi_appaiate,
)
from strumenti.cantiere_semantico.modelli import (
    CondizioneRun,
    Modalita,
    ParametriAula,
    ParametriRicerca,
    SpecificaCoppiaCorpus,
    SpecificaRun,
)
from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni, crea_stato_iniziale_id


def _config_data() -> dict:
    return {
        "storico_assegnazioni": [],
        "coppie_da_evitare": [
            {"tipo": "coppia", "studenti": ["A Uno", "B Due"], "volte_usata": 1}
        ],
        "adiacenze_terzetti_da_evitare": [],
        "studenti_trio_contatore": {},
        "studenti_vicino_fisso_contatore": {"C Tre": 1},
        "tema": "scuro",
    }


class ConfigFinta:
    def __init__(self, dati: dict):
        self.config_data = dati
        self.gestore_file_assente = object()
        self.gestore_azzeramento_completato = object()

    def copia_temporanea(self):
        nuova = copy.copy(self)
        nuova.config_data = copy.deepcopy(self.config_data)
        nuova.gestore_file_assente = None
        nuova.gestore_azzeramento_completato = None
        return nuova


class ConfigCopiaDifettosa(ConfigFinta):
    def copia_temporanea(self):
        nuova = copy.copy(self)
        nuova.config_data = self.config_data
        nuova.gestore_file_assente = None
        nuova.gestore_azzeramento_completato = None
        return nuova


def _run(condizione: CondizioneRun, stato_id: str, *, seed: int = 7) -> SpecificaRun:
    return SpecificaRun(
        run_id=f"run_{condizione.value}",
        pair_id="pair_x",
        file_classe=f"{condizione.value}.txt",
        condizione=condizione,
        modalita=Modalita.COPPIE,
        seed_principale=seed,
        numero_mesi=10,
        genere_misto_attivo=False,
        stato_iniziale_id=stato_id,
        parametri_ricerca=ParametriRicerca(
            numero_candidati=10,
            numero_stagioni_fisso=5,
        ),
        parametri_aula=ParametriAula(4, 6),
    )


def test_ambienti_appaiati_sono_indipendenti_e_non_mutano_la_sorgente():
    sorgente = ConfigFinta(_config_data())
    stato_id = crea_stato_iniziale_id(crea_snapshot_rotazioni(sorgente.config_data))
    ambienti = prepara_ambienti_appaiati(
        sorgente,
        _run(CondizioneRun.SENZA_FISSO, stato_id),
        _run(CondizioneRun.CON_FISSO, stato_id),
    )
    ambienti.senza_fisso.config_app.config_data["coppie_da_evitare"][0]["volte_usata"] = 9
    assert sorgente.config_data["coppie_da_evitare"][0]["volte_usata"] == 1
    assert ambienti.con_fisso.config_app.config_data["coppie_da_evitare"][0]["volte_usata"] == 1
    assert ambienti.stato_iniziale_id == stato_id


def test_ambiente_rifiuta_stato_dichiarato_diverso():
    sorgente = ConfigFinta(_config_data())
    with pytest.raises(ErroreAmbienteIsolato, match="snapshot effettivo"):
        prepara_ambienti_appaiati(
            sorgente,
            _run(CondizioneRun.SENZA_FISSO, "stato_errato"),
            _run(CondizioneRun.CON_FISSO, "stato_errato"),
        )


def test_ambiente_rifiuta_copia_che_condivide_config_data():
    sorgente = ConfigCopiaDifettosa(_config_data())
    stato_id = crea_stato_iniziale_id(crea_snapshot_rotazioni(sorgente.config_data))
    with pytest.raises(ErroreAmbienteIsolato, match="contenitori mutabili condivisi"):
        prepara_ambienti_appaiati(
            sorgente,
            _run(CondizioneRun.SENZA_FISSO, stato_id),
            _run(CondizioneRun.CON_FISSO, stato_id),
        )


def test_ambiente_rifiuta_parametri_non_appaiati():
    sorgente = ConfigFinta(_config_data())
    stato_id = crea_stato_iniziale_id(crea_snapshot_rotazioni(sorgente.config_data))
    with pytest.raises(ErroreAmbienteIsolato, match="parametri obbligatori"):
        prepara_ambienti_appaiati(
            sorgente,
            _run(CondizioneRun.SENZA_FISSO, stato_id, seed=7),
            _run(CondizioneRun.CON_FISSO, stato_id, seed=8),
        )


def _studente(nome: str, posizione: str = "NORMALE") -> dict:
    cognome, proprio = nome.split(" ", 1)
    return {
        "cognome": cognome,
        "nome": proprio,
        "sesso": "M",
        "posizione": posizione,
        "incompatibilita": {},
        "affinita": {},
    }


def _specifica() -> SpecificaCoppiaCorpus:
    return SpecificaCoppiaCorpus(
        pair_id="pair_x",
        classe="Classe X",
        file_senza_fisso="senza.txt",
        file_con_fisso="con.txt",
        studente_fisso="Riva Stefano",
        posizione_base="NORMALE",
        numero_studenti=2,
    )


def test_classi_appaiate_accettano_solo_la_promozione_a_fisso():
    senza = {"studenti": [_studente("Riva Stefano"), _studente("Bianchi Luca")]}
    con = copy.deepcopy(senza)
    con["studenti"][0]["posizione"] = "FISSO"
    esito = valida_dati_classi_appaiate(_specifica(), senza, con)
    assert esito.studente_fisso == "Riva Stefano"
    assert esito.numero_studenti == 2


def test_classi_appaiate_rifiutano_un_vincolo_modificato():
    senza = {"studenti": [_studente("Riva Stefano"), _studente("Bianchi Luca")]}
    con = copy.deepcopy(senza)
    con["studenti"][0]["posizione"] = "FISSO"
    con["studenti"][1]["affinita"] = {"Riva Stefano": 2}
    with pytest.raises(ErroreClassiAppaiate, match="affinita"):
        valida_dati_classi_appaiate(_specifica(), senza, con)
