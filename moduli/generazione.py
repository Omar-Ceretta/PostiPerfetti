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
from moduli.algoritmo import AssegnatorePosti
from moduli.strato_storico import applica_penalita_storico
from moduli.casualita import deriva_seed, risolvi_seed_principale


def genera_candidato_mese(studenti, aula_originale, config_app,
                          modalita_trio, flag_genere_misto, studente_fisso,
                          tentativo_iniziale=1, seed_principale=None,
                          contesto_casuale=None, indice_candidato=1):
    """
    Genera una disposizione candidata con tutto il contesto richiesto.

    La configurazione può essere quella reale, una copia temporanea usata per
    una stagione o una configurazione di collaudo. Il valore restituito è la
    tupla ``(successo, assegnatore)``; l'assegnatore resta disponibile anche in
    caso di fallimento, per recuperarne la diagnostica.
    """
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
    assegnatore = AssegnatorePosti()
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

    successo = assegnatore.esegui_assegnazione_completa(
        studenti,
        aula_candidato,
        modalita_trio,
        studente_fisso=studente_fisso,
        tentativo_iniziale=tentativo_iniziale
    )
    return successo, assegnatore
