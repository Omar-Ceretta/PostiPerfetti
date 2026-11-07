# -*- coding: utf-8 -*-
"""Ricostruzione delle rotazioni e dei contatori, indipendente da file e GUI.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from typing import List
from types import SimpleNamespace
from moduli.persistenza.strato_storico import (
    aggiorna_blacklist_terzetti, aggiorna_blacklist_personalizzata,
    CHIAVE_BLACKLIST_PER_MODO,
)

def aggiorna_rotazioni_coppie(dati, nuove_coppie: List[tuple], trio=None,
                                studente_fisso=None, gruppo_adiacente_fisso=None,
                                nome_adiacente_fisso=None):
    """Aggiorna blacklist e contatori della modalità a coppie.

    Registra le coppie normali, le adiacenze consecutive del trio, la coppia
    collocata accanto al FISSO e il suo vicino diretto.
    """

    # Indicizza le coppie esistenti per aggiornare i contatori in O(1).
    coppie_esistenti = {}
    for item in dati["coppie_da_evitare"]:
        studenti = item.get("studenti", [])
        if len(studenti) == 2:
            chiave = tuple(sorted(studenti))
            coppie_esistenti[chiave] = item

    for studente1, studente2, _ in nuove_coppie:
        chiave = tuple(sorted([studente1.get_nome_completo(), studente2.get_nome_completo()]))

        if chiave in coppie_esistenti:
            coppie_esistenti[chiave]["volte_usata"] += 1
        else:
            nuova_voce = {
                "tipo": "coppia",
                "studenti": [chiave[0], chiave[1]],
                "volte_usata": 1
            }
            dati["coppie_da_evitare"].append(nuova_voce)
            coppie_esistenti[chiave] = nuova_voce

    # Nel trio contano soltanto le due adiacenze consecutive.
    if trio and len(trio) == 3:

        studente1, studente2, studente3 = trio

        coppie_virtuali = [
            (studente1.get_nome_completo(), studente2.get_nome_completo()),
            (studente2.get_nome_completo(), studente3.get_nome_completo())
        ]

        for idx, (nome1, nome2) in enumerate(coppie_virtuali, 1):
            chiave = tuple(sorted([nome1, nome2]))
            print(f"   📝 Coppia virtuale {idx}: {chiave[0]} + {chiave[1]}")

            if chiave in coppie_esistenti:
                coppie_esistenti[chiave]["volte_usata"] += 1
                print(f"   ✅ Aggiornata: {chiave[0]} + {chiave[1]} (ora {coppie_esistenti[chiave]['volte_usata']} volte)")
            else:
                nuova_voce = {
                    "tipo": "coppia",
                    "studenti": [chiave[0], chiave[1]],
                    "origine": "trio",
                    "volte_usata": 1
                }
                dati["coppie_da_evitare"].append(nuova_voce)
                coppie_esistenti[chiave] = nuova_voce
                print(f"   🆕 Nuova coppia virtuale aggiunta: {chiave[0]} + {chiave[1]}")

        # Ogni componente del trio riceve un solo incremento.
        for studente in trio:
            nome_studente = studente.get_nome_completo()
            if nome_studente not in dati["studenti_trio_contatore"]:
                dati["studenti_trio_contatore"][nome_studente] = 0

            dati["studenti_trio_contatore"][nome_studente] += 1
            print(f"   📊 {nome_studente}: ora {dati['studenti_trio_contatore'][nome_studente]} volte nel trio")

    # La coppia accanto al FISSO vive fuori da ``coppie_formate`` e
    # deve quindi essere registrata separatamente.
    if gruppo_adiacente_fisso:
        s1_fisso, s2_fisso = gruppo_adiacente_fisso[0], gruppo_adiacente_fisso[1]
        chiave_adiacente = tuple(sorted([s1_fisso.get_nome_completo(), s2_fisso.get_nome_completo()]))

        if chiave_adiacente in coppie_esistenti:
            coppie_esistenti[chiave_adiacente]["volte_usata"] += 1
            print(f"   ✅ Coppia adiacente FISSO aggiornata (ora {coppie_esistenti[chiave_adiacente]['volte_usata']} volte)")
        else:
            nuova_voce = {
                "tipo": "coppia",
                "studenti": [chiave_adiacente[0], chiave_adiacente[1]],
                "volte_usata": 1
            }
            dati["coppie_da_evitare"].append(nuova_voce)
            coppie_esistenti[chiave_adiacente] = nuova_voce
            print(f"   🆕 Nuova coppia adiacente FISSO aggiunta in blacklist")

    # Il contatore dedicato riguarda solo il vicino diretto del FISSO,
    # non gli altri membri dell’eventuale gruppo adiacente.
    if studente_fisso and nome_adiacente_fisso:
        if "studenti_vicino_fisso_contatore" not in dati:
            dati["studenti_vicino_fisso_contatore"] = {}

        contatore = dati["studenti_vicino_fisso_contatore"]
        if nome_adiacente_fisso not in contatore:
            contatore[nome_adiacente_fisso] = 0
        contatore[nome_adiacente_fisso] += 1
        print(f"   📌 Contatore vicino FISSO: {nome_adiacente_fisso} → {contatore[nome_adiacente_fisso]} volte")


def ricostruisci_rotazioni(storico):
    """Deriva nuove strutture senza mutare lo Storico ricevuto."""
    dati = {"storico_assegnazioni": storico}
    contesto = SimpleNamespace(config_data=dati)
    print(f"🔄 RICOSTRUZIONE BLACKLIST: Inizio elaborazione Storico...")

    # Riparte da strutture vuote per entrambe le modalità e per tutti
    # i contatori derivati.
    dati["coppie_da_evitare"] = []
    dati[CHIAVE_BLACKLIST_PER_MODO["terzetti"]] = []
    dati[CHIAVE_BLACKLIST_PER_MODO["personalizzata"]] = []
    dati["studenti_trio_contatore"] = {}
    dati["studenti_vicino_fisso_contatore"] = {}
    print(
        "   ✅ Blacklist (coppie + terzetti + personalizzata) "
        "e contatori azzerati"
    )

    storico_rimasto = dati["storico_assegnazioni"]
    num_assegnazioni = len(storico_rimasto)

    if num_assegnazioni == 0:
        print(f"   ℹ️ Storico vuoto - blacklist rimane vuota")
        return {k: v for k, v in dati.items() if k != "storico_assegnazioni"}

    print(f"   📋 Elaborazione {num_assegnazioni} assegnazioni rimaste...")

    for idx, assegnazione in enumerate(storico_rimasto, 1):
        nome_assegnazione = assegnazione["nome"]
        print(f"   🔄 Elaboro: {nome_assegnazione}")

        # Le voci con fotografia fisica sono rigiocate dai posti reali,
        # prima dei formati legacy: incluse *entrambe* le vicinanze FISSO.
        if "formato_disposizione" in assegnazione or "disposizione_fisica" in assegnazione:
            from moduli.persistenza.storico_fisico_standard import aggiorna_rotazioni_da_voce_fisica
            aggiorna_rotazioni_da_voce_fisica(contesto, assegnazione)
            continue

        # Terzetti e Personalizzata si ricostruiscono dai gruppi ordinati.
        # Il ``continue`` impedisce che il loro contenuto alimenti anche la
        # blacklist delle coppie.
        if assegnazione["modo"] in {"terzetti", "personalizzata"}:
            adiacenze = []
            for gruppo in assegnazione["gruppi"]:
                membri = gruppo["membri"]
                adiacenze.extend(zip(membri, membri[1:]))
            if adiacenze:
                if assegnazione["modo"] == "terzetti":
                    aggiorna_blacklist_terzetti(contesto, adiacenze)
                else:
                    aggiorna_blacklist_personalizzata(contesto, adiacenze)
            print(
                f"      ✅ Voce {assegnazione['modo']}: "
                f"{len(adiacenze)} adiacenze ricostruite"
            )
            continue  # evita contaminazioni fra blacklist

        # Le disposizioni a coppie vengono ricostruite dal layout salvato.
        coppie_da_elaborare = []
        trio_da_elaborare = None
        studente_fisso_fittizio = None
        gruppo_adiacente_fittizio = None

        layout = assegnazione["layout"]

        coppie_processate = set()
        trio_nomi = []

        for studente_info in layout:
            tipo = studente_info["tipo"]
            nome = studente_info["studente"]

            if tipo == "coppia":
                compagno = studente_info["compagno"]
                if nome and compagno:
                    chiave = tuple(sorted([nome, compagno]))
                    if chiave not in coppie_processate:
                        coppie_processate.add(chiave)
                        s1 = type('Student', (), {'get_nome_completo': lambda self, n=chiave[0]: n})()
                        s2 = type('Student', (), {'get_nome_completo': lambda self, n=chiave[1]: n})()
                        coppie_da_elaborare.append((s1, s2, {}))

            elif tipo == "trio":
                trio_nomi.append(nome)

            elif tipo == "fisso":
                nome_adiacente = studente_info["adiacente"]
                if nome:
                    studente_fisso_fittizio = type('Student', (), {
                        'get_nome_completo': lambda self, n=nome: n
                    })()
                if nome_adiacente:
                    s_adj = type('Student', (), {
                        'get_nome_completo': lambda self, n=nome_adiacente: n
                    })()
                    s_dummy = type('Student', (), {
                        'get_nome_completo': lambda self: "RICOSTRUZIONE_DUMMY"
                    })()
                    gruppo_adiacente_fittizio = (s_adj, s_dummy, {})
                    print(f"      📌 FISSO ricostruito: {nome}, adiacente: {nome_adiacente}")

        if len(trio_nomi) == 3:
            trio_fittizio = []
            for nome_trio in trio_nomi:
                s = type('Student', (), {
                    'get_nome_completo': lambda self, n=nome_trio: n
                })()
                trio_fittizio.append(s)
            trio_da_elaborare = trio_fittizio

        # Riusa la stessa funzione di aggiornamento. La coppia accanto
        # al FISSO è già compresa fra le coppie del layout.
        if coppie_da_elaborare or trio_da_elaborare:
            aggiorna_rotazioni_coppie(dati, coppie_da_elaborare, trio_da_elaborare)
            print(f"      ✅ Elaborati: {len(coppie_da_elaborare)} coppie" +
                  (f" + 1 trio" if trio_da_elaborare else ""))

        # Il contatore del vicino diretto viene ricostruito separatamente.
        if studente_fisso_fittizio and gruppo_adiacente_fittizio:
            nome_adiacente = gruppo_adiacente_fittizio[0].get_nome_completo()
            if "studenti_vicino_fisso_contatore" not in dati:
                dati["studenti_vicino_fisso_contatore"] = {}
            contatore = dati["studenti_vicino_fisso_contatore"]
            if nome_adiacente not in contatore:
                contatore[nome_adiacente] = 0
            contatore[nome_adiacente] += 1
            print(f"      📌 Contatore vicino FISSO ricostruito: {nome_adiacente} → {contatore[nome_adiacente]}")

    num_coppie_blacklist = len(dati["coppie_da_evitare"])
    # Riepiloga separatamente le blacklist delle due modalità.
    num_adiacenze_terzetti = len(
        dati[CHIAVE_BLACKLIST_PER_MODO["terzetti"]])
    num_studenti_trio = len(dati["studenti_trio_contatore"])
    num_studenti_vicino = len(dati["studenti_vicino_fisso_contatore"])

    print(f"   📊 RICOSTRUZIONE COMPLETATA:")
    print(f"      • Coppie in blacklist: {num_coppie_blacklist}")
    print(f"      • Adiacenze terzetti in blacklist: {num_adiacenze_terzetti}")
    print(f"      • Studenti con contatore trio: {num_studenti_trio}")
    print(f"      • Studenti con contatore vicino FISSO: {num_studenti_vicino}")


    return {k: v for k, v in dati.items() if k != "storico_assegnazioni"}
