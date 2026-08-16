# Corpus di regressione R0.8 — congelato

## Composizione

Il corpus ordinario di regressione contiene **8 classi senza FISSO + 2 varianti con FISSO = 10 file**.

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

## Copertura

Il sottoinsieme conserva: numerosità 14–28; classi pari e dispari; tutti i resti modulo 3; profili di genere equilibrati e sbilanciati; 0–3 studenti `PRIMA`; presenza di `ULTIMA`; incompatibilità L3 assenti, sparse, dense ed estremamente dense; hub L3; affinità da assenti a molto dense; un caso dominato dalle affinità; una classe grande e difficile; due semantiche FISSO differenti.

Questo corpus serve alla **regressione ordinaria futura**. Non sostituisce il corpus completo di 38 file usato per la certificazione RC R0.8, che resta "congelato" come *artefatto esterno* separato dal presente repository.
