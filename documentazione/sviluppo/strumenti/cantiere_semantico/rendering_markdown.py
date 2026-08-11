"""Renderer Markdown puro di ``ANNATA.json`` — incremento I7.

Il renderer legge soltanto campi già presenti nell'output canonico. Non
ricalcola punteggi, riusi, livelli, distanze o massimi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .serializzazione import scrivi_testo_atomico
from .validazione import valida_dati_annata


class ErroreRenderingMarkdown(ValueError):
    """Segnala un JSON non renderizzabile."""


def _testo(valore: Any, assente: str = "—") -> str:
    if valore is None or valore == "":
        return assente
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    return str(valore)


def _tabella(intestazioni: Sequence[str], righe: Sequence[Sequence[Any]]) -> list[str]:
    linee = [
        "| " + " | ".join(intestazioni) + " |",
        "| " + " | ".join("---" for _ in intestazioni) + " |",
    ]
    for riga in righe:
        celle = [str(_testo(x)).replace("|", "\\|").replace("\n", " ") for x in riga]
        linee.append("| " + " | ".join(celle) + " |")
    return linee


def _nomi_evento(evento: Mapping[str, Any]) -> str:
    return f"{evento.get('studente_a', '—')} – {evento.get('studente_b', '—')}"


def _descrizione_riuso(evento: Mapping[str, Any]) -> str:
    if not evento.get("e_riuso"):
        return "prima comparsa"
    numero = evento.get("numero_ripetizione")
    distanza = evento.get("distanza_mesi")
    base = f"ripetizione n. {numero}"
    if distanza is not None:
        return f"{base}; distanza {distanza} mesi"
    origine = (evento.get("ultimo_uso") or {}).get("origine")
    return f"{base}; precedente: {_testo(origine)}"


def rendi_rapporto_markdown(dati: Mapping[str, Any], *, valida: bool = True) -> str:
    """Rende il rapporto leggibile derivato da ``ANNATA.json``."""
    if valida:
        esito = valida_dati_annata(dati)
        if not esito.valido:
            codici = ", ".join(p.codice for p in esito.problemi if p.gravita.value == "errore")
            raise ErroreRenderingMarkdown(f"ANNATA.json non valido: {codici}")

    run = dati["run"]
    ricerca = dati["ricerca"]
    riepilogo = dati["riepilogo"]
    mesi = dati["mesi"]
    studenti = dati["studenti"]
    cronologie = dati["cronologia_adiacenze"]
    genere = dati.get("genere_misto")

    linee: list[str] = [
        "# PostiPerfetti — Osservazione semantica annuale",
        "",
        "## 1. Identità e condizioni del run",
        "",
        *_tabella(
            ("Campo", "Valore"),
            (
                ("Run", run["run_id"]),
                ("Coppia corpus", run["pair_id"]),
                ("Classe", dati["classe"]),
                ("Condizione", run["condizione"]),
                ("Modalità", run["modalita"]),
                ("Seed principale", run["seed_principale"]),
                ("Mesi richiesti", run["numero_mesi"]),
                ("Genere misto attivo", run["genere_misto_attivo"]),
                ("Studente FISSO", dati.get("studente_fisso")),
                ("Stato iniziale", run["stato_iniziale_id"]),
            ),
        ),
        "",
        "## 2. Esito e controlli di validità",
        "",
        f"- Stato del run: **{dati['stato']}**.",
        f"- Mesi prodotti: **{len(mesi)}** su **{run['numero_mesi']}**.",
        f"- Incompatibilità L3 collocate: **{riepilogo['incompatibilita_l3']}**.",
        f"- Strategia osservata: **{dati['versioni']['strategia']}**.",
        "",
        "## 3. Bilancio descrittivo dell’annata",
        "",
        *_tabella(
            ("Fenomeno", "Totale"),
            (
                ("Adiacenze", riepilogo["adiacenze_totali"]),
                ("Riusi", riepilogo["riusi_totali"]),
                ("Prime ripetizioni", riepilogo["prime_ripetizioni"]),
                ("Seconde ripetizioni", riepilogo["seconde_ripetizioni"]),
                ("Terze o ulteriori", riepilogo["terze_o_ulteriori"]),
                ("Incompatibilità L1", riepilogo["incompatibilita_l1"]),
                ("Incompatibilità L2", riepilogo["incompatibilita_l2"]),
                ("Affinità L1", riepilogo["affinita_l1"]),
                ("Affinità L2", riepilogo["affinita_l2"]),
                ("Affinità L3", riepilogo["affinita_l3"]),
                ("Adiacenze miste ottenute", riepilogo["adiacenze_miste"]),
            ),
        ),
        "",
        "## 4. Andamento mese per mese",
        "",
        *_tabella(
            (
                "Mese", "Pos. generazione", "Riusi", "1ª rip.", "2ª rip.",
                "3ª+", "Inc. L1", "Inc. L2", "Aff. L1", "Aff. L2", "Aff. L3", "Miste",
            ),
            tuple(
                (
                    mese["mese_finale"], mese["posizione_generazione"], mese["riepilogo"]["riusi_totali"],
                    mese["riepilogo"]["prime_ripetizioni"], mese["riepilogo"]["seconde_ripetizioni"],
                    mese["riepilogo"]["terze_o_ulteriori"], mese["riepilogo"]["incompatibilita_l1"],
                    mese["riepilogo"]["incompatibilita_l2"], mese["riepilogo"]["affinita_l1"],
                    mese["riepilogo"]["affinita_l2"], mese["riepilogo"]["affinita_l3"],
                    mese["riepilogo"]["adiacenze_miste"],
                )
                for mese in mesi
            ),
        ),
        "",
        "## 5. Cronologia delle adiacenze riutilizzate",
        "",
    ]

    riutilizzate = [c for c in cronologie if c["usi_storico_iniziale"] > 0 or c["numero_occorrenze_annata"] > 1]
    if riutilizzate:
        linee.extend(_tabella(
            ("Adiacenza", "Canale", "Usi iniziali", "Mesi nell’annata", "Distanze interne", "Totale finale"),
            tuple(
                (
                    " – ".join(c["studenti"]), c["canale_rotazione"], c["usi_storico_iniziale"],
                    ", ".join(str(x) for x in c["mesi_occorrenza"]),
                    ", ".join(str(x) for x in c["distanze_interne"]) or "—",
                    c["numero_occorrenze_totali_finali"],
                )
                for c in riutilizzate
            ),
        ))
    else:
        linee.append("Nessuna adiacenza riutilizzata nell’annata osservata.")

    linee.extend(["", "## 6. Incompatibilità concrete L1 e L2", ""])
    incompatibili = [
        (mese["mese_finale"], evento)
        for mese in mesi for evento in mese["adiacenze"]
        if evento["incompatibilita_livello"] in (1, 2)
    ]
    if incompatibili:
        linee.extend(_tabella(
            ("Mese", "Adiacenza", "Livello", "Ruolo", "Riuso"),
            tuple((m, _nomi_evento(e), f"L{e['incompatibilita_livello']}", e["ruolo"], _descrizione_riuso(e)) for m, e in incompatibili),
        ))
    else:
        linee.append("Nessuna incompatibilità L1 o L2 collocata.")

    linee.extend(["", "## 7. Affinità concrete L1, L2 e L3", ""])
    affinita = [
        (mese["mese_finale"], evento)
        for mese in mesi for evento in mese["adiacenze"]
        if evento["affinita_livello"] in (1, 2, 3)
    ]
    if affinita:
        linee.extend(_tabella(
            ("Mese", "Adiacenza", "Livello", "Ruolo"),
            tuple((m, _nomi_evento(e), f"L{e['affinita_livello']}", e["ruolo"]) for m, e in affinita),
        ))
    else:
        linee.append("Nessuna affinità esplicita soddisfatta.")

    linee.extend([
        "", "## 8. Distribuzione dei riusi fra gli studenti", "",
        *_tabella(
            ("Studente", "Riusi", "1ª rip.", "2ª rip.", "3ª+", "Mesi", "Compagni distinti", "Vicino FISSO"),
            tuple(
                (
                    s["studente"], s["riusi_coinvolgenti"], s["prime_ripetizioni"],
                    s["seconde_ripetizioni"], s["terze_o_ulteriori"],
                    ", ".join(str(x) for x in s["mesi_con_riusi"]) or "—",
                    s["compagni_distinti"], s["incarichi_vicino_fisso"],
                )
                for s in studenti
            ),
        ),
        "",
        "Il prospetto è descrittivo: non attribuisce automaticamente un giudizio di equilibrio o squilibrio.",
        "",
        "## 9. Genere misto",
        "",
    ])

    if genere is None:
        linee.append("Analisi di genere misto non disponibile.")
    else:
        if genere["flag_attivo"]:
            linee.append("Il flag «Genere misto» era **attivo**.")
        else:
            linee.append("Il flag «Genere misto» era **disattivo**: i valori sono riportati a solo scopo descrittivo.")
        linee.extend([
            "",
            *_tabella(
                ("Mese", "Massimo geometrico", "Massimo ammissibile L3", "Ottenute", "Stesso genere"),
                tuple(
                    (
                        x["mese"], x["massimo_geometrico"]["valore"], x["massimo_ammissibile"]["valore"],
                        x["adiacenze_miste_ottenute"], x["adiacenze_stesso_genere"],
                    )
                    for x in genere["mesi"]
                ),
            ),
        ])

    linee.extend(["", "## 10. FISSO", ""])
    if dati.get("studente_fisso") is None:
        linee.append("Il run non contiene uno studente FISSO.")
    else:
        linee.append(f"Studente FISSO: **{dati['studente_fisso']}**.")
        vicini = [m.get("vicino_fisso") for m in mesi if m.get("vicino_fisso")]
        if vicini:
            linee.extend(["", *_tabella(
                ("Mese", "Vicino", "Usi precedenti nel ruolo", "Ripetizione", "Distanza"),
                tuple(
                    (
                        mese["mese_finale"], mese["vicino_fisso"].get("studente"),
                        mese["vicino_fisso"].get("usi_precedenti"),
                        mese["vicino_fisso"].get("numero_ripetizione"),
                        mese["vicino_fisso"].get("distanza_mesi"),
                    )
                    for mese in mesi if mese.get("vicino_fisso")
                ),
            )])

    linee.extend([
        "", "## 11. Diagnostica tecnica C1", "",
        *_tabella(
            ("Campo", "Valore"),
            (
                ("Stagioni tentate", ricerca["stagioni_tentate"]),
                ("Stagioni complete", ricerca["stagioni_complete"]),
                ("Indice stagione vincente", ricerca["indice_stagione_vincente"]),
                ("Motivo arresto", ricerca["motivo_arresto"]),
                ("Punteggio tecnico", ricerca["punteggio_tecnico"]),
                ("Durata in secondi", ricerca["durata_secondi"]),
            ),
        ),
        "",
        "Questi valori descrivono il funzionamento tecnico di C1 e non costituiscono un giudizio pedagogico dell’annata.",
        "",
        "## 12. Note sui dati nulli o non calcolabili",
        "",
        "- La distanza mensile è valorizzata soltanto quando il precedente appartiene alla stessa annata.",
        "- Un precedente nello Storico iniziale viene registrato senza inventare una distanza mensile.",
        "- I raggruppamenti delle ripetizioni sono descrittivi e non fissano soglie pedagogiche.",
        "",
    ])
    return "\n".join(linee)


def scrivi_rapporto_markdown(percorso: str | Path, dati: Mapping[str, Any]) -> str:
    testo = rendi_rapporto_markdown(dati)
    return scrivi_testo_atomico(percorso, testo)
