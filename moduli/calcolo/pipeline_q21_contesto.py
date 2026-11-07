"""Pipeline Q21 usata da Mensile e Annuale, indipendente da Qt.

Genera e verifica proposte complete sul Layout unico. Gli esperimenti
B1-B4b sono conservati soltanto nell’archivio di sviluppo separato.
"""

from __future__ import annotations
from dataclasses import asdict
from os import environ
from time import monotonic
from threading import Event
from moduli.calcolo.archivio_candidate_q21 import ArchivioCandidateQ21
from moduli.calcolo.profilo_pipeline_q21 import ProfiloPipelineQ21
from moduli.calcolo.annuale import (
    genera_migliore_stagione,
    genera_una_stagione_personalizzata_gui,
    riordina_stagione_personalizzata_gui,
)
from moduli.calcolo.config_calcolo_q21 import ConfigCalcoloQ21
from moduli.calcolo.ingresso_q21 import IngressoQ21
from moduli.dominio.metrica_pulizia import punteggio_stagione
from moduli.calcolo.pianificazione_q21_contesto import (
    precedenza_c1,
    chiave_r12_grezza,
    piano_q11,
    scegli_q11,
    piano_q12,
    scegli_q12,
    piano_q15,
)
from moduli.processi.ponte_risultati_q21 import prepara_risultato_fisico_q21
from moduli.calcolo.politica_annuale import analizza_baseline, analizza_candidata, seleziona_s1
from moduli.calcolo.recupero_q15_contesto import (
    ripara as recupera_q15,
    verifica_percorso as verifica_q15,
)
from moduli.calcolo.rifinitura_q20_contesto import (
    ripara as ripara_q20,
    verifica_percorso as verifica_q20,
)
from moduli.calcolo.riparazione_q5_q12_contesto import ripara_q5, ripara_q12
from moduli.calcolo.selezione_q19_contesto import FinalistaFisica, scegli as scegli_q19
from moduli.calcolo.valutazione_q21_contesto import (
    ProblemaContestuale,
    riordina_contestuale,
    protetta,
)


class BudgetContestualeEsaurito(TimeoutError):
    pass


class Scadenza:
    def __init__(self, stop, budget):
        self.stop = stop
        self.inizio = monotonic()
        self.fine = self.inizio + budget

    def annullato(self):
        return self.stop.is_set() or monotonic() >= self.fine

    def verifica(self):
        if self.stop.is_set():
            raise InterruptedError("Generazione contestuale annullata.")
        if monotonic() >= self.fine:
            raise BudgetContestualeEsaurito("Budget totale contestuale esaurito.")


def _foto(mesi, ss, schema, freq):
    p = ProblemaContestuale(mesi, ss, schema, frequenze_storico=freq)
    return p.verifica(p.iniziali)


def esegui_contestuale(
    ingresso: IngressoQ21,
    stop: Event,
    invia=lambda _: None,
    *,
    limite_finaliste=6,
    backend_ricerca="nativo",
    traccia_candidate=False,
    diversifica_q2=False,
    numero_candidate_diagnostiche=None,
):
    """Genera, rifinisce e verifica un'Annuale 1..10 mesi, con Storico.

    L'interfaccia restituisce (risultato_produttivo, diagnostica). Non salva
    alcunché. Richiede un processo dedicato per il CPU, ma non applica hook.
    """
    if not isinstance(ingresso, IngressoQ21):
        raise TypeError("Serve un ingresso immutabile I1b/1.")
    if not hasattr(stop, "is_set") or not callable(invia):
        raise TypeError("Stop e invia non validi.")
    if numero_candidate_diagnostiche is not None:
        if (
            type(numero_candidate_diagnostiche) is not int
            or not 1 <= numero_candidate_diagnostiche <= 1000
            or ingresso.numero_mesi != 10
            or ingresso.frequenze_iniziali
            or (backend_ricerca != "q17")
            or (not diversifica_q2)
        ):
            raise ValueError("La riproduzione a numero fisso e riservata al Gate di identita Q21.")
    if limite_finaliste != 6:
        raise ValueError("Il tetto delle finaliste è congelato a sei.")
    if backend_ricerca not in ("nativo", "q17"):
        raise ValueError("Backend Q17 sconosciuto.")
    if environ.get("POSTIPERFETTI_STAGIONI") is not None:
        raise ValueError("Il pilota non ammette un numero di annuali fisso dall’ambiente.")
    profilo = ProfiloPipelineQ21()
    timer = Scadenza(stop, ingresso.budget_totale)
    timer.verifica()
    if ingresso.fotografia.identita() != ingresso.identita_fotografia:
        raise ValueError("Fotografia dell'ingresso modificata.")
    ss = ingresso.crea_studenti()
    schema = ingresso.fotografia.layout.schema
    freq = ingresso.frequenze_storico()
    misto = ingresso.fotografia.genere_misto
    cfg = ConfigCalcoloQ21(ingresso)
    durata = ingresso.numero_mesi
    riserva = ingresso.riserva
    timer.verifica()
    quota = timer.fine - monotonic() - riserva
    if quota <= 0:
        raise BudgetContestualeEsaurito("Preparazione oltre la riserva.")
    retained = {}
    riepiloghi = {}
    registro = []
    foto_storico = {tuple(sorted(k)) for k in freq}
    miglior_c1 = None
    miglior_riusi_completati = None
    c1_attuale = None
    c1_precedente = None
    massimo_memoria = 0
    osservate = 0
    archivio = ArchivioCandidateQ21()

    def generazione(indice, t0, budget, deve_fermarsi, *, seme=None, indice_locale=None):
        nonlocal \
            miglior_c1, \
            miglior_riusi_completati, \
            c1_attuale, \
            c1_precedente, \
            massimo_memoria, \
            osservate
        timer.verifica()
        mesi, chiavi, config, motivo = profilo.misura(
            "generazione_mesi",
            genera_una_stagione_personalizzata_gui,
            ss,
            schema,
            cfg,
            misto,
            durata,
            num_candidati=ingresso.num_candidati,
            t0_globale=t0,
            budget_secondi=budget,
            deve_fermarsi=lambda: deve_fermarsi() or timer.annullato(),
            seed_principale=ingresso.seed_principale if seme is None else seme,
            indice_stagione=indice if indice_locale is None else indice_locale,
            backend_ricerca=backend_ricerca,
            diversifica_q2=diversifica_q2,
            progresso=lambda mese, _: invia(dict(evento="mese", annata=indice, mese=mese)),
        )
        if motivo is None and len(mesi) == durata:
            p = ProblemaContestuale(mesi, ss, schema, frequenze_storico=freq)
            foto = p.verifica(p.iniziali)
            osservate += 1
            chiave_c1 = punteggio_stagione(chiavi)
            if miglior_c1 is None or chiave_c1 < miglior_c1:
                miglior_c1 = chiave_c1
            fm = foto.metriche
            riusi_validi = fm["riusi"]
            if miglior_riusi_completati is None or riusi_validi < miglior_riusi_completati:
                miglior_riusi_completati = riusi_validi
                invia(
                    dict(
                        evento="migliore_completata", annata=indice, riusi=miglior_riusi_completati
                    )
                )
            registro.append(
                dict(
                    annata=indice,
                    metriche=dict(
                        riusi=fm["riusi"],
                        l1=fm["incompatibilita_l1"],
                        l2=fm["incompatibilita_l2"],
                        l3=fm["incompatibilita_l3"],
                        aff1=fm["affinita_l1"],
                        aff2=fm["affinita_l2"],
                        aff3=fm["affinita_l3"],
                        affinita_pesate=fm["affinita_pesate"],
                        massimo_riusi_studente=fm["massimo_individuale"],
                    ),
                )
            )
            if traccia_candidate:
                invia(
                    dict(
                        evento="candidata_completa",
                        annata=indice,
                        metriche=dict(registro[-1]["metriche"]),
                        righe=[list(r) for r in p.iniziali],
                    )
                )
            c1_attuale, c1_precedente = precedenza_c1(registro)
            riepiloghi[indice] = (foto.chiave, chiave_c1)
            profilo.misura("archiviazione_candidate", archivio.conserva, indice, mesi, chiavi)
            retained[indice] = (tuple(mesi), tuple(chiavi))
            top3 = [
                e["annata"]
                for e in sorted(
                    registro, key=lambda e: (chiave_r12_grezza(e["metriche"]), e["annata"])
                )[:3]
            ]
            conserva = set(top3) | {c1_attuale, c1_precedente}
            for i in list(retained):
                if i not in conserva:
                    del retained[i]
            massimo_memoria = max(massimo_memoria, len(retained))
            if massimo_memoria > 6:
                raise ValueError("Cache oltre sei finaliste.")
        return (mesi, chiavi, config, motivo)

    def analizza(mesi, indice):
        return profilo.misura(
            "analisi_s1",
            analizza_candidata,
            mesi,
            indice_stagione=indice,
            modalita="personalizzata",
            blacklist_iniziale=foto_storico,
        )

    def analizza_c1(mesi, indice):
        return profilo.misura(
            "analisi_c1",
            analizza_baseline,
            mesi,
            indice_stagione=indice,
            modalita="personalizzata",
            blacklist_iniziale=foto_storico,
        )

    def ricarica_residente(indice, deve_fermarsi):
        timer.verifica()
        if indice not in retained:
            mesi, chiavi = profilo.misura("ricaricamento_snapshot_s1", archivio.carica, indice)
            if len(retained) >= 6:
                espelli = max(
                    (i for i in retained if i not in (c1_attuale, c1_precedente)),
                    key=lambda i: (riepiloghi[i][0], i),
                    default=None,
                )
                if espelli is None:
                    raise ValueError("Cache fisica S1 priva di spazio sicuro.")
                del retained[espelli]
            retained[indice] = (mesi, chiavi)
        mesi, chiavi = retained[indice]
        return (mesi, chiavi, None, None)

    invia(dict(evento="fase", fase="generazione_contestuale"))
    try:
        base, chiavi_base, info = genera_migliore_stagione(
            generazione,
            durata,
            budget_secondi=quota,
            deve_fermarsi=timer.annullato,
            numero_stagioni_fisso=numero_candidate_diagnostiche,
            analizza_candidata=analizza,
            analizza_baseline=analizza_c1,
            seleziona_stagione=lambda a, b: profilo.misura("selezione_s1", seleziona_s1, a, b),
            rigenera_una_stagione=ricarica_residente,
        )
    finally:
        dati_archivio = dict(
            candidate_salvate=archivio.n_salvate,
            candidate_ricaricate=archivio.n_ricaricate,
            byte_massimi=archivio.byte_massimi,
            limite_byte=archivio.limite_byte,
        )
        archivio.close()
    profilo.campiona("dopo_generazione_e_s1")
    timer.verifica()
    if info["motivo_stop"] in ("annullato", "mese_fallito") or len(base) != durata:
        raise ValueError("Non è stata generata un'Annuale completa.")
    vincitore_c1 = info["indice_stagione_migliore"]
    if vincitore_c1 not in retained:
        raise ValueError("C1/S1 non conservata: non si rigenera la vincitrice.")
    fine_q5 = timer.fine - 5
    stop_rifiniture = lambda: timer.annullato() or monotonic() >= fine_q5
    piano11 = piano_q11(registro, vincitore_c1, indice_c1=info["indice_stagione_c1"])
    if any((p["indice"] not in retained for p in piano11)):
        raise ValueError("Q11 richiede una candidata non residente: nessun replay.")
    prove = []
    fasi = []
    q15_accettati = 0
    stadi = [] if numero_candidate_diagnostiche is not None else None
    opportunita = durata * min(
        sum((s.nota_posizione == "ULTIMA" for s in ss)),
        sum((b.capienza for b in schema.blocchi if b.zona_ultima)),
    )
    for candidato in piano11:
        indice, ruolo = (candidato["indice"], candidato["ruolo"])
        timer.verifica()
        invia(dict(evento="fase", fase="finalista_q11", annata=indice))
        mesi = retained[indice][0]
        ordine = (
            info["ordine_stagione_preferito"]
            if ruolo == "attuale"
            else analizza(mesi, indice)["ordine"]
        )
        mesi, _ = profilo.misura(
            "riordino_preliminare",
            riordina_stagione_personalizzata_gui,
            mesi,
            cfg,
            ordine_iniziale=ordine,
        )
        mesi, q5 = profilo.misura(
            "riparazione_q5",
            ripara_q5,
            mesi,
            ss,
            schema,
            frequenze_storico=freq,
            genere_misto=misto,
            annullato=stop_rifiniture,
        )
        timer.verifica()
        dopo = _foto(mesi, ss, schema, freq)
        righe_dopo_q5 = (
            [
                list(r)
                for r in ProblemaContestuale(mesi, ss, schema, frequenze_storico=freq).iniziali
            ]
            if stadi is not None
            else None
        )
        mesi, fine, r2 = profilo.misura(
            "riordino_r2_preliminare",
            riordina_contestuale,
            mesi,
            ss,
            schema,
            cfg,
            frequenze_storico=freq,
            genere_misto=misto,
        )
        timer.verifica()
        prove.append(
            dict(
                indice=indice,
                ruolo=ruolo,
                dopo=dopo,
                finale=fine,
                opportunita=opportunita,
                mesi=tuple(mesi),
            )
        )
        fasi.append(dict(indice=indice, ruolo=ruolo, q5=q5["stop"], r2_accettato=r2))
        if stadi is not None:
            stadi.append(
                dict(
                    fase="q11",
                    indice=indice,
                    ruolo=ruolo,
                    dopo_q5=righe_dopo_q5,
                    dopo_r2=[
                        list(r)
                        for r in ProblemaContestuale(
                            tuple(prove[-1]["mesi"]), ss, schema, frequenze_storico=freq
                        ).iniziali
                    ],
                    q5_contatori={
                        k: q5[k]
                        for k in ("valutazioni", "mosse_esaminate", "mosse_accettate", "stop")
                    },
                )
            )
    sc11 = scegli_q11(prove, misto)
    piano12 = piano_q12(prove, sc11["indice_q11"], misto)
    risposte12 = []
    fine_q12 = timer.fine - 5
    for voce in piano12:
        if not voce["da_riparare"] or monotonic() >= fine_q12:
            continue
        timer.verifica()
        indice = voce["indice"]
        mesi = next((p["mesi"] for p in prove if p["indice"] == indice))
        invia(dict(evento="fase", fase="riparazione_q12", annata=indice))
        nuovi, q12 = profilo.misura(
            "riparazione_q12",
            ripara_q12,
            mesi,
            ss,
            schema,
            frequenze_storico=freq,
            genere_misto=misto,
            annullato=lambda: timer.annullato() or monotonic() >= fine_q12,
        )
        timer.verifica()
        nuovi, foto_q12, _ = profilo.misura(
            "riordino_r2_q12",
            riordina_contestuale,
            nuovi,
            ss,
            schema,
            cfg,
            frequenze_storico=freq,
            genere_misto=misto,
        )
        timer.verifica()
        if stadi is not None:
            stadi.append(
                dict(
                    fase="q12",
                    indice=indice,
                    dopo_r2=[
                        list(r)
                        for r in ProblemaContestuale(
                            nuovi, ss, schema, frequenze_storico=freq
                        ).iniziali
                    ],
                    q12_contatori={
                        k: q12[k]
                        for k in ("valutazioni", "mosse_esaminate", "mosse_accettate", "stop")
                    },
                )
            )
        risposte12.append(dict(indice=indice, finale=foto_q12, mesi=tuple(nuovi)))
        next((f for f in fasi if f["indice"] == indice))["q12"] = q12["stop"]
    vincente12 = scegli_q12(prove, risposte12, sc11["indice_q11"], misto)
    riferimento = vincente12["foto"]
    finaliste = [
        FinalistaFisica(
            "riferimento", vincente12["indice"], vincente12["versione"], vincente12["mesi"]
        )
    ]
    finaliste.extend((FinalistaFisica("q11", p["indice"], "q11", p["mesi"]) for p in prove))
    finaliste.extend((FinalistaFisica("q12", p["indice"], "q12", p["mesi"]) for p in risposte12))
    prove15 = []
    for f in finaliste[1:]:
        p15 = ProblemaContestuale(f.mesi, ss, schema, frequenze_storico=freq)
        prove15.append(
            dict(
                indice=f.indice,
                versione=f.versione,
                foto=p15.verifica(p15.iniziali),
                firma=tuple((tuple(r) for r in p15.iniziali)),
            )
        )
    piano15 = piano_q15(prove15, riferimento, misto)
    fine_q15 = timer.fine - 5
    if monotonic() < fine_q15:
        for indice, versione in piano15:
            timer.verifica()
            f = next((f for f in finaliste[1:] if f.indice == indice and f.versione == versione))
            nuovi, prova = profilo.misura(
                "recupero_q15",
                recupera_q15,
                f.mesi,
                ss,
                schema,
                riferimento,
                genere_misto=misto,
                frequenze_storico=freq,
                annullato=lambda: timer.annullato() or monotonic() >= fine_q15,
            )
            verifica_q15(f.mesi, ss, schema, riferimento, prova, misto, frequenze_storico=freq)
            timer.verifica()
            if stadi is not None:
                stadi.append(
                    dict(
                        fase="q15",
                        indice=indice,
                        versione=versione,
                        recuperata=prova["recuperata"],
                        percorso=prova["percorso"],
                        contatori={
                            k: prova[k]
                            for k in (
                                "valutazioni",
                                "mosse_esaminate",
                                "passi",
                                "combinazioni_filtrate",
                                "stop",
                            )
                        },
                    )
                )
            if prova["recuperata"]:
                finaliste.append(FinalistaFisica("q15", f.indice, f.versione, tuple(nuovi)))
                q15_accettati += 1
            if monotonic() >= fine_q15:
                break
    recuperate = [f for f in finaliste if f.origine == "q15"]
    alternative_q16 = [(finaliste[0], riferimento)]
    for f in recuperate:
        p15 = ProblemaContestuale(f.mesi, ss, schema, frequenze_storico=freq)
        alternativa = p15.verifica(p15.iniziali)
        alternative_q16.append((f, alternativa))
    scelta_q16 = min(alternative_q16, key=lambda a: (a[1].chiave, -a[1].ultima))
    if scelta_q16[0].origine == "q15":
        vincitrice = scelta_q16[0]
        finaliste[0] = FinalistaFisica(
            "riferimento", vincitrice.indice, vincitrice.versione, vincitrice.mesi
        )
    invia(dict(evento="fase", fase="selezione_q19"))
    scelta = profilo.misura(
        "selezione_q19",
        scegli_q19,
        finaliste,
        ss,
        schema,
        frequenze_storico=freq,
        genere_misto=misto,
    )
    timer.verifica()
    mesi_scelti = scelta["mesi"]
    foto_base = scelta["fotografia"]
    invia(
        dict(
            evento="finalista_selezionata",
            annata=scelta["finalista"].indice,
            riusi=foto_base.metriche["riusi"],
            l1=foto_base.metriche["incompatibilita_l1"],
            l2=foto_base.metriche["incompatibilita_l2"],
        )
    )
    if stadi is not None:
        stadi.append(
            dict(
                fase="q19",
                righe=[
                    list(r)
                    for r in ProblemaContestuale(
                        mesi_scelti, ss, schema, frequenze_storico=freq
                    ).iniziali
                ],
            )
        )
    q20 = None
    fine_q20 = timer.fine - 5
    if monotonic() < fine_q20:
        invia(dict(evento="fase", fase="affinita_q20"))
        nuovi, prova = profilo.misura(
            "affinita_q20",
            ripara_q20,
            mesi_scelti,
            ss,
            schema,
            frequenze_storico=freq,
            genere_misto=misto,
            annullato=lambda: timer.annullato() or monotonic() >= fine_q20,
        )
        ricostruiti, _ = verifica_q20(
            mesi_scelti, ss, schema, prova, frequenze_storico=freq, genere_misto=misto
        )
        if (
            ProblemaContestuale(nuovi, ss, schema, frequenze_storico=freq).iniziali
            != ProblemaContestuale(ricostruiti, ss, schema, frequenze_storico=freq).iniziali
        ):
            raise ValueError("Percorso Q20 diverso dall'esito fisico.")
        timer.verifica()
        nuovi, foto_r2, _ = profilo.misura(
            "riordino_r2_finale",
            riordina_contestuale,
            nuovi,
            ss,
            schema,
            cfg,
            frequenze_storico=freq,
            genere_misto=misto,
        )
        timer.verifica()
        if protetta(foto_r2, foto_base, misto) and foto_r2.chiave <= foto_base.chiave:
            mesi_scelti = tuple(nuovi)
        q20 = dict(stop=prova["stop"], mosse=len(prova["percorso"]))
        if stadi is not None:
            stadi.append(
                dict(
                    fase="q20",
                    percorso=prova["percorso"],
                    contatori={
                        k: prova[k] for k in ("valutazioni", "mosse_esaminate", "filtrate", "stop")
                    },
                )
            )
    p = ProblemaContestuale(mesi_scelti, ss, schema, frequenze_storico=freq)
    foto = p.verifica(p.iniziali)
    timer.verifica()
    mesi, chiavi = prepara_risultato_fisico_q21(p.iniziali, ss, schema, frequenze_storico=freq)
    if len(mesi) != durata or punteggio_stagione(chiavi)[0] != foto.metriche["riusi"]:
        raise ValueError("Ponte in uscita non coerente con il contesto.")
    for mese in mesi:
        ingresso.fotografia.verifica_risultato(mese)
    timer.verifica()
    invia(
        dict(
            evento="risultato_verificato",
            riusi=foto.metriche["riusi"],
            l1=foto.metriche["incompatibilita_l1"],
            l2=foto.metriche["incompatibilita_l2"],
        )
    )
    politica_generazione = info["politica_annuale"]
    info = dict(
        info,
        politica_annuale="i1b2d_pilota_contestuale",
        numero_mesi=durata,
        seed_principale=ingresso.seed_principale,
        schema_identita=schema.identita_semantica(),
        punteggio=punteggio_stagione(chiavi),
        tot_ripetizioni=foto.metriche["riusi"],
        riordino_temporale=True,
    )
    risultato = dict(mesi=mesi, chiavi=chiavi, info=info)
    report = dict(
        mesi=durata,
        candidate_complete=osservate,
        archivio_candidate_s1=dati_archivio,
        profilazione=profilo.resoconto(),
        c1=info["indice_stagione_c1"],
        s1=vincitore_c1,
        politica_generazione=politica_generazione,
        massimo_candidate_in_memoria=massimo_memoria,
        finaliste=len(finaliste),
        fasi=fasi,
        q15_promossi=q15_accettati,
        piano_q11=piano11,
        scelta_q11=sc11,
        piano_q12=piano12,
        piano_q15=piano15,
        scelta_q12=dict(indice=vincente12["indice"], versione=vincente12["versione"]),
        scelta_q16=dict(
            origine=scelta_q16[0].origine,
            indice=scelta_q16[0].indice,
            versione=scelta_q16[0].versione,
        ),
        scelta_q19=dict(
            origine=scelta["finalista"].origine,
            indice=scelta["finalista"].indice,
            versione=scelta["finalista"].versione,
            cambiata=scelta["cambiata"],
            deroga_ultima=scelta["deroga_ultima"],
        ),
        q20=q20,
        stadi_diagnostici=stadi,
        fotografia_finale=asdict(foto),
        tempo_totale=monotonic() - timer.inizio,
        nessun_replay_generazione=True,
        backend_ricerca=backend_ricerca,
        numero_candidate_diagnostiche=numero_candidate_diagnostiche,
        stato="Q21_OPERATIVO",
    )
    return (risultato, report)
