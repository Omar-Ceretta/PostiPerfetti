"""Modelli canonici immutabili dell'osservatore semantico annuale.

I modelli di questo modulo non importano né Qt né i motori produttivi. Sono il
vocabolario condiviso da protocollo, osservatore, validatore e renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


SCHEMA_OUTPUT_VERSIONE = "0.1.0"
PROTOCOLLO_VERSIONE = "0.1"
OSSERVATORE_VERSIONE = "1.0.0"


class Modalita(str, Enum):
    COPPIE = "coppie"
    TERZETTI = "terzetti"


class CondizioneRun(str, Enum):
    SENZA_FISSO = "senza_fisso"
    CON_FISSO = "con_fisso"


class StatoRun(str, Enum):
    COMPLETO = "completo"
    PARZIALE = "parziale"
    FALLITO = "fallito"
    ANNULLATO = "annullato"
    NON_ESEGUITO = "non_eseguito"
    INVALIDO = "invalido"


class TipoGruppo(str, Enum):
    COPPIA = "coppia"
    TRIO = "trio"
    TERZETTO = "terzetto"
    QUARTETTO = "quartetto"


class FunzioneGruppo(str, Enum):
    ORDINARIO = "ordinario"
    BLOCCO_FINALE = "blocco_finale"
    BLOCCO_FISSO = "blocco_fisso"


class RuoloAdiacenza(str, Enum):
    COPPIA_ORDINARIA = "coppia_ordinaria"
    COPPIA_FINALE_TERZETTI = "coppia_finale_terzetti"
    TRIO_MODALITA_COPPIE = "trio_modalita_coppie"
    TERZETTO = "terzetto"
    QUARTETTO = "quartetto"
    VICINO_FISSO = "vicino_fisso"


class CanaleRotazione(str, Enum):
    COPPIE = "coppie"
    TERZETTI = "terzetti"
    VICINO_FISSO = "vicino_fisso"


class OrigineUltimoUso(str, Enum):
    NESSUNO = "nessuno"
    STORICO_INIZIALE = "storico_iniziale"
    ANNATA_CORRENTE = "annata_corrente"


class FasciaRipetizione(str, Enum):
    PRIMA_COMPARSA = "prima_comparsa"
    PRIMA_RIPETIZIONE = "prima_ripetizione"
    SECONDA_RIPETIZIONE = "seconda_ripetizione"
    TERZA_O_ULTERIORE = "terza_o_ulteriore"


class GravitaValidazione(str, Enum):
    ERRORE = "errore"
    AVVISO = "avviso"


def _testo_non_vuoto(valore: str, campo: str) -> str:
    testo = str(valore).strip()
    if not testo:
        raise ValueError(f"{campo} non può essere vuoto.")
    return testo


def _intero_positivo(valore: int, campo: str) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 1:
        raise ValueError(f"{campo} deve essere un intero positivo.")
    return valore


def _intero_non_negativo(valore: int, campo: str) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ValueError(f"{campo} deve essere un intero non negativo.")
    return valore


def _livello(valore: int, campo: str) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or not 0 <= valore <= 3:
        raise ValueError(f"{campo} deve essere un intero compreso fra 0 e 3.")
    return valore


def _numero_finito_non_negativo(valore: float | None, campo: str) -> float | None:
    if valore is None:
        return None
    numero = float(valore)
    if not isfinite(numero) or numero < 0:
        raise ValueError(f"{campo} deve essere un numero finito non negativo.")
    return numero


def congela_valore(valore: Any) -> Any:
    """Copia ricorsivamente collezioni mutabili in contenitori immutabili."""
    if isinstance(valore, Mapping):
        return MappingProxyType({
            str(chiave): congela_valore(contenuto)
            for chiave, contenuto in valore.items()
        })
    if isinstance(valore, list):
        return tuple(congela_valore(elemento) for elemento in valore)
    if isinstance(valore, tuple):
        return tuple(congela_valore(elemento) for elemento in valore)
    if isinstance(valore, set):
        return frozenset(congela_valore(elemento) for elemento in valore)
    if isinstance(valore, frozenset):
        return frozenset(congela_valore(elemento) for elemento in valore)
    return valore


@dataclass(frozen=True, slots=True)
class VersioniOutput:
    schema: str = SCHEMA_OUTPUT_VERSIONE
    protocollo: str = PROTOCOLLO_VERSIONE
    osservatore: str = OSSERVATORE_VERSIONE
    corpus: str = "R0.1"
    codice: str = "non_specificata"
    strategia: str = "C1"

    def __post_init__(self) -> None:
        for campo in ("schema", "protocollo", "osservatore", "corpus", "codice", "strategia"):
            object.__setattr__(self, campo, _testo_non_vuoto(getattr(self, campo), campo))
        if self.strategia != "C1":
            raise ValueError("La fase R0.1 osserva esclusivamente la strategia C1.")


@dataclass(frozen=True, slots=True)
class ParametriRicerca:
    numero_candidati: int
    numero_stagioni_fisso: int | None = None
    budget_secondi: float | None = None
    tetto_stagioni: int | None = None
    convergenza: int | None = None

    def __post_init__(self) -> None:
        _intero_positivo(self.numero_candidati, "numero_candidati")
        if self.numero_stagioni_fisso is not None:
            _intero_positivo(self.numero_stagioni_fisso, "numero_stagioni_fisso")
        object.__setattr__(
            self,
            "budget_secondi",
            _numero_finito_non_negativo(self.budget_secondi, "budget_secondi"),
        )
        for campo in ("tetto_stagioni", "convergenza"):
            valore = getattr(self, campo)
            if valore is not None:
                _intero_positivo(valore, campo)
        if self.numero_stagioni_fisso is None and all(
            valore is None
            for valore in (self.budget_secondi, self.tetto_stagioni, self.convergenza)
        ):
            raise ValueError(
                "Occorre indicare numero_stagioni_fisso oppure almeno un criterio di arresto."
            )

    @property
    def arresto_riproducibile(self) -> bool:
        return self.numero_stagioni_fisso is not None


@dataclass(frozen=True, slots=True)
class ParametriAula:
    numero_file: int
    posti_per_fila: int
    modalita_trio: str | None = None
    posizione_blocco_finale: str | None = None
    preferenza_resto2: str = "coppia"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _intero_positivo(self.numero_file, "numero_file")
        _intero_positivo(self.posti_per_fila, "posti_per_fila")
        if self.modalita_trio is not None:
            object.__setattr__(self, "modalita_trio", _testo_non_vuoto(self.modalita_trio, "modalita_trio"))
        if self.posizione_blocco_finale is not None:
            object.__setattr__(
                self,
                "posizione_blocco_finale",
                _testo_non_vuoto(self.posizione_blocco_finale, "posizione_blocco_finale"),
            )
        if self.preferenza_resto2 not in {"coppia", "due_quartetti"}:
            raise ValueError("preferenza_resto2 deve essere 'coppia' o 'due_quartetti'.")
        object.__setattr__(self, "extra", congela_valore(self.extra))


@dataclass(frozen=True, slots=True)
class SpecificaCoppiaCorpus:
    pair_id: str
    classe: str
    file_senza_fisso: str
    file_con_fisso: str
    studente_fisso: str
    posizione_base: str
    numero_studenti: int

    def __post_init__(self) -> None:
        for campo in (
            "pair_id",
            "classe",
            "file_senza_fisso",
            "file_con_fisso",
            "studente_fisso",
            "posizione_base",
        ):
            object.__setattr__(self, campo, _testo_non_vuoto(getattr(self, campo), campo))
        _intero_positivo(self.numero_studenti, "numero_studenti")
        if self.file_senza_fisso == self.file_con_fisso:
            raise ValueError("I due file della coppia corpus devono essere distinti.")


@dataclass(frozen=True, slots=True)
class SpecificaRun:
    run_id: str
    pair_id: str
    file_classe: str
    condizione: CondizioneRun
    modalita: Modalita
    seed_principale: int
    numero_mesi: int
    genere_misto_attivo: bool
    stato_iniziale_id: str
    parametri_ricerca: ParametriRicerca
    parametri_aula: ParametriAula
    metadati: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for campo in ("run_id", "pair_id", "file_classe", "stato_iniziale_id"):
            object.__setattr__(self, campo, _testo_non_vuoto(getattr(self, campo), campo))
        if isinstance(self.seed_principale, bool) or not isinstance(self.seed_principale, int):
            raise ValueError("seed_principale deve essere un intero.")
        if not 0 <= self.seed_principale < (1 << 64):
            raise ValueError("seed_principale deve essere un intero unsigned a 64 bit.")
        _intero_positivo(self.numero_mesi, "numero_mesi")
        if not isinstance(self.genere_misto_attivo, bool):
            raise ValueError("genere_misto_attivo deve essere booleano.")
        object.__setattr__(self, "metadati", congela_valore(self.metadati))

    def chiave_appaiamento(self) -> tuple[Any, ...]:
        """Restituisce i parametri che devono coincidere nei due run gemelli."""
        return (
            self.pair_id,
            self.modalita.value,
            self.seed_principale,
            self.numero_mesi,
            self.genere_misto_attivo,
            self.stato_iniziale_id,
            self.parametri_ricerca,
            self.parametri_aula,
        )


@dataclass(frozen=True, slots=True)
class ProtocolloRaccolta:
    protocollo_id: str
    titolo: str
    versione: str
    data_approvazione: str
    corpus_id: str
    osservatore_id: str
    strategia: str
    richiede_appaiamento_completo: bool
    coppie: tuple[SpecificaCoppiaCorpus, ...]
    run: tuple[SpecificaRun, ...]
    metadati: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for campo in (
            "protocollo_id",
            "titolo",
            "versione",
            "data_approvazione",
            "corpus_id",
            "osservatore_id",
            "strategia",
        ):
            object.__setattr__(self, campo, _testo_non_vuoto(getattr(self, campo), campo))
        if self.strategia != "C1":
            raise ValueError("Il protocollo R0.1 può osservare soltanto C1.")
        if not isinstance(self.richiede_appaiamento_completo, bool):
            raise ValueError("richiede_appaiamento_completo deve essere booleano.")
        object.__setattr__(self, "coppie", tuple(self.coppie))
        object.__setattr__(self, "run", tuple(self.run))
        object.__setattr__(self, "metadati", congela_valore(self.metadati))
        if not self.coppie:
            raise ValueError("Il protocollo deve contenere almeno una coppia corpus.")
        if not self.run:
            raise ValueError("Il protocollo deve contenere almeno un run esplicito.")


@dataclass(frozen=True, slots=True)
class VoceRotazione:
    canale: CanaleRotazione
    studenti: tuple[str, str]
    usi_precedenti: int
    ultimo_riferimento_disponibile: str | None = None

    def __post_init__(self) -> None:
        if len(self.studenti) != 2:
            raise ValueError("Una voce di rotazione richiede due studenti.")
        studenti = tuple(_testo_non_vuoto(nome, "studente") for nome in self.studenti)
        if studenti[0] == studenti[1]:
            raise ValueError("Una rotazione non può collegare lo stesso studente.")
        object.__setattr__(self, "studenti", tuple(sorted(studenti)))
        _intero_non_negativo(self.usi_precedenti, "usi_precedenti")
        if self.ultimo_riferimento_disponibile is not None:
            object.__setattr__(
                self,
                "ultimo_riferimento_disponibile",
                _testo_non_vuoto(
                    self.ultimo_riferimento_disponibile,
                    "ultimo_riferimento_disponibile",
                ),
            )


@dataclass(frozen=True, slots=True)
class VoceVicinoFisso:
    studente: str
    usi_precedenti: int
    ultimo_riferimento_disponibile: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "studente", _testo_non_vuoto(self.studente, "studente"))
        _intero_non_negativo(self.usi_precedenti, "usi_precedenti")
        if self.ultimo_riferimento_disponibile is not None:
            object.__setattr__(
                self,
                "ultimo_riferimento_disponibile",
                _testo_non_vuoto(
                    self.ultimo_riferimento_disponibile,
                    "ultimo_riferimento_disponibile",
                ),
            )


@dataclass(frozen=True, slots=True)
class SnapshotRotazioni:
    coppie: tuple[VoceRotazione, ...] = ()
    terzetti: tuple[VoceRotazione, ...] = ()
    vicini_fisso: tuple[VoceVicinoFisso, ...] = ()
    sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "coppie", tuple(self.coppie))
        object.__setattr__(self, "terzetti", tuple(self.terzetti))
        object.__setattr__(self, "vicini_fisso", tuple(self.vicini_fisso))

        for voce in self.coppie:
            if voce.canale != CanaleRotazione.COPPIE:
                raise ValueError("La sezione coppie contiene un canale non coerente.")
        for voce in self.terzetti:
            if voce.canale != CanaleRotazione.TERZETTI:
                raise ValueError("La sezione terzetti contiene un canale non coerente.")

        chiavi_coppie = [voce.studenti for voce in self.coppie]
        chiavi_terzetti = [voce.studenti for voce in self.terzetti]
        nomi_vicini = [voce.studente for voce in self.vicini_fisso]
        if len(set(chiavi_coppie)) != len(chiavi_coppie):
            raise ValueError("Lo snapshot contiene coppie duplicate.")
        if len(set(chiavi_terzetti)) != len(chiavi_terzetti):
            raise ValueError("Lo snapshot contiene adiacenze a terzetti duplicate.")
        if len(set(nomi_vicini)) != len(nomi_vicini):
            raise ValueError("Lo snapshot contiene vicini del FISSO duplicati.")

        if self.sha256 is not None:
            digest = _testo_non_vuoto(self.sha256, "sha256").lower()
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("sha256 deve contenere 64 caratteri esadecimali.")
            object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True, slots=True)
class TracciaMese:
    """Corrispondenza stabile fra ordine generato e ordine finale di C1.

    Le fotografie sono quelle *precedenti* al mese nella posizione finale.
    Restano dati tecnici di passaggio: I4 le userà per costruire gli eventi
    semantici senza interrogare nuovamente lo stato produttivo.
    """

    posizione_generazione: int
    posizione_finale: int
    chiave_generazione: tuple[int, int, int]
    chiave_finale: tuple[int, int, int]
    foto_rotazioni_precedenti: tuple[tuple[str, str], ...] = ()
    vicini_fisso_precedenti: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _intero_positivo(self.posizione_generazione, "posizione_generazione")
        _intero_positivo(self.posizione_finale, "posizione_finale")
        for campo in ("chiave_generazione", "chiave_finale"):
            valore = tuple(getattr(self, campo))
            if len(valore) != 3 or any(
                isinstance(elemento, bool) or not isinstance(elemento, int)
                for elemento in valore
            ):
                raise ValueError(f"{campo} deve essere una tupla di tre interi.")
            object.__setattr__(self, campo, valore)

        foto = []
        for coppia in self.foto_rotazioni_precedenti:
            if len(coppia) != 2:
                raise ValueError(
                    "foto_rotazioni_precedenti contiene una relazione non binaria."
                )
            nomi = tuple(sorted(_testo_non_vuoto(nome, "studente") for nome in coppia))
            if nomi[0] == nomi[1]:
                raise ValueError("Una fotografia non può contenere auto-adiacenze.")
            foto.append(nomi)
        foto_ordinate = tuple(sorted(set(foto)))
        if len(foto_ordinate) != len(foto):
            raise ValueError("foto_rotazioni_precedenti contiene duplicati.")
        object.__setattr__(self, "foto_rotazioni_precedenti", foto_ordinate)

        vicini = tuple(sorted(
            _testo_non_vuoto(nome, "vicino_fisso")
            for nome in self.vicini_fisso_precedenti
        ))
        if len(set(vicini)) != len(vicini):
            raise ValueError("vicini_fisso_precedenti contiene duplicati.")
        object.__setattr__(self, "vicini_fisso_precedenti", vicini)


@dataclass(frozen=True, slots=True)
class UltimoUso:
    origine: OrigineUltimoUso
    mese_annata: int | None = None
    riferimento_storico: str | None = None
    motivo_distanza_non_calcolabile: str | None = None

    def __post_init__(self) -> None:
        if self.mese_annata is not None:
            _intero_positivo(self.mese_annata, "mese_annata")
        if self.origine == OrigineUltimoUso.NESSUNO:
            if self.mese_annata is not None or self.riferimento_storico is not None:
                raise ValueError("Un ultimo uso inesistente non può avere riferimenti.")
        elif self.origine == OrigineUltimoUso.STORICO_INIZIALE:
            if self.mese_annata is not None:
                raise ValueError("Un precedente nello Storico iniziale non ha mese nell'annata.")
            if not self.motivo_distanza_non_calcolabile:
                raise ValueError("Un precedente nello Storico iniziale deve motivare la distanza non calcolabile.")
        elif self.origine == OrigineUltimoUso.ANNATA_CORRENTE:
            if self.mese_annata is None:
                raise ValueError("Un precedente nell'annata corrente richiede il mese.")
            if self.motivo_distanza_non_calcolabile is not None:
                raise ValueError("Un precedente nell'annata corrente ha distanza calcolabile.")


@dataclass(frozen=True, slots=True)
class GruppoCanonico:
    group_id: str
    tipo: TipoGruppo
    membri_ordinati: tuple[str, ...]
    fila: int | None = None
    posizione_nella_fila: int | None = None
    funzione: FunzioneGruppo = FunzioneGruppo.ORDINARIO

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", _testo_non_vuoto(self.group_id, "group_id"))
        membri = tuple(_testo_non_vuoto(nome, "membro") for nome in self.membri_ordinati)
        attesi = {
            TipoGruppo.COPPIA: 2,
            TipoGruppo.TRIO: 3,
            TipoGruppo.TERZETTO: 3,
            TipoGruppo.QUARTETTO: 4,
        }
        if len(membri) != attesi[self.tipo]:
            raise ValueError(f"Il gruppo {self.tipo.value} richiede {attesi[self.tipo]} membri.")
        if len(set(membri)) != len(membri):
            raise ValueError("Un gruppo non può contenere lo stesso studente più volte.")
        object.__setattr__(self, "membri_ordinati", membri)
        for campo in ("fila", "posizione_nella_fila"):
            valore = getattr(self, campo)
            if valore is not None:
                _intero_non_negativo(valore, campo)


@dataclass(frozen=True, slots=True)
class EventoAdiacenza:
    event_id: str
    run_id: str
    mese: int
    group_id: str
    studente_a: str
    studente_b: str
    ordine_a: int
    ordine_b: int
    chiave_adiacenza: tuple[str, str]
    ruolo: RuoloAdiacenza
    canale_rotazione: CanaleRotazione
    coinvolge_fisso: bool
    nome_fisso: str | None
    nome_vicino_fisso: str | None
    incompatibilita_livello: int
    affinita_livello: int
    genere_a: str
    genere_b: str
    adiacenza_mista: bool
    usi_precedenti_totali: int
    usi_precedenti_nell_annata: int
    e_riuso: bool
    numero_ripetizione: int | None
    fascia_ripetizione: FasciaRipetizione
    ultimo_uso: UltimoUso
    distanza_mesi: int | None

    def __post_init__(self) -> None:
        for campo in ("event_id", "run_id", "group_id", "studente_a", "studente_b"):
            object.__setattr__(self, campo, _testo_non_vuoto(getattr(self, campo), campo))
        _intero_positivo(self.mese, "mese")
        _intero_non_negativo(self.ordine_a, "ordine_a")
        _intero_non_negativo(self.ordine_b, "ordine_b")
        if abs(self.ordine_a - self.ordine_b) != 1:
            raise ValueError("Un evento deve collegare posizioni consecutive.")
        chiave = tuple(sorted((self.studente_a, self.studente_b)))
        if tuple(self.chiave_adiacenza) != chiave:
            raise ValueError("chiave_adiacenza non coincide con gli studenti dell'evento.")
        _livello(self.incompatibilita_livello, "incompatibilita_livello")
        _livello(self.affinita_livello, "affinita_livello")
        if self.incompatibilita_livello and self.affinita_livello:
            raise ValueError("La stessa adiacenza non può avere insieme affinità e incompatibilità.")
        if self.genere_a not in {"M", "F"} or self.genere_b not in {"M", "F"}:
            raise ValueError("I generi devono essere M o F.")
        if self.adiacenza_mista != (self.genere_a != self.genere_b):
            raise ValueError("adiacenza_mista non coincide con i generi dichiarati.")
        _intero_non_negativo(self.usi_precedenti_totali, "usi_precedenti_totali")
        _intero_non_negativo(self.usi_precedenti_nell_annata, "usi_precedenti_nell_annata")
        if self.usi_precedenti_nell_annata > self.usi_precedenti_totali:
            raise ValueError("Gli usi nell'annata non possono superare gli usi totali.")
        if self.e_riuso != (self.usi_precedenti_totali > 0):
            raise ValueError("e_riuso non coincide con gli usi precedenti.")
        fascia_attesa: FasciaRipetizione
        if self.usi_precedenti_totali == 0:
            fascia_attesa = FasciaRipetizione.PRIMA_COMPARSA
            if self.numero_ripetizione is not None:
                raise ValueError("Una prima comparsa non ha numero di ripetizione.")
        else:
            if self.numero_ripetizione != self.usi_precedenti_totali:
                raise ValueError("numero_ripetizione deve coincidere con gli usi precedenti totali.")
            fascia_attesa = (
                FasciaRipetizione.PRIMA_RIPETIZIONE
                if self.numero_ripetizione == 1
                else FasciaRipetizione.SECONDA_RIPETIZIONE
                if self.numero_ripetizione == 2
                else FasciaRipetizione.TERZA_O_ULTERIORE
            )
        if self.fascia_ripetizione != fascia_attesa:
            raise ValueError("fascia_ripetizione incoerente con la cronologia.")
        if self.ultimo_uso.origine == OrigineUltimoUso.ANNATA_CORRENTE:
            if self.distanza_mesi is None or self.distanza_mesi < 1:
                raise ValueError("Un precedente nell'annata richiede una distanza positiva.")
            if self.ultimo_uso.mese_annata is not None and (
                self.mese - self.ultimo_uso.mese_annata != self.distanza_mesi
            ):
                raise ValueError("distanza_mesi non coincide con i mesi dichiarati.")
        elif self.distanza_mesi is not None:
            raise ValueError("La distanza è calcolabile soltanto dentro la stessa annata.")
        if self.coinvolge_fisso:
            if not self.nome_fisso or not self.nome_vicino_fisso:
                raise ValueError("Un evento col FISSO richiede fisso e vicino.")
        elif self.nome_fisso is not None or self.nome_vicino_fisso is not None:
            raise ValueError("Un evento senza FISSO non può indicarne i nomi.")


@dataclass(frozen=True, slots=True)
class RiepilogoMensile:
    adiacenze_totali: int
    riusi_totali: int
    prime_ripetizioni: int
    seconde_ripetizioni: int
    terze_o_ulteriori: int
    incompatibilita_l1: int
    incompatibilita_l2: int
    incompatibilita_l3: int
    affinita_l1: int
    affinita_l2: int
    affinita_l3: int
    adiacenze_miste: int
    adiacenze_stesso_genere: int

    def __post_init__(self) -> None:
        for campo in self.__dataclass_fields__:
            _intero_non_negativo(getattr(self, campo), campo)
        if self.riusi_totali != (
            self.prime_ripetizioni + self.seconde_ripetizioni + self.terze_o_ulteriori
        ):
            raise ValueError("Il totale dei riusi non coincide con le fasce di ripetizione.")
        if self.adiacenze_totali != self.adiacenze_miste + self.adiacenze_stesso_genere:
            raise ValueError("Il totale delle adiacenze non coincide con la ripartizione di genere.")


@dataclass(frozen=True, slots=True)
class MeseCanonico:
    mese_finale: int
    posizione_generazione: int
    posizione_finale: int
    gruppi: tuple[GruppoCanonico, ...]
    adiacenze: tuple[EventoAdiacenza, ...]
    riepilogo: RiepilogoMensile
    configurazione_aula: Mapping[str, Any] = field(default_factory=dict)
    vicino_fisso: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for campo in ("mese_finale", "posizione_generazione", "posizione_finale"):
            _intero_positivo(getattr(self, campo), campo)
        object.__setattr__(self, "gruppi", tuple(self.gruppi))
        object.__setattr__(self, "adiacenze", tuple(self.adiacenze))
        object.__setattr__(self, "configurazione_aula", congela_valore(self.configurazione_aula))
        if self.vicino_fisso is not None:
            object.__setattr__(self, "vicino_fisso", congela_valore(self.vicino_fisso))
        if self.mese_finale != self.posizione_finale:
            raise ValueError("Nella R0.1 mese_finale deve coincidere con posizione_finale.")
        if self.riepilogo.adiacenze_totali != len(self.adiacenze):
            raise ValueError("Il riepilogo mensile non coincide con gli eventi.")


@dataclass(frozen=True, slots=True)
class RiepilogoStudente:
    studente: str
    genere: str
    posizione: str
    e_fisso: bool
    riusi_coinvolgenti: int
    prime_ripetizioni: int
    seconde_ripetizioni: int
    terze_o_ulteriori: int
    mesi_con_riusi: tuple[int, ...]
    compagni_distinti: int
    incarichi_vicino_fisso: int
    mesi_vicino_fisso: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "studente", _testo_non_vuoto(self.studente, "studente"))
        if self.genere not in {"M", "F"}:
            raise ValueError("genere deve essere M o F.")
        object.__setattr__(self, "posizione", _testo_non_vuoto(self.posizione, "posizione"))
        for campo in (
            "riusi_coinvolgenti",
            "prime_ripetizioni",
            "seconde_ripetizioni",
            "terze_o_ulteriori",
            "compagni_distinti",
            "incarichi_vicino_fisso",
        ):
            _intero_non_negativo(getattr(self, campo), campo)
        object.__setattr__(self, "mesi_con_riusi", tuple(self.mesi_con_riusi))
        object.__setattr__(self, "mesi_vicino_fisso", tuple(self.mesi_vicino_fisso))
        for mese in (*self.mesi_con_riusi, *self.mesi_vicino_fisso):
            _intero_positivo(mese, "mese")


@dataclass(frozen=True, slots=True)
class RiepilogoAnnuale:
    adiacenze_totali: int
    riusi_totali: int
    prime_ripetizioni: int
    seconde_ripetizioni: int
    terze_o_ulteriori: int
    incompatibilita_l1: int
    incompatibilita_l2: int
    incompatibilita_l3: int
    affinita_l1: int
    affinita_l2: int
    affinita_l3: int
    adiacenze_miste: int
    studenti_con_0_riusi: int
    studenti_con_1_riuso: int
    studenti_con_2_riusi: int
    studenti_con_3_o_piu_riusi: int
    massimo_individuale: int
    studenti_al_massimo: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for campo in self.__dataclass_fields__:
            if campo != "studenti_al_massimo":
                _intero_non_negativo(getattr(self, campo), campo)
        object.__setattr__(self, "studenti_al_massimo", tuple(self.studenti_al_massimo))
        if self.riusi_totali != (
            self.prime_ripetizioni + self.seconde_ripetizioni + self.terze_o_ulteriori
        ):
            raise ValueError("Il totale annuale dei riusi non coincide con le fasce.")


@dataclass(frozen=True, slots=True)
class CronologiaAdiacenza:
    canale_rotazione: CanaleRotazione
    studenti: tuple[str, str]
    mesi_occorrenza: tuple[int, ...]
    numero_occorrenze_annata: int
    usi_storico_iniziale: int
    numero_occorrenze_totali_finali: int
    distanze_interne: tuple[int, ...] = ()
    coinvolge_fisso: bool = False

    def __post_init__(self) -> None:
        if len(self.studenti) != 2:
            raise ValueError("Una cronologia richiede due studenti.")
        studenti = tuple(sorted(_testo_non_vuoto(nome, "studente") for nome in self.studenti))
        if studenti[0] == studenti[1]:
            raise ValueError("Una cronologia non può contenere lo stesso studente due volte.")
        object.__setattr__(self, "studenti", studenti)
        mesi = tuple(self.mesi_occorrenza)
        for mese in mesi:
            _intero_positivo(mese, "mese_occorrenza")
        if tuple(sorted(mesi)) != mesi or len(set(mesi)) != len(mesi):
            raise ValueError("mesi_occorrenza deve essere crescente e privo di duplicati.")
        object.__setattr__(self, "mesi_occorrenza", mesi)
        _intero_non_negativo(self.numero_occorrenze_annata, "numero_occorrenze_annata")
        _intero_non_negativo(self.usi_storico_iniziale, "usi_storico_iniziale")
        _intero_non_negativo(self.numero_occorrenze_totali_finali, "numero_occorrenze_totali_finali")
        if self.numero_occorrenze_annata != len(mesi):
            raise ValueError("numero_occorrenze_annata non coincide con i mesi registrati.")
        if self.numero_occorrenze_totali_finali != self.usi_storico_iniziale + self.numero_occorrenze_annata:
            raise ValueError("Il totale finale non coincide con storico iniziale e annata.")
        distanze = tuple(self.distanze_interne)
        for distanza in distanze:
            _intero_positivo(distanza, "distanza_interna")
        attese = tuple(secondo - primo for primo, secondo in zip(mesi, mesi[1:]))
        if distanze != attese:
            raise ValueError("distanze_interne non coincide con i mesi di occorrenza.")
        object.__setattr__(self, "distanze_interne", distanze)


@dataclass(frozen=True, slots=True)
class PuntoSerieMensile:
    mese: int
    riepilogo: RiepilogoMensile
    vicino_fisso: str | None = None

    def __post_init__(self) -> None:
        _intero_positivo(self.mese, "mese")
        if self.vicino_fisso is not None:
            object.__setattr__(self, "vicino_fisso", _testo_non_vuoto(self.vicino_fisso, "vicino_fisso"))


@dataclass(frozen=True, slots=True)
class RicercaAnnuale:
    stagioni_tentate: int
    stagioni_complete: int
    indice_stagione_vincente: int | None
    motivo_arresto: str
    punteggio_tecnico: tuple[int, int, int] | None
    durata_secondi: float | None = None

    def __post_init__(self) -> None:
        _intero_non_negativo(self.stagioni_tentate, "stagioni_tentate")
        _intero_non_negativo(self.stagioni_complete, "stagioni_complete")
        if self.stagioni_complete > self.stagioni_tentate:
            raise ValueError("Le stagioni complete non possono superare quelle tentate.")
        if self.indice_stagione_vincente is not None:
            _intero_positivo(self.indice_stagione_vincente, "indice_stagione_vincente")
        object.__setattr__(self, "motivo_arresto", _testo_non_vuoto(self.motivo_arresto, "motivo_arresto"))
        if self.punteggio_tecnico is not None:
            if len(self.punteggio_tecnico) != 3 or any(
                isinstance(x, bool) or not isinstance(x, int) for x in self.punteggio_tecnico
            ):
                raise ValueError("punteggio_tecnico deve essere una tupla di tre interi.")
        object.__setattr__(
            self,
            "durata_secondi",
            _numero_finito_non_negativo(self.durata_secondi, "durata_secondi"),
        )


@dataclass(frozen=True, slots=True)
class EsitoOttimoMisto:
    valore: int
    esatto: bool
    nodi_visitati: int
    durata_secondi: float
    motivo_mancanza: str | None = None
    testimone: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        _intero_non_negativo(self.valore, "valore")
        if not isinstance(self.esatto, bool):
            raise ValueError("esatto deve essere booleano.")
        _intero_non_negativo(self.nodi_visitati, "nodi_visitati")
        object.__setattr__(
            self,
            "durata_secondi",
            _numero_finito_non_negativo(self.durata_secondi, "durata_secondi"),
        )
        object.__setattr__(
            self,
            "testimone",
            tuple(tuple(_testo_non_vuoto(x, "elemento_testimone") for x in gruppo) for gruppo in self.testimone),
        )
        if self.esatto and self.motivo_mancanza is not None:
            raise ValueError("Un ottimo esatto non deve avere motivo_mancanza.")
        if not self.esatto and not self.motivo_mancanza:
            raise ValueError("Un ottimo non esatto deve motivare la mancanza.")


@dataclass(frozen=True, slots=True)
class GruppoNonPienamenteMisto:
    group_id: str
    tipo: TipoGruppo
    membri: tuple[str, ...]
    adiacenze_stesso_genere: int
    motivo: str = "non_determinato"

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", _testo_non_vuoto(self.group_id, "group_id"))
        membri = tuple(_testo_non_vuoto(x, "membro") for x in self.membri)
        if len(membri) < 2:
            raise ValueError("Un gruppo osservato deve avere almeno due membri.")
        object.__setattr__(self, "membri", membri)
        _intero_positivo(self.adiacenze_stesso_genere, "adiacenze_stesso_genere")
        if self.adiacenze_stesso_genere >= len(membri):
            raise ValueError("Troppe adiacenze dello stesso genere per il gruppo.")
        motivi = {
            "squilibrio_numerico",
            "vincolo_assoluto",
            "effetto_del_fisso_sul_massimo",
            "non_determinato",
        }
        if self.motivo not in motivi:
            raise ValueError("motivo del gruppo non misto non riconosciuto.")


@dataclass(frozen=True, slots=True)
class AnalisiGenereMese:
    mese: int
    firma_template: str
    massimo_geometrico: EsitoOttimoMisto
    massimo_ammissibile: EsitoOttimoMisto
    adiacenze_miste_ottenute: int
    adiacenze_stesso_genere: int
    gruppi_non_pienamente_misti: tuple[GruppoNonPienamenteMisto, ...] = ()

    def __post_init__(self) -> None:
        _intero_positivo(self.mese, "mese")
        object.__setattr__(self, "firma_template", _testo_non_vuoto(self.firma_template, "firma_template"))
        _intero_non_negativo(self.adiacenze_miste_ottenute, "adiacenze_miste_ottenute")
        _intero_non_negativo(self.adiacenze_stesso_genere, "adiacenze_stesso_genere")
        object.__setattr__(self, "gruppi_non_pienamente_misti", tuple(self.gruppi_non_pienamente_misti))
        if self.massimo_ammissibile.valore > self.massimo_geometrico.valore:
            raise ValueError("Il massimo ammissibile non può superare quello geometrico.")
        if self.adiacenze_miste_ottenute > self.massimo_ammissibile.valore:
            raise ValueError("Il risultato ottenuto supera il massimo ammissibile dichiarato.")


@dataclass(frozen=True, slots=True)
class AnalisiGenereAnnuale:
    flag_attivo: bool
    mesi: tuple[AnalisiGenereMese, ...]
    massimo_geometrico_totale: int
    massimo_ammissibile_totale: int
    adiacenze_miste_ottenute_totali: int

    def __post_init__(self) -> None:
        if not isinstance(self.flag_attivo, bool):
            raise ValueError("flag_attivo deve essere booleano.")
        object.__setattr__(self, "mesi", tuple(self.mesi))
        for campo in (
            "massimo_geometrico_totale",
            "massimo_ammissibile_totale",
            "adiacenze_miste_ottenute_totali",
        ):
            _intero_non_negativo(getattr(self, campo), campo)
        if self.massimo_geometrico_totale != sum(x.massimo_geometrico.valore for x in self.mesi):
            raise ValueError("Il totale geometrico non coincide con i mesi.")
        if self.massimo_ammissibile_totale != sum(x.massimo_ammissibile.valore for x in self.mesi):
            raise ValueError("Il totale ammissibile non coincide con i mesi.")
        if self.adiacenze_miste_ottenute_totali != sum(x.adiacenze_miste_ottenute for x in self.mesi):
            raise ValueError("Il totale ottenuto non coincide con i mesi.")


@dataclass(frozen=True, slots=True)
class AnnataCanonica:
    versioni: VersioniOutput
    run: SpecificaRun
    stato: StatoRun
    classe: str
    numero_studenti: int
    studente_fisso: str | None
    snapshot_iniziale: SnapshotRotazioni
    ricerca: RicercaAnnuale
    mesi: tuple[MeseCanonico, ...]
    studenti: tuple[RiepilogoStudente, ...]
    riepilogo: RiepilogoAnnuale
    cronologia_adiacenze: tuple[CronologiaAdiacenza, ...] = ()
    serie_mensile: tuple[PuntoSerieMensile, ...] = ()
    genere_misto: AnalisiGenereAnnuale | None = None
    metadati: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "classe", _testo_non_vuoto(self.classe, "classe"))
        _intero_positivo(self.numero_studenti, "numero_studenti")
        object.__setattr__(self, "mesi", tuple(self.mesi))
        object.__setattr__(self, "studenti", tuple(self.studenti))
        object.__setattr__(self, "cronologia_adiacenze", tuple(self.cronologia_adiacenze))
        object.__setattr__(self, "serie_mensile", tuple(self.serie_mensile))
        object.__setattr__(self, "metadati", congela_valore(self.metadati))
        if self.run.condizione == CondizioneRun.CON_FISSO and not self.studente_fisso:
            raise ValueError("Un run con FISSO deve indicare lo studente FISSO.")
        if self.run.condizione == CondizioneRun.SENZA_FISSO and self.studente_fisso is not None:
            raise ValueError("Un run senza FISSO non può indicare uno studente FISSO.")
        if self.stato == StatoRun.COMPLETO and len(self.mesi) != self.run.numero_mesi:
            raise ValueError("Un run completo deve contenere tutti i mesi richiesti.")
        if len(self.studenti) != self.numero_studenti:
            raise ValueError("Il riepilogo studenti non coincide con numero_studenti.")
        if len({voce.studente for voce in self.studenti}) != len(self.studenti):
            raise ValueError("Il riepilogo studenti contiene duplicati.")
        if self.serie_mensile and tuple(punto.mese for punto in self.serie_mensile) != tuple(mese.mese_finale for mese in self.mesi):
            raise ValueError("La serie mensile non coincide con i mesi canonici.")
        if self.genere_misto is not None and tuple(x.mese for x in self.genere_misto.mesi) != tuple(mese.mese_finale for mese in self.mesi):
            raise ValueError("L’analisi di genere non coincide con i mesi canonici.")


@dataclass(frozen=True, slots=True)
class ProblemaValidazione:
    codice: str
    messaggio: str
    gravita: GravitaValidazione = GravitaValidazione.ERRORE
    percorso: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "codice", _testo_non_vuoto(self.codice, "codice"))
        object.__setattr__(self, "messaggio", _testo_non_vuoto(self.messaggio, "messaggio"))


@dataclass(frozen=True, slots=True)
class EsitoValidazione:
    valido: bool
    problemi: tuple[ProblemaValidazione, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "problemi", tuple(self.problemi))
        ha_errori = any(p.gravita == GravitaValidazione.ERRORE for p in self.problemi)
        if self.valido == ha_errori:
            raise ValueError("Il flag valido non coincide con i problemi registrati.")
