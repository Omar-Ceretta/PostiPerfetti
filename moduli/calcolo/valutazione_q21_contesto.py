# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""I1b/2b: fotografie R12/S1/R2 con Storico e durata 1..10.

Non avvia la ricerca e non importa il laboratorio Q*. Le metriche veloci
sono verificate indipendentemente dalle funzioni produttive di politica_annuale.
Le frequenze iniziali influenzano la presenza di una vicinanza pregressa; il
numero di occorrenze non viene impropriamente sommato ai riusi del periodo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations

from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.metrica_pulizia import Gruppo, livello_affinita, livello_incompatibilita, nome_completo, peso_incompatibilita
from moduli.calcolo.politica_annuale import (
    _obiettivo_temporale, ammissibile_s1, chiave_r12, descrivi_stagione,
    metriche_ordine, metriche_temporali,
)
from moduli.dominio.validazione_blocchi import valida_soluzione_blocchi


@dataclass(frozen=True)
class FotoContestuale:
    metriche: dict
    temporali: dict
    profilo: tuple
    ultima: int
    miste: int

    @property
    def chiave(self):
        return chiave_r12(self.metriche), _obiettivo_temporale(self.temporali)


def protetta(nuova, base, genere_misto):
    """Identiche guardie Q5: non aggiunge una diversa gerarchia dei pesi."""
    return (ammissibile_s1(nuova.metriche, nuova.temporali, base.metriche, base.temporali)
            and nuova.profilo <= base.profilo
            and nuova.temporali['massimo_riusi_mese'] <= base.temporali['massimo_riusi_mese']
            and nuova.ultima >= base.ultima
            and (not genere_misto or nuova.miste >= base.miste))


def _storico(frequenze):
    if frequenze is None:
        return frozenset()
    if not isinstance(frequenze, Mapping):
        raise TypeError('Le frequenze iniziali devono essere una mappa.')
    coppie = set()
    for coppia, n in frequenze.items():
        if (not isinstance(coppia, (tuple, frozenset, set, list)) or len(coppia) != 2
                or any(type(x) is not str or not x.strip() for x in coppia)
                or len(set(coppia)) != 2 or type(n) is not int or n < 1):
            raise ValueError('Coppia/frequenza dello Storico iniziale non valida.')
        coppie.add(tuple(sorted(coppia)))
    return frozenset(coppie)


class ProblemaContestuale:
    """Precalcola geometria e vincoli; valuta da 1 a 10 mesi, anche con Storico."""

    def __init__(self, mesi, studenti, schema, *, frequenze_storico=None):
        if not isinstance(mesi, (list, tuple)) or not 1 <= len(mesi) <= 10:
            raise ValueError('Servono da 1 a 10 mesi fisici completi.')
        self.durata = len(mesi)
        self.studenti, self.schema = tuple(studenti), schema
        self.n = len(self.studenti)
        self.nomi = {nome_completo(s): i for i, s in enumerate(self.studenti)}
        if len(self.nomi) != self.n:
            raise ValueError('Studenti duplicati.')
        self.storico = _storico(frequenze_storico)
        self.blocchi = tuple(schema.blocchi)
        self.posti = [(b, p) for b in self.blocchi for p in b.posti]
        self.archi, self.fette = [], []
        pos = 0
        for blocco in self.blocchi:
            self.fette.append((pos, pos + blocco.capienza))
            self.archi.extend((i, i + 1) for i in range(pos, pos + blocco.capienza - 1))
            pos += blocco.capienza
        if len(self.posti) != self.n:
            raise ValueError('Schema e numero studenti incoerenti.')
        self.ammessi = [tuple(
            (s.nota_posizione != 'PRIMA' or b.zona_prima)
            and ((s.nota_posizione == 'FISSO') == posto.ancora_fisso)
            for b, posto in self.posti) for s in self.studenti]
        self.ultima = tuple(s.nota_posizione == 'ULTIMA' for s in self.studenti)
        self.inc = [0] * (self.n * self.n)
        self.aff = [0] * (self.n * self.n)
        self.mix = [0] * (self.n * self.n)
        self.ends = {}
        self.storico_indici = set()
        for a, b in combinations(range(self.n), 2):
            k = a * self.n + b
            self.inc[k] = livello_incompatibilita(self.studenti[a], self.studenti[b])
            self.aff[k] = livello_affinita(self.studenti[a], self.studenti[b])
            self.mix[k] = self.studenti[a].sesso != self.studenti[b].sesso
            self.ends[k] = (a, b)
            if tuple(sorted((nome_completo(self.studenti[a]), nome_completo(self.studenti[b])))) in self.storico:
                self.storico_indici.add(k)
        self.iniziali = []
        viste = set(self.storico)
        for mese in mesi:
            if mese['schema_identita'] != schema.identita_semantica():
                raise ValueError('Schema differente fra i mesi.')
            esito = valida_soluzione_blocchi(self.studenti, mese['gruppi'], schema, mese['collocazioni'])
            if not esito.valida:
                raise ValueError('Violazione HARD nella disposizione di partenza.')
            if set(tuple(sorted(pair)) for pair in mese['adiacenze_prima']) != viste:
                raise ValueError('La sequenza di adiacenze_prima non corrisponde allo Storico iniziale.')
            for gruppo in mese['gruppi']:
                nomi = [nome_completo(s) for s in gruppo.membri]
                viste.update(tuple(sorted((a, b))) for a, b in zip(nomi, nomi[1:]))
            collocazioni = {c.blocco.id: c for c in mese['collocazioni']}
            self.iniziali.append([
                self.nomi[nome_completo(s)] for b in self.blocchi
                for s in collocazioni[b.id].gruppo.membri
            ])
        if not all(self.valida(row) for row in self.iniziali):
            raise ValueError('Disposizione di partenza non valida.')

    def coppia(self, a, b):
        return min(a, b) * self.n + max(a, b)

    def valida(self, row):
        return (len(row) == self.n and sorted(row) == list(range(self.n))
                and all(self.ammessi[s][p] for p, s in enumerate(row))
                and all(self.inc[self.coppia(row[a], row[b])] != 3 for a, b in self.archi))

    def valuta(self, rows):
        if len(rows) != self.durata or not all(self.valida(row) for row in rows):
            raise ValueError('Righe incomplete oppure con violazioni HARD.')
        inc, aff = [0] * 4, [0] * 4
        maschere, profilo = {}, []
        ultima = miste = 0
        for m, row in enumerate(rows):
            per_mese = [0] * 4
            for a, b in self.archi:
                k = self.coppia(row[a], row[b])
                livello, amicizia = self.inc[k], self.aff[k]
                inc[livello] += 1; per_mese[livello] += 1
                aff[amicizia] += 1
                miste += self.mix[k]
                maschere[k] = maschere.get(k, 0) | (1 << m)
            profilo.append(peso_incompatibilita(dict(enumerate(per_mese))))
            ultima += sum(self.ultima[s] and self.posti[p][0].zona_ultima for p, s in enumerate(row))
        individuali, mensili = [0] * self.n, [0] * self.durata
        nr = sg = g1 = g2 = g3 = ngap = 0
        for k, mask in maschere.items():
            posizioni = [m for m in range(self.durata) if mask & (1 << m)]
            pregressa = k in self.storico_indici
            ripetuti = posizioni if pregressa else posizioni[1:]
            n = len(ripetuti)
            nr += n
            intervalli = [b - a for a, b in zip(posizioni, posizioni[1:])]
            sg += sum(intervalli)
            ngap += len(intervalli)
            g1 += sum(d == 1 for d in intervalli)
            g2 += sum(d <= 2 for d in intervalli)
            g3 += sum(d <= 3 for d in intervalli)
            a, b = self.ends[k]
            individuali[a] += n; individuali[b] += n
            for m in ripetuti:
                mensili[m] += 1
        metriche = dict(riusi=nr, incompatibilita_l1=inc[1], incompatibilita_l2=inc[2],
            incompatibilita_l3=inc[3], affinita_l1=aff[1], affinita_l2=aff[2], affinita_l3=aff[3],
            affinita_totali=sum(aff[1:]), affinita_pesate=aff[1] + 2 * aff[2] + 3 * aff[3],
            massimo_individuale=max(individuali, default=0), studenti_con_riuso=sum(x > 0 for x in individuali))
        temporali = dict(primo_mese_riuso=next((m + 1 for m, v in enumerate(mensili) if v), 0),
            mesi_con_riuso=sum(v > 0 for v in mensili), massimo_riusi_mese=max(mensili, default=0),
            gap_1=g1, gap_le_2=g2, gap_le_3=g3, gap_medio=sg / ngap if ngap else None)
        return FotoContestuale(metriche, temporali, tuple(profilo), ultima, miste)

    def costruisci(self, rows):
        if len(rows) != self.durata or not all(self.valida(row) for row in rows):
            raise ValueError('Non si costruisce una disposizione invalida.')
        risultati, viste = [], set(self.storico)
        for row in rows:
            gruppi, collocazioni = [], []
            for b, (a, z) in zip(self.blocchi, self.fette):
                gruppo = Gruppo('coppia' if b.capienza == 2 else 'terzetto',
                                [self.studenti[i] for i in row[a:z]])
                gruppi.append(gruppo)
                collocazioni.append(CollocazioneGruppoBlocco(gruppo, b))
            risultati.append(dict(gruppi=gruppi, collocazioni=tuple(collocazioni),
                schema_identita=self.schema.identita_semantica(), adiacenze_prima=set(viste)))
            for c in collocazioni:
                nomi = [nome_completo(s) for s in c.gruppo.membri]
                viste.update(tuple(sorted((a,b))) for a,b in zip(nomi, nomi[1:]))
        return risultati

    def priorita(self, rows):
        conteggi = {}
        for row in rows:
            for a,b in self.archi:
                k = self.coppia(row[a],row[b]); conteggi[k] = conteggi.get(k,0)+1
        ordinati = []
        for m,row in enumerate(rows):
            gravita = [0]*self.n
            for a,b in self.archi:
                k = self.coppia(row[a],row[b])
                if conteggi[k] > 1 or k in self.storico_indici or self.inc[k]:
                    gravita[a] += 1; gravita[b] += 1
            pos = [p for p,(_,posto) in enumerate(self.posti) if not posto.ancora_fisso]
            pos.sort(key=lambda p: (-gravita[p],p))
            ordinati.append((m,pos,gravita))
        return sorted(ordinati,key=lambda x: (-sum(x[2]),-x[0]))

    def verifica(self, rows, foto=None):
        """Oracolo produttivo, indipendente dal calcolo veloce."""
        mesi = self.costruisci(rows)
        descrittori = descrivi_stagione(mesi,'personalizzata')
        ordine = list(range(1,self.durata+1))
        f = self.valuta(rows)
        if foto is not None and f != foto:
            raise ValueError('Foto contestuale diversa dal riferimento.')
        if (metriche_ordine(descrittori,ordine,blacklist_iniziale=self.storico) != f.metriche
                or metriche_temporali(descrittori,ordine,blacklist_iniziale=self.storico) != f.temporali):
            raise ValueError('Le metriche veloci non coincidono con la politica annuale produttiva.')
        return f


def riordina_contestuale(mesi, studenti, schema, config_calcolo, *, frequenze_storico=None, genere_misto=False):
    """R2 nativo e protezioni contestuali; restituisce la base se peggiora."""
    from moduli.calcolo.annuale import riordina_stagione_personalizzata_gui
    from moduli.persistenza.strato_storico import frequenze_blacklist_adiacenze
    iniziali = _storico(frequenze_storico)
    estratte = _storico(frequenze_blacklist_adiacenze(config_calcolo, modo='personalizzata'))
    if iniziali != estratte:
        raise ValueError('Il contesto R2 non coincide con lo Storico del calcolo.')
    p = ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    base = p.verifica(p.iniziali)
    proposta,_ = riordina_stagione_personalizzata_gui(mesi,config_calcolo,
        ordine_iniziale=list(range(1,len(mesi)+1)))
    q = ProblemaContestuale(proposta,studenti,schema,frequenze_storico=frequenze_storico)
    nuova = q.verifica(q.iniziali)
    if (sorted(map(tuple, q.iniziali)) != sorted(map(tuple, p.iniziali))
            or nuova.metriche != base.metriche or nuova.ultima != base.ultima
            or nuova.miste != base.miste):
        raise ValueError('R2 ha cambiato le assegnazioni, non solo il loro ordine.')
    scelta = protetta(nuova,base,genere_misto) and nuova.chiave <= base.chiave
    return (proposta if scelta else p.costruisci(p.iniziali)), (nuova if scelta else base), scelta
