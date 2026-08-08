# -*- coding: utf-8 -*-
"""Calcolo, visualizzazione ed esportazione delle statistiche storiche."""

import os
from datetime import datetime
from html import escape

from PySide6.QtWidgets import (
    QLabel, QGroupBox, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog
)
from PySide6.QtCore import Qt

from moduli.percorsi import get_export_path
from moduli.lingua import quantita
from moduli.utilita import (
    pulisci_nome_file, mostra_popup_file_salvato,
    abbrevia_nome_assegnazione, mostra_popup_semantico,
    applica_icona_etichetta,
)
from moduli.tema import C
from moduli.editor_studenti import ComboBoxProtetto


class StatisticheMixin:
    """Aggiunge alla finestra principale le statistiche per classe e studente."""

    @staticmethod
    def _nome_studente_html(nome) -> str:
        """Rende il nome dello studente con peso regolare nel rich text."""
        return (
            '<span style="font-weight: normal;">'
            f'{escape(str(nome))}'
            '</span>'
        )

    @staticmethod
    def _testo_volte(conteggio, complemento: str = "") -> str:
        """Compone la forma singolare o plurale di «volta»."""
        forma = "volta" if int(conteggio) == 1 else "volte"
        return f"{conteggio} {forma}{complemento}"

    @staticmethod
    def _elenco_assegnazioni(
            assegnazioni, limite: int = 5, *, html: bool = False) -> str:
        """Elenca le assegnazioni, proteggendo i nomi usati nel rich text."""
        visibili = [str(nome) for nome in assegnazioni[:limite]]
        if html:
            visibili = [escape(nome) for nome in visibili]
        testo = ", ".join(visibili)
        residue = len(assegnazioni) - len(visibili)
        if residue <= 0:
            return testo
        coda = (
            "un’altra assegnazione"
            if residue == 1
            else f"altre {residue} assegnazioni"
        )
        return f"{testo} (e {coda})"

    @staticmethod
    def _applica_stile_titolo_sezione(gruppo) -> None:
        """Evidenzia il titolo del gruppo senza appesantirne i contenuti."""
        # Qt usa il font del QGroupBox anche per il titolo: i figli vengono neutralizzati.
        font_titolo = gruppo.font()
        font_titolo.setBold(True)
        gruppo.setFont(font_titolo)

        gruppo.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
            }}
            QGroupBox QLabel,
            QGroupBox QComboBox,
            QGroupBox QPushButton,
            QGroupBox QWidget {{
                font-weight: normal;
            }}
            QGroupBox::title {{
                color: {C("statistiche_titolo_sezione")};
                font-size: 14px;
                font-weight: bold;
            }}
        """)


    def _aggiorna_statistiche(self):
        """Calcola e mostra le statistiche della classe selezionata."""
        print("📈 Aggiornamento statistiche...")

        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        while self.layout_statistiche_content.count():
            child = self.layout_statistiche_content.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if file_origine_filtro == "__placeholder__":
            print("   ⏳ Placeholder attivo: in attesa di selezione classe")
            label = QLabel(
                "NESSUNA CLASSE SELEZIONATA.\n\n"
                "Seleziona una classe dal menu in alto\n"
                "per visualizzare le statistiche delle assegnazioni."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
            )
            self.layout_statistiche_content.addWidget(label)
            return

        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            label = QLabel(
                "NESSUNA ASSEGNAZIONE SALVATA.\n\n"
                "Esegui almeno un'assegnazione e salvala\n"
                "per visualizzare e/o esportare le Statistiche."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        nome_file = os.path.basename(file_origine_filtro) if file_origine_filtro else "Classe"
        print(f"   📁 Mostrando statistiche per: {nome_file}")
        nome_filtro = nome_file

        assegnazioni_filtrate = []
        for assegnazione in storico:
            if assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            label = QLabel(
                f"NESSUNA ASSEGNAZIONE PER: {nome_filtro}\n\n"
                "Esegui almeno un'assegnazione per questa classe\n"
                "e salvala per visualizzare le statistiche."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        print(f"   ✅ {len(assegnazioni_filtrate)} assegnazioni filtrate")

        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        self._mostra_statistiche_complete(stats, nome_filtro)


    def _esporta_statistiche_txt(self):
        """Esporta in testo le statistiche della classe selezionata."""
        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            mostra_popup_semantico(
                self,
                "Nessuna statistica",
                "Seleziona una classe prima di esportare le statistiche.",
                "triangle-alert",
            )
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        if file_origine_filtro == "__placeholder__" or file_origine_filtro is None:
            mostra_popup_semantico(
                self,
                "Nessuna classe selezionata",
                "Seleziona una classe dal menu prima di esportare le statistiche.",
                "triangle-alert",
            )
            return

        nome_filtro = pulisci_nome_file(os.path.basename(file_origine_filtro))

        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        assegnazioni_filtrate = []
        for assegnazione in storico:
            if assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            mostra_popup_semantico(
                self,
                "Nessuna assegnazione",
                "Non ci sono assegnazioni disponibili per l'esportazione.",
                "triangle-alert",
            )
            return

        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        contenuto_txt = self._genera_testo_statistiche(stats, nome_filtro)

        data_ora = datetime.now().strftime('%Y%m%d_%H%M')
        # L’estensione è tolta solo dal nome proposto, non dall’etichetta della classe.
        nome_filtro_per_file = os.path.splitext(nome_filtro)[0]
        nome_suggerito = f"Statistiche_{nome_filtro_per_file}_{data_ora}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta statistiche (.txt)",
            get_export_path(nome_suggerito),
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(contenuto_txt)

                mostra_popup_file_salvato(self, "Esportazione completata", "Statistiche salvate con successo!", file_path)

            except Exception as e:
                mostra_popup_semantico(
                    self,
                    "Esportazione non riuscita",
                    "Si è verificato un errore durante il salvataggio.",
                    "circle-x",
                    testo_informativo=str(e),
                )


    def _genera_testo_statistiche(self, stats, nome_filtro):
        """Compone il report testuale delle statistiche calcolate."""
        linee = []

        linee.append("=" * 80)
        linee.append("📈 STATISTICHE ASSEGNAZIONI POSTI")
        linee.append("=" * 80)
        linee.append("")

        linee.append("📋 RIEPILOGO GENERALE")
        linee.append("-" * 80)
        linee.append(f"Classe: {nome_filtro}")
        etichetta_assegnazioni = (
            "Assegnazione totale"
            if stats['num_assegnazioni'] == 1
            else "Assegnazioni totali"
        )
        linee.append(
            f"{etichetta_assegnazioni}: {stats['num_assegnazioni']}"
        )
        if stats['prima_data']:
            linee.append(f"Periodo: dal {stats['prima_data']} al {stats['ultima_data']}")
        numero_studenti = len(stats['studenti_unici'])
        etichetta_studenti = (
            "Studente coinvolto" if numero_studenti == 1 else "Studenti coinvolti"
        )
        linee.append(f"{etichetta_studenti}: {numero_studenti}")
        linee.append("")

        linee.append("👥 COPPIE PIÙ FREQUENTI (fino a 10)")
        linee.append("-" * 80)

        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"{idx:2d}. {nome1} + {nome2} ({self._testo_volte(count)})")

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni)
                    linee.append(f"    → {asseg_str}")
        else:
            linee.append("Nessuna coppia registrata")

        linee.append("")

        if stats['trio_frequenza']:
            linee.append("🎯 STATISTICHE TRIO")
            linee.append("-" * 80)

            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({self._testo_volte(count, ' nel trio')})")

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni)
                    linee.append(f"  → {asseg_str}")

            linee.append("")

        linee.append("🔍 DETTAGLIO PER STUDENTE")
        linee.append("-" * 80)

        for nome_studente in sorted(stats['studenti_unici']):
            dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
            compagni = dettagli.get('compagni', {})

            linee.append(
                f"\n{nome_studente}: "
                f"{quantita(stats['num_assegnazioni'], 'assegnazione totale', 'assegnazioni totali')}"
            )

            if nome_studente in stats['trio_frequenza']:
                dati_trio = stats['trio_frequenza'][nome_studente]
                count_trio = dati_trio['count']
                asseg_trio = dati_trio['assegnazioni']

                linee.append(f"  🎯 Nel trio: {self._testo_volte(count_trio)}")
                if asseg_trio:
                    asseg_str = self._elenco_assegnazioni(asseg_trio)
                    linee.append(f"     → {asseg_str}")

            if compagni:
                compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)
                linee.append("  Vicinanze registrate:")

                for compagno, dati in compagni_ordinati:
                    count = dati['count']
                    assegnazioni = dati['assegnazioni']

                    linee.append(f"    • {compagno} ({self._testo_volte(count)})")

                    if assegnazioni:
                        asseg_str = self._elenco_assegnazioni(assegnazioni)
                        linee.append(f"       → {asseg_str}")

            tutti_studenti = stats['studenti_unici']
            mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

            if mai_abbinati:
                linee.append(
                    f"  Mai insieme a ({len(mai_abbinati)}): "
                    f"{', '.join(sorted(mai_abbinati))}"
                )

        linee.append("")

        if stats['posizioni_prima_fila']:
            linee.append("📍 STUDENTI IN PRIMA FILA")
            linee.append("-" * 80)

            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({self._testo_volte(count)})")

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni)
                    linee.append(f"  → {asseg_str}")

            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                linee.append(f"\nMai in prima fila ({len(mai_prima)}): {', '.join(sorted(mai_prima))}")

            linee.append("")

        linee.append("🚫 COPPIE MAI FORMATE")
        linee.append("-" * 80)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            verbo = "Trovata" if len(coppie_mai_formate) == 1 else "Trovate"
            linee.append(
                f"{verbo} "
                f"{quantita(len(coppie_mai_formate), 'coppia mai formata', 'coppie mai formate')}:"
            )
            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:50], 1):
                linee.append(f"{idx:2d}. {nome1} - {nome2}")

            if len(coppie_mai_formate) > 50:
                residue = len(coppie_mai_formate) - 50
                linee.append(
                    "... e "
                    + (
                        "un’altra coppia"
                        if residue == 1
                        else f"altre {residue} coppie"
                    )
                )
        else:
            linee.append(
                "✅ Ogni studente è stato vicino almeno una volta a tutti gli altri!"
            )

        linee.append("")
        linee.append("=" * 80)
        linee.append(f"Report generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        linee.append("=" * 80)

        return "\n".join(linee)


    def _calcola_tutte_statistiche(self, assegnazioni_filtrate, nome_filtro):
        """Aggrega assegnazioni, vicinanze, trio e posizioni per la classe."""
        print(f"   🔢 Calcolo statistiche per {len(assegnazioni_filtrate)} assegnazioni...")

        # La deduplicazione usa l’indice reale nello Storico, non il nome visibile.
        stats = {
            'nome_filtro': nome_filtro,
            'num_assegnazioni': len(assegnazioni_filtrate),
            'prima_data': None,
            'ultima_data': None,
            'studenti_unici': set(),
            'coppie_frequenza': {},
            'trio_frequenza': {},
            'dettaglio_studenti': {},
            'posizioni_prima_fila': {},

            '_registrazioni_viste': set(),
        }

        if assegnazioni_filtrate:
            stats['prima_data'] = assegnazioni_filtrate[0]['data_creazione'].split()[0]
            stats['ultima_data'] = assegnazioni_filtrate[-1]['data_creazione'].split()[0]

        for indice_assegnazione, assegnazione in enumerate(
                assegnazioni_filtrate):
            chiave_assegnazione = indice_assegnazione
            layout = assegnazione.get('layout', [])
            nome_assegnazione = assegnazione.get('nome', 'Senza nome')
            nome_abbr = abbrevia_nome_assegnazione(nome_assegnazione)

            # Nei terzetti le relazioni provengono dai gruppi ordinati, non dal layout.
            if assegnazione['modo'] == 'terzetti':
                for gruppo in assegnazione.get('gruppi', []):
                    membri = gruppo.get('membri', [])
                    # Contano soltanto le coppie consecutive: gli estremi non sono vicini.
                    for nome_a, nome_b in zip(membri, membri[1:]):
                        self._registra_coppia_in_stats(
                            stats,
                            nome_a,
                            nome_b,
                            nome_abbr,
                            chiave_assegnazione
                        )
                # Il layout resta necessario per studenti e posizioni fisiche.

            for studente_info in layout:
                nome = studente_info['studente']
                tipo = studente_info.get('tipo')

                stats['studenti_unici'].add(nome)

                if nome not in stats['dettaglio_studenti']:
                    stats['dettaglio_studenti'][nome] = {'compagni': {}}

                if tipo == 'coppia':
                    compagno = studente_info.get('compagno')
                    if compagno:
                        self._registra_coppia_in_stats(
                            stats,
                            nome,
                            compagno,
                            nome_abbr,
                            chiave_assegnazione
                        )

                elif tipo == 'trio':
                    if nome not in stats['trio_frequenza']:
                        stats['trio_frequenza'][nome] = {
                            'count': 0,
                            'assegnazioni': []
                        }

                    marcatore_trio = (
                        'trio',
                        nome,
                        chiave_assegnazione
                    )
                    if marcatore_trio not in stats['_registrazioni_viste']:
                        stats['_registrazioni_viste'].add(
                            marcatore_trio
                        )
                        stats['trio_frequenza'][nome]['count'] += 1
                        stats['trio_frequenza'][nome]['assegnazioni'].append(
                            nome_abbr
                        )

                    # Nel trio si registrano una volta sola le adiacenze primo-centrale e centrale-terzo.
                    if studente_info.get('posizione_trio') == 'centrale':
                        for compagno_trio in studente_info.get(
                                'compagni_trio', []):
                            self._registra_coppia_in_stats(
                                stats,
                                nome,
                                compagno_trio,
                                nome_abbr,
                                chiave_assegnazione
                            )

                elif tipo == 'fisso':
                    # L’adiacenza FISSO-vicino compare soltanto nella voce del FISSO.
                    adiacente = studente_info.get('adiacente')
                    if adiacente:
                        self._registra_coppia_in_stats(
                            stats,
                            nome,
                            adiacente,
                            nome_abbr,
                            chiave_assegnazione
                        )

                # La prima fila dipende dalla posizione fisica, non dal tipo di gruppo.
                riga = studente_info.get('riga', -1)

                if riga == 2:
                    if nome not in stats['posizioni_prima_fila']:
                        stats['posizioni_prima_fila'][nome] = {
                            'count': 0,
                            'assegnazioni': []
                        }

                    marcatore_prima_fila = (
                        'prima_fila',
                        nome,
                        chiave_assegnazione
                    )
                    if marcatore_prima_fila not in stats['_registrazioni_viste']:
                        stats['_registrazioni_viste'].add(
                            marcatore_prima_fila
                        )
                        stats['posizioni_prima_fila'][nome]['count'] += 1
                        stats['posizioni_prima_fila'][nome]['assegnazioni'].append(
                            nome_abbr
                        )

        stats.pop('_registrazioni_viste', None)

        print(
            f"   ✅ Statistiche calcolate: "
            f"{len(stats['studenti_unici'])} studenti, "
            f"{len(stats['coppie_frequenza'])} coppie uniche"
        )

        return stats

    def _registra_coppia_in_stats(
            self, stats, nome_a, nome_b, nome_abbr,
            chiave_assegnazione):
        """
        Registra una vicinanza una sola volta per assegnazione.
        
        Aggiorna simmetricamente sia il conteggio globale sia il dettaglio dei due
        studenti, anche quando la relazione compare in una sola voce dello Storico.
        """
        if not nome_a or not nome_b or nome_a == nome_b:
            return

        chiave_coppia = tuple(sorted((nome_a, nome_b)))
        marcatore = (
            'vicinanza',
            chiave_coppia,
            chiave_assegnazione
        )

        # Una relazione vale una volta per voce storica, anche se emerge da più sorgenti.
        if marcatore in stats['_registrazioni_viste']:
            return
        stats['_registrazioni_viste'].add(marcatore)

        if chiave_coppia not in stats['coppie_frequenza']:
            stats['coppie_frequenza'][chiave_coppia] = {
                'count': 0,
                'assegnazioni': []
            }

        dati_coppia = stats['coppie_frequenza'][chiave_coppia]
        dati_coppia['count'] += 1
        dati_coppia['assegnazioni'].append(nome_abbr)

        # Il dettaglio viene aggiornato simmetricamente per entrambi gli studenti.
        for primo, secondo in (
                (nome_a, nome_b),
                (nome_b, nome_a)):
            if primo not in stats['dettaglio_studenti']:
                stats['dettaglio_studenti'][primo] = {
                    'compagni': {}
                }

            compagni = stats['dettaglio_studenti'][primo]['compagni']

            if secondo not in compagni:
                compagni[secondo] = {
                    'count': 0,
                    'assegnazioni': []
                }

            compagni[secondo]['count'] += 1
            compagni[secondo]['assegnazioni'].append(
                nome_abbr
            )


    def _mostra_statistiche_complete(self, stats, nome_filtro):
        """Costruisce la vista completa delle statistiche."""
        group_riepilogo = QGroupBox("RIEPILOGO GENERALE")
        self._applica_stile_titolo_sezione(group_riepilogo)
        layout_riepilogo = QVBoxLayout(group_riepilogo)

        label_filtro = QLabel(
            f"<b>Classe:</b> {escape(str(nome_filtro))}"
        )
        layout_riepilogo.addWidget(label_filtro)

        etichetta_assegnazioni = (
            "Assegnazione totale"
            if stats['num_assegnazioni'] == 1
            else "Assegnazioni totali"
        )
        label_assegnazioni = QLabel(
            f"<b>{etichetta_assegnazioni}:</b> {stats['num_assegnazioni']}"
        )
        layout_riepilogo.addWidget(label_assegnazioni)

        if stats['prima_data']:
            label_date = QLabel(
                "<b>Periodo:</b> dal "
                f"{escape(str(stats['prima_data']))} al "
                f"{escape(str(stats['ultima_data']))}"
            )
            layout_riepilogo.addWidget(label_date)

        numero_studenti = len(stats['studenti_unici'])
        etichetta_studenti = (
            "Studente coinvolto" if numero_studenti == 1 else "Studenti coinvolti"
        )
        label_studenti = QLabel(
            f"<b>{etichetta_studenti}:</b> {numero_studenti}"
        )
        layout_riepilogo.addWidget(label_studenti)

        self.layout_statistiche_content.addWidget(group_riepilogo)

        group_coppie = QGroupBox("COPPIE PIÙ FREQUENTI (fino a 10)")
        self._applica_stile_titolo_sezione(group_coppie)
        layout_coppie = QVBoxLayout(group_coppie)

        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                label_coppia = QLabel(
                    f"<b>{idx:2d}.</b> {self._nome_studente_html(nome1)} "
                    f"<b>+</b> {self._nome_studente_html(nome2)} "
                    f"<b>({self._testo_volte(count)})</b>"
                )
                label_coppia.setTextFormat(Qt.RichText)
                label_coppia.setStyleSheet("padding-left: 10px;")
                layout_coppie.addWidget(label_coppia)

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni, html=True)

                    label_asseg = QLabel(f"     → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_coppie.addWidget(label_asseg)
        else:
            label_vuoto = QLabel("Nessuna coppia registrata")
            label_vuoto.setStyleSheet(f"color: {C('testo_placeholder')}; font-style: italic; padding-left: 10px;")
            layout_coppie.addWidget(label_vuoto)

        self.layout_statistiche_content.addWidget(group_coppie)

        if stats['trio_frequenza']:
            group_trio = QGroupBox("STATISTICHE TRIO")
            self._applica_stile_titolo_sezione(group_trio)
            layout_trio = QVBoxLayout(group_trio)

            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                label_trio = QLabel(
                    f"• {self._nome_studente_html(nome)} "
                    f"<b>({self._testo_volte(count, ' nel trio')})</b>"
                )
                label_trio.setTextFormat(Qt.RichText)
                label_trio.setStyleSheet("padding-left: 10px;")
                layout_trio.addWidget(label_trio)

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni, html=True)

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_trio.addWidget(label_asseg)

            self.layout_statistiche_content.addWidget(group_trio)

        group_dettaglio = QGroupBox("DETTAGLIO PER STUDENTE")
        self._applica_stile_titolo_sezione(group_dettaglio)
        layout_dettaglio = QVBoxLayout(group_dettaglio)

        label_istruzione = QLabel(
            "Seleziona uno studente per vedere le vicinanze registrate:"
        )
        label_istruzione.setStyleSheet(f"font-style: italic; color: {C('testo_info')};")
        layout_dettaglio.addWidget(label_istruzione)

        # Il ComboBox protetto evita cambi involontari durante lo scorrimento.
        combo_studenti = ComboBoxProtetto()
        combo_studenti.addItem("-- Seleziona uno studente --", None)
        for nome in sorted(stats['studenti_unici']):
            combo_studenti.addItem(nome, nome)
        combo_studenti.setStyleSheet(f"""
            QComboBox {{
                padding: 6px;
                border: 2px solid {C("bordo_normale")};
                border-radius: 4px;
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                font-weight: normal;
            }}
            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                font-weight: normal;
                selection-background-color: {C("accento")};
                selection-color: {C('selezione_testo')};
                border: 1px solid {C("bordo_leggero")};
            }}
        """)
        layout_dettaglio.addWidget(combo_studenti)

        self.area_dettaglio_studente = QWidget()
        layout_area_dettaglio = QVBoxLayout(self.area_dettaglio_studente)
        layout_dettaglio.addWidget(self.area_dettaglio_studente)

        combo_studenti.currentIndexChanged.connect(
            lambda: self._mostra_dettaglio_studente(
                combo_studenti.currentData(),
                stats
            )
        )

        self.layout_statistiche_content.addWidget(group_dettaglio)

        if stats['posizioni_prima_fila']:
            group_prima = QGroupBox("STUDENTI IN PRIMA FILA")
            self._applica_stile_titolo_sezione(group_prima)
            layout_prima = QVBoxLayout(group_prima)

            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                label_pos = QLabel(
                    f"• {self._nome_studente_html(nome)} "
                    f"<b>({self._testo_volte(count)})</b>"
                )
                label_pos.setTextFormat(Qt.RichText)
                label_pos.setStyleSheet("padding-left: 10px;")
                layout_prima.addWidget(label_pos)

                if assegnazioni:
                    asseg_str = self._elenco_assegnazioni(assegnazioni, html=True)

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_prima.addWidget(label_asseg)

            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                label_mai = QLabel(f"\n<b>Mai in prima fila ({len(mai_prima)}):</b>")
                layout_prima.addWidget(label_mai)

                for nome in sorted(mai_prima):
                    label_nome = QLabel(
                        f"  • {self._nome_studente_html(nome)}"
                    )
                    label_nome.setTextFormat(Qt.RichText)
                    label_nome.setStyleSheet(
                        f"color: {C('testo_arancione')}; "
                        "padding-left: 20px; font-weight: normal;"
                    )
                    layout_prima.addWidget(label_nome)

            self.layout_statistiche_content.addWidget(group_prima)

        group_mai = QGroupBox("COPPIE MAI FORMATE")
        self._applica_stile_titolo_sezione(group_mai)
        layout_mai = QVBoxLayout(group_mai)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            verbo = "Trovata" if len(coppie_mai_formate) == 1 else "Trovate"
            limite_testo = (
                " (mostrando le prime 20)"
                if len(coppie_mai_formate) > 20
                else ""
            )
            label_info = QLabel(
                f"{verbo} "
                f"{quantita(len(coppie_mai_formate), 'coppia mai formata', 'coppie mai formate')}"
                f"{limite_testo}:"
            )
            label_info.setStyleSheet("font-style: italic;")
            layout_mai.addWidget(label_info)

            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:20], 1):
                label_coppia_mai = QLabel(
                    f"<b>{idx:2d}.</b> {self._nome_studente_html(nome1)} "
                    f"– {self._nome_studente_html(nome2)}"
                )
                label_coppia_mai.setTextFormat(Qt.RichText)
                label_coppia_mai.setStyleSheet(
                    f"padding-left: 10px; color: {C('testo_negativo')};"
                )
                layout_mai.addWidget(label_coppia_mai)
        else:
            riga_completo = QWidget()
            layout_completo = QHBoxLayout(riga_completo)
            layout_completo.setContentsMargins(10, 0, 0, 0)
            layout_completo.setSpacing(8)
            icona_completo = QLabel()
            icona_completo.setFixedSize(22, 22)
            applica_icona_etichetta(icona_completo, "circle-check", 18)
            layout_completo.addWidget(icona_completo)
            label_completo = QLabel(
                "Ogni studente è stato vicino almeno una volta a tutti gli altri!"
            )
            label_completo.setStyleSheet(f"color: {C('accento')};")
            layout_completo.addWidget(label_completo, 1)
            layout_mai.addWidget(riga_completo)

        self.layout_statistiche_content.addWidget(group_mai)

        self.layout_statistiche_content.addStretch()


    def _mostra_dettaglio_studente(self, nome_studente, stats):
        """Mostra frequenze e assegnazioni di un singolo studente."""
        while self.area_dettaglio_studente.layout().count():
            child = self.area_dettaglio_studente.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not nome_studente:
            return

        dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
        compagni = dettagli.get('compagni', {})

        if not compagni:
            label_vuoto = QLabel("Nessun dato disponibile per questo studente")
            label_vuoto.setStyleSheet(f"color: {C('testo_placeholder')}; font-style: italic;")
            self.area_dettaglio_studente.layout().addWidget(label_vuoto)
            return

        label_header = QLabel(
            f"{self._nome_studente_html(nome_studente)}: "
            f"<b>{quantita(stats['num_assegnazioni'], 'assegnazione totale', 'assegnazioni totali')}</b>"
        )
        label_header.setTextFormat(Qt.RichText)
        label_header.setStyleSheet("font-size: 13px; margin-top: 10px;")
        self.area_dettaglio_studente.layout().addWidget(label_header)

        if nome_studente in stats['trio_frequenza']:
            dati_trio = stats['trio_frequenza'][nome_studente]
            count_trio = dati_trio['count']
            asseg_trio = dati_trio['assegnazioni']

            riga_trio_info = QWidget()
            layout_trio_info = QHBoxLayout(riga_trio_info)
            layout_trio_info.setContentsMargins(10, 0, 0, 0)
            layout_trio_info.setSpacing(8)
            icona_trio_info = QLabel()
            icona_trio_info.setFixedSize(20, 20)
            applica_icona_etichetta(icona_trio_info, "chart-column", 16)
            layout_trio_info.addWidget(icona_trio_info)
            label_trio_info = QLabel(f"Nel trio: {self._testo_volte(count_trio)}")
            label_trio_info.setStyleSheet(
                f"color: {C('testo_arancione')}; font-weight: bold;"
            )
            layout_trio_info.addWidget(label_trio_info, 1)
            self.area_dettaglio_studente.layout().addWidget(riga_trio_info)

            if asseg_trio:
                asseg_str = self._elenco_assegnazioni(asseg_trio, html=True)

                label_trio_asseg = QLabel(f"     → {asseg_str}")
                label_trio_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_arancione')}; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_trio_asseg)

        compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)

        label_compagni = QLabel("<b>Vicinanze registrate:</b>")
        label_compagni.setStyleSheet("margin-top: 5px;")
        self.area_dettaglio_studente.layout().addWidget(label_compagni)

        for compagno, dati in compagni_ordinati:
            count = dati['count']
            assegnazioni = dati['assegnazioni']

            label_comp = QLabel(
                f"  • {self._nome_studente_html(compagno)} "
                f"<b>({self._testo_volte(count)})</b>"
            )
            label_comp.setTextFormat(Qt.RichText)
            self.area_dettaglio_studente.layout().addWidget(label_comp)

            if assegnazioni:
                asseg_str = self._elenco_assegnazioni(assegnazioni, html=True)

                label_asseg = QLabel(f"     → {asseg_str}")
                label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_asseg)

        tutti_studenti = stats['studenti_unici']
        mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

        if mai_abbinati:
            label_mai = QLabel(
                f"\n<b>Mai insieme a ({len(mai_abbinati)}):</b>"
            )
            label_mai.setStyleSheet(f"color: {C('testo_negativo')};")
            self.area_dettaglio_studente.layout().addWidget(label_mai)

            for nome in sorted(mai_abbinati):
                label_nome_mai = QLabel(
                    f"  • {self._nome_studente_html(nome)}"
                )
                label_nome_mai.setTextFormat(Qt.RichText)
                label_nome_mai.setStyleSheet(
                    f"color: {C('testo_negativo')}; font-weight: normal;"
                )
                self.area_dettaglio_studente.layout().addWidget(label_nome_mai)


    def _trova_coppie_mai_formate(self, stats):
        """Restituisce le coppie di studenti mai risultate vicine."""
        studenti = list(stats['studenti_unici'])
        coppie_formate = set(stats['coppie_frequenza'].keys())

        coppie_mai = []

        for i in range(len(studenti)):
            for j in range(i + 1, len(studenti)):
                coppia = tuple(sorted([studenti[i], studenti[j]]))
                if coppia not in coppie_formate:
                    coppie_mai.append(coppia)

        return coppie_mai
