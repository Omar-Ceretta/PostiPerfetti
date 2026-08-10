# Validazione RC su corpus esterno

Questa cartella contiene collaudi approfonditi utilizzati durante la
validazione delle Release Candidate di «PostiPerfetti».

Alcuni collaudi richiedono il corpus completo di classi impiegato durante
lo sviluppo. Tale corpus non è distribuito nel repository.

Per questo motivo i relativi file sono denominati `collaudo_*.py` anziché
`test_*.py`: non fanno parte della normale suite pytest pubblica e non
vengono raccolti automaticamente.

Quando il corpus esterno è disponibile, il suo percorso deve essere
indicato tramite la variabile d'ambiente:

    POSTIPERFETTI_CORPUS_RC

I collaudi possono quindi essere eseguiti esplicitamente con pytest.
