# -*- coding: utf-8 -*-
"""Coordinamento GUI della configurazione dell’aula.

Gestisce geometria a coppie/terzetti, capienza, posti per fila e blocco
finale. Il mixin lavora sui widget e sullo StatoSessione posseduti dalla
finestra principale; i calcoli geometrici restano delegati a ConfigurazioneAula.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

import math

from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie
from moduli.lingua import quantita


def testi_opzione_genere_misto(geometria: str) -> tuple[str, str]:
    """Restituisce etichetta e tooltip coerenti con la geometria attiva."""
    if geometria == "terzetti":
        return (
            "Preferisci vicinanze miste (M+F)",
            "Se attivo, dà forte preferenza alle vicinanze consecutive M+F "
            "nei gruppi.\nNon vieta vicinanze dello stesso genere se "
            "necessarie per variare le rotazioni.",
        )
    return (
        "Preferisci coppie miste (M+F)",
        "Se attivo, dà forte preferenza alle coppie M+F.\n"
        "Non vieta coppie dello stesso genere se necessarie per variare "
        "le rotazioni.",
    )


class ConfigurazioneAulaUIMixin:
    """Aggiunge alla finestra principale il coordinamento dell’aula."""

    def _on_geometria_cambiata(self, _checked=False):
        """Aggiorna l’interfaccia quando cambia la modalità geometrica."""

        if self.radio_geo_terzetti.isChecked():
            self.sessione.imposta_geometria('terzetti')
        else:
            self.sessione.imposta_geometria('coppie')

        self._precompila_schema_per_modo()

        self._aggiorna_disponibilita_annuale()
        self._aggiorna_opzione_genere_misto()

        self._aggiorna_box_resto()


    def _aggiorna_opzione_genere_misto(self) -> None:
        """Adegua il testo dell'opzione al tipo di adiacenza ottimizzato."""
        if not hasattr(self, "checkbox_genere_misto"):
            return
        etichetta, tooltip = testi_opzione_genere_misto(
            self.sessione.geometria
        )
        self.checkbox_genere_misto.setText(etichetta)
        self.checkbox_genere_misto.setToolTip(tooltip)


    def _aggiorna_disponibilita_annuale(self):
        """Mantiene disponibile l'Annuale in entrambe le geometrie."""
        if not hasattr(self, "radio_annuale"):
            return
        self.radio_annuale.setEnabled(True)
        self.radio_annuale.setToolTip(
            "Genera in un colpo solo più mesi consecutivi, confrontando\n"
            "più tentativi e scegliendo la combinazione più pulita."
        )


    def _posizione_resto_corrente(self) -> str:
        """Restituisce la posizione selezionata per il blocco speciale."""
        if self.radio_trio_prima.isChecked():
            return "prima"
        if self.radio_trio_ultima.isChecked():
            return "ultima"
        return "centro"


    def _crea_layout_capienza_corrente(self) -> ConfigurazioneAula:
        """Costruisce la stessa geometria che verrà consegnata al motore."""
        aula = ConfigurazioneAula("Anteprima capienza GUI")
        n = len(self.sessione.studenti)
        posti_per_fila = int(self.input_posti_fila.text())
        ha_fisso = any(
            studente.nota_posizione == "FISSO"
            for studente in self.sessione.studenti
        )
        if self.sessione.geometria == "terzetti":
            preferenza = (
                "due_quartetti"
                if hasattr(self, "radio_resto_quartetti")
                and self.radio_resto_quartetti.isChecked()
                else "coppia"
            )
            aula.crea_layout_terzetti(
                n,
                terzetti_per_fila=max(1, posti_per_fila // 3),
                posizione_blocco_finale=self._posizione_resto_corrente(),
                ha_fisso=ha_fisso,
                preferenza_resto2=preferenza,
            )
        else:
            aula.crea_layout_standard(
                n,
                int(self.input_num_file.text()),
                posti_per_fila,
                self._posizione_resto_corrente(),
                ha_fisso=ha_fisso,
            )
        return aula


    def _aggiorna_posti_totali(self):
        """Mostra la capienza effettiva della geometria corrente."""
        if not self.sessione.studenti:
            num_file = int(self.input_num_file.text())
            posti_per_fila = int(self.input_posti_fila.text())
            posti_totali = num_file * posti_per_fila
            self._ultimo_totale_posti = posti_totali
            self.label_posti_totali.setText(
                f"{quantita(posti_totali, 'posto totale', 'posti totali')}"
            )
            self._applica_stile_label_capienza("neutro")
            return

        aula = self._crea_layout_capienza_corrente()
        per_fila = aula.capienze_file_banchi()
        posti_totali = sum(per_fila)
        num_studenti = len(self.sessione.studenti)
        self._ultimo_totale_posti = posti_totali
        schema = " + ".join(str(numero) for numero in per_fila)

        if num_studenti > posti_totali:
            self._applica_stile_label_capienza("errore")
            self.label_posti_totali.setText(
                "POSTI INSUFFICIENTI!\n"
                f"Servono: {num_studenti} | Disponibili: {posti_totali}"
            )
            self.sessione.imposta_posti_insufficienti(True)
            return

        self._applica_stile_label_capienza("neutro")
        self.sessione.imposta_posti_insufficienti(False)
        differenza = posti_totali - num_studenti
        if differenza == 0:
            self.label_posti_totali.setText(
                f"Schema: {schema} = {quantita(posti_totali, 'posto', 'posti')} "
                "(PERFETTO!)"
            )
            return

        self.label_posti_totali.setText(
            f"Schema: {schema} = {quantita(posti_totali, 'posto', 'posti')}\n"
            f"{quantita(differenza, 'posto vuoto', 'posti vuoti')} "
            f"{'sarà tolto' if differenza == 1 else 'saranno tolti'}"
        )


    def _cambia_posti_fila(self, delta):
        """Modifica il numero di posti per fila entro i limiti della modalità."""
        valore_attuale = int(self.input_posti_fila.text())

        if self.sessione.geometria == 'terzetti':
            passo, minimo, massimo = 3, 6, 9
        else:
            passo, minimo, massimo = 2, 4, 10

        direzione = 1 if delta > 0 else -1
        nuovo_valore = valore_attuale + direzione * passo

        if minimo <= nuovo_valore <= massimo:
            self.input_posti_fila.setText(str(nuovo_valore))

            self._aggiorna_stato_bottoni_posti()
            self._aggiorna_posti_totali()

            self._aggiorna_box_resto()


    def _aggiorna_stato_bottoni_posti(self):
        """Abilita o disabilita i comandi per cambiare i posti per fila."""
        valore = int(self.input_posti_fila.text())
        if self.sessione.geometria == 'terzetti':
            passo, minimo, massimo = 3, 6, 9
        else:
            passo, minimo, massimo = 2, 4, 10
        self.btn_posti_meno.setEnabled(valore > minimo)
        self.btn_posti_piu.setEnabled(valore < massimo)
        self.btn_posti_meno.setToolTip(
            f"Riduci i posti per fila di {passo}"
        )
        self.btn_posti_piu.setToolTip(
            f"Aumenta i posti per fila di {passo}"
        )


    def _precompila_schema_per_modo(self):
        """Imposta i valori iniziali della geometria per la modalità selezionata."""
        if self.sessione.geometria == 'terzetti':

            self.input_posti_fila.setText("9")

            if self.sessione.studenti:
                file_necessarie = max(1, min(math.ceil(len(self.sessione.studenti) / 9), 6))
            else:
                file_necessarie = 3
            self.input_num_file.setText(str(file_necessarie))

            self._aggiorna_stato_bottoni_posti()

            self._aggiorna_posti_totali()
        else:

            self.btn_posti_meno.setEnabled(True)
            self.btn_posti_piu.setEnabled(True)
            self._auto_calcola_layout_aula()


    def _aggiorna_box_resto(self):
        """Aggiorna composizione, posizione e visibilità del blocco finale."""
        if not hasattr(self, 'group_dispari'):
            return

        if not self.sessione.studenti:
            self.group_dispari.setVisible(False)
            return

        n = len(self.sessione.studenti)
        num_fissi = sum(1 for s in self.sessione.studenti if s.nota_posizione == 'FISSO')

        if self.sessione.geometria != self._modo_box_resto_corrente:

            if self.radio_trio_prima.isChecked():
                posizione_attuale = 'prima'
            elif self.radio_trio_centro.isChecked():
                posizione_attuale = 'centro'
            else:
                posizione_attuale = 'ultima'
            self._memoria_posizione_resto[self._modo_box_resto_corrente] = \
                posizione_attuale

            ricordata = self._memoria_posizione_resto[self.sessione.geometria]
            if ricordata == 'prima':
                self.radio_trio_prima.setChecked(True)
            elif ricordata == 'centro':
                self.radio_trio_centro.setChecked(True)
            else:
                self.radio_trio_ultima.setChecked(True)

            self._modo_box_resto_corrente = self.sessione.geometria

        if self.sessione.geometria == 'terzetti':
            self._aggiorna_box_resto_terzetti(n, num_fissi > 0)
        else:
            self._aggiorna_box_resto_coppie(n, num_fissi)


    def _aggiorna_box_resto_coppie(self, n, num_fissi):
        """Aggiorna il blocco finale della modalità a coppie."""
        self.group_dispari.setTitle("GESTIONE NUMERO DISPARI")

        self.widget_composizione_resto.setVisible(False)

        posti = max(2, int(self.input_posti_fila.text()))
        posizione = self._posizione_resto_corrente()
        self.input_num_file.setText(str(numero_minimo_file_coppie(
            n,
            posti,
            posizione_trio=posizione,
            ha_fisso=num_fissi > 0,
        )))
        self._aggiorna_posti_totali()

        num_rimanenti = n - num_fissi
        if num_rimanenti % 2 == 1:
            self.group_dispari.setVisible(True)
            if num_fissi > 0:
                info = (
                    f"Con {quantita(n, 'studente', 'studenti')} "
                    f"({quantita(num_fissi, 'studente FISSO', 'studenti FISSO')}, "
                    f"{quantita(num_rimanenti, 'rimanente dispari', 'rimanenti dispari')}), "
                    "il banco da 3 sarà posizionato:"
                )
            else:
                info = (
                    f"Con {quantita(n, 'studente', 'studenti')}, "
                    "il banco da 3 sarà posizionato:"
                )

            self._mostra_posizioni_resto(True, True, True, info)
        else:
            self.group_dispari.setVisible(False)


    def _aggiorna_box_resto_terzetti(self, n, ha_fisso):
        """Aggiorna il blocco finale della modalità a terzetti."""
        self.group_dispari.setTitle("GESTIONE DEL RESTO")
        P = max(1, int(self.input_posti_fila.text()) // 3)
        resto = n % 3

        composizione_possibile = (resto == 2 and n >= 8)
        mostra_composizione = False
        if composizione_possibile:
            _, minf_coppia = self._terzetti_righe_e_minfila(n, P, ha_fisso, False)
            _, minf_quart  = self._terzetti_righe_e_minfila(n, P, ha_fisso, True)
            mostra_composizione = (minf_quart > minf_coppia)
        self.widget_composizione_resto.setVisible(mostra_composizione)

        if not mostra_composizione and self.radio_resto_quartetti.isChecked():
            self.radio_resto_coppia.blockSignals(True)
            self.radio_resto_quartetti.blockSignals(True)
            self.radio_resto_coppia.setChecked(True)
            self.radio_resto_coppia.blockSignals(False)
            self.radio_resto_quartetti.blockSignals(False)

        usa_due_quartetti = mostra_composizione and self.radio_resto_quartetti.isChecked()

        righe, _ = self._terzetti_righe_e_minfila(n, P, ha_fisso, usa_due_quartetti)
        self.input_num_file.setText(str(righe))
        self._aggiorna_posti_totali()

        if resto == 0:

            self.group_dispari.setVisible(False)
            return

        self.group_dispari.setVisible(True)
        if usa_due_quartetti:
            self._posizioni_due_quartetti(n, ha_fisso, righe)
        else:
            self._posizioni_blocco_singolo(n, ha_fisso, resto, righe)


    def _terzetti_righe_e_minfila(self, n, P, ha_fisso, due_quartetti):
        """Calcola numero di file e capienza minima della geometria a terzetti."""
        pref = 'due_quartetti' if due_quartetti else 'coppia'
        cfg = ConfigurazioneAula()
        cfg.crea_layout_terzetti(n, terzetti_per_fila=P, posizione_blocco_finale='ultima',
                                 ha_fisso=ha_fisso, preferenza_resto2=pref)

        per_fila = []
        for ri, riga in enumerate(cfg.griglia):
            if ri < 2:
                continue
            nb = sum(1 for p in riga
                     if p is not None and getattr(p, 'tipo', None) == 'banco')
            if nb > 0:
                per_fila.append(nb)
        righe = len(per_fila)
        min_fila = min(per_fila) if per_fila else 0
        return righe, min_fila


    def _terzetti_posti_per_fila(self, n, P, ha_fisso, due_quartetti):
        """Restituisce i posti effettivi presenti in ciascuna fila a terzetti."""
        pref = 'due_quartetti' if due_quartetti else 'coppia'
        cfg = ConfigurazioneAula()
        cfg.crea_layout_terzetti(n, terzetti_per_fila=P,
                                 posizione_blocco_finale='ultima',
                                 ha_fisso=ha_fisso, preferenza_resto2=pref)

        per_fila = []
        for ri, riga in enumerate(cfg.griglia):
            if ri < 2:
                continue
            nb = sum(1 for p in riga
                     if p is not None and getattr(p, 'tipo', None) == 'banco')
            if nb > 0:
                per_fila.append(nb)
        return per_fila


    def _posizioni_blocco_singolo(self, n, ha_fisso, resto, righe):
        """Restituisce le posizioni ammesse per un singolo blocco finale."""
        nome_banco = "banco da 4" if resto == 1 else "banco da 2"
        k = (n // 3 - 1) if resto == 1 else (n // 3)
        fisso_nel_resto = ha_fisso and k == 0
        if fisso_nel_resto:
            self._mostra_posizioni_resto(False, False, False,
                f"Il FISSO siede nel {nome_banco}, che va in prima fila.")
        elif ha_fisso:
            if righe <= 2:
                self._mostra_posizioni_resto(False, False, False,
                    f"Con il FISSO in prima fila, il {nome_banco} va nella 2ª fila.")
            else:
                self._mostra_posizioni_resto(False, True, True,
                    f"Il {nome_banco} sarà posizionato:")
        else:
            if righe <= 1:
                self._mostra_posizioni_resto(False, False, False,
                    f"Con una sola fila di banchi, il {nome_banco} va in quell'unica fila.")
            elif righe == 2:
                self._mostra_posizioni_resto(True, False, True,
                    f"Il {nome_banco} sarà posizionato:")
            else:
                self._mostra_posizioni_resto(True, True, True,
                    f"Il {nome_banco} sarà posizionato:")


    def _posizioni_due_quartetti(self, n, ha_fisso, righe):
        """Restituisce le posizioni ammesse per due quartetti finali."""
        k = (n - 8) // 3
        fisso_nel_resto = ha_fisso and k == 0
        if fisso_nel_resto:
            self._mostra_posizioni_resto(False, False, False,
                "I 2 quartetti occupano la colonna sinistra delle prime due "
                "file (il FISSO siede nel primo).")
        elif ha_fisso:
            if righe <= 3:
                self._mostra_posizioni_resto(False, False, False,
                    "Con il FISSO in prima fila, i 2 quartetti vanno nella "
                    "colonna sinistra di 2ª e 3ª fila.")
            else:
                self._mostra_posizioni_resto(False, True, True,
                    "I 2 quartetti saranno posizionati:")
        else:
            if righe <= 2:
                self._mostra_posizioni_resto(False, False, False,
                    "I 2 quartetti vanno nella colonna sinistra di entrambe le file.")
            elif righe == 3:
                self._mostra_posizioni_resto(True, False, True,
                    "I 2 quartetti saranno posizionati:")
            else:
                self._mostra_posizioni_resto(True, True, True,
                    "I 2 quartetti saranno posizionati:")


    def _mostra_posizioni_resto(self, mostra_davanti, mostra_in_mezzo,
                                 mostra_in_fondo, info_testo):
        """Mostra le posizioni ammesse e mantiene valida la selezione corrente."""
        self.label_info_dispari.setText(info_testo)
        self.radio_trio_prima.setVisible(mostra_davanti)
        self.radio_trio_centro.setVisible(mostra_in_mezzo)
        self.radio_trio_ultima.setVisible(mostra_in_fondo)

        spuntata_visibile = (
            (self.radio_trio_prima.isChecked() and mostra_davanti) or
            (self.radio_trio_centro.isChecked() and mostra_in_mezzo) or
            (self.radio_trio_ultima.isChecked() and mostra_in_fondo)
        )
        if not spuntata_visibile:

            self.radio_trio_ultima.setChecked(True)


    def _on_composizione_resto_cambiata(self, _checked=False):
        """Aggiorna la geometria quando cambia la composizione del blocco finale."""
        self._aggiorna_box_resto()


    def _reset_modalita_geometria(self):
        """Ripristina la geometria e le scelte del blocco finale."""
        self.sessione.imposta_geometria('coppie')

        if hasattr(self, 'radio_geo_coppie'):
            self.radio_geo_coppie.blockSignals(True)
            self.radio_geo_terzetti.blockSignals(True)
            self.radio_geo_coppie.setChecked(True)
            self.radio_geo_coppie.blockSignals(False)
            self.radio_geo_terzetti.blockSignals(False)
            self._aggiorna_disponibilita_annuale()

        self._memoria_posizione_resto = dict(self.DEFAULT_POSIZIONE_RESTO)
        self._modo_box_resto_corrente = 'coppie'

        if hasattr(self, 'radio_resto_coppia'):
            self.radio_resto_coppia.setChecked(True)
        if hasattr(self, 'radio_trio_centro'):
            self.radio_trio_centro.setChecked(True)


    def _auto_calcola_layout_aula(self):
        """Calcola una geometria iniziale capace di contenere la classe."""

        posti_per_fila_default = self.DEFAULT_POSTI_PER_FILA_COPPIE
        self.input_posti_fila.setText(str(posti_per_fila_default))

        if self.sessione.studenti:
            num_studenti = len(self.sessione.studenti)
            ha_fisso = any(
                studente.nota_posizione == "FISSO"
                for studente in self.sessione.studenti
            )
            file_necessarie = numero_minimo_file_coppie(
                num_studenti,
                posti_per_fila_default,
                posizione_trio=self._posizione_resto_corrente(),
                ha_fisso=ha_fisso,
            )
            self.input_num_file.setText(str(file_necessarie))
            print(f"   📐 Auto-calcolo aula: {num_studenti} studenti → "
                  f"{file_necessarie} file × {posti_per_fila_default} posti "
                  f"(schema nominale: {file_necessarie * posti_per_fila_default} posti)")
        else:

            self.input_num_file.setText("4")

        self._aggiorna_posti_totali()
