# -*- coding: utf-8 -*-
"""
metrica_pulizia.py — metriche condivise per confrontare assegnazioni e stagioni.

Parte di «PostiPerfetti».
Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3. Distribuito "così com'è", senza garanzie.

Il modulo misura, in ordine di priorità, le ripetizioni, le incompatibilità
tollerate e le affinità soddisfatte. Le funzioni restituiscono tuple ordinabili:
il valore più piccolo identifica il candidato o la stagione più pulita.

Non dipende dall'interfaccia grafica e legge direttamente i dati degli studenti,
così le modalità a coppie e a terzetti applicano gli stessi criteri.
"""

from collections import namedtuple


# Le incompatibilità di livello 2 pesano dieci volte quelle di livello 1.
# Il livello 3 è una guardia: il motore non dovrebbe mai collocarlo.
PESO_INCOMP_LIV1 = 1
PESO_INCOMP_LIV2 = 10
PESO_INCOMP_LIV3 = 1000


def nome_completo(studente):
    """Restituisce il nome completo di uno studente."""
    return studente.get_nome_completo()


def coppia_ordinata(nome_a, nome_b):
    """Restituisce due nomi in ordine alfabetico come tupla.

    In questo modo ``(A, B)`` e ``(B, A)`` rappresentano la stessa coppia.
    """
    return tuple(sorted((nome_a, nome_b)))


def livello_incompatibilita(studente_a, studente_b):
    """Restituisce il livello reale di incompatibilità fra due studenti.

    Legge i dati degli studenti, non i punteggi eventualmente rilassati dal
    motore, e usa il massimo delle due direzioni. Restituisce un valore da 0 a 3.
    """
    a_vs_b = studente_a.incompatibilita.get(nome_completo(studente_b), 0)
    b_vs_a = studente_b.incompatibilita.get(nome_completo(studente_a), 0)
    return max(a_vs_b, b_vs_a)


def livello_affinita(studente_a, studente_b):
    """Restituisce il livello reale di affinità fra due studenti.

    Legge entrambe le direzioni e ne usa il valore massimo; restituisce 0 quando
    non è dichiarata alcuna affinità.
    """
    a_vs_b = studente_a.affinita.get(nome_completo(studente_b), 0)
    b_vs_a = studente_b.affinita.get(nome_completo(studente_a), 0)
    return max(a_vs_b, b_vs_a)

# Tipi condivisi da motore, metrica, report e storico.
TIPO_COPPIA    = "coppia"
TIPO_TERZETTO  = "terzetto"
TIPO_QUARTETTO = "quartetto"


# I membri sono ordinati da sinistra a destra.
Gruppo = namedtuple("Gruppo", ["tipo", "membri"])


def adiacenze_in_fila(membri):
    """Restituisce le coppie consecutive di un gruppo disposto in fila.

    Per ``[A, B, C]`` produce ``[(A, B), (B, C)]``: gli estremi non sono
    adiacenti.
    """
    return [(membri[i], membri[i + 1]) for i in range(len(membri) - 1)]


def estrai_gruppi(assegnatore):
    """Ricostruisce i gruppi sociali di un'assegnazione a coppie.

    Comprende coppie normali, l'eventuale coppia collocata accanto al FISSO e il
    trio finale. Il FISSO non entra nei gruppi: la sua adiacenza diretta conta per
    la qualità, ma è gestita separatamente e non appartiene alla blacklist delle
    coppie.
    """
    gruppi = []

    # Coppie prodotte dal motore.
    for studente1, studente2, _info in assegnatore.coppie_formate:
        gruppi.append(Gruppo(TIPO_COPPIA, [studente1, studente2]))

    # La coppia accanto al FISSO vive fuori da coppie_formate.
    gruppo_fisso = getattr(assegnatore, 'gruppo_adiacente_fisso', None)
    if gruppo_fisso is not None:
        gruppi.append(Gruppo(TIPO_COPPIA, [gruppo_fisso[0], gruppo_fisso[1]]))

    # L'eventuale resto dispari costituisce un terzetto ordinato.
    trio = getattr(assegnatore, 'trio_identificato', None)
    if trio:
        gruppi.append(Gruppo(TIPO_TERZETTO, list(trio)))

    return gruppi


def estrai_adiacenze(assegnatore):
    """Restituisce tutte le adiacenze reali di un'assegnazione.

    Alle adiacenze consecutive dei gruppi aggiunge, quando presente, quella fra
    il FISSO e il suo vicino diretto.
    """
    adiacenze = []

    for gruppo in estrai_gruppi(assegnatore):
        adiacenze.extend(adiacenze_in_fila(gruppo.membri))

    # L'adiacenza FISSO-vicino incide sulla qualità, non sulla blacklist.
    fisso = getattr(assegnatore, 'studente_fisso', None)
    gruppo_fisso = getattr(assegnatore, 'gruppo_adiacente_fisso', None)
    if fisso is not None and gruppo_fisso is not None:
        adiacenze.append((fisso, gruppo_fisso[0]))

    return adiacenze


def coppie_per_blacklist(assegnatore):
    """Restituisce le coppie da registrare nella blacklist ordinaria.

    Include le adiacenze interne dei gruppi, ma non l'adiacenza FISSO-vicino,
    tracciata con un contatore dedicato.
    """
    coppie = set()
    for gruppo in estrai_gruppi(assegnatore):
        for studente_a, studente_b in adiacenze_in_fila(gruppo.membri):
            coppie.add(coppia_ordinata(nome_completo(studente_a),
                                       nome_completo(studente_b)))
    return coppie


def snapshot_blacklist(config_app):
    """Restituisce la fotografia corrente della blacklist delle coppie."""
    gia_usate = set()
    # Ogni voce valida contiene esattamente i due nomi della coppia.
    for voce in config_app.config_data.get("coppie_da_evitare", []):
        if voce.get("tipo") == "coppia":
            studenti = voce.get("studenti", [])
            if len(studenti) == 2:
                gia_usate.add(coppia_ordinata(studenti[0], studenti[1]))
    return gia_usate


def conta_incompatibilita_per_livello(assegnatore):
    """Conta le incompatibilità tollerate e restituisce ``{1: n1, 2: n2, 3: n3}``."""
    per_livello = {1: 0, 2: 0, 3: 0}
    for studente_a, studente_b in estrai_adiacenze(assegnatore):
        livello = livello_incompatibilita(studente_a, studente_b)
        if livello >= 1:
            per_livello[livello] += 1
    return per_livello


def peso_incompatibilita(per_livello):
    """Converte il conteggio per livello in un unico peso; più alto è peggio."""
    return (
        per_livello.get(1, 0) * PESO_INCOMP_LIV1 +
        per_livello.get(2, 0) * PESO_INCOMP_LIV2 +
        per_livello.get(3, 0) * PESO_INCOMP_LIV3
    )


def snapshot_vicini_fisso(config_app):
    """Restituisce i nomi già usati come vicini diretti del FISSO."""
    contatori = config_app.config_data.get(
        "studenti_vicino_fisso_contatore",
        {},
    )
    return {
        nome
        for nome, volte in contatori.items()
        if int(volte or 0) >= 1
    }


def conta_ripetizioni(
        assegnatore,
        coppie_gia_usate,
        vicini_fisso_gia_usati=None):
    """Conta le vicinanze già utilizzate presenti nel candidato.

    Somma le coppie della blacklist ordinaria e l'eventuale vicino diretto del
    FISSO già impiegato nello stesso ruolo.
    """
    coppie_ora = coppie_per_blacklist(assegnatore)
    ripetizioni = len(coppie_ora & coppie_gia_usate)

    nome_vicino = getattr(
        assegnatore,
        "nome_adiacente_fisso",
        None,
    )
    if (
        nome_vicino
        and vicini_fisso_gia_usati
        and nome_vicino in vicini_fisso_gia_usati
    ):
        ripetizioni += 1

    return ripetizioni


def conta_affinita_soddisfatte(assegnatore):
    """Conta le adiacenze con un'affinità dichiarata di livello almeno 1."""
    soddisfatte = 0
    for studente_a, studente_b in estrai_adiacenze(assegnatore):
        if livello_affinita(studente_a, studente_b) >= 1:
            soddisfatte += 1
    return soddisfatte


def chiave_pulizia(
        assegnatore,
        coppie_gia_usate,
        vicini_fisso_gia_usati=None):
    """Restituisce la chiave di qualità di un candidato a coppie.

    La tupla è ``(ripetizioni, incompatibilità_pesate, -affinità)``. Python la
    confronta da sinistra a destra: prima si minimizzano le ripetizioni, poi le
    incompatibilità tollerate; le affinità sono lo spareggio finale. Una tupla
    più piccola identifica un candidato più pulito.
    """
    per_livello = conta_incompatibilita_per_livello(assegnatore)
    incomp_pesate = peso_incompatibilita(per_livello)

    ripetizioni = conta_ripetizioni(
        assegnatore,
        coppie_gia_usate,
        vicini_fisso_gia_usati,
    )

    affinita = conta_affinita_soddisfatte(assegnatore)

    # Il segno meno trasforma "più affinità" in una chiave più piccola.
    return (ripetizioni, incomp_pesate, -affinita)

def adiacenze_partizione(gruppi):
    """Restituisce le adiacenze consecutive di tutti i gruppi della partizione.

    Nei terzetti il FISSO è un membro ordinario: anche le sue adiacenze
    consecutive partecipano alla blacklist.
    """
    adiacenze = []
    for gruppo in gruppi:
        adiacenze.extend(adiacenze_in_fila(gruppo.membri))
    return adiacenze


def adiacenze_per_blacklist_terzetti(gruppi):
    """Restituisce le adiacenze della partizione come coppie di nomi ordinati."""
    coppie = set()
    for studente_a, studente_b in adiacenze_partizione(gruppi):
        coppie.add(coppia_ordinata(nome_completo(studente_a),
                                   nome_completo(studente_b)))
    return coppie


def snapshot_blacklist_terzetti(config_app):
    """Restituisce la fotografia corrente della blacklist dei terzetti.

    La chiave della configurazione è scritta localmente per mantenere puro il
    modulo; la mappatura autorevole resta in ``strato_storico.py``.
    """
    gia_usate = set()
    # La struttura delle voci è analoga a quella della blacklist a coppie.
    for voce in config_app.config_data.get("adiacenze_terzetti_da_evitare", []):
        if voce.get("tipo") == "adiacenza":
            studenti = voce.get("studenti", [])
            if len(studenti) == 2:
                gia_usate.add(coppia_ordinata(studenti[0], studenti[1]))
    return gia_usate


def conta_incompatibilita_per_livello_terzetti(gruppi):
    """Conta per livello le incompatibilità delle adiacenze della partizione."""
    per_livello = {1: 0, 2: 0, 3: 0}
    for studente_a, studente_b in adiacenze_partizione(gruppi):
        livello = livello_incompatibilita(studente_a, studente_b)
        if livello >= 1:
            per_livello[livello] += 1
    return per_livello


def conta_ripetizioni_terzetti(gruppi, adiacenze_gia_usate):
    """Conta le adiacenze della partizione già presenti nella blacklist."""
    return len(adiacenze_per_blacklist_terzetti(gruppi) & adiacenze_gia_usate)


def conta_affinita_soddisfatte_terzetti(gruppi):
    """Conta le adiacenze della partizione con un'affinità dichiarata."""
    soddisfatte = 0
    for studente_a, studente_b in adiacenze_partizione(gruppi):
        if livello_affinita(studente_a, studente_b) >= 1:
            soddisfatte += 1
    return soddisfatte


def chiave_pulizia_terzetti(gruppi, adiacenze_gia_usate):
    """Restituisce la chiave di qualità di una partizione a terzetti.

    Usa la stessa struttura della modalità a coppie:
    ``(ripetizioni, incompatibilità_pesate, -affinità)``.
    """
    per_livello = conta_incompatibilita_per_livello_terzetti(gruppi)
    incomp_pesate = peso_incompatibilita(per_livello)

    ripetizioni = conta_ripetizioni_terzetti(gruppi, adiacenze_gia_usate)

    affinita = conta_affinita_soddisfatte_terzetti(gruppi)

    # Il segno meno trasforma "più affinità" in una chiave più piccola.
    return (ripetizioni, incomp_pesate, -affinita)


def punteggio_stagione(chiavi_turni):
    """Somma le chiavi dei turni in una chiave complessiva di stagione.

    Restituisce ``(totale_ripetizioni, totale_incompatibilità_pesate,
    -totale_affinità)``; una tupla più piccola identifica una stagione più
    pulita.
    Una sequenza vuota produce ``(0, 0, 0)``.
    """
    tot_rip = 0
    tot_incomp = 0
    tot_aff_negata = 0
    for chiave in chiavi_turni:
        tot_rip        += chiave[0]
        tot_incomp     += chiave[1]
        tot_aff_negata += chiave[2]
    return (tot_rip, tot_incomp, tot_aff_negata)


def riordina_stagione_per_pulizia(
        assegnazioni,
        blacklist_iniziale,
        vicini_fisso_iniziali=None):
    """Riordina assegnazioni già generate dalla più pulita alla meno pulita.

    A ogni posizione sceglie, fra le assegnazioni rimanenti, quella con la
    chiave migliore rispetto alla blacklist cumulata. Il riordino non modifica
    i gruppi: cambia soltanto il turno in cui una ripetizione viene conteggiata
    e aggiorna la fotografia della blacklist associata a ciascuna posizione.

    Restituisce tuple ``(indice_originale, assegnatore, chiave, foto_blacklist)``.
    La funzione è pura: non modifica gli assegnatori, la configurazione o lo stato
    casuale.
    """
    rimanenti = list(enumerate(assegnazioni))

    # La fotografia cresce soltanto dopo aver collocato ciascun turno.
    blacklist_cumulata = set(blacklist_iniziale)

    vicini_fisso_cumulati = set(
        vicini_fisso_iniziali or set()
    )

    risultato = []

    while rimanenti:
        migliore_pos = 0
        migliore_idx_orig, migliore_assegn = rimanenti[0]
        migliore_chiave = chiave_pulizia(
            migliore_assegn,
            blacklist_cumulata,
            vicini_fisso_cumulati,
        )

        for pos in range(1, len(rimanenti)):
            idx_orig_i, assegn_i = rimanenti[pos]
            chiave_i = chiave_pulizia(
                assegn_i,
                blacklist_cumulata,
                vicini_fisso_cumulati,
            )
            if chiave_i < migliore_chiave:
                migliore_pos = pos
                migliore_idx_orig = idx_orig_i
                migliore_assegn = assegn_i
                migliore_chiave = chiave_i

        rimanenti.pop(migliore_pos)
        # La foto precede l'assorbimento delle coppie del turno corrente.
        risultato.append((migliore_idx_orig, migliore_assegn, migliore_chiave,
                          set(blacklist_cumulata)))

        blacklist_cumulata |= coppie_per_blacklist(migliore_assegn)

        nome_vicino = getattr(
            migliore_assegn,
            "nome_adiacente_fisso",
            None,
        )
        if nome_vicino:
            vicini_fisso_cumulati.add(nome_vicino)

    return risultato


def riordina_stagione_per_pulizia_terzetti(mesi, blacklist_iniziale):
    """Riordina i mesi a terzetti dalla partizione più pulita alla meno pulita.

    Applica lo stesso criterio greedy della modalità a coppie. Ogni mese
    restituito è una copia superficiale con ``adiacenze_prima`` ricalcolato
    rispetto alla
    nuova posizione, così report e conteggi descrivono il nuovo ordine.

    Restituisce tuple ``(indice_originale, mese_aggiornato, chiave)`` senza
    modificare i dizionari ricevuti.
    """
    rimanenti = list(enumerate(mesi))

    # La fotografia cresce soltanto dopo aver collocato ciascun turno.
    blacklist_cumulata = set(blacklist_iniziale)

    risultato = []

    while rimanenti:
        migliore_pos = 0
        migliore_idx_orig, migliore_mese = rimanenti[0]
        migliore_chiave = chiave_pulizia_terzetti(migliore_mese['gruppi'],
                                                  blacklist_cumulata)

        for pos in range(1, len(rimanenti)):
            idx_orig_i, mese_i = rimanenti[pos]
            chiave_i = chiave_pulizia_terzetti(mese_i['gruppi'],
                                               blacklist_cumulata)
            if chiave_i < migliore_chiave:
                migliore_pos = pos
                migliore_idx_orig = idx_orig_i
                migliore_mese = mese_i
                migliore_chiave = chiave_i

        rimanenti.pop(migliore_pos)
        mese_nuovo = dict(migliore_mese)
        # Il report deve vedere la blacklist precedente alla nuova posizione.
        mese_nuovo['adiacenze_prima'] = set(blacklist_cumulata)
        risultato.append((migliore_idx_orig, mese_nuovo, migliore_chiave))

        blacklist_cumulata |= adiacenze_per_blacklist_terzetti(
            migliore_mese['gruppi'])

    return risultato



def conta_riutilizzate_con_foto(
    assegnatore,
    foto,
    vicini_fisso_precedenti=None,
) -> dict:
    """Conta i riutilizzi rispetto a una fotografia esplicita della blacklist.

    Serve dopo il riordinamento dell'Annuale, quando lo stato vivo del motore
    rappresenta ancora l'ordine originario. Restituisce lo stesso contratto di
    ``utilita.conta_riutilizzate`` e riceve a parte i precedenti vicini del
    FISSO. La funzione resta qui perché è metrica pura e non dipende da Qt.
    """
    if vicini_fisso_precedenti is None:
        vicini_fisso_precedenti = set()

    def _in_foto(studente_a, studente_b):
        return tuple(sorted([
            studente_a.get_nome_completo(),
            studente_b.get_nome_completo(),
        ])) in foto

    normali = sum(
        1
        for studente_a, studente_b, _punteggio in assegnatore.coppie_formate
        if _in_foto(studente_a, studente_b)
    )

    trio = 0
    for gruppo in estrai_gruppi(assegnatore):
        if gruppo.tipo in (TIPO_TERZETTO, TIPO_QUARTETTO):
            for studente_a, studente_b in adiacenze_in_fila(gruppo.membri):
                if _in_foto(studente_a, studente_b):
                    trio += 1

    vicino_fisso = 0
    vicino_fisso_nome = None
    nome_vicino = getattr(assegnatore, "nome_adiacente_fisso", None)
    if (
        getattr(assegnatore, "studente_fisso", None)
        and nome_vicino
        and nome_vicino in vicini_fisso_precedenti
    ):
        vicino_fisso = 1
        vicino_fisso_nome = nome_vicino

    coppia_fisso = 0
    coppia_fisso_nomi = None
    gruppo_adiacente = getattr(
        assegnatore,
        "gruppo_adiacente_fisso",
        None,
    )
    if (
        gruppo_adiacente
        and len(gruppo_adiacente) >= 2
        and _in_foto(gruppo_adiacente[0], gruppo_adiacente[1])
    ):
        coppia_fisso = 1
        coppia_fisso_nomi = (
            gruppo_adiacente[0].get_nome_completo(),
            gruppo_adiacente[1].get_nome_completo(),
        )

    totali = normali + trio + coppia_fisso + vicino_fisso
    return {
        "normali": normali,
        "trio": trio,
        "totali": totali,
        "vicino_fisso": vicino_fisso,
        "vicino_fisso_nome": vicino_fisso_nome,
        "coppia_fisso": coppia_fisso,
        "coppia_fisso_nomi": coppia_fisso_nomi,
    }
