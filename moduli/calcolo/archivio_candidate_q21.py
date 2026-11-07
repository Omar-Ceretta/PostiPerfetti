# -*- coding: utf-8 -*-
# Parte di «PostiPerfetti». Licenza: GNU GPLv3.
"""Archivio effimero di annuali fisiche: selezione S1 senza rigenerazione.

L'archivio vive solo nel processo di calcolo e viene eliminato alla chiusura.
Il formato pickle e' riservato a dati creati *dal processo stesso*: MAI aprire
file utente o archivi esterni attraverso questa classe.
"""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from zlib import compress, decompress


class ArchivioCandidateQ21:
    def __init__(self, *, limite_byte=512 * 1024 * 1024):
        if type(limite_byte) is not int or limite_byte < 1024:
            raise ValueError('Limite archivio non valido.')
        self._tmp = TemporaryDirectory(prefix='pp-q21-finaliste-')
        self._radice = Path(self._tmp.name)
        self._indice = {}
        self.limite_byte = limite_byte
        self.byte_totali = 0
        self.byte_massimi = 0
        self.n_salvate = 0
        self.n_ricaricate = 0
        self._chiuso = False

    def __enter__(self):
        if self._chiuso:
            raise RuntimeError('Archivio chiuso.')
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self._chiuso:
            self._chiuso = True
            self._tmp.cleanup()

    def _controlla(self, indice):
        if self._chiuso:
            raise RuntimeError('Archivio gia\' chiuso.')
        if type(indice) is not int or indice < 1:
            raise ValueError('Indice della candidata non valido.')

    def conserva(self, indice, mesi, chiavi):
        self._controlla(indice)
        if indice in self._indice:
            raise ValueError('Candidata duplicata.')
        # Snapshot reale, non una ricetta che riesegue il generatore.
        payload = compress(pickle.dumps((tuple(mesi), tuple(chiavi)), protocol=pickle.HIGHEST_PROTOCOL), 1)
        if self.byte_totali + len(payload) > self.limite_byte:
            raise MemoryError('Archivio candidate S1 oltre il limite: arresto sicuro.')
        digest = hashlib.sha256(payload).digest()
        path = self._radice / f'{indice:08d}.bin'
        with path.open('xb') as f:
            f.write(payload)
        self._indice[indice] = (path, digest, len(payload))
        self.byte_totali += len(payload)
        self.byte_massimi = max(self.byte_massimi, self.byte_totali)
        self.n_salvate += 1

    def carica(self, indice):
        self._controlla(indice)
        try:
            path, digest, lunghezza = self._indice[indice]
        except KeyError as exc:
            raise ValueError('Candidata S1 non registrata: nessun replay.') from exc
        dati = path.read_bytes()
        if len(dati) != lunghezza or hashlib.sha256(dati).digest() != digest:
            raise ValueError('Snapshot fisico S1 alterato: nessun replay.')
        mesi, chiavi = pickle.loads(decompress(dati))
        self.n_ricaricate += 1
        return mesi, chiavi

    @property
    def quantita(self):
        return len(self._indice)
