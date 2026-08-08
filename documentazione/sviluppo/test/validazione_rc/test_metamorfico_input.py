from __future__ import annotations

import pytest

from strumenti.validazione_rc.esecuzione import (
    esegui_mensile_coppie_rc,
    esegui_mensile_terzetti_rc,
)
from strumenti.validazione_rc.generatori import genera_classe_sintetica
from strumenti.validazione_rc.invarianti import firma_semantica_classe
from strumenti.validazione_rc.metamorfico import (
    indebolisci_una_incompatibilita_assoluta,
    inverti_generi,
    permuta_ordine_relazioni,
    permuta_righe,
    rimuovi_un_vincolo_prima,
    rimuovi_una_affinita,
)


def _firma_risultato(esito):
    if not esito.successo or esito.verifica is None:
        return None
    return tuple(sorted(esito.verifica.adiacenze))


def test_ordine_righe_non_cambia_il_significato():
    classe = genera_classe_sintetica(23, seed=45, famiglia="media")
    trasformata = permuta_righe(classe, seed=999)
    assert firma_semantica_classe(trasformata) == firma_semantica_classe(classe)


def test_ordine_relazioni_non_cambia_il_significato():
    classe = genera_classe_sintetica(28, seed=46, famiglia="due_blocchi")
    trasformata = permuta_ordine_relazioni(classe, seed=998)
    assert firma_semantica_classe(trasformata) == firma_semantica_classe(classe)


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_permuta_righe_non_cambia_il_risultato_con_stesso_seed(modalita):
    classe = genera_classe_sintetica(
        23, seed=20260807, famiglia="media", con_fisso=True
    )
    permutata = permuta_righe(classe, seed=77123)
    funzione = (
        esegui_mensile_coppie_rc
        if modalita == "coppie"
        else esegui_mensile_terzetti_rc
    )
    originale = funzione(classe, seed=998877, num_candidati=1)
    trasformato = funzione(permutata, seed=998877, num_candidati=1)
    assert originale.successo == trasformato.successo
    assert _firma_risultato(originale) == _firma_risultato(trasformato)


@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_invertire_tutti_i_generi_preserva_risultato_con_preferenza_mista(modalita):
    classe = genera_classe_sintetica(24, seed=8123, famiglia="sparsa")
    invertita = inverti_generi(classe)
    funzione = (
        esegui_mensile_coppie_rc
        if modalita == "coppie"
        else esegui_mensile_terzetti_rc
    )
    originale = funzione(
        classe, seed=445566, genere_misto=True, num_candidati=1
    )
    trasformato = funzione(
        invertita, seed=445566, genere_misto=True, num_candidati=1
    )
    assert originale.successo == trasformato.successo
    assert _firma_risultato(originale) == _firma_risultato(trasformato)


@pytest.mark.parametrize("trasformazione", [
    rimuovi_una_affinita,
    indebolisci_una_incompatibilita_assoluta,
    rimuovi_un_vincolo_prima,
])
@pytest.mark.parametrize("modalita", ["coppie", "terzetti"])
def test_allentare_un_vincolo_non_rende_impossibile_un_caso_gia_risolto(
    trasformazione, modalita
):
    classe = genera_classe_sintetica(
        24, seed=9931, famiglia="media", con_fisso=True
    )
    trasformata = trasformazione(classe, seed=17)
    assert trasformata is not None
    funzione = (
        esegui_mensile_coppie_rc
        if modalita == "coppie"
        else esegui_mensile_terzetti_rc
    )
    originale = funzione(classe, seed=221144, num_candidati=1)
    trasformato = funzione(trasformata, seed=221144, num_candidati=1)
    assert originale.successo
    assert trasformato.successo
    assert trasformato.verifica is not None and trasformato.verifica.valido
