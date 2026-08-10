# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Watchdog diagnostico, attivabile da ambiente, dell'event loop GUI.

Questo modulo è intenzionalmente estraneo alla semantica di generazione:
non modifica seed, input, opzioni, candidati o risultati. Il timer Qt vive nel
thread GUI; un thread Python ausiliario legge soltanto un heartbeat numerico e,
quando la GUI non lo aggiorna, acquisisce gli stack di tutti i thread.

Variabili d'ambiente:
    POSTIPERFETTI_GUI_WATCHDOG=1
    POSTIPERFETTI_GUI_WATCHDOG_RUN=<etichetta>
    POSTIPERFETTI_GUI_WATCHDOG_INTERVAL_MS=100
    POSTIPERFETTI_GUI_WATCHDOG_STALL_MS=250
    POSTIPERFETTI_GUI_WATCHDOG_STACK_MS=2000
"""

from __future__ import annotations

import faulthandler
import json
import os
import platform
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QAbstractButton, QTabBar

from moduli.percorsi import get_log_path


_TRUE = {"1", "true", "yes", "on", "si", "sì"}


def _env_bool(nome: str, default: bool = False) -> bool:
    valore = os.environ.get(nome)
    if valore is None:
        return default
    return valore.strip().lower() in _TRUE


def _env_int(nome: str, default: int, minimo: int) -> int:
    valore = os.environ.get(nome)
    if valore is None:
        return default
    try:
        return max(minimo, int(valore))
    except (TypeError, ValueError):
        return default


def _etichetta_sicura(valore: str) -> str:
    pulita = re.sub(r"[^A-Za-z0-9_.-]+", "-", valore.strip())
    return pulita.strip("-.") or "run"


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class EventLoopWatchdog(QObject):
    """Misura i ritardi del timer GUI e acquisisce stack durante gli stall."""

    def __init__(self, app: QObject, finestra: QObject):
        super().__init__(app)
        self._app = app
        self._finestra = finestra
        self._interval_ms = _env_int(
            "POSTIPERFETTI_GUI_WATCHDOG_INTERVAL_MS", 100, 20
        )
        self._stall_ms = _env_int(
            "POSTIPERFETTI_GUI_WATCHDOG_STALL_MS", 250, 1
        )
        self._stack_ms = _env_int(
            "POSTIPERFETTI_GUI_WATCHDOG_STACK_MS", 2000, 250
        )
        self._run = _etichetta_sicura(
            os.environ.get("POSTIPERFETTI_GUI_WATCHDOG_RUN", "run")
        )

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._tick)

        self._last_tick = 0.0
        self._heartbeat = 0.0
        self._running = False
        self._stack_dumped_for_stall = False
        self._last_action = "nessuna"
        self._monitor: threading.Thread | None = None

        stem = f"event-loop-watchdog-{self._run}"
        self._pipe_path = Path(get_log_path(f"{stem}.log", crea_genitori=True))
        self._json_path = Path(get_log_path(f"{stem}.jsonl", crea_genitori=True))
        self._stack_path = Path(
            get_log_path(f"event-loop-stackdump-{self._run}.log", crea_genitori=True)
        )
        self._pipe_file = None
        self._json_file = None
        self._stack_file = None

    @property
    def run_label(self) -> str:
        return self._run

    def start(self) -> None:
        """Avvia il watchdog; deve essere chiamato dal thread GUI."""
        if self._running:
            return

        self._pipe_file = self._pipe_path.open("a", encoding="utf-8", buffering=1)
        self._json_file = self._json_path.open("a", encoding="utf-8", buffering=1)
        self._stack_file = self._stack_path.open("a", encoding="utf-8", buffering=1)

        self._running = True
        adesso = time.perf_counter()
        self._last_tick = adesso
        self._heartbeat = adesso
        self._app.installEventFilter(self)

        intestazione = {
            "evento": "watchdog_start",
            "timestamp": _timestamp(),
            "run": self._run,
            "pid": os.getpid(),
            "python": sys.version.split()[0],
            "piattaforma": platform.platform(),
            "switch_interval_s": sys.getswitchinterval(),
            "interval_ms": self._interval_ms,
            "stall_threshold_ms": self._stall_ms,
            "stack_threshold_ms": self._stack_ms,
            "thread_gui_ident": threading.get_ident(),
        }
        self._json_file.write(json.dumps(intestazione, ensure_ascii=False) + "\n")
        self._pipe_file.write(
            "# timestamp | stall_ms | operazione | fase_worker | stagione | mese | azione_gui\n"
        )
        self._pipe_file.write(
            "# watchdog_start " + json.dumps(intestazione, ensure_ascii=False) + "\n"
        )
        self._stack_file.write(
            f"\n{'=' * 78}\nWATCHDOG START {_timestamp()} | run={self._run} | "
            f"pid={os.getpid()}\n"
        )

        self._monitor = threading.Thread(
            target=self._monitor_heartbeat,
            name=f"PostiPerfettiEventLoopWatchdog-{self._run}",
            daemon=True,
        )
        self._monitor.start()
        self._timer.start()

    def stop(self) -> None:
        """Ferma il watchdog e chiude i file di diagnostica."""
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        try:
            self._app.removeEventFilter(self)
        except RuntimeError:
            pass

        if self._monitor is not None and self._monitor.is_alive():
            self._monitor.join(timeout=0.5)

        for file_obj in (self._pipe_file, self._json_file, self._stack_file):
            try:
                if file_obj is not None:
                    file_obj.flush()
                    file_obj.close()
            except Exception:
                pass

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Registra l'ultima azione GUI senza intercettarla."""
        try:
            tipo = event.type()
            if tipo == QEvent.Type.MouseButtonPress:
                self._last_action = self._descrivi_click(watched)
            elif tipo == QEvent.Type.KeyPress:
                key = getattr(event, "key", lambda: None)()
                self._last_action = f"tasto:{key}"
            elif watched is self._finestra and tipo == QEvent.Type.Resize:
                self._last_action = "ridimensiona_finestra"
            elif watched is self._finestra and tipo == QEvent.Type.WindowStateChange:
                self._last_action = "cambia_stato_finestra"
        except Exception:
            # Il watchdog non deve mai interferire con la GUI osservata.
            pass
        return False

    def _descrivi_click(self, watched: QObject) -> str:
        nome = ""
        try:
            nome = watched.objectName() or ""
        except Exception:
            nome = ""

        if isinstance(watched, QTabBar):
            return f"cambio_tab:{nome or 'tabbar'}"

        if isinstance(watched, QAbstractButton):
            try:
                testo = " ".join((watched.text() or "").split())[:80]
            except Exception:
                testo = ""
            return f"click:{nome or testo or watched.__class__.__name__}"

        return f"click:{nome or watched.__class__.__name__}"

    def _stato_operazione(self) -> tuple[str, str, Any, Any]:
        season_worker = getattr(self._finestra, "season_worker", None)
        try:
            annuale_attivo = season_worker is not None and season_worker.isRunning()
        except RuntimeError:
            annuale_attivo = False

        if annuale_attivo:
            classe = season_worker.__class__.__name__
            operazione = (
                "annuale_terzetti"
                if classe == "SeasonWorkerProcessBridgeTerzetti"
                else "annuale_coppie"
            )
            stato_annuale = getattr(
                getattr(self._finestra, "sessione", None), "annuale", None
            )
            fase_obj = getattr(stato_annuale, "fase", "elaborazione")
            fase = getattr(fase_obj, "value", str(fase_obj))
            progresso = getattr(stato_annuale, "progresso", {}) or {}
            return (
                operazione,
                fase,
                progresso.get("tentativo"),
                progresso.get("mese"),
            )

        worker = getattr(self._finestra, "worker_thread", None)
        try:
            mensile_attivo = worker is not None and worker.isRunning()
        except RuntimeError:
            mensile_attivo = False
        if mensile_attivo:
            classe = worker.__class__.__name__
            if classe == "MensileTerzettiProcessBridge":
                return (
                    "mensile_terzetti",
                    "elaborazione_processo",
                    None,
                    1,
                )
            return "mensile_coppie", "calcolo_worker", None, 1

        return "inattiva", "event_loop", None, None

    def _tick(self) -> None:
        adesso = time.perf_counter()
        gap_ms = (adesso - self._last_tick) * 1000.0
        stall_ms = max(0.0, gap_ms - self._interval_ms)
        self._last_tick = adesso
        self._heartbeat = adesso
        self._stack_dumped_for_stall = False

        if stall_ms < self._stall_ms:
            return

        operazione, fase, stagione, mese = self._stato_operazione()
        record = {
            "evento": "stall",
            "timestamp": _timestamp(),
            "run": self._run,
            "stall_ms": round(stall_ms, 3),
            "gap_ms": round(gap_ms, 3),
            "operazione": operazione,
            "fase_worker": fase,
            "stagione": stagione,
            "mese": mese,
            "azione_gui": self._last_action,
            "thread_gui_ident": threading.get_ident(),
        }
        if self._json_file is not None:
            self._json_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self._pipe_file is not None:
            self._pipe_file.write(
                f"{record['timestamp']} | {record['stall_ms']:.3f} | "
                f"{operazione} | {fase} | {stagione} | {mese} | "
                f"{self._last_action}\n"
            )

    def _monitor_heartbeat(self) -> None:
        """Thread non Qt: acquisisce gli stack quando l'heartbeat si arresta."""
        soglia_s = self._stack_ms / 1000.0
        recupero_s = max(0.25, self._interval_ms / 1000.0 * 3)
        while self._running:
            time.sleep(min(0.1, max(0.02, soglia_s / 10)))
            eta = time.perf_counter() - self._heartbeat
            if eta >= soglia_s and not self._stack_dumped_for_stall:
                self._stack_dumped_for_stall = True
                try:
                    if self._stack_file is not None:
                        self._stack_file.write(
                            f"\n{'-' * 78}\nSTACK DUMP {_timestamp()} | "
                            f"run={self._run} | heartbeat_age_ms={eta * 1000:.1f}\n"
                        )
                        self._stack_file.flush()
                        faulthandler.dump_traceback(
                            file=self._stack_file,
                            all_threads=True,
                        )
                        self._stack_file.flush()
                except Exception:
                    pass
            elif eta < recupero_s:
                self._stack_dumped_for_stall = False


def avvia_watchdog_gui_da_ambiente(
    app: QObject, finestra: QObject
) -> EventLoopWatchdog | None:
    """Crea il watchdog soltanto quando l'override diagnostico è attivo."""
    if not _env_bool("POSTIPERFETTI_GUI_WATCHDOG", False):
        return None
    return EventLoopWatchdog(app, finestra)
