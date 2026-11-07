# -*- coding: utf-8 -*-
"""Normalizzazione visuale della piantina Personalizzata.

Il modello/editor conserva le coordinate logiche scelte dal docente. La vista
finale ``Aula`` non deve però trasformare ogni casella vuota in spazio fisico:
questa unità pura compatta le file, rende costanti i corridoi fra blocchi e
mantiene soltanto l'informazione topologica utile (ordine, eccentricità e
laterali rispetto alla postazione docente).

Non importa Qt e non modifica lo ``SchemaBlocchiSemantico`` usato dal motore.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from moduli.dominio.aula import ConfigurazioneAula, PostoAula


CORRIDOIO_UNITA = 0.30
LARGHEZZA_DOCENTE_UNITA = 2.25
DISTANZA_DOCENTE_UNITA = 0.38
MARGINE_LATERALE_UNITA = 0.55
LARGHEZZA_MINIMA_CAMPO_UNITA = 8.4


@dataclass(frozen=True, slots=True)
class BloccoPresentazionePersonalizzata:
    """Posizione normalizzata di un blocco nella vista finale."""

    blocco: Any
    x_unita: float
    fila_dal_docente: int | None
    fianco_docente: bool = False

    @property
    def id(self) -> str:
        return str(self.blocco.id)

    @property
    def capienza(self) -> int:
        return int(self.blocco.capienza)

    @property
    def x_finale_unita(self) -> float:
        return self.x_unita + self.capienza


@dataclass(frozen=True, slots=True)
class LayoutPresentazioneAulaPersonalizzata:
    """Layout compatto, espresso in unità di larghezza-posto."""

    blocchi: tuple[BloccoPresentazionePersonalizzata, ...]
    larghezza_unita: float
    numero_file: int
    x_docente_unita: float
    larghezza_docente_unita: float = LARGHEZZA_DOCENTE_UNITA

    def per_id(self, id_blocco: str) -> BloccoPresentazionePersonalizzata:
        for elemento in self.blocchi:
            if elemento.id == id_blocco:
                return elemento
        raise KeyError(id_blocco)


def _valida_blocchi(blocchi: tuple[Any, ...]) -> None:
    ids: set[str] = set()
    for blocco in blocchi:
        for attributo in ("id", "capienza", "riga", "colonna"):
            if not hasattr(blocco, attributo):
                raise TypeError(
                    "Blocco visuale Personalizzata privo dell'attributo "
                    f"{attributo!r}."
                )
        id_blocco = str(blocco.id)
        if id_blocco in ids:
            raise ValueError(f"ID blocco duplicato nel layout visuale: {id_blocco!r}.")
        ids.add(id_blocco)
        if int(blocco.capienza) not in (2, 3):
            raise ValueError("La presentazione supporta soltanto blocchi da 2 o 3 posti.")
        if int(blocco.riga) < 0 or int(blocco.colonna) < 0:
            raise ValueError("Riga e colonna visuali devono essere non negative.")


def _larghezza_compatta(blocchi: list[Any]) -> float:
    if not blocchi:
        return 0.0
    return (
        sum(int(blocco.capienza) for blocco in blocchi)
        + CORRIDOIO_UNITA * (len(blocchi) - 1)
    )


def _posizioni_compatte(blocchi: list[Any], start: float) -> dict[str, float]:
    risultato: dict[str, float] = {}
    x = start
    for indice, blocco in enumerate(blocchi):
        risultato[str(blocco.id)] = x
        x += int(blocco.capienza)
        if indice < len(blocchi) - 1:
            x += CORRIDOIO_UNITA
    return risultato


def costruisci_layout_presentazione_personalizzata(
    istantanea,
    *,
    max_colonne_editor: int = 16,
    riga_fianco_docente: int = 0,
) -> LayoutPresentazioneAulaPersonalizzata:
    """Compatta una fotografia dell'editor per la scheda ``Aula``.

    Regole:
    - le righe vuote vengono eliminate: resta l'ordine davanti→fondo;
    - fra due blocchi della stessa fila rimane un solo corridoio standard;
    - l'eccentricità sinistra/destra di ogni fila viene conservata tramite il
      centro originario della fila, senza conservare la quantità di caselle vuote;
    - i blocchi della fascia docente restano ai lati di una postazione centrale.
    """

    if max_colonne_editor <= 0:
        raise ValueError("max_colonne_editor deve essere positivo.")
    if not hasattr(istantanea, "blocchi"):
        raise TypeError("istantanea deve esporre la sequenza 'blocchi'.")

    blocchi = tuple(istantanea.blocchi)
    _valida_blocchi(blocchi)

    laterali = sorted(
        (b for b in blocchi if int(b.riga) == riga_fianco_docente),
        key=lambda b: (int(b.colonna), str(b.id)),
    )
    regolari = tuple(b for b in blocchi if int(b.riga) != riga_fianco_docente)
    righe_originali = sorted({int(b.riga) for b in regolari})
    indice_fila = {riga: indice for indice, riga in enumerate(righe_originali)}

    righe: dict[int, list[Any]] = {}
    for blocco in regolari:
        righe.setdefault(int(blocco.riga), []).append(blocco)
    for riga in righe:
        righe[riga].sort(key=lambda b: (int(b.colonna), str(b.id)))

    larghezza_regolare_massima = max(
        (_larghezza_compatta(righe[riga]) for riga in righe_originali),
        default=0.0,
    )

    centro_editor = max_colonne_editor / 2.0
    sinistra = [
        b for b in laterali
        if int(b.colonna) + int(b.capienza) / 2.0 <= centro_editor
    ]
    destra = [b for b in laterali if b not in sinistra]
    larghezza_sx = _larghezza_compatta(sinistra)
    larghezza_dx = _larghezza_compatta(destra)

    larghezza_fascia_docente = (
        2.0 * max(larghezza_sx, larghezza_dx)
        + LARGHEZZA_DOCENTE_UNITA
        + 2.0 * DISTANZA_DOCENTE_UNITA
    )
    larghezza_campo = max(
        LARGHEZZA_MINIMA_CAMPO_UNITA,
        larghezza_regolare_massima + 2.0 * MARGINE_LATERALE_UNITA,
        larghezza_fascia_docente + 2.0 * MARGINE_LATERALE_UNITA,
    )

    elementi: list[BloccoPresentazionePersonalizzata] = []

    # Le file normali vengono compattate internamente, ma mantengono una
    # eccentricità coerente con il loro centro nell'editor.
    for riga in righe_originali:
        blocchi_riga = righe[riga]
        larghezza = _larghezza_compatta(blocchi_riga)
        originale_sx = min(int(b.colonna) for b in blocchi_riga)
        originale_dx = max(int(b.colonna) + int(b.capienza) for b in blocchi_riga)
        centro_normalizzato = ((originale_sx + originale_dx) / 2.0) / max_colonne_editor
        centro_normalizzato = min(1.0, max(0.0, centro_normalizzato))
        centro_desiderato = centro_normalizzato * larghezza_campo
        start_massimo = max(0.0, larghezza_campo - larghezza)
        start = min(start_massimo, max(0.0, centro_desiderato - larghezza / 2.0))
        posizioni = _posizioni_compatte(blocchi_riga, start)
        for blocco in blocchi_riga:
            elementi.append(
                BloccoPresentazionePersonalizzata(
                    blocco=blocco,
                    x_unita=posizioni[str(blocco.id)],
                    fila_dal_docente=indice_fila[riga],
                    fianco_docente=False,
                )
            )

    # La postazione docente resta geometricamente centrata; eventuali blocchi
    # della riga 0 vengono avvicinati ai suoi lati, con un solo corridoio.
    x_docente = (larghezza_campo - LARGHEZZA_DOCENTE_UNITA) / 2.0
    if sinistra:
        start_sx = x_docente - DISTANZA_DOCENTE_UNITA - larghezza_sx
        posizioni = _posizioni_compatte(sinistra, start_sx)
        for blocco in sinistra:
            elementi.append(
                BloccoPresentazionePersonalizzata(
                    blocco=blocco,
                    x_unita=posizioni[str(blocco.id)],
                    fila_dal_docente=None,
                    fianco_docente=True,
                )
            )
    if destra:
        start_dx = x_docente + LARGHEZZA_DOCENTE_UNITA + DISTANZA_DOCENTE_UNITA
        posizioni = _posizioni_compatte(destra, start_dx)
        for blocco in destra:
            elementi.append(
                BloccoPresentazionePersonalizzata(
                    blocco=blocco,
                    x_unita=posizioni[str(blocco.id)],
                    fila_dal_docente=None,
                    fianco_docente=True,
                )
            )

    elementi.sort(
        key=lambda e: (
            -1 if e.fianco_docente else int(e.fila_dal_docente or 0),
            e.x_unita,
            e.id,
        )
    )
    return LayoutPresentazioneAulaPersonalizzata(
        blocchi=tuple(elementi),
        larghezza_unita=larghezza_campo,
        numero_file=len(righe_originali),
        x_docente_unita=x_docente,
    )

# ==========================================================================
# P3.2c — adattamento alla griglia Aula storica
# ==========================================================================

CORRIDOIO_COLONNE = 1
LARGHEZZA_POSTAZIONE_DOCENTE = 2
CORSIE_MINIME = 3


@dataclass(frozen=True, slots=True)
class BloccoGrigliaClassicaPersonalizzata:
    """Collocazione di un blocco nella griglia condivisa dell'Aula storica."""

    blocco: Any
    colonna: int
    fila_dal_docente: int | None
    fianco_docente: bool = False

    @property
    def id(self) -> str:
        return str(self.blocco.id)

    @property
    def capienza(self) -> int:
        return int(self.blocco.capienza)


@dataclass(frozen=True, slots=True)
class PianoGrigliaClassicaPersonalizzata:
    """Piano intero a corsie comuni usato dal ``QGridLayout`` storico."""

    blocchi: tuple[BloccoGrigliaClassicaPersonalizzata, ...]
    numero_colonne: int
    numero_file: int
    colonna_postazione_docente: int
    larghezza_postazione_docente: int = LARGHEZZA_POSTAZIONE_DOCENTE

    def per_id(self, id_blocco: str) -> BloccoGrigliaClassicaPersonalizzata:
        for elemento in self.blocchi:
            if elemento.id == id_blocco:
                return elemento
        raise KeyError(id_blocco)


def _centro_blocco(blocco: Any) -> float:
    return int(blocco.colonna) + int(blocco.capienza) / 2.0


def _assegna_corsie(
    blocchi_riga: list[Any],
    *,
    numero_corsie: int,
    max_colonne_editor: int,
) -> tuple[int, ...]:
    """Assegna una fila a corsie globali, preservando ordine ed eccentricità.

    Le ancore delle corsie appartengono a un unico asse orizzontale condiviso
    da tutta l'aula. Una fila con meno blocchi può quindi lasciare corsie vuote,
    ma non può inventarsi un proprio sistema di coordinate.
    """

    if not blocchi_riga:
        return ()
    if len(blocchi_riga) > numero_corsie:
        raise ValueError("Più blocchi nella fila che corsie disponibili.")

    ancore = tuple(
        (indice + 0.5) * max_colonne_editor / numero_corsie
        for indice in range(numero_corsie)
    )
    centri = tuple(_centro_blocco(blocco) for blocco in blocchi_riga)

    migliore: tuple[float, tuple[int, ...]] | None = None
    for scelta in combinations(range(numero_corsie), len(blocchi_riga)):
        costo = sum(
            abs(centro - ancore[corsia])
            for centro, corsia in zip(centri, scelta)
        )
        candidato = (costo, scelta)
        if migliore is None or candidato < migliore:
            migliore = candidato

    assert migliore is not None
    return migliore[1]


def _larghezza_blocchi_compatti(blocchi: list[Any]) -> int:
    if not blocchi:
        return 0
    return (
        sum(int(blocco.capienza) for blocco in blocchi)
        + CORRIDOIO_COLONNE * (len(blocchi) - 1)
    )


def _posizioni_blocchi_compatti(blocchi: list[Any], start: int) -> dict[str, int]:
    risultato: dict[str, int] = {}
    colonna = int(start)
    for indice, blocco in enumerate(blocchi):
        risultato[str(blocco.id)] = colonna
        colonna += int(blocco.capienza)
        if indice < len(blocchi) - 1:
            colonna += CORRIDOIO_COLONNE
    return risultato


def costruisci_piano_griglia_classica_personalizzata(
    istantanea,
    *,
    max_colonne_editor: int = 16,
    riga_fianco_docente: int = 0,
) -> PianoGrigliaClassicaPersonalizzata:
    """Normalizza l'editor in corsie comuni per la scheda ``Aula``.

    A differenza del renderer P3.2b, le file NON vengono centrate o compattate
    indipendentemente. Tutti i blocchi regolari sono assegnati alle stesse
    corsie verticali; fra due corsie resta sempre una sola colonna-corridoio.
    Le righe inutilizzate vengono eliminate, gli Spazi espliciti conservati.
    I blocchi a fianco della postazione
    docente restano nella riga degli arredi, compattati ai lati della postazione.
    """

    if max_colonne_editor <= 0:
        raise ValueError("max_colonne_editor deve essere positivo.")
    if not hasattr(istantanea, "blocchi"):
        raise TypeError("istantanea deve esporre la sequenza 'blocchi'.")

    blocchi = tuple(istantanea.blocchi)
    _valida_blocchi(blocchi)
    if getattr(istantanea, "griglia_fissa", False):
        from moduli.dominio.griglia_layout_fissa import valida_griglia_fissa
        valida_griglia_fissa(istantanea)
        max_colonne_editor = 20

    regolari = tuple(
        blocco for blocco in blocchi
        if int(blocco.riga) != riga_fianco_docente
    )
    laterali = sorted(
        (blocco for blocco in blocchi if int(blocco.riga) == riga_fianco_docente),
        key=lambda b: (int(b.colonna), str(b.id)),
    )

    righe_originali = sorted({int(blocco.riga) for blocco in regolari}
                             | {r for r, c in getattr(istantanea, "spazi", ())
                                if r != riga_fianco_docente})
    righe: dict[int, list[Any]] = {r: [] for r in righe_originali}
    for blocco in regolari:
        righe.setdefault(int(blocco.riga), []).append(blocco)
    for riga in righe:
        righe[riga].sort(key=lambda b: (int(b.colonna), str(b.id)))

    massimo_blocchi_fila = max(
        (len(righe[riga]) for riga in righe_originali),
        default=0,
    )
    numero_corsie = max(CORSIE_MINIME, massimo_blocchi_fila) if regolari else 0

    assegnazioni: dict[str, int] = {}
    larghezze_massime = [2] * numero_corsie
    corsie_per_riga: dict[int, tuple[int, ...]] = {}
    for riga in righe_originali:
        blocchi_riga = righe[riga]
        corsie = _assegna_corsie(
            blocchi_riga,
            numero_corsie=numero_corsie,
            max_colonne_editor=max_colonne_editor,
        )
        corsie_per_riga[riga] = corsie
        for blocco, corsia in zip(blocchi_riga, corsie):
            assegnazioni[str(blocco.id)] = corsia
            larghezze_massime[corsia] = max(
                larghezze_massime[corsia],
                int(blocco.capienza),
            )

    # Una sola ascissa per ciascuna corsia. Le distanze minime sono ricavate
    # dalle coppie di blocchi che coesistono davvero nella stessa fila: in
    # questo modo il layout resta più compatto di una griglia a slot di
    # larghezza massima, ma nessuna fila può spostare autonomamente le corsie.
    inizi_corsie = [0] * numero_corsie
    for corsia in range(1, numero_corsie):
        inizi_corsie[corsia] = (
            inizi_corsie[corsia - 1] + 2 + CORRIDOIO_COLONNE
        )

    for riga in righe_originali:
        blocchi_riga = righe[riga]
        corsie = corsie_per_riga[riga]
        for indice in range(len(blocchi_riga) - 1):
            blocco = blocchi_riga[indice]
            corsia_sx = corsie[indice]
            corsia_dx = corsie[indice + 1]
            richiesto = (
                inizi_corsie[corsia_sx]
                + int(blocco.capienza)
                + CORRIDOIO_COLONNE
            )
            if inizi_corsie[corsia_dx] < richiesto:
                delta = richiesto - inizi_corsie[corsia_dx]
                for j in range(corsia_dx, numero_corsie):
                    inizi_corsie[j] += delta

    larghezza_regolare = max(
        (inizi_corsie[i] + larghezze_massime[i] for i in range(numero_corsie)),
        default=0,
    )

    centro_editor = max_colonne_editor / 2.0
    sinistra = [blocco for blocco in laterali if _centro_blocco(blocco) <= centro_editor]
    destra = [blocco for blocco in laterali if blocco not in sinistra]
    larghezza_sinistra = _larghezza_blocchi_compatti(sinistra)
    larghezza_destra = _larghezza_blocchi_compatti(destra)
    ingombro_laterale = max(
        larghezza_sinistra + (CORRIDOIO_COLONNE if sinistra else 0),
        larghezza_destra + (CORRIDOIO_COLONNE if destra else 0),
    )
    larghezza_fascia_docente = (
        2 * ingombro_laterale + LARGHEZZA_POSTAZIONE_DOCENTE
    )

    numero_colonne = max(
        LARGHEZZA_POSTAZIONE_DOCENTE,
        larghezza_regolare,
        larghezza_fascia_docente,
    )
    # Due colonne centrali esatte richiedono una larghezza pari; una colonna in
    # più è un corridoio innocuo e mantiene la postazione realmente centrata.
    if numero_colonne % 2:
        numero_colonne += 1

    offset_regolare = (
        (numero_colonne - larghezza_regolare) // 2
        if larghezza_regolare else 0
    )
    colonna_docente = (numero_colonne - LARGHEZZA_POSTAZIONE_DOCENTE) // 2

    elementi: list[BloccoGrigliaClassicaPersonalizzata] = []
    indice_fila = {riga: indice for indice, riga in enumerate(righe_originali)}
    for riga in righe_originali:
        blocchi_riga = righe[riga]
        corsie = corsie_per_riga[riga]
        for indice, (blocco, corsia) in enumerate(zip(blocchi_riga, corsie)):
            colonna_blocco = inizi_corsie[corsia]
            # Se esiste un blocco successivo, il blocco corrente viene
            # appoggiato al bordo destro della propria corsia: fra i due resta
            # così esattamente UNA colonna-corridoio anche quando la capienza
            # corrente è 2 e altrove la stessa corsia ospita un terzetto.
            if indice + 1 < len(blocchi_riga):
                corsia_successiva = corsie[indice + 1]
                colonna_blocco = (
                    inizi_corsie[corsia_successiva]
                    - CORRIDOIO_COLONNE
                    - int(blocco.capienza)
                )
            elementi.append(
                BloccoGrigliaClassicaPersonalizzata(
                    blocco=blocco,
                    colonna=offset_regolare + colonna_blocco,
                    fila_dal_docente=indice_fila[riga],
                    fianco_docente=False,
                )
            )

    if sinistra:
        start = colonna_docente - CORRIDOIO_COLONNE - larghezza_sinistra
        posizioni = _posizioni_blocchi_compatti(sinistra, start)
        for blocco in sinistra:
            elementi.append(
                BloccoGrigliaClassicaPersonalizzata(
                    blocco=blocco,
                    colonna=posizioni[str(blocco.id)],
                    fila_dal_docente=None,
                    fianco_docente=True,
                )
            )
    if destra:
        start = (
            colonna_docente
            + LARGHEZZA_POSTAZIONE_DOCENTE
            + CORRIDOIO_COLONNE
        )
        posizioni = _posizioni_blocchi_compatti(destra, start)
        for blocco in destra:
            elementi.append(
                BloccoGrigliaClassicaPersonalizzata(
                    blocco=blocco,
                    colonna=posizioni[str(blocco.id)],
                    fila_dal_docente=None,
                    fianco_docente=True,
                )
            )

    elementi.sort(
        key=lambda e: (
            -1 if e.fianco_docente else int(e.fila_dal_docente or 0),
            e.colonna,
            e.id,
        )
    )
    return PianoGrigliaClassicaPersonalizzata(
        blocchi=tuple(elementi),
        numero_colonne=numero_colonne,
        numero_file=len(righe_originali),
        colonna_postazione_docente=colonna_docente,
    )


def costruisci_configurazione_aula_personalizzata(
    istantanea,
    collocazioni,
    *,
    max_colonne_editor: int = 16,
    riga_fianco_docente: int = 0,
) -> ConfigurazioneAula:
    """Converte il risultato Personalizzata nella ``ConfigurazioneAula`` storica.

    Il renderer finale può quindi usare esattamente ``QGridLayout`` e
    ``crea_widget_posto()`` già impiegati da Coppie/Terzetti.
    """

    # Prima valida blocchi/posti con l'adattatore P3.2 già collaudato.
    from moduli.dominio.layout_risultato_personalizzata import (
        valida_layout_risultato_personalizzata,
    )
    valida_layout_risultato_personalizzata(istantanea, collocazioni)
    piano = costruisci_piano_griglia_classica_personalizzata(
        istantanea,
        max_colonne_editor=max_colonne_editor,
        riga_fianco_docente=riga_fianco_docente,
    )

    identificatori: dict[tuple[str, int], str] = {}
    sessi_studenti: dict[str, str] = {}
    for collocazione in collocazioni:
        for posto, studente in collocazione.occupazioni:
            identificatori[(str(collocazione.blocco.id), int(posto.indice))] = (
                f"{studente.cognome}_{studente.nome}"
            )
            if getattr(studente, 'sesso', None) in ('M', 'F'):
                sessi_studenti[f"{studente.cognome} {studente.nome}"] = studente.sesso

    configurazione = ConfigurazioneAula("Personalizzata")
    configurazione.sessi_studenti = sessi_studenti
    configurazione.modalita = "personalizzata"
    configurazione.num_colonne = piano.numero_colonne
    configurazione.num_righe = piano.numero_file + 1  # riga 0 = docente/laterali
    configurazione.griglia = [
        [PostoAula(riga, col, "corridoio") for col in range(piano.numero_colonne)]
        for riga in range(configurazione.num_righe)
    ]

    c0 = piano.colonna_postazione_docente
    configurazione.griglia[0][c0] = PostoAula(0, c0, "postazione_docente")
    configurazione.griglia[0][c0 + 1] = PostoAula(0, c0 + 1, "postazione_docente")
    configurazione.elementi_fissi = {
        "postazione_docente": (0, c0),
    }

    coordinate_blocchi: dict[str, tuple[int, int]] = {}
    for elemento in piano.blocchi:
        riga_griglia = (
            0 if elemento.fianco_docente
            else 1 + int(elemento.fila_dal_docente)
        )
        coordinate_blocchi[elemento.id] = (riga_griglia, elemento.colonna)
        for indice in range(elemento.capienza):
            col = elemento.colonna + indice
            chiave = (elemento.id, indice)
            if col >= configurazione.num_colonne:
                raise ValueError(f"Blocco {elemento.id!r} fuori dalla griglia finale.")
            if configurazione.griglia[riga_griglia][col].tipo != "corridoio":
                raise ValueError(
                    "Sovrapposizione nella griglia di presentazione Personalizzata: "
                    f"blocco={elemento.id!r}, riga={riga_griglia}, colonna={col}."
                )
            configurazione.griglia[riga_griglia][col] = PostoAula(
                riga_griglia,
                col,
                "banco",
                occupato_da=identificatori[chiave],
            )

    configurazione.posti_disponibili = len(identificatori)
    configurazione.ha_fisso = istantanea.ancora_fisso is not None
    configurazione.coord_fisso = None
    if istantanea.ancora_fisso is not None:
        id_blocco, indice = istantanea.ancora_fisso
        riga, colonna_inizio = coordinate_blocchi[id_blocco]
        configurazione.coord_fisso = (riga, colonna_inizio + int(indice))

    # Metadato puro utile ai prossimi Gate (report/export) senza dover dedurre
    # nuovamente le corsie dalla griglia Qt.
    configurazione.piano_personalizzato = piano
    righe_visuali = sorted({b.riga for b in istantanea.blocchi if b.riga != 0}
                           | {r for r, c in getattr(istantanea, "spazi", ()) if r != 0})
    configurazione.righe_spazio_personalizzato = frozenset(
        1 + righe_visuali.index(r) for r, c in getattr(istantanea, "spazi", ()) if r != 0)

    return configurazione
