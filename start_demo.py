"""Lanzador portable de la demo de MediTriage (Windows / macOS / Linux).

 Qué hace:
   1. Verifica Python 3.10+.
   2. Crea .venv-demo/ si no existe (NO toca el .venv del proyecto).
   3. Instala requirements.txt la primera vez. Si existe carpeta wheels/,
      instala SIN internet desde ahí.
   4. Lanza demo_server.py con los mismos argumentos.

 Uso:
    python start_demo.py
    python start_demo.py --port 8080
    python start_demo.py --download-wheels   # preparar PC sin internet
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv-demo"
WHEELS = ROOT / "wheels"
REQUIREMENTS = ROOT / "requirements.txt"
MIN_VERSION = (3, 10)


def _fail(message: str) -> NoReturn:
    print(f"\nERROR: {message}\n", file=sys.stderr)
    raise SystemExit(1)


def _venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _download_wheels() -> int:
    WHEELS.mkdir(exist_ok=True)
    if not REQUIREMENTS.exists():
        _fail(f"No se encontró {REQUIREMENTS}")
    print(f"Descargando dependencias en {WHEELS} ...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "download", "-r", str(REQUIREMENTS), "-d", str(WHEELS)]
    )
    print("\nListo. Copia TODA esta carpeta (incluida wheels/) a la otra PC.")
    print("En la otra PC, el lanzador instalará sin internet.")
    return 0


def _ensure_env() -> Path:
    python = _venv_python()

    if not python.exists():
        print("Creando entorno virtual .venv-demo/ (solo la primera vez) ...")
        try:
            venv.create(VENV_DIR, with_pip=True)
        except Exception as exc:  # ensurepip ausente en algunas distros
            _fail(
                "No se pudo crear el entorno virtual. "
                "En Ubuntu/Debian instala: sudo apt install python3-venv\n"
                f"Detalle: {exc}"
            )
        if not python.exists():
            _fail(f"No se creó {python}")

    probe = subprocess.run(
        [str(python), "-c", "import fastapi, uvicorn, pydantic"],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return python

    if not REQUIREMENTS.exists():
        _fail(f"No se encontró {REQUIREMENTS}")

    cmd = [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)]
    if WHEELS.is_dir() and any(WHEELS.iterdir()):
        cmd += ["--no-index", "--find-links", str(WHEELS)]
        print("Instalando dependencias desde wheels/ (sin internet) ...")
    else:
        print("Instalando dependencias (primera vez; requiere internet) ...")

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        _fail(
            "No se pudieron instalar las dependencias. Revisa tu conexión o ejecuta "
            "python start_demo.py --download-wheels en una PC con internet."
        )
    return python


def main() -> int:
    if sys.version_info < MIN_VERSION:
        _fail(
            f"Se necesita Python {MIN_VERSION[0]}.{MIN_VERSION[1]}+ y tienes "
            f"{sys.version_info.major}.{sys.version_info.minor}. "
            "Descárgalo de https://www.python.org/downloads/"
        )

    if "--download-wheels" in sys.argv[1:]:
        return _download_wheels()

    required = ["main.py", "demo_server.py", "demo_panel.html", "requirements.txt"]
    missing = [name for name in required if not (ROOT / name).exists()]
    if missing:
        _fail("Faltan archivos en esta carpeta: " + ", ".join(missing))

    python = _ensure_env()
    print("Iniciando demo ...", flush=True)
    child_env = os.environ.copy()
    child_env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.call(
        [str(python), str(ROOT / "demo_server.py"), *sys.argv[1:]],
        cwd=str(ROOT),
        env=child_env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
