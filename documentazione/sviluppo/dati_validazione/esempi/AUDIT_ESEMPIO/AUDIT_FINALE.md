# Audit finale dell’osservatore semantico

- **contratto:** `R0.1`
- **audit valido:** sì
- **pronto per la raccolta reale:** sì
- **controlli superati:** 25/25
- **errori:** 0
- **avvisi:** 0

## Controlli

| Esito | Codice | Controllo |
|---|---|---|
| OK | `RACCOLTA_STRUTTURALE` | La raccolta supera la validazione I9/I10 |
| OK | `MANIFESTO` | Il manifesto SHA-256 copre tutti i file |
| OK | `OUTPUT_O1_O2_O5_O7` | Protocollo, indice, CSV, validazione e manifesto sono presenti |
| OK | `PROTOCOLLO_R0_1` | Protocollo C1 leggibile e versionato |
| OK | `MATRICE_COMPLETA` | Tutti i run espliciti sono completi |
|  |  | run completi=2/2 |
| OK | `OUTPUT_RUN_run_3ad01c2d9201d0b9ff0684c1` | Il run completo contiene JSON, Markdown e validazione |
| OK | `ANNATA_VALIDA` | ANNATA.json supera la validazione autonoma |
| OK | `EVENTI_COMPLETI` | Gli eventi conservano identità, ruolo, livelli e cronologia |
| OK | `STUDENTI_COMPLETI` | Il riepilogo per studente espone distribuzione dei riusi e FISSO |
| OK | `LIVELLI_SEPARATI` | Incompatibilità e affinità restano separate per livello |
| OK | `GENERE_MISTO` | Flag, massimi esatti e risultato ottenuto sono presenti |
| OK | `TRACCIA_RIORDINO` | Ordine di generazione e ordine finale sono entrambi conservati |
| OK | `NESSUN_GIUDIZIO_OPACO` | Non sono introdotti voti o indici pedagogici automatici |
| OK | `RENDER_run_3ad01c2d9201d0b9ff0684c1` | ANNATA.md deriva esattamente dal JSON canonico |
| OK | `OUTPUT_RUN_run_e00a90482bd6d6815690a9b1` | Il run completo contiene JSON, Markdown e validazione |
| OK | `ANNATA_VALIDA` | ANNATA.json supera la validazione autonoma |
| OK | `EVENTI_COMPLETI` | Gli eventi conservano identità, ruolo, livelli e cronologia |
| OK | `STUDENTI_COMPLETI` | Il riepilogo per studente espone distribuzione dei riusi e FISSO |
| OK | `LIVELLI_SEPARATI` | Incompatibilità e affinità restano separate per livello |
| OK | `GENERE_MISTO` | Flag, massimi esatti e risultato ottenuto sono presenti |
| OK | `TRACCIA_RIORDINO` | Ordine di generazione e ordine finale sono entrambi conservati |
| OK | `FISSO` | Cronologia e ruolo del vicino del FISSO sono osservabili |
| OK | `NESSUN_GIUDIZIO_OPACO` | Non sono introdotti voti o indici pedagogici automatici |
| OK | `RENDER_run_e00a90482bd6d6815690a9b1` | ANNATA.md deriva esattamente dal JSON canonico |
| OK | `OUTPUT_O6` | I confronti appaiati hanno JSON, Markdown e validazione |
|  |  | confronti prodotti=1 |
|  |  | attesi=1 |
