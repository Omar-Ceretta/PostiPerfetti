from types import SimpleNamespace

from moduli.configurazione_aula_ui import (
    testi_opzione_genere_misto as _testi_opzione_genere_misto,
)
from moduli.risultati_annuali import (
    descrivi_abbinamenti_coppie,
    descrivi_abbinamenti_terzetti,
)


def test_opzione_genere_misto_nomina_il_tipo_di_relazione_corretto():
    etichetta_coppie, tooltip_coppie = _testi_opzione_genere_misto("coppie")
    etichetta_terzetti, tooltip_terzetti = _testi_opzione_genere_misto("terzetti")

    assert "coppie miste" in etichetta_coppie
    assert "coppie M+F" in tooltip_coppie
    assert "vicinanze miste" in etichetta_terzetti
    assert "vicinanze consecutive M+F" in tooltip_terzetti


def test_descrizione_coppie_omette_le_categorie_assenti():
    assegnatore = SimpleNamespace(
        coppie_formate=[],
        trio_identificato=[1, 2, 3],
        studente_fisso=None,
        gruppo_adiacente_fisso=None,
    )

    assert descrivi_abbinamenti_coppie(assegnatore) == "1 trio"


def test_descrizione_terzetti_non_mostra_zero_terzetti():
    gruppi = [
        SimpleNamespace(tipo="coppia"),
        SimpleNamespace(tipo="quartetto"),
        SimpleNamespace(tipo="quartetto"),
    ]

    assert descrivi_abbinamenti_terzetti(gruppi) == (
        "2 quartetti + 1 coppia"
    )


def test_descrizione_vuota_e_esplicita_e_comune_ai_due_modi():
    assegnatore = SimpleNamespace(
        coppie_formate=[],
        trio_identificato=None,
        studente_fisso=None,
        gruppo_adiacente_fisso=None,
    )

    assert descrivi_abbinamenti_coppie(assegnatore) == "Nessun abbinamento"
    assert descrivi_abbinamenti_terzetti([]) == "Nessun abbinamento"
