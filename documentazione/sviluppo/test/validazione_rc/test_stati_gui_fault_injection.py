from pathlib import Path

import pytest

from moduli.stato_annuale import FaseAnnuale, StatoAnnuale
from moduli.stato_mensile import FaseMensile, StatoMensile
from moduli.stato_sessione import puo_avviare_elaborazione, risultato_appartiene_sessione
from moduli.supervisione_processi import finalizza_processo
from strumenti.validazione_rc.stati_gui import campagna_stati_gui_fault_rc


RADICE = Path(__file__).resolve().parents[4]


def test_doppio_avvio_e_bloccato_da_qualunque_elaborazione_attiva():
    assert puo_avviare_elaborazione(
        worker_mensile_presente=False,
        worker_annuale_presente=False,
        annuale_in_corso=False,
    )
    for mensile, annuale, stato_annuale in (
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ):
        assert not puo_avviare_elaborazione(
            worker_mensile_presente=mensile,
            worker_annuale_presente=annuale,
            annuale_in_corso=stato_annuale,
        )



def test_risultato_tardivo_richiede_stessa_classe_studenti_e_aula_per_identita():
    studenti = []
    aula = object()
    base = dict(
        file_origine_corrente="2A.txt",
        studenti_correnti=studenti,
        aula_corrente=aula,
        file_origine_atteso="2A.txt",
        studenti_attesi=studenti,
        aula_attesa=aula,
    )
    assert risultato_appartiene_sessione(**base)

    cambiato = dict(base, file_origine_corrente="2B.txt")
    assert not risultato_appartiene_sessione(**cambiato)

    cambiato = dict(base, studenti_correnti=list(studenti))
    assert not risultato_appartiene_sessione(**cambiato)

    cambiato = dict(base, aula_corrente=object())
    assert not risultato_appartiene_sessione(**cambiato)

def test_eliminare_la_voce_corrente_non_lascia_salvata_senza_indice():
    stato = StatoMensile(
        fase=FaseMensile.SALVATA,
        modo="coppie",
        assegnatore=object(),
        nome="2A - Mensile Coppie - 01",
        progressivo=1,
        data_creazione="07/08/2026 03:00",
        file_origine="2A.txt",
        nome_classe="2A",
        genere_misto=False,
        indice_storico=2,
    )
    stato.aggiorna_indice_dopo_eliminazione(2)
    assert stato.fase == FaseMensile.DA_SALVARE
    assert stato.indice_storico is None



def test_mensile_non_puo_essere_marcato_salvato_due_volte():
    stato = StatoMensile()
    stato.prepara_coppie(
        object(),
        nome="2A - Mensile Coppie - 01",
        progressivo=1,
        data_creazione="07/08/2026 03:00",
        file_origine="2A.txt",
        nome_classe="2A",
        genere_misto=False,
    )
    stato.segna_salvata(0)
    with pytest.raises(RuntimeError, match="soltanto un risultato Mensile ancora da salvare"):
        stato.segna_salvata(1)
    assert stato.indice_storico == 0

def test_annuale_rifiuta_salvataggio_senza_anteprima():
    stato = StatoAnnuale()
    stato.avvia(3, ora=0)
    with pytest.raises(RuntimeError, match="Transizione Annuale non valida"):
        stato.segna_salvata()
    assert stato.fase == FaseAnnuale.ELABORAZIONE


def test_annuale_percorso_normale_elaborazione_anteprima_salvata():
    stato = StatoAnnuale()
    stato.avvia(3, ora=0)
    stato.apri_anteprima()
    stato.segna_salvata()
    assert stato.fase == FaseAnnuale.SALVATA



class _ProcessoFinto:
    def __init__(self, *, esce_al_join=False, ignora_terminate=False):
        self.pid = 4242
        self._vivo = True
        self.esce_al_join = esce_al_join
        self.ignora_terminate = ignora_terminate
        self.join_timeout = []
        self.terminate_chiamato = False
        self.kill_chiamato = False

    def is_alive(self):
        return self._vivo

    def join(self, timeout=None):
        self.join_timeout.append(timeout)
        if self.esce_al_join:
            self._vivo = False

    def terminate(self):
        self.terminate_chiamato = True
        if not self.ignora_terminate:
            self._vivo = False

    def kill(self):
        self.kill_chiamato = True
        self._vivo = False


def test_processo_appeso_dopo_terminale_viene_terminato_senza_join_infinito():
    processo = _ProcessoFinto()
    esito = finalizza_processo(
        processo,
        terminale_ricevuto=True,
        canale_inutilizzabile=False,
        tempo_grazia=0.01,
    )
    assert processo.terminate_chiamato
    assert not processo.kill_chiamato
    assert not esito.ancora_vivo
    assert all(timeout is not None for timeout in processo.join_timeout)


def test_processo_che_esce_nella_grazia_non_viene_terminato():
    processo = _ProcessoFinto(esce_al_join=True)
    esito = finalizza_processo(
        processo,
        terminale_ricevuto=True,
        canale_inutilizzabile=False,
        tempo_grazia=0.01,
    )
    assert not processo.terminate_chiamato
    assert not processo.kill_chiamato
    assert not esito.uscita_forzata


def test_canale_perso_termina_un_figlio_che_non_puo_piu_restituire_esito():
    processo = _ProcessoFinto()
    esito = finalizza_processo(
        processo,
        terminale_ricevuto=False,
        canale_inutilizzabile=True,
        tempo_grazia=0.01,
    )
    assert processo.terminate_chiamato
    assert not esito.ancora_vivo


def test_calcolo_ancora_legittimo_non_viene_ucciso_dal_finalizzatore():
    processo = _ProcessoFinto()
    esito = finalizza_processo(
        processo,
        terminale_ricevuto=False,
        canale_inutilizzabile=False,
        tempo_grazia=0.01,
    )
    assert not processo.terminate_chiamato
    assert esito.ancora_vivo


def test_kill_e_fallback_se_terminate_non_basta():
    processo = _ProcessoFinto(ignora_terminate=True)
    esito = finalizza_processo(
        processo,
        terminale_ricevuto=True,
        canale_inutilizzabile=False,
        tempo_grazia=0.01,
    )
    assert processo.terminate_chiamato
    assert processo.kill_chiamato
    assert esito.kill_usato
    assert not esito.ancora_vivo

def test_campagna_stati_gui_e_fault_injection_e_verde():
    rapporto = campagna_stati_gui_fault_rc(RADICE)
    assert rapporto.verde, [x for x in rapporto.dettaglio if not x.verde]
    assert rapporto.controlli >= 50
