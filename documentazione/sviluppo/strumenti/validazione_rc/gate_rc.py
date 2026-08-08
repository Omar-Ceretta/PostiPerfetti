# -*- coding: utf-8 -*-
"""Gate finale Release Candidate per PostiPerfetti R0.8.

Il gate orchestra prove già validate nelle fasi RC senza duplicarne la logica.
Ogni blocco gira in un sottoprocesso, produce un artefatto separato e contribuisce
al verdetto finale. Il manifest del codice deve restare identico prima/dopo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Iterable


STRESS_STRUTTURALE_TIMEOUT_S = 15
STRESS_STRUTTURALE_PARALLELISMO_MAX = 4


def _parallelismo_stress() -> int:
    """Limita il carico CPU del gate senza trasformare la concorrenza in un falso timeout."""
    return max(1, min(STRESS_STRUTTURALE_PARALLELISMO_MAX, os.cpu_count() or 1))


@dataclass(frozen=True, slots=True)
class EsitoGate:
    id: str
    descrizione: str
    obbligatorio: bool
    stato: str  # PASS / FAIL / SKIP
    durata_s: float
    returncode: int | None
    comando: tuple[str, ...]
    stdout_tail: str = ""
    stderr_tail: str = ""
    rapporto: str | None = None
    motivo: str | None = None


@dataclass(frozen=True, slots=True)
class RapportoGateRC:
    profilo: str
    root: str
    iniziato_utc: str
    concluso_utc: str
    manifest_prima: str
    manifest_dopo: str
    manifest_stabile: bool
    esiti: tuple[EsitoGate, ...]
    verdetto: str

    @property
    def passati(self) -> int:
        return sum(e.stato == "PASS" for e in self.esiti)

    @property
    def falliti(self) -> int:
        return sum(e.stato == "FAIL" for e in self.esiti)

    @property
    def saltati(self) -> int:
        return sum(e.stato == "SKIP" for e in self.esiti)

    def come_dict(self) -> dict:
        return {
            "profilo": self.profilo,
            "root": self.root,
            "iniziato_utc": self.iniziato_utc,
            "concluso_utc": self.concluso_utc,
            "manifest_prima": self.manifest_prima,
            "manifest_dopo": self.manifest_dopo,
            "manifest_stabile": self.manifest_stabile,
            "passati": self.passati,
            "falliti": self.falliti,
            "saltati": self.saltati,
            "verdetto": self.verdetto,
            "esiti": [asdict(e) for e in self.esiti],
        }


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_sorgente(root: Path) -> Iterable[Path]:
    radici = [
        root / "moduli",
        root / "documentazione" / "sviluppo" / "strumenti",
        root / "documentazione" / "sviluppo" / "strumenti_diagnostica",
        root / "documentazione" / "sviluppo" / "test",
    ]
    singoli = [root / "postiperfetti.py"]
    for path in singoli:
        if path.is_file():
            yield path
    for base in radici:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json"}:
                if "__pycache__" not in path.parts:
                    yield path


def manifest_codice(root: Path) -> tuple[str, dict[str, str]]:
    dettaglio: dict[str, str] = {}
    aggregato = hashlib.sha256()
    for path in sorted(_file_sorgente(root), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        dettaglio[rel] = digest
        aggregato.update(rel.encode("utf-8"))
        aggregato.update(b"\0")
        aggregato.update(digest.encode("ascii"))
        aggregato.update(b"\n")
    return aggregato.hexdigest(), dettaglio


def residui_sorgente(root: Path) -> list[str]:
    vietati: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(p in {".git", ".venv", "__pycache__"} for p in rel.parts):
            continue
        nome = path.name
        if nome.endswith((".orig", ".rej")) or nome.endswith("_ORIGINALE.py"):
            vietati.append(rel.as_posix())
    return sorted(vietati)


def _tail(testo: str, righe: int = 14) -> str:
    parti = testo.rstrip().splitlines()
    return "\n".join(parti[-righe:])


def _json_verde(path: Path, predicato: Callable[[dict], bool]) -> tuple[bool, str | None]:
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"rapporto JSON non leggibile: {exc}"
    try:
        ok = bool(predicato(dati))
    except Exception as exc:
        return False, f"validazione rapporto fallita: {exc}"
    return ok, None if ok else "il rapporto non soddisfa il contratto del gate"


def _esegui(
    *,
    root: Path,
    output_dir: Path,
    id_step: str,
    descrizione: str,
    args: list[str],
    obbligatorio: bool = True,
    timeout_s: float | None = None,
    rapporto_nome: str | None = None,
    valida: Callable[[dict], bool] | None = None,
    riusa_rapporto: bool = False,
) -> EsitoGate:
    rapporto = output_dir / rapporto_nome if rapporto_nome else None
    comando = [sys.executable, *args]
    print(f"[GATE] {id_step}: {descrizione}...", flush=True)
    if riusa_rapporto and rapporto is not None and rapporto.is_file() and valida is not None:
        ok, motivo = _json_verde(rapporto, valida)
        if ok:
            print(f"[GATE] {id_step}: PASS (rapporto riusato)", flush=True)
            return EsitoGate(
                id_step, descrizione, obbligatorio, "PASS", 0.0, 0, tuple(comando),
                rapporto=str(rapporto), motivo="rapporto precedente valido riusato",
            )
    start = time.monotonic()
    try:
        env = dict(os.environ)
        pythonpath = [str(root / "documentazione" / "sviluppo"), str(root)]
        if env.get("PYTHONPATH"):
            pythonpath.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
        proc = subprocess.run(
            comando,
            cwd=root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
        durata = time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        return EsitoGate(
            id_step, descrizione, obbligatorio, "FAIL", time.monotonic() - start,
            None, tuple(comando), _tail(exc.stdout or ""), _tail(exc.stderr or ""),
            str(rapporto) if rapporto else None, f"timeout del gate ({timeout_s}s)",
        )

    ok = proc.returncode == 0
    motivo = None if ok else f"exit code {proc.returncode}"
    if ok and rapporto is not None and valida is not None:
        ok, motivo = _json_verde(rapporto, valida)
    print(f"[GATE] {id_step}: {'PASS' if ok else 'FAIL'} ({durata:.2f}s)", flush=True)
    return EsitoGate(
        id_step, descrizione, obbligatorio, "PASS" if ok else "FAIL", durata,
        proc.returncode, tuple(comando), _tail(proc.stdout), _tail(proc.stderr),
        str(rapporto) if rapporto else None, motivo,
    )


def _esito_residui(root: Path) -> EsitoGate:
    start = time.monotonic()
    residui = residui_sorgente(root)
    return EsitoGate(
        "source-residues", "Assenza di residui .orig/.rej/*_ORIGINALE.py",
        True, "PASS" if not residui else "FAIL", time.monotonic() - start, 0 if not residui else 1,
        (), motivo=None if not residui else ", ".join(residui),
    )


def _percorsi_corpus_rc(root: Path) -> tuple[str, str]:
    """Restituisce protocollo e corpus RC completi, entrambi esterni alla root."""
    valore_corpus = os.environ.get("POSTIPERFETTI_CORPUS_RC", "").strip()
    corpus = (
        Path(valore_corpus).expanduser().resolve()
        if valore_corpus
        else (root.parent / "CORPUS_RC_COMPLETO_R0_8.zip").resolve()
    )
    valore_protocollo = os.environ.get("POSTIPERFETTI_PROTOCOLLO_RC", "").strip()
    protocollo = (
        Path(valore_protocollo).expanduser().resolve()
        if valore_protocollo
        else corpus.parent / "PROTOCOLLO_PREFLIGHT_CORPUS_R0_1.json"
    )
    return str(protocollo), str(corpus)


def _aggiungi_precheck(root: Path, out: Path, esiti: list[EsitoGate], *, qt: bool) -> None:
    protocollo_rc, corpus_rc = _percorsi_corpus_rc(root)
    esiti.append(_esito_residui(root))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="compileall", descrizione="Compilazione sorgenti Python",
        args=["-m", "compileall", "-q", "postiperfetti.py", "moduli", "documentazione/sviluppo/strumenti/validazione_rc", "documentazione/sviluppo/test/validazione_rc"],
    ))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="pytest", descrizione="Suite semantica + Validazione RC",
        args=["-m", "pytest", "-q", "documentazione/sviluppo/test/cantiere_semantico", "documentazione/sviluppo/test/validazione_rc"],
    ))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="corpus", descrizione="Attestazione corpus ufficiale 19×2",
        args=["-m", "strumenti.validazione_rc", "attesta-corpus",
              protocollo_rc, corpus_rc,
              "--rapporto", str(out / "01_CORPUS.json")],
        rapporto_nome="01_CORPUS.json",
        valida=lambda d: d.get("coppie") == 19 and d.get("file_classe") == 38
                         and d.get("minimo_studenti", 0) >= 12 and d.get("massimo_studenti", 99) <= 30,
    ))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="gui-fault", descrizione="Macchina a stati GUI + fault injection",
        args=["-m", "strumenti.validazione_rc", "campagna-gui-stati", "--root", str(root),
              "--rapporto", str(out / "02_GUI_FAULT.json")],
        rapporto_nome="02_GUI_FAULT.json",
        valida=lambda d: d.get("verde") is True and d.get("rossi") == 0 and d.get("controlli", 0) >= 78,
    ))
    if qt:
        esiti.append(_esegui(
            root=root, output_dir=out, id_step="qt-smoke", descrizione="Smoke Qt/processi reali",
            args=["-m", "strumenti.validazione_rc.qt_fault_smoke"], timeout_s=30.0,
        ))
    else:
        esiti.append(EsitoGate(
            "qt-smoke", "Smoke Qt/processi reali", True, "SKIP", 0.0, None, (),
            motivo="non richiesto nel profilo PRECHECK",
        ))


def _aggiungi_full(root: Path, out: Path, esiti: list[EsitoGate], *, riprendi: bool = False) -> None:
    protocollo_rc, corpus_rc = _percorsi_corpus_rc(root)
    comune = [protocollo_rc, corpus_rc]
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="mensile-corpus", descrizione="Mensile corpus ufficiale coppie+terzetti",
        args=["-m", "strumenti.validazione_rc", "campagna-corpus", *comune,
              "--seed-base", "20260807", "--candidati", "1", "--rapporto", str(out / "10_MENSILE_CORPUS.json")],
        rapporto_nome="10_MENSILE_CORPUS.json",
        valida=lambda d: d.get("casi") == 76 and d.get("successi") == 76 and d.get("risultati_invalidi") == 0,
         riusa_rapporto=riprendi,
    ))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="annuale-produzione", descrizione="Annuale corpus parametri produttivi",
        args=["-m", "strumenti.validazione_rc", "campagna-annuale", *comune,
              "--seed", "20260807", "--produzione", "--rapporto", str(out / "11_ANNUALE_PRODUZIONE.json")],
        rapporto_nome="11_ANNUALE_PRODUZIONE.json",
        valida=lambda d: d.get("verde") is True and d.get("casi") == 76 and d.get("anomalie") == 0,
         riusa_rapporto=riprendi,
    ))

    # Processi e Storico sono segmentati: impedisce a un singolo batch lungo di nascondere il progresso.
    for start in range(38):
        indici = [start]
        flag_indici = sum((["--indice", str(i)] for i in indici), [])
        nome = f"12_PROCESSI_{start:02d}_{indici[-1]:02d}.json"
        esiti.append(_esegui(
            root=root, output_dir=out, id_step=f"processi-{start:02d}",
            descrizione=f"Differenziale Annuale diretto/processo classi {start}-{indici[-1]}",
            args=["-m", "strumenti.validazione_rc", "campagna-processi-annuale", *comune,
                  "--seed-base", "310000", "--mesi", "3", "--stagioni", "2", *flag_indici,
                  "--rapporto", str(out / nome)],
            rapporto_nome=nome,
            valida=lambda d: d.get("verde") is True and d.get("anomalie") == 0 and d.get("casi", 0) > 0,
            timeout_s=90.0, riusa_rapporto=riprendi,
        ))

    esiti.append(_esegui(
        root=root, output_dir=out, id_step="t4", descrizione="Fallback T4 su dominio 12–30",
        args=["-m", "strumenti.validazione_rc", "campagna-t4", "--seed-base", "600000",
              "--rapporto", str(out / "13_T4.json")],
        rapporto_nome="13_T4.json",
        valida=lambda d: d.get("verde") is True and d.get("casi") == 76 and d.get("anomalie") == 0,
         riusa_rapporto=riprendi,
    ))

    for start in range(38):
        indici = [start]
        flag_indici = sum((["--indice", str(i)] for i in indici), [])
        nome = f"14_STORICO_{start:02d}_{indici[-1]:02d}.json"
        esiti.append(_esegui(
            root=root, output_dir=out, id_step=f"storico-{start:02d}",
            descrizione=f"Storico cumulativo 10 mesi classi {start}-{indici[-1]}",
            args=["-m", "strumenti.validazione_rc", "campagna-storico", *comune,
                  "--seed-base", "700000", "--mesi", "10", *flag_indici,
                  "--rapporto", str(out / nome)],
            rapporto_nome=nome,
            valida=lambda d: d.get("verde") is True and d.get("anomalie") == 0 and d.get("casi", 0) > 0,
            timeout_s=90.0, riusa_rapporto=riprendi,
        ))

    esiti.append(_esegui(
        root=root, output_dir=out, id_step="metamorfica", descrizione="Metamorfismi corpus su tre seed",
        args=["-m", "strumenti.validazione_rc", "campagna-metamorfica", *comune,
              "--seed", "810000", "--seed", "810001", "--seed", "810002",
              "--permutazioni-righe", "3", "--rapporto", str(out / "15_METAMORFICA.json")],
        rapporto_nome="15_METAMORFICA.json",
        valida=lambda d: d.get("verde") is True and d.get("casi") == 1788 and d.get("anomalie") == 0,
         riusa_rapporto=riprendi,
    ))

    for idx, seed in enumerate((20260807, 20260808, 20260809), start=1):
        nome = f"16_FUZZ_{idx}.json"
        esiti.append(_esegui(
            root=root, output_dir=out, id_step=f"fuzz-{idx}", descrizione=f"Property fuzzing seed {seed}",
            args=["-m", "strumenti.validazione_rc", "campagna-fuzz", "--seed-base", str(seed),
                  "--casi-filtri", "2000", "--casi-mensili", "100", "--timeout-mensile", "6",
                  "--parallelismo", "4", "--reperti-dir", str(out / f"reperti_fuzz_{idx}"),
                  "--rapporto", str(out / nome)],
            rapporto_nome=nome,
            valida=lambda d: d.get("verde") is True and not d.get("anomalie")
                             and d.get("timeout_mensili") == 0 and d.get("crash_mensili") == 0,
            timeout_s=180.0, riusa_rapporto=riprendi,
        ))

    esiti.append(_esegui(
        root=root, output_dir=out, id_step="oracolo-standard", descrizione="Oracolo esatto coppie standard",
        args=["-m", "strumenti.validazione_rc", "campagna-oracolo-coppie", "--seed-base", "606000",
              "--casi", "400", "--rapporto", str(out / "17_ORACOLO_STANDARD.json")],
        rapporto_nome="17_ORACOLO_STANDARD.json",
        valida=lambda d: d.get("verde") is True and d.get("casi") == 400 and not d.get("anomalie"),
         riusa_rapporto=riprendi,
    ))
    esiti.append(_esegui(
        root=root, output_dir=out, id_step="oracolo-estremo", descrizione="Oracolo esatto coppie ad alta densità",
        args=["-m", "strumenti.validazione_rc", "campagna-oracolo-coppie", "--seed-base", "606500",
              "--casi", "200", "--estremo", "--rapporto", str(out / "18_ORACOLO_ESTREMO.json")],
        rapporto_nome="18_ORACOLO_ESTREMO.json",
        valida=lambda d: d.get("verde") is True and d.get("casi") == 200 and not d.get("anomalie"),
         riusa_rapporto=riprendi,
    ))

    esiti.append(_esegui(
        root=root, output_dir=out, id_step="mutation", descrizione="Mutation testing completo",
        args=["-m", "strumenti.validazione_rc", "mutation-test", "--root", str(root), "--timeout", "12",
              "--rapporto", str(out / "19_MUTATION.json")],
        rapporto_nome="19_MUTATION.json",
        valida=lambda d: d.get("verde") is True and d.get("mutanti", 0) >= 36
                         and d.get("uccisi") == d.get("mutanti") and d.get("sopravvissuti") == 0,
        timeout_s=300.0, riusa_rapporto=riprendi,
    ))

    esiti.append(_esegui(
        root=root, output_dir=out, id_step="stress-strutturale", descrizione="Stress strutturale 12–30 produzione",
        args=["-m", "strumenti.validazione_rc", "campagna-stress", "--profilo", "strutturale",
              "--seed-base", "20260806", "--ricerca", "produzione", "--semi-per-combinazione", "1",
              "--timeout", str(STRESS_STRUTTURALE_TIMEOUT_S),
              "--parallelismo", str(_parallelismo_stress()),
              "--reperti-dir", str(out / "reperti_stress"),
              "--rapporto", str(out / "20_STRESS_STRUTTURALE.json")],
        rapporto_nome="20_STRESS_STRUTTURALE.json",
        valida=lambda d: d.get("casi") == 304 and d.get("risultati_invalidi") == 0
                         and d.get("timeout") == 0 and d.get("crash") == 0
                         and d.get("successi_validi") == 286 and d.get("fallimenti_motore") == 18,
        timeout_s=240.0, riusa_rapporto=riprendi,
    ))


def esegui_gate_rc(
    root: Path, output_dir: Path, *, profilo: str = "precheck",
    qt: bool | None = None, riprendi: bool = False,
) -> RapportoGateRC:
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if profilo not in {"precheck", "full"}:
        raise ValueError("profilo deve essere 'precheck' oppure 'full'")
    if qt is None:
        qt = profilo == "full"

    iniziato = _utc()
    manifest_prima, dettaglio_prima = manifest_codice(root)
    manifest_file = output_dir / "MANIFEST_PRIMA.json"
    if riprendi and manifest_file.is_file():
        precedente = json.loads(manifest_file.read_text(encoding="utf-8"))
        if precedente.get("sha256") != manifest_prima:
            raise RuntimeError(
                "Impossibile riprendere il gate: il manifest del codice è cambiato "
                f"({precedente.get('sha256')} != {manifest_prima})."
            )
    (output_dir / "MANIFEST_PRIMA.json").write_text(
        json.dumps({"sha256": manifest_prima, "files": dettaglio_prima}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    esiti: list[EsitoGate] = []
    _aggiungi_precheck(root, output_dir, esiti, qt=qt)
    if profilo == "full" and not any(e.stato == "FAIL" and e.obbligatorio for e in esiti):
        _aggiungi_full(root, output_dir, esiti, riprendi=riprendi)

    manifest_dopo, dettaglio_dopo = manifest_codice(root)
    manifest_stabile = manifest_prima == manifest_dopo and dettaglio_prima == dettaglio_dopo
    (output_dir / "MANIFEST_DOPO.json").write_text(
        json.dumps({"sha256": manifest_dopo, "files": dettaglio_dopo}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    obbligatori_falliti = [e for e in esiti if e.obbligatorio and e.stato == "FAIL"]
    obbligatori_saltati = [e for e in esiti if e.obbligatorio and e.stato == "SKIP"]
    if obbligatori_falliti or not manifest_stabile:
        verdetto = "RC_BLOCKED"
    elif profilo != "full" or obbligatori_saltati:
        verdetto = "PRECHECK_PASS"
    else:
        verdetto = "RC_ELIGIBLE"

    rapporto = RapportoGateRC(
        profilo=profilo,
        root=str(root),
        iniziato_utc=iniziato,
        concluso_utc=_utc(),
        manifest_prima=manifest_prima,
        manifest_dopo=manifest_dopo,
        manifest_stabile=manifest_stabile,
        esiti=tuple(esiti),
        verdetto=verdetto,
    )
    return rapporto


def scrivi_rapporto_gate(rapporto: RapportoGateRC, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "GATE_RC.json").write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    righe = [
        "# Gate Release Candidate — PostiPerfetti R0.8",
        "",
        f"**Verdetto: {rapporto.verdetto}**",
        "",
        f"Profilo: `{rapporto.profilo}`  ",
        f"PASS: {rapporto.passati} — FAIL: {rapporto.falliti} — SKIP: {rapporto.saltati}  ",
        f"Manifest stabile: {'SÌ' if rapporto.manifest_stabile else 'NO'}  ",
        f"SHA-256 codice: `{rapporto.manifest_dopo}`",
        "",
        "| ID | Controllo | Stato | Durata s |",
        "|---|---|---:|---:|",
    ]
    for e in rapporto.esiti:
        righe.append(f"| `{e.id}` | {e.descrizione} | **{e.stato}** | {e.durata_s:.3f} |")
    rossi = [e for e in rapporto.esiti if e.stato == "FAIL"]
    if rossi:
        righe.extend(["", "## Blocchi", ""])
        for e in rossi:
            righe.append(f"- `{e.id}`: {e.motivo or e.stderr_tail or e.stdout_tail}")
    (output_dir / "GATE_RC.md").write_text("\n".join(righe) + "\n", encoding="utf-8")
