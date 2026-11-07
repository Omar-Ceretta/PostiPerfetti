# -*- coding: utf-8 -*-
"""Preparazione, identità e salvataggio atomico delle annate.

Il modulo raccoglie la parte non grafica che trasforma il risultato dei worker
annuali in mesi pronti per l'anteprima e, dopo l'accettazione dell'utente, li
registra nello Storico con un'unica scrittura finale.

Non importa PySide6: può essere collaudato senza avviare l'interfaccia.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable, Sequence

from moduli.persistenza.configurazione import ESITO_SALVATAGGIO_AZZERATO


class EsitoRisultatoAnnuale(str, Enum):
    """Classificazione minima del dizionario emesso da un worker annuale."""

    PRONTO = "pronto"
    ANNULLATO = "annullato"
    VUOTO = "vuoto"


class ErroreSalvataggioAnnata(RuntimeError):
    """Segnala che l'intera annata non è stata registrata in modo atomico."""


@dataclass(frozen=True)
class RisultatoAnnuale:
    """Vista validata e indipendente dal dizionario grezzo del worker."""

    esito: EsitoRisultatoAnnuale
    mesi: list
    info: dict


@dataclass(frozen=True)
class IdentitaAnnata:
    """Metadati comuni e progressivi assegnati a tutti i mesi dell'annata."""

    file_origine: str
    nome_classe: str
    modo: str
    generazione: str
    data_creazione: str
    progressivi: tuple[int, ...]
    nomi: tuple[str, ...]




def data_creazione_corrente() -> str:
    """Restituisce la data tecnica usata da report e Storico."""
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def nome_assegnazione_automatico(
        nome_classe: str, generazione: str, modo: str, numero: int) -> str:
    """Compone il nome uniforme di una voce dello Storico."""
    etichetta_generazione = "Annuale" if generazione == "annuale" else "Mensile"
    etichette_modo = {
        "coppie": "Coppie",
        "terzetti": "Terzetti",
        "personalizzata": "Personalizzata",
    }
    try:
        etichetta_modo = etichette_modo[modo]
    except KeyError as errore:
        raise ValueError(
            f"Modalità non valida per il nome automatico: {modo!r}."
        ) from errore
    # Il Layout unico e' l'unica modalita' oggi proposta: nel nome visibile
    # non serve indicare la chiave tecnica interna «personalizzata».
    if modo == "personalizzata":
        return f"{nome_classe} - {etichetta_generazione} - {numero:02d}"
    return (
        f"{nome_classe} - {etichetta_generazione} "
        f"{etichetta_modo} - {numero:02d}"
    )


def prossimo_progressivo_storico(
        config_app, file_origine: str, generazione: str, modo: str) -> int:
    """Conta la serie omogenea classe/generazione/geometria."""
    storico = config_app.config_data.get("storico_assegnazioni", [])
    progressivi = [
        int(assegnazione["progressivo"])
        for assegnazione in storico
        if assegnazione["file_origine"] == file_origine
        and assegnazione["generazione"] == generazione
        and assegnazione["modo"] == modo
    ]
    return max(progressivi, default=0) + 1


def sostituisci_campo_report(testo: str, prefisso: str, valore: str) -> str:
    """Aggiorna la prima riga del report che usa il prefisso indicato."""
    righe = str(testo or "").splitlines()
    for indice, riga in enumerate(righe):
        if riga.startswith(prefisso):
            righe[indice] = f"{prefisso}{valore}"
            break
    return "\n".join(righe)


def _descrivi_quantita_gruppo(numero: int, singolare: str, plurale: str) -> str:
    return f"{numero} {singolare if numero == 1 else plurale}"


def _unisci_gruppi_presenti(componenti) -> str:
    parti = [
        _descrivi_quantita_gruppo(numero, singolare, plurale)
        for numero, singolare, plurale in componenti
        if numero > 0
    ]
    return " + ".join(parti) if parti else "Nessun abbinamento"








def descrivi_abbinamenti_personalizzata(gruppi: Iterable) -> str:
    """Descrive i blocchi realmente presenti nella geometria Personalizzata."""
    gruppi = list(gruppi or [])
    n_cop = sum(1 for gruppo in gruppi if gruppo.tipo == "coppia")
    n_ter = sum(1 for gruppo in gruppi if gruppo.tipo == "terzetto")
    composizione = _unisci_gruppi_presenti((
        (n_cop, "coppia", "coppie"),
        (n_ter, "terzetto", "terzetti"),
    ))
    return composizione

def classifica_risultato_annuale(risultato: dict | None) -> RisultatoAnnuale:
    """Valida e classifica il risultato grezzo emesso dal worker."""
    risultato = dict(risultato or {})
    mesi = list(risultato.get("mesi") or [])
    info = dict(risultato.get("info") or {})

    if info.get("motivo_stop") == "annullato":
        esito = EsitoRisultatoAnnuale.ANNULLATO
    elif not mesi:
        esito = EsitoRisultatoAnnuale.VUOTO
    else:
        esito = EsitoRisultatoAnnuale.PRONTO

    return RisultatoAnnuale(esito=esito, mesi=mesi, info=info)


def prepara_identita_annata(
        config_app,
        file_origine: str,
        nome_classe: str,
        modo: str,
        numero_mesi: int,
        *,
        data_creazione: str | None = None,
        generazione: str = "annuale",
) -> IdentitaAnnata:
    """Assegna data, progressivi e nomi prima di aprire l'anteprima."""
    if modo not in {"coppie", "terzetti", "personalizzata"}:
        raise ValueError(f"Modo annuale non valido: {modo!r}")
    if numero_mesi < 0:
        raise ValueError("Il numero dei mesi non può essere negativo.")

    nome_classe = nome_classe or "Classe"
    data = data_creazione or data_creazione_corrente()
    numero_partenza = prossimo_progressivo_storico(
        config_app, file_origine, generazione, modo
    )
    progressivi = tuple(
        numero_partenza + indice for indice in range(numero_mesi)
    )
    nomi = tuple(
        nome_assegnazione_automatico(
            nome_classe, generazione, modo, progressivo
        )
        for progressivo in progressivi
    )
    return IdentitaAnnata(
        file_origine=file_origine,
        nome_classe=nome_classe,
        modo=modo,
        generazione=generazione,
        data_creazione=data,
        progressivi=progressivi,
        nomi=nomi,
    )






def _salva_batch_atomico(config_app, operazione: Callable[[], None]) -> None:
    """Applica più registrazioni in memoria e persiste una sola volta.

    Le funzioni di ConfigurazioneApp aggiornano Storico e blacklist. Durante il
    batch il salvataggio immediato è disattivato; se una registrazione o la
    scrittura finale fallisce, l'intera configurazione in memoria viene
    ripristinata alla fotografia precedente. Il JSON su disco non viene mai
    sostituito prima che tutte le voci siano pronte.
    """
    fotografia = copy.deepcopy(config_app.config_data)
    in_scrittura = False
    try:
        operazione()
        in_scrittura = True
        if not config_app.salva_configurazione():
            if (
                getattr(config_app, "ultimo_esito_salvataggio", None)
                == ESITO_SALVATAGGIO_AZZERATO
            ):
                raise ErroreSalvataggioAnnata(
                    "Storico e rotazioni sono stati azzerati. "
                    "L'annata non è stata registrata; puoi riprovare "
                    "dall'anteprima per salvarla nel nuovo Storico."
                )
            raise ErroreSalvataggioAnnata(
                "La configurazione non è stata salvata su disco."
            )
    except Exception as errore:
        if not (
            in_scrittura and getattr(config_app, "ultimo_esito_salvataggio", None)
            == ESITO_SALVATAGGIO_AZZERATO
        ):
            config_app.config_data = fotografia
        if isinstance(errore, ErroreSalvataggioAnnata):
            raise
        raise ErroreSalvataggioAnnata(
            f"Salvataggio dell'annata interrotto: {errore}"
        ) from errore






def prepara_mesi_salvataggio_annuale(bozza, mesi_q21: Sequence[dict]) -> list[dict]:
    """Prepara una fotografia finale indipendente, senza metriche Q21 obsolete.

    I mesi vengono riproiettati e riverificati, inclusa la cronologia dei
    riusi. Dopo la prima modifica manuale, i metadati di ricerca Q21 non
    descrivono più la stessa sequenza di input e non vengono persistiti.
    La proposta automatica originale resta intatta.
    """
    from moduli.dominio.editing_annuale import BozzaAnnuale

    if not isinstance(bozza, BozzaAnnuale):
        raise TypeError("Serve una bozza annuale validata.")
    proiettati = bozza.proietta_mesi(mesi_q21)
    if bozza.modificata:
        primo_modificato = bozza.mesi_modificati()[0] - 1
        for mese in proiettati[primo_modificato:]:
            mese.pop("metadati_casualita", None)
    return proiettati

def prepara_mesi_da_anteprima_annuale(
        bozza, mesi_q21: Sequence[dict], mesi_visualizzati: Sequence[dict],
) -> list[dict]:
    """Sceglie la fonte corretta e rifiuta divergenze prima del salvataggio.

    In assenza di editing conserva il comportamento storico: salva i mesi
    correnti dell'anteprima, previa validazione HARD nel chiamante. Quando
    l'insegnante ha adottato modifiche, la fonte è esclusivamente la bozza;
    la vista deve però coincidere con essa, per non ignorare alterazioni o
    mostrare una disposizione differente da quella che si salverà.
    """
    if bozza is None or not bozza.modificata:
        return copy.deepcopy(list(mesi_visualizzati))
    if len(mesi_visualizzati) != bozza.numero_mesi:
        raise ValueError("Anteprima e bozza annuale hanno numeri di mesi diversi.")
    for indice, mese in enumerate(mesi_visualizzati):
        vista = bozza.fotografia.verifica_risultato(mese)
        if vista.occupazioni != bozza.corrente[indice].occupazioni:
            raise ValueError(
                f"Mese {indice + 1}: la disposizione visualizzata "
                "non coincide con la bozza modificata."
            )
    return prepara_mesi_salvataggio_annuale(bozza, mesi_q21)


def salva_annata_personalizzata(
        config_app,
        mesi: Sequence[dict],
        identita: IdentitaAnnata,
        *,
        schema_personalizzato,
        layout_visuale,
        report_per_mese: Sequence[str],
        genere_misto: bool,
) -> None:
    """Registra atomicamente una stagione Personalizzata completa o parziale."""
    if identita.modo != "personalizzata":
        raise ValueError("L'identità dell'annata non è in modo personalizzata.")
    lunghezze = {len(mesi), len(identita.nomi), len(report_per_mese)}
    if len(lunghezze) != 1:
        raise ValueError("Mesi, identità e report hanno lunghezze diverse.")

    identita_schema = schema_personalizzato.identita_semantica()
    layout_visuale.valida_contro_schema(schema_personalizzato)

    # Tutti gli indicatori persistiti devono essere stati ricalcolati per
    # le disposizioni definitive. Rifiutiamo il tipo sbagliato prima del batch.
    for indice, mese in enumerate(mesi, 1):
        if type(mese.get('modificata_manualmente', False)) is not bool:
            raise ValueError(f'Mese {indice}: indicatore manuale non valido.')

    def registra() -> None:
        for indice, mese in enumerate(mesi):
            gruppi = list(mese.get("gruppi") or [])
            collocazioni = list(mese.get("collocazioni") or [])
            if not gruppi or len(collocazioni) != len(gruppi):
                raise ValueError(
                    f"Il mese {indice + 1} non contiene gruppi/collocazioni completi."
                )
            if mese.get("schema_identita") != identita_schema:
                raise ValueError(
                    f"Il mese {indice + 1} appartiene a uno schema diverso."
                )

            config_app.aggiungi_assegnazione_storico_personalizzata(
                identita.nomi[indice],
                gruppi,
                collocazioni,
                schema_personalizzato,
                layout_visuale,
                file_origine=identita.file_origine,
                report_completo=report_per_mese[indice],
                genere_misto=genere_misto,
                statistiche_generali=mese.get("statistiche_generali", []),
                metadati_casualita=mese.get("metadati_casualita"),
                nome_classe=identita.nome_classe,
                generazione=identita.generazione,
                data_creazione=identita.data_creazione,
                progressivo=identita.progressivi[indice],
                abbinamenti=descrivi_abbinamenti_personalizzata(gruppi),
                salva_subito=False,
                modificata_manualmente=mese.get('modificata_manualmente', False),
            )

    _salva_batch_atomico(config_app, registra)

