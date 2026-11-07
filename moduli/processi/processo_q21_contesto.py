# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""I2/1: frontiera produttiva isolata (senza Qt) per l'Annuale Q21.

Il motore rimane quello di ``pipeline_q21_contesto``. Questo modulo si
occupa esclusivamente di input fotografato e protocollo IPC del worker;
non scrive lo Storico, non rigioca candidate e non importa runner LAB.
Mensile e Annuale della GUI usano questo percorso.
"""
from __future__ import annotations

import pickle
import traceback

from moduli.calcolo.ingresso_q21 import IngressoQ21, prepara_ingresso_q21_da_config
from moduli.calcolo.pipeline_q21_contesto import (BudgetContestualeEsaurito,
                                          esegui_contestuale)
from moduli.calcolo.riordino_pulizia_finale_q21 import riordina_risultato_per_presentazione


def prepara_richiesta_annuale_q21(fotografia, config_app, *,
                                 numero_mesi, seed_principale,
                                 num_candidati, budget_totale=600,
                                 riserva=60):
    """Acquisisce una sola volta lo Storico Personalizzata su copia isolata.

    La configurazione viva non viene mai trasferita al processo figlio.
    Il risultato contiene soltanto un ``IngressoQ21`` serializzabile.
    """
    if not callable(getattr(config_app, 'copia_temporanea', None)):
        raise TypeError('La configurazione deve consentire una copia temporanea.')
    snapshot = config_app.copia_temporanea()
    ingresso = prepara_ingresso_q21_da_config(
        fotografia, snapshot, numero_mesi=numero_mesi,
        seed_principale=seed_principale, num_candidati=num_candidati,
        budget_totale=budget_totale, riserva=riserva)
    richiesta = {'ingresso': ingresso}
    # La serializzazione avviene prima di esporre un worker alla GUI.
    pickle.dumps(richiesta, protocol=pickle.HIGHEST_PROTOCOL)
    return richiesta


def _annullato():
    return {'mesi': [], 'chiavi': [], 'info': {'motivo_stop': 'annullato'}}


def _messaggio_stato(evento, numero_mesi, *, migliore=None,
                     ultimo_tentativo=None, proposta_riusi=None):
    """Traduce la telemetria Q21 senza inventare nuovi tentativi.

    Gli eventi ``fase`` individuano rifiniture di candidate gia' generate:
    l'eventuale ``annata`` in quell'evento e' l'INDICE DELLA FINALISTA,
    non un nuovo tentativo. Il contatore produttivo resta monotono.
    """
    if not isinstance(evento, dict):
        return None
    tipo = evento.get('evento')
    if tipo not in ('mese', 'fase', 'migliore_completata',
                      'finalista_selezionata', 'risultato_verificato'):
        return None
    if type(migliore) is not int or migliore < 0:
        migliore = None
    if tipo in ('fase', 'finalista_selezionata', 'risultato_verificato'):
        # Q11/Q12 comunicano l'indice della candidata che rifiniscono,
        # Q19/Q20 non comunicano alcun indice: nessuno dei due deve
        # far ripartire il contatore dei tentativi dalla GUI.
        annata = ultimo_tentativo
        mese = 0
    else:
        annata = evento.get('annata', 1)
        mese = evento.get('mese', 0)
    if type(annata) is not int or annata < 1:
        annata = 1
    if type(mese) is not int or not 0 <= mese <= numero_mesi:
        mese = 0
    stato = dict(tentativo=annata, mese=mese, num_mesi=numero_mesi,
                 best=migliore, eta_max=None)
    if tipo == 'fase':
        # Soltanto Q21: il monitor dell'Annuale precedente non cambia.
        stato['fase_q21'] = evento.get('fase')
    elif tipo == 'finalista_selezionata':
        stato['fase_q21'] = 'finalista_selezionata'
    elif tipo == 'risultato_verificato':
        stato['fase_q21'] = 'risultato_verificato'
    if type(proposta_riusi) is int and proposta_riusi >= 0:
        stato['proposta_riusi'] = proposta_riusi
    return dict(tipo='stato', stato=stato)


def esegui_annuale_q21_in_processo(payload_serializzato, connessione,
                                   evento_stop):
    """Target ``spawn`` compatibile con il ponte annuale Qt preesistente.

    Esiti terminali: ``risultato``, ``errore`` o ``eccezione``. L'annullamento
    restituisce un risultato esplicitamente ANNULLATO e *nessun* mese parziale.
    Ogni fallimento impedisce che la GUI riceva una proposta accettabile.
    """
    try:
        richiesta = pickle.loads(payload_serializzato)
        if not isinstance(richiesta, dict) or set(richiesta) != {'ingresso'}:
            raise ValueError('Richiesta Annuale Q21 non riconosciuta.')
        ingresso = richiesta['ingresso']
        if not isinstance(ingresso, IngressoQ21):
            raise TypeError('Ingresso Q21 non valido.')
        if evento_stop is None or not callable(getattr(evento_stop, 'is_set', None)):
            raise TypeError('Evento di annullamento obbligatorio.')
        if evento_stop.is_set():
            connessione.send({'tipo': 'risultato', 'risultato': _annullato()})
            return

        migliore_finora = None
        proposta_riusi = None
        ultimo_tentativo = 1

        def progresso(evento):
            nonlocal migliore_finora, proposta_riusi, ultimo_tentativo
            if isinstance(evento, dict) and evento.get('evento') in (
                    'mese', 'migliore_completata'):
                corrente = evento.get('annata')
                if type(corrente) is int and corrente > ultimo_tentativo:
                    ultimo_tentativo = corrente
            if isinstance(evento, dict) and evento.get('evento') == 'migliore_completata':
                riusi = evento.get('riusi')
                if type(riusi) is not int or riusi < 0:
                    raise ValueError('Progresso Q21: riusi non validi.')
                if migliore_finora is None or riusi < migliore_finora:
                    migliore_finora = riusi
            if isinstance(evento, dict) and evento.get('evento') in (
                    'finalista_selezionata', 'risultato_verificato'):
                riusi = evento.get('riusi')
                if type(riusi) is not int or riusi < 0:
                    raise ValueError('Q21: riusi della finalista non validi.')
                proposta_riusi = riusi
            messaggio = _messaggio_stato(
                evento, ingresso.numero_mesi, migliore=migliore_finora,
                ultimo_tentativo=ultimo_tentativo, proposta_riusi=proposta_riusi)
            if messaggio is not None:
                connessione.send(messaggio)

        risultato, _diagnostica = esegui_contestuale(
            ingresso, evento_stop, progresso,
            backend_ricerca='q17', diversifica_q2=True)
        # Copre anche lo stop richiesto dopo l'ultima verifica del nucleo.
        if evento_stop.is_set():
            connessione.send({'tipo': 'risultato', 'risultato': _annullato()})
            return
        if (len(risultato.get('mesi') or ()) != ingresso.numero_mesi
                or len(risultato.get('chiavi') or ()) != ingresso.numero_mesi
                or risultato.get('info', {}).get('schema_identita') !=
                   ingresso.fotografia.layout.schema.identita_semantica()):
            raise ValueError('Annuale Q21 incompleta o incoerente: nessun risultato promosso.')
        for mese in risultato['mesi']:
            ingresso.fotografia.verifica_risultato(mese)
        # Solo in uscita produttiva: la candidata e le fasi Q21/R2
        # sono gia' state selezionate e verificate. Un eventuale scambio
        # deve conservare integralmente metriche e profilo temporale.
        if ingresso.numero_mesi > 1:
            risultato = riordina_risultato_per_presentazione(risultato, ingresso)
        if evento_stop.is_set():
            connessione.send({'tipo': 'risultato', 'risultato': _annullato()})
            return
        pickle.dumps(risultato, protocol=pickle.HIGHEST_PROTOCOL)
        connessione.send({'tipo': 'risultato', 'risultato': risultato})
    except InterruptedError:
        connessione.send({'tipo': 'risultato', 'risultato': _annullato()})
    except BudgetContestualeEsaurito as errore:
        connessione.send({'tipo': 'errore', 'messaggio': str(errore), 'report': None})
    except BaseException as errore:
        connessione.send({
            'tipo': 'eccezione',
            'messaggio': f'Errore processo Annuale Q21: {type(errore).__name__}: {errore}',
            'traceback': traceback.format_exc(),
        })
    finally:
        connessione.close()
