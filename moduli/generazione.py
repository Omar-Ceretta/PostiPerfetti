# -*- coding: utf-8 -*-
"""
generazione.py — costruzione condivisa di un candidato mensile.

Fornisce ``genera_candidato_mese()``, il punto unico usato dalla GUI e dagli
strumenti di collaudo per preparare ed eseguire una singola disposizione del
best-of-N. Centralizzare questa procedura garantisce che tutti i chiamanti
configurino il motore nello stesso modo.

La funzione risolve la casualità riproducibile, collega la configurazione,
attiva rotazione e genere misto, applica la penalità storica e consegna al
motore una copia indipendente dell'aula.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import copy
from time import perf_counter_ns
from moduli.algoritmo import AssegnatorePosti
from moduli.strato_storico import applica_penalita_storico
from moduli.casualita import deriva_seed, risolvi_seed_principale
from moduli.studenti import chiave_ordinamento_studente


def genera_candidato_mese(studenti, aula_originale, config_app,
                          modalita_trio, flag_genere_misto, studente_fisso,
                          tentativo_iniziale=1, seed_principale=None,
                          contesto_casuale=None, indice_candidato=1,
                          diagnostica=None):
    """
    Genera una disposizione candidata con tutto il contesto richiesto.

    La configurazione può essere quella reale, una copia temporanea usata per
    una stagione o una configurazione di collaudo. Il valore restituito è la
    tupla ``(successo, assegnatore)``; l'assegnatore resta disponibile anche in
    caso di fallimento, per recuperarne la diagnostica.
    """
    # L'ordine delle righe del file classe non ha significato semantico.
    # Canonicalizza gli studenti prima di alimentare qualunque scelta del motore.
    studenti = sorted(studenti, key=chiave_ordinamento_studente)

    # Deriva un seed figlio stabile dal seed dell'operazione e dal contesto.
    seed_principale_effettivo = risolvi_seed_principale(seed_principale)
    contesto_casuale = dict(contesto_casuale or {})
    seed_candidato = deriva_seed(
        seed_principale_effettivo,
        "modalita", "coppie",
        "contesto", contesto_casuale,
        "candidato", indice_candidato,
    )

    # Crea l'assegnatore e registra i dati necessari alla riproducibilità.
    assegnatore = AssegnatorePosti(diagnostica=diagnostica)
    assegnatore.imposta_contesto_casuale(
        seed_principale_effettivo,
        seed_candidato,
        {**contesto_casuale, "candidato": indice_candidato},
    )

    # La configurazione alimenta penalità storiche e rotazione.
    assegnatore.config_app = config_app
    assegnatore.modalita_rotazione = True

    motore = assegnatore.motore_vincoli
    motore.imposta_genere_misto_obbligatorio(flag_genere_misto)
    # Il tentativo 4 usa la configurazione anche per distribuire equamente
    # eventuali riutilizzi fra gli studenti.
    motore._config_app_ref = config_app

    # Lo strato storico è sempre attivo; con una blacklist vuota non produce
    # effetti. Viene applicato prima della penalità specifica del tentativo:
    # al tentativo 4 le due penalità si sommano, come descritto nella mappa di
    # ``vincoli.calcola_punteggio_coppia``.
    applica_penalita_storico(motore, config_app)

    # L'assegnazione modifica l'aula: occupa i banchi e converte quelli vuoti
    # in corridoi. Ogni candidato deve quindi partire da una copia indipendente
    # della stessa aula originale.
    aula_candidato = copy.deepcopy(aula_originale)

    inizio_ns = perf_counter_ns()
    if diagnostica is not None:
        diagnostica.evento(
            "candidato_inizio",
            modalita="coppie",
            candidato=indice_candidato,
            seed_principale=seed_principale_effettivo,
            seed_candidato=seed_candidato,
            tentativo_iniziale=tentativo_iniziale,
            contesto=contesto_casuale,
        )
        with diagnostica.attiva():
            successo = assegnatore.esegui_assegnazione_completa(
                studenti,
                aula_candidato,
                modalita_trio,
                studente_fisso=studente_fisso,
                tentativo_iniziale=tentativo_iniziale
            )
        diagnostica.evento(
            "candidato_fine",
            modalita="coppie",
            candidato=indice_candidato,
            seed_candidato=seed_candidato,
            successo=bool(successo),
            durata_ns=perf_counter_ns() - inizio_ns,
            tentativo=getattr(motore, "tentativo_corrente", None),
        )
    else:
        successo = assegnatore.esegui_assegnazione_completa(
            studenti,
            aula_candidato,
            modalita_trio,
            studente_fisso=studente_fisso,
            tentativo_iniziale=tentativo_iniziale
        )
    return successo, assegnatore


# Numero predefinito di candidati confrontati nel modo a coppie.
NUM_CANDIDATI = 10


def calcola_miglior_mese(
    studenti,
    aula_originale,
    config_app,
    modalita_trio,
    flag_genere_misto,
    studente_fisso,
    coppie_gia_usate,
    num_candidati=NUM_CANDIDATI,
    deve_fermarsi=None,
    seed_principale=None,
    contesto_casuale=None,
    diagnostica=None,
):
    """Restituisce il candidato mensile con la migliore chiave di pulizia.

    La funzione è condivisa fra il worker mensile e il motore annuale. Tutti i
    candidati vengono confrontati rispetto alla stessa fotografia iniziale e
    usano seed figli locali e riproducibili.
    """
    from moduli.metrica_pulizia import (
        chiave_pulizia,
        snapshot_vicini_fisso,
        conta_incompatibilita_per_livello,
        conta_affinita_soddisfatte,
        estrai_adiacenze,
    )

    miglior_assegnatore = None
    miglior_chiave = None
    ultimo_assegnatore = None

    seed_principale = risolvi_seed_principale(seed_principale)
    contesto_casuale = dict(contesto_casuale or {})
    vicini_fisso_gia_usati = snapshot_vicini_fisso(config_app)

    # Dopo un candidato arrivato al quarto tentativo si possono saltare i
    # tentativi già dimostrati inutili per i candidati successivi.
    tentativo_partenza = 1

    for indice_candidato in range(1, num_candidati + 1):
        if deve_fermarsi is not None and deve_fermarsi():
            break

        successo, assegnatore = genera_candidato_mese(
            studenti,
            aula_originale,
            config_app,
            modalita_trio,
            flag_genere_misto,
            studente_fisso,
            tentativo_iniziale=tentativo_partenza,
            seed_principale=seed_principale,
            contesto_casuale=contesto_casuale,
            indice_candidato=indice_candidato,
            diagnostica=diagnostica,
        )
        ultimo_assegnatore = assegnatore

        tentativo_candidato = getattr(
            assegnatore.motore_vincoli,
            "tentativo_corrente",
            None,
        )
        if tentativo_candidato == 4:
            tentativo_partenza = 4

        if not successo:
            continue

        chiave = chiave_pulizia(
            assegnatore,
            coppie_gia_usate,
            vicini_fisso_gia_usati,
        )
        if diagnostica is not None:
            frequenze_riuso = []
            for studente_a, studente_b in estrai_adiacenze(assegnatore):
                utilizzi = assegnatore.motore_vincoli._conta_utilizzi_coppia(
                    studente_a, studente_b
                )
                if utilizzi > 0:
                    frequenze_riuso.append(utilizzi)
            diagnostica.evento(
                "qualita_candidato",
                modalita="coppie",
                candidato=indice_candidato,
                seed_candidato=assegnatore.seed_candidato,
                tentativo=tentativo_candidato,
                chiave=chiave,
                incompatibilita_per_livello=(
                    conta_incompatibilita_per_livello(assegnatore)
                ),
                affinita=conta_affinita_soddisfatte(assegnatore),
                frequenze_riuso=frequenze_riuso,
            )
        if miglior_chiave is None or chiave < miglior_chiave:
            miglior_chiave = chiave
            miglior_assegnatore = assegnatore

        # Nei primi tre tentativi non vengono tollerate incompatibilità: il
        # risultato è già pienamente valido e non richiede altri candidati.
        if tentativo_candidato is not None and tentativo_candidato <= 3:
            break

    if diagnostica is not None:
        vincitore = miglior_assegnatore
        diagnostica.evento(
            "best_of_n_fine",
            modalita="coppie",
            successo=vincitore is not None,
            chiave_vincente=miglior_chiave,
            seed_candidato=(
                getattr(vincitore, "seed_candidato", None)
                if vincitore is not None else None
            ),
            tentativo=(
                getattr(vincitore.motore_vincoli, "tentativo_corrente", None)
                if vincitore is not None else None
            ),
        )
    return miglior_assegnatore, ultimo_assegnatore
