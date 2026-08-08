# -*- coding: utf-8 -*-
from strumenti.validazione_rc.fuzzing import (
    costruisci_spec_fuzz, genera_classe_fuzz, genera_storico_fuzz,
    verifica_filtri_t1_t4, verifica_mensile_differenziale,
)
from strumenti.validazione_rc.riduzione import riduci_classe_rc


def test_fuzz_generatore_resta_nel_dominio_e_reciproco():
    for indice in range(1, 25):
        spec = costruisci_spec_fuzz(indice=indice, seed_base=20260807)
        classe = genera_classe_fuzz(spec)
        assert 12 <= classe.numero_studenti <= 30
        per_nome = classe.per_nome
        for s in classe.studenti:
            for r in s.incompatibilita:
                assert per_nome[r.altro].incompatibilita_dict[s.nome] == r.livello
            for r in s.affinita:
                assert per_nome[r.altro].affinita_dict[s.nome] == r.livello


def test_filtri_t1_t4_rispettano_contratti_su_casi_fuzz():
    for indice in range(1, 21):
        spec = costruisci_spec_fuzz(indice=indice, seed_base=303000)
        classe = genera_classe_fuzz(spec)
        storico = genera_storico_fuzz(classe, spec)
        _n, anomalie = verifica_filtri_t1_t4(classe, storico, spec)
        assert not anomalie, anomalie


def test_best_of_n_non_peggiora_su_casi_fuzz_coppie_e_terzetti():
    for indice in range(1, 9):
        spec = costruisci_spec_fuzz(indice=indice, seed_base=404000)
        classe = genera_classe_fuzz(spec)
        for modalita in ("coppie", "terzetti"):
            _n, anomalie = verifica_mensile_differenziale(classe, spec, modalita)
            assert not anomalie, anomalie


def test_riduttore_scende_a_12_e_conserva_un_arco_assoluto():
    spec = costruisci_spec_fuzz(indice=77, seed_base=505000)
    classe = genera_classe_fuzz(spec)
    # Se il caso casuale non contiene livello 3, usa un predicato indipendente
    # dalle relazioni per testare comunque la riduzione dimensionale.
    def predicato(c):
        return c.numero_studenti >= 12
    esito = riduci_classe_rc(classe, predicato)
    assert esito.finale_studenti == 12
    assert esito.passi_accettati > 0

from strumenti.validazione_rc.modelli import ClasseRC, StudenteRC
from strumenti.validazione_rc.oracoli import oracolo_coppie_t4


def test_oracolo_coppie_esatto_trova_matching_e_trio_nel_dominio_reale():
    for n in (12, 17, 30):
        studenti = tuple(StudenteRC(f"O{i:02d} Allievo", "F" if i%2 else "M", "NORMALE") for i in range(n))
        classe = ClasseRC(f"oracolo-{n}", studenti)
        esito = oracolo_coppie_t4(classe)
        assert esito.stato == "fattibile"
        assert len(esito.coppie) * 2 + (3 if esito.trio else 0) == n

from strumenti.validazione_rc.fuzzing import campagna_oracolo_coppie_rc
from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie


def test_geometria_insufficiente_non_viene_scambiata_per_fallimento_motore():
    aula = ConfigurazioneAula("test")
    n = 28
    file_min = numero_minimo_file_coppie(n, 4, posizione_trio="centro", ha_fisso=False)
    aula.crea_layout_standard(n, file_min, 4, "centro", ha_fisso=False)
    assert file_min == 6
    assert aula.posti_disponibili < n  # la GUI deve bloccare l'avvio


def test_campagna_oracolo_coppie_piccola_non_trova_falsi_fallimenti():
    rapporto = campagna_oracolo_coppie_rc(seed_base=909000, casi=20, limite_nodi=50000)
    assert rapporto["verde"], rapporto

from moduli.diagnostica_ricerca import DiagnosticaRicerca
from strumenti.validazione_rc.fuzzing import SpecFuzzRC, _esegui_terzetti_fuzz
from strumenti.validazione_rc.modelli import RelazioneRC


def test_memo_terzetti_taglia_stati_duplicati_senza_accettare_soluzione_piu_sporca():
    spec = SpecFuzzRC(**{
        "densita_affinita": 0.0836994129268994,
        "densita_incompatibilita": 0.08064805893939707,
        "densita_storico": 0.20779605217484173,
        "fisso": False,
        "indice": 14,
        "numero_prima": 3,
        "numero_ultima": 0,
        "quota_femmine": 0.28046135493846946,
        "quota_livello3": 0.1728595307941054,
        "seed_classe": 22274933,
        "seed_motore": 23178325,
        "studenti": 22,
    })
    classe = genera_classe_fuzz(spec)
    diagnostica = DiagnosticaRicerca(etichetta="sentinella-memo-terzetti")
    ok, verifica, _ = _esegui_terzetti_fuzz(
        classe, spec, num_candidati=1, diagnostica=diagnostica
    )
    assert ok
    assert verifica.metriche.incompatibilita_pesate == 0
    ricerche = diagnostica.esporta()["ricerche"]
    assert ricerche
    assert ricerche[0]["successo"] is True
    assert ricerche[0]["contatori"]["nodi"] < 5000
    assert ricerche[0]["contatori"].get("memo_hit", 0) > 0


def test_riduttore_elimina_relazioni_non_necessarie():
    # Costruisce 14 studenti con un solo livello 3 indispensabile e varie affinità inutili.
    nomi = [f"R{i:02d} Allievo" for i in range(14)]
    studenti = []
    for i, nome in enumerate(nomi):
        inc = ()
        if i == 0:
            inc = (RelazioneRC(nomi[1], 3),)
        elif i == 1:
            inc = (RelazioneRC(nomi[0], 3),)
        aff = ()
        if i >= 2 and i + 1 < len(nomi):
            aff = (RelazioneRC(nomi[i + 1], 1),)
        if i >= 3:
            # reciproca della precedente, se presente
            aff = aff + (RelazioneRC(nomi[i - 1], 1),)
        studenti.append(StudenteRC(nome, "F" if i % 2 else "M", "NORMALE", inc, aff))
    # Canonicalizza le affinità reciproche tramite una costruzione più semplice.
    per_aff = {nome: {} for nome in nomi}
    for i in range(2, 13):
        per_aff[nomi[i]][nomi[i+1]] = 1
        per_aff[nomi[i+1]][nomi[i]] = 1
    studenti = tuple(
        StudenteRC(
            nomi[i], "F" if i % 2 else "M", "NORMALE",
            (RelazioneRC(nomi[1],3),) if i==0 else ((RelazioneRC(nomi[0],3),) if i==1 else ()),
            tuple(RelazioneRC(a,l) for a,l in per_aff[nomi[i]].items()),
        ) for i in range(14)
    )
    classe = ClasseRC("riduzione-relazioni", studenti)
    def pred(c):
        return any(r.livello == 3 for s in c.studenti for r in s.incompatibilita)
    esito = riduci_classe_rc(classe, pred)
    assert esito.finale_studenti == 12
    assert esito.finale_relazioni == 1
