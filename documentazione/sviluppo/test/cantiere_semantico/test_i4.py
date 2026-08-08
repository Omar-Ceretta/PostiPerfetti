from __future__ import annotations
import pytest
from strumenti.cantiere_semantico.adattatore_coppie import adatta_mese_coppie
from strumenti.cantiere_semantico.adattatore_terzetti import adatta_mese_terzetti
from strumenti.cantiere_semantico.adattatori_comuni import MeseAdattato,RelazioneAdattata
from strumenti.cantiere_semantico.cronologia import ErroreCronologia,costruisci_cronologia,osserva_esito_c1
from strumenti.cantiere_semantico.esecuzione_c1 import esegui_c1_coppie,esegui_c1_terzetti
from strumenti.cantiere_semantico.identita import crea_group_id
from strumenti.cantiere_semantico.modelli import CanaleRotazione,CondizioneRun,FasciaRipetizione,FunzioneGruppo,GruppoCanonico,Modalita,OrigineUltimoUso,RuoloAdiacenza,TipoGruppo,TracciaMese
from strumenti.cantiere_semantico.snapshot import crea_snapshot_rotazioni
from .supporto_i3 import configurazione_produttiva_vuota,crea_run,firma_coppie,firma_terzetti,studenti_semplici

def studenti_fisso(n):
    from moduli.studenti import Student
    return [Student("Fisso","Test","M","FISSO")]+[Student(f"Alunno{i:02d}","Test","F" if i%2 else "M") for i in range(1,n)]

def test_adatta_coppie_reali(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    from moduli.aula import ConfigurazioneAula
    c=configurazione_produttiva_vuota(); run,amb=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=1,numero_candidati=1,numero_stagioni=1); ss=studenti_semplici(8)
    aula=ConfigurazioneAula("i4"); aula.crea_layout_standard(8,2,6,None,ha_fisso=False); e=esegui_c1_coppie(amb,ss,aula); prima=firma_coppie(e.mesi_finali)
    m=adatta_mese_coppie(run,1,e.mesi_finali[0],e.traccia_riordino[0],ss)
    assert sum(len(g.membri_ordinati) for g in m.gruppi)==8
    assert len(m.relazioni)==sum(len(g.membri_ordinati)-1 for g in m.gruppi)
    assert all(r.canale_rotazione==CanaleRotazione.COPPIE for r in m.relazioni)
    assert firma_coppie(e.mesi_finali)==prima

def test_adatta_coppie_fisso(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    from moduli.aula import ConfigurazioneAula
    c=configurazione_produttiva_vuota(); run,amb=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=1,numero_candidati=1,numero_stagioni=1,condizione=CondizioneRun.CON_FISSO); ss=studenti_fisso(7)
    aula=ConfigurazioneAula("i4f"); aula.crea_layout_standard(7,2,6,None,ha_fisso=True); e=esegui_c1_coppie(amb,ss,aula,studente_fisso=ss[0])
    m=adatta_mese_coppie(run,1,e.mesi_finali[0],e.traccia_riordino[0],ss); f=[r for r in m.relazioni if r.coinvolge_fisso]
    assert len(f)==1 and f[0].canale_rotazione==CanaleRotazione.VICINO_FISSO
    assert sum(g.funzione==FunzioneGruppo.BLOCCO_FISSO for g in m.gruppi)==1

def test_adatta_terzetti_reali(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    c=configurazione_produttiva_vuota(); run,amb=crea_run(c,modalita=Modalita.TERZETTI,numero_mesi=1,numero_candidati=1,numero_stagioni=1); ss=studenti_semplici(6)
    e=esegui_c1_terzetti(amb,ss); prima=firma_terzetti(e.mesi_finali); m=adatta_mese_terzetti(run,1,e.mesi_finali[0],e.traccia_riordino[0],ss)
    assert [g.tipo for g in m.gruppi]==[TipoGruppo.TERZETTO,TipoGruppo.TERZETTO]
    assert len(m.relazioni)==4 and all(r.canale_rotazione==CanaleRotazione.TERZETTI for r in m.relazioni)
    assert firma_terzetti(e.mesi_finali)==prima

def test_adatta_terzetti_fisso(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    c=configurazione_produttiva_vuota(); run,amb=crea_run(c,modalita=Modalita.TERZETTI,numero_mesi=1,numero_candidati=1,numero_stagioni=1,condizione=CondizioneRun.CON_FISSO); ss=studenti_fisso(7)
    e=esegui_c1_terzetti(amb,ss,studente_fisso=ss[0]); m=adatta_mese_terzetti(run,1,e.mesi_finali[0],e.traccia_riordino[0],ss); f=[r for r in m.relazioni if r.coinvolge_fisso]
    assert len(f)==1 and f[0].canale_rotazione==CanaleRotazione.TERZETTI

def rel(canale=CanaleRotazione.COPPIE,fisso=False):
    return RelazioneAdattata("tmp","Fisso Test" if fisso else "A Test","B Test",0,1,RuoloAdiacenza.VICINO_FISSO if fisso else RuoloAdiacenza.COPPIA_ORDINARIA,canale,fisso,"Fisso Test" if fisso else None,"B Test" if fisso else None,0,0 if fisso else 2,"M","F")

def mese(run,n,r):
    gid=crea_group_id(run.run_id,n,1,(r.studente_a,r.studente_b)); rr=RelazioneAdattata(gid,r.studente_a,r.studente_b,0,1,r.ruolo,r.canale_rotazione,r.coinvolge_fisso,r.nome_fisso,r.nome_vicino_fisso,r.incompatibilita_livello,r.affinita_livello,r.genere_a,r.genere_b)
    return MeseAdattato(n,TracciaMese(n,n,(0,0,0),(0,0,0)),(GruppoCanonico(gid,TipoGruppo.COPPIA,(rr.studente_a,rr.studente_b),0,0),),(rr,))

def test_cronologia_contatori_e_distanza():
    c=configurazione_produttiva_vuota(); c.config_data["coppie_da_evitare"]=[{"tipo":"coppia","studenti":["A Test","B Test"],"volte_usata":2}]
    snap=crea_snapshot_rotazioni(c.config_data); run,_=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=2,numero_candidati=1,numero_stagioni=1); r=rel()
    out=costruisci_cronologia(run,snap,(mese(run,1,r),mese(run,2,r))); a=out.mesi[0].adiacenze[0]; b=out.mesi[1].adiacenze[0]
    assert (a.usi_precedenti_totali,a.numero_ripetizione,a.fascia_ripetizione)==(2,2,FasciaRipetizione.SECONDA_RIPETIZIONE)
    assert a.ultimo_uso.origine==OrigineUltimoUso.STORICO_INIZIALE and a.distanza_mesi is None
    assert (b.usi_precedenti_totali,b.usi_precedenti_nell_annata,b.distanza_mesi)==(3,1,1)
    assert b.ultimo_uso.origine==OrigineUltimoUso.ANNATA_CORRENTE

def test_cronologia_separa_canale_fisso():
    c=configurazione_produttiva_vuota(); c.config_data["coppie_da_evitare"]=[{"tipo":"coppia","studenti":["Fisso Test","B Test"],"volte_usata":4}]
    snap=crea_snapshot_rotazioni(c.config_data); run,_=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=1,numero_candidati=1,numero_stagioni=1,condizione=CondizioneRun.CON_FISSO)
    e=costruisci_cronologia(run,snap,(mese(run,1,rel(CanaleRotazione.VICINO_FISSO,True)),)).mesi[0].adiacenze[0]
    assert e.usi_precedenti_totali==0 and e.fascia_ripetizione==FasciaRipetizione.PRIMA_COMPARSA

def test_cronologia_rifiuta_snapshot_diverso():
    c=configurazione_produttiva_vuota(); snap=crea_snapshot_rotazioni(c.config_data); run,_=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=1,numero_candidati=1,numero_stagioni=1)
    c2=configurazione_produttiva_vuota(); c2.config_data["coppie_da_evitare"]=[{"tipo":"coppia","studenti":["X","Y"],"volte_usata":1}]; altro=crea_snapshot_rotazioni(c2.config_data)
    with pytest.raises(ErroreCronologia): costruisci_cronologia(run,altro,(mese(run,1,rel()),))
    assert snap.sha256!=altro.sha256

def test_end_to_end_coppie(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    from moduli.aula import ConfigurazioneAula
    c=configurazione_produttiva_vuota(); snap=crea_snapshot_rotazioni(c.config_data); run,amb=crea_run(c,modalita=Modalita.COPPIE,numero_mesi=2,numero_candidati=1,numero_stagioni=1); ss=studenti_semplici(8)
    aula=ConfigurazioneAula("e2e"); aula.crea_layout_standard(8,2,6,None,ha_fisso=False); e=esegui_c1_coppie(amb,ss,aula); prima=firma_coppie(e.mesi_finali); out=osserva_esito_c1(e,run,snap,ss)
    assert len(out.mesi)==2 and all(m.adiacenze for m in out.mesi); assert firma_coppie(e.mesi_finali)==prima

def test_end_to_end_terzetti_fisso(monkeypatch):
    monkeypatch.delenv("POSTIPERFETTI_STRATEGIA_RICERCA",raising=False)
    c=configurazione_produttiva_vuota(); snap=crea_snapshot_rotazioni(c.config_data); run,amb=crea_run(c,modalita=Modalita.TERZETTI,numero_mesi=2,numero_candidati=1,numero_stagioni=1,condizione=CondizioneRun.CON_FISSO); ss=studenti_fisso(7)
    e=esegui_c1_terzetti(amb,ss,studente_fisso=ss[0]); prima=firma_terzetti(e.mesi_finali); out=osserva_esito_c1(e,run,snap,ss)
    assert len(out.mesi)==2 and all(m.vicino_fisso for m in out.mesi); assert firma_terzetti(e.mesi_finali)==prima
