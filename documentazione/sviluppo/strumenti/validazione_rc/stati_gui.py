# -*- coding: utf-8 -*-
"""Macchina a stati e fault injection headless per i flussi GUI della RC.

Non importa Qt: esercita gli oggetti di stato produttivi, la persistenza e i
processi puri. Le verifiche di orchestrazione Qt che non sono separabili dalla
GUI vengono espresse come contratti strutturali sul sorgente attivo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import random
from pathlib import Path
import tempfile

from moduli.configurazione import (
    AZIONE_FILE_ASSENTE_ANNULLA,
    AZIONE_FILE_ASSENTE_AZZERA,
    ESITO_SALVATAGGIO_ANNULLATO,
    ESITO_SALVATAGGIO_AZZERATO,
    ESITO_SALVATAGGIO_ERRORE,
    ConfigurazioneApp,
)
from moduli.processo_annuale import (
    esegui_annuale_coppie_in_processo,
    esegui_annuale_terzetti_in_processo,
)
from moduli.processo_mensile import esegui_mensile_terzetti_in_processo
from moduli.stato_annuale import FaseAnnuale, StatoAnnuale
from moduli.stato_mensile import FaseMensile, StatoMensile
from moduli.stato_sessione import puo_avviare_elaborazione, StatoSessione
from moduli.supervisione_processi import finalizza_processo


@dataclass(frozen=True, slots=True)
class EsitoControlloGUIRC:
    nome: str
    verde: bool
    dettaglio: str = ""


@dataclass(frozen=True, slots=True)
class RapportoGUIRC:
    controlli: int
    verdi: int
    rossi: int
    dettaglio: tuple[EsitoControlloGUIRC, ...]

    @property
    def verde(self) -> bool:
        return self.rossi == 0

    def come_dict(self) -> dict:
        return {
            "campagna": "fase7_stati_gui_fault_injection",
            "controlli": self.controlli,
            "verdi": self.verdi,
            "rossi": self.rossi,
            "verde": self.verde,
            "dettaglio": [asdict(x) for x in self.dettaglio],
        }


class _ConnessioneFinta:
    def __init__(self):
        self.messaggi = []
        self.chiusa = False

    def send(self, messaggio):
        self.messaggi.append(messaggio)

    def close(self):
        self.chiusa = True


class _ConnessioneSendRotta(_ConnessioneFinta):
    def send(self, _messaggio):
        raise BrokenPipeError("fault injection send")


class _EventoFinto:
    def is_set(self):
        return False


def _config_temp(percorso: Path) -> ConfigurazioneApp:
    cfg = object.__new__(ConfigurazioneApp)
    cfg.file_config = str(percorso)
    cfg.file_backup = str(percorso.with_name("backup.json"))
    cfg.avviso_recupero = None
    cfg.gestore_file_assente = None
    cfg.gestore_azzeramento_completato = None
    cfg.ultimo_esito_salvataggio = None
    cfg._file_config_presente_nella_sessione = False
    cfg.config_data = ConfigurazioneApp._carica_configurazione_default(cfg)
    return cfg


def _controlla_transizioni_annuali() -> list[EsitoControlloGUIRC]:
    esiti = []
    transizioni = {
        "anteprima": (
            {FaseAnnuale.ELABORAZIONE},
            lambda s: s.apri_anteprima(),
            FaseAnnuale.ANTEPRIMA,
        ),
        "annullata": (
            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
            lambda s: s.segna_annullata(),
            FaseAnnuale.ANNULLATA,
        ),
        "salvata": (
            {FaseAnnuale.ANTEPRIMA},
            lambda s: s.segna_salvata(),
            FaseAnnuale.SALVATA,
        ),
        "scartata": (
            {FaseAnnuale.ANTEPRIMA},
            lambda s: s.segna_scartata(),
            FaseAnnuale.SCARTATA,
        ),
        "fallita": (
            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
            lambda s: s.segna_fallita(),
            FaseAnnuale.FALLITA,
        ),
    }
    for nome, (ammesse, azione, destinazione) in transizioni.items():
        for fase in FaseAnnuale:
            stato = StatoAnnuale(fase=fase)
            if fase in ammesse:
                try:
                    azione(stato)
                    ok = stato.fase == destinazione
                    dettaglio = ""
                except Exception as exc:
                    ok = False
                    dettaglio = f"transizione lecita ha sollevato {type(exc).__name__}: {exc}"
            else:
                try:
                    azione(stato)
                except RuntimeError:
                    ok = stato.fase == fase
                    dettaglio = ""
                except Exception as exc:
                    ok = False
                    dettaglio = f"eccezione inattesa {type(exc).__name__}: {exc}"
                else:
                    ok = False
                    dettaglio = f"transizione impossibile accettata: {fase.value} -> {nome}"
            esiti.append(EsitoControlloGUIRC(
                f"annuale:{fase.value}:{nome}", ok, dettaglio
            ))
    return esiti


def _controlla_stato_mensile() -> list[EsitoControlloGUIRC]:
    esiti = []
    stato = StatoMensile(
        fase=FaseMensile.SALVATA,
        modo="coppie",
        assegnatore=object(),
        nome="2A - Mensile Coppie - 01",
        progressivo=1,
        data_creazione="07/08/2026 03:00",
        file_origine="2A.txt",
        nome_classe="2A",
        genere_misto=False,
        indice_storico=3,
    )
    stato.aggiorna_indice_dopo_eliminazione(3)
    esiti.append(EsitoControlloGUIRC(
        "mensile:elimina_voce_corrente_atomica",
        stato.fase == FaseMensile.DA_SALVARE and stato.indice_storico is None,
        f"fase={stato.fase.value}, indice={stato.indice_storico}",
    ))

    stato = StatoMensile(
        fase=FaseMensile.SALVATA,
        modo="coppie",
        assegnatore=object(),
        nome="2A - Mensile Coppie - 03",
        progressivo=3,
        data_creazione="07/08/2026 03:00",
        file_origine="2A.txt",
        nome_classe="2A",
        genere_misto=False,
        indice_storico=5,
    )
    stato.aggiorna_indice_dopo_eliminazione(2)
    esiti.append(EsitoControlloGUIRC(
        "mensile:elimina_voce_precedente_trasla_indice",
        stato.salvata and stato.indice_storico == 4,
        f"fase={stato.fase.value}, indice={stato.indice_storico}",
    ))
    return esiti


def _controlla_doppio_avvio() -> list[EsitoControlloGUIRC]:
    esiti = []
    for mensile in (False, True):
        for annuale in (False, True):
            for stato_annuale in (False, True):
                atteso = not (mensile or annuale or stato_annuale)
                ottenuto = puo_avviare_elaborazione(
                    worker_mensile_presente=mensile,
                    worker_annuale_presente=annuale,
                    annuale_in_corso=stato_annuale,
                )
                esiti.append(EsitoControlloGUIRC(
                    f"avvio:m{int(mensile)}:a{int(annuale)}:s{int(stato_annuale)}",
                    ottenuto == atteso,
                    f"atteso={atteso}, ottenuto={ottenuto}",
                ))
    return esiti


def _controlla_fault_persistenza() -> list[EsitoControlloGUIRC]:
    esiti = []
    with tempfile.TemporaryDirectory(prefix="postiperfetti-fault-gui-") as temp:
        temp = Path(temp)

        # Fallimento della sostituzione atomica: il file precedente deve restare
        # intatto e il temporaneo deve essere rimosso.
        cfg = _config_temp(temp / "config.json")
        cfg.salva_configurazione()
        precedente = Path(cfg.file_config).read_text(encoding="utf-8")
        cfg.config_data["tema"] = "chiaro"
        replace_originale = os.replace
        try:
            def _fallisci_replace(*_args, **_kwargs):
                raise OSError("fault injection os.replace")
            os.replace = _fallisci_replace
            ok = cfg.salva_configurazione()
        finally:
            os.replace = replace_originale
        invariato = Path(cfg.file_config).read_text(encoding="utf-8") == precedente
        esiti.append(EsitoControlloGUIRC(
            "persistenza:replace_fallisce_rollback_disco",
            (not ok and cfg.ultimo_esito_salvataggio == ESITO_SALVATAGGIO_ERRORE
             and invariato and not Path(cfg.file_config + ".tmp").exists()),
            f"esito={cfg.ultimo_esito_salvataggio}, disco_invariato={invariato}",
        ))

        # File scomparso + Annulla: non deve creare né azzerare nulla.
        cfg = _config_temp(temp / "assente-annulla.json")
        cfg._file_config_presente_nella_sessione = True
        cfg.config_data["studenti_trio_contatore"] = {"Alfa Anna": 2}
        cfg.gestore_file_assente = lambda _p: AZIONE_FILE_ASSENTE_ANNULLA
        ok = cfg.salva_configurazione()
        esiti.append(EsitoControlloGUIRC(
            "persistenza:file_assente_annulla_preserva_memoria",
            (not ok and cfg.ultimo_esito_salvataggio == ESITO_SALVATAGGIO_ANNULLATO
             and cfg.config_data["studenti_trio_contatore"] == {"Alfa Anna": 2}
             and not Path(cfg.file_config).exists()),
            f"esito={cfg.ultimo_esito_salvataggio}",
        ))

        # File scomparso + Azzera: il nuovo file deve essere coerente e vuoto.
        cfg = _config_temp(temp / "assente-azzera.json")
        cfg._file_config_presente_nella_sessione = True
        cfg.config_data["studenti_trio_contatore"] = {"Alfa Anna": 2}
        cfg.gestore_file_assente = lambda _p: AZIONE_FILE_ASSENTE_AZZERA
        ok = cfg.salva_configurazione()
        esiti.append(EsitoControlloGUIRC(
            "persistenza:file_assente_azzera_riparte_pulito",
            (not ok and cfg.ultimo_esito_salvataggio == ESITO_SALVATAGGIO_AZZERATO
             and cfg.config_data["studenti_trio_contatore"] == {}
             and Path(cfg.file_config).exists()),
            f"esito={cfg.ultimo_esito_salvataggio}",
        ))
    return esiti


def _controlla_fault_processi() -> list[EsitoControlloGUIRC]:
    esiti = []
    casi = (
        ("mensile_terzetti", lambda c: esegui_mensile_terzetti_in_processo(b"non-pickle", c)),
        ("annuale_coppie", lambda c: esegui_annuale_coppie_in_processo(b"non-pickle", c, _EventoFinto())),
        ("annuale_terzetti", lambda c: esegui_annuale_terzetti_in_processo(b"non-pickle", c, _EventoFinto())),
    )
    for nome, esegui in casi:
        conn = _ConnessioneFinta()
        try:
            esegui(conn)
            terminali = [m for m in conn.messaggi if m.get("tipo") in {"risultato", "errore", "eccezione"}]
            ok = conn.chiusa and len(terminali) == 1 and terminali[0].get("tipo") == "eccezione"
            dettaglio = f"messaggi={len(conn.messaggi)}, terminali={[m.get('tipo') for m in terminali]}"
        except Exception as exc:
            ok = False
            dettaglio = f"eccezione uscita dal processo puro: {type(exc).__name__}: {exc}"
        esiti.append(EsitoControlloGUIRC(f"processo:{nome}:payload_malformato", ok, dettaglio))

    # Se il canale di ritorno si rompe, il figlio non deve propagare BrokenPipe
    # oltre il proprio entry-point e deve comunque chiudere la connessione.
    for nome, esegui in casi:
        conn = _ConnessioneSendRotta()
        try:
            esegui(conn)
            ok = conn.chiusa
            dettaglio = f"chiusa={conn.chiusa}"
        except Exception as exc:
            ok = False
            dettaglio = f"BrokenPipe propagato: {type(exc).__name__}: {exc}"
        esiti.append(EsitoControlloGUIRC(
            f"processo:{nome}:canale_send_rotto_non_propaga", ok, dettaglio
        ))
    return esiti


class _ProcessoFintoSupervisione:
    def __init__(self, *, esce_al_join=False, ignora_terminate=False):
        self.pid = 7373
        self._vivo = True
        self.esce_al_join = esce_al_join
        self.ignora_terminate = ignora_terminate
        self.join_timeout = []
        self.terminate_chiamato = False
        self.kill_chiamato = False

    def is_alive(self):
        return self._vivo

    def join(self, timeout=None):
        self.join_timeout.append(timeout)
        if self.esce_al_join:
            self._vivo = False

    def terminate(self):
        self.terminate_chiamato = True
        if not self.ignora_terminate:
            self._vivo = False

    def kill(self):
        self.kill_chiamato = True
        self._vivo = False


def _controlla_supervisione_processi() -> list[EsitoControlloGUIRC]:
    esiti = []

    processo = _ProcessoFintoSupervisione()
    chiusura = finalizza_processo(
        processo, terminale_ricevuto=True, canale_inutilizzabile=False, tempo_grazia=0.0
    )
    esiti.append(EsitoControlloGUIRC(
        "processo:terminale_ma_figlio_appeso_viene_terminato",
        processo.terminate_chiamato and not chiusura.ancora_vivo
        and all(t is not None for t in processo.join_timeout),
        f"terminate={processo.terminate_chiamato}, join={processo.join_timeout}",
    ))

    processo = _ProcessoFintoSupervisione(esce_al_join=True)
    chiusura = finalizza_processo(
        processo, terminale_ricevuto=True, canale_inutilizzabile=False, tempo_grazia=0.0
    )
    esiti.append(EsitoControlloGUIRC(
        "processo:uscita_nella_grazia_non_forzata",
        not processo.terminate_chiamato and not chiusura.uscita_forzata,
        f"terminate={processo.terminate_chiamato}",
    ))

    processo = _ProcessoFintoSupervisione()
    chiusura = finalizza_processo(
        processo, terminale_ricevuto=False, canale_inutilizzabile=True, tempo_grazia=0.0
    )
    esiti.append(EsitoControlloGUIRC(
        "processo:canale_perso_figlio_terminato",
        processo.terminate_chiamato and not chiusura.ancora_vivo,
        f"terminate={processo.terminate_chiamato}",
    ))

    processo = _ProcessoFintoSupervisione()
    chiusura = finalizza_processo(
        processo, terminale_ricevuto=False, canale_inutilizzabile=False, tempo_grazia=0.0
    )
    esiti.append(EsitoControlloGUIRC(
        "processo:calcolo_legittimo_non_terminato",
        not processo.terminate_chiamato and chiusura.ancora_vivo,
        f"terminate={processo.terminate_chiamato}",
    ))

    processo = _ProcessoFintoSupervisione(ignora_terminate=True)
    chiusura = finalizza_processo(
        processo, terminale_ricevuto=True, canale_inutilizzabile=False, tempo_grazia=0.0
    )
    esiti.append(EsitoControlloGUIRC(
        "processo:kill_fallback_se_terminate_non_basta",
        processo.kill_chiamato and chiusura.kill_usato and not chiusura.ancora_vivo,
        f"kill={processo.kill_chiamato}",
    ))
    return esiti


def _controlla_sequenze_stato(
    *, seed: int = 20260807, sequenze: int = 1000, passi: int = 40
) -> list[EsitoControlloGUIRC]:
    """Confronta migliaia di transizioni con un modello di riferimento puro."""
    rng = random.Random(seed)
    operazioni = (
        "carica", "chiudi", "prepara", "salva", "elimina", "scollega",
        "rinomina", "avvia_annuale", "annulla_annuale", "anteprima",
        "annullata", "salvata_annuale", "scartata_annuale",
        "fallita_annuale", "geometria",
    )
    transizioni = 0
    try:
        for indice_seq in range(sequenze):
            sessione = StatoSessione()
            fase_mensile = FaseMensile.VUOTA
            indice_storico = None
            fase_annuale = FaseAnnuale.INATTIVA
            classe = False

            for passo in range(passi):
                op = rng.choice(operazioni)
                transizioni += 1

                if op == "carica" and not sessione.annuale.in_corso:
                    sessione.carica_classe(
                        [object(), object()], f"RC-{indice_seq}.txt"
                    )
                    classe = True
                    fase_mensile = FaseMensile.VUOTA
                    indice_storico = None
                    fase_annuale = FaseAnnuale.INATTIVA

                elif op == "chiudi" and not sessione.annuale.in_corso:
                    sessione.chiudi_classe()
                    classe = False
                    fase_mensile = FaseMensile.VUOTA
                    indice_storico = None
                    fase_annuale = FaseAnnuale.INATTIVA

                elif op == "prepara" and classe and not sessione.annuale.in_corso:
                    sessione.mensile.prepara_coppie(
                        object(), nome="RC Mensile", progressivo=1,
                        data_creazione="07/08/2026 03:00",
                        file_origine=sessione.file_origine, nome_classe="RC",
                        genere_misto=False,
                    )
                    fase_mensile = FaseMensile.DA_SALVARE
                    indice_storico = None

                elif op == "salva":
                    prima = (sessione.mensile.fase, sessione.mensile.indice_storico)
                    if fase_mensile == FaseMensile.DA_SALVARE:
                        nuovo = rng.randrange(0, 6)
                        sessione.mensile.segna_salvata(nuovo)
                        fase_mensile = FaseMensile.SALVATA
                        indice_storico = nuovo
                    else:
                        try:
                            sessione.mensile.segna_salvata(0)
                        except RuntimeError:
                            pass
                        else:
                            raise AssertionError("salvataggio Mensile illecito accettato")
                        assert (sessione.mensile.fase, sessione.mensile.indice_storico) == prima

                elif op == "elimina":
                    eliminato = rng.randrange(0, 6)
                    sessione.mensile.aggiorna_indice_dopo_eliminazione(eliminato)
                    if indice_storico is not None:
                        if indice_storico == eliminato:
                            fase_mensile = FaseMensile.DA_SALVARE
                            indice_storico = None
                        elif indice_storico > eliminato:
                            indice_storico -= 1

                elif op == "scollega":
                    sessione.mensile.scollega_dallo_storico()
                    if fase_mensile != FaseMensile.VUOTA:
                        fase_mensile = FaseMensile.DA_SALVARE
                        indice_storico = None

                elif op == "rinomina":
                    if fase_mensile == FaseMensile.VUOTA:
                        try:
                            sessione.mensile.rinomina("Nuovo")
                        except RuntimeError:
                            pass
                        else:
                            raise AssertionError("rinomina senza risultato accettata")
                    else:
                        sessione.mensile.rinomina(f"RC-{passo}")

                elif op == "avvia_annuale" and classe and not sessione.annuale.in_corso:
                    sessione.annuale.avvia(rng.randint(1, 10), ora=float(passo))
                    fase_annuale = FaseAnnuale.ELABORAZIONE

                elif op == "annulla_annuale":
                    ottenuto = sessione.annuale.richiedi_annullamento()
                    atteso = fase_annuale == FaseAnnuale.ELABORAZIONE
                    assert ottenuto == atteso
                    if atteso:
                        fase_annuale = FaseAnnuale.ANNULLAMENTO_RICHIESTO

                elif op in {
                    "anteprima", "annullata", "salvata_annuale",
                    "scartata_annuale", "fallita_annuale",
                }:
                    tabella = {
                        "anteprima": (
                            {FaseAnnuale.ELABORAZIONE},
                            FaseAnnuale.ANTEPRIMA, sessione.annuale.apri_anteprima,
                        ),
                        "annullata": (
                            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
                            FaseAnnuale.ANNULLATA, sessione.annuale.segna_annullata,
                        ),
                        "salvata_annuale": (
                            {FaseAnnuale.ANTEPRIMA},
                            FaseAnnuale.SALVATA, sessione.annuale.segna_salvata,
                        ),
                        "scartata_annuale": (
                            {FaseAnnuale.ANTEPRIMA},
                            FaseAnnuale.SCARTATA, sessione.annuale.segna_scartata,
                        ),
                        "fallita_annuale": (
                            {FaseAnnuale.ELABORAZIONE, FaseAnnuale.ANNULLAMENTO_RICHIESTO},
                            FaseAnnuale.FALLITA, sessione.annuale.segna_fallita,
                        ),
                    }
                    ammesse, destinazione, azione = tabella[op]
                    prima = sessione.annuale.fase
                    if fase_annuale in ammesse:
                        azione()
                        fase_annuale = destinazione
                    else:
                        try:
                            azione()
                        except RuntimeError:
                            pass
                        else:
                            raise AssertionError(
                                f"transizione Annuale illecita accettata: {op}"
                            )
                        assert sessione.annuale.fase == prima

                elif op == "geometria":
                    valore = rng.choice(("coppie", "terzetti"))
                    sessione.imposta_geometria(valore)
                    assert sessione.geometria == valore

                assert sessione.classe_caricata == classe
                assert sessione.mensile.fase == fase_mensile
                assert sessione.mensile.indice_storico == indice_storico
                assert sessione.annuale.fase == fase_annuale
                assert sessione.annuale.in_corso == (
                    fase_annuale in {
                        FaseAnnuale.ELABORAZIONE,
                        FaseAnnuale.ANNULLAMENTO_RICHIESTO,
                    }
                )
                if fase_mensile == FaseMensile.SALVATA:
                    assert indice_storico is not None
                else:
                    assert indice_storico is None
                if not classe:
                    assert sessione.aula is None
                    assert fase_mensile == FaseMensile.VUOTA
                    assert fase_annuale == FaseAnnuale.INATTIVA
    except Exception as exc:
        return [EsitoControlloGUIRC(
            "sequenze:macchina_stati_randomizzata", False,
            f"dopo {transizioni} transizioni: {type(exc).__name__}: {exc}",
        )]

    return [EsitoControlloGUIRC(
        "sequenze:macchina_stati_randomizzata", True,
        f"{sequenze} sequenze, {transizioni} transizioni",
    )]

def _controlla_contratti_sorgente(radice: Path) -> list[EsitoControlloGUIRC]:
    mensile = (radice / "moduli" / "flusso_mensile_ui.py").read_text(encoding="utf-8")
    annuale = (radice / "moduli" / "flusso_annuale_ui.py").read_text(encoding="utf-8")
    salvataggio = (radice / "moduli" / "salvataggio_mensile_ui.py").read_text(encoding="utf-8")
    ciclo_vita = (radice / "moduli" / "ciclo_vita_ui.py").read_text(encoding="utf-8")
    principale = (radice / "postiperfetti.py").read_text(encoding="utf-8")
    ponte = (radice / "moduli" / "ponte_processo.py").read_text(encoding="utf-8")
    helper_annuale = annuale[
        annuale.index("    def _fallimento_preparazione_annuale"):
        annuale.index("    def _avvia_annuale_coppie")
    ]
    conclude_annuale = annuale[
        annuale.index("    def _concludi_monitoraggio_annuale"):
        annuale.index("    def _aggiorna_eta_annuale")
    ]
    conclude_terzetti = mensile[
        mensile.index("    def _concludi_mensile_terzetti_processo"):
        mensile.index("    def _elaborazione_terzetti_processo_completata")
    ]
    completata_coppie = mensile[
        mensile.index("    def _elaborazione_completata"):
        mensile.index("    def _mostra_popup_riepilogo_terzetti")
    ]
    controlli = {
        "sorgente:doppio_avvio_guardia": "puo_avviare_elaborazione(" in mensile,
        "sorgente:doppio_salvataggio_mensile_guardia": (
            "if not self.sessione.mensile.non_salvata:" in salvataggio
        ),
        "sorgente:ownership_mensile_fino_finished": (
            mensile.count("finished.connect(self._worker_mensile_finito)") >= 2
            and "self.worker_thread = None" not in conclude_terzetti
            and "self.worker_thread = None" not in completata_coppie
        ),
        "sorgente:ownership_annuale_fino_finished": (
            annuale.count("finished.connect(self._worker_annuale_finito)") >= 2
            and "self.season_worker = None" not in conclude_annuale
        ),
        "sorgente:close_event_passa_dal_gestore_protettivo": (
            "CicloVitaUIMixin.closeEvent(self, event)" in principale
            and "worker_mensile.isRunning()" in ciclo_vita
            and "worker_annuale.isRunning()" in ciclo_vita
        ),
        "sorgente:prepara_mensile_coppie_protetto": "Impossibile preparare il calcolo Mensile a coppie" in mensile,
        "sorgente:prepara_mensile_terzetti_protetto": "Impossibile preparare il processo Mensile a terzetti" in mensile,
        "sorgente:prepara_annuale_coppie_protetto": "Impossibile preparare il processo Annuale a coppie" in annuale,
        "sorgente:prepara_annuale_terzetti_protetto": "Impossibile preparare il processo Annuale a terzetti" in annuale,
        "sorgente:fallimento_preparazione_annuale_ripristina_gui": (
            "self._contesto_annuale = None" in helper_annuale
            and "self.season_worker = None" in helper_annuale
            and "self.timer_messaggi.stop()" in helper_annuale
            and "self._imposta_modalita_elaborazione(False)" in helper_annuale
        ),
        "sorgente:risultati_tardivi_usano_regola_comune": (
            "risultato_appartiene_sessione(" in mensile
            and "risultato_appartiene_sessione(" in annuale
        ),
        "sorgente:ponte_finalizzazione_limitata": "finalizza_processo(" in ponte,
        "sorgente:ponte_nessun_join_indefinito": "processo.join()" not in ponte,
    }
    return [EsitoControlloGUIRC(nome, ok, "" if ok else "contratto assente") for nome, ok in controlli.items()]


def campagna_stati_gui_fault_rc(radice: str | Path) -> RapportoGUIRC:
    radice = Path(radice).resolve()
    esiti: list[EsitoControlloGUIRC] = []
    esiti.extend(_controlla_transizioni_annuali())
    esiti.extend(_controlla_stato_mensile())
    esiti.extend(_controlla_doppio_avvio())
    esiti.extend(_controlla_fault_persistenza())
    esiti.extend(_controlla_fault_processi())
    esiti.extend(_controlla_supervisione_processi())
    esiti.extend(_controlla_sequenze_stato())
    esiti.extend(_controlla_contratti_sorgente(radice))
    return RapportoGUIRC(
        controlli=len(esiti),
        verdi=sum(x.verde for x in esiti),
        rossi=sum(not x.verde for x in esiti),
        dettaglio=tuple(esiti),
    )


def scrivi_rapporto_gui_rc(rapporto: RapportoGUIRC, destinazione: str | Path) -> None:
    path = Path(destinazione)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
