#!/usr/bin/env python3
"""serve_nocache.py -- statischer HTTP-Server OHNE Caching.

`python -m http.server` laesst den Browser HTML/JS aggressiv cachen, sodass
Aenderungen an den Viewern nicht sichtbar werden. Dieser Server schickt bei
jeder Antwort No-Cache-Header -> jedes Neuladen holt die aktuelle Datei.

Nutzung:  python scripts/serve_nocache.py [port]   (Default 8360, Wurzel = CWD)
"""
import sys, http.server, socketserver

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8360

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

with Server(("127.0.0.1", PORT), Handler) as httpd:
    print(f"No-Cache-Server laeuft auf http://localhost:{PORT}  (Wurzel = Projektordner)")
    httpd.serve_forever()
