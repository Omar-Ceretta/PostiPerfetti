from moduli.file_classe import prepara_righe_file_classe, serializza_file_classe
from strumenti.validazione_rc.generatori import dati_validati_da_classe, genera_classe_sintetica
from strumenti.validazione_rc.invarianti import firma_semantica_classe, valida_classe_rc
from strumenti.validazione_rc.modelli import FamigliaSintetica, classe_da_dati_validati


def _roundtrip(classe):
    testo = serializza_file_classe(classe.nome, dati_validati_da_classe(classe))
    caricato = prepara_righe_file_classe(testo.splitlines())
    return classe_da_dati_validati(classe.nome, caricato["studenti"], origine="roundtrip")


def test_generatore_copre_tutte_le_famiglie_ai_limiti_12_30():
    for numero in (12, 13, 29, 30):
        for indice, famiglia in enumerate(FamigliaSintetica):
            classe = genera_classe_sintetica(
                numero,
                seed=1000 + numero * 10 + indice,
                famiglia=famiglia,
                con_fisso=(indice % 2 == 0),
            )
            assert not valida_classe_rc(classe, solleva=False)
            assert firma_semantica_classe(_roundtrip(classe)) == firma_semantica_classe(classe)


def test_generatore_e_deterministico_per_seed_parametri():
    a = genera_classe_sintetica(24, seed=987654, famiglia="media", con_fisso=True)
    b = genera_classe_sintetica(24, seed=987654, famiglia="media", con_fisso=True)
    c = genera_classe_sintetica(24, seed=987655, famiglia="media", con_fisso=True)

    assert firma_semantica_classe(a) == firma_semantica_classe(b)
    assert firma_semantica_classe(a) != firma_semantica_classe(c)


def test_gemella_fisso_modifica_una_sola_posizione():
    base = genera_classe_sintetica(20, seed=1234, famiglia="due_blocchi", con_fisso=False)
    gemella = genera_classe_sintetica(20, seed=1234, famiglia="due_blocchi", con_fisso=True)

    base_per_nome = base.per_nome
    gemella_per_nome = gemella.per_nome
    assert set(base_per_nome) == set(gemella_per_nome)

    differenze = []
    for nome in sorted(base_per_nome):
        a = base_per_nome[nome]
        b = gemella_per_nome[nome]
        assert a.sesso == b.sesso
        assert a.incompatibilita == b.incompatibilita
        assert a.affinita == b.affinita
        if a.posizione != b.posizione:
            differenze.append((nome, a.posizione, b.posizione))

    assert len(differenze) == 1
    assert differenze[0][2] == "FISSO"
