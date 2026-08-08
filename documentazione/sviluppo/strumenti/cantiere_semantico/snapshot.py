"""Snapshot canonico e verificabile delle rotazioni iniziali.

Il modulo osserva esclusivamente strutture JSON già presenti nella
``config_data`` di PostiPerfetti. Non importa Qt, non salva la configurazione
produttiva e non riduce i contatori a semplici insiemi.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .identita import chiave_adiacenza, crea_identificatore
from .modelli import (
    CanaleRotazione,
    SnapshotRotazioni,
    VoceRotazione,
    VoceVicinoFisso,
)
from .serializzazione import firma_json_sha256, leggi_json, scrivi_json_atomico


CHIAVE_COPPIE = "coppie_da_evitare"
CHIAVE_TERZETTI = "adiacenze_terzetti_da_evitare"
CHIAVE_VICINI_FISSO = "studenti_vicino_fisso_contatore"
CHIAVE_STORICO = "storico_assegnazioni"
CHIAVI_RICHIESTE = {
    CHIAVE_COPPIE,
    CHIAVE_TERZETTI,
    CHIAVE_VICINI_FISSO,
    CHIAVE_STORICO,
}


class ErroreSnapshot(ValueError):
    """Segnala una configurazione non fotografabile senza correzioni implicite."""



def _nome(valore: Any, contesto: str) -> str:
    if not isinstance(valore, str):
        raise ErroreSnapshot(f"{contesto}: atteso un nome testuale.")
    testo = " ".join(valore.strip().split())
    if not testo:
        raise ErroreSnapshot(f"{contesto}: il nome non può essere vuoto.")
    return testo



def _intero_non_negativo(valore: Any, contesto: str) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ErroreSnapshot(f"{contesto}: atteso un intero non negativo.")
    return valore



def _intero_positivo(valore: Any, contesto: str) -> int:
    numero = _intero_non_negativo(valore, contesto)
    if numero < 1:
        raise ErroreSnapshot(f"{contesto}: atteso un intero positivo.")
    return numero



def _mapping(valore: Any, contesto: str) -> Mapping[str, Any]:
    if not isinstance(valore, Mapping):
        raise ErroreSnapshot(f"{contesto}: atteso un oggetto JSON.")
    return valore



def _sequenza(valore: Any, contesto: str) -> Sequence[Any]:
    if isinstance(valore, (str, bytes, bytearray)) or not isinstance(valore, Sequence):
        raise ErroreSnapshot(f"{contesto}: attesa una lista JSON.")
    return valore



def _riferimento_storico(assegnazione: Mapping[str, Any], indice: int) -> str:
    nome = str(assegnazione.get("nome") or f"Assegnazione {indice}").strip()
    data = str(assegnazione.get("data_creazione") or "data non disponibile").strip()
    progressivo = assegnazione.get("progressivo")
    parti = [nome, data]
    if isinstance(progressivo, int) and not isinstance(progressivo, bool):
        parti.append(f"progressivo={progressivo}")
    return " | ".join(parti)



def _ultimi_riferimenti_storici(
    storico: Sequence[Any],
) -> tuple[
    dict[tuple[str, str], str],
    dict[tuple[str, str], str],
    dict[str, str],
]:
    """Ricostruisce l'ultimo riferimento disponibile per i tre canali."""
    coppie: dict[tuple[str, str], str] = {}
    terzetti: dict[tuple[str, str], str] = {}
    vicini_fisso: dict[str, str] = {}

    for indice, voce_grezza in enumerate(storico, start=1):
        assegnazione = _mapping(voce_grezza, f"storico[{indice}]")
        modo = assegnazione.get("modo")
        riferimento = _riferimento_storico(assegnazione, indice)

        if modo == "coppie":
            layout = _sequenza(assegnazione.get("layout", []), f"storico[{indice}].layout")
            for pos, riga_grezza in enumerate(layout, start=1):
                riga = _mapping(riga_grezza, f"storico[{indice}].layout[{pos}]")
                tipo = riga.get("tipo")
                studente_raw = riga.get("studente")
                if not isinstance(studente_raw, str) or not studente_raw.strip():
                    continue
                studente = _nome(studente_raw, f"storico[{indice}].layout[{pos}].studente")

                if tipo == "coppia":
                    compagno_raw = riga.get("compagno")
                    if isinstance(compagno_raw, str) and compagno_raw.strip():
                        compagno = _nome(
                            compagno_raw,
                            f"storico[{indice}].layout[{pos}].compagno",
                        )
                        coppie[chiave_adiacenza(studente, compagno)] = riferimento

                elif tipo == "trio" and riga.get("posizione_trio") == "centrale":
                    compagni = _sequenza(
                        riga.get("compagni_trio", []),
                        f"storico[{indice}].layout[{pos}].compagni_trio",
                    )
                    for numero, compagno_raw in enumerate(compagni, start=1):
                        compagno = _nome(
                            compagno_raw,
                            f"storico[{indice}].layout[{pos}].compagni_trio[{numero}]",
                        )
                        coppie[chiave_adiacenza(studente, compagno)] = riferimento

                elif tipo == "fisso":
                    adiacente_raw = riga.get("adiacente")
                    if isinstance(adiacente_raw, str) and adiacente_raw.strip():
                        adiacente = _nome(
                            adiacente_raw,
                            f"storico[{indice}].layout[{pos}].adiacente",
                        )
                        vicini_fisso[adiacente] = riferimento

        elif modo == "terzetti":
            gruppi = _sequenza(
                assegnazione.get("gruppi", []),
                f"storico[{indice}].gruppi",
            )
            for pos, gruppo_grezzo in enumerate(gruppi, start=1):
                gruppo = _mapping(gruppo_grezzo, f"storico[{indice}].gruppi[{pos}]")
                membri_raw = _sequenza(
                    gruppo.get("membri", []),
                    f"storico[{indice}].gruppi[{pos}].membri",
                )
                membri = [
                    _nome(nome, f"storico[{indice}].gruppi[{pos}].membri")
                    for nome in membri_raw
                ]
                for nome_a, nome_b in zip(membri, membri[1:]):
                    terzetti[chiave_adiacenza(nome_a, nome_b)] = riferimento

    return coppie, terzetti, vicini_fisso



def _leggi_blacklist(
    dati: Mapping[str, Any],
    chiave: str,
    tipo_atteso: str,
    canale: CanaleRotazione,
    riferimenti: Mapping[tuple[str, str], str],
) -> tuple[VoceRotazione, ...]:
    lista = _sequenza(dati[chiave], chiave)
    viste: set[tuple[str, str]] = set()
    risultato: list[VoceRotazione] = []

    for indice, voce_grezza in enumerate(lista, start=1):
        voce = _mapping(voce_grezza, f"{chiave}[{indice}]")
        if voce.get("tipo") != tipo_atteso:
            raise ErroreSnapshot(
                f"{chiave}[{indice}].tipo: atteso {tipo_atteso!r}."
            )
        studenti_raw = _sequenza(voce.get("studenti"), f"{chiave}[{indice}].studenti")
        if len(studenti_raw) != 2:
            raise ErroreSnapshot(
                f"{chiave}[{indice}].studenti: occorrono esattamente due nomi."
            )
        chiave_coppia = chiave_adiacenza(
            _nome(studenti_raw[0], f"{chiave}[{indice}].studenti[0]"),
            _nome(studenti_raw[1], f"{chiave}[{indice}].studenti[1]"),
        )
        if chiave_coppia in viste:
            raise ErroreSnapshot(
                f"{chiave}[{indice}]: adiacenza duplicata {chiave_coppia!r}."
            )
        viste.add(chiave_coppia)
        usi = _intero_positivo(voce.get("volte_usata"), f"{chiave}[{indice}].volte_usata")
        risultato.append(
            VoceRotazione(
                canale=canale,
                studenti=chiave_coppia,
                usi_precedenti=usi,
                ultimo_riferimento_disponibile=riferimenti.get(chiave_coppia),
            )
        )

    return tuple(sorted(risultato, key=lambda elemento: elemento.studenti))



def _leggi_vicini_fisso(
    dati: Mapping[str, Any],
    riferimenti: Mapping[str, str],
) -> tuple[VoceVicinoFisso, ...]:
    contatore = _mapping(dati[CHIAVE_VICINI_FISSO], CHIAVE_VICINI_FISSO)
    risultato: list[VoceVicinoFisso] = []
    nomi_visti: set[str] = set()
    for nome_raw, valore in contatore.items():
        nome = _nome(nome_raw, f"{CHIAVE_VICINI_FISSO}.chiave")
        if nome in nomi_visti:
            raise ErroreSnapshot(
                f"{CHIAVE_VICINI_FISSO}: nome duplicato dopo la normalizzazione: {nome!r}."
            )
        nomi_visti.add(nome)
        usi = _intero_non_negativo(valore, f"{CHIAVE_VICINI_FISSO}[{nome!r}]")
        risultato.append(
            VoceVicinoFisso(
                studente=nome,
                usi_precedenti=usi,
                ultimo_riferimento_disponibile=riferimenti.get(nome),
            )
        )
    return tuple(sorted(risultato, key=lambda elemento: elemento.studente))



def _contenuto_firmato(snapshot: SnapshotRotazioni) -> dict[str, Any]:
    return {
        "coppie": snapshot.coppie,
        "terzetti": snapshot.terzetti,
        "vicini_fisso": snapshot.vicini_fisso,
    }



def firma_snapshot(snapshot: SnapshotRotazioni) -> str:
    """Calcola la firma del contenuto, escludendo il campo ``sha256``."""
    return firma_json_sha256(_contenuto_firmato(snapshot))



def crea_snapshot_rotazioni(config_data: Mapping[str, Any]) -> SnapshotRotazioni:
    """Crea una fotografia completa e canonica delle rotazioni iniziali."""
    dati = _mapping(config_data, "config_data")
    mancanti = sorted(CHIAVI_RICHIESTE - set(dati))
    if mancanti:
        raise ErroreSnapshot(
            "config_data incompleta; mancano: " + ", ".join(mancanti) + "."
        )

    storico = _sequenza(dati[CHIAVE_STORICO], CHIAVE_STORICO)
    ultimi_coppie, ultimi_terzetti, ultimi_vicini = _ultimi_riferimenti_storici(storico)

    snapshot_senza_firma = SnapshotRotazioni(
        coppie=_leggi_blacklist(
            dati,
            CHIAVE_COPPIE,
            "coppia",
            CanaleRotazione.COPPIE,
            ultimi_coppie,
        ),
        terzetti=_leggi_blacklist(
            dati,
            CHIAVE_TERZETTI,
            "adiacenza",
            CanaleRotazione.TERZETTI,
            ultimi_terzetti,
        ),
        vicini_fisso=_leggi_vicini_fisso(dati, ultimi_vicini),
    )
    digest = firma_snapshot(snapshot_senza_firma)
    return SnapshotRotazioni(
        coppie=snapshot_senza_firma.coppie,
        terzetti=snapshot_senza_firma.terzetti,
        vicini_fisso=snapshot_senza_firma.vicini_fisso,
        sha256=digest,
    )



def verifica_snapshot(snapshot: SnapshotRotazioni) -> None:
    """Rifiuta snapshot privi di firma o con firma non coerente."""
    if snapshot.sha256 is None:
        raise ErroreSnapshot("Lo snapshot non contiene la firma SHA-256.")
    attesa = firma_snapshot(snapshot)
    if snapshot.sha256 != attesa:
        raise ErroreSnapshot(
            f"Firma snapshot non coerente: dichiarata {snapshot.sha256}, attesa {attesa}."
        )



def crea_stato_iniziale_id(snapshot: SnapshotRotazioni) -> str:
    """Crea l'identificatore stabile usato dal protocollo dei run."""
    verifica_snapshot(snapshot)
    return crea_identificatore("stato", snapshot.sha256)



def snapshot_da_file_configurazione(percorso: str | Path) -> SnapshotRotazioni:
    dati = leggi_json(percorso)
    return crea_snapshot_rotazioni(dati)



def scrivi_snapshot(percorso: str | Path, snapshot: SnapshotRotazioni) -> str:
    verifica_snapshot(snapshot)
    payload = {
        "stato_iniziale_id": crea_stato_iniziale_id(snapshot),
        "snapshot": snapshot,
    }
    return scrivi_json_atomico(percorso, payload)
