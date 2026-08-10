# -*- coding: utf-8 -*-
"""Formato, validazione e persistenza dei file-classe di PostiPerfetti.

Il modulo è indipendente da PySide6. Riconosce i formati BASE e COMPLETO,
normalizza soltanto dati inequivocabili, analizza la bidirezionalità dei
vincoli, serializza il formato canonico e salva mediante sostituzione atomica.

Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from moduli.studenti import chiave_identita_studente
from moduli.lingua import quantita


FORMATO_BASE = "BASE"
FORMATO_COMPLETO = "COMPLETO"
PLACEHOLDER_GENERE = "---"
POSIZIONI_VALIDE = ("NORMALE", "PRIMA", "ULTIMA", "FISSO")


@dataclass(frozen=True)
class RigaFileClasse:
    """Conserva testo e numero fisico della riga nel file sorgente."""

    numero: int
    testo: str


class FileClasseVuoto(ValueError):
    """Segnala un file senza righe dati utilizzabili."""


class ErroreCodificaFileClasse(ValueError):
    """Segnala una codifica non supportata o caratteri di controllo sospetti."""


class ErroreValidazioneFileClasse(ValueError):
    """Raccoglie gli errori che impediscono di caricare un file classe."""

    def __init__(self, errori: Iterable[str], *, formato: str | None = None):
        self.errori = list(errori)
        self.formato = formato
        super().__init__("\n".join(self.errori))


def normalizza_spazi(valore) -> str:
    """Uniforma gli spazi esterni e interni di un valore."""
    return " ".join(str(valore).strip().split())


def chiave_nome_completo(nome_completo) -> str:
    """Restituisce la chiave normalizzata di un nome completo."""
    return normalizza_spazi(nome_completo).casefold()


def estrai_righe_utili(righe: Iterable[str]) -> list[RigaFileClasse]:
    """Filtra vuoti e commenti preservando il numero fisico originale."""
    risultato = []
    for numero_fisico, riga in enumerate(righe, start=1):
        riga_pulita = str(riga).strip()
        if not riga_pulita or riga_pulita.startswith("#"):
            continue
        risultato.append(RigaFileClasse(numero_fisico, riga_pulita))
    return risultato


@dataclass(frozen=True)
class _LetturaFileClasse:
    """Testo letto dal disco con informazioni sulla codifica riconosciuta."""

    righe: list[str]
    codifica: str
    legacy: bool
    conversione_utf8: bool = False
    testo: str = ""


_BOM_CONVERTIBILI = (
    (b"\xff\xfe\x00\x00", "UTF-32", "utf-32"),
    (b"\x00\x00\xfe\xff", "UTF-32", "utf-32"),
    (b"\xff\xfe", "UTF-16", "utf-16"),
    (b"\xfe\xff", "UTF-16", "utf-16"),
)


def _valida_caratteri_testo(testo: str) -> None:
    """Rifiuta controlli invisibili che possono indicare una codifica errata."""
    riga = 1
    colonna = 0
    for carattere in testo:
        if carattere == "\n":
            riga += 1
            colonna = 0
            continue
        colonna += 1
        codice = ord(carattere)
        if carattere in ("\t", "\r"):
            continue
        if codice < 32 or 0x7F <= codice <= 0x9F:
            suggerimento = (
                " Il file potrebbe essere stato salvato in UTF-16."
                if codice == 0
                else ""
            )
            raise ErroreCodificaFileClasse(
                f"Carattere di controllo U+{codice:04X} alla riga {riga}, "
                f"colonna {colonna}.{suggerimento} Salva il file come UTF-8 "
                "e selezionalo di nuovo."
            )


def _leggi_file_classe_con_codifica(percorso) -> _LetturaFileClasse:
    """Legge UTF-8 oppure, in compatibilità, una codifica occidentale legacy.

    Windows-1252 è preferita a Latin-1 perché interpreta correttamente la
    punteggiatura tipica dei file creati su Windows. La codifica legacy resta
    necessariamente ambigua: il chiamante deve quindi chiedere conferma prima
    di sostituire la classe già aperta.
    """
    percorso = os.fspath(percorso)
    with open(percorso, "rb") as file:
        dati = file.read()

    for bom, nome_codifica, decoder in _BOM_CONVERTIBILI:
        if dati.startswith(bom):
            try:
                testo = dati.decode(decoder)
            except UnicodeDecodeError as errore:
                raise ErroreCodificaFileClasse(
                    f"Il file dichiara la codifica {nome_codifica}, ma contiene "
                    "una sequenza di byte non valida. Aprilo con un editor di "
                    "testo, scegli «Salva con nome» e seleziona UTF-8, quindi "
                    "carica il nuovo file."
                ) from errore

            _valida_caratteri_testo(testo)
            return _LetturaFileClasse(
                righe=testo.splitlines(keepends=True),
                codifica=nome_codifica,
                legacy=False,
                conversione_utf8=True,
                testo=testo,
            )

    try:
        testo = dati.decode("utf-8-sig")
        codifica = "UTF-8"
        legacy = False
    except UnicodeDecodeError:
        try:
            testo = dati.decode("cp1252")
        except UnicodeDecodeError as errore_legacy:
            byte = dati[errore_legacy.start] if errore_legacy.start < len(dati) else None
            dettaglio = f" (byte 0x{byte:02X})" if byte is not None else ""
            raise ErroreCodificaFileClasse(
                "Il file non è UTF-8 e contiene una sequenza non valida anche "
                f"per la codifica occidentale Windows-1252{dettaglio}. "
                "Salvalo come UTF-8 e selezionalo di nuovo."
            ) from errore_legacy
        codifica = "Windows-1252/Latin-1 occidentale"
        legacy = True

    _valida_caratteri_testo(testo)
    return _LetturaFileClasse(
        righe=testo.splitlines(keepends=True),
        codifica=codifica,
        legacy=legacy,
        conversione_utf8=False,
        testo=testo,
    )


def _verifica_identita_uniche(studenti_minimi: Sequence[dict]) -> None:
    """Rifiuta identità vuote o duplicate dopo la normalizzazione degli spazi."""
    errori = []
    conteggi = {}
    nomi_visualizzati = {}

    for indice, dati in enumerate(studenti_minimi, start=1):
        cognome = normalizza_spazi(dati.get("cognome", ""))
        nome = normalizza_spazi(dati.get("nome", ""))
        numero_riga = int(dati.get("numero_riga", indice))

        if not cognome or not nome:
            errori.append(
                f"Riga {numero_riga}: cognome e nome devono essere entrambi presenti."
            )
            continue

        caratteri_riservati = sorted(
            {carattere for carattere in f"{cognome}{nome}" if carattere in ";,:"}
        )
        if "_" in cognome or "_" in nome or caratteri_riservati:
            elenco = ["underscore (_)"] if "_" in cognome or "_" in nome else []
            elenco.extend(f"{carattere!r}" for carattere in caratteri_riservati)
            errori.append(
                f"Riga {numero_riga}: cognome e nome contengono caratteri "
                f"riservati ({', '.join(elenco)}); usa lettere, spazi, apostrofi "
                "o trattini."
            )
            continue

        if cognome.startswith("#"):
            errori.append(
                f"Riga {numero_riga}: il cognome non può iniziare con '#', "
                "perché la riga verrebbe interpretata come commento."
            )
            continue

        chiave = chiave_identita_studente(cognome, nome)
        nome_visuale = f"{cognome} {nome}"
        nomi_visualizzati.setdefault(chiave, nome_visuale)
        conteggi[chiave] = conteggi.get(chiave, 0) + 1

    for chiave, occorrenze in sorted(conteggi.items()):
        if occorrenze > 1:
            errori.append(
                f"Lo studente '{nomi_visualizzati[chiave]}' compare "
                f"{occorrenze} volte."
            )

    if errori:
        raise ErroreValidazioneFileClasse(errori)


def analizza_coerenza_bidirezionale_dati(
    studenti_dati: Sequence[dict],
    completa_mancanti: bool = False,
) -> dict:
    """Rileva contraddizioni, livelli discordanti e vincoli non speculari.

    Con ``completa_mancanti=True`` aggiunge alle strutture ricevute soltanto le
    copie speculari inequivocabili; non corregge contraddizioni o livelli
    discordanti.
    """
    per_nome = {
        f"{dati['cognome']} {dati['nome']}": dati
        for dati in studenti_dati
    }

    contraddizioni = []
    discordanze_livello = []
    vincoli_aggiunti = []
    coppie_contraddittorie_viste = set()
    coppie_discordi_viste = set()

    for nome_sorgente, dati_sorgente in per_nome.items():
        for tipo, tipo_opposto, etichetta in (
            ("incompatibilita", "affinita", "INCOMPATIBILITÀ"),
            ("affinita", "incompatibilita", "AFFINITÀ"),
        ):
            for nome_target, livello in list(dati_sorgente[tipo].items()):
                dati_target = per_nome.get(nome_target)
                if dati_target is None:
                    # Il parser rigoroso impedisce questo caso nei file; la
                    # guardia mantiene la funzione sicura anche sui dati GUI.
                    continue

                coppia = tuple(sorted((nome_sorgente, nome_target)))

                if nome_sorgente in dati_target[tipo_opposto]:
                    if coppia not in coppie_contraddittorie_viste:
                        coppie_contraddittorie_viste.add(coppia)
                        livello_opposto = dati_target[tipo_opposto][nome_sorgente]
                        contraddizioni.append(
                            f"{nome_sorgente} → {nome_target}: {etichetta} "
                            f"livello {livello}; direzione opposta: "
                            f"{'AFFINITÀ' if tipo_opposto == 'affinita' else 'INCOMPATIBILITÀ'} "
                            f"livello {livello_opposto}."
                        )
                    continue

                if nome_sorgente in dati_target[tipo]:
                    livello_speculare = dati_target[tipo][nome_sorgente]
                    chiave_discordanza = (coppia, tipo)
                    if (
                        livello != livello_speculare
                        and chiave_discordanza not in coppie_discordi_viste
                    ):
                        coppie_discordi_viste.add(chiave_discordanza)
                        discordanze_livello.append(
                            f"{etichetta}: {nome_sorgente} → {nome_target} "
                            f"livello {livello}; {nome_target} → {nome_sorgente} "
                            f"livello {livello_speculare}."
                        )
                    continue

                if completa_mancanti:
                    dati_target[tipo][nome_sorgente] = livello
                    vincoli_aggiunti.append({
                        "tipo": tipo,
                        "sorgente": nome_sorgente,
                        "target": nome_target,
                        "livello": livello,
                    })

    return {
        "contraddizioni": contraddizioni,
        "discordanze_livello": discordanze_livello,
        "vincoli_aggiunti": vincoli_aggiunti,
    }


def nomi_studenti_fissi(studenti_dati: Sequence[dict]) -> list[str]:
    """Restituisce i nomi degli studenti marcati con posizione FISSO."""
    nomi = []
    for dati in studenti_dati:
        posizione = normalizza_spazi(dati.get("posizione", "")).upper()
        if posizione != "FISSO":
            continue
        cognome = normalizza_spazi(dati.get("cognome", ""))
        nome = normalizza_spazi(dati.get("nome", ""))
        nomi.append(f"{cognome} {nome}".strip())
    return nomi


def valida_dati_canonici_classe(studenti_dati: Sequence[dict]) -> None:
    """Verifica la struttura completa prima di serializzare o usare l'Editor.

    La funzione non corregge né completa nulla: i dati devono già essere nel
    formato canonico prodotto dall'Editor. In caso contrario raccoglie tutte le
    anomalie rilevabili e blocca l'operazione.
    """
    studenti = list(studenti_dati)
    if not studenti:
        raise ErroreValidazioneFileClasse(
            ["La classe deve contenere almeno uno studente."],
            formato=FORMATO_COMPLETO,
        )

    minimi = [
        {
            "numero_riga": indice,
            "cognome": dati.get("cognome", ""),
            "nome": dati.get("nome", ""),
        }
        for indice, dati in enumerate(studenti, start=1)
    ]
    _verifica_identita_uniche(minimi)

    nomi = [
        f"{normalizza_spazi(dati.get('cognome', ''))} "
        f"{normalizza_spazi(dati.get('nome', ''))}"
        for dati in studenti
    ]
    insieme_nomi = set(nomi)
    errori = []

    for indice, (nome_sorgente, dati) in enumerate(
        zip(nomi, studenti), start=1
    ):
        cognome_raw = str(dati.get("cognome", ""))
        nome_raw = str(dati.get("nome", ""))
        if cognome_raw != normalizza_spazi(cognome_raw) \
                or nome_raw != normalizza_spazi(nome_raw):
            errori.append(
                f"Studente {indice} — {nome_sorgente}: cognome e nome non "
                "sono nella forma canonica senza spazi superflui."
            )

        sesso_raw = str(dati.get("sesso", ""))
        sesso = normalizza_spazi(sesso_raw).upper()
        if sesso not in ("M", "F") or sesso_raw != sesso:
            errori.append(
                f"Studente {indice} — {nome_sorgente}: genere "
                f"'{sesso_raw or '<vuoto>'}' non canonico; usare esattamente M o F."
            )

        posizione_raw = str(dati.get("posizione", ""))
        posizione = normalizza_spazi(posizione_raw).upper()
        if posizione not in POSIZIONI_VALIDE or posizione_raw != posizione:
            errori.append(
                f"Studente {indice} — {nome_sorgente}: posizione "
                f"'{posizione_raw or '<vuoto>'}' non canonica; usare uno fra "
                + ", ".join(POSIZIONI_VALIDE)
                + "."
            )

        for tipo, etichetta in (
            ("incompatibilita", "incompatibilità"),
            ("affinita", "affinità"),
        ):
            vincoli = dati.get(tipo)
            if not isinstance(vincoli, dict):
                errori.append(
                    f"Studente {indice} — {nome_sorgente}: il campo "
                    f"{etichetta} non è una mappa valida."
                )
                continue

            for nome_target, livello in vincoli.items():
                if nome_target not in insieme_nomi:
                    errori.append(
                        f"Studente {indice} — {nome_sorgente}: il riferimento "
                        f"'{nome_target}' nelle {etichetta} non appartiene alla classe."
                    )
                elif nome_target == nome_sorgente:
                    errori.append(
                        f"Studente {indice} — {nome_sorgente}: non è ammesso un "
                        f"vincolo di {etichetta} verso se stesso."
                    )

                if isinstance(livello, bool) or not isinstance(livello, int)                         or livello not in (1, 2, 3):
                    errori.append(
                        f"Studente {indice} — {nome_sorgente}: livello "
                        f"{livello!r} non valido per il vincolo verso "
                        f"'{nome_target}'; usare 1, 2 o 3."
                    )

        incompatibilita = dati.get("incompatibilita", {})
        affinita = dati.get("affinita", {})
        if isinstance(incompatibilita, dict) and isinstance(affinita, dict):
            for nome_target in sorted(set(incompatibilita) & set(affinita)):
                errori.append(
                    f"Studente {indice} — {nome_sorgente}: '{nome_target}' compare "
                    "sia tra le incompatibilità sia tra le affinità."
                )

    fissi = nomi_studenti_fissi(studenti)
    if len(fissi) > 1:
        errori.append(
            "È ammesso un solo studente con posizione FISSO; trovati: "
            + ", ".join(fissi)
            + "."
        )

    if not errori:
        import copy

        fotografia = copy.deepcopy(studenti)
        coerenza = analizza_coerenza_bidirezionale_dati(
            fotografia,
            completa_mancanti=True,
        )
        errori.extend(coerenza["contraddizioni"])
        errori.extend(coerenza["discordanze_livello"])
        for vincolo in coerenza["vincoli_aggiunti"]:
            tipo = (
                "incompatibilità"
                if vincolo["tipo"] == "incompatibilita"
                else "affinità"
            )
            errori.append(
                f"Vincolo non bidirezionale: {vincolo['sorgente']} → "
                f"{vincolo['target']} ({tipo}, livello {vincolo['livello']})."
            )

    if errori:
        raise ErroreValidazioneFileClasse(errori, formato=FORMATO_COMPLETO)


def prepara_file_base(righe: Sequence[RigaFileClasse]) -> dict:
    """Valida e converte un file BASE con due o tre campi per riga."""
    studenti = []
    minimi = []
    errori = []

    for riga_sorgente in righe:
        numero_riga = riga_sorgente.numero
        parti = riga_sorgente.testo.split(";")
        if len(parti) not in (2, 3):
            numero_campi = len(parti)
            verbo = "è stato trovato" if numero_campi == 1 else "sono stati trovati"
            raise ErroreValidazioneFileClasse([
                f"Riga {numero_riga}: un file BASE deve avere 2 o 3 campi; "
                f"ne {verbo} {numero_campi}."
            ])

        cognome = normalizza_spazi(parti[0])
        nome = normalizza_spazi(parti[1])
        nome_completo = f"{cognome} {nome}"
        minimi.append({
            "numero_riga": numero_riga,
            "cognome": cognome,
            "nome": nome,
        })

        sesso = PLACEHOLDER_GENERE
        if len(parti) == 3:
            sesso_raw = parti[2].strip()
            if sesso_raw.upper() in ("M", "F"):
                sesso = sesso_raw.upper()
            elif sesso_raw:
                errori.append(
                    f"Riga {numero_riga} — {nome_completo}: genere "
                    f"'{sesso_raw}' non valido; usare M, F oppure lasciare vuoto."
                )

        studenti.append({
            "cognome": cognome,
            "nome": nome,
            "sesso": sesso,
            "posizione": "NORMALE",
            "incompatibilita": {},
            "affinita": {},
        })

    _verifica_identita_uniche(minimi)
    if errori:
        raise ErroreValidazioneFileClasse(errori)

    return {
        "studenti": studenti,
        "avvisi": [],
        "contraddizioni": [],
        "discordanze_livello": [],
        "vincoli_aggiunti": [],
    }


def prepara_file_completo(righe: Sequence[RigaFileClasse]) -> dict:
    """Valida le sei colonne di un file COMPLETO e prepara i dati per l’Editor."""
    errori = []
    avvisi = []
    righe_preparate = []

    for riga_sorgente in righe:
        numero_riga = riga_sorgente.numero
        parti = riga_sorgente.testo.split(";")

        if len(parti) != 6:
            numero_campi = len(parti)
            verbo = "trovato" if numero_campi == 1 else "trovati"
            errori.append(
                f"Riga {numero_riga}: {verbo} "
                f"{quantita(numero_campi, 'campo', 'campi')}; "
                "un file completo deve averne esattamente 6."
            )
            continue

        cognome = normalizza_spazi(parti[0])
        nome = normalizza_spazi(parti[1])
        righe_preparate.append({
            "numero_riga": numero_riga,
            "parti": parti,
            "cognome": cognome,
            "nome": nome,
            "nome_completo": f"{cognome} {nome}",
        })

    if errori:
        raise ErroreValidazioneFileClasse(errori)

    _verifica_identita_uniche(righe_preparate)

    nomi_canonici = {
        chiave_nome_completo(riga["nome_completo"]): riga["nome_completo"]
        for riga in righe_preparate
    }

    def parsing_vincoli_rigoroso(
        testo,
        tipo,
        nome_sorgente,
        numero_riga,
    ):
        risultato = {}
        testo = testo.strip()
        if not testo:
            return risultato

        for indice, elemento in enumerate(testo.split(","), start=1):
            elemento = elemento.strip()
            descrizione = f"riga {numero_riga}, {tipo}, elemento {indice}"

            if not elemento:
                errori.append(
                    f"{descrizione}: vincolo vuoto; controlla virgole doppie o finali."
                )
                continue

            if elemento.count(":") != 1:
                errori.append(
                    f"{descrizione}: '{elemento}' deve avere la sintassi "
                    "'Cognome Nome:livello'."
                )
                continue

            riferimento_raw, livello_raw = elemento.rsplit(":", 1)
            riferimento_raw = normalizza_spazi(riferimento_raw)
            livello_raw = livello_raw.strip()

            if not riferimento_raw or not livello_raw:
                errori.append(
                    f"{descrizione}: riferimento o livello mancante in '{elemento}'."
                )
                continue

            try:
                livello = int(livello_raw)
            except ValueError:
                errori.append(
                    f"{descrizione}: il livello '{livello_raw}' non è numerico."
                )
                continue

            if livello not in (1, 2, 3):
                errori.append(
                    f"{descrizione}: il livello {livello} è fuori dall'intervallo 1-3."
                )
                continue

            nome_target = nomi_canonici.get(chiave_nome_completo(riferimento_raw))
            if nome_target is None:
                errori.append(
                    f"{descrizione}: lo studente '{riferimento_raw}' non esiste nel file."
                )
                continue

            if nome_target == nome_sorgente:
                errori.append(
                    f"{descrizione}: uno studente non può avere un vincolo verso se stesso."
                )
                continue

            if nome_target in risultato:
                errori.append(
                    f"{descrizione}: '{nome_target}' è duplicato nello stesso campo."
                )
                continue

            risultato[nome_target] = livello

        return risultato

    studenti_dati = []
    for riga in righe_preparate:
        parti = riga["parti"]
        numero_riga = riga["numero_riga"]
        nome_completo = riga["nome_completo"]

        sesso_raw = parti[2].strip().upper()
        if not sesso_raw:
            sesso = PLACEHOLDER_GENERE
            avvisi.append(
                f"Riga {numero_riga} — {nome_completo}: genere mancante; "
                "nell'Editor resta il placeholder '---'."
            )
        elif sesso_raw in ("M", "F"):
            sesso = sesso_raw
        else:
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: genere "
                f"'{parti[2].strip()}' non valido; usare M, F oppure lasciare vuoto."
            )
            sesso = PLACEHOLDER_GENERE

        posizione = parti[3].strip().upper()
        if posizione not in POSIZIONI_VALIDE:
            valore = parti[3].strip() or "<vuoto>"
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: posizione '{valore}' "
                "non valida; usare NORMALE, PRIMA, ULTIMA o FISSO."
            )

        incompatibilita = parsing_vincoli_rigoroso(
            parti[4], "incompatibilità", nome_completo, numero_riga
        )
        affinita = parsing_vincoli_rigoroso(
            parti[5], "affinità", nome_completo, numero_riga
        )

        for nome_target in sorted(set(incompatibilita).intersection(affinita)):
            errori.append(
                f"Riga {numero_riga} — {nome_completo}: '{nome_target}' compare "
                "sia tra le incompatibilità sia tra le affinità."
            )

        studenti_dati.append({
            "cognome": riga["cognome"],
            "nome": riga["nome"],
            "sesso": sesso,
            "posizione": posizione,
            "incompatibilita": incompatibilita,
            "affinita": affinita,
        })

    if errori:
        raise ErroreValidazioneFileClasse(errori)

    coerenza = analizza_coerenza_bidirezionale_dati(
        studenti_dati,
        completa_mancanti=True,
    )

    return {
        "studenti": studenti_dati,
        "avvisi": avvisi,
        "contraddizioni": coerenza["contraddizioni"],
        "discordanze_livello": coerenza["discordanze_livello"],
        "vincoli_aggiunti": coerenza["vincoli_aggiunti"],
    }


def prepara_righe_file_classe(righe: Iterable[str]) -> dict:
    """Riconosce il formato e restituisce una struttura validata e transazionale."""
    righe_utili = estrai_righe_utili(righe)
    if not righe_utili:
        raise FileClasseVuoto("Il file non contiene righe utili.")

    numeri_campi = [len(riga.testo.split(";")) for riga in righe_utili]
    if any(numero >= 4 for numero in numeri_campi):
        formato = FORMATO_COMPLETO
        preparatore = prepara_file_completo
    else:
        formato = FORMATO_BASE
        preparatore = prepara_file_base

    try:
        risultato = preparatore(righe_utili)
    except ErroreValidazioneFileClasse as errore:
        errore.formato = formato
        raise

    return {
        "formato": formato,
        **risultato,
    }


def carica_file_classe(percorso) -> dict:
    """Legge, riconosce e valida un file senza modificare lo stato del chiamante."""
    lettura = _leggi_file_classe_con_codifica(percorso)
    risultato = prepara_righe_file_classe(lettura.righe)
    risultato["codifica_sorgente"] = lettura.codifica
    risultato["codifica_legacy"] = lettura.legacy
    risultato["conversione_utf8_disponibile"] = lettura.conversione_utf8
    risultato["avviso_codifica"] = (
        "Il file non è UTF-8 ed è stato interpretato come codifica occidentale "
        "Windows-1252/Latin-1. Controlla attentamente accenti, apostrofi e "
        "caratteri speciali prima di salvarlo: il prossimo salvataggio lo "
        "convertirà in UTF-8."
        if lettura.legacy
        else ""
    )
    return risultato


def crea_copia_utf8_file_classe(percorso) -> Path:
    """Crea accanto al sorgente una copia UTF-8 senza modificare l'originale.

    La conversione automatica è consentita soltanto quando il BOM identifica
    in modo inequivocabile UTF-16 o UTF-32. La copia usa un nome non esistente
    del tipo ``<nome>_UTF8.txt`` e conserva esattamente il testo decodificato,
    inclusi i terminatori di riga.
    """
    sorgente = Path(percorso)
    lettura = _leggi_file_classe_con_codifica(sorgente)
    if not lettura.conversione_utf8:
        raise ErroreCodificaFileClasse(
            "La conversione automatica è disponibile soltanto per file "
            "UTF-16 o UTF-32 riconosciuti con certezza."
        )

    suffisso = sorgente.suffix
    base = f"{sorgente.stem}_UTF8"
    indice = 1
    while True:
        nome = f"{base}{suffisso}" if indice == 1 else f"{base}_{indice}{suffisso}"
        destinazione = sorgente.with_name(nome)
        try:
            descrittore = os.open(
                destinazione,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            break
        except FileExistsError:
            indice += 1

    try:
        with os.fdopen(descrittore, "wb") as file:
            file.write(lettura.testo.encode("utf-8"))
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        try:
            os.close(descrittore)
        except OSError:
            pass
        try:
            destinazione.unlink()
        except FileNotFoundError:
            pass
        raise

    return destinazione


def serializza_file_classe(nome_classe: str, studenti_dati: Sequence[dict]) -> str:
    """Genera il contenuto canonico completo a sei campi."""
    valida_dati_canonici_classe(studenti_dati)
    linee = [
        f"# Classe: {nome_classe} ({quantita(len(studenti_dati), 'studente', 'studenti')})",
        "# Formato: Cognome;Nome;Genere;Posizione;Incompatibilità;Affinità",
        '# Genere: M/F (se il flag "Genere misto" è attivo, l\'abbinamento [maschio][femmina] riceve un BONUS forte, non obbligatorio)',
        "# Vincoli di posizione: NORMALE (= neutro) / PRIMA (= OBBLIGATORIO: prima fila) / ULTIMA (= preferenza per ultima fila) / FISSO (= OBBLIGATORIO: primo banco a sinistra della prima fila)",
        '# Vincoli di "Incompatibilità": Cognome Nome:livello (1-3, dove 1 = Leggera, 2 = Media, 3 = ASSOLUTA [= mai insieme])',
        '# Vincoli di "Affinità": Cognome Nome:livello (1-3, dove 1 = Leggera, 2 = Buona, 3 = Forte)',
        "",
    ]

    for dati in studenti_dati:
        incompatibilita = ",".join(
            f"{nome}:{livello}"
            for nome, livello in dati["incompatibilita"].items()
        )
        affinita = ",".join(
            f"{nome}:{livello}"
            for nome, livello in dati["affinita"].items()
        )
        linee.append(
            f"{dati['cognome']};{dati['nome']};{dati['sesso']};"
            f"{dati['posizione']};{incompatibilita};{affinita}"
        )

    return "\n".join(linee)


def scrivi_file_classe_atomico(percorso, contenuto: str) -> None:
    """Scrive il file nella stessa cartella e lo promuove con ``os.replace``.

    La destinazione precedente resta integra finché il temporaneo non è stato
    scritto e sincronizzato completamente. Il temporaneo viene sempre rimosso
    in caso di errore.
    """
    destinazione = Path(percorso)
    cartella = destinazione.parent
    if not cartella.is_dir():
        raise FileNotFoundError(f"La cartella di destinazione non esiste: {cartella}")

    modo_precedente = None
    if destinazione.exists():
        modo_precedente = stat.S_IMODE(destinazione.stat().st_mode)
        if modo_precedente & 0o222 == 0:
            raise PermissionError(f"Il file non è scrivibile: {destinazione}")

    descrittore, temporaneo = tempfile.mkstemp(
        prefix=f".{destinazione.name}.",
        suffix=".tmp",
        dir=cartella,
    )

    try:
        with os.fdopen(descrittore, "w", encoding="utf-8") as file:
            file.write(contenuto)
            file.flush()
            os.fsync(file.fileno())

        if modo_precedente is not None:
            os.chmod(temporaneo, modo_precedente)

        os.replace(temporaneo, destinazione)
    except Exception:
        try:
            os.close(descrittore)
        except OSError:
            pass
        try:
            os.remove(temporaneo)
        except FileNotFoundError:
            pass
        raise
