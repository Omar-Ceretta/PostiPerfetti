# -*- coding: utf-8 -*-
"""Gate E1 — fotografia semantica *post-generazione* delle tre modalità.

Solo dominio Python: niente Qt, salvataggi applicativi o modifiche ai motori.
L'identità di blocchi/posti non dipende dai pixel. L'occupazione è separata
esplicitamente dalla geometria e può diventare editabile nei Gate successivi.

Parte di «PostiPerfetti». Autore: Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

MODI = frozenset({"coppie", "terzetti", "personalizzata"})
CAPIENZE = frozenset({2, 3, 4})


def _id(nome: str, valore: object) -> str:
    if not isinstance(valore, str) or not valore.strip() or valore != valore.strip():
        raise ValueError(f"{nome} deve essere una stringa non vuota senza spazi esterni.")
    return valore


def _intero(nome: str, valore: object) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ValueError(f"{nome} deve essere un intero non negativo.")
    return valore


def _bool(nome: str, valore: object) -> bool:
    if not isinstance(valore, bool):
        raise ValueError(f"{nome} deve essere booleano.")
    return valore


def _chiavi(record: Mapping[str, Any], chiavi: set[str], contesto: str) -> None:
    if not isinstance(record, dict) or set(record) != chiavi:
        raise ValueError(f"Campi {contesto} errati: attesi {sorted(chiavi)}.")


@dataclass(frozen=True, slots=True)
class PostoEffettivo:
    id: str
    indice: int

    def __post_init__(self) -> None:
        _id("id posto", self.id)
        _intero("indice posto", self.indice)


@dataclass(frozen=True, slots=True)
class BloccoEffettivo:
    id: str
    profondita: int
    colonna: int
    riga_visuale: int
    zona_prima: bool
    zona_ultima: bool
    posti: tuple[PostoEffettivo, ...]

    def __post_init__(self) -> None:
        _id("id blocco", self.id)
        _intero("profondita", self.profondita)
        _intero("colonna", self.colonna)
        _intero("riga_visuale", self.riga_visuale)
        _bool("zona_prima", self.zona_prima)
        _bool("zona_ultima", self.zona_ultima)
        if not isinstance(self.posti, tuple) or len(self.posti) not in CAPIENZE:
            raise ValueError(f"Il blocco {self.id!r} deve avere 2, 3 o 4 posti.")
        if any(not isinstance(p, PostoEffettivo) for p in self.posti):
            raise ValueError("Ogni posto deve essere un PostoEffettivo.")
        if tuple(p.indice for p in self.posti) != tuple(range(len(self.posti))):
            raise ValueError(f"Gli indici del blocco {self.id!r} non sono consecutivi.")

    @property
    def capienza(self) -> int:
        return len(self.posti)


@dataclass(frozen=True, slots=True)
class DisposizioneEffettiva:
    """Valore immutabile. Le occupazioni sono tuple ``(id_posto, nome)``.

    ``adiacenze_fisiche`` registra ogni vicinanza consecutiva; nella vecchia
    modalità Coppie la vicinanza del FISSO resta *fuori* dalla blacklist comune
    e va contata separatamente (``adiacenze_fisso_separate``).
    """

    modo: str
    blocchi: tuple[BloccoEffettivo, ...]
    occupazioni: tuple[tuple[str, str], ...]
    studente_fisso: str | None = None
    ancora_fisso: str | None = None
    genere_misto: bool = False
    modificata_manualmente: bool = False

    def __post_init__(self) -> None:
        if self.modo not in MODI:
            raise ValueError(f"Modalità sconosciuta: {self.modo!r}.")
        _bool("genere_misto", self.genere_misto)
        _bool("modificata_manualmente", self.modificata_manualmente)
        if not isinstance(self.blocchi, tuple) or not self.blocchi:
            raise ValueError("La disposizione non contiene blocchi.")
        if any(not isinstance(b, BloccoEffettivo) for b in self.blocchi):
            raise ValueError("La disposizione contiene blocchi non validi.")
        ids_blocchi = [b.id for b in self.blocchi]
        ids_posti = [p.id for b in self.blocchi for p in b.posti]
        if len(set(ids_blocchi)) != len(ids_blocchi):
            raise ValueError("ID di blocco duplicato.")
        if len(set(ids_posti)) != len(ids_posti):
            raise ValueError("ID di posto duplicato.")
        # Controllo geometrico globale, inclusi blocchi di capienza differente.
        caselle: set[tuple[int, int]] = set()
        for b in self.blocchi:
            for i in range(b.capienza):
                casella = (b.profondita, b.colonna + i)
                if casella in caselle:
                    raise ValueError(f"Sovrapposizione di blocchi a {casella}.")
                caselle.add(casella)
        profondita = sorted({b.profondita for b in self.blocchi})
        if profondita != list(range(len(profondita))):
            raise ValueError("Le profondità devono iniziare da 0 ed essere consecutive.")
        if (not isinstance(self.occupazioni, tuple)
                or any(not isinstance(o, tuple) or len(o) != 2 for o in self.occupazioni)):
            raise ValueError("Le occupazioni devono essere tuple (id_posto, nome).")
        for id_posto, nome in self.occupazioni:
            _id("id posto occupato", id_posto)
            _id("nome studente", nome)
        id_occupati = [id_posto for id_posto, _ in self.occupazioni]
        studenti = [nome for _, nome in self.occupazioni]
        if len(id_occupati) != len(set(id_occupati)) or set(id_occupati) != set(ids_posti):
            raise ValueError("Ogni posto attivo deve essere occupato esattamente una volta.")
        if len(studenti) != len(set(studenti)):
            raise ValueError("Uno studente occupa più posti.")
        if (self.studente_fisso is None) != (self.ancora_fisso is None):
            raise ValueError("FISSO e ancora devono essere presenti insieme.")
        if self.studente_fisso is not None:
            _id("studente FISSO", self.studente_fisso)
            _id("ancora FISSO", self.ancora_fisso)
            if dict(self.occupazioni).get(self.ancora_fisso) != self.studente_fisso:
                raise ValueError("Il FISSO non occupa il proprio posto-ancora.")

    def occupanti_per_blocco(self) -> tuple[tuple[str, ...], ...]:
        occupanti = dict(self.occupazioni)
        return tuple(tuple(occupanti[p.id] for p in b.posti) for b in self.blocchi)

    def adiacenze_fisiche(self) -> frozenset[tuple[str, str]]:
        coppie = set()
        for nomi in self.occupanti_per_blocco():
            coppie.update(tuple(sorted((a, b))) for a, b in zip(nomi, nomi[1:]))
        return frozenset(coppie)

    def adiacenze_fisso_separate(self) -> frozenset[tuple[str, str]]:
        if self.modo != "coppie" or self.studente_fisso is None:
            return frozenset()
        return frozenset(c for c in self.adiacenze_fisiche() if self.studente_fisso in c)

    def adiacenze_rotazioni(self) -> frozenset[tuple[str, str]]:
        """Proiezione della blacklist storica, NON le vicinanze fisiche totali."""
        return self.adiacenze_fisiche() - self.adiacenze_fisso_separate()

    def a_json(self) -> dict[str, Any]:
        """Solo payload semantico in memoria; NON è lo schema della configurazione."""
        return {
            "modo": self.modo,
            "blocchi": [
                {"id": b.id, "profondita": b.profondita, "colonna": b.colonna,
                 "riga_visuale": b.riga_visuale, "zona_prima": b.zona_prima,
                 "zona_ultima": b.zona_ultima,
                 "posti": [{"id": p.id, "indice": p.indice} for p in b.posti]}
                for b in self.blocchi
            ],
            "occupazioni": [{"id_posto": p, "studente": n} for p, n in self.occupazioni],
            "studente_fisso": self.studente_fisso,
            "ancora_fisso": self.ancora_fisso,
            "genere_misto": self.genere_misto,
            "modificata_manualmente": self.modificata_manualmente,
        }

    @classmethod
    def da_json(cls, dati: Mapping[str, Any]) -> DisposizioneEffettiva:
        _chiavi(dati, {"modo", "blocchi", "occupazioni", "studente_fisso",
                       "ancora_fisso", "genere_misto", "modificata_manualmente"},
                "disposizione")
        if not isinstance(dati["blocchi"], list) or not isinstance(dati["occupazioni"], list):
            raise ValueError("blocchi e occupazioni devono essere liste JSON.")
        blocchi = []
        for b in dati["blocchi"]:
            _chiavi(b, {"id", "profondita", "colonna", "riga_visuale",
                        "zona_prima", "zona_ultima", "posti"}, "blocco")
            if not isinstance(b["posti"], list):
                raise ValueError("posti deve essere una lista JSON.")
            posti = []
            for p in b["posti"]:
                _chiavi(p, {"id", "indice"}, "posto")
                posti.append(PostoEffettivo(**p))
            blocchi.append(BloccoEffettivo(**{**b, "posti": tuple(posti)}))
        occupazioni = []
        for o in dati["occupazioni"]:
            _chiavi(o, {"id_posto", "studente"}, "occupazione")
            occupazioni.append((o["id_posto"], o["studente"]))
        return cls(
            modo=dati["modo"], blocchi=tuple(blocchi),
            occupazioni=tuple(occupazioni), studente_fisso=dati["studente_fisso"],
            ancora_fisso=dati["ancora_fisso"], genere_misto=dati["genere_misto"],
            modificata_manualmente=dati["modificata_manualmente"],
        )


def _da_griglia(aula: Any, modo: str, *, studente_fisso: str | None,
                ancora_fisso_coord: tuple[int, int] | None = None,
                genere_misto: bool = False) -> DisposizioneEffettiva:
    """Fotografa la griglia già assegnata; non crea/riposiziona alcun banco."""
    from moduli.dominio.studenti import nome_completo_da_identificatore

    righe = []
    for r, fila in enumerate(aula.griglia):
        blocchi = aula._raggruppa_banchi_in_blocchi(fila)
        if blocchi:
            righe.append((r, blocchi))
    if not righe:
        raise ValueError("La griglia non contiene posti assegnati.")
    blocchi_out = []
    occupazioni = []
    ancora = None
    for profondita, (r, blocchi) in enumerate(righe):
        for gruppo in blocchi:
            c = gruppo[0].colonna
            prefisso = f"std-r{r}-c{c}"
            posti = []
            for indice, cella in enumerate(gruppo):
                id_posto = f"std-r{r}-c{cella.colonna}"
                if cella.occupato_da is None:
                    raise ValueError("Griglia ancora non interamente occupata: manca uno studente.")
                nome = nome_completo_da_identificatore(cella.occupato_da)
                posti.append(PostoEffettivo(id_posto, indice))
                occupazioni.append((id_posto, nome))
                if (r, cella.colonna) == ancora_fisso_coord:
                    ancora = id_posto
            blocchi_out.append(BloccoEffettivo(
                id=prefisso, profondita=profondita, colonna=c, riga_visuale=r - 2,
                zona_prima=(profondita == 0), zona_ultima=(profondita == len(righe) - 1),
                posti=tuple(posti),
            ))
    if studente_fisso is not None and ancora is None:
        posizioni = [p for p, nome in occupazioni if nome == studente_fisso]
        if len(posizioni) != 1:
            raise ValueError("Studente FISSO assente o duplicato nella griglia.")
        ancora = posizioni[0]
    return DisposizioneEffettiva(
        modo, tuple(blocchi_out), tuple(occupazioni), studente_fisso, ancora,
        genere_misto,
    )


def da_assegnatore_coppie(assegnatore: Any, *, genere_misto: bool = False) -> DisposizioneEffettiva:
    """Adattatore di sola lettura dall'AssegnatorePosti completo."""
    fisso = assegnatore.studente_fisso
    nome = fisso.get_nome_completo() if fisso is not None else None
    disposizione = _da_griglia(assegnatore.configurazione_aula, "coppie",
                              studente_fisso=nome, genere_misto=genere_misto)
    # E3a: nel modello post-generazione il FISSO può essere all'estremo
    # (un vicino) oppure in posizione interna a trio/quartetto (due vicini).
    # La vecchia assunzione «esattamente un vicino» impediva l'adattamento
    # delle future ancore non frontali. La generazione resta invariata.
    numero_vicini = len(disposizione.adiacenze_fisso_separate())
    if numero_vicini not in ((1, 2) if fisso else (0,)):
        raise ValueError("La vicinanza FISSO nella modalità Coppie è incoerente.")
    return disposizione


def da_risultato_terzetti(aula: Any, gruppi: Any, *,
                           studente_fisso: Any = None,
                           genere_misto: bool = False) -> DisposizioneEffettiva:
    """Adattatore dalla griglia riempita con ``piazza_gruppi_terzetti``.

    Verifica anche che i gruppi ordinati prodotti dal motore coincidano con
    quelli effettivamente collocati (l'ordine *dei* gruppi può differire).
    """
    from moduli.dominio.metrica_pulizia import nome_completo

    coord = getattr(aula, "coord_fisso", None)
    nome = nome_completo(studente_fisso) if studente_fisso is not None else None
    if nome is None and coord is not None:
        from moduli.dominio.studenti import nome_completo_da_identificatore
        nome = nome_completo_da_identificatore(aula.griglia[coord[0]][coord[1]].occupato_da)
    disposizione = _da_griglia(aula, "terzetti", studente_fisso=nome,
                              ancora_fisso_coord=coord if nome is not None else None,
                              genere_misto=genere_misto)
    attesi = Counter(tuple(nome_completo(s) for s in g.membri) for g in gruppi)
    trovati = Counter(disposizione.occupanti_per_blocco())
    if attesi != trovati:
        raise ValueError("La griglia Terzetti non coincide con i gruppi del motore.")
    return disposizione


def da_risultato_personalizzata(schema: Any, collocazioni: Any, *,
                                istantanea_visuale: Any = None,
                                genere_misto: bool = False) -> DisposizioneEffettiva:
    """Preserva ID, posto-ancora, ordine e profondità dello schema esistente."""
    from moduli.dominio.metrica_pulizia import nome_completo
    if istantanea_visuale is not None:
        istantanea_visuale.valida_contro_schema(schema)
    visuali = ({b.id: b.riga for b in istantanea_visuale.blocchi}
               if istantanea_visuale is not None else {})
    per_id = {b.id: b for b in schema.blocchi}
    if len(per_id) != len(schema.blocchi):
        raise ValueError("Schema Personalizzato con ID di blocco duplicati.")
    blocchi = tuple(BloccoEffettivo(
        id=b.id, profondita=b.profondita, colonna=b.colonna,
        riga_visuale=visuali.get(b.id, b.profondita),
        zona_prima=b.zona_prima, zona_ultima=b.zona_ultima,
        posti=tuple(PostoEffettivo(p.id, p.indice) for p in b.posti),
    ) for b in schema.blocchi)
    occupazioni_per_posto = {}
    for collocazione in collocazioni:
        blocco = per_id.get(collocazione.blocco.id)
        if blocco is None or blocco != collocazione.blocco:
            raise ValueError("Collocazione riferita a un blocco diverso dallo schema.")
        for posto, studente in collocazione.occupazioni:
            if posto.id in occupazioni_per_posto:
                raise ValueError("Posto Personalizzato occupato due volte.")
            occupazioni_per_posto[posto.id] = nome_completo(studente)
    occupazioni = tuple((p.id, occupazioni_per_posto[p.id]) for b in blocchi for p in b.posti
                       if p.id in occupazioni_per_posto)
    ancora = schema.posto_ancora_fisso
    id_ancora = ancora.id if ancora is not None else None
    nome_fisso = occupazioni_per_posto.get(id_ancora) if id_ancora is not None else None
    # L'ancora identifica l'unico FISSO, non un occupante qualsiasi.
    fissi = [(p.id, s) for c in collocazioni for p, s in c.occupazioni
             if getattr(s, "nota_posizione", "") == "FISSO"]
    if id_ancora is not None:
        if len(fissi) != 1 or fissi[0][0] != id_ancora:
            raise ValueError("L'ancora Personalizzata non contiene l'unico studente FISSO.")
    elif fissi:
        raise ValueError("FISSO Personalizzato senza ancora fisica.")
    return DisposizioneEffettiva(
        "personalizzata", blocchi, occupazioni, nome_fisso, id_ancora, genere_misto,
    )
