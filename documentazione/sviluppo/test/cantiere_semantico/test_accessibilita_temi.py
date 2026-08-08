from pathlib import Path
import ast


RADICE = Path(__file__).resolve().parents[4]


def _palette():
    albero = ast.parse((RADICE / "moduli" / "tema.py").read_text(encoding="utf-8"))
    assegnazione = next(
        nodo for nodo in albero.body
        if isinstance(nodo, ast.Assign)
        and any(
            isinstance(destinazione, ast.Name) and destinazione.id == "TEMI"
            for destinazione in nodo.targets
        )
    )
    return ast.literal_eval(assegnazione.value)


def _luminanza(colore):
    valore = colore.lstrip("#")
    canali = [int(valore[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lineari = [
        canale / 12.92
        if canale <= 0.04045
        else ((canale + 0.055) / 1.055) ** 2.4
        for canale in canali
    ]
    return 0.2126 * lineari[0] + 0.7152 * lineari[1] + 0.0722 * lineari[2]


def _contrasto(primo, secondo):
    chiaro, scuro = sorted(
        (_luminanza(primo), _luminanza(secondo)),
        reverse=True,
    )
    return (chiaro + 0.05) / (scuro + 0.05)


def test_testi_semantici_e_placeholder_superano_il_contrasto_minimo():
    coppie = (
        ("testo_grigio", "sfondo_principale"),
        ("testo_placeholder", "sfondo_input"),
        ("btn_disabilitato_txt", "btn_disabilitato_sf"),
        ("btn_avvia_disabled_txt", "btn_avvia_disabled_bg"),
        ("testo_ocra", "sfondo_principale"),
        ("testo_incomp", "sfondo_principale"),
    )

    for nome_tema, colori in _palette().items():
        for testo, sfondo in coppie:
            assert _contrasto(colori[testo], colori[sfondo]) >= 4.5, (
                nome_tema,
                testo,
                sfondo,
            )


def test_focus_da_tastiera_e_visibile_sui_controlli_principali():
    sorgente = (RADICE / "moduli" / "stili.py").read_text(encoding="utf-8")

    assert "QPushButton:focus" in sorgente
    assert "QRadioButton:focus" in sorgente
    assert "QCheckBox:focus" in sorgente
    assert "QTextEdit:focus, QTableWidget:focus, QTabWidget:focus" in sorgente


def test_controlli_principali_hanno_nomi_accessibili_e_ordine_da_tastiera():
    sorgente = (RADICE / "moduli" / "pannelli_principali.py").read_text(
        encoding="utf-8"
    )

    assert "_configura_accessibilita_principale()" in sorgente
    assert "setAccessibleName(\"Riduci i posti per fila\")" in sorgente
    assert "setAccessibleName(\"Assegnazioni salvate\")" in sorgente
    assert "QWidget.setTabOrder(corrente, successivo)" in sorgente
    assert "label_filtro.setBuddy(self.filtro_classe_combo)" in sorgente


def test_dati_dinamici_sono_protetti_prima_del_rich_text():
    storico = (RADICE / "moduli" / "storico_ui.py").read_text(encoding="utf-8")
    diagnostica = (RADICE / "moduli" / "flusso_mensile_ui.py").read_text(
        encoding="utf-8"
    )
    statistiche = (RADICE / "moduli" / "statistiche.py").read_text(
        encoding="utf-8"
    )

    assert "escape(str(self.dati_assegnazione['nome']))" in storico
    assert "escape(str(causa))" in diagnostica
    assert "escape(str(coppia))" in diagnostica
    assert "html=True" in statistiche
    assert "escape(str(nome_filtro))" in statistiche


def test_istruzioni_distinguono_export_layout_e_report():
    sorgente = (RADICE / "moduli" / "istruzioni.py").read_text(encoding="utf-8")

    assert "esportarla in Excel oppure salvare il Report" in sorgente
    assert "esportarla in Excel o in <code>.txt</code>" not in sorgente
