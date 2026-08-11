"""Primitive comuni agli adattatori dei risultati produttivi.

Il modulo non conosce Qt e non modifica gli oggetti di PostiPerfetti. Legge la
geometria viva dell'aula e la trasforma in blocchi fisici neutri, conservando
ordine, fila e coordinate degli studenti.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from .modelli import CanaleRotazione, GruppoCanonico, RuoloAdiacenza, TracciaMese

class ErroreAdattatore(ValueError):
    """Segnala un risultato produttivo non normalizzabile senza ambiguità."""

@dataclass(frozen=True, slots=True)
class BloccoFisico:
    membri: tuple[Any, ...]
    nomi: tuple[str, ...]
    fila: int
    posizione_nella_fila: int
    coordinate: tuple[tuple[int, int], ...]

@dataclass(frozen=True, slots=True)
class RelazioneAdattata:
    group_id: str
    studente_a: str
    studente_b: str
    ordine_a: int
    ordine_b: int
    ruolo: RuoloAdiacenza
    canale_rotazione: CanaleRotazione
    coinvolge_fisso: bool
    nome_fisso: str | None
    nome_vicino_fisso: str | None
    incompatibilita_livello: int
    affinita_livello: int
    genere_a: str
    genere_b: str
    def __post_init__(self) -> None:
        if not self.group_id.strip(): raise ValueError("group_id non può essere vuoto.")
        if not self.studente_a.strip() or not self.studente_b.strip(): raise ValueError("I nomi non possono essere vuoti.")
        if self.studente_a == self.studente_b: raise ValueError("Una relazione richiede due studenti distinti.")
        if abs(self.ordine_a - self.ordine_b) != 1: raise ValueError("Posizioni non consecutive.")
        if self.genere_a not in {"M","F"} or self.genere_b not in {"M","F"}: raise ValueError("Genere non valido.")
        for nome, valore in (("incompatibilita_livello",self.incompatibilita_livello),("affinita_livello",self.affinita_livello)):
            if isinstance(valore,bool) or not isinstance(valore,int) or not 0 <= valore <= 3: raise ValueError(f"{nome} fuori intervallo.")
        if self.incompatibilita_livello and self.affinita_livello: raise ValueError("Affinità e incompatibilità insieme.")
        if self.coinvolge_fisso:
            if not self.nome_fisso or not self.nome_vicino_fisso: raise ValueError("Evento FISSO incompleto.")
        elif self.nome_fisso is not None or self.nome_vicino_fisso is not None:
            raise ValueError("Evento senza FISSO con nomi FISSO.")

@dataclass(frozen=True, slots=True)
class MeseAdattato:
    mese: int
    traccia: TracciaMese
    gruppi: tuple[GruppoCanonico, ...]
    relazioni: tuple[RelazioneAdattata, ...]
    configurazione_aula: Mapping[str, Any] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if isinstance(self.mese,bool) or not isinstance(self.mese,int) or self.mese < 1: raise ValueError("mese non valido.")
        object.__setattr__(self,"gruppi",tuple(self.gruppi)); object.__setattr__(self,"relazioni",tuple(self.relazioni))
        object.__setattr__(self,"configurazione_aula",MappingProxyType(dict(self.configurazione_aula)))
        if self.traccia.posizione_finale != self.mese: raise ValueError("Traccia non coincidente col mese.")
        ids={g.group_id for g in self.gruppi}
        if len(ids)!=len(self.gruppi): raise ValueError("group_id duplicati.")
        if any(r.group_id not in ids for r in self.relazioni): raise ValueError("Relazione con gruppo inesistente.")

def nome_studente(studente: Any) -> str:
    metodo=getattr(studente,"get_nome_completo",None)
    if not callable(metodo): raise ErroreAdattatore("Studente privo di get_nome_completo().")
    nome=str(metodo()).strip()
    if not nome: raise ErroreAdattatore("Nome completo vuoto.")
    return nome

def _nome_da_occupante(occupante: Any) -> str:
    testo=str(occupante or "").strip()
    if not testo: raise ErroreAdattatore("Banco occupato senza identificativo.")
    if "_" in testo:
        cognome,nome=testo.split("_",1); testo=f"{cognome} {nome}"
    return " ".join(testo.split())

def indice_studenti(studenti: Sequence[Any]) -> dict[str,Any]:
    indice={}
    for studente in studenti:
        nome=nome_studente(studente)
        if nome in indice: raise ErroreAdattatore(f"Studente duplicato: {nome}.")
        genere=str(getattr(studente,"sesso","")).strip().upper()
        if genere not in {"M","F"}: raise ErroreAdattatore(f"Genere non valido per {nome}.")
        indice[nome]=studente
    if not indice: raise ErroreAdattatore("Elenco studenti vuoto.")
    return indice

def estrai_blocchi_fisici(aula: Any, studenti: Sequence[Any]) -> tuple[BloccoFisico,...]:
    griglia=getattr(aula,"griglia",None)
    if not isinstance(griglia,list) or not griglia: raise ErroreAdattatore("Aula priva di griglia valida.")
    indice=indice_studenti(studenti); blocchi=[]; nomi_visti=[]; fila_logica=0
    for riga in griglia:
        occupati=sorted((p for p in riga if getattr(p,"tipo",None)=="banco" and getattr(p,"occupato_da",None) is not None),key=lambda p:int(p.colonna))
        if not occupati: continue
        segmenti=[]; corrente=[]; precedente=None
        for posto in occupati:
            col=int(posto.colonna)
            if corrente and precedente is not None and col != precedente+1: segmenti.append(corrente); corrente=[]
            corrente.append(posto); precedente=col
        if corrente: segmenti.append(corrente)
        for posizione,segmento in enumerate(segmenti):
            nomi=tuple(_nome_da_occupante(p.occupato_da) for p in segmento)
            sconosciuti=[n for n in nomi if n not in indice]
            if sconosciuti: raise ErroreAdattatore("Studenti sconosciuti nella griglia: "+", ".join(sconosciuti))
            if len(set(nomi))!=len(nomi): raise ErroreAdattatore("Duplicati in un blocco.")
            coordinate=tuple((int(p.riga),int(p.colonna)) for p in segmento)
            blocchi.append(BloccoFisico(tuple(indice[n] for n in nomi),nomi,fila_logica,posizione,coordinate)); nomi_visti.extend(nomi)
        fila_logica += 1
    attesi=set(indice); visti=set(nomi_visti)
    if len(nomi_visti)!=len(visti): raise ErroreAdattatore("Studente presente in più blocchi.")
    if visti!=attesi:
        mancanti=sorted(attesi-visti); eccedenti=sorted(visti-attesi); dettagli=[]
        if mancanti: dettagli.append("mancanti: "+", ".join(mancanti))
        if eccedenti: dettagli.append("eccedenti: "+", ".join(eccedenti))
        raise ErroreAdattatore("La griglia non copre la classe ("+"; ".join(dettagli)+").")
    return tuple(blocchi)

def livelli_relazione(a: Any,b: Any)->tuple[int,int]:
    na,nb=nome_studente(a),nome_studente(b)
    inc=max(int(getattr(a,"incompatibilita",{}).get(nb,0)),int(getattr(b,"incompatibilita",{}).get(na,0)))
    aff=max(int(getattr(a,"affinita",{}).get(nb,0)),int(getattr(b,"affinita",{}).get(na,0)))
    if inc and aff: raise ErroreAdattatore(f"Relazione contraddittoria fra {na} e {nb}.")
    if not 0<=inc<=3 or not 0<=aff<=3: raise ErroreAdattatore("Livello fuori intervallo.")
    return inc,aff

def crea_relazione_adattata(*,group_id:str,membri:Sequence[Any],indice_a:int,indice_b:int,ruolo:RuoloAdiacenza,canale:CanaleRotazione,nome_fisso:str|None)->RelazioneAdattata:
    a,b=membri[indice_a],membri[indice_b]; na,nb=nome_studente(a),nome_studente(b); inc,aff=livelli_relazione(a,b)
    coinvolge=nome_fisso is not None and nome_fisso in {na,nb}; vicino=(nb if na==nome_fisso else na) if coinvolge else None
    return RelazioneAdattata(group_id,na,nb,indice_a,indice_b,ruolo,canale,coinvolge,nome_fisso if coinvolge else None,vicino,inc,aff,str(a.sesso).upper(),str(b.sesso).upper())

def descrivi_aula(aula:Any,blocchi:Sequence[BloccoFisico])->dict[str,Any]:
    campi=("nome_config","modalita","num_righe","num_colonne","posti_disponibili","larghezza_blocco_sx","ha_fisso","ha_trio","fila_trio","tipo_blocco_finale","fila_blocco_finale","file_blocchi_finali","terzetti_per_fila","num_terzetti","coord_fisso")
    dati={}
    for campo in campi:
        valore=getattr(aula,campo,None); dati[campo]=tuple(valore) if isinstance(valore,list) else valore
    dati["blocchi_occupati"]=tuple({"fila":b.fila,"posizione_nella_fila":b.posizione_nella_fila,"membri":b.nomi,"coordinate_griglia":b.coordinate} for b in blocchi)
    return dati

__all__=["BloccoFisico","ErroreAdattatore","MeseAdattato","RelazioneAdattata","crea_relazione_adattata","descrivi_aula","estrai_blocchi_fisici","indice_studenti","livelli_relazione","nome_studente"]
