from __future__ import annotations

from moduli.annuale import genera_migliore_stagione
from moduli import motore_terzetti as mt
from moduli.metrica_pulizia import Gruppo, TIPO_TERZETTO
from moduli.politica_annuale import (
    POLITICA_BASELINE,
    POLITICA_PROTETTA,
    ammissibile_s1,
    chiave_r12,
    metriche_temporali,
    riordina_greedy,
    riordino_temporale_protetto,
    seleziona_s1,
)


def _metriche(**cambiamenti):
    base = {
        "riusi": 1,
        "incompatibilita_l1": 2,
        "incompatibilita_l2": 2,
        "incompatibilita_l3": 0,
        "affinita_l1": 2,
        "affinita_l2": 1,
        "affinita_l3": 1,
        "affinita_totali": 4,
        "affinita_pesate": 7,
        "massimo_individuale": 1,
        "studenti_con_riuso": 2,
    }
    base.update(cambiamenti)
    return base


def _temporali(**cambiamenti):
    base = {
        "primo_mese_riuso": 8,
        "mesi_con_riuso": 1,
        "massimo_riusi_mese": 1,
        "gap_1": 0,
        "gap_le_2": 0,
        "gap_le_3": 0,
        "gap_medio": 7.0,
    }
    base.update(cambiamenti)
    return base


def _candidato(indice, metriche, temporali, ordine=None):
    return {
        "indice": indice,
        "ordine": ordine or list(range(1, 11)),
        "metriche": metriche,
        "temporali": temporali,
        "chiave_r12": chiave_r12(metriche),
    }


def test_s1_accetta_un_riuso_solo_con_beneficio_sociale_protetto():
    baseline = _candidato(1, _metriche(), _temporali())
    alternativa = _candidato(
        2,
        _metriche(
            riusi=2,
            incompatibilita_l1=1,
            incompatibilita_l2=0,
            affinita_l1=3,
            affinita_totali=5,
            affinita_pesate=8,
        ),
        _temporali(primo_mese_riuso=9),
    )

    scelta = seleziona_s1([baseline, alternativa], baseline)

    assert scelta["indice"] == 2
    assert scelta["politica"] == POLITICA_PROTETTA


def test_s1_mantiene_c1_se_una_dimensione_protetta_peggiora():
    baseline = _candidato(1, _metriche(), _temporali())
    alternativa = _candidato(
        2,
        _metriche(
            riusi=0,
            incompatibilita_l1=3,  # Peggioramento vietato.
            incompatibilita_l2=0,
            affinita_l1=5,
            affinita_totali=7,
            affinita_pesate=10,
        ),
        _temporali(),
    )

    assert not ammissibile_s1(
        alternativa["metriche"],
        alternativa["temporali"],
        baseline["metriche"],
        baseline["temporali"],
    )
    scelta = seleziona_s1([alternativa], baseline)
    assert scelta["indice"] == 1
    assert scelta["politica"] == POLITICA_BASELINE


def _mese(chiave: str, *, incompatibilita=0, affinita=0):
    coppia = tuple(sorted((chiave, f"{chiave}_vicino")))
    return {
        "adiacenze": [
            {
                "chiave": ("ordinaria",) + coppia,
                "studenti": coppia,
                "incompatibilita": incompatibilita,
                "affinita": affinita,
            }
        ],
        "blacklist": {coppia},
        "vicino_fisso": None,
    }


def test_ordine_protetto_non_compensa_un_incompatibilita_con_le_affinita():
    descrittori = [
        _mese("pulito"),
        _mese("delicato", incompatibilita=1, affinita=3),
    ]

    ordine, _metriche_finali = riordina_greedy(
        descrittori,
        politica=POLITICA_PROTETTA,
    )

    assert ordine == [1, 2]


def test_riordino_temporale_senza_riusi_non_modifica_l_ordine():
    descrittori = [
        _mese("A"),
        _mese("B"),
        _mese("C", incompatibilita=1),
    ]
    ordine_iniziale = [1, 2, 3]

    ordine, dopo = riordino_temporale_protetto(
        descrittori,
        ordine_iniziale,
    )

    assert ordine == ordine_iniziale
    assert dopo["mesi_con_riuso"] == 0


def test_riordino_temporale_non_anticipa_un_mese_incompatibile():
    descrittori = [
        _mese("A"),
        _mese("A"),
        _mese("B"),
        _mese("C"),
        _mese("D", incompatibilita=1),
    ]
    ordine_iniziale = [1, 2, 3, 4, 5]

    ordine, dopo = riordino_temporale_protetto(
        descrittori,
        ordine_iniziale,
    )

    assert ordine != ordine_iniziale
    assert ordine[-1] == 5
    assert dopo["gap_1"] == 0
    assert dopo["gap_le_2"] == 0


def test_riordino_temporale_allontana_la_ripetizione_senza_anticiparla():
    descrittori = [_mese("A"), _mese("A"), _mese("B"), _mese("C"), _mese("D")]
    ordine_iniziale = [1, 2, 3, 4, 5]
    prima = metriche_temporali(descrittori, ordine_iniziale)

    ordine, dopo = riordino_temporale_protetto(descrittori, ordine_iniziale)

    assert ordine != ordine_iniziale
    assert prima["primo_mese_riuso"] == 2
    assert dopo["primo_mese_riuso"] >= prima["primo_mese_riuso"]
    assert dopo["gap_1"] == 0
    assert dopo["gap_le_3"] == 0
    assert dopo["massimo_riusi_mese"] <= prima["massimo_riusi_mese"]


def test_generazione_rigenera_solo_la_stagione_s1_scelta():
    chiamate = []
    rigenerate = []

    def genera(indice, _t0, _budget, _stop):
        chiamate.append(indice)
        # C1 preferisce la stagione 1: nessun riuso nella chiave produttiva.
        chiavi = [(0, 20, -1)] if indice == 1 else [(1, 0, -5)]
        return [f"mese-{indice}"], chiavi, object(), None

    def analizza_candidata(_mesi, indice):
        if indice == 1:
            return _candidato(1, _metriche(), _temporali())
        return _candidato(
            2,
            _metriche(
                riusi=2,
                incompatibilita_l1=0,
                incompatibilita_l2=0,
                affinita_l1=4,
                affinita_totali=6,
                affinita_pesate=9,
            ),
            _temporali(primo_mese_riuso=9),
        )

    def analizza_baseline(_mesi, indice):
        assert indice == 1
        return _candidato(1, _metriche(), _temporali())

    def rigenera(indice, _stop):
        rigenerate.append(indice)
        return [f"mese-rigenerato-{indice}"], [(2, 0, -6)], object(), None

    mesi, _chiavi, info = genera_migliore_stagione(
        genera,
        num_mesi=1,
        numero_stagioni_fisso=2,
        analizza_candidata=analizza_candidata,
        analizza_baseline=analizza_baseline,
        seleziona_stagione=seleziona_s1,
        rigenera_una_stagione=rigenera,
    )

    assert chiamate == [1, 2]
    assert rigenerate == [2]
    assert mesi == ["mese-rigenerato-2"]
    assert info["indice_stagione_c1"] == 1
    assert info["indice_stagione_migliore"] == 2
    assert info["politica_annuale"] == POLITICA_PROTETTA


class _MotoreFinto:
    def __init__(self):
        self.tentativi = []
        self.tentativo_corrente = None
        self.diagnostica = None

    def configura_per_tentativo(self, tentativo):
        self.tentativo_corrente = tentativo
        self.tentativi.append(tentativo)


class _StudenteFinto:
    nota_posizione = "NORMALE"

    def __init__(self, nome):
        self.nome = nome
        self.incompatibilita = {}
        self.affinita = {}
        self.sesso = "M"

    def get_nome_completo(self):
        return self.nome


def test_t2_t3_sono_saltati_solo_dopo_t1_esaustivo(monkeypatch):
    studenti = [_StudenteFinto("A"), _StudenteFinto("B"), _StudenteFinto("C")]
    motore = _MotoreFinto()
    soluzione = [Gruppo(TIPO_TERZETTO, studenti)]

    monkeypatch.setattr(mt, "calcola_punteggi_coppie", lambda *a, **k: ({}, set()))
    monkeypatch.setattr(
        mt,
        "_genera_terzetti_ammissibili",
        lambda studenti, *a, **k: {id(s): [] for s in studenti},
    )
    monkeypatch.setattr(mt, "diversifica_indice_terzetti", lambda indice, **k: indice)
    monkeypatch.setattr(mt, "_punteggio_partizione", lambda *a, **k: 0)
    monkeypatch.setattr(mt, "NUM_RIPARTENZE_TENTATIVO_4", 1)

    def backtrack(*args, contatore_nodi, **kwargs):
        contatore_nodi[0] = 1
        return soluzione if motore.tentativo_corrente == 4 else None

    monkeypatch.setattr(mt, "_backtrack", backtrack)

    risultato = mt.partiziona_in_gruppi(motore, studenti, seed=123)

    assert risultato == soluzione
    assert motore.tentativi == [1, 4]


def test_t2_non_viene_saltato_se_t1_raggiunge_il_tetto(monkeypatch):
    studenti = [_StudenteFinto("A"), _StudenteFinto("B"), _StudenteFinto("C")]
    motore = _MotoreFinto()
    soluzione = [Gruppo(TIPO_TERZETTO, studenti)]

    monkeypatch.setattr(mt, "calcola_punteggi_coppie", lambda *a, **k: ({}, set()))
    monkeypatch.setattr(
        mt,
        "_genera_terzetti_ammissibili",
        lambda studenti, *a, **k: {id(s): [] for s in studenti},
    )
    monkeypatch.setattr(mt, "_punteggio_partizione", lambda *a, **k: 0)

    def backtrack(*args, contatore_nodi, **kwargs):
        if motore.tentativo_corrente == 1:
            contatore_nodi[0] = mt.LIMITE_NODI_BACKTRACK + 1
            return None
        contatore_nodi[0] = 1
        return soluzione

    monkeypatch.setattr(mt, "_backtrack", backtrack)

    risultato = mt.partiziona_in_gruppi(motore, studenti, seed=456)

    assert risultato == soluzione
    assert motore.tentativi[:2] == [1, 2]
