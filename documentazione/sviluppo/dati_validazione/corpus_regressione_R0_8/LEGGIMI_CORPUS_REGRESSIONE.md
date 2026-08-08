# Corpus di regressione R0.8 — congelato

## Composizione

Il corpus ordinario di regressione contiene **8 classi senza FISSO + 2 varianti con FISSO = 10 file**.
La selezione è stata effettuata prima di conoscere quali classi avrebbero richiesto anonimizzazione o rinomina.

### Classi senza FISSO

- `Piccola(14).txt`
- `Affinita-dominante(16).txt`
- `Squilibrata-murata(16).txt`
- `Terzetti-regolare(18).txt`
- `Ipervincolata(19).txt`
- `Elastica(22).txt`
- `Affollata-vincolata(23).txt`
- `Affollata-difficile(28).txt`

### Varianti con FISSO

- `Ipervincolata(19+fisso).txt`
- `Affollata-difficile(28+fisso).txt`

## Rinomine applicate dopo la selezione

- `Classe3A(16)` → `Squilibrata-murata(16)`: forte squilibrio M/F e nucleo denso di incompatibilità assolute.
- `Classe2D(18)` → `Terzetti-regolare(18)`: numerosità esattamente divisibile per 3 e profilo di vincoli relativamente regolare.
- `Classe-Autori(19)` → `Ipervincolata(19)`: densità molto elevata di incompatibilità e affinità; stessa denominazione per la variante `+fisso`.

Gli studenti di `Squilibrata-murata(16)` e `Terzetti-regolare(18)` sono stati anonimizzati con identificatori tecnici (`CasoMxx Test` / `CasoFxx Test`). La trasformazione è biiettiva: genere, posizione, livelli e grafo di incompatibilità/affinità restano invariati.

## Copertura

Il sottoinsieme conserva: numerosità 14–28; classi pari e dispari; tutti i resti modulo 3; profili di genere equilibrati e sbilanciati; 0–3 studenti `PRIMA`; presenza di `ULTIMA`; incompatibilità L3 assenti, sparse, dense ed estremamente dense; hub L3; affinità da assenti a molto dense; un caso dominato dalle affinità; una classe grande e difficile; due semantiche FISSO differenti.

Questo corpus serve alla **regressione ordinaria futura**. Non sostituisce il corpus completo di 38 file usato per la certificazione RC R0.8, che resta congelato come artefatto esterno separato.
