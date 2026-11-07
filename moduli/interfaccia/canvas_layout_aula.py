# -*- coding: utf-8 -*-
"""Layout a posizioni permanenti: seleziona uno spazio, aggiungi o sposta.

Nessun parcheggio o trascinamento che possa ridisegnare la griglia.
Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QWidget
from moduli.dominio.aula_personalizzata import ModelloAulaPersonalizzata
from moduli.dominio.griglia_layout_fissa import PASSO_COLONNA, POSIZIONE_DOCENTE, nome_posizione
from moduli.dominio.layout_unico import GrigliaLayoutUnico
from moduli.interfaccia.risultato_corrente_ui import RisultatoCorrenteUIMixin
from moduli.interfaccia.vista_layout_fisso import VistaLayoutFisso


class CanvasLayoutAula(QWidget):
    modelloModificato = Signal()
    selezioneCambiata = Signal()
    messaggio = Signal(str)
    modalitaFissoTerminata = Signal()
    menuRichiesto = Signal(int, int)
    GRIGLIA = GrigliaLayoutUnico(righe=6, colonne=20, zona_docente=(0, 8, 11))

    def __init__(self, modello, *, ha_fisso=False, parent=None):
        super().__init__(parent)
        self.modello = modello
        self.modello.griglia_fissa = True
        self.ha_fisso = ha_fisso
        self.posizione_selezionata = None
        self._spostando = None
        self._modalita_fisso = False
        # La finestra può proteggere una proposta non salvata prima della modifica.
        # Il canvas standalone continua a funzionare senza dipendenze dalla sessione.
        self.verifica_modifica = lambda: True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.vista = VistaLayoutFisso(self._crea_posto, parent=self)
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        # La griglia cresce con la finestra lasciando una cornice proporzionata;
        # su finestre piccole la cornice si riduce prima di richiedere scorrimento.
        for indice, peso in ((0, 1), (1, 24), (2, 1)):
            layout.setColumnStretch(indice, peso)
            layout.setRowStretch(indice, peso)
        layout.addWidget(self.vista, 1, 1)
        self.vista.posizioneScelta.connect(self.scegli_posizione)
        self._ridisegna()

    def _estrai_nome_completo_da_id(self, testo):
        return testo

    def _crea_posto(self, posto, **kwargs):
        return RisultatoCorrenteUIMixin.crea_widget_posto(self, posto, **kwargs)

    @property
    def selezionati(self):
        blocco = self.blocco_selezionato()
        return (blocco.id,) if blocco else ()

    @property
    def sta_spostando(self):
        return self._spostando is not None

    def blocco_selezionato(self):
        if self.posizione_selezionata is None:
            return None
        r, c = self.posizione_selezionata
        return next((b for b in self.modello.blocchi
                     if (b.riga, b.colonna) == (r, c * PASSO_COLONNA)), None)

    def spazio_selezionato(self):
        return (self.posizione_selezionata is not None
                and (self.posizione_selezionata[0], self.posizione_selezionata[1] * PASSO_COLONNA)
                in self.modello.spazi)

    def aggiungi_spazio(self):
        if (self.posizione_selezionata is None or self.blocco_selezionato()
                or self.spazio_selezionato() or self.sta_spostando or self._modalita_fisso):
            return
        r, c = self.posizione_selezionata
        if not self.verifica_modifica():
            return
        self.modello.aggiungi_spazio(r, c * PASSO_COLONNA)
        self._ridisegna()
        self.modelloModificato.emit()
        self.messaggio.emit('Spazio riservato: il vuoto resterà in Aula e in Excel.')

    def _ridisegna(self):
        self.vista.popola(self.modello, selezione=self.posizione_selezionata)
        self.selezioneCambiata.emit()

    def scegli_posizione(self, riga, colonna, indice=-1):
        if type(riga) is not int or type(colonna) is not int or not (0 <= riga < 6 and 0 <= colonna < 5):
            self.messaggio.emit("Scegli uno spazio della griglia.")
            return
        posizione = (riga, colonna)
        if posizione == POSIZIONE_DOCENTE:
            self.messaggio.emit('Questo spazio è riservato alla cattedra.')
            return
        b = next((b for b in self.modello.blocchi
                  if (b.riga, b.colonna) == (riga, colonna * PASSO_COLONNA)), None)
        if self.sta_spostando:
            if b and b.id == self._spostando:
                self.annulla_operazione()
                return
            if b or (riga, colonna * PASSO_COLONNA) in self.modello.spazi:
                self.messaggio.emit('Posizione occupata: scegli uno spazio libero.')
                return
            if not self.verifica_modifica():
                return
            self.modello.sposta_blocco(self._spostando, riga=riga, colonna=colonna * PASSO_COLONNA)
            self._spostando = None
            self.posizione_selezionata = posizione
            self._ridisegna()
            self.modelloModificato.emit()
            self.messaggio.emit('Blocco spostato in ' + nome_posizione(riga, colonna) + '.')
        elif self._modalita_fisso:
            if b and indice >= 0:
                cambiata = self.modello.ancora_fisso != (b.id, indice)
                if cambiata and not self.verifica_modifica():
                    return
                self.modello.imposta_ancora_fisso(b.id, indice)
                self.posizione_selezionata = posizione
                self._modalita_fisso = False
                self.modalitaFissoTerminata.emit()
                self._ridisegna()
                if cambiata:
                    self.modelloModificato.emit()
                self.messaggio.emit(f'Posto FISSO assegnato a {b.id}, posto {indice+1}.')
            else:
                self.messaggio.emit('Per il FISSO fai clic su un singolo posto già inserito.')
        else:
            self.posizione_selezionata = posizione
            self._ridisegna()
            self.menuRichiesto.emit(riga, colonna)

    def aggiungi_primo_spazio(self, capienza):
        if self.posizione_selezionata is None or self.blocco_selezionato() or self.spazio_selezionato() or self.sta_spostando or self._modalita_fisso:
            self.messaggio.emit('Clicca prima su Aggiungi.')
            return
        r, c = self.posizione_selezionata
        if not self.verifica_modifica():
            return
        self.modello.aggiungi_blocco(capienza, riga=r, colonna=c * PASSO_COLONNA)
        self._ridisegna()
        self.modelloModificato.emit()
        self.messaggio.emit(f'Blocco da {capienza} inserito in {nome_posizione(r, c)}.')

    def avvia_spostamento(self):
        b = self.blocco_selezionato()
        if b and not self._modalita_fisso:
            self._spostando = b.id
            self.selezioneCambiata.emit()
            self.messaggio.emit(f'Sposta {b.id}: clicca su Aggiungi nella posizione di destinazione.')

    def annulla_operazione(self):
        self._spostando = None
        if self._modalita_fisso:
            self._modalita_fisso = False
            self.modalitaFissoTerminata.emit()
        self.selezioneCambiata.emit()
        self.messaggio.emit('Operazione annullata.')

    def imposta_modalita_fisso(self, attiva):
        self._modalita_fisso = bool(attiva and self.ha_fisso and not self.sta_spostando)
        self.selezioneCambiata.emit()
        if self._modalita_fisso:
            self.messaggio.emit('Clicca sul singolo posto dello studente FISSO.')

    def imposta_ha_fisso(self, valore):
        self.ha_fisso = bool(valore)
        if not self.ha_fisso:
            self._modalita_fisso = False

    def applica_zona_ai_selezionati(self, zona):
        b = self.blocco_selezionato()
        if b and not self.sta_spostando and not self._modalita_fisso:
            if b.zona == zona or not self.verifica_modifica():
                return
            self.modello.imposta_zona(b.id, zona)
            self._ridisegna()
            self.modelloModificato.emit()

    def elimina_selezionati(self):
        b = self.blocco_selezionato()
        if b and not self.sta_spostando and not self._modalita_fisso:
            if not self.verifica_modifica():
                return
            self.modello.rimuovi_blocco(b.id)
            self._ridisegna()
            self.modelloModificato.emit()
        elif self.spazio_selezionato() and not self.sta_spostando and not self._modalita_fisso:
            if not self.verifica_modifica():
                return
            r, c = self.posizione_selezionata
            self.modello.rimuovi_spazio(r, c * PASSO_COLONNA)
            self._ridisegna()
            self.modelloModificato.emit()

    def rimuovi_ancora_fisso(self):
        if self.modello.ancora_fisso is None or not self.verifica_modifica():
            return
        self.modello.rimuovi_ancora_fisso()
        self._ridisegna()
        self.modelloModificato.emit()

    def svuota(self):
        if not (self.modello.blocchi or self.modello.spazi) or not self.verifica_modifica():
            return
        self.modello.svuota()
        self.annulla_operazione()
        self.posizione_selezionata = None
        self._ridisegna()
        self.modelloModificato.emit()

    def imposta_modello(self, modello):
        self.modello = modello
        self.modello.griglia_fissa = True
        self.posizione_selezionata = None
        self._spostando = None
        self._modalita_fisso = False
        self._ridisegna()
        self.modelloModificato.emit()

    def modello_persistibile(self):
        copia = ModelloAulaPersonalizzata(self.modello.blocchi, griglia_fissa=True, spazi=self.modello.spazi)
        if self.modello.ancora_fisso is not None:
            copia.imposta_ancora_fisso(*self.modello.ancora_fisso)
        return copia

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.annulla_operazione()
        elif event.key() == Qt.Key.Key_Delete:
            self.elimina_selezionati()
        else:
            super().keyPressEvent(event)

    def aggiorna_tema(self):
        self._ridisegna()
