# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""Gate I1b/1: contratto immutabile di INGRESSO al motore Q21.

Il modulo e' puro (senza Qt, senza import dei runner Q*, senza I/O).
Il contratto fotografa durate da 1 a 10 mesi e lo Storico pregresso.
La pipeline contestuale valida questi casi. Il solo metodo storico
``verifica_compatibilita_q21`` conserva il controllo del riferimento congelato
a 10 mesi e Storico vuoto, per i relativi confronti di identità.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

from moduli.dominio.fotografia_generazione_layout import FotografiaGenerazioneLayout


class Q21NonAncoraCompatibile(ValueError):
    """L'input e' valido per il prodotto, non per il Q21 congelato."""


def _frequenze_immutabili(frequenze):
    if not isinstance(frequenze, Mapping):
        raise TypeError("Servono le frequenze dello Storico in una mappa esplicita.")
    copia = {}
    for coppia, volte in frequenze.items():
        if (not isinstance(coppia, (frozenset, tuple, set, list))
                or len(coppia) != 2
                or any(not isinstance(s, str) or not s.strip() for s in coppia)
                or len(set(coppia)) != 2 or type(volte) is not int or volte <= 0):
            raise ValueError("Voce dello Storico non valida: servono due nomi e una frequenza positiva.")
        chiave = tuple(sorted(coppia))
        copia[chiave] = copia.get(chiave, 0) + volte
    return tuple(sorted((a, b, n) for (a, b), n in copia.items()))


@dataclass(frozen=True, slots=True)
class IngressoQ21:
    fotografia: FotografiaGenerazioneLayout
    numero_mesi: int
    seed_principale: int
    num_candidati: int
    frequenze_iniziali: tuple[tuple[str, str, int], ...]
    budget_totale: float
    riserva: float
    identita_fotografia: tuple

    def crea_studenti(self):
        return self.fotografia.crea_studenti()

    def frequenze_storico(self):
        return {frozenset((a, b)): n for a, b, n in self.frequenze_iniziali}

    def verifica_compatibilita_q21(self):
        """Fail-closed: il Q21 originale NON ottimizza lo Storico pregresso o 1–9 mesi."""
        if self.numero_mesi != 10:
            raise Q21NonAncoraCompatibile(
                "Q21 congelato: la generazione e le verifiche assumono 10 mesi; "
                f"ne sono stati richiesti {self.numero_mesi}.")
        if self.frequenze_iniziali:
            raise Q21NonAncoraCompatibile(
                "Q21 congelato: la ricerca usa Storico iniziale vuoto; "
                "non basta ricostruire i riusi in uscita.")
        if self.fotografia.identita() != self.identita_fotografia:
            raise ValueError("La fotografia dell'aula e' stata alterata.")


def prepara_ingresso_q21(fotografia: FotografiaGenerazioneLayout, *,
                         numero_mesi: int, seed_principale: int,
                         num_candidati: int, frequenze_storico: Mapping,
                         budget_totale: float = 600, riserva: float = 60) -> IngressoQ21:
    """Fotografa classe/Layout/Storico e parametri, senza mutare il chiamante.

    Non sceglie altre modalita' e non esegue ricerca. ``frequenze_storico``
    deve essere lo snapshot delle adiacenze della modalita' Personalizzata,
    non un dizionario ricavato successivamente dagli esiti della proposta.
    """
    if not isinstance(fotografia, FotografiaGenerazioneLayout):
        raise TypeError("Serve una FotografiaGenerazioneLayout reale.")
    if type(numero_mesi) is not int or not 1 <= numero_mesi <= 10:
        raise ValueError("La durata richiesta deve essere un intero tra 1 e 10 mesi.")
    if type(seed_principale) is not int or not 0 <= seed_principale < 2**64:
        raise ValueError("Seed principale non valido (unsigned 64 bit).")
    if type(num_candidati) is not int or num_candidati <= 0:
        raise ValueError("Il numero dei candidati mensili deve essere positivo.")
    if (isinstance(budget_totale, bool) or isinstance(riserva, bool)
            or not isinstance(budget_totale, (int, float))
            or not isinstance(riserva, (int, float))
            or not 0 < riserva < budget_totale < float('inf')):
        raise ValueError("Budget e riserva devono essere finiti e 0 < riserva < budget.")
    foto = deepcopy(fotografia)
    studenti = foto.crea_studenti()
    nomi = [s.get_nome_completo() for s in studenti]
    schema = foto.layout.schema
    fissi = sum(s.nota_posizione == "FISSO" for s in studenti)
    if (not studenti or len(nomi) != len(set(nomi))
            or len(studenti) != sum(b.capienza for b in schema.blocchi)
            or fissi > 1 or (fissi == 1) != (schema.posto_ancora_fisso is not None)):
        raise ValueError("Fotografia incoerente: studenti, posti o ancora FISSO.")
    return IngressoQ21(
        fotografia=foto, numero_mesi=numero_mesi, seed_principale=seed_principale,
        num_candidati=num_candidati, frequenze_iniziali=_frequenze_immutabili(frequenze_storico),
        budget_totale=float(budget_totale), riserva=float(riserva),
        identita_fotografia=foto.identita())


def prepara_ingresso_q21_da_config(fotografia, config_app, **parametri):
    """Legge UNA VOLTA lo Storico Personalizzata dal config snapshot del processo.

    Non unisce altre modalita', non legge il file utente e non registra mesi.
    ``config_app`` deve gia' essere una copia temporanea della configurazione.
    """
    if 'frequenze_storico' in parametri:
        raise TypeError("Lo Storico deve provenire dal config snapshot, non da due origini.")
    from moduli.persistenza.strato_storico import frequenze_blacklist_adiacenze
    frequenze = frequenze_blacklist_adiacenze(config_app, modo='personalizzata')
    return prepara_ingresso_q21(fotografia, frequenze_storico=frequenze, **parametri)
