#!/usr/bin/env python3
"""Riepiloga uno o più log JSONL prodotti dal watchdog GUI."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


def percentile(valori: list[float], p: float) -> float:
    if not valori:
        return float("nan")
    ordinati = sorted(valori)
    posizione = (len(ordinati) - 1) * p
    basso = math.floor(posizione)
    alto = math.ceil(posizione)
    if basso == alto:
        return ordinati[basso]
    peso = posizione - basso
    return ordinati[basso] * (1.0 - peso) + ordinati[alto] * peso


def carica(percorso: Path) -> list[dict]:
    record = []
    with percorso.open(encoding="utf-8") as file_obj:
        for numero, riga in enumerate(file_obj, 1):
            riga = riga.strip()
            if not riga:
                continue
            try:
                dato = json.loads(riga)
            except json.JSONDecodeError as errore:
                raise SystemExit(
                    f"{percorso}:{numero}: JSON non valido: {errore}"
                ) from errore
            if dato.get("evento") == "stall":
                dato["_file"] = percorso.name
                record.append(dato)
    return record


def fmt_ms(valore: float) -> str:
    return "n/d" if math.isnan(valore) else f"{valore:.1f} ms"


def tabella_markdown(righe: list[tuple[str, int, float]]) -> str:
    out = ["| Gruppo | Stall | Massimo |", "|---|---:|---:|"]
    for nome, quanti, massimo in righe:
        out.append(f"| {nome} | {quanti} | {massimo:.1f} ms |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", nargs="+", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    record = []
    for percorso in args.log:
        record.extend(carica(percorso))

    valori = [float(r["stall_ms"]) for r in record]
    soglie = {s: sum(v >= s for v in valori) for s in (250, 500, 1000, 5000)}
    gruppi: dict[str, list[float]] = defaultdict(list)
    azioni = Counter()
    for r in record:
        chiave = f"{r.get('operazione')} / {r.get('fase_worker')}"
        gruppi[chiave].append(float(r["stall_ms"]))
        azioni[str(r.get("azione_gui"))] += 1

    righe_gruppi = sorted(
        ((k, len(v), max(v)) for k, v in gruppi.items()),
        key=lambda x: (-x[2], x[0]),
    )

    lines = [
        "# Riepilogo watchdog event loop",
        "",
        f"- file analizzati: {len(args.log)}",
        f"- stall registrati (>= soglia configurata): {len(valori)}",
    ]
    if valori:
        lines.extend([
            f"- minimo: {fmt_ms(min(valori))}",
            f"- mediana: {fmt_ms(median(valori))}",
            f"- p95: {fmt_ms(percentile(valori, 0.95))}",
            f"- p99: {fmt_ms(percentile(valori, 0.99))}",
            f"- massimo: {fmt_ms(max(valori))}",
        ])
    else:
        lines.append("- nessuno stall oltre soglia")

    lines.extend([
        "",
        "## Conteggi per soglia",
        "",
        f"- >= 250 ms: {soglie[250]}",
        f"- >= 500 ms: {soglie[500]}",
        f"- >= 1 s: {soglie[1000]}",
        f"- >= 5 s: {soglie[5000]}",
        "",
        "## Operazione e fase",
        "",
        tabella_markdown(righe_gruppi) if righe_gruppi else "Nessun dato.",
        "",
        "## Azioni GUI associate",
        "",
    ])
    if azioni:
        lines.extend(f"- {nome}: {quanti}" for nome, quanti in azioni.most_common())
    else:
        lines.append("Nessun dato.")

    testo = "\n".join(lines) + "\n"
    print(testo, end="")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(testo, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
