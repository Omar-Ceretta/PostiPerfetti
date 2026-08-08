# -*- coding: utf-8 -*-
"""Stato esplicito dell'ultima assegnazione mensile.

Raccoglie in un unico oggetto il risultato corrente, i metadati necessari al
salvataggio e la relazione con lo Storico. La GUI può così distinguere con una
sola fonte di verità fra assenza di risultato, disposizione da salvare e
assegnazione già registrata.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FaseMensile(str, Enum):
    """Fasi possibili del risultato mensile mostrato nella GUI."""

    VUOTA = "vuota"
    DA_SALVARE = "da_salvare"
    SALVATA = "salvata"


@dataclass
class StatoMensile:
    """Contiene l'intero stato dell'ultima assegnazione mensile."""

    fase: FaseMensile = FaseMensile.VUOTA
    modo: str | None = None
    assegnatore: Any | None = None
    dati_terzetti: dict | None = None
    nome: str | None = None
    progressivo: int | None = None
    data_creazione: str | None = None
    file_origine: str | None = None
    nome_classe: str | None = None
    genere_misto: bool | None = None
    indice_storico: int | None = None

    def reset(self) -> None:
        """Azzera il risultato corrente e tutti i relativi metadati."""
        self.fase = FaseMensile.VUOTA
        self.modo = None
        self.assegnatore = None
        self.dati_terzetti = None
        self.nome = None
        self.progressivo = None
        self.data_creazione = None
        self.file_origine = None
        self.nome_classe = None
        self.genere_misto = None
        self.indice_storico = None

    def prepara_coppie(
        self,
        assegnatore,
        *,
        nome: str,
        progressivo: int,
        data_creazione: str,
        file_origine: str,
        nome_classe: str,
        genere_misto: bool,
    ) -> None:
        """Registra un nuovo risultato mensile a coppie, ancora da salvare."""
        self._valida_metadati(
            nome, progressivo, data_creazione, file_origine, nome_classe
        )
        if assegnatore is None:
            raise ValueError("Il risultato a coppie richiede un assegnatore.")

        self.fase = FaseMensile.DA_SALVARE
        self.modo = "coppie"
        self.assegnatore = assegnatore
        self.dati_terzetti = None
        self.nome = nome
        self.progressivo = int(progressivo)
        self.data_creazione = data_creazione
        self.file_origine = str(file_origine)
        self.nome_classe = str(nome_classe).strip()
        self.genere_misto = bool(genere_misto)
        self.indice_storico = None

    def prepara_terzetti(
        self,
        dati_terzetti: dict,
        *,
        nome: str,
        progressivo: int,
        data_creazione: str,
        file_origine: str,
        nome_classe: str,
        genere_misto: bool,
    ) -> None:
        """Registra un nuovo risultato mensile a terzetti, ancora da salvare."""
        self._valida_metadati(
            nome, progressivo, data_creazione, file_origine, nome_classe
        )
        if not isinstance(dati_terzetti, dict) or not dati_terzetti:
            raise ValueError("Il risultato a terzetti richiede dati non vuoti.")

        self.fase = FaseMensile.DA_SALVARE
        self.modo = "terzetti"
        self.assegnatore = None
        self.dati_terzetti = dati_terzetti
        self.nome = nome
        self.progressivo = int(progressivo)
        self.data_creazione = data_creazione
        self.file_origine = str(file_origine)
        self.nome_classe = str(nome_classe).strip()
        self.genere_misto = bool(genere_misto)
        self.indice_storico = None

    def segna_salvata(self, indice_storico: int, *, nome: str | None = None) -> None:
        """Collega il risultato corrente alla voce appena scritta nello Storico."""
        if self.fase != FaseMensile.DA_SALVARE:
            raise RuntimeError(
                "Può essere salvato soltanto un risultato Mensile ancora da salvare."
            )
        if indice_storico < 0:
            raise ValueError("L'indice dello Storico non può essere negativo.")
        if nome is not None:
            self.rinomina(nome)

        self.fase = FaseMensile.SALVATA
        self.indice_storico = int(indice_storico)

    def rinomina(self, nuovo_nome: str) -> None:
        """Aggiorna il nome del risultato corrente."""
        nome = str(nuovo_nome).strip()
        if not nome:
            raise ValueError("Il nome dell'assegnazione non può essere vuoto.")
        if not self.ha_risultato:
            raise RuntimeError("Non esiste un risultato mensile da rinominare.")
        self.nome = nome

    def aggiorna_indice_dopo_eliminazione(self, indice_eliminato: int) -> None:
        """Mantiene coerente il collegamento dopo una cancellazione dallo Storico."""
        if indice_eliminato < 0:
            raise ValueError("L'indice eliminato non può essere negativo.")
        if self.indice_storico is None:
            return
        if self.indice_storico == indice_eliminato:
            # La voce collegata non esiste più: lo stato non può restare
            # SALVATA con indice None nemmeno per una singola transizione.
            self.scollega_dallo_storico()
        elif self.indice_storico > indice_eliminato:
            self.indice_storico -= 1

    def scollega_dallo_storico(self) -> None:
        """Mantiene il risultato corrente ma lo rende nuovamente da salvare."""
        if not self.ha_risultato:
            return
        self.fase = FaseMensile.DA_SALVARE
        self.indice_storico = None

    @property
    def ha_risultato(self) -> bool:
        return self.fase != FaseMensile.VUOTA

    @property
    def non_salvata(self) -> bool:
        return self.fase == FaseMensile.DA_SALVARE

    @property
    def salvata(self) -> bool:
        return self.fase == FaseMensile.SALVATA

    def nome_per_export(self) -> str:
        """Restituisce il nome della voce salvata collegata al risultato."""
        if not self.salvata or self.indice_storico is None:
            raise RuntimeError(
                "L'esportazione richiede un'assegnazione salvata nello Storico."
            )
        nome = str(self.nome or "").strip()
        if not nome:
            raise RuntimeError(
                "L'assegnazione salvata non ha un nome valido per l'esportazione."
            )
        return nome

    @property
    def e_coppie(self) -> bool:
        return self.modo == "coppie"

    @property
    def e_terzetti(self) -> bool:
        return self.modo == "terzetti"

    @staticmethod
    def _valida_metadati(
        nome: str,
        progressivo: int,
        data_creazione: str,
        file_origine: str,
        nome_classe: str,
    ) -> None:
        if not str(nome).strip():
            raise ValueError("Il nome dell'assegnazione non può essere vuoto.")
        if int(progressivo) < 1:
            raise ValueError("Il progressivo deve essere almeno 1.")
        if not str(data_creazione).strip():
            raise ValueError("La data di creazione non può essere vuota.")
        if not str(file_origine).strip():
            raise ValueError("Il file di origine non può essere vuoto.")
        if not str(nome_classe).strip():
            raise ValueError("Il nome della classe non può essere vuoto.")
