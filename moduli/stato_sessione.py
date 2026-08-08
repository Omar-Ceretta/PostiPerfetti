# -*- coding: utf-8 -*-
"""Stato operativo condiviso della sessione di «PostiPerfetti».

Raccoglie la classe caricata, la geometria corrente, l'aula preparata e le due
macchine a stati delle elaborazioni Mensile e Annuale. La finestra principale e
i suoi mixin leggono così una sola fonte di verità, senza campi paralleli che
possano divergere durante cambio classe, annullamento o salvataggio.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from moduli.stato_annuale import StatoAnnuale
from moduli.stato_mensile import StatoMensile


_MODI_GEOMETRIA = frozenset({"coppie", "terzetti"})


@dataclass(frozen=True)
class AbilitazioneControlliElaborazione:
    """Stato coerente dei controlli mentre un calcolo è in corso."""

    avvio: bool
    configurazione: bool
    editor: bool
    storico: bool


def calcola_abilitazione_controlli(
        *, in_elaborazione: bool, classe_caricata: bool
) -> AbilitazioneControlliElaborazione:
    """Decide quali controlli possono mutare la sessione corrente.

    Durante un'elaborazione restano disponibili navigazione, ridimensionamento,
    cambio tema e consultazione delle schede, ma vengono congelate le sorgenti
    del calcolo: classe, geometria, opzioni e Storico.
    """
    bloccata = bool(in_elaborazione)
    operativa = bool(classe_caricata) and not bloccata
    return AbilitazioneControlliElaborazione(
        avvio=operativa,
        configurazione=operativa,
        editor=not bloccata,
        storico=not bloccata,
    )


def puo_avviare_elaborazione(
    *,
    worker_mensile_presente: bool,
    worker_annuale_presente: bool,
    annuale_in_corso: bool,
) -> bool:
    """Rifiuta avvii sovrapposti anche se arrivano da chiamate programmatiche.

    La GUI disabilita il pulsante durante il calcolo, ma questa guardia pura
    protegge anche doppi segnali già accodati, callback o future chiamate dirette.
    Un riferimento worker non ancora ripulito viene trattato prudentemente come
    elaborazione attiva.
    """
    return not (
        bool(worker_mensile_presente)
        or bool(worker_annuale_presente)
        or bool(annuale_in_corso)
    )


def risultato_appartiene_sessione(
    *,
    file_origine_corrente: str | None,
    studenti_correnti,
    aula_corrente,
    file_origine_atteso: str | None,
    studenti_attesi,
    aula_attesa,
) -> bool:
    """Verifica che un esito asincrono appartenga ancora alla stessa sessione.

    File uguale non basta: una classe puo' essere ricaricata o l'Aula puo'
    essere ricostruita mentre un risultato vecchio e' ancora in viaggio. Le
    identita' di lista studenti e Aula costituiscono quindi il token di
    sessione non persistente usato da tutti i flussi asincroni.
    """
    return bool(
        file_origine_corrente == file_origine_atteso
        and studenti_correnti is studenti_attesi
        and aula_corrente is aula_attesa
    )


@dataclass
class StatoSessione:
    """Contiene lo stato operativo non persistente della finestra principale."""

    studenti: list = field(default_factory=list)
    file_origine: str | None = None
    aula: Any | None = None
    geometria: str = "coppie"
    posti_insufficienti: bool = False
    mensile: StatoMensile = field(default_factory=StatoMensile)
    annuale: StatoAnnuale = field(default_factory=StatoAnnuale)

    def carica_classe(self, studenti, file_origine: str) -> None:
        """Registra una classe validata e azzera i risultati della precedente."""
        nome_file = str(file_origine).strip()
        if not nome_file:
            raise ValueError("Il file di origine della classe non può essere vuoto.")
        elenco = list(studenti or [])
        if not elenco:
            raise ValueError("La classe caricata deve contenere almeno uno studente.")

        self.studenti = elenco
        self.file_origine = nome_file
        self.azzera_risultati()

    def chiudi_classe(self) -> None:
        """Azzera classe, aula, capienza e risultati della sessione corrente."""
        self.studenti = []
        self.file_origine = None
        self.geometria = "coppie"
        self.posti_insufficienti = False
        self.azzera_risultati()

    def azzera_risultati(self) -> None:
        """Rimuove aula e risultato Mensile; l'Annuale torna inattivo."""
        self.aula = None
        self.mensile.reset()
        self.annuale = StatoAnnuale()

    def azzera_risultato_mensile(self) -> None:
        """Rimuove l'aula corrente e il solo risultato Mensile mostrato."""
        self.aula = None
        self.mensile.reset()

    def imposta_aula(self, aula) -> None:
        """Registra l'aula costruita per l'elaborazione corrente."""
        if aula is None:
            raise ValueError("L'aula della sessione non può essere None.")
        self.aula = aula

    def imposta_geometria(self, geometria: str) -> None:
        """Imposta coppie o terzetti, rifiutando valori sconosciuti."""
        valore = str(geometria).strip().lower()
        if valore not in _MODI_GEOMETRIA:
            raise ValueError(f"Geometria non valida: {geometria!r}.")
        self.geometria = valore

    def imposta_posti_insufficienti(self, valore: bool) -> None:
        """Aggiorna l'esito del controllo di capienza."""
        self.posti_insufficienti = bool(valore)

    @property
    def classe_caricata(self) -> bool:
        return bool(self.studenti and self.file_origine)
