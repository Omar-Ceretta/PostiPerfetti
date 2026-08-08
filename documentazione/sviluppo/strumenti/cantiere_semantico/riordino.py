"""Riordino produttivo di C1 con conservazione della traccia temporale.

Le funzioni delegano la scelta dell'ordine alle funzioni pure già usate da
PostiPerfetti. Aggiungono soltanto la corrispondenza fra indice originario e
posizione finale e riproducono gli effetti di presentazione applicati dai
wrapper annuali, senza modificare alcun criterio di scelta.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .modelli import TracciaMese


class ErroreRiordinoC1(ValueError):
    """Segnala incoerenze fra stagione, chiavi e riordino produttivo."""


def _chiave_tecnica(valore: Any, contesto: str) -> tuple[int, int, int]:
    try:
        chiave = tuple(valore)
    except TypeError as errore:
        raise ErroreRiordinoC1(f"{contesto}: chiave non iterabile.") from errore
    if len(chiave) != 3 or any(
        isinstance(elemento, bool) or not isinstance(elemento, int)
        for elemento in chiave
    ):
        raise ErroreRiordinoC1(
            f"{contesto}: attesa una chiave tecnica di tre interi."
        )
    return chiave


def _verifica_input(mesi: Sequence[Any], chiavi: Sequence[Any]) -> None:
    if len(mesi) != len(chiavi):
        raise ErroreRiordinoC1(
            f"Mesi e chiavi hanno lunghezze diverse: {len(mesi)} != {len(chiavi)}."
        )
    for indice, chiave in enumerate(chiavi, start=1):
        _chiave_tecnica(chiave, f"chiavi[{indice}]")


def riordina_coppie_con_traccia(
    mesi: Sequence[Any],
    chiavi_generazione: Sequence[Any],
    config_app: Any,
    *,
    cattura_report: Callable[..., str] | None = None,
) -> tuple[tuple[Any, ...], tuple[tuple[int, int, int], ...], tuple[TracciaMese, ...]]:
    """Applica lo stesso riordino della GUI a coppie conservandone la traccia.

    Il risultato finale coincide con ``riordina_e_cattura_stagione_coppie``;
    in più ogni mese conserva indice originario, chiave originaria, chiave
    ricalcolata e fotografie precedenti alla nuova posizione.
    """
    _verifica_input(mesi, chiavi_generazione)

    from moduli.metrica_pulizia import (
        conta_riutilizzate_con_foto,
        riordina_stagione_per_pulizia,
        snapshot_blacklist,
    )

    foto_iniziale = snapshot_blacklist(config_app)
    contatore_vicini = config_app.config_data.get(
        "studenti_vicino_fisso_contatore",
        {},
    )
    vicini_visti = {
        str(nome)
        for nome, volte in contatore_vicini.items()
        if int(volte or 0) >= 1
    }

    ordine_nuovo = riordina_stagione_per_pulizia(
        mesi,
        foto_iniziale,
        vicini_visti,
    )
    if len(ordine_nuovo) != len(mesi):
        raise ErroreRiordinoC1("Il riordino a coppie ha perso uno o più mesi.")

    ultimo_uso_coppie: dict[tuple[str, str], str] = {}
    ultimo_uso_vicino: dict[str, str] = {}
    mesi_riordinati: list[Any] = []
    chiavi_finali: list[tuple[int, int, int]] = []
    traccia: list[TracciaMese] = []
    indici_visti: set[int] = set()

    for posizione_finale, voce in enumerate(ordine_nuovo, start=1):
        indice_originale, assegnatore, chiave_finale_raw, foto = voce
        if not isinstance(indice_originale, int) or isinstance(indice_originale, bool):
            raise ErroreRiordinoC1("Il riordino ha restituito un indice non intero.")
        if not 0 <= indice_originale < len(mesi):
            raise ErroreRiordinoC1(
                f"Indice originario fuori intervallo: {indice_originale}."
            )
        if indice_originale in indici_visti:
            raise ErroreRiordinoC1(
                f"Indice originario duplicato: {indice_originale}."
            )
        indici_visti.add(indice_originale)

        chiave_generazione = _chiave_tecnica(
            chiavi_generazione[indice_originale],
            f"chiave generazione mese {indice_originale + 1}",
        )
        chiave_finale = _chiave_tecnica(
            chiave_finale_raw,
            f"chiave finale posizione {posizione_finale}",
        )
        foto_precedente = tuple(sorted(tuple(sorted(coppia)) for coppia in foto))
        vicini_precedenti = tuple(sorted(vicini_visti))

        # Stessi campi prodotti dal wrapper della GUI annuale.
        assegnatore.riutilizzate_snapshot = conta_riutilizzate_con_foto(
            assegnatore,
            foto,
            vicini_visti,
        )
        if cattura_report is not None:
            assegnatore.report_testo = cattura_report(
                assegnatore,
                ultimo_uso_coppie,
                ultimo_uso_vicino,
                foto,
                set(vicini_visti),
            )

        traccia.append(
            TracciaMese(
                posizione_generazione=indice_originale + 1,
                posizione_finale=posizione_finale,
                chiave_generazione=chiave_generazione,
                chiave_finale=chiave_finale,
                foto_rotazioni_precedenti=foto_precedente,
                vicini_fisso_precedenti=vicini_precedenti,
            )
        )

        etichetta_mese = f"mese {posizione_finale}"
        for studente_a, studente_b, _info in assegnatore.coppie_formate:
            chiave = tuple(sorted((
                studente_a.get_nome_completo(),
                studente_b.get_nome_completo(),
            )))
            ultimo_uso_coppie[chiave] = etichetta_mese

        trio = getattr(assegnatore, "trio_identificato", None)
        if trio and len(trio) == 3:
            for studente_a, studente_b in (
                (trio[0], trio[1]),
                (trio[1], trio[2]),
            ):
                chiave = tuple(sorted((
                    studente_a.get_nome_completo(),
                    studente_b.get_nome_completo(),
                )))
                ultimo_uso_coppie[chiave] = etichetta_mese

        gruppo = getattr(assegnatore, "gruppo_adiacente_fisso", None)
        if gruppo and len(gruppo) >= 2:
            chiave = tuple(sorted((
                gruppo[0].get_nome_completo(),
                gruppo[1].get_nome_completo(),
            )))
            ultimo_uso_coppie[chiave] = etichetta_mese

        nome_vicino = getattr(assegnatore, "nome_adiacente_fisso", None)
        if nome_vicino:
            ultimo_uso_vicino[nome_vicino] = etichetta_mese
            vicini_visti.add(nome_vicino)

        mesi_riordinati.append(assegnatore)
        chiavi_finali.append(chiave_finale)

    if indici_visti != set(range(len(mesi))):
        raise ErroreRiordinoC1("La traccia a coppie non copre tutti i mesi originari.")

    return tuple(mesi_riordinati), tuple(chiavi_finali), tuple(traccia)


def riordina_terzetti_con_traccia(
    mesi: Sequence[dict[str, Any]],
    chiavi_generazione: Sequence[Any],
    config_app: Any,
) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[int, int, int], ...], tuple[TracciaMese, ...]]:
    """Applica il riordino produttivo dei terzetti conservando gli indici."""
    _verifica_input(mesi, chiavi_generazione)

    from moduli.metrica_pulizia import (
        riordina_stagione_per_pulizia_terzetti,
        snapshot_blacklist_terzetti,
    )

    foto_iniziale = snapshot_blacklist_terzetti(config_app)
    ordine_nuovo = riordina_stagione_per_pulizia_terzetti(
        mesi,
        foto_iniziale,
    )
    if len(ordine_nuovo) != len(mesi):
        raise ErroreRiordinoC1("Il riordino a terzetti ha perso uno o più mesi.")

    mesi_riordinati: list[dict[str, Any]] = []
    chiavi_finali: list[tuple[int, int, int]] = []
    traccia: list[TracciaMese] = []
    indici_visti: set[int] = set()

    for posizione_finale, voce in enumerate(ordine_nuovo, start=1):
        indice_originale, mese_nuovo, chiave_finale_raw = voce
        if not isinstance(indice_originale, int) or isinstance(indice_originale, bool):
            raise ErroreRiordinoC1("Il riordino ha restituito un indice non intero.")
        if not 0 <= indice_originale < len(mesi):
            raise ErroreRiordinoC1(
                f"Indice originario fuori intervallo: {indice_originale}."
            )
        if indice_originale in indici_visti:
            raise ErroreRiordinoC1(
                f"Indice originario duplicato: {indice_originale}."
            )
        indici_visti.add(indice_originale)

        chiave_generazione = _chiave_tecnica(
            chiavi_generazione[indice_originale],
            f"chiave generazione mese {indice_originale + 1}",
        )
        chiave_finale = _chiave_tecnica(
            chiave_finale_raw,
            f"chiave finale posizione {posizione_finale}",
        )
        foto = mese_nuovo.get("adiacenze_prima", set())
        foto_precedente = tuple(sorted(tuple(sorted(coppia)) for coppia in foto))

        traccia.append(
            TracciaMese(
                posizione_generazione=indice_originale + 1,
                posizione_finale=posizione_finale,
                chiave_generazione=chiave_generazione,
                chiave_finale=chiave_finale,
                foto_rotazioni_precedenti=foto_precedente,
            )
        )
        mesi_riordinati.append(mese_nuovo)
        chiavi_finali.append(chiave_finale)

    if indici_visti != set(range(len(mesi))):
        raise ErroreRiordinoC1("La traccia a terzetti non copre tutti i mesi originari.")

    return tuple(mesi_riordinati), tuple(chiavi_finali), tuple(traccia)
