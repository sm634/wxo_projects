#!/usr/bin/env bash
# Starts the client_insights_agent A2A server locally with uvicorn.
#
# The Agent Card is served at http://localhost:PORT/.well-known/agent-card.json and its
# `url` field defaults to http://localhost:PORT (override with A2A_PUBLIC_URL, e.g. when
# the caller reaches this host under another name such as host.docker.internal).
#
# State is written to .run/ (pid, log). Stop with scripts/stop_a2a_stack.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT}/.run"
PORT="${A2A_PORT:-10000}"
PYTHON="${ROOT}/.venv/bin/python"

mkdir -p "${RUN_DIR}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Error: ${PYTHON} not found. Create the venv first (see README)." >&2; exit 1
fi
if [[ -f "${RUN_DIR}/server.pid" ]] && kill -0 "$(cat "${RUN_DIR}/server.pid")" 2>/dev/null; then
  echo "A2A server already running (pid $(cat "${RUN_DIR}/server.pid")). Run scripts/stop_a2a_stack.sh first." >&2
  exit 1
fi

export A2A_PUBLIC_URL="${A2A_PUBLIC_URL:-http://localhost:${PORT}}"

cd "${ROOT}/agents/client_insights_agent"
nohup "${PYTHON}" -m uvicorn server:app --host 0.0.0.0 --port "${PORT}" \
  > "${RUN_DIR}/server.log" 2>&1 &
echo $! > "${RUN_DIR}/server.pid"

echo "Waiting for A2A server..."
for _ in $(seq 1 30); do
  if curl -fs "http://localhost:${PORT}/.well-known/agent-card.json" 2>/dev/null | grep -q client_insights_agent; then
    echo "OK: http://localhost:${PORT}/.well-known/agent-card.json (card url: ${A2A_PUBLIC_URL})"
    echo "Log: ${RUN_DIR}/server.log"
    exit 0
  fi
  sleep 1
done
echo "Error: server did not become ready. See ${RUN_DIR}/server.log" >&2
exit 1
