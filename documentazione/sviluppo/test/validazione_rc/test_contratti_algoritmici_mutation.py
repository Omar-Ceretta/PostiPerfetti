from __future__ import annotations

from types import SimpleNamespace

import pytest

import moduli.generazione as generazione
import moduli.metrica_pulizia as metrica
import moduli.motore_terzetti as mt
import moduli.politica_annuale as politica
from moduli.strato_storico import applica_penalita_storico
from moduli.studenti import Student
from moduli.vincoli import MotoreVincoliConfigurato
from strumenti.validazione_rc.esecuzione import configurazione_vuota_rc


def _descrittore(chiave: str, *, incompatibilita: int = 0, affinita: int = 0):
    coppia = tuple(sorted((chiave, f"{chiave}_vicino")))
    return {
        "adiacenze": [{
            "chiave": ("ordinaria",) + coppia,
            "studenti": coppia,
            "incompatibilita": incompatibilita,
            "affinita": affinita,
        }],
        "blacklist": {coppia},
        "vicino_fisso": None,
    }


def test_pesi_incompatibilita_sono_contratto_1_10_1000():
    assert metrica.peso_incompatibilita({1: 1, 2: 0, 3: 0}) == 1
    assert metrica.peso_incompatibilita({1: 0, 2: 1, 3: 0}) == 10
    assert metrica.peso_incompatibilita({1: 0, 2: 0, 3: 1}) == 1000
    assert metrica.peso_incompatibilita({1: 2, 2: 3, 3: 1}) == 1032


def test_chiave_pulizia_coppie_ha_ordine_riusi_incompatibilita_affinita(monkeypatch):
    monkeypatch.setattr(metrica, "conta_incompatibilita_per_livello", lambda _a: {1: 0, 2: 1, 3: 0})
    monkeypatch.setattr(metrica, "conta_ripetizioni", lambda *_a, **_k: 2)
    monkeypatch.setattr(metrica, "conta_affinita_soddisfatte", lambda _a: 3)
    assert metrica.chiave_pulizia(object(), set()) == (2, 10, -3)


def test_chiave_pulizia_terzetti_ha_ordine_riusi_incompatibilita_affinita(monkeypatch):
    monkeypatch.setattr(metrica, "conta_incompatibilita_per_livello_terzetti", lambda _g: {1: 0, 2: 1, 3: 0})
    monkeypatch.setattr(metrica, "conta_ripetizioni_terzetti", lambda *_a: 2)
    monkeypatch.setattr(metrica, "conta_affinita_soddisfatte_terzetti", lambda _g: 3)
    assert metrica.chiave_pulizia_terzetti([], set()) == (2, 10, -3)


def test_ordine_annuale_mette_prima_zero_riusi_anche_se_ha_incompatibilita():
    gia_vista = tuple(sorted(("riuso", "riuso_vicino")))
    descrittori = [
        _descrittore("riuso"),
        _descrittore("delicato", incompatibilita=1),
    ]
    ordine, _ = politica.riordina_greedy(
        descrittori,
        politica=politica.POLITICA_PROTETTA,
        blacklist_iniziale={gia_vista},
    )
    assert ordine == [2, 1]


def test_riordino_temporale_senza_riusi_esce_subito(monkeypatch):
    originale = politica.metriche_temporali
    chiamate = []

    def conta(*args, **kwargs):
        chiamate.append(1)
        return originale(*args, **kwargs)

    monkeypatch.setattr(politica, "metriche_temporali", conta)
    descrittori = [_descrittore("A"), _descrittore("B"), _descrittore("C")]
    ordine, temporali = politica.riordino_temporale_protetto(descrittori, [1, 2, 3])
    assert ordine == [1, 2, 3]
    assert temporali["mesi_con_riuso"] == 0
    assert len(chiamate) == 1


def test_penalita_storico_e_esattamente_500_per_utilizzo():
    a = Student("Alfa", "Uno", "M")
    b = Student("Beta", "Due", "F")
    motore = MotoreVincoliConfigurato()
    base = motore.calcola_punteggio_coppia(a, b)["punteggio_totale"]
    config = configurazione_vuota_rc()
    config.config_data["coppie_da_evitare"] = [{
        "tipo": "coppia",
        "studenti": [a.get_nome_completo(), b.get_nome_completo()],
        "volte_usata": 2,
    }]
    applica_penalita_storico(motore, config)
    dopo = motore.calcola_punteggio_coppia(a, b)
    assert dopo["punteggio_totale"] == base - 1000
    assert any("-1000" in nota for nota in dopo["note"])


def test_best_of_n_coppie_si_ferma_se_t3_ha_gia_soluzione(monkeypatch):
    config = configurazione_vuota_rc()
    chiamate = []

    class Finto:
        def __init__(self):
            self.motore_vincoli = SimpleNamespace(tentativo_corrente=3)
            self.seed_candidato = 123

    def genera(*args, **kwargs):
        chiamate.append(kwargs["indice_candidato"])
        if len(chiamate) > 1:
            pytest.fail("Dopo un successo T3 il best-of-N non deve generare altri candidati.")
        return True, Finto()

    monkeypatch.setattr(generazione, "genera_candidato_mese", genera)
    monkeypatch.setattr(metrica, "chiave_pulizia", lambda *_a, **_k: (0, 0, 0))
    monkeypatch.setattr(metrica, "estrai_adiacenze", lambda _a: [])

    migliore, _ultimo = generazione.calcola_miglior_mese(
        [], object(), config, "centro", False, None, set(),
        num_candidati=4, seed_principale=1,
    )
    assert migliore is not None
    assert chiamate == [1]


def test_best_of_n_coppie_dopo_t4_parte_direttamente_da_t4(monkeypatch):
    config = configurazione_vuota_rc()
    partenze = []

    class Finto:
        def __init__(self, indice):
            self.motore_vincoli = SimpleNamespace(tentativo_corrente=4)
            self.seed_candidato = indice

    def genera(*args, **kwargs):
        partenze.append(kwargs["tentativo_iniziale"])
        indice = kwargs["indice_candidato"]
        return True, Finto(indice)

    monkeypatch.setattr(generazione, "genera_candidato_mese", genera)
    monkeypatch.setattr(metrica, "chiave_pulizia", lambda a, *_args, **_k: (0, 0, -a.seed_candidato))
    monkeypatch.setattr(metrica, "estrai_adiacenze", lambda _a: [])

    generazione.calcola_miglior_mese(
        [], object(), config, "centro", False, None, set(),
        num_candidati=3, seed_principale=1,
    )
    assert partenze == [1, 4, 4]


def test_best_of_n_terzetti_si_ferma_se_t3_ha_gia_soluzione(monkeypatch):
    studenti = [Student(f"S{i:02d}", "Alunno", "M" if i % 2 else "F") for i in range(12)]
    chiamate = []
    soluzione = [metrica.Gruppo(metrica.TIPO_TERZETTO, studenti[i:i+3]) for i in range(0, 12, 3)]

    def partiziona(motore, *_args, **_kwargs):
        chiamate.append(1)
        motore.tentativo_corrente = 3
        return soluzione

    monkeypatch.setattr(mt, "partiziona_in_gruppi", partiziona)
    monkeypatch.setattr(mt, "chiave_pulizia_terzetti", lambda *_a, **_k: (0, 0, 0))
    gruppi = mt.calcola_miglior_mese_terzetti(
        studenti, False, config_app=configurazione_vuota_rc(),
        num_candidati=4, seed_base=1,
    )
    assert gruppi == soluzione
    assert len(chiamate) == 1


def test_guardie_s1_proteggono_tutte_le_incompatibilita_e_affinita():
    base_m = {
        "riusi": 1, "incompatibilita_l1": 1, "incompatibilita_l2": 1,
        "incompatibilita_l3": 0, "affinita_l1": 1, "affinita_l2": 1,
        "affinita_l3": 1, "affinita_totali": 3, "affinita_pesate": 6,
        "massimo_individuale": 1, "studenti_con_riuso": 2,
    }
    base_t = {
        "primo_mese_riuso": 5, "mesi_con_riuso": 1, "massimo_riusi_mese": 1,
        "gap_1": 0, "gap_le_2": 0, "gap_le_3": 0, "gap_medio": 4.0,
    }
    for campo in ("incompatibilita_l1", "incompatibilita_l2", "incompatibilita_l3"):
        candidata = dict(base_m)
        candidata[campo] += 1
        assert not politica.ammissibile_s1(candidata, base_t, base_m, base_t), campo
    candidata = dict(base_m)
    candidata["affinita_pesate"] -= 1
    assert not politica.ammissibile_s1(candidata, base_t, base_m, base_t)
    candidata = dict(base_m)
    candidata["affinita_l3"] -= 1
    assert not politica.ammissibile_s1(candidata, base_t, base_m, base_t)


def test_wrapper_penalita_storico_e_idempotente():
    a = Student("Alfa", "Uno", "M")
    b = Student("Beta", "Due", "F")
    motore = MotoreVincoliConfigurato()
    base = motore.calcola_punteggio_coppia(a, b)["punteggio_totale"]
    config = configurazione_vuota_rc()
    config.config_data["coppie_da_evitare"] = [{
        "tipo": "coppia",
        "studenti": [a.get_nome_completo(), b.get_nome_completo()],
        "volte_usata": 1,
    }]
    applica_penalita_storico(motore, config)
    applica_penalita_storico(motore, config)
    assert motore.calcola_punteggio_coppia(a, b)["punteggio_totale"] == base - 500


def test_livello3_resta_veto_assoluto_in_entrambe_le_direzioni():
    a = Student("Alfa", "Uno", "M")
    b = Student("Beta", "Due", "F")
    motore = MotoreVincoliConfigurato()
    a.aggiungi_incompatibilita(b.get_nome_completo(), 3)
    assert motore._ha_incompatibilita_assoluta(a, b)
    a.incompatibilita.clear()
    b.aggiungi_incompatibilita(a.get_nome_completo(), 3)
    assert motore._ha_incompatibilita_assoluta(a, b)


def test_blacklist_terzetti_incrementa_lo_stesso_arco_senza_duplicarlo():
    from moduli.strato_storico import aggiorna_blacklist_terzetti

    config = configurazione_vuota_rc()
    aggiorna_blacklist_terzetti(config, [("Alfa Uno", "Beta Due")])
    aggiorna_blacklist_terzetti(config, [("Beta Due", "Alfa Uno")])
    lista = config.config_data["adiacenze_terzetti_da_evitare"]
    assert len(lista) == 1
    assert lista[0]["studenti"] == ["Alfa Uno", "Beta Due"]
    assert lista[0]["volte_usata"] == 2


def test_ordinamento_canonico_studenti_ignora_i_diacritici():
    from moduli.studenti import chiave_ordinamento_studente

    studenti = [
        Student("Dante", "Uno", "M"),
        Student("Čechov", "Anton", "M"),
        Student("Calvino", "Italo", "M"),
    ]
    ordinati = sorted(studenti, key=chiave_ordinamento_studente)
    assert [s.cognome for s in ordinati] == ["Calvino", "Čechov", "Dante"]
