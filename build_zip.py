#!/usr/bin/env python3
"""Baut ein Krita-importierbares ZIP dieses Plugins.

Ergebnis: dist/krita-ai-api-diffusion.zip

Layout im Archiv (genau was Krita "Import Python Plugin from File" erwartet):
    ai_api_diffusion.desktop
    ai_api_diffusion/__init__.py
    ai_api_diffusion/ai_api_diffusion_docker.py
    ai_api_diffusion/README.md
    ai_api_diffusion/LICENSE          (falls vorhanden)

Aufruf (mit System-Python oder Kritas Python):
    python build_zip.py
"""
import os
import zipfile

MODULE = "ai_api_diffusion"           # Ordner-/Modulname == X-KDE-Library
OUT = os.path.join("dist", "krita-ai-api-diffusion.zip")

# Dateien, die als Modulinhalt ins ZIP wandern (unter ai_api_diffusion/)
INCLUDE = ["__init__.py", "ai_api_diffusion_docker.py", "README.md", "LICENSE"]
DESKTOP = "ai_api_diffusion.desktop"  # kommt an die Wurzel des Archivs


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "dist"), exist_ok=True)
    out_path = os.path.join(here, OUT)

    if not os.path.exists(os.path.join(here, DESKTOP)):
        raise SystemExit("Fehlt: %s" % DESKTOP)

    added = []
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # .desktop an die Wurzel
        z.write(os.path.join(here, DESKTOP), DESKTOP)
        added.append(DESKTOP)
        # Modulinhalt
        for name in INCLUDE:
            src = os.path.join(here, name)
            if os.path.exists(src):
                arc = "%s/%s" % (MODULE, name)
                z.write(src, arc)
                added.append(arc)

    print("Erstellt: %s" % out_path)
    for a in added:
        print("  + %s" % a)
    print("\nInstallation in Krita: Werkzeuge -> Skripte -> "
          "'Python-Plugin aus Datei importieren' -> dieses ZIP wählen, "
          "dann im Python Plugin Manager aktivieren und Krita neu starten.")


if __name__ == "__main__":
    main()
