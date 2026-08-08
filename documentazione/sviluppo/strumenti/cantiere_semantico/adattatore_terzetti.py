"""Adattatore del risultato produttivo a terzetti."""
from __future__ import annotations
from collections import Counter
from typing import Any,Sequence
from .adattatori_comuni import ErroreAdattatore,MeseAdattato,crea_relazione_adattata,descrivi_aula,estrai_blocchi_fisici,nome_studente
from .identita import crea_group_id
from .modelli import CanaleRotazione,CondizioneRun,FunzioneGruppo,GruppoCanonico,RuoloAdiacenza,SpecificaRun,TipoGruppo,TracciaMese
TIPI={"coppia":TipoGruppo.COPPIA,"terzetto":TipoGruppo.TERZETTO,"quartetto":TipoGruppo.QUARTETTO}
RUOLI={TipoGruppo.COPPIA:RuoloAdiacenza.COPPIA_FINALE_TERZETTI,TipoGruppo.TERZETTO:RuoloAdiacenza.TERZETTO,TipoGruppo.QUARTETTO:RuoloAdiacenza.QUARTETTO}

def _aula(run:SpecificaRun,gruppi:Sequence[Any])->Any:
    from moduli.aula import ConfigurazioneAula
    n=sum(len(g.membri) for g in gruppi); per_fila=run.parametri_aula.posti_per_fila//3
    if per_fila<1: raise ErroreAdattatore("posti_per_fila non consente un terzetto.")
    aula=ConfigurazioneAula("Osservatore I4 terzetti")
    aula.crea_layout_terzetti(n,terzetti_per_fila=per_fila,posizione_blocco_finale=run.parametri_aula.posizione_blocco_finale or "ultima",ha_fisso=run.condizione==CondizioneRun.CON_FISSO,preferenza_resto2=run.parametri_aula.preferenza_resto2)
    report=aula.piazza_gruppi_terzetti(list(gruppi))
    if not report.get("valido_struttura",True): raise ErroreAdattatore("Geometria terzetti non valida: "+"; ".join(report.get("avvisi",[])))
    if not report.get("valido_prima",True): raise ErroreAdattatore("Geometria terzetti viola PRIMA.")
    return aula

def adatta_mese_terzetti(run:SpecificaRun,mese:int,risultato_mese:dict[str,Any],traccia:TracciaMese,studenti:Sequence[Any])->MeseAdattato:
    produttivi=tuple(risultato_mese.get("gruppi") or ())
    if not produttivi: raise ErroreAdattatore("Mese a terzetti privo di gruppi.")
    fonte={}; sequenze=[]
    for g in produttivi:
        raw=str(getattr(g,"tipo",""))
        if raw not in TIPI: raise ErroreAdattatore(f"Tipo gruppo sconosciuto: {raw!r}.")
        nomi=tuple(nome_studente(s) for s in g.membri)
        if nomi in fonte: raise ErroreAdattatore("Sequenza di gruppo duplicata.")
        fonte[nomi]=TIPI[raw]; sequenze.append(nomi)
    aula=_aula(run,produttivi); blocchi=estrai_blocchi_fisici(aula,studenti)
    if Counter(sequenze)!=Counter(b.nomi for b in blocchi): raise ErroreAdattatore("Gruppi in griglia diversi dai gruppi del motore.")
    fissi=[nome_studente(s) for s in studenti if str(getattr(s,"nota_posizione","")).upper()=="FISSO"]
    if run.condizione==CondizioneRun.CON_FISSO:
        if len(fissi)!=1: raise ErroreAdattatore("Run con FISSO senza unico studente FISSO.")
        fisso=fissi[0]
    else:
        if fissi: raise ErroreAdattatore("Run senza FISSO con studente FISSO.")
        fisso=None
    gruppi=[]; relazioni=[]
    for i,b in enumerate(blocchi,start=1):
        tipo=fonte[b.nomi]; attesi={TipoGruppo.COPPIA:2,TipoGruppo.TERZETTO:3,TipoGruppo.QUARTETTO:4}[tipo]
        if len(b.nomi)!=attesi: raise ErroreAdattatore("Dimensione incoerente col tipo.")
        if fisso is not None and fisso in b.nomi and b.nomi[0]!=fisso: raise ErroreAdattatore("Il FISSO a terzetti deve essere all'estremo sinistro.")
        funzione=FunzioneGruppo.BLOCCO_FINALE if tipo in {TipoGruppo.COPPIA,TipoGruppo.QUARTETTO} else FunzioneGruppo.ORDINARIO
        gid=crea_group_id(run.run_id,mese,i,b.nomi); gruppi.append(GruppoCanonico(gid,tipo,b.nomi,b.fila,b.posizione_nella_fila,funzione))
        for a in range(len(b.membri)-1): relazioni.append(crea_relazione_adattata(group_id=gid,membri=b.membri,indice_a=a,indice_b=a+1,ruolo=RUOLI[tipo],canale=CanaleRotazione.TERZETTI,nome_fisso=fisso))
    eventi_fisso=[r for r in relazioni if r.coinvolge_fisso]
    if fisso is not None and len(eventi_fisso)!=1: raise ErroreAdattatore(f"Attesa una adiacenza FISSO, trovate {len(eventi_fisso)}.")
    return MeseAdattato(mese,traccia,tuple(gruppi),tuple(relazioni),descrivi_aula(aula,blocchi))

__all__=["ErroreAdattatore","adatta_mese_terzetti"]
