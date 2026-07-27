# -*- coding: utf-8 -*-
"""
statistiche_generali.py — contratto unico delle «STATISTICHE GENERALI».

Il modulo separa nettamente tre responsabilità:

1. calcolo dei dati grezzi (coppie / vicinanze a terzetti);
2. costruzione di righe strutturate, serializzabili nello Storico;
3. rendering delle stesse righe come testo, HTML o formattazione QTextEdit.

I renderer NON ricalcolano alcun numero: leggono soltanto i metadati delle righe.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from html import escape
from typing import Iterable

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

from moduli.metrica_pulizia import (
    adiacenze_in_fila,
    TIPO_COPPIA,
    TIPO_TERZETTO,
    TIPO_QUARTETTO,
)
from moduli.tema import C
from moduli.utilita import (
    giudizio_da_note,
    conteggio_giudizi_vicinanze,
    conta_riutilizzate,
)


GIUDIZI = (
    ("ottimali", "OTTIMA", "ottimali", "affinità 3", "positivo"),
    ("buone", "BUONA", "buone", "affinità 2", "positivo"),
    ("discrete", "DISCRETA", "discrete", "affinità 1", "positivo"),
    ("accettabili", "ACCETTABILE", "accettabili", "neutrali", "positivo"),
    ("problematiche", "PROBLEMATICA", "delicate", "incompatibilità 1", "problematica"),
    ("critiche", "CRITICA", "problematiche", "incompatibilità 2", "critica"),
)

# Grammatica visiva UNICA della severità. La usano sia le righe aggregate
# di «STATISTICHE GENERALI» sia il dettaglio di coppie, trio e vicinanze.
# In questo modo livello 1 / PROBLEMATICA e livello 2 / CRITICA non possono
# più ricevere icone divergenti nei diversi punti del programma.
ICONE_CRITICITA = {
    "PROBLEMATICA": "❗",
    "CRITICA": "‼️",
}


def icona_giudizio_criticita(giudizio: str) -> str | None:
    """Restituisce l'icona canonica del giudizio, se è una criticità."""
    return ICONE_CRITICITA.get(giudizio)


def etichetta_visibile_giudizio(giudizio: str) -> str:
    """Traduce il giudizio interno nell'etichetta mostrata all'utente.

    Le chiavi interne restano invariate per non toccare logica, conteggi,
    serializzazione e collaudi algoritmici.
    """
    return {
        "PROBLEMATICA": "DELICATA",
        "CRITICA": "PROBLEMATICA",
    }.get(giudizio, giudizio)


def icona_nota_incompatibilita(nota: str) -> str | None:
    """Restituisce l'icona canonica per una nota di incompatibilità.

    Livello 1 è PROBLEMATICO (❗); livello 2 è CRITICO (‼️).
    Livelli ulteriori e incompatibilità assolute conservano il segnale
    più forte, perché non appartengono alla categoria problematica.
    """
    if nota.startswith("Incompatibilità di livello 1"):
        return ICONE_CRITICITA["PROBLEMATICA"]
    if nota.startswith("Incompatibilità di livello 2"):
        return ICONE_CRITICITA["CRITICA"]
    if (
        nota.startswith("Incompatibilità di livello")
        or nota.startswith("INCOMPATIBILITÀ ASSOLUTA")
    ):
        return ICONE_CRITICITA["CRITICA"]
    return None


def _riga(
    chiave: str,
    etichetta: str,
    valore,
    *,
    grassetto: bool = False,
    icona: str | None = None,
    icona_ui: str | None = None,
    colore: str | None = None,
    suffisso: str = "",
) -> dict:
    """Crea una riga statistica JSON-serializzabile."""
    return {
        "tipo": "statistica",
        "chiave": chiave,
        "etichetta": etichetta,
        "valore": valore,
        "icona": icona,
        "icona_ui": icona_ui,
        "grassetto": bool(grassetto),
        "colore": colore,
        "suffisso": suffisso,
    }


def _dettaglio(
    chiave: str,
    testo: str,
    *,
    grassetto: bool = False,
    colore: str | None = None,
) -> dict:
    """Crea una sotto-riga descrittiva, anch'essa serializzabile."""
    return {
        "tipo": "dettaglio",
        "chiave": chiave,
        "testo": testo,
        "icona_ui": None,
        "grassetto": bool(grassetto),
        "colore": colore,
    }


def _righe_giudizi(prefisso: str, conteggio: dict) -> list[dict]:
    righe = []
    for chiave, chiave_conteggio, aggettivo, spiegazione, famiglia in GIUDIZI:
        valore = int(conteggio.get(chiave_conteggio, 0))
        icona = None
        icona_ui = None
        colore = None
        grassetto = valore > 0
        if famiglia in ("problematica", "critica") and valore > 0:
            icona = icona_giudizio_criticita(chiave_conteggio)
            icona_ui = (
                "triangle-dashed"
                if famiglia == "problematica"
                else "triangle-alert"
            )
        righe.append(_riga(
            chiave,
            f"{prefisso} {aggettivo} ({spiegazione})",
            valore,
            grassetto=grassetto,
            icona=icona,
            icona_ui=icona_ui,
            colore=colore,
        ))
    return righe


def costruisci_statistiche_generali_coppie(
    assegnatore,
    riutilizzi: dict | None = None,
) -> list[dict]:
    """Costruisce la struttura unica delle statistiche per il modo a coppie."""
    conteggio = conteggio_giudizi_vicinanze(assegnatore)
    if riutilizzi is None:
        riutilizzi = conta_riutilizzate(assegnatore)

    righe = [_riga("totali", "Coppie totali", sum(conteggio.values()))]
    righe.extend(_righe_giudizi("Coppie", conteggio))

    totale_riusi = int(riutilizzi.get("totali", 0))
    riusi_trio = int(riutilizzi.get("trio", 0))
    suffisso = f" (di cui {riusi_trio} nel trio)" if riusi_trio > 0 else ""
    righe.append(_riga(
        "riutilizzate",
        "Coppie riutilizzate",
        totale_riusi,
        grassetto=totale_riusi > 0,
        icona="⚠️" if totale_riusi > 0 else None,
        icona_ui="repeat-2" if totale_riusi > 0 else None,
        colore="ocra" if totale_riusi > 0 else None,
        suffisso=suffisso,
    ))

    # L'adiacenza diretta FISSO-vicino è già compresa nel totale principale.
    # Questa sotto-riga non aggiunge quindi un altro riutilizzo: indica soltanto
    # QUALE studente è tornato nel ruolo di vicino diretto del FISSO.
    if int(riutilizzi.get("vicino_fisso", 0)) > 0:
        nome = riutilizzi.get("vicino_fisso_nome") or "non disponibile"
        righe.append(_dettaglio(
            "dettaglio_vicino_fisso",
            f"Di cui vicino del FISSO: {nome}",
            grassetto=True,
            colore="ocra",
        ))

    if getattr(assegnatore, "trio_identificato", None):
        righe.append(_riga("trio_formato", "Trio formato", 1))

    return righe


def calcola_dati_statistiche_terzetti(
    gruppi,
    motore,
    adiacenze_gia_usate: set | None = None,
) -> dict:
    """Calcola una sola volta composizione, giudizi e riutilizzi dei terzetti.

    Se ``adiacenze_gia_usate`` è fornito, la verità sul riuso viene dalla foto
    esplicita (Annualità riordinata/anteprima). Altrimenti viene dalle note del
    motore, come nel flusso mensile.
    """
    composizione = {
        "terzetti": sum(1 for g in gruppi if g.tipo == TIPO_TERZETTO),
        "quartetti": sum(1 for g in gruppi if g.tipo == TIPO_QUARTETTO),
        "coppie": sum(1 for g in gruppi if g.tipo == TIPO_COPPIA),
    }
    conteggio = {
        "OTTIMA": 0,
        "BUONA": 0,
        "DISCRETA": 0,
        "ACCETTABILE": 0,
        "PROBLEMATICA": 0,
        "CRITICA": 0,
    }
    riutilizzi = 0
    vicini_fisso_riutilizzati = []

    def _riutilizzata(a, b, note) -> bool:
        if adiacenze_gia_usate is None:
            return any("già usata" in n for n in note)
        chiave = tuple(sorted((a.get_nome_completo(), b.get_nome_completo())))
        return chiave in adiacenze_gia_usate

    for gruppo in gruppi:
        for a, b in adiacenze_in_fila(gruppo.membri):
            note = motore.calcola_punteggio_coppia(a, b).get("note", []) or []
            giudizio = giudizio_da_note(note)
            if giudizio in conteggio:
                conteggio[giudizio] += 1

            if not _riutilizzata(a, b, note):
                continue

            riutilizzi += 1
            if getattr(a, "nota_posizione", None) == "FISSO":
                nome_vicino = b.get_nome_completo()
            elif getattr(b, "nota_posizione", None) == "FISSO":
                nome_vicino = a.get_nome_completo()
            else:
                nome_vicino = None

            if nome_vicino and nome_vicino not in vicini_fisso_riutilizzati:
                vicini_fisso_riutilizzati.append(nome_vicino)

    return {
        "composizione": composizione,
        "conteggio": conteggio,
        "riutilizzi": riutilizzi,
        "vicini_fisso_riutilizzati": vicini_fisso_riutilizzati,
    }


def costruisci_statistiche_generali_terzetti(
    gruppi,
    motore,
    adiacenze_gia_usate: set | None = None,
) -> tuple[list[dict], dict]:
    """Costruisce struttura e dati grezzi delle statistiche a terzetti."""
    dati = calcola_dati_statistiche_terzetti(
        gruppi,
        motore,
        adiacenze_gia_usate=adiacenze_gia_usate,
    )
    conteggio = dati["conteggio"]
    composizione = dati["composizione"]
    riutilizzi = int(dati["riutilizzi"])

    righe = [_riga("totali", "Vicinanze totali", sum(conteggio.values()))]
    righe.extend(_righe_giudizi("Vicinanze", conteggio))
    righe.append(_riga(
        "riutilizzate",
        "Vicinanze riutilizzate",
        riutilizzi,
        grassetto=riutilizzi > 0,
        icona="⚠️" if riutilizzi > 0 else None,
        icona_ui="repeat-2" if riutilizzi > 0 else None,
        colore="ocra" if riutilizzi > 0 else None,
    ))

    if dati["vicini_fisso_riutilizzati"]:
        nomi = ", ".join(dati["vicini_fisso_riutilizzati"])
        righe.append(_dettaglio(
            "dettaglio_vicino_fisso",
            f"Di cui vicino del FISSO: {nomi}",
            grassetto=True,
            colore="ocra",
        ))

    righe.append(_riga(
        "terzetti_formati",
        "Terzetti formati",
        int(composizione["terzetti"]),
    ))
    if int(composizione["quartetti"]) > 0:
        righe.append(_riga(
            "quartetti_formati",
            "Quartetti formati",
            int(composizione["quartetti"]),
        ))
    if int(composizione["coppie"]) > 0:
        righe.append(_riga(
            "coppia_residua",
            "Coppia residua",
            int(composizione["coppie"]),
        ))

    return righe, dati


def render_riga_testo(riga: dict) -> str:
    """Renderer testuale di UNA riga strutturata."""
    if riga.get("tipo") == "dettaglio":
        return f"  ↳ {riga.get('testo', '')}"

    icona = riga.get("icona")
    prefisso = f"{icona} " if icona else ""
    suffisso = riga.get("suffisso", "")
    return f"- {prefisso}{riga.get('etichetta', '')}: {riga.get('valore', '')}{suffisso}"


def render_statistiche_testo(righe: Iterable[dict]) -> list[str]:
    """Renderer testuale dell'intera struttura."""
    return [render_riga_testo(riga) for riga in righe]


def render_riga_html(riga: dict) -> str:
    """Renderer HTML di UNA riga, senza emoji incorporate nel testo."""
    riga_senza_icona_testuale = dict(riga)
    riga_senza_icona_testuale["icona"] = None
    testo = escape(render_riga_testo(riga_senza_icona_testuale))
    if riga.get("grassetto"):
        testo = f"<b>{testo}</b>"
    if riga.get("colore") == "ocra":
        testo = f'<span style="color: {C("testo_ocra")};">{testo}</span>'
    return testo


def render_statistiche_html(
    righe: Iterable[dict],
    chiavi: set[str] | None = None,
    solo_positive: bool = False,
) -> list[str]:
    """Renderer HTML, con filtro opzionale usato dalle schede dell'Annuale."""
    risultato = []
    for riga in righe:
        if chiavi is not None and riga.get("chiave") not in chiavi:
            continue
        if solo_positive and riga.get("tipo") == "statistica":
            valore = riga.get("valore")
            if isinstance(valore, (int, float)) and valore <= 0:
                continue
        risultato.append(render_riga_html(riga))
    return risultato


def applica_formattazione_statistiche_generali(text_edit, righe: Iterable[dict]) -> None:
    """Applica al QTextEdit grassetto/ocra leggendo SOLO i metadati delle righe.

    Non interpreta vecchi report e non deduce significati dalle parole: genera
    la riga canonica dalla struttura corrente e formatta esattamente quella.
    """
    documento = text_edit.document()

    for riga in righe or []:
        if not riga.get("grassetto") and not riga.get("colore"):
            continue

        testo = render_riga_testo(riga)
        cursore = QTextCursor(documento)
        cursore.movePosition(QTextCursor.Start)

        while True:
            trovato = documento.find(testo, cursore)
            if trovato.isNull():
                break
            trovato.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
            trovato.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

            formato = QTextCharFormat()
            if riga.get("grassetto"):
                formato.setFontWeight(QFont.Bold)
            if riga.get("colore") == "ocra":
                formato.setForeground(QColor(C("testo_ocra")))
            trovato.mergeCharFormat(formato)
            cursore = trovato

    cursore_iniziale = text_edit.textCursor()
    cursore_iniziale.movePosition(QTextCursor.Start)
    text_edit.setTextCursor(cursore_iniziale)
