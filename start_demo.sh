#!/usr/bin/env bash
# Lanzador portable de MediTriage para macOS / Linux.
# Uso: chmod +x start_demo.sh && ./start_demo.sh
set -euo pipefail
cd "$(dirname "$0")"

for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    exec "$candidate" start_demo.py "$@"
  fi
done

echo "ERROR: no se encontró Python 3.10+. Instálalo y vuelve a intentar." >&2
exit 1
