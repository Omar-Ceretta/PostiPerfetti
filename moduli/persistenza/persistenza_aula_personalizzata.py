# -*- coding: utf-8 -*-
"""Persistenza autonoma delle bozze dell'Aula personalizzata.

Il file ``postiperfetti_aule_personalizzate.json`` e' separato dallo Storico.
Ogni Layout e' identificato dagli studenti e dall'identita' dello studente
FISSO; varianti con FISSO differente non si sovrascrivono.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import unicodedata
from typing import Iterable, Mapping, Any

from moduli.dominio.aula_personalizzata import (
    BloccoBozzaPersonalizzata,
    ModelloAulaPersonalizzata,
)
from moduli.percorsi import get_state_path


VERSIONE_ARCHIVIO_AULE_PERSONALIZZATE = 2
TIPO_ARCHIVIO_AULE_PERSONALIZZATE = "postiperfetti_aule_personalizzate"
NOME_FILE_ARCHIVIO_AULE_PERSONALIZZATE = "postiperfetti_aule_personalizzate.json"


@dataclass(frozen=True, slots=True)
class BozzaAulaPersistita:
    """Bozza ricostruita insieme all'identita' della classe che l'ha generata."""

    fingerprint: str
    file_origine: str
    nomi_studenti: tuple[str, ...]
    studente_fisso: str
    numero_studenti: int
    aggiornata_il: str
    modello: ModelloAulaPersonalizzata


@dataclass(frozen=True, slots=True)
class CorrispondenzaBozzaAula:
    """Miglior match prudente fra la classe caricata e una bozza salvata."""

    bozza: BozzaAulaPersistita
    nomi_in_comune: tuple[str, ...]



def _normalizza_nome(nome: object) -> str:
    testo = unicodedata.normalize("NFKC", str(nome))
    return " ".join(testo.split()).casefold()


def _nomi_puliti(nomi_studenti: Iterable[object]) -> tuple[str, ...]:
    nomi = tuple(" ".join(str(nome).split()) for nome in nomi_studenti)
    if not nomi or any(not nome for nome in nomi):
        raise ValueError("La classe deve contenere nomi studente non vuoti.")
    return nomi


def _normalizza_fisso(studente_fisso: object | None, nomi: tuple[str, ...]) -> str:
    """Normalizza il FISSO e verifica che appartenga alla classe."""
    fisso = " ".join(str(studente_fisso or "").split())
    if fisso and _normalizza_nome(fisso) not in {_normalizza_nome(n) for n in nomi}:
        raise ValueError("Lo studente FISSO deve appartenere alla classe.")
    return fisso


def fingerprint_classe(
    nomi_studenti: Iterable[object], *, studente_fisso: str | None = None,
) -> str:
    """Identita' stabile della variante: studenti + FISSO, non nome del file."""
    nomi = _nomi_puliti(nomi_studenti)
    canonici = sorted(_normalizza_nome(nome) for nome in nomi)
    fisso = _normalizza_nome(_normalizza_fisso(studente_fisso, nomi))
    materiale = json.dumps([canonici, fisso], ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(materiale).hexdigest()


def _chiavi_esatte(dati: Mapping[str, Any], attese: set[str], contesto: str) -> None:
    presenti = set(dati)
    mancanti = sorted(attese - presenti)
    inattese = sorted(presenti - attese)
    if mancanti or inattese:
        parti = []
        if mancanti:
            parti.append("mancano: " + ", ".join(mancanti))
        if inattese:
            parti.append("non previste: " + ", ".join(inattese))
        raise ValueError(f"{contesto}: formato non valido ({'; '.join(parti)}).")


def _modello_a_json(modello: ModelloAulaPersonalizzata) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(modello, ModelloAulaPersonalizzata):
        raise TypeError("modello deve essere un ModelloAulaPersonalizzata.")
    blocchi = [
        {
            "id": blocco.id,
            "capienza": blocco.capienza,
            "riga": blocco.riga,
            "colonna": blocco.colonna,
            "zona": blocco.zona,
            "ids_posti": list(blocco.ids_posti),
        }
        for blocco in modello.blocchi
    ]
    ancora = None
    if modello.ancora_fisso is not None:
        ancora = {
            "id_blocco": modello.ancora_fisso[0],
            "indice_posto": modello.ancora_fisso[1],
        }
    return blocchi, ancora


def _modello_da_record(record: Mapping[str, Any]) -> ModelloAulaPersonalizzata:
    blocchi_json = record["blocchi"]
    if not isinstance(blocchi_json, list):
        raise ValueError("La chiave 'blocchi' deve essere una lista.")

    blocchi: list[BloccoBozzaPersonalizzata] = []
    for indice, item in enumerate(blocchi_json, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Blocco {indice}: atteso un oggetto JSON.")
        _chiavi_esatte(
            item,
            {"id", "capienza", "riga", "colonna", "zona", "ids_posti"},
            f"Blocco {indice}",
        )
        ids_posti = item["ids_posti"]
        if not isinstance(ids_posti, list):
            raise ValueError(f"Blocco {indice}: 'ids_posti' deve essere una lista.")
        blocchi.append(BloccoBozzaPersonalizzata(
            id=item["id"],
            capienza=item["capienza"],
            riga=item["riga"],
            colonna=item["colonna"],
            zona=item["zona"],
            ids_posti=tuple(ids_posti),
        ))

    spazi = record.get("spazi", [])
    if not isinstance(spazi, list):
        raise ValueError("spazi deve essere una lista.")
    modello = ModelloAulaPersonalizzata(
        blocchi, griglia_fissa=record.get("griglia_fissa", False), spazi=spazi)
    if modello.griglia_fissa:
        from moduli.dominio.griglia_layout_fissa import valida_griglia_fissa
        valida_griglia_fissa(modello)
    ancora = record["ancora_fisso"]
    if ancora is not None:
        if not isinstance(ancora, Mapping):
            raise ValueError("'ancora_fisso' deve essere null oppure un oggetto JSON.")
        _chiavi_esatte(
            ancora,
            {"id_blocco", "indice_posto"},
            "Ancora FISSO",
        )
        modello.imposta_ancora_fisso(
            ancora["id_blocco"],
            ancora["indice_posto"],
        )

    # Costruisce lo schema senza legarlo alla classe corrente: e' una guardia
    # strutturale aggiuntiva sul contenuto appena letto.
    if modello.blocchi:
        modello.costruisci_schema()
    return modello


def _record_a_bozza(fingerprint: str, record: Mapping[str, Any]) -> BozzaAulaPersistita:
    if not isinstance(record, Mapping):
        raise ValueError("Ogni aula salvata deve essere un oggetto JSON.")
    _chiavi_esatte(
        record,
        {
            "file_origine",
            "nomi_studenti",
            "studente_fisso",
            "numero_studenti",
            "aggiornata_il",
            "blocchi",
            "ancora_fisso",
        } | ({"griglia_fissa"} if "griglia_fissa" in record else set())
          | ({"spazi"} if "spazi" in record else set()),
        "Bozza Aula personalizzata",
    )
    nomi = record["nomi_studenti"]
    if not isinstance(nomi, list):
        raise ValueError("'nomi_studenti' deve essere una lista.")
    nomi_puliti = _nomi_puliti(nomi)
    numero = record["numero_studenti"]
    if isinstance(numero, bool) or not isinstance(numero, int) or numero < 1:
        raise ValueError("'numero_studenti' deve essere un intero positivo.")
    if numero != len(nomi_puliti):
        raise ValueError("'numero_studenti' non coincide con 'nomi_studenti'.")
    studente_fisso = _normalizza_fisso(record["studente_fisso"], nomi_puliti)
    fingerprint_atteso = fingerprint_classe(nomi_puliti, studente_fisso=studente_fisso)
    if fingerprint != fingerprint_atteso:
        raise ValueError("Fingerprint della classe non coerente con i nomi salvati.")
    file_origine = str(record["file_origine"]).strip()
    if not file_origine:
        raise ValueError("'file_origine' non puo' essere vuoto.")
    aggiornata_il = str(record["aggiornata_il"]).strip()
    if not aggiornata_il:
        raise ValueError("'aggiornata_il' non puo' essere vuoto.")
    return BozzaAulaPersistita(
        fingerprint=fingerprint,
        file_origine=file_origine,
        nomi_studenti=nomi_puliti,
        studente_fisso=studente_fisso,
        numero_studenti=numero,
        aggiornata_il=aggiornata_il,
        modello=_modello_da_record(record),
    )


class ArchivioAulePersonalizzate:
    """Legge e scrive in modo atomico le bozze dell'editor Personalizzata."""

    def __init__(self, percorso: str | os.PathLike[str] | None = None):
        self.percorso = os.fspath(
            percorso
            if percorso is not None
            else get_state_path(
                NOME_FILE_ARCHIVIO_AULE_PERSONALIZZATE,
                crea_genitori=True,
            )
        )
        self.avviso_caricamento: str | None = None
        self._dati = self._carica()

    @staticmethod
    def _vuoto() -> dict[str, Any]:
        return {
            "schema_versione": VERSIONE_ARCHIVIO_AULE_PERSONALIZZATE,
            "tipo": TIPO_ARCHIVIO_AULE_PERSONALIZZATE,
            "aule": {},
        }

    def _valida_archivio(self, dati: object) -> dict[str, Any]:
        if not isinstance(dati, Mapping):
            raise ValueError("L'archivio aule deve essere un oggetto JSON.")
        _chiavi_esatte(dati, {"schema_versione", "tipo", "aule"}, "Archivio aule")
        if dati["schema_versione"] != VERSIONE_ARCHIVIO_AULE_PERSONALIZZATE:
            raise ValueError(
                "Versione archivio aule non supportata: "
                f"{dati['schema_versione']!r}."
            )
        if dati["tipo"] != TIPO_ARCHIVIO_AULE_PERSONALIZZATE:
            raise ValueError(f"Tipo archivio aule non valido: {dati['tipo']!r}.")
        aule = dati["aule"]
        if not isinstance(aule, Mapping):
            raise ValueError("La chiave 'aule' deve essere un oggetto JSON.")
        for fingerprint, record in aule.items():
            if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                raise ValueError("Fingerprint aula non valido.")
            _record_a_bozza(fingerprint, record)
        return {
            "schema_versione": VERSIONE_ARCHIVIO_AULE_PERSONALIZZATE,
            "tipo": TIPO_ARCHIVIO_AULE_PERSONALIZZATE,
            "aule": dict(aule),
        }

    def _preserva_corrotto(self) -> str | None:
        sorgente = Path(self.percorso)
        if not sorgente.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destinazione = sorgente.with_name(
            f"{sorgente.stem}.corrotto-{timestamp}{sorgente.suffix}"
        )
        try:
            os.replace(sorgente, destinazione)
        except OSError:
            return None
        return os.fspath(destinazione)

    def _carica(self) -> dict[str, Any]:
        if not os.path.exists(self.percorso):
            return self._vuoto()
        try:
            with open(self.percorso, "r", encoding="utf-8") as file:
                dati = json.load(file)
            return self._valida_archivio(dati)
        except Exception as exc:
            preservato = self._preserva_corrotto()
            dettaglio = f" Copia conservata in: {preservato}" if preservato else ""
            self.avviso_caricamento = (
                "Il file delle Aule personalizzate non era leggibile; "
                "PostiPerfetti riparte con un archivio vuoto." + dettaglio +
                f" Errore: {exc}"
            )
            return self._vuoto()

    def _scrivi(self, dati: dict[str, Any]) -> None:
        """Pubblica la copia in memoria soltanto dopo il commit su disco."""
        self._valida_archivio(dati)
        percorso = Path(self.percorso)
        percorso.parent.mkdir(parents=True, exist_ok=True)
        temporaneo = percorso.with_name(percorso.name + ".tmp")
        try:
            with open(temporaneo, "w", encoding="utf-8", newline="\n") as file:
                json.dump(dati, file, ensure_ascii=False, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporaneo, percorso)
        except BaseException:
            # La pulizia non deve nascondere l'errore che impedisce il salvataggio.
            try:
                temporaneo.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self._dati = dati

    def _bozze(self) -> tuple[BozzaAulaPersistita, ...]:
        return tuple(
            _record_a_bozza(fingerprint, record)
            for fingerprint, record in self._dati["aule"].items()
        )

    def salva(
        self,
        *,
        file_origine: str,
        nomi_studenti: Iterable[object],
        modello: ModelloAulaPersonalizzata,
        studente_fisso: str | None = None,
    ) -> None:
        nomi = _nomi_puliti(nomi_studenti)
        fisso = _normalizza_fisso(studente_fisso, nomi)
        fingerprint = fingerprint_classe(nomi, studente_fisso=fisso)
        dati = deepcopy(self._dati)
        if not modello.blocchi and not modello.spazi:
            if dati["aule"].pop(fingerprint, None) is not None:
                self._scrivi(dati)
            return
        blocchi, ancora = _modello_a_json(modello)
        dati["aule"][fingerprint] = {
            "file_origine": str(file_origine).strip(),
            "nomi_studenti": list(nomi),
            "studente_fisso": fisso,
            "numero_studenti": len(nomi),
            "aggiornata_il": datetime.now().isoformat(timespec="seconds"),
            "blocchi": blocchi,
            "ancora_fisso": ancora,
            **({"griglia_fissa": True} if modello.griglia_fissa else {}),
            **({"spazi": [list(p) for p in modello.spazi]} if modello.spazi else {}),
        }
        self._scrivi(dati)

    def trova_esatta(
        self, nomi_studenti: Iterable[object], *, studente_fisso: str | None = None,
    ) -> BozzaAulaPersistita | None:
        fingerprint = fingerprint_classe(nomi_studenti, studente_fisso=studente_fisso)
        record = self._dati["aule"].get(fingerprint)
        if record is None:
            return None
        return _record_a_bozza(fingerprint, record)

    def trova_per_file_origine(
        self, file_origine: str, *, studente_fisso: str | None = None,
    ) -> BozzaAulaPersistita | None:
        cercato = str(file_origine).strip()
        fisso = _normalizza_nome(studente_fisso or "")
        candidate = [
            bozza for bozza in self._bozze()
            if bozza.file_origine == cercato
            and _normalizza_nome(bozza.studente_fisso) == fisso
        ]
        if not candidate:
            return None
        return max(candidate, key=lambda bozza: bozza.aggiornata_il)

    def trova_simile(
        self,
        nomi_studenti: Iterable[object],
        *,
        soglia_minima: int = 5,
        studente_fisso: str | None = None,
        file_origine: str | None = None,
    ) -> CorrispondenzaBozzaAula | None:
        correnti = _nomi_puliti(nomi_studenti)
        correnti_norm = {_normalizza_nome(nome): nome for nome in correnti}
        candidati: list[tuple[int, int, int, str, BozzaAulaPersistita, tuple[str, ...]]] = []
        fisso = _normalizza_nome(studente_fisso or "")
        for bozza in self._bozze():
            salvati_norm = {_normalizza_nome(nome): nome for nome in bozza.nomi_studenti}
            chiavi_comuni = set(correnti_norm) & set(salvati_norm)
            # Anche una classe piccola con gli stessi studenti, ma FISSO
            # diverso, deve poter proporre il recupero con conferma.
            stessi_studenti = (
                len(correnti_norm) == len(salvati_norm)
                and chiavi_comuni == set(correnti_norm)
            )
            if len(chiavi_comuni) < soglia_minima and not stessi_studenti:
                continue
            nomi_comuni = tuple(sorted(correnti_norm[k] for k in chiavi_comuni))
            candidati.append((
                len(chiavi_comuni),
                int(_normalizza_nome(bozza.studente_fisso) == fisso),
                int(bozza.file_origine == str(file_origine or "")),
                bozza.aggiornata_il,
                bozza,
                nomi_comuni,
            ))
        if not candidati:
            return None
        # Fra piu' bozze compatibili preferisce FISSO uguale e file di origine;
        # la conferma dell'utente resta obbligatoria per qualunque match non esatto.
        candidati.sort(key=lambda elemento: elemento[:4], reverse=True)
        migliore = candidati[0]
        return CorrispondenzaBozzaAula(migliore[4], migliore[5])

    def ricollega(
        self,
        bozza: BozzaAulaPersistita,
        *,
        file_origine: str,
        nomi_studenti: Iterable[object],
        modello: ModelloAulaPersonalizzata | None = None,
        studente_fisso: str | None = None,
    ) -> None:
        # Copia, non sposta: la variante della classe di origine resta intatta.
        nomi = _nomi_puliti(nomi_studenti)
        fisso = _normalizza_fisso(studente_fisso, nomi)
        modello_finale = modello if modello is not None else bozza.modello
        blocchi, ancora = _modello_a_json(modello_finale)
        nuovo_fingerprint = fingerprint_classe(nomi, studente_fisso=fisso)
        dati = deepcopy(self._dati)
        dati["aule"][nuovo_fingerprint] = {
            "file_origine": str(file_origine).strip(),
            "nomi_studenti": list(nomi),
            "studente_fisso": fisso,
            "numero_studenti": len(nomi),
            "aggiornata_il": datetime.now().isoformat(timespec="seconds"),
            "blocchi": blocchi,
            "ancora_fisso": ancora,
            **({"griglia_fissa": True} if modello_finale.griglia_fissa else {}),
            **({"spazi": [list(p) for p in modello_finale.spazi]} if modello_finale.spazi else {}),
        }
        self._scrivi(dati)

    @property
    def numero_bozze(self) -> int:
        return len(self._dati["aule"])
