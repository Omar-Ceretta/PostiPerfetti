# -*- coding: utf-8 -*-
"""Anteprima e salvataggio delle assegnazioni annuali.

Il dialogo presenta i mesi generati, apre piantine e report e coordina
l'accettazione atomica o lo scarto dell'intera annata. La finestra principale
fornisce soltanto il contesto applicativo necessario ai report del Layout.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from copy import deepcopy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QGroupBox,
    QLabel, QFrame, QPushButton, QTextEdit, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from moduli.calcolo.annuale import formatta_durata
from moduli.dominio.fotografia_generazione_layout import (
    FotografiaGenerazioneLayout, fotografa_studenti,
)
from moduli.dominio.layout_unico import LayoutUnico
from moduli.dominio.editing_annuale import BozzaAnnuale
from moduli.lingua import forma_numerata
from moduli.dominio.riferimenti_riuso import ultimi_usi_nell_annata
from moduli.persistenza.risultati_annuali import descrivi_abbinamenti_personalizzata as _descrivi_abbinamenti_personalizzata, prepara_identita_annata, prepara_mesi_da_anteprima_annuale, salva_annata_personalizzata
from moduli.interfaccia.statistiche_generali import (
    costruisci_statistiche_generali_terzetti,
    applica_formattazione_statistiche_generali,
)
from moduli.interfaccia.tema import C
from moduli.interfaccia.utilita import (
    adatta_finestra_allo_schermo,
    applica_icona,
    applica_icona_etichetta,
    applica_icona_finestra,
    applica_stile_pulsante_popup,
    crea_popup_semantico,
    mostra_popup_semantico,
)
from moduli.dominio.vincoli import MotoreVincoliConfigurato
from moduli.interfaccia.esportazione import evidenzia_riutilizzi
from moduli.interfaccia.storico_ui import PopupLayoutStorico
from moduli.dominio.presentazione_aula_personalizzata import (
    costruisci_configurazione_aula_personalizzata,
)
from moduli.interfaccia.widget_statistiche import crea_widget_righe_statistiche

def _testo_assegnazioni_salvate(nomi) -> str:
    """Descrive il salvataggio senza duplicare nomi o accordi scorretti."""
    nomi = list(nomi)
    if not nomi:
        return "Nessuna assegnazione è stata aggiunta allo Storico.\n\n"
    if len(nomi) == 1:
        return f"L’assegnazione «{nomi[0]}» è stata aggiunta allo Storico.\n\n"
    return (
        f"Tutte le {len(nomi)} assegnazioni sono state aggiunte allo Storico\n"
        f"— da «{nomi[0]}» a «{nomi[-1]}».\n\n"
    )


class AnteprimaStagioneDialog(QDialog):
    """Mostra una stagione mese per mese e consente di accettarla o scartarla."""

    def __init__(
            self, parent, config_app, mesi, info, file_origine, nome_classe, *,
            genere_misto, studenti, studente_fisso=None, modo='personalizzata',
            schema_personalizzato=None, layout_visuale_personalizzato=None):
        """Inizializza l’anteprima con i mesi generati e i dati di riepilogo."""
        if modo != 'personalizzata':
            raise ValueError("L'anteprima annuale richiede il Layout unico.")
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.mesi = deepcopy(mesi or [])
        self.info = deepcopy(info or {})
        self.file_origine = file_origine
        self.nome_classe = nome_classe or "Classe"
        self._genere_misto = bool(genere_misto)
        self._studenti = deepcopy(list(studenti))
        self._studente_fisso = deepcopy(studente_fisso)

        self.modo = modo
        self._schema_personalizzato = schema_personalizzato
        self._layout_visuale_personalizzato = layout_visuale_personalizzato

        self.identita_annata = prepara_identita_annata(
            self.config_app,
            self.file_origine,
            self.nome_classe,
            self.modo,
            len(self.mesi),
        )
        self.generazione = self.identita_annata.generazione
        self.data_creazione = self.identita_annata.data_creazione
        self.nomi_assegnazioni = list(self.identita_annata.nomi)

        self._mesi_non_validi_struttura = 0
        if (
            self._schema_personalizzato is None
            or self._layout_visuale_personalizzato is None
        ):
            raise ValueError(
                "L'anteprima richiede schema e Layout visuale."
            )
        self._layout_visuale_personalizzato.valida_contro_schema(
            self._schema_personalizzato
        )
        self._fotografia_generazione = FotografiaGenerazioneLayout(
            LayoutUnico(self._schema_personalizzato, self._layout_visuale_personalizzato),
            fotografa_studenti(self._studenti), self.file_origine,
            self.nome_classe, self._genere_misto,
        )
        # La sorgente Q21 resta congelata; le proiezioni della bozza sono copie.
        self._mesi_q21 = deepcopy(self.mesi)
        self._bozza_annuale = None
        self._errore_editing = ''
        try:
            self._bozza_annuale = BozzaAnnuale.crea(
                self._fotografia_generazione, self._mesi_q21,
            )
        except (ValueError, TypeError) as errore:
            # La visualizzazione storica rimane disponibile. Non si attiva
            # l'editing su una sequenza non verificata dal dominio A1.
            self._errore_editing = str(errore)
        self._prepara_mesi_visualizzati()

        self.accettato = False

        self._concluso = False
        self._salvataggio_in_corso = False

        self.setWindowTitle(
            "Anteprima assegnazioni annuali — accetta o scarta"
        )
        applica_icona_finestra(self, "history")
        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
        )

        self._setup_ui()
        self._applica_stile()

    def _prepara_mesi_visualizzati(self):
        """Ricostruisce aula e metriche di ogni mese dai dati correnti."""
        self._mesi_non_validi_struttura = 0
        identita_schema = self._schema_personalizzato.identita_semantica()
        motore_statistiche = MotoreVincoliConfigurato()
        motore_statistiche.imposta_genere_misto_obbligatorio(
            self._genere_misto
        )
        for mese in self.mesi:
            gruppi = list(mese.get("gruppi") or [])
            collocazioni = list(mese.get("collocazioni") or [])
            if (
                not gruppi
                or len(collocazioni) != len(gruppi)
                or mese.get("schema_identita") != identita_schema
            ):
                self._mesi_non_validi_struttura += 1
                continue
            try:
                mese["aula"] = costruisci_configurazione_aula_personalizzata(
                    self._layout_visuale_personalizzato,
                    collocazioni,
                )
            except Exception:
                self._mesi_non_validi_struttura += 1
                continue
            righe, _dati = costruisci_statistiche_generali_terzetti(
                gruppi,
                motore_statistiche,
                adiacenze_gia_usate=set(mese.get("adiacenze_prima") or ()),
            )
            righe = [dict(riga) for riga in righe]
            for riga in righe:
                if riga.get("chiave") == "coppia_residua":
                    valore = int(riga.get("valore", 0))
                    riga["etichetta"] = (
                        "Coppia formata" if valore == 1 else "Coppie formate"
                    )
            mese["statistiche_generali"] = righe


    def _setup_ui(self):
        """Costruisce intestazione, elenco dei mesi e comandi dell’anteprima."""
        layout_principale = QVBoxLayout(self)
        self._layout_principale = layout_principale
        self._header_anteprima = self._crea_header()
        layout_principale.addWidget(self._header_anteprima)

        scroll = QScrollArea()
        self._scroll_mesi = scroll
        scroll.setWidgetResizable(True)
        contenitore = QWidget()
        layout_mesi = QVBoxLayout(contenitore)
        self._layout_mesi = layout_mesi

        for indice, assegnatore in enumerate(self.mesi):
            layout_mesi.addWidget(self._crea_scheda_mese(indice, assegnatore))
        layout_mesi.addStretch()
        scroll.setWidget(contenitore)
        layout_principale.addWidget(scroll)

        layout_principale.addWidget(self._crea_footer())

    def _crea_header(self):
        """Crea il riepilogo generale della stagione."""
        num_mesi = len(self.mesi)
        num_richiesti = self.info.get('num_mesi_richiesti', num_mesi)

        n_stagioni_complete = self.info.get(
            'n_stagioni_complete',
            self.info.get('n_stagioni', 1),
        )
        ripetizioni = self.info.get('tot_ripetizioni', 0)
        punteggio = self.info.get('punteggio', (0, 0, 0))

        incomp_pesate = punteggio[1] if len(punteggio) > 1 else 0
        elapsed = self.info.get('elapsed', 0)

        parziale = num_mesi < num_richiesti

        header = QGroupBox("Riepilogo")
        layout = QVBoxLayout(header)

        DIM_FONT_HEADER = 14

        def _riga(testo_html, icona_nome):
            contenitore_riga = QWidget()
            contenitore_riga.setAutoFillBackground(False)
            contenitore_riga.setStyleSheet(
                "background-color: transparent; border: none;"
            )
            layout_riga = QHBoxLayout(contenitore_riga)
            layout_riga.setContentsMargins(0, 1, 0, 1)
            layout_riga.setSpacing(8)

            icona = QLabel()
            icona.setFixedSize(24, 24)
            icona.setAlignment(Qt.AlignCenter)
            icona.setAutoFillBackground(False)
            icona.setStyleSheet(
                "background-color: transparent; border: none;"
            )
            applica_icona_etichetta(icona, icona_nome, 20)
            layout_riga.addWidget(icona, alignment=Qt.AlignTop)

            etichetta = QLabel(testo_html)
            etichetta.setTextFormat(Qt.RichText)
            etichetta.setWordWrap(True)
            etichetta.setAutoFillBackground(False)
            etichetta.setStyleSheet(
                f"font-size: {DIM_FONT_HEADER}px; "
                "background-color: transparent; border: none;"
            )
            layout_riga.addWidget(etichetta, 1)
            return contenitore_riga

        parola_mese = forma_numerata(num_mesi, "mese", "mesi")
        parola_pronto = forma_numerata(num_mesi, "pronto", "pronti")
        if parziale:
            testo_mesi = (
                f"<b>{num_mesi}</b> {parola_mese} {parola_pronto} "
                f"su {num_richiesti} "
                f"(annata <b>parziale</b>: raggiunto il tempo massimo)."
            )
            icona_mesi = "triangle-alert"
        else:
            testo_mesi = (
                f"<b>{num_mesi}</b> {parola_mese} {parola_pronto} "
                "(annata completa)."
            )
            icona_mesi = "circle-check"
        layout.addWidget(_riga(testo_mesi, icona_mesi))

        if n_stagioni_complete <= 1:
            testo_confronto = "Disposizione unica (nessun confronto)."
            icona_confronto = "file-text"
        else:
            testo_confronto = (
                f"Migliore tra {n_stagioni_complete} "
                f"annate complete confrontate."
            )
            icona_confronto = "wand-sparkles"
        if self._bozza_annuale is not None and self._bozza_annuale.modificata:
            testo_confronto += ' Confronto riferito alla generazione automatica.'
        layout.addWidget(_riga(testo_confronto, icona_confronto))

        if self._bozza_annuale is not None and self._bozza_annuale.modificata:
            quadri = self._bozza_annuale.quadri()
            ripetizioni = sum(len(q.riutilizzi) for q in quadri)
            incomp_pesate = sum(
                q.metriche.incompatibilita_l1 + q.metriche.incompatibilita_l2
                for q in quadri
            )
            modificati = ', '.join(map(str, self._bozza_annuale.mesi_modificati()))
            layout.addWidget(_riga(
                f'<b>Bozza manuale</b> — mesi modificati: {modificati}. '
                'I valori seguenti sono ricalcolati dalle disposizioni correnti; '
                'non sono i punteggi del motore Q21.', 'hand',
            ))

        if ripetizioni == 0:
            testo_rip = "Nessuna vicinanza ripetuta."
            icona_rip = "circle-check"
        else:
            testo_rip = f"Vicinanze che si ripresentano: <b>{ripetizioni}</b>."
            icona_rip = "repeat-2"
        layout.addWidget(_riga(testo_rip, icona_rip))

        if incomp_pesate == 0:
            testo_incomp = "Tutti i vincoli di incompatibilità rispettati."
            icona_incomp = "circle-check"
        else:
            testo_incomp = ("Alcuni vincoli di incompatibilità non pienamente "
                            "rispettati (dettagli nei singoli mesi).")
            icona_incomp = "triangle-alert"
        layout.addWidget(_riga(testo_incomp, icona_incomp))

        layout.addWidget(_riga(
            f"Tempo impiegato: {formatta_durata(elapsed)}.",
            "timer",
        ))

        if self._mesi_non_validi_struttura > 0:
            n = self._mesi_non_validi_struttura
            layout.addWidget(_riga(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Errore interno in {n} '
                f'{"mese" if n == 1 else "mesi"}: i gruppi prodotti non '
                f'corrispondono ai blocchi fisici dell’aula. L’annata non '
                f'può essere salvata.</span>',
                "circle-x",
            ))

        return header

    def _crea_scheda_mese(self, indice, mese):
        """Presenta il mese sulla fotografia del Layout."""
        return self._crea_scheda_mese_personalizzata(indice, mese)

    def _crea_scheda_mese_personalizzata(self, indice, mese):
        """Crea la scheda riepilogativa di un mese Personalizzato."""
        scheda = QFrame()
        scheda.setFrameShape(QFrame.StyledPanel)
        # Una riga per mese: mostrare tutti i mesi senza scorrere e' piu'
        # importante di eliminare ogni singolo ritorno a capo delle statistiche.
        # Recuperiamo larghezza riducendo margini e spazi, non aggiungendo righe.
        layout = QHBoxLayout(scheda)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(4)

        modificato = (self._bozza_annuale is not None
                      and indice + 1 in self._bozza_annuale.mesi_modificati())
        riga_titolo = QHBoxLayout()
        riga_titolo.setSpacing(3)
        etichetta_mese = QLabel(f"Mese {indice + 1}")
        etichetta_mese.setObjectName(f"titoloMeseAnnuale{indice + 1}")
        etichetta_mese.setStyleSheet(
            f"color: {C('testo_blu')}; font-weight: bold; font-size: 16px;"
        )
        riga_titolo.addWidget(etichetta_mese)
        if modificato:
            icona_modifica = QLabel()
            icona_modifica.setObjectName("indicatoreModificaManualeAnnuale")
            icona_modifica.setFixedSize(20, 20)
            icona_modifica.setAlignment(Qt.AlignCenter)
            icona_modifica.setToolTip("Disposizione modificata manualmente")
            applica_icona_etichetta(icona_modifica, "hand", 18)
            riga_titolo.addWidget(icona_modifica)
        layout.addLayout(riga_titolo)
        statistiche = self._crea_widget_righe_anteprima(
            mese.get('statistiche_generali', [])
        )
        statistiche.setObjectName('statisticheMeseAnnuale')
        statistiche.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(statistiche, 1)

        riga_azioni = QHBoxLayout()
        riga_azioni.setSpacing(4)

        btn_modifica = QPushButton("Modifica/ripristina posti" if modificato
                                  else "Modifica posti")
        applica_icona(btn_modifica, "hand", 16)
        btn_modifica.setMinimumHeight(36)
        btn_modifica.setEnabled(self._bozza_annuale is not None)
        if self._bozza_annuale is None:
            btn_modifica.setToolTip(
                "Modifica non disponibile: " + self._errore_editing
            )
        btn_modifica.clicked.connect(
            lambda _checked=False, i=indice: self._modifica_posti_mese(i)
        )
        riga_azioni.addWidget(btn_modifica)

        btn_vedi = QPushButton("Disposizione")
        applica_icona(btn_vedi, "eye", 16)
        btn_vedi.setMinimumHeight(36)
        btn_vedi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_layout_bg")};
                color: {C("storico_btn_layout_txt")};
                border: 1px solid {C("storico_btn_layout_bordo")};
                font-weight: bold; border-radius: 4px; padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_layout_hover")};
                border-color: {C("storico_btn_layout_bordo")};
            }}
        """)
        btn_vedi.clicked.connect(
            lambda _checked=False, i=indice:
                self._vedi_disposizione_personalizzata(i, self.mesi[i])
        )
        btn_report = QPushButton("Report")
        applica_icona(btn_report, "file-text", 16)
        btn_report.setMinimumHeight(36)
        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_dettagli_bg")};
                color: {C("storico_btn_dettagli_txt")};
                border: 1px solid {C("storico_btn_dettagli_bordo")};
                font-weight: bold; border-radius: 4px; padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_dettagli_hover")};
                border-color: {C("storico_btn_dettagli_bordo")};
            }}
        """)
        btn_report.clicked.connect(
            lambda _checked=False, i=indice:
                self._vedi_report_personalizzata(i, self.mesi[i])
        )
        riga_azioni.addWidget(btn_report)
        riga_azioni.addWidget(btn_vedi)
        layout.addLayout(riga_azioni)
        return scheda


    def _modifica_posti_mese(self, indice):
        """A2: modifica un mese nella bozza, non nello Storico."""
        from moduli.interfaccia.dialogo_dragdrop_prova import DialogoProvaDragDrop

        if self._concluso or self._bozza_annuale is None:
            return
        if not (0 <= indice < self._bozza_annuale.numero_mesi):
            return
        # Ogni mese vede lo Storico ricalcolato fino al mese precedente.
        mese = self.mesi[indice]
        dati = dict(mese)
        dati['fotografia_generazione'] = self._fotografia_generazione
        dati['configurazione_aula'] = mese['aula']
        dati['disposizione_automatica'] = self._bozza_annuale.originale[indice]
        dialogo = DialogoProvaDragDrop(self, dati, lambda: not self._concluso)
        dialogo.setWindowTitle(f'Modifica posti — Mese {indice + 1} dell’Annuale')
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            nuova = self._bozza_annuale.adotta_mese(
                indice, dialogo.bozza.corrente,
            )
            if nuova is self._bozza_annuale:
                return
            # La nuova bozza diventa visibile solo dopo la validazione di
            # TUTTA la sequenza, senza mai mutare gli input Q21.
            self._imposta_bozza_annuale(nuova)
        except (ValueError, TypeError, KeyError) as errore:
            mostra_popup_semantico(
                self, 'Modifiche non adottate',
                'Non è stato possibile verificare la bozza annuale.',
                'circle-x', testo_informativo=str(errore),
            )

    def _aggiorna_anteprima_editing(self):
        """Aggiorna le schede e lo stato di salvataggio senza ridurre l'aula."""
        self._scroll_mesi.setUpdatesEnabled(False)
        try:
            posizione = self._scroll_mesi.verticalScrollBar().value()
            while self._layout_mesi.count():
                elemento = self._layout_mesi.takeAt(0)
                if elemento.widget() is not None:
                    elemento.widget().deleteLater()
            for indice, mese in enumerate(self.mesi):
                self._layout_mesi.addWidget(self._crea_scheda_mese(indice, mese))
            self._layout_mesi.addStretch()
            nuovo_header = self._crea_header()
            self._layout_principale.replaceWidget(self._header_anteprima, nuovo_header)
            self._header_anteprima.deleteLater()
            self._header_anteprima = nuovo_header
            self._scroll_mesi.verticalScrollBar().setValue(posizione)
            self._aggiorna_comandi_editing()
        finally:
            self._scroll_mesi.setUpdatesEnabled(True)

    def _annulla_editing_annuale(self):
        if self._bozza_annuale is None or not self._bozza_annuale.undo:
            return
        self._imposta_bozza_annuale(self._bozza_annuale.annulla())

    def _ripristina_editing_annuale(self):
        if self._bozza_annuale is None or not self._bozza_annuale.modificata:
            return
        self._imposta_bozza_annuale(self._bozza_annuale.ripristina_annata())

    def _imposta_bozza_annuale(self, nuova):
        # Convalida la sequenza prima di presentarla, conservando Q21 intatto.
        proiettati = nuova.proietta_mesi(self._mesi_q21)
        precedente = self.mesi
        try:
            self.mesi = proiettati
            self._prepara_mesi_visualizzati()
        except Exception:
            self.mesi = precedente
            self._prepara_mesi_visualizzati()
            raise
        self._bozza_annuale = nuova
        self._aggiorna_anteprima_editing()

    def _aggiorna_comandi_editing(self):
        bozza = self._bozza_annuale
        if bozza is None:
            self.btn_undo_annuale.setEnabled(False)
            self.btn_ripristina_annuale.setEnabled(False)
            return
        self.btn_undo_annuale.setEnabled(bool(bozza.undo))
        self.btn_ripristina_annuale.setEnabled(bozza.modificata)
        self.btn_accetta.setEnabled(self._mesi_non_validi_struttura == 0)
        self.btn_accetta.setText('Accetta e salva nello Storico')
        self.btn_accetta.setToolTip(
            'Salva l’intera annata, compresi i mesi modificati manualmente.'
            if bozza.modificata else ''
        )

    def _crea_widget_righe_anteprima(self, righe):
        """Crea il riepilogo mensile con lo stesso renderer dei popup."""
        return crea_widget_righe_statistiche(
            righe,
            solo_segnalazioni=True,
            sfondo_trasparente=True,
        )


    def _vedi_disposizione_personalizzata(self, indice, mese):
        """Apre la vera geometria di un mese Personalizzato in sola lettura."""
        configurazione_aula = mese.get("aula")
        if configurazione_aula is None:
            mostra_popup_semantico(
                self,
                "Layout non disponibile",
                "Il mese non contiene una piantina valida.",
                "circle-x",
            )
            return
        dati = {
            "nome": self.nomi_assegnazioni[indice],
            "classe": self.nome_classe,
            "data_creazione": self.data_creazione,
            "abbinamenti": _descrivi_abbinamenti_personalizzata(
                mese.get("gruppi") or []
            ),
            "modo": "personalizzata",
        }
        popup = PopupLayoutStorico.da_configurazione(
            self.parent_window, self.config_app, configurazione_aula, dati
        )
        popup.exec()


    def _ultimi_usi_annata(self, indice):
        return ultimi_usi_nell_annata(self.mesi, indice)

    def _costruisci_report_mese_personalizzata(self, indice):
        """Costruisce e congela il report di un mese Personalizzato."""
        mese = self.mesi[indice]
        configurazione_aula = costruisci_configurazione_aula_personalizzata(
            self._layout_visuale_personalizzato, mese.get("collocazioni") or (),
        )
        mese["aula"] = configurazione_aula

        report = self.parent_window.prepara_report_personalizzata(
            mese.get("gruppi") or [], mese.get("collocazioni") or [],
            nome_classe=self.nome_classe, studenti=self._studenti,
            configurazione_aula=configurazione_aula,
            genere_misto=self._genere_misto,
            nome_assegnazione=self.nomi_assegnazioni[indice],
            data_creazione=self.data_creazione,
            adiacenze_gia_usate=set(mese.get("adiacenze_prima") or ()),
            ultimo_uso_vicinanze=self._ultimi_usi_annata(indice),
            modificata_manualmente=bool(mese.get("modificata_manualmente")),
        )
        mese["statistiche_generali"] = [dict(riga) for riga in report.statistiche]
        mese["report_completo"] = report.testo
        return report.testo, report.riutilizzi

    def _vedi_report_personalizzata(self, indice, mese):
        """Apre il report Annuale Personalizzato in sola lettura."""
        try:
            testo = self._costruisci_report_mese_personalizzata(indice)[0]
        except Exception as errore:
            mostra_popup_semantico(
                self,
                "Report non disponibile",
                "Non è stato possibile costruire il Report.",
                "circle-x",
                testo_informativo=str(errore),
                messaggio_in_grassetto=True,
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Report — {self.nomi_assegnazioni[indice]}")
        applica_icona_finestra(dialog, "file-text")
        adatta_finestra_allo_schermo(
            dialog, larghezza_ideale=1200, altezza_ideale=750,
            larghezza_minima=760, altezza_minima=480,
        )
        layout = QVBoxLayout(dialog)
        area = QTextEdit()
        area.setReadOnly(True)
        area.setLineWrapMode(QTextEdit.NoWrap)
        font_mono = QFont("monospace")
        font_mono.setStyleHint(QFont.Monospace)
        area.setFont(font_mono)
        area.setPlainText(testo)
        evidenzia_riutilizzi(area)
        applica_formattazione_statistiche_generali(
            area, mese.get("statistiche_generali", [])
        )
        layout.addWidget(area)
        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.clicked.connect(dialog.close)
        layout.addWidget(btn_chiudi)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QTextEdit {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
            }}
        """)
        dialog.exec()


    def _crea_footer(self):
        """Crea i comandi per accettare o scartare la stagione."""
        footer = QWidget()
        layout = QHBoxLayout(footer)
        self.btn_undo_annuale = QPushButton('Annulla ultima modifica')
        applica_icona(self.btn_undo_annuale, 'history', 17)
        self.btn_undo_annuale.clicked.connect(self._annulla_editing_annuale)
        layout.addWidget(self.btn_undo_annuale)
        self.btn_ripristina_annuale = QPushButton('Ripristina tutti i mesi')
        applica_icona(self.btn_ripristina_annuale, 'rotate-ccw', 17)
        self.btn_ripristina_annuale.clicked.connect(self._ripristina_editing_annuale)
        layout.addWidget(self.btn_ripristina_annuale)
        layout.addStretch()

        btn_scarta = QPushButton("Scarta")
        applica_icona(btn_scarta, "trash-2", 18)
        btn_scarta.setMinimumHeight(45)
        btn_scarta.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_grigio_bg")};
                color: white;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_grigio_hover")};
            }}
        """)
        btn_scarta.clicked.connect(self._on_scarta)
        layout.addWidget(btn_scarta)

        self.btn_accetta = QPushButton("Accetta e salva nello Storico")
        applica_icona(self.btn_accetta, "circle-check", 18)
        self.btn_accetta.setMinimumHeight(45)
        self.btn_accetta.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("btn_salva_bg")};
                color: {C("btn_salva_txt")};
                border: 1px solid {C("btn_salva_bordo")};
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {C("btn_salva_hover")};
                border-color: {C("btn_salva_bordo")};
            }}
            QPushButton:disabled {{
                background-color: {C("btn_azione_disabled_bg")};
                color: {C("btn_azione_disabled_txt")};
                border-color: {C("btn_azione_disabled_bordo")};
            }}
        """)
        self.btn_accetta.clicked.connect(self._on_accetta)
        if self._mesi_non_validi_struttura > 0:
            self.btn_accetta.setEnabled(False)
            self.btn_accetta.setToolTip(
                "Salvataggio bloccato: almeno un mese contiene un "
                "errore interno di posizionamento."
            )
        layout.addWidget(self.btn_accetta)
        self._aggiorna_comandi_editing()

        return footer

    def _conferma_scarto(self):
        """Chiede conferma prima di scartare la stagione."""

        n = len(self.mesi)
        parola = "assegnazione mensile" if n == 1 else "assegnazioni mensili"

        conferma = crea_popup_semantico(
            self.parent_window,
            "Scartare l'intera annata?",
            "L'intera annata appena generata verrà eliminata.",
            "triangle-alert",
            testo_informativo=(
                f"Le {n} {parola} che vedi in anteprima andranno perse e, "
                "se ti servono, dovrai rigenerarle da capo.\n\n"
                "Lo Storico già salvato non viene toccato.\n\n"
                "Vuoi davvero scartare tutto?"
            ),
            messaggio_in_grassetto=True,
        )

        btn_annulla = conferma.addButton("Annulla", QMessageBox.RejectRole)
        btn_scarta = conferma.addButton("Scarta tutto", QMessageBox.DestructiveRole)
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_scarta, "trash-2", 18)
        applica_stile_pulsante_popup(btn_scarta, "distruttivo")

        conferma.setDefaultButton(btn_annulla)
        conferma.setEscapeButton(btn_annulla)

        conferma.exec()
        return conferma.clickedButton() == btn_scarta

    def _on_scarta(self):
        """Scarta la stagione senza modificare lo Storico."""
        self.reject()

    def reject(self):
        """Chiude l’anteprima senza salvare, dopo l’eventuale conferma."""

        if self._concluso:
            super().reject()
            return
        if self._conferma_scarto():
            self.accettato = False
            self._concluso = True
            super().reject()

    def closeEvent(self, event):
        """Gestisce la chiusura della finestra senza salvataggio implicito."""

        if self._concluso:
            event.accept()
            return
        if self._conferma_scarto():
            self.accettato = False
            self._concluso = True
            event.accept()
        else:
            event.ignore()

    def _on_accetta(self):
        """Salva nello Storico tutti i mesi della stagione accettata."""
        if self._concluso or self._salvataggio_in_corso:
            return
        if self._mesi_non_validi_struttura > 0:
            mostra_popup_semantico(
                self.parent_window,
                "Annata non salvabile",
                "Almeno un mese contiene un errore interno di posizionamento.",
                "circle-x",
                testo_informativo=(
                    "L'intera annata deve essere scartata e rigenerata."
                ),
                messaggio_in_grassetto=True,
            )
            return

        self._salva_annata_personalizzata()

    def _salva_annata_personalizzata(self):
        """Salva atomicamente tutti i mesi Personalizzati dell'anteprima."""
        if self._concluso or self._salvataggio_in_corso:
            return
        self._salvataggio_in_corso = True
        try:
            # La bozza annuale, non i widget o le cache dell'anteprima, è
            # l'unica fonte ammessa per un salvataggio con modifiche manuali.
            # Questa operazione verifica tutti i mesi e la cronologia Q21.
            mesi_salvabili = prepara_mesi_da_anteprima_annuale(
                self._bozza_annuale, self._mesi_q21, self.mesi,
            )
            for mese in mesi_salvabili:
                self._fotografia_generazione.verifica_risultato(mese)
            precedenti = self.mesi
            problemi_precedenti = self._mesi_non_validi_struttura
            try:
                self.mesi = mesi_salvabili
                self._prepara_mesi_visualizzati()
                if self._mesi_non_validi_struttura:
                    raise ValueError('Almeno un mese ha una struttura non valida.')
                report_per_mese = [
                    self._costruisci_report_mese_personalizzata(indice)[0]
                    for indice in range(len(mesi_salvabili))
                ]
            finally:
                # Anche in caso di errore rimane consultabile la bozza di prima.
                self.mesi = precedenti
                self._mesi_non_validi_struttura = problemi_precedenti
            salva_annata_personalizzata(
                self.config_app,
                mesi_salvabili,
                self.identita_annata,
                schema_personalizzato=self._schema_personalizzato,
                layout_visuale=self._layout_visuale_personalizzato,
                report_per_mese=report_per_mese,
                genere_misto=self._genere_misto,
            )
        except Exception as errore:
            self._salvataggio_in_corso = False
            mostra_popup_semantico(
                self.parent_window,
                "Annata non salvata",
                "Non è stato possibile registrare l'intera annata.",
                "circle-x",
                testo_informativo=(
                    f"{errore}\n\n"
                    "Nessun mese della nuova annata è stato aggiunto allo "
                    "Storico. Puoi riprovare senza chiudere l'anteprima."
                ),
                messaggio_in_grassetto=True,
            )
            return

        self.accettato = True
        self._concluso = True
        mostra_popup_semantico(
            self.parent_window,
            "Annata salvata nello Storico",
            "L'intera annata è stata salvata.",
            "circle-check",
            testo_informativo=(
                _testo_assegnazioni_salvate(self.nomi_assegnazioni)
                + "Puoi consultare le assegnazioni, rinominarle, esportarle "
                "o eliminarle dalla scheda Storico."
            ),
            messaggio_in_grassetto=True,
        )
        self.accept()


    def _applica_stile(self):
        """Applica all’anteprima il tema corrente."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {C("bordo_normale")};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: {C("sfondo_pannello")};
                color: {C("testo_principale")};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                background-color: {C("sfondo_principale")};
                color: {C("testo_principale")};
            }}
            QLabel {{
                color: {C("testo_principale")};
            }}
            QFrame {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 6px;
                background-color: {C("sfondo_pannello")};
            }}
            QScrollArea {{
                border: 1px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_pannello")};
            }}
        """)

