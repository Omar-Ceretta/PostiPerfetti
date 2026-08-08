# -*- coding: utf-8 -*-
"""Anteprima e salvataggio delle assegnazioni annuali.

Il dialogo presenta i mesi generati, apre piantine e report e coordina
l'accettazione atomica o lo scarto dell'intera annata. La finestra principale
fornisce soltanto il contesto applicativo necessario ai report a terzetti.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QGroupBox,
    QLabel, QFrame, QPushButton, QTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from moduli.annuale import formatta_durata
from moduli.lingua import forma_numerata
from moduli.metrica_pulizia import adiacenze_per_blacklist_terzetti
from moduli.risultati_annuali import (
    ErroreSalvataggioAnnata,
    aggiorna_report_mesi_coppie,
    descrivi_abbinamenti_coppie as _descrivi_abbinamenti_coppie,
    descrivi_abbinamenti_terzetti as _descrivi_abbinamenti_terzetti,
    prepara_identita_annata,
    prepara_mesi_terzetti,
    salva_annata_coppie,
    salva_annata_terzetti,
)
from moduli.statistiche_generali import (
    costruisci_statistiche_generali_terzetti,
    applica_formattazione_statistiche_generali,
)
from moduli.strato_storico import (
    applica_penalita_storico as _applica_penalita_storico_mese,
    aggiorna_blacklist_terzetti,
)
from moduli.tema import C
from moduli.utilita import (
    adatta_finestra_allo_schermo,
    applica_icona,
    applica_icona_etichetta,
    applica_icona_finestra,
    applica_stile_pulsante_popup,
    crea_popup_semantico,
    mostra_popup_semantico,
)
from moduli.vincoli import MotoreVincoliConfigurato
from moduli.esportazione import evidenzia_riutilizzi
from moduli.storico_ui import PopupLayoutStorico
from moduli.widget_statistiche import crea_widget_righe_statistiche

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
            genere_misto, studenti, studente_fisso=None, modo='coppie',
            terzetti_per_fila=None, posizione_blocco_finale=None,
            ha_fisso=False, preferenza_resto2='coppia'):
        """Inizializza l’anteprima con i mesi generati e i dati di riepilogo."""
        super().__init__(parent)

        self.parent_window = parent
        self.config_app = config_app
        self.mesi = mesi or []
        self.info = info or {}
        self.file_origine = file_origine
        self.nome_classe = nome_classe or "Classe"
        self._genere_misto = bool(genere_misto)
        self._studenti = list(studenti)
        self._studente_fisso = studente_fisso

        self.modo = modo
        self._terzetti_per_fila = terzetti_per_fila
        self._posizione_blocco_finale = posizione_blocco_finale
        self._ha_fisso = ha_fisso
        self._preferenza_resto2 = preferenza_resto2

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

        if self.modo == "coppie":
            aggiorna_report_mesi_coppie(
                self.mesi,
                self.identita_annata,
            )

        self._mesi_non_validi_prima = 0
        self._mesi_non_validi_struttura = 0
        if self.modo == 'terzetti':
            preparazione = prepara_mesi_terzetti(
                self.mesi,
                terzetti_per_fila=self._terzetti_per_fila,
                posizione_blocco_finale=self._posizione_blocco_finale,
                ha_fisso=self._ha_fisso,
                preferenza_resto2=self._preferenza_resto2,
                costruisci_statistiche=(
                    costruisci_statistiche_generali_terzetti
                ),
            )
            self._mesi_non_validi_prima = (
                preparazione.mesi_non_validi_prima
            )
            self._mesi_non_validi_struttura = (
                preparazione.mesi_non_validi_struttura
            )

        self.accettato = False

        self._concluso = False

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

    def _setup_ui(self):
        """Costruisce intestazione, elenco dei mesi e comandi dell’anteprima."""
        layout_principale = QVBoxLayout(self)

        layout_principale.addWidget(self._crea_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        contenitore = QWidget()
        layout_mesi = QVBoxLayout(contenitore)

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
        layout.addWidget(_riga(testo_confronto, icona_confronto))

        if self.modo == 'terzetti':
            if ripetizioni == 0:
                testo_rip = "Nessuna vicinanza ripetuta."
                icona_rip = "circle-check"
            else:
                testo_rip = f"Vicinanze che si ripresentano: <b>{ripetizioni}</b>."
                icona_rip = "repeat-2"
        else:
            if ripetizioni == 0:
                testo_rip = "Nessuna ripetizione di coppie."
                icona_rip = "circle-check"
            else:
                testo_rip = f"Coppie che si ritrovano vicine: <b>{ripetizioni}</b>."
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

        if self.modo == 'terzetti' and self._mesi_non_validi_struttura > 0:
            n = self._mesi_non_validi_struttura
            layout.addWidget(_riga(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Errore interno in {n} '
                f'{"mese" if n == 1 else "mesi"}: i gruppi prodotti non '
                f'corrispondono ai blocchi fisici dell’aula. L’annata non '
                f'può essere salvata.</span>',
                "circle-x",
            ))

        if self.modo == 'terzetti' and self._mesi_non_validi_prima > 0:
            n = self._mesi_non_validi_prima
            layout.addWidget(_riga(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Errore interno in {n} '
                f'{"mese" if n == 1 else "mesi"}: il vincolo assoluto PRIMA '
                f'non è stato rispettato. L’annata non può essere salvata.</span>',
                "circle-x",
            ))

        return header

    def _crea_scheda_mese(self, indice, assegnatore):
        """Crea la scheda riepilogativa di un mese a coppie."""

        if self.modo == 'terzetti':
            return self._crea_scheda_mese_terzetti(indice, assegnatore)
        scheda = QFrame()
        scheda.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(scheda)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        etichetta_mese = QLabel(f"Mese {indice + 1}")
        etichetta_mese.setStyleSheet(
            f"color: {C('testo_blu')}; font-weight: bold; font-size: 16px;"
        )

        layout.addWidget(etichetta_mese, alignment=Qt.AlignTop)
        layout.addSpacing(20)

        colonna_note = QVBoxLayout()

        colonna_note.addWidget(
            self._crea_widget_righe_anteprima(
                getattr(assegnatore, 'statistiche_generali', [])
            )
        )

        colonna_note.addStretch()
        layout.addLayout(colonna_note)

        layout.addStretch()

        btn_vedi = QPushButton("Vedi disposizione")
        applica_icona(btn_vedi, "eye", 16)
        btn_vedi.setMinimumHeight(36)

        btn_vedi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_layout_bg")};
                color: {C("storico_btn_layout_txt")};
                border: 1px solid {C("storico_btn_layout_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_layout_hover")};
                border-color: {C("storico_btn_layout_bordo")};
            }}
        """)

        btn_vedi.clicked.connect(
            lambda _checked=False, i=indice, a=assegnatore: self._vedi_disposizione(i, a)
        )
        layout.addWidget(btn_vedi)

        btn_report = QPushButton("Report")
        applica_icona(btn_report, "file-text", 16)
        btn_report.setMinimumHeight(36)

        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_dettagli_bg")};
                color: {C("storico_btn_dettagli_txt")};
                border: 1px solid {C("storico_btn_dettagli_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_dettagli_hover")};
                border-color: {C("storico_btn_dettagli_bordo")};
            }}
        """)
        btn_report.clicked.connect(
            lambda _checked=False, i=indice, a=assegnatore: self._vedi_report(i, a)
        )
        layout.addWidget(btn_report)

        return scheda

    def _crea_scheda_mese_terzetti(self, indice, mese):
        """Crea la scheda riepilogativa di un mese a terzetti."""
        scheda = QFrame()
        scheda.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(scheda)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        etichetta_mese = QLabel(f"Mese {indice + 1}")
        etichetta_mese.setStyleSheet(
            f"color: {C('testo_blu')}; font-weight: bold; font-size: 16px;"
        )
        layout.addWidget(etichetta_mese, alignment=Qt.AlignTop)
        layout.addSpacing(20)

        colonna_note = QVBoxLayout()

        colonna_note.addWidget(
            self._crea_widget_righe_anteprima(
                mese.get('statistiche_generali', [])
            )
        )

        prima_fuori = mese.get('prima_fuori', 0)
        if prima_fuori > 0:
            etichetta_prima = QLabel(
                f'<span style="color: {C("testo_incomp")}; font-weight: bold;">'
                f'Disposizione non valida: {prima_fuori} '
                f'{"gruppo" if prima_fuori == 1 else "gruppi"} con studenti PRIMA '
                f'fuori dalla prima fila</span>'
            )
            etichetta_prima.setTextFormat(Qt.RichText)
            colonna_note.addWidget(etichetta_prima)

        colonna_note.addStretch()
        layout.addLayout(colonna_note)
        layout.addStretch()

        btn_vedi = QPushButton("Vedi disposizione")
        applica_icona(btn_vedi, "eye", 16)
        btn_vedi.setMinimumHeight(36)
        btn_vedi.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_layout_bg")};
                color: {C("storico_btn_layout_txt")};
                border: 1px solid {C("storico_btn_layout_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_layout_hover")};
                border-color: {C("storico_btn_layout_bordo")};
            }}
        """)

        btn_vedi.clicked.connect(
            lambda _checked=False, i=indice, m=mese: self._vedi_disposizione_terzetti(i, m)
        )
        layout.addWidget(btn_vedi)

        btn_report = QPushButton("Report")
        applica_icona(btn_report, "file-text", 16)
        btn_report.setMinimumHeight(36)
        btn_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {C("storico_btn_dettagli_bg")};
                color: {C("storico_btn_dettagli_txt")};
                border: 1px solid {C("storico_btn_dettagli_bordo")};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {C("storico_btn_dettagli_hover")};
                border-color: {C("storico_btn_dettagli_bordo")};
            }}
        """)
        btn_report.clicked.connect(
            lambda _checked=False, i=indice, m=mese: self._vedi_report_terzetti(i, m)
        )
        layout.addWidget(btn_report)

        return scheda

    def _crea_widget_righe_anteprima(self, righe):
        """Crea il riepilogo mensile con lo stesso renderer dei popup."""
        return crea_widget_righe_statistiche(
            righe,
            solo_segnalazioni=True,
            sfondo_trasparente=True,
        )

    def _vedi_disposizione_terzetti(self, indice, mese):
        """Apre in sola lettura la piantina di un mese a terzetti."""
        configurazione_aula = mese['aula']

        dati = {
            "nome": self.nomi_assegnazioni[indice],
            "classe": self.nome_classe,
            "data_creazione": self.data_creazione,
            "abbinamenti": _descrivi_abbinamenti_terzetti(mese["gruppi"]),
            "modo": "terzetti",
        }

        popup = PopupLayoutStorico.da_configurazione(
            self.parent_window, self.config_app, configurazione_aula, dati
        )
        popup.exec()

    def _vedi_disposizione(self, indice, assegnatore):
        """Apre in sola lettura la piantina di un mese a coppie."""
        configurazione_aula = assegnatore.configurazione_aula

        dati = {
            "nome": self.nomi_assegnazioni[indice],
            "classe": self.nome_classe,
            "data_creazione": self.data_creazione,
            "abbinamenti": _descrivi_abbinamenti_coppie(assegnatore),
            "modo": "coppie",
        }

        popup = PopupLayoutStorico.da_configurazione(
            self.parent_window, self.config_app, configurazione_aula, dati
        )
        popup.exec()

    def _vedi_report(self, indice, assegnatore):
        """Apre il report di un mese a coppie in sola lettura."""

        testo = getattr(assegnatore, 'report_testo', None)
        if not str(testo or "").strip():
            mostra_popup_semantico(
                self,
                "Report non disponibile",
                "Il mese Annuale non contiene il Report previsto.",
                "circle-x",
                testo_informativo=(
                    "Il risultato non rispetta il formato corrente e non può "
                    "essere mostrato o salvato."
                ),
                messaggio_in_grassetto=True,
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Report — {self.nomi_assegnazioni[indice]}")
        applica_icona_finestra(dialog, "file-text")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
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
            area, getattr(assegnatore, 'statistiche_generali', []))
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

    def _costruisci_report_mese_terzetti(self, indice):
        """Costruisce il report e il conteggio dei riutilizzi di un mese a terzetti."""
        mese = self.mesi[indice]
        gruppi = mese['gruppi']

        # Copia soltanto i dati persistenti, escludendo i callback GUI legati
        # alla finestra principale: un deepcopy dell'intero ConfigurazioneApp
        # tenterebbe di serializzare il QObject e fallirebbe in fase di salvataggio.
        config_report = self.config_app.copia_temporanea()
        ultimo_uso_vicinanze = {}
        for j, m_prec in enumerate(self.mesi[:indice], start=1):
            adiacenze = adiacenze_per_blacklist_terzetti(m_prec['gruppi'])
            aggiorna_blacklist_terzetti(config_report, adiacenze)

            for coppia in adiacenze:
                ultimo_uso_vicinanze[tuple(sorted(coppia))] = f"mese {j}"

        motore = MotoreVincoliConfigurato()
        motore.imposta_genere_misto_obbligatorio(self._genere_misto)
        _applica_penalita_storico_mese(motore, config_report, modo="terzetti")

        riga_salvata = getattr(
            self.parent_window,
            '_riga_identificativa_report',
            None,
        )
        try:
            testo, riutilizzi = self.parent_window.costruisci_testo_report_terzetti(
                gruppi, motore,
                nome_classe=self.nome_classe,
                studenti=self._studenti,
                configurazione_aula=mese['aula'],
                ultimo_uso_vicinanze=ultimo_uso_vicinanze,
                nome_assegnazione=self.nomi_assegnazioni[indice],
                data_creazione=self.data_creazione,
            )
            mese['statistiche_generali'] = [
                dict(riga) for riga in getattr(
                    self.parent_window,
                    '_statistiche_generali_terzetti_correnti',
                    [],
                )
            ]
        finally:
            self.parent_window._riga_identificativa_report = riga_salvata
        return testo, riutilizzi

    def _vedi_report_terzetti(self, indice, mese):
        """Apre il report di un mese a terzetti in sola lettura."""
        testo = self._costruisci_report_mese_terzetti(indice)[0]

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Report — {self.nomi_assegnazioni[indice]}")
        applica_icona_finestra(dialog, "file-text")
        adatta_finestra_allo_schermo(
            dialog,
            larghezza_ideale=1200,
            altezza_ideale=750,
            larghezza_minima=760,
            altezza_minima=480,
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
            area, mese.get('statistiche_generali', []))
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
        if (self._mesi_non_validi_prima > 0
                or self._mesi_non_validi_struttura > 0):
            self.btn_accetta.setEnabled(False)
            if self._mesi_non_validi_struttura > 0:
                self.btn_accetta.setToolTip(
                    "Salvataggio bloccato: almeno un mese contiene un "
                    "errore interno di posizionamento."
                )
            else:
                self.btn_accetta.setToolTip(
                    "Salvataggio bloccato: almeno un mese non rispetta il "
                    "vincolo assoluto PRIMA."
                )
        layout.addWidget(self.btn_accetta)

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

        if self._mesi_non_validi_prima > 0:
            mostra_popup_semantico(
                self.parent_window,
                "Annata non salvabile",
                "Almeno un mese non rispetta il vincolo assoluto PRIMA.",
                "circle-x",
                testo_informativo=(
                    "L'intera annata deve essere scartata e rigenerata."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if self.modo == 'terzetti':
            self._salva_annata_terzetti()
            return

        try:
            salva_annata_coppie(
                self.config_app,
                self.mesi,
                self.identita_annata,
                genere_misto=self._genere_misto,
            )
        except ErroreSalvataggioAnnata as errore:
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

        self._concluso = True
        self.accept()

    def _salva_annata_terzetti(self):
        """Salva atomicamente una stagione a terzetti mantenendo l'ordine dei mesi."""
        studente_fisso = self._studente_fisso
        report_per_mese = [
            self._costruisci_report_mese_terzetti(indice)[0]
            for indice in range(len(self.mesi))
        ]

        try:
            salva_annata_terzetti(
                self.config_app,
                self.mesi,
                self.identita_annata,
                report_per_mese=report_per_mese,
                studente_fisso=studente_fisso,
                genere_misto=self._genere_misto,
                posizione_blocco_finale=self._posizione_blocco_finale,
                preferenza_resto2=self._preferenza_resto2,
            )
        except ErroreSalvataggioAnnata as errore:
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
            "L'intera annata a terzetti è stata salvata.",
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

