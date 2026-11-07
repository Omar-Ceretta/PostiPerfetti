# -*- coding: utf-8 -*-
"""Salvataggio del risultato Mensile nella GUI principale.

Raccoglie acquisizione del nome, registrazione transazionale nello Storico e
aggiornamento dello stato del risultato corrente. Il calcolo Mensile resta in
``flusso_mensile_ui.py``; questo modulo interviene soltanto dopo che una
disposizione è stata completata e marcata come ``DA_SALVARE``.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from moduli.dominio.presentazione_aula_personalizzata import costruisci_configurazione_aula_personalizzata
from moduli.dominio.adozione_dragdrop_mensile import metadati_casualita_salvabili
from moduli.persistenza.risultati_annuali import descrivi_abbinamenti_personalizzata as _descrivi_abbinamenti_personalizzata
from moduli.interfaccia.utilita import applica_icona_finestra, mostra_popup_semantico
from moduli.persistenza.configurazione import ESITO_SALVATAGGIO_AZZERATO


class SalvataggioMensileUIMixin:
    """Aggiunge alla finestra principale il salvataggio della Mensile."""

    def salva_assegnazione(self):
        """Registra soltanto una proposta del Layout, una sola volta."""
        if not self.sessione.mensile.non_salvata:
            if not self.sessione.mensile.ha_risultato:
                self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return
        if not self.sessione.mensile.e_personalizzata:
            self._mostra_errore(
                "Formato non operativo",
                "La proposta corrente deve provenire dal Layout unico. "
                "Le disposizioni già salvate restano disponibili nello Storico."
            )
            return
        self._salva_assegnazione_personalizzata()

    def _salva_assegnazione_personalizzata(self):
        """Salva nello Storico il Mensile Personalizzato corrente."""

        dati = self.sessione.mensile.dati_personalizzata
        if not dati:
            self._mostra_errore("Nessun risultato", "Esegui prima un'assegnazione.")
            return

        nome_assegnazione, ok = self._chiedi_nome_assegnazione()
        if not ok:
            return
        nome_assegnazione = nome_assegnazione.strip()
        if not nome_assegnazione:
            self._mostra_errore("Nome non valido", "Inserisci un nome per l'assegnazione.")
            return

        layout_visuale = dati.get("layout_visuale")
        gruppi = dati.get("gruppi")
        collocazioni = dati.get("collocazioni")
        if layout_visuale is None or not gruppi or not collocazioni:
            self._mostra_errore(
                "Risultato incompleto",
                "La disposizione corrente non contiene tutti i dati necessari "
                "al salvataggio.",
            )
            return

        try:
            schema = layout_visuale.ricostruisci_modello().costruisci_schema()
            layout_visuale.valida_contro_schema(schema)
            dati["fotografia_generazione"].verifica_risultato(dati)
            identita_attesa = dati.get("schema_identita")
            if (
                identita_attesa is not None
                and schema.identita_semantica() != identita_attesa
            ):
                raise ValueError(
                    "La geometria congelata del risultato non coincide con lo "
                    "schema usato durante il calcolo."
                )
        except Exception as errore:
            mostra_popup_semantico(
                self,
                "Assegnazione non salvata",
                "La disposizione corrente non supera i controlli di coerenza.",
                "circle-x",
                testo_informativo=str(errore),
                messaggio_in_grassetto=True,
            )
            return

        try:
            configurazione = costruisci_configurazione_aula_personalizzata(
                layout_visuale, collocazioni,
            )
            report = self.prepara_report_personalizzata(
                gruppi, collocazioni, nome_classe=self.sessione.mensile.nome_classe,
                studenti=dati["fotografia_generazione"].crea_studenti(),
                configurazione_aula=configurazione,
                genere_misto=self.sessione.mensile.genere_misto,
                nome_assegnazione=nome_assegnazione,
                data_creazione=self.sessione.mensile.data_creazione,
                adiacenze_gia_usate=set(dati["adiacenze_prima"]),
                modificata_manualmente=bool(dati.get("modificata_manualmente")),
            )
            salvataggio_riuscito = (
                self.config_app.aggiungi_assegnazione_storico_personalizzata(
                    nome_assegnazione,
                    gruppi,
                    collocazioni,
                    schema,
                    layout_visuale,
                    file_origine=self.sessione.mensile.file_origine,
                    report_completo=report.testo,
                    genere_misto=self.sessione.mensile.genere_misto,
                    statistiche_generali=report.statistiche,
                    metadati_casualita=metadati_casualita_salvabili(dati),
                    nome_classe=self.sessione.mensile.nome_classe,
                    generazione="mensile",
                    data_creazione=self.sessione.mensile.data_creazione,
                    progressivo=self.sessione.mensile.progressivo,
                    abbinamenti=_descrivi_abbinamenti_personalizzata(gruppi),
                    modificata_manualmente=bool(dati.get("modificata_manualmente")),
                )
            )

        except Exception as errore:
            mostra_popup_semantico(
                self, "Assegnazione non salvata",
                "Non è stato possibile registrare la disposizione.", "circle-x",
                testo_informativo=str(errore), messaggio_in_grassetto=True,
            )
            return

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

        if hasattr(self, "btn_prova_dragdrop"):
            self.btn_prova_dragdrop.setEnabled(False)
        self.sessione.mensile.segna_salvata(
            len(self.config_app.config_data["storico_assegnazioni"]) - 1,
            nome=nome_assegnazione,
        )
        self._aggiorna_testo_bottone_modifica_posti()
        dati.update(
            report_completo=report.testo, configurazione_aula=configurazione,
            statistiche_generali=[dict(riga) for riga in report.statistiche],
        )
        self._configurazione_aula_personalizzata_corrente = configurazione
        self._aggiorna_visualizzazione_aula(configurazione)
        self._adotta_riepilogo_report_personalizzata(report)
        self._aggiorna_riga_identificativa_report(nome_assegnazione)
        self._aggiorna_info_storico()
        self._aggiorna_tabella_storico()
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
        self.btn_export_excel.setToolTip(
            "Esporta questa assegnazione in formato Excel."
        )
        self.btn_export_report_txt.setEnabled(True)
        self.btn_export_report_txt.setToolTip(
            "Esporta il Report testuale di questa assegnazione."
        )

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
