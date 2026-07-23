# 📻 HoerspielTag

**HoerspielTag** ist ein modulares, KI-gestütztes Tool zur automatischen Analyse, Bereinigung, Tagging und Umbenennung von Hörspiel-Dateien (MP3). Es bereitet unordentliche Ordnerstrukturen und Dateinamen optimal auf, damit Mediensysteme wie **Plex** sie perfekt indexieren können.

Das Tool bietet sowohl eine intuitive **grafische Benutzeroberfläche (GUI)** auf Basis von *CustomTkinter* (inklusive Live-Vorschau und Editierung vor dem Speichern) als auch einen **CLI-Modus** für automatisierte Skripte.

---

## ✨ Features

- **Ordner- & Dateianalyse:** Scannt rekursiv Zielverzeichnisse nach MP3-Dateien und extrahiert Dateipfade, Namen und bereits vorhandene ID3-Metadaten als Kontext.
- **KI-Metadatenabgleich (LLM):** Sendet den analysierten Kontext an eine OpenAI-kompatible API (z. B. lokales **LM Studio** oder **ESAB Nexus / LibreChat**). Die KI analysiert den Text und gibt ein sauberes JSON-Objekt mit Seriennamen, Folge, Titel, Jahr, Genre und bereinigten Kapitelnamen zurück.
- **Interaktiver Review-Prozess (GUI):** Bevor Änderungen auf die Festplatte geschrieben werden, kannst du in der GUI alle vorgeschlagenen Werte (Serientitel, Episodennummer, Track-Titel etc.) manuell bearbeiten.
- **Automatischer Cover-Downloader:** Sucht bei fehlendem Cover-Art automatisch über die iTunes-Search-API nach passenden Bildern in hoher Auflösung, zeigt diese zur Bestätigung an, speichert sie als `cover.jpg` und bettet sie direkt in die MP3s ein.
- **Lossless MP3 Merge (Optional):** Ermöglicht es, die einzelnen Tracks eines Hörspiels mithilfe von `ffmpeg` verlustfrei (`-c copy` ohne Qualitätsverlust) zu einer einzigen Datei zusammenzufügen (standardmäßig ab 10 Tracks).
- **Clean Tagging (ID3v2.3):** Schreibt Metadaten sauber in ID3v2.3-Tags und entfernt veraltete ID3v1-Tags vollständig, um Kompatibilitätsprobleme zu vermeiden.
- **Automatische Strukturierung:** Benennt die Dateien sauber um (z. B. `01 - Titel.mp3`) und benennt auch den Hauptordner des Hörspiels sauber um (z. B. `Serienname - Albumname`).
- **Sicherer Dry-Run-Modus:** Simuliert alle Operationen ohne tatsächliche Dateizugriffe (in der GUI standardmäßig aktiviert).

---

## 🛠️ Installation & Setup

### 1. System-Voraussetzungen
- Python 3.10+
- **FFmpeg** (nur benötigt, falls das Feature "Verlustfreies Zusammenfügen" genutzt werden soll. Stelle sicher, dass `ffmpeg` im System-PATH verfügbar ist).

### 2. Python-Bibliotheken installieren
Installiere alle Abhängigkeiten über die `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 3. Konfiguration (`.env`)
Erstelle eine `.env`-Datei im Projektordner (eine Vorlage findest du in `.env.example`).
Hier stellst du deine LLM-Schnittstelle ein:

```ini
# Option A: Lokales LM Studio (Standard)
LLM_API_BASE_URL=http://127.0.0.1:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL_ID=meta-llama-3-8b-instruct

# Option B: ESAB Nexus / LibreChat API
# LLM_API_BASE_URL=https://nexus.ebxai.esab.com/api/agents/v1
# LLM_API_KEY=sk-your-nexus-key
# LLM_MODEL_ID=agent_nIygK72ZaL9reO730sKaE

# Schwellenwert für das Zusammenfügen von MP3s
MERGE_THRESHOLD=10
```

---

## 🚀 Verwendung

### Start über Batch-Datei (Windows)
Doppelklicke einfach auf die **`run.bat`** im Hauptverzeichnis. Das Skript überprüft automatisch deine Python-Installation und fehlende Bibliotheken im Hintergrund und startet direkt die GUI.

### Manuell über das Terminal (GUI)
```powershell
python main.py
```

### Verwendung im CLI-Modus
Für automatisierte Abläufe kannst du das Tool direkt über Parameter steuern:
```powershell
python main.py "D:\Pfad\zu\deinen\Hoerspielen" [Optionen]
```

**Verfügbare Argumente:**
- `directory`: Das Zielverzeichnis, das verarbeitet werden soll.
- `--dry-run`: Zeigt alle geplanten Änderungen an, ohne Dateien zu schreiben oder umzubenennen.
- `--merge`: Aktiviert das Zusammenfügen der MP3-Dateien eines Hörspiels zu einer einzigen Datei, wenn die Anzahl der Tracks den Schwellenwert (z.B. 10) erreicht.
- `--cli`: Erzwingt den CLI-Modus (auch wenn kein Pfad übergeben wurde, z. B. um Fehler zu werfen).

---

## 📂 Datei- und Modul-Architektur

- **`main.py`**: Einstiegspunkt. Erkennt, ob Parameter übergeben wurden, und leitet entweder an die CLI-Pipeline oder an die GUI weiter.
- **`gui.py`**: CustomTkinter-Benutzeroberfläche. Steuert den gesamten Interaktions- und Review-Prozess.
- **`audio_scanner.py`**: Sucht nach MP3-Dateien und bereitet den aktuellen Metadaten-Zustand für das LLM auf.
- **`llm_client.py`**: Kommuniziert mit der konfigurierten API und validiert das Antwort-JSON per *Pydantic*.
- **`cover_downloader.py`**: Frägt die iTunes Search API ab und lädt hochauflösende Cover herunter.
- **`tag_writer.py`**: Führt die Schreiboperationen mit *Mutagen* durch (Schreibt ID3v2.3, löscht ID3v1, bettet Bilder ein).
- **`file_merger.py`**: Kommuniziert mit der lokalen `ffmpeg`-Installation, um Dateien verlustfrei zu verbinden.
- **`config.py`**: Baut Verbindungsobjekte und integriert spezielle Header/Body-Payloads für LibreChat/Nexus-Agenten.
