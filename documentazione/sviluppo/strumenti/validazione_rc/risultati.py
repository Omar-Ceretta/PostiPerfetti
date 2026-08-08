# -*- coding: utf-8 -*-
"""Controllori indipendenti dei risultati prodotti dai motori di PostiPerfetti.

Il modulo non usa le metriche del motore per decidere se un risultato è valido:
ricostruisce occupanti, blocchi e adiacenze direttamente dalla griglia fisica e
li confronta con la classe RC sorgente.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from moduli.studenti import nome_completo_da_identificatore

from .modelli import ClasseRC


@dataclass(frozen=True, slots=True)
class MetricheRisultatoRC:
    studenti: int
    blocchi: tuple[int, ...]
    adiacenze: int
    incompatibilita_l1: int
    incompatibilita_l2: int
    incompatibilita_l3: int
    affinita: int
    adiacenze_miste: int

    @property
    def incompatibilita_pesate(self) -> int:
        # Pesi correnti della semantica R0.8, duplicati intenzionalmente:
        # il controllore non importa metrica_pulizia.py.
        return (
            self.incompatibilita_l1
            + 10 * self.incompatibilita_l2
            + 1000 * self.incompatibilita_l3
        )

    def come_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ViolazioneRisultatoRC:
    codice: str
    messaggio: str


@dataclass(frozen=True, slots=True)
class VerificaRisultatoRC:
    modalita: str
    valido: bool
    metriche: MetricheRisultatoRC
    violazioni: tuple[ViolazioneRisultatoRC, ...]
    occupanti: tuple[str, ...]
    adiacenze: tuple[tuple[str, str], ...]

    def come_dict(self) -> dict:
        return {
            "modalita": self.modalita,
            "valido": self.valido,
            "metriche": self.metriche.come_dict(),
            "violazioni": [asdict(v) for v in self.violazioni],
            "occupanti": list(self.occupanti),
            "adiacenze": [list(coppia) for coppia in self.adiacenze],
        }


class ErroreRisultatoRC(AssertionError):
    def __init__(self, verifica: VerificaRisultatoRC):
        self.verifica = verifica
        super().__init__(
            "\n".join(f"{v.codice}: {v.messaggio}" for v in verifica.violazioni)
        )


def _nome_occupante(posto) -> str | None:
    if not getattr(posto, "occupato_da", None):
        return None
    return nome_completo_da_identificatore(posto.occupato_da)


def _blocchi_occupati(aula) -> list[list[str]]:
    """Ricostruisce i blocchi fisici senza usare metadati del motore.

    Due studenti sono nello stesso blocco soltanto quando occupano banchi nelle
    colonne consecutive della stessa fila. Corridoi e colonne vuote spezzano il
    blocco.
    """
    blocchi: list[list[str]] = []
    for riga in getattr(aula, "griglia", []):
        corrente: list[str] = []
        colonna_precedente: int | None = None
        for posto in sorted(riga, key=lambda p: p.colonna):
            nome = _nome_occupante(posto) if getattr(posto, "tipo", None) == "banco" else None
            if nome is not None:
                if colonna_precedente is not None and posto.colonna == colonna_precedente + 1:
                    corrente.append(nome)
                else:
                    if corrente:
                        blocchi.append(corrente)
                    corrente = [nome]
                colonna_precedente = posto.colonna
            else:
                if corrente:
                    blocchi.append(corrente)
                    corrente = []
                colonna_precedente = None
        if corrente:
            blocchi.append(corrente)
    return blocchi


def _posizioni_occupanti(aula) -> dict[str, tuple[int, int]]:
    risultato: dict[str, tuple[int, int]] = {}
    for riga in getattr(aula, "griglia", []):
        for posto in riga:
            nome = _nome_occupante(posto)
            if nome is not None:
                # Il duplicato viene rilevato separatamente dal conteggio degli occupanti.
                risultato.setdefault(nome, (posto.riga, posto.colonna))
    return risultato


def _adiacenze_da_blocchi(blocchi: Iterable[Iterable[str]]) -> list[tuple[str, str]]:
    risultato = []
    for blocco in blocchi:
        membri = list(blocco)
        for indice in range(len(membri) - 1):
            risultato.append(tuple(sorted((membri[indice], membri[indice + 1]))))
    return risultato


def _livello(classe: ClasseRC, a: str, b: str, attributo: str) -> int:
    studente = classe.per_nome[a]
    relazioni = (
        studente.incompatibilita_dict
        if attributo == "incompatibilita"
        else studente.affinita_dict
    )
    return int(relazioni.get(b, 0))


def _blocchi_attesi_coppie(
    classe: ClasseRC,
    *,
    posizione_trio: str,
) -> tuple[int, ...]:
    n = classe.numero_studenti
    ha_fisso = classe.studente_fisso is not None
    rimanenti = n - 1 if ha_fisso else n
    ha_trio = (rimanenti % 2 == 1)

    dimensioni: list[int] = []
    if ha_fisso and ha_trio and posizione_trio == "prima":
        # FISSO e trio condividono il blocco sinistro frontale.
        dimensioni.append(4)
        rimanenti -= 3
    elif ha_fisso and ha_trio:
        # Il FISSO ha una coppia adiacente; il trio vive in un altro blocco.
        dimensioni.extend((3, 3))
        rimanenti -= 5
    elif ha_fisso:
        dimensioni.append(3)
        rimanenti -= 2
    elif ha_trio:
        dimensioni.append(3)
        rimanenti -= 3

    dimensioni.extend([2] * (rimanenti // 2))
    return tuple(sorted(dimensioni))


def _blocchi_attesi_terzetti(
    classe: ClasseRC,
    *,
    preferenza_resto2: str,
) -> tuple[int, ...]:
    n = classe.numero_studenti
    resto = n % 3
    if resto == 0:
        dimensioni = [3] * (n // 3)
    elif resto == 1:
        dimensioni = [3] * ((n - 4) // 3) + [4]
    elif preferenza_resto2 == "due_quartetti" and n >= 8:
        dimensioni = [3] * ((n - 8) // 3) + [4, 4]
    else:
        dimensioni = [3] * ((n - 2) // 3) + [2]
    return tuple(sorted(dimensioni))


def verifica_aula_rc(
    classe: ClasseRC,
    aula,
    *,
    modalita: str,
    preferenza_resto2: str = "coppia",
    posizione_trio: str = "centro",
    solleva: bool = False,
) -> VerificaRisultatoRC:
    """Valida un'aula occupata contro il contratto della classe sorgente."""
    if modalita not in {"coppie", "terzetti"}:
        raise ValueError("modalita deve essere 'coppie' o 'terzetti'.")

    blocchi = _blocchi_occupati(aula)
    occupanti_lista = [nome for blocco in blocchi for nome in blocco]
    occupanti = tuple(sorted(occupanti_lista))
    adiacenze_lista = _adiacenze_da_blocchi(blocchi)
    adiacenze = tuple(sorted(adiacenze_lista))
    attesi = set(classe.per_nome)
    presenti = set(occupanti_lista)
    violazioni: list[ViolazioneRisultatoRC] = []

    duplicati = sorted({nome for nome in occupanti_lista if occupanti_lista.count(nome) > 1})
    mancanti = sorted(attesi - presenti)
    estranei = sorted(presenti - attesi)
    if duplicati:
        violazioni.append(ViolazioneRisultatoRC("RC_RIS_DUPLICATI", f"Occupanti duplicati: {duplicati}."))
    if mancanti:
        violazioni.append(ViolazioneRisultatoRC("RC_RIS_MANCANTI", f"Studenti non collocati: {mancanti}."))
    if estranei:
        violazioni.append(ViolazioneRisultatoRC("RC_RIS_ESTRANEI", f"Occupanti non appartenenti alla classe: {estranei}."))

    dimensioni = tuple(sorted(len(blocco) for blocco in blocchi))
    dimensioni_attese = (
        _blocchi_attesi_coppie(classe, posizione_trio=posizione_trio)
        if modalita == "coppie"
        else _blocchi_attesi_terzetti(classe, preferenza_resto2=preferenza_resto2)
    )
    if dimensioni != dimensioni_attese:
        violazioni.append(
            ViolazioneRisultatoRC(
                "RC_RIS_BLOCCHI",
                f"Blocchi fisici {dimensioni}, attesi {dimensioni_attese} per {modalita}.",
            )
        )

    posizioni = _posizioni_occupanti(aula)
    righe_occupate = [riga for riga, _colonna in posizioni.values()]
    prima_riga = min(righe_occupate) if righe_occupate else None
    for studente in classe.studenti:
        posizione = posizioni.get(studente.nome)
        if posizione is None:
            continue
        if studente.posizione in {"PRIMA", "FISSO"} and posizione[0] != prima_riga:
            violazioni.append(
                ViolazioneRisultatoRC(
                    "RC_RIS_PRIMA",
                    f"{studente.nome} ({studente.posizione}) è in riga {posizione[0]}, prima riga={prima_riga}.",
                )
            )

    if classe.studente_fisso is not None and prima_riga is not None:
        posti_prima = [
            (colonna, nome)
            for nome, (riga, colonna) in posizioni.items()
            if riga == prima_riga
        ]
        if posti_prima:
            nome_sinistra = min(posti_prima)[1]
            if nome_sinistra != classe.studente_fisso:
                violazioni.append(
                    ViolazioneRisultatoRC(
                        "RC_RIS_FISSO",
                        f"Il posto frontale sinistro è di {nome_sinistra}, non del FISSO {classe.studente_fisso}.",
                    )
                )

    incompatibilita = {1: 0, 2: 0, 3: 0}
    affinita = 0
    miste = 0
    adiacenze_note = []
    for a, b in adiacenze_lista:
        if a not in attesi or b not in attesi:
            continue
        livello_inc = max(
            _livello(classe, a, b, "incompatibilita"),
            _livello(classe, b, a, "incompatibilita"),
        )
        if livello_inc in incompatibilita:
            incompatibilita[livello_inc] += 1
        if livello_inc == 3:
            adiacenze_note.append((a, b))
        livello_aff = max(
            _livello(classe, a, b, "affinita"),
            _livello(classe, b, a, "affinita"),
        )
        affinita += int(livello_aff >= 1)
        miste += int(classe.per_nome[a].sesso != classe.per_nome[b].sesso)

    if adiacenze_note:
        violazioni.append(
            ViolazioneRisultatoRC(
                "RC_RIS_INCOMPATIBILITA_3",
                "Adiacenze assolutamente vietate: " + ", ".join(f"{a} ↔ {b}" for a, b in adiacenze_note),
            )
        )

    metriche = MetricheRisultatoRC(
        studenti=len(occupanti_lista),
        blocchi=dimensioni,
        adiacenze=len(adiacenze_lista),
        incompatibilita_l1=incompatibilita[1],
        incompatibilita_l2=incompatibilita[2],
        incompatibilita_l3=incompatibilita[3],
        affinita=affinita,
        adiacenze_miste=miste,
    )
    verifica = VerificaRisultatoRC(
        modalita=modalita,
        valido=not violazioni,
        metriche=metriche,
        violazioni=tuple(violazioni),
        occupanti=occupanti,
        adiacenze=adiacenze,
    )
    if solleva and not verifica.valido:
        raise ErroreRisultatoRC(verifica)
    return verifica
