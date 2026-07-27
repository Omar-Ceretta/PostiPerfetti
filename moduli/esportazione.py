# -*- coding: utf-8 -*-
"""
esportazione.py — report testuali ed esportazione Excel.

Fornisce ``EsportazioneMixin`` e gli helper condivisi che trasformano una
assegnazione in report leggibili, aggiornano la scheda Report ed esportano la
piantina in TXT o XLSX. Le modalità a coppie e a terzetti condividono giudizi,
note, statistiche e disegno testuale dell'aula.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta.
Licenza: GNU GPLv3. Distribuito senza garanzie.
"""

from datetime import datetime

from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

from moduli.utilita import (
    pulisci_nome_file, mostra_popup_file_salvato,
    PATTERN_EVIDENZIAZIONE_REPORT, giudizio_da_note,
    conta_riutilizzate_con_foto,
)
from moduli.statistiche_generali import (
    costruisci_statistiche_generali_coppie,
    costruisci_statistiche_generali_terzetti,
    render_statistiche_testo,
    applica_formattazione_statistiche_generali,
    icona_giudizio_criticita,
    icona_nota_incompatibilita,
    etichetta_visibile_giudizio,
)
from moduli.tema import C
from moduli.metrica_pulizia import (
    adiacenze_in_fila, TIPO_COPPIA, TIPO_TERZETTO, TIPO_QUARTETTO,
)
from moduli.strato_storico import trova_quando_coppia_usata

# Le rotazioni restano separate: il precedente nell’altro modo è solo informativo.
NOTA_PRECEDENTE_PREFISSO = "ℹ️ Già stati vicini in modalità"
PREFISSO_ASSEGNAZIONE_REPORT = "Assegnazione: "


def sostituisci_nome_assegnazione_report(testo: str, nuovo_nome: str) -> str:
    """Aggiorna il nome dell'assegnazione nella testata del report."""
    righe = testo.splitlines()
    for indice, riga in enumerate(righe):
        if riga.startswith(PREFISSO_ASSEGNAZIONE_REPORT):
            righe[indice] = f"{PREFISSO_ASSEGNAZIONE_REPORT}{nuovo_nome}"
            break
    return "\n".join(righe)


def nota_precedente_altro_modo(s1, s2, config_app, modo_corrente):
    """Restituisce la nota informativa su precedenti vicinanze nell'altro modo.

    Le rotazioni delle due modalità restano indipendenti: la nota non modifica
    punteggi, blacklist o contatori.
    """
    if config_app is None:
        return None

    altro_modo = 'terzetti' if modo_corrente == 'coppie' else 'coppie'
    cognomi = {s1.get_nome_completo(), s2.get_nome_completo()}
    quando = trova_quando_coppia_usata(cognomi, config_app, altro_modo)
    if quando is None:
        return None

    # Conserva “ultima volta”; rimuove soltanto il prefisso della rotazione.
    riferimento = quando.replace("usata in: ", "", 1)
    return f"{NOTA_PRECEDENTE_PREFISSO} {altro_modo} ({riferimento})"

def inserisci_riepilogo_precedenti_altro_modo(report, riga_ancora_prefisso,
                                              modo_corrente):
    """Inserisce nel riepilogo il numero di note riferite all'altro modo.

    Conta le righe effettivamente emesse nel dettaglio e restituisce lo stesso
    numero usato dai popup. Se non trova precedenti, non aggiunge alcuna riga.
    """
    conta = sum(1 for r in report if NOTA_PRECEDENTE_PREFISSO in r)
    if conta == 0:
        return 0

    altro_modo = 'terzetti' if modo_corrente == 'coppie' else 'coppie'
    for indice, riga in enumerate(report):
        if riga.startswith(riga_ancora_prefisso):
            report.insert(
                indice + 1,
                f"- ℹ️ Vicinanze con precedenti in modalità {altro_modo}: {conta} "
                f"(solo informativo: le rotazioni dei modi sono indipendenti)"
            )
            break

    return conta

def evidenzia_riutilizzi(text_edit):
    """Evidenzia in ocra le note di dettaglio relative ai riutilizzi.

    Le statistiche generali ricevono invece la formattazione dal renderer
    strutturato.
    """
    formato_ocra = QTextCharFormat()
    formato_ocra.setForeground(QColor(C("testo_ocra")))
    formato_ocra.setFontWeight(QFont.Bold)

    for pattern in PATTERN_EVIDENZIAZIONE_REPORT:
        cursore = text_edit.textCursor()
        cursore.movePosition(QTextCursor.Start)
        text_edit.setTextCursor(cursore)

        while True:
            cursore = text_edit.document().find(pattern, cursore)
            if cursore.isNull():
                break
            cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
            cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            cursore.setCharFormat(formato_ocra)

    cursore_iniziale = text_edit.textCursor()
    cursore_iniziale.movePosition(QTextCursor.Start)
    text_edit.setTextCursor(cursore_iniziale)

class EsportazioneMixin:
    """Aggiunge report ed esportazioni alla finestra principale.

    Il mixin usa gli studenti e l'ultima assegnazione della finestra, il
    ``QTextEdit`` del report e la configurazione persistente.
    """

    def _estrai_nome_completo_da_id(self, id_univoco: str) -> str:
        """Converte ``Cognome_Nome`` in ``Cognome Nome``.

        Gli identificatori già separati da spazi vengono restituiti invariati.
        """
        if '_' in id_univoco:
            cognome, nome = id_univoco.split('_', 1)
            return f"{cognome} {nome}"
        else:
            return id_univoco

    def _verifica_prima_fila_note(self, s1, s2, configurazione_aula):
        """Verifica sulla griglia reale le richieste di prima fila della coppia."""
        righe = []
        riga_prima = None
        for r, riga in enumerate(configurazione_aula.griglia):
            if any(p.tipo == 'banco' for p in riga):
                riga_prima = r
                break

        for s in (s1, s2):
            if s.nota_posizione != 'PRIMA':
                continue
            identificatore = f"{s.cognome}_{s.nome}"
            riga_attuale = None
            for r, riga in enumerate(configurazione_aula.griglia):
                for p in riga:
                    if p.tipo == 'banco' and p.occupato_da == identificatore:
                        riga_attuale = r
                        break
                if riga_attuale is not None:
                    break
            if riga_attuale == riga_prima:
                righe.append(f"🪑 PRIMA FILA richiesta: {s.get_nome_completo()}")
            else:
                righe.append(f"‼️ NON in PRIMA FILA come richiesto: {s.get_nome_completo()}")
        return righe

    def _verifica_ultima_fila_note(self, s1, s2, configurazione_aula):
        """Verifica le richieste di ultima fila rispetto all'ultima fila occupata."""
        righe = []
        riga_ultima = None
        for r in range(len(configurazione_aula.griglia) - 1, -1, -1):
            riga = configurazione_aula.griglia[r]
            if any(p.tipo == 'banco' and p.occupato_da for p in riga):
                riga_ultima = r
                break

        for s in (s1, s2):
            if s.nota_posizione != 'ULTIMA':
                continue
            identificatore = f"{s.cognome}_{s.nome}"
            riga_attuale = None
            for r, riga in enumerate(configurazione_aula.griglia):
                for p in riga:
                    if p.tipo == 'banco' and p.occupato_da == identificatore:
                        riga_attuale = r
                        break
                if riga_attuale is not None:
                    break
            if riga_attuale is not None and riga_attuale == riga_ultima:
                righe.append(f"🪑 ULTIMA FILA richiesta: {s.get_nome_completo()}")
            else:
                righe.append(f"❗ NON in ULTIMA FILA come richiesto: {s.get_nome_completo()}")
        return righe

    def _righe_layout_aula_testuale(self, configurazione_aula):
        """Restituisce il layout testuale delle sole file di banchi.

        La griglia è letta direttamente, quindi lo stesso disegno funziona per
        coppie, terzetti, quartetti e blocchi finali.
        """
        righe = []

        # Il fondo dell’aula viene stampato in alto; la prima fila resta in basso.
        griglia_invertita = list(reversed(configurazione_aula.griglia))
        num_file_banchi = sum(1 for riga in griglia_invertita
                             if any(p.tipo == 'banco' for p in riga))
        contatore_fila = num_file_banchi

        for riga in griglia_invertita:
            ha_banchi = any(p.tipo == 'banco' for p in riga)

            if ha_banchi:
                riga_str = f"Fila {contatore_fila:2d}: "
                contatore_fila -= 1
            else:
                continue

            for posto in riga:
                if posto.occupato_da:
                    nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                    riga_str += f"[{nome_completo}] "
                elif posto.tipo == 'banco':
                    riga_str += " 🪑 "
                elif posto.tipo == 'cattedra':
                    riga_str += " 🏫 "
                elif posto.tipo == 'lim':
                    riga_str += " 📺 "
                elif posto.tipo == 'lavagna':
                    riga_str += " ⬛ "
                else:
                    riga_str += "   "

            righe.append(riga_str)

        return righe

    def _righe_note_coppia(self, s1, s2, note_filtrate, configurazione_aula,
                           modo='coppie'):
        """Compone le note visibili di una vicinanza.

        Sostituisce le richieste generiche di posizione con verifiche sulla
        griglia e aggiunge l'eventuale precedente informativo nell'altro modo.
        Le righe restituite non includono il bullet del chiamante.
        """
        out = []
        for nota in note_filtrate:
            if nota.startswith("PRIMA FILA richiesta:"):
                righe_prima = self._verifica_prima_fila_note(
                    s1, s2, configurazione_aula)
                out.extend(righe_prima if righe_prima else [nota])
            else:
                out.append(nota)
        out.extend(self._verifica_ultima_fila_note(s1, s2, configurazione_aula))

        # La nota non contiene le parole chiave usate per contare i riutilizzi.
        nota_cross = nota_precedente_altro_modo(s1, s2, self.config_app, modo)
        if nota_cross:
            out.append(nota_cross)

        return out

    def _trova_quando_vicino_fisso(self, nome_vicino, config_app):
        """Cerca quando uno studente è già stato vicino diretto del FISSO.

        La relazione è letta dal campo ``adiacente`` dell'elemento ``fisso``
        nello Storico, non dalle coppie ordinarie.
        """
        storico = config_app.config_data.get("storico_assegnazioni", [])
        assegnazioni_trovate = []

        for assegnazione in reversed(storico):
            nome_assegnazione = assegnazione.get("nome", "Assegnazione senza nome")
            layout = assegnazione.get("layout", [])
            for studente_info in layout:
                if studente_info.get("tipo") == "fisso":
                    if studente_info.get("adiacente", "") == nome_vicino:
                        assegnazioni_trovate.append(nome_assegnazione)
                    break

        if assegnazioni_trovate:
            if len(assegnazioni_trovate) == 1:
                return f"in: {assegnazioni_trovate[0]}"
            else:
                return f"ultima volta: {assegnazioni_trovate[0]}"

        return None

    def _giudizio_da_note(self, risultato):
        """Delega al metro condiviso il giudizio ricavato dalle note."""
        return giudizio_da_note(risultato.get('note', []))

    def _etichetta_valutazione(self, risultato):
        """Restituisce il giudizio mostrato nel report.

        I giudizi ordinari derivano dalle note; ``VIETATA`` conserva il valore
        interno perché rappresenta un vincolo assoluto.
        """
        valutazione = risultato.get('valutazione', '')

        # I vincoli assoluti non vengono reinterpretati dal metro descrittivo.
        if valutazione not in ('VIETATA',):
            giudizio = self._giudizio_da_note(risultato)
            icona = icona_giudizio_criticita(giudizio)
            etichetta = etichetta_visibile_giudizio(giudizio)
            return f"{icona} {etichetta}" if icona else etichetta

        return valutazione

    def _filtra_note_report(self, note):
        """Ripulisce le note per la sola visualizzazione nel report.

        Elimina diagnostica e penalità numeriche note, conserva ogni testo non
        riconosciuto e applica le icone condivise a riusi, incompatibilità,
        affinità e coppie miste. Non modifica dati o punteggi del motore.
        """
        note_pulite = []
        for nota in note:
            if nota.startswith("Valutazione TENTATIVO "):
                continue
            if (
                nota.startswith("Penalità blacklist T4")
                or nota.strip().lstrip("• ")
                == "Riutilizzo ammesso per completare l’assegnazione."
            ):
                # Il ricorso al quarto tentativo è un dettaglio interno e compare
                # soltanto in alcuni percorsi del motore. Il riutilizzo resta già
                # segnalato in modo uniforme da testo, icona e colore; esporre anche
                # questa nota intermittente renderebbe il report meno chiaro. La
                # seconda condizione elimina anche eventuali note già trasformate
                # prima di raggiungere questo filtro.
                continue
            if nota.startswith("Penalità blacklist:"):
                continue
            if nota.startswith("COPPIA BLACKLISTATA"):
                continue

            if nota.startswith("Entrambi preferiscono ultima fila"):
                continue

            if nota.startswith("Conflitto di fila"):
                continue

            if "Coppia già usata" in nota and "(penalità:" in nota:
                inizio = nota.find("(penalità:")
                fine = nota.find(")", inizio)
                if inizio != -1 and fine != -1:
                    nota_senza_penalita = nota[:inizio] + nota[fine + 1:]
                    nota_senza_penalita = nota_senza_penalita.replace("  ", " ").strip()
                    note_pulite.append(f"⚠️ {nota_senza_penalita}")
                    continue

            if nota.startswith("Coppia già usata"):
                note_pulite.append(f"⚠️ {nota}")
                continue

            icona_incompatibilita = icona_nota_incompatibilita(nota)
            if icona_incompatibilita:
                note_pulite.append(f"{icona_incompatibilita} {nota}")
                continue

            if nota.startswith("Affinità di livello"):
                note_pulite.append(f"❤️ {nota}")
                continue

            if nota.startswith("Coppia mista"):
                note_pulite.append(f"👫 {nota}")
                continue

            note_pulite.append(nota)

        return note_pulite

    def costruisci_testo_report_terzetti(self, gruppi, motore,
                                         nome_classe=None, studenti=None,
                                         ultimo_uso_vicinanze=None,
                                         metadati_casualita=None,
                                         nome_assegnazione=None,
                                         data_creazione=None):
        """Costruisce il report della modalità a terzetti senza usare widget.

        Ogni gruppo è descritto attraverso le adiacenze consecutive reali. Le
        stesse funzioni del modo a coppie producono giudizi, note, verifiche di
        posizione e informazioni cross-modo. Restituisce il testo completo e
        il numero di vicinanze riutilizzate.
        """
        nome_classe = nome_classe if nome_classe is not None else self.input_nome_classe.text()
        studenti = studenti if studenti is not None else self.studenti
        data_creazione = (
            data_creazione
            if data_creazione is not None
            else datetime.now().strftime('%d/%m/%Y %H:%M')
        )
        nome_assegnazione = nome_assegnazione or nome_classe

        def _con_ultimo_uso(note, s1, s2):
            if not ultimo_uso_vicinanze:
                return note
            chiave = tuple(sorted([s1.get_nome_completo(), s2.get_nome_completo()]))
            etichetta = ultimo_uso_vicinanze.get(chiave)
            if not etichetta:
                return note
            return [f"{n} (ultimo uso: {etichetta})" if "Coppia già usata" in n else n
                    for n in note]

        # Il riuso del vicino diretto ha un’etichetta distinta dalle altre adiacenze.
        vicini_fisso_riutilizzati = []

        # La rinomina avviene dopo il filtraggio della nota canonica di riuso.
        def _marca_vicino_fisso(riga, s1, s2):
            if studente_fisso is None:
                return riga
            n1, n2 = s1.get_nome_completo(), s2.get_nome_completo()
            if n1 == nome_fisso:
                nome_vicino = n2
            elif n2 == nome_fisso:
                nome_vicino = n1
            else:
                return riga
            if "Coppia già usata" not in riga:
                return riga
            if nome_vicino not in vicini_fisso_riutilizzati:
                vicini_fisso_riutilizzati.append(nome_vicino)
            return riga.replace("Coppia già usata", "Vicino del FISSO già usato")

        etichette_tipo = {
            TIPO_TERZETTO:  'terzetto',
            TIPO_QUARTETTO: 'quartetto',
            TIPO_COPPIA:    'coppia',
        }

        studente_fisso = next((s for s in studenti if s.nota_posizione == 'FISSO'), None)
        nome_fisso = studente_fisso.get_nome_completo() if studente_fisso else None

        report = []

        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("=" * 60)
        report.append(f"Classe: {nome_classe}")
        report.append(f"Data creazione: {data_creazione}")
        report.append(f"Studenti elaborati: {len(studenti)}")
        riga_identificativa = (
            f"{PREFISSO_ASSEGNAZIONE_REPORT}{nome_assegnazione}"
        )
        report.append(riga_identificativa)
        self._riga_identificativa_report = riga_identificativa
        report.append("")

        righe_statistiche, dati_statistiche = \
            costruisci_statistiche_generali_terzetti(gruppi, motore)
        riutilizzi_totali = dati_statistiche["riutilizzi"]
        self._statistiche_generali_terzetti_correnti = righe_statistiche

        righe_dettaglio = []
        for idx, g in enumerate(gruppi, start=1):
            # Un membro centrale può produrre la stessa verifica di fila due volte.
            note_posizione_viste = set()
            tipo_umano = etichette_tipo.get(g.tipo, g.tipo)
            nomi_membri = []
            for s in g.membri:
                nome = s.get_nome_completo()
                nomi_membri.append(f"📌 {nome}" if nome == nome_fisso else nome)
            righe_dettaglio.append(f"Banco {idx} ({tipo_umano}): {' — '.join(nomi_membri)}")

            for a, b in adiacenze_in_fila(g.membri):
                ris = motore.calcola_punteggio_coppia(a, b)
                righe_dettaglio.append(
                    f"   Vicinanza {a.get_nome_completo()} + {b.get_nome_completo()}:"
                )
                _et = self._etichetta_valutazione(ris)
                if _et:
                    righe_dettaglio.append(f"      {_et}")
                _note = _con_ultimo_uso(self._filtra_note_report(ris['note']), a, b)
                for riga_nota in self._righe_note_coppia(
                        a, b,
                        _note,
                        self.configurazione_aula,
                        modo='terzetti'):
                    if ("FILA richiesta" in riga_nota
                            or "FILA come richiesto" in riga_nota):
                        if riga_nota in note_posizione_viste:
                            continue
                        note_posizione_viste.add(riga_nota)
                    righe_dettaglio.append(
                        f"      • {_marca_vicino_fisso(riga_nota, a, b)}")
            righe_dettaglio.append("")

        report.append("📈 STATISTICHE GENERALI")
        report.append("-" * 30)
        report.extend(render_statistiche_testo(righe_statistiche))
        report.append("")

        if studente_fisso is not None:
            report.append("📌 POSIZIONE FISSA")
            report.append("-" * 30)
            report.append(f"📌 {nome_fisso} (POSIZIONE FISSA)")
            report.append("   Posizione: primo banco a sinistra, prima fila")
            gruppo_fisso = next(
                (g for g in gruppi
                 if any(s.get_nome_completo() == nome_fisso for s in g.membri)),
                None
            )
            if gruppo_fisso is not None:
                compagni = [s.get_nome_completo() for s in gruppo_fisso.membri
                            if s.get_nome_completo() != nome_fisso]
                if compagni:
                    report.append(f"   Compagni di banco: {', '.join(compagni)}")
            report.append("")

        report.append("📋 DETTAGLIO BANCO PER BANCO")
        report.append("-" * 30)
        report.extend(righe_dettaglio)

        report.append("🏫 LAYOUT AULA")
        report.append("-" * 30)
        report.extend(self._righe_layout_aula_testuale(self.configurazione_aula))

        # Il riepilogo conta le note realmente emesse nel dettaglio.
        self._precedenti_altro_modo = inserisci_riepilogo_precedenti_altro_modo(
            report, "- Vicinanze riutilizzate:", modo_corrente='terzetti')

        return "\n".join(report), riutilizzi_totali

    def costruisci_testo_report(self, assegnatore, nome_classe=None, studenti=None,
                                ultimo_uso_coppie=None, ultimo_uso_vicino=None,
                                coppie_gia_usate_esplicite=None,
                                vicini_fisso_espliciti=None,
                                nome_assegnazione=None,
                                data_creazione=None):
        """Costruisce il report del modo a coppie senza modificare i widget.

        Nel flusso mensile legge lo stato corrente del motore. Nell'Annuale
        riordinato, le fotografie esplicite di coppie e vicini già usati
        sostituiscono le note congelate nell'ordine originario. Restituisce il
        testo, la riga identificativa provvisoria e il totale dei riutilizzi.
        """
        nome_classe = nome_classe if nome_classe is not None else self.input_nome_classe.text()
        studenti = studenti if studenti is not None else self.studenti
        data_creazione = (
            data_creazione
            if data_creazione is not None
            else datetime.now().strftime('%d/%m/%Y %H:%M')
        )
        nome_assegnazione = nome_assegnazione or nome_classe

        def _normalizza_ultimo_uso_storico(riferimento):
            """Uniforma il riferimento storico nella forma ``ultimo uso: X``."""
            if not riferimento:
                return None

            for prefisso in ("usata in: ", "ultima volta: ", "in: "):
                if riferimento.startswith(prefisso):
                    return f"ultimo uso: {riferimento[len(prefisso):]}"

            return riferimento

        def _con_ultimo_uso(note, s1, s2):
            """Completa una nota di riuso con il riferimento più recente.

            Nell'Annuale preferisce il mese precedente nel nuovo ordine; in
            mancanza di esso consulta lo Storico reale.
            """
            if coppie_gia_usate_esplicite is None:
                return note

            if not any("Coppia già usata" in n for n in note):
                return note

            nome_1 = s1.get_nome_completo()
            nome_2 = s2.get_nome_completo()
            chiave = tuple(sorted([nome_1, nome_2]))

            etichetta = (
                ultimo_uso_coppie.get(chiave)
                if ultimo_uso_coppie
                else None
            )

            if etichetta:
                riferimento = f"ultimo uso: {etichetta}"

            else:
                config_reale = getattr(self, "config_app", None)
                riferimento = None

                if config_reale is not None:
                    riferimento = trova_quando_coppia_usata(
                        {nome_1, nome_2},
                        config_reale,
                        modo="coppie",
                    )
                    riferimento = _normalizza_ultimo_uso_storico(
                        riferimento
                    )

            if not riferimento:
                return note

            return [
                f"{n} ({riferimento})"
                if "Coppia già usata" in n
                else n
                for n in note
            ]

        def _note_riuso_da_foto(note, s1, s2):
            if coppie_gia_usate_esplicite is None:
                return note
            note = [n for n in note if "Coppia già usata" not in n]
            chiave = tuple(sorted([s1.get_nome_completo(), s2.get_nome_completo()]))
            if chiave in coppie_gia_usate_esplicite:
                note = note + ["⚠️ Coppia già usata"]
            return note

        report = []

        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("=" * 60)
        report.append(f"Classe: {nome_classe}")
        report.append(f"Data creazione: {data_creazione}")
        report.append(f"Studenti elaborati: {len(studenti)}")
        riga_identificativa = (
            f"{PREFISSO_ASSEGNAZIONE_REPORT}{nome_assegnazione}"
        )
        report.append(riga_identificativa)

        report.append("")

        # Nell’Annuale riordinato la fotografia esplicita è la fonte del riuso.
        if coppie_gia_usate_esplicite is not None:
            riut = conta_riutilizzate_con_foto(
                assegnatore, coppie_gia_usate_esplicite, vicini_fisso_espliciti)
        else:
            from moduli.utilita import conta_riutilizzate
            riut = conta_riutilizzate(assegnatore)

        riutilizzate_totali = riut['totali']
        righe_statistiche = costruisci_statistiche_generali_coppie(
            assegnatore, riutilizzi=riut)
        assegnatore.statistiche_generali = righe_statistiche

        report.append("📈 STATISTICHE GENERALI")
        report.append("-" * 30)
        report.extend(render_statistiche_testo(righe_statistiche))
        report.append("")

        if hasattr(assegnatore, 'studente_fisso') and assegnatore.studente_fisso:
            report.append("📌 POSIZIONE FISSA")
            report.append("-" * 30)
            report.append(f"📌 {assegnatore.studente_fisso.get_nome_completo()} (POSIZIONE FISSA)")
            report.append(f"   Posizione: primo banco a sinistra, prima fila")

            banchi_prima_fila = assegnatore.configurazione_aula.get_banchi_per_fila()
            if banchi_prima_fila and banchi_prima_fila[0]:
                adiacenti = []
                colonna_attesa = 1
                for banco in banchi_prima_fila[0]:
                    if banco.colonna == colonna_attesa and banco.occupato_da:
                        nome = self._estrai_nome_completo_da_id(banco.occupato_da)
                        adiacenti.append(nome)
                        colonna_attesa += 1
                    elif banco.colonna > colonna_attesa:
                        break

                if adiacenti:
                    report.append(f"   Adiacente diretto: {adiacenti[0]}")
                    for nome in adiacenti[1:]:
                        report.append(f"   Compagno blocco: {nome}")

                    gruppo = getattr(
                        assegnatore,
                        'gruppo_adiacente_fisso',
                        None
                    )
                    fisso = assegnatore.studente_fisso
                    motore = assegnatore.motore_vincoli

                    # Le verifiche di fila appartengono allo studente, non all’adiacenza.
                    note_posizione_viste_fisso = set()

                    vicino_diretto = None
                    secondo_coppia = None
                    if gruppo and len(gruppo) >= 2:
                        vicino_diretto, secondo_coppia = gruppo[0], gruppo[1]
                    elif getattr(assegnatore, 'trio_identificato', None):
                        for s in assegnatore.trio_identificato:
                            if s.get_nome_completo() == adiacenti[0]:
                                vicino_diretto = s
                                break

                    if vicino_diretto is not None:
                        ris_f = motore.calcola_punteggio_coppia(fisso, vicino_diretto)
                        report.append(f"   Adiacenza {fisso.get_nome_completo()} + "
                                      f"{vicino_diretto.get_nome_completo()}:")
                        _et = self._etichetta_valutazione(ris_f)
                        if _et:
                            report.append(f"      {_et}")
                        for riga_nota in self._righe_note_coppia(
                                fisso,
                                vicino_diretto,
                                self._filtra_note_report(ris_f['note']),
                                assegnatore.configurazione_aula):

                            if (
                                "FILA richiesta" in riga_nota
                                or "FILA come richiesto" in riga_nota
                            ):
                                if (
                                    riga_nota
                                    in note_posizione_viste_fisso
                                ):
                                    continue
                                note_posizione_viste_fisso.add(
                                    riga_nota
                                )

                            report.append(f"      • {riga_nota}")

                        if vicini_fisso_espliciti is not None:
                            nome_vicino = vicino_diretto.get_nome_completo()
                            if nome_vicino in vicini_fisso_espliciti:
                                if ultimo_uso_vicino and nome_vicino in ultimo_uso_vicino:
                                    quando = (
                                        f"ultimo uso: "
                                        f"{ultimo_uso_vicino[nome_vicino]}"
                                    )

                                else:
                                    config_reale = getattr(
                                        self,
                                        "config_app",
                                        None,
                                    )
                                    quando = None

                                    if config_reale is not None:
                                        quando = (
                                            self._trova_quando_vicino_fisso(
                                                nome_vicino,
                                                config_reale,
                                            )
                                        )
                                        quando = (
                                            _normalizza_ultimo_uso_storico(
                                                quando
                                            )
                                        )
                                if quando:
                                    report.append(
                                        f"      • ⚠️ Vicino del FISSO già usato ({quando})")
                                else:
                                    report.append(
                                        "      • ⚠️ Vicino del FISSO già usato")
                        else:
                            config_app = getattr(assegnatore, 'config_app', None)
                            if config_app is not None:
                                contatore_vicino = config_app.config_data.get(
                                    "studenti_vicino_fisso_contatore", {})
                                nome_vicino = vicino_diretto.get_nome_completo()
                                volte_vicino = contatore_vicino.get(nome_vicino, 0)
                                if volte_vicino >= 1:
                                    etichetta = "volta" if volte_vicino == 1 else "volte"
                                    if ultimo_uso_vicino and nome_vicino in ultimo_uso_vicino:
                                        quando = f"ultimo uso: {ultimo_uso_vicino[nome_vicino]}"
                                    else:
                                        quando = self._trova_quando_vicino_fisso(
                                            nome_vicino, config_app)
                                    if quando:
                                        report.append(
                                            f"      • ⚠️ Vicino del FISSO già usato "
                                            f"{volte_vicino} {etichetta} ({quando})")
                                    else:
                                        report.append(
                                            f"      • ⚠️ Vicino del FISSO già usato "
                                            f"{volte_vicino} {etichetta}")

                        if secondo_coppia is not None:
                            ris_c = motore.calcola_punteggio_coppia(vicino_diretto, secondo_coppia)
                            report.append(f"   Coppia adiacente {vicino_diretto.get_nome_completo()} + "
                                          f"{secondo_coppia.get_nome_completo()}:")
                            _et = self._etichetta_valutazione(ris_c)
                            if _et:
                                report.append(f"      {_et}")
                            for riga_nota in self._righe_note_coppia(
                                    vicino_diretto,
                                    secondo_coppia,
                                    _con_ultimo_uso(
                                        _note_riuso_da_foto(
                                            self._filtra_note_report(
                                                ris_c['note']
                                            ),
                                            vicino_diretto,
                                            secondo_coppia
                                        ),
                                        vicino_diretto,
                                        secondo_coppia
                                    ),
                                    assegnatore.configurazione_aula):

                                if (
                                    "FILA richiesta" in riga_nota
                                    or "FILA come richiesto" in riga_nota
                                ):
                                    if (
                                        riga_nota
                                        in note_posizione_viste_fisso
                                    ):
                                        continue
                                    note_posizione_viste_fisso.add(
                                        riga_nota
                                    )

                                report.append(f"      • {riga_nota}")

            report.append("")

        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            report.append("👥 TRIO FORMATO")
            report.append("-" * 30)

            trio = assegnatore.trio_identificato

            nomi_trio = [s.get_nome_completo() for s in trio]
            report.append(f"Trio: {' + '.join(nomi_trio)}")

            # Nel trio contano soltanto le adiacenze consecutive.
            coppie_adiacenti = [(trio[0], trio[1]), (trio[1], trio[2])]
            # Un membro centrale può produrre la stessa verifica di fila due volte.
            note_posizione_viste = set()
            for i, (s1, s2) in enumerate(coppie_adiacenti, 1):
                risultato = assegnatore.motore_vincoli.calcola_punteggio_coppia(s1, s2)
                report.append(f"  Coppia adiacente {i}: {s1.get_nome_completo()} + {s2.get_nome_completo()}")
                _et = self._etichetta_valutazione(risultato)
                if _et:
                    report.append(f"    {_et}")

                note_da_mostrare = _con_ultimo_uso(
                    _note_riuso_da_foto(
                        self._filtra_note_report(risultato['note']), s1, s2),
                    s1, s2)
                for riga_nota in self._righe_note_coppia(
                        s1, s2, note_da_mostrare, assegnatore.configurazione_aula):
                    if ("FILA richiesta" in riga_nota
                            or "FILA come richiesto" in riga_nota):
                        if riga_nota in note_posizione_viste:
                            continue
                        note_posizione_viste.add(riga_nota)
                    report.append(f"    • {riga_nota}")

            report.append("")

        report.append("👥 COPPIE FORMATE")
        report.append("-" * 30)

        for idx, (studente1, studente2, info) in enumerate(assegnatore.coppie_formate, 1):
            report.append(f"{idx:2d}. {studente1.get_nome_completo()} + {studente2.get_nome_completo()}")
            _et = self._etichetta_valutazione(info)
            if _et:
                report.append(f"    {_et}")

            note_da_mostrare = _con_ultimo_uso(
                _note_riuso_da_foto(
                    self._filtra_note_report(info['note']), studente1, studente2),
                studente1, studente2)
            for riga_nota in self._righe_note_coppia(
                    studente1, studente2, note_da_mostrare,
                    assegnatore.configurazione_aula):
                report.append(f"    • {riga_nota}")

            report.append("")

        report.append("🏫 LAYOUT AULA")
        report.append("-" * 30)
        report.extend(self._righe_layout_aula_testuale(
            assegnatore.configurazione_aula))

        # Il riepilogo conta le note realmente emesse nel dettaglio.
        self._precedenti_altro_modo = inserisci_riepilogo_precedenti_altro_modo(
            report, "- Vicinanze riutilizzate:", modo_corrente='coppie')

        return "\n".join(report), riga_identificativa, riutilizzate_totali

    def _aggiorna_report_testuale(
            self, assegnatore, nome_assegnazione=None, data_creazione=None):
        """Costruisce il report, lo mostra nel widget e applica gli stili."""
        testo, riga_identificativa, _riutilizzate_totali = \
            self.costruisci_testo_report(
                assegnatore,
                nome_assegnazione=nome_assegnazione,
                data_creazione=data_creazione,
            )

        self._riga_identificativa_report = riga_identificativa

        self.text_report.setPlainText(testo)

        evidenzia_riutilizzi(self.text_report)
        applica_formattazione_statistiche_generali(
            self.text_report, getattr(assegnatore, 'statistiche_generali', []))

    def _aggiorna_riga_identificativa_report(self, nome_assegnazione: str):
        """Aggiorna il campo Assegnazione nella testata del report corrente."""
        testo = sostituisci_nome_assegnazione_report(
            self.text_report.toPlainText(),
            nome_assegnazione,
        )
        self.text_report.setPlainText(testo)
        evidenzia_riutilizzi(self.text_report)
        if getattr(self, "modo_ultima_assegnazione", None) == "terzetti":
            righe = getattr(
                self, "_statistiche_generali_terzetti_correnti", []
            )
        else:
            assegnatore = getattr(self, "ultimo_assegnatore", None)
            righe = getattr(assegnatore, "statistiche_generali", [])
        applica_formattazione_statistiche_generali(self.text_report, righe)
        self._riga_identificativa_report = (
            f"{PREFISSO_ASSEGNAZIONE_REPORT}{nome_assegnazione}"
        )

    def esporta_excel(self):
        """Esporta la piantina corrente in formato XLSX.

        Per i terzetti usa la fotografia dell'aula salvata con l'ultima
        assegnazione; per le coppie usa l'ultimo assegnatore.
        """
        if self.modo_ultima_assegnazione == 'terzetti':
            if not self.dati_ultima_assegnazione_terzetti:
                self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
                return
        elif not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        ultima = storico[-1] if storico else {}
        nome_base = (
            getattr(self, "nome_assegnazione_corrente", None)
            or ultima.get("nome", self.input_nome_classe.text())
        )

        nome_pulito = pulisci_nome_file(nome_base)
        nome_suggerito = f"{nome_pulito}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva file Excel",
            nome_suggerito,
            "File Excel (*.xlsx);;Tutti i file (*)"
        )

        if file_path:
            try:
                if self.modo_ultima_assegnazione == 'terzetti':
                    class _SorgenteAulaTerzetti:
                        """Espone a ``crea_file_excel`` la sola configurazione dell'aula."""
                        pass
                    sorgente = _SorgenteAulaTerzetti()
                    sorgente.configurazione_aula = \
                        self.dati_ultima_assegnazione_terzetti['configurazione_aula']
                else:
                    sorgente = self.ultimo_assegnatore

                self.crea_file_excel(
                    file_path,
                    sorgente,
                    nome_assegnazione=nome_base,
                )

                mostra_popup_file_salvato(self, "Export completato", "File Excel salvato con successo!", file_path)

            except Exception as e:
                self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    def esporta_report_txt(self):
        """Salva su file il report testuale dell'ultima assegnazione."""
        if self.modo_ultima_assegnazione == 'terzetti':
            if not self.dati_ultima_assegnazione_terzetti:
                self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
                return
        elif not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        try:
            storico = self.config_app.config_data.get("storico_assegnazioni", [])
            ultima = storico[-1] if storico else {}
            nome_assegnazione = (
                getattr(self, "nome_assegnazione_corrente", None)
                or ultima.get("nome", "Report")
            )
            nome_suggerito = f"{pulisci_nome_file(nome_assegnazione)}.txt"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva Report assegnazione (.txt)",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                report_completo = self.text_report.toPlainText()

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_completo)

                mostra_popup_file_salvato(self, "Export completato", "Report testuale salvato con successo!", file_path)

        except Exception as e:
            self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    def crea_file_excel(self, file_path: str, assegnatore,
                        nome_assegnazione=None):
        """Crea il foglio XLSX con la piantina dell'aula.

        Usa XlsxWriter perché produce bordi e riempimenti correttamente visibili
        nelle versioni di Excel supportate. ``nome_assegnazione`` è il titolo
        modificabile conservato nello Storico e usato anche come nome del file.
        """
        if nome_assegnazione is None:
            nome_assegnazione = getattr(
                self, "nome_assegnazione_corrente", self.input_nome_classe.text()
            )
        # Import locale: la dipendenza serve soltanto durante la creazione XLSX.
        import xlsxwriter

        wb = xlsxwriter.Workbook(file_path)
        ws = wb.add_worksheet("PostiPerfetti")

        fmt_titolo = wb.add_format({"bold": True, "font_size": 16})

        fmt_banco_occupato = wb.add_format({
            "bold": True,
            "font_size": 9,
            "bg_color": "#C8E6C9",
            "border": 2,
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
        })

        fmt_banco_libero = wb.add_format({
            "bg_color": "#F5F5F5",
            "border": 2,
            "align": "center",
            "valign": "vcenter",
        })

        fmt_lim = wb.add_format({
            "bold": True,
            "bg_color": "#BBDEFB",
            "align": "center",
            "valign": "vcenter",
        })
        fmt_cattedra = wb.add_format({
            "bold": True,
            "bg_color": "#FFE0B2",
            "align": "center",
            "valign": "vcenter",
        })
        fmt_lavagna = wb.add_format({
            "bold": True,
            "bg_color": "#D7CCC8",
            "align": "center",
            "valign": "vcenter",
        })

        mappa_arredi = {
            "lim": (fmt_lim, "LIM"),
            "cattedra": (fmt_cattedra, "CATTEDRA"),
            "lavagna": (fmt_lavagna, "LAVAGNA"),
        }

        ws.write(1, 1, nome_assegnazione, fmt_titolo)

        configurazione = assegnatore.configurazione_aula

        griglia_invertita = list(reversed(configurazione.griglia))

        righe_con_contenuto = [
            riga for riga in griglia_invertita
            if any(p.tipo != 'corridoio' for p in riga)
        ]

        colonne_con_contenuto = set()
        riga_excel_arredi = None

        excel_row = 3

        for riga in righe_con_contenuto:
            ws.set_row(excel_row, 35)

            for col_idx, posto in enumerate(riga):
                excel_col = col_idx + 1

                if posto.tipo == 'banco':
                    if posto.occupato_da:
                        nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                        ws.write(excel_row, excel_col, nome_completo, fmt_banco_occupato)
                    else:
                        ws.write(excel_row, excel_col, "🪑", fmt_banco_libero)

                    colonne_con_contenuto.add(excel_col)

                elif posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    # Ogni arredo occupa due celle: il merge parte solo dalla prima.
                    is_prima_cella = (cella_precedente is None or cella_precedente.tipo != posto.tipo)

                    if is_prima_cella:
                        fmt_arredo, etichetta = mappa_arredi[posto.tipo]
                        ws.merge_range(
                            excel_row, excel_col,
                            excel_row, excel_col + 1,
                            etichetta, fmt_arredo
                        )

                    riga_excel_arredi = excel_row
                    colonne_con_contenuto.add(excel_col)

            excel_row += 2

        ws.set_column(0, 0, 2)

        if colonne_con_contenuto:
            max_col = max(colonne_con_contenuto)
            for col_num in range(1, max_col + 2):
                if col_num in colonne_con_contenuto:
                    ws.set_column(col_num, col_num, 18)
                else:
                    ws.set_column(col_num, col_num, 3)

        ws.set_landscape()
        ws.set_paper(9)

        ws.fit_to_pages(1, 1)

        ws.set_margins(left=0.4, right=0.4, top=0.4, bottom=0.4)
        ws.set_header("", {"margin": 0.2})
        ws.set_footer("", {"margin": 0.2})

        wb.close()
