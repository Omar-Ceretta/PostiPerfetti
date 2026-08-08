"""Adattatore del risultato produttivo a coppie."""
from __future__ import annotations
from typing import Any, Sequence
from .adattatori_comuni import ErroreAdattatore,MeseAdattato,crea_relazione_adattata,descrivi_aula,estrai_blocchi_fisici,nome_studente
from .identita import crea_group_id
from .modelli import CanaleRotazione,FunzioneGruppo,GruppoCanonico,RuoloAdiacenza,SpecificaRun,TipoGruppo,TracciaMese

def _nome_fisso(assegnatore:Any,studenti:Sequence[Any])->str|None:
    fisso=getattr(assegnatore,"studente_fisso",None)
    note=[nome_studente(s) for s in studenti if str(getattr(s,"nota_posizione","")).upper()=="FISSO"]
    if fisso is None:
        if note: raise ErroreAdattatore("La classe contiene un FISSO non dichiarato dall'assegnatore.")
        return None
    nome=nome_studente(fisso)
    if note != [nome]: raise ErroreAdattatore("Fonte FISSO incoerente fra classe e assegnatore.")
    return nome

def adatta_mese_coppie(run:SpecificaRun,mese:int,assegnatore:Any,traccia:TracciaMese,studenti:Sequence[Any])->MeseAdattato:
    aula=getattr(assegnatore,"configurazione_aula",None)
    if aula is None: raise ErroreAdattatore("Mese a coppie privo di ConfigurazioneAula.")
    blocchi=estrai_blocchi_fisici(aula,studenti); fisso=_nome_fisso(assegnatore,studenti); gruppi=[]; relazioni=[]; n_blocchi_fisso=0
    for i,blocco in enumerate(blocchi,start=1):
        n=len(blocco.nomi); contiene=fisso is not None and fisso in blocco.nomi
        if n==2: tipo=TipoGruppo.COPPIA; funzione=FunzioneGruppo.ORDINARIO
        elif n==3: tipo=TipoGruppo.TRIO; funzione=FunzioneGruppo.BLOCCO_FISSO if contiene else FunzioneGruppo.ORDINARIO
        elif n==4 and contiene: tipo=TipoGruppo.QUARTETTO; funzione=FunzioneGruppo.BLOCCO_FISSO
        else: raise ErroreAdattatore(f"Blocco a coppie non riconosciuto: {n} membri.")
        if contiene:
            n_blocchi_fisso += 1
            if blocco.nomi[0] != fisso: raise ErroreAdattatore("Il FISSO deve essere all'estremo sinistro.")
        gid=crea_group_id(run.run_id,mese,i,blocco.nomi)
        gruppi.append(GruppoCanonico(gid,tipo,blocco.nomi,blocco.fila,blocco.posizione_nella_fila,funzione))
        for a in range(n-1):
            b=a+1; coinvolge=fisso is not None and fisso in {blocco.nomi[a],blocco.nomi[b]}
            if coinvolge: ruolo=RuoloAdiacenza.VICINO_FISSO; canale=CanaleRotazione.VICINO_FISSO
            elif n==2 or (n==3 and contiene): ruolo=RuoloAdiacenza.COPPIA_ORDINARIA; canale=CanaleRotazione.COPPIE
            else: ruolo=RuoloAdiacenza.TRIO_MODALITA_COPPIE; canale=CanaleRotazione.COPPIE
            relazioni.append(crea_relazione_adattata(group_id=gid,membri=blocco.membri,indice_a=a,indice_b=b,ruolo=ruolo,canale=canale,nome_fisso=fisso))
    if fisso is not None and n_blocchi_fisso != 1: raise ErroreAdattatore(f"Atteso un blocco FISSO, trovati {n_blocchi_fisso}.")
    vicini=[r.nome_vicino_fisso for r in relazioni if r.coinvolge_fisso]
    if fisso is not None:
        if len(vicini)!=1: raise ErroreAdattatore("Il FISSO deve avere un solo vicino diretto.")
        if getattr(assegnatore,"nome_adiacente_fisso",None) != vicini[0]: raise ErroreAdattatore("Vicino FISSO incoerente con la griglia.")
    return MeseAdattato(mese,traccia,tuple(gruppi),tuple(relazioni),descrivi_aula(aula,blocchi))

__all__=["ErroreAdattatore","adatta_mese_coppie"]
