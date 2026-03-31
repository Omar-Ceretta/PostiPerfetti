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
    Esportazione Excel e report TXT.

    Contiene la classe EsportazioneMixin con i metodi per generare file
    Excel (.xlsx) e report testuali delle assegnazioni:

    • _estrai_nome_completo_da_id()   → Converte ID "Cognome_Nome" in nome leggibile
    • _aggiorna_report_testuale()     → Genera report completo + evidenzia coppie riutilizzate
    • esporta_excel()                 → Dialog salvataggio + crea file Excel
    • esporta_report_txt()            → Dialog salvataggio + scrive file TXT
    • crea_file_excel()              → Core generazione Excel con xlsxwriter

    USO (Mixin Pattern):
        from moduli.esportazione import EsportazioneMixin
        class FinestraPostiPerfetti(QMainWindow, StatisticheMixin, StiliMixin, EsportazioneMixin):
"""

from datetime import datetime

from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

# Importa funzioni di utilità
from moduli.utilita import pulisci_nome_file, mostra_popup_file_salvato
from moduli.tema import C


class EsportazioneMixin:
    """
    Mixin che aggiunge le funzionalità di esportazione a FinestraPostiPerfetti.

    Attributi usati da self (devono esistere nella classe principale):
        - self.input_nome_classe        (QLineEdit)
        - self.studenti                 (list di Student)
        - self.ultimo_assegnatore       (AssegnatorePosti o None)
        - self.config_app               (ConfigurazioneApp)
        - self.text_report              (QTextEdit)
        - self._mostra_errore()         (metodo della classe principale)
    """

    # =================================================================
    # UTILITÀ — Conversione ID studente → nome completo leggibile
    # =================================================================

    def _estrai_nome_completo_da_id(self, id_univoco: str) -> str:
        """
        Estrae il nome completo dall'identificatore univoco.

        Gestisce DUE formati possibili:
        - "Cognome_Nome" (dati "vivi" dall'algoritmo, es: "Colombo_Giulio Maria")
        - "Cognome Nome" (dati ricostruiti dallo storico, es: "Colombo Giulio Maria")

        Args:
            id_univoco: ID studente in uno dei due formati

        Returns:
            Nome completo formattato (es: "Colombo Giulio Maria")
        """
        if '_' in id_univoco:
            # Formato Cognome_Nome → separa al primo underscore
            cognome, nome = id_univoco.split('_', 1)
            return f"{cognome} {nome}"
        else:
            return id_univoco

    # =================================================================
    # REPORT TESTUALE — Generazione + evidenziazione coppie riutilizzate
    # =================================================================

    def _aggiorna_report_testuale(self, assegnatore):
        """Aggiorna il report testuale con dettagli dell'assegnazione."""

        report = []

        # Header
        report.append("🎓 REPORT ASSEGNAZIONE AUTOMATICA POSTI")
        report.append("=" * 60)
        report.append(f"Classe: {self.input_nome_classe.text()}")
        report.append(f"Data/Ora: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        report.append(f"Studenti elaborati: {len(self.studenti)}")

        # Riga identificativa: classe + data (sarà completata col nome
        # assegnazione dopo il salvataggio tramite _aggiorna_riga_identificativa_report)
        nome_classe = self.input_nome_classe.text()
        data_oggi = datetime.now().strftime('%d/%m/%Y')
        self._riga_identificativa_report = f"{nome_classe} - {data_oggi}"
        report.append(self._riga_identificativa_report)

        report.append("")

        # Statistiche generali - categorie allineate 1:1 con le etichette
        # che l'utente vede nel report dettagliato di ogni coppia
        report.append("📊 STATISTICHE GENERALI")
        report.append("-" * 30)
        report.append(f"Coppie totali: {len(assegnatore.coppie_formate)}")
        report.append(f"Coppie ottimali: {assegnatore.stats['coppie_ottimali']}")
        report.append(f"Coppie buone: {assegnatore.stats['coppie_buone']}")
        report.append(f"Coppie accettabili: {assegnatore.stats['coppie_accettabili']}")
        report.append(f"Coppie problematiche: {assegnatore.stats['coppie_problematiche']}")
        if assegnatore.stats['coppie_critiche'] > 0:
            report.append(f"Coppie critiche: {assegnatore.stats['coppie_critiche']}")
        report.append(f"Coppie riutilizzate: {assegnatore.stats['coppie_riutilizzate']}")
        # Aggiungi informazioni sul trio se presente
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            report.append(f"Trio formato: 1 ({len(assegnatore.trio_identificato)} studenti)")
        report.append("")

        # === SEZIONE STUDENTE CON POSIZIONE FISSA ===
        # Mostra informazioni sul FISSO e sul compagno adiacente (col 1).
        # Nessun riferimento a certificazioni per privacy e inclusione.
        # Legge direttamente dalla griglia per essere affidabile in tutti i casi
        # (coppia adiacente, trio adiacente, ecc.)
        if hasattr(assegnatore, 'studente_fisso') and assegnatore.studente_fisso:
            report.append("📌 POSIZIONE FISSA")
            report.append("-" * 30)
            report.append(f"📌 {assegnatore.studente_fisso.get_nome_completo()} (POSIZIONE FISSA)")
            report.append(f"   Posizione: primo banco a sinistra, prima fila")

            # Legge chi è adiacente al FISSO direttamente dalla griglia
            # La prima fila di banchi è in riga 2 (riga 0=arredi, riga 1=vuota)
            banchi_prima_fila = assegnatore.configurazione_aula.get_banchi_per_fila()
            if banchi_prima_fila and banchi_prima_fila[0]:
                # Cerca banchi con colonne consecutive a partire da col 1
                # (col 0 = FISSO, col 1 = adiacente diretto, col 2-3 = compagni)
                adiacenti = []
                colonna_attesa = 1  # Parto dalla colonna subito dopo il FISSO
                for banco in banchi_prima_fila[0]:
                    if banco.colonna == colonna_attesa and banco.occupato_da:
                        nome = self._estrai_nome_completo_da_id(banco.occupato_da)
                        adiacenti.append(nome)
                        colonna_attesa += 1
                    elif banco.colonna > colonna_attesa:
                        # Gap nelle colonne → fine del blocco adiacente
                        break

                if adiacenti:
                    report.append(f"   Adiacente diretto: {adiacenti[0]}")
                    for nome in adiacenti[1:]:
                        report.append(f"   Compagno blocco: {nome}")

            report.append("")

        # Dettaglio trio se presente
        if hasattr(assegnatore, 'trio_identificato') and assegnatore.trio_identificato:
            report.append("👥 TRIO FORMATO")
            report.append("-" * 30)

            trio = assegnatore.trio_identificato
            punteggio_trio = assegnatore._valuta_trio(trio)

            # Valuta ogni coppia interna al trio
            nomi_trio = [s.get_nome_completo() for s in trio]
            report.append(f"Trio: {' + '.join(nomi_trio)}")
            report.append(f"Punteggio totale: {punteggio_trio}")

            # Analizza SOLO le 2 coppie fisicamente adiacenti nel trio
            coppie_adiacenti = [(trio[0], trio[1]), (trio[1], trio[2])]  # Solo 1-2 e 2-3
            for i, (s1, s2) in enumerate(coppie_adiacenti, 1):
                risultato = assegnatore.motore_vincoli.calcola_punteggio_coppia(s1, s2)
                report.append(f"  Coppia adiacente {i}: {s1.get_nome_completo()} + {s2.get_nome_completo()}")
                report.append(f"    Punteggio: {risultato['punteggio_totale']} - {risultato['valutazione']}")

                if risultato['note']:
                    for nota in risultato['note']:
                        report.append(f"    • {nota}")

            # Nota informativa sulla coppia non adiacente
            report.append(f"  NOTA: {trio[0].get_nome_completo()} e {trio[2].get_nome_completo()} non sono adiacenti (separati da {trio[1].get_nome_completo()})")

            report.append("")

        # Dettaglio coppie formate
        report.append("👥 COPPIE FORMATE")
        report.append("-" * 30)

        for idx, (studente1, studente2, info) in enumerate(assegnatore.coppie_formate, 1):
            report.append(f"{idx:2d}. {studente1.get_nome_completo()} + {studente2.get_nome_completo()}")
            report.append(f"    Punteggio: {info['punteggio_totale']} - {info['valutazione']}")

            if info['note']:
                for nota in info['note']:
                    report.append(f"    • {nota}")

            report.append("")

        # Layout aula testuale
        report.append("🏫 LAYOUT AULA")
        report.append("-" * 30)

        # Usa il metodo della configurazione aula per il layout testuale
        # arredi in basso, ultima fila banchi in alto
        griglia_invertita = list(reversed(assegnatore.configurazione_aula.griglia))
        # Contatore file banchi: numera dal basso (fila 1 = più vicina alla cattedra)
        num_file_banchi = sum(1 for riga in griglia_invertita
                             if any(p.tipo == 'banco' for p in riga))
        contatore_fila = num_file_banchi  # Parte dal numero più alto

        for riga in griglia_invertita:
            # Mostra solo le righe di banchi (gli arredi hanno il rendering
            # dedicato nella UI e non aggiungono informazione utile nel report)
            ha_banchi = any(p.tipo == 'banco' for p in riga)

            if ha_banchi:
                # Riga di banchi: usa contatore decrescente (ultima fila = numero più alto)
                riga_str = f"Fila {contatore_fila:2d}: "
                contatore_fila -= 1
            else:
                continue  # Salta righe arredi e righe vuote (solo corridoi)

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

            report.append(riga_str)

        # Aggiorna il widget di testo
        self.text_report.setPlainText("\n".join(report))

        # === EVIDENZIAZIONE COPPIE RIUTILIZZATE ===
        # Cerca nel report le righe relative a coppie riutilizzate e le colora in ocra/giallo

        # Formato ocra/giallo grassetto per evidenziare le righe critiche
        formato_ocra = QTextCharFormat()
        formato_ocra.setForeground(QColor(C("testo_ocra")))  # Colore ocra
        formato_ocra.setFontWeight(QFont.Bold)

        # Pattern da evidenziare: "Coppia già usata" nelle note delle coppie
        cursore = self.text_report.textCursor()
        patterns_da_evidenziare = ["Coppia già usata", "BLACKLISTATA_SOFT", "RIUTILIZZATA"]

        # Se ci sono coppie riutilizzate, evidenzia anche la riga
        # di riepilogo "Coppie riutilizzate: N" nella sezione statistiche
        if assegnatore.stats['coppie_riutilizzate'] > 0:
            patterns_da_evidenziare.append("Coppie riutilizzate:")

        for pattern in patterns_da_evidenziare:
            # Riporta il cursore all'inizio per ogni pattern
            cursore.movePosition(QTextCursor.Start)
            self.text_report.setTextCursor(cursore)

            # Cerca tutte le occorrenze del pattern nel testo
            while True:
                # Usa la funzione di ricerca del QTextEdit
                cursore = self.text_report.document().find(pattern, cursore)
                if cursore.isNull():
                    break  # Nessuna altra occorrenza trovata

                # Seleziona l'INTERA RIGA che contiene il pattern
                cursore.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                cursore.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)

                # Applica il formato ocra alla riga intera
                cursore.setCharFormat(formato_ocra)

        # Riporta il cursore all'inizio del documento (evita scroll in fondo)
        cursore_iniziale = self.text_report.textCursor()
        cursore_iniziale.movePosition(QTextCursor.Start)
        self.text_report.setTextCursor(cursore_iniziale)

    def _aggiorna_riga_identificativa_report(self, nome_assegnazione: str):
        """
        Aggiorna la riga identificativa nel report con il nome dell'assegnazione.

        Chiamato da salva_assegnazione() DOPO che l'utente ha scelto il nome.
        Cerca la riga provvisoria (es. "Classe3A - 21/03/2026") e la
        sostituisce con la versione completa (es. "Classe3A - Assegnazione 01 - 21/03/2026").

        Usa QTextCursor.find() per preservare la formattazione (evidenziazione
        coppie riutilizzate) del resto del report.
        """
        if not hasattr(self, '_riga_identificativa_report'):
            return  # Nessuna riga da aggiornare (report non ancora generato)

        riga_vecchia = self._riga_identificativa_report
        # nome_assegnazione contiene già tutto: "Classe2D - Assegnazione 02 - 21/03/2026"
        # (costruito da _chiedi_nome_assegnazione), quindi lo usiamo direttamente.
        riga_nuova = nome_assegnazione

        # Cerca la riga nel QTextEdit e la sostituisce preservando la formattazione
        doc = self.text_report.document()
        cursore = doc.find(riga_vecchia)
        if not cursore.isNull():
            cursore.insertText(riga_nuova)

        # Aggiorna il riferimento per usi futuri (es. export TXT)
        self._riga_identificativa_report = riga_nuova

    # =================================================================
    # EXPORT EXCEL — Dialog salvataggio + generazione file .xlsx
    # =================================================================

    def esporta_excel(self):
        """Esporta i risultati in formato Excel (.xlsx)."""

        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        # A questo punto il salvataggio è garantito: prendiamo il nome
        # esattamente dall'ultima assegnazione salvata nello storico.
        storico = self.config_app.config_data.get("storico_assegnazioni", [])
        ultima = storico[-1] if storico else {}
        nome_base = ultima.get("nome", self.input_nome_classe.text())

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
                self.crea_file_excel(file_path, self.ultimo_assegnatore)

                mostra_popup_file_salvato(self, "Export completato", "✅ File Excel salvato con successo!", file_path)

            except Exception as e:
                self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    # =================================================================
    # EXPORT REPORT TXT — Dialog salvataggio + scrittura file testo
    # =================================================================

    def esporta_report_txt(self):
        """Esporta il report testuale dell'assegnazione corrente in formato TXT."""
        if not self.ultimo_assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        try:
            # Nome suggerito: "NomeClasse_-_Report_-_Assegnazione_XX_-_data.txt"
            # Esempio: "Classe2D_-_Report_-_Assegnazione_02_-_21-03-2026.txt"
            storico = self.config_app.config_data.get("storico_assegnazioni", [])
            ultima = storico[-1] if storico else {}
            nome_assegnazione = ultima.get("nome", "Report")
            nome_classe = self.input_nome_classe.text()

            # nome_assegnazione contiene già "Classe2D - Assegnazione 02 - 21/03/2026"
            prefisso_classe = nome_classe + " - "
            nome_senza_classe = nome_assegnazione
            if nome_senza_classe.startswith(prefisso_classe):
                nome_senza_classe = nome_senza_classe[len(prefisso_classe):]

            nome_classe_pulito = pulisci_nome_file(nome_classe)
            nome_parte_pulita = pulisci_nome_file(nome_senza_classe)
            nome_suggerito = f"{nome_classe_pulito}_-_Report_-_{nome_parte_pulita}.txt"

            # Dialog salvataggio file
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salva Report assegnazione (.txt)",
                nome_suggerito,
                "File di testo (*.txt);;Tutti i file (*)"
            )

            if file_path:
                # Usa il report già generato nel tab Report
                report_completo = self.text_report.toPlainText()

                # Salva su file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(report_completo)

                mostra_popup_file_salvato(self, "Export completato", "✅ Report testuale salvato con successo!", file_path)

        except Exception as e:
            self._mostra_errore("Errore Export", f"Errore durante l'export:\n{str(e)}")

    # =================================================================
    # CREAZIONE FILE EXCEL — Core generazione con xlsxwriter
    # =================================================================

    def crea_file_excel(self, file_path: str, assegnatore):
        """
        Crea il file Excel con il layout dell'aula.
        Usa xlsxwriter per compatibilità nativa con Excel 2019+
        (openpyxl genera XML privo degli attributi applyFill/applyBorder
        che Excel richiede, causando bordi e colori invisibili).

        NOTA: xlsxwriter usa indici 0-based (riga 0 = prima riga, colonna 0 = A).

        Args:
            file_path: Percorso completo del file .xlsx da creare
            assegnatore: Oggetto AssegnatorePosti con i dati dell'assegnazione
        """
        import xlsxwriter

        wb = xlsxwriter.Workbook(file_path)
        ws = wb.add_worksheet("PostiPerfetti")

        # === DEFINIZIONE FORMATI (vanno creati una volta, poi riusati) ===

        # Header titolo e data
        fmt_titolo = wb.add_format({"bold": True, "font_size": 16})
        fmt_data = wb.add_format({"font_size": 11})

        # Banco occupato: sfondo verde chiaro + bordo medio + grassetto
        fmt_banco_occupato = wb.add_format({
            "bold": True,
            "font_size": 9,
            "bg_color": "#C8E6C9",
            "border": 2,  # 2 = medium (compatibile con tutte le versioni Excel)
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,  # A capo automatico per nomi lunghi
        })

        # Banco libero: sfondo grigio chiaro + bordo medio
        fmt_banco_libero = wb.add_format({
            "bg_color": "#F5F5F5",
            "border": 2,
            "align": "center",
            "valign": "vcenter",
        })

        # Arredi: sfondo colorato + grassetto + centrato (uno per tipo)
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

        # Mappa tipo arredo → (formato, etichetta)
        mappa_arredi = {
            "lim": (fmt_lim, "LIM"),
            "cattedra": (fmt_cattedra, "CATTEDRA"),
            "lavagna": (fmt_lavagna, "LAVAGNA"),
        }

        # === HEADER (B2, B3 in notazione umana → riga 1, col 1 in 0-based) ===
        ws.write(1, 1, f"«PostiPerfetti» - {self.input_nome_classe.text()}", fmt_titolo)
        ws.write(2, 1, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_data)

        # === LAYOUT AULA ===
        configurazione = assegnatore.configurazione_aula

        # Arredi in basso, ultima fila banchi in alto
        griglia_invertita = list(reversed(configurazione.griglia))

        # Filtra solo le righe con contenuto (banchi o arredi, no righe vuote)
        righe_con_contenuto = [
            riga for riga in griglia_invertita
            if any(p.tipo != 'corridoio' for p in riga)
        ]

        # Traccia le colonne con contenuto per ottimizzare le larghezze
        colonne_con_contenuto = set()
        # Traccia la riga degli arredi per l'unione celle
        riga_excel_arredi = None

        # start_row = 4 (0-based, equivale alla riga 5 in Excel)
        excel_row = 4

        for riga in righe_con_contenuto:
            # Imposta altezza riga (35 pixel) per tutti i banchi e arredi
            ws.set_row(excel_row, 35)

            for col_idx, posto in enumerate(riga):
                # +1 per lasciare colonna A vuota (margine stampa, 0-based)
                excel_col = col_idx + 1

                if posto.tipo == 'banco':
                    # --- BANCHI ---
                    if posto.occupato_da:
                        nome_completo = self._estrai_nome_completo_da_id(posto.occupato_da)
                        ws.write(excel_row, excel_col, nome_completo, fmt_banco_occupato)
                    else:
                        ws.write(excel_row, excel_col, "🪑", fmt_banco_libero)

                    colonne_con_contenuto.add(excel_col)

                elif posto.tipo in ('cattedra', 'lim', 'lavagna'):
                    # --- ARREDI ---
                    # Gli arredi vengono gestiti a coppie (es. [LIM,LIM]).
                    # Scriviamo il merge SOLO sulla prima cella della coppia.
                    # Rilevamento DINAMICO: è "prima cella" se la cella precedente
                    # nella griglia NON è dello stesso tipo (funziona con qualsiasi
                    # disposizione colonne, incluso layout trio con doppio corridoio)
                    cella_precedente = riga[col_idx - 1] if col_idx > 0 else None
                    is_prima_cella = (cella_precedente is None or cella_precedente.tipo != posto.tipo)

                    if is_prima_cella:
                        fmt_arredo, etichetta = mappa_arredi[posto.tipo]
                        # merge_range(riga_inizio, col_inizio, riga_fine, col_fine, testo, formato)
                        ws.merge_range(
                            excel_row, excel_col,
                            excel_row, excel_col + 1,
                            etichetta, fmt_arredo
                        )

                    riga_excel_arredi = excel_row
                    colonne_con_contenuto.add(excel_col)

            # Dopo ogni riga con contenuto, salta una riga per il corridoio visivo
            excel_row += 2

        # === OTTIMIZZAZIONE LARGHEZZA COLONNE ===

        # Colonna A (indice 0): margine stretto per stampa
        ws.set_column(0, 0, 2)

        # Imposta larghezze: colonne con contenuto = 18, corridoi = 3
        if colonne_con_contenuto:
            max_col = max(colonne_con_contenuto)
            for col_num in range(1, max_col + 2):  # +2 per sicurezza
                if col_num in colonne_con_contenuto:
                    ws.set_column(col_num, col_num, 18)
                else:
                    ws.set_column(col_num, col_num, 3)

        # === CONFIGURAZIONE STAMPA A4 ===
        # Orientamento orizzontale per sfruttare la larghezza del foglio
        ws.set_landscape()
        ws.set_paper(9)  # 9 = A4

        # Adatta tutto il contenuto a una singola pagina
        ws.fit_to_pages(1, 1)  # (larghezza, altezza) in numero di pagine

        # Margini ridotti per massimizzare lo spazio utile (in pollici)
        ws.set_margins(left=0.4, right=0.4, top=0.4, bottom=0.4)
        ws.set_header("", {"margin": 0.2})
        ws.set_footer("", {"margin": 0.2})

        # Fine generazione Excel
        wb.close()
