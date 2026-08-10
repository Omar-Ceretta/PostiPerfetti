# -*- coding: utf-8 -*-
"""
motore_terzetti.py — partizione degli studenti per la modalità a terzetti.

Parte di «PostiPerfetti», programma per l'assegnazione automatica dei posti
in una classe scolastica. Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

Il modulo suddivide gli studenti in terzetti e nell'eventuale blocco finale:
una coppia, un quartetto oppure, quando richiesto, due quartetti. Riusa il
punteggio a coppie di ``MotoreVincoliConfigurato`` e applica le regole di
rotazione dello Storico senza duplicarle.

Gli studenti di ogni gruppo siedono in fila: contano soltanto le adiacenze
consecutive. L'ordine interno è quindi parte della soluzione; gli estremi non
sono considerati vicini. Un gruppo è ammissibile quando esiste almeno un ordine
privo di adiacenze assolutamente vietate.

La ricerca usa un backtracking ancorato sul primo studente libero. I tentativi
1–3 sono deterministici; il quarto esegue ripartenze casuali con semi locali e
riproducibili. Un limite ai nodi visitati impedisce esplosioni combinatorie
quando una soluzione senza ripetizioni non esiste.
"""

import itertools
from collections import Counter
from time import perf_counter_ns
from moduli.studenti import chiave_ordinamento_studente

# Tipi di gruppo e regole condivise per adiacenze, vincoli assoluti e blacklist.
from moduli.metrica_pulizia import (
    Gruppo, TIPO_COPPIA, TIPO_TERZETTO, TIPO_QUARTETTO,
    livello_incompatibilita, nome_completo,
    # Metrica del best-of-N e fotografia iniziale della blacklist.
    chiave_pulizia_terzetti, snapshot_blacklist_terzetti,
    conta_incompatibilita_per_livello_terzetti,
    conta_affinita_soddisfatte_terzetti, adiacenze_partizione,
)

# Lo strato storico applica la penalità dei riusi e fornisce la chiave della
# blacklist riservata alla modalità a terzetti.
from moduli.strato_storico import applica_penalita_storico, CHIAVE_BLACKLIST_PER_MODO

from moduli.vincoli import MotoreVincoliConfigurato
from moduli.aula import (
    pianifica_blocco_finale_terzetti,
    valida_preferenza_resto2,
)
from moduli.casualita import (
    crea_generatore, deriva_seed, risolvi_seed_principale
)
from moduli.diagnostica_ricerca import (
    firma_indice_terzetti, messaggio_motore,
)
from moduli.lingua import quantita
from moduli.strategie_ricerca import (
    diversifica_indice_terzetti,
    precalcola_chiavi_strette_terzetti,
    strategia_corrente,
)

# Ripartenze casuali eseguite dal quarto tentativo.
NUM_RIPARTENZE_TENTATIVO_4 = 15

# Numero massimo di nodi visitabili in un singolo tentativo. Se il limite è
# superato, la cascata passa al tentativo successivo, evitando ricerche
# esaustive troppo costose quando una soluzione più restrittiva non esiste.
LIMITE_NODI_BACKTRACK = 100000

# Elimina le disposizioni speculari, equivalenti per adiacenze e punteggio.
OTTIMIZZA_SPECCHIATE = True

# Penalità per un gruppo che contiene insieme PRIMA/FISSO e ULTIMA. È inferiore
# alla penalità di riuso, quindi agisce come criterio secondario; 0 la disattiva.
PESO_PRIMA_ULTIMA = 50

# Numero di candidati mensili valutati dal best-of-N. Tre offre un compromesso
# fra il beneficio, generalmente modesto, e il costo elevato delle partizioni
# con quartetti. Tutti i chiamanti leggono questa costante.
NUM_CANDIDATI_TERZETTI = 3


def _incrementa_contatore(contatore, voce, quantita=1):
    """Incrementa Counter o TelemetriaRicerca senza imporre una dipendenza."""
    if contatore is None:
        return
    incrementa = getattr(contatore, "incrementa", None)
    if incrementa is not None:
        incrementa(voce, quantita)
    else:
        contatore[voce] += quantita


def _rappresenta_partizione(gruppi):
    """Rappresentazione persistente di una partizione per firme e JSON."""
    if gruppi is None:
        return None
    return [
        (gruppo.tipo, [nome_completo(membro) for membro in gruppo.membri])
        for gruppo in gruppi
    ]


# ---------------------------------------------------------------------------
# Pianificazione del blocco finale
# ---------------------------------------------------------------------------
def pianifica_resto(n_rimanenti, preferenza_resto2='coppia'):
    """Determina terzetti e blocco finale dal numero di studenti.

    Restituisce ``(numero_terzetti, tipo_resto, dimensione_resto)``. Il resto
    può essere assente, una coppia o un quartetto. Con ``due_quartetti`` e
    almeno otto studenti, un resto modulo 3 pari a 2 viene chiuso con due
    quartetti, segnalati dalla dimensione 8.

    Restituisce ``None`` per i casi degeneri che non possono formare gruppi
    validi.
    """
    valida_preferenza_resto2(preferenza_resto2)

    if n_rimanenti < 2:
        return None

    resto = n_rimanenti % 3
    if resto == 1 and n_rimanenti < 4:
        return None

    k_terzetti, blocchi_finali = pianifica_blocco_finale_terzetti(
        n_rimanenti, preferenza_resto2
    )
    if not blocchi_finali:
        return (k_terzetti, None, 0)

    dimensione = sum(larghezza for larghezza, _tipo in blocchi_finali)
    tipo = (
        TIPO_QUARTETTO
        if any(tipo_blocco == 'quartetto'
               for _larghezza, tipo_blocco in blocchi_finali)
        else TIPO_COPPIA
    )
    return (k_terzetti, tipo, dimensione)


# ---------------------------------------------------------------------------
# Cache dei punteggi a coppie
# ---------------------------------------------------------------------------
def _chiave_coppia(studente_a, studente_b):
    """Restituisce la chiave indipendente dall'ordine di due studenti.

    Il punteggio della coppia è simmetrico; gli ``id`` ordinati evitano chiavi
    diverse quando gli argomenti arrivano invertiti.
    """
    return tuple(sorted((id(studente_a), id(studente_b))))


def calcola_punteggi_coppie(motore_vincoli, studenti,
                            volte_blacklist=None, blacklist_blocca=False,
                            contatori=None):
    """Calcola una volta per tentativo punteggi e adiacenze bloccate.

    ``punteggio`` contiene il valore già comprensivo dell'eventuale penalità
    storica. ``bloccata`` vale per le incompatibilità assolute e, nei tentativi
    1–3, per le coppie presenti nella blacklist. Nel quarto tentativo i riusi
    restano ammessi ma penalizzati.

    La funzione deve essere richiamata dopo ogni configurazione del tentativo,
    perché i vincoli non assoluti possono cambiare.
    """
    punteggio = {}
    bloccata = {}
    for i in range(len(studenti)):
        for j in range(i + 1, len(studenti)):
            a = studenti[i]
            b = studenti[j]
            risultato = motore_vincoli.calcola_punteggio_coppia(a, b)
            if contatori is not None:
                _incrementa_contatore(contatori, "coppie_valutate")
            k = _chiave_coppia(a, b)
            punteggio[k] = risultato['punteggio_totale']

            # Il livello 3 viene letto dai dati: il wrapper storico può cambiare
            # la valutazione testuale, ma non deve rendere lecita l'adiacenza.
            e_liv3 = (livello_incompatibilita(a, b) == 3)

            e_blacklist_bloccante = False
            if blacklist_blocca and volte_blacklist:
                chiave_nomi = frozenset((nome_completo(a), nome_completo(b)))
                e_blacklist_bloccante = chiave_nomi in volte_blacklist

            bloccata[k] = e_liv3 or e_blacklist_bloccante
    return punteggio, bloccata


# ---------------------------------------------------------------------------
# Valutazione e ordinamento dei gruppi
# ---------------------------------------------------------------------------
def _penalita_prima_ultima(membri):
    """Restituisce la penalità per preferenze di fila inconciliabili.

    FISSO conta come posizione frontale. La penalità dipende dai membri, non
    dall'ordine interno del gruppo.
    """
    if PESO_PRIMA_ULTIMA == 0:
        return 0
    # FISSO è una posizione frontale come PRIMA.
    ha_front = any(getattr(s, 'nota_posizione', 'NORMALE') in ('PRIMA', 'FISSO')
                   for s in membri)
    ha_ultima = any(getattr(s, 'nota_posizione', 'NORMALE') == 'ULTIMA' for s in membri)
    return PESO_PRIMA_ULTIMA if (ha_front and ha_ultima) else 0


def valuta_gruppo(membri, punteggio, bloccata, contatori=None):
    """Trova l'ordine ammissibile col punteggio più alto.

    Valuta tutte le disposizioni di una coppia, un terzetto o un quartetto e
    somma i punteggi delle sole adiacenze consecutive. Scarta gli ordini con
    almeno un'adiacenza bloccata e restituisce ``None`` se nessun ordine è
    valido.

    Le coppie interne vengono precaricate e le disposizioni speculari vengono
    escluse, perché producono le stesse adiacenze. Se il gruppo contiene FISSO,
    questo occupa l'estremo sinistro.
    """
    misura = contatori is not None
    if misura:
        _incrementa_contatore(contatori, "gruppi_valutati")
    miglior_ordine = None
    miglior_punteggio = None
    membri = list(membri)
    n_membri = len(membri)

    # Il FISSO occupa l'estremo sinistro; il vincolo rompe già la simmetria.
    gruppo_ha_fisso = any(getattr(s, 'nota_posizione', 'NORMALE') == 'FISSO'
                          for s in membri)

    # Precarica blocco e punteggio di ogni coppia interna al gruppo.
    info_coppia = {}
    for i in range(n_membri):
        for j in range(i + 1, n_membri):
            k = _chiave_coppia(membri[i], membri[j])
            info_coppia[(i, j)] = (bloccata[k], punteggio[k])

    for perm in itertools.permutations(range(n_membri)):
        if misura:
            _incrementa_contatore(contatori, "orientamenti_generati")
        if gruppo_ha_fisso and getattr(membri[perm[0]], 'nota_posizione', 'NORMALE') != 'FISSO':
            continue
        # Una fila e la sua immagine speculare hanno le stesse adiacenze.
        if OTTIMIZZA_SPECCHIATE and not gruppo_ha_fisso and n_membri > 1:
            if perm[0] > perm[-1]:
                continue
        if misura:
            _incrementa_contatore(contatori, "orientamenti_valutati")
        somma = 0
        ammissibile = True
        for posizione in range(n_membri - 1):
            a = perm[posizione]
            b = perm[posizione + 1]
            blocc, punt = info_coppia[(a, b) if a < b else (b, a)]
            if blocc:
                ammissibile = False
                break
            somma += punt

        if not ammissibile:
            continue

        if miglior_punteggio is None or somma > miglior_punteggio:
            miglior_punteggio = somma
            miglior_ordine = [membri[i] for i in perm]

    if miglior_ordine is None:
        return None
    # La penalità di fila non cambia l'ordine, ma il valore del gruppo.
    return (miglior_ordine, miglior_punteggio - _penalita_prima_ultima(miglior_ordine))


# ---------------------------------------------------------------------------
# Indice dei terzetti ammissibili
# ---------------------------------------------------------------------------
def _genera_terzetti_ammissibili(studenti, punteggio, bloccata, contatori=None):
    """Indicizza per studente i terzetti ammissibili.

    Ogni combinazione viene ordinata da ``valuta_gruppo`` e inserita nelle
    liste dei suoi tre membri. Le liste sono ordinate per punteggio decrescente
    e alimentano il backtracking ancorato.
    """
    terzetti_per_studente = {id(s): [] for s in studenti}

    misura = contatori is not None
    for combinazione in itertools.combinations(studenti, 3):
        if misura:
            _incrementa_contatore(contatori, "terne_considerate")
        valutazione = valuta_gruppo(
            list(combinazione), punteggio, bloccata, contatori=contatori
        )
        if valutazione is None:
            continue
        membri_ordinati, punti = valutazione
        if misura:
            _incrementa_contatore(contatori, "terne_ammissibili")
        voce = (membri_ordinati, punti)
        for studente in combinazione:
            terzetti_per_studente[id(studente)].append(voce)

    for chiave in terzetti_per_studente:
        terzetti_per_studente[chiave].sort(key=lambda voce: voce[1], reverse=True)

    return terzetti_per_studente


# ---------------------------------------------------------------------------
# Backtracking della partizione
# ---------------------------------------------------------------------------
def _gruppo_richiede_prima_fila(membri):
    """True se il gruppo deve occupare fisicamente la prima fila."""
    return any(
        getattr(membro, 'nota_posizione', 'NORMALE') in ('PRIMA', 'FISSO')
        for membro in membri
    )


def _backtrack(disponibili, disponibili_id, terzetti_per_studente,
               tipo_resto, dim_resto, punteggio, bloccata,
               resto_vietato_prima=False, contatore_nodi=None,
               max_terzetti_prima_fila=None,
               max_resti_prima_fila=None,
               terzetti_frontali_usati=0,
               riservati_resto_id=None,
               profondita=0, telemetria=None, stati_falliti=None):
    """Partiziona ricorsivamente gli studenti in terzetti e resto.

    A ogni livello prova i terzetti del primo studente libero. Quando rimangono
    esattamente 0, 2, 4 o 8 studenti, chiude il blocco finale. Restituisce la
    lista completa di ``Gruppo`` oppure ``None``.

    ``disponibili_id`` accelera i controlli di appartenenza; ``contatore_nodi``
    applica il limite alla ricerca. I parametri di capienza garantiscono che i
    gruppi con PRIMA o FISSO trovino posto nei blocchi frontali disponibili.
    """
    if riservati_resto_id is None:
        riservati_resto_id = set()

    # Memo locale alla singola ricerca: conserva soltanto stati completamente
    # esplorati senza soluzione. La chiave include gli studenti rimasti e gli
    # slot frontali già consumati; tutti gli altri parametri sono costanti
    # nell'invocazione radice. Non si memorizza mai dopo il tetto nodi.
    chiave_stato = None
    if stati_falliti is not None:
        chiave_stato = (frozenset(disponibili_id), terzetti_frontali_usati)
        if chiave_stato in stati_falliti:
            if telemetria is not None:
                telemetria.potatura("memo_stato_fallito")
                telemetria.incrementa("memo_hit")
            return None

    # Il contatore è condiviso da tutte le chiamate della stessa ricerca.
    if contatore_nodi is not None:
        contatore_nodi[0] += 1
        if telemetria is not None:
            telemetria.nodo(profondita)
        if contatore_nodi[0] > LIMITE_NODI_BACKTRACK:
            if telemetria is not None:
                telemetria.potatura("tetto_nodi")
            return None

    # Terzetti e resto consumano blocchi frontali distinti.
    if max_terzetti_prima_fila is not None:
        slot_terzetti_rimanenti = (
            max_terzetti_prima_fila - terzetti_frontali_usati
        )
        if slot_terzetti_rimanenti < 0:
            if telemetria is not None:
                telemetria.potatura("capienza_terzetti_negativa")
            return None

        richieste_frontali_rimanenti = sum(
            1
            for studente in disponibili
            if getattr(
                studente,
                'nota_posizione',
                'NORMALE'
            ) in ('PRIMA', 'FISSO')
        )

        # Le richieste non assorbite dal resto devono entrare nei terzetti.
        slot_resto_frontali = max_resti_prima_fila or 0
        if dim_resto == 8:
            posti_frontali_resto = 4 * min(slot_resto_frontali, 2)
        elif dim_resto in (2, 4):
            posti_frontali_resto = (
                dim_resto if slot_resto_frontali >= 1 else 0
            )
        else:
            posti_frontali_resto = 0

        capacita_frontale_residua = (
            posti_frontali_resto
            + 3 * slot_terzetti_rimanenti
        )

        if richieste_frontali_rimanenti > capacita_frontale_residua:
            if telemetria is not None:
                telemetria.potatura("capienza_frontale_insufficiente")
            return None

    # Caso base: rimangono soltanto gli studenti del blocco finale.
    if len(disponibili) == dim_resto:
        if dim_resto == 0:
            return []

        # Senza capienza esatta, il booleano equivale a 0 o 1 blocchi-resto.
        if max_resti_prima_fila is None:
            max_resti_effettivi = 0 if resto_vietato_prima else 1
        else:
            max_resti_effettivi = max_resti_prima_fila

        if dim_resto == 8:
            # Divide gli otto studenti in due quartetti. Ancorare il primo
            # studente nel primo quartetto evita di valutare due volte la stessa
            # spartizione: restano 35 combinazioni distinte.
            ancora8 = disponibili[0]
            altri = disponibili[1:]
            migliore = None
            for combo in itertools.combinations(altri, 3):
                if telemetria is not None:
                    telemetria.incrementa("partizioni_due_quartetti")
                id_combo = {id(s) for s in combo}
                primo = [ancora8] + list(combo)
                secondo = [s for s in altri if id(s) not in id_combo]
                val1 = valuta_gruppo(
                    primo, punteggio, bloccata, contatori=telemetria
                )
                if val1 is None:
                    continue
                val2 = valuta_gruppo(
                    secondo, punteggio, bloccata, contatori=telemetria
                )
                if val2 is None:
                    continue
                membri1, punti1 = val1
                membri2, punti2 = val2

                resti_frontali_necessari = sum((
                    1 if _gruppo_richiede_prima_fila(membri1) else 0,
                    1 if _gruppo_richiede_prima_fila(membri2) else 0,
                ))
                if resti_frontali_necessari > max_resti_effettivi:
                    continue

                punti_tot = punti1 + punti2
                # Il confronto stretto conserva il determinismo a parità.
                if migliore is None or punti_tot > migliore[0]:
                    migliore = (punti_tot, membri1, membri2)
            if migliore is None:
                return None
            _punti_tot, membri1, membri2 = migliore
            gruppi_resto = [
                Gruppo(TIPO_QUARTETTO, membri1),
                Gruppo(TIPO_QUARTETTO, membri2),
            ]
            gruppi_resto.sort(
                key=lambda gruppo: (
                    0 if any(
                        getattr(m, 'nota_posizione', 'NORMALE') == 'FISSO'
                        for m in gruppo.membri
                    ) else 1 if any(
                        getattr(m, 'nota_posizione', 'NORMALE') == 'PRIMA'
                        for m in gruppo.membri
                    ) else 2
                )
            )
            return gruppi_resto

        valutazione = valuta_gruppo(
            disponibili, punteggio, bloccata, contatori=telemetria
        )
        if valutazione is None:
            return None
        membri_ordinati, _punti = valutazione

        if (
            _gruppo_richiede_prima_fila(membri_ordinati)
            and max_resti_effettivi < 1
        ):
            return None

        return [Gruppo(tipo_resto, membri_ordinati)]

    # Ancorare il primo libero evita permutazioni della stessa partizione.
    ancora = disponibili[0]

    for membri_ordinati, _punti in terzetti_per_studente[id(ancora)]:
        if not all(id(m) in disponibili_id for m in membri_ordinati):
            if telemetria is not None:
                telemetria.potatura("membri_non_disponibili")
            continue

        # I PRIMA prenotati per il resto non possono entrare nel terzetto.
        if any(id(m) in riservati_resto_id for m in membri_ordinati):
            if telemetria is not None:
                telemetria.potatura("studente_riservato_resto")
            continue

        richiede_prima_fila = _gruppo_richiede_prima_fila(
            membri_ordinati
        )
        nuovi_terzetti_frontali_usati = (
            terzetti_frontali_usati
            + (1 if richiede_prima_fila else 0)
        )

        if (
            max_terzetti_prima_fila is not None
            and nuovi_terzetti_frontali_usati
            > max_terzetti_prima_fila
        ):
            if telemetria is not None:
                telemetria.potatura("terzetto_oltre_capienza_frontale")
            continue

        if telemetria is not None:
            telemetria.decisione(
                "terzetto",
                tuple(nome_completo(membro) for membro in membri_ordinati),
                profondita,
            )

        usati = {id(m) for m in membri_ordinati}
        nuovi_disponibili = [s for s in disponibili if id(s) not in usati]
        nuovi_disponibili_id = disponibili_id - usati

        risultato = _backtrack(
            nuovi_disponibili, nuovi_disponibili_id, terzetti_per_studente,
            tipo_resto, dim_resto, punteggio, bloccata,
            resto_vietato_prima=resto_vietato_prima,
            contatore_nodi=contatore_nodi,
            max_terzetti_prima_fila=max_terzetti_prima_fila,
            max_resti_prima_fila=max_resti_prima_fila,
            terzetti_frontali_usati=nuovi_terzetti_frontali_usati,
            riservati_resto_id=riservati_resto_id,
            profondita=profondita + 1,
            telemetria=telemetria,
            stati_falliti=stati_falliti,
        )

        if risultato is not None:
            return [Gruppo(TIPO_TERZETTO, membri_ordinati)] + risultato

        if telemetria is not None:
            telemetria.backtrack()

    # Nessun terzetto dell'ancora completa la partizione. Memorizza soltanto
    # se la ricerca di questo ramo è stata completa: dopo il tetto nodi, None
    # significa "non concluso" e non è una prova di impossibilità.
    if (
        stati_falliti is not None
        and chiave_stato is not None
        and (contatore_nodi is None or contatore_nodi[0] <= LIMITE_NODI_BACKTRACK)
    ):
        stati_falliti.add(chiave_stato)
        if telemetria is not None:
            telemetria.incrementa("memo_store")
    return None


# ---------------------------------------------------------------------------
# Cascata dei tentativi
# ---------------------------------------------------------------------------
def _indice_volte_blacklist(config_app):
    """Indicizza i riusi della blacklist dei terzetti.

    Usa la stessa chiave dello strato storico, ignora le voci malformate e
    conserva la prima occorrenza in caso di duplicati.
    """
    indice = {}
    if config_app is None:
        return indice
    for voce in config_app.config_data.get(CHIAVE_BLACKLIST_PER_MODO["terzetti"], []):
        nomi = voce.get("studenti", [])
        if len(nomi) != 2:
            continue
        chiave = frozenset((nomi[0], nomi[1]))
        if chiave not in indice:
            indice[chiave] = voce.get("volte_usata", 1)
    return indice


def partiziona_in_gruppi(motore_vincoli, studenti,
                         tentativo_iniziale=1, solo_tentativo=None, seed=None,
                         config_app=None, preferenza_resto2='coppia',
                         resto_in_prima_fila=False,
                         max_terzetti_prima_fila=None,
                         max_resti_prima_fila=None,
                         diagnostica=None):
    """Suddivide gli studenti percorrendo la cascata dei tentativi 1–4.

    Con ``config_app`` applica la rotazione della modalità a terzetti: nei
    tentativi 1–3 le adiacenze già usate sono bloccate; nel quarto sono ammesse
    con penalità e le ripartenze casuali scelgono la soluzione migliore.

    ``preferenza_resto2`` sceglie fra coppia finale e due quartetti quando il
    numero di studenti ha resto 2. I parametri di capienza frontale impediscono
    che PRIMA o FISSO vengano collocati fuori dalla prima fila. Il vincolo PRIMA
    non viene mai rilassato.

    ``solo_tentativo`` limita la ricerca a un singolo tentativo. ``seed`` rende
    riproducibile la parte casuale. Restituisce una lista di ``Gruppo`` oppure
    ``None`` quando nessuna partizione valida è disponibile.
    """
    diagnostica = diagnostica or getattr(motore_vincoli, "diagnostica", None)
    if diagnostica is not None:
        motore_vincoli.diagnostica = diagnostica

    # L'ordine delle righe del file classe non ha significato semantico.
    studenti = sorted(studenti, key=chiave_ordinamento_studente)

    # Ogni candidato usa un generatore locale, senza modificare random globale.
    seed_candidato = risolvi_seed_principale(seed)
    motore_vincoli.seed_candidato = seed_candidato
    motore_vincoli.ripartenza_vincente = None
    motore_vincoli.seed_ripartenza_vincente = None
    motore_vincoli.ripartenze_eseguite = 0

    # Penalità e blocco leggono la stessa blacklist riservata ai terzetti.
    if config_app is not None:
        applica_penalita_storico(motore_vincoli, config_app, modo="terzetti")
    volte_blacklist = _indice_volte_blacklist(config_app)

    piano = pianifica_resto(len(studenti), preferenza_resto2)
    if piano is None:
        return None
    _num_terzetti, tipo_resto, dim_resto = piano

    # In assenza della capienza esatta, il booleano viene convertito in 0 o 1.
    if max_resti_prima_fila is None:
        max_resti_prima_fila = (
            1 if resto_in_prima_fila and dim_resto > 0 else 0
        )

    # Se il resto non è frontale, non può contenere studenti PRIMA.
    resto_vietato_prima = (
        dim_resto > 0
        and not resto_in_prima_fila
        and any(getattr(s, 'nota_posizione', 'NORMALE') == 'PRIMA'
                for s in studenti)
    )

    # L'ordine delle righe del file classe non ha significato semantico.
    # Canonicalizza prima la classe; il FISSO viene poi ancorato per primo.
    studenti_ordinati = list(studenti)
    idx_fisso = next((i for i, s in enumerate(studenti_ordinati)
                      if getattr(s, 'nota_posizione', 'NORMALE') == 'FISSO'), None)
    if idx_fisso is not None and idx_fisso != 0:
        studenti_ordinati.insert(0, studenti_ordinati.pop(idx_fisso))

    # Quando il resto è frontale, alcune richieste PRIMA possono dovervi essere
    # prenotate prima del backtracking.
    riserve_prima_resto = [set()]

    if max_terzetti_prima_fila is not None and dim_resto > 0:
        if dim_resto == 8:
            posti_prima_nel_resto = 4 * min(max_resti_prima_fila, 2)
        elif dim_resto in (2, 4):
            posti_prima_nel_resto = (
                dim_resto if max_resti_prima_fila >= 1 else 0
            )
        else:
            posti_prima_nel_resto = 0

        studenti_prima = [
            studente
            for studente in studenti_ordinati
            if getattr(studente, 'nota_posizione', 'NORMALE') == 'PRIMA'
        ]
        richieste_frontali = sum(
            1
            for studente in studenti_ordinati
            if getattr(
                studente,
                'nota_posizione',
                'NORMALE'
            ) in ('PRIMA', 'FISSO')
        )

        capacita_terzetti_frontali = 3 * max_terzetti_prima_fila
        capacita_frontale_totale = (
            capacita_terzetti_frontali + posti_prima_nel_resto
        )

        if richieste_frontali > capacita_frontale_totale:
            return None

        # Se non è previsto alcun terzetto, il FISSO appartiene già al
        # blocco finale frontale. Non va quindi contato come uno studente PRIMA
        # da scegliere fra ``studenti_prima``.
        fisso_nel_resto = (
            _num_terzetti == 0
            and any(
                getattr(studente, 'nota_posizione', 'NORMALE') == 'FISSO'
                for studente in studenti_ordinati
            )
        )
        minimo_prima_nel_resto = max(
            0,
            richieste_frontali
            - capacita_terzetti_frontali
            - (1 if fisso_nel_resto else 0)
        )
        massimo_prima_nel_resto = min(
            len(studenti_prima),
            posti_prima_nel_resto,
            dim_resto,
        )

        if minimo_prima_nel_resto > massimo_prima_nel_resto:
            return None

        riserve_prima_resto = []
        for quanti in range(
                minimo_prima_nel_resto,
                massimo_prima_nel_resto + 1):
            for combinazione in itertools.combinations(
                    studenti_prima,
                    quanti):
                riserve_prima_resto.append({
                    id(studente)
                    for studente in combinazione
                })

        if not riserve_prima_resto:
            riserve_prima_resto = [set()]

    if diagnostica is not None:
        diagnostica.evento(
            "riserve_prima",
            modalita="terzetti",
            seed_candidato=seed_candidato,
            numero_riserve=len(riserve_prima_resto),
            dimensioni=sorted(len(riserva) for riserva in riserve_prima_resto),
            tipo_resto=tipo_resto,
            dimensione_resto=dim_resto,
        )

    if solo_tentativo is not None:
        tentativi = [solo_tentativo]
    else:
        tentativi = list(range(max(1, tentativo_iniziale), 5))

    # T1–T3 condividono lo stesso insieme di adiacenze ammissibili. Se T1
    # esaurisce tutte le riserve senza raggiungere il tetto dei nodi, T2 e T3
    # possono cambiare soltanto l'ordine di visita, non l'esistenza di una
    # soluzione. In quel solo caso si passa direttamente a T4.
    salta_t2_t3 = False

    for tentativo in tentativi:
        if salta_t2_t3 and tentativo in (2, 3):
            if diagnostica is not None:
                diagnostica.evento(
                    "tentativo_saltato",
                    modalita="terzetti",
                    tentativo=tentativo,
                    causa="T1_esaurito_senza_tetto",
                    seed_candidato=seed_candidato,
                )
            continue

        tentativo_ha_tetto = False
        inizio_tentativo_ns = perf_counter_ns()
        if diagnostica is not None:
            diagnostica.evento(
                "tentativo_inizio",
                modalita="terzetti",
                tentativo=tentativo,
                seed_candidato=seed_candidato,
            )

        motore_vincoli.configura_per_tentativo(tentativo)

        # Nei primi tre tentativi i riusi sono bloccati; nel quarto sono
        # soltanto penalizzati.
        blacklist_blocca = (tentativo <= 3)
        contatori_preparazione = Counter() if diagnostica is not None else None
        inizio_preparazione_ns = perf_counter_ns()

        punteggio, bloccata = calcola_punteggi_coppie(
            motore_vincoli, studenti,
            volte_blacklist=volte_blacklist,
            blacklist_blocca=blacklist_blocca,
            contatori=contatori_preparazione,
        )
        terzetti_per_studente = _genera_terzetti_ammissibili(
            studenti, punteggio, bloccata,
            contatori=contatori_preparazione,
        )

        if diagnostica is not None:
            diagnostica.evento(
                "preparazione_tentativo",
                modalita="terzetti",
                tentativo=tentativo,
                durata_ns=perf_counter_ns() - inizio_preparazione_ns,
                contatori=dict(contatori_preparazione),
                alternative_per_ancora={
                    nome_completo(studente): len(
                        terzetti_per_studente[id(studente)]
                    )
                    for studente in studenti
                },
            )

        if tentativo < 4:
            # I tentativi 1–3 provano le riserve frontali in ordine deterministico.
            # Una riserva è soltanto un artificio di ricerca: non deve imporre
            # una soluzione più sporca quando una riserva successiva elimina
            # del tutto le incompatibilità. Conserva quindi la migliore chiave
            # osservata e termina appena raggiunge (riusi=0, incompatibilità=0).
            migliore_soluzione_riserve = None
            migliore_chiave_riserve = None
            adiacenze_gia_usate = set(volte_blacklist)
            for indice_riserva, riserva_resto in enumerate(
                    riserve_prima_resto, start=1):
                disponibili = [
                    studente
                    for studente in studenti_ordinati
                    if id(studente) not in riserva_resto
                ] + [
                    studente
                    for studente in studenti_ordinati
                    if id(studente) in riserva_resto
                ]
                disponibili_id = {id(s) for s in disponibili}
                contatore_nodi = [0]
                telemetria = None
                if diagnostica is not None:
                    telemetria = diagnostica.nuova_ricerca(
                        firma_ordine=firma_indice_terzetti(
                            terzetti_per_studente, studenti
                        ),
                        modalita="terzetti",
                        tentativo=tentativo,
                        seed_candidato=seed_candidato,
                        ripartenza=None,
                        riserva=indice_riserva,
                        riservati=[
                            nome_completo(studente)
                            for studente in studenti
                            if id(studente) in riserva_resto
                        ],
                        tipo_resto=tipo_resto,
                        dimensione_resto=dim_resto,
                    )

                stati_falliti = set()
                soluzione = _backtrack(
                    disponibili, disponibili_id, terzetti_per_studente,
                    tipo_resto, dim_resto, punteggio, bloccata,
                    resto_vietato_prima=resto_vietato_prima,
                    contatore_nodi=contatore_nodi,
                    max_terzetti_prima_fila=max_terzetti_prima_fila,
                    max_resti_prima_fila=max_resti_prima_fila,
                    terzetti_frontali_usati=0,
                    riservati_resto_id=riserva_resto,
                    profondita=0,
                    telemetria=telemetria,
                    stati_falliti=stati_falliti,
                )
                ha_tetto = contatore_nodi[0] > LIMITE_NODI_BACKTRACK
                tentativo_ha_tetto = tentativo_ha_tetto or ha_tetto
                if telemetria is not None:
                    telemetria.finalizza(
                        successo=soluzione is not None,
                        soluzione=_rappresenta_partizione(soluzione),
                        punteggio=(
                            _punteggio_partizione(soluzione, punteggio)
                            if soluzione is not None else None
                        ),
                        tetto_nodi=ha_tetto,
                        dati={"nodi_contatore_storico": contatore_nodi[0]},
                    )
                if soluzione is not None:
                    chiave_soluzione = chiave_pulizia_terzetti(
                        soluzione, adiacenze_gia_usate
                    )
                    if (
                        migliore_chiave_riserve is None
                        or chiave_soluzione < migliore_chiave_riserve
                    ):
                        migliore_chiave_riserve = chiave_soluzione
                        migliore_soluzione_riserve = soluzione
                    if chiave_soluzione[0] == 0 and chiave_soluzione[1] == 0:
                        if diagnostica is not None:
                            diagnostica.evento(
                                "tentativo_fine",
                                modalita="terzetti",
                                tentativo=tentativo,
                                successo=True,
                                durata_ns=(perf_counter_ns() - inizio_tentativo_ns),
                                riserva_vincente=indice_riserva,
                                chiave=chiave_soluzione,
                            )
                        return soluzione

            if migliore_soluzione_riserve is not None:
                motore_vincoli.tetto_nodi_scattato = bool(tentativo_ha_tetto)
                if diagnostica is not None:
                    diagnostica.evento(
                        "tentativo_fine",
                        modalita="terzetti", tentativo=tentativo, successo=True,
                        durata_ns=perf_counter_ns() - inizio_tentativo_ns,
                        chiave=migliore_chiave_riserve,
                    )
                return migliore_soluzione_riserve

            motore_vincoli.tetto_nodi_scattato = bool(tentativo_ha_tetto)
            if diagnostica is not None:
                diagnostica.evento(
                    "tentativo_fine",
                    modalita="terzetti",
                    tentativo=tentativo,
                    successo=False,
                    durata_ns=perf_counter_ns() - inizio_tentativo_ns,
                    tetto_nodi=bool(tentativo_ha_tetto),
                )
            if tentativo == 1 and not tentativo_ha_tetto:
                salta_t2_t3 = True

        else:
            # Il quarto tentativo diversifica secondo la strategia selezionata.
            migliore_soluzione = None
            migliore_punteggio = None
            strategia = strategia_corrente()
            chiavi_strette = (
                precalcola_chiavi_strette_terzetti(
                    terzetti_per_studente, volte_blacklist
                )
                if strategia in ("B2", "B3", "B4") else None
            )

            for indice_ripartenza in range(NUM_RIPARTENZE_TENTATIVO_4):
                numero_ripartenza = indice_ripartenza + 1
                seed_ripartenza = deriva_seed(
                    seed_candidato,
                    "terzetti",
                    "ripartenza", numero_ripartenza,
                )
                rng = crea_generatore(seed_ripartenza)
                motore_vincoli.ripartenze_eseguite = numero_ripartenza

                indice_mescolato = diversifica_indice_terzetti(
                    terzetti_per_studente,
                    rng=rng,
                    ripartenza=numero_ripartenza,
                    frequenze=volte_blacklist,
                    strategia=strategia,
                    contesto=seed_candidato,
                    chiavi_strette=chiavi_strette,
                )

                for indice_riserva, riserva_resto in enumerate(
                        riserve_prima_resto, start=1):
                    disponibili = [
                        studente
                        for studente in studenti_ordinati
                        if id(studente) not in riserva_resto
                    ] + [
                        studente
                        for studente in studenti_ordinati
                        if id(studente) in riserva_resto
                    ]
                    disponibili_id = {id(s) for s in disponibili}
                    contatore_nodi = [0]
                    telemetria = None
                    if diagnostica is not None:
                        telemetria = diagnostica.nuova_ricerca(
                            firma_ordine=firma_indice_terzetti(
                                indice_mescolato, studenti
                            ),
                            modalita="terzetti",
                            tentativo=tentativo,
                            strategia_ricerca=strategia,
                            seed_candidato=seed_candidato,
                            ripartenza=numero_ripartenza,
                            seed_ripartenza=seed_ripartenza,
                            riserva=indice_riserva,
                            riservati=[
                                nome_completo(studente)
                                for studente in studenti
                                if id(studente) in riserva_resto
                            ],
                            tipo_resto=tipo_resto,
                            dimensione_resto=dim_resto,
                        )

                    stati_falliti = set()
                    soluzione = _backtrack(
                        disponibili, disponibili_id, indice_mescolato,
                        tipo_resto, dim_resto, punteggio, bloccata,
                        resto_vietato_prima=resto_vietato_prima,
                        contatore_nodi=contatore_nodi,
                        max_terzetti_prima_fila=max_terzetti_prima_fila,
                        max_resti_prima_fila=max_resti_prima_fila,
                        terzetti_frontali_usati=0,
                        riservati_resto_id=riserva_resto,
                        profondita=0,
                        telemetria=telemetria,
                        stati_falliti=stati_falliti,
                    )
                    ha_tetto = contatore_nodi[0] > LIMITE_NODI_BACKTRACK
                    tentativo_ha_tetto = tentativo_ha_tetto or ha_tetto
                    punti_totali = (
                        _punteggio_partizione(soluzione, punteggio)
                        if soluzione is not None else None
                    )
                    if telemetria is not None:
                        telemetria.finalizza(
                            successo=soluzione is not None,
                            soluzione=_rappresenta_partizione(soluzione),
                            punteggio=punti_totali,
                            tetto_nodi=ha_tetto,
                            dati={
                                "nodi_contatore_storico": contatore_nodi[0]
                            },
                        )
                    if soluzione is None:
                        continue

                    if (
                        migliore_punteggio is None
                        or punti_totali > migliore_punteggio
                    ):
                        migliore_punteggio = punti_totali
                        migliore_soluzione = soluzione
                        motore_vincoli.ripartenza_vincente = numero_ripartenza
                        motore_vincoli.seed_ripartenza_vincente = seed_ripartenza

            motore_vincoli.tetto_nodi_scattato = bool(tentativo_ha_tetto)
            if diagnostica is not None:
                diagnostica.evento(
                    "tentativo_fine",
                    modalita="terzetti",
                    tentativo=tentativo,
                    successo=migliore_soluzione is not None,
                    durata_ns=perf_counter_ns() - inizio_tentativo_ns,
                    ripartenza_vincente=getattr(
                        motore_vincoli, "ripartenza_vincente", None
                    ),
                    punteggio_vincente=migliore_punteggio,
                )
            if migliore_soluzione is not None:
                return migliore_soluzione

    # PRIMA resta assoluto: una capienza frontale insufficiente produce None.
    return None



def _incompatibilita_assolute_terzetti(studenti):
    """Restituisce le incompatibilità assolute senza duplicare le coppie."""
    viste = set()
    risultato = []
    for indice, studente in enumerate(studenti):
        for altro in studenti[indice + 1:]:
            if livello_incompatibilita(studente, altro) != 3:
                continue
            nomi = tuple(sorted((
                nome_completo(studente),
                nome_completo(altro),
            )))
            if nomi in viste:
                continue
            viste.add(nomi)
            risultato.append(f"{nomi[0]}  ↔  {nomi[1]}")
    return risultato


def costruisci_report_fallimento_terzetti(
        studenti, *, genere_misto=False, config_app=None,
        preferenza_resto2='coppia', resto_in_prima_fila=False,
        max_terzetti_prima_fila=None, max_resti_prima_fila=None,
        metadati_casualita=None):
    """Spiega un fallimento a terzetti senza trasformare indizi in certezze."""
    studenti = list(studenti)
    metadati_casualita = dict(metadati_casualita or {})
    incompatibilita = _incompatibilita_assolute_terzetti(studenti)
    piano = pianifica_resto(len(studenti), preferenza_resto2)

    studenti_prima = [
        studente
        for studente in studenti
        if getattr(studente, 'nota_posizione', 'NORMALE') == 'PRIMA'
    ]
    studenti_fissi = [
        studente
        for studente in studenti
        if getattr(studente, 'nota_posizione', 'NORMALE') == 'FISSO'
    ]

    capacita_frontale = None
    posti_prima_utilizzabili = None
    distribuzione_frontale_impossibile = False
    if piano is not None and max_terzetti_prima_fila is not None:
        num_terzetti, _tipo_resto, dim_resto = piano
        max_resti = int(max_resti_prima_fila or 0)
        if dim_resto == 8:
            posti_resto_frontali = 4 * min(max_resti, 2)
        elif dim_resto in (2, 4):
            posti_resto_frontali = dim_resto if max_resti >= 1 else 0
        else:
            posti_resto_frontali = 0

        capacita_terzetti = 3 * max_terzetti_prima_fila
        capacita_frontale = capacita_terzetti + posti_resto_frontali
        posti_prima_utilizzabili = max(
            0,
            capacita_frontale - len(studenti_fissi),
        )

        fisso_nel_resto = bool(num_terzetti == 0 and studenti_fissi)
        minimo_prima_nel_resto = max(
            0,
            len(studenti_prima) + len(studenti_fissi)
            - capacita_terzetti
            - (1 if fisso_nel_resto else 0),
        )
        massimo_prima_nel_resto = min(
            len(studenti_prima),
            posti_resto_frontali,
            dim_resto,
        )
        distribuzione_frontale_impossibile = (
            minimo_prima_nel_resto > massimo_prima_nel_resto
        )

    fisso = studenti_fissi[0] if studenti_fissi else None
    possibili_vicini_fisso = (
        [
            nome_completo(altro)
            for altro in studenti
            if (
                altro is not fisso
                and livello_incompatibilita(fisso, altro) != 3
            )
        ]
        if fisso is not None
        else []
    )

    senza_vicino = []
    for studente in studenti:
        if studente is fisso:
            continue
        altri = [altro for altro in studenti if altro is not studente]
        if altri and all(
            livello_incompatibilita(studente, altro) == 3
            for altro in altri
        ):
            senza_vicino.append(nome_completo(studente))

    cause_certe = []
    suggerimenti = []

    if piano is None:
        cause_certe.append(
            "Il numero di studenti non consente di formare alcun blocco "
            "valido nella modalità a terzetti."
        )
        suggerimenti.append(
            "Controlla la classe caricata: la modalità a terzetti richiede "
            "almeno due studenti."
        )

    if len(studenti_fissi) > 1:
        cause_certe.append(
            f"La classe contiene {quantita(len(studenti_fissi), 'studente FISSO', 'studenti FISSO')}, "
            "ma la disposizione ne ammette uno soltanto."
        )
        suggerimenti.append(
            "Nell'Editor studenti lascia la posizione FISSO a un solo studente."
        )

    capienza_prima_impossibile = (
        posti_prima_utilizzabili is not None
        and len(studenti_prima) > posti_prima_utilizzabili
    )
    if capienza_prima_impossibile:
        eccesso = len(studenti_prima) - posti_prima_utilizzabili
        cause_certe.append(
            f"Dopo avere riservato il posto del FISSO, la prima fila offre "
            f"{quantita(posti_prima_utilizzabili, 'posto utilizzabile', 'posti utilizzabili')} "
            f"per {quantita(len(studenti_prima), 'studente con posizione PRIMA', 'studenti con posizione PRIMA')}: "
            f"{quantita(eccesso, 'richiesta non collocabile', 'richieste non collocabili')}."
        )
        suggerimenti.append(
            "Riduci le posizioni PRIMA oppure aumenta la capienza frontale "
            "della configurazione a terzetti."
        )
    elif distribuzione_frontale_impossibile:
        cause_certe.append(
            "La capienza frontale complessiva è sufficiente, ma la sua "
            "suddivisione fra terzetti e blocco finale non consente di "
            "collocare tutte le posizioni PRIMA."
        )
        suggerimenti.append(
            "Modifica la posizione del blocco finale oppure riduci le "
            "posizioni PRIMA."
        )

    if fisso is not None and not possibili_vicini_fisso:
        cause_certe.append(
            f"Nessuno studente può sedere accanto al FISSO "
            f"{nome_completo(fisso)} senza violare un'incompatibilità "
            "di livello 3."
        )
        suggerimenti.append(
            "Nell'Editor studenti lascia almeno un possibile vicino "
            "compatibile per lo studente FISSO."
        )

    if senza_vicino:
        if len(senza_vicino) == 1:
            causa = (
                "Il seguente studente è incompatibile al livello 3 con ogni "
                "possibile vicino: "
            )
        else:
            causa = (
                "I seguenti studenti sono incompatibili al livello 3 con "
                "ogni possibile vicino: "
            )
        cause_certe.append(causa + ", ".join(senza_vicino) + ".")
        suggerimenti.append(
            "Nell'Editor studenti lascia a ciascun allievo almeno un possibile "
            "vicino non incompatibile al livello 3."
        )

    ricerca_incompleta = bool(
        metadati_casualita.get("tetto_nodi_scattato", False)
    )
    if ricerca_incompleta:
        suggerimenti.append(
            "La ricerca ha raggiunto il limite di sicurezza: riprova una "
            "volta; se il problema persiste, semplifica alcuni vincoli assoluti."
        )

    if incompatibilita and not senza_vicino:
        suggerimenti.append(
            "Controlla le incompatibilità di livello 3: considerate nel loro "
            "insieme possono impedire la costruzione dei gruppi."
        )

    if not suggerimenti:
        suggerimenti.append(
            "Riprova l'assegnazione; se il fallimento si ripete, controlla "
            "incompatibilità di livello 3, posizioni PRIMA e blocco finale."
        )

    maschi = sum(getattr(studente, 'sesso', None) == 'M' for studente in studenti)
    femmine = sum(getattr(studente, 'sesso', None) == 'F' for studente in studenti)
    genere = None
    if genere_misto:
        genere = {
            "maschi": maschi,
            "femmine": femmine,
            "preferenza_soft": True,
            "sbilanciamento": abs(maschi - femmine) > 1,
        }

    numero_riusi = (
        len(snapshot_blacklist_terzetti(config_app))
        if config_app is not None
        else 0
    )
    return {
        "modalita": "terzetti",
        "casualita": metadati_casualita,
        "cause_certe": cause_certe,
        "ricerca_incompleta": ricerca_incompleta,
        "incompatibilita_assolute": incompatibilita,
        "studenti_prima_fila": [nome_completo(s) for s in studenti_prima],
        "prima_fila": {
            "studenti": [nome_completo(s) for s in studenti_prima],
            "richieste": len(studenti_prima),
            "posti_totali": capacita_frontale,
            "posti_utilizzabili": posti_prima_utilizzabili,
            "eccesso": (
                max(0, len(studenti_prima) - posti_prima_utilizzabili)
                if posti_prima_utilizzabili is not None else 0
            ),
            "impossibile_per_capienza": capienza_prima_impossibile,
            "impossibile_per_distribuzione": distribuzione_frontale_impossibile,
        },
        "studenti_senza_vicini_compatibili": senza_vicino,
        "gruppo_incompatibile_sovrabbondante": None,
        "fisso": {
            "presente": fisso is not None,
            "nome": nome_completo(fisso) if fisso is not None else None,
            "possibili_vicini": possibili_vicini_fisso,
            "nessun_vicino_lecito": bool(
                fisso is not None and not possibili_vicini_fisso
            ),
        },
        "capienza": {
            "studenti": len(studenti),
            "posti": len(studenti),
            "mancanti": 0,
        },
        "blacklist": {"coppie": numero_riusi, "piu_usate": []},
        "genere_misto": genere,
        "tetto_nodi_scattato": ricerca_incompleta,
        "suggerimenti": suggerimenti,
    }


# ---------------------------------------------------------------------------
# Selezione best-of-N del mese
# ---------------------------------------------------------------------------
def _metadati_casualita_terzetti(motore, seed_principale,
                                  seed_candidato, contesto,
                                  indice_candidato, successo):
    """Compone i metadati condivisi da GUI, Storico e diagnostica."""
    return {
        "seed_principale": seed_principale,
        "modalita": "terzetti",
        "contesto": {**dict(contesto or {}),
                     "candidato": indice_candidato},
        "seed_candidato": seed_candidato,
        "tentativo": getattr(motore, "tentativo_corrente", None),
        "ripartenza": getattr(motore, "ripartenza_vincente", None),
        "seed_ripartenza": getattr(
            motore, "seed_ripartenza_vincente", None
        ),
        "ripartenze_eseguite": getattr(
            motore, "ripartenze_eseguite", 0
        ),
        "successo": bool(successo),
        "tetto_nodi_scattato": bool(
            getattr(motore, "tetto_nodi_scattato", False)
        ),
    }


def calcola_miglior_mese_terzetti(studenti, genere_misto,
                                  config_app=None, preferenza_resto2='coppia',
                                  resto_in_prima_fila=False,
                                  max_terzetti_prima_fila=None,
                                  max_resti_prima_fila=None,
                                  num_candidati=1, seed_base=None,
                                  contesto_casuale=None,
                                  restituisci_metadati=False,
                                  diagnostica=None):
    """Genera più partizioni e restituisce quella con la chiave migliore.

    Il seed di ogni candidato deriva stabilmente dal seed principale, dal
    contesto e dall'indice. Con ``restituisci_metadati`` restituisce anche i
    dati necessari a diagnosi e riproduzione.
    """
    if config_app is not None:
        adiacenze_gia_usate = snapshot_blacklist_terzetti(config_app)
    else:
        adiacenze_gia_usate = set()
    frequenze_blacklist = _indice_volte_blacklist(config_app)

    seed_principale = risolvi_seed_principale(seed_base)
    contesto_casuale = dict(contesto_casuale or {})

    migliore_gruppi = None
    migliore_chiave = None
    migliori_metadati = None
    ultimi_metadati = None

    for indice_candidato_zero in range(max(1, num_candidati)):
        indice_candidato = indice_candidato_zero + 1
        motore = MotoreVincoliConfigurato(diagnostica=diagnostica)
        motore.imposta_genere_misto_obbligatorio(genere_misto)

        seed_candidato = deriva_seed(
            seed_principale,
            "modalita", "terzetti",
            "contesto", contesto_casuale,
            "candidato", indice_candidato,
        )

        inizio_candidato_ns = perf_counter_ns()
        if diagnostica is not None:
            diagnostica.evento(
                "candidato_inizio",
                modalita="terzetti",
                candidato=indice_candidato,
                seed_principale=seed_principale,
                seed_candidato=seed_candidato,
                contesto=contesto_casuale,
            )
            with diagnostica.attiva():
                gruppi = partiziona_in_gruppi(
                    motore, studenti,
                    seed=seed_candidato,
                    config_app=config_app,
                    preferenza_resto2=preferenza_resto2,
                    resto_in_prima_fila=resto_in_prima_fila,
                    max_terzetti_prima_fila=max_terzetti_prima_fila,
                    max_resti_prima_fila=max_resti_prima_fila,
                    diagnostica=diagnostica,
                )
            diagnostica.evento(
                "candidato_fine",
                modalita="terzetti",
                candidato=indice_candidato,
                seed_candidato=seed_candidato,
                successo=gruppi is not None,
                durata_ns=perf_counter_ns() - inizio_candidato_ns,
                tentativo=getattr(motore, "tentativo_corrente", None),
            )
        else:
            gruppi = partiziona_in_gruppi(
                motore, studenti,
                seed=seed_candidato,
                config_app=config_app,
                preferenza_resto2=preferenza_resto2,
                resto_in_prima_fila=resto_in_prima_fila,
                max_terzetti_prima_fila=max_terzetti_prima_fila,
                max_resti_prima_fila=max_resti_prima_fila,
            )

        metadati = _metadati_casualita_terzetti(
            motore, seed_principale, seed_candidato,
            contesto_casuale, indice_candidato, gruppi is not None
        )
        ultimi_metadati = metadati

        if gruppi is None:
            continue

        chiave = chiave_pulizia_terzetti(gruppi, adiacenze_gia_usate)
        if diagnostica is not None:
            frequenze_riuso = []
            for studente_a, studente_b in adiacenze_partizione(gruppi):
                chiave_nomi = frozenset((
                    nome_completo(studente_a), nome_completo(studente_b)
                ))
                utilizzi = frequenze_blacklist.get(chiave_nomi, 0)
                if utilizzi > 0:
                    frequenze_riuso.append(utilizzi)
            diagnostica.evento(
                "qualita_candidato",
                modalita="terzetti",
                candidato=indice_candidato,
                seed_candidato=seed_candidato,
                tentativo=getattr(motore, "tentativo_corrente", None),
                chiave=chiave,
                incompatibilita_per_livello=(
                    conta_incompatibilita_per_livello_terzetti(gruppi)
                ),
                affinita=conta_affinita_soddisfatte_terzetti(gruppi),
                frequenze_riuso=frequenze_riuso,
            )
        if migliore_chiave is None or chiave < migliore_chiave:
            migliore_chiave = chiave
            migliore_gruppi = gruppi
            migliori_metadati = metadati

        # I candidati successivi sarebbero identici nei tentativi deterministici.
        if getattr(motore, 'tentativo_corrente', 4) <= 3:
            break

    metadati_finali = migliori_metadati or ultimi_metadati or {
        "seed_principale": seed_principale,
        "modalita": "terzetti",
        "contesto": contesto_casuale,
        "successo": False,
    }

    messaggio_motore(
        f"🎲 Terzetti: seed principale={seed_principale}, "
        f"candidato={metadati_finali.get('contesto', {}).get('candidato')}, "
        f"tentativo={metadati_finali.get('tentativo')}, "
        f"ripartenza={metadati_finali.get('ripartenza')}"
    )

    if diagnostica is not None:
        diagnostica.evento(
            "best_of_n_fine",
            modalita="terzetti",
            successo=migliore_gruppi is not None,
            chiave_vincente=migliore_chiave,
            seed_candidato=metadati_finali.get("seed_candidato"),
            tentativo=metadati_finali.get("tentativo"),
            ripartenza=metadati_finali.get("ripartenza"),
        )

    if migliore_gruppi is None:
        metadati_finali["report_fallimento"] = (
            costruisci_report_fallimento_terzetti(
                studenti,
                genere_misto=genere_misto,
                config_app=config_app,
                preferenza_resto2=preferenza_resto2,
                resto_in_prima_fila=resto_in_prima_fila,
                max_terzetti_prima_fila=max_terzetti_prima_fila,
                max_resti_prima_fila=max_resti_prima_fila,
                metadati_casualita=metadati_finali,
            )
        )

    if restituisci_metadati:
        return migliore_gruppi, metadati_finali
    return migliore_gruppi

def _punteggio_partizione(gruppi, punteggio):
    """Somma i punteggi delle adiacenze di una partizione.

    Il quarto tentativo usa il totale per confrontare le ripartenze.
    """
    totale = 0
    for gruppo in gruppi:
        membri = gruppo.membri
        for posizione in range(len(membri) - 1):
            k = _chiave_coppia(membri[posizione], membri[posizione + 1])
            totale += punteggio[k]
        # Include la stessa penalità di fila usata nella valutazione dei gruppi.
        totale -= _penalita_prima_ultima(membri)
    return totale
