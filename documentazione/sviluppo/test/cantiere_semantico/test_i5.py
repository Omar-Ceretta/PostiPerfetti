from __future__ import annotations

from copy import deepcopy

from strumenti.cantiere_semantico.adattatori_comuni import MeseAdattato, RelazioneAdattata
from strumenti.cantiere_semantico.aggregati import (
    costruisci_annata_canonica,
    costruisci_cronologia_adiacenze,
    costruisci_riepilogo_annuale,
    costruisci_riepiloghi_studenti,
    costruisci_serie_mensile,
)
from strumenti.cantiere_semantico.cronologia import costruisci_cronologia, osserva_esito_c1
from strumenti.cantiere_semantico.esecuzione_c1 import EsitoC1, esegui_c1_coppie, esegui_c1_terzetti
from strumenti.cantiere_semantico.identita import crea_group_id
from strumenti.cantiere_semantico.modelli import (
    CanaleRotazione,
    CondizioneRun,
    FasciaRipetizione,
    FunzioneGruppo,
    GruppoCanonico,
    Modalita,
    RuoloAdiacenza,
    StatoRun,
    TipoGruppo,
    TracciaMese,
)
from strumenti.cantiere_semantico.serializzazione import firma_json_sha256, serializza_json
from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni

from .supporto_i3 import (
    configurazione_produttiva_vuota,
    crea_run,
    studenti_semplici,
)


def _studenti_quattro():
    from moduli.studenti import Student

    return [
        Student("A", "Test", "M"),
        Student("B", "Test", "F"),
        Student("C", "Test", "M"),
        Student("D", "Test", "F"),
    ]


def _studenti_fisso():
    from moduli.studenti import Student

    return [
        Student("Fisso", "Test", "M", "FISSO"),
        Student("B", "Test", "F"),
        Student("C", "Test", "M"),
    ]


def _mese(run, numero, coppie, *, canale=CanaleRotazione.COPPIE, fisso=None):
    gruppi = []
    relazioni = []
    generi = {
        "A Test": "M",
        "B Test": "F",
        "C Test": "M",
        "D Test": "F",
        "Fisso Test": "M",
    }
    for indice, (a, b) in enumerate(coppie, start=1):
        gid = crea_group_id(run.run_id, numero, indice, (a, b))
        coinvolge = fisso is not None and fisso in {a, b}
        vicino = b if a == fisso else a if b == fisso else None
        ruolo = RuoloAdiacenza.VICINO_FISSO if coinvolge else RuoloAdiacenza.COPPIA_ORDINARIA
        gruppo = GruppoCanonico(
            gid,
            TipoGruppo.COPPIA,
            (a, b),
            fila=indice - 1,
            posizione_nella_fila=0,
            funzione=FunzioneGruppo.BLOCCO_FISSO if coinvolge else FunzioneGruppo.ORDINARIO,
        )
        relazione = RelazioneAdattata(
            gid,
            a,
            b,
            0,
            1,
            ruolo,
            CanaleRotazione.VICINO_FISSO if coinvolge else canale,
            coinvolge,
            fisso if coinvolge else None,
            vicino,
            0,
            0,
            generi[a],
            generi[b],
        )
        gruppi.append(gruppo)
        relazioni.append(relazione)
    traccia = TracciaMese(numero, numero, (0, 0, 0), (0, 0, 0))
    return MeseAdattato(numero, traccia, tuple(gruppi), tuple(relazioni))


def test_riepiloghi_studenti_e_distribuzione():
    config = configurazione_produttiva_vuota()
    config.config_data["coppie_da_evitare"] = [
        {"tipo": "coppia", "studenti": ["A Test", "B Test"], "volte_usata": 1}
    ]
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
    )
    cronologia = costruisci_cronologia(
        run,
        snapshot,
        (
            _mese(run, 1, (("A Test", "B Test"), ("C Test", "D Test"))),
            _mese(run, 2, (("A Test", "B Test"), ("C Test", "D Test"))),
        ),
    )
    studenti = costruisci_riepiloghi_studenti(cronologia.mesi, _studenti_quattro())
    per_nome = {voce.studente: voce for voce in studenti}
    assert per_nome["A Test"].riusi_coinvolgenti == 2
    assert per_nome["A Test"].prime_ripetizioni == 1
    assert per_nome["A Test"].seconde_ripetizioni == 1
    assert per_nome["C Test"].riusi_coinvolgenti == 1
    assert per_nome["C Test"].mesi_con_riusi == (2,)
    assert all(voce.compagni_distinti == 1 for voce in studenti)

    annuale = costruisci_riepilogo_annuale(cronologia.mesi, studenti)
    assert annuale.riusi_totali == 3
    assert annuale.studenti_con_1_riuso == 2
    assert annuale.studenti_con_2_riusi == 2
    assert annuale.massimo_individuale == 2
    assert annuale.studenti_al_massimo == ("A Test", "B Test")


def test_cronologia_adiacenze_conserva_storico_e_distanze():
    config = configurazione_produttiva_vuota()
    config.config_data["coppie_da_evitare"] = [
        {"tipo": "coppia", "studenti": ["A Test", "B Test"], "volte_usata": 2}
    ]
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=3,
        numero_candidati=1,
        numero_stagioni=1,
    )
    cronologia = costruisci_cronologia(
        run,
        snapshot,
        (
            _mese(run, 1, (("A Test", "B Test"),)),
            _mese(run, 2, (("C Test", "D Test"),)),
            _mese(run, 3, (("A Test", "B Test"),)),
        ),
    )
    voci = costruisci_cronologia_adiacenze(cronologia.mesi)
    ab = next(voce for voce in voci if voce.studenti == ("A Test", "B Test"))
    assert ab.mesi_occorrenza == (1, 3)
    assert ab.usi_storico_iniziale == 2
    assert ab.numero_occorrenze_annata == 2
    assert ab.numero_occorrenze_totali_finali == 4
    assert ab.distanze_interne == (2,)


def test_vicino_fisso_ha_riepilogo_separato():
    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
        condizione=CondizioneRun.CON_FISSO,
    )
    cronologia = costruisci_cronologia(
        run,
        snapshot,
        (
            _mese(run, 1, (("Fisso Test", "B Test"),), fisso="Fisso Test"),
            _mese(run, 2, (("Fisso Test", "B Test"),), fisso="Fisso Test"),
        ),
    )
    studenti = costruisci_riepiloghi_studenti(cronologia.mesi, _studenti_fisso())
    per_nome = {voce.studente: voce for voce in studenti}
    assert per_nome["B Test"].incarichi_vicino_fisso == 2
    assert per_nome["B Test"].mesi_vicino_fisso == (1, 2)
    assert per_nome["Fisso Test"].incarichi_vicino_fisso == 0
    serie = costruisci_serie_mensile(cronologia.mesi)
    assert tuple(punto.vicino_fisso for punto in serie) == ("B Test", "B Test")


def test_costruisce_annata_canonica_sintetica():
    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=1,
        numero_candidati=1,
        numero_stagioni=1,
    )
    cronologia = costruisci_cronologia(
        run,
        snapshot,
        (_mese(run, 1, (("A Test", "B Test"), ("C Test", "D Test"))),),
    )
    raw = object()
    esito = EsitoC1(
        run_id=run.run_id,
        modalita=run.modalita,
        stato=StatoRun.COMPLETO,
        mesi_generazione=(raw,),
        chiavi_generazione=((0, 0, 0),),
        mesi_finali=(raw,),
        chiavi_finali=((0, 0, 0),),
        traccia_riordino=(TracciaMese(1, 1, (0, 0, 0), (0, 0, 0)),),
        info={
            "n_stagioni": 1,
            "n_stagioni_complete": 1,
            "punteggio": (0, 0, 0),
            "motivo_stop": "riproduzione",
            "elapsed": 0.01,
            "indice_stagione_migliore": 1,
        },
    )
    annata = costruisci_annata_canonica(
        esito,
        cronologia,
        run,
        snapshot,
        _studenti_quattro(),
        classe="Classe Test",
    )
    assert annata.versioni.osservatore == "1.0.0"
    assert annata.numero_studenti == 4
    assert len(annata.serie_mensile) == 1
    assert len(annata.cronologia_adiacenze) == 2
    assert annata.ricerca.indice_stagione_vincente == 1
    assert annata.metadati["numero_eventi"] == 2


def test_annata_json_stabile():
    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, _ = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=0 + 1,
        numero_candidati=1,
        numero_stagioni=1,
    )
    cronologia = costruisci_cronologia(
        run,
        snapshot,
        (_mese(run, 1, (("A Test", "B Test"), ("C Test", "D Test"))),),
    )
    raw = object()
    esito = EsitoC1(
        run.run_id,
        run.modalita,
        StatoRun.COMPLETO,
        (raw,),
        ((0, 0, 0),),
        (raw,),
        ((0, 0, 0),),
        (TracciaMese(1, 1, (0, 0, 0), (0, 0, 0)),),
        {"n_stagioni": 1, "n_stagioni_complete": 1, "punteggio": (0, 0, 0), "motivo_stop": "riproduzione", "indice_stagione_migliore": 1},
    )
    annata = costruisci_annata_canonica(esito, cronologia, run, snapshot, _studenti_quattro(), classe="Test")
    prima = serializza_json(annata)
    seconda = serializza_json(annata)
    assert prima == seconda
    assert firma_json_sha256(annata) == firma_json_sha256(annata)
    assert '"cronologia_adiacenze"' in prima
    assert '"serie_mensile"' in prima


def test_end_to_end_reale_coppie(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA", raising=False)
    from moduli.aula import ConfigurazioneAula

    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, ambiente = crea_run(
        config,
        modalita=Modalita.COPPIE,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
    )
    studenti = studenti_semplici(8)
    aula = ConfigurazioneAula("i5_coppie")
    aula.crea_layout_standard(8, 2, 6, None, ha_fisso=False)
    esito = esegui_c1_coppie(ambiente, studenti, aula)
    cronologia = osserva_esito_c1(esito, run, snapshot, studenti)
    firma_prima = deepcopy(esito.info)
    annata = costruisci_annata_canonica(
        esito,
        cronologia,
        run,
        snapshot,
        studenti,
        classe="Classe reale coppie",
    )
    assert annata.stato == StatoRun.COMPLETO
    assert len(annata.mesi) == 2
    assert len(annata.studenti) == 8
    assert annata.riepilogo.adiacenze_totali == sum(m.riepilogo.adiacenze_totali for m in annata.mesi)
    assert esito.info == firma_prima


def test_end_to_end_reale_terzetti_con_fisso(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA", raising=False)
    studenti = _studenti_fisso() + studenti_semplici(4)
    # Evita collisioni con i nomi B/C già presenti.
    from moduli.studenti import Student
    studenti = [
        Student("Fisso", "Test", "M", "FISSO"),
        Student("T01", "Test", "F"),
        Student("T02", "Test", "M"),
        Student("T03", "Test", "F"),
        Student("T04", "Test", "M"),
        Student("T05", "Test", "F"),
        Student("T06", "Test", "M"),
    ]
    config = configurazione_produttiva_vuota()
    snapshot = crea_snapshot_rotazioni(config.config_data)
    run, ambiente = crea_run(
        config,
        modalita=Modalita.TERZETTI,
        numero_mesi=2,
        numero_candidati=1,
        numero_stagioni=1,
        condizione=CondizioneRun.CON_FISSO,
    )
    esito = esegui_c1_terzetti(ambiente, studenti, studente_fisso=studenti[0])
    cronologia = osserva_esito_c1(esito, run, snapshot, studenti)
    annata = costruisci_annata_canonica(
        esito,
        cronologia,
        run,
        snapshot,
        studenti,
        classe="Classe reale terzetti",
        studente_fisso=studenti[0],
    )
    assert annata.studente_fisso == "Fisso Test"
    assert all(mese.vicino_fisso for mese in annata.mesi)
    assert sum(s.incarichi_vicino_fisso for s in annata.studenti) == 2
    assert any(voce.coinvolge_fisso for voce in annata.cronologia_adiacenze)
