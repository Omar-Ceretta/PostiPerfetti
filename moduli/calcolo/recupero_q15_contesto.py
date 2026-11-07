# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""I1b/2c: Q15 contestuale, recupera finaliste migliori escluse dalle guardie.

La distanza dalle guardie guida soltanto la ricerca locale: non modifica
la graduatoria R12/R2 o i suoi pesi. Ogni passo conserva le protezioni
della finalista iniziale; la promozione richiede ANCHE tutte le protezioni
del vincitore Q14 immutabile e una chiave R12/R2 strettamente migliore.
Un tentativo incompleto non viene mai restituito come soluzione promossa.
"""
from dataclasses import asdict
from itertools import combinations
from time import perf_counter

from moduli.calcolo.valutazione_q21_contesto import ProblemaContestuale, FotoContestuale, protetta


def _foto(d):
    return FotoContestuale(**dict(d, profilo=tuple(d['profilo'])))


def _serializza(f):
    return asdict(f)


MAX_VALUTAZIONI=24000
MAX_TENTATIVI=96000


def distanza(f,base,misto):
    """Debiti delle guardie native, senza penalita nuove nel punteggio."""
    m,b=f.metriche,base.metriche;t,u=f.temporali,base.temporali
    d=[max(0,m[k]-b[k]) for k in ('incompatibilita_l3','incompatibilita_l2',
        'incompatibilita_l1','massimo_individuale')]
    d += [max(0,b[k]-m[k]) for k in ('affinita_pesate','affinita_l3')]
    # Nel Q21 congelato (10 mesi) l'assenza di riuso equivale al mese 11.
    # Nei contesti piu' brevi la stessa regola e' (durata + 1): usare 11
    # altererebbe il debito numerico Q15 e l'ordine dei recuperi, anche se
    # le guardie booleane restassero corrette.
    durata = len(f.profilo)
    if not 1 <= durata <= 10 or len(base.profilo) != durata:
        raise ValueError('Q15 richiede fotografie della stessa durata (1..10 mesi).')
    assente = durata + 1
    d.append(max(0,(u['primo_mese_riuso'] or assente)
                    -(t['primo_mese_riuso'] or assente)))
    d += [max(0,t[k]-u[k]) for k in ('gap_1','gap_le_2','gap_le_3','massimo_riusi_mese')]
    diff=next((a-b for a,b in zip(f.profilo,base.profilo) if a!=b),0)
    d += [max(0,diff),max(0,base.ultima-f.ultima),max(0,base.miste-f.miste) if misto else 0]
    if (not any(d)) != protetta(f,base,misto):
        raise ValueError('Distanza Q15 diversa dalle guardie native.')
    return tuple(d)


def chiave_ricerca(f,base,misto):
    debiti=distanza(f,base,misto)
    return sum(v>0 for v in debiti),sum(debiti),debiti,f.chiave,-f.ultima


def promuovibile(f,base,iniziale,misto):
    return (protetta(f,base,misto) and f.chiave<base.chiave
        and protetta(f,iniziale,misto) and f.chiave<=iniziale.chiave
        and f.metriche['riusi']<=iniziale.metriche['riusi'])


def compatibili_additivi(a,b,corrente,iniziale,base,misto):
    """Filtro esatto solo per due mesi distinti; i riusi si ricalcolano."""
    metriche={k:a.metriche[k]+b.metriche[k]-corrente.metriche[k] for k in (
        'incompatibilita_l3','incompatibilita_l2','incompatibilita_l1','affinita_pesate','affinita_l3')}
    if any(metriche[k]>min(iniziale.metriche[k],base.metriche[k]) for k in (
        'incompatibilita_l3','incompatibilita_l2','incompatibilita_l1')):return False
    if any(metriche[k]<max(iniziale.metriche[k],base.metriche[k]) for k in ('affinita_pesate','affinita_l3')):return False
    profilo=tuple(x+y-z for x,y,z in zip(a.profilo,b.profilo,corrente.profilo))
    return (profilo<=min(iniziale.profilo,base.profilo)
        and a.ultima+b.ultima-corrente.ultima>=max(iniziale.ultima,base.ultima)
        and (not misto or a.miste+b.miste-corrente.miste>=max(iniziale.miste,base.miste)))


def ripara(mesi,studenti,schema,base,*,genere_misto=False,
           max_valutazioni=MAX_VALUTAZIONI,max_tentativi=MAX_TENTATIVI,
           annullato=lambda:False, frequenze_storico=None):
    for n in (max_valutazioni,max_tentativi):
        if not isinstance(n,int) or isinstance(n,bool) or n<1:raise ValueError('Limiti Q15 interi positivi.')
    inizio=perf_counter();p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    rows=[list(r) for r in p.iniziali];iniziale=corrente=p.valuta(rows)
    p.verifica(rows,iniziale)
    if iniziale.chiave>=base.chiave or protetta(iniziale,base,genere_misto):
        raise ValueError('Q15 richiede una finalista migliore ma esclusa dalle guardie.')
    valutazioni=tentativi=passi=filtrate=0;stop='nessuna_mossa_nel_vicinato';percorso=[]
    def limite():
        if annullato():return 'annullato'
        if valutazioni>=max_valutazioni:return 'limite_valutazioni'
        if tentativi>=max_tentativi:return 'limite_tentativi'
        return None
    while not limite() and not promuovibile(corrente,base,iniziale,genere_misto):
        migliore=corrente;scelta=None;scambi=[]
        # Tutti gli scambi; i cicli di tre possono superare un blocco locale.
        for taglia in (2,3):
            for m,posizioni,_ in p.priorita(rows):
                for indici in combinations(posizioni,taglia):
                    for direzione in ((1,) if taglia==2 else (1,2)):
                        if limite():break
                        tentativi+=1;vecchi=[rows[m][i] for i in indici]
                        nuovi=vecchi[direzione:]+vecchi[:direzione]
                        for i,s in zip(indici,nuovi):rows[m][i]=s
                        try:
                            if not p.valida(rows[m]):continue
                            f=p.valuta(rows);valutazioni+=1
                            if taglia==2:
                                scambi.append((f,(m,tuple(indici),tuple(nuovi))))
                            if (protetta(f,iniziale,genere_misto) and f.chiave<=iniziale.chiave
                                    and f.metriche['riusi']<=iniziale.metriche['riusi']
                                    and chiave_ricerca(f,base,genere_misto)<chiave_ricerca(migliore,base,genere_misto)):
                                migliore=f;scelta=[(m,indici,nuovi)]
                        finally:
                            for i,s in zip(indici,vecchi):rows[m][i]=s
                    if limite():break
                if limite():break
            if scelta is not None or limite():break
        if scelta is None and not limite():
            # Due scambi atomici in mesi distinti possono compensarsi.
            # L'additivita dei soli vincoli sociali scarta presto le coppie
            # impossibili; cronologia e riusi si valutano sempre per intero.
            pool=sorted(scambi,key=lambda x:(chiave_ricerca(x[0],base,genere_misto),x[0].chiave,x[1]))
            for (foto1,prima),(foto2,seconda) in combinations(pool,2):
                if limite():break
                if prima[0]==seconda[0]:continue
                tentativi+=1;vecchi=[]
                if not compatibili_additivi(foto1,foto2,corrente,iniziale,base,genere_misto):
                    filtrate+=1;continue
                for m,indici,nuovi in (prima,seconda):
                    vecchi.append((m,indici,[rows[m][i] for i in indici]))
                    for i,s in zip(indici,nuovi):rows[m][i]=s
                try:
                    if not all(p.valida(rows[m]) for m in {prima[0],seconda[0]}):continue
                    f=p.valuta(rows);valutazioni+=1
                    if (protetta(f,iniziale,genere_misto) and f.chiave<=iniziale.chiave
                            and f.metriche['riusi']<=iniziale.metriche['riusi']
                            and chiave_ricerca(f,base,genere_misto)<chiave_ricerca(migliore,base,genere_misto)):
                        migliore=f;scelta=[prima,seconda]
                finally:
                    for m,indici,studenti_prima in reversed(vecchi):
                        for i,s in zip(indici,studenti_prima):rows[m][i]=s
        if scelta is None:break
        for m,indici,nuovi in scelta:
            for i,s in zip(indici,nuovi):rows[m][i]=s
        corrente=migliore;passi+=1
        percorso.append(dict(modifiche=[dict(mese=m+1,posti=list(indici),studenti=list(nuovi))
            for m,indici,nuovi in scelta],foto=_serializza(corrente)))
    recuperata=promuovibile(corrente,base,iniziale,genere_misto) and not annullato()
    stop=limite() or ('recuperata' if recuperata else stop)
    risultato=p.costruisci(rows);p.verifica(rows,corrente)
    return (risultato if recuperata else None),dict(secondi=perf_counter()-inizio,
        valutazioni=valutazioni,mosse_esaminate=tentativi,passi=passi,stop=stop,
        combinazioni_filtrate=filtrate,
        recuperata=recuperata,prima=_serializza(iniziale),esplorata=_serializza(corrente),
        debiti_prima=distanza(iniziale,base,genere_misto),
        debiti_dopo=distanza(corrente,base,genere_misto),percorso=percorso)


def verifica_percorso(mesi,studenti,schema,base,info,misto,*,frequenze_storico=None):
    """Ricalcola le mosse sul layout fisico e controlla ogni protezione."""
    p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico);rows=[list(r) for r in p.iniziali]
    iniziale=corrente=p.valuta(rows)
    if _foto(info['prima'])!=iniziale:raise ValueError('Partenza Q15 alterata.')
    for passo in info['percorso']:
        modifiche=passo['modifiche'];toccati=set()
        if len(modifiche) not in (1,2):raise ValueError('Passo Q15 estraneo.')
        if len(modifiche)==2 and modifiche[0]['mese']==modifiche[1]['mese']:
            raise ValueError('I due scambi Q15 richiedono mesi distinti.')
        for modifica in modifiche:
            m=modifica['mese']-1;indici=modifica['posti'];nuovi=modifica['studenti']
            if (not 0<=m<p.durata or len(indici) not in ((2,) if len(modifiche)==2 else (2,3))
                    or len(set(indici))!=len(indici) or len(nuovi)!=len(indici)
                    or any(not 0<=i<p.n or p.posti[i][1].ancora_fisso or (m,i) in toccati for i in indici)
                    or sorted(nuovi)!=sorted(rows[m][i] for i in indici)):
                raise ValueError('Mossa Q15 estranea.')
            toccati.update((m,i) for i in indici)
            for i,s in zip(indici,nuovi):rows[m][i]=s
        if not all(p.valida(rows[m]) for m,_ in toccati):raise ValueError('Mossa Q15 viola hard.')
        f=p.valuta(rows)
        if (f!=_foto(passo['foto']) or not protetta(f,iniziale,misto)
                or f.chiave>iniziale.chiave or f.metriche['riusi']>iniziale.metriche['riusi']
                or chiave_ricerca(f,base,misto)>=chiave_ricerca(corrente,base,misto)):
            raise ValueError('Percorso Q15 fuori dalle protezioni.')
        corrente=f
    if corrente!=_foto(info['esplorata']) or len(info['percorso'])!=info['passi']:
        raise ValueError('Esito esplorato Q15 alterato.')
    if info['recuperata'] and not promuovibile(corrente,base,iniziale,misto):
        raise ValueError('Promozione Q15 non protetta.')
    return p.costruisci(rows),corrente
