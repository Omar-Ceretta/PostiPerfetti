# -*- coding: utf-8 -*-
"""Contratto puro del Layout unico 2/3 usato dalla GUI e dal calcolo.

La riga visuale resta nella fotografia; la profondità semantica è il rango
delle sole righe occupate. Il corridoio verticale è una fascia di rendering,
non una profondità aggiuntiva. Le colonne crescono da sinistra a destra viste
dal docente, in basso, che guarda gli studenti; riga 0 è la fascia più vicina.
Questa convenzione entra nella firma in memoria, senza nuovi campi su disco.

Il controllo riguarda la topologia logica, con limiti opzionali dell'editor
e fascia docente espressi in celle, senza Qt o pixel. Non valuta L3, PRIMA, ULTIMA,
scoring o fattibilità: una geometria pronta non garantisce una soluzione HARD.
Non modifica bozza, lettori storici 2/3/4, preflight delle zone o JSON esistenti.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from dataclasses import dataclass

from moduli.dominio.aula_personalizzata import (
    BloccoBozzaPersonalizzata,
    IstantaneaVisualeAulaPersonalizzata,
    ModelloAulaPersonalizzata,
)
from moduli.dominio.disposizione_effettiva import DisposizioneEffettiva
from moduli.dominio.schema_blocchi_semantico import SchemaBlocchiSemantico


CONVENZIONE_DOCENTE = "docente_in_basso_sinistra_destra_viste_dal_docente"


@dataclass(frozen=True, slots=True)
class ProblemaLayoutUnico:
    codice: str
    messaggio: str
    ambito: str = "geometria"
    severita: str = "bloccante"
    blocco_id: str | None = None
    posto_id: str | None = None
    altro_blocco_id: str | None = None


@dataclass(frozen=True, slots=True)
class EsitoLayoutUnico:
    problemi: tuple[ProblemaLayoutUnico, ...] = ()

    @property
    def valido(self) -> bool:
        return not self.problemi

    @property
    def geometria_valida(self) -> bool:
        """La bozza può essere corretta anche senza dati sufficienti di classe."""
        return not any(p.ambito != "classe" for p in self.problemi)


class ErroreLayoutUnico(ValueError):
    def __init__(self, esito: EsitoLayoutUnico) -> None:
        self.esito = esito
        super().__init__("\n".join(p.messaggio for p in esito.problemi))


def _fotografia(
    aula: ModelloAulaPersonalizzata | IstantaneaVisualeAulaPersonalizzata,
) -> IstantaneaVisualeAulaPersonalizzata:
    if isinstance(aula, ModelloAulaPersonalizzata):
        aula = IstantaneaVisualeAulaPersonalizzata.da_modello(aula)
    if not isinstance(aula, IstantaneaVisualeAulaPersonalizzata):
        raise TypeError("aula deve essere una bozza o un'istantanea visuale.")
    blocchi = tuple(aula.blocchi)
    if any(not isinstance(b, BloccoBozzaPersonalizzata) for b in blocchi):
        raise TypeError("La fotografia deve contenere blocchi della bozza.")
    # L'istantanea storica non impone tuple: copiare anche un'eventuale lista.
    ancora = aula.ancora_fisso
    if isinstance(ancora, (tuple, list)):
        ancora = tuple(ancora)
    return IstantaneaVisualeAulaPersonalizzata(blocchi, ancora, aula.griglia_fissa, tuple(tuple(p) for p in aula.spazi))


def _intero(valore: object) -> bool:
    return type(valore) is int and valore >= 0


@dataclass(frozen=True, slots=True)
class GrigliaLayoutUnico:
    """Limiti dell'editor; zona docente = (riga, colonna iniziale, fine esclusa).

    Non restringe retroattivamente lettori o schemi storici. La fascia docente
    occupa le colonne 5..10 della riga 0 nella griglia attuale 8 × 16.
    """

    righe: int = 8
    colonne: int = 16
    zona_docente: tuple[int, int, int] = (0, 5, 11)

    def __post_init__(self) -> None:
        if not _intero(self.righe) or not _intero(self.colonne) or min(self.righe, self.colonne) < 1:
            raise ValueError("La griglia richiede righe e colonne intere positive.")
        zona = tuple(self.zona_docente)
        if (len(zona) != 3 or not all(_intero(v) for v in zona)
                or zona[0] >= self.righe or not 0 <= zona[1] < zona[2] <= self.colonne):
            raise ValueError("Zona docente non valida per la griglia.")
        object.__setattr__(self, "zona_docente", zona)


def _problemi_ingombro(capienza, riga, colonna, griglia, id_blocco=None):
    dettagli = {"blocco_id": id_blocco}
    if not _intero(capienza) or capienza not in (2, 3):
        return (ProblemaLayoutUnico("capienza_blocco", "Il banco deve avere 2 o 3 posti interi.",
                                   **dettagli),)
    if (not _intero(riga) or not _intero(colonna)
            or riga >= griglia.righe or colonna + capienza > griglia.colonne):
        return (ProblemaLayoutUnico("fuori_griglia", "Il banco uscirebbe dalla griglia dell'aula.",
                                   **dettagli),)
    r, inizio, fine = griglia.zona_docente
    if riga == r and colonna < fine and colonna + capienza > inizio:
        return (ProblemaLayoutUnico("zona_docente", "Questo spazio è riservato alla zona docente.",
                                   **dettagli),)
    return ()


def _problema_separazione(capienza, riga, colonna, blocco, id_blocco=None):
    if riga != blocco.riga:
        return None
    spazio = max(colonna, blocco.colonna) - min(colonna + capienza,
                                               blocco.colonna + blocco.capienza)
    if spazio >= 1:
        return None
    codice = "collisione" if spazio < 0 else "corridoio_mancante"
    motivo = "si sovrappongono" if spazio < 0 else "richiedono una cella libera fra loro"
    return ProblemaLayoutUnico(codice, f"I banchi {id_blocco or 'nuovo'} e {blocco.id} {motivo}.",
                              blocco_id=id_blocco, altro_blocco_id=blocco.id)


def valuta_posizione_blocco(
    aula: ModelloAulaPersonalizzata | IstantaneaVisualeAulaPersonalizzata,
    *, capienza: int, riga: int, colonna: int, griglia: GrigliaLayoutUnico,
    escludi_id: str | None = None,
) -> EsitoLayoutUnico:
    """Valuta solo la posizione proposta, per consentire riparazioni progressive.

    Non blocca lo spostamento a causa di errori fra altri banchi di una vecchia
    bozza. Non cambia ID, ancora, zone, input o contatori della classe.
    """
    if not isinstance(griglia, GrigliaLayoutUnico):
        raise TypeError("griglia deve essere una GrigliaLayoutUnico.")
    foto = _fotografia(aula)
    problemi = list(_problemi_ingombro(capienza, riga, colonna, griglia, escludi_id))
    if problemi:
        return EsitoLayoutUnico(tuple(problemi))
    if escludi_id is not None:
        originale = next((b for b in foto.blocchi if b.id == escludi_id), None)
        if originale is None or originale.capienza != capienza:
            return EsitoLayoutUnico((ProblemaLayoutUnico(
                "blocco_non_coerente", "Il banco da spostare non corrisponde alla bozza.",
                blocco_id=escludi_id),))
    for b in foto.blocchi:
        if b.id == escludi_id:
            continue
        problema = _problema_separazione(capienza, riga, colonna, b, escludi_id)
        if problema is not None:
            problemi.append(problema)
    return EsitoLayoutUnico(tuple(problemi))


def posizione_lecita_piu_vicina(
    aula: ModelloAulaPersonalizzata | IstantaneaVisualeAulaPersonalizzata,
    *, capienza: int, riga: int, colonna: int, griglia: GrigliaLayoutUnico,
    escludi_id: str | None = None,
) -> tuple[int, int] | None:
    """Proposta senza mutazioni: distanza Manhattan in celle, non centimetri.

    A pari distanza preferisce la stessa riga, poi la riga più vicina al
    docente e la colonna più a sinistra. La GUI deve chiedere un nuovo rilascio.
    """
    if not isinstance(griglia, GrigliaLayoutUnico):
        raise TypeError("griglia deve essere una GrigliaLayoutUnico.")
    if (not _intero(capienza) or capienza not in (2, 3)
            or type(riga) is not int or type(colonna) is not int):
        return None
    foto = _fotografia(aula)
    candidati = ((r, c) for r in range(griglia.righe)
                 for c in range(max(0, griglia.colonne - capienza + 1)))
    ordine = sorted(candidati, key=lambda p: (
        abs(p[0] - riga) + abs(p[1] - colonna), abs(p[0] - riga), p[0], p[1]))
    return next((p for p in ordine if valuta_posizione_blocco(
        foto, capienza=capienza, riga=p[0], colonna=p[1], griglia=griglia,
        escludi_id=escludi_id).valido), None)


def valuta_layout_unico(
    aula: ModelloAulaPersonalizzata | IstantaneaVisualeAulaPersonalizzata,
    *,
    numero_studenti: int | None = None,
    numero_fissi: int | None = None,
    griglia: GrigliaLayoutUnico | None = None,
) -> EsitoLayoutUnico:
    """Diagnostica senza mutazioni; entrambi i conteggi servono per generare.

    Gli errori di classe sono distinti dalla geometria. Senza FISSO si richiede
    di rimuovere l'ancora residua, come nel contratto Personalizzata vigente.
    Il conteggio non certifica identità, vincoli o occupanti della classe.
    """
    foto = _fotografia(aula)
    if griglia is not None and not isinstance(griglia, GrigliaLayoutUnico):
        raise TypeError("griglia deve essere una GrigliaLayoutUnico oppure None.")
    problemi: list[ProblemaLayoutUnico] = []

    def segnala(codice: str, messaggio: str, **dettagli: object) -> None:
        problemi.append(ProblemaLayoutUnico(codice, messaggio, **dettagli))

    if not foto.blocchi:
        segnala("aula_vuota", "Aggiungi almeno un blocco da 2 o 3 posti.")
    per_id: dict[str, BloccoBozzaPersonalizzata] = {}
    posti: dict[str, str] = {}
    regolari: list[BloccoBozzaPersonalizzata] = []
    for b in foto.blocchi:
        if b.id in per_id:
            segnala("id_blocco_duplicato", f"ID blocco duplicato: {b.id}.",
                    blocco_id=b.id)
        per_id[b.id] = b
        for id_posto in b.ids_posti:
            if id_posto in posti:
                segnala("id_posto_duplicato", f"ID posto duplicato: {id_posto}.",
                        blocco_id=b.id, posto_id=id_posto,
                        altro_blocco_id=posti[id_posto])
            posti[id_posto] = b.id
        if not _intero(b.capienza) or b.capienza not in (2, 3):
            segnala("capienza_blocco", f"Il blocco {b.id} deve avere 2 o 3 posti interi.",
                    blocco_id=b.id)
            continue
        regolari.append(b)
        if griglia is not None:
            problemi.extend(_problemi_ingombro(b.capienza, b.riga, b.colonna, griglia, b.id))
    # Tutte le coppie, anche quando una collisione nasconde un terzo blocco.
    for i, a in enumerate(regolari):
        for b in regolari[i + 1:]:
            problema = _problema_separazione(a.capienza, a.riga, a.colonna, b, a.id)
            if problema is not None:
                problemi.append(problema)

    ancora = foto.ancora_fisso
    if ancora is not None:
        valida = (isinstance(ancora, tuple) and len(ancora) == 2
                  and isinstance(ancora[0], str) and _intero(ancora[1])
                  and ancora[0] in per_id
                  and ancora[1] < len(per_id[ancora[0]].ids_posti))
        if not valida:
            segnala("ancora_non_reale", "L'ancora FISSO deve indicare un posto reale.",
                    blocco_id=ancora[0] if isinstance(ancora, tuple) and ancora
                    and isinstance(ancora[0], str) else None)

    if numero_studenti is None:
        segnala("studenti_non_specificati", "Specifica il numero di studenti della classe.",
                ambito="classe")
    elif not _intero(numero_studenti) or numero_studenti == 0:
        segnala("numero_studenti", "Il numero di studenti deve essere un intero positivo.",
                ambito="classe")
    elif len(posti) != numero_studenti:
        segnala("capienza_classe", f"Posti unici: {len(posti)}; studenti: {numero_studenti}.",
                ambito="classe")

    if numero_fissi is None:
        segnala("fissi_non_specificati", "Specifica quanti studenti FISSO ha la classe.",
                ambito="classe")
    elif not _intero(numero_fissi) or numero_fissi > 1:
        segnala("numero_fissi", "La classe deve avere zero o un solo FISSO.", ambito="classe")
    elif numero_fissi == 1 and ancora is None:
        segnala("ancora_mancante", "Assegna il posto FISSO.", ambito="classe")
    elif numero_fissi == 0 and ancora is not None:
        segnala("ancora_senza_fisso", "Rimuovi l'ancora: la classe non ha un FISSO.",
                ambito="classe")
    return EsitoLayoutUnico(tuple(problemi))


@dataclass(frozen=True, slots=True)
class LayoutUnico:
    """Geometria congelata; non contiene nomi, scoring o stato di persistenza."""

    schema: SchemaBlocchiSemantico
    istantanea_visuale: IstantaneaVisualeAulaPersonalizzata

    def __post_init__(self) -> None:
        if not isinstance(self.schema, SchemaBlocchiSemantico):
            raise TypeError("schema deve essere uno SchemaBlocchiSemantico.")
        foto = _fotografia(self.istantanea_visuale)
        esito = valuta_layout_unico(foto)
        errori = EsitoLayoutUnico(tuple(p for p in esito.problemi if p.ambito != "classe"))
        if not errori.valido:
            raise ErroreLayoutUnico(errori)
        foto = IstantaneaVisualeAulaPersonalizzata(
            tuple(sorted(foto.blocchi, key=lambda b: (b.riga, b.colonna, b.id))),
            foto.ancora_fisso, foto.griglia_fissa, tuple(sorted(foto.spazi)),
        )
        foto.valida_contro_schema(self.schema)
        object.__setattr__(self, "istantanea_visuale", foto)


def congela_layout_unico(
    aula: ModelloAulaPersonalizzata | IstantaneaVisualeAulaPersonalizzata,
    *, numero_studenti: int, numero_fissi: int,
    griglia: GrigliaLayoutUnico | None = None,
) -> LayoutUnico:
    """Convalida i conteggi e congela una copia, senza correggere la bozza."""
    foto = _fotografia(aula)
    esito = valuta_layout_unico(foto, numero_studenti=numero_studenti,
                               numero_fissi=numero_fissi, griglia=griglia)
    if not esito.valido:
        raise ErroreLayoutUnico(esito)
    if foto.griglia_fissa:
        from moduli.dominio.griglia_layout_fissa import valida_griglia_fissa
        valida_griglia_fissa(foto)
    schema = foto.ricostruisci_modello().costruisci_schema(
        numero_studenti=numero_studenti, ha_fisso=bool(numero_fissi))
    return LayoutUnico(schema, foto)


def identita_layout_unico(layout: LayoutUnico) -> tuple:
    """Firma geometrica completa e deterministica, indipendente dagli occupanti.

    La futura guardia di sessione deve aggiungere classe, vincoli e opzioni.
    L'ordine di inserimento non conta; gli ID e le righe visuali invece contano.
    """
    if not isinstance(layout, LayoutUnico):
        raise TypeError("layout deve essere un LayoutUnico congelato.")
    return (
        "layout_unico_v1", CONVENZIONE_DOCENTE,
        layout.schema.identita_semantica(),
        tuple((b.id, b.riga, b.colonna, b.capienza, b.zona, b.ids_posti)
              for b in layout.istantanea_visuale.blocchi),
        layout.istantanea_visuale.ancora_fisso,
        layout.istantanea_visuale.griglia_fissa,
        layout.istantanea_visuale.spazi,
    )


def verifica_geometria_output(
    layout: LayoutUnico, output: DisposizioneEffettiva,
) -> EsitoLayoutUnico:
    """Confronto esatto per ID; restituisce diagnostica senza mutare l'output.

    Ignora ordine dei blocchi, occupanti e modalità del motore. Il risultato
    tipizzato certifica già copertura/unicità, ma la classe e gli HARD degli
    studenti richiedono un verificatore distinto prima dell'accettazione.
    """
    if not isinstance(layout, LayoutUnico) or not isinstance(output, DisposizioneEffettiva):
        raise TypeError("Servono LayoutUnico e DisposizioneEffettiva.")
    problemi: list[ProblemaLayoutUnico] = []

    def segnala(codice: str, messaggio: str, **dettagli: object) -> None:
        problemi.append(ProblemaLayoutUnico(codice, messaggio, ambito="output", **dettagli))

    attesi = {b.id: b for b in layout.schema.blocchi}
    ricevuti = {b.id: b for b in output.blocchi}
    righe = {b.id: b.riga for b in layout.istantanea_visuale.blocchi}
    for id_blocco in sorted(attesi.keys() - ricevuti.keys()):
        segnala("blocco_mancante", f"Manca il blocco {id_blocco}.", blocco_id=id_blocco)
    for id_blocco in sorted(ricevuti.keys() - attesi.keys()):
        segnala("blocco_aggiunto", f"Blocco estraneo: {id_blocco}.", blocco_id=id_blocco)
    for id_blocco in sorted(attesi.keys() & ricevuti.keys()):
        a, b = attesi[id_blocco], ricevuti[id_blocco]
        for campo, atteso in (
            ("capienza", a.capienza), ("profondita", a.profondita),
            ("colonna", a.colonna), ("riga_visuale", righe[id_blocco]),
            ("zona_prima", a.zona_prima), ("zona_ultima", a.zona_ultima),
        ):
            if getattr(b, campo) != atteso:
                segnala(f"{campo}_alterata", f"{campo} alterata nel blocco {id_blocco}.",
                        blocco_id=id_blocco)
        for indice in range(max(len(a.posti), len(b.posti))):
            id_atteso = a.posti[indice].id if indice < len(a.posti) else None
            id_ricevuto = b.posti[indice].id if indice < len(b.posti) else None
            if id_atteso != id_ricevuto:
                segnala("posto_alterato", f"Posto {indice} alterato nel blocco {id_blocco}.",
                        blocco_id=id_blocco, posto_id=id_atteso or id_ricevuto)
    ancora = layout.schema.posto_ancora_fisso
    id_ancora = ancora.id if ancora is not None else None
    if output.ancora_fisso != id_ancora:
        segnala("ancora_alterata", "L'output ha alterato l'ancora FISSO.", posto_id=id_ancora)
    return EsitoLayoutUnico(tuple(problemi))
