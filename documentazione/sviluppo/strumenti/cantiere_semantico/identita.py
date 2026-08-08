"""Identificatori stabili e indipendenti dal processo Python."""

from __future__ import annotations

import re
from typing import Any

from .serializzazione import firma_json_sha256


_PREFISSO = re.compile(r"^[a-z][a-z0-9_-]*$")


def crea_identificatore(
    prefisso: str,
    *componenti: Any,
    lunghezza_digest: int = 24,
) -> str:
    """Crea ``prefisso_<digest>`` da componenti serializzate stabilmente."""
    if not _PREFISSO.fullmatch(prefisso):
        raise ValueError(
            "Il prefisso deve iniziare con una lettera minuscola e contenere "
            "solo lettere minuscole, numeri, '_' o '-'."
        )
    if isinstance(lunghezza_digest, bool) or not isinstance(lunghezza_digest, int):
        raise ValueError("lunghezza_digest deve essere un intero.")
    if not 12 <= lunghezza_digest <= 64:
        raise ValueError("lunghezza_digest deve essere compresa fra 12 e 64.")
    digest = firma_json_sha256({
        "dominio": "postiperfetti-osservatore-semantico-r0.1",
        "prefisso": prefisso,
        "componenti": componenti,
    })
    return f"{prefisso}_{digest[:lunghezza_digest]}"


def chiave_adiacenza(studente_a: str, studente_b: str) -> tuple[str, str]:
    """Restituisce l'identità non orientata di una relazione fra due studenti."""
    a = str(studente_a).strip()
    b = str(studente_b).strip()
    if not a or not b:
        raise ValueError("I nomi dell'adiacenza non possono essere vuoti.")
    if a == b:
        raise ValueError("Un'adiacenza richiede due studenti distinti.")
    return tuple(sorted((a, b)))



def crea_stato_iniziale_id(sha256_snapshot: str) -> str:
    """Crea l'identità protocollare da una firma SHA-256 già verificata."""
    digest = str(sha256_snapshot).strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("sha256_snapshot deve contenere 64 caratteri esadecimali.")
    return crea_identificatore("stato", digest)


def crea_pair_id(classe: str, studente_fisso: str) -> str:
    return crea_identificatore("pair", classe, studente_fisso)


def crea_run_id(
    pair_id: str,
    condizione: str,
    modalita: str,
    seed_principale: int,
    numero_mesi: int,
    genere_misto_attivo: bool,
    stato_iniziale_id: str,
    parametri_ricerca: Any,
    parametri_aula: Any,
) -> str:
    return crea_identificatore(
        "run",
        pair_id,
        condizione,
        modalita,
        seed_principale,
        numero_mesi,
        genere_misto_attivo,
        stato_iniziale_id,
        parametri_ricerca,
        parametri_aula,
    )


def crea_group_id(run_id: str, mese: int, indice_gruppo: int, membri_ordinati: Any) -> str:
    return crea_identificatore("group", run_id, mese, indice_gruppo, membri_ordinati)


def crea_event_id(
    run_id: str,
    mese: int,
    group_id: str,
    ordine_a: int,
    ordine_b: int,
    studente_a: str,
    studente_b: str,
) -> str:
    return crea_identificatore(
        "event",
        run_id,
        mese,
        group_id,
        ordine_a,
        ordine_b,
        studente_a,
        studente_b,
    )


def crea_confronto_id(run_senza_fisso: str, run_con_fisso: str) -> str:
    return crea_identificatore("confronto", run_senza_fisso, run_con_fisso)
