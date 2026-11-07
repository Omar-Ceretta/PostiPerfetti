# -*- coding: utf-8 -*-
"""Modello puro dell'editor per la modalità Personalizzata.

Il modulo non importa Qt e non esegue alcuna assegnazione di studenti. Mantiene
una bozza logica composta soltanto da banchi da 2/3 posti, la converte nello
``SchemaBlocchiSemantico`` già validato dal motore misto e fornisce una
serializzazione JSON stabile, indipendente dai pixel della GUI.

La riga usata durante l'editing è una coordinata logica: al momento della
conversione le righe effettivamente occupate vengono compattate in profondità
consecutive 0..N, mantenendo l'ordine fronte→fondo. Le colonne, invece, restano
esplicite per preservare corridoi e blocchi eccentrici.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from moduli.dominio.schema_blocchi_semantico import (
    BloccoAulaSemanticoSpec,
    CAPIENZE_BLOCCO_SUPPORTATE,
    PostoAulaSemanticoSpec,
    SchemaBlocchiSemantico,
)


VERSIONE_SCHEMA_AULA_PERSONALIZZATA = 1
TIPO_SCHEMA_AULA_PERSONALIZZATA = "aula_personalizzata"
VERSIONE_LAYOUT_VISUALE_AULA_PERSONALIZZATA = 1
TIPO_LAYOUT_VISUALE_AULA_PERSONALIZZATA = "aula_personalizzata_visuale"
ZONE_BLOCCO = frozenset({"neutra", "prima", "ultima"})


def _intero_non_negativo(nome: str, valore: object) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ValueError(f"{nome} deve essere un intero non negativo.")
    return valore


def _testo_non_vuoto(nome: str, valore: object) -> str:
    testo = str(valore).strip()
    if not testo:
        raise ValueError(f"{nome} non può essere vuoto.")
    return testo


@dataclass(frozen=True, slots=True)
class BloccoBozzaPersonalizzata:
    """Banco presente nella bozza logica dell'editor.

    ``riga`` è una coordinata di editing e può avere buchi; viene normalizzata
    in ``profondita`` solo quando si costruisce lo schema semantico.
    """

    id: str
    capienza: int
    riga: int
    colonna: int
    zona: str = "neutra"
    ids_posti: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        identificatore = _testo_non_vuoto("L'id del blocco", self.id)
        object.__setattr__(self, "id", identificatore)
        if self.capienza not in CAPIENZE_BLOCCO_SUPPORTATE:
            ammesse = ", ".join(str(v) for v in sorted(CAPIENZE_BLOCCO_SUPPORTATE))
            raise ValueError(
                f"capienza non supportata: {self.capienza!r}; ammesse: {ammesse}."
            )
        _intero_non_negativo("riga", self.riga)
        _intero_non_negativo("colonna", self.colonna)
        zona = str(self.zona).strip().lower()
        if zona not in ZONE_BLOCCO:
            raise ValueError(f"Zona non valida: {self.zona!r}.")
        object.__setattr__(self, "zona", zona)

        ids = tuple(self.ids_posti) or tuple(
            f"{identificatore}-S{indice}" for indice in range(self.capienza)
        )
        if len(ids) != self.capienza:
            raise ValueError(
                f"Il blocco {identificatore!r} richiede {self.capienza} id posto, "
                f"ma ne ha {len(ids)}."
            )
        ids = tuple(_testo_non_vuoto("L'id del posto", item) for item in ids)
        if len(set(ids)) != len(ids):
            raise ValueError(f"Id posto duplicato nel blocco {identificatore!r}.")
        object.__setattr__(self, "ids_posti", ids)

    @property
    def colonna_finale(self) -> int:
        return self.colonna + self.capienza - 1


@dataclass(frozen=True, slots=True)
class EsitoZoneAulaPersonalizzata:
    """Compatibilità fra richieste PRIMA/ULTIMA e zone create dal docente.

    PRIMA insufficiente è bloccante. ULTIMA insufficiente produce un avviso:
    resta una preferenza e la ricerca può soddisfarla solo parzialmente.
    Le preferenze effettivamente mancate sono indicate nel Report del risultato.
    """

    richieste_prima: int
    richieste_ultima: int
    posti_prima: int
    posti_ultima: int
    posti_prima_utilizzabili: int
    posti_ultima_utilizzabili: int
    fisso_occupa_prima: bool
    fisso_occupa_ultima: bool
    errori: tuple[str, ...] = ()
    avvisi: tuple[str, ...] = ()

    @property
    def valido(self) -> bool:
        return not self.errori

    def messaggio_errore(self) -> str:
        """Descrive il blocco PRIMA senza dettagli interni del calcolo.

        ULTIMA e' una preferenza: non si chiedono mai posti IN FONDO per
        risolvere un errore di capienza DAVANTI.
        """
        if self.valido:
            return ""
        if self.richieste_prima > self.posti_prima_utilizzabili:
            nota_fisso = (
                "\nUn posto DAVANTI è già riservato allo studente FISSO."
                if self.fisso_occupa_prima else ""
            )
            return (
                "Non è possibile avviare l'assegnazione: non ci sono abbastanza "
                "posti DAVANTI per gli studenti con posizione PRIMA.\n\n"
                f"Studenti con posizione PRIMA: {self.richieste_prima}\n"
                f"Posti DAVANTI utilizzabili: {self.posti_prima_utilizzabili}"
                f"{nota_fisso}\n\n"
                "Apri la scheda Layout, contrassegna come DAVANTI uno o più "
                "blocchi e riprova."
            )
        return "\n".join(self.errori)

    def messaggio_avviso_ultima(self) -> str:
        """Promemoria pre-calcolo per ULTIMA, mai bloccante.

        Distingue l'assenza completa di posti IN FONDO da una capienza
        soltanto parziale; non attribuisce la geometria a righe implicite.
        """
        if self.richieste_ultima <= self.posti_ultima_utilizzabili:
            return ""

        numeri = (
            f"Studenti con preferenza ULTIMA: {self.richieste_ultima}\n"
            f"Posti IN FONDO utilizzabili: {self.posti_ultima_utilizzabili}"
        )
        if self.posti_ultima == 0:
            spiegazione = (
                "Nel Layout non hai contrassegnato alcun blocco come IN FONDO. "
                "Senza questa indicazione la preferenza ULTIMA non potrà "
                "essere soddisfatta."
            )
        elif self.posti_ultima_utilizzabili == 0:
            spiegazione = (
                "Nessun posto IN FONDO è disponibile per gli studenti con "
                "preferenza ULTIMA."
            )
        else:
            spiegazione = (
                "I posti IN FONDO sono meno degli studenti che li preferiscono. "
                "La preferenza potrà essere soddisfatta solo parzialmente."
            )

        return (
            f"{spiegazione}\n\n{numeri}\n\n"
            "Puoi tornare alla scheda Layout e contrassegnare altri blocchi "
            "come IN FONDO, oppure proseguire ugualmente. ULTIMA è una "
            "preferenza, non un vincolo obbligatorio."
        )


class PostiDavantiInsufficienti(ValueError):
    """Preflight bloccante per PRIMA; non e' un errore del motore Q21."""


def valuta_zone_aula_personalizzata(
    schema: SchemaBlocchiSemantico,
    studenti: Iterable[object],
) -> EsitoZoneAulaPersonalizzata:
    """Valuta la capienza delle zone rispetto alle posizioni della classe.

    Un eventuale FISSO occupa il proprio posto-ancora: se l'ancora appartiene a
    DAVANTI o IN FONDO, quel posto non è disponibile per uno studente PRIMA o
    ULTIMA. Blocchi neutri, corridoi e distanze grafiche non entrano nel conto.
    """
    if not isinstance(schema, SchemaBlocchiSemantico):
        raise TypeError("schema deve essere uno SchemaBlocchiSemantico.")

    studenti = tuple(studenti)
    richieste_prima = sum(
        1
        for studente in studenti
        if str(getattr(studente, "nota_posizione", "")).strip().upper()
        == "PRIMA"
    )
    richieste_ultima = sum(
        1
        for studente in studenti
        if str(getattr(studente, "nota_posizione", "")).strip().upper()
        == "ULTIMA"
    )

    posti_prima = sum(blocco.capienza for blocco in schema.blocchi_prima)
    posti_ultima = sum(blocco.capienza for blocco in schema.blocchi_ultima)

    blocco_fisso = schema.blocco_ancora_fisso
    fisso_occupa_prima = bool(
        blocco_fisso is not None and blocco_fisso.zona_prima
    )
    fisso_occupa_ultima = bool(
        blocco_fisso is not None and blocco_fisso.zona_ultima
    )

    posti_prima_utilizzabili = max(
        0, posti_prima - (1 if fisso_occupa_prima else 0)
    )
    posti_ultima_utilizzabili = max(
        0, posti_ultima - (1 if fisso_occupa_ultima else 0)
    )

    errori: list[str] = []
    avvisi: list[str] = []
    if richieste_prima > posti_prima_utilizzabili:
        dettaglio_fisso = (
            " Un posto DAVANTI è già riservato al FISSO."
            if fisso_occupa_prima
            else ""
        )
        posti_testo = (
            "1 posto DAVANTI utilizzabile" if posti_prima_utilizzabili == 1
            else f"{posti_prima_utilizzabili} posti DAVANTI utilizzabili"
        )
        errori.append(
            f"PRIMA: {richieste_prima} richieste, ma soltanto "
            f"{posti_testo}.{dettaglio_fisso}"
        )

    if richieste_ultima > posti_ultima_utilizzabili:
        dettaglio_fisso = (
            " Un posto IN FONDO è già riservato al FISSO."
            if fisso_occupa_ultima
            else ""
        )
        avvisi.append(
            f"Preferenza ULTIMA: {richieste_ultima} richieste, ma soltanto "
            f"{posti_ultima_utilizzabili} posti IN FONDO utilizzabili."
            f"{dettaglio_fisso}"
            " La ricerca prosegue cercando di soddisfarne il maggior numero possibile."
        )

    return EsitoZoneAulaPersonalizzata(
        richieste_prima=richieste_prima,
        richieste_ultima=richieste_ultima,
        posti_prima=posti_prima,
        posti_ultima=posti_ultima,
        posti_prima_utilizzabili=posti_prima_utilizzabili,
        posti_ultima_utilizzabili=posti_ultima_utilizzabili,
        fisso_occupa_prima=fisso_occupa_prima,
        fisso_occupa_ultima=fisso_occupa_ultima,
        errori=tuple(errori),
        avvisi=tuple(avvisi),
    )


def richiedi_zone_aula_personalizzata_valide(
    schema: SchemaBlocchiSemantico,
    studenti: Iterable[object],
) -> EsitoZoneAulaPersonalizzata:
    """Restituisce il preflight oppure solleva un errore umano e immediato."""
    esito = valuta_zone_aula_personalizzata(schema, studenti)
    if not esito.valido:
        raise PostiDavantiInsufficienti(esito.messaggio_errore())
    return esito


@dataclass(frozen=True, slots=True)
class IstantaneaVisualeAulaPersonalizzata:
    """Fotografia non-pixel della disposizione costruita nell'editor.

    Lo ``SchemaBlocchiSemantico`` compatta le righe vuote in profondità
    consecutive, come richiesto dal motore. Questa fotografia conserva invece
    la riga logica scelta dall'utente (compresa la fascia 0 ai lati della
    cattedra), così il risultato può essere ridisegnato esattamente come
    l'aula costruita senza introdurre coordinate in pixel.
    """

    blocchi: tuple[BloccoBozzaPersonalizzata, ...]
    ancora_fisso: tuple[str, int] | None = None
    griglia_fissa: bool = False
    spazi: tuple[tuple[int, int], ...] = ()

    @classmethod
    def da_modello(
        cls, modello: "ModelloAulaPersonalizzata"
    ) -> "IstantaneaVisualeAulaPersonalizzata":
        if not isinstance(modello, ModelloAulaPersonalizzata):
            raise TypeError("modello deve essere un ModelloAulaPersonalizzata.")
        return cls(tuple(modello.blocchi), modello.ancora_fisso, modello.griglia_fissa, modello.spazi)

    def ricostruisci_modello(self) -> "ModelloAulaPersonalizzata":
        modello = ModelloAulaPersonalizzata(self.blocchi, griglia_fissa=self.griglia_fissa, spazi=self.spazi)
        if self.ancora_fisso is not None:
            modello.imposta_ancora_fisso(*self.ancora_fisso)
        return modello

    def valida_contro_schema(self, schema: SchemaBlocchiSemantico) -> None:
        if not isinstance(schema, SchemaBlocchiSemantico):
            raise TypeError("schema deve essere uno SchemaBlocchiSemantico.")
        if self.griglia_fissa:
            from moduli.dominio.griglia_layout_fissa import valida_griglia_fissa
            valida_griglia_fissa(self)
        ricostruito = self.ricostruisci_modello().costruisci_schema()
        if ricostruito.identita_semantica() != schema.identita_semantica():
            raise ValueError(
                "La fotografia visuale non corrisponde allo schema semantico."
            )


class ModelloAulaPersonalizzata:
    """Stato puro e modificabile di un futuro editor visuale Personalizzata."""

    def __init__(self, blocchi: Iterable[BloccoBozzaPersonalizzata] = (), *,
                 griglia_fissa: bool = False, spazi=()) -> None:
        if type(griglia_fissa) is not bool:
            raise ValueError("griglia_fissa deve essere booleana.")
        self.griglia_fissa = griglia_fissa
        self._blocchi: dict[str, BloccoBozzaPersonalizzata] = {}
        self._ancora_fisso: tuple[str, int] | None = None
        self._progressivo_id = 0
        self._spazi: set[tuple[int, int]] = set()
        for blocco in blocchi:
            self._inserisci_blocco(blocco)
        for posizione in spazi:
            if not isinstance(posizione, (tuple, list)) or len(posizione) != 2:
                raise ValueError("Uno Spazio deve avere riga e colonna.")
            self.aggiungi_spazio(*posizione)

    @classmethod
    def da_schema(cls, schema: SchemaBlocchiSemantico) -> "ModelloAulaPersonalizzata":
        """Crea una bozza che preserva integralmente l'identità dello schema."""
        if not isinstance(schema, SchemaBlocchiSemantico):
            raise TypeError("schema deve essere uno SchemaBlocchiSemantico.")

        modello = cls()
        for blocco in schema.blocchi:
            zona = "prima" if blocco.zona_prima else "ultima" if blocco.zona_ultima else "neutra"
            if blocco.zona_prima and blocco.zona_ultima:
                raise ValueError(
                    f"Il blocco {blocco.id!r} appartiene sia a PRIMA sia a ULTIMA: "
                    "l'editor Personalizzata richiede una sola zona per blocco."
                )
            modello._inserisci_blocco(BloccoBozzaPersonalizzata(
                id=blocco.id,
                capienza=blocco.capienza,
                riga=blocco.profondita,
                colonna=blocco.colonna,
                zona=zona,
                ids_posti=tuple(posto.id for posto in blocco.posti),
            ))
            ancora = blocco.posto_ancora_fisso
            if ancora is not None:
                modello._ancora_fisso = (blocco.id, ancora.indice)
        return modello

    @property
    def blocchi(self) -> tuple[BloccoBozzaPersonalizzata, ...]:
        return tuple(sorted(
            self._blocchi.values(),
            key=lambda blocco: (blocco.riga, blocco.colonna, blocco.id),
        ))

    @property
    def spazi(self) -> tuple[tuple[int, int], ...]:
        return tuple(sorted(self._spazi))

    def aggiungi_spazio(self, riga: int, colonna: int) -> None:
        from moduli.dominio.griglia_layout_fissa import posizione_spazio
        posizione_spazio((riga, colonna))
        if not self.griglia_fissa:
            raise ValueError("Spazio richiede la griglia del Layout.")
        if (riga, colonna) in self._spazi:
            raise ValueError("Spazio già presente.")
        if any((b.riga, b.colonna) == (riga, colonna) for b in self.blocchi):
            raise ValueError("Questa posizione contiene già un blocco.")
        self._spazi.add((riga, colonna))

    def rimuovi_spazio(self, riga: int, colonna: int) -> None:
        self._spazi.remove((riga, colonna))

    @property
    def ancora_fisso(self) -> tuple[str, int] | None:
        return self._ancora_fisso

    @property
    def posti_totali(self) -> int:
        return sum(blocco.capienza for blocco in self._blocchi.values())

    def _inserisci_blocco(self, blocco: BloccoBozzaPersonalizzata) -> None:
        if (blocco.riga, blocco.colonna) in self._spazi:
            raise ValueError("La posizione è riservata a uno Spazio.")
        if blocco.id in self._blocchi:
            raise ValueError(f"Id blocco duplicato: {blocco.id!r}.")
        ids_esistenti = {
            posto_id
            for esistente in self._blocchi.values()
            for posto_id in esistente.ids_posti
        }
        duplicati = ids_esistenti.intersection(blocco.ids_posti)
        if duplicati:
            raise ValueError(
                "Id posto già usato nella bozza: " + ", ".join(sorted(duplicati)) + "."
            )
        self._blocchi[blocco.id] = blocco
        if blocco.id.startswith("B") and blocco.id[1:].isdigit():
            self._progressivo_id = max(self._progressivo_id, int(blocco.id[1:]))

    def _nuovo_id_blocco(self) -> str:
        while True:
            self._progressivo_id += 1
            candidato = f"B{self._progressivo_id:04d}"
            if candidato not in self._blocchi:
                return candidato

    def aggiungi_blocco(
        self,
        capienza: int,
        *,
        riga: int,
        colonna: int,
        zona: str = "neutra",
        id_blocco: str | None = None,
        ids_posti: Iterable[str] | None = None,
    ) -> str:
        """Aggiunge un banco alla bozza e restituisce il suo id stabile."""
        identificatore = self._nuovo_id_blocco() if id_blocco is None else id_blocco
        blocco = BloccoBozzaPersonalizzata(
            id=identificatore,
            capienza=capienza,
            riga=riga,
            colonna=colonna,
            zona=zona,
            ids_posti=tuple(ids_posti or ()),
        )
        self._inserisci_blocco(blocco)
        return blocco.id

    def sposta_blocco(self, id_blocco: str, *, riga: int, colonna: int) -> None:
        blocco = self._richiedi_blocco(id_blocco)
        if (riga, colonna) in self._spazi:
            raise ValueError("La posizione è riservata a uno Spazio.")
        self._blocchi[blocco.id] = replace(
            blocco,
            riga=_intero_non_negativo("riga", riga),
            colonna=_intero_non_negativo("colonna", colonna),
        )

    def imposta_zona(self, id_blocco: str, zona: str) -> None:
        blocco = self._richiedi_blocco(id_blocco)
        zona_norm = str(zona).strip().lower()
        if zona_norm not in ZONE_BLOCCO:
            raise ValueError(f"Zona non valida: {zona!r}.")
        self._blocchi[blocco.id] = replace(blocco, zona=zona_norm)

    def rimuovi_blocco(self, id_blocco: str) -> None:
        blocco = self._richiedi_blocco(id_blocco)
        del self._blocchi[blocco.id]
        if self._ancora_fisso is not None and self._ancora_fisso[0] == blocco.id:
            self._ancora_fisso = None

    def svuota(self) -> None:
        self._blocchi.clear()
        self._spazi.clear()
        self._ancora_fisso = None

    def imposta_ancora_fisso(self, id_blocco: str, indice_posto: int) -> None:
        blocco = self._richiedi_blocco(id_blocco)
        indice = _intero_non_negativo("indice_posto", indice_posto)
        if indice >= blocco.capienza:
            raise ValueError(
                f"Il blocco {blocco.id!r} ha posti 0..{blocco.capienza - 1}: "
                f"indice ricevuto {indice}."
            )
        self._ancora_fisso = (blocco.id, indice)

    def rimuovi_ancora_fisso(self) -> None:
        self._ancora_fisso = None

    def _richiedi_blocco(self, id_blocco: str) -> BloccoBozzaPersonalizzata:
        identificatore = str(id_blocco).strip()
        try:
            return self._blocchi[identificatore]
        except KeyError as exc:
            raise ValueError(f"Blocco inesistente: {id_blocco!r}.") from exc

    def costruisci_schema(
        self,
        *,
        numero_studenti: int | None = None,
        ha_fisso: bool | None = None,
    ) -> SchemaBlocchiSemantico:
        """Converte la bozza nello schema semantico validato del motore.

        Se ``ha_fisso`` è ``True`` viene richiesta esattamente una puntina; se è
        ``False`` una puntina residua è considerata un errore di configurazione.
        Con ``None`` l'ancora viene semplicemente preservata: è utile per
        round-trip, Storico e test indipendenti dalla classe caricata.
        """
        if not self._blocchi:
            raise ValueError("L'aula Personalizzata non contiene alcun banco.")
        if ha_fisso is not None and not isinstance(ha_fisso, bool):
            raise ValueError("ha_fisso deve essere booleano oppure None.")
        if ha_fisso is True and self._ancora_fisso is None:
            raise ValueError(
                "La classe contiene uno studente FISSO: assegna la puntina a un posto."
            )
        if ha_fisso is False and self._ancora_fisso is not None:
            raise ValueError(
                "La classe non contiene studenti FISSO: rimuovi la puntina dall'aula."
            )

        righe = sorted({blocco.riga for blocco in self._blocchi.values()})
        profondita_per_riga = {riga: indice for indice, riga in enumerate(righe)}

        blocchi_semantici: list[BloccoAulaSemanticoSpec] = []
        for blocco in self.blocchi:
            ancora_indice = None
            if self._ancora_fisso is not None and self._ancora_fisso[0] == blocco.id:
                ancora_indice = self._ancora_fisso[1]
            posti = tuple(
                PostoAulaSemanticoSpec(
                    indice=indice,
                    id=blocco.ids_posti[indice],
                    ancora_fisso=(indice == ancora_indice),
                )
                for indice in range(blocco.capienza)
            )
            blocchi_semantici.append(BloccoAulaSemanticoSpec(
                id=blocco.id,
                capienza=blocco.capienza,
                profondita=profondita_per_riga[blocco.riga],
                colonna=blocco.colonna,
                zona_prima=(blocco.zona == "prima"),
                zona_ultima=(blocco.zona == "ultima"),
                posti=posti,
            ))

        schema = SchemaBlocchiSemantico(tuple(blocchi_semantici))
        if numero_studenti is not None:
            schema.valida_numero_studenti(numero_studenti)
        return schema

    def contatori(self, *, numero_studenti: int | None = None) -> dict[str, Any]:
        """Restituisce i valori destinati ai contatori live della futura GUI."""
        blocchi = self.blocchi
        posti_prima = sum(b.capienza for b in blocchi if b.zona == "prima")
        posti_ultima = sum(b.capienza for b in blocchi if b.zona == "ultima")
        risultato: dict[str, Any] = {
            "studenti": numero_studenti,
            "posti": self.posti_totali,
            "differenza": (
                None if numero_studenti is None else self.posti_totali - numero_studenti
            ),
            "coppie": sum(1 for b in blocchi if b.capienza == 2),
            "terzetti": sum(1 for b in blocchi if b.capienza == 3),
            "posti_prima": posti_prima,
            "posti_ultima": posti_ultima,
            "fisso_assegnato": self._ancora_fisso is not None,
        }
        return risultato

    def a_json(self, *, numero_studenti: int | None = None, ha_fisso: bool | None = None) -> dict[str, Any]:
        """Serializza soltanto uno schema semantico valido e canonico."""
        return schema_personalizzato_a_json(
            self.costruisci_schema(
                numero_studenti=numero_studenti,
                ha_fisso=ha_fisso,
            )
        )


def schema_personalizzato_a_json(schema: SchemaBlocchiSemantico) -> dict[str, Any]:
    """Converte uno schema semantico nel formato JSON stabile v1."""
    if not isinstance(schema, SchemaBlocchiSemantico):
        raise TypeError("schema deve essere uno SchemaBlocchiSemantico.")
    return {
        "schema_versione": VERSIONE_SCHEMA_AULA_PERSONALIZZATA,
        "tipo": TIPO_SCHEMA_AULA_PERSONALIZZATA,
        "blocchi": [
            {
                "id": blocco.id,
                "capienza": blocco.capienza,
                "profondita": blocco.profondita,
                "colonna": blocco.colonna,
                "zona_prima": blocco.zona_prima,
                "zona_ultima": blocco.zona_ultima,
                "posti": [
                    {
                        "indice": posto.indice,
                        "id": posto.id,
                        "ancora_fisso": posto.ancora_fisso,
                    }
                    for posto in blocco.posti
                ],
            }
            for blocco in schema.blocchi
        ],
    }


def _richiedi_chiavi_esatte(dati: Mapping[str, Any], attese: set[str], contesto: str) -> None:
    presenti = set(dati)
    mancanti = sorted(attese - presenti)
    inattese = sorted(presenti - attese)
    if mancanti or inattese:
        dettagli = []
        if mancanti:
            dettagli.append("mancano: " + ", ".join(mancanti))
        if inattese:
            dettagli.append("non previste: " + ", ".join(inattese))
        raise ValueError(f"{contesto}: formato non valido ({'; '.join(dettagli)}).")


def istantanea_visuale_a_json(
    istantanea: IstantaneaVisualeAulaPersonalizzata,
) -> dict[str, Any]:
    """Serializza la fotografia logica usata dal rendering Personalizzata.

    A differenza dello schema semantico conserva le righe di editing con gli
    eventuali vuoti, così una voce dello Storico può ridisegnare esattamente
    corridoi, blocchi laterali e banchi accanto alla cattedra.
    """
    if not isinstance(istantanea, IstantaneaVisualeAulaPersonalizzata):
        raise TypeError(
            "istantanea deve essere un'IstantaneaVisualeAulaPersonalizzata."
        )
    ancora = None
    if istantanea.ancora_fisso is not None:
        ancora = {
            "blocco": istantanea.ancora_fisso[0],
            "indice_posto": istantanea.ancora_fisso[1],
        }
    return {
        "schema_versione": VERSIONE_LAYOUT_VISUALE_AULA_PERSONALIZZATA,
        "tipo": TIPO_LAYOUT_VISUALE_AULA_PERSONALIZZATA,
        "blocchi": [
            {
                "id": blocco.id,
                "capienza": blocco.capienza,
                "riga": blocco.riga,
                "colonna": blocco.colonna,
                "zona": blocco.zona,
                "ids_posti": list(blocco.ids_posti),
            }
            for blocco in istantanea.blocchi
        ],
        "ancora_fisso": ancora,
        **({"griglia_fissa": True} if istantanea.griglia_fissa else {}),
        **({"spazi": [list(p) for p in istantanea.spazi]} if istantanea.spazi else {}),
    }


def istantanea_visuale_da_json(
    dati: Mapping[str, Any],
) -> IstantaneaVisualeAulaPersonalizzata:
    """Valida e ricostruisce la fotografia visuale Personalizzata v1."""
    if not isinstance(dati, Mapping):
        raise ValueError("Il layout visuale Personalizzata deve essere un oggetto JSON.")
    _richiedi_chiavi_esatte(
        dati,
        {"schema_versione", "tipo", "blocchi", "ancora_fisso"}
        | ({"griglia_fissa"} if "griglia_fissa" in dati else set())
        | ({"spazi"} if "spazi" in dati else set()),
        "Layout visuale Personalizzata",
    )
    if dati["schema_versione"] != VERSIONE_LAYOUT_VISUALE_AULA_PERSONALIZZATA:
        raise ValueError(
            "Versione layout visuale Personalizzata non supportata: "
            f"{dati['schema_versione']!r}."
        )
    if dati["tipo"] != TIPO_LAYOUT_VISUALE_AULA_PERSONALIZZATA:
        raise ValueError(
            f"Tipo layout visuale Personalizzata non valido: {dati['tipo']!r}."
        )
    blocchi_json = dati["blocchi"]
    if not isinstance(blocchi_json, list):
        raise ValueError("La chiave «blocchi» del layout visuale deve essere una lista.")

    blocchi: list[BloccoBozzaPersonalizzata] = []
    for indice, blocco_json in enumerate(blocchi_json, start=1):
        if not isinstance(blocco_json, Mapping):
            raise ValueError(
                f"Il blocco visuale {indice} non è un oggetto JSON."
            )
        _richiedi_chiavi_esatte(
            blocco_json,
            {"id", "capienza", "riga", "colonna", "zona", "ids_posti"},
            f"Blocco visuale {indice}",
        )
        ids_posti = blocco_json["ids_posti"]
        if not isinstance(ids_posti, list):
            raise ValueError(
                f"Gli id posto del blocco visuale {indice} devono essere una lista."
            )
        blocchi.append(BloccoBozzaPersonalizzata(
            id=blocco_json["id"],
            capienza=blocco_json["capienza"],
            riga=blocco_json["riga"],
            colonna=blocco_json["colonna"],
            zona=blocco_json["zona"],
            ids_posti=tuple(ids_posti),
        ))

    ancora_json = dati["ancora_fisso"]
    ancora = None
    if ancora_json is not None:
        if not isinstance(ancora_json, Mapping):
            raise ValueError("L'ancora FISSO del layout visuale non è valida.")
        _richiedi_chiavi_esatte(
            ancora_json,
            {"blocco", "indice_posto"},
            "Ancora FISSO visuale",
        )
        blocco_id = _testo_non_vuoto("Il blocco dell'ancora FISSO", ancora_json["blocco"])
        indice_posto = _intero_non_negativo(
            "indice_posto", ancora_json["indice_posto"]
        )
        ancora = (blocco_id, indice_posto)

    spazi = dati.get("spazi", [])
    if not isinstance(spazi, list):
        raise ValueError("spazi deve essere una lista.")
    modello = ModelloAulaPersonalizzata(
        blocchi, griglia_fissa=dati.get("griglia_fissa", False), spazi=spazi)
    if modello.griglia_fissa:
        from moduli.dominio.griglia_layout_fissa import valida_griglia_fissa
        valida_griglia_fissa(modello)
    if ancora is not None:
        modello.imposta_ancora_fisso(*ancora)
    return IstantaneaVisualeAulaPersonalizzata.da_modello(modello)


def schema_personalizzato_da_json(dati: Mapping[str, Any]) -> SchemaBlocchiSemantico:
    """Valida e ricostruisce il formato JSON stabile v1."""
    if not isinstance(dati, Mapping):
        raise ValueError("Lo schema Personalizzata deve essere un oggetto JSON.")
    _richiedi_chiavi_esatte(
        dati,
        {"schema_versione", "tipo", "blocchi"},
        "Schema Personalizzata",
    )
    if dati["schema_versione"] != VERSIONE_SCHEMA_AULA_PERSONALIZZATA:
        raise ValueError(
            "Versione schema Personalizzata non supportata: "
            f"{dati['schema_versione']!r}."
        )
    if dati["tipo"] != TIPO_SCHEMA_AULA_PERSONALIZZATA:
        raise ValueError(f"Tipo schema Personalizzata non valido: {dati['tipo']!r}.")
    blocchi_json = dati["blocchi"]
    if not isinstance(blocchi_json, list):
        raise ValueError("La chiave «blocchi» deve essere una lista.")

    blocchi: list[BloccoAulaSemanticoSpec] = []
    for indice_blocco, blocco_json in enumerate(blocchi_json, start=1):
        if not isinstance(blocco_json, Mapping):
            raise ValueError(f"Il blocco {indice_blocco} non è un oggetto JSON.")
        _richiedi_chiavi_esatte(
            blocco_json,
            {
                "id", "capienza", "profondita", "colonna",
                "zona_prima", "zona_ultima", "posti",
            },
            f"Blocco {indice_blocco}",
        )
        posti_json = blocco_json["posti"]
        if not isinstance(posti_json, list):
            raise ValueError(f"I posti del blocco {indice_blocco} devono essere una lista.")
        posti: list[PostoAulaSemanticoSpec] = []
        for indice_posto, posto_json in enumerate(posti_json, start=1):
            if not isinstance(posto_json, Mapping):
                raise ValueError(
                    f"Il posto {indice_posto} del blocco {indice_blocco} non è un oggetto JSON."
                )
            _richiedi_chiavi_esatte(
                posto_json,
                {"indice", "id", "ancora_fisso"},
                f"Posto {indice_posto} del blocco {indice_blocco}",
            )
            posti.append(PostoAulaSemanticoSpec(
                indice=posto_json["indice"],
                id=posto_json["id"],
                ancora_fisso=posto_json["ancora_fisso"],
            ))
        blocchi.append(BloccoAulaSemanticoSpec(
            id=blocco_json["id"],
            capienza=blocco_json["capienza"],
            profondita=blocco_json["profondita"],
            colonna=blocco_json["colonna"],
            zona_prima=blocco_json["zona_prima"],
            zona_ultima=blocco_json["zona_ultima"],
            posti=tuple(posti),
        ))
    return SchemaBlocchiSemantico(tuple(blocchi))
