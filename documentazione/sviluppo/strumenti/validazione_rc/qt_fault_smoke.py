# -*- coding: utf-8 -*-
"""Smoke Qt locale del ciclo di vita dei bridge a processo della RC.

Va eseguito nell'ambiente reale di PostiPerfetti, dove PySide6 e' installato.
Non usa finestre: QCoreApplication basta a collaudare segnali, QThread, spawn,
EOF del Pipe e spegnimento finito dei processi figli.
"""

from __future__ import annotations

import multiprocessing
import os
import pickle
import time

from PySide6.QtCore import QCoreApplication, QTimer, Signal

from moduli.ponte_processo import PonteProcessoQtBase


def _figlio_normale(_payload: bytes, connessione) -> None:
    try:
        connessione.send({"tipo": "risultato", "pid": os.getpid()})
    finally:
        connessione.close()


def _figlio_terminale_poi_appeso(_payload: bytes, connessione) -> None:
    try:
        connessione.send({"tipo": "risultato", "pid": os.getpid()})
        time.sleep(60.0)
    finally:
        try:
            connessione.close()
        except Exception:
            pass


def _figlio_chiude_canale_poi_appeso(_payload: bytes, connessione) -> None:
    connessione.send({"tipo": "pid", "pid": os.getpid()})
    connessione.close()
    time.sleep(60.0)


class _BridgeSmoke(PonteProcessoQtBase):
    terminale = Signal(object)
    error_occurred = Signal(str, object)

    def __init__(self, target, nome):
        self.pid_figlio = None
        super().__init__(
            {"smoke": True},
            target_processo=target,
            nome_processo=nome,
            descrizione=nome,
        )

    def _gestisci_messaggio(self, messaggio: dict) -> bool:
        if messaggio.get("pid"):
            self.pid_figlio = int(messaggio["pid"])
        if messaggio.get("tipo") == "risultato":
            self.terminale.emit(messaggio)
            return True
        return False


def _pid_esiste(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _esegui_scenario(app: QCoreApplication, nome: str, target, *, attende_terminale: bool) -> tuple[bool, str]:
    bridge = _BridgeSmoke(target, f"RC-{nome}")
    terminali = []
    errori = []
    concluso = {"ok": False, "timeout": False}

    bridge.terminale.connect(lambda msg: terminali.append(dict(msg)))
    bridge.error_occurred.connect(lambda msg, _report: errori.append(str(msg)))
    bridge.finished.connect(lambda: (concluso.__setitem__("ok", True), app.quit()))

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: (concluso.__setitem__("timeout", True), app.quit()))
    timer.start(6000)
    bridge.start()
    app.exec()
    timer.stop()

    # Se lo smoke stesso e' scaduto, evita di lasciare il QThread vivo.
    if concluso["timeout"] and bridge.isRunning():
        processo = getattr(bridge, "_processo", None)
        try:
            if processo is not None and processo.is_alive():
                processo.terminate()
                processo.join(timeout=1.0)
                if processo.is_alive() and hasattr(processo, "kill"):
                    processo.kill()
                    processo.join(timeout=1.0)
        except Exception:
            pass
        bridge.wait(2000)
        return False, "timeout del bridge oltre 6 s"

    pid = bridge.pid_figlio
    if attende_terminale:
        ok = concluso["ok"] and len(terminali) == 1 and not errori and not _pid_esiste(pid)
    else:
        ok = (
            concluso["ok"] and not terminali and len(errori) == 1
            and not _pid_esiste(pid)
        )

    dettaglio = (
        f"finished={concluso['ok']}, terminali={len(terminali)}, "
        f"errori={len(errori)}, pid_vivo={_pid_esiste(pid)}"
    )
    return ok, dettaglio


def main() -> int:
    # Lo spawn deve poter reimportare il modulo senza creare una GUI.
    multiprocessing.freeze_support()
    app = QCoreApplication.instance() or QCoreApplication([])
    scenari = (
        ("normale", _figlio_normale, True),
        ("terminale_poi_appeso", _figlio_terminale_poi_appeso, True),
        ("canale_perso", _figlio_chiude_canale_poi_appeso, False),
    )
    rossi = []
    for nome, target, attende_terminale in scenari:
        ok, dettaglio = _esegui_scenario(
            app, nome, target, attende_terminale=attende_terminale
        )
        print(f"{'OK' if ok else 'ROSSO'}  {nome}: {dettaglio}")
        if not ok:
            rossi.append(nome)

    print(
        f"Smoke Qt/processi RC: {len(scenari) - len(rossi)}/{len(scenari)} verdi."
    )
    return 0 if not rossi else 1


if __name__ == "__main__":
    raise SystemExit(main())
