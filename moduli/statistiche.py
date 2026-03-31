    # =================================================================
"""
    «PostiPerfetti» v. 2.0 — Programma per l'assegnazione automatica
    dei posti degli allievi in una classe scolastica,
    con gestione di vincoli, affinità, incompatibilità,
    rotazione allievi e storico assegnazioni.

    Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD)
    Licenza: GNU GPLv3

    ▣ Questo software è libero: puoi usarlo, copiarlo, studiarlo
    e redistribuirlo liberamente.
    ▣ Se lo modifichi e redistribuisci, sei tenuto a mantenere
    l'attribuzione al creatore originale e a rendere pubblico
    il codice sorgente delle tue modifiche con la stessa licenza GPLv3.
    ▣ Questo programma è distribuito «così com'è», senza alcuna
    garanzia espressa o implicita.
"""
    # =================================================================
"""
    Calcolo e visualizzazione statistiche.

    Contiene la classe StatisticheMixin con 7 metodi:
    • _aggiorna_statistiche()            → Filtra e aggiorna la tab statistiche
    • _esporta_statistiche_txt()         → Salva statistiche in file TXT
    • _genera_testo_statistiche()        → Genera il contenuto testuale completo
    • _calcola_tutte_statistiche()       → Calcola tutte le statistiche
    • _mostra_statistiche_complete()     → Mostra le statistiche nell'interfaccia
    • _mostra_dettaglio_studente()       → Mostra dettaglio per singolo studente
    • _trova_coppie_mai_formate()        → Trova coppie mai abbinate

    USO (Mixin Pattern):
        La classe StatisticheMixin va aggiunta come classe base a FinestraPostiPerfetti:
            from moduli.statistiche import StatisticheMixin
            class FinestraPostiPerfetti(QMainWindow, StatisticheMixin):
                ...
        Questo è un "mixin": una classe che aggiunge metodi a un'altra classe.
        I metodi usano `self` perché, una volta mixata, `self` è l'istanza di
        FinestraPostiPerfetti — esattamente come se fossero definiti lì dentro.
"""

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QLabel, QGroupBox, QVBoxLayout, QWidget, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

# Importa funzioni di utilità dal modulo estratto al punto 2
from moduli.utilita import pulisci_nome_file, mostra_popup_file_salvato, abbrevia_nome_assegnazione
# Importa i colori del tema attivo
from moduli.tema import C
# Importa il ComboBox protetto dall'editor studenti
from moduli.editor_studenti import ComboBoxProtetto


class StatisticheMixin:
    """
    Mixin che aggiunge le funzionalità statistiche a FinestraPostiPerfetti.

    Un "mixin" è una classe Python che non si usa da sola, ma si aggiunge
    come ingrediente a un'altra classe. I metodi qui definiti accedono a
    `self` esattamente come se fossero scritti dentro FinestraPostiPerfetti.

    Attributi usati da self (devono esistere nella classe principale):
        - self.filtro_classe_combo      (QComboBox)
        - self.config_app               (ConfigurazioneApp)
        - self.layout_statistiche_content (QVBoxLayout)
        - self.area_dettaglio_studente  (QWidget)
    """

    # =================================================================
    # AGGIORNAMENTO STATISTICHE — Filtro per classe e ricalcolo
    # =================================================================

    def _aggiorna_statistiche(self):
        """
        Calcola e mostra le statistiche filtrate per la classe selezionata.
        Gestisce 3 stati del combo filtro:
          - "__placeholder__" → messaggio invito a selezionare una classe
          - None              → nessuna assegnazione salvata (combo vuoto)
          - stringa file      → classe specifica, mostra statistiche
        """
        print("📊 Aggiornamento statistiche...")

        # Ottiene il filtro selezionato
        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        # Pulisce layout esistente (serve in TUTTI i casi)
        while self.layout_statistiche_content.count():
            child = self.layout_statistiche_content.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # --- CASO 1: Placeholder attivo (2+ classi, nessuna selezionata) ---
        # Mostra messaggio invito coerente con lo stile dell'Editor Studenti
        if file_origine_filtro == "__placeholder__":
            print("   ⏳ Placeholder attivo: in attesa di selezione classe")
            label = QLabel(
                "NESSUNA CLASSE SELEZIONATA.\n\n"
                "📊 Seleziona una classe dal menu in alto\n"
                "per visualizzare le statistiche delle assegnazioni."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;"
            )
            self.layout_statistiche_content.addWidget(label)
            return

        # --- CASO 2: Nessuna assegnazione nello storico ---
        storico = self.config_app.config_data.get("storico_assegnazioni", [])

        if not storico:
            label = QLabel(
                "📭 NESSUNA ASSEGNAZIONE SALVATA.\n\n"
                "📊 Esegui almeno un'assegnazione e salvala\n"
                "per visualizzare e/o esportare le Statistiche."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        # --- CASO 3: Classe specifica selezionata ---
        nome_file = os.path.basename(file_origine_filtro) if file_origine_filtro else "Classe"
        print(f"   📁 Mostrando statistiche per: {nome_file}")
        nome_filtro = nome_file

        # Filtra assegnazioni per la classe selezionata
        assegnazioni_filtrate = []
        for assegnazione in storico:
            if assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            # Nessuna assegnazione per questo filtro
            label = QLabel(
                f"NESSUNA ASSEGNAZIONE PER: {nome_filtro}\n\n"
                "📊 Esegui almeno un'assegnazione per questa classe\n"
                "e salvala per visualizzare le statistiche."
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(f"color: {C('testo_grigio')}; font-size: 16px; padding: 50px;")
            self.layout_statistiche_content.addWidget(label)
            return

        print(f"   ✅ {len(assegnazioni_filtrate)} assegnazioni filtrate")

        # Calcola tutte le statistiche
        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        # Mostra le statistiche
        self._mostra_statistiche_complete(stats, nome_filtro)

    # =================================================================
    # EXPORT STATISTICHE TXT — Salvataggio su file
    # =================================================================

    def _esporta_statistiche_txt(self):
        """
        Esporta le statistiche complete in formato TXT.
        """
        # Verifica che ci siano statistiche da esportare
        indice_selezionato = self.filtro_classe_combo.currentIndex()
        if indice_selezionato < 0:
            QMessageBox.warning(self, "Nessuna statistica", "Seleziona una classe per esportare le statistiche.")
            return

        file_origine_filtro = self.filtro_classe_combo.currentData()

        # Blocca export se il placeholder è attivo (nessuna classe selezionata)
        if file_origine_filtro == "__placeholder__" or file_origine_filtro is None:
            QMessageBox.warning(
                self, "Nessuna classe selezionata",
                "Seleziona una classe dal menu a tendina\nprima di esportare le statistiche."
            )
            return

        nome_filtro = pulisci_nome_file(os.path.basename(file_origine_filtro))

        # Filtra assegnazioni per la classe selezionata
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        assegnazioni_filtrate = []
        for assegnazione in storico:
            if assegnazione.get('file_origine') == file_origine_filtro:
                assegnazioni_filtrate.append(assegnazione)

        if not assegnazioni_filtrate:
            QMessageBox.warning(self, "Nessuna assegnazione", "Nessuna assegnazione disponibile per l'export.")
            return

        # Calcola statistiche
        stats = self._calcola_tutte_statistiche(assegnazioni_filtrate, nome_filtro)

        # Genera contenuto TXT
        contenuto_txt = self._genera_testo_statistiche(stats, nome_filtro)

        # Dialog salvataggio
        data_ora = datetime.now().strftime('%Y%m%d_%H%M')
        nome_suggerito = f"Statistiche_{nome_filtro}_{data_ora}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta Statistiche (.txt)",
            nome_suggerito,
            "File di testo (*.txt);;Tutti i file (*)"
        )

        if file_path:
            try:
                # Salva file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(contenuto_txt)

                mostra_popup_file_salvato(self, "Export completato", "✅ Statistiche salvate con successo!", file_path)

            except Exception as e:
                QMessageBox.critical(self, "Errore Export", f"Errore durante il salvataggio:\n{str(e)}")

    # =================================================================
    # GENERAZIONE TESTO — Contenuto testuale completo per il file TXT
    # =================================================================

    def _genera_testo_statistiche(self, stats, nome_filtro):
        """
        Genera il contenuto testuale completo delle statistiche.

        Args:
            stats: Dizionario con statistiche calcolate
            nome_filtro: Nome classe filtrata

        Returns:
            str: Testo formattato pronto per il file
        """
        linee = []

        # Header
        linee.append("=" * 80)
        linee.append("📊 STATISTICHE ASSEGNAZIONI POSTI")
        linee.append("=" * 80)
        linee.append("")

        # === SEZIONE 1: RIEPILOGO ===
        linee.append("📋 RIEPILOGO GENERALE")
        linee.append("-" * 80)
        linee.append(f"Classe: {nome_filtro}")
        linee.append(f"Assegnazioni totali: {stats['num_assegnazioni']}")
        if stats['prima_data']:
            linee.append(f"Periodo: dal {stats['prima_data']} al {stats['ultima_data']}")
        linee.append(f"Studenti coinvolti: {len(stats['studenti_unici'])}")
        linee.append("")

        # === SEZIONE 2: COPPIE PIÙ FREQUENTI ===
        linee.append("👥 COPPIE PIÙ FREQUENTI (Top 10)")
        linee.append("-" * 80)

        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"{idx:2d}. {nome1} + {nome2} ({count} volte)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"    → {asseg_str}")
        else:
            linee.append("Nessuna coppia registrata")

        linee.append("")

        # === SEZIONE 3: STATISTICHE TRIO ===
        if stats['trio_frequenza']:
            linee.append("🎯 STATISTICHE TRIO")
            linee.append("-" * 80)

            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({count} volte nel trio)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"  → {asseg_str}")

            linee.append("")

        # === SEZIONE 4: DETTAGLIO PER STUDENTE (tutti) ===
        linee.append("🔍 DETTAGLIO PER STUDENTE")
        linee.append("-" * 80)

        for nome_studente in sorted(stats['studenti_unici']):
            dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
            compagni = dettagli.get('compagni', {})

            linee.append(f"\n{nome_studente}: {stats['num_assegnazioni']} assegnazioni totali")

            # Trio
            if nome_studente in stats['trio_frequenza']:
                dati_trio = stats['trio_frequenza'][nome_studente]
                count_trio = dati_trio['count']
                asseg_trio = dati_trio['assegnazioni']

                linee.append(f"  🎯 Nel trio: {count_trio} volte")
                if asseg_trio:
                    if len(asseg_trio) <= 5:
                        asseg_str = ", ".join(asseg_trio)
                    else:
                        asseg_str = ", ".join(asseg_trio[:5]) + f" (e altre {len(asseg_trio)-5})"
                    linee.append(f"     → {asseg_str}")

            # Compagni
            if compagni:
                compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)
                linee.append(f"  Abbinato con:")

                for compagno, dati in compagni_ordinati:
                    count = dati['count']
                    assegnazioni = dati['assegnazioni']

                    linee.append(f"    • {compagno} ({count} volte)")

                    if assegnazioni:
                        if len(assegnazioni) <= 5:
                            asseg_str = ", ".join(assegnazioni)
                        else:
                            asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                        linee.append(f"       → {asseg_str}")

            # Mai abbinati
            tutti_studenti = stats['studenti_unici']
            mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

            if mai_abbinati:
                linee.append(f"  Mai stato con ({len(mai_abbinati)}): {', '.join(sorted(mai_abbinati))}")

        linee.append("")

        # === SEZIONE 5: POSIZIONI PRIMA FILA ===
        if stats['posizioni_prima_fila']:
            linee.append("📍 STUDENTI IN PRIMA FILA")
            linee.append("-" * 80)

            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                linee.append(f"• {nome} ({count} volte)")

                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"
                    linee.append(f"  → {asseg_str}")

            # Mai in prima fila
            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                linee.append(f"\nMai in prima fila ({len(mai_prima)}): {', '.join(sorted(mai_prima))}")

            linee.append("")

        # === SEZIONE 6: COPPIE MAI FORMATE ===
        linee.append("🚫 COPPIE MAI FORMATE")
        linee.append("-" * 80)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            linee.append(f"Trovate {len(coppie_mai_formate)} coppie mai formate:")
            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:50], 1):  # Max 50 per non esagerare
                linee.append(f"{idx:2d}. {nome1} - {nome2}")

            if len(coppie_mai_formate) > 50:
                linee.append(f"... e altre {len(coppie_mai_formate) - 50} coppie")
        else:
            linee.append("✅ Tutti gli studenti sono stati abbinati almeno una volta con tutti gli altri!")

        linee.append("")
        linee.append("=" * 80)
        linee.append(f"Report generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}")
        linee.append("=" * 80)

        return "\n".join(linee)

    # =================================================================
    # CALCOLO STATISTICHE — Elaborazione dati dalle assegnazioni
    # =================================================================

    def _calcola_tutte_statistiche(self, assegnazioni_filtrate, nome_filtro):
        """
        Calcola tutte le statistiche dalle assegnazioni filtrate.
        Traccia anche in quali assegnazioni sono avvenuti gli abbinamenti.

        Returns:
            dict: Dizionario con tutte le statistiche calcolate
        """
        print(f"   🔢 Calcolo statistiche per {len(assegnazioni_filtrate)} assegnazioni...")

        stats = {
            'nome_filtro': nome_filtro,
            'num_assegnazioni': len(assegnazioni_filtrate),
            'prima_data': None,
            'ultima_data': None,
            'studenti_unici': set(),
            'coppie_frequenza': {},  # {(nome1, nome2): {'count': N, 'assegnazioni': [lista]}}
            'trio_frequenza': {},    # {nome: {'count': N, 'assegnazioni': [lista]}}
            'dettaglio_studenti': {},  # {nome: {compagni: {nome_compagno: {'count': N, 'assegnazioni': [lista]}}}}
            'posizioni_prima_fila': {}  # {nome: {'count': N, 'assegnazioni': [lista]}}
        }

        # Date prima/ultima assegnazione
        if assegnazioni_filtrate:
            stats['prima_data'] = assegnazioni_filtrate[0].get('data', 'N/A')
            stats['ultima_data'] = assegnazioni_filtrate[-1].get('data', 'N/A')

        # Analizza ogni assegnazione
        for assegnazione in assegnazioni_filtrate:
            layout = assegnazione.get('layout', [])
            nome_assegnazione = assegnazione.get('nome', 'Senza nome')
            data_assegnazione = assegnazione.get('data', '')

            # Nome abbreviato per visualizzazione
            nome_abbr = abbrevia_nome_assegnazione(nome_assegnazione, data_assegnazione)

            # Analizza layout per estrarre dati
            for studente_info in layout:
                nome = studente_info['studente']
                tipo = studente_info.get('tipo')

                # Aggiungi a studenti unici
                stats['studenti_unici'].add(nome)

                # Inizializza dettaglio studente se nuovo
                if nome not in stats['dettaglio_studenti']:
                    stats['dettaglio_studenti'][nome] = {'compagni': {}}

                # ANALISI COPPIE
                if tipo == 'coppia':
                    compagno = studente_info.get('compagno')
                    if compagno:
                        # Frequenza coppie (chiave ordinata per evitare duplicati)
                        chiave_coppia = tuple(sorted([nome, compagno]))

                        if chiave_coppia not in stats['coppie_frequenza']:
                            stats['coppie_frequenza'][chiave_coppia] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        # Incrementa count solo se non già contato in questa assegnazione
                        if nome_abbr not in stats['coppie_frequenza'][chiave_coppia]['assegnazioni']:
                            stats['coppie_frequenza'][chiave_coppia]['count'] += 1
                            stats['coppie_frequenza'][chiave_coppia]['assegnazioni'].append(nome_abbr)

                        # Dettaglio per studente
                        if compagno not in stats['dettaglio_studenti'][nome]['compagni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['count'] += 1
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni'].append(nome_abbr)

                # ANALISI TRIO
                elif tipo == 'trio':
                    if nome not in stats['trio_frequenza']:
                        stats['trio_frequenza'][nome] = {
                            'count': 0,
                            'assegnazioni': []
                        }

                    if nome_abbr not in stats['trio_frequenza'][nome]['assegnazioni']:
                        stats['trio_frequenza'][nome]['count'] += 1
                        stats['trio_frequenza'][nome]['assegnazioni'].append(nome_abbr)

                    # Anche per trio, conta i compagni (coppie virtuali adiacenti)
                    compagno = studente_info.get('compagno')
                    if compagno:
                        if compagno not in stats['dettaglio_studenti'][nome]['compagni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni']:
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['count'] += 1
                            stats['dettaglio_studenti'][nome]['compagni'][compagno]['assegnazioni'].append(nome_abbr)

                # ANALISI POSIZIONI (solo se non è trio)
                if tipo == 'coppia':
                    riga = studente_info.get('riga', -1)

                    # Prima fila = riga 2 (dopo elementi fissi)
                    if riga == 2:
                        if nome not in stats['posizioni_prima_fila']:
                            stats['posizioni_prima_fila'][nome] = {
                                'count': 0,
                                'assegnazioni': []
                            }

                        if nome_abbr not in stats['posizioni_prima_fila'][nome]['assegnazioni']:
                            stats['posizioni_prima_fila'][nome]['count'] += 1
                            stats['posizioni_prima_fila'][nome]['assegnazioni'].append(nome_abbr)

        print(f"   ✅ Statistiche calcolate: {len(stats['studenti_unici'])} studenti, {len(stats['coppie_frequenza'])} coppie uniche")

        return stats

    # =================================================================
    # VISUALIZZAZIONE STATISTICHE — Costruzione interfaccia grafica
    # =================================================================

    def _mostra_statistiche_complete(self, stats, nome_filtro):
        """
        Mostra tutte le statistiche calcolate nell'interfaccia.

        Args:
            stats: Dizionario con statistiche calcolate
            nome_filtro: Nome classe filtrata
        """
        # === SEZIONE 1: RIEPILOGO GENERALE ===
        group_riepilogo = QGroupBox("📋 RIEPILOGO GENERALE")
        group_riepilogo.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_riepilogo = QVBoxLayout(group_riepilogo)

        label_filtro = QLabel(f"<b>Classe:</b> {nome_filtro}")
        layout_riepilogo.addWidget(label_filtro)

        label_assegnazioni = QLabel(f"<b>Assegnazioni totali:</b> {stats['num_assegnazioni']}")
        layout_riepilogo.addWidget(label_assegnazioni)

        if stats['prima_data']:
            label_date = QLabel(f"<b>Periodo:</b> dal {stats['prima_data']} al {stats['ultima_data']}")
            layout_riepilogo.addWidget(label_date)

        label_studenti = QLabel(f"<b>Studenti coinvolti:</b> {len(stats['studenti_unici'])}")
        layout_riepilogo.addWidget(label_studenti)

        self.layout_statistiche_content.addWidget(group_riepilogo)

        # === SEZIONE 2: COPPIE PIÙ FREQUENTI (Top 10) ===
        group_coppie = QGroupBox("👥 COPPIE PIÙ FREQUENTI (Top 10)")
        group_coppie.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_coppie = QVBoxLayout(group_coppie)

        # Ordina coppie per frequenza (x[1] è un dict con 'count')
        coppie_ordinate = sorted(stats['coppie_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

        if coppie_ordinate:
            for idx, (coppia, dati) in enumerate(coppie_ordinate[:10], 1):
                nome1, nome2 = coppia
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale con conteggio
                label_coppia = QLabel(f"{idx:2d}. {nome1} + {nome2} ({count} volte)")
                label_coppia.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_coppie.addWidget(label_coppia)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"     → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_coppie.addWidget(label_asseg)
        else:
            label_vuoto = QLabel("Nessuna coppia registrata")
            label_vuoto.setStyleSheet(f"color: {C('testo_placeholder')}; font-style: italic; padding-left: 10px;")
            layout_coppie.addWidget(label_vuoto)

        self.layout_statistiche_content.addWidget(group_coppie)

        # === SEZIONE 3: STATISTICHE TRIO ===
        if stats['trio_frequenza']:
            group_trio = QGroupBox("🎯 STATISTICHE TRIO")
            group_trio.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
            layout_trio = QVBoxLayout(group_trio)

            # Ordina per frequenza (x[1] è un dict con 'count')
            trio_ordinato = sorted(stats['trio_frequenza'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in trio_ordinato:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale
                label_trio = QLabel(f"• {nome} ({count} volte nel trio)")
                label_trio.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_trio.addWidget(label_trio)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_trio.addWidget(label_asseg)

            self.layout_statistiche_content.addWidget(group_trio)

        # === SEZIONE 4: DETTAGLIO PER STUDENTE (con dropdown) ===
        group_dettaglio = QGroupBox("🔍 DETTAGLIO PER STUDENTE")
        group_dettaglio.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_dettaglio = QVBoxLayout(group_dettaglio)

        # Label istruzione
        label_istruzione = QLabel("Seleziona uno studente per vedere con chi è stato abbinato:")
        label_istruzione.setStyleSheet(f"font-style: italic; color: {C('testo_info')};")
        layout_dettaglio.addWidget(label_istruzione)

        # Dropdown studenti — usa ComboBoxProtetto per evitare che la rotella
        # cambi accidentalmente la selezione quando si scrolla il pannello
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
            }}
            QComboBox QAbstractItemView {{
                background-color: {C("sfondo_input")};
                color: {C("testo_principale")};
                selection-background-color: {C("accento")};
                selection-color: {C('selezione_testo')};
                border: 1px solid {C("bordo_leggero")};
            }}
        """)
        layout_dettaglio.addWidget(combo_studenti)

        # Area risultati dettaglio studente
        self.area_dettaglio_studente = QWidget()
        layout_area_dettaglio = QVBoxLayout(self.area_dettaglio_studente)
        layout_dettaglio.addWidget(self.area_dettaglio_studente)

        # Connetti dropdown per mostrare dettagli
        combo_studenti.currentIndexChanged.connect(
            lambda: self._mostra_dettaglio_studente(
                combo_studenti.currentData(),
                stats
            )
        )

        self.layout_statistiche_content.addWidget(group_dettaglio)

        # === SEZIONE 5: POSIZIONI PRIMA FILA ===
        if stats['posizioni_prima_fila']:
            group_prima = QGroupBox("📍 STUDENTI IN PRIMA FILA")
            group_prima.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
            layout_prima = QVBoxLayout(group_prima)

            # Ordina per frequenza (x[1] è un dict con 'count')
            prima_ordinata = sorted(stats['posizioni_prima_fila'].items(), key=lambda x: x[1]['count'], reverse=True)

            for nome, dati in prima_ordinata:
                count = dati['count']
                assegnazioni = dati['assegnazioni']

                # Label principale
                label_pos = QLabel(f"• {nome} ({count} volte)")
                label_pos.setStyleSheet("padding-left: 10px; font-weight: bold;")
                layout_prima.addWidget(label_pos)

                # Mostra assegnazioni (max 5)
                if assegnazioni:
                    if len(assegnazioni) <= 5:
                        asseg_str = ", ".join(assegnazioni)
                    else:
                        asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                    label_asseg = QLabel(f"   → {asseg_str}")
                    label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                    layout_prima.addWidget(label_asseg)

            # Identifica chi NON è mai stato in prima fila
            mai_prima = stats['studenti_unici'] - set(stats['posizioni_prima_fila'].keys())
            if mai_prima:
                label_mai = QLabel(f"\n<b>Mai in prima fila ({len(mai_prima)}):</b>")
                layout_prima.addWidget(label_mai)

                for nome in sorted(mai_prima):
                    label_nome = QLabel(f"  • {nome}")
                    label_nome.setStyleSheet(f"color: {C('testo_arancione')}; padding-left: 20px;")
                    layout_prima.addWidget(label_nome)

            self.layout_statistiche_content.addWidget(group_prima)

        # === SEZIONE 6: COPPIE MAI FORMATE ===
        group_mai = QGroupBox("🚫 COPPIE MAI FORMATE")
        group_mai.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout_mai = QVBoxLayout(group_mai)

        coppie_mai_formate = self._trova_coppie_mai_formate(stats)

        if coppie_mai_formate:
            # Limita a 20 per non intasare
            label_info = QLabel(f"Trovate {len(coppie_mai_formate)} coppie mai formate (mostrando le prime 20):")
            label_info.setStyleSheet("font-style: italic;")
            layout_mai.addWidget(label_info)

            for idx, (nome1, nome2) in enumerate(coppie_mai_formate[:20], 1):
                label_coppia_mai = QLabel(f"{idx:2d}. {nome1} - {nome2}")
                label_coppia_mai.setStyleSheet(f"padding-left: 10px; color: {C('testo_negativo')};")
                layout_mai.addWidget(label_coppia_mai)
        else:
            label_completo = QLabel("✅ Tutti gli studenti sono stati abbinati almeno una volta con tutti gli altri!")
            label_completo.setStyleSheet(f"color: {C('accento')}; padding-left: 10px;")
            layout_mai.addWidget(label_completo)

        self.layout_statistiche_content.addWidget(group_mai)

        # Spacer finale
        self.layout_statistiche_content.addStretch()

    # =================================================================
    # DETTAGLIO STUDENTE — Mostra abbinamenti per uno studente specifico
    # =================================================================

    def _mostra_dettaglio_studente(self, nome_studente, stats):
        """
        Mostra i dettagli di abbinamento per uno studente specifico.
        Include lista assegnazioni per ogni abbinamento.
        """
        # Pulisce area dettaglio
        while self.area_dettaglio_studente.layout().count():
            child = self.area_dettaglio_studente.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not nome_studente:
            return

        # Ottiene dati studente
        dettagli = stats['dettaglio_studenti'].get(nome_studente, {})
        compagni = dettagli.get('compagni', {})

        if not compagni:
            label_vuoto = QLabel("Nessun dato disponibile per questo studente")
            label_vuoto.setStyleSheet(f"color: {C('testo_placeholder')}; font-style: italic;")
            self.area_dettaglio_studente.layout().addWidget(label_vuoto)
            return

        # Header
        label_header = QLabel(f"<b>{nome_studente}:</b> {stats['num_assegnazioni']} assegnazioni totali")
        label_header.setStyleSheet("font-size: 13px; margin-top: 10px;")
        self.area_dettaglio_studente.layout().addWidget(label_header)

        # È stato nel trio?
        if nome_studente in stats['trio_frequenza']:
            dati_trio = stats['trio_frequenza'][nome_studente]
            count_trio = dati_trio['count']
            asseg_trio = dati_trio['assegnazioni']

            label_trio_info = QLabel(f"  🎯 Nel trio: {count_trio} volte")
            label_trio_info.setStyleSheet(f"color: {C('testo_arancione')}; font-weight: bold;")
            self.area_dettaglio_studente.layout().addWidget(label_trio_info)

            # Mostra assegnazioni trio (max 5)
            if asseg_trio:
                if len(asseg_trio) <= 5:
                    asseg_str = ", ".join(asseg_trio)
                else:
                    asseg_str = ", ".join(asseg_trio[:5]) + f" (e altre {len(asseg_trio)-5})"

                label_trio_asseg = QLabel(f"     → {asseg_str}")
                label_trio_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_arancione')}; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_trio_asseg)

        # Compagni ordinati per frequenza (x[1] è un dict)
        compagni_ordinati = sorted(compagni.items(), key=lambda x: x[1]['count'], reverse=True)

        label_compagni = QLabel(f"<b>Abbinato con:</b>")
        label_compagni.setStyleSheet("margin-top: 5px;")
        self.area_dettaglio_studente.layout().addWidget(label_compagni)

        for compagno, dati in compagni_ordinati:
            count = dati['count']
            assegnazioni = dati['assegnazioni']

            # Label principale
            label_comp = QLabel(f"  • {compagno} ({count} volte)")
            label_comp.setStyleSheet("font-weight: bold;")
            self.area_dettaglio_studente.layout().addWidget(label_comp)

            # Mostra assegnazioni (max 5)
            if assegnazioni:
                if len(assegnazioni) <= 5:
                    asseg_str = ", ".join(assegnazioni)
                else:
                    asseg_str = ", ".join(assegnazioni[:5]) + f" (e altre {len(assegnazioni)-5})"

                label_asseg = QLabel(f"     → {asseg_str}")
                label_asseg.setStyleSheet(f"padding-left: 20px; color: {C('testo_info')}; font-size: 11px;")
                self.area_dettaglio_studente.layout().addWidget(label_asseg)

        # Chi non ha mai avuto come compagno
        tutti_studenti = stats['studenti_unici']
        mai_abbinati = tutti_studenti - set(compagni.keys()) - {nome_studente}

        if mai_abbinati:
            label_mai = QLabel(f"\n<b>Mai stato con ({len(mai_abbinati)}):</b>")
            label_mai.setStyleSheet(f"color: {C('testo_negativo')};")
            self.area_dettaglio_studente.layout().addWidget(label_mai)

            for nome in sorted(mai_abbinati):
                label_nome_mai = QLabel(f"  • {nome}")
                label_nome_mai.setStyleSheet(f"color: {C('testo_negativo')};")
                self.area_dettaglio_studente.layout().addWidget(label_nome_mai)

    # =================================================================
    # COPPIE MAI FORMATE — Calcolo combinatorio
    # =================================================================

    def _trova_coppie_mai_formate(self, stats):
        """
        Trova tutte le coppie di studenti che non sono mai stati abbinati.

        Returns:
            list: Lista di tuple (nome1, nome2) di coppie mai formate
        """
        studenti = list(stats['studenti_unici'])
        coppie_formate = set(stats['coppie_frequenza'].keys())

        coppie_mai = []

        # Genera tutte le coppie possibili
        for i in range(len(studenti)):
            for j in range(i + 1, len(studenti)):
                coppia = tuple(sorted([studenti[i], studenti[j]]))
                if coppia not in coppie_formate:
                    coppie_mai.append(coppia)

        return coppie_mai
