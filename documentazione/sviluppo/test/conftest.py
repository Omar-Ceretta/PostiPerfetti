from __future__ import annotations

import sys
from pathlib import Path

# Test e strumenti sono archiviati sotto documentazione/, mentre il runtime
# resta nella root. Rendiamo entrambi importabili senza lasciare configurazioni
# di sviluppo nella radice pubblica del progetto.
RADICE = Path(__file__).resolve().parents[3]
for percorso in (RADICE / "documentazione" / "sviluppo", RADICE):
    testo = str(percorso)
    if testo not in sys.path:
        sys.path.insert(0, testo)
