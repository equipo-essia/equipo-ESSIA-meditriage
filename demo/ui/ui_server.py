"""Sirve la interfaz y reenvia /api/* a la API (evita CORS). Solo libreria estandar.
Uso:  python ui_server.py            (API en http://127.0.0.1:8080 por defecto)
      $env:API_URL="http://127.0.0.1:8000"; python ui_server.py
Luego abre http://127.0.0.1:9000"""

import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = os.environ.get("API_URL", "http://127.0.0.1:8080").rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
PASS = ("Authorization", "Content-Type", "Idempotency-Key")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self):
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(n) if n else None
        req = urllib.request.Request(API + self.path[4:], data=data, method=self.command)
        for k in PASS:
            if self.headers.get(k):
                req.add_header(k, self.headers[k])
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                self._send(r.status, r.read(), r.headers.get("Content-Type", "application/json"))
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read(), e.headers.get("Content-Type", "application/json"))
        except Exception as e:
            self._send(
                502,
                ('{"title":"API no disponible","detail":"%s"}' % str(e).replace('"', "'")).encode(),
            )

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy()
        with open(os.path.join(HERE, "index.html"), "rb") as f:
            self._send(200, f.read(), "text/html; charset=utf-8")

    do_POST = do_PATCH = _proxy

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"MediTriage UI -> http://127.0.0.1:9000   (API: {API})")
    ThreadingHTTPServer(("127.0.0.1", 9000), H).serve_forever()
