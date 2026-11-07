# -*- coding: utf-8 -*-
"""Convenzione VISIVA comune per la zona docente in tutte le modalità.

Non modifica la geometria fisica o lo Storico: le vecchie celle LIM e lavagna
restano eventualmente nei dati, ma non sono arredi dichiarati dal docente.
"""

ETICHETTA_DOCENTE = "CATTEDRA / ZONA DOCENTE"
TIPI_ARREDI = frozenset({"cattedra", "postazione_docente", "lim", "lavagna"})


def riga_solo_arredi(riga):
    """Una fila di soli arredi legacy/corridoio, senza posti di studenti.

    Nella Personalizzata i banchi possono trovarsi *accanto* alla cattedra:
    quella riga non va ricostruita, per non spostare nessun posto.
    """
    tipi = [posto.tipo for posto in riga]
    return (any(tipo in TIPI_ARREDI for tipo in tipi)
            and all(tipo in TIPI_ARREDI or tipo == "corridoio" for tipo in tipi))
