# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.

"""Motori mensili eseguibili in un processo Python separato.

Il modulo è deliberatamente privo di import Qt. Riceve fotografie già
serializzate degli input, esegue il medesimo percorso di calcolo del motore e
comunica soltanto messaggi serializzabili al processo principale.
"""

from __future__ import annotations

import pickle
import traceback

import moduli.motore_terzetti as mt


def esegui_mensile_terzetti_in_processo(
    payload_serializzato: bytes,
    connessione,
) -> None:
    """Calcola un Mensile a terzetti e ne invia l'esito sul canale IPC."""

    def invia(tipo: str, **dati) -> None:
        connessione.send({"tipo": tipo, **dati})

    try:
        richiesta = pickle.loads(payload_serializzato)
        gruppi, metadati_casualita = mt.calcola_miglior_mese_terzetti(
            richiesta["studenti"],
            richiesta["genere_misto"],
            config_app=richiesta["config_app"],
            preferenza_resto2=richiesta["preferenza_resto2"],
            resto_in_prima_fila=richiesta["resto_in_prima_fila"],
            max_terzetti_prima_fila=(
                richiesta["max_terzetti_prima_fila"]
            ),
            max_resti_prima_fila=richiesta["max_resti_prima_fila"],
            num_candidati=richiesta["num_candidati"],
            seed_base=richiesta["seed_principale"],
            contesto_casuale={
                "operazione": "mensile",
                "mese": 1,
            },
            restituisci_metadati=True,
        )
        risultato = {
            "gruppi": gruppi,
            "metadati_casualita": metadati_casualita,
        }
        # Fallisce qui con un messaggio leggibile se un futuro oggetto del
        # dominio dovesse diventare non serializzabile.
        pickle.dumps(risultato, protocol=pickle.HIGHEST_PROTOCOL)
        invia("risultato", risultato=risultato)
    except BaseException as errore:
        try:
            invia(
                "eccezione",
                messaggio=(
                    "Errore nel processo Mensile a terzetti: "
                    f"{errore.__class__.__name__}: {errore}"
                ),
                traceback=traceback.format_exc(),
            )
        except BaseException:
            pass
    finally:
        try:
            connessione.close()
        except BaseException:
            pass
