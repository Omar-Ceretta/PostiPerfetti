# -*- coding: utf-8 -*-
"""Mutation testing mirato sui contratti algoritmici di PostiPerfetti.

Ogni mutante viene applicato a una copia temporanea della root attiva e viene
eseguito soltanto il test sentinella che deve rilevarlo. Il codice produttivo
non viene mai modificato dal runner.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MutazioneRC:
    id: str
    file: str
    cerca: str
    sostituisci: str
    test: tuple[str, ...]
    occorrenza: int = 1  # 0 = tutte
    descrizione: str = ""


@dataclass(frozen=True, slots=True)
class EsitoMutazioneRC:
    id: str
    stato: str
    durata_s: float
    test: tuple[str, ...]
    descrizione: str
    dettaglio: str = ""


@dataclass(frozen=True, slots=True)
class RapportoMutazioniRC:
    mutanti: int
    uccisi: int
    sopravvissuti: int
    timeout: int
    errori: int
    durata_s: float
    dettaglio: tuple[EsitoMutazioneRC, ...]

    @property
    def score(self) -> float:
        valutabili = self.uccisi + self.sopravvissuti
        return 100.0 if valutabili == 0 else 100.0 * self.uccisi / valutabili

    @property
    def verde(self) -> bool:
        # Nel mutation testing un timeout provocato dal mutante è un kill:
        # il test sentinella ha rilevato una regressione prestazionale.
        return self.sopravvissuti == 0 and self.errori == 0

    def come_dict(self) -> dict:
        return {
            "campagna": "mutation_testing_mirato",
            "mutanti": self.mutanti,
            "uccisi": self.uccisi,
            "sopravvissuti": self.sopravvissuti,
            "timeout": self.timeout,
            "errori": self.errori,
            "score_percentuale": round(self.score, 2),
            "durata_s": self.durata_s,
            "verde": self.verde,
            "dettaglio": [asdict(esito) for esito in self.dettaglio],
        }


_TEST_CONTRATTI = "documentazione/sviluppo/test/validazione_rc/test_contratti_algoritmici_mutation.py"
_TEST_ANNUALE = "documentazione/sviluppo/test/cantiere_semantico/test_r08_semantica_annuale.py"


MUTAZIONI_FASE5: tuple[MutazioneRC, ...] = (
    MutazioneRC("M01_PESO_L2", "moduli/metrica_pulizia.py", "PESO_INCOMP_LIV2 = 10", "PESO_INCOMP_LIV2 = 1", (f"{_TEST_CONTRATTI}::test_pesi_incompatibilita_sono_contratto_1_10_1000",), descrizione="Livello 2 reso equivalente al livello 1."),
    MutazioneRC("M02_PESO_L3", "moduli/metrica_pulizia.py", "PESO_INCOMP_LIV3 = 1000", "PESO_INCOMP_LIV3 = 10", (f"{_TEST_CONTRATTI}::test_pesi_incompatibilita_sono_contratto_1_10_1000",), descrizione="Peso sentinella del livello 3 drasticamente ridotto."),
    MutazioneRC("M03_CHIAVE_COPPIE", "moduli/metrica_pulizia.py", "return (ripetizioni, incomp_pesate, -affinita)", "return (incomp_pesate, ripetizioni, -affinita)", (f"{_TEST_CONTRATTI}::test_chiave_pulizia_coppie_ha_ordine_riusi_incompatibilita_affinita",), occorrenza=1, descrizione="Inverte le prime due priorità della chiave mensile a coppie."),
    MutazioneRC("M04_CHIAVE_TERZETTI", "moduli/metrica_pulizia.py", "return (ripetizioni, incomp_pesate, -affinita)", "return (incomp_pesate, ripetizioni, -affinita)", (f"{_TEST_CONTRATTI}::test_chiave_pulizia_terzetti_ha_ordine_riusi_incompatibilita_affinita",), occorrenza=2, descrizione="Inverte le priorità della chiave mensile a terzetti."),
    MutazioneRC("M05_ORDINE_ANNUALE", "moduli/politica_annuale.py", 'return (delta["riusi"], incomp_pesate, -affinita)', 'return (incomp_pesate, delta["riusi"], -affinita)', (f"{_TEST_CONTRATTI}::test_ordine_annuale_mette_prima_zero_riusi_anche_se_ha_incompatibilita",), descrizione="Rende le incompatibilità prioritarie sui riusi nell'ordine cronologico."),
    MutazioneRC("M06_NOOP_SENZA_RIUSI", "moduli/politica_annuale.py", 'if temporali_base["mesi_con_riuso"] == 0:', 'if False and temporali_base["mesi_con_riuso"] == 0:', (f"{_TEST_CONTRATTI}::test_riordino_temporale_senza_riusi_esce_subito",), descrizione="Disattiva l'uscita immediata della cintura temporale senza riusi."),
    MutazioneRC("M07_GUARDIA_PROFILO_INCOMP", "moduli/politica_annuale.py", 'if profilo_nuovo > profilo_incompatibilita:\n                    continue', 'if False and profilo_nuovo > profilo_incompatibilita:\n                    continue', (f"{_TEST_ANNUALE}::test_riordino_temporale_non_anticipa_un_mese_incompatibile",), descrizione="Permette alla cintura temporale di anticipare lo sporco sociale."),
    MutazioneRC("M08_GUARDIA_S1_L1", "moduli/politica_annuale.py", 'metriche["incompatibilita_l1"] <= metriche_base["incompatibilita_l1"],', 'True,  # MUTAZIONE RC', (f"{_TEST_CONTRATTI}::test_guardie_s1_proteggono_tutte_le_incompatibilita_e_affinita",), descrizione="Rimuove la guardia S1 sulle incompatibilità leggere."),
    MutazioneRC("M09_PRIMO_RIUSO", "moduli/politica_annuale.py", 'return primo_candidato >= primo_base', 'return primo_candidato <= primo_base', (f"{_TEST_ANNUALE}::test_riordino_temporale_allontana_la_ripetizione_senza_anticiparla",), descrizione="Inverte la protezione sul primo mese di riuso."),
    MutazioneRC("M10_PENALITA_STORICO", "moduli/strato_storico.py", 'penalita = 500 * volte_usata', 'penalita = 50 * volte_usata', (f"{_TEST_CONTRATTI}::test_penalita_storico_e_esattamente_500_per_utilizzo",), descrizione="Riduce di dieci volte la pressione contro i riusi."),
    MutazioneRC("M11_LIVELLO3", "moduli/vincoli.py", '== 3:\n                return True', '== 2:\n                return True', (f"{_TEST_CONTRATTI}::test_livello3_resta_veto_assoluto_in_entrambe_le_direzioni",), occorrenza=0, descrizione="Sposta il veto assoluto dal livello 3 al livello 2."),
    MutazioneRC("M12_STOP_T3_COPPIE", "moduli/generazione.py", 'tentativo_candidato <= 3', 'tentativo_candidato < 3', (f"{_TEST_CONTRATTI}::test_best_of_n_coppie_si_ferma_se_t3_ha_gia_soluzione",), descrizione="Non considera più definitivo un successo al tentativo 3."),
    MutazioneRC("M13_PROPAGA_T4", "moduli/generazione.py", 'tentativo_partenza = 4', 'tentativo_partenza = 1  # MUTAZIONE RC', (f"{_TEST_CONTRATTI}::test_best_of_n_coppie_dopo_t4_parte_direttamente_da_t4",), descrizione="Fa ripartire da T1 i candidati successivi dopo un T4."),
    MutazioneRC("M14_PRECHECK_PARTNER", "moduli/algoritmo.py", 'if tentativo <= 3 and len(studenti_per_coppie) >= 2:', 'if False and tentativo <= 3 and len(studenti_per_coppie) >= 2:', ("documentazione/sviluppo/test/validazione_rc/test_precheck_partner_nuovo.py::test_studente_senza_partner_nuovo_salva_t1_t3_e_passa_subito_al_t4",), descrizione="Disattiva il precheck matematico sul partner nuovo."),
    MutazioneRC("M15_POTATURA_CLIQUE", "moduli/vincoli.py", 'if clique_potatura:', 'if False and clique_potatura:', ("documentazione/sviluppo/test/validazione_rc/test_stress_isolato.py::test_frontiera_clique_30_fisso_fattibile_non_esplode_piu",), descrizione="Disattiva la potatura di clique nel backtracking a coppie."),
    MutazioneRC("M16_SALTO_T2_T3_TERZETTI", "moduli/motore_terzetti.py", 'if tentativo == 1 and not tentativo_ha_tetto:\n                salta_t2_t3 = True', 'if tentativo == 1 and not tentativo_ha_tetto:\n                salta_t2_t3 = False', (f"{_TEST_ANNUALE}::test_t2_t3_sono_saltati_solo_dopo_t1_esaustivo",), descrizione="Riesegue T2 e T3 dopo un T1 esaustivo a terzetti."),
    MutazioneRC("M17_STOP_T3_TERZETTI", "moduli/motore_terzetti.py", "if getattr(motore, 'tentativo_corrente', 4) <= 3:", "if getattr(motore, 'tentativo_corrente', 4) < 3:", (f"{_TEST_CONTRATTI}::test_best_of_n_terzetti_si_ferma_se_t3_ha_gia_soluzione",), descrizione="Continua il best-of-N terzetti dopo un successo T3."),
    MutazioneRC("M18_WRAPPER_DOPPIO", "moduli/strato_storico.py", "if getattr(motore_vincoli, '_penalita_storico_applicata', False):\n        return", "if False and getattr(motore_vincoli, '_penalita_storico_applicata', False):\n        return", (f"{_TEST_CONTRATTI}::test_wrapper_penalita_storico_e_idempotente",), descrizione="Permette di applicare due volte il wrapper della penalità storica."),
    MutazioneRC("M19_CONTATORE_TERZETTI", "moduli/strato_storico.py", 'per_chiave[chiave]["volte_usata"] += 1', 'per_chiave[chiave]["volte_usata"] += 0', (f"{_TEST_CONTRATTI}::test_blacklist_terzetti_incrementa_lo_stesso_arco_senza_duplicarlo",), descrizione="Impedisce l'incremento dei riusi a terzetti."),
    MutazioneRC("M20_ORDINE_RIGHE_COPPIE", "moduli/generazione.py", "studenti = sorted(studenti, key=chiave_ordinamento_studente)", "studenti = list(studenti)  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_metamorfico_input.py::test_permuta_righe_non_cambia_il_risultato_con_stesso_seed[coppie]",), descrizione="Rende di nuovo significativo l'ordine delle righe a coppie."),
    MutazioneRC("M21_ORDINE_RIGHE_TERZETTI", "moduli/motore_terzetti.py", "studenti = sorted(studenti, key=chiave_ordinamento_studente)", "studenti = list(studenti)  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_metamorfico_input.py::test_permuta_righe_non_cambia_il_risultato_con_stesso_seed[terzetti]",), descrizione="Rende di nuovo significativo l'ordine delle righe a terzetti."),
    MutazioneRC("M22_DIACRITICI", "moduli/studenti.py", 'normalizzato = unicodedata.normalize("NFKD", nome).casefold()', 'normalizzato = nome.casefold()  # MUTAZIONE RC', (f"{_TEST_CONTRATTI}::test_ordinamento_canonico_studenti_ignora_i_diacritici",), descrizione="Reintroduce l'ordine Unicode grezzo per i cognomi accentati."),
    MutazioneRC("M23_MEMO_TERZETTI", "moduli/motore_terzetti.py", "if chiave_stato in stati_falliti:", "if False and chiave_stato in stati_falliti:  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_fuzzing_riduzione.py::test_memo_terzetti_taglia_stati_duplicati_senza_accettare_soluzione_piu_sporca",), descrizione="Disattiva il riuso degli stati terzetti già dimostrati impossibili."),
    MutazioneRC("M24_PRIMA_RISERVA_TERZETTI", "moduli/motore_terzetti.py", "if chiave_soluzione[0] == 0 and chiave_soluzione[1] == 0:", "if True:  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_fuzzing_riduzione.py::test_memo_terzetti_taglia_stati_duplicati_senza_accettare_soluzione_piu_sporca",), descrizione="Ripristina il comportamento 'prima riserva che riesce', anche se più sporca."),
    MutazioneRC("M25_DOPPIO_AVVIO_GUI", "moduli/stato_sessione.py", "return not (\n        bool(worker_mensile_presente)", "return True or not (  # MUTAZIONE RC\n        bool(worker_mensile_presente)", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_doppio_avvio_e_bloccato_da_qualunque_elaborazione_attiva",), descrizione="Disattiva la guardia difensiva contro avvii sovrapposti."),
    MutazioneRC("M26_MENSILE_INDICE_FANTASMA", "moduli/stato_mensile.py", "self.scollega_dallo_storico()", "self.indice_storico = None  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_eliminare_la_voce_corrente_non_lascia_salvata_senza_indice",), descrizione="Lascia SALVATA una disposizione la cui voce Storico e' stata eliminata."),
    MutazioneRC("M27_TRANSIZIONE_ANNUALE_LIBERA", "moduli/stato_annuale.py", "if self.fase not in ammesse:", "if False and self.fase not in ammesse:  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_annuale_rifiuta_salvataggio_senza_anteprima",), descrizione="Permette transizioni Annuali fuori dalla macchina a stati."),
    MutazioneRC("M28_PROCESSO_FANTASMA", "moduli/supervisione_processi.py", "if not (terminale_ricevuto or canale_inutilizzabile):", "if True or not (terminale_ricevuto or canale_inutilizzabile):  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_processo_appeso_dopo_terminale_viene_terminato_senza_join_infinito",), descrizione="Impedisce la terminazione finita di un figlio rimasto vivo dopo l'esito terminale."),
    MutazioneRC("M29_AULA_ANNUALE_TARDIVA", "moduli/stato_sessione.py", "and aula_corrente is aula_attesa", "and True  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_risultato_tardivo_richiede_stessa_classe_studenti_e_aula_per_identita",), descrizione="Permette di applicare un risultato asincrono a un'Aula cambiata dopo l'avvio."),
    MutazioneRC("M30_PREPARAZIONE_ANNUALE_BLOCCA_GUI", "moduli/flusso_annuale_ui.py", "self._imposta_modalita_elaborazione(False)", "self._imposta_modalita_elaborazione(True)  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), occorrenza=2, descrizione="Lascia congelata la GUI quando il bridge Annuale fallisce prima dello start."),
    MutazioneRC("M31_DOPPIO_SALVATAGGIO_STATO", "moduli/stato_mensile.py", "if self.fase != FaseMensile.DA_SALVARE:", "if False and self.fase != FaseMensile.DA_SALVARE:  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_mensile_non_puo_essere_marcato_salvato_due_volte",), descrizione="Permette di marcare come salvato due volte lo stesso Mensile."),
    MutazioneRC("M32_DOPPIO_SALVATAGGIO_GUI", "moduli/salvataggio_mensile_ui.py", "if not self.sessione.mensile.non_salvata:", "if False and not self.sessione.mensile.non_salvata:  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), descrizione="Rimuove la guardia GUI contro una seconda scrittura nello Storico."),
    MutazioneRC("M33_OWNERSHIP_MENSILE_PREMATURA", "moduli/flusso_mensile_ui.py", "self.timer_messaggi.stop()\n            self._imposta_modalita_elaborazione(False)", "self.timer_messaggi.stop()\n            self.worker_thread = None  # MUTAZIONE RC\n            self._imposta_modalita_elaborazione(False)", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), occorrenza=1, descrizione="Rilascia il QThread Mensile al messaggio terminale invece che a finished."),
    MutazioneRC("M34_OWNERSHIP_ANNUALE_PREMATURA", "moduli/flusso_annuale_ui.py", "self.timer_messaggi.stop()\n        self._imposta_modalita_elaborazione(False)", "self.timer_messaggi.stop()\n        self.season_worker = None  # MUTAZIONE RC\n        self._imposta_modalita_elaborazione(False)", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), occorrenza=1, descrizione="Rilascia il bridge Annuale prima del vero finished."),
    MutazioneRC("M35_FINISHED_MENSILE_ASSENTE", "moduli/flusso_mensile_ui.py", "worker.finished.connect(self._worker_mensile_finito)", "# worker.finished disconnesso  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), occorrenza=1, descrizione="Rimuove uno dei collegamenti finished che custodiscono l'ownership Mensile."),
    MutazioneRC("M36_CLOSEEVENT_BYPASS", "postiperfetti.py", "return CicloVitaUIMixin.closeEvent(self, event)", "return super().closeEvent(event)  # MUTAZIONE RC", ("documentazione/sviluppo/test/validazione_rc/test_stati_gui_fault_injection.py::test_campagna_stati_gui_e_fault_injection_e_verde",), descrizione="Bypassa il gestore protettivo della chiusura finestra."),
)


def _sostituisci(testo: str, mutazione: MutazioneRC) -> str:
    occorrenze = []
    posizione = 0
    while True:
        indice = testo.find(mutazione.cerca, posizione)
        if indice < 0:
            break
        occorrenze.append(indice)
        posizione = indice + len(mutazione.cerca)
    if not occorrenze:
        raise ValueError(f"Pattern non trovato per {mutazione.id}")
    if mutazione.occorrenza == 0:
        return testo.replace(mutazione.cerca, mutazione.sostituisci)
    if len(occorrenze) < mutazione.occorrenza:
        raise ValueError(
            f"{mutazione.id}: richiesto match {mutazione.occorrenza}, trovati {len(occorrenze)}"
        )
    indice = occorrenze[mutazione.occorrenza - 1]
    return (
        testo[:indice]
        + mutazione.sostituisci
        + testo[indice + len(mutazione.cerca):]
    )


def _copia_minima(root: Path, destinazione: Path) -> None:
    ignora = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo")
    for nome in ("moduli", "documentazione"):
        sorgente = root / nome
        if sorgente.exists():
            shutil.copytree(sorgente, destinazione / nome, ignore=ignora)
    for nome in ("postiperfetti.py",):
        sorgente = root / nome
        if sorgente.exists():
            shutil.copy2(sorgente, destinazione / nome)


def esegui_mutation_testing(
    root: str | Path,
    *,
    timeout_s: float = 12.0,
    ids: Iterable[str] | None = None,
) -> RapportoMutazioniRC:
    root = Path(root).resolve()
    selezione = set(ids or ())
    mutazioni = [m for m in MUTAZIONI_FASE5 if not selezione or m.id in selezione]
    risultati: list[EsitoMutazioneRC] = []
    inizio = time.monotonic()

    for mutazione in mutazioni:
        t0 = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="postiperfetti-mutazione-") as temp:
                copia = Path(temp)
                _copia_minima(root, copia)
                file_mutato = copia / mutazione.file
                testo = file_mutato.read_text(encoding="utf-8")
                file_mutato.write_text(_sostituisci(testo, mutazione), encoding="utf-8")
                ambiente = dict(os.environ)
                ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
                pythonpath = [str(copia / "documentazione" / "sviluppo"), str(copia)]
                if ambiente.get("PYTHONPATH"):
                    pythonpath.append(ambiente["PYTHONPATH"])
                ambiente["PYTHONPATH"] = os.pathsep.join(pythonpath)
                processo = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", *mutazione.test],
                    cwd=copia,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout_s,
                    env=ambiente,
                )
                stato = "ucciso" if processo.returncode != 0 else "sopravvissuto"
                dettaglio = "\n".join(processo.stdout.splitlines()[-8:])
        except subprocess.TimeoutExpired:
            stato = "ucciso_timeout"
            dettaglio = (
                f"Mutante ucciso per regressione prestazionale: "
                f"il test sentinella ha superato {timeout_s:.1f}s."
            )
        except Exception as errore:  # pragma: no cover - difesa CLI
            stato = "errore"
            dettaglio = f"{type(errore).__name__}: {errore}"
        risultati.append(EsitoMutazioneRC(
            id=mutazione.id,
            stato=stato,
            durata_s=round(time.monotonic() - t0, 6),
            test=mutazione.test,
            descrizione=mutazione.descrizione,
            dettaglio=dettaglio,
        ))

    return RapportoMutazioniRC(
        mutanti=len(risultati),
        uccisi=sum(r.stato in {"ucciso", "ucciso_timeout"} for r in risultati),
        sopravvissuti=sum(r.stato == "sopravvissuto" for r in risultati),
        timeout=sum(r.stato == "ucciso_timeout" for r in risultati),
        errori=sum(r.stato == "errore" for r in risultati),
        durata_s=round(time.monotonic() - inizio, 6),
        dettaglio=tuple(risultati),
    )


def scrivi_rapporto_mutazioni(rapporto: RapportoMutazioniRC, destinazione: str | Path) -> None:
    path = Path(destinazione)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
