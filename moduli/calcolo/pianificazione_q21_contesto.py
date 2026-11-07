# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""I1b/2d/4: contratti di pianificazione Q10/Q11/Q12, senza import LAB.

Input: fotografie e metadati gia' calcolati, mai seed o generatori.
Nessun peso, guardia o vicinato viene ridefinito.
"""
from __future__ import annotations

from moduli.calcolo.politica_annuale import chiave_r12
from moduli.calcolo.selezione_q19_contesto import motivi_esclusione
from moduli.calcolo.valutazione_q21_contesto import protetta


def chiave_c1_grezza(m):
    return (m['riusi'], m['l1'] + 10*m['l2'] + 1000*m['l3'],
            -(m['aff1'] + m['aff2'] + m['aff3']))


def chiave_r12_grezza(m):
    return chiave_r12(dict(riusi=m['riusi'],
        incompatibilita_l1=m['l1'], incompatibilita_l2=m['l2'],
        massimo_individuale=m['massimo_riusi_studente'],
        affinita_pesate=m['affinita_pesate']))


def precedenza_c1(eventi):
    """Ultima C1 con piu' riusi; in mancanza penultima C1."""
    storico=[]; migliore=None
    for e in eventi:
        if migliore is None or chiave_c1_grezza(e['metriche']) < chiave_c1_grezza(migliore['metriche']):
            migliore=e;storico.append(e)
    if migliore is None: raise ValueError('Manca una candidata completa.')
    precedenti=[e for e in storico[:-1] if e['metriche']['riusi']>migliore['metriche']['riusi']]
    precedente=precedenti[-1] if precedenti else storico[-2] if len(storico)>1 else None
    return migliore['annata'],precedente['annata'] if precedente else None


def piano_q11(eventi, attuale, *, indice_c1=None):
    """Ricalca Q10.pianifica sui soli riepiloghi; ordine significativo."""
    if not eventi or any(type(e['annata']) is not int or e['annata']<1 for e in eventi):
        raise ValueError('Registro delle candidate non valido.')
    if len({e['annata'] for e in eventi})!=len(eventi) or [e['annata'] for e in eventi]!=sorted(e['annata'] for e in eventi):
        raise ValueError('Registro non cronologico o con duplicati.')
    migliore,precedente=precedenza_c1(eventi)
    if indice_c1 is not None and migliore != indice_c1:
        raise ValueError('C1 nativa e registro non coincidono.')
    if attuale not in {e['annata'] for e in eventi}:
        raise ValueError('S1 non presente nel registro.')
    piano=[dict(indice=attuale,ruolo='attuale')]
    if migliore!=attuale:
        piano.append(dict(indice=migliore,ruolo='c1_corrente'))
    elif precedente is not None:
        piano.append(dict(indice=precedente,ruolo='c1_precedente'))
    usati={p['indice'] for p in piano}
    for e in sorted(eventi,key=lambda e:(chiave_r12_grezza(e['metriche']),e['annata'])):
        if e['annata'] not in usati:
            piano.append(dict(indice=e['annata'],ruolo='r12_grezza'))
            break
    return piano[:3]


def scegli_q11(prove, misto):
    """Due scelte: Q10 sulla fotografia dopo Q5, Q11 dopo R2 finale.

    prove: indice, ruolo, dopo, finale (FotoContestuale), opportunita.
    """
    attuali=[r for r in prove if r['ruolo']=='attuale']
    if len(attuali)!=1 or len({r['indice'] for r in prove})!=len(prove):
        raise ValueError('Richiesta una sola finalista attuale e indici unici.')
    attuale=attuali[0]
    chiave10=lambda r:(r['dopo'].chiave,r is not attuale,r['indice'])
    ammesse10=[r for r in prove if protetta(r['dopo'],attuale['dopo'],misto)]
    riferimento=min(ammesse10,key=chiave10)
    chiave11=lambda r:(r['finale'].chiave,r is not riferimento,r['indice'])
    ammesse11=[r for r in prove if protetta(r['finale'],riferimento['finale'],misto)
               and r['finale'].chiave<=riferimento['finale'].chiave]
    scelta=min(ammesse11,key=chiave11)
    if any(not protetta(scelta['finale'],r['dopo'],misto) or scelta['finale'].chiave>r['dopo'].chiave
           for r in (attuale,riferimento)):
        raise ValueError('Q11 peggiora Q9/Q10.')
    return dict(indice_q10=riferimento['indice'],indice_q11=scelta['indice'])


def piano_q12(prove, indice_q11, misto):
    """Ripara solo le prove Q11 con margine ULTIMA e chiave ammissibile."""
    per={r['indice']:r for r in prove}
    if indice_q11 not in per or len(per)!=len(prove):
        raise ValueError('Riferimento Q11 mancante o duplicato.')
    base=per[indice_q11]['finale'];out=[]
    for r in prove:
        f=r['finale'];motivi=motivi_esclusione(f,base,misto)
        if f.chiave>base.chiave or set(motivi)-{'ULTIMA diminuisce'}:continue
        out.append(dict(indice=r['indice'],ruolo=r['ruolo'],
            ruolo_q12=('riferimento_q11' if r['indice']==indice_q11 else
                        'recupero_ultima' if motivi else 'pari_chiave'),
            da_riparare=f.ultima<r['opportunita']))
    return out


def scegli_q12(prove, risposte_q12, indice_q11, misto):
    """Restituisce l'identita' fisica Q13, protetta da Q11, senza replay.

    Le Q12 sono (indice, finale, mesi), gia' verificate e complete.
    """
    per={r['indice']:r for r in prove};base=per[indice_q11]['finale']
    piano=piano_q12(prove,indice_q11,misto)
    ammessi={p['indice'] for p in piano}
    elementi=[dict(indice=indice_q11,versione='riferimento_q11',
                   foto=base,mesi=per[indice_q11]['mesi'])]
    elementi += [dict(indice=r['indice'],versione='q11',foto=r['finale'],mesi=r['mesi'])
                 for r in prove if r['indice'] in ammessi and r['indice']!=indice_q11]
    for r in risposte_q12:
        if r['indice'] not in {p['indice'] for p in piano if p['da_riparare']}:
            raise ValueError('Q12 non pianificata.')
        elementi.append(dict(indice=r['indice'],versione='q12',foto=r['finale'],mesi=r['mesi']))
    ammesse=[e for e in elementi if protetta(e['foto'],base,misto) and e['foto'].chiave<=base.chiave]
    if not ammesse:raise ValueError('Nessuna finalista Q12 protetta.')
    return min(ammesse,key=lambda e:(e['foto'].chiave,-e['foto'].ultima,
        e['versione']!='riferimento_q11',e['indice'],e['versione']))


def piano_q15(prove, riferimento, misto):
    """Piano Q15/Q16 congelato: alternative Q11 e poi Q12, senza deroga Q19.

    Ogni prova contiene indice, versione, foto e firma FISICA dei mesi.
    L'ordine e la deduplicazione seguono sweep_q15_recupero.alternative.
    """
    visti=set();out=[]
    for p in prove:
        versione=p['versione'];indice=p['indice'];foto=p['foto'];firma=p['firma']
        if versione not in ('q11','q12') or type(indice) is not int or not isinstance(firma,tuple):
            raise ValueError('Provenienza o firma Q15 invalida.')
        if firma in visti or foto.chiave>=riferimento.chiave or protetta(foto,riferimento,misto):
            continue
        visti.add(firma)
        out.append((indice,versione))
    return out
