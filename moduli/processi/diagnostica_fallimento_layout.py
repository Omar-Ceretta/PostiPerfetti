# -*- coding: utf-8 -*-
"""M2: fotografia dei vincoli dopo una ricerca Mensile Q21 senza soluzione.

Non lancia Q21, non modifica lo schema e non pretende di dimostrare
l'impossibilità quando una ricerca si è conclusa senza una candidata.
La diagnosi usa la stessa fotografia immutabile consegnata al processo.
"""

from __future__ import annotations

from moduli.dominio.aula_personalizzata import valuta_zone_aula_personalizzata
from moduli.dominio.metrica_pulizia import livello_incompatibilita, nome_completo


def analizza_fallimento_layout(fotografia) -> dict:
    """Costruisce il report già compreso dal vecchio popup informativo.

    ``cause_certe`` contiene soltanto condizioni necessarie violate.
    Le altre evidenze sono indizi e i suggerimenti restano ipotesi.
    """
    schema = fotografia.layout.schema
    studenti = tuple(fotografia.crea_studenti())
    per_nome = {nome_completo(s): s for s in studenti}
    nomi = sorted(per_nome)
    zona = valuta_zone_aula_personalizzata(schema, studenti)
    primo = sorted(
        (nome_completo(s) for s in studenti if s.nota_posizione == 'PRIMA')
    )
    fisso = next((s for s in studenti if s.nota_posizione == 'FISSO'), None)
    coppie_l3 = []
    compatibili = {nome: [] for nome in nomi}
    for i, a in enumerate(nomi):
        for b in nomi[i + 1:]:
            if livello_incompatibilita(per_nome[a], per_nome[b]) >= 3:
                coppie_l3.append(f'{a} — {b}')
            else:
                compatibili[a].append(b)
                compatibili[b].append(a)

    senza_vicini = [nome for nome in nomi if not compatibili[nome]]
    cause_certe = []
    if senza_vicini:
        cause_certe.append(
            'Ogni blocco contiene almeno due posti, ma ' +
            (f'{senza_vicini[0]} non ha alcun compagno compatibile (L3).'
             if len(senza_vicini) == 1 else
             f'{len(senza_vicini)} studenti non hanno alcun compagno compatibile (L3).')
        )

    info_fisso = {'presente': fisso is not None}
    if fisso is not None:
        nome_fisso = nome_completo(fisso)
        blocco = schema.blocco_ancora_fisso
        ancora = None if blocco is None else blocco.posto_ancora_fisso
        min_vicini = (2 if blocco is not None and blocco.capienza == 3
                       and ancora is not None and ancora.indice == 1 else 1)
        possibili = sorted(compatibili[nome_fisso])
        info_fisso.update(nome=nome_fisso, possibili_vicini=possibili)
        if len(possibili) < min_vicini and nome_fisso not in senza_vicini:
            cause_certe.append(
                f'{nome_fisso} occupa una posizione FISSO con {min_vicini} '
                f'vicini necessari, ma ha soltanto {len(possibili)} '
                'studenti compatibili con il livello 3.'
            )

    # Qui non si ripete la guardia di capienza: il preflight ha già impedito
    # l'avvio se la zona DAVANTI non offre abbastanza posti.
    margine = zona.posti_prima_utilizzabili - zona.richieste_prima
    # Caso dimostrabile non intercettato dalla sola capienza preliminare:
    # due PRIMA costretti nell'unico banco DAVANTI da due posti, ma L3 fra loro.
    if (len(primo) == 2 and len(schema.blocchi_prima) == 1
            and schema.blocchi_prima[0].capienza == 2
            and not zona.fisso_occupa_prima
            and livello_incompatibilita(
                per_nome[primo[0]], per_nome[primo[1]]) >= 3):
        cause_certe.append(
            f'{primo[0]} e {primo[1]} devono occupare i due posti '
            'dell’unico blocco DAVANTI, ma sono incompatibili a livello 3.'
        )
    l3_prima = any(
        livello_incompatibilita(per_nome[a], per_nome[b]) >= 3
        for a in primo for b in nomi if a != b
    )
    suggerimenti = []
    if primo and 0 <= margine <= 2 and l3_prima:
        suggerimenti.append(
            'I posti DAVANTI bastano numericamente, ma la disponibilità è '
            'ristretta e ci sono incompatibilità L3 che coinvolgono studenti '
            "PRIMA. Se la geometria dell'aula lo permette, prova a contrassegnare "
            'come DAVANTI anche un altro blocco: potrebbe facilitare la ricerca.'
        )
    if coppie_l3:
        suggerimenti.append(
            'Controlla le incompatibilità di livello 3 mostrate nei dettagli: '
            'possono rendere difficili gli abbinamenti, soprattutto nei trii.'
        )
    if fisso is not None and len(info_fisso['possibili_vicini']) <= 3:
        suggerimenti.append(
            'Verifica i compagni compatibili con il posto FISSO; '
            'la sua posizione vincolata riduce le alternative.'
        )
    if not suggerimenti:
        suggerimenti.append(
            'Riprova la ricerca o verifica se qualche altra configurazione '
            'del Layout rispetta le caratteristiche reali dell’aula. '
            'L’esito negativo non dimostra l’assenza di soluzioni.'
        )

    return {
        'cause_certe': cause_certe,
        'ricerca_incompleta': not bool(cause_certe),
        'incompatibilita_assolute': coppie_l3,
        'studenti_senza_vicini_compatibili': senza_vicini,
        'studenti_prima_fila': primo,
        'prima_fila': {
            'richieste': zona.richieste_prima,
            'posti_utilizzabili': zona.posti_prima_utilizzabili,
            'margine': margine,
            # Non ripetere l'errore di capienza già gestito prima di Q21.
            'impossibile_per_capienza': False,
        },
        'fisso': info_fisso,
        'suggerimenti': suggerimenti,
    }
