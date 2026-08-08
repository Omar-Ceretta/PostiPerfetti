import copy
import json
from types import SimpleNamespace

import pytest

from moduli.aula import ConfigurazioneAula
from moduli.configurazione import ConfigurazioneApp
from moduli.risultati_annuali import (
    ErroreSalvataggioAnnata,
    _salva_batch_atomico,
)


class StudenteFinto:
    def __init__(self, cognome, nome):
        self.cognome = cognome
        self.nome = nome

    def get_nome_completo(self):
        return f"{self.cognome} {self.nome}"


def _configurazione_con_coppia(progressivo=1, posti_per_fila=6):
    config = object.__new__(ConfigurazioneApp)
    config.config_data = ConfigurazioneApp._carica_configurazione_default(config)

    anna = StudenteFinto("Alfa", "Anna")
    bruno = StudenteFinto("Beta", "Bruno")
    aula = ConfigurazioneAula("Test Storico")
    aula.crea_layout_standard(2, num_file=1, posti_per_fila=posti_per_fila)
    banchi = [
        posto
        for riga in aula.griglia
        for posto in riga
        if posto.tipo == "banco"
    ]
    banchi[0].occupato_da = "Alfa_Anna"
    banchi[1].occupato_da = "Beta_Bruno"

    config.aggiungi_assegnazione_storico(
        "2A - Mensile Coppie - 01",
        [(anna, bruno, {"punteggio_totale": 0})],
        configurazione_aula=aula,
        file_origine="/classi/2A.txt",
        nome_classe="2A",
        generazione="mensile",
        data_creazione="06/08/2026 17:00",
        progressivo=progressivo,
        abbinamenti="1 coppia",
        salva_subito=False,
    )
    return config


def _scrivi_json(tmp_path, dati):
    percorso = tmp_path / "config.json"
    percorso.write_text(json.dumps(dati), encoding="utf-8")
    return percorso


def test_formato_corrente_rifiuta_progressivo_duplicato(tmp_path):
    config = _configurazione_con_coppia()
    duplicata = copy.deepcopy(config.config_data["storico_assegnazioni"][0])
    config.config_data["storico_assegnazioni"].append(duplicata)

    convalida = object.__new__(ConfigurazioneApp)
    with pytest.raises(ValueError, match="duplica il progressivo"):
        convalida._leggi_json_validato(_scrivi_json(tmp_path, config.config_data))


def test_formato_corrente_rifiuta_coppia_non_reciproca(tmp_path):
    config = _configurazione_con_coppia()
    layout = config.config_data["storico_assegnazioni"][0]["layout"]
    layout[1]["compagno"] = "Studente Inesistente"

    convalida = object.__new__(ConfigurazioneApp)
    with pytest.raises(ValueError, match="coppia non reciproca"):
        convalida._leggi_json_validato(_scrivi_json(tmp_path, config.config_data))


def test_nuova_voce_richiede_file_origine_e_progressivo_unico():
    config = _configurazione_con_coppia()
    with pytest.raises(ValueError, match="file_origine"):
        ConfigurazioneApp._valida_metadati_nuova_assegnazione(
            config.config_data["storico_assegnazioni"],
            nome_assegnazione="Nuova",
            nome_classe="2A",
            file_origine="",
            generazione="mensile",
            modo="coppie",
            data_creazione="06/08/2026 17:01",
            progressivo=2,
            abbinamenti="1 coppia",
        )

    with pytest.raises(ValueError, match="già presente"):
        ConfigurazioneApp._valida_metadati_nuova_assegnazione(
            config.config_data["storico_assegnazioni"],
            nome_assegnazione="Duplicata",
            nome_classe="2A",
            file_origine="/classi/2A.txt",
            generazione="mensile",
            modo="coppie",
            data_creazione="06/08/2026 17:01",
            progressivo=1,
            abbinamenti="1 coppia",
        )


def test_ricostruzione_rotazioni_riproduce_lo_storico():
    config = _configurazione_con_coppia(progressivo=1)
    prima_voce = copy.deepcopy(config.config_data["storico_assegnazioni"][0])
    seconda_voce = copy.deepcopy(prima_voce)
    seconda_voce["progressivo"] = 2
    seconda_voce["nome"] = "2A - Mensile Coppie - 02"
    config.config_data["storico_assegnazioni"].append(seconda_voce)

    config.config_data["coppie_da_evitare"] = []
    config.config_data["studenti_trio_contatore"] = {}
    config.config_data["studenti_vicino_fisso_contatore"] = {}
    config._ricostruisci_blacklist_da_storico()

    assert config.config_data["coppie_da_evitare"] == [
        {
            "tipo": "coppia",
            "studenti": ["Alfa Anna", "Beta Bruno"],
            "volte_usata": 2,
        }
    ]


def test_batch_annuale_ripristina_tutto_se_la_scrittura_finale_fallisce():
    config = SimpleNamespace(
        config_data={"storico_assegnazioni": []},
        ultimo_esito_salvataggio="errore",
        salva_configurazione=lambda: False,
    )

    def muta():
        config.config_data["storico_assegnazioni"].append({"nome": "Mese 1"})

    with pytest.raises(ErroreSalvataggioAnnata):
        _salva_batch_atomico(config, muta)

    assert config.config_data == {"storico_assegnazioni": []}




def test_layout_corrente_a_quattro_posti_si_ricostruisce_senza_fallback():
    config = _configurazione_con_coppia(posti_per_fila=4)
    aula, assegnazione = config.ricostruisci_layout_da_storico(0)

    assert assegnazione["configurazione_aula"]["posti_per_fila"] == 4
    assert aula is not None
    assert sum(
        posto.tipo == "banco"
        for riga in aula.griglia
        for posto in riga
    ) == 2
