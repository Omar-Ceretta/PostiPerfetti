# -*- coding: utf-8 -*-
"""U4: ingresso immutabile e verifica degli esiti del Layout unico.

La fotografia conserva valori, senza riferimenti agli studenti vivi. Non
modifica motori, preflight, bozze o formati dello Storico. ULTIMA resta una
misura soft nel verificatore HARD esistente.

Parte di «PostiPerfetti». Autore: prof. Omar Ceretta. Licenza: GNU GPLv3.
"""

from dataclasses import dataclass

from moduli.dominio.disposizione_effettiva import da_risultato_personalizzata
from moduli.dominio.layout_unico import (
    LayoutUnico, congela_layout_unico, identita_layout_unico,
    verifica_geometria_output,
)
from moduli.calcolo.matcher_blocchi import CollocazioneGruppoBlocco
from moduli.dominio.metrica_pulizia import Gruppo
from moduli.dominio.studenti import Student
from moduli.dominio.validazione_blocchi import valida_soluzione_blocchi


@dataclass(frozen=True, slots=True)
class StudenteFotografato:
    cognome: str
    nome: str
    sesso: str
    nota_posizione: str
    incompatibilita: tuple
    affinita: tuple

    @classmethod
    def da_studente(cls, studente):
        # Leggere i campi, non la cache del nome: rileva anche mutazioni dirette.
        return cls(studente.cognome, studente.nome, studente.sesso,
                   studente.nota_posizione,
                   tuple(sorted(studente.incompatibilita.items())),
                   tuple(sorted(studente.affinita.items())))

    def crea_studente(self):
        studente = Student(self.cognome, self.nome, self.sesso, self.nota_posizione)
        studente.incompatibilita = dict(self.incompatibilita)
        studente.affinita = dict(self.affinita)
        return studente


def fotografa_studenti(studenti):
    return tuple(sorted((StudenteFotografato.da_studente(s) for s in studenti),
                        key=lambda s: (s.cognome, s.nome)))


@dataclass(frozen=True, slots=True)
class FotografiaGenerazioneLayout:
    layout: LayoutUnico
    studenti: tuple[StudenteFotografato, ...]
    file_origine: str
    nome_classe: str
    genere_misto: bool

    @classmethod
    def cattura(cls, modello, studenti, *, file_origine, nome_classe,
                genere_misto, griglia):
        righe = fotografa_studenti(studenti)
        layout = congela_layout_unico(
            modello, numero_studenti=len(righe),
            numero_fissi=sum(s.nota_posizione == "FISSO" for s in righe),
            griglia=griglia,
        )
        return cls(layout, righe, file_origine, nome_classe, bool(genere_misto))

    def crea_studenti(self):
        """Ogni consumatore riceve una copia privata del dominio mutabile."""
        return [s.crea_studente() for s in self.studenti]

    def identita(self):
        return (self.file_origine, self.nome_classe, self.studenti,
                identita_layout_unico(self.layout), self.genere_misto)

    def verifica_risultato(self, risultato):
        """Controlla geometria, copertura e HARD prima di qualsiasi anteprima."""
        schema = self.layout.schema
        if risultato.get("schema_identita") != schema.identita_semantica():
            raise ValueError("Lo schema restituito differisce dalla fotografia iniziale.")
        gruppi = tuple(risultato.get("gruppi") or ())
        collocazioni = tuple(risultato.get("collocazioni") or ())
        if not gruppi or len(collocazioni) != len(gruppi):
            raise ValueError("Gruppi o collocazioni fisiche incompleti.")
        studenti = self.crea_studenti()
        per_nome = {s.get_nome_completo(): s for s in studenti}
        dati_attesi = {s.get_nome_completo(): StudenteFotografato.da_studente(s)
                       for s in studenti}

        def gruppo_canonico(gruppo):
            if gruppo.tipo != {2: "coppia", 3: "terzetto"}.get(len(gruppo.membri)):
                raise ValueError("Il tipo di gruppo non coincide con la sua capienza.")
            membri = []
            for studente in gruppo.membri:
                dati = StudenteFotografato.da_studente(studente)
                nome = f"{dati.cognome} {dati.nome}"
                if (dati_attesi.get(nome) != dati
                        or studente.get_nome_completo() != nome):
                    raise ValueError("Studente estraneo o vincoli alterati nell'output.")
                membri.append(per_nome[nome])
            return Gruppo(gruppo.tipo, tuple(membri))

        gruppi_canonici = tuple(gruppo_canonico(g) for g in gruppi)
        collocazioni_canoniche = tuple(
            CollocazioneGruppoBlocco(gruppo_canonico(c.gruppo), c.blocco)
            for c in collocazioni
        )
        # L'adattatore confronta ciascun blocco restituito con lo schema
        # congelato prima di costruire la disposizione: non corregge l'output.
        output = da_risultato_personalizzata(
            schema, collocazioni, istantanea_visuale=self.layout.istantanea_visuale,
            genere_misto=self.genere_misto,
        )
        geometria = verifica_geometria_output(self.layout, output)
        if not geometria.valido:
            raise ValueError("\n".join(p.messaggio for p in geometria.problemi))
        esito = valida_soluzione_blocchi(
            studenti, gruppi_canonici, schema, collocazioni_canoniche,
        )
        if not esito.valida:
            raise ValueError("Violazioni HARD: " + ", ".join(esito.errori_duri))
        return output
