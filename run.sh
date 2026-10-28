#!/usr/bin/env bash
# Starts the web app on THIS computer only (127.0.0.1). Run from the project root:
# ./run.sh
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python

[ -x "$PY" ] || { echo "Missing .venv. Do the Setup steps in README.md first."; exit 1; }
grep -q '^GROQ_API_KEY=.' .env 2>/dev/null || { echo "No GROQ_API_KEY in .env. Copy .env.example to .env and add your key."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker is not running. Open Docker Desktop and wait until it has started."; exit 1; }
IMAGE=$("$PY" -c "from app import config; print(config.SANDBOX_IMAGE)")
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "Sandbox image '$IMAGE' is missing. Run: docker build -t $IMAGE sandbox/"; exit 1; }

echo "Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop."
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
