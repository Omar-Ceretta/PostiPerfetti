# -*- coding: utf-8 -*-
"""Gate A1 — bozza annuale unica e cronologia delle vicinanze (senza Qt).

Non muta i dati Q21, non modifica lo Storico e non esegue generazioni.
Le operazioni riguardano gli OCCUPANTI, non la geometria dei blocchi.
Gli indicatori sono ricalcolati dalla disposizione; non sono punteggi Q21.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.disposizione_effettiva import (
    DisposizioneEffettiva,
)
from moduli.dominio.editing_disposizione import (
    BozzaDisposizione, MetricheManuali, _avvisi, _controlla, _storico_normalizzato,
    misura,
)
from moduli.dominio.fotografia_generazione_layout import FotografiaGenerazioneLayout
from moduli.dominio.metrica_pulizia import Gruppo


Coppia = tuple[str, str]


@dataclass(frozen=True, slots=True)
class QuadroMese:
    """Fotografia derivata del mese nella sequenza attuale (indice 0-based)."""

    indice: int
    adiacenze_prima: frozenset[Coppia]
    adiacenze_mese: frozenset[Coppia]
    riutilizzi: frozenset[Coppia]
    ultimi_mesi: tuple[tuple[Coppia, int], ...]  # coppia -> mese precedente, 1-based
    metriche: MetricheManuali

    def ultimo_mese(self, coppia: Coppia) -> int | None:
        return dict(self.ultimi_mesi).get(tuple(sorted(coppia)))


@dataclass(frozen=True, slots=True)
class EsitoMossaAnnuale:
    accettata: bool
    bozza: BozzaAnnuale
    motivo: str = ""
    avvisi: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BozzaAnnuale:
    """Dieci (o N) mesi in un'unica bozza, con Undo globale e fonte congelata.

    Le disposizioni sono valori immutabili, l'originale non cambia mai.
    ``undo`` conserva lo stato *intero* precedente: una mossa nel mese 2
    può cambiare le metriche del mese 7, pur lasciandone identici gli occupanti.
    """

    fotografia: FotografiaGenerazioneLayout
    originale: tuple[DisposizioneEffettiva, ...]
    corrente: tuple[DisposizioneEffettiva, ...]
    storico_iniziale: frozenset[Coppia]
    undo: tuple[tuple[DisposizioneEffettiva, ...], ...] = ()

    @classmethod
    def crea(
        cls, fotografia: FotografiaGenerazioneLayout, mesi: Sequence[dict],
    ) -> BozzaAnnuale:
        if not isinstance(fotografia, FotografiaGenerazioneLayout):
            raise TypeError("Serve la fotografia congelata dell'Annuale.")
        if not isinstance(mesi, (list, tuple)) or not mesi:
            raise ValueError("L'Annuale non contiene mesi completi.")
        iniziali: list[DisposizioneEffettiva] = []
        for numero, mese in enumerate(mesi, 1):
            if not isinstance(mese, dict):
                raise ValueError(f"Mese {numero}: formato non valido.")
            verificata = fotografia.verifica_risultato(mese)
            iniziali.append(verificata)
        precedenti = mesi[0].get("adiacenze_prima")
        if not isinstance(precedenti, (set, frozenset)):
            raise ValueError("Mese 1: manca la fotografia dello Storico iniziale.")
        storico = _storico_normalizzato({tuple(pair): 1 for pair in precedenti})
        # Q21 riporta per ciascun mese la blacklist costruita sino al mese
        # precedente. Non accettiamo una sequenza iniziale incoerente.
        visti = set(storico)
        for numero, (mese, disposizione) in enumerate(zip(mesi, iniziali, strict=True), 1):
            ricevuti = mese.get("adiacenze_prima")
            if not isinstance(ricevuti, (set, frozenset)):
                raise ValueError(f"Mese {numero}: manca la cronologia delle adiacenze.")
            effettivi = _storico_normalizzato({tuple(pair): 1 for pair in ricevuti})
            if effettivi != visti:
                raise ValueError(f"Mese {numero}: cronologia Q21 non coerente.")
            visti.update(disposizione.adiacenze_rotazioni())
        originali = tuple(iniziali)
        return cls(fotografia, originali, originali, storico)

    @property
    def numero_mesi(self) -> int:
        return len(self.corrente)

    @property
    def modificata(self) -> bool:
        return any(a.occupazioni != b.occupazioni
                   for a, b in zip(self.originale, self.corrente, strict=True))

    def mesi_modificati(self) -> tuple[int, ...]:
        """Numeri di mese 1-based, pronti per l'anteprima."""
        return tuple(i for i, (a, b) in enumerate(
            zip(self.originale, self.corrente, strict=True), 1,
        ) if a.occupazioni != b.occupazioni)

    def _indice(self, indice: int) -> None:
        if type(indice) is not int or indice < 0 or indice >= self.numero_mesi:
            raise ValueError("Mese inesistente nella bozza Annuale.")

    def quadri(self, *, originali: bool = False) -> tuple[QuadroMese, ...]:
        """Ricalcola tutti i precedenti e gli ultimi usi in ordine cronologico."""
        disposizioni = self.originale if originali else self.corrente
        precedenti = set(self.storico_iniziale)
        ultima_apparizione: dict[Coppia, int] = {}
        quadri = []
        for indice, disposizione in enumerate(disposizioni):
            vicinanze = disposizione.adiacenze_rotazioni()
            riusi = vicinanze & precedenti
            riferimenti = tuple(sorted(
                (pair, ultima_apparizione[pair])
                for pair in riusi if pair in ultima_apparizione
            ))
            quadri.append(QuadroMese(
                indice=indice,
                adiacenze_prima=frozenset(precedenti),
                adiacenze_mese=vicinanze,
                riutilizzi=frozenset(riusi),
                ultimi_mesi=riferimenti,
                metriche=misura(disposizione, self.fotografia, frozenset(precedenti)),
            ))
            for pair in vicinanze:
                ultima_apparizione[pair] = indice + 1
            precedenti.update(vicinanze)
        return tuple(quadri)

    def avvisi_rispetto_automatica(self) -> tuple[str, ...]:
        """Confronta ogni mese con la sua metrica cronologica Q21 originaria."""
        prima = self.quadri(originali=True)
        dopo = self.quadri()
        avvisi = []
        for p, d in zip(prima, dopo, strict=True):
            avvisi.extend(
                f"Mese {p.indice + 1}: {messaggio}"
                for messaggio in _avvisi(
                    p.metriche, d.metriche, self.fotografia.genere_misto,
                )
            )
        return tuple(avvisi)

    def _sostituisci(self, indice: int, nuova: DisposizioneEffettiva) -> BozzaAnnuale:
        originale = self.originale[indice]
        nuova = replace(
            nuova, modificata_manualmente=(nuova.occupazioni != originale.occupazioni),
        )
        if nuova == self.corrente[indice]:
            return self
        aggiornate = list(self.corrente)
        aggiornate[indice] = nuova
        return replace(self, corrente=tuple(aggiornate), undo=(*self.undo, self.corrente))

    def _mossa(self, indice: int, azione: str, a: str, b: str) -> EsitoMossaAnnuale:
        try:
            self._indice(indice)
        except ValueError as errore:
            return EsitoMossaAnnuale(False, self, str(errore))
        prima = self.avvisi_rispetto_automatica()
        quadro = self.quadri()[indice]
        # Riutilizza la validazione HARD D1 e la semantica dei banchi.
        base = BozzaDisposizione.crea(
            self.fotografia, self.corrente[indice],
            frequenze_storico={pair: 1 for pair in quadro.adiacenze_prima},
        )
        operazione = getattr(base, azione)(a, b)
        if not operazione.accettata:
            return EsitoMossaAnnuale(False, self, operazione.motivo)
        aggiornata = self._sostituisci(indice, operazione.bozza.corrente)
        dopo = aggiornata.avvisi_rispetto_automatica()
        nuovi = tuple(msg for msg in dopo if msg not in prima)
        return EsitoMossaAnnuale(True, aggiornata, avvisi=nuovi)

    def scambia_studenti(self, indice: int, posto_a: str, posto_b: str) -> EsitoMossaAnnuale:
        return self._mossa(indice, "scambia_studenti", posto_a, posto_b)

    def scambia_blocchi(self, indice: int, blocco_a: str, blocco_b: str) -> EsitoMossaAnnuale:
        """Scambia occupanti: solo coppia-coppia o trio-trio, non la geometria."""
        return self._mossa(indice, "scambia_occupanti_banchi", blocco_a, blocco_b)

    def adotta_mese(self, indice: int, nuova: DisposizioneEffettiva) -> BozzaAnnuale:
        """A2: riceve una bozza da un dialogo e la adotta come UNA mossa globale.

        Controlla anche i campi immutabili (identità, geometria, ancora FISSO),
        non solo le occupazioni. Non muta la proposta originale Q21.
        """
        self._indice(indice)
        if not isinstance(nuova, DisposizioneEffettiva):
            raise ValueError("La disposizione del mese non è valida.")
        originale = self.originale[indice]
        if replace(nuova, occupazioni=originale.occupazioni,
                   modificata_manualmente=originale.modificata_manualmente) != originale:
            raise ValueError("La geometria o l'identità della proposta è cambiata.")
        _controlla(nuova, self.fotografia)
        return self._sostituisci(indice, nuova)

    def annulla(self) -> BozzaAnnuale:
        if not self.undo:
            return self
        return replace(self, corrente=self.undo[-1], undo=self.undo[:-1])

    def ripristina_mese(self, indice: int) -> BozzaAnnuale:
        self._indice(indice)
        return self._sostituisci(indice, self.originale[indice])

    def ripristina_annata(self) -> BozzaAnnuale:
        if self.corrente == self.originale:
            return self
        return replace(self, corrente=self.originale, undo=(*self.undo, self.corrente))

    def proietta_mesi(self, mesi_originali: Sequence[dict]) -> list[dict]:
        """Produce mesi pronti a ricalcolare Report, senza scrivere né mutare Q21.

        ATTENZIONE: non salva nello Storico. I punteggi globali Q21 e i
        metadati del solver NON sono ricalcolati: la GUI dovrà distinguerli.
        """
        if len(mesi_originali) != self.numero_mesi:
            raise ValueError("Numero di mesi diverso da quello della bozza.")
        # Il collegamento alla proposta originale è verificato, senza fidarsi
        # di oggetti/gruppi potenzialmente sostituiti dopo l'apertura.
        for i, mese in enumerate(mesi_originali):
            verifica = self.fotografia.verifica_risultato(mese)
            if verifica != self.originale[i]:
                raise ValueError(f"Mese {i + 1}: proposta Q21 cambiata dopo l'apertura.")
        studenti = {s.get_nome_completo(): s for s in self.fotografia.crea_studenti()}
        quadri = self.quadri()
        nuovi = []
        for i, (mese, disposizione, quadro) in enumerate(
            zip(mesi_originali, self.corrente, quadri, strict=True),
        ):
            occupanti = dict(disposizione.occupazioni)
            # Non riordinare in base allo schema: Q21 può restituire i gruppi
            # in un ordine diverso da quello fisico delle collocazioni. I due
            # ordinamenti sono entrambi parte del risultato che salviamo.
            gruppi_per_chiave = {}
            collocazioni = []
            for collocazione in mese["collocazioni"]:
                blocco = collocazione.blocco
                membri = tuple(studenti[occupanti[p.id]] for p in blocco.posti)
                gruppo = Gruppo("coppia" if blocco.capienza == 2 else "terzetto", membri)
                chiave = tuple(s.get_nome_completo() for s in collocazione.gruppo.membri)
                gruppi_per_chiave[chiave] = gruppo
                collocazioni.append(CollocazioneGruppoBlocco(gruppo, blocco))
            riga = dict(mese)
            riga["gruppi"] = tuple(
                gruppi_per_chiave[tuple(s.get_nome_completo() for s in g.membri)]
                for g in mese["gruppi"]
            )
            riga["collocazioni"] = tuple(collocazioni)
            riga["adiacenze_prima"] = set(quadro.adiacenze_prima)
            if disposizione.modificata_manualmente:
                riga["modificata_manualmente"] = True
            else:
                riga.pop("modificata_manualmente", None)
            for cache in ("report_completo", "statistiche_generali", "aula", "configurazione_aula"):
                riga.pop(cache, None)
            self.fotografia.verifica_risultato(riga)
            nuovi.append(riga)
        return nuovi
