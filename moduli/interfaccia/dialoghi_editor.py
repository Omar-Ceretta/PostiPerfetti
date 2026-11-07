# -*- coding: utf-8 -*-
"""Dialoghi dell’Editor e selezione transazionale di un file-classe.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit,
    QMessageBox, QDialog
)
from PySide6.QtCore import Qt
import os



from moduli.persistenza.file_classe import (
    FORMATO_BASE, FORMATO_COMPLETO, FileClasseVuoto, ErroreCodificaFileClasse, ErroreValidazioneFileClasse,
    carica_file_classe,
    crea_copia_utf8_file_classe,
    chiave_nome_completo,
)


from moduli.interfaccia.utilita import (
    adatta_finestra_allo_schermo,
    applica_icona, applica_icona_applicazione_finestra,
    applica_icona_etichetta, crea_popup_semantico, mostra_popup_semantico,
    apri_file_con_applicazione_default,
)

def _popup_info(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un messaggio informativo con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "info", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_successo(parent, titolo, messaggio, *, dettagli=""):
    """Mostra una conferma con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "circle-check", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_avviso(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un avviso con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "triangle-alert", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


def _popup_errore(parent, titolo, messaggio, *, dettagli=""):
    """Mostra un errore con lo stile comune."""
    return mostra_popup_semantico(
        parent, titolo, messaggio, "circle-x", testo_informativo=dettagli,
        messaggio_in_grassetto=True,
    )


class DialogoErroreFileClasse(QDialog):
    """Mostra gli errori di un file e permette di aprirlo senza chiudere l'avviso."""

    def __init__(self, parent, titolo, percorso, dettagli):
        super().__init__(parent)
        self._percorso = os.fspath(percorso)

        self.setWindowTitle(titolo)
        applica_icona_applicazione_finestra(self)
        adatta_finestra_allo_schermo(
            self,
            larghezza_ideale=720,
            altezza_ideale=520,
            larghezza_minima=560,
            altezza_minima=360,
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intestazione = QHBoxLayout()
        icona = QLabel()
        applica_icona_etichetta(icona, "circle-x", 42)
        intestazione.addWidget(icona, 0, Qt.AlignTop)

        testo = QLabel("Il nuovo file non è stato caricato.")
        testo.setWordWrap(True)
        testo.setStyleSheet("font-size: 14px; font-weight: bold;")
        intestazione.addWidget(testo, 1)
        layout.addLayout(intestazione)

        area_errori = QTextEdit()
        area_errori.setReadOnly(True)
        area_errori.setPlainText(str(dettagli))
        area_errori.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(area_errori, 1)

        percorso_label = QLabel(f"File selezionato:\n{self._percorso}")
        percorso_label.setWordWrap(True)
        percorso_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(percorso_label)

        pulsanti = QHBoxLayout()
        pulsanti.addStretch()

        btn_apri = QPushButton("Apri file")
        applica_icona(btn_apri, "file-text", 18)
        btn_apri.setMinimumHeight(40)
        btn_apri.clicked.connect(self._apri_file)
        pulsanti.addWidget(btn_apri)

        btn_chiudi = QPushButton("Chiudi")
        applica_icona(btn_chiudi, "x", 18)
        btn_chiudi.setMinimumHeight(40)
        btn_chiudi.clicked.connect(self.accept)
        pulsanti.addWidget(btn_chiudi)

        layout.addLayout(pulsanti)

    def _apri_file(self):
        """Avvia l'applicazione predefinita senza chiudere il dialogo."""
        if apri_file_con_applicazione_default(self._percorso):
            return

        _popup_errore(
            self,
            "Apertura non riuscita",
            "Impossibile aprire automaticamente il file selezionato.",
            dettagli=(
                "Aprilo manualmente dalla cartella delle classi.\n\n"
                f"Percorso:\n{self._percorso}"
            ),
        )


def seleziona_file_classe(parent, cartella_classi):
    """Restituisce percorso e dati accettati; Annulla lascia invariata la classe."""
    percorso, _ = QFileDialog.getOpenFileName(
        parent,
        "SELEZIONA CLASSE (.txt)",
        cartella_classi,
        "File di testo (*.txt);;Tutti i file (*)",
    )
    if not percorso:
        return

    try:
        risultato = carica_file_classe(
            percorso,
            consenti_vincoli_orfani=True,
        )
    except FileClasseVuoto:
        _popup_avviso(
            parent,
            "File vuoto",
            "Il file non contiene righe utili.",
        )
        return
    except ErroreCodificaFileClasse as errore:
        DialogoErroreFileClasse(
            parent,
            "Codifica del file non supportata",
            percorso,
            f"{errore}\n\nIl nuovo file non è stato caricato.",
        ).exec()
        return
    except ErroreValidazioneFileClasse as errore:
        testo = "\n".join(f"• {voce}" for voce in errore.errori[:20])
        if len(errore.errori) > 20:
            testo += f"\n\n... e altri {len(errore.errori) - 20} errori."

        if errore.formato == FORMATO_COMPLETO:
            titolo = "File completo non valido"
            istruzione = "Correggi il file .txt e selezionalo di nuovo."
        elif errore.formato == FORMATO_BASE:
            titolo = "File base non valido"
            istruzione = "Correggi i dati indicati nel file .txt e selezionalo di nuovo."
        else:
            titolo = "Formato non valido"
            istruzione = (
                "Sono accettate righe BASE con 2 o 3 campi e righe "
                "COMPLETE con 6 campi."
            )

        DialogoErroreFileClasse(
            parent,
            titolo,
            percorso,
            f"{testo}\n\n{istruzione}",
        ).exec()
        return
    except Exception as errore:
        _popup_errore(
            parent,
            "Lettura del file non riuscita",
            "Impossibile leggere il file selezionato.",
            dettagli=str(errore),
        )
        return

    if risultato.get("conversione_utf8_disponibile"):
        codifica = risultato.get("codifica_sorgente", "UTF-16")
        dialog = crea_popup_semantico(
            parent,
            "Conversione UTF-8",
            (
                f"Il file usa la codifica {codifica}, mentre "
                "PostiPerfetti utilizza UTF-8."
            ),
            "file-check",
            testo_informativo=(
                "Vuoi crearne automaticamente una copia compatibile "
                "senza modificare il contenuto del file originale?"
            ),
            messaggio_in_grassetto=True,
        )
        btn_converti = dialog.addButton(
            "Crea copia UTF-8 e carica", QMessageBox.AcceptRole
        )
        applica_icona(btn_converti, "file-check", 18)
        btn_annulla = dialog.addButton("Annulla", QMessageBox.RejectRole)
        applica_icona(btn_annulla, "x", 18)
        dialog.setDefaultButton(btn_converti)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()
        if dialog.clickedButton() != btn_converti:
            return

        try:
            percorso_copia = crea_copia_utf8_file_classe(percorso)
            risultato = carica_file_classe(
                percorso_copia,
                consenti_vincoli_orfani=True,
            )
        except Exception as errore:
            _popup_errore(
                parent,
                "Conversione UTF-8 non riuscita",
                "Non è stato possibile creare la copia compatibile.",
                dettagli=(
                    f"Il file originale non è stato modificato.\n\n{errore}"
                ),
            )
            return

        percorso = os.fspath(percorso_copia)

    if risultato.get("codifica_legacy"):
        dialog = crea_popup_semantico(
            parent,
            "Codifica precedente rilevata",
            "Il file non è in UTF-8.",
            "triangle-alert",
            testo_informativo=(
                f"{risultato.get('avviso_codifica', '')}\n\n"
                "Vuoi caricarlo comunque nell’Editor? La classe già aperta "
                "resterà invariata se scegli Annulla."
            ),
            messaggio_in_grassetto=True,
        )
        btn_carica = dialog.addButton(
            "Carica e controlla", QMessageBox.AcceptRole
        )
        applica_icona(btn_carica, "file-check", 18)
        btn_annulla = dialog.addButton("Annulla", QMessageBox.RejectRole)
        applica_icona(btn_annulla, "x", 18)
        dialog.setDefaultButton(btn_annulla)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()
        if dialog.clickedButton() != btn_carica:
            return

    vincoli_orfani = list(risultato.get("vincoli_orfani", []))
    if vincoli_orfani:
        nomi_assenti = []
        visti = set()
        for vincolo in vincoli_orfani:
            nome = vincolo["target"]
            chiave = chiave_nome_completo(nome)
            if chiave not in visti:
                visti.add(chiave)
                nomi_assenti.append(nome)

        elenco = "\n".join(f"  • {nome}" for nome in nomi_assenti)
        n_vincoli = len(vincoli_orfani)
        n_studenti = len(nomi_assenti)
        dialog = crea_popup_semantico(
            parent,
            "Riferimenti a studenti non più presenti",
            (
                f"Sono stati trovati {n_vincoli} "
                f"{'vincolo' if n_vincoli == 1 else 'vincoli'} riferiti a "
                f"{n_studenti} "
                f"{'studente' if n_studenti == 1 else 'studenti'} "
                "non più presenti nella classe."
            ),
            "triangle-alert",
            testo_informativo=(
                f"{elenco}\n\n"
                "Vuoi rimuovere automaticamente questi riferimenti e "
                "aprire comunque la classe?\n\n"
                "Verranno eliminati soltanto i riferimenti agli studenti "
                "assenti. Gli altri dati e vincoli resteranno invariati. "
                "La correzione sarà salvata nel .txt quando userai "
                "«SALVA e CARICA»."
            ),
            messaggio_in_grassetto=True,
        )
        btn_annulla = dialog.addButton("Annulla", QMessageBox.RejectRole)
        btn_rimuovi = dialog.addButton(
            "Rimuovi riferimenti e apri",
            QMessageBox.AcceptRole,
        )
        applica_icona(btn_annulla, "x", 18)
        applica_icona(btn_rimuovi, "trash-2", 18)
        dialog.setDefaultButton(btn_annulla)
        dialog.setEscapeButton(btn_annulla)
        dialog.exec()
        if dialog.clickedButton() != btn_rimuovi:
            return

    return percorso, risultato
