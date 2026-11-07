# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""I1b/2d: porting contestuale Q5 e Q12, senza dipendenze LAB.

Vincoli e vicinati invariati; Storico e 1..10 mesi gestiti dal valutatore
contestuale. La cancellazione impedisce la promozione di risultati incompleti.
"""
from collections import Counter
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations
from time import perf_counter
import time

from moduli.calcolo.valutazione_q21_contesto import ProblemaContestuale, protetta as protetta_base

MAX_VALUTAZIONI = 24000
MAX_TENTATIVI = 96000


def ripara_q5(mesi, studenti, schema, *, frequenze_storico=None,
              genere_misto=False, max_valutazioni=MAX_VALUTAZIONI,
              annullato=lambda: False):
    """Porting del vicinato Q5 (scambi/cicli) nel contesto completo."""
    if type(max_valutazioni) is not int or max_valutazioni < 1:
        raise ValueError('Q5 richiede un limite positivo.')
    start=perf_counter()
    p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    rows=[list(r) for r in p.iniziali]
    base=corrente=p.verifica(rows)
    valutazioni=tentativi=accettate=0
    mesi_toccati=set()
    def limite():
        if annullato():return 'annullato'
        if valutazioni>=max_valutazioni:return 'limite_valutazioni'
        return None
    while not limite():
        migliore,migliori_rows,miglior_mese=corrente,None,None
        for taglia in (2,3):
            for m,posizioni,gravita in p.priorita(rows):
                for indici in combinations(posizioni,taglia):
                    if taglia==3 and not any(gravita[k] for k in indici):continue
                    vecchi=[rows[m][k] for k in indici]
                    for direzione in ((1,) if taglia==2 else (1,2)):
                        if limite():break
                        tentativi+=1
                        nuovi=vecchi[direzione:]+vecchi[:direzione]
                        for i,s in zip(indici,nuovi):rows[m][i]=s
                        try:
                            if not p.valida(rows[m]):continue
                            f=p.valuta(rows);valutazioni+=1
                            if f.chiave<migliore.chiave and protetta_base(f,base,genere_misto):
                                migliore,migliori_rows,miglior_mese=f,[list(r) for r in rows],m
                        finally:
                            for i,s in zip(indici,vecchi):rows[m][i]=s
                    if limite():break
                if limite():break
            if migliori_rows is not None or limite():break
        if migliori_rows is None:break
        rows,corrente=migliori_rows,migliore
        accettate+=1;mesi_toccati.add(miglior_mese+1)
    nuovi=p.costruisci(rows)
    p.verifica(rows,corrente)
    if not protetta_base(corrente,base,genere_misto) or corrente.chiave>base.chiave:
        raise ValueError('Q5 fuori dalle protezioni.')
    return nuovi,dict(prima=asdict(base),dopo=asdict(corrente),
        secondi=perf_counter()-start,valutazioni=valutazioni,
        mosse_esaminate=tentativi,mosse_accettate=accettate,
        mesi_modificati=sorted(mesi_toccati),stop=limite() or 'nessuna_mossa_nel_vicinato')


def chiave_recupero(f):
    return (-f.ultima,f.chiave)


def protetta_q12(f,base,misto):
    return protetta_base(f,base,misto) and f.chiave<=base.chiave and f.metriche['riusi']<=base.metriche['riusi']

def rialloca_gruppi(p,row,annullato=lambda:False):
    """Massimo ULTIMA a gruppi/archi invariati; i pareggi tengono la riga."""
    prima=sum(p.ultima[s] and p.posti[k][0].zona_ultima for k,s in enumerate(row))
    tetto=min(sum(p.ultima),sum(b.capienza for b in p.blocchi if b.zona_ultima))
    if prima==tetto: return list(row),0
    gruppi=[tuple(row[a:z]) for a,z in p.fette];stati=0
    @lru_cache(None)
    def assegna(i,mask):
        nonlocal stati
        if annullato(): raise InterruptedError('Riallocazione Q12 annullata.')
        stati+=1
        if i==len(p.blocchi): return 0,()
        a,z=p.fette[i];soluzioni=[];b=p.blocchi[i]
        for j,g in enumerate(gruppi):
            if mask&(1<<j) or len(g)!=z-a: continue
            for orientata in sorted(set((g,g[::-1]))):
                if not all(p.ammessi[s][a+k] for k,s in enumerate(orientata)): continue
                resto=assegna(i+1,mask|(1<<j))
                if resto is not None:
                    punti=sum(p.ultima[s] and b.zona_ultima for s in orientata)
                    soluzioni.append((punti+resto[0],orientata+resto[1]))
        return min(soluzioni,key=lambda r:(-r[0],r[1])) if soluzioni else None
    out=assegna(0,0)
    if out is None: raise ValueError('Riga Q12 valida senza riallocazione fattibile.')
    nuova=list(out[1]) if out[0]>prima else list(row)
    archi=lambda r:Counter(p.coppia(r[a],r[b]) for a,b in p.archi)
    if not p.valida(nuova) or archi(nuova)!=archi(row):
        raise ValueError('Riallocazione Q12 ha modificato hard o adiacenze.')
    return nuova,stati


def mosse_mirate(p,rows,taglia):
    """Porta un ULTIMA fuori zona verso un posto in fondo, senza FISSO."""
    for m,row in enumerate(rows):
        liberi=[k for k,(_,posto) in enumerate(p.posti) if not posto.ancora_fisso]
        mancanti=[k for k in liberi if p.ultima[row[k]] and not p.posti[k][0].zona_ultima]
        destinazioni=[k for k in liberi if p.posti[k][0].zona_ultima and not p.ultima[row[k]]]
        visti=set()
        for a in mancanti:
            for b in destinazioni:
                if taglia==2:
                    indici=tuple(sorted((a,b)))
                    if indici not in visti: visti.add(indici);yield m,indici,1
                elif taglia==3:
                    for c in liberi:
                        if c in (a,b): continue
                        indici=tuple(sorted((a,b,c)))
                        if indici in visti: continue
                        visti.add(indici)
                        for direzione in (1,2): yield m,indici,direzione
                else:
                    for c,d in combinations([k for k in liberi if k not in (a,b)],2):
                        firma=tuple(sorted((tuple(sorted((a,b))),tuple(sorted((c,d))))))
                        if firma in visti: continue
                        visti.add(firma)
                        yield m,(a,b,c,d),0


def ripara_q12(mesi,studenti,schema,*,genere_misto=False,max_valutazioni=MAX_VALUTAZIONI,
           max_tentativi=MAX_TENTATIVI,annullato=lambda:False,frequenze_storico=None):
    if (not isinstance(max_valutazioni,int) or max_valutazioni<1
            or not isinstance(max_tentativi,int) or max_tentativi<1):
        raise ValueError('Limiti Q12 interi positivi richiesti.')
    inizio=time.perf_counter();p=ProblemaContestuale(mesi,studenti,schema,frequenze_storico=frequenze_storico)
    rows=[list(r) for r in p.iniziali];base=corrente=p.valuta(rows)
    p.verifica(rows,base)
    valutazioni=tentativi=accettate=stati=0;modificati=set();stop='nessuna_mossa_mirata'
    def limite():
        if annullato(): return 'annullato'
        if valutazioni>=max_valutazioni: return 'limite_valutazioni'
        if tentativi>=max_tentativi: return 'limite_tentativi'
        return None
    if not annullato():
        riallocate=[]
        try:
            for row in rows:
                nuova,nst=rialloca_gruppi(p,row,annullato);riallocate.append(nuova);stati+=nst
        except InterruptedError:
            riallocate=rows
        f=p.valuta(riallocate)
        if chiave_recupero(f)<chiave_recupero(corrente) and protetta_q12(f,base,genere_misto):
            modificati.update(i+1 for i,(a,b) in enumerate(zip(rows,riallocate)) if a!=b)
            rows,corrente=riallocate,f
    ultima_dopo_gruppi=corrente.ultima
    while not limite():
        migliore=corrente;migliori_rows=None;mese=None
        for taglia in (2,3,4):
            for m,indici,direzione in mosse_mirate(p,rows,taglia):
                if limite(): break
                tentativi+=1;vecchi=[rows[m][i] for i in indici]
                nuovi=([vecchi[1],vecchi[0],vecchi[3],vecchi[2]] if taglia==4
                       else vecchi[direzione:]+vecchi[:direzione])
                for i,s in zip(indici,nuovi): rows[m][i]=s
                try:
                    if not p.valida(rows[m]): continue
                    f=p.valuta(rows);valutazioni+=1
                    if chiave_recupero(f)<chiave_recupero(migliore) and protetta_q12(f,base,genere_misto):
                        migliore,migliori_rows,mese=f,[list(r) for r in rows],m
                finally:
                    for i,s in zip(indici,vecchi): rows[m][i]=s
            if migliori_rows is not None or limite(): break
        if migliori_rows is None: break
        rows,corrente=migliori_rows,migliore;accettate+=1;modificati.add(mese+1)
        if not annullato():
            try:
                nuova,nst=rialloca_gruppi(p,rows[mese],annullato);stati+=nst
                riga_prima=rows[mese];rows[mese]=nuova;f=p.valuta(rows)
                if chiave_recupero(f)<chiave_recupero(corrente) and protetta_q12(f,base,genere_misto):
                    corrente=f
                else: rows[mese]=riga_prima
            except InterruptedError: pass
    stop=limite() or stop
    risultato=p.costruisci(rows);ProblemaContestuale(risultato,studenti,schema,frequenze_storico=frequenze_storico).verifica(ProblemaContestuale(risultato,studenti,schema,frequenze_storico=frequenze_storico).iniziali,corrente)
    if not protetta_q12(corrente,base,genere_misto) or corrente.ultima<base.ultima:
        raise ValueError('Recupero Q12 fuori dalle protezioni.')
    return risultato,dict(secondi=time.perf_counter()-inizio,valutazioni=valutazioni,
        mosse_esaminate=tentativi,mosse_accettate=accettate,stati_riallocazione=stati,
        ultima_dopo_gruppi=ultima_dopo_gruppi,mesi_modificati=sorted(modificati),stop=stop,
        prima=asdict(base),dopo=asdict(corrente))
