"""Servidor visual portable para la defensa S18 de MediTriage.

Sirve la API real y el panel en el MISMO puerto (sin CORS):

    python demo_server.py                       -> http://127.0.0.1:8000/demo
    python demo_server.py --port 8080           -> http://127.0.0.1:8080/demo
    DEMO_HOST=0.0.0.0 DEMO_PORT=8000 python demo_server.py

Opciones:
    --host HOST     default 127.0.0.1 (o DEMO_HOST)
    --port PORT     default 8000 (o DEMO_PORT). Si está ocupado, busca el siguiente libre.
    --no-browser    no abre el navegador (o DEMO_NO_BROWSER=1)

El panel usa los mismos endpoints que demo_s18.py; no modifica main.py.
"""

from __future__ import annotations

import argparse
import os
import socket
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi.responses import HTMLResponse

import main as meditriage  # alias: evita que def main() shadowee el módulo main.py

app = meditriage.app
_PANEL = Path(__file__).with_name("demo_panel.html")


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_panel() -> HTMLResponse:
    return HTMLResponse(_PANEL.read_text(encoding="utf-8"))


@app.post("/demo/reset", include_in_schema=False)
def demo_reset() -> dict[str, object]:
    """Limpia el STORE en memoria para que cada demo empiece con 2 eventos de auditoría.

    Es un helper SOLO de la demo; no forma parte del contrato api/openapi.yaml.
    """
    for key in ("patients", "evaluations", "audit", "idempotency"):
        meditriage.STORE[key].clear()
    return {"ok": True, "message": "Datos de demo reiniciados"}


def _port_is_free(host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((probe_host, port))
            return True
        except OSError:
            return False


def _pick_port(host: str, preferred: int) -> int:
    for candidate in range(preferred, preferred + 21):
        if _port_is_free(host, candidate):
            return candidate
    raise SystemExit(
        f"No hay puertos libres entre {preferred} y {preferred + 20}. "
        "Cierra otros programas o indica otro con --port."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Panel demo de MediTriage")
    parser.add_argument("--host", default=os.getenv("DEMO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DEMO_PORT", "8000")))
    parser.add_argument(
        "--no-browser",
        action="store_true",
        default=os.getenv("DEMO_NO_BROWSER", "0") == "1",
    )
    args = parser.parse_args()

    port = _pick_port(args.host, args.port)
    shown_host = "localhost" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{shown_host}:{port}/demo"

    print("\n  MediTriage - Demo S18", flush=True)
    print(f"  Panel : {url}", flush=True)
    print(f"  API   : http://{shown_host}:{port}/docs", flush=True)
    if port != args.port:
        print(f"  Aviso : el puerto {args.port} estaba ocupado; se usa {port}.", flush=True)
    print("  Detener: Ctrl+C en esta terminal\n", flush=True)

    if not args.no_browser:

        def _open() -> None:
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
