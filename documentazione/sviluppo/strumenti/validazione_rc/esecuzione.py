# -*- coding: utf-8 -*-
"""Ponti headless fra il corpus RC e i motori produttivi.

Queste funzioni eseguono il motore reale ma consegnano il risultato ai
controllori indipendenti di ``risultati.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie
from moduli.configurazione import ConfigurazioneApp
from moduli.generazione import calcola_miglior_mese
from moduli.motore_terzetti import calcola_miglior_mese_terzetti
from moduli.studenti import crea_studenti_da_dati_validati

from .generatori import dati_validati_da_classe
from .modelli import ClasseRC
from .risultati import VerificaRisultatoRC, verifica_aula_rc


@dataclass(frozen=True, slots=True)
class EsecuzioneMensileRC:
    modalita: str
    successo: bool
    verifica: VerificaRisultatoRC | None
    risultato: object | None
    aula: ConfigurazioneAula | None


def configurazione_vuota_rc() -> ConfigurazioneApp:
    """Crea la configurazione corrente senza leggere o scrivere dati utente."""
    classe = ConfigurazioneApp
    config = classe.__new__(classe)
    config.config_data = {
        "storico_assegnazioni": [],
        "coppie_da_evitare": [],
        "adiacenze_terzetti_da_evitare": [],
        "studenti_trio_contatore": {},
        "studenti_vicino_fisso_contatore": {},
        "tema": "scuro",
    }
    config.avviso_recupero = None
    config.gestore_file_assente = None
    config.gestore_azzeramento_completato = None
    config.ultimo_esito_salvataggio = None
    config.file_config = "non_usato_validazione_rc.json"
    config.file_backup = "non_usato_validazione_rc.backup.json"
    config._file_config_presente_nella_sessione = False
    return config


def _studenti_produttivi(classe: ClasseRC):
    studenti = crea_studenti_da_dati_validati(dati_validati_da_classe(classe))
    fisso = next((s for s in studenti if s.nota_posizione == "FISSO"), None)
    return studenti, fisso


def esegui_mensile_coppie_rc(
    classe: ClasseRC,
    *,
    seed: int,
    genere_misto: bool = False,
    posti_per_fila: int = 6,
    posizione_trio: str = "centro",
    num_candidati: int = 3,
) -> EsecuzioneMensileRC:
    studenti, fisso = _studenti_produttivi(classe)
    ha_fisso = fisso is not None
    num_file = numero_minimo_file_coppie(
        classe.numero_studenti,
        posti_per_fila,
        posizione_trio=posizione_trio,
        ha_fisso=ha_fisso,
    )
    aula = ConfigurazioneAula("RC coppie")
    aula.crea_layout_standard(
        classe.numero_studenti,
        num_file=num_file,
        posti_per_fila=posti_per_fila,
        posizione_trio=posizione_trio,
        ha_fisso=ha_fisso,
    )
    config = configurazione_vuota_rc()
    migliore, ultimo = calcola_miglior_mese(
        studenti,
        aula,
        config,
        posizione_trio,
        genere_misto,
        fisso,
        coppie_gia_usate=set(),
        num_candidati=num_candidati,
        seed_principale=seed,
        contesto_casuale={"operazione": "validazione_rc", "mese": 1},
    )
    risultato = migliore or ultimo
    if migliore is None:
        return EsecuzioneMensileRC("coppie", False, None, risultato, None)
    verifica = verifica_aula_rc(
        classe,
        migliore.configurazione_aula,
        modalita="coppie",
        posizione_trio=posizione_trio,
    )
    return EsecuzioneMensileRC(
        "coppie", verifica.valido, verifica, migliore, migliore.configurazione_aula
    )


def esegui_mensile_terzetti_rc(
    classe: ClasseRC,
    *,
    seed: int,
    genere_misto: bool = False,
    preferenza_resto2: str = "coppia",
    posizione_blocco_finale: str = "ultima",
    terzetti_per_fila: int = 3,
    num_candidati: int = 2,
) -> EsecuzioneMensileRC:
    studenti, fisso = _studenti_produttivi(classe)
    aula = ConfigurazioneAula("RC terzetti")
    aula.crea_layout_terzetti(
        classe.numero_studenti,
        terzetti_per_fila=terzetti_per_fila,
        posizione_blocco_finale=posizione_blocco_finale,
        ha_fisso=fisso is not None,
        preferenza_resto2=preferenza_resto2,
    )
    capienza = aula.capienza_prima_fila_terzetti()
    gruppi, metadati = calcola_miglior_mese_terzetti(
        studenti,
        genere_misto,
        config_app=configurazione_vuota_rc(),
        preferenza_resto2=preferenza_resto2,
        resto_in_prima_fila=(posizione_blocco_finale == "prima"),
        max_terzetti_prima_fila=capienza["terzetti"],
        max_resti_prima_fila=capienza["resti"],
        num_candidati=num_candidati,
        seed_base=seed,
        contesto_casuale={"operazione": "validazione_rc", "mese": 1},
        restituisci_metadati=True,
    )
    if gruppi is None:
        return EsecuzioneMensileRC("terzetti", False, None, metadati, None)

    esito_piazzamento = aula.piazza_gruppi_terzetti(gruppi)
    if not esito_piazzamento.get("valido_struttura", False) or not esito_piazzamento.get("valido_prima", False):
        return EsecuzioneMensileRC("terzetti", False, None, gruppi, aula)
    aula.rimuovi_banchi_vuoti()
    verifica = verifica_aula_rc(
        classe,
        aula,
        modalita="terzetti",
        preferenza_resto2=preferenza_resto2,
    )
    return EsecuzioneMensileRC("terzetti", verifica.valido, verifica, gruppi, aula)
