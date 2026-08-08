# -*- coding: utf-8 -*-
"""Selezione pura delle righe statistiche da mostrare nei riepiloghi.

Il modulo non dipende da Qt: decide soltanto quali righe strutturate meritano
una segnalazione sintetica nell'anteprima annuale e nei popup di risultato.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""


def seleziona_righe_segnalazioni(righe):
    """Restituisce riusi e criticità non nulle, conservando l'ordine originale."""
    selezionate = []
    for riga in righe or []:
        chiave = riga.get("chiave")
        valore = riga.get("valore")
        if chiave == "riutilizzate":
            selezionate.append(riga)
        elif chiave in {"vicino_fisso_riutilizzato", "dettaglio_vicino_fisso"}:
            selezionate.append(riga)
        elif chiave in {"problematiche", "critiche"}:
            if isinstance(valore, (int, float)) and valore > 0:
                selezionate.append(riga)
    return selezionate
