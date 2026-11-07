# -*- coding: utf-8 -*-
"""Gate D1 — operazioni pure sulla bozza *post-generazione* del Layout unico.

Non legge/scrive lo Storico né la GUI. Non cambia la geometria: lo scambio
integrale degli occupanti di due banchi di pari capienza NON è lo spostamento
fisico dei banchi, che richiederà un contratto e un Gate separati.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.disposizione_effettiva import DisposizioneEffettiva
from moduli.dominio.fotografia_generazione_layout import FotografiaGenerazioneLayout
from moduli.dominio.layout_unico import verifica_geometria_output
from moduli.dominio.metrica_pulizia import (
    Gruppo, livello_affinita, livello_incompatibilita,
)
from moduli.dominio.validazione_blocchi import valida_soluzione_blocchi


@dataclass(frozen=True, slots=True)
class MetricheManuali:
    """Indicatori diagnostici della bozza, non il punteggio Q21 del solver."""

    incompatibilita_l1: int
    incompatibilita_l2: int
    affinita_l1: int
    affinita_l2: int
    affinita_l3: int
    riusi_storico: int
    ultima_in_zona: int
    adiacenze_miste: int


def _storico_normalizzato(frequenze: Mapping | None) -> frozenset[tuple[str, str]]:
    if frequenze is None:
        return frozenset()
    if not isinstance(frequenze, Mapping):
        raise TypeError("Le frequenze dello Storico devono essere una mappa.")
    risultato = set()
    for coppia, n in frequenze.items():
        if (not isinstance(coppia, (tuple, frozenset)) or len(coppia) != 2
                or any(type(x) is not str or not x.strip() for x in coppia)
                or len(set(coppia)) != 2 or type(n) is not int or n < 1):
            raise ValueError("Coppia/frequenza dello Storico non valida.")
        risultato.add(tuple(sorted(coppia)))
    return frozenset(risultato)


def _controlla(disposizione: DisposizioneEffettiva, foto: FotografiaGenerazioneLayout) -> None:
    """Riusa geometria e validatore HARD del programma, senza il motore."""
    if not isinstance(foto, FotografiaGenerazioneLayout):
        raise TypeError("Serve la fotografia congelata della generazione.")
    if disposizione.modo != "personalizzata":
        raise ValueError("L'editing D1 richiede il Layout unico.")
    if disposizione.genere_misto != foto.genere_misto:
        raise ValueError("Opzione genere misto differente dalla fotografia.")
    geometria = verifica_geometria_output(foto.layout, disposizione)
    if not geometria.valido:
        raise ValueError("Geometria alterata: " + ", ".join(
            problema.codice for problema in geometria.problemi))
    studenti = foto.crea_studenti()
    per_nome = {s.get_nome_completo(): s for s in studenti}
    occupanti = dict(disposizione.occupazioni)
    if set(occupanti.values()) != set(per_nome) or len(occupanti) != len(per_nome):
        raise ValueError("Studenti estranei, mancanti o duplicati nella bozza.")
    gruppi = []
    collocazioni = []
    for blocco in foto.layout.schema.blocchi:
        nomi = [occupanti[p.id] for p in blocco.posti]
        gruppo = Gruppo("coppia" if blocco.capienza == 2 else "terzetto",
                        tuple(per_nome[nome] for nome in nomi))
        gruppi.append(gruppo)
        collocazioni.append(CollocazioneGruppoBlocco(gruppo, blocco))
    esito = valida_soluzione_blocchi(studenti, gruppi, foto.layout.schema, collocazioni)
    if not esito.valida:
        raise ValueError("Vincoli obbligatori: " + ", ".join(esito.errori_duri))
    if disposizione.studente_fisso != next(
        (s.get_nome_completo() for s in studenti if s.nota_posizione == "FISSO"), None
    ):
        raise ValueError("Identità dello studente FISSO alterata.")


def misura(disposizione: DisposizioneEffettiva, foto: FotografiaGenerazioneLayout,
           storico: frozenset[tuple[str, str]]) -> MetricheManuali:
    """Conta solo vicini veri A–B/B–C, usando i vincoli fotografati."""
    copie = [s.crea_studente() for s in foto.studenti]
    studenti = {s.get_nome_completo(): s for s in copie}
    per_posto = dict(disposizione.occupazioni)
    l1 = l2 = a1 = a2 = a3 = ultima = miste = 0
    for blocco in disposizione.blocchi:
        nomi = [per_posto[p.id] for p in blocco.posti]
        ultima += sum(studenti[n].nota_posizione == "ULTIMA" and blocco.zona_ultima
                      for n in nomi)
        for n1, n2 in zip(nomi, nomi[1:]):
            x, y = studenti[n1], studenti[n2]
            inc = livello_incompatibilita(x, y)
            aff = livello_affinita(x, y)
            l1 += inc == 1
            l2 += inc == 2
            a1 += aff == 1
            a2 += aff == 2
            a3 += aff == 3
            miste += x.sesso != y.sesso
    riusi = len(disposizione.adiacenze_rotazioni() & storico)
    return MetricheManuali(l1, l2, a1, a2, a3, riusi, ultima, miste)


def _avvisi(prima: MetricheManuali, dopo: MetricheManuali,
            genere_misto: bool) -> tuple[str, ...]:
    voci = (
        ("riusi_storico", "Riusi rispetto allo Storico", True),
        ("incompatibilita_l2", "Incompatibilità L2", True),
        ("incompatibilita_l1", "Incompatibilità L1", True),
        ("affinita_l3", "Affinità L3", False),
        ("affinita_l2", "Affinità L2", False),
        ("affinita_l1", "Affinità L1", False),
        ("ultima_in_zona", "Studenti ULTIMA nella zona", False),
    )
    if genere_misto:
        voci += (("adiacenze_miste", "Adiacenze di genere misto", False),)
    avvisi = []
    for campo, descrizione, peggiora_se_aumenta in voci:
        a, b = getattr(prima, campo), getattr(dopo, campo)
        peggiorato = b > a if peggiora_se_aumenta else b < a
        if peggiorato:
            avvisi.append(f"{descrizione}: {a} → {b}.")
    return tuple(avvisi)


@dataclass(frozen=True, slots=True)
class EsitoMossa:
    accettata: bool
    bozza: BozzaDisposizione
    motivo: str = ""
    avvisi: tuple[str, ...] = ()
    prima: MetricheManuali | None = None
    dopo: MetricheManuali | None = None


@dataclass(frozen=True, slots=True)
class BozzaDisposizione:
    """La sessione Qt possiederà questa bozza; nessuna modifica in-place.

    Creare soltanto per proposte DA_SALVARE/ANTEPRIMA. Il Gate D2 dovrà
    controllare fase, classe e mese PRIMA di inoltrare eventi di trascinamento.
    """

    fotografia: FotografiaGenerazioneLayout
    originale: DisposizioneEffettiva
    corrente: DisposizioneEffettiva
    storico: frozenset[tuple[str, str]]
    undo: tuple[DisposizioneEffettiva, ...] = ()

    @classmethod
    def crea(cls, foto: FotografiaGenerazioneLayout, proposta: DisposizioneEffettiva,
             *, frequenze_storico: Mapping | None = None) -> BozzaDisposizione:
        _controlla(proposta, foto)
        storico = _storico_normalizzato(frequenze_storico)
        return cls(foto, proposta, proposta, storico)

    def _applica(self, cambi: dict[str, str]) -> EsitoMossa:
        occupazioni = dict(self.corrente.occupazioni)
        if not cambi or all(occupazioni[p] == n for p, n in cambi.items()):
            return EsitoMossa(False, self, "Nessuna modifica da applicare.")
        try:
            nuove_occupazioni = tuple((posto, cambi.get(posto, nome))
                                     for posto, nome in self.corrente.occupazioni)
            nuove = replace(
                self.corrente,
                occupazioni=nuove_occupazioni,
                modificata_manualmente=(self.originale.modificata_manualmente
                                        or nuove_occupazioni != self.originale.occupazioni),
            )
            _controlla(nuove, self.fotografia)
        except ValueError as exc:
            return EsitoMossa(False, self, str(exc))
        prima = misura(self.corrente, self.fotografia, self.storico)
        dopo = misura(nuove, self.fotografia, self.storico)
        nuova_bozza = replace(self, corrente=nuove, undo=(*self.undo, self.corrente))
        return EsitoMossa(True, nuova_bozza, avvisi=_avvisi(
            prima, dopo, self.fotografia.genere_misto), prima=prima, dopo=dopo)

    def scambia_studenti(self, posto_a: str, posto_b: str) -> EsitoMossa:
        occupazioni = dict(self.corrente.occupazioni)
        if posto_a not in occupazioni or posto_b not in occupazioni:
            return EsitoMossa(False, self, "Posto inesistente nella disposizione.")
        if posto_a == posto_b:
            return EsitoMossa(False, self, "Il posto di partenza coincide con l'arrivo.")
        return self._applica({posto_a: occupazioni[posto_b],
                             posto_b: occupazioni[posto_a]})

    def scambia_occupanti_banchi(self, blocco_a: str, blocco_b: str) -> EsitoMossa:
        """Scambia *gruppi* di pari capienza, non coordinate dei banchi."""
        blocchi = {b.id: b for b in self.corrente.blocchi}
        if blocco_a not in blocchi or blocco_b not in blocchi:
            return EsitoMossa(False, self, "Banco inesistente nella disposizione.")
        if blocco_a == blocco_b:
            return EsitoMossa(False, self, "Il banco di partenza coincide con l'arrivo.")
        a, b = blocchi[blocco_a], blocchi[blocco_b]
        if a.capienza != b.capienza:
            return EsitoMossa(False, self, "Banchi da 2 e 3: scambio integrale non definito.")
        occupazioni = dict(self.corrente.occupazioni)
        modifiche = {}
        for p, q in zip(a.posti, b.posti, strict=True):
            modifiche[p.id] = occupazioni[q.id]
            modifiche[q.id] = occupazioni[p.id]
        return self._applica(modifiche)

    def avvisi_rispetto_originale(self) -> tuple[str, ...]:
        """Peggioramenti soft ancora presenti, non solo nell'ultima mossa.

        I dati vengono ricavati dalla disposizione corrente ogni volta, quindi
        Annulla/Ripristina e le mosse successive non lasciano avvisi obsoleti.
        """
        if self.corrente == self.originale:
            return ()
        prima = misura(self.originale, self.fotografia, self.storico)
        dopo = misura(self.corrente, self.fotografia, self.storico)
        return _avvisi(prima, dopo, self.fotografia.genere_misto)

    def annulla(self) -> BozzaDisposizione:
        if not self.undo:
            return self
        return replace(self, corrente=self.undo[-1], undo=self.undo[:-1])

    def ripristina_automatica(self) -> BozzaDisposizione:
        if self.corrente == self.originale:
            return self
        return replace(self, corrente=self.originale,
                       undo=(*self.undo, self.corrente))
