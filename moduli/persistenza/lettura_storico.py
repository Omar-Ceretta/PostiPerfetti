# -*- coding: utf-8 -*-
"""Ricostruzione delle piantine nei formati supportati, senza scritture.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from moduli.persistenza.validazione_storico import valida_voce_layout

def ricostruisci_layout(dati, indice_assegnazione):
    """Ricostruisce la piantina di un'assegnazione salvata.

    Restituisce ``(configurazione_aula, assegnazione)`` oppure
    ``(None, None)`` quando i dati non permettono la ricostruzione.

    Le voci Personalizzata non possiedono il vecchio ``layout`` a griglia:
    conservano invece schema semantico, fotografia visuale e collocazioni.
    Questi dati vengono ricomposti e passati all'adattatore di presentazione
    già usato dalla scheda ``Aula``, senza dedurre la geometria dai pixel.
    """
    try:
        storico = dati.get("storico_assegnazioni", [])
        if indice_assegnazione < 0 or indice_assegnazione >= len(storico):
            print(f"❌ Indice {indice_assegnazione} non valido (storico ha {len(storico)} elementi)")
            return None, None

        assegnazione = storico[indice_assegnazione]

        if "formato_disposizione" in assegnazione or "disposizione_fisica" in assegnazione:
            from moduli.persistenza.storico_fisico_standard import ricostruisci_aula_da_voce_fisica
            config = ricostruisci_aula_da_voce_fisica(assegnazione)
            config.sessi_studenti = dict(assegnazione.get('sessi_studenti', {}))
            return config, assegnazione

        if assegnazione.get("modo") == "personalizzata":
            # Riusa il validatore persistente P4.1: se la voce è arrivata
            # fin qui dal file v2 è già valida, ma il controllo locale rende
            # sicura anche una fotografia costruita/modificata in memoria.
            valida_voce_layout(
                assegnazione, indice_assegnazione
            )

            from moduli.dominio.aula_personalizzata import (
                istantanea_visuale_da_json,
                schema_personalizzato_da_json,
            )
            from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
            from moduli.dominio.metrica_pulizia import Gruppo
            from moduli.dominio.presentazione_aula_personalizzata import (
                costruisci_configurazione_aula_personalizzata,
            )
            from moduli.dominio.studenti import Student

            schema = schema_personalizzato_da_json(
                assegnazione["schema_personalizzato"]
            )
            istantanea = istantanea_visuale_da_json(
                assegnazione["layout_visuale_personalizzato"]
            )
            istantanea.valida_contro_schema(schema)

            blocchi_per_id = {blocco.id: blocco for blocco in schema.blocchi}
            tipo_per_firma = {
                tuple(gruppo["membri"]): gruppo["tipo"]
                for gruppo in assegnazione["gruppi"]
            }
            studenti_per_nome = {}

            def studente_segnaposto(nome_completo):
                """Crea un oggetto minimo preservando esattamente il nome."""
                studente = studenti_per_nome.get(nome_completo)
                if studente is not None:
                    return studente

                parti = str(nome_completo).split(" ", 1)
                cognome = parti[0]
                nome = parti[1] if len(parti) > 1 else ""
                studente = Student(cognome, nome, assegnazione.get('sessi_studenti', {}).get(nome_completo, "N"))
                studenti_per_nome[nome_completo] = studente
                return studente

            collocazioni = []
            for dati_collocazione in assegnazione["collocazioni"]:
                firma = tuple(dati_collocazione["gruppo"])
                membri = [
                    studente_segnaposto(nome)
                    for nome in dati_collocazione["gruppo"]
                ]
                gruppo = Gruppo(tipo_per_firma[firma], membri)
                blocco = blocchi_per_id[dati_collocazione["blocco"]]
                collocazioni.append(
                    CollocazioneGruppoBlocco(gruppo, blocco)
                )

            config_ricostruita = costruisci_configurazione_aula_personalizzata(
                istantanea,
                tuple(collocazioni),
            )
            print(
                "🔄 Ricostruzione layout Personalizzata: "
                f"{assegnazione['nome']}"
            )
            print(
                "   🧩 Schema/visuale/collocazioni persistiti: "
                f"{len(collocazioni)} blocchi, "
                f"{config_ricostruita.posti_disponibili} posti"
            )
            print("✅ Layout Personalizzata ricostruito con successo!")
            return config_ricostruita, assegnazione

        config_aula_data = assegnazione["configurazione_aula"]
        layout_data = assegnazione["layout"]

        print(f"🔄 Ricostruzione layout: {assegnazione['nome']}")
        print(f"   📊 Configurazione: {config_aula_data['num_file']} file x {config_aula_data['posti_per_fila']} posti")
        print(f"   👥 Studenti: {config_aula_data['num_studenti']}")

        from moduli.dominio.aula import ConfigurazioneAula, PostoAula
        config_ricostruita = ConfigurazioneAula(f"Layout {assegnazione['nome']}")

        num_righe_salvate = config_aula_data['num_righe']
        num_colonne_salvate = config_aula_data['num_colonne']

        # Le voci a terzetti ricreano la geometria dedicata; quelle a coppie
        # usano le dimensioni salvate.
        if assegnazione["modo"] == "terzetti":
            print(f"   🧩 Voce TERZETTI: geometria ricreata con crea_layout_terzetti")
            config_ricostruita.crea_layout_terzetti(
                config_aula_data['num_studenti'],
                terzetti_per_fila=config_aula_data['terzetti_per_fila'],
                # In assenza del blocco finale la posizione non incide
                # sulla geometria ricostruita.
                posizione_blocco_finale=(
                    config_aula_data['posizione_blocco_finale'] or 'ultima'
                ),
                ha_fisso=config_aula_data['ha_fisso'],
                preferenza_resto2=config_aula_data['preferenza_resto2'],
            )
            # Le dimensioni ricreate devono coincidere con quelle salvate:
            # una divergenza indica dati incoerenti.
            if (
                config_ricostruita.num_righe != num_righe_salvate
                or config_ricostruita.num_colonne != num_colonne_salvate
            ):
                raise ValueError(
                    "La geometria a terzetti ricreata non coincide con "
                    "le dimensioni salvate"
                )

        else:
            # Ricostruisce la griglia usando le dimensioni esatte salvate.
            print(f"   🎯 Usando dimensioni esatte: {num_righe_salvate} righe × {num_colonne_salvate} colonne")

            config_ricostruita.num_righe = num_righe_salvate
            config_ricostruita.num_colonne = num_colonne_salvate

            config_ricostruita.griglia = []
            for r in range(num_righe_salvate):
                riga = []
                for c in range(num_colonne_salvate):
                    riga.append(PostoAula(r, c, 'corridoio'))
                config_ricostruita.griglia.append(riga)

            larghezza_blocco = config_aula_data['larghezza_blocco_sx']

            # Ricava dalla geometria salvata quanti blocchi-coppia erano
            # presenti nel layout live. Non usa direttamente
            # ``posti_per_fila``: nelle file speciali con FISSO/trio quel
            # metadato può includere i posti aggiuntivi del blocco sinistro
            # e non rappresentare il numero di blocchi degli arredi.
            delta_blocchi = num_colonne_salvate - larghezza_blocco + 3
            if delta_blocchi < 9 or delta_blocchi % 3 != 0:
                raise ValueError(
                    "Geometria a coppie non riconducibile al formato corrente"
                )
            num_blocchi_arredi = delta_blocchi // 3
            posti_geometrici = num_blocchi_arredi * 2

            posizioni_arredi = config_ricostruita._calcola_posizioni_fila_normale(
                larghezza_blocco, posti_geometrici)
            blocchi_arredi = [
                (posizioni_arredi[i], posizioni_arredi[i + 1])
                for i in range(0, len(posizioni_arredi), 2)
                if posizioni_arredi[i + 1] < num_colonne_salvate
            ]
            if len(blocchi_arredi) < 3:
                raise ValueError(
                    "Geometria degli arredi non valida nella voce di Storico"
                )

            blocco_lim = blocchi_arredi[0]
            blocco_cattedra = blocchi_arredi[len(blocchi_arredi) // 2]
            blocco_lavagna = blocchi_arredi[-1]
            for colonna in blocco_lim:
                config_ricostruita.griglia[0][colonna] = PostoAula(0, colonna, 'lim')
            for colonna in blocco_cattedra:
                config_ricostruita.griglia[0][colonna] = PostoAula(0, colonna, 'cattedra')
            for colonna in blocco_lavagna:
                config_ricostruita.griglia[0][colonna] = PostoAula(0, colonna, 'lavagna')

            for studente_info in layout_data:
                riga = studente_info["riga"]
                colonna = studente_info["colonna"]

                if riga < num_righe_salvate and colonna < num_colonne_salvate:
                    if config_ricostruita.griglia[riga][colonna].tipo == 'corridoio':
                        config_ricostruita.griglia[riga][colonna] = PostoAula(riga, colonna, 'banco')

            posti_contati = 0
            for riga in config_ricostruita.griglia:
                for posto in riga:
                    if posto.tipo == 'banco':
                        posti_contati += 1

            config_ricostruita.posti_disponibili = posti_contati
            print(f"   ✅ Griglia ricostruita: {posti_contati} banchi totali")


        for studente_info in layout_data:
            nome_studente = studente_info["studente"]
            riga = studente_info["riga"]
            colonna = studente_info["colonna"]

            # Il JSON conserva già il nome completo in forma leggibile.
            id_univoco = nome_studente

            if riga < len(config_ricostruita.griglia) and colonna < len(config_ricostruita.griglia[riga]):
                posto = config_ricostruita.griglia[riga][colonna]
                if posto.tipo == 'banco':
                    posto.occupato_da = id_univoco
                    if studente_info.get('tipo') == 'fisso':
                        config_ricostruita.coord_fisso = (riga, colonna)
                else:
                    print(f"⚠️ Posizione ({riga},{colonna}) non è un banco per {nome_studente}")
            else:
                print(f"⚠️ Posizione ({riga},{colonna}) fuori range per {nome_studente}")

        config_ricostruita.sessi_studenti = dict(assegnazione.get('sessi_studenti', {}))
        print(f"✅ Layout ricostruito con successo!")

        return config_ricostruita, assegnazione

    except Exception as e:
        print(f"❌ Errore ricostruzione layout: {e}")
        import traceback
        traceback.print_exc()
        return None, None


