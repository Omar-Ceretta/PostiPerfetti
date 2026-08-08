# -*- coding: utf-8 -*-
"""Salvataggio del risultato Mensile nella GUI principale.

Raccoglie acquisizione del nome, registrazione transazionale nello Storico e
aggiornamento dello stato del risultato corrente. Il calcolo Mensile resta in
``flusso_mensile_ui.py``; questo modulo interviene soltanto dopo che una
disposizione è stata completata e marcata come ``DA_SALVARE``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import QInputDialog

from moduli.risultati_annuali import (
    descrivi_abbinamenti_coppie as _descrivi_abbinamenti_coppie,
    descrivi_abbinamenti_terzetti as _descrivi_abbinamenti_terzetti,
)
from moduli.utilita import applica_icona_finestra, mostra_popup_semantico
from moduli.configurazione import ESITO_SALVATAGGIO_AZZERATO


class SalvataggioMensileUIMixin:
    """Aggiunge alla finestra principale il salvataggio della Mensile."""

    def salva_assegnazione(self):
        """Salva l’ultima assegnazione completata nella modalità corretta."""

        # Guardia difensiva contro doppie callback o chiamate programmatiche:
        # lo Storico non deve poter ricevere due volte lo stesso risultato.
        if not self.sessione.mensile.non_salvata:
            if not self.sessione.mensile.ha_risultato:
                self._mostra_errore(
                    "Nessun risultato", "Esegui prima un'assegnazione."
                )
            return

        # Decide il modo che ha prodotto il risultato, non il radio che l’utente può avere cambiato dopo.
        if self.sessione.mensile.e_terzetti:
            self._salva_assegnazione_terzetti()
            return

        if not self.sessione.mensile.assegnatore:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        nome_assegnazione, ok = self._chiedi_nome_assegnazione()

        if ok and nome_assegnazione:

            self.sessione.mensile.rinomina(nome_assegnazione)
            trio_presente = getattr(self.sessione.mensile.assegnatore, 'trio_identificato', None)

            studente_fisso = getattr(self.sessione.mensile.assegnatore, 'studente_fisso', None)
            gruppo_adiacente_fisso = getattr(self.sessione.mensile.assegnatore, 'gruppo_adiacente_fisso', None)

            nome_adiacente_fisso = getattr(self.sessione.mensile.assegnatore, 'nome_adiacente_fisso', None)

            self._aggiorna_riga_identificativa_report(nome_assegnazione)

            report_completo = self.text_report.toPlainText()

            salvataggio_riuscito = self.config_app.aggiungi_assegnazione_storico(
                nome_assegnazione,
                self.sessione.mensile.assegnatore.coppie_formate,
                trio_presente,
                self.sessione.mensile.assegnatore.configurazione_aula,
                file_origine=self.sessione.mensile.file_origine,
                report_completo=report_completo,
                studente_fisso=studente_fisso,
                gruppo_adiacente_fisso=gruppo_adiacente_fisso,
                nome_adiacente_fisso=nome_adiacente_fisso,
                genere_misto=self.sessione.mensile.genere_misto,
                statistiche_generali=getattr(
                    self.sessione.mensile.assegnatore, 'statistiche_generali', []),
                metadati_casualita=(
                    self.sessione.mensile.assegnatore.esporta_metadati_casualita()
                ),
                nome_classe=self.sessione.mensile.nome_classe,
                generazione="mensile",
                data_creazione=self.sessione.mensile.data_creazione,
                progressivo=self.sessione.mensile.progressivo,
                abbinamenti=_descrivi_abbinamenti_coppie(
                    self.sessione.mensile.assegnatore
                ),
            )

            if not salvataggio_riuscito:
                if (
                    self.config_app.ultimo_esito_salvataggio
                    == ESITO_SALVATAGGIO_AZZERATO
                ):
                    mostra_popup_semantico(
                        self,
                        "Storico azzerato",
                        "Storico e rotazioni sono ripartiti da zero.",
                        "triangle-alert",
                        testo_informativo=(
                            "La disposizione corrente è ancora aperta e non è "
                            "stata salvata. Premi nuovamente «Salva "
                            "assegnazione» per registrarla come prima voce del "
                            "nuovo Storico."
                        ),
                        messaggio_in_grassetto=True,
                    )
                    return
                mostra_popup_semantico(
                    self,
                    "Assegnazione non salvata",
                    "Non è stato possibile scrivere lo Storico su disco.",
                    "circle-x",
                    testo_informativo=(
                        "La disposizione resta aperta e può essere salvata "
                        "nuovamente. Nessuna nuova voce è stata aggiunta "
                        "allo Storico."
                    ),
                    messaggio_in_grassetto=True,
                )
                return

            self.sessione.mensile.segna_salvata(
                len(self.config_app.config_data["storico_assegnazioni"]) - 1,
                nome=nome_assegnazione,
            )
            self._aggiorna_info_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()

            mostra_popup_semantico(
                self,
                "Assegnazione salvata",
                "L'assegnazione è stata salvata nello Storico.",
                "circle-check",
                testo_informativo=f"Nome: {nome_assegnazione}",
                messaggio_in_grassetto=True,
            )


            self.btn_export_excel.setEnabled(True)
            self.btn_export_excel.setToolTip("Esporta questa assegnazione in formato Excel.")
            self.btn_export_report_txt.setEnabled(True)
            self.btn_export_report_txt.setToolTip("Esporta il Report testuale di questa assegnazione.")
    def _salva_assegnazione_terzetti(self):
        """Salva nello Storico l’ultima assegnazione a terzetti."""

        dati = self.sessione.mensile.dati_terzetti
        if not dati:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        nome_assegnazione, ok = self._chiedi_nome_assegnazione()
        if not (ok and nome_assegnazione):
            return

        self.sessione.mensile.rinomina(nome_assegnazione)
        self._aggiorna_riga_identificativa_report(nome_assegnazione)
        report_completo = self.text_report.toPlainText()

        salvataggio_riuscito = self.config_app.aggiungi_assegnazione_storico_terzetti(
            nome_assegnazione,
            dati['gruppi'],
            dati['configurazione_aula'],
            file_origine=self.sessione.mensile.file_origine,
            report_completo=report_completo,
            studente_fisso=dati['studente_fisso'],
            genere_misto=self.sessione.mensile.genere_misto,
            posizione_blocco_finale=dati['posizione_blocco_finale'],
            preferenza_resto2=dati['preferenza_resto2'],
            statistiche_generali=dati.get('statistiche_generali', []),
            metadati_casualita=dati.get('metadati_casualita'),
            nome_classe=self.sessione.mensile.nome_classe,
            generazione="mensile",
            data_creazione=self.sessione.mensile.data_creazione,
            progressivo=self.sessione.mensile.progressivo,
            abbinamenti=_descrivi_abbinamenti_terzetti(dati['gruppi']),
        )

        if not salvataggio_riuscito:
            if (
                self.config_app.ultimo_esito_salvataggio
                == ESITO_SALVATAGGIO_AZZERATO
            ):
                mostra_popup_semantico(
                    self,
                    "Storico azzerato",
                    "Storico e rotazioni sono ripartiti da zero.",
                    "triangle-alert",
                    testo_informativo=(
                        "La disposizione corrente è ancora aperta e non è "
                        "stata salvata. Premi nuovamente «Salva "
                        "assegnazione» per registrarla come prima voce del "
                        "nuovo Storico."
                    ),
                    messaggio_in_grassetto=True,
                )
                return
            mostra_popup_semantico(
                self,
                "Assegnazione non salvata",
                "Non è stato possibile scrivere lo Storico su disco.",
                "circle-x",
                testo_informativo=(
                    "La disposizione resta aperta e può essere salvata "
                    "nuovamente. Nessuna nuova voce è stata aggiunta "
                    "allo Storico."
                ),
                messaggio_in_grassetto=True,
            )
            return

        self.sessione.mensile.segna_salvata(
            len(self.config_app.config_data["storico_assegnazioni"]) - 1,
            nome=nome_assegnazione,
        )
        self._aggiorna_info_storico()
        self._popola_filtro_classi()
        self._aggiorna_statistiche()

        mostra_popup_semantico(
            self,
            "Assegnazione salvata",
            "L'assegnazione è stata salvata nello Storico.",
            "circle-check",
            testo_informativo=f"Nome: {nome_assegnazione}",
            messaggio_in_grassetto=True,
        )


        self.btn_export_report_txt.setEnabled(True)
        self.btn_export_report_txt.setToolTip(
            "Esporta il Report testuale di questa assegnazione.")

        self.btn_export_excel.setEnabled(True)
        self.btn_export_excel.setToolTip(
            "Esporta la piantina di questa assegnazione in Excel.")
    def _chiedi_nome_assegnazione(self) -> tuple:
        """Propone e acquisisce il nome modificabile dell'assegnazione."""

        from PySide6.QtWidgets import QInputDialog

        nome_suggerito = self.sessione.mensile.nome
        if not nome_suggerito:
            self._mostra_errore(
                "Nessun risultato",
                "Esegui prima un'assegnazione.",
            )
            return "", False

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Nome assegnazione")
        applica_icona_finestra(dialog, "save")
        dialog.setLabelText("Inserisci un nome per questa assegnazione:")
        dialog.setTextValue(nome_suggerito)
        dialog.resize(550, 150)

        ok = dialog.exec()
        return dialog.textValue(), ok
