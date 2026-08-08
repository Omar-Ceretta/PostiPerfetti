# -*- coding: utf-8 -*-

from types import SimpleNamespace

from moduli.algoritmo import AssegnatorePosti
from moduli.motore_terzetti import costruisci_report_fallimento_terzetti
from moduli.studenti import Student


def _studenti(numero, *, genere="M"):
    return [
        Student(f"Cognome{indice}", f"Nome{indice}", genere)
        for indice in range(numero)
    ]


def _rendi_incompatibili(a, b):
    a.aggiungi_incompatibilita(b.get_nome_completo(), 3)
    b.aggiungi_incompatibilita(a.get_nome_completo(), 3)


def _aula(posti=10, prima=6):
    return SimpleNamespace(
        posti_disponibili=posti,
        get_banchi_per_fila=lambda: [list(range(prima))],
    )


def test_report_coppie_completa_il_contratto_genere_misto():
    assegnatore = AssegnatorePosti()
    assegnatore.studenti = [
        Student("Rossi", "Ada", "F"),
        Student("Bianchi", "Luca", "M"),
        Student("Verdi", "Paolo", "M"),
        Student("Neri", "Marco", "M"),
    ]
    assegnatore.configurazione_aula = _aula(posti=4, prima=4)
    assegnatore.motore_vincoli.imposta_genere_misto_obbligatorio(True)

    report = assegnatore._costruisci_report_diagnostico()

    assert report["genere_misto"]["preferenza_soft"] is True
    assert report["genere_misto"]["sbilanciamento"] is True
    assert report["ricerca_incompleta"] is False


def test_report_coppie_non_duplica_il_fisso_come_studente_isolato():
    fisso = Student("Fisso", "Uno", "M", "FISSO")
    altri = _studenti(2)
    for altro in altri:
        _rendi_incompatibili(fisso, altro)

    assegnatore = AssegnatorePosti()
    assegnatore.studente_fisso = fisso
    assegnatore.studenti = altri
    assegnatore.configurazione_aula = _aula(posti=3, prima=3)

    report = assegnatore._costruisci_report_diagnostico()

    assert report["studenti_senza_vicini_compatibili"] == []
    assert report["fisso"]["nessun_vicino_lecito"] is True
    assert sum("FISSO" in causa for causa in report["cause_certe"]) == 1


def test_report_terzetti_rileva_numero_studenti_non_partizionabile():
    report = costruisci_report_fallimento_terzetti(_studenti(1))

    assert report["cause_certe"]
    assert "numero di studenti" in report["cause_certe"][0]


def test_report_terzetti_rileva_capienza_frontale_insufficiente():
    studenti = _studenti(4)
    studenti[0].nota_posizione = "PRIMA"
    studenti[1].nota_posizione = "PRIMA"

    report = costruisci_report_fallimento_terzetti(
        studenti,
        max_terzetti_prima_fila=0,
        max_resti_prima_fila=0,
    )

    assert report["prima_fila"]["impossibile_per_capienza"] is True
    assert any("prima fila" in causa for causa in report["cause_certe"])


def test_report_terzetti_rileva_studente_senza_vicini_compatibili():
    studenti = _studenti(4)
    for altro in studenti[1:]:
        _rendi_incompatibili(studenti[0], altro)

    report = costruisci_report_fallimento_terzetti(studenti)

    assert studenti[0].get_nome_completo() in report[
        "studenti_senza_vicini_compatibili"
    ]
    assert any("ogni possibile vicino" in causa for causa in report["cause_certe"])


def test_report_terzetti_distingue_ricerca_incompleta_da_impossibilita():
    report = costruisci_report_fallimento_terzetti(
        _studenti(6),
        metadati_casualita={"tetto_nodi_scattato": True},
    )

    assert report["cause_certe"] == []
    assert report["ricerca_incompleta"] is True
    assert any("limite di sicurezza" in voce for voce in report["suggerimenti"])


def test_calcolo_terzetti_allega_il_report_al_fallimento():
    from moduli.motore_terzetti import calcola_miglior_mese_terzetti

    gruppi, metadati = calcola_miglior_mese_terzetti(
        _studenti(1),
        False,
        restituisci_metadati=True,
        seed_base=7,
    )

    assert gruppi is None
    assert metadati["report_fallimento"]["cause_certe"]


def test_report_terzetti_descrive_il_fisso_senza_duplicarlo():
    fisso = Student("Fisso", "Uno", "M", "FISSO")
    altri = _studenti(2)
    for altro in altri:
        _rendi_incompatibili(fisso, altro)

    report = costruisci_report_fallimento_terzetti([fisso, *altri])

    assert report["fisso"]["nessun_vicino_lecito"] is True
    assert fisso.get_nome_completo() not in report[
        "studenti_senza_vicini_compatibili"
    ]
    assert sum("FISSO" in causa for causa in report["cause_certe"]) == 1
