# -*- coding: utf-8 -*-
"""Validazione indipendente delle soluzioni della modalità Mista a blocchi.

Gate C M1.4: il validatore non genera né corregge soluzioni. Controlla in modo
indipendente partizione e collocazione rispetto allo schema semantico, senza
dedurre PRIMA/ULTIMA dalla profondità e senza eccezioni per l'assenza di FISSO.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from moduli.dominio.metrica_pulizia import (
    Gruppo,
    adiacenze_partizione,
    livello_incompatibilita,
    nome_completo,
)
from moduli.dominio.schema_blocchi_semantico import SchemaBlocchiSemantico


def _firma_gruppo(gruppo: Gruppo) -> tuple[str, ...]:
    return tuple(nome_completo(studente) for studente in gruppo.membri)


@dataclass(frozen=True, slots=True)
class EsitoValidazioneBlocchi:
    """Misure semantiche e fisiche di una soluzione già prodotta."""

    studenti_attesi: int
    studenti_collocati: int
    studenti_unici: int
    copertura_esatta: bool
    blocchi_attesi: int
    gruppi_prodotti: int
    forma_esatta: bool
    collocazioni_prodotte: int
    blocchi_fisici_unici: int
    blocchi_schema_esatti: bool
    gruppi_collocati_esatti: bool
    gruppi_da_2: int
    gruppi_da_3: int
    adiacenze_attese: int
    adiacenze_reali: int
    violazioni_liv3: int
    prima_totali: int
    prima_fuori_zona: int
    ultima_totali: int
    ultima_in_zona: int
    fissi_totali: int
    fisso_fuori_ancora: int

    @property
    def valida(self) -> bool:
        return not self.errori_duri

    @property
    def errori_duri(self) -> tuple[str, ...]:
        errori: list[str] = []
        if self.studenti_collocati != self.studenti_attesi:
            errori.append("numero_studenti")
        if not self.copertura_esatta:
            errori.append("copertura_studenti")
        if self.gruppi_prodotti != self.blocchi_attesi:
            errori.append("numero_gruppi")
        if not self.forma_esatta:
            errori.append("forma_gruppi")
        if self.collocazioni_prodotte != self.blocchi_attesi:
            errori.append("numero_collocazioni")
        if self.blocchi_fisici_unici != self.blocchi_attesi:
            errori.append("blocchi_collocati_duplicati")
        if not self.blocchi_schema_esatti:
            errori.append("blocchi_fuori_schema")
        if not self.gruppi_collocati_esatti:
            errori.append("gruppi_collocati_incoerenti")
        if self.adiacenze_reali != self.adiacenze_attese:
            errori.append("numero_adiacenze")
        if self.violazioni_liv3:
            errori.append("incompatibilita_liv3")
        if self.prima_fuori_zona:
            errori.append("prima_fuori_zona")
        if self.fissi_totali > 1:
            errori.append("fissi_multipli")
        if self.fisso_fuori_ancora:
            errori.append("fisso_fuori_ancora")
        return tuple(errori)

    # Alias temporanei per rendere leggibili eventuali strumenti M1.2 ancora in
    # uso durante il cantiere. La semantica autorevole è quella dei nomi nuovi.
    @property
    def prima_fuori_prima_fila(self) -> int:
        return self.prima_fuori_zona

    @property
    def ultima_in_ultima_fila(self) -> int:
        return self.ultima_in_zona

    @property
    def fisso_blocco_errato(self) -> int:
        return self.fisso_fuori_ancora

    @property
    def fisso_lato_errato(self) -> int:
        return self.fisso_fuori_ancora

    def come_dict(self) -> dict[str, Any]:
        return {
            "valida": self.valida,
            "errori_duri": list(self.errori_duri),
            "studenti_attesi": self.studenti_attesi,
            "studenti_collocati": self.studenti_collocati,
            "studenti_unici": self.studenti_unici,
            "copertura_esatta": self.copertura_esatta,
            "blocchi_attesi": self.blocchi_attesi,
            "gruppi_prodotti": self.gruppi_prodotti,
            "forma_esatta": self.forma_esatta,
            "collocazioni_prodotte": self.collocazioni_prodotte,
            "blocchi_fisici_unici": self.blocchi_fisici_unici,
            "blocchi_schema_esatti": self.blocchi_schema_esatti,
            "gruppi_collocati_esatti": self.gruppi_collocati_esatti,
            "gruppi_da_2": self.gruppi_da_2,
            "gruppi_da_3": self.gruppi_da_3,
            "adiacenze_attese": self.adiacenze_attese,
            "adiacenze_reali": self.adiacenze_reali,
            "violazioni_liv3": self.violazioni_liv3,
            "prima_totali": self.prima_totali,
            "prima_fuori_zona": self.prima_fuori_zona,
            "ultima_totali": self.ultima_totali,
            "ultima_in_zona": self.ultima_in_zona,
            "fissi_totali": self.fissi_totali,
            "fisso_fuori_ancora": self.fisso_fuori_ancora,
        }


def valida_soluzione_blocchi(
    studenti: Sequence[Any],
    gruppi: Sequence[Gruppo],
    schema: SchemaBlocchiSemantico,
    collocazioni: Sequence[Any],
) -> EsitoValidazioneBlocchi:
    """Controlla gli invarianti hard e misura ULTIMA senza fidarsi del motore."""
    attesi = [nome_completo(s) for s in studenti]
    collocati = [nome_completo(s) for g in gruppi for s in g.membri]
    contatore_collocati = Counter(collocati)
    contatore_attesi = Counter(attesi)
    studenti_unici = len(contatore_collocati)
    copertura_esatta = contatore_collocati == contatore_attesi

    forma = Counter(len(g.membri) for g in gruppi)
    forma_attesa = schema.conteggio_per_capienza()
    forma_valida = (
        int(forma.get(2, 0)) == int(forma_attesa.get(2, 0))
        and int(forma.get(3, 0)) == int(forma_attesa.get(3, 0))
        and not any(taglia not in (2, 3) for taglia in forma)
    )

    adiacenze = adiacenze_partizione(gruppi)
    violazioni_liv3 = sum(
        1 for a, b in adiacenze if livello_incompatibilita(a, b) == 3
    )

    blocchi_schema = {blocco.id for blocco in schema.blocchi}
    blocchi_collocati = [collocazione.blocco.id for collocazione in collocazioni]
    blocchi_schema_esatti = (
        Counter(blocchi_collocati) == Counter({blocco_id: 1 for blocco_id in blocchi_schema})
    )

    firme_gruppi = Counter(_firma_gruppo(gruppo) for gruppo in gruppi)
    firme_collocazioni = Counter(
        _firma_gruppo(collocazione.gruppo) for collocazione in collocazioni
    )
    gruppi_collocati_esatti = firme_gruppi == firme_collocazioni

    mappa_occupazione: dict[str, tuple[Any, Any]] = {}
    for collocazione in collocazioni:
        blocco = collocazione.blocco
        if len(collocazione.gruppo.membri) != blocco.capienza:
            continue
        for posto, studente in zip(
            blocco.posti,
            collocazione.gruppo.membri,
            strict=True,
        ):
            mappa_occupazione[nome_completo(studente)] = (blocco, posto)

    prima = [s for s in studenti if getattr(s, "nota_posizione", "NORMALE") == "PRIMA"]
    prima_fuori_zona = sum(
        1
        for studente in prima
        if (
            nome_completo(studente) not in mappa_occupazione
            or not mappa_occupazione[nome_completo(studente)][0].zona_prima
        )
    )

    ultima = [s for s in studenti if getattr(s, "nota_posizione", "NORMALE") == "ULTIMA"]
    ultima_in_zona = sum(
        1
        for studente in ultima
        if (
            nome_completo(studente) in mappa_occupazione
            and mappa_occupazione[nome_completo(studente)][0].zona_ultima
        )
    )

    fissi = [s for s in studenti if getattr(s, "nota_posizione", "NORMALE") == "FISSO"]
    fisso_fuori_ancora = 0
    if fissi:
        fisso = fissi[0]
        occupazione = mappa_occupazione.get(nome_completo(fisso))
        blocco_ancora = schema.blocco_ancora_fisso
        posto_ancora = schema.posto_ancora_fisso
        if (
            occupazione is None
            or blocco_ancora is None
            or posto_ancora is None
            or occupazione[0].id != blocco_ancora.id
            or occupazione[1].id != posto_ancora.id
            or occupazione[1].indice != posto_ancora.indice
        ):
            fisso_fuori_ancora = 1

    return EsitoValidazioneBlocchi(
        studenti_attesi=len(studenti),
        studenti_collocati=len(collocati),
        studenti_unici=studenti_unici,
        copertura_esatta=copertura_esatta,
        blocchi_attesi=schema.numero_blocchi,
        gruppi_prodotti=len(gruppi),
        forma_esatta=forma_valida,
        collocazioni_prodotte=len(collocazioni),
        blocchi_fisici_unici=len(set(blocchi_collocati)),
        blocchi_schema_esatti=blocchi_schema_esatti,
        gruppi_collocati_esatti=gruppi_collocati_esatti,
        gruppi_da_2=int(forma.get(2, 0)),
        gruppi_da_3=int(forma.get(3, 0)),
        adiacenze_attese=schema.posti_totali - schema.numero_blocchi,
        adiacenze_reali=len(adiacenze),
        violazioni_liv3=violazioni_liv3,
        prima_totali=len(prima),
        prima_fuori_zona=prima_fuori_zona,
        ultima_totali=len(ultima),
        ultima_in_zona=ultima_in_zona,
        fissi_totali=len(fissi),
        fisso_fuori_ancora=fisso_fuori_ancora,
    )
