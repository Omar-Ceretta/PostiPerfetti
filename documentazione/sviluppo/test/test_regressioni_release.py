# -*- coding: utf-8 -*-
"""Regression test per difetti corretti durante l'audit della release.

Questi test proteggono invarianti che non devono più regredire:
- identità/versione unica;
- esportazione XLSX di testo utente senza formule;
- validazione fail-fast dei token geometrici.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta.
Licenza: GNU GPLv3.
"""

from __future__ import annotations

from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from moduli.aula import (
    ConfigurazioneAula,
    PostoAula,
    pianifica_blocco_finale_terzetti,
)
from moduli.esportazione import EsportazioneMixin
from moduli.motore_terzetti import pianifica_resto
from moduli.versione import (
    TAG_RELEASE,
    VERSIONE,
    VERSIONE_PARTI,
    VERSIONE_WINDOWS,
)


# ============================================================================
# A1 — identità di versione
# ============================================================================

def test_versione_derivata_da_unica_fonte():
    """Le rappresentazioni secondarie devono derivare tutte da VERSIONE."""
    parti = tuple(int(parte) for parte in VERSIONE.split("."))

    assert len(parti) == 3
    assert VERSIONE_PARTI == parti
    assert VERSIONE_WINDOWS == (*parti, 0)
    assert TAG_RELEASE == f"v{VERSIONE}"


# ============================================================================
# B1 — Excel: il testo utente non deve diventare una formula
# ============================================================================

class _EsportatoreTest(EsportazioneMixin):
    """Versione minima del mixin sufficiente al test XLSX."""

    def _estrai_nome_completo_da_id(self, id_univoco: str) -> str:
        return id_univoco


def test_excel_non_interpreta_testo_utente_come_formula(tmp_path):
    """Titolo e nome studente che iniziano con = restano semplici stringhe."""
    nome_assegnazione = "=2+2"
    nome_studente = "=SOMMA(1;1)"

    configurazione = SimpleNamespace(
        griglia=[
            [
                PostoAula(
                    riga=2,
                    colonna=0,
                    tipo="banco",
                    occupato_da=nome_studente,
                ),
            ],
        ],
    )

    assegnatore = SimpleNamespace(
        configurazione_aula=configurazione,
    )

    destinazione = tmp_path / "formula_injection.xlsx"

    esportatore = _EsportatoreTest()
    esportatore.crea_file_excel(
        str(destinazione),
        assegnatore,
        nome_assegnazione=nome_assegnazione,
    )

    assert destinazione.is_file()

    with ZipFile(destinazione) as archivio:
        foglio = archivio.read(
            "xl/worksheets/sheet1.xml"
        ).decode("utf-8")

        shared_strings = archivio.read(
            "xl/sharedStrings.xml"
        ).decode("utf-8")

    # Non deve esistere alcuna formula nel foglio.
    assert "<f>" not in foglio
    assert "<f " not in foglio

    # I valori pericolosi devono essere conservati come testo.
    assert nome_assegnazione in shared_strings
    assert nome_studente in shared_strings


# ============================================================================
# B3 — geometria a coppie: posizione del trio
# ============================================================================

@pytest.mark.parametrize(
    "posizione",
    ["prima", "centro", "ultima"],
)
def test_token_validi_posizione_trio_restano_accettati(posizione):
    aula = ConfigurazioneAula("Test")

    aula.crea_layout_standard(
        17,
        posizione_trio=posizione,
    )

    assert aula.ha_trio is True
    assert aula.fila_trio is not None


def test_token_invalido_posizione_trio_fallisce():
    aula = ConfigurazioneAula("Test")

    with pytest.raises(
        ValueError,
        match="posizione_trio non valida",
    ):
        aula.crea_layout_standard(
            17,
            posizione_trio="centrale",
        )


def test_posizione_trio_mancante_fallisce_se_trio_necessario():
    aula = ConfigurazioneAula("Test")

    with pytest.raises(
        ValueError,
        match="posizione_trio non valida",
    ):
        aula.crea_layout_standard(
            17,
            posizione_trio=None,
        )


def test_posizione_trio_none_valida_se_trio_non_necessario():
    aula = ConfigurazioneAula("Test")

    aula.crea_layout_standard(
        18,
        posizione_trio=None,
    )

    assert aula.ha_trio is False
    assert aula.fila_trio is None


# ============================================================================
# B3-bis — geometria a terzetti
# ============================================================================

@pytest.mark.parametrize(
    "funzione",
    [
        lambda: pianifica_blocco_finale_terzetti(
            20,
            "banana",
        ),
        lambda: pianifica_resto(
            20,
            "banana",
        ),
        lambda: pianifica_resto(
            1,
            "banana",
        ),
    ],
)
def test_preferenza_resto2_invalida_fallisce(funzione):
    with pytest.raises(
        ValueError,
        match="preferenza_resto2 non valida",
    ):
        funzione()


def test_posizione_blocco_finale_invalida_fallisce():
    aula = ConfigurazioneAula("Test")

    with pytest.raises(
        ValueError,
        match="posizione_blocco_finale non valida",
    ):
        aula.crea_layout_terzetti(
            20,
            terzetti_per_fila=3,
            posizione_blocco_finale="centrale",
            preferenza_resto2="coppia",
        )


@pytest.mark.parametrize(
    "posizione",
    [None, "centro", "ultima"],
)
def test_posizioni_blocco_finale_usate_dalla_gui_restano_valide(
    posizione,
):
    """Il resto può mantenere il default oppure stare in mezzo/in fondo."""
    aula = ConfigurazioneAula("Test")

    aula.crea_layout_terzetti(
        20,
        terzetti_per_fila=3,
        posizione_blocco_finale=posizione,
        preferenza_resto2="coppia",
    )

    assert aula.tipo_blocco_finale == "coppia"
    assert aula.fila_blocco_finale is not None


@pytest.mark.parametrize(
    "preferenza",
    ["coppia", "due_quartetti"],
)
def test_preferenze_resto2_ufficiali_restano_valide(preferenza):
    pianifica_resto(
        20,
        preferenza,
    )
