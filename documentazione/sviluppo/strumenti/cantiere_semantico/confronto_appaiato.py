"""Confronto appaiato fra annate senza/con FISSO — incremento I8.

Il modulo lavora esclusivamente su ``ANNATA.json`` già validati e su una
attestazione I2 delle classi gemelle. Non interroga C1 e non attribuisce
causalità: espone differenze osservate con convenzione ``con_fisso - senza_fisso``.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from .ambiente import EsitoClassiAppaiate
from .identita import crea_confronto_id
from .modelli import OSSERVATORE_VERSIONE, SCHEMA_OUTPUT_VERSIONE
from .serializzazione import (
    firma_file_sha256,
    firma_json_sha256,
    leggi_json,
    rendi_json_stabile,
    scrivi_json_atomico,
    scrivi_testo_atomico,
)
from .validazione import valida_dati_annata


class ErroreConfrontoAppaiato(ValueError):
    """Segnala input illeggibili o un output di confronto incoerente."""


@dataclass(frozen=True, slots=True)
class ProblemaAppaiamento:
    codice: str
    messaggio: str

    def __post_init__(self) -> None:
        if not str(self.codice).strip() or not str(self.messaggio).strip():
            raise ValueError("Codice e messaggio del problema non possono essere vuoti.")


@dataclass(frozen=True, slots=True)
class ConfrontoAppaiato:
    versioni: Mapping[str, Any]
    confronto_id: str
    pair_id: str
    validita_appaiamento: bool
    problemi_appaiamento: tuple[ProblemaAppaiamento, ...]
    attestazione_classi: Mapping[str, Any] | None
    impronte_input: Mapping[str, str]
    run_senza_fisso: Mapping[str, Any]
    run_con_fisso: Mapping[str, Any]
    parametri_comuni: Mapping[str, Any]
    studente_fisso: str | None
    mesi: tuple[Mapping[str, Any], ...] = ()
    annuale: Mapping[str, Any] = field(default_factory=dict)
    nota_interpretativa: str = (
        "Le differenze sono osservate in una coppia appaiata e non costituiscono "
        "da sole una prova causale né un giudizio pedagogico automatico."
    )

    def __post_init__(self) -> None:
        if not str(self.confronto_id).strip() or not str(self.pair_id).strip():
            raise ValueError("confronto_id e pair_id non possono essere vuoti.")
        object.__setattr__(self, "versioni", _congela_mapping(self.versioni))
        object.__setattr__(self, "problemi_appaiamento", tuple(self.problemi_appaiamento))
        if self.attestazione_classi is not None:
            object.__setattr__(self, "attestazione_classi", _congela_mapping(self.attestazione_classi))
        object.__setattr__(self, "impronte_input", _congela_mapping(self.impronte_input))
        object.__setattr__(self, "run_senza_fisso", _congela_mapping(self.run_senza_fisso))
        object.__setattr__(self, "run_con_fisso", _congela_mapping(self.run_con_fisso))
        object.__setattr__(self, "parametri_comuni", _congela_mapping(self.parametri_comuni))
        object.__setattr__(self, "mesi", tuple(_congela_mapping(mese) for mese in self.mesi))
        object.__setattr__(self, "annuale", _congela_mapping(self.annuale))
        if self.validita_appaiamento and self.problemi_appaiamento:
            raise ValueError("Un appaiamento valido non può contenere problemi.")
        if not self.validita_appaiamento and not self.problemi_appaiamento:
            raise ValueError("Un appaiamento invalido deve spiegare il motivo.")
        if self.validita_appaiamento and (not self.mesi or not self.annuale):
            raise ValueError("Un confronto valido deve contenere differenze mensili e annuali.")
        if not self.validita_appaiamento and (self.mesi or self.annuale):
            raise ValueError("Un appaiamento invalido non deve produrre confronti interpretativi.")


@dataclass(frozen=True, slots=True)
class EsitoValidazioneConfronto:
    valido: bool
    problemi: tuple[ProblemaAppaiamento, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "problemi", tuple(self.problemi))
        if self.valido == bool(self.problemi):
            raise ValueError("Il flag valido non coincide con i problemi del confronto.")


@dataclass(frozen=True, slots=True)
class EsitoPubblicazioneConfronto:
    confronto_id: str
    directory: str
    confronto_json: str
    confronto_markdown: str
    validazione_json: str
    sha256_confronto_json: str
    sha256_confronto_markdown: str
    sha256_validazione_json: str


def _congela_mapping(valore: Mapping[str, Any]) -> Mapping[str, Any]:
    """Congela un mapping mediante la sua rappresentazione JSON stabile."""
    normalizzato = rendi_json_stabile(valore)

    def congela(x: Any) -> Any:
        if isinstance(x, dict):
            return MappingProxyType({str(k): congela(v) for k, v in x.items()})
        if isinstance(x, list):
            return tuple(congela(v) for v in x)
        return x

    return congela(normalizzato)


def _mapping(valore: Any, nome: str) -> Mapping[str, Any]:
    if not isinstance(valore, Mapping):
        raise ErroreConfrontoAppaiato(f"{nome} deve essere un oggetto JSON.")
    return valore


def _lista(valore: Any, nome: str) -> Sequence[Any]:
    if not isinstance(valore, list):
        raise ErroreConfrontoAppaiato(f"{nome} deve essere una lista JSON.")
    return valore


def _valida_input_annata(dati: Mapping[str, Any], etichetta: str) -> None:
    esito = valida_dati_annata(dati)
    if esito.valido:
        return
    codici = ", ".join(p.codice for p in esito.problemi if p.gravita.value == "errore")
    raise ErroreConfrontoAppaiato(f"{etichetta} non è un ANNATA.json valido: {codici}")


def _normalizza_condizioni(
    primo: Mapping[str, Any],
    secondo: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    c1 = _mapping(primo.get("run"), "run del primo input").get("condizione")
    c2 = _mapping(secondo.get("run"), "run del secondo input").get("condizione")
    if {c1, c2} != {"senza_fisso", "con_fisso"}:
        raise ErroreConfrontoAppaiato(
            "Gli input devono contenere esattamente una condizione senza_fisso e una con_fisso."
        )
    return (primo, secondo) if c1 == "senza_fisso" else (secondo, primo)


def _problema(problemi: list[ProblemaAppaiamento], codice: str, messaggio: str) -> None:
    problemi.append(ProblemaAppaiamento(codice, messaggio))


def _attestazione_json(attestazione: EsitoClassiAppaiate | Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if attestazione is None:
        return None
    dati = rendi_json_stabile(attestazione)
    if not isinstance(dati, Mapping):
        raise ErroreConfrontoAppaiato("L'attestazione delle classi non è serializzabile come oggetto.")
    return dati


def _studenti_per_nome(dati: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    risultato: dict[str, Mapping[str, Any]] = {}
    for indice, voce_raw in enumerate(_lista(dati.get("studenti"), "studenti")):
        voce = _mapping(voce_raw, f"studenti[{indice}]")
        nome = str(voce.get("studente", "")).strip()
        if not nome:
            raise ErroreConfrontoAppaiato(f"studenti[{indice}] non ha identità.")
        if nome in risultato:
            raise ErroreConfrontoAppaiato(f"Studente duplicato nell'input: {nome}.")
        risultato[nome] = voce
    return risultato


def _verifica_appaiamento(
    senza: Mapping[str, Any],
    con: Mapping[str, Any],
    attestazione: Mapping[str, Any] | None,
) -> tuple[ProblemaAppaiamento, ...]:
    problemi: list[ProblemaAppaiamento] = []
    rs = _mapping(senza.get("run"), "run senza_fisso")
    rc = _mapping(con.get("run"), "run con_fisso")

    if rs.get("condizione") != "senza_fisso" or rc.get("condizione") != "con_fisso":
        _problema(problemi, "CONDIZIONI", "Le condizioni dei due run non sono canoniche.")
    if rs.get("run_id") == rc.get("run_id"):
        _problema(problemi, "RUN_ID", "I due run devono avere identificatori distinti.")
    if rs.get("pair_id") != rc.get("pair_id"):
        _problema(problemi, "PAIR_ID", "I due run non condividono lo stesso pair_id.")
    if senza.get("stato") != "completo" or con.get("stato") != "completo":
        _problema(problemi, "RUN_NON_COMPLETO", "Entrambi i run devono essere completi.")
    if senza.get("classe") != con.get("classe"):
        _problema(problemi, "CLASSE", "Le due annate non dichiarano la stessa classe logica.")
    if senza.get("numero_studenti") != con.get("numero_studenti"):
        _problema(problemi, "NUMERO_STUDENTI", "Il numero degli studenti non coincide.")
    if rs.get("file_classe") == rc.get("file_classe"):
        _problema(problemi, "FILE_CLASSE", "I due run devono provenire da file gemelli distinti.")

    campi_run_comuni = (
        "pair_id",
        "modalita",
        "seed_principale",
        "numero_mesi",
        "genere_misto_attivo",
        "stato_iniziale_id",
        "parametri_ricerca",
        "parametri_aula",
    )
    for campo in campi_run_comuni:
        if rendi_json_stabile(rs.get(campo)) != rendi_json_stabile(rc.get(campo)):
            _problema(problemi, f"PARAMETRO_{campo.upper()}", f"Il parametro {campo} non coincide.")

    if rendi_json_stabile(senza.get("versioni")) != rendi_json_stabile(con.get("versioni")):
        _problema(problemi, "VERSIONI", "Le versioni dei due output non coincidono.")
    if rendi_json_stabile(senza.get("snapshot_iniziale")) != rendi_json_stabile(con.get("snapshot_iniziale")):
        _problema(problemi, "SNAPSHOT", "Gli snapshot iniziali non coincidono integralmente.")

    fisso = con.get("studente_fisso")
    if not isinstance(fisso, str) or not fisso.strip():
        _problema(problemi, "FISSO_ASSENTE", "Il run con_fisso non identifica lo studente FISSO.")
        fisso = None
    if senza.get("studente_fisso") is not None:
        _problema(problemi, "FISSO_NELLA_BASE", "Il run senza_fisso dichiara uno studente FISSO.")

    ss = _studenti_per_nome(senza)
    sc = _studenti_per_nome(con)
    if set(ss) != set(sc):
        _problema(problemi, "IDENTITA_STUDENTI", "Le identità degli studenti non coincidono.")
    else:
        fissi_senza = sorted(nome for nome, voce in ss.items() if voce.get("e_fisso") is True)
        fissi_con = sorted(nome for nome, voce in sc.items() if voce.get("e_fisso") is True)
        if fissi_senza:
            _problema(problemi, "FISSO_BASE", f"La classe base contiene FISSO: {fissi_senza}.")
        if fisso is not None and fissi_con != [fisso]:
            _problema(problemi, "FISSO_GEMELLA", f"FISSO osservati nella gemella: {fissi_con}.")
        for nome in sorted(ss):
            a, b = ss[nome], sc[nome]
            if a.get("genere") != b.get("genere"):
                _problema(problemi, "GENERE_STUDENTE", f"Il genere di {nome} non coincide.")
            if nome == fisso:
                if a.get("posizione") == "FISSO" or b.get("posizione") != "FISSO":
                    _problema(problemi, "POSIZIONE_FISSO", f"Trasformazione FISSO non canonica per {nome}.")
            elif a.get("posizione") != b.get("posizione") or a.get("e_fisso") != b.get("e_fisso"):
                _problema(problemi, "POSIZIONE_NON_AUTORIZZATA", f"Posizione modificata per {nome}.")

    if attestazione is None:
        _problema(
            problemi,
            "ATTESTAZIONE_ASSENTE",
            "Manca l'attestazione I2 che prova l'equivalenza completa dei file-classe.",
        )
    else:
        if attestazione.get("pair_id") != rs.get("pair_id"):
            _problema(problemi, "ATTESTAZIONE_PAIR_ID", "L'attestazione I2 appartiene a un'altra coppia.")
        if fisso is not None and attestazione.get("studente_fisso") != fisso:
            _problema(problemi, "ATTESTAZIONE_FISSO", "L'attestazione I2 indica un FISSO differente.")
        if attestazione.get("numero_studenti") != senza.get("numero_studenti"):
            _problema(problemi, "ATTESTAZIONE_NUMERO", "L'attestazione I2 ha un numero studenti differente.")
        for campo in ("firma_senza_fisso", "firma_con_fisso"):
            valore = attestazione.get(campo)
            if not isinstance(valore, str) or len(valore) != 64 or any(c not in "0123456789abcdef" for c in valore.lower()):
                _problema(problemi, "ATTESTAZIONE_FIRMA", f"{campo} non è una firma SHA-256 valida.")

    return tuple(problemi)


def _tripla(senza: int | float, con: int | float) -> dict[str, int | float]:
    return {"senza_fisso": senza, "con_fisso": con, "delta": con - senza}


def _descrittore_evento(evento: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "studenti": list(evento.get("chiave_adiacenza") or (evento.get("studente_a"), evento.get("studente_b"))),
        "canale_rotazione": evento.get("canale_rotazione"),
        "ruolo": evento.get("ruolo"),
        "coinvolge_fisso": bool(evento.get("coinvolge_fisso")),
        "incompatibilita_livello": int(evento.get("incompatibilita_livello") or 0),
        "affinita_livello": int(evento.get("affinita_livello") or 0),
        "adiacenza_mista": bool(evento.get("adiacenza_mista")),
        "e_riuso": bool(evento.get("e_riuso")),
        "numero_ripetizione": evento.get("numero_ripetizione"),
        "distanza_mesi": evento.get("distanza_mesi"),
    }


def _eventi_per_chiave(mese: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    risultato: dict[tuple[str, str], Mapping[str, Any]] = {}
    for evento_raw in _lista(mese.get("adiacenze"), "adiacenze del mese"):
        evento = _mapping(evento_raw, "evento")
        chiave_raw = evento.get("chiave_adiacenza")
        if not isinstance(chiave_raw, list) or len(chiave_raw) != 2:
            raise ErroreConfrontoAppaiato("Evento privo di chiave_adiacenza canonica.")
        chiave = tuple(sorted(str(x) for x in chiave_raw))
        if chiave in risultato:
            raise ErroreConfrontoAppaiato(f"Adiacenza duplicata nello stesso mese: {chiave}.")
        risultato[chiave] = evento
    return risultato


_METRICHE_MESE = (
    "adiacenze_totali",
    "riusi_totali",
    "prime_ripetizioni",
    "seconde_ripetizioni",
    "terze_o_ulteriori",
    "incompatibilita_l1",
    "incompatibilita_l2",
    "incompatibilita_l3",
    "affinita_l1",
    "affinita_l2",
    "affinita_l3",
    "adiacenze_miste",
    "adiacenze_stesso_genere",
)

_METRICHE_ANNO = (
    "adiacenze_totali",
    "riusi_totali",
    "prime_ripetizioni",
    "seconde_ripetizioni",
    "terze_o_ulteriori",
    "incompatibilita_l1",
    "incompatibilita_l2",
    "incompatibilita_l3",
    "affinita_l1",
    "affinita_l2",
    "affinita_l3",
    "adiacenze_miste",
    "studenti_con_0_riusi",
    "studenti_con_1_riuso",
    "studenti_con_2_riusi",
    "studenti_con_3_o_piu_riusi",
    "massimo_individuale",
)

_METRICHE_STUDENTE = (
    "riusi_coinvolgenti",
    "prime_ripetizioni",
    "seconde_ripetizioni",
    "terze_o_ulteriori",
    "compagni_distinti",
    "incarichi_vicino_fisso",
)


def _valori_riepilogo(senza: Mapping[str, Any], con: Mapping[str, Any], campi: Iterable[str]) -> dict[str, Any]:
    risultato = {}
    for campo in campi:
        a = senza.get(campo)
        b = con.get(campo)
        if isinstance(a, bool) or not isinstance(a, (int, float)) or isinstance(b, bool) or not isinstance(b, (int, float)):
            raise ErroreConfrontoAppaiato(f"Il campo numerico {campo} è assente o invalido.")
        risultato[campo] = _tripla(a, b)
    return risultato


def _analisi_genere_mese(dati: Mapping[str, Any], mese: int) -> Mapping[str, Any]:
    genere = _mapping(dati.get("genere_misto"), "genere_misto")
    for voce_raw in _lista(genere.get("mesi"), "genere_misto.mesi"):
        voce = _mapping(voce_raw, "analisi genere mese")
        if voce.get("mese") == mese:
            return voce
    raise ErroreConfrontoAppaiato(f"Analisi di genere non trovata per il mese {mese}.")


def _confronta_mese(
    senza: Mapping[str, Any],
    con: Mapping[str, Any],
    annata_senza: Mapping[str, Any],
    annata_con: Mapping[str, Any],
) -> dict[str, Any]:
    mese = int(senza.get("mese_finale"))
    if con.get("mese_finale") != mese:
        raise ErroreConfrontoAppaiato("I mesi appaiati non hanno lo stesso numero.")
    es = _eventi_per_chiave(senza)
    ec = _eventi_per_chiave(con)
    comuni = []
    for chiave in sorted(set(es) & set(ec)):
        comuni.append({
            "studenti": list(chiave),
            "senza_fisso": _descrittore_evento(es[chiave]),
            "con_fisso": _descrittore_evento(ec[chiave]),
        })
    solo_senza = [_descrittore_evento(es[k]) for k in sorted(set(es) - set(ec))]
    solo_con = [_descrittore_evento(ec[k]) for k in sorted(set(ec) - set(es))]
    gs = _analisi_genere_mese(annata_senza, mese)
    gc = _analisi_genere_mese(annata_con, mese)
    genere = {
        "massimo_geometrico": _tripla(
            int(_mapping(gs.get("massimo_geometrico"), "massimo geometrico senza").get("valore")),
            int(_mapping(gc.get("massimo_geometrico"), "massimo geometrico con").get("valore")),
        ),
        "massimo_ammissibile": _tripla(
            int(_mapping(gs.get("massimo_ammissibile"), "massimo ammissibile senza").get("valore")),
            int(_mapping(gc.get("massimo_ammissibile"), "massimo ammissibile con").get("valore")),
        ),
        "adiacenze_miste_ottenute": _tripla(
            int(gs.get("adiacenze_miste_ottenute")), int(gc.get("adiacenze_miste_ottenute"))
        ),
    }
    return {
        "mese": mese,
        "adiacenze_comuni": comuni,
        "adiacenze_solo_senza_fisso": solo_senza,
        "adiacenze_solo_con_fisso": solo_con,
        "conteggi_adiacenze": {
            "comuni": len(comuni),
            "solo_senza_fisso": len(solo_senza),
            "solo_con_fisso": len(solo_con),
        },
        "valori": _valori_riepilogo(
            _mapping(senza.get("riepilogo"), "riepilogo mese senza"),
            _mapping(con.get("riepilogo"), "riepilogo mese con"),
            _METRICHE_MESE,
        ),
        "genere_misto": genere,
        "vicino_fisso": _mapping(con.get("vicino_fisso"), "vicino_fisso") if con.get("vicino_fisso") is not None else None,
    }


def _distribuzione_distanze(dati: Mapping[str, Any]) -> dict[str, int]:
    risultato = {"distanza_1": 0, "distanza_2": 0, "distanza_3_o_piu": 0, "non_calcolabile": 0}
    for mese_raw in _lista(dati.get("mesi"), "mesi"):
        mese = _mapping(mese_raw, "mese")
        for evento_raw in _lista(mese.get("adiacenze"), "adiacenze"):
            evento = _mapping(evento_raw, "evento")
            if not evento.get("e_riuso"):
                continue
            distanza = evento.get("distanza_mesi")
            if distanza is None:
                risultato["non_calcolabile"] += 1
            elif distanza == 1:
                risultato["distanza_1"] += 1
            elif distanza == 2:
                risultato["distanza_2"] += 1
            elif isinstance(distanza, int) and distanza >= 3:
                risultato["distanza_3_o_piu"] += 1
            else:
                raise ErroreConfrontoAppaiato("Distanza di riuso non valida.")
    return risultato


def _confronta_studenti(senza: Mapping[str, Any], con: Mapping[str, Any]) -> list[dict[str, Any]]:
    ss, sc = _studenti_per_nome(senza), _studenti_per_nome(con)
    risultato = []
    for nome in sorted(set(ss) & set(sc)):
        a, b = ss[nome], sc[nome]
        valori = _valori_riepilogo(a, b, _METRICHE_STUDENTE)
        cambiato = any(voce["delta"] != 0 for voce in valori.values()) or any(
            rendi_json_stabile(a.get(campo)) != rendi_json_stabile(b.get(campo))
            for campo in ("posizione", "e_fisso", "mesi_con_riusi", "mesi_vicino_fisso")
        )
        risultato.append({
            "studente": nome,
            "genere": a.get("genere"),
            "posizione": {"senza_fisso": a.get("posizione"), "con_fisso": b.get("posizione")},
            "e_fisso": {"senza_fisso": bool(a.get("e_fisso")), "con_fisso": bool(b.get("e_fisso"))},
            "valori": valori,
            "mesi_con_riusi": {
                "senza_fisso": list(a.get("mesi_con_riusi") or []),
                "con_fisso": list(b.get("mesi_con_riusi") or []),
            },
            "mesi_vicino_fisso": {
                "senza_fisso": list(a.get("mesi_vicino_fisso") or []),
                "con_fisso": list(b.get("mesi_vicino_fisso") or []),
            },
            "cambiato": cambiato,
        })
    return risultato


def _confronto_annuale(senza: Mapping[str, Any], con: Mapping[str, Any]) -> dict[str, Any]:
    ds, dc = _distribuzione_distanze(senza), _distribuzione_distanze(con)
    genere_s = _mapping(senza.get("genere_misto"), "genere_misto senza")
    genere_c = _mapping(con.get("genere_misto"), "genere_misto con")
    studenti = _confronta_studenti(senza, con)
    ruolo = [
        {
            "studente": voce["studente"],
            "numero_incarichi": voce["valori"]["incarichi_vicino_fisso"]["con_fisso"],
            "mesi": voce["mesi_vicino_fisso"]["con_fisso"],
        }
        for voce in studenti
        if voce["valori"]["incarichi_vicino_fisso"]["con_fisso"] > 0
    ]
    return {
        "valori": _valori_riepilogo(
            _mapping(senza.get("riepilogo"), "riepilogo annuale senza"),
            _mapping(con.get("riepilogo"), "riepilogo annuale con"),
            _METRICHE_ANNO,
        ),
        "distanze_riusi": {campo: _tripla(ds[campo], dc[campo]) for campo in ds},
        "genere_misto": {
            "massimo_geometrico_totale": _tripla(
                int(genere_s.get("massimo_geometrico_totale")), int(genere_c.get("massimo_geometrico_totale"))
            ),
            "massimo_ammissibile_totale": _tripla(
                int(genere_s.get("massimo_ammissibile_totale")), int(genere_c.get("massimo_ammissibile_totale"))
            ),
            "adiacenze_miste_ottenute_totali": _tripla(
                int(genere_s.get("adiacenze_miste_ottenute_totali")), int(genere_c.get("adiacenze_miste_ottenute_totali"))
            ),
        },
        "studenti": studenti,
        "studenti_con_cambiamento": [voce["studente"] for voce in studenti if voce["cambiato"]],
        "distribuzione_vicino_fisso": ruolo,
    }


def _versioni_confronto(dati: Mapping[str, Any]) -> dict[str, Any]:
    versioni = dict(_mapping(dati.get("versioni"), "versioni"))
    versioni["osservatore"] = OSSERVATORE_VERSIONE
    versioni["schema_confronto"] = SCHEMA_OUTPUT_VERSIONE
    return versioni


def _run_sintetico(dati: Mapping[str, Any]) -> dict[str, Any]:
    run = _mapping(dati.get("run"), "run")
    return {
        "run_id": run.get("run_id"),
        "file_classe": run.get("file_classe"),
        "condizione": run.get("condizione"),
        "stato": dati.get("stato"),
        "classe": dati.get("classe"),
    }


def _parametri_comuni(dati: Mapping[str, Any]) -> dict[str, Any]:
    run = _mapping(dati.get("run"), "run")
    snapshot = _mapping(dati.get("snapshot_iniziale"), "snapshot_iniziale")
    return {
        "modalita": run.get("modalita"),
        "seed_principale": run.get("seed_principale"),
        "numero_mesi": run.get("numero_mesi"),
        "genere_misto_attivo": run.get("genere_misto_attivo"),
        "stato_iniziale_id": run.get("stato_iniziale_id"),
        "snapshot_sha256": snapshot.get("sha256"),
        "parametri_ricerca": run.get("parametri_ricerca"),
        "parametri_aula": run.get("parametri_aula"),
    }


def costruisci_confronto_appaiato(
    primo: Mapping[str, Any],
    secondo: Mapping[str, Any],
    *,
    attestazione_classi: EsitoClassiAppaiate | Mapping[str, Any] | None,
) -> ConfrontoAppaiato:
    """Costruisce il confronto, oppure un record invalido privo di differenze."""
    primo = _mapping(primo, "primo ANNATA.json")
    secondo = _mapping(secondo, "secondo ANNATA.json")
    _valida_input_annata(primo, "Primo input")
    _valida_input_annata(secondo, "Secondo input")
    senza, con = _normalizza_condizioni(primo, secondo)
    rs, rc = _mapping(senza["run"], "run senza"), _mapping(con["run"], "run con")
    attestazione = _attestazione_json(attestazione_classi)
    problemi = _verifica_appaiamento(senza, con, attestazione)
    confronto_id = crea_confronto_id(str(rs.get("run_id")), str(rc.get("run_id")))
    base = dict(
        versioni=_versioni_confronto(senza),
        confronto_id=confronto_id,
        pair_id=str(rs.get("pair_id")),
        validita_appaiamento=not problemi,
        problemi_appaiamento=problemi,
        attestazione_classi=attestazione,
        impronte_input={
            "annata_senza_fisso_sha256": firma_json_sha256(senza),
            "annata_con_fisso_sha256": firma_json_sha256(con),
        },
        run_senza_fisso=_run_sintetico(senza),
        run_con_fisso=_run_sintetico(con),
        parametri_comuni=_parametri_comuni(senza) if not problemi else {},
        studente_fisso=con.get("studente_fisso") if not problemi else None,
    )
    if problemi:
        return ConfrontoAppaiato(**base)

    mesi_s = _lista(senza.get("mesi"), "mesi senza")
    mesi_c = _lista(con.get("mesi"), "mesi con")
    if len(mesi_s) != len(mesi_c):
        # Dovrebbe essere già intercettato dai parametri, ma resta una guardia.
        problema = ProblemaAppaiamento("MESI", "Il numero effettivo dei mesi non coincide.")
        base["validita_appaiamento"] = False
        base["problemi_appaiamento"] = (problema,)
        base["parametri_comuni"] = {}
        base["studente_fisso"] = None
        return ConfrontoAppaiato(**base)
    mesi = tuple(
        _confronta_mese(_mapping(a, "mese senza"), _mapping(b, "mese con"), senza, con)
        for a, b in zip(mesi_s, mesi_c)
    )
    return ConfrontoAppaiato(
        **base,
        mesi=mesi,
        annuale=_confronto_annuale(senza, con),
    )


def _controlla_tripla(
    voce: Any,
    percorso: str,
    problemi: list[ProblemaAppaiamento],
) -> None:
    if not isinstance(voce, Mapping):
        _problema(problemi, "TRIPLA", f"{percorso} non è un oggetto senza/con/delta.")
        return
    a, b, d = voce.get("senza_fisso"), voce.get("con_fisso"), voce.get("delta")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (a, b, d)):
        _problema(problemi, "TRIPLA_TIPO", f"{percorso} contiene valori non numerici.")
    elif b - a != d:
        _problema(problemi, "TRIPLA_DELTA", f"{percorso}: delta incoerente.")


def valida_dati_confronto(dati: Mapping[str, Any]) -> EsitoValidazioneConfronto:
    """Valida autonomamente la coerenza interna di CONFRONTO.json."""
    problemi: list[ProblemaAppaiamento] = []
    if not isinstance(dati, Mapping):
        return EsitoValidazioneConfronto(False, (ProblemaAppaiamento("RADICE", "La radice deve essere un oggetto."),))
    versioni = dati.get("versioni")
    if not isinstance(versioni, Mapping):
        _problema(problemi, "VERSIONI", "versioni deve essere un oggetto.")
    else:
        if versioni.get("strategia") != "C1":
            _problema(problemi, "STRATEGIA", "Il confronto R0.1 ammette soltanto C1.")
        if versioni.get("osservatore") != OSSERVATORE_VERSIONE:
            _problema(problemi, "VERSIONE_OSSERVATORE", "Versione osservatore non corrente.")
    confronto_id = dati.get("confronto_id")
    rs = dati.get("run_senza_fisso")
    rc = dati.get("run_con_fisso")
    if not isinstance(rs, Mapping) or not isinstance(rc, Mapping):
        _problema(problemi, "RUN", "I riferimenti ai due run devono essere oggetti.")
    else:
        atteso = crea_confronto_id(str(rs.get("run_id")), str(rc.get("run_id")))
        if confronto_id != atteso:
            _problema(problemi, "CONFRONTO_ID", "confronto_id non è canonico.")
        if rs.get("condizione") != "senza_fisso" or rc.get("condizione") != "con_fisso":
            _problema(problemi, "CONDIZIONI", "Le condizioni dei run non sono canoniche.")
        if dati.get("pair_id") is None or dati.get("pair_id") == "":
            _problema(problemi, "PAIR_ID", "pair_id non può essere vuoto.")
    impronte = dati.get("impronte_input")
    if not isinstance(impronte, Mapping):
        _problema(problemi, "IMPRONTE", "impronte_input deve essere un oggetto.")
    else:
        for campo in ("annata_senza_fisso_sha256", "annata_con_fisso_sha256"):
            valore = impronte.get(campo)
            if not isinstance(valore, str) or len(valore) != 64 or any(c not in "0123456789abcdef" for c in valore.lower()):
                _problema(problemi, "IMPRONTA_INPUT", f"{campo} non è una firma SHA-256 valida.")
    valido_app = dati.get("validita_appaiamento") is True
    problemi_app = dati.get("problemi_appaiamento")
    if not isinstance(problemi_app, list):
        _problema(problemi, "PROBLEMI_APPAIAMENTO", "problemi_appaiamento deve essere una lista.")
        problemi_app = []
    mesi = dati.get("mesi")
    annuale = dati.get("annuale")
    if valido_app:
        if problemi_app:
            _problema(problemi, "APPAIAMENTO", "Appaiamento valido con problemi dichiarati.")
        if not isinstance(mesi, list) or not mesi or not isinstance(annuale, Mapping) or not annuale:
            _problema(problemi, "CONTENUTO", "Un confronto valido richiede mesi e riepilogo annuale.")
        else:
            numeri = [mese.get("mese") for mese in mesi if isinstance(mese, Mapping)]
            if numeri != list(range(1, len(mesi) + 1)):
                _problema(problemi, "ORDINE_MESI", "I mesi non sono consecutivi da 1 a N.")
            for i, mese in enumerate(mesi):
                if not isinstance(mese, Mapping):
                    _problema(problemi, "MESE", f"mesi[{i}] non è un oggetto.")
                    continue
                valori = mese.get("valori")
                if isinstance(valori, Mapping):
                    for campo, tripla in valori.items():
                        _controlla_tripla(tripla, f"mesi[{i}].valori.{campo}", problemi)
                else:
                    _problema(problemi, "VALORI_MESE", f"mesi[{i}].valori non è un oggetto.")
                genere = mese.get("genere_misto")
                if isinstance(genere, Mapping):
                    for campo, tripla in genere.items():
                        _controlla_tripla(tripla, f"mesi[{i}].genere_misto.{campo}", problemi)
                insiemi: list[set[tuple[str, str]]] = []
                for campo in ("adiacenze_comuni", "adiacenze_solo_senza_fisso", "adiacenze_solo_con_fisso"):
                    lista = mese.get(campo)
                    if not isinstance(lista, list):
                        _problema(problemi, "ADIACENZE", f"mesi[{i}].{campo} non è una lista.")
                        insiemi.append(set())
                        continue
                    chiavi = set()
                    for voce in lista:
                        if not isinstance(voce, Mapping):
                            continue
                        studenti = voce.get("studenti")
                        if isinstance(studenti, list) and len(studenti) == 2:
                            chiavi.add(tuple(sorted(str(x) for x in studenti)))
                    if len(chiavi) != len(lista):
                        _problema(problemi, "ADIACENZE_DUPLICATE", f"mesi[{i}].{campo} contiene duplicati o voci invalide.")
                    insiemi.append(chiavi)
                if any(insiemi[a] & insiemi[b] for a, b in ((0, 1), (0, 2), (1, 2))):
                    _problema(problemi, "ADIACENZE_SOVRAPPOSTE", f"Le categorie del mese {i+1} si sovrappongono.")
                conteggi = mese.get("conteggi_adiacenze")
                if not isinstance(conteggi, Mapping) or (
                    conteggi.get("comuni") != len(insiemi[0])
                    or conteggi.get("solo_senza_fisso") != len(insiemi[1])
                    or conteggi.get("solo_con_fisso") != len(insiemi[2])
                ):
                    _problema(problemi, "CONTEGGI_ADIACENZE", f"Conteggi incoerenti nel mese {i+1}.")
            valori_annuali = annuale.get("valori")
            if isinstance(valori_annuali, Mapping):
                for campo, tripla in valori_annuali.items():
                    _controlla_tripla(tripla, f"annuale.valori.{campo}", problemi)
            distanze = annuale.get("distanze_riusi")
            if isinstance(distanze, Mapping):
                for campo, tripla in distanze.items():
                    _controlla_tripla(tripla, f"annuale.distanze_riusi.{campo}", problemi)
            genere_annuale = annuale.get("genere_misto")
            if isinstance(genere_annuale, Mapping):
                for campo, tripla in genere_annuale.items():
                    _controlla_tripla(tripla, f"annuale.genere_misto.{campo}", problemi)
            studenti = annuale.get("studenti")
            if not isinstance(studenti, list):
                _problema(problemi, "STUDENTI", "annuale.studenti deve essere una lista.")
            else:
                nomi = [v.get("studente") for v in studenti if isinstance(v, Mapping)]
                if len(set(nomi)) != len(nomi) or None in nomi:
                    _problema(problemi, "STUDENTI_DUPLICATI", "Il confronto studenti contiene duplicati.")
                for i, studente in enumerate(studenti):
                    if isinstance(studente, Mapping) and isinstance(studente.get("valori"), Mapping):
                        for campo, tripla in studente["valori"].items():
                            _controlla_tripla(tripla, f"annuale.studenti[{i}].valori.{campo}", problemi)
                dichiarati = annuale.get("studenti_con_cambiamento")
                attesi = [s.get("studente") for s in studenti if isinstance(s, Mapping) and s.get("cambiato") is True]
                if dichiarati != attesi:
                    _problema(problemi, "STUDENTI_CAMBIAMENTO", "studenti_con_cambiamento non coincide con i record individuali.")
            # I totali annuali devono coincidere con la somma delle viste mensili.
            if isinstance(valori_annuali, Mapping):
                for campo in set(_METRICHE_MESE).intersection(_METRICHE_ANNO):
                    if campo not in valori_annuali:
                        continue
                    for condizione in ("senza_fisso", "con_fisso"):
                        somma = sum(
                            mese.get("valori", {}).get(campo, {}).get(condizione, 0)
                            for mese in mesi if isinstance(mese, Mapping)
                        )
                        if valori_annuali[campo].get(condizione) != somma:
                            _problema(problemi, "TOTALE_ANNUALE", f"annuale.valori.{campo}.{condizione} non coincide con i mesi.")
    else:
        if not problemi_app:
            _problema(problemi, "APPAIAMENTO", "Appaiamento invalido senza motivazioni.")
        if mesi not in ([], ()) or annuale not in ({}, None):
            _problema(problemi, "CONTENUTO_INVALIDO", "Un appaiamento invalido non deve contenere differenze.")

    return EsitoValidazioneConfronto(not problemi, tuple(problemi))


def rendi_confronto_markdown(dati: Mapping[str, Any], *, valida: bool = True) -> str:
    """Rende un rapporto descrittivo da CONFRONTO.json."""
    if valida:
        esito = valida_dati_confronto(dati)
        if not esito.valido:
            codici = ", ".join(p.codice for p in esito.problemi)
            raise ErroreConfrontoAppaiato(f"CONFRONTO.json non valido: {codici}")
    righe = [
        "# PostiPerfetti — Confronto appaiato",
        "",
        f"**Confronto:** `{dati.get('confronto_id')}`  ",
        f"**Coppia:** `{dati.get('pair_id')}`",
        "",
    ]
    if not dati.get("validita_appaiamento"):
        righe.extend(["## Appaiamento non valido", ""])
        for problema in dati.get("problemi_appaiamento", []):
            righe.append(f"- **{problema.get('codice')}** — {problema.get('messaggio')}")
        righe.extend([
            "",
            "Non vengono prodotte differenze interpretative finché l’appaiamento non è valido.",
            "",
        ])
        return "\n".join(righe) + "\n"

    p = dati["parametri_comuni"]
    righe.extend([
        "## 1. Validità e condizioni comuni",
        "",
        "L’appaiamento è valido: i file-classe sono stati attestati da I2 e i parametri osservabili coincidono.",
        "",
        f"- Modalità: **{p.get('modalita')}**",
        f"- Seed principale: `{p.get('seed_principale')}`",
        f"- Mesi: **{p.get('numero_mesi')}**",
        f"- Genere misto attivo: **{'sì' if p.get('genere_misto_attivo') else 'no'}**",
        f"- Studente FISSO: **{dati.get('studente_fisso')}**",
        "",
        "## 2. Differenze annuali",
        "",
        "| Indicatore | Senza FISSO | Con FISSO | Δ con−senza |",
        "|---|---:|---:|---:|",
    ])
    for campo, voce in dati["annuale"]["valori"].items():
        righe.append(f"| {campo.replace('_', ' ')} | {voce['senza_fisso']} | {voce['con_fisso']} | {voce['delta']:+} |")
    righe.extend(["", "### Distanza delle ripetizioni", "", "| Fascia | Senza | Con | Δ |", "|---|---:|---:|---:|"])
    for campo, voce in dati["annuale"]["distanze_riusi"].items():
        righe.append(f"| {campo.replace('_', ' ')} | {voce['senza_fisso']} | {voce['con_fisso']} | {voce['delta']:+} |")
    righe.extend(["", "### Genere misto", "", "| Indicatore | Senza | Con | Δ |", "|---|---:|---:|---:|"])
    for campo, voce in dati["annuale"]["genere_misto"].items():
        righe.append(f"| {campo.replace('_', ' ')} | {voce['senza_fisso']} | {voce['con_fisso']} | {voce['delta']:+} |")

    righe.extend(["", "## 3. Andamento mese per mese", ""])
    for mese in dati["mesi"]:
        righe.extend([
            f"### Mese {mese['mese']}",
            "",
            f"Adiacenze comuni: **{mese['conteggi_adiacenze']['comuni']}**; "
            f"solo senza FISSO: **{mese['conteggi_adiacenze']['solo_senza_fisso']}**; "
            f"solo con FISSO: **{mese['conteggi_adiacenze']['solo_con_fisso']}**.",
            "",
            "| Indicatore | Senza | Con | Δ |",
            "|---|---:|---:|---:|",
        ])
        for campo, voce in mese["valori"].items():
            righe.append(f"| {campo.replace('_', ' ')} | {voce['senza_fisso']} | {voce['con_fisso']} | {voce['delta']:+} |")
        if mese["adiacenze_solo_senza_fisso"]:
            righe.extend(["", "**Adiacenze presenti soltanto senza FISSO**"])
            for evento in mese["adiacenze_solo_senza_fisso"]:
                righe.append(f"- {' — '.join(evento['studenti'])} ({evento['ruolo']})")
        if mese["adiacenze_solo_con_fisso"]:
            righe.extend(["", "**Adiacenze presenti soltanto con FISSO**"])
            for evento in mese["adiacenze_solo_con_fisso"]:
                righe.append(f"- {' — '.join(evento['studenti'])} ({evento['ruolo']})")
        if mese.get("vicino_fisso"):
            righe.append(f"\nVicino del FISSO: **{mese['vicino_fisso'].get('studente')}**.")
        righe.append("")

    righe.extend([
        "## 4. Distribuzione per studente",
        "",
        "| Studente | Riusi senza | Riusi con | Δ | Incarichi vicino FISSO |",
        "|---|---:|---:|---:|---:|",
    ])
    for studente in dati["annuale"]["studenti"]:
        riusi = studente["valori"]["riusi_coinvolgenti"]
        incarichi = studente["valori"]["incarichi_vicino_fisso"]["con_fisso"]
        righe.append(
            f"| {studente['studente']} | {riusi['senza_fisso']} | {riusi['con_fisso']} | {riusi['delta']:+} | {incarichi} |"
        )

    righe.extend(["", "## 5. Distribuzione del vicino del FISSO", ""])
    ruolo = dati["annuale"]["distribuzione_vicino_fisso"]
    if ruolo:
        for voce in ruolo:
            mesi = ", ".join(str(x) for x in voce["mesi"])
            righe.append(f"- **{voce['studente']}**: {voce['numero_incarichi']} incarichi; mesi {mesi}.")
    else:
        righe.append("Nessun incarico registrato.")

    righe.extend([
        "",
        "## 6. Limite interpretativo",
        "",
        dati.get("nota_interpretativa", ""),
        "",
        "Il rapporto descrive associazioni osservate fra le due traiettorie. Non dichiara automaticamente che il FISSO abbia migliorato o peggiorato l’annata.",
        "",
    ])
    return "\n".join(righe) + "\n"


def pubblica_confronto_appaiato(
    confronto: ConfrontoAppaiato,
    directory_destinazione: str | os.PathLike[str],
    *,
    consenti_sostituzione: bool = False,
) -> EsitoPubblicazioneConfronto:
    """Pubblica CONFRONTO.json, Markdown e validazione in modo transazionale."""
    dati_vivi = rendi_json_stabile(confronto)
    esito_vivo = valida_dati_confronto(dati_vivi)
    if not esito_vivo.valido:
        raise ErroreConfrontoAppaiato(
            "Confronto vivo non valido: " + ", ".join(p.codice for p in esito_vivo.problemi)
        )
    destinazione = Path(directory_destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if destinazione.exists() and not consenti_sostituzione:
        raise FileExistsError(f"La directory di confronto esiste già: {destinazione}")
    temporanea = Path(tempfile.mkdtemp(prefix=f".{destinazione.name}.", dir=destinazione.parent))
    backup: Path | None = None
    try:
        percorso_json = temporanea / "CONFRONTO.json"
        percorso_md = temporanea / "CONFRONTO.md"
        percorso_validazione = temporanea / "VALIDAZIONE.json"
        scrivi_json_atomico(percorso_json, confronto)
        dati = leggi_json(percorso_json)
        esito = valida_dati_confronto(dati)
        scrivi_json_atomico(
            percorso_validazione,
            {
                "confronto_id": confronto.confronto_id,
                "fase": "rilettura_confronto_json",
                "valido": esito.valido,
                "numero_errori": len(esito.problemi),
                "problemi": [rendi_json_stabile(p) for p in esito.problemi],
            },
        )
        if not esito.valido:
            raise ErroreConfrontoAppaiato(
                "CONFRONTO.json riletto non valido: " + ", ".join(p.codice for p in esito.problemi)
            )
        scrivi_testo_atomico(percorso_md, rendi_confronto_markdown(dati, valida=False))
        if destinazione.exists():
            backup = destinazione.with_name(f".{destinazione.name}.backup")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(destinazione, backup)
        os.replace(temporanea, destinazione)
        if backup is not None:
            shutil.rmtree(backup)
        return EsitoPubblicazioneConfronto(
            confronto_id=confronto.confronto_id,
            directory=os.fspath(destinazione),
            confronto_json=os.fspath(destinazione / "CONFRONTO.json"),
            confronto_markdown=os.fspath(destinazione / "CONFRONTO.md"),
            validazione_json=os.fspath(destinazione / "VALIDAZIONE.json"),
            sha256_confronto_json=firma_file_sha256(destinazione / "CONFRONTO.json"),
            sha256_confronto_markdown=firma_file_sha256(destinazione / "CONFRONTO.md"),
            sha256_validazione_json=firma_file_sha256(destinazione / "VALIDAZIONE.json"),
        )
    except Exception:
        shutil.rmtree(temporanea, ignore_errors=True)
        if backup is not None and backup.exists() and not destinazione.exists():
            os.replace(backup, destinazione)
        raise


__all__ = [
    "ConfrontoAppaiato",
    "ErroreConfrontoAppaiato",
    "EsitoPubblicazioneConfronto",
    "EsitoValidazioneConfronto",
    "ProblemaAppaiamento",
    "costruisci_confronto_appaiato",
    "pubblica_confronto_appaiato",
    "rendi_confronto_markdown",
    "valida_dati_confronto",
]
