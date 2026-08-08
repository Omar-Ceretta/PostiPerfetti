# -*- coding: utf-8 -*-
"""
Gestisce lo storico delle vicinanze e le penalità di rotazione.

Il modulo cerca quando due studenti sono già stati vicini, avvolge il calcolo
del punteggio con la penalità ``−500 × volte_usata`` e aggiorna la blacklist
delle adiacenze nella modalità a terzetti.

Coppie e terzetti mantengono blacklist separate: la prima registra i compagni
di banco, la seconda le adiacenze consecutive nei gruppi. Le funzioni lavorano
per duck typing e non importano componenti dell'interfaccia o classi del dominio,
così possono essere condivise fra applicazione e strumenti di collaudo.

Parte di «PostiPerfetti». Autore: Omar Ceretta. Licenza: GNU GPLv3.
"""

from moduli.lingua import forma_numerata


# Ogni modalità usa una chiave distinta del file di configurazione.
# La separazione strutturale impedisce che una vicinanza di un modo influenzi
# la rotazione dell'altro.
CHIAVE_BLACKLIST_PER_MODO = {
    "coppie":   "coppie_da_evitare",
    "terzetti": "adiacenze_terzetti_da_evitare",
}


def trova_quando_coppia_usata(cognomi_coppia: set[str], config_app, modo: str = "coppie") -> str | None:
    """Restituisce l'assegnazione più recente in cui la coppia era vicina.

    La ricerca considera soltanto le assegnazioni della modalità richiesta e
    produce la nota diagnostica del report; non modifica punteggi o blacklist.
    Se la coppia compare una sola volta restituisce ``"usata in: ..."``;
    altrimenti restituisce ``"ultima volta: ..."``. Ritorna ``None`` quando
    non trova corrispondenze nello Storico.
    """
    # La configurazione può essere quella reale o una copia temporanea.
    storico = config_app.config_data.get("storico_assegnazioni", [])

    assegnazioni_trovate = []

    for assegnazione in reversed(storico):
        # Le assegnazioni appartenenti all'altra modalità non contribuiscono
        # alla nota.
        if assegnazione["modo"] != modo:
            continue

        nome_assegnazione = assegnazione.get("nome", "Assegnazione senza nome")

        # Nei gruppi a terzetti contano soltanto le coppie consecutive;
        # gli estremi non sono adiacenti. La regola viene applicata direttamente
        # alle stringhe per mantenere questo modulo indipendente dal dominio.
        if modo == "terzetti":
            trovata = False
            for gruppo in assegnazione.get("gruppi", []):
                membri = gruppo.get("membri", [])
                tipo_gruppo = gruppo.get("tipo", "gruppo")
                for nome_a, nome_b in zip(membri, membri[1:]):
                    if {nome_a, nome_b} == cognomi_coppia:
                        assegnazioni_trovate.append(
                            f"{nome_assegnazione} [{tipo_gruppo}]")
                        trovata = True
                        break
                if trovata:
                    break
            continue

        # Le assegnazioni a coppie leggono il layout salvato.
        layout = assegnazione.get("layout", [])

        trovata = False
        for studente_info in layout:
            tipo = studente_info.get("tipo")
            nome = studente_info.get("studente", "")

            # Coppia normale.
            if tipo == "coppia":
                compagno = studente_info.get("compagno", "")
                if {nome, compagno} == cognomi_coppia:
                    assegnazioni_trovate.append(nome_assegnazione)
                    trovata = True
                    break

            # Nel trio contano soltanto le due adiacenze che coinvolgono
            # lo studente centrale. Le versioni precedenti del formato salvato
            # elencavano, anche per gli estremi, entrambi gli altri componenti:
            # leggerli tutti farebbe risultare adiacenti anche primo e terzo.
            elif (
                tipo == "trio"
                and studente_info.get("posizione_trio") == "centrale"
            ):
                compagni = studente_info.get("compagni_trio", [])
                for compagno in compagni:
                    if {nome, compagno} == cognomi_coppia:
                        assegnazioni_trovate.append(f"{nome_assegnazione} [trio]")
                        trovata = True
                        break
                if trovata:
                    break

            # L'adiacenza FISSO-vicino è un dato diagnostico del layout:
            # non appartiene alla blacklist della modalità a coppie.
            elif tipo == "fisso":
                adiacente = studente_info.get("adiacente", "")
                if adiacente and {nome, adiacente} == cognomi_coppia:
                    assegnazioni_trovate.append(
                        f"{nome_assegnazione} [FISSO]"
                    )
                    trovata = True
                    break

    if assegnazioni_trovate:
        if len(assegnazioni_trovate) == 1:
            return f"usata in: {assegnazioni_trovate[0]}"
        else:
            return f"ultima volta: {assegnazioni_trovate[0]}"

    return None


def applica_penalita_storico(motore_vincoli, config_app, modo: str = "coppie") -> None:
    """Applica al motore la penalità per le vicinanze già utilizzate.

    Sostituisce a runtime ``calcola_punteggio_coppia`` con un wrapper che legge
    la blacklist della modalità richiesta e sottrae ``500 × volte_usata``.
    La nota diagnostica viene cercata nello Storico della stessa modalità.

    Va applicata una sola volta a un motore appena creato; una guardia interna
    evita comunque il doppio avvolgimento. Per la stratificazione completa del
    punteggio, vedere la mappa in ``MotoreVincoli.calcola_punteggio_coppia``.
    """
    # Un doppio wrapper applicherebbe due volte la penalità; la guardia rende
    # sicuro anche un eventuale secondo passaggio dello stesso motore.
    if getattr(motore_vincoli, '_penalita_storico_applicata', False):
        return

    # L'indicizzazione diretta segnala immediatamente un modo sconosciuto,
    # invece di ripiegare silenziosamente su un'altra blacklist.
    chiave_blacklist = CHIAVE_BLACKLIST_PER_MODO[modo]

    # Una lista assente equivale a una blacklist ancora vuota.
    coppie_usate = config_app.config_data.get(chiave_blacklist, [])

    if not coppie_usate:
        return

    # Indicizza la blacklist una sola volta: il wrapper può così cercare ogni
    # coppia in O(1). Le voci malformate vengono ignorate e, in presenza di
    # duplicati, viene conservata la prima occorrenza.
    indice_blacklist = {}
    for coppia_usata in coppie_usate:
        studenti = coppia_usata.get("studenti", [])
        if len(studenti) != 2:
            continue
        chiave_coppia = frozenset((studenti[0], studenti[1]))
        if chiave_coppia not in indice_blacklist:
            indice_blacklist[chiave_coppia] = coppia_usata

    calcola_originale = motore_vincoli.calcola_punteggio_coppia

    def calcola_con_penalita_storico(studente1, studente2):
        risultato = calcola_originale(studente1, studente2)

        # Un'incompatibilità assoluta resta vietata anche se la coppia compare
        # nello Storico: la penalità di rotazione non deve riclassificarla.
        if risultato.get("valutazione") == "VIETATA":
            return risultato

        cognomi_attuali = {studente1.get_nome_completo(), studente2.get_nome_completo()}

        coppia_usata = indice_blacklist.get(frozenset(cognomi_attuali))

        if coppia_usata is not None:
            # Il valore predefinito mantiene utilizzabile anche una voce priva
            # del contatore ``volte_usata``.
            volte_usata = coppia_usata.get("volte_usata", 1)
            penalita = 500 * volte_usata

            # La nota cita soltanto assegnazioni della stessa modalità.
            info_quando = trova_quando_coppia_usata(cognomi_attuali, config_app, modo)

            risultato["punteggio_totale"] -= penalita
            forma_volta = forma_numerata(volte_usata, "volta", "volte")
            nota = (
                f"Coppia già usata {volte_usata} {forma_volta} "
                f"(penalità: -{penalita})"
            )
            if info_quando:
                nota += f" - {info_quando}"
            risultato["note"].append(nota)

            # Un punteggio negativo segnala esplicitamente il riutilizzo.
            if risultato["punteggio_totale"] < 0:
                risultato["valutazione"] = "RIUTILIZZATA"

        return risultato

    # Installa il wrapper e registra che la penalità è già stata applicata.
    motore_vincoli.calcola_punteggio_coppia = calcola_con_penalita_storico
    motore_vincoli._penalita_storico_applicata = True


def aggiorna_blacklist_terzetti(config_app, adiacenze_nomi) -> None:
    """Aggiorna la blacklist dei terzetti con le adiacenze ricevute.

    Ogni elemento di ``adiacenze_nomi`` è una coppia di nomi completi. Se
    l'adiacenza esiste già, incrementa ``volte_usata``; altrimenti aggiunge una
    nuova voce. Entrano nella blacklist tutte le adiacenze consecutive dei
    gruppi, comprese quelle che coinvolgono lo studente FISSO; gli estremi non
    consecutivi non contano.

    La funzione modifica soltanto ``config_app.config_data`` e non salva il
    file JSON. Il chiamante resta responsabile della persistenza su disco.
    """
    # ``setdefault`` crea la lista al primo utilizzo e restituisce il
    # riferimento conservato nella configurazione.
    lista = config_app.config_data.setdefault(
        CHIAVE_BLACKLIST_PER_MODO["terzetti"], [])

    # L'indice locale consente aggiornamenti in O(1); ignora le voci
    # malformate e conserva la prima occorrenza di eventuali duplicati.
    per_chiave = {}
    for voce in lista:
        nomi = voce.get("studenti", [])
        if len(nomi) != 2:
            continue
        chiave = frozenset(nomi)
        if chiave not in per_chiave:
            per_chiave[chiave] = voce

    for nome_a, nome_b in adiacenze_nomi:
        # L'ordinamento rende stabile la rappresentazione nel file JSON,
        # indipendentemente dall'ordine dell'adiacenza ricevuta.
        coppia = sorted((nome_a, nome_b))
        chiave = frozenset(coppia)

        if chiave in per_chiave:
            per_chiave[chiave]["volte_usata"] += 1
        else:
            # Il campo ``tipo`` descrive la natura della voce; il calcolo usa
            # soltanto studenti e contatore.
            voce = {"tipo": "adiacenza",
                    "studenti": coppia,
                    "volte_usata": 1}
            lista.append(voce)
            per_chiave[chiave] = voce
