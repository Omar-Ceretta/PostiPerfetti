#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════
 BANCO DI PROVA — Strumento di sviluppo per misurare la qualità dell'algoritmo
═══════════════════════════════════════════════════════════════════════════

A COSA SERVE
------------
Questo NON è parte del programma per gli insegnanti: è uno strumento di
sviluppo (da tenere nella cartella del progetto, accanto a "moduli/").
Simula molte assegnazioni consecutive sulla STESSA classe — esattamente come
farebbe un docente mese dopo mese, salvando ogni volta nello Storico — e
misura con numeri la QUALITÀ di ciascuna assegnazione:

  • a quale TENTATIVO è arrivato l'algoritmo (1 = tutto rispettato,
    4 = ha dovuto rilassare i vincoli e/o ripetere coppie);
  • quante INCOMPATIBILITÀ ha tollerato (e di che livello);
  • quante COPPIE ha RIPETUTO rispetto alle assegnazioni precedenti.

Alla fine stampa una tabella e dei riepiloghi (MEDIA e CASO PEGGIORE).
Serve a rispondere con i numeri alla domanda: "questa modifica all'algoritmo
migliora davvero, o peggiora?".

COME PILOTA IL MOTORE
---------------------
Usa il MOTORE VERO (gli stessi moduli del programma), senza interfaccia
grafica. Riproduce il flusso reale:
  1. carica gli studenti dal file .txt;
  2. crea il layout dell'aula;
  3. esegue l'assegnazione (AssegnatorePosti);
  4. "salva nello Storico" aggiornando la blacklist (coppie_da_evitare),
     così l'assegnazione successiva eviterà le coppie già usate.

USO
---
    python3 banco_prova.py PERCORSO_CLASSE.txt
    python3 banco_prova.py Classe3A.txt --turni 12
    python3 banco_prova.py Classe3A.txt --turni 10 --ripetizioni 20 --seed 42

  --turni N         quante assegnazioni consecutive per "stagione" (default 10)
  --ripetizioni R   quante "stagioni" indipendenti ripetere e mediare (default 1)
                    (più stagioni = stima più affidabile del caso peggiore)
  --seed S          fissa il caso (riproducibile); senza, ogni run è diverso
  --modalita-trio   prima | ultima | centro   (default centro, come nella UI)
═══════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import io
import argparse
import copy           # per snapshot/restore di config_data nel lookahead (Leva A)
import random
import contextlib

# Permette di importare "moduli" anche lanciando lo script da un'altra cartella
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from moduli.studenti import carica_studenti_da_file       # loader (pensato per test/debug)
from moduli.aula import ConfigurazioneAula                 # layout dell'aula
from moduli.algoritmo import AssegnatorePosti              # motore di assegnazione
from moduli.configurazione import ConfigurazioneApp        # contiene la blacklist (coppie_da_evitare)

# Funzioni di misura CONDIVISE con la GUI, importate dal modulo "metrica_pulizia".
# Le importo con alias che ricalcano i vecchi nomi locali (_nome, _estrai_adiacenze, ...)
# così tutto il resto del banco resta INVARIATO. È la "fonte unica di verità":
# banco e GUI misurano la pulizia esattamente nello stesso modo.
from moduli.metrica_pulizia import (
    nome_completo as _nome,
    coppia_ordinata as _coppia_ordinata,
    livello_incompatibilita as _livello_incompatibilita_reale,
    estrai_adiacenze as _estrai_adiacenze,
    coppie_per_blacklist as _coppie_per_blacklist,
    snapshot_blacklist as _snapshot_blacklist,
    chiave_pulizia,                                       # giudizio complessivo (best-of-N)
)


# ───────────────────────────────────────────────────────────────────────────
# UTILITÀ
# ───────────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def _silenzia_output():
    """
    Il motore stampa moltissimi messaggi di debug con print().
    Questo gestore di contesto li cattura e li scarta, così l'output del
    banco di prova resta pulito e leggibile.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        yield


# NOTA: le funzioni di misura (_nome, _coppia_ordinata, _livello_incompatibilita_reale,
# _estrai_adiacenze, _coppie_per_blacklist, _snapshot_blacklist) NON sono più definite
# qui: ora vivono nel modulo "moduli/metrica_pulizia.py" e sono importate in cima a
# questo file (con gli stessi nomi, tramite alias). Così esiste UNA sola versione di
# queste regole, condivisa tra banco di prova e programma vero.


# ───────────────────────────────────────────────────────────────────────────
# GENERAZIONE DI UN SINGOLO CANDIDATO (helper riusabile)
# ───────────────────────────────────────────────────────────────────────────

def _genera_un_candidato(studenti_master, num_studenti, posizione_trio,
                        ha_fisso, modalita_trio, fisso, config_app):
    """
    Genera UNA singola assegnazione candidata contro la blacklist corrente
    di config_app, partendo da stato pulito (aula e assegnatore nuovi).

    Estratto da esegui_una_stagione() per essere riusato identico dal
    lookahead di Leva A: la stessa identica procedura va invocata sia per i
    candidati "reali" del turno T sia per i candidati "ipotetici" del T+1
    simulato. Centralizzare qui la generazione GARANTISCE che le due
    chiamate usino parametri identici — nessun rischio di divergenza
    involontaria fra "timeline principale" e "simulazione".

    Comportamento INVARIATO rispetto al codice inline che sostituisce:
    è un puro refactoring, gli stessi byte spostati in una funzione.

    Ritorna (ok, assegnatore):
      - ok        = True/False, esito del motore (assegnazione completata?)
      - assegnatore = oggetto AssegnatorePosti col risultato (o stato
        parziale se ok=False; il chiamante in genere lo scarta).
    """
    with _silenzia_output():
        # Aula e assegnatore NUOVI per OGNI candidato (stato pulito),
        # ma sempre la STESSA config_app (stessa blacklist di partenza).
        aula = ConfigurazioneAula("Banco di prova")
        aula.crea_layout_standard(
            num_studenti, None, None, posizione_trio, ha_fisso=ha_fisso
        )
        # Passo una COPIA della lista (per sicurezza: lo STEP 0 del FISSO
        # rimuove il fisso dalla lista su cui lavora).
        assegnatore = AssegnatorePosti()
        assegnatore.config_app = config_app
        ok = assegnatore.esegui_assegnazione_completa(
            list(studenti_master), aula, modalita_trio, fisso
        )
    return ok, assegnatore


# ───────────────────────────────────────────────────────────────────────────
# LOOKAHEAD DI UN PASSO (Leva A "leggera") — simulazione del turno T+1
# ───────────────────────────────────────────────────────────────────────────
# Idea: quando al turno T scegliamo fra più candidati, non guardiamo solo
# QUANTO È PULITO il candidato in sé (Leva 1), ma anche QUANTO COSTRINGE il
# turno SUCCESSIVO. Un candidato "egoista" può essere pulitissimo ora e
# lasciare T+1 in un vicolo cieco: è il paradosso descritto nel §5 del
# PROMPT.md (turno 1 goloso che rovina il turno 2).
#
# Per stimare il "costo sul futuro" di un candidato T:
#   1. fingiamo di salvarlo nello storico (la blacklist cresce),
#   2. generiamo M disposizioni IPOTETICHE per T+1 e teniamo la più pulita,
#   3. quella "miglior pulizia raggiungibile a T+1" è la stima del costo,
#   4. ANNULLIAMO tutto: la simulazione non deve lasciare alcuna traccia.
#
# Il punto 4 è cruciale per la SOLIDITÀ: se la simulazione sporcasse la
# blacklist, i contatori trio/FISSO o lo stato del generatore casuale, il
# turno T+1 REALE divergerebbe e i confronti con la baseline sarebbero
# falsati. Per questo salviamo e ripristiniamo TUTTO lo stato mutabile.

def _valuta_lookahead(candidato_T, M_lookahead, studenti_master, num_studenti,
                      posizione_trio, ha_fisso, modalita_trio, fisso, config_app):
    """
    Simula il turno T+1 ASSUMENDO di aver scelto 'candidato_T' al turno T, e
    ritorna la chiave_pulizia del MIGLIORE fra M_lookahead candidati ipotetici
    di T+1. È la stima di "quanto bene si potrà fare a T+1" se ora scegliamo
    candidato_T: più piccola = T+1 resta in salute.

    NON lascia tracce: salva e ripristina sia l'intero config_app.config_data
    (blacklist + contatori trio/FISSO) sia lo stato del generatore casuale.

    Ritorna:
      - la tupla chiave_pulizia del miglior candidato ipotetico di T+1, oppure
      - None se TUTTI gli M candidati ipotetici falliscono (caso raro: il
        chiamante in tal caso ripiega sulla sola pulizia di T).
    """
    # ── 1. SNAPSHOT dello stato mutabile, PRIMA di sporcare qualunque cosa ──
    # deepcopy dell'INTERO config_data: così qualsiasi struttura mutata da
    # _aggiorna_coppie_da_evitare (coppie_da_evitare, studenti_trio_contatore,
    # studenti_vicino_fisso_contatore e ogni eventuale aggiunta futura) viene
    # comunque ripristinata, senza dover sapere in anticipo quali chiavi tocca.
    snapshot_config_data = copy.deepcopy(config_app.config_data)
    # Stato del generatore casuale: generare i candidati ipotetici consuma
    # numeri casuali. Ripristinandolo, la "timeline principale" del random
    # resta IDENTICA al caso senza lookahead (garanzia di riproducibilità).
    snapshot_random = random.getstate()

    try:
        # ── 2. "SALVO NELLO STORICO" il candidato T (la blacklist cresce) ──
        # Replica ESATTA della chiamata in esegui_una_stagione: stessi
        # argomenti, stesso ordine, stesse keyword del FISSO. Qualsiasi
        # differenza qui renderebbe il T+1 simulato diverso dal T+1 reale.
        with _silenzia_output():
            config_app._aggiorna_coppie_da_evitare(
                candidato_T.coppie_formate,
                getattr(candidato_T, 'trio_identificato', None),
                studente_fisso=getattr(candidato_T, 'studente_fisso', None),
                gruppo_adiacente_fisso=getattr(candidato_T, 'gruppo_adiacente_fisso', None),
                nome_adiacente_fisso=getattr(candidato_T, 'nome_adiacente_fisso', None),
            )

        # ── 3. Fotografo la blacklist AGGIORNATA: serve a misurare le
        # ripetizioni dei candidati di T+1, esattamente come nel turno reale.
        gia_usate_Tp1 = _snapshot_blacklist(config_app)

        # ── 4. Genero M candidati IPOTETICI per T+1 e tengo il PIÙ PULITO ──
        miglior_chiave_Tp1 = None   # chiave_pulizia del miglior T+1 simulato
        for _ in range(M_lookahead):
            ok_Tp1, cand_Tp1 = _genera_un_candidato(
                studenti_master, num_studenti, posizione_trio,
                ha_fisso, modalita_trio, fisso, config_app
            )
            if not ok_Tp1:
                # Candidato ipotetico fallito: lo scarto e provo il prossimo.
                continue
            chiave_Tp1 = chiave_pulizia(cand_Tp1, gia_usate_Tp1)
            if miglior_chiave_Tp1 is None or chiave_Tp1 < miglior_chiave_Tp1:
                miglior_chiave_Tp1 = chiave_Tp1

        return miglior_chiave_Tp1

    finally:
        # ── 5. RIPRISTINO totale: la simulazione non deve lasciare traccia ──
        # Eseguito SEMPRE, anche se sopra fosse stata sollevata un'eccezione:
        # è la garanzia che il turno T+1 reale riparta da stato immacolato.
        # clear()+update() ripristina IN-PLACE (stesso oggetto-dizionario),
        # difensivo verso eventuali riferimenti diretti a config_data.
        config_app.config_data.clear()
        config_app.config_data.update(snapshot_config_data)
        random.setstate(snapshot_random)


# ───────────────────────────────────────────────────────────────────────────
# ESECUZIONE DI UNA SINGOLA STAGIONE (K assegnazioni consecutive)
# ───────────────────────────────────────────────────────────────────────────

def esegui_una_stagione(percorso_file, num_turni, modalita_trio, num_candidati,
                        lookahead=False, M_lookahead=3):
    """
    Esegue 'num_turni' assegnazioni consecutive sulla stessa classe,
    facendo crescere la blacklist tra una e l'altra (come nell'uso reale).

    Per OGNI turno applica la "Leva 1" (best-of-N): genera fino a
    'num_candidati' disposizioni e tiene la PIÙ PULITA secondo chiave_pulizia.
    Con num_candidati = 1 il comportamento è identico alla baseline storica.

    LEVA A "leggera" (lookahead di un passo), attiva se lookahead=True:
    per scegliere il vincitore del turno T non si guarda solo la pulizia di T,
    ma anche quanto T "costringe" il turno T+1. Per ogni candidato di T si
    simula il T+1 con M_lookahead disposizioni ipotetiche (vedi
    _valuta_lookahead) e si sceglie il candidato che MINIMIZZA il caso
    peggiore fra T e T+1 (criterio MINIMAX): l'obiettivo è evitare i "dirupi"
    in cui un turno è molto più sporco del precedente (§2/§5 del PROMPT.md).
    All'ULTIMO turno non c'è un T+1 da simulare: il lookahead viene
    automaticamente disattivato e si ricade nel puro best-of-N.

    Con lookahead=False il comportamento è IDENTICO alla baseline storica.

    Ritorna una lista di dizionari, uno per turno, con le misure di qualità.
    """
    # Carico studenti e individuo l'eventuale FISSO (silenzio i print di debug)
    with _silenzia_output():
        studenti_master = carica_studenti_da_file(percorso_file)

    fisso = next((s for s in studenti_master if s.nota_posizione == 'FISSO'), None)
    ha_fisso = fisso is not None
    num_studenti = len(studenti_master)

    # Posizione del trio: serve solo se i "rimanenti" sono dispari
    num_rimanenti = num_studenti - 1 if ha_fisso else num_studenti
    posizione_trio = modalita_trio if (num_rimanenti % 2 == 1) else None

    # UNA sola configurazione condivisa: la blacklist vive qui e cresce a ogni turno
    config_app = ConfigurazioneApp()

    risultati = []

    for turno in range(1, num_turni + 1):
        # LEVA A: il lookahead ha senso solo se è stato richiesto E se esiste
        # un turno T+1 da simulare. All'ULTIMO turno non c'è futuro da
        # proteggere, quindi disattiviamo il lookahead localmente e ricadiamo
        # nel puro best-of-N (come la baseline).
        usa_lookahead = lookahead and (turno < num_turni)

        # Fotografo la blacklist PRIMA di generare i candidati, UNA volta sola:
        # tutti i candidati di questo turno partono dalla STESSA blacklist e
        # contano le ripetizioni rispetto a questa identica fotografia.
        gia_usate_prima = _snapshot_blacklist(config_app)

        # ── SELEZIONE DEL CANDIDATO (Leva 1, eventualmente + Leva A) ──────────
        # Genero fino a 'num_candidati' disposizioni per questo turno.
        # - Senza lookahead: tengo la PIÙ PULITA (chiave_pulizia più piccola).
        # - Con lookahead: tengo quella col MIGLIOR caso-peggiore fra T e T+1
        #   (punteggio minimax più piccolo).
        miglior_assegnatore = None   # il candidato vincente finora
        miglior_chiave = None        # la sua chiave di pulizia P(t) — METRICA riportata
        miglior_score = None         # il suo punteggio di SELEZIONE (minimax se lookahead)

        for _n_candidato in range(num_candidati):
            # Genero UNA candidata assegnazione contro la blacklist corrente.
            # La logica vive in _genera_un_candidato() per essere usata
            # identica anche dal lookahead T+1 di Leva A (PASSO 3).
            ok, assegnatore = _genera_un_candidato(
                studenti_master, num_studenti, posizione_trio,
                ha_fisso, modalita_trio, fisso, config_app
            )

            if not ok:
                # Candidato fallito: lo scarto e provo il prossimo.
                continue

            # P(t): pulizia di QUESTO candidato sul turno T. Resta la metrica
            # "ufficiale" del turno (quella riportata e usata dall'analisi
            # regressioni), a prescindere dal lookahead.
            chiave_T = chiave_pulizia(assegnatore, gia_usate_prima)

            if usa_lookahead:
                # LEVA A: stimo quanto bene si potrà fare a T+1 SE scelgo questo
                # candidato. _valuta_lookahead non lascia tracce (ripristina
                # blacklist, contatori e stato random).
                chiave_Tp1 = _valuta_lookahead(
                    assegnatore, M_lookahead,
                    studenti_master, num_studenti, posizione_trio,
                    ha_fisso, modalita_trio, fisso, config_app
                )
                # Punteggio MINIMAX: il "caso peggiore" fra il turno T e il
                # miglior T+1 raggiungibile. max() fra due tuple chiave_pulizia
                # confronta in modo lessicografico, quindi restituisce la tupla
                # "più sporca" delle due. Vogliamo il candidato che rende questo
                # caso peggiore il più PICCOLO possibile (= traiettoria liscia).
                # Se NESSUN candidato ipotetico di T+1 riesce (chiave_Tp1 None),
                # degradiamo con eleganza alla sola pulizia di T.
                if chiave_Tp1 is not None:
                    score = max(chiave_T, chiave_Tp1)
                else:
                    score = chiave_T
            else:
                # Senza lookahead: il punteggio di selezione È la pulizia di T.
                # Così questo ramo resta BIT-IDENTICO alla baseline storica.
                score = chiave_T

            # Eleggo nuovo campione se ha punteggio di selezione più piccolo.
            # Nota: miglior_chiave traccia SEMPRE la P(t) del vincitore (metrica),
            # mentre miglior_score traccia il criterio di scelta (minimax o P(t)).
            if miglior_score is None or score < miglior_score:
                miglior_assegnatore = assegnatore
                miglior_chiave = chiave_T
                miglior_score = score

            # CORTOCIRCUITO (solo SENZA lookahead): un'assegnazione che arriva al
            # tentativo <= 3 rispetta già tutti i vincoli "duri" (zero incomp.
            # tollerate); per tenere istantanee le classi facili ci fermiamo qui.
            # Con lookahead ATTIVO il cortocircuito va DISATTIVATO: al turno 1 la
            # blacklist è vuota e quasi ogni candidato è a tentativo 1, quindi il
            # cortocircuito fermerebbe il loop dopo UN solo candidato — proprio
            # dove la Leva A deve invece confrontarne molti per scegliere quello
            # che non rovina il turno 2 (§5 del PROMPT.md).
            if not usa_lookahead:
                tentativo_corrente = getattr(assegnatore.motore_vincoli, 'tentativo_corrente', None)
                if tentativo_corrente is not None and tentativo_corrente <= 3:
                    break

        # Se TUTTI i candidati sono falliti, registro il fallimento del turno.
        if miglior_assegnatore is None:
            risultati.append({
                "turno": turno, "successo": False,
                "tentativo": None, "incomp": {}, "tot_incomp": 0, "ripetizioni": 0,
                # Coerenza con il ramo "successo": chiavi sempre presenti.
                "chiave_pulizia": None, "incomp_pesate": None,
            })
            continue

        # Da qui in avanti lavoro SOLO sul candidato vincente.
        assegnatore = miglior_assegnatore

        # --- MISURE DI QUALITÀ ---
        tentativo = getattr(assegnatore.motore_vincoli, 'tentativo_corrente', None)

        # Incompatibilità tollerate: scorro tutte le adiacenze e leggo il livello reale
        incomp_per_livello = {1: 0, 2: 0, 3: 0}
        for studente_a, studente_b in _estrai_adiacenze(assegnatore):
            livello = _livello_incompatibilita_reale(studente_a, studente_b)
            if livello >= 1:
                incomp_per_livello[livello] += 1
        tot_incomp = sum(incomp_per_livello.values())

        # Ripetizioni: coppie formate ora che erano GIÀ nella blacklist
        coppie_ora = _coppie_per_blacklist(assegnatore)
        ripetizioni = len(coppie_ora & gia_usate_prima)

        risultati.append({
            "turno": turno, "successo": True,
            "tentativo": tentativo,
            "incomp": dict(incomp_per_livello),
            "tot_incomp": tot_incomp,
            "ripetizioni": ripetizioni,
            # ── NUOVO per la Leva 2 (Diagnostica): salvo la chiave di pulizia
            # P(t) del turno e, separato per comodità, il valore "incomp_pesate"
            # (prima componente della chiave). È la stessa misura usata dalla
            # Leva 1 per scegliere il vincitore tra i candidati: la riusiamo qui
            # come definizione operativa di "pulizia di un turno", coerente col
            # §2 del PROMPT.md.  Più piccola = più pulita.
            "chiave_pulizia": miglior_chiave,
            "incomp_pesate": miglior_chiave[0],
        })

        # --- "SALVO NELLO STORICO": faccio crescere la blacklist come il programma ---
        with _silenzia_output():
            config_app._aggiorna_coppie_da_evitare(
                assegnatore.coppie_formate,
                getattr(assegnatore, 'trio_identificato', None),
                studente_fisso=getattr(assegnatore, 'studente_fisso', None),
                gruppo_adiacente_fisso=getattr(assegnatore, 'gruppo_adiacente_fisso', None),
                nome_adiacente_fisso=getattr(assegnatore, 'nome_adiacente_fisso', None),
            )

    return risultati


# ───────────────────────────────────────────────────────────────────────────
# ANALISI DELLE REGRESSIONI (paradosso di monotonia — Leva 2)
# ───────────────────────────────────────────────────────────────────────────
# Un'assegnazione precoce non dovrebbe essere PEGGIORE di una successiva: con
# più storico accumulato la difficoltà sale, non scende. Il §2 del PROMPT.md
# formalizza questa proprietà come "monotonia non decrescente della P(t)".
# Una REGRESSIONE qui è definita così:
#     esiste un turno t2 > t1 strettamente più pulito di t1
#     (cioè P(t2) < P(t1) in senso lessicografico).
# La gravità si esprime sul DISLIVELLO della prima componente della chiave,
# cioè le incompatibilità pesate (con liv.2 che pesa 10 volte un liv.1):
# è la componente che cattura il "vero" paradosso descritto al §5.

def analizza_regressioni(risultati_stagione):
    """
    Trova i turni REGRESSIVI di UNA stagione.

    Per ciascun turno t1, controlla se esiste un turno SUCCESSIVO t2 > t1
    con chiave di pulizia strettamente migliore (tupla più piccola). Se sì,
    t1 è regressivo: si registra il "miglior turno successivo" (quello con la
    P più piccola in assoluto) e i dislivelli su incompatibilità e ripetizioni.

    Ritorna una LISTA di dizionari, uno per turno regressivo.
    Stagione monotona = lista vuota (la cosa che vogliamo arrivare a osservare).
    """
    # Lavoriamo solo sui turni riusciti: un turno fallito non ha P(t) confrontabile
    riusciti = [r for r in risultati_stagione if r["successo"]]
    regressivi = []

    for i, r in enumerate(riusciti):
        successivi = riusciti[i + 1:]
        if not successivi:
            continue  # l'ultimo turno non può regredire (non ha "dopo")

        # Tra i turni successivi cerco quello con la P PIÙ PICCOLA (più pulito).
        # min con key=tupla usa il confronto lessicografico, esattamente come §2.
        miglior_succ = min(successivi, key=lambda x: x["chiave_pulizia"])

        if miglior_succ["chiave_pulizia"] < r["chiave_pulizia"]:
            # P(t2) lessicograficamente più piccola: c'è una regressione formale.
            # Ma vogliamo segnalare SOLO quelle "sensibili" (§2 del PROMPT.md
            # parla esplicitamente di P(t1) "sensibilmente" peggiore).
            # Una regressione che si manifesta SOLO sulla terza componente
            # (affinità) è rumore di spareggio: ai fini del paradosso descritto
            # al §5 conta la prima componente (incompatibilità pesate) e, a
            # parità di quella, la seconda (ripetizioni). Filtriamo qui.
            delta_incomp = r["incomp_pesate"] - miglior_succ["incomp_pesate"]
            delta_rip = r["ripetizioni"] - miglior_succ["ripetizioni"]
            sensibile = (delta_incomp > 0) or (delta_incomp == 0 and delta_rip > 0)
            if not sensibile:
                continue   # solo affinità: rumore, non è il paradosso

            regressivi.append({
                "turno": r["turno"],
                "incomp_pesate": r["incomp_pesate"],
                "ripetizioni": r["ripetizioni"],
                "miglior_succ_turno": miglior_succ["turno"],
                "miglior_succ_incomp": miglior_succ["incomp_pesate"],
                "miglior_succ_rip": miglior_succ["ripetizioni"],
                "delta_incomp": delta_incomp,
                "delta_rip": delta_rip,
            })

    return regressivi


# ───────────────────────────────────────────────────────────────────────────
# STAMPA DEI RISULTATI
# ───────────────────────────────────────────────────────────────────────────

def stampa_tabella_stagione(risultati):
    """
    Stampa la tabella turno-per-turno di una singola stagione.

    I turni REGRESSIVI (= esiste un turno successivo più pulito) sono marcati
    con "⚠" nell'ultima colonna; subito sotto la tabella, per ognuno, si
    stampa una riga di spiegazione: a quale turno successivo "perde" e con
    quale dislivello di incompatibilità pesate. Così il paradosso, se c'è,
    si vede immediatamente senza dover confrontare a mano.
    """
    # Calcolo le regressioni UNA volta sola, così la marcatura nella tabella
    # e il dettaglio sottostante restano garantitamente coerenti.
    regressivi = analizza_regressioni(risultati)
    turni_regressivi = {reg["turno"] for reg in regressivi}

    # Tabella: ho ristretto un po' la colonna "Tentativo" per fare spazio
    # alla nuova colonna "Paradosso?" sulla destra.
    print("  Turno | Tent. | Incomp. tollerate (liv.1 / liv.2) | Ripet. | Paradosso?")
    print("  ------+-------+-----------------------------------+--------+-------------")
    for r in risultati:
        if not r["successo"]:
            print(f"  {r['turno']:>5} |   —   |   ASSEGNAZIONE FALLITA            |   —    |  —")
            continue
        liv1 = r["incomp"].get(1, 0)
        liv2 = r["incomp"].get(2, 0)
        dettaglio = f"{r['tot_incomp']:>2}  ({liv1} di liv.1 / {liv2} di liv.2)"
        marker = "⚠ regressivo" if r["turno"] in turni_regressivi else ""
        print(f"  {r['turno']:>5} |   {r['tentativo']}   |  {dettaglio:<32} |  {r['ripetizioni']:>3}   | {marker}")

    # Dettaglio "umano" delle regressioni, se ce ne sono.
    if regressivi:
        print()
        print("  ⚠ Regressioni rilevate (paradosso di monotonia):")
        for reg in regressivi:
            print(f"     Turno {reg['turno']:>2}: incomp. pesate = {reg['incomp_pesate']:>3}"
                  f"  (ripetizioni: {reg['ripetizioni']})")
            print(f"        → ma il turno successivo {reg['miglior_succ_turno']:>2}"
                  f" ha incomp. pesate = {reg['miglior_succ_incomp']:>3}"
                  f"  (rip.: {reg['miglior_succ_rip']})"
                  f"  →  dislivello = {reg['delta_incomp']}")


def stampa_riepilogo(tutti_risultati):
    """
    Aggrega TUTTE le assegnazioni riuscite (di tutte le stagioni) e stampa
    medie e casi peggiori. È la parte che serve per confrontare 'prima/dopo'
    una modifica all'algoritmo.
    """
    riusciti = [r for r in tutti_risultati if r["successo"]]
    falliti = len(tutti_risultati) - len(riusciti)
    n = len(riusciti)

    print("\n" + "=" * 70)
    print("RIEPILOGO COMPLESSIVO")
    print("=" * 70)
    if n == 0:
        print("Nessuna assegnazione riuscita: impossibile calcolare statistiche.")
        return

    # Distribuzione dei tentativi
    distribuzione = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in riusciti:
        distribuzione[r["tentativo"]] = distribuzione.get(r["tentativo"], 0) + 1

    medie_incomp = sum(r["tot_incomp"] for r in riusciti) / n
    peggio_incomp = max(r["tot_incomp"] for r in riusciti)
    media_rip = sum(r["ripetizioni"] for r in riusciti) / n
    peggio_rip = max(r["ripetizioni"] for r in riusciti)
    media_tent = sum(r["tentativo"] for r in riusciti) / n

    print(f"Assegnazioni totali analizzate : {len(tutti_risultati)}  "
          f"(riuscite: {n}, fallite: {falliti})")
    print()
    print("INCOMPATIBILITÀ TOLLERATE per assegnazione:")
    print(f"   • media        : {medie_incomp:.2f}")
    print(f"   • CASO PEGGIORE: {peggio_incomp}")
    print()
    print("COPPIE RIPETUTE per assegnazione:")
    print(f"   • media        : {media_rip:.2f}")
    print(f"   • CASO PEGGIORE: {peggio_rip}")
    print()
    print(f"TENTATIVO raggiunto (1=ottimo … 4=molto rilassato): media {media_tent:.2f}")
    print("   Distribuzione:")
    for tentativo in (1, 2, 3, 4):
        conteggio = distribuzione.get(tentativo, 0)
        percentuale = 100.0 * conteggio / n
        barra = "█" * int(round(percentuale / 5))   # 1 blocco ogni 5%
        print(f"     Tentativo {tentativo}: {conteggio:>4}  ({percentuale:5.1f}%) {barra}")
    print("=" * 70)


def stampa_riepilogo_regressioni(per_stagione):
    """
    Riepilogo CROSS-STAGIONE delle regressioni: quantifica il PARADOSSO sul
    panel di semi simulati. Risponde alle domande chiave del §2:
        - quante stagioni hanno almeno un turno regressivo?
        - in totale, quanti turni regressivi su quanti riusciti?
        - quanto è grande la regressione PEGGIORE (dislivello incomp.)?
        - qual è il TURNO PEGGIORE in assoluto?  Questo è il valore da NON
          peggiorare quando agiremo sull'algoritmo (vincolo del §2:
          "ridurre le regressioni senza peggiorare il caso peggiore").

    `per_stagione` è una lista di tuple (seme, risultati).
    """
    n_stagioni = len(per_stagione)
    if n_stagioni == 0:
        return

    # Contatori aggregati
    totale_turni_riusciti = 0
    totale_regressivi = 0
    stagioni_con_regressioni = 0

    # "Record negativi": dove è successa la regressione peggiore e il turno
    # in assoluto più sporco. Servono perché un solo numero non basta:
    # dobbiamo poterli RITROVARE (seme + turno) per ispezione.
    gravita_max = 0
    gravita_max_dove = None       # tupla (seme, turno_regressivo, turno_successivo_migliore)
    incomp_peggiore = 0
    incomp_peggiore_dove = None   # tupla (seme, turno)

    for seme, risultati in per_stagione:
        regressivi = analizza_regressioni(risultati)
        n_riusciti = sum(1 for r in risultati if r["successo"])
        totale_turni_riusciti += n_riusciti
        totale_regressivi += len(regressivi)
        if regressivi:
            stagioni_con_regressioni += 1
            for reg in regressivi:
                if reg["delta_incomp"] > gravita_max:
                    gravita_max = reg["delta_incomp"]
                    gravita_max_dove = (seme, reg["turno"], reg["miglior_succ_turno"])

        # Scansione anche per il "turno peggiore assoluto"
        for r in risultati:
            if r["successo"] and r["incomp_pesate"] is not None \
                    and r["incomp_pesate"] > incomp_peggiore:
                incomp_peggiore = r["incomp_pesate"]
                incomp_peggiore_dove = (seme, r["turno"])

    # Stampa
    print()
    print("=" * 70)
    print("ANALISI REGRESSIONI (paradosso di monotonia — Leva 2)")
    print("=" * 70)
    print(f"Stagioni analizzate                 : {n_stagioni}")
    print(f"Turni riusciti totali               : {totale_turni_riusciti}")

    perc_stag = 100.0 * stagioni_con_regressioni / n_stagioni
    print(f"Stagioni con ALMENO 1 regressione   : "
          f"{stagioni_con_regressioni} su {n_stagioni}  ({perc_stag:.1f}%)")

    if totale_turni_riusciti > 0:
        perc_turni = 100.0 * totale_regressivi / totale_turni_riusciti
        print(f"Turni REGRESSIVI totali             : "
              f"{totale_regressivi} su {totale_turni_riusciti}  ({perc_turni:.1f}%)")

    if totale_regressivi > 0 and gravita_max_dove is not None:
        s, t_reg, t_succ = gravita_max_dove
        print(f"GRAVITÀ MASSIMA (dislivello incomp.): {gravita_max}"
              f"  [seme {s}, turno {t_reg} → migliore al turno {t_succ}]")

    if incomp_peggiore_dove is not None:
        s, t = incomp_peggiore_dove
        print(f"TURNO PEGGIORE in assoluto          : "
              f"incomp. pesate {incomp_peggiore}  [seme {s}, turno {t}]")
        print("   (è il valore-soglia da NON peggiorare quando agiremo sul motore)")
    print("=" * 70)


# ───────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Banco di prova: misura la qualità dell'algoritmo su assegnazioni ripetute."
    )
    parser.add_argument("file_classe", help="Percorso al file .txt della classe")
    parser.add_argument("--turni", type=int, default=10,
                        help="Assegnazioni consecutive per stagione (default 10)")
    parser.add_argument("--ripetizioni", type=int, default=1,
                        help="Numero di stagioni indipendenti da mediare (default 1)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seme casuale per risultati riproducibili (default: casuale)")
    parser.add_argument("--modalita-trio", choices=["prima", "ultima", "centro"],
                        default="centro", help="Posizione del trio (default centro)")
    parser.add_argument("--candidati", type=int, default=1,
                        help="Quante disposizioni generare per turno tenendo la più "
                             "pulita - Leva 1 / best-of-N (default 1 = baseline)")
    # ── LEVA A "leggera" (lookahead di un passo) ─────────────────────────────
    parser.add_argument("--lookahead", action="store_true",
                        help="Attiva la Leva A: per scegliere il candidato del "
                             "turno T simula anche il turno T+1 e minimizza il "
                             "caso peggiore (minimax). Default: disattivata.")
    parser.add_argument("--m-lookahead", dest="M_lookahead", type=int, default=3,
                        help="Quanti candidati ipotetici generare per il turno "
                             "T+1 durante il lookahead (default 3). Ha effetto "
                             "solo con --lookahead.")
    args = parser.parse_args()

    if not os.path.exists(args.file_classe):
        print(f"❌ File non trovato: {args.file_classe}")
        sys.exit(1)

    # ── SEME BASE ──────────────────────────────────────────────────────────
    # Se l'utente fornisce --seed lo usiamo come seme base; altrimenti ne
    # estraiamo uno casuale dal sistema e lo STAMPIAMO subito, così la corsa
    # resta riproducibile anche "a caso" (basta ricopiare il numero).
    # Da qui in poi NON usiamo più un random.seed() globale: ogni stagione
    # avrà il SUO seme derivato (vedi sotto).
    seme_base = args.seed if args.seed is not None else random.randint(1, 999_999)

    print("=" * 70)
    print("BANCO DI PROVA — Misura qualità algoritmo PostiPerfetti")
    print("=" * 70)
    print(f"Classe        : {args.file_classe}")
    print(f"Turni/stagione: {args.turni}")
    print(f"Stagioni      : {args.ripetizioni}")
    nota_seme = "(fornito)" if args.seed is not None else "(estratto a caso, ricopialo per riprodurre)"
    print(f"Seme base     : {seme_base}  {nota_seme}")
    if args.ripetizioni > 1:
        # Mostro il "range" dei semi usati nello sweep, così è chiaro a colpo
        # d'occhio quali stagioni stiamo confrontando se rilanciamo dopo.
        ultimo = seme_base + args.ripetizioni - 1
        print(f"Semi stagioni : {seme_base} … {ultimo}  "
              f"(uno per stagione, derivato dal seme base)")
    print(f"Modalità trio : {args.modalita_trio}")
    print(f"Candidati/turno (Leva 1): {args.candidati}"
          f"{'  (= baseline)' if args.candidati == 1 else ''}")
    # Stato della Leva A: lo dichiaro a inizio corsa per non confondere i
    # risultati di due esecuzioni diverse messe a confronto.
    if args.lookahead:
        print(f"Leva A (lookahead 1 passo): ATTIVA  "
              f"(M={args.M_lookahead} candidati ipotetici per T+1, criterio minimax)")
        if args.candidati <= 1:
            # Con 1 solo candidato non c'è scelta da fare: la leva non ha gambe.
            print("   ⚠ ATTENZIONE: con --candidati 1 il lookahead è inutile "
                  "(un solo candidato per turno = nessuna scelta da guidare).")
    else:
        print("Leva A (lookahead 1 passo): disattivata")
    print("=" * 70)

    tutti_risultati = []
    # NUOVO: oltre alla lista "piatta" (per il riepilogo aggregato esistente),
    # tengo anche la lista raggruppata PER STAGIONE, con il rispettivo seme.
    # È quello che serve a stampa_riepilogo_regressioni per dirci "stagione X
    # (seme Y) ha questi turni regressivi".
    per_stagione = []

    for numero_stagione in range(1, args.ripetizioni + 1):
        # ── SEME DERIVATO ─────────────────────────────────────────────────
        # Ogni stagione usa un proprio seme = seme_base + (n - 1).
        # Vantaggio strutturale: ogni stagione è riproducibile DA SOLA, e una
        # futura modifica del motore (es. che cambia quanta casualità una
        # stagione consuma) NON sposta le stagioni successive. Senza questo
        # accorgimento, cambiando una cosa al turno 1 della stagione 1 si
        # sposterebbero TUTTE le altre stagioni, sporcando il confronto
        # prima/dopo.
        seme_stagione = seme_base + (numero_stagione - 1)
        random.seed(seme_stagione)

        risultati = esegui_una_stagione(
            args.file_classe, args.turni, args.modalita_trio, args.candidati,
            lookahead=args.lookahead, M_lookahead=args.M_lookahead
        )
        tutti_risultati.extend(risultati)
        per_stagione.append((seme_stagione, risultati))

        # Mostro la tabella dettagliata solo se le stagioni sono poche
        # (altrimenti, con sweep di 20+ stagioni, si annega tutto: si va
        # direttamente al riepilogo).
        if args.ripetizioni <= 3:
            print(f"\n--- STAGIONE {numero_stagione}  "
                  f"(seme {seme_stagione}, turno per turno) ---")
            stampa_tabella_stagione(risultati)

    # Riepilogo "tradizionale" (medie, peggiore, distribuzione tentativi)
    stampa_riepilogo(tutti_risultati)
    # Riepilogo NUOVO della Leva 2 (regressioni cross-stagione + turno peggiore)
    stampa_riepilogo_regressioni(per_stagione)


if __name__ == "__main__":
    main()
