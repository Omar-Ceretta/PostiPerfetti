# Officina di sviluppo e validazione

Questa cartella contiene materiale tecnico destinato allo sviluppo e al collaudo di «PostiPerfetti», non all'utente finale.

- **`strumenti/`** — programmi e infrastrutture usati per eseguire verifiche, campagne, confronti e gate di validazione.
- **`test/`** — test automatici `pytest` che verificano il programma e gli stessi strumenti di collaudo.
- **`strumenti_diagnostica/`** — utilità diagnostiche specifiche.
- **`dati_validazione/`** — corpus ridotto di regressione ed esempi necessari ai controlli.

Le sottodirectory `cantiere_semantico` e `validazione_rc` compaiono sia in `strumenti/` sia in `test/`:

```text
strumenti/cantiere_semantico/   = implementazione degli strumenti
test/cantiere_semantico/        = test di quegli strumenti e dei relativi contratti

strumenti/validazione_rc/       = infrastruttura di validazione della Release Candidate
test/validazione_rc/            = test dell'infrastruttura e dei contratti Release Candidate
```

Non sono strumenti duplicati: la separazione fra codice di collaudo e test del codice di collaudo evita che le due responsabilità vengano confuse.
