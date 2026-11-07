# -*- coding: utf-8 -*-
"""Gate E3 produttivo/4 — rappresentazione persistente della disposizione standard.

Nessuna inferenza da pixel o gruppi legacy: la fonte di verita' e' il valore
DisposizioneEffettiva. La coppia FISSO-vicino resta distinta nella blacklist
Coppie legacy, ma TUTTI i vicini sono persistiti e ricostruiti.

Il modulo non esegue salvataggi autonomi e non e' connesso alla GUI.
"""
from __future__ import annotations

from moduli.dominio.disposizione_effettiva import DisposizioneEffettiva
from moduli.persistenza.strato_storico import aggiorna_blacklist_terzetti
from moduli.dominio.verifica_disposizione_standard import verifica_disposizione_standard

FORMATO_FISICO = "fisica_standard_v1"
TIPO_PER_CAPIENZA = {2: "coppia", 3: "terzetto", 4: "quartetto"}


def _coord(id_posto: str) -> tuple[int, int]:
    """Gli ID dei posti standard sono una parte verificata del contratto E2."""
    import re
    trovato = re.fullmatch(r"std-r([0-9]+)-c([0-9]+)", id_posto)
    if not trovato:
        raise ValueError(f"ID posto standard non valido: {id_posto!r}.")
    r, c = (int(v) for v in trovato.groups())
    if r < 2:
        raise ValueError("Un posto studente non puo' essere nella zona arredi.")
    return r, c


def _fotografia(disposizione: DisposizioneEffettiva, num_righe: int, num_colonne: int) -> tuple[list, list]:
    occupanti = dict(disposizione.occupazioni)
    gruppi = []
    layout = []
    for blocco in disposizione.blocchi:
        nomi = [occupanti[p.id] for p in blocco.posti]
        gruppi.append({"tipo": TIPO_PER_CAPIENZA[len(nomi)], "membri": nomi})
        for posto, nome in zip(blocco.posti, nomi):
            r, c = _coord(posto.id)
            if (r != blocco.riga_visuale + 2 or c != blocco.colonna + posto.indice
                    or r >= num_righe or c >= num_colonne):
                raise ValueError("Posti fisici non coerenti con la griglia dell'aula.")
            layout.append({"studente": nome, "riga": r, "colonna": c,
                           "tipo": TIPO_PER_CAPIENZA[len(nomi)],
                           "fisso": nome == disposizione.studente_fisso})
    return gruppi, layout


def crea_payload_fisico(disposizione: DisposizioneEffettiva, aula, studenti) -> dict:
    """Valida gli HARD e congela geometria, gruppi, posti e legami reali."""
    if disposizione.modo not in ("coppie", "terzetti"):
        raise ValueError("Serve una disposizione standard Coppie o Terzetti.")
    verifica = verifica_disposizione_standard(disposizione, studenti,
                                  ancora_attesa=disposizione.ancora_fisso)
    gruppi, layout = _fotografia(disposizione, aula.num_righe, aula.num_colonne)
    # Evita che un oggetto di geometria *diversa* venga salvato sotto lo stesso
    # numero di righe e colonne. I blocchi attivi devono esistere nell'aula.
    blocchi_aula = {
        tuple(f"std-r{r}-c{cella.colonna}" for cella in blocco)
        for r, fila in enumerate(aula.griglia) if r >= 2
        for blocco in aula._raggruppa_banchi_in_blocchi(fila)
    }
    if not {tuple(p.id for p in b.posti) for b in disposizione.blocchi} <= blocchi_aula:
        raise ValueError("I blocchi fisici non coincidono con l'aula selezionata.")
    celle = [
        {"riga": r, "colonna": c, "tipo": posto.tipo}
        for r, fila in enumerate(aula.griglia)
        for c, posto in enumerate(fila)
        if posto.tipo != "corridoio"
    ]
    return {
        "formato_disposizione": FORMATO_FISICO,
        "celle_aula": celle,
        "disposizione_fisica": disposizione.a_json(),
        "gruppi": gruppi,
        "layout": layout,
        "adiacenze_fisiche": [list(coppia) for coppia in verifica.adiacenze],
        "vicini_fisso": list(verifica.vicini_fisso),
        "configurazione_aula": {
            "num_file": aula.num_righe - 2,
            "posti_per_fila": sum(p.tipo == "banco" for p in aula.griglia[2]),
            "num_studenti": len(disposizione.occupazioni),
            "num_righe": aula.num_righe,
            "num_colonne": aula.num_colonne,
            "ha_fisso": disposizione.studente_fisso is not None,
            "larghezza_blocco_sx": getattr(aula, "larghezza_blocco_sx", 2),
            "genere_misto": disposizione.genere_misto,
        },
    }


def valida_voce_fisica(voce: dict, indice: int = 0) -> DisposizioneEffettiva:
    """Rifiuta alterazioni di una voce salvata; non richiede studenti in memoria."""
    if not isinstance(voce, dict) or voce.get("formato_disposizione") != FORMATO_FISICO:
        raise ValueError(f"Voce fisica {indice}: formato non riconosciuto.")
    d = DisposizioneEffettiva.da_json(voce["disposizione_fisica"])
    if d.modo != voce.get("modo") or d.modo not in {"coppie", "terzetti"}:
        raise ValueError(f"Voce fisica {indice}: modalita' discordanti.")
    meta = voce.get("configurazione_aula")
    if not isinstance(meta, dict):
        raise ValueError(f"Voce fisica {indice}: geometria mancante.")
    r = meta.get("num_righe")
    c = meta.get("num_colonne")
    if (type(r) is not int or type(c) is not int or r < 3 or c < 1
            or meta.get("num_file") != r - 2
            or meta.get("num_studenti") != len(d.occupazioni)
            or meta.get("ha_fisso") != (d.studente_fisso is not None)
            or meta.get("genere_misto") != d.genere_misto):
        raise ValueError(f"Voce fisica {indice}: metadati d'aula discordanti.")
    gruppi, layout = _fotografia(d, r, c)
    celle = voce.get("celle_aula")
    if not isinstance(celle, list):
        raise ValueError(f"Voce fisica {indice}: celle dell'aula mancanti.")
    coordinate = set()
    tipi = {}
    for cella in celle:
        if not isinstance(cella, dict) or set(cella) != {"riga", "colonna", "tipo"}:
            raise ValueError(f"Voce fisica {indice}: formato cella errato.")
        rr, cc, tipo = cella["riga"], cella["colonna"], cella["tipo"]
        if (type(rr) is not int or type(cc) is not int or rr < 0 or cc < 0
                or rr >= r or cc >= c or tipo not in {"banco", "lim", "lavagna", "cattedra", "postazione_docente"}
                or (rr < 2 and tipo == "banco") or (rr >= 2 and tipo != "banco")
                or (rr, cc) in coordinate):
            raise ValueError(f"Voce fisica {indice}: geometria delle celle incoerente.")
        coordinate.add((rr, cc))
        tipi[(rr, cc)] = tipo
    if any(tipi.get((e["riga"], e["colonna"])) != "banco" for e in layout):
        raise ValueError(f"Voce fisica {indice}: studente fuori da un banco.")
    if voce.get("gruppi") != gruppi or voce.get("layout") != layout:
        raise ValueError(f"Voce fisica {indice}: gruppi o layout alterati.")
    adiacenze = sorted(d.adiacenze_fisiche())
    vicini = sorted(c[0] if c[1] == d.studente_fisso else c[1]
                    for c in adiacenze if d.studente_fisso in c)
    if (voce.get("adiacenze_fisiche") != [list(c) for c in adiacenze]
            or voce.get("vicini_fisso") != vicini):
        raise ValueError(f"Voce fisica {indice}: adiacenze o vicini FISSO alterati.")
    if d.studente_fisso is not None and len(vicini) not in (1, 2):
        raise ValueError(f"Voce fisica {indice}: numero vicini FISSO errato.")
    if len(adiacenze) != sum(len(b.posti) - 1 for b in d.blocchi):
        raise ValueError(f"Voce fisica {indice}: adiacenze mancanti o duplicate.")
    return d


def aggiorna_rotazioni_da_voce_fisica(config_app, voce: dict) -> None:
    """Stessa regola usata sia per la scrittura sia per il replay dello Storico."""
    disposizione = valida_voce_fisica(voce)
    adiacenze = sorted(disposizione.adiacenze_fisiche())
    if disposizione.modo == "terzetti":
        aggiorna_blacklist_terzetti(config_app, adiacenze)
        return
    nome_fisso = disposizione.studente_fisso
    blacklist = config_app.config_data["coppie_da_evitare"]
    presenti = {tuple(sorted(v["studenti"])): v for v in blacklist}
    for a, b in adiacenze:
        if nome_fisso in (a, b):
            altro = b if a == nome_fisso else a
            contatore = config_app.config_data["studenti_vicino_fisso_contatore"]
            contatore[altro] = contatore.get(altro, 0) + 1
            continue
        coppia = (a, b)
        if coppia in presenti:
            presenti[coppia]["volte_usata"] += 1
        else:
            voce_blacklist = {"tipo": "coppia", "studenti": [a, b], "volte_usata": 1}
            blacklist.append(voce_blacklist)
            presenti[coppia] = voce_blacklist
    # Non aggiorna 'studenti_trio_contatore': e' un contatore della specifica
    # forma legacy trio, e non dei blocchi fisici di dimensione arbitraria.


def ricostruisci_aula_da_voce_fisica(voce: dict):
    """Riapre il Layout fisico, nascondendo i banchi inutilizzati.

    La fotografia JSON rimane intatta: la pulizia riguarda solo la copia
    ricostruita per Layout Storico ed esportazione Excel.
    """
    from moduli.dominio.aula import ConfigurazioneAula, PostoAula
    d = valida_voce_fisica(voce)
    m = voce["configurazione_aula"]
    aula = ConfigurazioneAula(f"Layout {voce['nome']}")
    aula.num_righe = m["num_righe"]
    aula.num_colonne = m["num_colonne"]
    aula.griglia = [[PostoAula(r, c, "corridoio") for c in range(aula.num_colonne)]
                   for r in range(aula.num_righe)]
    for cella in voce["celle_aula"]:
        r, c = cella["riga"], cella["colonna"]
        aula.griglia[r][c] = PostoAula(r, c, cella["tipo"])
    for posto, nome in d.occupazioni:
        r, c = _coord(posto)
        aula.griglia[r][c].occupato_da = nome
    if d.ancora_fisso:
        aula.coord_fisso = _coord(d.ancora_fisso)
    aula.posti_disponibili = sum(c.tipo == "banco" for fila in aula.griglia for c in fila)
    aula.larghezza_blocco_sx = m["larghezza_blocco_sx"]
    aula.ha_fisso = d.studente_fisso is not None
    # Stessa regola del Mensile e della 1.0. Funziona anche per le voci
    # fisiche già salvate: non occorre modificare o migrare il JSON.
    aula.rimuovi_banchi_vuoti()
    return aula
