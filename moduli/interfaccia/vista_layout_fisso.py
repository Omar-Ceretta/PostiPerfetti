# -*- coding: utf-8 -*-
"""Editor responsive a posizioni permanenti 6 × 5.

La griglia appartiene soltanto al Layout; Aula usa il suo rendering originale.
Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""
import re
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from moduli.dominio.aula import PostoAula
from moduli.dominio.griglia_layout_fissa import COLONNE, POSIZIONE_DOCENTE, RIGHE, nome_posizione, posizione_blocco
from moduli.interfaccia.tema import C


class _Spazio(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.selezionato = False

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selezionato:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(C("accento")), 3))
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))


class VistaLayoutFisso(QWidget):
    posizioneScelta = Signal(int, int, int)

    def __init__(self, crea_posto, *, parent=None):
        super().__init__(parent)
        self.crea_posto = crea_posto
        self.spazi, self.posti, self.placeholder, self.intestazioni = {}, {}, {}, {}
        self.spazi_intenzionali = {}
        self._mouse_premuto = None
        self._modello = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(700, 454)
        self.griglia = QGridLayout(self)
        self.griglia.setContentsMargins(6, 6, 6, 6)
        self.griglia.setHorizontalSpacing(12)
        self.griglia.setVerticalSpacing(8)
        self.colonne = []
        for c in range(COLONNE):
            self.griglia.setColumnMinimumWidth(c, 128)
            self.griglia.setColumnStretch(c, 1)
            header = QLabel('ABCDE'[c])
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.colonne.append(header)
            self.griglia.addWidget(header, 0, c)
        self.griglia.setRowStretch(0, 1)
        for r in range(RIGHE - 1, -1, -1):
            display = RIGHE - r
            self.griglia.setRowStretch(display, 1)
            for c in range(COLONNE):
                spazio = _Spazio(self)
                spazio.setMinimumSize(128, 64)
                layout = QVBoxLayout(spazio)
                layout.setContentsMargins(2, 2, 2, 2)
                layout.setSpacing(0)
                head = QPushButton(spazio)
                head.setFlat(True)
                head.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
                head.clicked.connect(lambda checked=False, r=r, c=c, w=head:
                                     self._scegli_da_widget(w, r, c, -1))
                layout.addWidget(head, 16)
                corpo = QWidget(spazio)
                corpo.setObjectName('corpoBloccoLayout')
                corpo.setStyleSheet('QWidget#corpoBloccoLayout {background: transparent; border: none;}')
                corpo.setMinimumHeight(32)
                corpo_layout = QHBoxLayout(corpo)
                corpo_layout.setContentsMargins(0, 0, 0, 0)
                corpo_layout.setSpacing(3)
                layout.addWidget(corpo, 36)
                zona = QLabel(spazio)
                zona.setAlignment(Qt.AlignmentFlag.AlignCenter)
                zona.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
                layout.addWidget(zona, 14)
                self.spazi[r, c] = (spazio, head, corpo, corpo_layout, zona)
                self.griglia.addWidget(spazio, display, c)

    def _scegli_da_widget(self, widget, riga, colonna, indice):
        self.posizioneScelta.emit(riga, colonna, indice)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._mouse_premuto = watched
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._mouse_premuto is watched and watched.rect().contains(event.position().toPoint()):
                self._scegli_da_widget(watched, *watched.property('posizione_layout'))
            self._mouse_premuto = None
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adatta_dimensioni()

    def _adatta_dimensioni(self):
        # Si usano i pixel logici Qt: lo zoom del desktop è già gestito da Qt.
        scala = max(1.0, min(self.width() / 700, self.height() / 454))
        font = max(11, round(11 * scala))
        font_intestazione = max(10, round(10 * scala))
        for header in self.colonne:
            header.setMaximumHeight(round(16 * scala))
            header.setStyleSheet(f'font-size: {font}px; font-weight: bold;')
        for _slot, head, corpo, _layout, zona in self.spazi.values():
            head.setMaximumHeight(round(16 * scala))
            head.setStyleSheet(
                f'QPushButton {{padding: 0; margin: 0; border: none; background: transparent; '
                f'color: {C("testo_secondario")}; font-size: {font_intestazione}px; font-weight: normal;}}')
            zona.setMaximumHeight(round(14 * scala))
            zona.setStyleSheet(f'background: transparent; border: none; color: {C("testo_secondario")}; font-size: {font}px;')
        for p in self.placeholder.values():
            p.setStyleSheet(
                f'QPushButton {{border: 1px dashed {C("bordo_normale")}; '
                f'background: {C("sfondo_pannello")}; color: {C("testo_secondario")}; '
                f'font-size: {font}px; padding: 0; margin: 0;}}')
        for p in self.spazi_intenzionali.values():
            p.setStyleSheet(
                f'QPushButton {{border: 2px dashed {C("banco_occupato_bordo")}; '
                f'background: {C("banco_occupato_sf")}; color: {C("banco_occupato_txt")}; '
                f'font-size: {font}px; font-weight: 600; padding: 0; margin: 0;}}')
        for w in self.posti.values():
            css = re.sub(r'font-size:\s*\d+px;', f'font-size: {font}px;', w.styleSheet())
            w.setStyleSheet(css)
        if hasattr(self, 'cattedra'):
            w = self.cattedra
            w.setStyleSheet(re.sub(r'font-size:\s*\d+px;', f'font-size: {round(13*scala)}px;', w.styleSheet()))

    def aggiorna_tema(self):
        if self._modello is not None:
            self.popola(self._modello, selezione=self._selezione)

    def popola(self, modello, *, selezione=None):
        self._modello, self._selezione = modello, selezione
        blocchi = {}
        for b in modello.blocchi:
            try:
                blocchi[posizione_blocco(b)] = b
            except ValueError:
                continue  # La validazione segnala la bozza non canonica senza riposizionarla.
        intenzionali = {(r, c // 4) for r, c in modello.spazi}
        self.posti.clear()
        self.placeholder.clear()
        self.spazi_intenzionali.clear()
        self.intestazioni.clear()
        for (r, c), (spazio, head, corpo, layout, zona) in self.spazi.items():
            spazio.selezionato = selezione == (r, c)
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
            # La cattedra ha gia la propria etichetta nel riquadro: niente intestazione sopra.
            e_cattedra = (r, c) == POSIZIONE_DOCENTE
            head.setText("" if e_cattedra else nome_posizione(r, c))
            head.setToolTip("Cattedra" if e_cattedra else nome_posizione(r, c))
            head.setEnabled(not e_cattedra)
            zona.setText('')
            layout.setContentsMargins(0, 0, 0, 0)
            if (r, c) == POSIZIONE_DOCENTE:
                w = self.crea_posto(PostoAula(0, 8, 'postazione_docente'), merged=True)
                w.setParent(corpo)
                w.setText('Cattedra')
                w.setWordWrap(False)
                w.setMinimumSize(0, 0)
                w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
                layout.addStretch(1)
                layout.addWidget(w, 8)
                layout.addStretch(1)
                self.cattedra = w
            elif (r, c) not in blocchi:
                intenzionale = (r, c) in intenzionali
                p = QPushButton('Spazio' if intenzionale else '+\nAggiungi', corpo)
                p.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
                p.setAccessibleName(nome_posizione(r, c) + (', Spazio riservato' if intenzionale else ', Aggiungi'))
                p.setToolTip('Vuoto conservato in Aula e in Excel' if intenzionale else nome_posizione(r, c))
                p.clicked.connect(lambda checked=False, r=r, c=c, w=p:
                                  self._scegli_da_widget(w, r, c, -1))
                layout.addWidget(p)
                (self.spazi_intenzionali if intenzionale else self.placeholder)[r, c] = p
            else:
                b = blocchi[r, c]
                # Il bordo di selezione appartiene al riquadro esterno.
                # Posti e contenitore trasparente devono lasciargli spazio.
                layout.setContentsMargins(8, 4, 8, 4)
                head.setToolTip(f'{b.id} · {nome_posizione(r, c)}')
                head.setAccessibleName(f'Seleziona {b.id}, {b.capienza} posti, {nome_posizione(r, c)}')
                zona.setText({'prima': 'DAVANTI', 'ultima': 'IN FONDO', 'neutra': ''}[b.zona])
                self.intestazioni[b.id] = head
                if b.capienza == 2:
                    layout.addStretch(1)
                for i in range(b.capienza):
                    fixed = modello.ancora_fisso == (b.id, i)
                    posto = PostoAula(r, b.colonna+i, 'banco', occupato_da=f'{i+1}' + ('\nFISSO' if fixed else ''))
                    w = self.crea_posto(posto)
                    w.setParent(corpo)
                    w.setMinimumSize(0, 0)
                    w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
                    layout.addWidget(w, 2)
                    self.posti[b.id, i] = w
                    w.setAccessibleName(f'{b.id}, posto {i+1}' + (' FISSO' if fixed else ''))
                    w.setToolTip(f'{b.id}, posto {i+1}' + (' · FISSO' if fixed else ''))
                    w.setProperty('posizione_layout', (r, c, i))
                    w.installEventFilter(self)
                if b.capienza == 2:
                    layout.addStretch(1)
            spazio.update()
            for i in range(layout.count()):
                if layout.itemAt(i).widget():
                    layout.itemAt(i).widget().show()
        self._adatta_dimensioni()
        self.griglia.invalidate()
        self.griglia.activate()
