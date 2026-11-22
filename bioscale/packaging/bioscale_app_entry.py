# Einstiegspunkt fuer PyInstaller (absoluter Import, damit das Paket gebuendelt wird)
import multiprocessing
import os
import sys

if getattr(sys, "frozen", False):
    # macOS-Build: PROJ-Datenbank von Homebrew (siehe build_app.py) fuer pyproj und rasterio
    _brew = os.path.join(getattr(sys, "_MEIPASS", ""), "proj_data_brew")
    if os.path.isdir(_brew):
        os.environ["PROJ_DATA"] = _brew
        os.environ["PROJ_LIB"] = _brew

from bioscale.app import main  # noqa: E402

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
