from pathlib import Path
import sys

from strumenti.validazione_rc.stress import (
    CasoStressRC,
    costruisci_casi_stress,
    esegui_caso_stress_isolato,
    esegui_comando_isolato,
)


RADICE = Path(__file__).resolve().parents[4]


def test_profilo_pilot_copre_famiglie_estremi_fisso_e_modalita():
    casi = costruisci_casi_stress(
        profilo="pilot",
        seed_base=1000,
        profilo_ricerca="produzione",
        semi_per_combinazione=1,
    )
    assert len(casi) == 4 * 4 * 2 * 2
    assert {c.studenti for c in casi} == {12, 17, 24, 30}
    assert {c.famiglia for c in casi} == {
        "stella", "due_blocchi", "quasi_clique", "clique_sovrabbondante"
    }
    assert {c.fisso for c in casi} == {False, True}
    assert {c.modalita for c in casi} == {"coppie", "terzetti"}
    assert {c.num_candidati for c in casi if c.modalita == "coppie"} == {10}
    assert {c.num_candidati for c in casi if c.modalita == "terzetti"} == {3}


def test_runner_isolato_taglia_un_processo_che_supera_timeout():
    stato, exit_code, durata, _stdout, _stderr = esegui_comando_isolato(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_s=0.1,
        cwd=RADICE,
    )
    assert stato == "timeout"
    assert exit_code is None
    assert durata < 1.5


def test_caso_isolato_semplice_restituisce_successo_valido():
    caso = CasoStressRC(
        id_caso="test-isolato",
        studenti=16,
        famiglia="stella",
        fisso=False,
        modalita="coppie",
        seed_classe=12345,
        seed_motore=67890,
        num_candidati=1,
    )
    esito = esegui_caso_stress_isolato(
        caso,
        timeout_s=5.0,
        radice_progetto=RADICE,
    )
    assert esito.stato == "successo_valido"
    assert esito.exit_code == 0
    assert esito.violazioni == ()


def test_caso_impossibile_o_duro_non_puo_diventare_risultato_invalido():
    caso = CasoStressRC(
        id_caso="test-clique",
        studenti=20,
        famiglia="clique_sovrabbondante",
        fisso=False,
        modalita="coppie",
        seed_classe=111,
        seed_motore=222,
        num_candidati=1,
    )
    esito = esegui_caso_stress_isolato(
        caso,
        timeout_s=5.0,
        radice_progetto=RADICE,
    )
    assert esito.stato in {"fallimento_motore", "timeout"}


def test_checkpoint_riprende_senza_rieseguire_casi_gia_conclusi(tmp_path):
    from strumenti.validazione_rc.stress import esegui_campagna_stress

    checkpoint = tmp_path / "stress.jsonl"
    primo = esegui_campagna_stress(
        profilo="strutturale",
        profilo_ricerca="minima",
        seed_base=4321,
        semi_per_combinazione=1,
        timeout_s=4.0,
        parallelismo=2,
        radice_progetto=RADICE,
        famiglie=("stella",),
        minimo_studenti=12,
        massimo_studenti=12,
        checkpoint_path=checkpoint,
    )
    assert primo.casi == 4
    assert len(checkpoint.read_text(encoding="utf-8").splitlines()) == 4

    secondo = esegui_campagna_stress(
        profilo="strutturale",
        profilo_ricerca="minima",
        seed_base=4321,
        semi_per_combinazione=1,
        timeout_s=0.01,  # sarebbe insufficiente se i worker venissero rilanciati
        parallelismo=2,
        radice_progetto=RADICE,
        famiglie=("stella",),
        minimo_studenti=12,
        massimo_studenti=12,
        checkpoint_path=checkpoint,
        riprendi=True,
    )
    assert secondo.come_dict()["dettaglio"] == primo.come_dict()["dettaglio"]
    assert len(checkpoint.read_text(encoding="utf-8").splitlines()) == 4


def test_frontiera_clique_30_fisso_fattibile_non_esplode_piu():
    caso = CasoStressRC(
        id_caso="regressione-clique-30-fisso",
        studenti=30,
        famiglia="clique_sovrabbondante",
        fisso=True,
        modalita="coppie",
        seed_classe=20261877,
        seed_motore=20324373,
        num_candidati=1,
    )
    esito = esegui_caso_stress_isolato(
        caso,
        timeout_s=3.0,
        radice_progetto=RADICE,
    )
    assert esito.stato == "successo_valido"


def test_clique_24_fisso_esterno_viene_dimostrata_impossibile_senza_timeout():
    caso = CasoStressRC(
        id_caso="regressione-clique-24-fisso-esterno",
        studenti=24,
        famiglia="clique_sovrabbondante",
        fisso=True,
        modalita="coppie",
        seed_classe=20261809,
        seed_motore=20320337,
        num_candidati=1,
    )
    esito = esegui_caso_stress_isolato(
        caso,
        timeout_s=3.0,
        radice_progetto=RADICE,
    )
    assert esito.stato == "fallimento_motore"
