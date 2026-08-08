from pathlib import Path
import ast

from moduli.stato_mensile import FaseMensile, StatoMensile


class _Assegnatore:
    pass


def _contesto():
    return {
        "nome": "2A - Mensile Coppie - 01",
        "progressivo": 1,
        "data_creazione": "06/08/2026 17:00",
        "file_origine": "/classi/2A.txt",
        "nome_classe": "2A",
        "genere_misto": True,
    }


def test_stato_mensile_conserva_il_contesto_di_generazione_coppie():
    stato = StatoMensile()
    stato.prepara_coppie(_Assegnatore(), **_contesto())

    assert stato.fase is FaseMensile.DA_SALVARE
    assert stato.file_origine == "/classi/2A.txt"
    assert stato.nome_classe == "2A"
    assert stato.genere_misto is True


def test_stato_mensile_conserva_il_contesto_di_generazione_terzetti_e_lo_azzera():
    stato = StatoMensile()
    stato.prepara_terzetti({"gruppi": [object()]}, **_contesto())

    assert stato.file_origine == "/classi/2A.txt"
    assert stato.nome_classe == "2A"
    assert stato.genere_misto is True

    stato.reset()
    assert stato.file_origine is None
    assert stato.nome_classe is None
    assert stato.genere_misto is None


def test_anteprima_annuale_richiede_un_contesto_esplicito():
    radice = Path(__file__).resolve().parents[4]
    albero = ast.parse(
        (radice / "moduli" / "anteprima_annuale.py").read_text(encoding="utf-8")
    )
    classe = next(
        nodo for nodo in albero.body
        if isinstance(nodo, ast.ClassDef) and nodo.name == "AnteprimaStagioneDialog"
    )
    init = next(
        nodo for nodo in classe.body
        if isinstance(nodo, ast.FunctionDef) and nodo.name == "__init__"
    )
    nomi_kw = [arg.arg for arg in init.args.kwonlyargs]
    default_kw = dict(zip(nomi_kw, init.args.kw_defaults))

    assert "genere_misto" in nomi_kw
    assert "studenti" in nomi_kw
    assert default_kw["genere_misto"] is None
    assert default_kw["studenti"] is None


def test_persistenza_non_rilegge_opzioni_modificabili_dalla_gui():
    radice = Path(__file__).resolve().parents[4]
    salvataggio = (radice / "moduli" / "salvataggio_mensile_ui.py").read_text(
        encoding="utf-8"
    )
    anteprima = (radice / "moduli" / "anteprima_annuale.py").read_text(
        encoding="utf-8"
    )

    assert "checkbox_genere_misto.isChecked()" not in salvataggio
    assert "input_nome_classe.text()" not in salvataggio
    assert "parent_window.checkbox_genere_misto" not in anteprima
    assert "parent_window.sessione.studenti" not in anteprima
