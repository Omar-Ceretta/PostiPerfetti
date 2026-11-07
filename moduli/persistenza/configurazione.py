# -*- coding: utf-8 -*-
"""
configurazione.py — persistenza, backup e Storico delle assegnazioni.

Parte di «PostiPerfetti».
Autore: prof. Omar Ceretta — I.C. di Tombolo e Galliera Veneta (PD).
Licenza: GNU GPLv3. Distribuito "così com'è", senza garanzie.

Il modulo carica e salva il JSON applicativo, recupera configurazioni danneggiate,
registra le assegnazioni e ricostruisce layout, blacklist e contatori. Le
rotazioni di Coppie, Terzetti e Personalizzata restano strutturalmente separate.
"""

import os
import json
import shutil
import copy
from datetime import datetime
from typing import Dict

from moduli.percorsi import (
    get_state_path,
    inizializza_struttura_dati_utente,
)

# Blacklist e aggiornamento delle adiacenze a terzetti sono definiti
# nello strato storico condiviso da applicazione e collaudi.
from moduli.persistenza.strato_storico import (
    aggiorna_blacklist_personalizzata,
    CHIAVE_BLACKLIST_PER_MODO,
)


AZIONE_FILE_ASSENTE_RICREA = "ricrea"
AZIONE_FILE_ASSENTE_AZZERA = "azzera"
AZIONE_FILE_ASSENTE_ANNULLA = "annulla"

ESITO_SALVATAGGIO_SALVATO = "salvato"
ESITO_SALVATAGGIO_AZZERATO = "azzerato"
ESITO_SALVATAGGIO_ANNULLATO = "annullato"
ESITO_SALVATAGGIO_ERRORE = "errore"



from moduli.persistenza.schema_configurazione import (
    CHIAVE_VERSIONE_SCHEMA as CHIAVE_VERSIONE_SCHEMA,
    VERSIONE_SCHEMA_CONFIGURAZIONE as VERSIONE_SCHEMA_CONFIGURAZIONE,
    CHIAVI_STORICO_E_ROTAZIONI as CHIAVI_STORICO_E_ROTAZIONI,
    configurazione_default, valida_configurazione,
)
from moduli.persistenza.validazione_storico import (
    valida_voce_layout, valida_metadati_assegnazione,
)
from moduli.persistenza.lettura_storico import ricostruisci_layout
from moduli.persistenza.operazioni_storico import rinomina_assegnazione, elimina_assegnazione
from moduli.persistenza.rotazioni_storico import (
    aggiorna_rotazioni_coppie, ricostruisci_rotazioni,
)

class ConfigurazioneApp:
    """Gestisce la configurazione persistente e lo Storico."""

    def __init__(self):
        inizializza_struttura_dati_utente()
        self.file_config = get_state_path(
            "postiperfetti_configurazione.json"
        )

        # Il temporaneo protegge la singola scrittura; il backup conserva
        # invece l’ultima configurazione valida precedente.
        self.file_backup = get_state_path(
            "postiperfetti_configurazione.backup.json"
        )

        self.avviso_recupero = None

        # La GUI installa questi callback dopo avere creato la finestra.
        # Restano opzionali per mantenere il modello utilizzabile nei test e
        # negli strumenti senza interfaccia grafica.
        self.gestore_file_assente = None
        self.gestore_azzeramento_completato = None

        self.ultimo_esito_salvataggio = None
        self._file_config_presente_nella_sessione = False

        self.config_data = self._carica_configurazione_default()

    def copia_temporanea(self):
        """Crea una copia isolata per i calcoli senza duplicare la GUI.

        Le generazioni Annuali modificano una fotografia privata di Storico e
        rotazioni. I callback installati dalla finestra principale non fanno
        parte di quella fotografia e, essendo metodi legati a un QObject, non
        devono essere attraversati da ``deepcopy``.
        """
        temporanea = copy.copy(self)
        temporanea.config_data = copy.deepcopy(self.config_data)
        temporanea.avviso_recupero = None
        temporanea.gestore_file_assente = None
        temporanea.gestore_azzeramento_completato = None
        temporanea.ultimo_esito_salvataggio = None
        return temporanea

    def _carica_configurazione_default(self) -> Dict:
        return configurazione_default()

    # Caricamento e salvataggio

    @staticmethod
    def _valida_voce_storico_personalizzata(assegnazione, indice):
        return valida_voce_layout(assegnazione, indice)

    def _leggi_json_validato(self, percorso: str) -> Dict:
        """Legge il documento e lo affida al validatore puro dello schema."""
        with open(percorso, 'r', encoding='utf-8') as file_json:
            return valida_configurazione(json.load(file_json))

    @staticmethod
    def _chiavi_formato_v1() -> set[str]:
        """Restituisce le chiavi esatte del formato storico pre-P4 (v1 implicito)."""
        return {
            "storico_assegnazioni",
            "coppie_da_evitare",
            CHIAVE_BLACKLIST_PER_MODO["terzetti"],
            "studenti_trio_contatore",
            "studenti_vicino_fisso_contatore",
            "tema",
        }

    def _prepara_migrazione_v1_a_v2(self, dati: object) -> Dict | None:
        """Normalizza in memoria un v1 esatto senza accettare formati ambigui."""
        if not isinstance(dati, dict):
            return None
        if CHIAVE_VERSIONE_SCHEMA in dati:
            return None
        if set(dati) != self._chiavi_formato_v1():
            return None

        migrati = copy.deepcopy(dati)
        migrati[CHIAVE_VERSIONE_SCHEMA] = VERSIONE_SCHEMA_CONFIGURAZIONE
        migrati[CHIAVE_BLACKLIST_PER_MODO["personalizzata"]] = []
        return migrati

    def _valida_dati_v2_senza_installare(self, dati: Dict, percorso_base: str) -> Dict:
        """Valida la fotografia JSON senza scrivere un temporaneo di verifica."""
        return valida_configurazione(json.loads(json.dumps(dati, ensure_ascii=False)))

    def _leggi_json_compatibile(self, percorso: str) -> tuple[Dict, bool]:
        """Legge v2 oppure riconosce e valida il solo v1 storico esatto.

        Restituisce ``(dati_v2, migrato_da_v1)``. Nessun file dell'utente viene
        modificato da questa funzione.
        """
        with open(percorso, "r", encoding="utf-8") as file_json:
            dati_grezzi = json.load(file_json)

        migrati = self._prepara_migrazione_v1_a_v2(dati_grezzi)
        if migrati is None:
            return valida_configurazione(dati_grezzi), False

        return (
            self._valida_dati_v2_senza_installare(migrati, percorso),
            True,
        )

    def _crea_snapshot_pre_v2(self, sorgente: str) -> str:
        """Conserva una copia byte-per-byte della sorgente legacy prima del v2."""
        cartella = os.path.dirname(self.file_config)
        radice = os.path.splitext(os.path.basename(self.file_config))[0]
        destinazione = os.path.join(cartella, f"{radice}.pre-v2.json")

        contatore = 2
        while os.path.exists(destinazione):
            destinazione = os.path.join(
                cartella, f"{radice}.pre-v2-{contatore}.json"
            )
            contatore += 1

        shutil.copy2(sorgente, destinazione)
        return destinazione

    def _installa_migrazione_v2(self, dati_v2: Dict, sorgente_legacy: str) -> str:
        """Promuove atomicamente il v2 dopo validazione e snapshot pre-migrazione."""
        file_temp = self.file_config + ".migrazione-v2.tmp"
        try:
            with open(file_temp, "w", encoding="utf-8") as file_json:
                json.dump(dati_v2, file_json, indent=2, ensure_ascii=False)
                file_json.flush()
                os.fsync(file_json.fileno())

            # La fotografia candidata deve essere valida prima di toccare il main.
            self._leggi_json_validato(file_temp)

            # Requisito P4.0: il legacy viene fotografato PRIMA della sostituzione.
            snapshot = self._crea_snapshot_pre_v2(sorgente_legacy)
            os.replace(file_temp, self.file_config)
            print(
                "✅ Configurazione migrata v1 → v2; fotografia pre-migrazione: "
                f"{snapshot}"
            )
            return snapshot
        finally:
            if os.path.exists(file_temp):
                try:
                    os.remove(file_temp)
                except OSError:
                    pass

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
        """Ripristina il main da un backup v2 o da un v1 legacy validato."""
        dati_backup, migrato_da_v1 = self._leggi_json_compatibile(
            self.file_backup
        )

        file_ripristino = self.file_config + ".ripristino.tmp"

        try:
            if migrato_da_v1:
                with open(file_ripristino, "w", encoding="utf-8") as file_json:
                    json.dump(dati_backup, file_json, indent=2, ensure_ascii=False)
                    file_json.flush()
                    os.fsync(file_json.fileno())
            else:
                shutil.copy2(self.file_backup, file_ripristino)

            # Il file destinato a diventare main è sempre v2 e viene validato
            # prima della promozione.
            self._leggi_json_validato(file_ripristino)

            if migrato_da_v1:
                snapshot = self._crea_snapshot_pre_v2(self.file_backup)
                print(
                    "✅ Backup legacy v1 recuperato come v2; fotografia "
                    f"pre-migrazione: {snapshot}"
                )

            os.replace(file_ripristino, self.file_config)

        finally:
            if os.path.exists(file_ripristino):
                try:
                    os.remove(file_ripristino)
                except OSError:
                    pass

        return dati_backup

    def _concludi_caricamento(self, esito: bool) -> bool:
        """Registra se il file principale esiste al termine del caricamento."""
        self._file_config_presente_nella_sessione = os.path.exists(
            self.file_config
        )
        return bool(esito)

    def azzera_storico_e_rotazioni(self) -> None:
        """Svuota soltanto Storico e memorie di rotazione, preservando il tema."""
        default = self._carica_configurazione_default()
        for chiave in CHIAVI_STORICO_E_ROTAZIONI:
            self.config_data[chiave] = copy.deepcopy(default[chiave])

    def _risolvi_file_assente_prima_del_salvataggio(self) -> str:
        """Chiede alla GUI come procedere se il JSON sparisce in sessione."""
        if (
            not self._file_config_presente_nella_sessione
            or os.path.exists(self.file_config)
        ):
            return AZIONE_FILE_ASSENTE_RICREA

        gestore = self.gestore_file_assente
        if gestore is None:
            return AZIONE_FILE_ASSENTE_ANNULLA

        try:
            azione = gestore(self.file_config)
        except Exception as errore:
            print(
                "⚠️ Errore nella richiesta sul file di stato assente: "
                f"{errore}"
            )
            return AZIONE_FILE_ASSENTE_ANNULLA

        if azione not in {
            AZIONE_FILE_ASSENTE_RICREA,
            AZIONE_FILE_ASSENTE_AZZERA,
            AZIONE_FILE_ASSENTE_ANNULLA,
        }:
            return AZIONE_FILE_ASSENTE_ANNULLA
        return azione

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
                return self._concludi_caricamento(False)

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

                print(
                    "✅ Configurazione ripristinata dal backup"
                )
                return self._concludi_caricamento(True)

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

                return self._concludi_caricamento(False)

        # File principale presente. Il solo v1 storico esatto viene migrato
        # esplicitamente; qualunque altro formato divergente segue il recupero.
        try:
            dati_caricati, migrato_da_v1 = self._leggi_json_compatibile(
                self.file_config
            )
            if migrato_da_v1:
                self._installa_migrazione_v2(
                    dati_caricati,
                    self.file_config,
                )
                self.config_data = self._leggi_json_validato(self.file_config)
            else:
                self.config_data = dati_caricati

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

                    print(
                        "✅ Configurazione recuperata dal backup"
                    )
                    return self._concludi_caricamento(True)

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

                    return self._concludi_caricamento(False)

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

            return self._concludi_caricamento(False)

        # File principale valido.

        # Un backup danneggiato viene preservato e rigenerato dal file
        # principale, che in questo ramo è già stato validato.
        if os.path.exists(self.file_backup):
            try:
                # Un backup v1 ancora integro resta una fonte di recupero valida:
                # verrà normalizzato a v2 soltanto se servirà davvero ripristinarlo.
                self._leggi_json_compatibile(
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

        print(
            f"✅ Configurazione caricata da "
            f"{self.file_config}"
        )
        return self._concludi_caricamento(True)

    def salva_configurazione(self) -> bool:
        """Salva la configurazione in modo atomico e mantiene un backup valido.

        Scrive e sincronizza un file temporaneo, lo valida, conserva il precedente
        JSON valido come backup e infine sostituisce il file principale.
        """
        file_temp = self.file_config + ".tmp"
        self.ultimo_esito_salvataggio = None

        file_assente_durante_sessione = (
            self._file_config_presente_nella_sessione
            and not os.path.exists(self.file_config)
        )
        azione_file_assente = (
            self._risolvi_file_assente_prima_del_salvataggio()
        )

        if azione_file_assente == AZIONE_FILE_ASSENTE_ANNULLA:
            self.ultimo_esito_salvataggio = ESITO_SALVATAGGIO_ANNULLATO
            return False

        fotografia_prima_azzeramento = None
        azzeramento_richiesto = (
            azione_file_assente == AZIONE_FILE_ASSENTE_AZZERA
        )
        if azzeramento_richiesto:
            fotografia_prima_azzeramento = copy.deepcopy(self.config_data)
            self.azzera_storico_e_rotazioni()

        try:
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

            # Se il principale è scomparso durante la sessione, il nuovo file
            # diventa l'unica fonte autorevole: anche il backup viene riallineato
            # per evitare che un recupero futuro resusciti dati scartati.
            if (
                file_assente_durante_sessione
                or not os.path.exists(self.file_backup)
            ):
                try:
                    self._crea_backup_atomico(
                        self.file_config
                    )
                except Exception as errore_backup:
                    print(
                        "⚠️ Configurazione salvata, ma non è stato "
                        f"possibile creare il backup: {errore_backup}"
                    )
                    if (
                        file_assente_durante_sessione
                        and os.path.exists(self.file_backup)
                    ):
                        try:
                            os.remove(self.file_backup)
                            print(
                                "⚠️ Backup precedente rimosso perché non "
                                "corrisponde più al file ricreato."
                            )
                        except OSError as errore_rimozione:
                            print(
                                "⚠️ Impossibile rimuovere il backup non "
                                f"allineato: {errore_rimozione}"
                            )

            self._file_config_presente_nella_sessione = True

            if azzeramento_richiesto:
                self.ultimo_esito_salvataggio = ESITO_SALVATAGGIO_AZZERATO
                gestore = self.gestore_azzeramento_completato
                if gestore is not None:
                    try:
                        gestore()
                    except Exception as errore_notifica:
                        print(
                            "⚠️ Configurazione azzerata, ma la GUI non è "
                            f"stata aggiornata completamente: {errore_notifica}"
                        )
                return False

            print(
                f"💾 Configurazione salvata in "
                f"{self.file_config}"
            )
            self.ultimo_esito_salvataggio = ESITO_SALVATAGGIO_SALVATO
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

            if fotografia_prima_azzeramento is not None:
                self.config_data = fotografia_prima_azzeramento

            self.ultimo_esito_salvataggio = ESITO_SALVATAGGIO_ERRORE
            return False

    @staticmethod
    def _valida_metadati_nuova_assegnazione(storico, **metadati):
        return valida_metadati_assegnazione(storico, **metadati)

    # Storico in modalità a coppie


    # Storico in modalità a terzetti



    # Storico in modalità Personalizzata

    def aggiungi_assegnazione_storico_personalizzata(
            self, nome_assegnazione, gruppi, collocazioni, schema_personalizzato,
            layout_visuale, *, file_origine: str, report_completo=None,
            genere_misto=False, statistiche_generali=None,
            metadati_casualita=None, nome_classe: str, generazione: str,
            data_creazione: str, progressivo: int, abbinamenti: str,
            salva_subito: bool = True, modificata_manualmente: bool = False):
        """Registra una disposizione Personalizzata senza approssimarne la geometria.

        Lo Storico conserva lo schema semantico, la fotografia visuale con gli
        eventuali vuoti e la collocazione ordinata gruppo→blocco. Le adiacenze
        vengono inoltre registrate nella blacklist Personalizzata indipendente.
        """
        from moduli.dominio.aula_personalizzata import (
            istantanea_visuale_a_json,
            schema_personalizzato_a_json,
        )

        self._valida_metadati_nuova_assegnazione(
            self.config_data["storico_assegnazioni"],
            nome_assegnazione=nome_assegnazione,
            nome_classe=nome_classe,
            file_origine=file_origine,
            generazione=generazione,
            modo="personalizzata",
            data_creazione=data_creazione,
            progressivo=progressivo,
            abbinamenti=abbinamenti,
        )

        layout_visuale.valida_contro_schema(schema_personalizzato)

        gruppi_salvati = [
            {
                "tipo": gruppo.tipo,
                "membri": [
                    studente.get_nome_completo() for studente in gruppo.membri
                ],
            }
            for gruppo in gruppi
        ]
        collocazioni_salvate = [
            {
                "blocco": collocazione.blocco.id,
                "gruppo": [
                    studente.get_nome_completo()
                    for studente in collocazione.gruppo.membri
                ],
                "posti": [posto.id for posto in collocazione.blocco.posti],
            }
            for collocazione in collocazioni
        ]

        nome_fisso = None
        for collocazione in collocazioni:
            for posto, studente in collocazione.occupazioni:
                if posto.ancora_fisso:
                    nome_fisso = studente.get_nome_completo()
                    break
            if nome_fisso is not None:
                break

        configurazione_precedente = (
            copy.deepcopy(self.config_data) if salva_subito else None
        )
        nuova_assegnazione = {
            "data_creazione": data_creazione,
            "nome": nome_assegnazione,
            "classe": nome_classe,
            "file_origine": file_origine,
            "generazione": generazione,
            "modo": "personalizzata",
            "progressivo": int(progressivo),
            "abbinamenti": abbinamenti,
            "gruppi": gruppi_salvati,
            "collocazioni": collocazioni_salvate,
            "schema_personalizzato": schema_personalizzato_a_json(
                schema_personalizzato
            ),
            "layout_visuale_personalizzato": istantanea_visuale_a_json(
                layout_visuale
            ),
            "studente_fisso": nome_fisso,
            "genere_misto": bool(genere_misto),
            "sessi_studenti": {
                s.get_nome_completo(): s.sesso
                for gruppo in gruppi for s in gruppo.membri
                if getattr(s, 'sesso', None) in ('M', 'F')
            },
        }
        if modificata_manualmente:
            nuova_assegnazione["modificata_manualmente"] = True
        if metadati_casualita:
            nuova_assegnazione["casualita"] = copy.deepcopy(metadati_casualita)
        if statistiche_generali:
            nuova_assegnazione["statistiche_generali"] = [
                dict(riga) for riga in statistiche_generali
            ]
        if report_completo:
            nuova_assegnazione["report_completo"] = report_completo

        # Valida anche quando il batch rinvia la scrittura su disco.
        self._valida_voce_storico_personalizzata(
            nuova_assegnazione, len(self.config_data["storico_assegnazioni"]))
        try:
            # Il validatore canonico deve poter leggere la voce prima della scrittura.
            self.config_data["storico_assegnazioni"].append(nuova_assegnazione)

            adiacenze = []
            for gruppo in gruppi_salvati:
                membri = gruppo["membri"]
                adiacenze.extend(zip(membri, membri[1:]))
            if adiacenze:
                aggiorna_blacklist_personalizzata(self, adiacenze)

            if salva_subito:
                if self.salva_configurazione():
                    return True
                if self.ultimo_esito_salvataggio != ESITO_SALVATAGGIO_AZZERATO:
                    self.config_data = configurazione_precedente
                return False
            return True

        except Exception:
            if configurazione_precedente is not None:
                self.config_data = configurazione_precedente
            raise

    # Metadati e ricostruzione dei layout






    # Ricostruzione del layout salvato

    def ricostruisci_layout_da_storico(self, indice_assegnazione):
        return ricostruisci_layout(self.config_data, indice_assegnazione)

    # Aggiornamento delle rotazioni in modalità a coppie

    def _aggiorna_coppie_da_evitare(self, nuove_coppie, trio=None,
                                    studente_fisso=None, gruppo_adiacente_fisso=None,
                                    nome_adiacente_fisso=None):
        return aggiorna_rotazioni_coppie(
            self.config_data, nuove_coppie, trio, studente_fisso,
            gruppo_adiacente_fisso, nome_adiacente_fisso,
        )

    # Ricostruzione delle blacklist dallo Storico

    def _ricostruisci_blacklist_da_storico(self):
        self.config_data.update(ricostruisci_rotazioni(
            self.config_data["storico_assegnazioni"],
        ))

    def _salva_modifica_storico(self, modifica):
        """Adotta una copia e ripristina la configurazione su un fallimento."""
        precedente = self.config_data
        nuova = modifica(precedente)
        self.config_data = nuova
        try:
            riuscito = self.salva_configurazione()
        except Exception:
            self.config_data = precedente
            raise
        if not riuscito and self.ultimo_esito_salvataggio != ESITO_SALVATAGGIO_AZZERATO:
            self.config_data = precedente
        return riuscito

    def rinomina_assegnazione(self, indice: int, nome: str) -> bool:
        return self._salva_modifica_storico(
            lambda dati: rinomina_assegnazione(dati, indice, nome),
        )

    def elimina_assegnazione(self, indice: int) -> bool:
        return self._salva_modifica_storico(
            lambda dati: elimina_assegnazione(dati, indice),
        )

    def imposta_tema(self, tema: str) -> bool:
        if tema not in {"scuro", "chiaro"}:
            raise ValueError("Tema non valido.")
        self.config_data["tema"] = tema
        return self.salva_configurazione()
