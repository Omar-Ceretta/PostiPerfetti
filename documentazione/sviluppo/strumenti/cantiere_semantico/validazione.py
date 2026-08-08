"""Validazione autosufficiente degli output canonici — incremento I7.

Il validatore opera sia sulle dataclass vive sia sul dizionario riletto da
``ANNATA.json``. La validazione del JSON non importa né interroga i motori
produttivi: il file deve contenere tutto ciò che serve a dimostrare la propria
coerenza interna.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .modelli import (
    AnnataCanonica,
    EsitoValidazione,
    GravitaValidazione,
    ProblemaValidazione,
    SCHEMA_OUTPUT_VERSIONE,
    StatoRun,
)
from .serializzazione import rendi_json_stabile


class ErroreValidazioneOutput(ValueError):
    """Segnala un uso non valido dell'API di validazione."""


@dataclass(slots=True)
class _Raccoglitore:
    problemi: list[ProblemaValidazione]

    def errore(self, codice: str, messaggio: str, percorso: str | None = None) -> None:
        self.problemi.append(
            ProblemaValidazione(
                codice=codice,
                messaggio=messaggio,
                gravita=GravitaValidazione.ERRORE,
                percorso=percorso,
            )
        )

    def avviso(self, codice: str, messaggio: str, percorso: str | None = None) -> None:
        self.problemi.append(
            ProblemaValidazione(
                codice=codice,
                messaggio=messaggio,
                gravita=GravitaValidazione.AVVISO,
                percorso=percorso,
            )
        )

    def esito(self) -> EsitoValidazione:
        return EsitoValidazione(
            valido=not any(
                problema.gravita == GravitaValidazione.ERRORE
                for problema in self.problemi
            ),
            problemi=tuple(self.problemi),
        )


def _mapping(valore: Any) -> Mapping[str, Any] | None:
    return valore if isinstance(valore, Mapping) else None


def _lista(valore: Any) -> Sequence[Any] | None:
    if isinstance(valore, list):
        return valore
    return None


def _intero_non_negativo(valore: Any) -> bool:
    return isinstance(valore, int) and not isinstance(valore, bool) and valore >= 0


def _intero_positivo(valore: Any) -> bool:
    return _intero_non_negativo(valore) and valore >= 1


def _testo_non_vuoto(valore: Any) -> bool:
    return isinstance(valore, str) and bool(valore.strip())


def _somma(record: Mapping[str, Any], campi: Iterable[str]) -> int | None:
    valori: list[int] = []
    for campo in campi:
        valore = record.get(campo)
        if not _intero_non_negativo(valore):
            return None
        valori.append(valore)
    return sum(valori)


def _conteggi_eventi(eventi: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    conteggi = {
        "adiacenze_totali": len(eventi),
        "riusi_totali": 0,
        "prime_ripetizioni": 0,
        "seconde_ripetizioni": 0,
        "terze_o_ulteriori": 0,
        "incompatibilita_l1": 0,
        "incompatibilita_l2": 0,
        "incompatibilita_l3": 0,
        "affinita_l1": 0,
        "affinita_l2": 0,
        "affinita_l3": 0,
        "adiacenze_miste": 0,
        "adiacenze_stesso_genere": 0,
    }
    for evento in eventi:
        if evento.get("e_riuso") is True:
            conteggi["riusi_totali"] += 1
        fascia = evento.get("fascia_ripetizione")
        if fascia == "prima_ripetizione":
            conteggi["prime_ripetizioni"] += 1
        elif fascia == "seconda_ripetizione":
            conteggi["seconde_ripetizioni"] += 1
        elif fascia == "terza_o_ulteriore":
            conteggi["terze_o_ulteriori"] += 1
        incompatibilita = evento.get("incompatibilita_livello")
        if incompatibilita in (1, 2, 3):
            conteggi[f"incompatibilita_l{incompatibilita}"] += 1
        affinita = evento.get("affinita_livello")
        if affinita in (1, 2, 3):
            conteggi[f"affinita_l{affinita}"] += 1
        if evento.get("adiacenza_mista") is True:
            conteggi["adiacenze_miste"] += 1
        else:
            conteggi["adiacenze_stesso_genere"] += 1
    return conteggi


def _valida_evento(
    evento: Mapping[str, Any],
    *,
    percorso: str,
    run_id: str | None,
    mese_numero: int | None,
    gruppi: Mapping[str, Sequence[str]],
    eventi_visti: set[str],
    raccoglitore: _Raccoglitore,
) -> None:
    event_id = evento.get("event_id")
    if not _testo_non_vuoto(event_id):
        raccoglitore.errore("EVENT_ID_ASSENTE", "event_id assente o vuoto.", f"{percorso}.event_id")
    elif event_id in eventi_visti:
        raccoglitore.errore("EVENT_ID_DUPLICATO", f"event_id duplicato: {event_id}.", f"{percorso}.event_id")
    else:
        eventi_visti.add(event_id)

    if run_id is not None and evento.get("run_id") != run_id:
        raccoglitore.errore("EVENT_RUN_DIVERSO", "L'evento appartiene a un run diverso.", f"{percorso}.run_id")
    if mese_numero is not None and evento.get("mese") != mese_numero:
        raccoglitore.errore("EVENT_MESE_DIVERSO", "Il mese dell'evento non coincide col record mensile.", f"{percorso}.mese")

    group_id = evento.get("group_id")
    membri = gruppi.get(str(group_id)) if _testo_non_vuoto(group_id) else None
    if membri is None:
        raccoglitore.errore("EVENT_GRUPPO_ASSENTE", "L'evento riferisce un gruppo inesistente.", f"{percorso}.group_id")
        return

    studente_a = evento.get("studente_a")
    studente_b = evento.get("studente_b")
    ordine_a = evento.get("ordine_a")
    ordine_b = evento.get("ordine_b")
    if not (_testo_non_vuoto(studente_a) and _testo_non_vuoto(studente_b)):
        raccoglitore.errore("EVENT_STUDENTI_INVALIDI", "Gli studenti dell'evento non sono validi.", percorso)
        return
    if not (_intero_non_negativo(ordine_a) and _intero_non_negativo(ordine_b)):
        raccoglitore.errore("EVENT_ORDINE_INVALIDO", "Gli indici fisici dell'evento non sono validi.", percorso)
        return
    if abs(ordine_a - ordine_b) != 1:
        raccoglitore.errore("EVENT_NON_CONSECUTIVO", "L'evento non collega posizioni consecutive.", percorso)
    if ordine_a >= len(membri) or ordine_b >= len(membri):
        raccoglitore.errore("EVENT_ORDINE_FUORI_GRUPPO", "Un indice dell'evento supera la dimensione del gruppo.", percorso)
    else:
        if membri[ordine_a] != studente_a or membri[ordine_b] != studente_b:
            raccoglitore.errore("EVENT_ORDINE_NON_COINCIDE", "Studenti e ordine fisico non coincidono col gruppo.", percorso)

    chiave = evento.get("chiave_adiacenza")
    if chiave != sorted((studente_a, studente_b)):
        raccoglitore.errore("EVENT_CHIAVE_INVALIDA", "La chiave non orientata non coincide con gli studenti.", f"{percorso}.chiave_adiacenza")

    incompatibilita = evento.get("incompatibilita_livello")
    affinita = evento.get("affinita_livello")
    if incompatibilita not in (0, 1, 2, 3):
        raccoglitore.errore("EVENT_INCOMPATIBILITA_INVALIDA", "Livello di incompatibilità non valido.", f"{percorso}.incompatibilita_livello")
    if affinita not in (0, 1, 2, 3):
        raccoglitore.errore("EVENT_AFFINITA_INVALIDA", "Livello di affinità non valido.", f"{percorso}.affinita_livello")
    if incompatibilita in (1, 2, 3) and affinita in (1, 2, 3):
        raccoglitore.errore("EVENT_RELAZIONE_DOPPIA", "Affinità e incompatibilità sono entrambe valorizzate.", percorso)
    if incompatibilita == 3:
        raccoglitore.errore("INCOMPATIBILITA_L3", "È stata collocata un'incompatibilità L3.", percorso)

    genere_a = evento.get("genere_a")
    genere_b = evento.get("genere_b")
    if genere_a not in ("M", "F") or genere_b not in ("M", "F"):
        raccoglitore.errore("EVENT_GENERE_INVALIDO", "Il genere deve essere M o F.", percorso)
    elif evento.get("adiacenza_mista") is not (genere_a != genere_b):
        raccoglitore.errore("EVENT_MISTO_INCOERENTE", "adiacenza_mista non coincide con i generi.", f"{percorso}.adiacenza_mista")

    usi_totali = evento.get("usi_precedenti_totali")
    usi_annata = evento.get("usi_precedenti_nell_annata")
    if not _intero_non_negativo(usi_totali) or not _intero_non_negativo(usi_annata):
        raccoglitore.errore("EVENT_USI_INVALIDI", "I contatori degli usi non sono validi.", percorso)
    elif usi_annata > usi_totali:
        raccoglitore.errore("EVENT_USI_INCOERENTI", "Gli usi nell'annata superano quelli totali.", percorso)
    if _intero_non_negativo(usi_totali):
        if evento.get("e_riuso") is not (usi_totali > 0):
            raccoglitore.errore("EVENT_FLAG_RIUSO", "e_riuso non coincide con gli usi precedenti.", percorso)
        numero = evento.get("numero_ripetizione")
        fascia = evento.get("fascia_ripetizione")
        if usi_totali == 0:
            if numero is not None or fascia != "prima_comparsa":
                raccoglitore.errore("EVENT_PRIMA_COMPARSA", "Prima comparsa e fascia di ripetizione sono incoerenti.", percorso)
        else:
            fascia_attesa = "prima_ripetizione" if usi_totali == 1 else "seconda_ripetizione" if usi_totali == 2 else "terza_o_ulteriore"
            if numero != usi_totali or fascia != fascia_attesa:
                raccoglitore.errore("EVENT_ORDINALE_RIUSO", "Ordinale o fascia della ripetizione non coincidono.", percorso)

    ultimo = _mapping(evento.get("ultimo_uso"))
    if ultimo is None:
        raccoglitore.errore("EVENT_ULTIMO_USO_ASSENTE", "ultimo_uso deve essere un oggetto.", f"{percorso}.ultimo_uso")
    else:
        origine = ultimo.get("origine")
        distanza = evento.get("distanza_mesi")
        if origine == "annata_corrente":
            mese_precedente = ultimo.get("mese_annata")
            if not (_intero_positivo(mese_precedente) and _intero_positivo(distanza)):
                raccoglitore.errore("EVENT_DISTANZA_ASSENTE", "Un precedente nell'annata richiede mese e distanza.", percorso)
            elif mese_numero is not None and mese_numero - mese_precedente != distanza:
                raccoglitore.errore("EVENT_DISTANZA_INCOERENTE", "La distanza non coincide coi mesi dichiarati.", percorso)
        elif origine in ("nessuno", "storico_iniziale"):
            if distanza is not None:
                raccoglitore.errore("EVENT_DISTANZA_NON_APPLICABILE", "La distanza è valorizzata fuori dall'annata corrente.", percorso)
        else:
            raccoglitore.errore("EVENT_ORIGINE_INVALIDA", "Origine dell'ultimo uso non riconosciuta.", f"{percorso}.ultimo_uso.origine")


def _valida_mese(
    mese: Mapping[str, Any],
    *,
    indice: int,
    studenti_attesi: set[str],
    run_id: str | None,
    eventi_visti: set[str],
    gruppi_visti: set[str],
    raccoglitore: _Raccoglitore,
) -> dict[str, int] | None:
    percorso = f"mesi[{indice}]"
    mese_numero = mese.get("mese_finale")
    if not _intero_positivo(mese_numero):
        raccoglitore.errore("MESE_NUMERO_INVALIDO", "mese_finale deve essere positivo.", f"{percorso}.mese_finale")
        mese_numero = None
    if mese.get("posizione_finale") != mese_numero:
        raccoglitore.errore("MESE_POSIZIONE_FINALE", "mese_finale e posizione_finale non coincidono.", percorso)
    if not _intero_positivo(mese.get("posizione_generazione")):
        raccoglitore.errore("MESE_POSIZIONE_GENERAZIONE", "posizione_generazione non valida.", f"{percorso}.posizione_generazione")

    gruppi_raw = _lista(mese.get("gruppi"))
    eventi_raw = _lista(mese.get("adiacenze"))
    riepilogo = _mapping(mese.get("riepilogo"))
    if gruppi_raw is None:
        raccoglitore.errore("MESE_GRUPPI_INVALIDI", "gruppi deve essere una lista.", f"{percorso}.gruppi")
        gruppi_raw = []
    if eventi_raw is None:
        raccoglitore.errore("MESE_EVENTI_INVALIDI", "adiacenze deve essere una lista.", f"{percorso}.adiacenze")
        eventi_raw = []
    if riepilogo is None:
        raccoglitore.errore("MESE_RIEPILOGO_INVALIDO", "riepilogo deve essere un oggetto.", f"{percorso}.riepilogo")

    gruppi: dict[str, Sequence[str]] = {}
    presenze: list[str] = []
    attesi_eventi: Counter[tuple[str, str, str, int, int]] = Counter()
    for j, gruppo_raw in enumerate(gruppi_raw):
        gruppo = _mapping(gruppo_raw)
        gp = f"{percorso}.gruppi[{j}]"
        if gruppo is None:
            raccoglitore.errore("GRUPPO_INVALIDO", "Il gruppo deve essere un oggetto.", gp)
            continue
        group_id = gruppo.get("group_id")
        membri = _lista(gruppo.get("membri_ordinati"))
        if not _testo_non_vuoto(group_id):
            raccoglitore.errore("GROUP_ID_ASSENTE", "group_id assente o vuoto.", f"{gp}.group_id")
            continue
        if group_id in gruppi_visti:
            raccoglitore.errore("GROUP_ID_DUPLICATO", f"group_id duplicato: {group_id}.", f"{gp}.group_id")
        else:
            gruppi_visti.add(group_id)
        if membri is None or len(membri) not in (2, 3, 4) or any(not _testo_non_vuoto(x) for x in membri):
            raccoglitore.errore("GRUPPO_MEMBRI_INVALIDI", "Il gruppo deve contenere 2, 3 o 4 nomi validi.", f"{gp}.membri_ordinati")
            continue
        if len(set(membri)) != len(membri):
            raccoglitore.errore("GRUPPO_DUPLICATO_INTERNO", "Uno studente compare due volte nello stesso gruppo.", gp)
        gruppi[group_id] = membri
        presenze.extend(membri)
        for ordine in range(len(membri) - 1):
            attesi_eventi[(group_id, membri[ordine], membri[ordine + 1], ordine, ordine + 1)] += 1

    conteggio_presenze = Counter(presenze)
    for studente, numero in sorted(conteggio_presenze.items()):
        if numero != 1:
            raccoglitore.errore("STUDENTE_DUPLICATO_NEL_MESE", f"{studente} compare {numero} volte nel mese.", percorso)
    mancanti = studenti_attesi - set(presenze)
    estranei = set(presenze) - studenti_attesi
    if mancanti:
        raccoglitore.errore("STUDENTI_MANCANTI", f"Studenti non collocati: {', '.join(sorted(mancanti))}.", percorso)
    if estranei:
        raccoglitore.errore("STUDENTI_ESTRANEI", f"Studenti non appartenenti al run: {', '.join(sorted(estranei))}.", percorso)

    eventi: list[Mapping[str, Any]] = []
    effettivi_eventi: Counter[tuple[str, str, str, int, int]] = Counter()
    for j, evento_raw in enumerate(eventi_raw):
        evento = _mapping(evento_raw)
        ep = f"{percorso}.adiacenze[{j}]"
        if evento is None:
            raccoglitore.errore("EVENTO_INVALIDO", "L'evento deve essere un oggetto.", ep)
            continue
        eventi.append(evento)
        _valida_evento(
            evento,
            percorso=ep,
            run_id=run_id,
            mese_numero=mese_numero,
            gruppi=gruppi,
            eventi_visti=eventi_visti,
            raccoglitore=raccoglitore,
        )
        if all(
            chiave in evento
            for chiave in ("group_id", "studente_a", "studente_b", "ordine_a", "ordine_b")
        ):
            effettivi_eventi[(
                evento["group_id"], evento["studente_a"], evento["studente_b"],
                evento["ordine_a"], evento["ordine_b"],
            )] += 1

    if effettivi_eventi != attesi_eventi:
        raccoglitore.errore(
            "EVENTI_NON_COINCIDONO_COI_GRUPPI",
            "Gli eventi non coincidono esattamente con tutte le adiacenze consecutive dei gruppi.",
            f"{percorso}.adiacenze",
        )

    conteggi = _conteggi_eventi(eventi)
    if riepilogo is not None:
        for campo, atteso in conteggi.items():
            if riepilogo.get(campo) != atteso:
                raccoglitore.errore(
                    "RIEPILOGO_MENSILE_INCOERENTE",
                    f"{campo}: dichiarato {riepilogo.get(campo)!r}, calcolato dagli eventi {atteso}.",
                    f"{percorso}.riepilogo.{campo}",
                )
    return conteggi


def _valida_cronologia(
    cronologie_raw: Sequence[Any],
    eventi_per_chiave: Mapping[tuple[str, tuple[str, str]], list[Mapping[str, Any]]],
    raccoglitore: _Raccoglitore,
) -> None:
    viste: set[tuple[str, tuple[str, str]]] = set()
    for i, raw in enumerate(cronologie_raw):
        cronologia = _mapping(raw)
        percorso = f"cronologia_adiacenze[{i}]"
        if cronologia is None:
            raccoglitore.errore("CRONOLOGIA_INVALIDA", "La cronologia deve essere un oggetto.", percorso)
            continue
        canale = cronologia.get("canale_rotazione")
        studenti_raw = _lista(cronologia.get("studenti"))
        if canale not in ("coppie", "terzetti", "vicino_fisso") or studenti_raw is None or len(studenti_raw) != 2:
            raccoglitore.errore("CRONOLOGIA_IDENTITA", "Canale o studenti della cronologia non validi.", percorso)
            continue
        studenti = tuple(sorted(str(x) for x in studenti_raw))
        chiave = (canale, studenti)
        if chiave in viste:
            raccoglitore.errore("CRONOLOGIA_DUPLICATA", "Cronologia duplicata.", percorso)
        viste.add(chiave)
        eventi = eventi_per_chiave.get(chiave, [])
        mesi_attesi = [int(evento["mese"]) for evento in eventi]
        if cronologia.get("mesi_occorrenza") != mesi_attesi:
            raccoglitore.errore("CRONOLOGIA_MESI", "I mesi della cronologia non coincidono con gli eventi.", f"{percorso}.mesi_occorrenza")
        if cronologia.get("numero_occorrenze_annata") != len(eventi):
            raccoglitore.errore("CRONOLOGIA_CONTEGGIO", "Il conteggio annuale non coincide con gli eventi.", percorso)
        storico = cronologia.get("usi_storico_iniziale")
        totale = cronologia.get("numero_occorrenze_totali_finali")
        if _intero_non_negativo(storico) and totale != storico + len(eventi):
            raccoglitore.errore("CRONOLOGIA_TOTALE", "Il totale finale non coincide con storico e annata.", percorso)
        distanze_attese = [b - a for a, b in zip(mesi_attesi, mesi_attesi[1:])]
        if cronologia.get("distanze_interne") != distanze_attese:
            raccoglitore.errore("CRONOLOGIA_DISTANZE", "Le distanze interne non coincidono coi mesi.", percorso)
    mancanti = set(eventi_per_chiave) - viste
    if mancanti:
        raccoglitore.errore("CRONOLOGIE_MANCANTI", f"Mancano {len(mancanti)} cronologie relative agli eventi.", "cronologia_adiacenze")


def valida_dati_annata(dati: Any) -> EsitoValidazione:
    """Valida il contenuto riletto da ``ANNATA.json``.

    La funzione non presuppone che il file sia stato costruito dalle dataclass:
    tratta l'input come dato non fidato e raccoglie tutti i problemi rilevabili.
    """
    raccoglitore = _Raccoglitore([])
    radice = _mapping(dati)
    if radice is None:
        raccoglitore.errore("RADICE_INVALIDA", "ANNATA.json deve contenere un oggetto JSON.", "$")
        return raccoglitore.esito()

    richieste = {
        "versioni", "run", "stato", "classe", "numero_studenti", "studente_fisso",
        "snapshot_iniziale", "ricerca", "mesi", "studenti", "riepilogo",
        "cronologia_adiacenze", "serie_mensile", "genere_misto", "metadati",
    }
    mancanti = richieste - set(radice)
    sconosciute = set(radice) - richieste
    for campo in sorted(mancanti):
        raccoglitore.errore("CAMPO_RADICE_MANCANTE", f"Campo obbligatorio mancante: {campo}.", f"$.{campo}")
    for campo in sorted(sconosciute):
        raccoglitore.errore("CAMPO_RADICE_SCONOSCIUTO", f"Campo non previsto dallo schema: {campo}.", f"$.{campo}")

    versioni = _mapping(radice.get("versioni"))
    if versioni is None:
        raccoglitore.errore("VERSIONI_INVALIDE", "versioni deve essere un oggetto.", "versioni")
    else:
        if versioni.get("schema") != SCHEMA_OUTPUT_VERSIONE:
            raccoglitore.errore("SCHEMA_NON_SUPPORTATO", f"Schema atteso: {SCHEMA_OUTPUT_VERSIONE}.", "versioni.schema")
        if versioni.get("strategia") != "C1":
            raccoglitore.errore("STRATEGIA_NON_C1", "L'osservatore R0.1 accetta soltanto C1.", "versioni.strategia")

    run = _mapping(radice.get("run"))
    run_id: str | None = None
    numero_mesi: int | None = None
    condizione: str | None = None
    if run is None:
        raccoglitore.errore("RUN_INVALIDO", "run deve essere un oggetto.", "run")
    else:
        run_id = run.get("run_id") if _testo_non_vuoto(run.get("run_id")) else None
        if run_id is None:
            raccoglitore.errore("RUN_ID_INVALIDO", "run_id assente o vuoto.", "run.run_id")
        numero_mesi = run.get("numero_mesi") if _intero_positivo(run.get("numero_mesi")) else None
        if numero_mesi is None:
            raccoglitore.errore("RUN_NUMERO_MESI", "numero_mesi non valido.", "run.numero_mesi")
        condizione = run.get("condizione")
        if condizione not in ("senza_fisso", "con_fisso"):
            raccoglitore.errore("RUN_CONDIZIONE", "condizione non riconosciuta.", "run.condizione")
        if run.get("modalita") not in ("coppie", "terzetti"):
            raccoglitore.errore("RUN_MODALITA", "modalità non riconosciuta.", "run.modalita")
        if not isinstance(run.get("genere_misto_attivo"), bool):
            raccoglitore.errore("RUN_FLAG_GENERE", "genere_misto_attivo deve essere booleano.", "run.genere_misto_attivo")

    stato = radice.get("stato")
    stati_ammessi = {x.value for x in StatoRun}
    if stato not in stati_ammessi:
        raccoglitore.errore("STATO_RUN_INVALIDO", "Stato del run non riconosciuto.", "stato")

    studente_fisso = radice.get("studente_fisso")
    if condizione == "con_fisso" and not _testo_non_vuoto(studente_fisso):
        raccoglitore.errore("FISSO_ASSENTE", "Un run con FISSO deve indicare lo studente.", "studente_fisso")
    if condizione == "senza_fisso" and studente_fisso is not None:
        raccoglitore.errore("FISSO_IN_RUN_SENZA", "Un run senza FISSO non può indicarlo.", "studente_fisso")

    numero_studenti = radice.get("numero_studenti")
    if not _intero_positivo(numero_studenti):
        raccoglitore.errore("NUMERO_STUDENTI_INVALIDO", "numero_studenti deve essere positivo.", "numero_studenti")
        numero_studenti = None

    studenti_raw = _lista(radice.get("studenti"))
    studenti_attesi: set[str] = set()
    if studenti_raw is None:
        raccoglitore.errore("STUDENTI_INVALIDI", "studenti deve essere una lista.", "studenti")
        studenti_raw = []
    for i, raw in enumerate(studenti_raw):
        studente = _mapping(raw)
        percorso = f"studenti[{i}]"
        if studente is None or not _testo_non_vuoto(studente.get("studente")):
            raccoglitore.errore("STUDENTE_INVALIDO", "Riepilogo studente non valido.", percorso)
            continue
        nome = studente["studente"]
        if nome in studenti_attesi:
            raccoglitore.errore("STUDENTE_RIEPILOGO_DUPLICATO", f"Riepilogo duplicato per {nome}.", percorso)
        studenti_attesi.add(nome)
    if numero_studenti is not None and len(studenti_raw) != numero_studenti:
        raccoglitore.errore("NUMERO_STUDENTI_NON_COINCIDE", "Il numero dei riepiloghi studenti non coincide.", "studenti")

    mesi_raw = _lista(radice.get("mesi"))
    if mesi_raw is None:
        raccoglitore.errore("MESI_INVALIDI", "mesi deve essere una lista.", "mesi")
        mesi_raw = []
    if stato == "completo" and numero_mesi is not None and len(mesi_raw) != numero_mesi:
        raccoglitore.errore("MESI_INCOMPLETI", "Un run completo non contiene tutti i mesi richiesti.", "mesi")

    eventi_visti: set[str] = set()
    gruppi_visti: set[str] = set()
    conteggi_mesi: list[dict[str, int]] = []
    numeri_mesi: list[int] = []
    eventi_per_chiave: defaultdict[tuple[str, tuple[str, str]], list[Mapping[str, Any]]] = defaultdict(list)
    for i, raw in enumerate(mesi_raw):
        mese = _mapping(raw)
        if mese is None:
            raccoglitore.errore("MESE_INVALIDO", "Il mese deve essere un oggetto.", f"mesi[{i}]")
            continue
        if _intero_positivo(mese.get("mese_finale")):
            numeri_mesi.append(mese["mese_finale"])
        conteggi = _valida_mese(
            mese,
            indice=i,
            studenti_attesi=studenti_attesi,
            run_id=run_id,
            eventi_visti=eventi_visti,
            gruppi_visti=gruppi_visti,
            raccoglitore=raccoglitore,
        )
        if conteggi is not None:
            conteggi_mesi.append(conteggi)
        for evento_raw in _lista(mese.get("adiacenze")) or []:
            evento = _mapping(evento_raw)
            if evento is None:
                continue
            canale = evento.get("canale_rotazione")
            chiave_raw = _lista(evento.get("chiave_adiacenza"))
            if canale in ("coppie", "terzetti", "vicino_fisso") and chiave_raw is not None and len(chiave_raw) == 2:
                eventi_per_chiave[(canale, tuple(sorted(str(x) for x in chiave_raw)))].append(evento)

    if numeri_mesi and numeri_mesi != list(range(1, len(numeri_mesi) + 1)):
        raccoglitore.errore("SEQUENZA_MESI", "I mesi finali devono essere consecutivi a partire da 1.", "mesi")
    posizioni_generazione = [m.get("posizione_generazione") for m in mesi_raw if isinstance(m, Mapping)]
    if posizioni_generazione and sorted(posizioni_generazione) != list(range(1, len(posizioni_generazione) + 1)):
        raccoglitore.errore("SEQUENZA_GENERAZIONE", "Le posizioni di generazione non formano una permutazione completa.", "mesi")

    riepilogo_annuale = _mapping(radice.get("riepilogo"))
    if riepilogo_annuale is None:
        raccoglitore.errore("RIEPILOGO_ANNUALE_INVALIDO", "riepilogo deve essere un oggetto.", "riepilogo")
    elif conteggi_mesi:
        campi_sommabili = tuple(conteggi_mesi[0])
        for campo in campi_sommabili:
            if campo == "adiacenze_stesso_genere":
                continue
            atteso = sum(conteggio[campo] for conteggio in conteggi_mesi)
            nome_annuale = "adiacenze_miste" if campo == "adiacenze_miste" else campo
            if riepilogo_annuale.get(nome_annuale) != atteso:
                raccoglitore.errore(
                    "RIEPILOGO_ANNUALE_INCOERENTE",
                    f"{nome_annuale}: dichiarato {riepilogo_annuale.get(nome_annuale)!r}, somma dei mesi {atteso}.",
                    f"riepilogo.{nome_annuale}",
                )
        if riepilogo_annuale.get("incompatibilita_l3") != 0:
            raccoglitore.errore("RIEPILOGO_L3", "Il totale annuale L3 deve essere zero.", "riepilogo.incompatibilita_l3")

    serie = _lista(radice.get("serie_mensile"))
    if serie is None:
        raccoglitore.errore("SERIE_MENSILE_INVALIDA", "serie_mensile deve essere una lista.", "serie_mensile")
    else:
        if [x.get("mese") for x in serie if isinstance(x, Mapping)] != numeri_mesi:
            raccoglitore.errore("SERIE_MENSILE_MESI", "La serie mensile non coincide coi mesi canonici.", "serie_mensile")
        for i, (punto_raw, conteggi) in enumerate(zip(serie, conteggi_mesi)):
            punto = _mapping(punto_raw)
            if punto is None or punto.get("riepilogo") != conteggi:
                raccoglitore.errore("SERIE_MENSILE_RIEPILOGO", "Il riepilogo della serie non coincide col mese.", f"serie_mensile[{i}]")

    cronologie = _lista(radice.get("cronologia_adiacenze"))
    if cronologie is None:
        raccoglitore.errore("CRONOLOGIE_INVALIDE", "cronologia_adiacenze deve essere una lista.", "cronologia_adiacenze")
    else:
        _valida_cronologia(cronologie, eventi_per_chiave, raccoglitore)

    genere = radice.get("genere_misto")
    if genere is not None:
        genere_mappa = _mapping(genere)
        if genere_mappa is None:
            raccoglitore.errore("GENERE_MISTO_INVALIDO", "genere_misto deve essere un oggetto o null.", "genere_misto")
        else:
            mesi_genere = _lista(genere_mappa.get("mesi"))
            if mesi_genere is None or len(mesi_genere) != len(mesi_raw):
                raccoglitore.errore("GENERE_MISTO_MESI", "L'analisi di genere non coincide coi mesi.", "genere_misto.mesi")
            else:
                geo = amm = ottenute = 0
                for i, raw in enumerate(mesi_genere):
                    analisi = _mapping(raw)
                    if analisi is None:
                        raccoglitore.errore("GENERE_MISTO_MESE_INVALIDO", "Analisi mensile non valida.", f"genere_misto.mesi[{i}]")
                        continue
                    massimo_geo = _mapping(analisi.get("massimo_geometrico"))
                    massimo_amm = _mapping(analisi.get("massimo_ammissibile"))
                    if massimo_geo is None or massimo_amm is None:
                        raccoglitore.errore("GENERE_MISTO_MASSIMO_ASSENTE", "Mancano i due massimi esatti.", f"genere_misto.mesi[{i}]")
                        continue
                    vg, va = massimo_geo.get("valore"), massimo_amm.get("valore")
                    vo = analisi.get("adiacenze_miste_ottenute")
                    if not all(_intero_non_negativo(x) for x in (vg, va, vo)):
                        raccoglitore.errore("GENERE_MISTO_VALORI", "Valori di genere misto non validi.", f"genere_misto.mesi[{i}]")
                        continue
                    if massimo_geo.get("esatto") is not True or massimo_amm.get("esatto") is not True:
                        raccoglitore.errore("GENERE_MISTO_NON_ESATTO", "I massimi della raccolta R0.1 devono essere esatti.", f"genere_misto.mesi[{i}]")
                    if va > vg or vo > va:
                        raccoglitore.errore("GENERE_MISTO_ORDINE", "Deve valere ottenuto ≤ ammissibile ≤ geometrico.", f"genere_misto.mesi[{i}]")
                    if i < len(conteggi_mesi) and vo != conteggi_mesi[i]["adiacenze_miste"]:
                        raccoglitore.errore("GENERE_MISTO_OTTENUTO", "Il risultato ottenuto non coincide con gli eventi.", f"genere_misto.mesi[{i}]")
                    geo += vg
                    amm += va
                    ottenute += vo
                if genere_mappa.get("massimo_geometrico_totale") != geo:
                    raccoglitore.errore("GENERE_MISTO_TOTALE_GEO", "Totale geometrico incoerente.", "genere_misto.massimo_geometrico_totale")
                if genere_mappa.get("massimo_ammissibile_totale") != amm:
                    raccoglitore.errore("GENERE_MISTO_TOTALE_AMM", "Totale ammissibile incoerente.", "genere_misto.massimo_ammissibile_totale")
                if genere_mappa.get("adiacenze_miste_ottenute_totali") != ottenute:
                    raccoglitore.errore("GENERE_MISTO_TOTALE_OTTENUTO", "Totale ottenuto incoerente.", "genere_misto.adiacenze_miste_ottenute_totali")

    return raccoglitore.esito()


def valida_annata(annata: AnnataCanonica) -> EsitoValidazione:
    """Valida una dataclass viva passando dallo stesso schema del JSON."""
    if not isinstance(annata, AnnataCanonica):
        raise ErroreValidazioneOutput("valida_annata richiede AnnataCanonica.")
    return valida_dati_annata(rendi_json_stabile(annata))


def richiedi_annata_valida(annata: AnnataCanonica) -> None:
    """Solleva ``ErroreValidazioneOutput`` se l'annata non è valida."""
    esito = valida_annata(annata)
    if esito.valido:
        return
    dettagli = "\n".join(
        f"- {problema.codice}: {problema.messaggio}"
        + (f" [{problema.percorso}]" if problema.percorso else "")
        for problema in esito.problemi
        if problema.gravita == GravitaValidazione.ERRORE
    )
    raise ErroreValidazioneOutput(f"Annata canonica non valida:\n{dettagli}")
