# -*- coding: utf-8 -*-
"""Gate D3: editing reversibile del Mensile sulla vista Aula post-generazione.

La bozza rimane nel dialogo finché l’utente non preme «Adotta modifiche».
La conferma verrà verificata e applicata dalla GUI principale; mai qui.
Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from uuid import uuid4

from PySide6.QtCore import QEvent, QObject, Qt, QMimeData
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QMessageBox, QVBoxLayout, QWidget,
)

from moduli.dominio.disposizione_effettiva import da_risultato_personalizzata
from moduli.dominio.editing_disposizione import BozzaDisposizione
from moduli.dominio.studenti import nome_completo_da_identificatore
from moduli.interfaccia.risultato_corrente_ui import RisultatoCorrenteUIMixin
from moduli.interfaccia.testi_dragdrop import spiega_rifiuto, spiega_avvisi
from moduli.interfaccia.dettagli_dragdrop import (
    dettagli_peggioramenti, spiega_rifiuto_con_nomi,
)
from moduli.interfaccia.tema import C
from moduli.interfaccia.utilita import applica_icona

MIME_POSTI = 'application/x-postiperfetti-d2a-posto'


class _Trascinamenti(QObject):
    """Tratta gli ID semantici; il testo dei QLabel non è mai un payload."""

    def __init__(self, dialogo):
        super().__init__(dialogo)
        self.dialogo = dialogo
        self.posti: dict[QWidget, tuple[str, str]] = {}
        self.inizio = None
        self.token = uuid4().hex
        self.revisione = 0

    def associa(self, widget, id_posto, id_blocco):
        self.posti[widget] = (id_posto, id_blocco)
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)
        widget.setToolTip(
            widget.toolTip() + '\nTrascina: uno studente. Ctrl+trascina: occupanti di un intero blocco.'
        )

    def _payload(self, fonte, modo):
        id_posto, id_blocco = self.posti[fonte]
        return json.dumps({
            'token': self.token, 'revisione': self.revisione,
            'modo': modo, 'posto': id_posto, 'blocco': id_blocco,
        }, sort_keys=True).encode('utf-8')

    def _decodifica(self, mime):
        if not mime.hasFormat(MIME_POSTI):
            return None
        try:
            raw = bytes(mime.data(MIME_POSTI))
            if len(raw) > 2048:
                return None
            dati = json.loads(raw.decode('utf-8'))
            if (not isinstance(dati, dict)
                    or set(dati) != {'token', 'revisione', 'modo', 'posto', 'blocco'}
                    or dati['token'] != self.token
                    or type(dati['revisione']) is not int
                    or dati['revisione'] != self.revisione
                    or dati['modo'] not in ('studente', 'banco')
                    or not isinstance(dati['posto'], str)
                    or not isinstance(dati['blocco'], str)):
                return None
            # Il payload deve riferirsi a un widget ancora presente nella vista.
            if (dati['posto'], dati['blocco']) not in self.posti.values():
                return None
            return dati
        except (ValueError, TypeError, UnicodeError):
            return None

    def _applica(self, dati, destinazione):
        if destinazione not in self.posti or not self.dialogo.puo_modificare():
            self.dialogo._stato('La proposta non è più modificabile.', 'errore')
            return False
        posto, blocco = self.posti[destinazione]
        if dati['modo'] == 'studente':
            esito = self.dialogo.bozza.scambia_studenti(dati['posto'], posto)
        else:
            esito = self.dialogo.bozza.scambia_occupanti_banchi(dati['blocco'], blocco)
        if not esito.accettata:
            nomi = spiega_rifiuto_con_nomi(
                self.dialogo.bozza, esito.motivo,
                dati['posto'] if dati['modo'] == 'studente' else dati['blocco'],
                posto if dati['modo'] == 'studente' else blocco, dati['modo'],
            )
            self.dialogo._stato('Scambio non consentito. ' + (
                nomi or spiega_rifiuto(esito.motivo)), 'errore')
            return False
        self.revisione += 1
        self.dialogo.bozza = esito.bozza
        self.dialogo._ridisegna()
        # Il riepilogo persistente si aggiorna in _ridisegna().
        # L'esito dell'ultima mossa non deve cancellare la situazione corrente.
        if esito.avvisi:
            self.dialogo._stato('Scambio effettuato, con peggioramenti delle preferenze.',
                                'avviso')
        else:
            self.dialogo._stato('Scambio effettuato.', 'ok')
        return True

    def eventFilter(self, oggetto, evento):
        # Qt può consegnare eventi di teardown dopo la distruzione parziale
        # del wrapper Python (attributi già eliminati da PySide).
        # In quel momento il filtro non deve sollevare eccezioni negli slot.
        if oggetto not in getattr(self, 'posti', ()):
            return False
        tipo = evento.type()
        if tipo == QEvent.Type.MouseButtonPress:
            self.inizio = (oggetto, evento.position().toPoint()) if (
                evento.button() == Qt.MouseButton.LeftButton) else None
        elif tipo == QEvent.Type.MouseButtonRelease:
            self.inizio = None
        elif tipo == QEvent.Type.MouseMove:
            if (self.inizio is not None and self.inizio[0] is oggetto
                    and evento.buttons() & Qt.MouseButton.LeftButton
                    and (evento.position().toPoint() - self.inizio[1]).manhattanLength()
                    >= QApplication.startDragDistance()):
                self.inizio = None
                if not self.dialogo.puo_modificare():
                    return True
                modo = ('banco' if evento.modifiers() & Qt.KeyboardModifier.ControlModifier
                        else 'studente')
                mime = QMimeData()
                mime.setData(MIME_POSTI, self._payload(oggetto, modo))
                drag = QDrag(oggetto)
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.MoveAction)
                return True
        elif tipo in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if self.dialogo.puo_modificare() and self._decodifica(evento.mimeData()):
                evento.acceptProposedAction()
            else:
                evento.ignore()
            return True
        elif tipo == QEvent.Type.Drop:
            dati = self._decodifica(evento.mimeData())
            if dati is not None and self._applica(dati, oggetto):
                evento.acceptProposedAction()
            else:
                evento.ignore()
            return True
        return False


class DialogoProvaDragDrop(QDialog, RisultatoCorrenteUIMixin):
    """Mostra lo stesso renderer di Aula, in una copia interamente reversibile."""

    def __init__(self, parent, risultato, puo_modificare):
        super().__init__(parent)
        foto = risultato['fotografia_generazione']
        disp = da_risultato_personalizzata(
            foto.layout.schema, risultato['collocazioni'],
            istantanea_visuale=foto.layout.istantanea_visuale,
            genere_misto=foto.genere_misto,
        )
        frequenze = {tuple(coppia): 1 for coppia in risultato.get('adiacenze_prima', ())}
        self.disposizione_all_apertura = disp
        originale = risultato.get('disposizione_automatica', disp)
        bozza = BozzaDisposizione.crea(foto, originale, frequenze_storico=frequenze)
        self.bozza = replace(bozza, corrente=disp)
        self._puo_modificare = puo_modificare
        self._base = deepcopy(risultato['configurazione_aula'])
        self._identificatori = {}
        for riga in self._base.griglia:
            for posto in riga:
                if posto.tipo == 'banco' and posto.occupato_da:
                    self._identificatori[
                        nome_completo_da_identificatore(posto.occupato_da)
                    ] = posto.occupato_da
        self._coord_widgets = {}
        self.setWindowTitle('Modifica disposizione mensile — Drag & Drop')
        self.resize(1150, 780)
        layout = QVBoxLayout(self)
        istruzioni = QLabel(
            'Trascina uno studente su un altro per scambiarli. '
            'Tieni premuto Ctrl per scambiare gli occupanti di due blocchi della stessa capienza. '
            'Premi «Adotta modifiche» per applicarle alla proposta da salvare.'
        )
        istruzioni.setObjectName('istruzioniDragDrop')
        istruzioni.setWordWrap(True)
        istruzioni.setContentsMargins(13, 10, 13, 10)
        istruzioni.setStyleSheet(
            f'QLabel#istruzioniDragDrop {{background-color: {C("layout_card_bg")}; '
            f'color: {C("testo_principale")}; border: 1px solid {C("layout_card_bordo")}; '
            'border-radius: 8px; font-size: 14px; font-weight: 600;}'
        )
        layout.addWidget(istruzioni)
        # La planimetria usa tutta la larghezza: nessun pannello laterale.
        self.scroll_aula = QScrollArea()
        self.widget_aula = QWidget()
        self.layout_griglia_aula = QGridLayout(self.widget_aula)
        self.scroll_aula.setWidget(self.widget_aula)
        self.scroll_aula.setWidgetResizable(True)
        layout.addWidget(self.scroll_aula, 1)
        self.messaggio = QLabel()
        self.messaggio.setObjectName('esitoDragDrop')
        self.messaggio.setWordWrap(True)
        self.messaggio.setMinimumHeight(60)
        self.messaggio.setContentsMargins(13, 10, 13, 10)
        layout.addWidget(self.messaggio)
        # Due informazioni distinte: esito dell'ultimo tentativo (transitorio)
        # e qualità ATTUALE della bozza (persistente fino alla sua risoluzione).
        self.riepilogo_preferenze = QLabel()
        self.riepilogo_preferenze.setObjectName('riepilogoPreferenzeDragDrop')
        self.riepilogo_preferenze.setWordWrap(True)
        self.riepilogo_preferenze.setMinimumHeight(60)
        self.riepilogo_preferenze.setContentsMargins(13, 10, 13, 10)
        riga_riepilogo = QHBoxLayout()
        riga_riepilogo.addWidget(self.riepilogo_preferenze, 1)
        self.btn_dettagli = QPushButton('Mostra dettagli')
        self.btn_dettagli.setObjectName('mostraDettagliDragDrop')
        applica_icona(self.btn_dettagli, 'list-tree', 18)
        self.btn_dettagli.clicked.connect(self._mostra_dettagli)
        riga_riepilogo.addWidget(self.btn_dettagli)
        layout.addLayout(riga_riepilogo)
        self._stato('Anteprima originale: nessuna modifica.', 'neutro')
        comandi = QHBoxLayout()
        self.btn_annulla = QPushButton('Annulla ultima mossa')
        self.btn_ripristina = QPushButton('Ripristina disposizione automatica')
        self.btn_adotta = QPushButton('Adotta modifiche')
        self.btn_chiudi = QPushButton('Scarta modifiche')
        # Icone SVG Lucide già incluse in entrambe le palette: i riferimenti
        # vengono registrati per l'eventuale cambio tema a finestra aperta.
        applica_icona(self.btn_annulla, 'history', 18)
        applica_icona(self.btn_ripristina, 'rotate-ccw', 18)
        applica_icona(self.btn_adotta, 'check', 18)
        applica_icona(self.btn_chiudi, 'x', 18)
        self.btn_annulla.clicked.connect(self._annulla)
        self.btn_ripristina.clicked.connect(self._ripristina)
        self.btn_adotta.clicked.connect(self._adotta)
        self.btn_chiudi.clicked.connect(self.reject)
        for bottone in (self.btn_annulla, self.btn_ripristina,
                        self.btn_adotta, self.btn_chiudi):
            comandi.addWidget(bottone)
        layout.addLayout(comandi)
        self.drag = _Trascinamenti(self)
        self._ridisegna()

    def _stato(self, testo: str, tipo: str = 'neutro') -> None:
        colore_bordo = {
            'neutro': C('layout_card_bordo'),
            'ok': C('accento'),
            'avviso': C('btn_export_bg'),
            'errore': C('btn_rosso_bg'),
        }.get(tipo, C('layout_card_bordo'))
        self.messaggio.setStyleSheet(
            f'QLabel#esitoDragDrop {{background-color: {C("layout_card_bg")}; '
            f'color: {C("testo_principale")}; border: 2px solid {colore_bordo}; '
            'border-radius: 8px; font-size: 14px; font-weight: 600;}'
        )
        self.messaggio.setText(testo)

    def _mostra_dettagli(self):
        """Mostra i nomi in un messaggio temporaneo con il solo pulsante OK.

        I dati sono ricostruiti quando si preme il pulsante: nessun pannello
        persistente e nessun riferimento a widget o segnalazioni ormai obsolete.
        """
        dettagli = dettagli_peggioramenti(self.bozza)
        righe = []
        if not dettagli:
            testo = 'Nessun peggioramento presente rispetto alla disposizione automatica.'
        else:
            for dettaglio in dettagli:
                righe.append(dettaglio.titolo)
                righe.extend('  • ' + studente for studente in dettaglio.studenti)
                righe.append('')
            testo = '\n'.join(righe).strip()
        # Il riepilogo è compatto, ma tutti i nomi rimangono consultabili.
        visibili = testo.splitlines()
        anteprima = '\n'.join(visibili[:12])
        box = QMessageBox(self)
        # L'anteprima Annuale applica uno stile generico a QFrame; QLabel
        # deriva da QFrame e altrimenti eredita una cornice non voluta.
        # Regola locale: stesso popup sobrio in Mensile e Annuale.
        box.setStyleSheet('''
            QMessageBox QLabel {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
            }
        ''')
        box.setWindowTitle('Dettagli dei peggioramenti')
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText('Studenti coinvolti nella disposizione attuale')
        box.setInformativeText(anteprima + (
            '\n… Apri «Mostra dettagli» per l’elenco completo.'
            if len(visibili) > 12 else ''))
        if len(visibili) > 12:
            box.setDetailedText(testo)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _aggiorna_riepilogo_preferenze(self) -> None:
        """Riepilogo persistente, derivato dalla bozza e non dall'ultima azione."""
        avvisi = self.bozza.avvisi_rispetto_originale()
        colore = C('btn_export_bg') if avvisi else C('accento')
        self.riepilogo_preferenze.setStyleSheet(
            f'QLabel#riepilogoPreferenzeDragDrop {{background-color: {C("layout_card_bg")}; '
            f'color: {C("testo_principale")}; border: 2px solid {colore}; '
            'border-radius: 8px; font-size: 14px; font-weight: 600;}'
        )
        if avvisi:
            self.riepilogo_preferenze.setText(
                'Peggioramenti presenti: ' + spiega_avvisi(avvisi))
        elif self.bozza.corrente == self.bozza.originale:
            self.riepilogo_preferenze.setText(
                'Situazione attuale: disposizione automatica, nessuna modifica.')
        else:
            self.riepilogo_preferenze.setText(
                'Situazione attuale: non sono peggiorate le preferenze '
                'rispetto alla disposizione automatica.')

    def puo_modificare(self):
        return bool(self._puo_modificare())

    def _estrai_nome_completo_da_id(self, ident):
        return nome_completo_da_identificatore(ident)

    def _forza_ridisegno_aula(self):
        self.layout_griglia_aula.activate()
        self.widget_aula.update()

    def crea_widget_posto(self, posto, merged=False, *, configurazione=None, mostra_fisso=True):
        widget = RisultatoCorrenteUIMixin.crea_widget_posto(
            self, posto, merged=merged, configurazione=configurazione,
            mostra_fisso=mostra_fisso,
        )
        if posto.tipo == 'banco':
            self._coord_widgets[(posto.riga, posto.colonna)] = widget
        return widget

    def _ridisegna(self):
        config = deepcopy(self._base)
        nomi = dict(self.bozza.corrente.occupazioni)
        self._coord_widgets = {}
        # Una sola fonte per geometria visiva e semantica: piano già calcolato.
        per_posti = {}
        for blocco in self.bozza.corrente.blocchi:
            vista = config.piano_personalizzato.per_id(blocco.id)
            riga = 0 if vista.fianco_docente else 1 + int(vista.fila_dal_docente)
            for posto in blocco.posti:
                colonna = vista.colonna + posto.indice
                per_posti[(riga, colonna)] = (posto.id, blocco.id)
                config.griglia[riga][colonna].occupato_da = self._identificatori[nomi[posto.id]]
        # Evita di mostrare la griglia vuota mentre i posti vengono ricreati.
        self.scroll_aula.setUpdatesEnabled(False)
        try:
            self._aggiorna_visualizzazione_aula(config)
        finally:
            self.scroll_aula.setUpdatesEnabled(True)
        self.drag.posti.clear()
        for coordinate, widget in self._coord_widgets.items():
            id_posto, id_blocco = per_posti[coordinate]
            self.drag.associa(widget, id_posto, id_blocco)
        self.btn_annulla.setEnabled(bool(self.bozza.undo))
        self.btn_ripristina.setEnabled(self.bozza.corrente != self.bozza.originale)
        self.btn_adotta.setEnabled(
            self.bozza.corrente.occupazioni != self.disposizione_all_apertura.occupazioni
            and self.puo_modificare()
        )
        self._aggiorna_riepilogo_preferenze()

    def _annulla(self):
        self.bozza = self.bozza.annulla()
        self.drag.revisione += 1
        self._ridisegna()
        self._stato('Ultima modifica annullata.', 'neutro')

    def _ripristina(self):
        self.bozza = self.bozza.ripristina_automatica()
        self.drag.revisione += 1
        self._ridisegna()
        self._stato('Ripristinata la disposizione automatica.', 'neutro')

    def _adotta(self):
        """Conferma la bozza; la GUI principale eseguirà verifica e commit."""
        if not self.puo_modificare():
            self._stato('La proposta non è più modificabile.', 'errore')
            return
        if self.bozza.corrente.occupazioni == self.disposizione_all_apertura.occupazioni:
            self._stato('Non hai effettuato modifiche da adottare.', 'neutro')
            return
        self.accept()
