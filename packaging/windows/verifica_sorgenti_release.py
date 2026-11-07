# -*- coding: utf-8 -*-
"""Controllo statico, senza dipendenze, dei sorgenti di una release.

Non sostituisce la suite di test funzionali di PostiPerfetti: verifica soltanto
che la copia pubblica sia sintatticamente integra e includa gli asset attesi.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]

FILE_OBBLIGATORI = (
    "postiperfetti.py",
    "requirements.txt",
    "LICENSE",
    "classi/Classe-BASE_esempio.txt",
    "classi/Classe-COMPLETO_esempio.txt",
    "moduli/versione.py",
    "packaging/linux/install.sh",
    "packaging/linux/uninstall.sh",
    "packaging/linux/crea_release_linux.py",
    "packaging/windows/PostiPerfetti.spec",
    "packaging/windows/postiperfetti_setup.iss",
    "packaging/windows/postiperfetti.ico",
    "packaging/windows/info_pre_installazione.txt",
    "packaging/windows/info_dopo_installazione.txt",
)


def main() -> int:
    mancanti = [rel for rel in FILE_OBBLIGATORI if not (ROOT / rel).is_file()]
    for rel in ("moduli", "risorse", "documentazione"):
        if not (ROOT / rel).is_dir():
            mancanti.append(rel + "/")
    if mancanti:
        raise RuntimeError("File o cartelle mancanti: " + ", ".join(mancanti))

    # compile() non scrive .pyc né importa moduli della GUI.
    sorgenti = [ROOT / "postiperfetti.py"]
    sorgenti += sorted((ROOT / "moduli").rglob("*.py"))
    sorgenti += sorted((ROOT / "packaging").rglob("*.py"))
    if len(sorgenti) < 30:
        raise RuntimeError("Struttura dei moduli anomala: pochi sorgenti Python.")
    for sorgente in sorgenti:
        codice = sorgente.read_bytes()
        compile(codice, str(sorgente), "exec")

    versione = runpy.run_path(str(ROOT / "moduli/versione.py"))
    for chiave in ("VERSIONE", "TAG_RELEASE", "VERSIONE_WINDOWS"):
        if chiave not in versione or not versione[chiave]:
            raise RuntimeError(f"Metadato obbligatorio non valido: {chiave}")

    print(f"OK: {len(sorgenti)} sorgenti Python compilabili; "
          "struttura e versione verificate.")
    print("Nota: questo controllo statico non esegue la suite pytest.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERRORE verifica sorgenti: {exc}", file=sys.stderr)
        sys.exit(1)
