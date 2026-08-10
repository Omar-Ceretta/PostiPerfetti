# -*- coding: utf-8 -*-
"""utilita.py — servizi condivisi per interfaccia, report e file.

Parte di «PostiPerfetti», programma per l'assegnazione automatica dei posti.
Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3. Software libero, distribuito senza garanzie.

Raccoglie funzioni senza stato per percorsi, vincoli, report, popup, icone e
controlli Qt riutilizzati da più moduli.
"""

import os
import unicodedata
from html import escape

from PySide6.QtWidgets import (
    QApplication, QMessageBox, QPushButton, QWidget,
    QTextEdit, QDialog, QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtCore import Qt, QObject, QEvent, QSize, QUrl

from moduli.metrica_pulizia import (
    estrai_gruppi,
    adiacenze_in_fila,
    TIPO_TERZETTO,
    TIPO_QUARTETTO,
)
from moduli.tema import C, get_tema
from moduli.percorsi import get_resource_path


# Dimensionamento delle finestre
def adatta_finestra_allo_schermo(
    finestra,
    larghezza_ideale: int,
    altezza_ideale: int,
    larghezza_minima: int = 640,
    altezza_minima: int = 480,
    margine_larghezza: float = 0.96,
    margine_altezza: float = 0.92,
) -> None:
    """Imposta dimensione iniziale e minima senza superare lo schermo.

    Qt lavora in pixel logici, quindi il calcolo rispetta automaticamente il
    ridimensionamento DPI. In assenza di uno schermo valido usa le misure richieste.
    """
    applicazione = QApplication.instance()

    schermo = finestra.screen()

    if schermo is None and applicazione is not None:
        schermo = applicazione.primaryScreen()

    if schermo is None:
        finestra.setMinimumSize(
            larghezza_minima,
            altezza_minima
        )
        finestra.resize(
            larghezza_ideale,
            altezza_ideale
        )
        return

    area_disponibile = schermo.availableGeometry()

    larghezza_massima = max(
        320,
        int(area_disponibile.width() * margine_larghezza)
    )
    altezza_massima = max(
        240,
        int(area_disponibile.height() * margine_altezza)
    )

    larghezza_iniziale = max(
        320,
        min(larghezza_ideale, larghezza_massima)
    )
    altezza_iniziale = max(
        240,
        min(altezza_ideale, altezza_massima)
    )

    larghezza_minima_effettiva = min(
        larghezza_minima,
        larghezza_iniziale
    )
    altezza_minima_effettiva = min(
        altezza_minima,
        altezza_iniziale
    )

    finestra.setMinimumSize(
        larghezza_minima_effettiva,
        altezza_minima_effettiva
    )
    finestra.resize(
        larghezza_iniziale,
        altezza_iniziale
    )


# Pattern condivisi dal report live e dallo Storico. I chiamanti devono
# copiarli prima di aggiungere condizioni locali.
PATTERN_EVIDENZIAZIONE_REPORT = [
    "Coppia già usata",
    "BLACKLIST",
    "RIUTILIZZATA",
    "Vicino del FISSO",
]

# Giudizi e conteggi delle vicinanze
def giudizio_da_note(note: list[str] | None) -> str:
    """Restituisce il giudizio di qualità ricavato dalle note della coppia.

    Le incompatibilità hanno precedenza sulle affinità; una coppia senza vincoli
    specifici è ACCETTABILE. La ripetizione viene segnalata separatamente.
    """
    note = note or []

    for n in note:
        if n.startswith("Incompatibilità di livello 2") or n.startswith("INCOMPATIBILITÀ ASSOLUTA"):
            return 'CRITICA'
        if n.startswith("Incompatibilità di livello 1"):
            return 'PROBLEMATICA'

    for n in note:
        if n.startswith("Affinità di livello 3"):
            return 'OTTIMA'
        if n.startswith("Affinità di livello 2"):
            return 'BUONA'
        if n.startswith("Affinità di livello 1"):
            return 'DISCRETA'

    return 'ACCETTABILE'


def conteggio_giudizi_vicinanze(assegnatore) -> dict:
    """Conta i giudizi di tutte le vicinanze nel modo a coppie.

    Comprende coppie ordinarie, adiacenze del trio, coppia accanto al FISSO e
    adiacenza FISSO-vicino. Usa lo stesso metro del dettaglio del report, così i
    riepiloghi condividono gli stessi valori.
    """
    conteggio = {
        'OTTIMA': 0, 'BUONA': 0, 'DISCRETA': 0,
        'ACCETTABILE': 0, 'PROBLEMATICA': 0, 'CRITICA': 0,
    }

    for _s1, _s2, info in assegnatore.coppie_formate:
        g = giudizio_da_note(info.get('note', []))
        if g in conteggio:
            conteggio[g] += 1

    if getattr(assegnatore, 'trio_identificato', None):
        _trio = assegnatore.trio_identificato
        for _s1, _s2 in [(_trio[0], _trio[1]), (_trio[1], _trio[2])]:
            _ris = assegnatore.motore_vincoli.calcola_punteggio_coppia(_s1, _s2)
            g = giudizio_da_note(_ris.get('note', []))
            if g in conteggio:
                conteggio[g] += 1

    _fisso = getattr(assegnatore, 'studente_fisso', None)
    if _fisso is not None:
        _gruppo_adj = getattr(assegnatore, 'gruppo_adiacente_fisso', None) or []
        if len(_gruppo_adj) >= 2:
            if len(_gruppo_adj) >= 3 and isinstance(_gruppo_adj[2], dict):
                _note_adj = _gruppo_adj[2].get('note', [])
            else:
                _note_adj = assegnatore.motore_vincoli.calcola_punteggio_coppia(
                    _gruppo_adj[0], _gruppo_adj[1]).get('note', [])
            g = giudizio_da_note(_note_adj)
            if g in conteggio:
                conteggio[g] += 1

        _nome_vic = getattr(assegnatore, 'nome_adiacente_fisso', None)
        _vicino = None
        if _nome_vic:
            _vicino = next(
                (s for s in (getattr(assegnatore, 'studenti', None) or [])
                 if s.get_nome_completo() == _nome_vic), None)
        if _vicino is not None:
            _ris = assegnatore.motore_vincoli.calcola_punteggio_coppia(
                _fisso, _vicino)
            g = giudizio_da_note(_ris.get('note', []))
            if g in conteggio:
                conteggio[g] += 1

    return conteggio


def conta_riutilizzate(assegnatore) -> dict:
    """Conta le vicinanze riutilizzate nel modo a coppie.

    Distingue coppie ordinarie, adiacenze dei gruppi non-coppia e le due relazioni
    del blocco FISSO. Il totale comprende tutte le vicinanze reali; i campi
    separati del FISSO servono a mostrarne i nomi nel dettaglio.
    """
    normali = assegnatore.stats['coppie_riutilizzate']

    trio = 0
    for gruppo in estrai_gruppi(assegnatore):
        if gruppo.tipo in (TIPO_TERZETTO, TIPO_QUARTETTO):
            for s1, s2 in adiacenze_in_fila(gruppo.membri):
                ris = assegnatore.motore_vincoli.calcola_punteggio_coppia(s1, s2)
                note_coppia = ris.get('note', []) or []
                if any("già usata" in nota for nota in note_coppia):
                    trio += 1

    vicino_fisso = 0
    vicino_fisso_nome = None
    fisso = getattr(assegnatore, 'studente_fisso', None)
    nome_vic = getattr(assegnatore, 'nome_adiacente_fisso', None)
    config_app = getattr(assegnatore, 'config_app', None)
    if fisso and nome_vic and config_app is not None:
        contatore_vic = config_app.config_data.get(
            "studenti_vicino_fisso_contatore", {})
        if contatore_vic.get(nome_vic, 0) >= 1:
            vicino_fisso = 1
            vicino_fisso_nome = nome_vic

    coppia_fisso = 0
    coppia_fisso_nomi = None
    gruppo_adj = getattr(assegnatore, 'gruppo_adiacente_fisso', None)
    if gruppo_adj and len(gruppo_adj) >= 2 and config_app is not None:
        s1_adj = gruppo_adj[0]
        s2_adj = gruppo_adj[1]
        nomi_adj = {s1_adj.get_nome_completo(), s2_adj.get_nome_completo()}
        coppie_usate = config_app.config_data.get("coppie_da_evitare", [])
        adj_riutilizzata = any(
            set(c.get("studenti", [])) == nomi_adj and c.get("volte_usata", 0) >= 1
            for c in coppie_usate)
        if adj_riutilizzata:
            coppia_fisso = 1
            coppia_fisso_nomi = (s1_adj.get_nome_completo(),
                                 s2_adj.get_nome_completo())

    totali = normali + trio + coppia_fisso + vicino_fisso

    return {
        'normali': normali,
        'trio': trio,
        'totali': totali,
        'vicino_fisso': vicino_fisso,
        'vicino_fisso_nome': vicino_fisso_nome,
        'coppia_fisso': coppia_fisso,
        'coppia_fisso_nomi': coppia_fisso_nomi,
    }


# Conteggio e presentazione dei vincoli
def conta_vincoli(studenti: list[dict]) -> dict:
    """Conta i vincoli di una classe per livello e posizione.

    Le coppie reciproche vengono fuse tramite una chiave ordinata; FISSO, PRIMA e
    ULTIMA sono invece conteggiati per studente.
    """
    incomp_livello = {}

    affinita_livello = {}

    n_fisso = 0
    n_prima = 0
    n_ultima = 0

    for studente in studenti:
        nome_studente = f"{studente['cognome']} {studente['nome']}"

        posizione = studente["posizione"]
        if posizione == "FISSO":
            n_fisso += 1
        elif posizione == "PRIMA":
            n_prima += 1
        elif posizione == "ULTIMA":
            n_ultima += 1

        for altro_nome, livello in studente["incompatibilita"].items():
            coppia = tuple(sorted([nome_studente, altro_nome]))
            incomp_livello[coppia] = int(livello)

        for altro_nome, livello in studente["affinita"].items():
            coppia = tuple(sorted([nome_studente, altro_nome]))
            affinita_livello[coppia] = int(livello)

    n_incomp_lievi = 0
    n_incomp_forti = 0
    n_incomp_assolute = 0
    for livello in incomp_livello.values():
        if livello >= 3:
            n_incomp_assolute += 1
        elif livello == 2:
            n_incomp_forti += 1
        else:
            n_incomp_lievi += 1

    n_aff_lievi = 0
    n_aff_medie = 0
    n_aff_ottime = 0
    for livello in affinita_livello.values():
        if livello >= 3:
            n_aff_ottime += 1
        elif livello == 2:
            n_aff_medie += 1
        else:
            n_aff_lievi += 1

    return {
        "incomp_lievi":    n_incomp_lievi,
        "incomp_forti":    n_incomp_forti,
        "incomp_assolute": n_incomp_assolute,
        "aff_lievi":       n_aff_lievi,
        "aff_medie":       n_aff_medie,
        "aff_ottime":      n_aff_ottime,
        "fisso":           n_fisso,
        "prima":           n_prima,
        "ultima":          n_ultima,
    }


def dettaglio_vincoli(studenti: list[dict]) -> dict:
    """Raggruppa i vincoli dal punto di vista di ciascuno studente.

    A differenza del riepilogo numerico, non fonde i reciproci. Gli studenti sono
    ordinati alfabeticamente; i vincoli per intensità decrescente e poi per nome.
    """
    blocchi_incomp = []
    blocchi_aff = []

    nomi_fisso = []
    nomi_prima = []
    nomi_ultima = []

    def ordina_vincoli(coppie):
        return sorted(coppie, key=lambda c: (-c[1], c[0]))

    for studente in studenti:
        nome_studente = f"{studente['cognome']} {studente['nome']}"

        posizione = studente["posizione"]
        if posizione == "FISSO":
            nomi_fisso.append(nome_studente)
        elif posizione == "PRIMA":
            nomi_prima.append(nome_studente)
        elif posizione == "ULTIMA":
            nomi_ultima.append(nome_studente)

        coppie_incomp = [(altro, int(liv)) for altro, liv in studente["incompatibilita"].items()]
        if coppie_incomp:
            blocchi_incomp.append({
                "nome": nome_studente,
                "vincoli": ordina_vincoli(coppie_incomp),
            })

        coppie_aff = [(altro, int(liv)) for altro, liv in studente["affinita"].items()]
        if coppie_aff:
            blocchi_aff.append({
                "nome": nome_studente,
                "vincoli": ordina_vincoli(coppie_aff),
            })

    blocchi_incomp.sort(key=lambda b: b["nome"])
    blocchi_aff.sort(key=lambda b: b["nome"])

    return {
        "incompatibilita": blocchi_incomp,
        "affinita":        blocchi_aff,
        "fisso":           sorted(nomi_fisso),
        "prima":           sorted(nomi_prima),
        "ultima":          sorted(nomi_ultima),
    }


def formato_vincoli(conteggi: dict, colore_etichetta: str, colore_critico: str, colore_normale: str) -> str:
    """Compone l'HTML sintetico dei vincoli per la label dell'Editor.

    Le quantità pari a zero vengono omesse; se non esistono vincoli restituisce un
    messaggio esplicito.
    """

    def voce(quantita, sing, plur, critico=False, grassetto=False):
        if quantita <= 0:
            return ""
        testo = f"{quantita} {sing if quantita == 1 else plur}"
        colore = colore_critico if critico else colore_normale
        peso = " font-weight:bold;" if grassetto else ""
        return f'<span style="color:{colore};{peso}">{testo}</span>'

    voci_incomp = [
        voce(conteggi["incomp_lievi"],    "leggera",  "leggere"),
        voce(conteggi["incomp_forti"],    "media",    "medie"),
        voce(conteggi["incomp_assolute"], "assoluta", "assolute", critico=True),
    ]
    voci_incomp = [v for v in voci_incomp if v]

    voci_aff = [
        voce(conteggi["aff_lievi"],  "leggera", "leggere"),
        voce(conteggi["aff_medie"],  "buona",   "buone"),
        voce(conteggi["aff_ottime"], "forte",   "forti", grassetto=True),
    ]
    voci_aff = [v for v in voci_aff if v]

    voci_pos = [
        voce(conteggi["fisso"],  "FISSO",  "FISSO", critico=True),
        voce(conteggi["prima"],  "PRIMA",  "PRIMA", critico=True),
        voce(conteggi["ultima"], "ULTIMA", "ULTIMA"),
    ]
    voci_pos = [v for v in voci_pos if v]

    def etichetta(testo):
        return f'<span style="color:{colore_etichetta}; font-weight:bold;">{testo}</span>'

    gruppi = []
    if voci_incomp:
        gruppi.append(etichetta("Incompatibilità:") + " " + " · ".join(voci_incomp))
    if voci_aff:
        gruppi.append(etichetta("Affinità:") + " " + " · ".join(voci_aff))
    if voci_pos:
        gruppi.append(etichetta("Posizione:") + " " + " · ".join(voci_pos))

    if not gruppi:
        return (
            f'<span style="color:{colore_normale};">'
            "Nessun vincolo impostato (incompatibilità, affinità, posizioni)"
            "</span>"
        )

    separatore = f'<span style="color:{colore_normale};"> | </span>'
    intestazione = f'<span style="color:{colore_normale}; font-weight:bold;">VINCOLI ATTIVI =</span> '
    return intestazione + separatore.join(gruppi)


def _chiave_vocabolario(testo: str) -> str:
    """Crea una chiave alfabetica senza distinzione di maiuscole e accenti."""
    decomposto = unicodedata.normalize("NFD", (testo or "").casefold())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def ordina_studenti(studenti_dati: list[dict]) -> tuple[list[dict], bool]:
    """Ordina i dizionari degli studenti per cognome e nome.

    L'ordinamento è stabile e usa la chiave da vocabolario del modulo.
    """
    def chiave(s):
        return (_chiave_vocabolario(s.get("cognome", "")),
                _chiave_vocabolario(s.get("nome", "")))

    ordinata = sorted(studenti_dati, key=chiave)
    riordino_avvenuto = ordinata != studenti_dati
    return ordinata, riordino_avvenuto


def formato_dettaglio_vincoli(dettaglio: dict, colore_titolo: str, colore_critico: str, colore_normale: str) -> str:
    """Compone l'HTML della vista dettagliata dei vincoli.

    Mostra incompatibilità, affinità e posizioni soltanto quando presenti, con
    colori ed evidenze coerenti col significato pedagogico.
    """

    etichette_incomp = {3: "assoluta", 2: "media", 1: "leggera"}
    etichette_aff = {3: "forte", 2: "buona", 1: "leggera"}

    INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"

    def intestazione_categoria(testo):
        return (f'<p style="color:{colore_critico}; font-weight:bold; '
                f'margin:10px 0 4px 0;">{testo}</p>')

    def separatore():
        return f'<hr style="border:none; border-top:1px solid {colore_normale}; margin:10px 0;">'

    def blocco_categoria(
        titolo, blocchi, etichette,
        colore_evidenza=None,
        evidenza_grassetto=False,
    ):
        if not blocchi:
            return ""
        html = intestazione_categoria(titolo)
        for b in blocchi:
            html += (f'<p style="color:{colore_normale}; font-weight:bold; '
                     f'margin:6px 0 0 0;">{b["nome"]}</p>')
            for compagno, livello in b["vincoli"]:
                etichetta = etichette.get(livello, f"liv. {livello}")
                testo = f'- {compagno} ({etichetta} - liv. {livello})'
                evidenziata = bool(colore_evidenza and livello >= 3)
                colore_riga = colore_evidenza if evidenziata else colore_normale
                peso = " font-weight:bold;" if (evidenziata and evidenza_grassetto) else ""
                html += (f'<p style="color:{colore_riga};{peso} margin:0 0 0 0;">'
                         f'{INDENT}{testo}</p>')
        return html

    def blocco_posizione(dett):
        righe = []
        for chiave, etichetta, critico in (
            ("fisso", "FISSO", True),
            ("prima", "PRIMA", True),
            ("ultima", "ULTIMA", False),
        ):
            for nome in dett.get(chiave, []):
                colore_riga = colore_critico if critico else colore_normale
                righe.append(f'<p style="color:{colore_riga}; margin:2px 0 0 0;">'
                             f'– {nome} → {etichetta}</p>')
        if not righe:
            return ""
        return intestazione_categoria("POSIZIONE") + "".join(righe)

    sezioni = []
    sezioni.append(blocco_categoria(
        "INCOMPATIBILITÀ", dettaglio["incompatibilita"],
        etichette_incomp, colore_evidenza=colore_critico,
    ))
    sezioni.append(blocco_categoria(
        "AFFINITÀ", dettaglio["affinita"],
        etichette_aff,
        colore_evidenza=colore_titolo,
        evidenza_grassetto=True,
    ))
    sezioni.append(blocco_posizione(dettaglio))

    sezioni = [s for s in sezioni if s]

    if not sezioni:
        return (
            f'<p style="color:{colore_normale};">'
            "Nessun vincolo impostato su questa classe."
            "</p>"
        )

    return separatore().join(sezioni)


# Percorsi, icone e popup

def carica_icona(nome: str) -> QIcon:
    """Carica l'icona Lucide corrispondente al tema attivo.

    Le varianti si trovano in ``risorse/icone/lucide/<tema>``. Se il tema è sconosciuto usa la variante scura; se il file non è disponibile,
    restituisce un'icona vuota e lascia comprensibile il testo.
    """
    tema = get_tema()
    if tema not in ("chiaro", "scuro"):
        print(
            f"⚠ Tema non riconosciuto per le icone: {tema!r}; "
            "uso 'scuro'."
        )
        tema = "scuro"

    percorso = get_resource_path(
        "icone",
        "lucide",
        tema,
        f"{nome}.svg",
    )

    if not os.path.isfile(percorso):
        print(f"⚠ Icona non trovata: {percorso}")
        return QIcon()

    icona = QIcon(percorso)
    if icona.isNull():
        print(f"⚠ Icona non caricabile: {percorso}")
        return QIcon()

    return icona


def applica_icona(widget, nome: str, dimensione: int = 18) -> None:
    """Applica un'icona a un widget e ne registra nome e dimensione."""
    widget.setProperty("lucide_nome", nome)
    widget.setProperty("lucide_dimensione", int(dimensione))
    widget.setIcon(carica_icona(nome))
    widget.setIconSize(QSize(int(dimensione), int(dimensione)))


def applica_icona_etichetta(etichetta, nome: str, dimensione: int = 36) -> None:
    """Applica una Lucide a una QLabel e la registra per il cambio tema."""
    etichetta.setProperty("lucide_pixmap_nome", str(nome))
    etichetta.setProperty("lucide_pixmap_dimensione", int(dimensione))
    etichetta.setPixmap(
        carica_icona(str(nome)).pixmap(
            QSize(int(dimensione), int(dimensione))
        )
    )


def applica_icona_finestra(finestra, nome: str) -> None:
    """Applica e registra l'icona tematica di una finestra."""
    finestra.setProperty("lucide_finestra_nome", str(nome))
    finestra.setWindowIcon(carica_icona(str(nome)))


def applica_icona_applicazione_finestra(finestra) -> None:
    """Usa nella barra del titolo l'icona neutra dell'applicazione."""
    finestra.setProperty("usa_icona_applicazione", True)
    applicazione = QApplication.instance()
    if applicazione is None:
        return

    icona_applicazione = applicazione.windowIcon()
    if not icona_applicazione.isNull():
        finestra.setWindowIcon(icona_applicazione)


def applica_icona_popup(popup, nome: str, dimensione: int = 48) -> None:
    """Mostra e registra l'unica icona semantica del corpo di un popup."""
    popup.setProperty("lucide_popup_nome", str(nome))
    popup.setProperty("lucide_popup_dimensione", int(dimensione))
    popup.setIcon(QMessageBox.NoIcon)
    popup.setIconPixmap(
        carica_icona(str(nome)).pixmap(
            QSize(int(dimensione), int(dimensione))
        )
    )


def crea_popup_semantico(
    parent,
    titolo: str,
    messaggio: str,
    icona: str,
    *,
    testo_informativo: str = "",
    testo_dettagliato: str = "",
    dimensione: int = 48,
    messaggio_in_grassetto: bool = False,
) -> QMessageBox:
    """Crea un QMessageBox coerente con il protocollo visivo dell'app.

    La barra usa l'icona neutra; il corpo una sola icona semantica. Il chiamante
    aggiunge i pulsanti per conservarne ruoli e ordine Qt.
    """
    popup = QMessageBox(parent)
    # I popup operativi usano il dialogo Qt non nativo per evitare i suoni
    # di sistema di Windows. Il crash handler resta volutamente separato e sonoro.
    popup.setOption(
        QMessageBox.Option.DontUseNativeDialog,
        True,
    )
    popup.setWindowTitle(titolo)
    applica_icona_applicazione_finestra(popup)
    applica_icona_popup(popup, icona, dimensione)
    if messaggio_in_grassetto:
        # L’HTML è costruito soltanto dopo avere neutralizzato il testo utente.
        testo_sicuro = escape(str(messaggio)).replace("\n", "<br>")
        popup.setTextFormat(Qt.AutoText)
        popup.setText(f"<b>{testo_sicuro}</b>")
    else:
        popup.setText(messaggio)

    if testo_informativo:
        testo_info_sicuro = escape(str(testo_informativo)).replace(
            "\n", "<br>"
        )
        popup.setInformativeText(f"<span>{testo_info_sicuro}</span>")
    if testo_dettagliato:
        popup.setDetailedText(testo_dettagliato)
    return popup


def mostra_dettagli_testuali_verticali(
    parent,
    titolo: str,
    testo: str,
    *,
    larghezza_ideale: int = 720,
    altezza_ideale: int = 520,
) -> int:
    """Mostra testo lungo in un dialogo a larghezza fissa e altezza variabile."""
    dialogo = QDialog(parent)
    dialogo.setWindowTitle(titolo)
    applica_icona_applicazione_finestra(dialogo)

    schermo = dialogo.screen()
    if schermo is not None:
        disponibile = schermo.availableGeometry()
        larghezza = min(
            int(larghezza_ideale),
            max(520, int(disponibile.width() * 0.72)),
        )
        altezza = min(
            int(altezza_ideale),
            max(320, int(disponibile.height() * 0.72)),
        )
    else:
        larghezza = int(larghezza_ideale)
        altezza = int(altezza_ideale)

    # La larghezza non cambia; il bordo della finestra resta ridimensionabile
    # soltanto in verticale. Il testo va a capo e non crea una barra orizzontale.
    dialogo.setMinimumWidth(larghezza)
    dialogo.setMaximumWidth(larghezza)
    dialogo.setMinimumHeight(min(300, altezza))
    dialogo.resize(larghezza, altezza)

    layout = QVBoxLayout(dialogo)
    layout.setSpacing(10)

    intestazione = QHBoxLayout()
    icona = QLabel()
    applica_icona_etichetta(icona, "file-text", 32)
    intestazione.addWidget(icona, 0, Qt.AlignTop)

    etichetta = QLabel("Dettagli diagnostici")
    etichetta.setStyleSheet("font-size: 14px; font-weight: bold;")
    intestazione.addWidget(etichetta, 1)
    layout.addLayout(intestazione)

    area = QTextEdit()
    area.setReadOnly(True)
    area.setPlainText(str(testo))
    area.setLineWrapMode(QTextEdit.WidgetWidth)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    layout.addWidget(area, 1)

    riga_pulsanti = QHBoxLayout()
    riga_pulsanti.addStretch()
    btn_chiudi = QPushButton("Chiudi")
    applica_icona(btn_chiudi, "x", 18)
    btn_chiudi.setMinimumHeight(40)
    btn_chiudi.clicked.connect(dialogo.accept)
    riga_pulsanti.addWidget(btn_chiudi)
    layout.addLayout(riga_pulsanti)

    return dialogo.exec()


def mostra_popup_con_dettagli_persistente(
    parent,
    titolo: str,
    testo_html: str,
    icona: str,
    titolo_dettagli: str,
    testo_dettagli: str,
    *,
    larghezza_ideale: int = 720,
) -> int:
    """Mostra un avviso che resta aperto mentre si consultano i dettagli.

    Il dialogo principale non viene chiuso dal pulsante dei dettagli: apre un
    secondo dialogo modale figlio e torna visibile/attivo appena questo viene
    chiuso. In questo modo consigli e cause sintetiche restano sempre il punto
    di ritorno.
    """
    dialogo = QDialog(parent)
    dialogo.setModal(True)
    dialogo.setWindowTitle(titolo)
    applica_icona_applicazione_finestra(dialogo)

    schermo = dialogo.screen()
    if schermo is not None:
        disponibile = schermo.availableGeometry()
        larghezza = min(
            int(larghezza_ideale),
            max(540, int(disponibile.width() * 0.72)),
        )
    else:
        larghezza = int(larghezza_ideale)

    dialogo.setMinimumWidth(larghezza)
    dialogo.setMaximumWidth(larghezza)

    layout = QVBoxLayout(dialogo)
    layout.setSpacing(14)

    riga_contenuto = QHBoxLayout()
    riga_contenuto.setSpacing(14)

    etichetta_icona = QLabel()
    applica_icona_etichetta(etichetta_icona, icona, 48)
    riga_contenuto.addWidget(etichetta_icona, 0, Qt.AlignTop)

    etichetta_testo = QLabel()
    etichetta_testo.setTextFormat(Qt.RichText)
    etichetta_testo.setWordWrap(True)
    etichetta_testo.setTextInteractionFlags(Qt.TextSelectableByMouse)
    etichetta_testo.setText(str(testo_html))
    riga_contenuto.addWidget(etichetta_testo, 1)

    layout.addLayout(riga_contenuto)

    riga_pulsanti = QHBoxLayout()
    btn_dettagli = QPushButton("Mostra dettagli...")
    applica_icona(btn_dettagli, "file-text", 18)
    btn_dettagli.setMinimumHeight(40)

    btn_ok = QPushButton("OK")
    applica_icona(btn_ok, "check", 18)
    btn_ok.setMinimumHeight(40)
    btn_ok.setDefault(True)

    def apri_dettagli() -> None:
        mostra_dettagli_testuali_verticali(
            dialogo,
            titolo_dettagli,
            testo_dettagli,
        )
        # Il dialogo principale non è mai stato chiuso: dopo il figlio modale
        # torna semplicemente in primo piano con i consigli ancora visibili.
        dialogo.raise_()
        dialogo.activateWindow()
        btn_dettagli.setFocus()

    btn_dettagli.clicked.connect(apri_dettagli)
    btn_ok.clicked.connect(dialogo.accept)

    riga_pulsanti.addWidget(btn_dettagli)
    riga_pulsanti.addStretch()
    riga_pulsanti.addWidget(btn_ok)
    layout.addLayout(riga_pulsanti)

    return dialogo.exec()


def applica_stile_pulsante_popup(pulsante, ruolo: str) -> None:
    """Applica lo stile semantico previsto per un pulsante distruttivo."""
    if ruolo != "distruttivo":
        return

    pulsante.setProperty("popup_ruolo", ruolo)
    pulsante.setStyleSheet(
        f"""
        QPushButton {{
            background-color: {C('popup_btn_distruttivo_bg')};
            color: {C('popup_btn_distruttivo_txt')};
            border: 1px solid {C('popup_btn_distruttivo_bordo')};
            border-radius: 6px;
            padding: 8px 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {C('popup_btn_distruttivo_hover')};
            border-color: {C('popup_btn_distruttivo_bordo')};
        }}
        QPushButton:pressed {{
            background-color: {C('popup_btn_distruttivo_hover')};
        }}
        """
    )


def mostra_popup_semantico(
    parent,
    titolo: str,
    messaggio: str,
    icona: str,
    *,
    testo_informativo: str = "",
    testo_dettagliato: str = "",
    dimensione: int = 48,
    messaggio_in_grassetto: bool = False,
) -> int:
    """Mostra un popup semantico con il solo pulsante standard OK."""
    popup = crea_popup_semantico(
        parent,
        titolo,
        messaggio,
        icona,
        testo_informativo=testo_informativo,
        testo_dettagliato=testo_dettagliato,
        dimensione=dimensione,
        messaggio_in_grassetto=messaggio_in_grassetto,
    )
    popup.addButton(QMessageBox.Ok)
    return popup.exec()


def applica_icona_tab(tab_widget, indice: int, nome: str,
                       dimensione: int = 20) -> None:
    """Applica un'icona a una linguetta e la registra per il cambio tema."""
    mappa = getattr(tab_widget, "_lucide_icone_tab", {})
    mappa[int(indice)] = str(nome)
    tab_widget._lucide_icone_tab = mappa
    tab_widget._lucide_dimensione_tab = int(dimensione)
    tab_widget.setIconSize(QSize(int(dimensione), int(dimensione)))
    tab_widget.setTabIcon(int(indice), carica_icona(str(nome)))


def aggiorna_icone_tab(tab_widget) -> None:
    """Ricarica le icone registrate nelle linguette di un QTabWidget."""
    dimensione = int(
        getattr(tab_widget, "_lucide_dimensione_tab", 20)
    )
    tab_widget.setIconSize(QSize(dimensione, dimensione))

    for indice, nome in getattr(
        tab_widget, "_lucide_icone_tab", {}
    ).items():
        tab_widget.setTabIcon(
            int(indice), carica_icona(str(nome))
        )


def aggiorna_icone_widget(radice) -> None:
    """Ricarica le icone registrate sotto un widget radice.

    La scansione considera soltanto QWidget e tollera gli oggetti Qt distrutti
    mentre una finestra viene chiusa.
    """
    # Un wrapper Python può sopravvivere per poco al corrispondente oggetto C++.
    try:
        oggetti = [radice, *radice.findChildren(QWidget)]
    except RuntimeError:
        return

    for oggetto in oggetti:
        try:
            if (
                oggetto.property("usa_icona_applicazione")
                and hasattr(oggetto, "setWindowIcon")
            ):
                applicazione = QApplication.instance()
                if applicazione is not None:
                    icona_applicazione = applicazione.windowIcon()
                    if not icona_applicazione.isNull():
                        oggetto.setWindowIcon(icona_applicazione)

            nome_finestra = oggetto.property("lucide_finestra_nome")
            if nome_finestra and hasattr(oggetto, "setWindowIcon"):
                oggetto.setWindowIcon(carica_icona(str(nome_finestra)))

            nome_popup = oggetto.property("lucide_popup_nome")
            if nome_popup and hasattr(oggetto, "setIconPixmap"):
                dimensione_popup = (
                    oggetto.property("lucide_popup_dimensione") or 48
                )
                oggetto.setIcon(QMessageBox.NoIcon)
                oggetto.setIconPixmap(
                    carica_icona(str(nome_popup)).pixmap(
                        QSize(int(dimensione_popup), int(dimensione_popup))
                    )
                )

            nome_pixmap = oggetto.property("lucide_pixmap_nome")
            if nome_pixmap and hasattr(oggetto, "setPixmap"):
                dimensione_pixmap = (
                    oggetto.property("lucide_pixmap_dimensione") or 36
                )
                oggetto.setPixmap(
                    carica_icona(str(nome_pixmap)).pixmap(
                        QSize(int(dimensione_pixmap), int(dimensione_pixmap))
                    )
                )

            if getattr(oggetto, "_lucide_icone_tab", None):
                aggiorna_icone_tab(oggetto)

            nome = oggetto.property("lucide_nome")
            if not nome or not hasattr(oggetto, "setIcon"):
                continue

            dimensione = oggetto.property("lucide_dimensione") or 18
            oggetto.setIcon(carica_icona(str(nome)))

            if hasattr(oggetto, "setIconSize"):
                oggetto.setIconSize(
                    QSize(int(dimensione), int(dimensione))
                )

        except RuntimeError:
            continue


def aggiorna_icone_applicazione() -> None:
    """Ricarica le icone registrate in tutte le finestre Qt aperte."""
    applicazione = QApplication.instance()
    if applicazione is None:
        return

    for finestra in applicazione.topLevelWidgets():
        aggiorna_icone_widget(finestra)


# File e apertura con le applicazioni di sistema
def pulisci_nome_file(nome: str) -> str:
    """Restituisce un nome file valido sui principali sistemi operativi.

    Sostituisce i caratteri vietati, normalizza spazi e separatori e protegge
    i nomi di dispositivo riservati da Windows (``CON``, ``PRN``, ``COM1``…).
    """
    caratteri_vietati = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    nomi_riservati_windows = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{numero}' for numero in range(1, 10)),
        *(f'LPT{numero}' for numero in range(1, 10)),
    }

    nome_pulito = str(nome)
    for char in caratteri_vietati:
        nome_pulito = nome_pulito.replace(char, '-')

    while '  ' in nome_pulito:
        nome_pulito = nome_pulito.replace('  ', ' ')

    nome_pulito = nome_pulito.replace(' ', '_')

    while '__' in nome_pulito:
        nome_pulito = nome_pulito.replace('__', '_')
    while '--' in nome_pulito:
        nome_pulito = nome_pulito.replace('--', '-')

    # Windows elimina implicitamente punti e spazi finali: rimuoverli qui evita
    # nomi ambigui o non creabili quando l'export viene eseguito su quel sistema.
    nome_pulito = nome_pulito.strip('_-').rstrip(' .')

    if not nome_pulito:
        return 'file'

    # I nomi di dispositivo restano riservati anche quando hanno un'estensione
    # (per esempio ``CON.txt``). Inseriamo un suffisso prima del primo punto,
    # preservando l'eventuale estensione proposta dal chiamante.
    radice, separatore, resto = nome_pulito.partition('.')
    if radice.upper() in nomi_riservati_windows:
        radice = f'{radice}_file'
        nome_pulito = radice + (separatore + resto if separatore else '')

    return nome_pulito


def apri_file_con_applicazione_default(file_path: str) -> bool:
    """Apre un file o una cartella con l'applicazione predefinita del sistema."""

    try:
        percorso = os.path.abspath(os.fspath(file_path))

        if not os.path.exists(percorso):
            return False

        url = QUrl.fromLocalFile(percorso)
        return bool(QDesktopServices.openUrl(url))

    except Exception:
        return False


def mostra_popup_file_salvato(parent, titolo: str, messaggio: str, file_path: str) -> None:
    """Mostra la conferma di salvataggio con un'azione per aprire il file."""
    msg_box = crea_popup_semantico(
        parent,
        titolo,
        messaggio,
        "circle-check",
        testo_informativo=f"Percorso:\n{file_path}",
        messaggio_in_grassetto=True,
    )

    btn_apri = msg_box.addButton("Apri", QMessageBox.ActionRole)
    applica_icona(btn_apri, "folder-open", 18)
    msg_box.addButton(QMessageBox.Ok)

    msg_box.exec()

    if msg_box.clickedButton() == btn_apri:
        if not apri_file_con_applicazione_default(file_path):
            mostra_popup_semantico(
                parent,
                "Apertura non riuscita",
                "Impossibile aprire il file automaticamente.",
                "circle-x",
                testo_informativo=(
                    "Aprilo manualmente dal percorso mostrato nel popup precedente."
                ),
                messaggio_in_grassetto=True,
            )


def abbrevia_nome_assegnazione(nome_completo: str) -> str:
    """Abbrevia il nome di un'assegnazione per gli spazi compatti dell'interfaccia.

    Rimuove l'eventuale prefisso della classe, applica abbreviazioni note e tronca
    a trenta caratteri.
    """
    nome = nome_completo
    if " - " in nome:
        nome = nome.split(" - ", 1)[1]

    abbreviazioni = {
        "Prima assegnazione": "Prima ass.",
        "Rotazione": "Rot.",
        "mensile": "mens.",
        "numero": "n.",
        "dell'anno": "",
        "scolastico": "scol."
    }

    for originale, abbreviato in abbreviazioni.items():
        nome = nome.replace(originale, abbreviato)

    if len(nome) > 30:
        nome = nome[:27] + "..."

    return nome.strip()


# Controlli Qt condivisi
def crea_bottone(testo: str, colore_bg: str, colore_hover: str, tooltip: str = "", altezza_min: int | None = None,
                 colore_disabled_bg: str | None = None, colore_disabled_txt: str | None = None,
                 font_size: int = 13, border_radius: int = 6, padding: str = "10px 20px",
                 colore_testo: str = "#ffffff", colore_bordo: str | None = None,
                 colore_disabled_bordo: str | None = None) -> QPushButton:
    """Crea un QPushButton rettangolare con stile uniforme.

    Colori, bordo, dimensioni e stato disabilitato sono configurabili. I controlli
    con geometrie speciali restano definiti localmente nei moduli che li usano.
    """
    btn = QPushButton(testo)

    if altezza_min is not None:
        btn.setMinimumHeight(altezza_min)

    # Un bordo esplicito mantiene leggibili anche i fondi chiari.
    bordo = colore_bordo or colore_bg
    bordo_disabled = colore_disabled_bordo or colore_disabled_bg
    stile = f"""
        QPushButton {{
            background-color: {colore_bg};
            color: {colore_testo};
            border: 1px solid {bordo};
            font-size: {font_size}px;
            font-weight: bold;
            border-radius: {border_radius}px;
            padding: {padding};
        }}
        QPushButton:hover {{
            background-color: {colore_hover};
            border-color: {bordo};
        }}"""

    if colore_disabled_bg and colore_disabled_txt:
        stile += f"""
        QPushButton:disabled {{
            background-color: {colore_disabled_bg};
            color: {colore_disabled_txt};
            border-color: {bordo_disabled};
        }}"""

    btn.setStyleSheet(stile)

    if tooltip:
        btn.setToolTip(tooltip)

    return btn


class FiltroCursoreManina(QObject):
    """Imposta il cursore a manina sui pulsanti abilitati.

    Il filtro non intercetta gli eventi: restituisce sempre ``False``.
    """
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter and isinstance(obj, QPushButton):
            if obj.isEnabled():
                obj.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                obj.setCursor(Qt.CursorShape.ArrowCursor)
        return False
