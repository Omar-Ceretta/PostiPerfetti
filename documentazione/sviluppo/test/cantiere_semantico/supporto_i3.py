from __future__ import annotations


from strumenti.cantiere_semantico.ambiente import prepara_ambiente_run
from strumenti.cantiere_semantico.modelli import (
    CondizioneRun,
    Modalita,
    ParametriAula,
    ParametriRicerca,
    SpecificaRun,
)
from strumenti.cantiere_semantico.snapshot import (
    crea_snapshot_rotazioni,
    crea_stato_iniziale_id,
)


def config_data_vuota():
    return {
        "storico_assegnazioni": [],
        "coppie_da_evitare": [],
        "adiacenze_terzetti_da_evitare": [],
        "studenti_trio_contatore": {},
        "studenti_vicino_fisso_contatore": {},
        "tema": "scuro",
    }


def configurazione_produttiva_vuota():
    from moduli.configurazione import ConfigurazioneApp

    config = object.__new__(ConfigurazioneApp)
    config.config_data = config_data_vuota()
    config.avviso_recupero = None
    config.gestore_file_assente = None
    config.gestore_azzeramento_completato = None
    config.ultimo_esito_salvataggio = None
    config._file_config_presente_nella_sessione = False
    config.file_config = ""
    config.file_backup = ""
    return config


def studenti_semplici(numero: int):
    from moduli.studenti import Student

    return [
        Student(f"Studente{i:02d}", "Test", "M" if i % 2 else "F")
        for i in range(1, numero + 1)
    ]


def crea_run(
    config,
    *,
    modalita: Modalita,
    numero_mesi: int = 2,
    numero_candidati: int = 2,
    numero_stagioni: int = 2,
    condizione: CondizioneRun = CondizioneRun.SENZA_FISSO,
):
    snapshot = crea_snapshot_rotazioni(config.config_data)
    stato_id = crea_stato_iniziale_id(snapshot)
    extra = {}
    if modalita == Modalita.TERZETTI:
        extra = {
            "resto_in_prima_fila": False,
            "max_terzetti_prima_fila": 2,
            "max_resti_prima_fila": 1,
        }
    run = SpecificaRun(
        run_id=f"run_test_{modalita.value}_{condizione.value}",
        pair_id="pair_test_i3",
        file_classe="classe_test.txt",
        condizione=condizione,
        modalita=modalita,
        seed_principale=123456789,
        numero_mesi=numero_mesi,
        genere_misto_attivo=False,
        stato_iniziale_id=stato_id,
        parametri_ricerca=ParametriRicerca(
            numero_candidati=numero_candidati,
            numero_stagioni_fisso=numero_stagioni,
            budget_secondi=None,
            tetto_stagioni=50,
            convergenza=20,
        ),
        parametri_aula=ParametriAula(
            numero_file=2,
            posti_per_fila=6,
            modalita_trio="centro",
            posizione_blocco_finale="ultima",
            preferenza_resto2="coppia",
            extra=extra,
        ),
    )
    return run, prepara_ambiente_run(config, run, snapshot=snapshot)


def firma_coppie(mesi):
    risultato = []
    for assegnatore in mesi:
        risultato.append({
            "coppie": [
                (a.get_nome_completo(), b.get_nome_completo())
                for a, b, _info in assegnatore.coppie_formate
            ],
            "trio": [
                s.get_nome_completo()
                for s in (getattr(assegnatore, "trio_identificato", None) or [])
            ],
            "fisso": (
                getattr(assegnatore, "studente_fisso", None).get_nome_completo()
                if getattr(assegnatore, "studente_fisso", None) is not None
                else None
            ),
            "gruppo_fisso": [
                s.get_nome_completo()
                for s in (getattr(assegnatore, "gruppo_adiacente_fisso", None) or [])
            ],
            "vicino_fisso": getattr(assegnatore, "nome_adiacente_fisso", None),
            "seed": getattr(assegnatore, "seed_candidato", None),
            "contesto": dict(getattr(assegnatore, "contesto_casuale", {})),
        })
    return risultato


def firma_terzetti(mesi):
    risultato = []
    for mese in mesi:
        risultato.append({
            "gruppi": [
                (
                    gruppo.tipo,
                    tuple(s.get_nome_completo() for s in gruppo.membri),
                )
                for gruppo in mese["gruppi"]
            ],
            "foto": tuple(sorted(mese.get("adiacenze_prima", set()))),
            "casualita": mese.get("metadati_casualita"),
        })
    return risultato
