# -*- coding: utf-8 -*-
"""Macchina a stati dell'elaborazione annuale.

Separa dalle finestre Qt le transizioni fra calcolo, annullamento, anteprima,
salvataggio, scarto e fallimento. Conserva inoltre i dati necessari a costruire
il testo dell'attesa massima mostrato dalla GUI.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class FaseAnnuale(str, Enum):
    INATTIVA = "inattiva"
    ELABORAZIONE = "elaborazione"
    ANNULLAMENTO_RICHIESTO = "annullamento_richiesto"
    ANTEPRIMA = "anteprima"
    ANNULLATA = "annullata"
    SALVATA = "salvata"
    SCARTATA = "scartata"
    FALLITA = "fallita"


@dataclass
class StatoAnnuale:
    """Stato esplicito e collaudabile del flusso annuale."""

    fase: FaseAnnuale = FaseAnnuale.INATTIVA
    t0: float | None = None
    boundary_time: float | None = None
    progresso: dict = field(default_factory=dict)
    tick: int = 0
    numero_stagioni_fisso: int | None = None

    def avvia(
            self, numero_mesi: int, *, numero_stagioni_fisso=None,
            ora: float | None = None) -> None:
        """Apre una nuova elaborazione e azzera ogni dato precedente."""
        if numero_mesi < 1:
            raise ValueError("L'elaborazione annuale richiede almeno un mese.")
        stagioni_fisse = (
            int(numero_stagioni_fisso)
            if numero_stagioni_fisso is not None
            else None
        )
        if stagioni_fisse is not None and stagioni_fisse < 1:
            raise ValueError(
                "Il numero fisso di stagioni deve essere almeno 1."
            )

        istante = time.monotonic() if ora is None else float(ora)
        self.fase = FaseAnnuale.ELABORAZIONE
        self.t0 = istante
        self.boundary_time = istante
        self.progresso = {
            "tentativo": 1,
            "mese": 0,
            "num_mesi": int(numero_mesi),
            "best": None,
            "eta_max": None,
        }
        self.tick = 0
        self.numero_stagioni_fisso = stagioni_fisse

    def aggiorna_progresso(
            self, stato: dict, *, ora: float | None = None) -> None:
        """Memorizza l'ultimo confine mensile comunicato dal worker."""
        if self.fase not in {
            FaseAnnuale.ELABORAZIONE,
            FaseAnnuale.ANNULLAMENTO_RICHIESTO,
        }:
            return
        self.progresso = dict(stato or {})
        self.boundary_time = (
            time.monotonic() if ora is None else float(ora)
        )

    def richiedi_annullamento(self) -> bool:
        """Passa allo stato di annullamento; ritorna False se non applicabile."""
        if self.fase != FaseAnnuale.ELABORAZIONE:
            return False
        self.fase = FaseAnnuale.ANNULLAMENTO_RICHIESTO
        return True

    def _richiedi_fase(self, ammesse: set[FaseAnnuale], azione: str) -> None:
        if self.fase not in ammesse:
            attese = ", ".join(sorted(f.value for f in ammesse))
            raise RuntimeError(
                f"Transizione Annuale non valida: {azione} da {self.fase.value}; "
                f"atteso stato: {attese}."
            )

    def apri_anteprima(self) -> None:
        self._richiedi_fase({FaseAnnuale.ELABORAZIONE}, "apri anteprima")
        self.fase = FaseAnnuale.ANTEPRIMA

    def segna_annullata(self) -> None:
        self._richiedi_fase(
            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
            "segna annullata",
        )
        self.fase = FaseAnnuale.ANNULLATA

    def segna_salvata(self) -> None:
        self._richiedi_fase({FaseAnnuale.ANTEPRIMA}, "segna salvata")
        self.fase = FaseAnnuale.SALVATA

    def segna_scartata(self) -> None:
        self._richiedi_fase({FaseAnnuale.ANTEPRIMA}, "segna scartata")
        self.fase = FaseAnnuale.SCARTATA

    def segna_fallita(self) -> None:
        self._richiedi_fase(
            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
            "segna fallita",
        )
        self.fase = FaseAnnuale.FALLITA

    @property
    def annullamento_richiesto(self) -> bool:
        return self.fase == FaseAnnuale.ANNULLAMENTO_RICHIESTO

    @property
    def in_corso(self) -> bool:
        return self.fase in {
            FaseAnnuale.ELABORAZIONE,
            FaseAnnuale.ANNULLAMENTO_RICHIESTO,
        }

    def testo_attesa(
            self,
            budget_secondi: float,
            formatta_durata: Callable[[float], str],
            *,
            ora: float | None = None,
    ) -> str:
        """Compone il testo periodico mostrato nella label di stato."""
        self.tick += 1

        if self.annullamento_richiesto:
            punti = "." * (1 + (self.tick % 3))
            return (
                "Annullamento in corso… attendo la fine del mese in corso"
                f"{punti}"
            )

        if self.fase != FaseAnnuale.ELABORAZIONE or self.t0 is None:
            return ""

        istante = time.monotonic() if ora is None else float(ora)
        elapsed = istante - self.t0
        rim_budget = max(0.0, float(budget_secondi) - elapsed)

        eta_max = self.progresso.get("eta_max")
        if eta_max is not None and self.boundary_time is not None:
            rim_raffinato = max(
                0.0,
                float(eta_max) - (istante - self.boundary_time),
            )
            eta = min(rim_budget, rim_raffinato)
        else:
            eta = rim_budget

        punti = " ." * (1 + (self.tick % 3))
        tentativo = self.progresso.get("tentativo", 1)
        mese = self.progresso.get("mese", 0)
        num_mesi = self.progresso.get("num_mesi", 0)
        best = self.progresso.get("best")

        if self.numero_stagioni_fisso is not None:
            intestazione = (
                f"Preparo il tentativo {tentativo} "
                f"di {self.numero_stagioni_fisso}"
            )
        else:
            intestazione = f"Preparo il tentativo {tentativo}"

        if mese <= 0:
            riga1 = f"{intestazione} — primo mese in corso {punti}"
        else:
            riga1 = (
                f"{intestazione}, mese {mese} "
                f"di {num_mesi}{punti}"
            )

        righe = [riga1]
        if best is not None:
            nome_coppie = "coppia" if best == 1 else "coppie"
            righe.append(
                f"Il migliore finora ripete {best} {nome_coppie}"
            )
        if self.numero_stagioni_fisso is None:
            righe.append(f"Attesa massima: {formatta_durata(eta)}")
        else:
            righe.append(
                "Riproduzione diagnostica a numero fisso di tentativi"
            )
        return "\n".join(righe)
