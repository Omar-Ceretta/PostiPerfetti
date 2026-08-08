"""Pubblicazione transazionale degli output di un singolo run — I7."""

from __future__ import annotations

import os
import shutil
import tempfile
import traceback as traceback_modulo
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .modelli import AnnataCanonica, EsitoValidazione, SpecificaRun, StatoRun, congela_valore
from .rendering_markdown import rendi_rapporto_markdown
from .serializzazione import (
    firma_file_sha256,
    leggi_json,
    rendi_json_stabile,
    scrivi_json_atomico,
    scrivi_testo_atomico,
)
from .validazione import ErroreValidazioneOutput, valida_annata, valida_dati_annata


class ErrorePubblicazioneRun(RuntimeError):
    """Segnala una pubblicazione incompleta o non valida."""


@dataclass(frozen=True, slots=True)
class EsitoPubblicazioneRun:
    run_id: str
    directory: str
    annata_json: str
    annata_markdown: str
    validazione_json: str
    sha256_annata_json: str
    sha256_annata_markdown: str
    sha256_validazione_json: str


@dataclass(frozen=True, slots=True)
class RecordFallimentoRun:
    run_id: str
    stato: StatoRun
    fase: str
    messaggio: str
    tipo_errore: str
    seed_principale: int
    parametri: Mapping[str, Any]
    mesi_completati: int = 0
    traceback_tecnico: str | None = None
    data_registrazione_utc: str | None = None
    metadati: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stato not in {StatoRun.FALLITO, StatoRun.PARZIALE, StatoRun.ANNULLATO, StatoRun.INVALIDO}:
            raise ValueError("Un record di fallimento richiede uno stato non completo.")
        for campo in ("run_id", "fase", "messaggio", "tipo_errore"):
            if not str(getattr(self, campo)).strip():
                raise ValueError(f"{campo} non può essere vuoto.")
        if isinstance(self.seed_principale, bool) or not isinstance(self.seed_principale, int):
            raise ValueError("seed_principale deve essere intero.")
        if isinstance(self.mesi_completati, bool) or not isinstance(self.mesi_completati, int) or self.mesi_completati < 0:
            raise ValueError("mesi_completati deve essere un intero non negativo.")
        object.__setattr__(self, "parametri", congela_valore(self.parametri))
        object.__setattr__(self, "metadati", congela_valore(self.metadati))
        if self.data_registrazione_utc is not None and not str(self.data_registrazione_utc).strip():
            raise ValueError("data_registrazione_utc non può essere vuota.")


def _esito_validazione_dati(esito: EsitoValidazione) -> dict[str, Any]:
    return {
        "valido": esito.valido,
        "problemi": [rendi_json_stabile(problema) for problema in esito.problemi],
        "numero_errori": sum(p.gravita.value == "errore" for p in esito.problemi),
        "numero_avvisi": sum(p.gravita.value == "avviso" for p in esito.problemi),
    }


def pubblica_output_run(
    annata: AnnataCanonica,
    directory_destinazione: str | os.PathLike[str],
    *,
    consenti_sostituzione: bool = False,
) -> EsitoPubblicazioneRun:
    """Pubblica ANNATA.json, ANNATA.md e VALIDAZIONE.json in modo transazionale.

    Il JSON viene scritto, riletto da disco e validato come dato non fidato.
    Soltanto dopo il successo di tale controllo viene reso il Markdown e la
    directory temporanea viene rinominata nella destinazione definitiva.
    """
    esito_vivo = valida_annata(annata)
    if not esito_vivo.valido:
        codici = ", ".join(p.codice for p in esito_vivo.problemi if p.gravita.value == "errore")
        raise ErroreValidazioneOutput(f"Annata viva non valida: {codici}")

    destinazione = Path(directory_destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if destinazione.exists() and not consenti_sostituzione:
        raise FileExistsError(f"La directory di output esiste già: {destinazione}")

    temporanea = Path(tempfile.mkdtemp(prefix=f".{destinazione.name}.", dir=destinazione.parent))
    backup: Path | None = None
    try:
        percorso_json = temporanea / "ANNATA.json"
        percorso_md = temporanea / "ANNATA.md"
        percorso_validazione = temporanea / "VALIDAZIONE.json"

        scrivi_json_atomico(percorso_json, annata)
        dati_riletti = leggi_json(percorso_json)
        esito_disco = valida_dati_annata(dati_riletti)
        scrivi_json_atomico(
            percorso_validazione,
            {
                "run_id": annata.run.run_id,
                "fase": "rilettura_annata_json",
                **_esito_validazione_dati(esito_disco),
            },
        )
        if not esito_disco.valido:
            codici = ", ".join(p.codice for p in esito_disco.problemi if p.gravita.value == "errore")
            raise ErroreValidazioneOutput(f"ANNATA.json riletto non valido: {codici}")

        scrivi_testo_atomico(percorso_md, rendi_rapporto_markdown(dati_riletti, valida=False))

        if destinazione.exists():
            backup = destinazione.with_name(f".{destinazione.name}.backup")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destinazione, backup)
        os.replace(temporanea, destinazione)
        if backup is not None:
            shutil.rmtree(backup)

        return EsitoPubblicazioneRun(
            run_id=annata.run.run_id,
            directory=os.fspath(destinazione),
            annata_json=os.fspath(destinazione / "ANNATA.json"),
            annata_markdown=os.fspath(destinazione / "ANNATA.md"),
            validazione_json=os.fspath(destinazione / "VALIDAZIONE.json"),
            sha256_annata_json=firma_file_sha256(destinazione / "ANNATA.json"),
            sha256_annata_markdown=firma_file_sha256(destinazione / "ANNATA.md"),
            sha256_validazione_json=firma_file_sha256(destinazione / "VALIDAZIONE.json"),
        )
    except Exception:
        shutil.rmtree(temporanea, ignore_errors=True)
        if backup is not None and backup.exists() and not destinazione.exists():
            os.replace(backup, destinazione)
        raise


def record_fallimento_da_eccezione(
    run: SpecificaRun,
    *,
    fase: str,
    errore: BaseException,
    stato: StatoRun = StatoRun.FALLITO,
    mesi_completati: int = 0,
    includi_traceback: bool = True,
    data_registrazione_utc: str | None = None,
    metadati: Mapping[str, Any] | None = None,
) -> RecordFallimentoRun:
    """Costruisce un record strutturato a partire da un'eccezione catturata."""
    traceback_tecnico = None
    if includi_traceback:
        traceback_tecnico = "".join(traceback_modulo.format_exception(type(errore), errore, errore.__traceback__))
    if data_registrazione_utc is None:
        data_registrazione_utc = datetime.now(timezone.utc).isoformat()
    return RecordFallimentoRun(
        run_id=run.run_id,
        stato=stato,
        fase=fase,
        messaggio=str(errore) or type(errore).__name__,
        tipo_errore=type(errore).__name__,
        seed_principale=run.seed_principale,
        parametri={
            "modalita": run.modalita.value,
            "condizione": run.condizione.value,
            "numero_mesi": run.numero_mesi,
            "genere_misto_attivo": run.genere_misto_attivo,
            "stato_iniziale_id": run.stato_iniziale_id,
            "parametri_ricerca": rendi_json_stabile(run.parametri_ricerca),
            "parametri_aula": rendi_json_stabile(run.parametri_aula),
        },
        mesi_completati=mesi_completati,
        traceback_tecnico=traceback_tecnico,
        data_registrazione_utc=data_registrazione_utc,
        metadati=metadati or {},
    )


def scrivi_fallimento_run(
    directory_destinazione: str | os.PathLike[str],
    record: RecordFallimentoRun,
    *,
    consenti_sostituzione: bool = False,
) -> str:
    """Scrive atomically una directory con ``FALLIMENTO.json``."""
    destinazione = Path(directory_destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if destinazione.exists() and not consenti_sostituzione:
        raise FileExistsError(f"La directory di fallimento esiste già: {destinazione}")
    temporanea = Path(tempfile.mkdtemp(prefix=f".{destinazione.name}.", dir=destinazione.parent))
    backup: Path | None = None
    try:
        scrivi_json_atomico(temporanea / "FALLIMENTO.json", record)
        dati = leggi_json(temporanea / "FALLIMENTO.json")
        if dati.get("run_id") != record.run_id or dati.get("stato") == "completo":
            raise ErrorePubblicazioneRun("Il record di fallimento riletto è incoerente.")
        if destinazione.exists():
            backup = destinazione.with_name(f".{destinazione.name}.backup")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destinazione, backup)
        os.replace(temporanea, destinazione)
        if backup is not None:
            shutil.rmtree(backup)
        return firma_file_sha256(destinazione / "FALLIMENTO.json")
    except Exception:
        shutil.rmtree(temporanea, ignore_errors=True)
        if backup is not None and backup.exists() and not destinazione.exists():
            os.replace(backup, destinazione)
        raise
