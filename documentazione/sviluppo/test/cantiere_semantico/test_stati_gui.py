from pathlib import Path

from moduli.stato_sessione import calcola_abilitazione_controlli


RADICE = Path(__file__).resolve().parents[4]


def test_durante_elaborazione_restano_bloccate_tutte_le_sorgenti_del_calcolo():
    stato = calcola_abilitazione_controlli(
        in_elaborazione=True,
        classe_caricata=True,
    )

    assert stato.avvio is False
    assert stato.configurazione is False
    assert stato.editor is False
    assert stato.storico is False


def test_fuori_elaborazione_editor_e_storico_restano_disponibili_senza_classe():
    stato = calcola_abilitazione_controlli(
        in_elaborazione=False,
        classe_caricata=False,
    )

    assert stato.avvio is False
    assert stato.configurazione is False
    assert stato.editor is True
    assert stato.storico is True


def test_fuori_elaborazione_con_classe_tutti_i_controlli_operativi_sono_attivi():
    stato = calcola_abilitazione_controlli(
        in_elaborazione=False,
        classe_caricata=True,
    )

    assert all((
        stato.avvio,
        stato.configurazione,
        stato.editor,
        stato.storico,
    ))


def test_salvare_prima_di_una_nuova_assegnazione_non_annulla_il_comando_richiesto():
    sorgente = (RADICE / "moduli" / "flusso_mensile_ui.py").read_text(
        encoding="utf-8"
    )
    blocco = sorgente.split(
        "if bottone_avvia == btn_salva_avvia:", 1
    )[1].split("elif bottone_avvia == btn_annulla_avvia:", 1)[0]

    assert "self.salva_assegnazione()" in blocco
    assert "if self.sessione.mensile.non_salvata:" in blocco
    assert blocco.count("return") == 1


def test_i_worker_non_restano_riferimenti_attivi_dopo_la_conclusione():
    mensile = (RADICE / "moduli" / "flusso_mensile_ui.py").read_text(
        encoding="utf-8"
    )
    annuale = (RADICE / "moduli" / "flusso_annuale_ui.py").read_text(
        encoding="utf-8"
    )

    assert "self.worker_thread = None" in mensile
    assert "self.season_worker = None" in annuale
    assert "Impossibile avviare il calcolo Mensile a coppie" in mensile
    assert "Impossibile avviare il processo Mensile a terzetti" in mensile
    assert "Impossibile avviare il processo Annuale a coppie" in annuale
    assert "Impossibile avviare il processo Annuale a terzetti" in annuale
