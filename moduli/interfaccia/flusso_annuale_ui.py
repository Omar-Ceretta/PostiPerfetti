# -*- coding: utf-8 -*-
"""Coordinamento GUI dell’elaborazione Annuale.

La fase F6 concentra qui avvio, monitoraggio, annullamento, classificazione
dei risultati e apertura dell’anteprima annuale. I motori, i worker e il
salvataggio transazionale dei mesi restano nei rispettivi moduli.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""


from PySide6.QtCore import QTimer

from moduli.calcolo.annuale import BUDGET_STAGIONI_SEC, formatta_durata
from moduli.processi.worker_annuale import SeasonWorkerProcessBridgeQ21
from moduli.persistenza.risultati_annuali import (
    EsitoRisultatoAnnuale,
    classifica_risultato_annuale,
)
from moduli.interfaccia.anteprima_annuale import AnteprimaStagioneDialog
from moduli.interfaccia.utilita import mostra_popup_semantico


class FlussoAnnualeUIMixin:
    """Coordina l’Annuale senza possedere motori o persistenza."""

    def _on_stato_annuale(self, stato: dict):
        """Memorizza lo stato corrente comunicato dal worker annuale."""
        self.sessione.annuale.aggiorna_progresso(stato)

    def _avvia_monitoraggio_annuale(
            self, numero_mesi: int, numero_stagioni_fisso=None) -> None:
        """Inizializza stato, annullamento e timer dell’Annuale Q21."""
        self.sessione.annuale.avvia(
            numero_mesi,
            numero_stagioni_fisso=numero_stagioni_fisso,
        )
        self.btn_annulla_annuale.setEnabled(True)
        self.btn_annulla_annuale.show()
        self.label_status.setText("Elaborazione delle assegnazioni annuali…")

        if not hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale = QTimer(self)
            self.timer_eta_annuale.timeout.connect(
                self._aggiorna_eta_annuale
            )
        self.timer_eta_annuale.start(500)

    def _worker_annuale_finito(self) -> None:
        """Rilascia il QThread bridge soltanto dopo il segnale ``finished``."""
        worker = self.sender()
        if getattr(self, 'season_worker', None) is worker:
            self.season_worker = None

    def _rilascia_worker_annuale_se_inattivo(self) -> None:
        """Pulisce un bridge che non e' mai partito o e' gia' terminato."""
        worker = getattr(self, 'season_worker', None)
        if worker is None:
            return
        try:
            in_esecuzione = worker.isRunning()
        except Exception:
            in_esecuzione = False
        if not in_esecuzione:
            self.season_worker = None

    def _concludi_monitoraggio_annuale(self) -> None:
        """Ferma i soli elementi UI legati al calcolo annuale."""
        if hasattr(self, 'timer_eta_annuale'):
            self.timer_eta_annuale.stop()
        self.btn_annulla_annuale.hide()
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)

    def _aggiorna_eta_annuale(self):
        """Aggiorna periodicamente stato ed attesa massima dell'Annuale."""
        testo = self.sessione.annuale.testo_attesa(
            BUDGET_STAGIONI_SEC,
            formatta_durata,
        )
        if testo:
            self.label_status.setText(testo)

    def _annulla_annuale(self):
        """Richiede l'arresto cooperativo dell'elaborazione annuale."""
        worker = getattr(self, 'season_worker', None)
        if worker is None:
            return
        if self.sessione.annuale.richiedi_annullamento():
            self.btn_annulla_annuale.setEnabled(False)
            worker.richiedi_stop()

    def _fallimento_preparazione_annuale(self, messaggio: str) -> None:
        """Ripristina la GUI se il bridge Annuale non arriva nemmeno allo start."""
        self._contesto_annuale = None
        self.season_worker = None
        self.timer_messaggi.stop()
        self._imposta_modalita_elaborazione(False)
        self._mostra_errore("Errore Assegnazione", messaggio)


    def _avvia_annuale_personalizzata(self) -> None:
        """I2b: collega l'Annuale del Layout unico al processo Q21."""
        from moduli.dominio.aula_personalizzata import (
            PostiDavantiInsufficienti,
            richiedi_zone_aula_personalizzata_valide,
        )
        schema = self.sessione.schema_personalizzato
        if schema is None:
            self._mostra_errore(
                "Layout incompleto",
                "Completa e valida il Layout prima di avviare "
                "l'Annuale."
            )
            return

        self._risultato_annuale_personalizzata_p51 = None
        num_mesi = self.spinbox_mesi.value()
        genere_misto = self.checkbox_genere_misto.isChecked()
        nome_classe = self.input_nome_classe.text() or "Classe"

        try:
            fotografia = self._fotografa_generazione_layout()
            schema = fotografia.layout.schema
            layout_visuale = fotografia.layout.istantanea_visuale
            studenti_report = fotografia.crea_studenti()
            zone = richiedi_zone_aula_personalizzata_valide(
                schema, studenti_report,
            )
            if not self._conferma_preferenza_ultima(zone):
                return
            studente_fisso_report = next(
                (s for s in studenti_report if s.nota_posizione == "FISSO"), None,
            )
            self.season_worker = SeasonWorkerProcessBridgeQ21(
                fotografia,
                self.config_app,
                num_mesi,
            )
            # Il seed effettivo resta consultabile nel terminale per i replay
            # diagnostici, non nell’etichetta di avanzamento della GUI.
            seed_effettivo = getattr(self.season_worker, "seed_principale", None)
            if seed_effettivo is not None:
                print(f"🎲 Annuale Q21 — seed principale: {seed_effettivo}", flush=True)
        except PostiDavantiInsufficienti as errore:
            self._mostra_errore('Posti DAVANTI insufficienti', str(errore))
            return
        except Exception as errore:
            self._fallimento_preparazione_annuale(
                "Impossibile preparare il processo Annuale: "
                f"{errore}"
            )
            return

        self._contesto_annuale = {
            "modo": "personalizzata",
            "worker": self.season_worker,
            "fotografia_generazione": fotografia,
            "file_origine": self.sessione.file_origine,
            "studenti_live": self.sessione.studenti,
            "schema_live": schema,
            "schema_identita": schema.identita_semantica(),
            "layout_visuale": layout_visuale,
            "num_mesi": num_mesi,
            "studenti_report": studenti_report,
            "nome_classe": nome_classe,
            "genere_misto": genere_misto,
            "studente_fisso": studente_fisso_report,
        }

        self._imposta_modalita_elaborazione(True)
        self.season_worker.status_updated.connect(self._stato_annuale_personalizzata)
        self.season_worker.stagione_completata.connect(
            self._stagione_completata_personalizzata_p51
        )
        self.season_worker.error_occurred.connect(self._errore_annuale_personalizzata)
        self.season_worker.stato_annuale_updated.connect(self._progresso_annuale_personalizzata)
        self.season_worker.finished.connect(self._worker_annuale_finito)

        self._avvia_monitoraggio_annuale(
            num_mesi,
            self.season_worker.numero_stagioni_fisso,
        )
        try:
            self.season_worker.start()
        except Exception as errore:
            self._elaborazione_fallita(
                "Impossibile avviare il processo Annuale: "
                f"{errore}",
                None,
            )

    def _stato_annuale_personalizzata(self, testo: str) -> None:
        if self._segnale_generazione_corrente(
                getattr(self, "_contesto_annuale", None), "season_worker"):
            self.label_status.setText(testo)

    def _progresso_annuale_personalizzata(self, stato: dict) -> None:
        if self._segnale_generazione_corrente(
                getattr(self, "_contesto_annuale", None), "season_worker"):
            self._on_stato_annuale(stato)

    def _errore_annuale_personalizzata(self, messaggio, report=None) -> None:
        if self._segnale_generazione_corrente(
                getattr(self, "_contesto_annuale", None), "season_worker"):
            self._elaborazione_fallita(messaggio, report)

    def _sessione_annuale_invariata(self) -> bool:
        """Il risultato deve appartenere alla fotografia e alla durata richieste."""
        contesto = getattr(self, "_contesto_annuale", None)
        return bool(contesto and contesto.get("modo") == "personalizzata"
                    and self._generazione_layout_invariata(contesto)
                    and self.spinbox_mesi.value() == contesto["num_mesi"])

    def _scarta_annuale_se_sessione_cambiata(self) -> bool:
        """Scarta un esito tardivo senza applicarlo a una nuova sessione."""
        if self._sessione_annuale_invariata():
            return False
        self._concludi_monitoraggio_annuale()
        self.sessione.annuale.segna_fallita()
        self._contesto_annuale = None
        mostra_popup_semantico(
            self,
            "Risultato non applicato",
            "La classe o la geometria sono cambiate durante il calcolo.",
            "triangle-alert",
            testo_informativo=(
                "Il risultato Annuale tardivo è stato scartato e nessun dato "
                "è stato salvato."
            ),
            messaggio_in_grassetto=True,
        )
        return True

    def _stagione_completata_personalizzata_p51(self, risultato: dict) -> None:
        """P5.2: valida, mostra e conclude l'Annuale Personalizzato."""
        if not self._segnale_generazione_corrente(
                getattr(self, "_contesto_annuale", None), "season_worker"):
            return
        if self._scarta_annuale_se_sessione_cambiata():
            return

        self._concludi_monitoraggio_annuale()
        contesto = getattr(self, "_contesto_annuale", None) or {}
        self._contesto_annuale = None
        ricevuto = classifica_risultato_annuale(risultato)

        if (ricevuto.esito == EsitoRisultatoAnnuale.ANNULLATO
                or self.sessione.annuale.annullamento_richiesto):
            self.sessione.annuale.segna_annullata()
            self._risultato_annuale_personalizzata_p51 = None
            mostra_popup_semantico(
                self,
                "Operazione annullata",
                "La preparazione annuale è stata annullata.",
                "info",
                testo_informativo=(
                    "Nulla è stato salvato: lo Storico è rimasto "
                    "esattamente com'era."
                ),
                messaggio_in_grassetto=True,
            )
            return

        if ricevuto.esito == EsitoRisultatoAnnuale.VUOTO:
            self.sessione.annuale.segna_fallita()
            self._risultato_annuale_personalizzata_p51 = None
            mostra_popup_semantico(
                self,
                "Nessuna assegnazione",
                "Non è stato preparato alcun mese.",
                "triangle-alert",
                testo_informativo="Nulla è stato salvato.",
                messaggio_in_grassetto=True,
            )
            return

        # I2b: anche dopo un messaggio IPC formalmente completo la GUI
        # deve rifiutare mesi mancanti, mesi in eccesso e chiavi incomplete.
        # Non aprire l'anteprima su una proposta diversa da quella richiesta.
        if (len(ricevuto.mesi) != contesto.get("num_mesi")
                or len((risultato or {}).get("chiavi") or ()) != contesto.get("num_mesi")):
            self.sessione.annuale.segna_fallita()
            self._risultato_annuale_personalizzata_p51 = None
            self._mostra_errore(
                "Risultato Annuale incompleto",
                "Il numero di mesi o delle chiavi non coincide con quello "
                "richiesto. Nulla è stato salvato."
            )
            return

        identita_attesa = contesto.get("schema_identita")
        info = ricevuto.info
        if info.get("schema_identita") != identita_attesa:
            self.sessione.annuale.segna_fallita()
            self._risultato_annuale_personalizzata_p51 = None
            self._mostra_errore(
                "Risultato Annuale non applicato",
                "Lo schema restituito dal processo non coincide con la "
                "fotografia del Layout usata per avviare il calcolo."
            )
            return

        for indice, mese in enumerate(ricevuto.mesi, start=1):
            if mese.get("schema_identita") != identita_attesa:
                self.sessione.annuale.segna_fallita()
                self._risultato_annuale_personalizzata_p51 = None
                self._mostra_errore(
                    "Risultato Annuale non applicato",
                    f"Il mese {indice} appartiene a uno schema "
                    "diverso da quello fotografato all'avvio."
                )
                return
            gruppi = list(mese.get("gruppi") or [])
            collocazioni = list(mese.get("collocazioni") or [])
            if not gruppi or len(collocazioni) != len(gruppi):
                self.sessione.annuale.segna_fallita()
                self._risultato_annuale_personalizzata_p51 = None
                self._mostra_errore(
                    "Risultato Annuale incompleto",
                    f"Il mese {indice} non contiene una collocazione fisica "
                    "completa per tutti i gruppi."
                )
                return
            try:
                contesto["fotografia_generazione"].verifica_risultato(mese)
            except Exception as errore:
                self.sessione.annuale.segna_fallita()
                self._risultato_annuale_personalizzata_p51 = None
                self._mostra_errore(
                    "Risultato Annuale non applicato",
                    f"Il mese {indice} non supera i controlli sulla geometria "
                    f"e sui vincoli della classe: {errore}\n\nNulla è stato salvato.",
                )
                return

        layout_visuale = contesto.get("layout_visuale")
        try:
            layout_visuale.valida_contro_schema(contesto["schema_live"])
        except Exception as errore:
            self.sessione.annuale.segna_fallita()
            self._risultato_annuale_personalizzata_p51 = None
            self._mostra_errore(
                "Fotografia Annuale non valida",
                "La geometria visuale congelata all'avvio non è più coerente "
                f"con lo schema del Layout: {errore}"
            )
            return

        risultato_memoria = dict(risultato or {})
        risultato_memoria["layout_visuale"] = layout_visuale
        self._risultato_annuale_personalizzata_p51 = risultato_memoria

        self.sessione.annuale.apri_anteprima()
        dialog = AnteprimaStagioneDialog(
            self,
            self.config_app,
            ricevuto.mesi,
            ricevuto.info,
            contesto.get("file_origine", self.sessione.file_origine),
            contesto.get("nome_classe", "Classe"),
            genere_misto=bool(contesto.get("genere_misto", False)),
            studenti=list(contesto.get("studenti_report") or []),
            studente_fisso=contesto.get("studente_fisso"),
            modo="personalizzata",
            schema_personalizzato=contesto["schema_live"],
            layout_visuale_personalizzato=layout_visuale,
        )
        dialog.exec()

        if dialog.accettato:
            self.sessione.annuale.segna_salvata()
            self._aggiorna_info_storico()
            self._aggiorna_tabella_storico()
            self._popola_filtro_classi()
            self._aggiorna_statistiche()
            self.tab_widget.setCurrentWidget(self.tab_storico)
        else:
            self.sessione.annuale.segna_scartata()


    def _gestisci_fallimento_annuale(self) -> bool:
        """Conclude lo stato Annuale fallito e segnala se era attivo."""
        if not self.sessione.annuale.in_corso:
            return False
        self.sessione.annuale.segna_fallita()
        self._contesto_annuale = None
        self._concludi_monitoraggio_annuale()
        self._rilascia_worker_annuale_se_inattivo()
        return True

