# -*- coding: utf-8 -*-
"""Coordinamento GUI della classe caricata e della sessione operativa.

Il mixin collega l'Editor alla finestra principale, protegge le assegnazioni
mensili non salvate e mantiene coerenti intestazione, controlli dell'aula e
stato della sessione. Parsing e serializzazione dei file restano nel modulo
``file_classe``; algoritmi e persistenza dello Storico non sono gestiti qui.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import os
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from moduli.persistenza.file_classe import scrivi_file_classe_atomico
from moduli.lingua import quantita
from moduli.dominio.studenti import crea_studenti_da_dati_validati
from moduli.interfaccia.tema import C
from moduli.interfaccia.utilita import (
    applica_icona,
    applica_stile_pulsante_popup,
    crea_popup_semantico,
    mostra_popup_semantico,
)


class SessioneClasseUIMixin:
    """Gestisce il ciclo GUI della classe e lo stato operativo associato."""

    def _verifica_assegnazione_prima_di_abbandonare(
        self,
        *,
        testo_azione: str,
        etichetta_distruttiva: str,
    ) -> bool:
        """Chiede come gestire un’assegnazione non salvata prima di abbandonarla."""
        if not self.sessione.mensile.non_salvata:
            return True

        dialog = crea_popup_semantico(
            self,
            "Assegnazione non salvata",
            "L'ultima assegnazione non è stata salvata nello Storico.",
            "triangle-alert",
            testo_informativo=(
                f"Se {testo_azione}, le vicinanze formate non verranno "
                "considerate nelle rotazioni future.\n\n"
                "Che cosa vuoi fare?"
            ),
            messaggio_in_grassetto=True,
        )

        btn_salva = dialog.addButton(
            "Salva assegnazione", QMessageBox.AcceptRole
        )
        btn_prosegui = dialog.addButton(
            etichetta_distruttiva, QMessageBox.DestructiveRole
        )
        btn_annulla = dialog.addButton(
            "Annulla", QMessageBox.RejectRole
        )
        applica_icona(btn_salva, "save", 18)
        applica_icona(btn_prosegui, "trash-2", 18)
        applica_stile_pulsante_popup(btn_prosegui, "distruttivo")
        applica_icona(btn_annulla, "x", 18)

        dialog.setDefaultButton(btn_salva)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()

        bottone = dialog.clickedButton()
        if bottone is None or bottone == btn_annulla:
            return False

        if bottone == btn_salva:
            self.salva_assegnazione()

            return not self.sessione.mensile.non_salvata

        return True

    def _verifica_prima_di_caricare(self) -> bool:
        """Protegge l’assegnazione corrente prima di caricare un altro file."""
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="selezioni una nuova classe adesso",
            etichetta_distruttiva="Prosegui senza salvare",
        )

    def _verifica_prima_di_chiudere_file(self) -> bool:
        """Protegge l’assegnazione corrente prima di chiudere il file."""
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="chiudi il file adesso",
            etichetta_distruttiva="Chiudi senza salvare",
        )

    def _verifica_prima_di_salvare_e_caricare(self) -> bool:
        """Protegge la proposta prima di aggiornare e ricaricare la classe."""
        return self._verifica_assegnazione_prima_di_abbandonare(
            testo_azione="salvi e ricarichi la classe adesso",
            etichetta_distruttiva="Prosegui senza salvare",
        )

    def _reset_modalita_mensile(self):
        """Ripristina la modalità mensile."""
        if hasattr(self, 'radio_mensile'):
            self.radio_mensile.setChecked(True)
        if hasattr(self, 'spinbox_mesi'):
            self.spinbox_mesi.setValue(self.DEFAULT_MESI_ANNUALE)
        if hasattr(self, 'widget_mesi_annuale'):
            self.widget_mesi_annuale.setVisible(False)

    def _ripristina_default_operativi(self):
        """Ripristina i valori operativi iniziali per una nuova classe."""
        self._reset_modalita_mensile()
        self._reset_modalita_geometria()

        if hasattr(self, 'checkbox_genere_misto'):
            self.checkbox_genere_misto.setChecked(False)


    def _imposta_visibilita_configurazione(self, attivo: bool):
        """Mostra o nasconde i controlli disponibili nello stato corrente."""
        for widget in (self.group_aula, self.group_opzioni, self.group_modalita,
                       self.btn_avvia_assegnazione):
            widget.setVisible(attivo)
            widget.setEnabled(attivo)
        self.group_aula.setVisible(True)
        self.group_aula.setEnabled(not getattr(self, "_layout_in_elaborazione", False))
        if hasattr(self, "editor_aula_personalizzata"):
            self.editor_aula_personalizzata.setEnabled(
                not getattr(self, "_layout_in_elaborazione", False)
            )

    def _on_editor_file_cambiato(self):
        """Aggiorna la finestra principale quando l’Editor carica un file."""

        aveva_classe = self.sessione.classe_caricata
        origine_editor = (
            self.editor_studenti.percorso_file
            or self.editor_studenti.nome_file
        )
        origine_precedente = getattr(self, "_origine_editor_layout", None)
        self.sessione.chiudi_classe()
        if aveva_classe or (
            origine_precedente is not None and origine_precedente != origine_editor
        ):
            self._sincronizza_editor_personalizzato(reset=True)
        self._origine_editor_layout = origine_editor

        self._ripristina_default_operativi()

        self._resetta_tab_aula_report()

        self.input_nome_classe.clear()

        self._imposta_visibilita_configurazione(False)

        if (self.editor_studenti.ha_studenti_caricati() and
                not self.editor_studenti.tutti_generi_impostati()):

            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                "NUOVA CLASSE PRESENTE NELL'EDITOR!\n"
                f"MODIFICHE NECESSARIE: "
                f"{quantita(len(mancanti), 'studente senza genere', 'studenti senza genere')}"
            )
        else:

            self.label_studenti_caricati.setText(
                "NUOVA CLASSE PRESENTE NELL'EDITOR!\n"
                "Usa «SALVA e CARICA», poi completa o verifica il Layout "
                "prima di avviare l'assegnazione."
            )
        self._applica_stile_label_stato_classe("attenzione")


        print("🔄 L'Editor ha caricato un nuovo file → dati pannello resettati")

        self.tab_widget.setCurrentWidget(self.editor_studenti)

    def _on_editor_dati_modificati(self):
        """Aggiorna lo stato della classe dopo una modifica nell’Editor."""
        self._sincronizza_editor_personalizzato(reset=False)
        if not self.editor_studenti.ha_studenti_caricati():
            return

        if not self.editor_studenti.tutti_generi_impostati():
            return

        ha_vincoli_incompleti = bool(self.editor_studenti.get_vincoli_incompleti())
        ha_modifiche_non_salvate = self.editor_studenti.ha_modifiche_non_salvate

        if ha_vincoli_incompleti or ha_modifiche_non_salvate:

            nome_file = self.editor_studenti.nome_file or ""
            self.label_studenti_caricati.setText(
                f"'{nome_file}' modificato nell'Editor!\n\n"
                f"Clicca 'SALVA e CARICA' per aggiornare."
            )
            self._applica_stile_label_stato_classe("attenzione")
        else:

            nome_file = self.editor_studenti.nome_file or ""
            self.label_studenti_caricati.setText(
                f"File '{nome_file}.txt' salvato e caricato.\n"
                "Completa o verifica il Layout prima dell'assegnazione."
            )
            self._applica_stile_label_stato_classe("successo")

    def _on_editor_genere_cambiato(self):
        """Aggiorna lo stato dei generi dopo una modifica nell’Editor."""
        self._sincronizza_editor_personalizzato(reset=False)
        if not self.editor_studenti.ha_studenti_caricati():
            return

        if self.editor_studenti.tutti_generi_impostati():

            nome_file = self.editor_studenti.nome_file or ""
            self.label_studenti_caricati.setText(
                f"'{nome_file}' pronto!\n\n"
                f"Clicca 'SALVA e CARICA' per procedere."
            )
            self._applica_stile_label_stato_classe("attenzione")
        else:

            mancanti = self.editor_studenti.get_nomi_studenti_senza_genere()
            self.label_studenti_caricati.setText(
                "Genere da impostare: "
                + quantita(len(mancanti), "studente", "studenti")
            )
            self._applica_stile_label_stato_classe("attenzione")

    def _on_editor_file_chiuso(self):
        """Azzera lo stato della classe quando l’Editor chiude il file."""

        self.sessione.chiudi_classe()
        self._origine_editor_layout = None
        self._sincronizza_editor_personalizzato(reset=True)

        self._ripristina_default_operativi()

        self._resetta_tab_aula_report()

        self.input_nome_classe.clear()

        self._imposta_visibilita_configurazione(False)

        self.label_studenti_caricati.setText(
            "NESSUN FILE CARICATO.\n\n"
            "Vai in 'Editor studenti' e clicca su 'Seleziona classe'.\n"
        )
        self._applica_stile_label_stato_classe("neutro")

    def _on_editor_file_salvato(self, percorso_file: str):
        """Carica nella finestra principale il file salvato dall’Editor."""

        self._carica_studenti_da_editor(percorso_file)

        nome_file = os.path.basename(percorso_file)
        self.label_studenti_caricati.setText(
            f"File '{nome_file}' salvato e caricato.\n"
            "Completa o verifica il Layout prima dell'assegnazione."
        )
        self._applica_stile_label_stato_classe("successo")

        self.label_status.setText("Classe salvata e caricata: verifica il Layout.")
        self.label_status.setStyleSheet(f"color: {C('testo_stato_ok')}; font-weight: bold;")
        QTimer.singleShot(10000, self, lambda: (
            self.label_status.setText("")
            if not self.timer_messaggi.isActive()
            else None
        ))

    def _carica_studenti_da_editor(self, file_path: str):
        """Crea gli oggetti Student dai dati già validati dall’Editor."""

        self._resetta_tab_aula_report()

        dati_studenti = self.editor_studenti.get_dati_tutti_studenti()

        if not dati_studenti:
            self._mostra_errore("File vuoto", "Il file selezionato non contiene studenti validi.")
            return

        studenti = crea_studenti_da_dati_validati(dati_studenti)

        self._auto_salva_file_corretto()

        self.sessione.carica_classe(
            studenti,
            Path(file_path).name,
        )
        num_studenti = len(studenti)

        verbo = "Caricato" if num_studenti == 1 else "Caricati"
        self.label_studenti_caricati.setText(
            f"{verbo} {quantita(num_studenti, 'studente', 'studenti')} "
            f"da «{Path(file_path).name}»"
        )
        self._applica_stile_label_stato_classe("successo")

        self._imposta_visibilita_configurazione(True)

        self._ripristina_default_operativi()

        nome_file = Path(file_path).stem.replace("_", " ").title()

        self.input_nome_classe.setText(nome_file)

        self._controlla_classe_gia_elaborata(nome_file)

        self._aggiorna_info_storico()

        self.tab_widget.setCurrentWidget(self.editor_studenti)

    def _auto_salva_file_corretto(self):
        """Salva le correzioni applicate dall’Editor senza bloccare i dati già caricati."""

        if not self.editor_studenti.correzioni_applicate:

            self.editor_studenti.conferma_acquisizione_classe()
            return

        percorso = self.editor_studenti.percorso_file

        if not percorso:

            print("⚠️ Auto-save: nessun percorso file disponibile")
            return

        try:

            contenuto_corretto = self.editor_studenti.genera_contenuto_file()

            scrivi_file_classe_atomico(percorso, contenuto_corretto)

            self.editor_studenti.conferma_salvataggio()

            nome_file = Path(percorso).name
            mostra_popup_semantico(
                self,
                "File salvato e pronto all'uso",
                "Il file è stato automaticamente salvato e caricato.",
                "circle-check",
                testo_informativo=(
                    f"File: {nome_file}\n"
                    f"Percorso: {percorso}\n\n"
                    "L'intera lista degli studenti è pronta per "
                    "l'assegnazione."
                ),
                messaggio_in_grassetto=True,
            )

            print(f"💾 Auto-save: file corretto salvato in '{percorso}'")

        except PermissionError:

            mostra_popup_semantico(
                self,
                "Salvataggio automatico non riuscito",
                "Il file non può essere sovrascritto.",
                "triangle-alert",
                testo_informativo=(
                    f"Il file potrebbe essere protetto:\n{percorso}\n\n"
                    "Le correzioni sono comunque attive per l'assegnazione "
                    "corrente. Puoi salvare manualmente dalla scheda Editor "
                    "studenti usando «Anteprima file classe (.txt)»."
                ),
                messaggio_in_grassetto=True,
            )

        except Exception as e:

            print(f"⚠️ Auto-save fallito: {e}")
            mostra_popup_semantico(
                self,
                "Salvataggio automatico non riuscito",
                "Si è verificato un errore durante il salvataggio automatico.",
                "triangle-alert",
                testo_informativo=(
                    f"Errore: {e}\n\n"
                    "Le correzioni sono comunque attive per l'assegnazione "
                    "corrente."
                ),
                messaggio_in_grassetto=True,
            )
