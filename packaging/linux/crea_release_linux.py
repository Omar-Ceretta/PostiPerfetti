# -*- coding: utf-8 -*-
"""Genera gli asset Linux di una release di PostiPerfetti."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
import runpy
import shutil
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PACKAGING_LINUX = Path(__file__).resolve().parent
DIST = ROOT / "dist-linux"

FILE_VERSIONE = ROOT / "moduli" / "versione.py"
INSTALLER_SORGENTE = PACKAGING_LINUX / "install.sh"
UNINSTALLER_SORGENTE = PACKAGING_LINUX / "uninstall.sh"

ESEMPI_CLASSI = (
    "Classe-BASE_esempio.txt",
    "Classe-COMPLETO_esempio.txt",
)


def sha256_file(percorso: Path) -> str:
    digest = hashlib.sha256()

    with percorso.open("rb") as file:
        for blocco in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(blocco)

    return digest.hexdigest()


def copia_albero(sorgente: Path, destinazione: Path) -> None:
    shutil.copytree(
        sorgente,
        destinazione,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.bak",
            "*.bak*",
        ),
    )


def normalizza_tar(info: tarfile.TarInfo) -> tarfile.TarInfo:
    """Elimina metadati locali inutili dal pacchetto distribuito."""
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0

    if info.isdir():
        info.mode = 0o755
    elif info.name.endswith("/uninstall.sh"):
        info.mode = 0o755
    elif info.name.endswith("/moduli/postiperfetti_launcher.py"):
        info.mode = 0o755
    else:
        info.mode = 0o644

    return info


def sostituisci_unica(
    testo: str,
    vecchio: str,
    nuovo: str,
) -> str:
    occorrenze = testo.count(vecchio)

    if occorrenze != 1:
        raise RuntimeError(
            f"Attesa una sola occorrenza di {vecchio!r}; "
            f"trovate: {occorrenze}"
        )

    return testo.replace(vecchio, nuovo, 1)


def main() -> int:
    dati_versione = runpy.run_path(str(FILE_VERSIONE))

    versione = dati_versione["VERSIONE"]
    tag = dati_versione["TAG_RELEASE"]

    nome_pacchetto = f"PostiPerfetti-{versione}-linux.tar.gz"
    nome_radice = f"PostiPerfetti-{versione}-linux"

    url_pacchetto = (
        "https://github.com/Omar-Ceretta/PostiPerfetti/"
        f"releases/download/{tag}/{nome_pacchetto}"
    )

    DIST.mkdir(parents=True, exist_ok=True)

    # Non lasciamo asset appartenenti a una build precedente.
    for percorso in DIST.iterdir():
        if percorso.is_dir():
            shutil.rmtree(percorso)
        else:
            percorso.unlink()

    pacchetto = DIST / nome_pacchetto
    installer_dest = DIST / "install.sh"

    with tempfile.TemporaryDirectory(
        prefix="postiperfetti-release-linux-"
    ) as temp:
        radice = Path(temp) / nome_radice
        radice.mkdir()

        copia_albero(ROOT / "moduli", radice / "moduli")
        copia_albero(ROOT / "risorse", radice / "risorse")

        for nome in (
            "postiperfetti.py",
            "requirements.txt",
            "LICENSE",
        ):
            shutil.copy2(ROOT / nome, radice / nome)

        cartella_classi = radice / "classi"
        cartella_classi.mkdir()

        for nome in ESEMPI_CLASSI:
            sorgente = ROOT / "classi" / nome

            if not sorgente.is_file():
                raise RuntimeError(
                    f"File-classe di esempio mancante: {sorgente}"
                )

            shutil.copy2(
                sorgente,
                cartella_classi / nome,
            )

        shutil.copy2(
            UNINSTALLER_SORGENTE,
            radice / "uninstall.sh",
        )

        # gzip con timestamp normalizzato: a parità di contenuti evitiamo
        # almeno la variabilità introdotta dalla data nel suo header.
        with pacchetto.open("wb") as file_grezzo:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=file_grezzo,
                compresslevel=9,
                mtime=0,
            ) as gzip_file:
                with tarfile.open(
                    fileobj=gzip_file,
                    mode="w",
                ) as archivio:
                    archivio.add(
                        radice,
                        arcname=nome_radice,
                        recursive=True,
                        filter=normalizza_tar,
                    )

    sha_pacchetto = sha256_file(pacchetto)

    testo_installer = INSTALLER_SORGENTE.read_text(
        encoding="utf-8"
    )

    testo_installer = sostituisci_unica(
        testo_installer,
        "MODALITA_RELEASE=0",
        "MODALITA_RELEASE=1",
    )
    testo_installer = sostituisci_unica(
        testo_installer,
        'VERSIONE_RELEASE=""',
        f'VERSIONE_RELEASE="{versione}"',
    )
    testo_installer = sostituisci_unica(
        testo_installer,
        (
            'URL_TARBALL="https://github.com/Omar-Ceretta/'
            'PostiPerfetti/archive/refs/heads/main.tar.gz"'
        ),
        f'URL_TARBALL="{url_pacchetto}"',
    )
    testo_installer = sostituisci_unica(
        testo_installer,
        'SHA256_ATTESO=""',
        f'SHA256_ATTESO="{sha_pacchetto}"',
    )

    installer_dest.write_text(
        testo_installer,
        encoding="utf-8",
        newline="\n",
    )

    try:
        installer_dest.chmod(0o755)
    except OSError:
        # Su Windows il bit Unix non è significativo.
        pass

    sha_installer = sha256_file(installer_dest)

    file_somme = DIST / "SHA256SUMS"
    file_somme.write_text(
        f"{sha_pacchetto}  {nome_pacchetto}\n"
        f"{sha_installer}  install.sh\n",
        encoding="utf-8",
        newline="\n",
    )

    print()
    print("Release Linux preparata")
    print("========================")
    print(f"Versione : {versione}")
    print(f"Tag      : {tag}")
    print()
    print(f"Pacchetto: {pacchetto}")
    print(f"SHA-256  : {sha_pacchetto}")
    print()
    print(f"Installer: {installer_dest}")
    print(f"SHA-256  : {sha_installer}")
    print()
    print(f"Checksum : {file_somme}")
    print()
    print(
        "Questi tre file sono gli asset Linux da pubblicare "
        "nella Release."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
