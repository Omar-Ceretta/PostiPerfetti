# 🧾️ Componenti di terze parti in «PostiPerfetti»

«PostiPerfetti» è distribuito sotto licenza **GNU GPL versione 3**.

Il programma usa alcune librerie, un carattere tipografico e una raccolta di icone realizzati da terzi. Questo documento elenca tali componenti e indica dove trovarne il testo di licenza completo.

> **A chi serve questo documento.**
> A chi ridistribuisce «PostiPerfetti», a chi lo modifica, a chi voglia verificare le attribuzioni.

---

## 1. Librerie di programmazione

| Componente | Versione | Licenza | Ruolo nel programma |
|---|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython/) (Qt for Python) | 6.11.1 | **LGPL-3.0-only** *oppure* GPL-2.0-only *oppure* GPL-3.0-only | Costruisce l'intera interfaccia grafica: finestre, tabelle, dialoghi, disegno dell'aula. |
| [XlsxWriter](https://xlsxwriter.readthedocs.io/) | 3.2.9 | **BSD 2-Clause** | Genera i file `.xlsx` esportati dalle tab "Aula" e "Storico". |

Le versioni sono quelle congelate in `requirements.txt`, per rendere riproducibile la Release.

### Come vengono distribuite

Il modo in cui queste librerie arrivano sul computer dell'utente cambia a seconda del sistema operativo:

- **Linux** — il pacchetto di Release *non* contiene le librerie. L'installer prepara un ambiente virtuale Python e le scarica da PyPI sul momento. È quindi l'utente stesso a ottenerle dalla fonte ufficiale, nella versione dichiarata.
- **Windows** — l'eseguibile prodotto con PyInstaller **incorpora** Python, le librerie Qt e XlsxWriter in un unico pacchetto. Sono quindi ridistribuite insieme al programma.

### Nota sulla combinazione con Qt

PySide6/Qt è offerto dai suoi autori con una scelta fra più licenze. Dal momento che «PostiPerfetti» è già GPLv3, la combinazione è compatibile per entrambe le strade possibili (LGPLv3 oppure GPLv3).

Restano gli obblighi ordinari di chi ridistribuisce software libero: conservare le note di copyright, indicare quali componenti sono inclusi e sotto quale licenza e mettere a disposizione il codice sorgente corrispondente.

> Il codice sorgente di «PostiPerfetti» è pubblicamente disponibile su 
> <https://github.com/Omar-Ceretta/PostiPerfetti>.
> Il codice sorgente di Qt e PySide6 è pubblicamente disponibile presso The Qt Company e il Qt Project (<https://download.qt.io/>), nelle stesse versioni qui dichiarate.

---

## 2. Carattere tipografico

| Componente | Licenza | Testo completo | Ruolo |
|---|---|---|---|
| **Noto Color Emoji** — Copyright 2021 Google Inc. | **SIL Open Font License 1.1** | `risorse/font/LICENSE` | Rende visibili le emoji dei report generati in modo uniforme su Windows e Linux. |

Il carattere è incluso in tutti i pacchetti di distribuzione, insieme al proprio file di licenza.

---

## 3. Icone

| Componente | Licenza | Testo completo | Ruolo |
|---|---|---|---|
| **Lucide Icons** — Copyright (c) 2026 Lucide Icons and Contributors | **ISC License** | `risorse/icone/lucide/LICENSE` | Le icone dell'interfaccia, in variante chiara e scura. |

Anche queste sono incluse in tutti i pacchetti, insieme al proprio file di licenza.

Lucide deriva da Feather Icons (Copyright (c) 2013-2022 Cole Bemis), a sua volta sotto licenza MIT: il testo in `risorse/icone/lucide/LICENSE` copre entrambe le attribuzioni.

---

## 4. Strumenti usati solo per lo sviluppo

Questi **non** vengono distribuiti con il programma, ma vengono elencati per completezza:

| Componente | Versione | Licenza | Ruolo |
|---|---|---|---|
| [pytest](https://pytest.org/) | 9.1.1 | MIT | Esegue la suite di collaudo. |
| [Ruff](https://docs.astral.sh/ruff/) | 0.16.2 | MIT | Analisi statica del codice. |
| [PyInstaller](https://pyinstaller.org/) | vedi `packaging/windows/requirements-build-windows.txt` | GPLv2+ con eccezione per i file generati | Costruisce l'eseguibile Windows. |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | — | Licenza Inno Setup (gratuita, permette la distribuzione degli installer prodotti) | Costruisce l'installer Windows. |

L'eccezione alla licenza di PyInstaller è ciò che consente di distribuire l'eseguibile prodotto sotto la licenza GPLv3.

---

*«PostiPerfetti» — prof. Omar Ceretta — GNU GPLv3*
