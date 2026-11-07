# -*- coding: utf-8 -*-
"""Helper puri per il Report della modalità Personalizzata.

Il modulo non importa Qt. Definisce il risultato strutturato del Report e
raccoglie le informazioni geometriche che il report storico di PostiPerfetti non può
dedurre da una normale ``ConfigurazioneAula``. In particolare, PRIMA e ULTIMA
sono proprietà esplicite dei blocchi e FISSO è legato a uno specifico posto.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ReportLayout:
    """Contenuti del Report separati dai widget che li visualizzano."""

    testo: str
    riutilizzi: int
    riga_identificativa: str
    statistiche: tuple[dict, ...]


def _nome(studente: Any) -> str:
    return studente.get_nome_completo()


def mappa_blocchi_per_studente(collocazioni: Iterable[Any]) -> dict[str, Any]:
    """Restituisce il blocco fisico occupato da ciascuno studente."""
    risultato: dict[str, Any] = {}
    for collocazione in collocazioni:
        blocco = collocazione.blocco
        for _posto, studente in collocazione.occupazioni:
            nome = _nome(studente)
            if nome in risultato:
                raise ValueError(f"Studente duplicato nelle collocazioni: {nome!r}.")
            risultato[nome] = blocco
    return risultato


def note_posizione_personalizzata(
    studenti: Iterable[Any],
    blocchi_per_studente: dict[str, Any],
) -> list[str]:
    """Produce le note PRIMA/ULTIMA usando le zone esplicite dei blocchi.

    Le stringhe seguono esattamente il lessico del report storico: sedia quando
    la richiesta è soddisfatta, doppio punto esclamativo per PRIMA mancata e
    punto esclamativo per ULTIMA mancata.
    """
    righe: list[str] = []
    for studente in studenti:
        posizione = getattr(studente, "nota_posizione", "NORMALE")
        if posizione not in {"PRIMA", "ULTIMA"}:
            continue

        nome = _nome(studente)
        blocco = blocchi_per_studente.get(nome)
        if blocco is None:
            raise ValueError(f"Studente non collocato nel report: {nome!r}.")

        if posizione == "PRIMA":
            if bool(getattr(blocco, "zona_prima", False)):
                righe.append(f"🪑 PRIMA FILA richiesta: {nome}")
            else:
                righe.append(f"‼️ NON in PRIMA FILA come richiesto: {nome}")
        else:
            if bool(getattr(blocco, "zona_ultima", False)):
                righe.append(f"🪑 ULTIMA FILA richiesta: {nome}")
            else:
                righe.append(f"❗ NON in ULTIMA FILA come richiesto: {nome}")

    return righe


def verifica_fisso_personalizzata(
    collocazioni: Iterable[Any],
    nome_fisso: str,
) -> tuple[bool, Any | None, int | None]:
    """Verifica che FISSO occupi proprio il posto-ancora dichiarato.

    Restituisce ``(ok, blocco, indice_posto)``. ``ok`` è vero soltanto quando il
    posto occupato dal FISSO ha ``ancora_fisso=True``.
    """
    for collocazione in collocazioni:
        for posto, studente in collocazione.occupazioni:
            if _nome(studente) != nome_fisso:
                continue
            return bool(getattr(posto, "ancora_fisso", False)), collocazione.blocco, int(posto.indice)
    return False, None, None


def collocazioni_ordinate_per_report(collocazioni: Iterable[Any]) -> tuple[Any, ...]:
    """Ordina i banchi dal docente verso il fondo, quindi da sinistra a destra."""
    return tuple(sorted(
        collocazioni,
        key=lambda c: (
            int(c.blocco.profondita),
            int(c.blocco.colonna),
            str(c.blocco.id),
        ),
    ))


PREFISSO_ASSEGNAZIONE_REPORT = "Assegnazione: "


def sostituisci_nome_assegnazione_report(testo: str, nuovo_nome: str) -> str:
    """Aggiorna il nome dell'assegnazione nella testata del report."""
    righe = testo.splitlines()
    for indice, riga in enumerate(righe):
        if riga.startswith(PREFISSO_ASSEGNAZIONE_REPORT):
            righe[indice] = f"{PREFISSO_ASSEGNAZIONE_REPORT}{nuovo_nome}"
            break
    return "\n".join(righe)

