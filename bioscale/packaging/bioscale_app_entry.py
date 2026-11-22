# Einstiegspunkt fuer PyInstaller (absoluter Import, damit das Paket gebuendelt wird)
import multiprocessing
import sys

from bioscale.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
