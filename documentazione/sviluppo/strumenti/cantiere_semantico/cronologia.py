"""Cronologia semantica degli eventi lungo l'annata finale."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Iterable,Sequence
from .adattatore_coppie import adatta_mese_coppie
from .adattatore_terzetti import adatta_mese_terzetti
from .adattatori_comuni import ErroreAdattatore,MeseAdattato,RelazioneAdattata
from .esecuzione_c1 import EsitoC1
from .identita import chiave_adiacenza,crea_event_id
from .modelli import CanaleRotazione,EventoAdiacenza,FasciaRipetizione,MeseCanonico,Modalita,OrigineUltimoUso,RiepilogoMensile,SnapshotRotazioni,SpecificaRun,StatoRun,UltimoUso
from .snapshot import crea_stato_iniziale_id,verifica_snapshot

class ErroreCronologia(ValueError): pass

@dataclass(frozen=True,slots=True)
class EsitoCronologiaI4:
    run_id:str; modalita:Modalita; stato:StatoRun; mesi:tuple[MeseCanonico,...]
    def __post_init__(self):
        if not self.run_id.strip(): raise ValueError("run_id vuoto.")
        object.__setattr__(self,"mesi",tuple(self.mesi))
        if [m.posizione_finale for m in self.mesi] != list(range(1,len(self.mesi)+1)): raise ValueError("Mesi non consecutivi.")
    @property
    def eventi(self)->tuple[EventoAdiacenza,...]: return tuple(e for m in self.mesi for e in m.adiacenze)

@dataclass(slots=True)
class _Stato:
    usi_iniziali:int=0; riferimento:str|None=None; usi_annata:int=0; ultimo_mese:int|None=None

class _Memoria:
    def __init__(self,snapshot:SnapshotRotazioni):
        self.rotazioni={(v.canale,v.studenti):_Stato(v.usi_precedenti,v.ultimo_riferimento_disponibile) for v in (*snapshot.coppie,*snapshot.terzetti)}
        self.vicini={v.studente:_Stato(v.usi_precedenti,v.ultimo_riferimento_disponibile) for v in snapshot.vicini_fisso}
    def stato(self,r:RelazioneAdattata)->_Stato:
        if r.canale_rotazione==CanaleRotazione.VICINO_FISSO:
            if not r.nome_vicino_fisso: raise ErroreCronologia("Evento vicino_fisso senza vicino.")
            return self.vicini.setdefault(r.nome_vicino_fisso,_Stato())
        return self.rotazioni.setdefault((r.canale_rotazione,chiave_adiacenza(r.studente_a,r.studente_b)),_Stato())

def _fascia(n:int)->FasciaRipetizione:
    return FasciaRipetizione.PRIMA_COMPARSA if n==0 else FasciaRipetizione.PRIMA_RIPETIZIONE if n==1 else FasciaRipetizione.SECONDA_RIPETIZIONE if n==2 else FasciaRipetizione.TERZA_O_ULTERIORE

def _ultimo(s:_Stato)->tuple[UltimoUso,int|None]:
    if s.usi_annata:
        if s.ultimo_mese is None: raise ErroreCronologia("Ultimo mese interno mancante.")
        return UltimoUso(OrigineUltimoUso.ANNATA_CORRENTE,mese_annata=s.ultimo_mese),s.ultimo_mese
    if s.usi_iniziali:
        return UltimoUso(OrigineUltimoUso.STORICO_INIZIALE,riferimento_storico=s.riferimento,motivo_distanza_non_calcolabile="Il precedente appartiene allo Storico iniziale e non alla sequenza mensile osservata."),None
    return UltimoUso(OrigineUltimoUso.NESSUNO),None

def _evento(run:SpecificaRun,mese:int,r:RelazioneAdattata,s:_Stato)->EventoAdiacenza:
    usi=s.usi_iniziali+s.usi_annata; ultimo,ultimo_mese=_ultimo(s); distanza=mese-ultimo_mese if ultimo_mese is not None else None
    return EventoAdiacenza(crea_event_id(run.run_id,mese,r.group_id,r.ordine_a,r.ordine_b,r.studente_a,r.studente_b),run.run_id,mese,r.group_id,r.studente_a,r.studente_b,r.ordine_a,r.ordine_b,chiave_adiacenza(r.studente_a,r.studente_b),r.ruolo,r.canale_rotazione,r.coinvolge_fisso,r.nome_fisso,r.nome_vicino_fisso,r.incompatibilita_livello,r.affinita_livello,r.genere_a,r.genere_b,r.genere_a!=r.genere_b,usi,s.usi_annata,usi>0,usi if usi>0 else None,_fascia(usi),ultimo,distanza)

def _riepilogo(eventi:Sequence[EventoAdiacenza])->RiepilogoMensile:
    c=lambda f:sum(e.fascia_ripetizione==f for e in eventi)
    return RiepilogoMensile(len(eventi),sum(e.e_riuso for e in eventi),c(FasciaRipetizione.PRIMA_RIPETIZIONE),c(FasciaRipetizione.SECONDA_RIPETIZIONE),c(FasciaRipetizione.TERZA_O_ULTERIORE),sum(e.incompatibilita_livello==1 for e in eventi),sum(e.incompatibilita_livello==2 for e in eventi),sum(e.incompatibilita_livello==3 for e in eventi),sum(e.affinita_livello==1 for e in eventi),sum(e.affinita_livello==2 for e in eventi),sum(e.affinita_livello==3 for e in eventi),sum(e.adiacenza_mista for e in eventi),sum(not e.adiacenza_mista for e in eventi))

def _vicino(eventi:Sequence[EventoAdiacenza])->dict[str,Any]|None:
    f=[e for e in eventi if e.coinvolge_fisso]
    if not f:return None
    if len(f)!=1: raise ErroreCronologia(f"Attesa una adiacenza FISSO, trovate {len(f)}.")
    e=f[0]
    return {"studente":e.nome_vicino_fisso,"canale_rotazione":e.canale_rotazione.value,"usi_precedenti":e.usi_precedenti_totali,"numero_ripetizione":e.numero_ripetizione,"ultimo_uso_origine":e.ultimo_uso.origine.value,"ultimo_mese":e.ultimo_uso.mese_annata,"distanza_mesi":e.distanza_mesi}

def costruisci_cronologia(run:SpecificaRun,snapshot:SnapshotRotazioni,mesi_adattati:Iterable[MeseAdattato],*,stato:StatoRun=StatoRun.COMPLETO)->EsitoCronologiaI4:
    verifica_snapshot(snapshot)
    if run.stato_iniziale_id != crea_stato_iniziale_id(snapshot): raise ErroreCronologia("Snapshot non coincidente con lo stato iniziale del run.")
    mesi=tuple(mesi_adattati)
    if [m.mese for m in mesi] != list(range(1,len(mesi)+1)): raise ErroreCronologia("Mesi adattati non consecutivi.")
    memoria=_Memoria(snapshot); canonici=[]; ids=set()
    for m in mesi:
        eventi=[]; aggiornamenti=[]
        for r in m.relazioni:
            s=memoria.stato(r); e=_evento(run,m.mese,r,s)
            if e.event_id in ids: raise ErroreCronologia("event_id duplicato.")
            ids.add(e.event_id); eventi.append(e); aggiornamenti.append(s)
        for s in aggiornamenti: s.usi_annata += 1; s.ultimo_mese=m.mese
        ev=tuple(eventi); canonici.append(MeseCanonico(m.mese,m.traccia.posizione_generazione,m.traccia.posizione_finale,m.gruppi,ev,_riepilogo(ev),m.configurazione_aula,_vicino(ev)))
    return EsitoCronologiaI4(run.run_id,run.modalita,stato,tuple(canonici))

def osserva_esito_c1(esito:EsitoC1,run:SpecificaRun,snapshot:SnapshotRotazioni,studenti:Sequence[Any])->EsitoCronologiaI4:
    if esito.run_id!=run.run_id or esito.modalita!=run.modalita: raise ErroreCronologia("Esito C1 non coerente col run.")
    if len(esito.mesi_finali)!=len(esito.traccia_riordino):
        if esito.mesi_finali: raise ErroreCronologia("Mesi senza traccia completa.")
        return costruisci_cronologia(run,snapshot,(),stato=esito.stato)
    adattati=[]
    for mese,(raw,traccia) in enumerate(zip(esito.mesi_finali,esito.traccia_riordino),start=1):
        try: adattati.append(adatta_mese_coppie(run,mese,raw,traccia,studenti) if run.modalita==Modalita.COPPIE else adatta_mese_terzetti(run,mese,raw,traccia,studenti))
        except ErroreAdattatore as err: raise ErroreCronologia(f"Mese {mese}: {err}") from err
    return costruisci_cronologia(run,snapshot,adattati,stato=esito.stato)

__all__=["ErroreCronologia","EsitoCronologiaI4","costruisci_cronologia","osserva_esito_c1"]
