# -*- coding: utf-8 -*-
"""Stress RC isolato: un processo, un timeout e un reperto per ogni caso."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

from moduli.file_classe import serializza_file_classe

from .generatori import dati_validati_da_classe, genera_classe_sintetica


FAMIGLIE_STRESS = ("stella", "due_blocchi", "quasi_clique", "clique_sovrabbondante")
PROFILI_STRESS = {
    # Piccolo ma rappresentativo: estremi, pari/dispari, centro del dominio.
    "pilot": (12, 17, 24, 30),
    # Copertura completa del dominio scolastico concordato.
    "strutturale": tuple(range(12, 31)),
}

PROFILI_RICERCA = {
    # Sonda economica: utile per localizzare rapidamente zone combinatorie dure.
    "minima": {"coppie": 1, "terzetti": 1},
    # Valori effettivamente usati dal programma produttivo.
    "produzione": {"coppie": 10, "terzetti": 3},
}

STATI_STRESS = {
    "successo_valido",
    "fallimento_motore",
    "risultato_invalido",
    "timeout",
    "crash",
}

_PROCESSI_ATTIVI: set[subprocess.Popen] = set()
_LOCK_PROCESSI_ATTIVI = threading.Lock()


def termina_processi_isolati_attivi() -> None:
    """Termina tutti i worker ancora registrati dal supervisore corrente."""
    with _LOCK_PROCESSI_ATTIVI:
        processi = tuple(_PROCESSI_ATTIVI)
    for processo in processi:
        _termina_gruppo(processo)


@dataclass(frozen=True, slots=True)
class CasoStressRC:
    id_caso: str
    studenti: int
    famiglia: str
    fisso: bool
    modalita: str
    seed_classe: int
    seed_motore: int
    num_candidati: int = 1

    def come_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EsitoStressRC:
    caso: CasoStressRC
    stato: str
    durata_s: float
    exit_code: int | None
    violazioni: tuple[str, ...] = ()
    errore: str | None = None
    reperto_classe: str | None = None
    reperto_esito: str | None = None

    @property
    def rosso_correttezza(self) -> bool:
        return self.stato in {"risultato_invalido", "crash"}

    @property
    def da_qualificare(self) -> bool:
        return self.stato in {"fallimento_motore", "timeout"}

    def come_dict(self) -> dict:
        dati = asdict(self)
        dati["caso"] = self.caso.come_dict()
        dati["rosso_correttezza"] = self.rosso_correttezza
        dati["da_qualificare"] = self.da_qualificare
        return dati


@dataclass(frozen=True, slots=True)
class RapportoStressRC:
    profilo: str
    profilo_ricerca: str
    timeout_s: float
    parallelismo: int
    casi: int
    successi_validi: int
    fallimenti_motore: int
    risultati_invalidi: int
    timeout: int
    crash: int
    durata_totale_s: float
    dettaglio: tuple[EsitoStressRC, ...]

    @property
    def verde_correttezza(self) -> bool:
        return self.risultati_invalidi == 0 and self.crash == 0

    def come_dict(self) -> dict:
        return {
            "profilo": self.profilo,
            "profilo_ricerca": self.profilo_ricerca,
            "timeout_s": self.timeout_s,
            "parallelismo": self.parallelismo,
            "casi": self.casi,
            "successi_validi": self.successi_validi,
            "fallimenti_motore": self.fallimenti_motore,
            "risultati_invalidi": self.risultati_invalidi,
            "timeout": self.timeout,
            "crash": self.crash,
            "durata_totale_s": round(self.durata_totale_s, 6),
            "verde_correttezza": self.verde_correttezza,
            "dettaglio": [e.come_dict() for e in self.dettaglio],
        }


def costruisci_casi_stress(
    *,
    profilo: str,
    seed_base: int,
    profilo_ricerca: str = "produzione",
    semi_per_combinazione: int = 1,
    famiglie: tuple[str, ...] | None = None,
    minimo_studenti: int | None = None,
    massimo_studenti: int | None = None,
) -> tuple[CasoStressRC, ...]:
    if profilo not in PROFILI_STRESS:
        raise ValueError(f"Profilo stress sconosciuto: {profilo!r}")
    if semi_per_combinazione < 1:
        raise ValueError("semi_per_combinazione deve essere >= 1")
    if profilo_ricerca not in PROFILI_RICERCA:
        raise ValueError(f"Profilo ricerca sconosciuto: {profilo_ricerca!r}")

    famiglie_effettive = tuple(famiglie or FAMIGLIE_STRESS)
    sconosciute = sorted(set(famiglie_effettive) - set(FAMIGLIE_STRESS))
    if sconosciute:
        raise ValueError(f"Famiglie stress sconosciute: {sconosciute}")
    dimensioni = tuple(
        n for n in PROFILI_STRESS[profilo]
        if (minimo_studenti is None or n >= minimo_studenti)
        and (massimo_studenti is None or n <= massimo_studenti)
    )
    if not dimensioni:
        raise ValueError("Il filtro dimensionale non seleziona alcuna classe.")

    casi: list[CasoStressRC] = []
    indice = 0
    for famiglia in famiglie_effettive:
        for n in dimensioni:
            for fisso in (False, True):
                for modalita in ("coppie", "terzetti"):
                    for replica in range(semi_per_combinazione):
                        indice += 1
                        # I due semi hanno progressioni diverse per evitare correlazioni accidentali.
                        seed_classe = seed_base + indice * 17 + replica * 104729
                        seed_motore = seed_base + indice * 1009 + replica * 130363
                        casi.append(
                            CasoStressRC(
                                id_caso=f"{profilo}-{indice:05d}",
                                studenti=n,
                                famiglia=famiglia,
                                fisso=fisso,
                                modalita=modalita,
                                seed_classe=seed_classe,
                                seed_motore=seed_motore,
                                num_candidati=PROFILI_RICERCA[profilo_ricerca][modalita],
                            )
                        )
    return tuple(casi)


def _termina_gruppo(processo: subprocess.Popen) -> None:
    if processo.poll() is not None:
        return
    try:
        os.killpg(processo.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except Exception:
        processo.kill()


def esegui_comando_isolato(
    comando: list[str],
    *,
    timeout_s: float,
    cwd: str | Path,
) -> tuple[str, int | None, float, str, str]:
    """Esegue un comando in un proprio process group.

    Restituisce (stato_processuale, exit_code, durata, stdout, stderr), dove
    stato_processuale è ``completato`` oppure ``timeout``.
    """
    if timeout_s <= 0:
        raise ValueError("timeout_s deve essere > 0")
    inizio = time.monotonic()
    cwd_path = Path(cwd).resolve()
    ambiente = dict(os.environ)
    documentazione = cwd_path / "documentazione" / "sviluppo"
    pythonpath = [str(cwd_path)]
    if documentazione.is_dir():
        pythonpath.insert(0, str(documentazione))
    if ambiente.get("PYTHONPATH"):
        pythonpath.append(ambiente["PYTHONPATH"])
    ambiente["PYTHONPATH"] = os.pathsep.join(pythonpath)
    processo = subprocess.Popen(
        comando,
        cwd=str(cwd_path),
        env=ambiente,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    with _LOCK_PROCESSI_ATTIVI:
        _PROCESSI_ATTIVI.add(processo)
    try:
        try:
            stdout, stderr = processo.communicate(timeout=timeout_s)
            durata = time.monotonic() - inizio
            return "completato", processo.returncode, durata, stdout, stderr
        except subprocess.TimeoutExpired:
            _termina_gruppo(processo)
            stdout, stderr = processo.communicate()
            durata = time.monotonic() - inizio
            return "timeout", None, durata, stdout, stderr
    finally:
        with _LOCK_PROCESSI_ATTIVI:
            _PROCESSI_ATTIVI.discard(processo)


def _scrivi_reperto_classe(caso: CasoStressRC, reperti_dir: Path) -> Path:
    classe = genera_classe_sintetica(
        caso.studenti,
        seed=caso.seed_classe,
        famiglia=caso.famiglia,
        con_fisso=caso.fisso,
    )
    contenuto = serializza_file_classe(classe.nome, dati_validati_da_classe(classe))
    destinazione = reperti_dir / f"{caso.id_caso}.txt"
    destinazione.write_text(contenuto + "\n", encoding="utf-8")
    return destinazione


def esegui_caso_stress_isolato(
    caso: CasoStressRC,
    *,
    timeout_s: float,
    radice_progetto: str | Path,
    reperti_dir: str | Path | None = None,
) -> EsitoStressRC:
    radice = Path(radice_progetto).resolve()
    reperti = Path(reperti_dir).resolve() if reperti_dir else None
    if reperti:
        reperti.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="postiperfetti-rc-stress-") as tmp:
        tmp_path = Path(tmp)
        spec_path = tmp_path / "caso.json"
        out_path = tmp_path / "esito.json"
        spec_path.write_text(
            json.dumps(caso.come_dict(), ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comando = [
            sys.executable,
            "-m",
            "strumenti.validazione_rc.worker_stress",
            "--spec",
            str(spec_path),
            "--out",
            str(out_path),
        ]
        stato_proc, exit_code, durata, stdout, stderr = esegui_comando_isolato(
            comando,
            timeout_s=timeout_s,
            cwd=radice,
        )

        if stato_proc == "timeout":
            stato = "timeout"
            errore = (stderr or stdout or None)
            payload = None
        elif out_path.exists():
            try:
                payload = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception as exc:
                payload = None
                stato = "crash"
                errore = f"Esito worker illeggibile: {exc}; stderr={stderr!r}; stdout={stdout!r}"
            else:
                stato = str(payload.get("stato", "crash"))
                errore = payload.get("errore")
                if stato not in STATI_STRESS:
                    stato = "crash"
                    errore = f"Stato worker sconosciuto: {payload!r}"
        else:
            payload = None
            stato = "crash"
            errore = f"Worker senza esito; exit={exit_code}; stderr={stderr!r}; stdout={stdout!r}"

        violazioni = tuple((payload or {}).get("violazioni", ()))
        reperto_classe = None
        reperto_esito = None
        if reperti is not None and stato != "successo_valido":
            classe_path = _scrivi_reperto_classe(caso, reperti)
            reperto_classe = str(classe_path)
            esito_path = reperti / f"{caso.id_caso}.json"
            esito_path.write_text(
                json.dumps(
                    {
                        "caso": caso.come_dict(),
                        "stato": stato,
                        "durata_s": durata,
                        "exit_code": exit_code,
                        "violazioni": list(violazioni),
                        "errore": errore,
                        "stdout": stdout,
                        "stderr": stderr,
                        "payload_worker": payload,
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            reperto_esito = str(esito_path)

        return EsitoStressRC(
            caso=caso,
            stato=stato,
            durata_s=round(durata, 6),
            exit_code=exit_code,
            violazioni=violazioni,
            errore=errore,
            reperto_classe=reperto_classe,
            reperto_esito=reperto_esito,
        )


def _leggi_checkpoint(path: str | Path | None) -> dict[str, EsitoStressRC]:
    if path is None:
        return {}
    path = Path(path)
    if not path.exists():
        return {}
    risultato: dict[str, EsitoStressRC] = {}
    for numero, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not riga.strip():
            continue
        raw = json.loads(riga)
        caso = CasoStressRC(**raw["caso"])
        risultato[caso.id_caso] = EsitoStressRC(
            caso=caso,
            stato=raw["stato"],
            durata_s=float(raw["durata_s"]),
            exit_code=raw.get("exit_code"),
            violazioni=tuple(raw.get("violazioni", ())),
            errore=raw.get("errore"),
            reperto_classe=raw.get("reperto_classe"),
            reperto_esito=raw.get("reperto_esito"),
        )
    return risultato


def _append_checkpoint(path: str | Path, esito: EsitoStressRC) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(esito.come_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def esegui_campagna_stress(
    *,
    profilo: str,
    seed_base: int = 20260806,
    profilo_ricerca: str = "produzione",
    semi_per_combinazione: int = 1,
    timeout_s: float = 3.0,
    parallelismo: int = 4,
    radice_progetto: str | Path = ".",
    reperti_dir: str | Path | None = None,
    famiglie: tuple[str, ...] | None = None,
    minimo_studenti: int | None = None,
    massimo_studenti: int | None = None,
    checkpoint_path: str | Path | None = None,
    riprendi: bool = False,
) -> RapportoStressRC:
    if parallelismo < 1:
        raise ValueError("parallelismo deve essere >= 1")
    casi = costruisci_casi_stress(
        profilo=profilo,
        seed_base=seed_base,
        profilo_ricerca=profilo_ricerca,
        semi_per_combinazione=semi_per_combinazione,
        famiglie=famiglie,
        minimo_studenti=minimo_studenti,
        massimo_studenti=massimo_studenti,
    )
    inizio = time.monotonic()

    def _esegui(caso: CasoStressRC) -> EsitoStressRC:
        return esegui_caso_stress_isolato(
            caso,
            timeout_s=timeout_s,
            radice_progetto=radice_progetto,
            reperti_dir=reperti_dir,
        )

    gia_eseguiti = _leggi_checkpoint(checkpoint_path) if riprendi else {}
    if checkpoint_path is not None and not riprendi:
        Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
        Path(checkpoint_path).write_text("", encoding="utf-8")

    esiti_per_id: dict[str, EsitoStressRC] = {
        caso_id: esito for caso_id, esito in gia_eseguiti.items()
        if any(c.id_caso == caso_id and c == esito.caso for c in casi)
    }
    pendenti = [caso for caso in casi if caso.id_caso not in esiti_per_id]

    # Thread soltanto come supervisori: il lavoro algoritmico resta in processi
    # separati e ciascun processo conserva il proprio timeout/kill group.
    try:
        with ThreadPoolExecutor(max_workers=parallelismo, thread_name_prefix="rc-stress") as pool:
            futuri = {pool.submit(_esegui, caso): caso for caso in pendenti}
            for futuro in as_completed(futuri):
                esito = futuro.result()
                esiti_per_id[esito.caso.id_caso] = esito
                if checkpoint_path is not None:
                    _append_checkpoint(checkpoint_path, esito)
    except BaseException:
        termina_processi_isolati_attivi()
        raise

    # Il rapporto finale torna sempre nell'ordine canonico dei casi, anche se
    # i processi sono terminati in ordine diverso.
    esiti = tuple(esiti_per_id[caso.id_caso] for caso in casi)

    conteggi = {stato: 0 for stato in STATI_STRESS}
    for esito in esiti:
        conteggi[esito.stato] += 1
    return RapportoStressRC(
        profilo=profilo,
        profilo_ricerca=profilo_ricerca,
        timeout_s=timeout_s,
        parallelismo=parallelismo,
        casi=len(esiti),
        successi_validi=conteggi["successo_valido"],
        fallimenti_motore=conteggi["fallimento_motore"],
        risultati_invalidi=conteggi["risultato_invalido"],
        timeout=conteggi["timeout"],
        crash=conteggi["crash"],
        durata_totale_s=round(time.monotonic() - inizio, 6),
        dettaglio=esiti,
    )


def scrivi_rapporto_stress(rapporto: RapportoStressRC, destinazione: str | Path) -> None:
    destinazione = Path(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
