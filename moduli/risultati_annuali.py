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

from moduli.aula import ConfigurazioneAula
from moduli.vincoli import MotoreVincoliConfigurato
from moduli.configurazione import ESITO_SALVATAGGIO_AZZERATO


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


@dataclass(frozen=True)
class PreparazioneTerzetti:
    """Esito della costruzione delle aule di anteprima a terzetti."""

    mesi_non_validi_prima: int
    mesi_non_validi_struttura: int


def data_creazione_corrente() -> str:
    """Restituisce la data tecnica usata da report e Storico."""
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def nome_assegnazione_automatico(
        nome_classe: str, generazione: str, modo: str, numero: int) -> str:
    """Compone il nome uniforme di una voce dello Storico."""
    etichetta_generazione = "Annuale" if generazione == "annuale" else "Mensile"
    etichetta_modo = "Terzetti" if modo == "terzetti" else "Coppie"
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


def descrivi_abbinamenti_coppie(assegnatore) -> str:
    """Descrive i blocchi fisici visibili nell'Aula a coppie."""
    num_coppie = len(getattr(assegnatore, "coppie_formate", []) or [])
    num_trii = 1 if getattr(assegnatore, "trio_identificato", None) else 0
    num_quartetti = 0

    if getattr(assegnatore, "studente_fisso", None) is not None:
        if getattr(assegnatore, "gruppo_adiacente_fisso", None):
            num_trii += 1
        elif getattr(assegnatore, "trio_identificato", None):
            num_trii -= 1
            num_quartetti = 1

    return _unisci_gruppi_presenti((
        (num_coppie, "coppia", "coppie"),
        (num_trii, "trio", "trii"),
        (num_quartetti, "quartetto", "quartetti"),
    ))


def descrivi_abbinamenti_terzetti(gruppi: Iterable) -> str:
    """Descrive soltanto i tipi di gruppo realmente presenti."""
    gruppi = list(gruppi)
    n_ter = sum(1 for gruppo in gruppi if gruppo.tipo == "terzetto")
    n_qua = sum(1 for gruppo in gruppi if gruppo.tipo == "quartetto")
    n_cop = sum(1 for gruppo in gruppi if gruppo.tipo == "coppia")
    return _unisci_gruppi_presenti((
        (n_ter, "terzetto", "terzetti"),
        (n_qua, "quartetto", "quartetti"),
        (n_cop, "coppia", "coppie"),
    ))


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
    if modo not in {"coppie", "terzetti"}:
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


def aggiorna_report_mesi_coppie(
        mesi: Sequence, identita: IdentitaAnnata) -> None:
    """Allinea data e nome dei report catturati durante la ricerca annuale."""
    if identita.modo != "coppie":
        raise ValueError("I report a coppie richiedono un'identità in modo coppie.")
    if len(mesi) != len(identita.nomi):
        raise ValueError("Mesi e nomi dell'annata hanno lunghezze diverse.")

    for indice, assegnatore in enumerate(mesi):
        report = getattr(assegnatore, "report_testo", None)
        if not report:
            continue
        report = sostituisci_campo_report(
            report, "Data creazione: ", identita.data_creazione
        )
        report = sostituisci_campo_report(
            report, "Assegnazione: ", identita.nomi[indice]
        )
        assegnatore.report_testo = report


def prepara_mesi_terzetti(
        mesi: Sequence[dict],
        *,
        terzetti_per_fila: int,
        posizione_blocco_finale: str,
        ha_fisso: bool,
        preferenza_resto2: str,
        costruisci_statistiche: Callable,
) -> PreparazioneTerzetti:
    """Costruisce le aule d'anteprima e le statistiche dei mesi a terzetti."""
    motore_statistiche = MotoreVincoliConfigurato()
    mesi_non_validi_prima = 0
    mesi_non_validi_struttura = 0

    for mese in mesi:
        gruppi = mese["gruppi"]
        num_studenti = sum(len(gruppo.membri) for gruppo in gruppi)

        aula = ConfigurazioneAula("Anteprima terzetti")
        aula.crea_layout_terzetti(
            num_studenti,
            terzetti_per_fila=terzetti_per_fila,
            posizione_blocco_finale=posizione_blocco_finale,
            ha_fisso=ha_fisso,
            preferenza_resto2=preferenza_resto2,
        )
        report = aula.piazza_gruppi_terzetti(gruppi)

        mese["aula"] = aula
        mese["prima_fuori"] = report.get("prima_fuori_capienza", 0)
        mese["valido_struttura"] = report.get("valido_struttura", True)
        mese["avvisi_posizionamento"] = list(report.get("avvisi", []))
        righe_statistiche, _ = (
            costruisci_statistiche(
                gruppi,
                motore_statistiche,
                adiacenze_gia_usate=mese.get("adiacenze_prima", set()),
            )
        )
        mese["statistiche_generali"] = righe_statistiche
        if not report.get("valido_prima", True):
            mesi_non_validi_prima += 1
        if not report.get("valido_struttura", True):
            mesi_non_validi_struttura += 1

    return PreparazioneTerzetti(
        mesi_non_validi_prima=mesi_non_validi_prima,
        mesi_non_validi_struttura=mesi_non_validi_struttura,
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
    try:
        operazione()
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
        if (
            getattr(config_app, "ultimo_esito_salvataggio", None)
            != ESITO_SALVATAGGIO_AZZERATO
        ):
            config_app.config_data = fotografia
        if isinstance(errore, ErroreSalvataggioAnnata):
            raise
        raise ErroreSalvataggioAnnata(
            f"Salvataggio dell'annata interrotto: {errore}"
        ) from errore


def salva_annata_coppie(
        config_app,
        mesi: Sequence,
        identita: IdentitaAnnata,
        *,
        genere_misto: bool,
) -> None:
    """Registra tutti i mesi a coppie con un'unica scrittura atomica."""
    if identita.modo != "coppie":
        raise ValueError("L'identità dell'annata non è in modo coppie.")
    if len(mesi) != len(identita.nomi):
        raise ValueError("Mesi e identità dell'annata hanno lunghezze diverse.")

    def registra() -> None:
        for indice, assegnatore in enumerate(mesi):
            config_app.aggiungi_assegnazione_storico(
                identita.nomi[indice],
                assegnatore.coppie_formate,
                trio=getattr(assegnatore, "trio_identificato", None),
                configurazione_aula=assegnatore.configurazione_aula,
                file_origine=identita.file_origine,
                report_completo=getattr(assegnatore, "report_testo", None),
                studente_fisso=getattr(assegnatore, "studente_fisso", None),
                gruppo_adiacente_fisso=getattr(
                    assegnatore, "gruppo_adiacente_fisso", None
                ),
                nome_adiacente_fisso=getattr(
                    assegnatore, "nome_adiacente_fisso", None
                ),
                genere_misto=genere_misto,
                statistiche_generali=getattr(
                    assegnatore, "statistiche_generali", []
                ),
                metadati_casualita=assegnatore.esporta_metadati_casualita(),
                nome_classe=identita.nome_classe,
                generazione=identita.generazione,
                data_creazione=identita.data_creazione,
                progressivo=identita.progressivi[indice],
                abbinamenti=descrivi_abbinamenti_coppie(assegnatore),
                salva_subito=False,
            )

    _salva_batch_atomico(config_app, registra)


def salva_annata_terzetti(
        config_app,
        mesi: Sequence[dict],
        identita: IdentitaAnnata,
        *,
        report_per_mese: Sequence[str],
        studente_fisso,
        genere_misto: bool,
        posizione_blocco_finale: str,
        preferenza_resto2: str,
) -> None:
    """Registra tutti i mesi a terzetti con un'unica scrittura atomica."""
    if identita.modo != "terzetti":
        raise ValueError("L'identità dell'annata non è in modo terzetti.")
    lunghezze = {len(mesi), len(identita.nomi), len(report_per_mese)}
    if len(lunghezze) != 1:
        raise ValueError("Mesi, identità e report hanno lunghezze diverse.")

    def registra() -> None:
        for indice, mese in enumerate(mesi):
            config_app.aggiungi_assegnazione_storico_terzetti(
                identita.nomi[indice],
                mese["gruppi"],
                mese["aula"],
                file_origine=identita.file_origine,
                report_completo=report_per_mese[indice],
                studente_fisso=studente_fisso,
                genere_misto=genere_misto,
                posizione_blocco_finale=posizione_blocco_finale,
                preferenza_resto2=preferenza_resto2,
                statistiche_generali=mese.get("statistiche_generali", []),
                metadati_casualita=mese.get("metadati_casualita"),
                nome_classe=identita.nome_classe,
                generazione=identita.generazione,
                data_creazione=identita.data_creazione,
                progressivo=identita.progressivi[indice],
                abbinamenti=descrivi_abbinamenti_terzetti(mese["gruppi"]),
                salva_subito=False,
            )

    _salva_batch_atomico(config_app, registra)
