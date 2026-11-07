# -*- coding: utf-8 -*-
"""Validatori puri dei record dello Storico, correnti e storici.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""


def valida_voce_layout(assegnazione: dict, indice: int) -> None:
    """Valida il payload persistente specifico della Personalizzata.

    La voce conserva separatamente geometria semantica, fotografia visuale
    con gli eventuali vuoti e collocazione gruppo→blocco. In questo modo la
    ricostruzione futura non deve dedurre DAVANTI/IN FONDO/FISSO da una
    griglia generica.
    """
    from moduli.dominio.aula_personalizzata import (
        istantanea_visuale_da_json,
        schema_personalizzato_da_json,
    )

    obbligatori = {
        "gruppi",
        "collocazioni",
        "schema_personalizzato",
        "layout_visuale_personalizzato",
        "studente_fisso",
        "genere_misto",
    }
    mancanti = sorted(obbligatori - set(assegnazione))
    if mancanti:
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata è incompleta; "
            "mancano: " + ", ".join(mancanti) + "."
        )

    if "modificata_manualmente" in assegnazione and not isinstance(
        assegnazione["modificata_manualmente"], bool
    ):
        raise ValueError("Indicazione di modifica manuale non valida nello Storico.")

    if not isinstance(assegnazione["genere_misto"], bool):
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata ha "
            "«genere_misto» in formato non valido."
        )
    nome_fisso_salvato = assegnazione["studente_fisso"]
    if nome_fisso_salvato is not None and (
        not isinstance(nome_fisso_salvato, str)
        or not nome_fisso_salvato.strip()
    ):
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata ha uno "
            "studente FISSO non valido."
        )

    schema = schema_personalizzato_da_json(
        assegnazione["schema_personalizzato"]
    )
    visuale = istantanea_visuale_da_json(
        assegnazione["layout_visuale_personalizzato"]
    )
    visuale.valida_contro_schema(schema)

    gruppi = assegnazione["gruppi"]
    if not isinstance(gruppi, list) or not gruppi:
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata non contiene "
            "gruppi validi."
        )
    dimensioni = {"coppia": 2, "terzetto": 3}
    firme_gruppi = []
    nomi = []
    for posizione, gruppo in enumerate(gruppi, start=1):
        if not isinstance(gruppo, dict):
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha il "
                f"gruppo {posizione} in formato non valido."
            )
        if set(gruppo) != {"tipo", "membri"}:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha il "
                f"gruppo {posizione} con campi non validi."
            )
        tipo = gruppo["tipo"]
        membri = gruppo["membri"]
        if tipo not in dimensioni or not isinstance(membri, list):
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha il "
                f"gruppo {posizione} in formato non valido."
            )
        if len(membri) != dimensioni[tipo] or any(
            not isinstance(nome, str) or not nome.strip()
            for nome in membri
        ):
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha il "
                f"gruppo {posizione} con membri non validi."
            )
        firme_gruppi.append(tuple(membri))
        nomi.extend(membri)

    if len(nomi) != len(set(nomi)):
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata contiene "
            "studenti duplicati nei gruppi."
        )
    schema.valida_numero_studenti(len(nomi))
    if "sessi_studenti" in assegnazione:
        sessi = assegnazione["sessi_studenti"]
        if (not isinstance(sessi, dict) or not set(sessi).issubset(nomi)
                or any(sesso not in ('M', 'F') for sesso in sessi.values())):
            raise ValueError(f"La voce {indice} dello Storico contiene generi visuali non validi.")

    collocazioni = assegnazione["collocazioni"]
    if not isinstance(collocazioni, list) or len(collocazioni) != len(gruppi):
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata ha un numero "
            "di collocazioni incoerente."
        )

    blocchi_per_id = {blocco.id: blocco for blocco in schema.blocchi}
    firme_attese = set(firme_gruppi)
    firme_viste = set()
    blocchi_visti = set()
    collocazione_per_blocco = {}
    for posizione, collocazione in enumerate(collocazioni, start=1):
        if not isinstance(collocazione, dict) or set(collocazione) != {
            "blocco", "gruppo", "posti"
        }:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha la "
                f"collocazione {posizione} in formato non valido."
            )
        id_blocco = collocazione["blocco"]
        gruppo = collocazione["gruppo"]
        posti = collocazione["posti"]
        if not isinstance(id_blocco, str) or id_blocco not in blocchi_per_id:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata riferisce "
                f"un blocco inesistente nella collocazione {posizione}."
            )
        if id_blocco in blocchi_visti:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata usa due "
                f"volte il blocco {id_blocco!r}."
            )
        if not isinstance(gruppo, list) or tuple(gruppo) not in firme_attese:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha un "
                f"gruppo non riconosciuto nella collocazione {posizione}."
            )
        firma = tuple(gruppo)
        if firma in firme_viste:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata colloca "
                "due volte lo stesso gruppo."
            )
        blocco = blocchi_per_id[id_blocco]
        posti_attesi = [posto.id for posto in blocco.posti]
        if posti != posti_attesi or len(gruppo) != blocco.capienza:
            raise ValueError(
                f"La voce {indice} dello Storico Personalizzata ha una "
                f"collocazione incoerente col blocco {id_blocco!r}."
            )
        blocchi_visti.add(id_blocco)
        firme_viste.add(firma)
        collocazione_per_blocco[id_blocco] = gruppo

    if blocchi_visti != set(blocchi_per_id) or firme_viste != firme_attese:
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata non copre "
            "esattamente tutti i blocchi e tutti i gruppi."
        )

    blocco_fisso = schema.blocco_ancora_fisso
    nome_fisso_atteso = None
    if blocco_fisso is not None:
        ancora = blocco_fisso.posto_ancora_fisso
        gruppo = collocazione_per_blocco[blocco_fisso.id]
        nome_fisso_atteso = gruppo[ancora.indice]
    if nome_fisso_salvato != nome_fisso_atteso:
        raise ValueError(
            f"La voce {indice} dello Storico Personalizzata non è coerente "
            "sullo studente FISSO."
        )


def valida_storico(storico: list) -> None:
    """Controlla le voci senza modificarle né aprire file."""
    def intero_valido(valore):
        return isinstance(valore, int) and not isinstance(valore, bool)

    campi_storico = {
        "data_creazione": str,
        "nome": str,
        "classe": str,
        "file_origine": str,
        "generazione": str,
        "modo": str,
        "progressivo": int,
        "abbinamenti": str,
    }
    campi_configurazione_aula = {
        "num_file": int,
        "posti_per_fila": int,
        "num_studenti": int,
        "num_righe": int,
        "num_colonne": int,
        "ha_fisso": bool,
        "larghezza_blocco_sx": int,
        "genere_misto": bool,
    }
    dimensioni_gruppo = {
        "coppia": 2,
        "terzetto": 3,
        "quartetto": 4,
    }

    serie_storico_viste = set()

    for indice, assegnazione in enumerate(
            storico, start=1):
        if not isinstance(assegnazione, dict):
            raise ValueError(
                f"La voce {indice} dello Storico non è un oggetto."
            )

        mancanti = [
            chiave for chiave in campi_storico
            if chiave not in assegnazione
        ]
        if mancanti:
            raise ValueError(
                f"La voce {indice} dello Storico non usa il formato "
                "corrente; mancano: " + ", ".join(mancanti) + "."
            )

        for chiave, tipo_atteso in campi_storico.items():
            valore = assegnazione[chiave]
            tipo_valido = isinstance(valore, tipo_atteso)
            if tipo_atteso is int:
                tipo_valido = intero_valido(valore)
            if not tipo_valido:
                raise ValueError(
                    f"La voce {indice} dello Storico ha «{chiave}» "
                    f"in formato non valido: atteso "
                    f"{tipo_atteso.__name__}."
                )

        if assegnazione["generazione"] not in {"mensile", "annuale"}:
            raise ValueError(
                f"La voce {indice} dello Storico dichiara una "
                "generazione non valida."
            )
        if assegnazione["modo"] not in {"coppie", "terzetti", "personalizzata"}:
            raise ValueError(
                f"La voce {indice} dello Storico dichiara una "
                "geometria non valida."
            )
        for chiave in ("data_creazione", "nome", "classe", "file_origine", "abbinamenti"):
            if not assegnazione[chiave].strip():
                raise ValueError(
                    f"La voce {indice} dello Storico ha «{chiave}» vuoto."
                )

        if assegnazione["progressivo"] < 1:
            raise ValueError(
                f"La voce {indice} dello Storico ha un progressivo "
                "non valido."
            )

        chiave_serie = (
            assegnazione["file_origine"],
            assegnazione["generazione"],
            assegnazione["modo"],
            assegnazione["progressivo"],
        )
        if chiave_serie in serie_storico_viste:
            raise ValueError(
                f"La voce {indice} dello Storico duplica il progressivo "
                "di una serie già registrata."
            )
        serie_storico_viste.add(chiave_serie)

        if assegnazione["modo"] == "personalizzata":
            valida_voce_layout(assegnazione, indice)
            continue
        # E3/4: voce standard con fonte geometrica esplicita. Non puo'
        # essere convalidata con le vecchie regole a un solo vicino FISSO.
        if "formato_disposizione" in assegnazione or "disposizione_fisica" in assegnazione:
            from moduli.persistenza.storico_fisico_standard import valida_voce_fisica
            valida_voce_fisica(assegnazione, indice)
            continue

        layout = assegnazione.get("layout")
        configurazione_aula = assegnazione.get("configurazione_aula")
        if not isinstance(layout, list):
            raise ValueError(
                f"La voce {indice} dello Storico non contiene un layout valido."
            )
        if not isinstance(configurazione_aula, dict):
            raise ValueError(
                f"La voce {indice} dello Storico non contiene una "
                "configurazione dell'aula valida."
            )

        for chiave, tipo_atteso in campi_configurazione_aula.items():
            if chiave not in configurazione_aula:
                raise ValueError(
                    f"La voce {indice} dello Storico ha una configurazione "
                    f"dell'aula incompleta; manca «{chiave}»."
                )
            valore = configurazione_aula[chiave]
            tipo_valido = isinstance(valore, tipo_atteso)
            if tipo_atteso is int:
                tipo_valido = intero_valido(valore) and valore > 0
            if not tipo_valido:
                raise ValueError(
                    f"La voce {indice} dello Storico ha «{chiave}» "
                    "in formato non valido nella configurazione dell'aula."
                )

        if configurazione_aula["num_righe"] != configurazione_aula["num_file"] + 2:
            raise ValueError(
                f"La voce {indice} dello Storico dichiara un numero di file "
                "incoerente con le righe della griglia."
            )

        if assegnazione["modo"] == "coppie":
            if "modalita_trio" not in configurazione_aula:
                raise ValueError(
                    f"La voce {indice} dello Storico a coppie non contiene "
                    "la posizione del trio."
                )
            if configurazione_aula["modalita_trio"] not in {
                None, "prima", "centro", "ultima", "auto"
            }:
                raise ValueError(
                    f"La voce {indice} dello Storico a coppie ha una "
                    "posizione del trio non valida."
                )
        else:
            campi_terzetti = {
                "modalita": str,
                "studente_fisso": (str, type(None)),
                "terzetti_per_fila": int,
                "tipo_blocco_finale": (str, type(None)),
                "fila_blocco_finale": (int, type(None)),
                "posizione_blocco_finale": (str, type(None)),
                "preferenza_resto2": str,
            }
            for chiave, tipo_atteso in campi_terzetti.items():
                if chiave not in configurazione_aula:
                    raise ValueError(
                        f"La voce {indice} dello Storico a terzetti è "
                        f"incompleta; manca «{chiave}»."
                    )
                valore = configurazione_aula[chiave]
                if not isinstance(valore, tipo_atteso) or isinstance(valore, bool):
                    raise ValueError(
                        f"La voce {indice} dello Storico a terzetti ha "
                        f"«{chiave}» in formato non valido."
                    )
            if configurazione_aula["modalita"] != "terzetti":
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti dichiara "
                    "una modalità dell'aula non valida."
                )
            if configurazione_aula["terzetti_per_fila"] < 1:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha un numero "
                    "non valido di terzetti per fila."
                )
            if configurazione_aula["tipo_blocco_finale"] not in {
                None, "coppia", "quartetto"
            }:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha un tipo "
                    "di blocco finale non valido."
                )
            fila_finale = configurazione_aula["fila_blocco_finale"]
            if fila_finale is not None and fila_finale < 0:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha una fila "
                    "del blocco finale non valida."
                )
            if configurazione_aula["posizione_blocco_finale"] not in {
                None, "prima", "centro", "ultima"
            }:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha una "
                    "posizione del blocco finale non valida."
                )
            if configurazione_aula["preferenza_resto2"] not in {
                "coppia", "due_quartetti"
            }:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha una "
                    "preferenza del resto non valida."
                )

        num_righe = configurazione_aula["num_righe"]
        num_colonne = configurazione_aula["num_colonne"]
        nomi_layout = []
        coordinate_layout = set()

        geometria_terzetti = None
        if assegnazione["modo"] == "terzetti":
            from moduli.dominio.aula import ConfigurazioneAula

            geometria_terzetti = ConfigurazioneAula(
                "Validazione Storico terzetti"
            )
            geometria_terzetti.crea_layout_terzetti(
                configurazione_aula["num_studenti"],
                terzetti_per_fila=configurazione_aula["terzetti_per_fila"],
                posizione_blocco_finale=(
                    configurazione_aula["posizione_blocco_finale"] or "ultima"
                ),
                ha_fisso=configurazione_aula["ha_fisso"],
                preferenza_resto2=configurazione_aula["preferenza_resto2"],
            )
            if (
                geometria_terzetti.num_righe != num_righe
                or geometria_terzetti.num_colonne != num_colonne
            ):
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti ha una "
                    "geometria incoerente con i metadati salvati."
                )

        for posizione, elemento in enumerate(layout, start=1):
            if not isinstance(elemento, dict):
                raise ValueError(
                    f"La voce {indice} dello Storico ha l'elemento "
                    f"{posizione} del layout in formato non valido."
                )
            for chiave in ("studente", "riga", "colonna"):
                if chiave not in elemento:
                    raise ValueError(
                        f"La voce {indice} dello Storico ha l'elemento "
                        f"{posizione} del layout incompleto; manca «{chiave}»."
                    )
            nome_studente = elemento["studente"]
            riga = elemento["riga"]
            colonna = elemento["colonna"]
            if not isinstance(nome_studente, str) or not nome_studente.strip():
                raise ValueError(
                    f"La voce {indice} dello Storico ha un nome studente "
                    "non valido nel layout."
                )
            if not intero_valido(riga) or not intero_valido(colonna):
                raise ValueError(
                    f"La voce {indice} dello Storico ha coordinate non valide "
                    "nel layout."
                )
            if not (0 <= riga < num_righe and 0 <= colonna < num_colonne):
                raise ValueError(
                    f"La voce {indice} dello Storico ha coordinate fuori "
                    "dalla geometria salvata."
                )

            coordinata = (riga, colonna)
            if coordinata in coordinate_layout:
                raise ValueError(
                    f"La voce {indice} dello Storico colloca più studenti "
                    f"nella posizione ({riga}, {colonna})."
                )
            coordinate_layout.add(coordinata)

            if riga < 2:
                raise ValueError(
                    f"La voce {indice} dello Storico colloca uno studente "
                    "nella zona degli arredi."
                )
            if (
                geometria_terzetti is not None
                and geometria_terzetti.griglia[riga][colonna].tipo != "banco"
            ):
                raise ValueError(
                    f"La voce {indice} dello Storico colloca uno studente "
                    f"fuori da un banco valido in ({riga}, {colonna})."
                )

            nomi_layout.append(nome_studente)

        if len(nomi_layout) != len(set(nomi_layout)):
            raise ValueError(
                f"La voce {indice} dello Storico contiene studenti duplicati "
                "nel layout."
            )
        if len(nomi_layout) != configurazione_aula["num_studenti"]:
            raise ValueError(
                f"La voce {indice} dello Storico dichiara un numero di "
                "studenti diverso da quello del layout."
            )

        mappa_layout = {elemento["studente"]: elemento for elemento in layout}

        if assegnazione["modo"] == "coppie":
            tipi_validi = {"coppia", "trio", "fisso"}
            for elemento in layout:
                if elemento.get("tipo") not in tipi_validi:
                    raise ValueError(
                        f"La voce {indice} dello Storico a coppie contiene "
                        "un tipo di posto non valido."
                    )

            fissi = [e for e in layout if e["tipo"] == "fisso"]
            if len(fissi) != int(configurazione_aula["ha_fisso"]):
                raise ValueError(
                    f"La voce {indice} dello Storico a coppie non è coerente "
                    "sulla presenza dello studente FISSO."
                )
            if fissi:
                adiacente = fissi[0].get("adiacente")
                if adiacente not in mappa_layout or adiacente == fissi[0]["studente"]:
                    raise ValueError(
                        f"La voce {indice} dello Storico a coppie ha un "
                        "adiacente del FISSO non valido."
                    )

            for elemento in layout:
                if elemento["tipo"] != "coppia":
                    continue
                compagno = elemento.get("compagno")
                controparte = mappa_layout.get(compagno)
                if (
                    controparte is None
                    or controparte.get("tipo") != "coppia"
                    or controparte.get("compagno") != elemento["studente"]
                ):
                    raise ValueError(
                        f"La voce {indice} dello Storico contiene una coppia "
                        "non reciproca."
                    )

            elementi_trio = [e for e in layout if e["tipo"] == "trio"]
            if elementi_trio:
                nomi_trio = {e["studente"] for e in elementi_trio}
                posizioni = {e.get("posizione_trio") for e in elementi_trio}
                if len(elementi_trio) != 3 or posizioni != {
                    "primo", "centrale", "terzo"
                }:
                    raise ValueError(
                        f"La voce {indice} dello Storico contiene un trio "
                        "incompleto o non ordinato."
                    )
                for elemento in elementi_trio:
                    compagni = elemento.get("compagni_trio")
                    if not isinstance(compagni, list) or set(compagni) != (
                        nomi_trio - {elemento["studente"]}
                    ):
                        raise ValueError(
                            f"La voce {indice} dello Storico contiene un trio "
                            "non reciproco."
                        )
                if configurazione_aula["modalita_trio"] is None:
                    raise ValueError(
                        f"La voce {indice} dello Storico contiene un trio ma "
                        "non ne registra la posizione."
                    )
            elif configurazione_aula["modalita_trio"] is not None:
                raise ValueError(
                    f"La voce {indice} dello Storico registra una posizione "
                    "del trio senza contenere un trio."
                )

        else:
            gruppi = assegnazione.get("gruppi")
            if not isinstance(gruppi, list):
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti non contiene "
                    "gruppi validi."
                )
            nomi_gruppi = []
            tipo_per_nome = {}
            for posizione, gruppo in enumerate(gruppi, start=1):
                if not isinstance(gruppo, dict):
                    raise ValueError(
                        f"La voce {indice} dello Storico ha il gruppo "
                        f"{posizione} in formato non valido."
                    )
                tipo = gruppo.get("tipo")
                membri = gruppo.get("membri")
                if tipo not in dimensioni_gruppo or not isinstance(membri, list):
                    raise ValueError(
                        f"La voce {indice} dello Storico ha il gruppo "
                        f"{posizione} in formato non valido."
                    )
                if len(membri) != dimensioni_gruppo[tipo]:
                    raise ValueError(
                        f"La voce {indice} dello Storico ha il gruppo "
                        f"{posizione} con una dimensione non valida."
                    )
                if any(not isinstance(nome, str) or not nome.strip()
                       for nome in membri):
                    raise ValueError(
                        f"La voce {indice} dello Storico ha membri non validi "
                        f"nel gruppo {posizione}."
                    )
                for nome in membri:
                    tipo_per_nome[nome] = tipo
                nomi_gruppi.extend(membri)

            if sorted(nomi_gruppi) != sorted(nomi_layout):
                raise ValueError(
                    f"La voce {indice} dello Storico ha gruppi non coerenti "
                    "con il layout."
                )
            for elemento in layout:
                if elemento.get("tipo") != tipo_per_nome[elemento["studente"]]:
                    raise ValueError(
                        f"La voce {indice} dello Storico a terzetti ha un "
                        "tipo di gruppo incoerente nel layout."
                    )
                if not isinstance(elemento.get("fisso"), bool):
                    raise ValueError(
                        f"La voce {indice} dello Storico a terzetti non "
                        "registra correttamente il FISSO nel layout."
                    )
            fissi_layout = [e for e in layout if e["fisso"]]
            nome_fisso = configurazione_aula["studente_fisso"]
            if configurazione_aula["ha_fisso"]:
                if len(fissi_layout) != 1 or fissi_layout[0]["studente"] != nome_fisso:
                    raise ValueError(
                        f"La voce {indice} dello Storico a terzetti non è "
                        "coerente sullo studente FISSO."
                    )
            elif fissi_layout or nome_fisso is not None:
                raise ValueError(
                    f"La voce {indice} dello Storico a terzetti registra un "
                    "FISSO non previsto."
                )



def valida_metadati_assegnazione(
        storico, *, nome_assegnazione: str, nome_classe: str,
        file_origine: str, generazione: str, modo: str,
        data_creazione: str, progressivo: int, abbinamenti: str) -> None:
    """Verifica il contratto corrente prima di mutare Storico e rotazioni."""
    testi = {
        "nome": nome_assegnazione,
        "classe": nome_classe,
        "file_origine": file_origine,
        "data_creazione": data_creazione,
        "abbinamenti": abbinamenti,
    }
    for etichetta, valore in testi.items():
        if not isinstance(valore, str) or not valore.strip():
            raise ValueError(
                f"Il campo «{etichetta}» della nuova assegnazione è obbligatorio."
            )
    if generazione not in {"mensile", "annuale"}:
        raise ValueError("La generazione deve essere «mensile» oppure «annuale».")
    if modo not in {"coppie", "terzetti", "personalizzata"}:
        raise ValueError(
            "La geometria deve essere «coppie», «terzetti» oppure "
            "«personalizzata»."
        )
    if not isinstance(progressivo, int) or isinstance(progressivo, bool) or progressivo < 1:
        raise ValueError("Il progressivo della nuova assegnazione non è valido.")

    chiave = (file_origine, generazione, modo, progressivo)
    for assegnazione in storico:
        esistente = (
            assegnazione["file_origine"],
            assegnazione["generazione"],
            assegnazione["modo"],
            assegnazione["progressivo"],
        )
        if esistente == chiave:
            raise ValueError(
                "Il progressivo è già presente nella stessa serie dello Storico."
            )


