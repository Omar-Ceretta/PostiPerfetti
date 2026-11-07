# -*- coding: utf-8 -*-
"""Schema del JSON applicativo: costanti, valori iniziali e validazione in memoria.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from typing import Dict

from moduli.persistenza.strato_storico import CHIAVE_BLACKLIST_PER_MODO
from moduli.persistenza.validazione_storico import valida_storico

VERSIONE_SCHEMA_CONFIGURAZIONE = 2
CHIAVE_VERSIONE_SCHEMA = "schema_versione"

CHIAVI_STORICO_E_ROTAZIONI = (
    "storico_assegnazioni",
    "coppie_da_evitare",
    CHIAVE_BLACKLIST_PER_MODO["terzetti"],
    CHIAVE_BLACKLIST_PER_MODO["personalizzata"],
    "studenti_trio_contatore",
    "studenti_vicino_fisso_contatore",
)


def configurazione_default() -> Dict:
    """Restituisce la struttura iniziale della configurazione."""
    return {
        CHIAVE_VERSIONE_SCHEMA: VERSIONE_SCHEMA_CONFIGURAZIONE,
        # Persistono soltanto Storico, rotazioni e preferenze globali.
        "storico_assegnazioni": [],
        "coppie_da_evitare": [],
        # Terzetti e Personalizzata usano blacklist di adiacenze distinte
        # fra loro e dalla modalità Coppie.
        CHIAVE_BLACKLIST_PER_MODO["terzetti"]: [],
        CHIAVE_BLACKLIST_PER_MODO["personalizzata"]: [],
        "studenti_trio_contatore": {},  # presenze nel trio
        "studenti_vicino_fisso_contatore": {},  # presenze accanto al FISSO
        "tema": "scuro"  # tema dell’interfaccia
    }


def valida_configurazione(dati: object) -> Dict:
    """Valida il JSON già letto: nessun file o stato applicativo viene modificato."""
    if not isinstance(dati, dict):
        raise ValueError(
            "La radice del file JSON non è un oggetto."
        )

    tipi_attesi = {
        CHIAVE_VERSIONE_SCHEMA: int,
        "storico_assegnazioni": list,
        "coppie_da_evitare": list,
        CHIAVE_BLACKLIST_PER_MODO["terzetti"]: list,
        CHIAVE_BLACKLIST_PER_MODO["personalizzata"]: list,
        "studenti_trio_contatore": dict,
        "studenti_vicino_fisso_contatore": dict,
        "tema": str,
    }
    chiavi_attese = set(tipi_attesi)
    chiavi_presenti = set(dati)

    mancanti = sorted(chiavi_attese - chiavi_presenti)
    inattese = sorted(chiavi_presenti - chiavi_attese)
    if mancanti or inattese:
        dettagli = []
        if mancanti:
            dettagli.append("mancano: " + ", ".join(mancanti))
        if inattese:
            dettagli.append("non previste: " + ", ".join(inattese))
        raise ValueError(
            "Il file JSON non usa il formato corrente; "
            + "; ".join(dettagli)
            + "."
        )

    for chiave, tipo_atteso in tipi_attesi.items():
        valore = dati[chiave]
        tipo_valido = isinstance(valore, tipo_atteso)
        if tipo_atteso is int:
            tipo_valido = tipo_valido and not isinstance(valore, bool)
        if not tipo_valido:
            raise ValueError(
                f"La chiave «{chiave}» ha un formato non valido: "
                f"atteso {tipo_atteso.__name__}."
            )

    if dati[CHIAVE_VERSIONE_SCHEMA] != VERSIONE_SCHEMA_CONFIGURAZIONE:
        raise ValueError(
            "Versione dello schema di configurazione non supportata: "
            f"{dati[CHIAVE_VERSIONE_SCHEMA]!r}."
        )

    def intero_valido(valore) -> bool:
        return isinstance(valore, int) and not isinstance(valore, bool)

    if dati["tema"] not in {"scuro", "chiaro"}:
        raise ValueError(
            "La chiave «tema» deve valere «scuro» oppure «chiaro»."
        )

    def valida_blacklist(nome_chiave: str, tipo_atteso: str) -> None:
        """Verifica struttura, contatori e unicità di una blacklist."""
        coppie_viste = set()
        for posizione, voce in enumerate(dati[nome_chiave], start=1):
            if not isinstance(voce, dict):
                raise ValueError(
                    f"La voce {posizione} di «{nome_chiave}» non è un oggetto."
                )

            if voce.get("tipo") != tipo_atteso:
                raise ValueError(
                    f"La voce {posizione} di «{nome_chiave}» ha un tipo "
                    "non valido."
                )

            studenti = voce.get("studenti")
            if (
                not isinstance(studenti, list)
                or len(studenti) != 2
                or any(
                    not isinstance(nome, str) or not nome.strip()
                    for nome in studenti
                )
                or studenti[0] == studenti[1]
            ):
                raise ValueError(
                    f"La voce {posizione} di «{nome_chiave}» non contiene "
                    "due studenti validi e distinti."
                )

            volte_usata = voce.get("volte_usata")
            if not intero_valido(volte_usata) or volte_usata < 1:
                raise ValueError(
                    f"La voce {posizione} di «{nome_chiave}» ha un "
                    "contatore non valido."
                )

            chiave_coppia = tuple(sorted(studenti))
            if chiave_coppia in coppie_viste:
                raise ValueError(
                    f"La voce {posizione} di «{nome_chiave}» duplica "
                    "una coppia già presente."
                )
            coppie_viste.add(chiave_coppia)

    def valida_contatore_nomi(nome_chiave: str) -> None:
        """Verifica i contatori indicizzati per nome completo."""
        for nome, conteggio in dati[nome_chiave].items():
            if not isinstance(nome, str) or not nome.strip():
                raise ValueError(
                    f"La chiave «{nome_chiave}» contiene un nome non valido."
                )
            if not intero_valido(conteggio) or conteggio < 0:
                raise ValueError(
                    f"La chiave «{nome_chiave}» contiene un contatore "
                    f"non valido per «{nome}»."
                )

    valida_blacklist("coppie_da_evitare", "coppia")
    valida_blacklist(
        CHIAVE_BLACKLIST_PER_MODO["terzetti"],
        "adiacenza",
    )
    valida_blacklist(
        CHIAVE_BLACKLIST_PER_MODO["personalizzata"],
        "adiacenza",
    )
    valida_contatore_nomi("studenti_trio_contatore")
    valida_contatore_nomi("studenti_vicino_fisso_contatore")

    valida_storico(dati["storico_assegnazioni"])
    return dati
