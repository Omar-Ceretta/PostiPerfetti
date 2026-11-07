# -*- coding: utf-8 -*-
# Parte di PostiPerfetti (GNU GPLv3).
"""Backend Q17 esplicito, locale alla chiamata e privo di monkey-patching.

Porting meccanico delle funzioni congelate Q17, Q8 e Q8b; non cambia
pesi, ordinamento, memoizzazione o limiti. T1-T3 usano la sonda Q8b;
T4 usa Q17 direttamente. Nessuna funzione di modulo viene riassegnata.
La scelta del backend e' effettuata dal chiamante nel motore Blocchi.

Ottimizzazione E1: riusa transizioni immutabili e insiemi residui
entro una singola chiamata Q17. Ordine, memo esterna e tetti restano quelli
della base; nessuna cache viene condivisa fra mesi o ingressi diversi.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from time import perf_counter
from moduli.calcolo import motore_blocchi as motore
from moduli.dominio.metrica_pulizia import Gruppo, nome_completo

# Q17: algoritmo congelato, escluso il context manager che intercettava q7b.
def backtrack_q17(disponibili, disponibili_id, indice, rimanenti_per_taglia, schema, *,
              gruppi_scelti=(), fisso_atteso=False, contatore_nodi=None,
              limite_nodi=None, profondita=0, telemetria=None, stati_falliti=None,
              fcg_soglia_backtrack=None, fcg_massimo_attivazioni=None,
              fcg_stato=None, cache_matching=None, memo_geometrica=False):
    """Sostituzione sperimentale della sola ricerca deterministica senza FCG.

    Scarti per taglia aggregati solo nei contatori: le decisioni visitate e
    l'hash del percorso restano identici, anche in caso di tetto/soluzione.
    Non gestisce modifiche concorrenti o callback che mutano studenti/indice.
    """
    if not memo_geometrica or fcg_soglia_backtrack is not None:
        raise ValueError('Q7b richiede memo geometrica e ricerca senza FCG.')
    if len({id(s) for s in disponibili}) != len(disponibili) or set(disponibili_id) != {id(s) for s in disponibili}:
        raise ValueError('Q7b richiede disponibili univoci e identificativi coerenti.')
    limite = motore.LIMITE_NODI_BACKTRACK if limite_nodi is None else int(limite_nodi)
    if cache_matching is None:
        cache_matching = fcg_stato.setdefault('matcher_cache', {}) if fcg_stato is not None else {}
    fisso = bool(fisso_atteso)
    studenti = tuple(disponibili)
    bits = {id(s): 1 << i for i, s in enumerate(studenti)}
    taglie = tuple(sorted(rimanenti_per_taglia))
    # Dimensione/profilo/maschera condivisi dalle voci che riusano la stessa
    # lista membri, mai dalle sole identità degli studenti rimasti.
    voci = {}; note = {}; filtri = {}; forme = {}
    # La firma successiva dipende soltanto dalla firma attuale e dal profilo.
    # La maschera identifica univocamente il sottoinsieme degli studenti di
    # questa chiamata: il frozenset mantiene il formato della memo pubblica.
    transizioni_firma = {}
    ids_per_mask = {(1 << len(studenti)) - 1: frozenset(disponibili_id)}

    def profilo(membri):
        ns = []
        for s in membri:
            sid = id(s)
            if sid not in note:
                note[sid] = str(getattr(s, 'nota_posizione', 'NORMALE')).strip().upper()
            ns.append(note[sid])
        return len(membri), 'PRIMA' in ns, tuple(i for i, n in enumerate(ns) if n == 'FISSO')

    def alternative(ancora, attive):
        chiave = ancora, attive
        if chiave not in filtri:
            filtri[chiave] = [[], 0, indice.get(id(studenti[ancora]), ())]
        stato = filtri[chiave]
        def genera():
            # Riusa il prefisso già esaminato, poi avanza solo su richiesta.
            # Neppure la scansione per taglia anticipa le scelte successive.
            for voce in stato[0]:
                yield voce
            originali = stato[2]
            while stato[1] < len(originali):
                posizione = stato[1]; stato[1] += 1
                membri, _punti = originali[posizione]
                n = len(membri)
                if n in attive:
                    identita = id(membri)
                    if identita not in voci:
                        usati_id = frozenset(id(s) for s in membri)
                        usati = 0
                        for sid in usati_id:
                            usati |= bits.get(sid, 1 << len(studenti))
                        # Il gruppo/profilo resta pigro: solo se i membri sono liberi.
                        voci[identita] = [membri, usati, usati_id, None]
                    voce = posizione, n, voci[identita]
                    stato[0].append(voce)
                    yield voce
        return genera(), len(stato[2])

    def scarti_taglia(quanti):
        if telemetria is not None and quanti:
            telemetria.incrementa('pruning_totali', quanti)
            telemetria.incrementa('pruning:taglia_esaurita', quanti)

    def visita(mask, ids, quanti, scelti, firma, depth):
        if quanti not in forme:
            forma = tuple(zip(taglie, quanti))
            riduzioni = {n: quanti[:j] + (q - 1,) + quanti[j+1:]
                         for j, (n, q) in enumerate(forma) if q > 0}
            forme[quanti] = (forma, frozenset(riduzioni),
                             sum(n*q for n, q in forma), riduzioni)
        forma, attive, posti, riduzioni = forme[quanti]
        chiave = None
        if stati_falliti is not None:
            chiave = ids, forma, (firma, fisso)
            if chiave in stati_falliti:
                if telemetria is not None:
                    telemetria.potatura('memo_stato_fallito'); telemetria.incrementa('memo_hit')
                return None
        if contatore_nodi is not None:
            contatore_nodi[0] += 1
            if telemetria is not None: telemetria.nodo(depth)
            if contatore_nodi[0] > limite:
                if telemetria is not None: telemetria.potatura('tetto_nodi')
                return None
        if posti != mask.bit_count():
            if telemetria is not None: telemetria.potatura('forma_residua_incoerente')
            return None
        if not mask:
            if any(quanti):
                if telemetria is not None: telemetria.potatura('blocchi_residui')
                return None
            esito = motore.verifica_fattibilita_matching(scelti, schema)
            if telemetria is not None:
                telemetria.incrementa('matching_finale_chiamate')
                telemetria.incrementa('matching_finale_visite_archi', int(esito.diagnostica.visite_archi_fattibilita))
            if not esito.fattibile:
                if telemetria is not None:
                    telemetria.potatura('matching_geometrico_finale'); telemetria.incrementa('matching_finale_fallimenti')
                    for errore in esito.errori_duri: telemetria.incrementa('matching_fallimento:' + errore)
                return None
            return []
        ancora = (mask & -mask).bit_length() - 1
        opzioni, lunghezza = alternative(ancora, attive)
        precedente = -1
        for posizione, n, voce in opzioni:
            if telemetria is not None: scarti_taglia(posizione - precedente - 1)
            precedente = posizione
            membri, usati, usati_id, dati_gruppo = voce
            if mask & usati != usati:
                if telemetria is not None: telemetria.potatura('membri_non_disponibili')
                continue
            if dati_gruppo is None:
                dati_gruppo = Gruppo(motore._tipo_per_taglia(n), membri), profilo(membri)
                voce[3] = dati_gruppo
            gruppo, requisiti = dati_gruppo
            chiave_transizione = firma, requisiti
            transizione = transizioni_firma.get(chiave_transizione)
            if transizione is None:
                p = bisect_right(firma, requisiti)
                nuova_firma = firma[:p] + (requisiti,) + firma[p:]
                transizione = nuova_firma, (nuova_firma, fisso)
                transizioni_firma[chiave_transizione] = transizione
            nuova_firma, k_matching = transizione
            nuovi = scelti + (gruppo,)
            if k_matching in cache_matching:
                ok = bool(cache_matching[k_matching])
                if telemetria is not None: telemetria.incrementa('matching_parziale_cache_hit')
            else:
                esito = motore.verifica_fattibilita_parziale_matching(nuovi, schema, fisso_atteso=fisso_atteso)
                motore._registra_esito_matching_parziale(telemetria, esito)
                ok = bool(esito.fattibile); cache_matching[k_matching] = ok
            if not ok:
                if telemetria is not None: telemetria.potatura('matching_geometrico_parziale')
                continue
            if telemetria is not None:
                telemetria.decisione('gruppo_' + str(n), tuple(nome_completo(s) for s in gruppo.membri), depth)
            residui = riduzioni[n]
            nuova_mask = mask & ~usati
            nuovi_ids = ids_per_mask.get(nuova_mask)
            if nuovi_ids is None:
                nuovi_ids = ids - usati_id
                ids_per_mask[nuova_mask] = nuovi_ids
            risultato = visita(nuova_mask, nuovi_ids, residui, nuovi, nuova_firma, depth + 1)
            if risultato is not None: return [gruppo] + risultato
            if fcg_stato is not None: fcg_stato['backtrack'] = int(fcg_stato.get('backtrack', 0)) + 1
            if telemetria is not None: telemetria.backtrack()
            if contatore_nodi is not None and contatore_nodi[0] > limite: return None
        scarti_taglia(lunghezza - precedente - 1)
        if stati_falliti is not None and (contatore_nodi is None or contatore_nodi[0] <= limite):
            stati_falliti.add(chiave)
            if telemetria is not None: telemetria.incrementa('memo_store')
        return None

    firma = motore._firma_geometrica_parziale(gruppi_scelti)
    try:
        return visita((1 << len(studenti)) - 1, frozenset(disponibili_id),
                      tuple(rimanenti_per_taglia[n] for n in taglie), tuple(gruppi_scelti), firma, profondita)
    finally:
        # La chiusura ricorsiva altrimenti trattiene memo/cache fino al GC.
        visita = None


# Q8: sonda dei domini residui, senza esposizione al chiamante.
def backtrack_q8_domini(disponibili, disponibili_id, indice, rimanenti_per_taglia, schema, *,
              gruppi_scelti=(), fisso_atteso=False, contatore_nodi=None,
              limite_nodi=None, profondita=0, telemetria=None, stati_falliti=None,
              cache_matching=None, memo_geometrica=False, statistiche=None,
              **non_supportati):
    if non_supportati or telemetria is not None or not memo_geometrica:
        raise ValueError('Q8 usa snapshot senza FCG/telemetria e memo geometrica.')
    ss = tuple(disponibili); ids = frozenset(disponibili_id)
    if len(ids) != len(ss) or ids != frozenset(id(s) for s in ss):
        raise ValueError('Studenti iniziali non univoci/coerenti.')
    stats = Counter() if statistiche is None else statistiche
    nodi = [0] if contatore_nodi is None else contatore_nodi
    limite = motore.LIMITE_NODI_BACKTRACK if limite_nodi is None else int(limite_nodi)
    memo = set() if stati_falliti is None else stati_falliti
    cache = {} if cache_matching is None else cache_matching
    taglie = tuple(sorted(rimanenti_per_taglia)); pos = {n:i for i,n in enumerate(taglie)}
    bits = {id(s):1 << i for i,s in enumerate(ss)}
    record = []; per_identita = {}; ordini = []; coperture = [0]*len(ss)
    per_taglia = {}; per_profilo = {}
    # Indice di bit dei gruppi: eliminare uno studente elimina in blocco tutti
    # i gruppi che lo contengono, senza riesaminare ogni lista di membri.
    for s in ss:
        ordine = []; visti = set()
        for membri, _punti in indice.get(id(s), ()):
            identita = id(membri)
            if any(id(m) not in bits for m in membri):
                continue
            if id(s) not in {id(m) for m in membri}:
                raise ValueError('Gruppo estraneo alla propria ancora.')
            if identita not in per_identita:
                usati = frozenset(id(m) for m in membri)
                if len(usati) != len(membri):
                    raise ValueError('Membri duplicati nel gruppo.')
                n = len(membri)
                if n not in pos:
                    continue
                note = [str(getattr(m,'nota_posizione','NORMALE')).strip().upper() for m in membri]
                profilo = n, 'PRIMA' in note, tuple(i for i,x in enumerate(note) if x=='FISSO')
                mask = sum(bits[x] for x in usati)
                g = Gruppo(motore._tipo_per_taglia(n), membri)
                j = len(record); per_identita[identita] = j
                record.append((n,mask,usati,g,profilo))
                bit = 1 << j
                per_taglia[n] = per_taglia.get(n,0) | bit
                per_profilo[profilo] = per_profilo.get(profilo,0) | bit
                for i in range(len(ss)):
                    if mask & (1 << i): coperture[i] |= bit
            j = per_identita[identita]
            if j not in visti:
                ordine.append(j); visti.add(j)
        ordini.append({j:i for i,j in enumerate(ordine)})
    for i,ordine in enumerate(ordini):
        if sum(1 << j for j in ordine) != coperture[i]:
            raise ValueError('Q8 richiede indice simmetrico per tutti i membri.')
    stats['gruppi_indicizzati'] += len(record)
    firma_iniziale = motore._firma_geometrica_parziale(gruppi_scelti)

    def visita(mask, rimasti_id, quanti, scelti, firma, attivi):
        forma = tuple(zip(taglie,quanti))
        chiave = rimasti_id, forma, (firma,bool(fisso_atteso))
        if chiave in memo:
            stats['memo_hit'] += 1
            return None
        nodi[0] += 1
        if nodi[0] > limite:
            stats['tetto_nodi'] += 1
            return None
        if sum(n*q for n,q in forma) != mask.bit_count():
            stats['forma_incoerente'] += 1
            return None
        if not mask:
            if any(quanti): return None
            return [] if motore.verifica_fattibilita_matching(scelti,schema).fattibile else None
        ammessi_taglia = 0
        for n,q in forma:
            if q > 0: ammessi_taglia |= per_taglia.get(n,0)
        ammessi = attivi & ammessi_taglia
        # Tutte le voci con lo stesso profilo condividono la compatibilità
        # geometrica. Una verifica per profilo, poi esclusione tramite bit.
        firme = {}
        for profilo, insieme in per_profilo.items():
            presenti = ammessi & insieme
            if not presenti: continue
            p = bisect_right(firma,profilo)
            nuova = firma[:p]+(profilo,)+firma[p:]
            k = nuova,bool(fisso_atteso)
            if k not in cache:
                j = (presenti & -presenti).bit_length()-1
                cache[k] = motore.verifica_fattibilita_parziale_matching(
                    scelti+(record[j][3],),schema,fisso_atteso=fisso_atteso).fattibile
                stats['matching_nuovi'] += 1
            if not cache[k]:
                ammessi &= ~insieme
                stats['profili_esclusi'] += 1
            else: firme[profilo] = nuova
        # Forward check su TUTTI i rimasti. Anche dopo un dominio singleton
        # si continua: un altro studente senza opzioni rende il ramo sterile.
        da_esaminare = mask; migliore = None; dominio = 0; minimo = len(record)+1
        while da_esaminare:
            bit = da_esaminare & -da_esaminare; da_esaminare -= bit
            i = bit.bit_length()-1; d = ammessi & coperture[i]
            stats['domini_esaminati'] += 1
            conta = d.bit_count()
            if conta == 0:
                memo.add(chiave); stats['dominio_vuoto'] += 1
                return None
            if conta < minimo: migliore,dominio,minimo = i,d,conta
        candidati = []
        while dominio:
            bit = dominio & -dominio; dominio -= bit
            candidati.append(bit.bit_length()-1)
        candidati.sort(key=ordini[migliore].__getitem__)
        for j in candidati:
            n,usati,usati_id,g,profilo = record[j]
            residui = list(quanti); residui[pos[n]] -= 1
            conflitti = 0; resto = usati
            while resto:
                bit = resto & -resto; resto -= bit
                conflitti |= coperture[bit.bit_length()-1]
            stats['rami'] += 1
            risultato = visita(mask & ~usati,rimasti_id-usati_id,tuple(residui),
                               scelti+(g,),firme[profilo],ammessi & ~conflitti)
            if risultato is not None: return [g]+risultato
            if nodi[0] > limite: return None
        memo.add(chiave)
        return None

    try:
        return visita((1 << len(ss))-1,ids,tuple(rimanenti_per_taglia[n] for n in taglie),
                      tuple(gruppi_scelti),firma_iniziale,(1 << len(record))-1)
    finally:
        visita = None


# Q8b: orchestrazione della sonda e ripresa Q17, senza hook.
SOGLIA_PREFISSO = 1024
LIMITE_SONDA = 2048


def positivo(n):
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def backtrack_q8b(*args, soglia=SOGLIA_PREFISSO, limite_sonda=LIMITE_SONDA,
              resoconto=None, **kw):
    if not positivo(soglia) or not positivo(limite_sonda):
        raise ValueError('Soglia e limite sonda devono essere interi positivi.')
    if (kw.get('telemetria') is not None or not kw.get('memo_geometrica', False)
            or kw.get('fcg_soglia_backtrack') is not None
            or kw.get('fcg_stato') is not None):
        raise ValueError('Q8b richiede memo geometrica, senza FCG o telemetria per nodo.')
    dati = {} if resoconto is None else resoconto
    dati.clear()
    nodi = kw.get('contatore_nodi')
    if nodi is None: nodi = [0]
    iniziali = nodi[0]
    limite = kw.get('limite_nodi')
    limite = motore.LIMITE_NODI_BACKTRACK if limite is None else int(limite)
    prefisso_cap = min(limite, iniziali + soglia)
    memo = kw.get('stati_falliti'); cache = kw.get('cache_matching')
    if memo is None: memo = set()
    if cache is None: cache = {}
    # Il chiamante non vede le prove esplorative fino a un esito definitivo.
    prefisso_memo = set(memo); prefisso_cache = dict(cache); pn = [iniziali]
    opzioni = dict(kw, contatore_nodi=pn, stati_falliti=prefisso_memo,
                   cache_matching=prefisso_cache, limite_nodi=prefisso_cap)
    t0 = perf_counter(); risultato = backtrack_q17(*args, **opzioni)
    dati.update(sonda_domini=False, limite_nodi_q7b=limite, soglia_prefisso=soglia,
                limite_nodi_sonda=0, prefisso_secondi=perf_counter()-t0,
                prefisso_nodi=pn[0]-iniziali, domini_nodi=0, domini_secondi=0.,
                statistiche_domini={}, ripresa_q7b=False, ripresa_nodi=0,
                ripresa_secondi=0.)

    def termina(r):
        dati.update(nodi_restituiti=nodi[0]-iniziali,
                    nodi_lavoro=dati['prefisso_nodi']+dati['domini_nodi']+dati['ripresa_nodi'])
        return r

    if risultato is not None or pn[0] <= prefisso_cap or prefisso_cap == limite:
        nodi[0] = pn[0]; memo.update(prefisso_memo); cache.update(prefisso_cache)
        return termina(risultato)

    # La sentinella del prefisso non è un nodo esplorato. Un fallimento
    # certificato mantiene il contatore restituito entro il tetto nativo.
    cap_sonda = min(limite_sonda, limite-prefisso_cap)
    dn = [0]; stats = Counter()
    opzioni.update(contatore_nodi=dn, limite_nodi=cap_sonda, statistiche=stats)
    for nome in ('fcg_soglia_backtrack', 'fcg_massimo_attivazioni', 'fcg_stato'):
        opzioni.pop(nome, None)
    t0 = perf_counter(); prova = backtrack_q8_domini(*args, **opzioni)
    esito = 'SOLUZIONE' if prova is not None else 'TETTO_NODI' if dn[0] > cap_sonda else 'ESAURITA'
    dati.update(sonda_domini=True, limite_nodi_sonda=cap_sonda,
                domini_secondi=perf_counter()-t0, domini_nodi=dn[0],
                statistiche_domini=dict(stats), esito_domini=esito)
    if esito == 'ESAURITA':
        nodi[0] = prefisso_cap + dn[0]
        memo.update(prefisso_memo); cache.update(prefisso_cache)
        return termina(None)

    # Non riusare neppure la memo del prefisso: diminuirebbe i nodi nativi
    # e potrebbe trasformare un tetto Q7b in una soluzione prima irraggiunta.
    opzioni = dict(kw, contatore_nodi=nodi, stati_falliti=memo,
                   cache_matching=cache, limite_nodi=limite)
    t0 = perf_counter(); risultato = backtrack_q17(*args, **opzioni)
    dati.update(ripresa_q7b=True, ripresa_nodi=nodi[0]-iniziali,
                ripresa_secondi=perf_counter()-t0)
    return termina(risultato)
