# -*- coding: utf-8 -*-
"""
configurazione.py — persistenza, backup e Storico delle assegnazioni.

Parte di «PostiPerfetti».
Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3. Distribuito "così com'è", senza garanzie.

Il modulo carica e salva il JSON applicativo, recupera configurazioni danneggiate,
registra le assegnazioni e ricostruisce layout, blacklist e contatori. Le
rotazioni delle modalità a coppie e a terzetti restano separate.
"""

import os
import json
import shutil
from datetime import datetime
from typing import List, Dict

from moduli.utilita import get_base_path

# Blacklist e aggiornamento delle adiacenze a terzetti sono definiti
# nello strato storico condiviso da applicazione e collaudi.
from moduli.strato_storico import (aggiorna_blacklist_terzetti,
                                   CHIAVE_BLACKLIST_PER_MODO)


# Le scelte operative non sono persistenti: al nuovo avvio la GUI
# riparte dai propri valori predefiniti, mentre ogni voce dello Storico
# conserva la fotografia delle opzioni usate per quella disposizione.
CHIAVI_OPERATIVE_NON_PERSISTENTI = (
    "classe_info",
    "configurazione_aula",
    "opzioni_vincoli",
)


class ConfigurazioneApp:
    """Gestisce la configurazione persistente e lo Storico."""

    def __init__(self):
        cartella_dati = os.path.join(get_base_path(), "dati")
        os.makedirs(cartella_dati, exist_ok=True)
        self.file_config = os.path.join(
            cartella_dati,
            "postiperfetti_configurazione.json"
        )

        # Il temporaneo protegge la singola scrittura; il backup conserva
        # invece l’ultima configurazione valida precedente.
        self.file_backup = os.path.join(
            cartella_dati,
            "postiperfetti_configurazione.backup.json"
        )

        self.avviso_recupero = None

        self.config_data = self._carica_configurazione_default()

    def _carica_configurazione_default(self) -> Dict:
        """Restituisce la struttura iniziale della configurazione."""
        return {
            # Persistono soltanto Storico, rotazioni e preferenze globali.
            "storico_assegnazioni": [],
            "coppie_da_evitare": [],
            # Le adiacenze a terzetti hanno una blacklist distinta da
            # quella delle coppie; la chiave è centralizzata nello strato storico.
            CHIAVE_BLACKLIST_PER_MODO["terzetti"]: [],
            "studenti_trio_contatore": {},  # presenze nel trio
            "studenti_vicino_fisso_contatore": {},  # presenze accanto al FISSO
            "tema": "scuro"  # tema dell’interfaccia
        }

    # Caricamento e salvataggio

    def _leggi_json_validato(self, percorso: str) -> Dict:
        """Legge un JSON e ne verifica la struttura minima.

        Le chiavi mancanti possono essere integrate; una chiave presente con un
        tipo inatteso segnala invece un file non valido.
        """
        with open(percorso, 'r', encoding='utf-8') as file_json:
            dati = json.load(file_json)

        if not isinstance(dati, dict):
            raise ValueError(
                "La radice del file JSON non è un oggetto."
            )

        tipi_attesi = {
            "storico_assegnazioni": list,
            "coppie_da_evitare": list,
            CHIAVE_BLACKLIST_PER_MODO["terzetti"]: list,
            "studenti_trio_contatore": dict,
            "studenti_vicino_fisso_contatore": dict,
        }

        for chiave, tipo_atteso in tipi_attesi.items():
            if (
                chiave in dati
                and not isinstance(dati[chiave], tipo_atteso)
            ):
                raise ValueError(
                    f"La chiave «{chiave}» ha un formato non valido: "
                    f"atteso {tipo_atteso.__name__}."
                )

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
        for indice, assegnazione in enumerate(
                dati.get("storico_assegnazioni", []), start=1):
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
                if not isinstance(assegnazione[chiave], tipo_atteso):
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
            if assegnazione["modo"] not in {"coppie", "terzetti"}:
                raise ValueError(
                    f"La voce {indice} dello Storico dichiara una "
                    "geometria non valida."
                )
            if assegnazione["progressivo"] < 1:
                raise ValueError(
                    f"La voce {indice} dello Storico ha un progressivo "
                    "non valido."
                )

        return dati

    def _integra_chiavi_default(self, dati: Dict) -> bool:
        """Aggiunge ricorsivamente le chiavi mancanti senza sovrascrivere dati.

        Restituisce ``True`` quando la struttura è stata modificata.
        """
        configurazione_default = (
            self._carica_configurazione_default()
        )

        modificata = False

        def integra(destinazione, sorgente_default):
            nonlocal modificata

            for chiave, valore_default in sorgente_default.items():
                if chiave not in destinazione:
                    # I valori predefiniti contengono solo tipi JSON:
                    # la serializzazione produce una copia indipendente.
                    destinazione[chiave] = json.loads(
                        json.dumps(
                            valore_default,
                            ensure_ascii=False
                        )
                    )
                    modificata = True

                elif (
                    isinstance(valore_default, dict)
                    and isinstance(destinazione[chiave], dict)
                ):
                    integra(
                        destinazione[chiave],
                        valore_default
                    )

        integra(dati, configurazione_default)
        return modificata

    def _preserva_file_danneggiato(self, percorso: str) -> str:
        """Rinomina un file non valido con data e ora e ne restituisce il percorso."""
        cartella = os.path.dirname(percorso)
        nome_file = os.path.basename(percorso)
        radice, estensione = os.path.splitext(nome_file)

        timestamp = datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )

        destinazione = os.path.join(
            cartella,
            f"{radice}.corrotto-{timestamp}{estensione}"
        )

        # Evita collisioni fra recuperi avvenuti nello stesso secondo.
        contatore = 2
        while os.path.exists(destinazione):
            destinazione = os.path.join(
                cartella,
                f"{radice}.corrotto-{timestamp}-{contatore}"
                f"{estensione}"
            )
            contatore += 1

        os.replace(percorso, destinazione)
        return destinazione

    def _crea_backup_atomico(self, sorgente: str) -> None:
        """Copia un JSON valido nel backup mediante sostituzione atomica."""
        file_temp_backup = self.file_backup + ".tmp"

        try:
            shutil.copy2(
                sorgente,
                file_temp_backup
            )

            # Il backup viene validato prima della promozione.
            self._leggi_json_validato(
                file_temp_backup
            )

            os.replace(
                file_temp_backup,
                self.file_backup
            )

        finally:
            if os.path.exists(file_temp_backup):
                try:
                    os.remove(file_temp_backup)
                except OSError:
                    pass

    def _ripristina_da_backup(self) -> Dict:
        """Ripristina il file principale da un backup validato e restituisce i dati."""
        dati_backup = self._leggi_json_validato(
            self.file_backup
        )

        file_ripristino = (
            self.file_config + ".ripristino.tmp"
        )

        try:
            shutil.copy2(
                self.file_backup,
                file_ripristino
            )

            # Anche la copia temporanea viene validata prima del ripristino.
            self._leggi_json_validato(
                file_ripristino
            )

            os.replace(
                file_ripristino,
                self.file_config
            )

        finally:
            if os.path.exists(file_ripristino):
                try:
                    os.remove(file_ripristino)
                except OSError:
                    pass

        return dati_backup

    def _rimuovi_chiavi_operative_non_persistenti(self) -> list[str]:
        """Elimina le scelte operative che non devono sopravvivere alla sessione."""
        rimosse = []
        for chiave in CHIAVI_OPERATIVE_NON_PERSISTENTI:
            if chiave in self.config_data:
                del self.config_data[chiave]
                rimosse.append(chiave)
        return rimosse

    def _normalizza_configurazione_caricata(self) -> None:
        """Integra le chiavi obbligatorie e rimuove le scelte di sessione."""
        struttura_integrata = self._integra_chiavi_default(self.config_data)
        chiavi_operative_rimosse = (
            self._rimuovi_chiavi_operative_non_persistenti()
        )

        if struttura_integrata or chiavi_operative_rimosse:
            if self.salva_configurazione():
                dettagli = []
                if struttura_integrata:
                    dettagli.append("integrate le chiavi obbligatorie")
                if chiavi_operative_rimosse:
                    dettagli.append(
                        "rimosse scelte di sessione: "
                        + ", ".join(chiavi_operative_rimosse)
                    )
                print("🔖 Configurazione normalizzata: " + "; ".join(dettagli))

    def carica_configurazione(self) -> bool:
        """Carica la configurazione e tenta il recupero automatico se necessario.

        Usa il backup quando il file principale è assente o non valido; conserva
        i file danneggiati e ricorre ai valori predefiniti soltanto quando nessuna
        copia valida è disponibile.
        """
        self.avviso_recupero = None

        # File principale assente.
        if not os.path.exists(self.file_config):
            if not os.path.exists(self.file_backup):
                print(
                    "ℹ️ File configurazione non trovato, "
                    "uso i valori predefiniti"
                )
                return False

            try:
                self.config_data = (
                    self._ripristina_da_backup()
                )

                self.avviso_recupero = {
                    "gravita": "avviso",
                    "titolo": "Configurazione recuperata",
                    "messaggio": (
                        "Il file principale della configurazione "
                        "non era presente.\n\n"
                        "PostiPerfetti lo ha ricostruito usando "
                        "il backup automatico.\n\n"
                        f"Backup utilizzato:\n{self.file_backup}"
                    ),
                }

                self._normalizza_configurazione_caricata()

                print(
                    "✅ Configurazione ripristinata dal backup"
                )
                return True

            except Exception as errore_backup:
                percorso_backup_corrotto = None

                try:
                    percorso_backup_corrotto = (
                        self._preserva_file_danneggiato(
                            self.file_backup
                        )
                    )
                except Exception:
                    pass

                self.config_data = (
                    self._carica_configurazione_default()
                )

                dettaglio_backup = (
                    f"\n\nIl backup non valido è stato conservato in:\n"
                    f"{percorso_backup_corrotto}"
                    if percorso_backup_corrotto
                    else ""
                )

                self.avviso_recupero = {
                    "gravita": "critico",
                    "titolo": "Configurazione non recuperabile",
                    "messaggio": (
                        "Il file principale non era presente e il "
                        "backup automatico non è utilizzabile.\n\n"
                        "PostiPerfetti è stato avviato con una "
                        "configurazione vuota.\n\n"
                        f"Errore del backup:\n{errore_backup}"
                        f"{dettaglio_backup}"
                    ),
                }

                return False

        # File principale presente.
        try:
            self.config_data = self._leggi_json_validato(
                self.file_config
            )

        except Exception as errore_principale:
            percorso_corrotto = None

            try:
                percorso_corrotto = (
                    self._preserva_file_danneggiato(
                        self.file_config
                    )
                )
            except Exception as errore_preservazione:
                print(
                    "⚠️ Impossibile preservare il JSON "
                    f"danneggiato: {errore_preservazione}"
                )

            # Tenta il recupero dall’ultimo backup valido.
            if os.path.exists(self.file_backup):
                try:
                    self.config_data = (
                        self._ripristina_da_backup()
                    )

                    dettaglio_corrotto = (
                        f"\n\nIl file danneggiato è stato "
                        f"conservato in:\n{percorso_corrotto}"
                        if percorso_corrotto
                        else ""
                    )

                    self.avviso_recupero = {
                        "gravita": "avviso",
                        "titolo": "Storico recuperato dal backup",
                        "messaggio": (
                            "Il file principale della configurazione "
                            "era danneggiato o incompleto.\n\n"
                            "PostiPerfetti ha ripristinato automaticamente "
                            "l'ultima copia valida disponibile.\n\n"
                            f"Errore rilevato:\n{errore_principale}"
                            f"{dettaglio_corrotto}"
                        ),
                    }

                    self._normalizza_configurazione_caricata()

                    print(
                        "✅ Configurazione recuperata dal backup"
                    )
                    return True

                except Exception as errore_backup:
                    percorso_backup_corrotto = None

                    try:
                        percorso_backup_corrotto = (
                            self._preserva_file_danneggiato(
                                self.file_backup
                            )
                        )
                    except Exception:
                        pass

                    self.config_data = (
                        self._carica_configurazione_default()
                    )

                    dettagli = []

                    if percorso_corrotto:
                        dettagli.append(
                            "File principale conservato in:\n"
                            f"{percorso_corrotto}"
                        )

                    if percorso_backup_corrotto:
                        dettagli.append(
                            "Backup conservato in:\n"
                            f"{percorso_backup_corrotto}"
                        )

                    dettaglio_file = (
                        "\n\n" + "\n\n".join(dettagli)
                        if dettagli
                        else ""
                    )

                    self.avviso_recupero = {
                        "gravita": "critico",
                        "titolo": "Storico non recuperabile",
                        "messaggio": (
                            "Sia il file principale sia il backup "
                            "automatico risultano non validi.\n\n"
                            "PostiPerfetti è stato avviato con una "
                            "configurazione vuota.\n\n"
                            f"Errore principale:\n{errore_principale}\n\n"
                            f"Errore backup:\n{errore_backup}"
                            f"{dettaglio_file}"
                        ),
                    }

                    return False

            # Senza un backup valido riparte dalla configurazione iniziale.
            self.config_data = (
                self._carica_configurazione_default()
            )

            dettaglio_corrotto = (
                f"\n\nIl file danneggiato è stato conservato in:\n"
                f"{percorso_corrotto}"
                if percorso_corrotto
                else ""
            )

            self.avviso_recupero = {
                "gravita": "critico",
                "titolo": "Configurazione danneggiata",
                "messaggio": (
                    "Il file della configurazione non è leggibile e "
                    "non esiste ancora un backup automatico.\n\n"
                    "PostiPerfetti è stato avviato con una "
                    "configurazione vuota.\n\n"
                    f"Errore rilevato:\n{errore_principale}"
                    f"{dettaglio_corrotto}"
                ),
            }

            return False

        # File principale valido.

        # Un backup danneggiato viene preservato e rigenerato dal file
        # principale, che in questo ramo è già stato validato.
        if os.path.exists(self.file_backup):
            try:
                self._leggi_json_validato(
                    self.file_backup
                )

            except Exception as errore_backup:
                percorso_backup_corrotto = None

                try:
                    percorso_backup_corrotto = (
                        self._preserva_file_danneggiato(
                            self.file_backup
                        )
                    )
                except Exception:
                    pass

                try:
                    self._crea_backup_atomico(
                        self.file_config
                    )

                    dettaglio = (
                        f"\n\nIl vecchio backup è stato conservato in:\n"
                        f"{percorso_backup_corrotto}"
                        if percorso_backup_corrotto
                        else ""
                    )

                    self.avviso_recupero = {
                        "gravita": "avviso",
                        "titolo": "Backup automatico rigenerato",
                        "messaggio": (
                            "La configurazione principale è integra, "
                            "ma il backup automatico risultava danneggiato.\n\n"
                            "È stato creato un nuovo backup valido."
                            f"{dettaglio}\n\n"
                            f"Errore rilevato:\n{errore_backup}"
                        ),
                    }

                except Exception as errore_creazione:
                    print(
                        "⚠️ Impossibile rigenerare il backup: "
                        f"{errore_creazione}"
                    )

        else:
            # Se manca, crea il primo backup dal JSON esistente.
            try:
                self._crea_backup_atomico(
                    self.file_config
                )
            except Exception as errore_backup:
                print(
                    "⚠️ Impossibile creare il backup iniziale: "
                    f"{errore_backup}"
                )

        self._normalizza_configurazione_caricata()

        print(
            f"✅ Configurazione caricata da "
            f"{self.file_config}"
        )
        return True

    def salva_configurazione(self) -> bool:
        """Salva la configurazione in modo atomico e mantiene un backup valido.

        Scrive e sincronizza un file temporaneo, lo valida, conserva il precedente
        JSON valido come backup e infine sostituisce il file principale.
        """
        file_temp = self.file_config + ".tmp"

        try:
            # Integra le chiavi obbligatorie ed esclude le scelte operative
            # dalla persistenza.
            self._integra_chiavi_default(
                self.config_data
            )
            self._rimuovi_chiavi_operative_non_persistenti()

            # Scrive e sincronizza il file temporaneo.
            with open(
                    file_temp,
                    'w',
                    encoding='utf-8') as file_json:

                json.dump(
                    self.config_data,
                    file_json,
                    indent=2,
                    ensure_ascii=False
                )

                file_json.flush()

                # Sincronizza il contenuto prima della sostituzione finale.
                os.fsync(file_json.fileno())

            # Valida il temporaneo prima di promuoverlo.
            self._leggi_json_validato(
                file_temp
            )

            # Conserva come backup il precedente file principale valido.
            if os.path.exists(self.file_config):
                try:
                    self._leggi_json_validato(
                        self.file_config
                    )

                    self._crea_backup_atomico(
                        self.file_config
                    )

                except Exception as errore_precedente:
                    # Un file alterato mentre il programma è aperto non deve
                    # sostituire il backup valido.
                    try:
                        percorso_preservato = (
                            self._preserva_file_danneggiato(
                                self.file_config
                            )
                        )
                        print(
                            "⚠️ File precedente non valido, "
                            f"conservato in {percorso_preservato}: "
                            f"{errore_precedente}"
                        )
                    except Exception as errore_preservazione:
                        print(
                            "⚠️ File precedente non valido e non "
                            "preservabile: "
                            f"{errore_preservazione}"
                        )

            # Sostituisce atomicamente il file principale.
            os.replace(
                file_temp,
                self.file_config
            )

            # Al primo salvataggio crea anche il backup iniziale.
            if not os.path.exists(self.file_backup):
                try:
                    self._crea_backup_atomico(
                        self.file_config
                    )
                except Exception as errore_backup:
                    print(
                        "⚠️ Configurazione salvata, ma non è stato "
                        f"possibile creare il backup: {errore_backup}"
                    )

            print(
                f"💾 Configurazione salvata in "
                f"{self.file_config}"
            )
            return True

        except Exception as errore:
            print(
                f"❌ Errore salvataggio configurazione: "
                f"{errore}"
            )

            if os.path.exists(file_temp):
                try:
                    os.remove(file_temp)
                except OSError:
                    pass

            return False

    # Storico in modalità a coppie

    def aggiungi_assegnazione_storico(
            self, nome_assegnazione: str, coppie: List[tuple], trio=None,
            configurazione_aula=None, file_origine=None, report_completo=None,
            studente_fisso=None, gruppo_adiacente_fisso=None,
            nome_adiacente_fisso=None, genere_misto=False,
            statistiche_generali=None, metadati_casualita=None, *,
            nome_classe: str, generazione: str, data_creazione: str,
            progressivo: int, abbinamenti: str):
        """Registra nello Storico un'assegnazione della modalità a coppie.

        Salva layout, opzioni e diagnostica disponibili, quindi aggiorna coppie,
        trio e contatore del vicino diretto del FISSO.
        """

        nuova_assegnazione = {
            "data_creazione": data_creazione,
            "nome": nome_assegnazione,
            "classe": nome_classe,
            "file_origine": file_origine if file_origine else "Non specificato",
            "generazione": generazione,
            "modo": "coppie",
            "progressivo": int(progressivo),
            "abbinamenti": abbinamenti,
        }
        if metadati_casualita:
            nuova_assegnazione["casualita"] = metadati_casualita
        if statistiche_generali:
            nuova_assegnazione["statistiche_generali"] = [
                dict(riga) for riga in statistiche_generali
            ]

        if configurazione_aula:
            num_studenti = len(coppie) * 2 + (3 if trio else 0) + (1 if studente_fisso else 0)
            if gruppo_adiacente_fisso:
                num_studenti += 2

            nuova_assegnazione["configurazione_aula"] = {
                "num_file": configurazione_aula.num_righe - 2,  # esclude le due righe degli arredi
                "posti_per_fila": self._calcola_posti_per_fila(configurazione_aula),
                "modalita_trio": self._determina_modalita_trio_salvata(trio, configurazione_aula),
                "num_studenti": num_studenti,
                "num_righe": configurazione_aula.num_righe,
                "num_colonne": configurazione_aula.num_colonne,
                "ha_fisso": studente_fisso is not None,
                "larghezza_blocco_sx": getattr(configurazione_aula, 'larghezza_blocco_sx', 2),
                # Fotografia dell’opzione usata da questa assegnazione;
                # non diventa un valore predefinito per sessioni successive.
                "genere_misto": genere_misto
            }

            nuova_assegnazione["layout"] = self._estrai_layout_da_configurazione(
                configurazione_aula, coppie, trio, studente_fisso=studente_fisso,
                gruppo_adiacente_fisso=gruppo_adiacente_fisso,
                nome_adiacente_fisso=nome_adiacente_fisso
            )

            if report_completo:
                nuova_assegnazione["report_completo"] = report_completo

        self.config_data["storico_assegnazioni"].append(nuova_assegnazione)

        self._aggiorna_coppie_da_evitare(
            coppie, trio, studente_fisso=studente_fisso,
            gruppo_adiacente_fisso=gruppo_adiacente_fisso,
            nome_adiacente_fisso=nome_adiacente_fisso
        )

        self.salva_configurazione()

    # Storico in modalità a terzetti

    def aggiungi_assegnazione_storico_terzetti(self, nome_assegnazione, gruppi,
                                               configurazione_aula,
                                               file_origine=None,
                                               report_completo=None,
                                               studente_fisso=None,
                                               genere_misto=False,
                                               posizione_blocco_finale=None,
                                               preferenza_resto2='coppia',
                                               statistiche_generali=None,
                                               metadati_casualita=None, *,
                                               nome_classe: str,
                                               generazione: str,
                                               data_creazione: str,
                                               progressivo: int,
                                               abbinamenti: str):
        """Registra nello Storico un'assegnazione della modalità a terzetti.

        La voce conserva i gruppi ordinati come fonte delle adiacenze, il layout
        grafico e i metadati necessari alla ricostruzione. Storico e blacklist
        vengono aggiornati soltanto quando la disposizione è accettata.
        """
        # L’ordine dei membri è quello fisico da sinistra a destra ed è
        # la fonte da cui si ricavano le adiacenze consecutive.
        gruppi_salvati = []
        for gruppo in gruppi:
            gruppi_salvati.append({
                "tipo": gruppo.tipo,  # tipo e ordine del gruppo
                "membri": [s.get_nome_completo() for s in gruppo.membri],
            })

        num_studenti = sum(len(g["membri"]) for g in gruppi_salvati)

        # Il nome del FISSO permette di marcarne il posto nel layout.
        nome_fisso = (studente_fisso.get_nome_completo()
                      if studente_fisso is not None else None)

        # Associa a ogni studente il tipo del proprio gruppo.
        tipo_per_nome = {}
        for g in gruppi_salvati:
            for nome in g["membri"]:
                tipo_per_nome[nome] = g["tipo"]

        layout = []
        righe_con_banchi = set()  # file effettive con banchi
        for riga in range(configurazione_aula.num_righe):
            for colonna in range(configurazione_aula.num_colonne):
                posto = configurazione_aula.griglia[riga][colonna]
                if posto.tipo == 'banco':
                    righe_con_banchi.add(riga)
                    if posto.occupato_da:
                        # Converte l’identificatore interno nel nome leggibile.
                        nome = posto.occupato_da.replace('_', ' ')
                        layout.append({
                            "studente": nome,
                            "riga": riga,
                            "colonna": colonna,
                            "tipo": tipo_per_nome.get(nome, "gruppo"),
                            "fisso": (nome == nome_fisso),
                        })

        # Conta le file che contengono davvero banchi. I posti per fila sono
        # invece il valore nominale mostrato dalla GUI; i valori predefiniti
        # evitano che metadati incompleti blocchino il salvataggio.
        nuova_assegnazione = {
            "data_creazione": data_creazione,
            "nome": nome_assegnazione,
            "classe": nome_classe,
            "file_origine": file_origine if file_origine else "Non specificato",
            "generazione": generazione,
            "modo": "terzetti",
            "progressivo": int(progressivo),
            "abbinamenti": abbinamenti,
            "gruppi": gruppi_salvati,
            "layout": layout,
            "configurazione_aula": {
                "modalita": "terzetti",
                "num_file": len(righe_con_banchi),
                "posti_per_fila": getattr(configurazione_aula,
                                          'terzetti_per_fila', 3) * 3,
                "num_studenti": num_studenti,
                "num_righe": configurazione_aula.num_righe,
                "num_colonne": configurazione_aula.num_colonne,
                "ha_fisso": studente_fisso is not None,
                "studente_fisso": nome_fisso,
                "genere_misto": genere_misto,
                "larghezza_blocco_sx": getattr(configurazione_aula,
                                               'larghezza_blocco_sx', 3),
                "terzetti_per_fila": getattr(configurazione_aula,
                                             'terzetti_per_fila', 3),
                "tipo_blocco_finale": getattr(configurazione_aula,
                                              'tipo_blocco_finale', None),
                "fila_blocco_finale": getattr(configurazione_aula,
                                              'fila_blocco_finale', None),
                "posizione_blocco_finale": posizione_blocco_finale,
                "preferenza_resto2": preferenza_resto2,
            },
        }
        if metadati_casualita:
            nuova_assegnazione["casualita"] = metadati_casualita
        if statistiche_generali:
            nuova_assegnazione["statistiche_generali"] = [
                dict(riga) for riga in statistiche_generali
            ]

        if report_completo:
            nuova_assegnazione["report_completo"] = report_completo

        self.config_data["storico_assegnazioni"].append(nuova_assegnazione)

        # La blacklist registra tutte le coppie consecutive dei gruppi,
        # compresa l’adiacenza del FISSO; gli estremi non sono vicini.
        adiacenze = []
        for g in gruppi_salvati:
            membri = g["membri"]
            adiacenze.extend(zip(membri, membri[1:]))
        if adiacenze:
            aggiorna_blacklist_terzetti(self, adiacenze)

        self.salva_configurazione()

    # Metadati e ricostruzione dei layout

    def _calcola_posti_per_fila(self, configurazione_aula):
        """Conta i posti disponibili nella prima fila di banchi."""
        if len(configurazione_aula.griglia) > 2:
            prima_fila_banchi = configurazione_aula.griglia[2]
            posti_contati = sum(1 for posto in prima_fila_banchi if posto.tipo == 'banco')
            return posti_contati

        return 6


    def _determina_modalita_trio_salvata(self, trio, configurazione_aula):
        """Restituisce la posizione del trio nella griglia salvata."""
        if not trio:
            return None

        trio_nomi = {f"{s.cognome}_{s.nome}" for s in trio}

        banchi_per_fila = configurazione_aula.get_banchi_per_fila()

        for idx_fila, banchi_fila in enumerate(banchi_per_fila):
            studenti_trio_in_fila = 0
            for banco in banchi_fila:
                if banco.occupato_da and banco.occupato_da in trio_nomi:
                    studenti_trio_in_fila += 1

            if studenti_trio_in_fila == 3:
                if idx_fila == 0:
                    return "prima"
                elif idx_fila == len(banchi_per_fila) - 1:
                    return "ultima"
                else:
                    return "centro"

        return "auto"


    def _estrai_layout_da_configurazione(self, configurazione_aula, coppie, trio,
                                         studente_fisso=None, gruppo_adiacente_fisso=None,
                                         nome_adiacente_fisso=None):
        """Serializza coordinate e relazioni degli studenti presenti nell'aula."""
        layout = []

        mappa_coppie = {}
        for studente1, studente2, info in coppie:
            nome1 = studente1.get_nome_completo()
            nome2 = studente2.get_nome_completo()
            mappa_coppie[nome1] = {"tipo": "coppia", "compagno": nome2, "info": info}
            mappa_coppie[nome2] = {"tipo": "coppia", "compagno": nome1, "info": info}

        if gruppo_adiacente_fisso:
            s1_adj = gruppo_adiacente_fisso[0]
            s2_adj = gruppo_adiacente_fisso[1]
            info_adj = gruppo_adiacente_fisso[2] if len(gruppo_adiacente_fisso) > 2 else {}
            nome1_adj = s1_adj.get_nome_completo()
            nome2_adj = s2_adj.get_nome_completo()
            mappa_coppie[nome1_adj] = {"tipo": "coppia", "compagno": nome2_adj, "info": info_adj}
            mappa_coppie[nome2_adj] = {"tipo": "coppia", "compagno": nome1_adj, "info": info_adj}

        mappa_trio = {}
        if trio:
            nomi_trio = [s.get_nome_completo() for s in trio]
            for idx, studente in enumerate(trio):
                nome = studente.get_nome_completo()
                posizione = ["primo", "centrale", "terzo"][idx]
                mappa_trio[nome] = {
                    "tipo": "trio",
                    "posizione_trio": posizione,
                    "compagni_trio": [n for n in nomi_trio if n != nome]
                }

        mappa_fisso = {}
        if studente_fisso:
            nome_fisso = studente_fisso.get_nome_completo()
            mappa_fisso[nome_fisso] = {
                "tipo": "fisso",
                "adiacente": nome_adiacente_fisso  # valido per coppia e trio
            }

        for riga_idx, riga in enumerate(configurazione_aula.griglia):
            for col_idx, posto in enumerate(riga):
                if posto.tipo == 'banco' and posto.occupato_da:
                    nome_completo = posto.occupato_da.replace('_', ' ')

                    info_studente = {
                        "studente": nome_completo,
                        "riga": riga_idx,
                        "colonna": col_idx
                    }

                    if nome_completo in mappa_fisso:
                        info_studente.update(mappa_fisso[nome_completo])
                    elif nome_completo in mappa_trio:
                        info_studente.update(mappa_trio[nome_completo])
                    elif nome_completo in mappa_coppie:
                        info_studente.update(mappa_coppie[nome_completo])
                        info_studente["punteggio"] = mappa_coppie[nome_completo]["info"].get("punteggio_totale", 0)

                    layout.append(info_studente)

        return layout

    # Ricostruzione del layout salvato

    def ricostruisci_layout_da_storico(self, indice_assegnazione):
        """Ricostruisce la piantina di un'assegnazione salvata.

        Restituisce ``(configurazione_aula, assegnazione)`` oppure
        ``(None, None)`` quando i dati non permettono la ricostruzione.
        """
        try:
            storico = self.config_data.get("storico_assegnazioni", [])
            if indice_assegnazione < 0 or indice_assegnazione >= len(storico):
                print(f"❌ Indice {indice_assegnazione} non valido (storico ha {len(storico)} elementi)")
                return None, None

            assegnazione = storico[indice_assegnazione]

            if "layout" not in assegnazione or "configurazione_aula" not in assegnazione:
                print(f"⚠️ Assegnazione '{assegnazione.get('nome', 'Senza nome')}' in dati incompleti - impossibile ricostruire layout")
                return None, None

            config_aula_data = assegnazione["configurazione_aula"]
            layout_data = assegnazione["layout"]

            print(f"🔄 Ricostruzione layout: {assegnazione.get('nome', 'Senza nome')}")
            print(f"   📊 Configurazione: {config_aula_data['num_file']} file x {config_aula_data['posti_per_fila']} posti")
            print(f"   👥 Studenti: {config_aula_data['num_studenti']}")

            from moduli.aula import ConfigurazioneAula, PostoAula
            config_ricostruita = ConfigurazioneAula(f"Layout {assegnazione.get('nome', 'Storico')}")

            num_righe_salvate = config_aula_data.get('num_righe')
            num_colonne_salvate = config_aula_data.get('num_colonne')

            # Le voci a terzetti ricreano la geometria dedicata; quelle a coppie
            # usano le dimensioni salvate.
            if assegnazione["modo"] == "terzetti":
                print(f"   🧩 Voce TERZETTI: geometria ricreata con crea_layout_terzetti")
                config_ricostruita.crea_layout_terzetti(
                    config_aula_data.get('num_studenti', len(layout_data)),
                    terzetti_per_fila=config_aula_data.get('terzetti_per_fila', 3),
                    # In assenza del blocco finale la posizione non incide
                    # sulla geometria ricostruita.
                    posizione_blocco_finale=(config_aula_data.get('posizione_blocco_finale')
                                             or 'ultima'),
                    ha_fisso=config_aula_data.get('ha_fisso', False),
                    preferenza_resto2=config_aula_data.get('preferenza_resto2', 'coppia'),
                )
                # Le dimensioni ricreate devono coincidere con quelle salvate:
                # una divergenza indica dati incoerenti.
                if (num_righe_salvate and num_colonne_salvate
                        and (config_ricostruita.num_righe != num_righe_salvate
                             or config_ricostruita.num_colonne != num_colonne_salvate)):
                    print(f"   ⚠️ Dimensioni ricreate "
                          f"{config_ricostruita.num_righe}×{config_ricostruita.num_colonne} "
                          f"≠ salvate {num_righe_salvate}×{num_colonne_salvate}")

            elif num_righe_salvate and num_colonne_salvate:
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

                larghezza_sx_salvata = config_aula_data.get('larghezza_blocco_sx')
                if larghezza_sx_salvata:
                    larghezza_blocco = larghezza_sx_salvata
                else:
                    ha_trio_storico = (config_aula_data.get('num_studenti', 0) % 2 == 1)
                    larghezza_blocco = 3 if ha_trio_storico else 2

                posizioni_arredi = config_ricostruita._calcola_posizioni_fila_normale(larghezza_blocco)
                config_ricostruita.griglia[0][posizioni_arredi[0]] = PostoAula(0, posizioni_arredi[0], 'lim')
                config_ricostruita.griglia[0][posizioni_arredi[1]] = PostoAula(0, posizioni_arredi[1], 'lim')
                config_ricostruita.griglia[0][posizioni_arredi[2]] = PostoAula(0, posizioni_arredi[2], 'cattedra')
                config_ricostruita.griglia[0][posizioni_arredi[3]] = PostoAula(0, posizioni_arredi[3], 'cattedra')
                config_ricostruita.griglia[0][posizioni_arredi[4]] = PostoAula(0, posizioni_arredi[4], 'lavagna')
                config_ricostruita.griglia[0][posizioni_arredi[5]] = PostoAula(0, posizioni_arredi[5], 'lavagna')

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

            else:
                # Se le dimensioni mancano, ricorre al generatore standard.
                print(f"   ⚠️ Dimensioni esatte non disponibili, uso metodo standard")
                config_ricostruita.crea_layout_standard(
                    num_studenti=config_aula_data['num_studenti'],
                    num_file=config_aula_data['num_file'],
                    posti_per_fila=config_aula_data['posti_per_fila'],
                    posizione_trio=config_aula_data.get('modalita_trio'),
                    ha_fisso=config_aula_data.get('ha_fisso', False)
                )

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
                    else:
                        print(f"⚠️ Posizione ({riga},{colonna}) non è un banco per {nome_studente}")
                else:
                    print(f"⚠️ Posizione ({riga},{colonna}) fuori range per {nome_studente}")

            print(f"✅ Layout ricostruito con successo!")

            return config_ricostruita, assegnazione

        except Exception as e:
            print(f"❌ Errore ricostruzione layout: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    # Aggiornamento delle rotazioni in modalità a coppie

    def _aggiorna_coppie_da_evitare(self, nuove_coppie: List[tuple], trio=None,
                                    studente_fisso=None, gruppo_adiacente_fisso=None,
                                    nome_adiacente_fisso=None):
        """Aggiorna blacklist e contatori della modalità a coppie.

        Registra le coppie normali, le adiacenze consecutive del trio, la coppia
        collocata accanto al FISSO e il suo vicino diretto.
        """

        # Indicizza le coppie esistenti per aggiornare i contatori in O(1).
        coppie_esistenti = {}
        for item in self.config_data["coppie_da_evitare"]:
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
                self.config_data["coppie_da_evitare"].append(nuova_voce)
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
                    self.config_data["coppie_da_evitare"].append(nuova_voce)
                    coppie_esistenti[chiave] = nuova_voce
                    print(f"   🆕 Nuova coppia virtuale aggiunta: {chiave[0]} + {chiave[1]}")

            # Ogni componente del trio riceve un solo incremento.
            for studente in trio:
                nome_studente = studente.get_nome_completo()
                if nome_studente not in self.config_data["studenti_trio_contatore"]:
                    self.config_data["studenti_trio_contatore"][nome_studente] = 0

                self.config_data["studenti_trio_contatore"][nome_studente] += 1
                print(f"   📊 {nome_studente}: ora {self.config_data['studenti_trio_contatore'][nome_studente]} volte nel trio")

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
                self.config_data["coppie_da_evitare"].append(nuova_voce)
                coppie_esistenti[chiave_adiacente] = nuova_voce
                print(f"   🆕 Nuova coppia adiacente FISSO aggiunta in blacklist")

        # Il contatore dedicato riguarda solo il vicino diretto del FISSO,
        # non gli altri membri dell’eventuale gruppo adiacente.
        if studente_fisso and nome_adiacente_fisso:
            if "studenti_vicino_fisso_contatore" not in self.config_data:
                self.config_data["studenti_vicino_fisso_contatore"] = {}

            contatore = self.config_data["studenti_vicino_fisso_contatore"]
            if nome_adiacente_fisso not in contatore:
                contatore[nome_adiacente_fisso] = 0
            contatore[nome_adiacente_fisso] += 1
            print(f"   📌 Contatore vicino FISSO: {nome_adiacente_fisso} → {contatore[nome_adiacente_fisso]} volte")

    # Ricostruzione delle blacklist dallo Storico

    def _ricostruisci_blacklist_da_storico(self):
        """Ricalcola blacklist e contatori dalle assegnazioni rimaste nello Storico."""
        print(f"🔄 RICOSTRUZIONE BLACKLIST: Inizio elaborazione Storico...")

        # Riparte da strutture vuote per entrambe le modalità e per tutti
        # i contatori derivati.
        self.config_data["coppie_da_evitare"] = []
        self.config_data[CHIAVE_BLACKLIST_PER_MODO["terzetti"]] = []
        self.config_data["studenti_trio_contatore"] = {}
        self.config_data["studenti_vicino_fisso_contatore"] = {}
        print(f"   ✅ Blacklist (coppie + terzetti) e contatori azzerati")

        storico_rimasto = self.config_data["storico_assegnazioni"]
        num_assegnazioni = len(storico_rimasto)

        if num_assegnazioni == 0:
            print(f"   ℹ️ Storico vuoto - blacklist rimane vuota")
            return

        print(f"   📋 Elaborazione {num_assegnazioni} assegnazioni rimaste...")

        for idx, assegnazione in enumerate(storico_rimasto, 1):
            nome_assegnazione = assegnazione.get("nome", f"Assegnazione {idx}")
            print(f"   🔄 Elaboro: {nome_assegnazione}")

            # Le voci a terzetti si ricostruiscono dai gruppi ordinati.
            # Il ``continue`` impedisce che il loro layout alimenti anche
            # la blacklist delle coppie.
            if assegnazione["modo"] == "terzetti":
                adiacenze = []
                for gruppo in assegnazione.get("gruppi", []):
                    membri = gruppo.get("membri", [])
                    adiacenze.extend(zip(membri, membri[1:]))
                if adiacenze:
                    aggiorna_blacklist_terzetti(self, adiacenze)
                print(f"      ✅ Voce terzetti: {len(adiacenze)} adiacenze ricostruite")
                continue  # evita contaminazioni fra blacklist

            # Le disposizioni a coppie vengono ricostruite dal layout salvato.
            coppie_da_elaborare = []
            trio_da_elaborare = None
            studente_fisso_fittizio = None
            gruppo_adiacente_fittizio = None

            layout = assegnazione.get("layout", [])

            if layout:
                coppie_processate = set()
                trio_nomi = []

                for studente_info in layout:
                    tipo = studente_info.get("tipo")
                    nome = studente_info.get("studente", "")

                    if tipo == "coppia":
                        compagno = studente_info.get("compagno", "")
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
                        nome_adiacente = studente_info.get("adiacente", "")
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
                        s = type('Student', (), {'get_nome_completo': lambda self, n=nome_trio: n})()
                        trio_fittizio.append(s)
                    trio_da_elaborare = trio_fittizio

            # Riusa la stessa funzione di aggiornamento. La coppia accanto
            # al FISSO è già compresa fra le coppie del layout.
            if coppie_da_elaborare or trio_da_elaborare:
                self._aggiorna_coppie_da_evitare(coppie_da_elaborare, trio_da_elaborare)
                print(f"      ✅ Elaborati: {len(coppie_da_elaborare)} coppie" +
                      (f" + 1 trio" if trio_da_elaborare else ""))

            # Il contatore del vicino diretto viene ricostruito separatamente.
            if studente_fisso_fittizio and gruppo_adiacente_fittizio:
                nome_adiacente = gruppo_adiacente_fittizio[0].get_nome_completo()
                if "studenti_vicino_fisso_contatore" not in self.config_data:
                    self.config_data["studenti_vicino_fisso_contatore"] = {}
                contatore = self.config_data["studenti_vicino_fisso_contatore"]
                if nome_adiacente not in contatore:
                    contatore[nome_adiacente] = 0
                contatore[nome_adiacente] += 1
                print(f"      📌 Contatore vicino FISSO ricostruito: {nome_adiacente} → {contatore[nome_adiacente]}")

        num_coppie_blacklist = len(self.config_data["coppie_da_evitare"])
        # Riepiloga separatamente le blacklist delle due modalità.
        num_adiacenze_terzetti = len(
            self.config_data.get(CHIAVE_BLACKLIST_PER_MODO["terzetti"], []))
        num_studenti_trio = len(self.config_data["studenti_trio_contatore"])
        num_studenti_vicino = len(self.config_data.get("studenti_vicino_fisso_contatore", {}))

        print(f"   📊 RICOSTRUZIONE COMPLETATA:")
        print(f"      • Coppie in blacklist: {num_coppie_blacklist}")
        print(f"      • Adiacenze terzetti in blacklist: {num_adiacenze_terzetti}")
        print(f"      • Studenti con contatore trio: {num_studenti_trio}")
        print(f"      • Studenti con contatore vicino FISSO: {num_studenti_vicino}")
