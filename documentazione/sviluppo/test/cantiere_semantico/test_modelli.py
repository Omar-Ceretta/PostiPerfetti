from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from strumenti.cantiere_semantico.identita import chiave_adiacenza
from strumenti.cantiere_semantico.modelli import (
    CanaleRotazione,
    EventoAdiacenza,
    FasciaRipetizione,
    FunzioneGruppo,
    GruppoCanonico,
    OrigineUltimoUso,
    ParametriAula,
    ParametriRicerca,
    RiepilogoMensile,
    RuoloAdiacenza,
    TipoGruppo,
    UltimoUso,
)


def test_parametri_richiedono_un_criterio_di_arresto():
    with pytest.raises(ValueError, match="criterio di arresto"):
        ParametriRicerca(numero_candidati=10)


def test_parametri_aula_congelano_mapping_annidati():
    sorgente = {"opzioni": ["a", "b"]}
    parametri = ParametriAula(4, 6, extra=sorgente)
    sorgente["opzioni"].append("c")
    assert parametri.extra["opzioni"] == ("a", "b")
    with pytest.raises(TypeError):
        parametri.extra["nuovo"] = 1


def test_dataclass_frozen_non_modificabile():
    parametri = ParametriRicerca(numero_candidati=10, numero_stagioni_fisso=5)
    with pytest.raises(FrozenInstanceError):
        parametri.numero_candidati = 11


def test_gruppo_verifica_cardinalita():
    with pytest.raises(ValueError, match="richiede 3 membri"):
        GruppoCanonico(
            group_id="group_x",
            tipo=TipoGruppo.TERZETTO,
            membri_ordinati=("A", "B"),
            funzione=FunzioneGruppo.ORDINARIO,
        )


def _evento_prima_comparsa() -> EventoAdiacenza:
    return EventoAdiacenza(
        event_id="event_1",
        run_id="run_1",
        mese=1,
        group_id="group_1",
        studente_a="Rossi Anna",
        studente_b="Bianchi Luca",
        ordine_a=0,
        ordine_b=1,
        chiave_adiacenza=chiave_adiacenza("Rossi Anna", "Bianchi Luca"),
        ruolo=RuoloAdiacenza.COPPIA_ORDINARIA,
        canale_rotazione=CanaleRotazione.COPPIE,
        coinvolge_fisso=False,
        nome_fisso=None,
        nome_vicino_fisso=None,
        incompatibilita_livello=0,
        affinita_livello=2,
        genere_a="F",
        genere_b="M",
        adiacenza_mista=True,
        usi_precedenti_totali=0,
        usi_precedenti_nell_annata=0,
        e_riuso=False,
        numero_ripetizione=None,
        fascia_ripetizione=FasciaRipetizione.PRIMA_COMPARSA,
        ultimo_uso=UltimoUso(OrigineUltimoUso.NESSUNO),
        distanza_mesi=None,
    )


def test_evento_valido_di_prima_comparsa():
    evento = _evento_prima_comparsa()
    assert evento.affinita_livello == 2
    assert not evento.e_riuso


def test_evento_rifiuta_distanza_incoerente():
    dati = _evento_prima_comparsa().__dict__ if hasattr(_evento_prima_comparsa(), "__dict__") else None
    assert dati is None  # slots: nessun dizionario mutabile implicito
    with pytest.raises(ValueError, match="distanza_mesi"):
        EventoAdiacenza(
            event_id="event_2",
            run_id="run_1",
            mese=4,
            group_id="group_1",
            studente_a="Rossi Anna",
            studente_b="Bianchi Luca",
            ordine_a=0,
            ordine_b=1,
            chiave_adiacenza=chiave_adiacenza("Rossi Anna", "Bianchi Luca"),
            ruolo=RuoloAdiacenza.COPPIA_ORDINARIA,
            canale_rotazione=CanaleRotazione.COPPIE,
            coinvolge_fisso=False,
            nome_fisso=None,
            nome_vicino_fisso=None,
            incompatibilita_livello=1,
            affinita_livello=0,
            genere_a="F",
            genere_b="M",
            adiacenza_mista=True,
            usi_precedenti_totali=1,
            usi_precedenti_nell_annata=1,
            e_riuso=True,
            numero_ripetizione=1,
            fascia_ripetizione=FasciaRipetizione.PRIMA_RIPETIZIONE,
            ultimo_uso=UltimoUso(OrigineUltimoUso.ANNATA_CORRENTE, mese_annata=2),
            distanza_mesi=1,
        )


def test_evento_rifiuta_affinita_e_incompatibilita_insieme():
    with pytest.raises(ValueError, match="insieme"):
        EventoAdiacenza(
            event_id="event_3",
            run_id="run_1",
            mese=1,
            group_id="group_1",
            studente_a="A",
            studente_b="B",
            ordine_a=0,
            ordine_b=1,
            chiave_adiacenza=("A", "B"),
            ruolo=RuoloAdiacenza.COPPIA_ORDINARIA,
            canale_rotazione=CanaleRotazione.COPPIE,
            coinvolge_fisso=False,
            nome_fisso=None,
            nome_vicino_fisso=None,
            incompatibilita_livello=1,
            affinita_livello=1,
            genere_a="F",
            genere_b="F",
            adiacenza_mista=False,
            usi_precedenti_totali=0,
            usi_precedenti_nell_annata=0,
            e_riuso=False,
            numero_ripetizione=None,
            fascia_ripetizione=FasciaRipetizione.PRIMA_COMPARSA,
            ultimo_uso=UltimoUso(OrigineUltimoUso.NESSUNO),
            distanza_mesi=None,
        )


def test_riepilogo_mensile_verifica_totali():
    with pytest.raises(ValueError, match="fasce"):
        RiepilogoMensile(
            adiacenze_totali=2,
            riusi_totali=2,
            prime_ripetizioni=1,
            seconde_ripetizioni=0,
            terze_o_ulteriori=0,
            incompatibilita_l1=0,
            incompatibilita_l2=0,
            incompatibilita_l3=0,
            affinita_l1=0,
            affinita_l2=0,
            affinita_l3=0,
            adiacenze_miste=1,
            adiacenze_stesso_genere=1,
        )
