# -*- coding: utf-8 -*-
"""Property/differential fuzzing deterministico per il Cantiere Validazione RC.

La campagna lavora esclusivamente nel dominio scolastico 12–30.  Genera classi
plausibili con densità, genere, posizioni e Storico variabili e verifica sia i
filtri T1–T4 sia proprietà differenziali dei motori mensili.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
from typing import Iterable
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from moduli.algoritmo import AssegnatorePosti
from moduli.aula import ConfigurazioneAula, numero_minimo_file_coppie
from moduli.generazione import calcola_miglior_mese
from moduli.metrica_pulizia import snapshot_blacklist
from moduli.motore_terzetti import calcola_miglior_mese_terzetti
from moduli.strato_storico import applica_penalita_storico
from moduli.studenti import crea_studenti_da_dati_validati

from .esecuzione import configurazione_vuota_rc
from .generatori import dati_validati_da_classe
from .invarianti import valida_classe_rc
from .modelli import ClasseRC, RelazioneRC, StudenteRC
from .risultati import verifica_aula_rc


@dataclass(frozen=True, slots=True)
class SpecFuzzRC:
    indice: int
    seed_classe: int
    seed_motore: int
    studenti: int
    densita_incompatibilita: float
    quota_livello3: float
    densita_affinita: float
    quota_femmine: float
    numero_prima: int
    numero_ultima: int
    fisso: bool
    densita_storico: float


@dataclass(frozen=True, slots=True)
class AnomaliaFuzzRC:
    id_caso: str
    proprieta: str
    dettaglio: str
    spec: dict


@dataclass(frozen=True, slots=True)
class RapportoFuzzRC:
    seed_base: int
    casi_filtri: int
    coppie_valutate: int
    casi_mensili: int
    verifiche_mensili: int
    timeout_mensili: int
    crash_mensili: int
    anomalie: tuple[AnomaliaFuzzRC, ...]

    @property
    def verde(self) -> bool:
        return not self.anomalie

    def come_dict(self) -> dict:
        return {
            "seed_base": self.seed_base,
            "casi_filtri": self.casi_filtri,
            "coppie_valutate": self.coppie_valutate,
            "casi_mensili": self.casi_mensili,
            "verifiche_mensili": self.verifiche_mensili,
            "timeout_mensili": self.timeout_mensili,
            "crash_mensili": self.crash_mensili,
            "anomalie": [asdict(a) for a in self.anomalie],
            "verde": self.verde,
        }


def costruisci_spec_fuzz(*, indice: int, seed_base: int) -> SpecFuzzRC:
    rng = random.Random(seed_base + indice * 104729)
    n = rng.randint(12, 30)
    numero_prima = rng.randint(0, min(3, n // 5))
    numero_ultima = rng.randint(0, min(3, n - numero_prima))
    return SpecFuzzRC(
        indice=indice,
        seed_classe=seed_base + indice * 1009,
        seed_motore=seed_base + indice * 65537,
        studenti=n,
        densita_incompatibilita=rng.uniform(0.0, 0.13),
        quota_livello3=rng.uniform(0.03, 0.28),
        densita_affinita=rng.uniform(0.0, 0.12),
        quota_femmine=rng.uniform(0.25, 0.75),
        numero_prima=numero_prima,
        numero_ultima=numero_ultima,
        fisso=(rng.random() < 0.35),
        densita_storico=rng.uniform(0.0, 0.22),
    )


def genera_classe_fuzz(spec: SpecFuzzRC) -> ClasseRC:
    rng = random.Random(spec.seed_classe)
    n = spec.studenti
    nomi = [f"FZ{i:02d} Allievo" for i in range(1, n + 1)]
    incompat: list[dict[int, int]] = [dict() for _ in range(n)]
    affinita: list[dict[int, int]] = [dict() for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < spec.densita_incompatibilita:
                if rng.random() < spec.quota_livello3:
                    livello = 3
                else:
                    livello = 1 if rng.random() < 0.62 else 2
                incompat[i][j] = incompat[j][i] = livello
            elif rng.random() < spec.densita_affinita:
                livello = rng.choices((1, 2, 3), weights=(4, 3, 2))[0]
                affinita[i][j] = affinita[j][i] = livello

    indici = list(range(n))
    rng.shuffle(indici)
    posizioni = ["NORMALE"] * n
    cursore = 0
    for i in indici[cursore:cursore + spec.numero_prima]:
        posizioni[i] = "PRIMA"
    cursore += spec.numero_prima
    for i in indici[cursore:cursore + spec.numero_ultima]:
        posizioni[i] = "ULTIMA"
    cursore += spec.numero_ultima
    if spec.fisso:
        candidati = [i for i in indici if posizioni[i] != "PRIMA"]
        if candidati:
            posizioni[candidati[0]] = "FISSO"

    studenti = []
    for i, nome in enumerate(nomi):
        sesso = "F" if rng.random() < spec.quota_femmine else "M"
        studenti.append(StudenteRC(
            nome=nome,
            sesso=sesso,
            posizione=posizioni[i],
            incompatibilita=tuple(RelazioneRC(nomi[j], liv) for j, liv in incompat[i].items()),
            affinita=tuple(RelazioneRC(nomi[j], liv) for j, liv in affinita[i].items()),
        ))
    classe = ClasseRC(
        nome=f"RC-FUZZ-{spec.indice:05d}",
        studenti=tuple(studenti),
        origine="fuzz_rc",
        seed=spec.seed_classe,
        famiglia="fuzz",
    )
    valida_classe_rc(classe)
    return classe


def genera_storico_fuzz(classe: ClasseRC, spec: SpecFuzzRC) -> list[dict]:
    rng = random.Random(spec.seed_classe ^ 0x5A17A5)
    nomi = [s.nome for s in classe.studenti]
    storico = []
    for i in range(len(nomi)):
        for j in range(i + 1, len(nomi)):
            if rng.random() < spec.densita_storico:
                storico.append({
                    "studenti": [nomi[i], nomi[j]],
                    "volte_usata": rng.randint(1, 4),
                })
    return storico


def _anomalia(spec: SpecFuzzRC, proprieta: str, dettaglio: str) -> AnomaliaFuzzRC:
    return AnomaliaFuzzRC(
        id_caso=f"fuzz-{spec.indice:05d}", proprieta=proprieta,
        dettaglio=dettaglio, spec=asdict(spec),
    )


def verifica_filtri_t1_t4(classe: ClasseRC, storico: list[dict], spec: SpecFuzzRC):
    """Ritorna (numero_coppie_valutate, anomalie) per i contratti T1–T4."""
    studenti = crea_studenti_da_dati_validati(dati_validati_da_classe(classe))
    assegnatore = AssegnatorePosti()
    config = configurazione_vuota_rc()
    config.config_data["coppie_da_evitare"] = list(storico)
    assegnatore.config_app = config
    motore = assegnatore.motore_vincoli
    motore._config_app_ref = config
    applica_penalita_storico(motore, config, "coppie")

    storico_indice = {
        frozenset(voce["studenti"]): int(voce.get("volte_usata", 1))
        for voce in storico if len(voce.get("studenti", ())) == 2
    }
    risultati = {}
    for tentativo in (1, 2, 3, 4):
        motore.configura_per_tentativo(tentativo)
        assegnatore._applica_penalita_blacklist_tentativo(tentativo)
        per_coppia = {}
        for i, a in enumerate(studenti):
            for b in studenti[i + 1:]:
                k = frozenset((a.get_nome_completo(), b.get_nome_completo()))
                per_coppia[k] = motore.calcola_punteggio_coppia(a, b)
        risultati[tentativo] = per_coppia

    anomalie = []
    tutte = risultati[1]
    for k in tutte:
        nomi = tuple(sorted(k))
        a = classe.per_nome[nomi[0]]
        livello3 = a.incompatibilita_dict.get(nomi[1], 0) == 3
        in_storico = k in storico_indice
        val = {t: risultati[t][k]["valutazione"] for t in (1, 2, 3, 4)}

        if livello3:
            if any(val[t] != "VIETATA" for t in (1, 2, 3, 4)):
                anomalie.append(_anomalia(spec, "livello3_inviolabile", f"{nomi}: {val}"))
            continue
        if in_storico:
            if any(val[t] != "BLACKLISTATA" for t in (1, 2, 3)):
                anomalie.append(_anomalia(spec, "blacklist_assoluta_t1_t3", f"{nomi}: {val}"))
            if val[4] in {"VIETATA", "BLACKLISTATA"}:
                anomalie.append(_anomalia(spec, "blacklist_soft_t4", f"{nomi}: {val}"))
            # Contratto quantitativo corrente: storico -500 + T4 -200 per uso.
            uso = storico_indice[k]
            t4 = risultati[4][k]
            # Ricava il punteggio senza Storico/blacklist usando un motore fresco T4.
            # Il controllo preciso viene demandato ai test sentinella; qui basta
            # verificare che la classificazione non contraddica la cascata.
            if uso > 0 and t4["punteggio_totale"] > -1:
                anomalie.append(_anomalia(spec, "riuso_t4_non_penalizzato", f"{nomi}: uso={uso}, score={t4['punteggio_totale']}"))
        else:
            if any(val[t] in {"VIETATA", "BLACKLISTATA"} for t in (1, 2, 3, 4)):
                anomalie.append(_anomalia(spec, "coppia_estranea_bloccata", f"{nomi}: {val}"))

        ammessi_123 = [val[t] not in {"VIETATA", "BLACKLISTATA"} for t in (1, 2, 3)]
        if len(set(ammessi_123)) != 1:
            anomalie.append(_anomalia(spec, "grafo_t1_t3_divergente", f"{nomi}: {val}"))
        if ammessi_123[0] and val[4] == "VIETATA":
            anomalie.append(_anomalia(spec, "t4_restringe_grafo", f"{nomi}: {val}"))

    return len(tutte), anomalie


def _firma_verifica(verifica):
    if verifica is None:
        return None
    return tuple(sorted(tuple(c) for c in verifica.adiacenze))


def _chiave_verifica(verifica):
    m = verifica.metriche
    return (m.incompatibilita_pesate, -m.affinita)


def _esegui_coppie_fuzz(classe: ClasseRC, spec: SpecFuzzRC, *, num_candidati: int):
    studenti = crea_studenti_da_dati_validati(dati_validati_da_classe(classe))
    fisso = next((s for s in studenti if s.nota_posizione == "FISSO"), None)
    rng = random.Random(spec.seed_motore ^ 0xC011A)
    posizione_trio = rng.choice(("prima", "centro", "ultima"))
    # Il fuzz del motore percorre soltanto workflow che la GUI renderebbe
    # avviabili: 4 posti × 6 file, per esempio, non può ospitare 28 studenti.
    opzioni = [4, 6, 8]
    rng.shuffle(opzioni)
    aula = None
    posti_per_fila = None
    for posti in opzioni:
        num_file = numero_minimo_file_coppie(
            classe.numero_studenti, posti,
            posizione_trio=posizione_trio, ha_fisso=fisso is not None,
        )
        candidata = ConfigurazioneAula("RC fuzz coppie")
        candidata.crea_layout_standard(
            classe.numero_studenti, num_file=num_file, posti_per_fila=posti,
            posizione_trio=posizione_trio, ha_fisso=fisso is not None,
        )
        if candidata.posti_disponibili >= classe.numero_studenti:
            aula = candidata
            posti_per_fila = posti
            break
    if aula is None:
        return False, None, {"causa": "nessuna_geometria_capiente"}
    config = configurazione_vuota_rc()
    storico = genera_storico_fuzz(classe, spec)
    config.config_data["coppie_da_evitare"] = storico
    migliore, ultimo = calcola_miglior_mese(
        studenti, aula, config, posizione_trio, bool(spec.indice % 2), fisso,
        coppie_gia_usate=snapshot_blacklist(config),
        num_candidati=num_candidati, seed_principale=spec.seed_motore,
        contesto_casuale={"operazione": "fuzz_rc", "caso": spec.indice},
    )
    if migliore is None:
        return False, None, None
    verifica = verifica_aula_rc(classe, migliore.configurazione_aula,
                                modalita="coppie", posizione_trio=posizione_trio)
    return verifica.valido, verifica, migliore


def _esegui_terzetti_fuzz(classe: ClasseRC, spec: SpecFuzzRC, *, num_candidati: int, diagnostica=None):
    studenti = crea_studenti_da_dati_validati(dati_validati_da_classe(classe))
    fisso = next((s for s in studenti if s.nota_posizione == "FISSO"), None)
    rng = random.Random(spec.seed_motore ^ 0x7E2E771)
    preferenza = rng.choice(("coppia", "due_quartetti"))
    posizione = rng.choice(("prima", "ultima"))
    per_fila = rng.choice((2, 3, 4))
    aula = ConfigurazioneAula("RC fuzz terzetti")
    aula.crea_layout_terzetti(
        classe.numero_studenti, terzetti_per_fila=per_fila,
        posizione_blocco_finale=posizione, ha_fisso=fisso is not None,
        preferenza_resto2=preferenza,
    )
    cap = aula.capienza_prima_fila_terzetti()
    config = configurazione_vuota_rc()
    config.config_data["adiacenze_terzetti_da_evitare"] = genera_storico_fuzz(classe, spec)
    gruppi, meta = calcola_miglior_mese_terzetti(
        studenti, bool(spec.indice % 2), config_app=config,
        preferenza_resto2=preferenza,
        resto_in_prima_fila=(posizione == "prima"),
        max_terzetti_prima_fila=cap["terzetti"], max_resti_prima_fila=cap["resti"],
        num_candidati=num_candidati, seed_base=spec.seed_motore,
        contesto_casuale={"operazione": "fuzz_rc", "caso": spec.indice},
        restituisci_metadati=True, diagnostica=diagnostica,
    )
    if gruppi is None:
        return False, None, meta
    esito = aula.piazza_gruppi_terzetti(gruppi)
    if not esito.get("valido_struttura", False) or not esito.get("valido_prima", False):
        return False, None, gruppi
    aula.rimuovi_banchi_vuoti()
    verifica = verifica_aula_rc(classe, aula, modalita="terzetti", preferenza_resto2=preferenza)
    return verifica.valido, verifica, gruppi


def verifica_mensile_differenziale(classe: ClasseRC, spec: SpecFuzzRC, modalita: str):
    anomalie = []
    if modalita == "coppie":
        fn, produzione = _esegui_coppie_fuzz, 10
    else:
        fn, produzione = _esegui_terzetti_fuzz, 3

    ok1a, v1a, _ = fn(classe, spec, num_candidati=1)
    ok1b, v1b, _ = fn(classe, spec, num_candidati=1)
    if (ok1a, _firma_verifica(v1a)) != (ok1b, _firma_verifica(v1b)):
        anomalie.append(_anomalia(spec, f"determinismo_{modalita}",
                                  f"prima={(ok1a,_firma_verifica(v1a))}, seconda={(ok1b,_firma_verifica(v1b))}"))

    okn, vn, _ = fn(classe, spec, num_candidati=produzione)
    if ok1a and not okn:
        anomalie.append(_anomalia(spec, f"best_of_n_perde_successo_{modalita}", "N=1 riesce, produzione fallisce"))
    if ok1a and okn and _chiave_verifica(vn) > _chiave_verifica(v1a):
        anomalie.append(_anomalia(spec, f"best_of_n_peggiora_{modalita}",
                                  f"N=1={_chiave_verifica(v1a)}, produzione={_chiave_verifica(vn)}"))
    if ok1a and v1a is not None and not v1a.valido:
        anomalie.append(_anomalia(spec, f"risultato_invalido_{modalita}_n1", str(v1a.violazioni)))
    if okn and vn is not None and not vn.valido:
        anomalie.append(_anomalia(spec, f"risultato_invalido_{modalita}_prod", str(vn.violazioni)))
    return 3, anomalie


def _mensile_isolato(spec: SpecFuzzRC, modalita: str, *, timeout_s: float, radice: Path):
    from .stress import esegui_comando_isolato
    with tempfile.TemporaryDirectory(prefix="postiperfetti-fuzz-") as tmp:
        tmp=Path(tmp); spec_path=tmp/"spec.json"; out_path=tmp/"out.json"
        spec_path.write_text(json.dumps({"spec":asdict(spec),"modalita":modalita}, sort_keys=True)+"\n",encoding="utf-8")
        comando=[sys.executable,"-m","strumenti.validazione_rc.worker_fuzz","--spec",str(spec_path),"--out",str(out_path)]
        stato, exit_code, durata, stdout, stderr=esegui_comando_isolato(comando,timeout_s=timeout_s,cwd=radice)
        if stato=="timeout":
            return {"stato":"timeout","durata_s":durata,"errore":stderr or stdout}
        if exit_code!=0 or not out_path.exists():
            return {"stato":"crash","durata_s":durata,"errore":stderr or stdout or f"exit={exit_code}"}
        try:
            payload=json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"stato":"crash","durata_s":durata,"errore":str(exc)}
        payload.update(stato="ok",durata_s=durata)
        return payload


def campagna_fuzz_rc(*, seed_base: int = 20260807, casi_filtri: int = 2000,
                     casi_mensili: int = 300, reperti_dir: str | Path | None = None,
                     timeout_mensile_s: float = 4.0, parallelismo: int = 4,
                     radice_progetto: str | Path | None = None) -> RapportoFuzzRC:
    anomalie: list[AnomaliaFuzzRC] = []
    coppie_valutate = 0
    verifiche_mensili = 0
    timeout_mensili = 0
    crash_mensili = 0
    specifiche=[]
    classi={}
    for indice in range(1, casi_filtri + 1):
        spec = costruisci_spec_fuzz(indice=indice, seed_base=seed_base)
        classe = genera_classe_fuzz(spec)
        storico = genera_storico_fuzz(classe, spec)
        n_coppie, trovate = verifica_filtri_t1_t4(classe, storico, spec)
        coppie_valutate += n_coppie
        anomalie.extend(trovate)
        if trovate and reperti_dir is not None:
            salva_e_riduci_anomalia(classe, spec, trovate[0], reperti_dir)
        if indice <= casi_mensili:
            modalita = "coppie" if indice % 2 else "terzetti"
            specifiche.append((spec,modalita))
            classi[indice]=classe

    radice=Path(radice_progetto or Path.cwd()).resolve()
    if specifiche:
        with ThreadPoolExecutor(max_workers=max(1,parallelismo)) as pool:
            futuri={pool.submit(_mensile_isolato,spec,modalita,timeout_s=timeout_mensile_s,radice=radice):(spec,modalita) for spec,modalita in specifiche}
            for futuro in as_completed(futuri):
                spec,modalita=futuri[futuro]
                payload=futuro.result()
                if payload["stato"]=="timeout":
                    timeout_mensili += 1
                    anomalie.append(_anomalia(spec,f"timeout_{modalita}",f"> {timeout_mensile_s}s"))
                    continue
                if payload["stato"]=="crash":
                    crash_mensili += 1
                    anomalie.append(_anomalia(spec,f"crash_{modalita}",str(payload.get("errore"))))
                    continue
                verifiche_mensili += int(payload.get("verifiche",0))
                trovate=[AnomaliaFuzzRC(**x) for x in payload.get("anomalie",[])]
                anomalie.extend(trovate)
                if trovate and reperti_dir is not None:
                    salva_e_riduci_anomalia(classi[spec.indice],spec,trovate[0],reperti_dir)

    return RapportoFuzzRC(
        seed_base=seed_base, casi_filtri=casi_filtri,
        coppie_valutate=coppie_valutate, casi_mensili=min(casi_mensili, casi_filtri),
        verifiche_mensili=verifiche_mensili, timeout_mensili=timeout_mensili,
        crash_mensili=crash_mensili, anomalie=tuple(anomalie),
    )

def scrivi_rapporto_fuzz(rapporto: RapportoFuzzRC, destinazione: str | Path) -> Path:
    path = Path(destinazione)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rapporto.come_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _proprieta_presente(classe: ClasseRC, spec: SpecFuzzRC, proprieta: str) -> bool:
    storico = genera_storico_fuzz(classe, spec)
    if proprieta in {
        "livello3_inviolabile", "blacklist_assoluta_t1_t3", "blacklist_soft_t4",
        "riuso_t4_non_penalizzato", "coppia_estranea_bloccata",
        "grafo_t1_t3_divergente", "t4_restringe_grafo",
    }:
        _n, anomalie = verifica_filtri_t1_t4(classe, storico, spec)
    elif proprieta.endswith("_coppie") or "_coppie_" in proprieta:
        _n, anomalie = verifica_mensile_differenziale(classe, spec, "coppie")
    else:
        _n, anomalie = verifica_mensile_differenziale(classe, spec, "terzetti")
    return any(a.proprieta == proprieta for a in anomalie)


def salva_e_riduci_anomalia(classe: ClasseRC, spec: SpecFuzzRC, anomalia: AnomaliaFuzzRC,
                            reperti_dir: str | Path) -> dict:
    """Salva e riduce automaticamente un controesempio fuzz riproducibile."""
    from moduli.file_classe import serializza_file_classe
    from .generatori import dati_validati_da_classe
    from .riduzione import riduci_classe_rc

    destinazione = Path(reperti_dir)
    destinazione.mkdir(parents=True, exist_ok=True)
    base = destinazione / f"{anomalia.id_caso}-{anomalia.proprieta}"
    originale = base.with_name(base.name + "-originale.txt")
    originale.write_text(
        serializza_file_classe(classe.nome, dati_validati_da_classe(classe)) + "\n",
        encoding="utf-8",
    )
    esito = riduci_classe_rc(
        classe,
        lambda candidata: _proprieta_presente(candidata, spec, anomalia.proprieta),
    )
    ridotta = base.with_name(base.name + "-ridotta.txt")
    ridotta.write_text(
        serializza_file_classe(esito.classe.nome, dati_validati_da_classe(esito.classe)) + "\n",
        encoding="utf-8",
    )
    rapporto = base.with_name(base.name + "-riduzione.json")
    dati = {
        "anomalia": asdict(anomalia),
        "originale": str(originale),
        "ridotta": str(ridotta),
        "originale_studenti": esito.originale_studenti,
        "finale_studenti": esito.finale_studenti,
        "originale_relazioni": esito.originale_relazioni,
        "finale_relazioni": esito.finale_relazioni,
        "passi_accettati": esito.passi_accettati,
    }
    rapporto.write_text(json.dumps(dati, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dati


def campagna_oracolo_coppie_rc(*, seed_base: int = 606000, casi: int = 400,
                                estremo: bool = False, limite_nodi: int = 150000) -> dict:
    """Confronta il motore produttivo con l'oracolo T4 nel sottodominio esatto."""
    from .oracoli import oracolo_coppie_t4
    rng = random.Random(seed_base)
    conteggi = {"fattibile": 0, "impossibile": 0, "sconosciuto": 0, "fuori_dominio": 0}
    testati_motore = 0
    anomalie = []
    for indice in range(1, casi + 1):
        n = rng.randint(12, 30)
        if estremo:
            densita = rng.uniform(0.55, 0.90)
            quota3 = 1.0
            densita_aff = 0.0
        else:
            densita = rng.uniform(0.0, 0.13)
            quota3 = rng.uniform(0.03, 0.28)
            densita_aff = rng.uniform(0.0, 0.12)
        spec = SpecFuzzRC(
            indice, seed_base + indice * 1009, seed_base + 1000 + indice * 65537,
            n, densita, quota3, densita_aff, 0.5, 0, 0, False, 0.0,
        )
        classe = genera_classe_fuzz(spec)
        oracolo = oracolo_coppie_t4(classe, limite_nodi=limite_nodi)
        conteggi[oracolo.stato] = conteggi.get(oracolo.stato, 0) + 1
        # La verifica differenziale cerca falsi fallimenti: sui casi che l'oracolo
        # prova impossibili non serve consumare CPU per chiedere al motore la stessa prova.
        if oracolo.stato == "fattibile":
            testati_motore += 1
            ok, verifica, _ = _esegui_coppie_fuzz(classe, spec, num_candidati=10)
            if not ok:
                anomalie.append({
                    "indice": indice, "studenti": n, "seed_classe": spec.seed_classe,
                    "nodi_oracolo": oracolo.nodi, "tipo": "falso_fallimento",
                })
    return {
        "seed_base": seed_base,
        "casi": casi,
        "estremo": estremo,
        "limite_nodi": limite_nodi,
        "oracolo": conteggi,
        "casi_fattibili_testati_sul_motore": testati_motore,
        "anomalie": anomalie,
        "verde": not anomalie,
    }
