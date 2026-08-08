from __future__ import annotations

from dataclasses import replace

import pytest

from strumenti.cantiere_semantico.genere_misto import (
    arricchisci_annata_genere_misto,
    calcola_massimo_ammissibile,
    calcola_massimo_geometrico,
    costruisci_analisi_genere_misto,
)
from strumenti.cantiere_semantico.identita import crea_group_id
from strumenti.cantiere_semantico.modelli import (
    AnalisiGenereMese,
    CondizioneRun,
    EsitoOttimoMisto,
    FunzioneGruppo,
    GruppoCanonico,
    Modalita,
    TipoGruppo,
)

from .supporto_i3 import configurazione_produttiva_vuota, crea_run
from .test_i5 import _mese, _studenti_quattro


def _studenti(specifiche):
    from moduli.studenti import Student

    return [Student(nome, "Test", genere, posizione) for nome, genere, posizione in specifiche]


def _gruppi(run_id, membri, *, fisso=False):
    risultato = []
    for i, gruppo in enumerate(membri, start=1):
        tipo = {2: TipoGruppo.COPPIA, 3: TipoGruppo.TERZETTO, 4: TipoGruppo.QUARTETTO}[len(gruppo)]
        risultato.append(
            GruppoCanonico(
                crea_group_id(run_id, 1, i, gruppo),
                tipo,
                tuple(gruppo),
                fila=i - 1,
                posizione_nella_fila=0,
                funzione=FunzioneGruppo.BLOCCO_FISSO if fisso and i == 1 else FunzioneGruppo.ORDINARIO,
            )
        )
    return tuple(risultato)


def test_massimo_geometrico_due_coppie_bilanciate():
    studenti = _studenti((("M1", "M", "NORMALE"), ("M2", "M", "NORMALE"), ("F1", "F", "NORMALE"), ("F2", "F", "NORMALE")))
    gruppi = _gruppi("run", (("M1 Test", "F1 Test"), ("M2 Test", "F2 Test")))
    esito = calcola_massimo_geometrico(gruppi, studenti)
    assert esito.esatto is True
    assert esito.valore == 2
    assert sum(len(g) for g in esito.testimone) == 4


def test_fisso_centrale_puo_ridurre_il_massimo_geometrico():
    studenti = _studenti((("Fisso", "M", "FISSO"), ("M2", "M", "NORMALE"), ("F1", "F", "NORMALE")))
    gruppi = _gruppi("run", (("M2 Test", "Fisso Test", "F1 Test"),), fisso=True)
    esito = calcola_massimo_geometrico(gruppi, studenti, studente_fisso="Fisso Test")
    assert esito.valore == 1
    assert esito.testimone[0][1] == "M"


def test_massimo_ammissibile_rispetta_soltanto_l3():
    studenti = _studenti((("M1", "M", "NORMALE"), ("M2", "M", "NORMALE"), ("F1", "F", "NORMALE"), ("F2", "F", "NORMALE")))
    per_nome = {s.get_nome_completo(): s for s in studenti}
    # Tutte le coppie miste sono L3: restano ammissibili soltanto M-M e F-F.
    for m in ("M1 Test", "M2 Test"):
        for f in ("F1 Test", "F2 Test"):
            per_nome[m].incompatibilita[f] = 3
            per_nome[f].incompatibilita[m] = 3
    gruppi = _gruppi("run", (("M1 Test", "M2 Test"), ("F1 Test", "F2 Test")))
    geometrico = calcola_massimo_geometrico(gruppi, studenti)
    ammissibile = calcola_massimo_ammissibile(gruppi, studenti)
    assert geometrico.valore == 2
    assert ammissibile.valore == 0
    assert ammissibile.esatto is True


def test_l1_e_l2_non_limitano_il_massimo_ammissibile():
    studenti = _studenti((("M1", "M", "NORMALE"), ("M2", "M", "NORMALE"), ("F1", "F", "NORMALE"), ("F2", "F", "NORMALE")))
    per_nome = {s.get_nome_completo(): s for s in studenti}
    per_nome["M1 Test"].incompatibilita["F1 Test"] = 2
    per_nome["F1 Test"].incompatibilita["M1 Test"] = 2
    per_nome["M2 Test"].incompatibilita["F2 Test"] = 1
    per_nome["F2 Test"].incompatibilita["M2 Test"] = 1
    gruppi = _gruppi("run", (("M1 Test", "F1 Test"), ("M2 Test", "F2 Test")))
    assert calcola_massimo_ammissibile(gruppi, studenti).valore == 2


def test_massimo_ammissibile_restituisce_testimone_completo():
    studenti = _studenti((("A", "M", "NORMALE"), ("B", "F", "NORMALE"), ("C", "M", "NORMALE"), ("D", "F", "NORMALE"), ("E", "M", "NORMALE")))
    gruppi = _gruppi("run", (("A Test", "B Test", "C Test"), ("D Test", "E Test")))
    esito = calcola_massimo_ammissibile(gruppi, studenti)
    coperti = [nome for gruppo in esito.testimone for nome in gruppo]
    assert sorted(coperti) == sorted(s.get_nome_completo() for s in studenti)
    assert len(coperti) == len(set(coperti))


def _annata_sintetica(*, flag=False):
    from strumenti.cantiere_semantico.aggregati import costruisci_annata_canonica
    from strumenti.cantiere_semantico.cronologia import costruisci_cronologia
    from strumenti.cantiere_semantico.esecuzione_c1 import EsitoC1
    from strumenti.cantiere_semantico.modelli import StatoRun, TracciaMese
    from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni

    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(config, modalita=Modalita.COPPIE, numero_mesi=2, numero_candidati=1, numero_stagioni=1)
    run = replace(run, genere_misto_attivo=flag)
    mesi = (
        _mese(run, 1, (("A Test", "B Test"), ("C Test", "D Test"))),
        _mese(run, 2, (("A Test", "C Test"), ("B Test", "D Test"))),
    )
    cronologia = costruisci_cronologia(run, snapshot, mesi)
    raw1, raw2 = object(), object()
    esito = EsitoC1(
        run.run_id,
        run.modalita,
        StatoRun.COMPLETO,
        (raw1, raw2),
        ((0, 0, 0), (0, 0, 0)),
        (raw1, raw2),
        ((0, 0, 0), (0, 0, 0)),
        (
            TracciaMese(1, 1, (0, 0, 0), (0, 0, 0)),
            TracciaMese(2, 2, (0, 0, 0), (0, 0, 0)),
        ),
        {"n_stagioni": 1, "n_stagioni_complete": 1, "punteggio": (0, 0, 0), "motivo_stop": "test", "indice_stagione_migliore": 1},
    )
    return costruisci_annata_canonica(esito, cronologia, run, snapshot, _studenti_quattro(), classe="Test")


def test_annata_canonica_include_i6_anche_col_flag_disattivo():
    annata = _annata_sintetica(flag=False)
    assert annata.versioni.osservatore == "1.0.0"
    assert annata.genere_misto is not None
    assert annata.genere_misto.flag_attivo is False
    assert len(annata.genere_misto.mesi) == 2
    assert annata.genere_misto.adiacenze_miste_ottenute_totali == annata.riepilogo.adiacenze_miste


def test_cache_del_template_riusa_gli_stessi_esiti_immutabili():
    annata = _annata_sintetica(flag=True)
    analisi = annata.genere_misto
    assert analisi is not None
    assert analisi.mesi[0].firma_template == analisi.mesi[1].firma_template
    assert analisi.mesi[0].massimo_geometrico is analisi.mesi[1].massimo_geometrico
    assert analisi.mesi[0].massimo_ammissibile is analisi.mesi[1].massimo_ammissibile


def test_gruppi_non_pienamente_misti_sono_descrittivi():
    annata = _annata_sintetica(flag=False)
    analisi = annata.genere_misto
    assert analisi is not None
    secondo = analisi.mesi[1]
    assert secondo.adiacenze_miste_ottenute == 0
    assert len(secondo.gruppi_non_pienamente_misti) == 2
    assert {g.motivo for g in secondo.gruppi_non_pienamente_misti} == {"non_determinato"}


def test_modello_rifiuta_un_risultato_oltre_il_massimo():
    massimo = EsitoOttimoMisto(1, True, 1, 0.0)
    with pytest.raises(ValueError):
        AnalisiGenereMese(
            mese=1,
            firma_template="firma",
            massimo_geometrico=massimo,
            massimo_ammissibile=massimo,
            adiacenze_miste_ottenute=2,
            adiacenze_stesso_genere=0,
        )


def test_arricchimento_e_idempotente_sul_contenuto():
    annata = _annata_sintetica(flag=True)
    senza = replace(annata, genere_misto=None)
    prima = arricchisci_annata_genere_misto(senza, _studenti_quattro())
    seconda = arricchisci_annata_genere_misto(senza, _studenti_quattro())
    assert prima.genere_misto is not None and seconda.genere_misto is not None
    assert prima.genere_misto.massimo_geometrico_totale == seconda.genere_misto.massimo_geometrico_totale
    assert prima.genere_misto.massimo_ammissibile_totale == seconda.genere_misto.massimo_ammissibile_totale
    assert tuple(x.massimo_ammissibile.testimone for x in prima.genere_misto.mesi) == tuple(x.massimo_ammissibile.testimone for x in seconda.genere_misto.mesi)
