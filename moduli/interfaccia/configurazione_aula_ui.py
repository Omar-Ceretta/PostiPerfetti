# -*- coding: utf-8 -*-
"""Coordinamento GUI della configurazione dell’aula.

Gestisce il Layout unico, la sua validità e le opzioni di generazione.
Il mixin lavora sui widget e sullo StatoSessione della finestra principale;
la fotografia del Layout valida l'ingresso del calcolo.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""


from moduli.interfaccia.tema import C
from moduli.dominio.fotografia_generazione_layout import FotografiaGenerazioneLayout


def testi_opzione_genere_misto() -> tuple[str, str]:
    """Descrive la preferenza sulle vere adiacenze dei banchi da 2 e da 3."""
    return (
        "Preferisci vicinanze miste (M+F)",
        "Se attivo, dà forte preferenza alle vicinanze consecutive M+F "
        "nei gruppi.\nNon vieta vicinanze dello stesso genere se "
        "necessarie per variare le rotazioni.",
    )


class ConfigurazioneAulaUIMixin:
    """Aggiunge alla finestra principale il coordinamento dell’aula."""

    def _conferma_preferenza_ultima(self, esito_zone) -> bool:
        """Permette di correggere ULTIMA oppure proseguire senza bloccare Q21.

        Il controllo HARD di PRIMA deve essere eseguito prima di chiamare
        questo metodo. Non crea dialoghi in assenza di preferenze scoperte.
        """
        testo = esito_zone.messaggio_avviso_ultima()
        if not testo:
            return True

        from PySide6.QtWidgets import QMessageBox
        from moduli.interfaccia.utilita import crea_popup_semantico

        popup = crea_popup_semantico(
            self, "Preferenza ULTIMA: controlla il Layout", testo,
            "triangle-alert",
        )
        btn_layout = popup.addButton(
            "Torna al Layout", QMessageBox.ButtonRole.RejectRole,
        )
        btn_continua = popup.addButton(
            "Continua comunque", QMessageBox.ButtonRole.AcceptRole,
        )
        # Se l'utente preme Invio senza leggere, non parte una ricerca lunga.
        popup.setDefaultButton(btn_layout)
        popup.exec()
        if popup.clickedButton() is btn_continua:
            return True
        self._mostra_editor_aula_personalizzata()
        return False

    def _fotografa_generazione_layout(self):
        """U4: un solo ingresso completo per Mensile e Annuale."""
        if not self._classe_layout_confermata():
            raise ValueError("Conferma la classe con SALVA e CARICA.")
        foto = FotografiaGenerazioneLayout.cattura(
            self.editor_aula_personalizzata.modello, self.sessione.studenti,
            file_origine=self.sessione.file_origine,
            nome_classe=self.input_nome_classe.text() or "Classe",
            genere_misto=self.checkbox_genere_misto.isChecked(),
            griglia=self.editor_aula_personalizzata.canvas.GRIGLIA,
        )
        schema = self.sessione.schema_personalizzato
        if (self.sessione.geometria != "personalizzata" or schema is None
                or schema.identita_semantica() != foto.layout.schema.identita_semantica()):
            raise ValueError("Il Layout corrente non coincide con lo schema validato.")
        return foto

    def _generazione_layout_invariata(self, contesto):
        if (not contesto or getattr(self, "_finestra_chiusa", False)
                or self.sessione.studenti is not contesto["studenti_live"]):
            return False
        try:
            return (self._fotografa_generazione_layout().identita()
                    == contesto["fotografia_generazione"].identita())
        except (ValueError, TypeError, AttributeError, KeyError):
            return False

    def _segnale_generazione_corrente(self, contesto, attributo_worker):
        """I segnali duplicati o di un precedente bridge non toccano la GUI."""
        if not contesto or getattr(self, "_finestra_chiusa", False):
            return False
        worker = contesto["worker"]
        mittente = self.sender()
        return (getattr(self, attributo_worker, None) is worker
                and (mittente is None or mittente is worker))


    def _dati_fisso_personalizzata(self) -> tuple[bool, str | None]:
        """Restituisce presenza e nome del FISSO della classe caricata."""
        fissi = [
            studente
            for studente in self.sessione.studenti
            if studente.nota_posizione == "FISSO"
        ]
        if not fissi:
            return False, None
        return True, fissi[0].get_nome_completo()

    def _sincronizza_editor_personalizzato(self, *, reset: bool = False) -> None:
        """Allinea l'editor visuale alla classe senza coinvolgere il motore."""
        if not hasattr(self, "editor_aula_personalizzata"):
            return
        ha_fisso, nome_fisso = self._dati_fisso_personalizzata()
        numero_studenti = len(self.sessione.studenti) or None
        editor_studenti = getattr(self, "editor_studenti", None)
        if editor_studenti is not None and editor_studenti.ha_studenti_caricati():
            dati = editor_studenti.get_dati_tutti_studenti()
            numero_studenti = len(dati)
            fissi = [d for d in dati if d["posizione"] == "FISSO"]
            ha_fisso = bool(fissi)
            nome_fisso = (fissi[0]["cognome"] + " " + fissi[0]["nome"]).strip() if fissi else None
        kwargs = {
            "numero_studenti": numero_studenti,
            "ha_fisso": ha_fisso,
            "nome_fisso": nome_fisso,
        }
        if reset:
            self.sessione.azzera_schema_personalizzato()
            self.editor_aula_personalizzata.resetta_classe(**kwargs)
        else:
            self.editor_aula_personalizzata.imposta_classe(**kwargs)

    def _on_schema_personalizzato_cambiato(self, schema) -> None:
        """Registra nello StatoSessione soltanto schemi Personalizzati validi."""
        if self._classe_layout_confermata():
            self.sessione.imposta_schema_personalizzato(schema)
        else:
            self.sessione.azzera_schema_personalizzato()
        self._aggiorna_disponibilita_avvio_geometria()

    def _on_validita_personalizzata_cambiata(
        self, valida: bool, messaggio: str
    ) -> None:
        """Invalida lo snapshot se la bozza non è pronta e aggiorna il riepilogo."""
        if not valida:
            self.sessione.azzera_schema_personalizzato()
        if hasattr(self, "label_riepilogo_layout"):
            contatori = self.editor_aula_personalizzata.modello.contatori(
                numero_studenti=self.editor_aula_personalizzata.numero_studenti)
            attesi = contatori["studenti"]
            self.label_riepilogo_layout.setText(
                f"{contatori['posti']} posti / {attesi if attesi is not None else '—'} studenti\n"
                f"Banchi: {contatori['coppie']} da 2 · {contatori['terzetti']} da 3")
        if not self._classe_layout_confermata():
            valida = False
            self.sessione.azzera_schema_personalizzato()
            messaggio = "Completa la classe nell'Editor studenti e usa SALVA e CARICA."
        if hasattr(self, "label_stato_personalizzata"):
            prefisso = "Aula pronta" if valida else "Aula da completare"
            self.label_stato_personalizzata.setText(f"{prefisso}: {messaggio}")
            self.label_stato_personalizzata.setWordWrap(True)
            if valida:
                sfondo = C("label_successo_bg")
                bordo = C("label_successo_bordo")
                colore = C("label_successo_txt")
            else:
                sfondo = C("label_attenzione_bg")
                bordo = C("label_attenzione_bordo")
                colore = C("label_attenzione_txt")
            self.label_stato_personalizzata.setStyleSheet(
                "QLabel {"
                f"background-color: {sfondo}; color: {colore}; "
                f"border: 1px solid {bordo}; border-radius: 6px; "
                "padding: 7px 9px; font-weight: bold;"
                "}"
            )
        self._aggiorna_disponibilita_avvio_geometria()

    def _mostra_editor_aula_personalizzata(self) -> None:
        """Porta in primo piano la scheda visuale della geometria Personalizzata."""
        if not hasattr(self, "indice_tab_personalizzata"):
            return
        self.tab_widget.setCurrentWidget(self.editor_aula_personalizzata)

    def _aggiorna_visibilita_configurazione_geometria(self) -> None:
        """Il Layout è l’unico ingresso per la geometria della classe."""
        self.widget_configurazione_personalizzata.setVisible(True)
        self.editor_aula_personalizzata.setEnabled(
            not getattr(self, "_layout_in_elaborazione", False)
        )
        self._sincronizza_editor_personalizzato(reset=False)

    def _classe_layout_confermata(self) -> bool:
        """La capienza della bozza non abilita dati incompleti o non caricati."""
        if not self.sessione.classe_caricata:
            return False
        editor = getattr(self, "editor_studenti", None)
        return bool(editor is None or (
            not editor._modifiche_non_salvate
            and editor.tutti_generi_impostati()
            and not editor.get_vincoli_incompleti()
        ))

    def _verifica_modifica_layout(self) -> bool:
        """Protegge la proposta prima di qualunque mutazione della bozza."""
        if getattr(self, "_layout_in_elaborazione", False):
            return False
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="modifichi il Layout adesso",
            etichetta_distruttiva="Scarta e modifica Layout",
        )

    def _on_bozza_layout_modificata(self) -> None:
        """Una nuova geometria non può salvare/esportare una proposta precedente."""
        if self.sessione.mensile.modo is not None:
            self._resetta_tab_aula_report()
        self._risultato_mensile_personalizzata_p31 = None
        self._risultato_annuale_personalizzata_p51 = None
        self._aggiorna_disponibilita_avvio_geometria()


    def _aggiorna_disponibilita_avvio_geometria(self) -> None:
        """Abilita l'avvio solo quando la geometria corrente è pronta."""
        if not hasattr(self, "btn_avvia_assegnazione"):
            return
        if getattr(self, "_layout_in_elaborazione", False):
            self.btn_avvia_assegnazione.setEnabled(False)
            return
        if self.sessione.geometria == "personalizzata":
            schema_pronto = self.sessione.schema_personalizzato is not None
            annuale = bool(
                hasattr(self, "radio_annuale") and self.radio_annuale.isChecked()
            )
            abilitato = bool(
                self._classe_layout_confermata() and schema_pronto
            )
            self.btn_avvia_assegnazione.setEnabled(abilitato)
            if not self._classe_layout_confermata():
                tooltip = "Completa la classe e usa SALVA e CARICA nell’Editor studenti."
            elif not schema_pronto:
                tooltip = (
                    "Completa il Layout: il numero di posti deve "
                    "coincidere con gli studenti e l'eventuale FISSO deve avere "
                    "un posto assegnato."
                )
            elif annuale:
                tooltip = (
                    "Calcola più mesi consecutivi usando esattamente la geometria "
                    "costruita nella scheda Layout."
                )
            else:
                tooltip = (
                    "Calcola un Mensile usando esattamente la geometria "
                    "costruita nella scheda Layout."
                )
            self.btn_avvia_assegnazione.setToolTip(tooltip)
        else:
            self.btn_avvia_assegnazione.setEnabled(False)

    def _aggiorna_opzione_genere_misto(self) -> None:
        """Adegua il testo dell'opzione al tipo di adiacenza ottimizzato."""
        if not hasattr(self, "checkbox_genere_misto"):
            return
        etichetta, tooltip = testi_opzione_genere_misto()
        self.checkbox_genere_misto.setText(etichetta)
        self.checkbox_genere_misto.setToolTip(tooltip)


    def _aggiorna_disponibilita_annuale(self):
        """Il Layout consente sia Mensile sia Annuale."""
        if not hasattr(self, "radio_annuale"):
            return
        self.radio_annuale.setEnabled(True)
        self.radio_annuale.setToolTip(
            "Genera più mesi consecutivi con il Layout corrente e "
            "le vicinanze dello Storico della classe."
        )


    def _reset_modalita_geometria(self):
        """Allinea la nuova classe all'unica geometria operativa: il Layout."""
        self.sessione.imposta_geometria('personalizzata')
        self.sessione.imposta_posti_insufficienti(False)
        self._aggiorna_disponibilita_annuale()
        self._aggiorna_opzione_genere_misto()
        self._aggiorna_visibilita_configurazione_geometria()
        self._aggiorna_disponibilita_avvio_geometria()


