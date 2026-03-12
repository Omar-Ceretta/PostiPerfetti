"""
Modulo per la gestione degli studenti e caricamento dati.
Contiene la classe Student e le funzioni per caricare i dati dal file txt.
"""

class Student:
    """
    Classe che rappresenta un singolo studente con tutti i suoi vincoli.
    """

    def __init__(self, cognome, nome, sesso, nota_posizione="NORMALE"):
        # Dati base dello studente
        self.cognome = cognome.strip()
        self.nome = nome.strip()
        self.sesso = sesso.strip().upper()  # M o F
        self.nota_posizione = nota_posizione.strip().upper()  # PRIMA, ULTIMA, NORMALE

        # Dizionari per gestire vincoli sociali
        # Chiave: cognome studente, Valore: livello (1-5)
        self.incompatibilita = {}  # Chi NON deve stare vicino
        self.affinita = {}         # Chi DOVREBBE stare vicino

    def aggiungi_incompatibilita(self, cognome_studente, livello):
        """
        Aggiunge un'incompatibilità con un altro studente.
        Args:
            cognome_studente (str): Cognome dello studente incompatibile
            livello (int): Livello di incompatibilità (1-5, dove 5 è massimo)
        """
        self.incompatibilita[cognome_studente.strip()] = int(livello)

    def aggiungi_affinita(self, cognome_studente, livello):
        """
        Aggiunge un'affinità con un altro studente.
        Args:
            cognome_studente (str): Cognome dello studente affine
            livello (int): Livello di affinità (1-5, dove 5 è massimo)
        """
        self.affinita[cognome_studente.strip()] = int(livello)

    def get_nome_completo(self):
        """Restituisce nome e cognome formattati."""
        return f"{self.cognome} {self.nome}"

    def __str__(self):
        """Rappresentazione stringa per debug."""
        return f"{self.get_nome_completo()} ({self.sesso}) - Pos: {self.nota_posizione}"

def _risolvi_riferimento_completo(riferimento: str, tutti_studenti: list) -> Student:
    """
    Risolve riferimenti usando sempre Nome Cognome completo.
    VERSIONE MIGLIORATA: Gestisce cognomi composti e nomi composti.

    Args:
        riferimento: "Cognome Nome" (sempre completo)
        tutti_studenti: Lista di tuple (studente, incomp_str, aff_str)

    Returns:
        Student corrispondente o None se non trovato
    """
    if ' ' not in riferimento:
        print(f"ERRORE: Riferimento '{riferimento}' deve essere nel formato 'Cognome Nome'")
        return None

    # NUOVO: Gestisce meglio i cognomi composti
    # Prova diverse combinazioni di split per cognomi composti

    # Lista di tutte le possibili interpretazioni del riferimento
    possibili_interpretazioni = []

    # Metodo 1: Split normale (es: "Rossi Mario" -> cognome="Rossi", nome="Mario")
    parti = riferimento.split(' ', 1)
    if len(parti) == 2:
        possibili_interpretazioni.append((parti[0].strip(), parti[1].strip()))

    # Metodo 2: Per cognomi composti con 2 parole (es: "De Rossi Gian Marco")
    parti_complete = riferimento.split(' ')
    if len(parti_complete) >= 3:
        # Prova "De Rossi" + "Gian Marco"
        cognome_composto = ' '.join(parti_complete[:2])
        nome_composto = ' '.join(parti_complete[2:])
        possibili_interpretazioni.append((cognome_composto.strip(), nome_composto.strip()))

        # Prova anche "De" + "Rossi Gian Marco" (meno probabile, ma per completezza)
        cognome_semplice = parti_complete[0]
        nome_esteso = ' '.join(parti_complete[1:])
        possibili_interpretazioni.append((cognome_semplice.strip(), nome_esteso.strip()))

    # Metodo 3: Per cognomi composti con 3 parole (es: "Van Der Berg Maria Elena")
    if len(parti_complete) >= 4:
        # Prova "Van Der Berg" + "Maria Elena"
        cognome_lungo = ' '.join(parti_complete[:3])
        nome_finale = ' '.join(parti_complete[3:])
        possibili_interpretazioni.append((cognome_lungo.strip(), nome_finale.strip()))

    print(f"    🔍 Cerco '{riferimento}' con {len(possibili_interpretazioni)} interpretazioni:")

    # Prova tutte le interpretazioni possibili
    for idx, (cognome_target, nome_target) in enumerate(possibili_interpretazioni, 1):
        print(f"      Tentativo {idx}: cognome='{cognome_target}' + nome='{nome_target}'")

        # Cerca corrispondenza esatta
        for studente, _, _ in tutti_studenti:
            if studente.cognome == cognome_target and studente.nome == nome_target:
                print(f"      ✅ TROVATO: {studente.cognome} {studente.nome}")
                return studente

    # Se non trova nessuna corrispondenza esatta, prova ricerca parziale
    print(f"    🔍 Nessuna corrispondenza esatta, provo ricerca parziale...")

    # Estrae la prima parola come possibile cognome per debug
    prima_parola = riferimento.split()[0]
    print(f"    📋 Studenti disponibili con cognome che inizia per '{prima_parola}':")

    studenti_simili = []
    for studente, _, _ in tutti_studenti:
        if studente.cognome.startswith(prima_parola):
            studenti_simili.append(studente)
            print(f"      - {studente.cognome} {studente.nome}")

    # Se c'è un solo studente con cognome simile, suggerisce
    if len(studenti_simili) == 1:
        print(f"    💡 SUGGERIMENTO: Forse intendevi '{studenti_simili[0].cognome} {studenti_simili[0].nome}'?")
        # Per ora non assumiamo automaticamente, ma potremmo farlo in futuro

    print(f"    ❌ ERRORE: Studente '{riferimento}' non trovato con nessuna interpretazione")
    return None

def carica_studenti_da_file(percorso_file):
    """
    Carica la lista degli studenti dal file di testo.

    Args:
        percorso_file (str): Percorso al file .txt con i dati degli studenti

    Returns:
        list: Lista di oggetti Student

    Raises:
        FileNotFoundError: Se il file non esiste
        ValueError: Se ci sono errori nel formato dei dati
    """
    studenti = []
    studenti_temporanei = []

    # Contatori per il debug
    righe_totali = 0
    righe_vuote_o_commenti = 0
    righe_con_errori = 0
    righe_processate_ok = 0

    print("🔍 DEBUG CARICAMENTO FILE")
    print("=" * 40)

    try:
        with open(percorso_file, 'r', encoding='utf-8') as file:
            for numero_riga, riga in enumerate(file, 1):
                righe_totali += 1
                riga_originale = riga  # Salva la riga originale per debug

                # Salta righe vuote e commenti
                riga = riga.strip()
                if not riga or riga.startswith('#'):
                    righe_vuote_o_commenti += 1
                    print(f"  Riga {numero_riga:2d}: SALTATA (vuota/commento)")
                    continue

                try:
                    # Debug: mostra cosa stiamo processando
                    print(f"  Riga {numero_riga:2d}: ELABORO -> '{riga[:50]}{'...' if len(riga) > 50 else ''}'")

                    # Parsing della riga: Cognome;Nome;Sesso;NotePosizione;Incompatibilità;Affinità
                    parti = riga.split(';')
                    print(f"             Parti trovate: {len(parti)} -> {[p.strip()[:20] for p in parti]}")

                    if len(parti) != 6:
                        raise ValueError(f"Formato errato: attese 6 colonne, trovate {len(parti)}")

                    cognome, nome, sesso, nota_pos, incomp_str, aff_str = parti

                    # Debug: mostra i dati estratti
                    print(f"             Cognome: '{cognome.strip()}'")
                    print(f"             Nome: '{nome.strip()}'")
                    print(f"             Sesso: '{sesso.strip()}'")
                    print(f"             Posizione: '{nota_pos.strip()}'")

                    # Crea l'oggetto studente
                    studente = Student(cognome, nome, sesso, nota_pos)
                    print(f"             ✅ STUDENTE CREATO: {studente.get_nome_completo()}")

                    # Salva temporaneamente i dati per processarli dopo
                    studenti_temporanei.append((studente, incomp_str, aff_str))
                    righe_processate_ok += 1

                except Exception as e:
                    righe_con_errori += 1
                    print(f"             ❌ ERRORE: {e}")
                    print(f"             Riga originale: '{riga_originale.strip()}'")
                    continue

        print("\n📊 STATISTICHE CARICAMENTO PRIMA PASSATA:")
        print(f"  • Righe totali lette: {righe_totali}")
        print(f"  • Righe vuote/commenti: {righe_vuote_o_commenti}")
        print(f"  • Righe con errori: {righe_con_errori}")
        print(f"  • Righe processate OK: {righe_processate_ok}")
        print(f"  • Studenti temporanei: {len(studenti_temporanei)}")

        # SECONDA PASSATA: risolvi vincoli con nomi completi
        print("\n🔗 SECONDA PASSATA: Risoluzione vincoli...")

        vincoli_incomp_risolti = 0
        vincoli_aff_risolti = 0
        errori_vincoli = 0

        for idx, (studente, incomp_str, aff_str) in enumerate(studenti_temporanei, 1):
            print(f"\n  Studente {idx}: {studente.get_nome_completo()}")

            # Parsing incompatibilità con risoluzione nomi
            if incomp_str.strip():
                print(f"    Incompatibilità raw: '{incomp_str.strip()}'")
                for coppia in incomp_str.split(','):
                    if ':' in coppia:
                        riferimento, livello = coppia.split(':')
                        riferimento = riferimento.strip()
                        print(f"      Cerco: '{riferimento}' (livello {livello})")

                        studente_target = _risolvi_riferimento_completo(riferimento, studenti_temporanei)
                        if studente_target:
                            studente.aggiungi_incompatibilita(studente_target.cognome, int(livello))
                            vincoli_incomp_risolti += 1
                            print(f"        ✅ Risolto -> {studente_target.get_nome_completo()}")
                        else:
                            errori_vincoli += 1
                            print(f"        ❌ NON TROVATO!")

            # Parsing affinità con risoluzione nomi
            if aff_str.strip():
                print(f"    Affinità raw: '{aff_str.strip()}'")
                for coppia in aff_str.split(','):
                    if ':' in coppia:
                        riferimento, livello = coppia.split(':')
                        riferimento = riferimento.strip()
                        print(f"      Cerco: '{riferimento}' (livello {livello})")

                        studente_target = _risolvi_riferimento_completo(riferimento, studenti_temporanei)
                        if studente_target:
                            studente.aggiungi_affinita(studente_target.cognome, int(livello))
                            vincoli_aff_risolti += 1
                            print(f"        ✅ Risolto -> {studente_target.get_nome_completo()}")
                        else:
                            errori_vincoli += 1
                            print(f"        ❌ NON TROVATO!")

            studenti.append(studente)

        print(f"\n📊 STATISTICHE VINCOLI:")
        print(f"  • Incompatibilità risolte: {vincoli_incomp_risolti}")
        print(f"  • Affinità risolte: {vincoli_aff_risolti}")
        print(f"  • Errori vincoli: {errori_vincoli}")

    except FileNotFoundError:
        print(f"❌ ERRORE: File {percorso_file} non trovato!")
        return []

    print(f"\n🎯 RISULTATO FINALE:")
    print(f"  • Studenti caricati: {len(studenti)}")
    print("=" * 40)

    return studenti

