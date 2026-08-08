# -*- coding: utf-8 -*-
"""Attestazione del corpus ufficiale 19×2 della Release Candidate."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Iterator
from zipfile import ZipFile

from moduli.file_classe import carica_file_classe
from strumenti.cantiere_semantico.ambiente import carica_e_valida_coppia_classi
from strumenti.cantiere_semantico.protocollo import carica_protocollo

from .invarianti import firma_semantica_classe, valida_classe_rc
from .modelli import ClasseRC, classe_da_dati_validati


@dataclass(frozen=True, slots=True)
class StatisticheCorpusRC:
    coppie: int
    file_classe: int
    minimo_studenti: int
    massimo_studenti: int
    classi_pari: int
    classi_dispari: int
    classi_con_prima: int
    classi_con_ultima: int
    firme_semantiche: tuple[tuple[str, str], ...]

    def come_dict(self) -> dict:
        return asdict(self)


@contextmanager
def materializza_corpus_zip(archivio: str | Path) -> Iterator[Path]:
    """Estrae in sicurezza il corpus sotto una radice ``corpus/`` temporanea."""
    archivio = Path(archivio)
    with tempfile.TemporaryDirectory(prefix="postiperfetti-validazione-rc-") as temp:
        radice = Path(temp)
        destinazione = radice / "corpus"
        destinazione.mkdir()
        with ZipFile(archivio) as zip_file:
            for info in zip_file.infolist():
                relativo = PurePosixPath(info.filename)
                if relativo.is_absolute() or ".." in relativo.parts:
                    raise ValueError(f"Percorso non sicuro nell'archivio: {info.filename!r}")
                if info.is_dir():
                    continue
                if relativo.name in {"MANIFEST_SHA256.txt", "ATTESTAZIONE_CORPUS_SHA256.json"}:
                    target = radice / relativo.name
                elif relativo.parts and relativo.parts[0] in {"con_fisso", "senza_fisso"}:
                    target = destinazione.joinpath(*relativo.parts)
                else:
                    raise ValueError(f"Voce inattesa nel corpus: {info.filename!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zip_file.read(info))
        yield radice


def _verifica_manifest(radice: Path) -> None:
    manifest = radice / "MANIFEST_SHA256.txt"
    righe = [riga.strip() for riga in manifest.read_text(encoding="utf-8").splitlines() if riga.strip()]
    visti = set()
    for riga in righe:
        digest, relativo = riga.split(maxsplit=1)
        relativo = relativo.strip()
        if relativo in visti:
            raise ValueError(f"Voce duplicata nel manifest: {relativo}")
        visti.add(relativo)
        percorso = radice / "corpus" / relativo
        calcolato = sha256(percorso.read_bytes()).hexdigest()
        if calcolato != digest:
            raise ValueError(f"SHA-256 non valido per {relativo}")
    file_reali = {
        p.relative_to(radice / "corpus").as_posix()
        for p in (radice / "corpus").rglob("*.txt")
    }
    if visti != file_reali:
        mancanti = sorted(file_reali - visti)
        eccedenti = sorted(visti - file_reali)
        raise ValueError(f"Manifest non esaustivo: mancanti={mancanti}, eccedenti={eccedenti}")


def attesta_corpus_ufficiale(
    protocollo_path: str | Path,
    archivio_corpus: str | Path,
) -> StatisticheCorpusRC:
    """Valida integrità, appaiamento e dominio 12–30 dei 38 file ufficiali."""
    protocollo = carica_protocollo(protocollo_path)
    if len(protocollo.coppie) != 19:
        raise ValueError(f"Il corpus RC deve contenere 19 coppie, trovate {len(protocollo.coppie)}.")

    firme: list[tuple[str, str]] = []
    numeri: list[int] = []
    classi_pari = 0
    classi_dispari = 0
    classi_con_prima = 0
    classi_con_ultima = 0

    with materializza_corpus_zip(archivio_corpus) as radice:
        _verifica_manifest(radice)
        for specifica in protocollo.coppie:
            carica_e_valida_coppia_classi(specifica, radice)
            for relativo in (specifica.file_senza_fisso, specifica.file_con_fisso):
                percorso = radice / relativo
                risultato = carica_file_classe(percorso)
                if risultato["formato"] != "COMPLETO":
                    raise ValueError(f"{relativo}: il corpus RC accetta solo il formato COMPLETO.")
                if risultato["avvisi"] or risultato["contraddizioni"] or risultato["discordanze_livello"] or risultato["vincoli_aggiunti"]:
                    raise ValueError(f"{relativo}: il file non è già canonico e bidirezionale.")
                classe = classe_da_dati_validati(
                    specifica.classe,
                    risultato["studenti"],
                    origine=relativo,
                )
                valida_classe_rc(classe)
                firme.append((relativo, firma_semantica_classe(classe)))

            base = carica_file_classe(radice / specifica.file_senza_fisso)
            n = len(base["studenti"])
            numeri.append(n)
            classi_pari += int(n % 2 == 0)
            classi_dispari += int(n % 2 == 1)
            posizioni = {dati["posizione"] for dati in base["studenti"]}
            classi_con_prima += int("PRIMA" in posizioni)
            classi_con_ultima += int("ULTIMA" in posizioni)

    return StatisticheCorpusRC(
        coppie=19,
        file_classe=38,
        minimo_studenti=min(numeri),
        massimo_studenti=max(numeri),
        classi_pari=classi_pari,
        classi_dispari=classi_dispari,
        classi_con_prima=classi_con_prima,
        classi_con_ultima=classi_con_ultima,
        firme_semantiche=tuple(sorted(firme)),
    )


def scrivi_rapporto_corpus(statistiche: StatisticheCorpusRC, destinazione: str | Path) -> None:
    destinazione = Path(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(
        json.dumps(statistiche.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def carica_classi_corpus_ufficiale(
    protocollo_path: str | Path,
    archivio_corpus: str | Path,
) -> tuple[ClasseRC, ...]:
    """Restituisce i 38 casi canonici del corpus dopo l'attestazione completa."""
    # L'attestazione resta il cancello unico: nessun caso viene eseguito se il
    # corpus non coincide con quello dichiarato o contiene dati non canonici.
    attesta_corpus_ufficiale(protocollo_path, archivio_corpus)
    protocollo = carica_protocollo(protocollo_path)
    classi: list[ClasseRC] = []
    with materializza_corpus_zip(archivio_corpus) as radice:
        for specifica in protocollo.coppie:
            for condizione, relativo in (
                ("senza_fisso", specifica.file_senza_fisso),
                ("con_fisso", specifica.file_con_fisso),
            ):
                risultato = carica_file_classe(radice / relativo)
                classi.append(
                    classe_da_dati_validati(
                        specifica.classe,
                        risultato["studenti"],
                        origine=f"corpus_ufficiale:{specifica.pair_id}:{condizione}:{relativo}",
                    )
                )
    return tuple(classi)
