"""Baut die Standalone-App (Ordner mit ausfuehrbarer Datei, ohne Python-Installation beim Nutzer).

    pip install -e ".[all]" pyinstaller
    python packaging/build_app.py
Ergebnis: dist/BioScale/BioScale(.exe). Ordner zippen und weitergeben.
Die App laeuft nur auf dem Betriebssystem, auf dem sie gebaut wurde (Windows-App auf Windows bauen usw.;
siehe .github/workflows/bioscale-app.yml fuer alle drei Systeme).
"""
import sys
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

args = [
    str(HERE / "bioscale_app_entry.py"),
    "--name", "BioScale",
    "--noconfirm", "--clean",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
    # Paketdaten (Profile, HTML) und Geodaten (PROJ/GDAL) mitnehmen
    "--collect-data", "bioscale",
    "--collect-all", "rasterio",
    "--collect-all", "pyproj",
    "--collect-all", "pyogrio",
    "--collect-submodules", "bioscale",
    "--collect-submodules", "sklearn",
    "--collect-submodules", "uvicorn",
    "--collect-data", "elapid",
    "--hidden-import", "lightgbm",
    "--exclude-module", "tkinter",
    "--exclude-module", "IPython",
    "--console",  # Fenster zeigt Adresse und Fortschritt; Schliessen beendet BioScale
]
if sys.platform == "darwin":
    args += ["--osx-bundle-identifier", "org.for3dsuite.bioscale"]
    # pyproj ist auf macOS gegen Homebrew-PROJ gebaut: dessen Datenbank (proj.db) mitnehmen
    import subprocess
    try:
        prefix = subprocess.run(["brew", "--prefix", "proj"], capture_output=True, text=True).stdout.strip()
        if prefix and Path(prefix, "share", "proj").exists():
            args += ["--add-data", f"{prefix}/share/proj:proj_data_brew"]
    except FileNotFoundError:
        pass
PyInstaller.__main__.run(args)
