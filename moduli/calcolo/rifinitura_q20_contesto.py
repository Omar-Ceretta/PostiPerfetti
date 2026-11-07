# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""I1b/2c: vicinato Q20 contestuale, senza hook o dipendenze di laboratorio.

Riproduce le mosse Q20 (ciclo 3, doppio scambio in *uno stesso* mese)
applicando la stessa valutazione al contesto completo: storico e 1..10 mesi.
Il percorso fisico registrato e' verificabile indipendentemente dal runner.
"""
from dataclasses import asdict
from itertools import combinations
from time import perf_counter

from moduli.calcolo.valutazione_q21_contesto import ProblemaContestuale, protetta as protetta_base

MAX_VALUTAZIONI = 24000
MAX_TENTATIVI = 96000
PERMUTAZIONI = {3: ((1, 2, 0), (2, 0, 1)),
                4: ((1, 0, 3, 2), (2, 3, 0, 1), (3, 2, 1, 0))}


def _foto(f):
    """Serializzazione Q20 compatibile con i checkpoint JSON nativi."""
    return dict(asdict(f), profilo=list(f.profilo))


def _limite_intero(valore):
    if type(valore) is not int or valore < 1:
        raise ValueError('I limiti Q20 devono essere interi positivi.')


def misure_riga(p, row):
    inc = [0] * 4
    aff = [0] * 4
    miste = 0
    for a, b in p.archi:
        k = p.coppia(row[a], row[b])
        inc[p.inc[k]] += 1
        aff[p.aff[k]] += 1
        miste += p.mix[k]
    return dict(l1=inc[1], l2=inc[2], aff=aff[1]+2*aff[2]+3*aff[3],
                aff3=aff[3],
                ultima=sum(p.ultima[s] and p.posti[i][0].zona_ultima for i,s in enumerate(row)),
                miste=miste)


def filtro(prima, dopo, corrente, base, misto, mese):
    if dopo['aff'] <= prima['aff']:
        return False
    for locale, globale in (('l1','incompatibilita_l1'),('l2','incompatibilita_l2')):
        if corrente.metriche[globale]+dopo[locale]-prima[locale] > base.metriche[globale]:
            return False
    if corrente.metriche['affinita_l3']+dopo['aff3']-prima['aff3'] < base.metriche['affinita_l3']:
        return False
    if corrente.ultima+dopo['ultima']-prima['ultima'] < base.ultima:
        return False
    if misto and corrente.miste+dopo['miste']-prima['miste'] < base.miste:
        return False
    profilo = list(corrente.profilo)
    profilo[mese] = dopo['l1']+10*dopo['l2']
    return tuple(profilo) <= base.profilo


def protetta(f, base, misto):
    return protetta_base(f,base,misto) and f.metriche['riusi'] <= base.metriche['riusi']


def ripara(mesi, studenti, schema, *, frequenze_storico=None, genere_misto=False,
           max_valutazioni=MAX_VALUTAZIONI, max_tentativi=MAX_TENTATIVI,
           annullato=lambda: False):
    _limite_intero(max_valutazioni)
    _limite_intero(max_tentativi)
    t0=perf_counter()
    p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    rows=[r[:] for r in p.iniziali]
    base=corrente=p.verifica(rows)
    liberi=[i for i,(_,posto) in enumerate(p.posti) if not posto.ancora_fisso]
    tentativi=valutazioni=filtrate=0
    percorso=[]

    def limite():
        if annullato(): return 'annullato'
        if valutazioni>=max_valutazioni: return 'limite_valutazioni'
        if tentativi>=max_tentativi: return 'limite_tentativi'
        return None

    while not limite():
        migliore=corrente
        scelta=None
        for taglia in (3,4):
            for m,row in enumerate(rows):
                prima=misure_riga(p,row)
                for indici in combinations(liberi,taglia):
                    vecchi=[row[i] for i in indici]
                    for perm in PERMUTAZIONI[taglia]:
                        if limite(): break
                        tentativi+=1
                        nuovi=[vecchi[k] for k in perm]
                        for i,s in zip(indici,nuovi):row[i]=s
                        try:
                            if not p.valida(row): continue
                            dopo=misure_riga(p,row)
                            if not filtro(prima,dopo,corrente,base,genere_misto,m):
                                filtrate+=1
                                continue
                            f=p.valuta(rows)
                            valutazioni+=1
                            if f.chiave<migliore.chiave and protetta(f,base,genere_misto):
                                migliore=f
                                scelta=(m,indici,nuovi)
                        finally:
                            for i,s in zip(indici,vecchi):row[i]=s
                    if limite(): break
                if limite():break
            if scelta is not None or limite():break
        if scelta is None:break
        m,indici,nuovi=scelta
        for i,s in zip(indici,nuovi):rows[m][i]=s
        corrente=migliore
        percorso.append(dict(mese=m+1,posti=list(indici),studenti=list(nuovi),foto=_foto(corrente)))
    nuovi=p.costruisci(rows)
    p.verifica(rows,corrente)
    if not protetta(corrente,base,genere_misto):
        raise ValueError('Q20 contestuale fuori dalle protezioni.')
    return nuovi,dict(prima=_foto(base),dopo=_foto(corrente),percorso=percorso,
        valutazioni=valutazioni,mosse_esaminate=tentativi,filtrate=filtrate,
        stop=limite() or 'nessuna_mossa_migliore',secondi=perf_counter()-t0)


def verifica_percorso(mesi,studenti,schema,info,*,frequenze_storico=None,genere_misto=False):
    """Replay delle sole mosse accettate, non della ricerca/generazione."""
    p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    rows=[r[:] for r in p.iniziali]
    base=corrente=p.verifica(rows)
    if _foto(base)!=info['prima']:
        raise ValueError('Foto iniziale Q20 alterata.')
    for passo in info['percorso']:
        m=passo['mese']-1
        indici=passo['posti']
        nuovi=passo['studenti']
        if (type(m) is not int or not 0<=m<p.durata or len(indici) not in (3,4)
                or len(set(indici))!=len(indici) or indici!=sorted(indici)
                or any(type(i) is not int or not 0<=i<p.n or p.posti[i][1].ancora_fisso
                       for i in indici) or len(nuovi)!=len(indici)):
            raise ValueError('Mossa Q20 non ammessa.')
        vecchi=[rows[m][i] for i in indici]
        if nuovi not in [[vecchi[k] for k in v] for v in PERMUTAZIONI[len(indici)]]:
            raise ValueError('Permutazione Q20 estranea.')
        for i,s in zip(indici,nuovi):rows[m][i]=s
        if not p.valida(rows[m]):raise ValueError('Mossa Q20 viola HARD.')
        f=p.valuta(rows)
        if (_foto(f)!=passo['foto'] or not protetta(f,base,genere_misto)
                or f.chiave>=corrente.chiave
                or f.metriche['affinita_pesate']<=corrente.metriche['affinita_pesate']):
            raise ValueError('Passo Q20 non protetto o senza aumento delle affinita.')
        corrente=f
    if _foto(corrente)!=info['dopo']:
        raise ValueError('Foto finale Q20 alterata.')
    risultato=p.costruisci(rows)
    p.verifica(rows,corrente)
    return risultato,corrente
