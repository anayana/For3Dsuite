"""Doppelklick-Start: Web-Assistent lokal starten und Browser oeffnen (fuer die Standalone-App).

Arbeitsordner: ~/BioScale (Projekte, Ergebnisse). Beenden: Fenster/Terminal schliessen.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _free_port(preferred=8765):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Kein freier Port")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] not in ("--no-browser",):
        # Standalone-Programm kann auch die Kommandozeile: BioScale run projekt.yml
        from .cli import main as cli
        return cli(argv)
    import uvicorn

    from .web.app import create_app
    work = Path(os.environ.get("BIOSCALE_HOME", Path.home() / "BioScale"))
    work.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"BioScale laeuft: {url}\nArbeitsordner: {work}\nZum Beenden dieses Fenster schliessen (oder Strg+C).")
    if "--no-browser" not in argv:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    uvicorn.run(create_app(work / "web"), host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
