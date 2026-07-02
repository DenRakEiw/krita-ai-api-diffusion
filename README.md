# Krita AI API Diffusion

Ein Krita-Plugin, das die **FLUX**-Modelle von [Black Forest Labs (BFL)](https://bfl.ai)
direkt in Krita nutzbar macht – für Text-zu-Bild, kontextbasiertes Inpainting und
maskenbasiertes Inpainting, inklusive optionalem Referenzbild.

## Funktionen

- **Neues Bild (Text → Bild)** – Bildgenerierung aus einem Prompt (FLUX.2).
- **Kontext-Inpaint (FLUX.2)** – bearbeitet die aktuelle Auswahl kontextbasiert
  über `input_image` (keine Maske nötig). Ideal für Anweisungen wie
  „entferne die Person" oder „ersetze den Himmel".
- **Masken-Inpaint (FLUX.1 Fill)** – präzises Füllen exakt innerhalb der Auswahl
  über `image` + `mask` (`flux-pro-1.0-fill`).
- **Referenzbild (optional)** – ein zusätzliches Bild als Vorlage, z. B. eine
  bestimmte Sonnenbrille, die eine ausgewählte Katze tragen soll. Wird beim
  Kontext-Inpaint als `input_image_2` und beim Generieren als `input_image`
  mitgeschickt.
- Adaptiver Zuschnitt mit Kontext-Rand, gefederte Maskenkanten (keine sichtbaren
  Nähte), korrekte Farbbehandlung und lesbare Fehlermeldungen.

## Voraussetzungen

- **Krita 5.x** (mit Python/PyQt5 – in den offiziellen Builds enthalten).
- Ein **BFL API-Key** von <https://api.bfl.ai> (bzw. dem BFL-Dashboard).
- Guthaben auf dem BFL-Konto (die FLUX-Modelle sind kostenpflichtig).

## Installation

### Variante A – manuell (empfohlen)

1. Repository herunterladen oder klonen:
   ```bash
   git clone https://github.com/DenRakEiw/krita-ai-api-diffusion.git
   ```
2. Den Ordner `ai_api_diffusion` **und** die Datei `ai_api_diffusion.desktop`
   in das Krita-`pykrita`-Verzeichnis kopieren:

   | Betriebssystem | Pfad |
   |----------------|------|
   | Windows | `%APPDATA%\krita\pykrita\` |
   | Linux   | `~/.local/share/krita/pykrita/` |
   | macOS   | `~/Library/Application Support/krita/pykrita/` |

   Danach sieht es so aus:
   ```
   pykrita/
   ├── ai_api_diffusion.desktop
   └── ai_api_diffusion/
       ├── __init__.py
       └── ai_api_diffusion_docker.py
   ```

   > Falls die `.desktop`-Datei fehlt, mit diesem Inhalt anlegen:
   > ```ini
   > [Desktop Entry]
   > Type=Service
   > ServiceTypes=Krita/PythonPlugin
   > X-KDE-Library=ai_api_diffusion
   > X-Python-2-Compatible=false
   > Name=Krita AI API Diffusion
   > Comment=Plugin für Flux (BFL)
   > ```

3. **Krita starten.**
4. Menü **Einstellungen → Krita konfigurieren → Python Plugin Manager**
   öffnen, den Haken bei **Krita AI API Diffusion** setzen und Krita neu starten.
5. Das Andockfenster über **Einstellungen → Andockbare Dialoge →
   Krita AI API Diffusion** einblenden.

### Variante B – direkt ins pykrita-Verzeichnis klonen

```bash
cd <pykrita-Verzeichnis>
git clone https://github.com/DenRakEiw/krita-ai-api-diffusion.git ai_api_diffusion
```
Anschließend die `.desktop`-Datei wie oben eine Ebene höher (nach `pykrita/`)
kopieren und wie in Schritt 3–5 fortfahren.

## Einrichtung

1. Im Andockfenster auf den Tab **Optionen** wechseln.
2. Den **API Key (BFL)** eintragen und auf **Speichern** klicken.
   (Der Key wird in den Krita-Einstellungen gespeichert.)

## Benutzung

### Neues Bild
1. Tab **Generieren**, Modell wählen (z. B. `flux-2-pro`).
2. Prompt eingeben, optional Breite/Höhe unter **Optionen**.
3. **Neues Bild (Text → Bild)** klicken – das Ergebnis kommt als neue Ebene.

### Kontext-Inpaint (FLUX.2)
1. Mit einem Auswahlwerkzeug den zu ändernden Bereich auswählen.
2. Als Prompt eine Edit-Anweisung schreiben, z. B. „remove the object".
3. **Kontext-Inpaint (FLUX.2)** klicken.
4. Nur der Auswahlbereich wird ersetzt (weich eingeblendet).

### Masken-Inpaint (FLUX.1 Fill)
1. Bereich auswählen (mind. ~256 px – kleine Auswahlen werden hochskaliert).
2. Optional Prompt eingeben.
3. **Masken-Inpaint (FLUX.1 Fill)** klicken – präzises Füllen innerhalb der Maske.

### Mit Referenzbild (Beispiel: Sonnenbrille auf Katze)
1. Kopf-/Augenbereich der Katze auswählen.
2. **Referenzbild wählen …** und das Bild der Sonnenbrille laden.
3. Modell `flux-2-pro` oder `flux-2-max` wählen (unterstützen Multi-Image).
4. Prompt: *„the cat is wearing these sunglasses"*.
5. **Kontext-Inpaint (FLUX.2)** klicken.

## Modelle

| Auswahl | Endpoint | Einsatz |
|---------|----------|---------|
| `flux-2-pro` | `flux-2-pro` | Standard, gute Qualität, Multi-Image |
| `flux-2-max` | `flux-2-max` | Höchste Qualität, Multi-Image |
| `flux-2-flex` | `flux-2-flex` | Stark bei Typografie/Text |
| `flux-2-klein-9b` | `flux-2-klein-9b` | Schnell, leichter (kein Referenzbild) |
| Masken-Inpaint | `flux-pro-1.0-fill` | Maskenbasiertes Füllen |

## Tipps & Fehlerbehebung

- **HTTP 422 „Image dimensions must be at least 256x256"** – Auswahl zu klein.
  Wird automatisch hochskaliert; für scharfe Ergebnisse trotzdem größer auswählen.
- **HTTP 402 / „insufficient credits"** – kein Guthaben auf dem BFL-Konto.
- **HTTP 401 / 403** – API-Key falsch oder nicht gesetzt (Tab Optionen).
- **Zu große Payload / Timeout** bei Referenzbildern – `MAX_EDGE` in
  `ai_api_diffusion_docker.py` senken oder das Referenzbild vorher verkleinern.
- Fehlermeldungen erscheinen im Statusfeld unten und als Dialog (gekürzt).

## Hinweise

- Ergebnis-URLs von BFL sind nur kurz gültig; das Plugin lädt die Bilder sofort.
- Das Referenzbild wird nur bei FLUX.2 (Kontext-Inpaint/Generieren) verwendet,
  **nicht** bei FLUX.1 Fill.

## Lizenz

Nutzung auf eigene Verantwortung. Für die FLUX-Modelle gelten die
Nutzungsbedingungen und Preise von Black Forest Labs.
