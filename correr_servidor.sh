#!/usr/bin/env bash
# Arranca el servidor de Angels Online desde Git Bash / MINGW64.
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
PY="/c/laragon/bin/python/python-3.10/python"
[ -x "$PY" ] || PY="$(command -v python || command -v py)"
echo "usando: $PY"
exec "$PY" server/app.py -v "$@"
