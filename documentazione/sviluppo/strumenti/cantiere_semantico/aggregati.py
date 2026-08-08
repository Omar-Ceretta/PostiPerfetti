"""Aggregazioni annuali pure dell'osservatore semantico — incremento I5.

Il modulo riceve esclusivamente mesi canonici prodotti da I4 e costruisce le
viste longitudinali approvate dal contratto R0.1. Non interroga i motori, non
ricalcola i gruppi e non modifica gli oggetti produttivi.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .cronologia import EsitoCronologiaI4
from .esecuzione_c1 import EsitoC1
from .modelli import (
    AnnataCanonica,
    CanaleRotazione,
    CronologiaAdiacenza,
    EventoAdiacenza,
    FasciaRipetizione,
    MeseCanonico,
    PuntoSerieMensile,
    RicercaAnnuale,
    RiepilogoAnnuale,
    RiepilogoStudente,
    SnapshotRotazioni,
    SpecificaRun,
    VersioniOutput,
)
from .snapshot import crea_stato_iniziale_id, verifica_snapshot


class ErroreAggregazione(ValueError):
    """Segnala dati canonici incompleti o reciprocamente incoerenti."""


@dataclass(slots=True)
class _StudenteAccumulatore:
    nome: str
    genere: str
    posizione: str
    e_fisso: bool
    riusi_coinvolgenti: int = 0
    prime_ripetizioni: int = 0
    seconde_ripetizioni: int = 0
    terze_o_ulteriori: int = 0
    mesi_con_riusi: set[int] | None = None
    compagni: set[str] | None = None
    incarichi_vicino_fisso: int = 0
    mesi_vicino_fisso: set[int] | None = None

    def __post_init__(self) -> None:
        self.mesi_con_riusi = set()
        self.compagni = set()
        self.mesi_vicino_fisso = set()


def _nome_studente(studente: Any) -> str:
    metodo = getattr(studente, "get_nome_completo", None)
    nome = metodo() if callable(metodo) else str(studente)
    nome = str(nome).strip()
    if not nome:
        raise ErroreAggregazione("Uno studente non possiede un'identità leggibile.")
    return nome


def _genere_studente(studente: Any) -> str:
    genere = str(getattr(studente, "sesso", "")).strip().upper()
    if genere not in {"M", "F"}:
        raise ErroreAggregazione(
            f"Genere non valido per {_nome_studente(studente)!r}: {genere!r}."
        )
    return genere


def _posizione_studente(studente: Any) -> str:
    posizione = str(getattr(studente, "nota_posizione", "NORMALE")).strip().upper()
    if not posizione:
        raise ErroreAggregazione(
            f"Posizione vuota per {_nome_studente(studente)!r}."
        )
    return posizione


def _nome_fisso(studente_fisso: Any | None) -> str | None:
    if studente_fisso is None:
        return None
    if isinstance(studente_fisso, str):
        nome = studente_fisso.strip()
        if not nome:
            raise ErroreAggregazione("Il nome del FISSO non può essere vuoto.")
        return nome
    return _nome_studente(studente_fisso)


def _eventi(mesi: Sequence[MeseCanonico]) -> tuple[EventoAdiacenza, ...]:
    return tuple(evento for mese in mesi for evento in mese.adiacenze)


def costruisci_riepiloghi_studenti(
    mesi: Iterable[MeseCanonico],
    studenti: Sequence[Any],
) -> tuple[RiepilogoStudente, ...]:
    """Costruisce una riga annuale per ogni studente del run.

    I conteggi dei riusi sono incrementati per entrambi i membri dell'evento.
    Gli incarichi di vicino del FISSO sono invece attribuiti soltanto allo
    studente indicato da ``nome_vicino_fisso``.
    """
    mesi = tuple(mesi)
    accumulatori: dict[str, _StudenteAccumulatore] = {}
    for studente in studenti:
        nome = _nome_studente(studente)
        if nome in accumulatori:
            raise ErroreAggregazione(f"Studente duplicato nell'anagrafica: {nome!r}.")
        posizione = _posizione_studente(studente)
        accumulatori[nome] = _StudenteAccumulatore(
            nome=nome,
            genere=_genere_studente(studente),
            posizione=posizione,
            e_fisso=posizione == "FISSO",
        )

    for evento in _eventi(mesi):
        for nome, compagno in (
            (evento.studente_a, evento.studente_b),
            (evento.studente_b, evento.studente_a),
        ):
            try:
                acc = accumulatori[nome]
            except KeyError as errore:
                raise ErroreAggregazione(
                    f"L'evento {evento.event_id} usa lo studente sconosciuto {nome!r}."
                ) from errore
            assert acc.compagni is not None
            acc.compagni.add(compagno)
            if evento.e_riuso:
                acc.riusi_coinvolgenti += 1
                assert acc.mesi_con_riusi is not None
                acc.mesi_con_riusi.add(evento.mese)
                if evento.fascia_ripetizione == FasciaRipetizione.PRIMA_RIPETIZIONE:
                    acc.prime_ripetizioni += 1
                elif evento.fascia_ripetizione == FasciaRipetizione.SECONDA_RIPETIZIONE:
                    acc.seconde_ripetizioni += 1
                elif evento.fascia_ripetizione == FasciaRipetizione.TERZA_O_ULTERIORE:
                    acc.terze_o_ulteriori += 1
                else:  # pragma: no cover - protetto dal modello EventoAdiacenza
                    raise ErroreAggregazione(
                        "Un evento marcato come riuso non possiede una fascia di ripetizione."
                    )

        if evento.coinvolge_fisso:
            vicino = evento.nome_vicino_fisso
            if vicino not in accumulatori:
                raise ErroreAggregazione(
                    f"Il vicino del FISSO {vicino!r} non appartiene all'anagrafica."
                )
            acc_vicino = accumulatori[vicino]
            acc_vicino.incarichi_vicino_fisso += 1
            assert acc_vicino.mesi_vicino_fisso is not None
            acc_vicino.mesi_vicino_fisso.add(evento.mese)

    risultato = []
    for nome in sorted(accumulatori):
        acc = accumulatori[nome]
        assert acc.mesi_con_riusi is not None
        assert acc.compagni is not None
        assert acc.mesi_vicino_fisso is not None
        risultato.append(
            RiepilogoStudente(
                studente=acc.nome,
                genere=acc.genere,
                posizione=acc.posizione,
                e_fisso=acc.e_fisso,
                riusi_coinvolgenti=acc.riusi_coinvolgenti,
                prime_ripetizioni=acc.prime_ripetizioni,
                seconde_ripetizioni=acc.seconde_ripetizioni,
                terze_o_ulteriori=acc.terze_o_ulteriori,
                mesi_con_riusi=tuple(sorted(acc.mesi_con_riusi)),
                compagni_distinti=len(acc.compagni),
                incarichi_vicino_fisso=acc.incarichi_vicino_fisso,
                mesi_vicino_fisso=tuple(sorted(acc.mesi_vicino_fisso)),
            )
        )
    return tuple(risultato)


def costruisci_cronologia_adiacenze(
    mesi: Iterable[MeseCanonico],
) -> tuple[CronologiaAdiacenza, ...]:
    """Raggruppa gli eventi per canale e adiacenza canonica."""
    raggruppati: dict[
        tuple[CanaleRotazione, tuple[str, str]], list[EventoAdiacenza]
    ] = defaultdict(list)
    for evento in _eventi(tuple(mesi)):
        raggruppati[(evento.canale_rotazione, evento.chiave_adiacenza)].append(evento)

    risultato = []
    for (canale, studenti), eventi in sorted(
        raggruppati.items(),
        key=lambda voce: (voce[0][0].value, voce[0][1]),
    ):
        eventi.sort(key=lambda evento: evento.mese)
        mesi_occorrenza = tuple(evento.mese for evento in eventi)
        if len(set(mesi_occorrenza)) != len(mesi_occorrenza):
            raise ErroreAggregazione(
                f"L'adiacenza {studenti!r} compare più volte nello stesso mese."
            )
        usi_iniziali = eventi[0].usi_precedenti_totali
        for indice, evento in enumerate(eventi):
            if evento.usi_precedenti_nell_annata != indice:
                raise ErroreAggregazione(
                    f"Cronologia incoerente per {studenti!r} al mese {evento.mese}: "
                    f"usi nell'annata={evento.usi_precedenti_nell_annata}, attesi={indice}."
                )
            if evento.usi_precedenti_totali != usi_iniziali + indice:
                raise ErroreAggregazione(
                    f"Contatore totale incoerente per {studenti!r} al mese {evento.mese}."
                )
            if indice:
                distanza_attesa = mesi_occorrenza[indice] - mesi_occorrenza[indice - 1]
                if evento.distanza_mesi != distanza_attesa:
                    raise ErroreAggregazione(
                        f"Distanza incoerente per {studenti!r} al mese {evento.mese}."
                    )

        distanze = tuple(
            secondo - primo
            for primo, secondo in zip(mesi_occorrenza, mesi_occorrenza[1:])
        )
        risultato.append(
            CronologiaAdiacenza(
                canale_rotazione=canale,
                studenti=studenti,
                mesi_occorrenza=mesi_occorrenza,
                numero_occorrenze_annata=len(eventi),
                usi_storico_iniziale=usi_iniziali,
                numero_occorrenze_totali_finali=usi_iniziali + len(eventi),
                distanze_interne=distanze,
                coinvolge_fisso=any(evento.coinvolge_fisso for evento in eventi),
            )
        )
    return tuple(risultato)


def costruisci_serie_mensile(
    mesi: Iterable[MeseCanonico],
) -> tuple[PuntoSerieMensile, ...]:
    """Espone i riepiloghi mensili in una sequenza autonoma e ordinata."""
    risultato = []
    for mese in tuple(mesi):
        vicino = None
        if mese.vicino_fisso is not None:
            valore = mese.vicino_fisso.get("studente")
            vicino = str(valore).strip() if valore is not None else None
            if vicino == "":
                vicino = None
        risultato.append(
            PuntoSerieMensile(
                mese=mese.mese_finale,
                riepilogo=mese.riepilogo,
                vicino_fisso=vicino,
            )
        )
    return tuple(risultato)


def costruisci_riepilogo_annuale(
    mesi: Iterable[MeseCanonico],
    studenti: Sequence[RiepilogoStudente],
) -> RiepilogoAnnuale:
    """Somma i riepiloghi mensili e descrive la distribuzione individuale."""
    mesi = tuple(mesi)
    studenti = tuple(studenti)

    def somma(campo: str) -> int:
        return sum(getattr(mese.riepilogo, campo) for mese in mesi)

    carichi = [studente.riusi_coinvolgenti for studente in studenti]
    massimo = max(carichi, default=0)
    al_massimo = tuple(
        studente.studente
        for studente in studenti
        if studente.riusi_coinvolgenti == massimo
    )
    riepilogo = RiepilogoAnnuale(
        adiacenze_totali=somma("adiacenze_totali"),
        riusi_totali=somma("riusi_totali"),
        prime_ripetizioni=somma("prime_ripetizioni"),
        seconde_ripetizioni=somma("seconde_ripetizioni"),
        terze_o_ulteriori=somma("terze_o_ulteriori"),
        incompatibilita_l1=somma("incompatibilita_l1"),
        incompatibilita_l2=somma("incompatibilita_l2"),
        incompatibilita_l3=somma("incompatibilita_l3"),
        affinita_l1=somma("affinita_l1"),
        affinita_l2=somma("affinita_l2"),
        affinita_l3=somma("affinita_l3"),
        adiacenze_miste=somma("adiacenze_miste"),
        studenti_con_0_riusi=sum(carico == 0 for carico in carichi),
        studenti_con_1_riuso=sum(carico == 1 for carico in carichi),
        studenti_con_2_riusi=sum(carico == 2 for carico in carichi),
        studenti_con_3_o_piu_riusi=sum(carico >= 3 for carico in carichi),
        massimo_individuale=massimo,
        studenti_al_massimo=al_massimo,
    )
    if (
        riepilogo.studenti_con_0_riusi
        + riepilogo.studenti_con_1_riuso
        + riepilogo.studenti_con_2_riusi
        + riepilogo.studenti_con_3_o_piu_riusi
        != len(studenti)
    ):
        raise ErroreAggregazione("La distribuzione dei riusi non copre tutti gli studenti.")
    return riepilogo


def costruisci_ricerca_annuale(esito: EsitoC1) -> RicercaAnnuale:
    """Normalizza i metadati tecnici restituiti da ``genera_migliore_stagione``."""
    info = esito.info
    punteggio_raw = info.get("punteggio")
    punteggio = None if punteggio_raw is None else tuple(punteggio_raw)
    indice = info.get("indice_stagione_migliore")
    if indice is not None:
        indice = int(indice)
    motivo = info.get("motivo_stop")
    if motivo is None:
        motivo = "non_specificato"
    durata = info.get("elapsed")
    return RicercaAnnuale(
        stagioni_tentate=int(info.get("n_stagioni") or 0),
        stagioni_complete=int(info.get("n_stagioni_complete") or 0),
        indice_stagione_vincente=indice,
        motivo_arresto=str(motivo),
        punteggio_tecnico=punteggio,
        durata_secondi=None if durata is None else float(durata),
    )


def costruisci_annata_canonica(
    esito_c1: EsitoC1,
    cronologia: EsitoCronologiaI4,
    run: SpecificaRun,
    snapshot: SnapshotRotazioni,
    studenti: Sequence[Any],
    *,
    classe: str,
    studente_fisso: Any | None = None,
    versioni: VersioniOutput | None = None,
    metadati: Mapping[str, Any] | None = None,
) -> AnnataCanonica:
    """Compone la prima ``AnnataCanonica`` completa dell'osservatore."""
    verifica_snapshot(snapshot)
    if crea_stato_iniziale_id(snapshot) != run.stato_iniziale_id:
        raise ErroreAggregazione("Lo snapshot non coincide con lo stato iniziale del run.")
    if esito_c1.run_id != run.run_id or cronologia.run_id != run.run_id:
        raise ErroreAggregazione("Run, esito C1 e cronologia non coincidono.")
    if esito_c1.modalita != run.modalita or cronologia.modalita != run.modalita:
        raise ErroreAggregazione("La modalità non coincide fra run, C1 e cronologia.")
    if esito_c1.stato != cronologia.stato:
        raise ErroreAggregazione("Lo stato del run non coincide fra C1 e cronologia.")

    mesi = tuple(cronologia.mesi)
    riepiloghi_studenti = costruisci_riepiloghi_studenti(mesi, studenti)
    cronologie = costruisci_cronologia_adiacenze(mesi)
    serie = costruisci_serie_mensile(mesi)
    riepilogo = costruisci_riepilogo_annuale(mesi, riepiloghi_studenti)
    fisso = _nome_fisso(studente_fisso)

    metadati_output = dict(metadati or {})
    metadati_output.setdefault("chiavi_generazione", esito_c1.chiavi_generazione)
    metadati_output.setdefault("chiavi_finali", esito_c1.chiavi_finali)
    metadati_output.setdefault(
        "posizioni_generazione",
        tuple(traccia.posizione_generazione for traccia in esito_c1.traccia_riordino),
    )
    metadati_output.setdefault("numero_eventi", sum(len(mese.adiacenze) for mese in mesi))

    annata = AnnataCanonica(
        versioni=versioni or VersioniOutput(),
        run=run,
        stato=esito_c1.stato,
        classe=str(classe).strip(),
        numero_studenti=len(studenti),
        studente_fisso=fisso,
        snapshot_iniziale=snapshot,
        ricerca=costruisci_ricerca_annuale(esito_c1),
        mesi=mesi,
        studenti=riepiloghi_studenti,
        riepilogo=riepilogo,
        cronologia_adiacenze=cronologie,
        serie_mensile=serie,
        metadati=metadati_output,
    )
    # I6: il calcolo è post-hoc e puro; non interviene in alcuna scelta di C1.
    from .genere_misto import arricchisci_annata_genere_misto

    return arricchisci_annata_genere_misto(annata, studenti)


__all__ = [
    "ErroreAggregazione",
    "costruisci_annata_canonica",
    "costruisci_cronologia_adiacenze",
    "costruisci_ricerca_annuale",
    "costruisci_riepilogo_annuale",
    "costruisci_riepiloghi_studenti",
    "costruisci_serie_mensile",
]
