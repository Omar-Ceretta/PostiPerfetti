# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""I1b/2c: policy Q19 per finaliste FISICHE, Storico e durate variabili.

La finalista di riferimento e' IMMUTABILE durante la scelta: la deroga
ULTIMA non si concatena. Nessuna generazione e nessuna intercettazione globale.
"""
from dataclasses import dataclass

from moduli.dominio.metrica_pulizia import nome_completo
from moduli.calcolo.valutazione_q21_contesto import ProblemaContestuale, protetta
from moduli.calcolo.politica_annuale import primo_riuso_non_anticipato

POLITICA = 'Q19_ULTIMA_max1_meno_L1_o_L2_v1'


@dataclass(frozen=True)
class FinalistaFisica:
    origine: str
    indice: int
    versione: str
    mesi: tuple


def motivi_esclusione(nuova,base,misto):
    """Diagnostica nativa Q10, mantenuta separata dalla deroga Q19."""
    m,b=nuova.metriche,base.metriche
    t,u=nuova.temporali,base.temporali
    motivi=[]
    for k in ('incompatibilita_l3','incompatibilita_l2','incompatibilita_l1','massimo_individuale'):
        if m[k]>b[k]:motivi.append(k+' aumenta')
    for k in ('affinita_pesate','affinita_l3'):
        if m[k]<b[k]:motivi.append(k+' diminuisce')
    if not primo_riuso_non_anticipato(t,u):motivi.append('primo riuso anticipato')
    for k in ('gap_1','gap_le_2','gap_le_3','massimo_riusi_mese'):
        if t[k]>u[k]:motivi.append(k+' aumenta')
    if nuova.profilo>base.profilo:motivi.append('profilo mensile incompatibilita peggiora')
    if nuova.ultima<base.ultima:motivi.append('ULTIMA diminuisce')
    if misto and nuova.miste<base.miste:motivi.append('Misto attivo diminuisce')
    if bool(motivi)==protetta(nuova,base,misto):
        raise ValueError('La diagnostica non coincide con le protezioni native.')
    return motivi


def valuta(nuova,base,misto):
    motivi=motivi_esclusione(nuova,base,misto)
    punteggio_migliore=nuova.chiave[0][0]<base.chiave[0][0]
    meno_inc=any(nuova.metriche[k]<base.metriche[k] for k in
                  ('incompatibilita_l1','incompatibilita_l2'))
    deroga=(motivi==['ULTIMA diminuisce'] and base.ultima-nuova.ultima==1
            and punteggio_migliore and meno_inc)
    return dict(ammessa=nuova.chiave<=base.chiave and (not motivi or deroga),
                deroga_ultima=deroga, motivi_guardie_native=motivi)


def scegli(finaliste, studenti, schema, *, frequenze_storico=None, genere_misto=False):
    """Sceglie tra finaliste gia' complete. La prima e' il riferimento Q19.

    Non accetta fotografie dichiarate: calcola tutto dai mesi FISICI.
    Le duplicazioni della medesima disposizione sono rimosse senza cambiare
    l'identita' della finalista di riferimento o il criterio di pareggio.
    """
    if not finaliste or any(not isinstance(f,FinalistaFisica) for f in finaliste):
        raise ValueError('Serve la finalista fisica di riferimento e le alternative.')
    referenza=finaliste[0]
    if referenza.origine!='riferimento':
        raise ValueError('La prima finalista deve essere il riferimento immutabile.')
    candidati={}
    durata_riferimento=len(referenza.mesi)
    for f in finaliste:
        if (f.origine not in ('riferimento','q11','q12','q15')
                or not f.mesi or len(f.mesi)!=durata_riferimento):
            raise ValueError('Finalista con provenienza o mesi non validi.')
        p=ProblemaContestuale(f.mesi,studenti,schema,frequenze_storico=frequenze_storico)
        foto=p.verifica(p.iniziali)
        firma=tuple(tuple(nome_completo(studenti[i]) for i in row) for row in p.iniziali)
        if firma not in candidati:
            candidati[firma]=(f,foto)
        elif candidati[firma][1]!=foto:
            raise ValueError('Disposizione duplicata con fotografie differenti.')
    rif_firma=next(iter(candidati))
    rif_foto=candidati[rif_firma][1]
    diagnosi={k:valuta(v[1],rif_foto,genere_misto) for k,v in candidati.items()}
    ammesse=[(k,v) for k,v in candidati.items() if diagnosi[k]['ammessa']]
    if not ammesse:
        raise ValueError('Anche il riferimento e\' stato escluso.')
    vincente=min(ammesse,key=lambda x:(x[1][1].chiave,-x[1][1].ultima,
                                     x[0]!=rif_firma,x[0]))
    firma,(candidato,foto)=vincente
    return dict(finalista=candidato, fotografia=foto, mesi=candidato.mesi,
                cambiata=firma!=rif_firma, candidate_distinte=len(candidati),
                politica=POLITICA, **diagnosi[firma])
