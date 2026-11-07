# -*- coding: utf-8 -*-
"""Diagnostica pura delle assegnazioni Mensile in modalità Personalizzata.

Il modulo non importa Qt, non modifica il motore e non conosce lo Storico.
Legge esclusivamente gruppi e collocazioni fisiche già validati e produce dati
strutturati utili sia ai collaudi sia, in seguito, al report produttivo.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from typing import Any

from moduli.dominio.metrica_pulizia import (
    adiacenze_in_fila,
    coppia_ordinata,
    livello_affinita,
    livello_incompatibilita,
    nome_completo,
)


def _percentuale(parte: int, totale: int) -> float | None:
    if not totale:
        return None
    return 100.0 * parte / totale


def _studenti_da_collocazioni(collocazioni) -> tuple[Any, ...]:
    """Restituisce ogni studente una sola volta, nell'ordine delle collocazioni."""
    visti: set[str] = set()
    studenti: list[Any] = []
    for collocazione in collocazioni:
        for studente in collocazione.gruppo.membri:
            nome = nome_completo(studente)
            if nome not in visti:
                visti.add(nome)
                studenti.append(studente)
    return tuple(studenti)


def _affinita_dichiarate(studenti) -> dict[tuple[str, str], int]:
    """Normalizza le affinità dichiarate come relazioni uniche non direzionali."""
    dichiarate: dict[tuple[str, str], int] = {}
    for studente in studenti:
        nome = nome_completo(studente)
        for altro, livello in getattr(studente, "affinita", {}).items():
            chiave = coppia_ordinata(nome, str(altro))
            dichiarate[chiave] = max(dichiarate.get(chiave, 0), int(livello or 0))
    return dichiarate


def analizza_risultato_mensile_personalizzata(
    risultato: dict[str, Any],
    *,
    genere_misto_attivo: bool,
) -> dict[str, Any]:
    """Analizza le adiacenze reali e i vincoli posizionali del risultato.

    Le adiacenze sono soltanto quelle consecutive all'interno di ciascun blocco:
    in un terzetto A-B-C contano A-B e B-C, mai A-C.
    """
    collocazioni = tuple(risultato.get("collocazioni") or ())
    studenti = _studenti_da_collocazioni(collocazioni)

    posizione = {
        "prima_totali": 0,
        "prima_soddisfatti": 0,
        "prima_non_soddisfatti": [],
        "ultima_totali": 0,
        "ultima_soddisfatti": 0,
        "ultima_non_soddisfatti": [],
        "fisso_totali": 0,
        "fisso_soddisfatti": 0,
        "fisso_non_soddisfatti": [],
    }

    for collocazione in collocazioni:
        blocco = collocazione.blocco
        for posto, studente in collocazione.occupazioni:
            nota = str(getattr(studente, "nota_posizione", "NORMALE")).strip().upper()
            nome = nome_completo(studente)
            if nota == "PRIMA":
                posizione["prima_totali"] += 1
                if blocco.zona_prima:
                    posizione["prima_soddisfatti"] += 1
                else:
                    posizione["prima_non_soddisfatti"].append(nome)
            elif nota == "ULTIMA":
                posizione["ultima_totali"] += 1
                if blocco.zona_ultima:
                    posizione["ultima_soddisfatti"] += 1
                else:
                    posizione["ultima_non_soddisfatti"].append(nome)
            elif nota == "FISSO":
                posizione["fisso_totali"] += 1
                if posto.ancora_fisso:
                    posizione["fisso_soddisfatti"] += 1
                else:
                    posizione["fisso_non_soddisfatti"].append(nome)

    incompatibilita = {1: 0, 2: 0, 3: 0}
    affinita = {1: 0, 2: 0, 3: 0}
    adiacenze: list[tuple[Any, Any]] = []
    aff_osservate: set[tuple[str, str]] = set()
    miste = stesso_genere = genere_sconosciuto = 0

    for collocazione in collocazioni:
        for studente_a, studente_b in adiacenze_in_fila(collocazione.gruppo.membri):
            adiacenze.append((studente_a, studente_b))

            livello_i = int(livello_incompatibilita(studente_a, studente_b))
            if livello_i in incompatibilita:
                incompatibilita[livello_i] += 1

            livello_a = int(livello_affinita(studente_a, studente_b))
            if livello_a in affinita:
                affinita[livello_a] += 1
                aff_osservate.add(coppia_ordinata(
                    nome_completo(studente_a), nome_completo(studente_b)
                ))

            sesso_a = str(getattr(studente_a, "sesso", "")).strip().upper()
            sesso_b = str(getattr(studente_b, "sesso", "")).strip().upper()
            if sesso_a in {"M", "F"} and sesso_b in {"M", "F"}:
                if sesso_a != sesso_b:
                    miste += 1
                else:
                    stesso_genere += 1
            else:
                genere_sconosciuto += 1

    dichiarate = _affinita_dichiarate(studenti)
    coperte = {chiave for chiave in dichiarate if chiave in aff_osservate}
    peso_dichiarato = sum(dichiarate.values())
    peso_coperto = sum(dichiarate[chiave] for chiave in coperte)

    posizione = {
        **posizione,
        "prima_non_soddisfatti": tuple(posizione["prima_non_soddisfatti"]),
        "ultima_non_soddisfatti": tuple(posizione["ultima_non_soddisfatti"]),
        "fisso_non_soddisfatti": tuple(posizione["fisso_non_soddisfatti"]),
    }
    totale_adiacenze = len(adiacenze)
    aff_totali = sum(affinita.values())

    return {
        "adiacenze_totali": totale_adiacenze,
        "posizioni": posizione,
        "incompatibilita": {
            **incompatibilita,
            "totali": sum(incompatibilita.values()),
        },
        "affinita": {
            **affinita,
            "totali": aff_totali,
        },
        "copertura_affinita": {
            "dichiarate_uniche": len(dichiarate),
            "coperte_uniche": len(coperte),
            "percentuale": _percentuale(len(coperte), len(dichiarate)),
            "peso_dichiarato": peso_dichiarato,
            "peso_coperto": peso_coperto,
            "percentuale_pesata": _percentuale(peso_coperto, peso_dichiarato),
        },
        "genere": {
            "flag_attivo": bool(genere_misto_attivo),
            "miste": miste,
            "stesso_genere": stesso_genere,
            "sconosciuto": genere_sconosciuto,
            "percentuale_miste": _percentuale(miste, totale_adiacenze),
        },
        "hard_ok": bool(
            posizione["prima_soddisfatti"] == posizione["prima_totali"]
            and posizione["fisso_soddisfatti"] == posizione["fisso_totali"]
            and incompatibilita[3] == 0
        ),
    }


def _riga_posizione(
    etichetta: str,
    soddisfatti: int,
    totali: int,
    non_soddisfatti: tuple[str, ...],
    *,
    morbida: bool = False,
) -> str:
    if not totali:
        return f"— {etichetta}: non presente"
    if soddisfatti == totali:
        return f"✓ {etichetta}: {soddisfatti}/{totali} soddisfatti"
    icona = "❗" if morbida else "‼️"
    nomi = ", ".join(non_soddisfatti)
    return f"{icona} {etichetta}: {soddisfatti}/{totali} soddisfatti · fuori zona: {nomi}"


def _fmt_percentuale(valore: float | None) -> str:
    return "n/d" if valore is None else f"{valore:.1f}%"


def costruisci_report_diagnostico_personalizzata(
    risultato: dict[str, Any],
    *,
    genere_misto_attivo: bool,
) -> str:
    """Renderizza il report temporaneo P3.1a senza dipendenze Qt."""
    analisi = analizza_risultato_mensile_personalizzata(
        risultato,
        genere_misto_attivo=genere_misto_attivo,
    )
    pos = analisi["posizioni"]
    inc = analisi["incompatibilita"]
    aff = analisi["affinita"]
    cop = analisi["copertura_affinita"]
    gen = analisi["genere"]
    metadati = risultato.get("metadati_casualita") or {}
    gruppi = risultato.get("gruppi") or []
    collocazioni = risultato.get("collocazioni") or []

    righe = [
        "P3.1a — MENSILE PERSONALIZZATA · DIAGNOSTICA",
        "",
        "ESITO POSIZIONI",
        _riga_posizione(
            "PRIMA",
            pos["prima_soddisfatti"], pos["prima_totali"],
            pos["prima_non_soddisfatti"],
        ),
        _riga_posizione(
            "ULTIMA",
            pos["ultima_soddisfatti"], pos["ultima_totali"],
            pos["ultima_non_soddisfatti"],
            morbida=True,
        ),
        _riga_posizione(
            "FISSO",
            pos["fisso_soddisfatti"], pos["fisso_totali"],
            pos["fisso_non_soddisfatti"],
        ),
        "",
        "INCOMPATIBILITÀ TRA ADIACENTI",
        f"L3 obbligatorie: {inc[3]}",
        f"L2: {inc[2]}",
        f"L1: {inc[1]}",
        "",
        "AFFINITÀ TRA ADIACENTI",
        f"Totale: {aff['totali']} · L3: {aff[3]} · L2: {aff[2]} · L1: {aff[1]}",
    ]

    if cop["dichiarate_uniche"]:
        righe.extend((
            "Copertura affinità dichiarate: "
            f"{cop['coperte_uniche']}/{cop['dichiarate_uniche']} "
            f"({_fmt_percentuale(cop['percentuale'])})",
            "Copertura pesata: "
            f"{cop['peso_coperto']}/{cop['peso_dichiarato']} "
            f"({_fmt_percentuale(cop['percentuale_pesata'])})",
        ))
    else:
        righe.append("Copertura affinità dichiarate: nessuna affinità dichiarata")

    righe.extend((
        "",
        "GENERE MISTO",
        f"Preferenza: {'ON' if gen['flag_attivo'] else 'OFF'}",
        f"Adiacenze M/F: {gen['miste']}/{analisi['adiacenze_totali']} "
        f"({_fmt_percentuale(gen['percentuale_miste'])}) · "
        f"stesso genere: {gen['stesso_genere']} · "
        f"genere non noto: {gen['sconosciuto']}",
        "",
        "RICERCA",
        f"Gruppi: {len(gruppi)} · adiacenze reali: {analisi['adiacenze_totali']}",
        f"Tentativo vincente: T{metadati.get('tentativo', '?')}",
        f"Seed principale: {metadati.get('seed_principale', '?')}",
        f"Chiave vincente: {metadati.get('chiave_vincente')}",
        "Riusi: non valutati in P3.1a (Storico Personalizzata non ancora collegato)",
        "",
        "DIAGNOSTICA TECNICA · COLLOCAZIONI FISICHE",
    ))

    for collocazione in collocazioni:
        blocco = collocazione.blocco
        nomi = " | ".join(
            membro.get_nome_completo()
            for membro in collocazione.gruppo.membri
        )
        zone = []
        if blocco.zona_prima:
            zone.append("PRIMA")
        if blocco.zona_ultima:
            zone.append("ULTIMA")
        zona = "+".join(zone) or "neutra"
        righe.append(
            f"- prof={blocco.profondita} col={blocco.colonna} "
            f"blocco={blocco.id} n={blocco.capienza} zona={zona}: {nomi}"
        )

    righe.extend((
        "",
        "Nota P3.1a: questo è ancora un report diagnostico di cantiere. Il report "
        "produttivo Personalizzata adotterà lo stesso formato e la stessa grammatica "
        "visiva di Coppie e Terzetti.",
    ))
    return "\n".join(righe)
