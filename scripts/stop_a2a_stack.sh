#!/usr/bin/env bash
# Stops the local A2A server started by scripts/start_a2a_stack.sh.

set -uo pipefail

PID_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.run/server.pid"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}")"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" && echo "Stopped A2A server (pid ${pid})"
  fi
  rm -f "${PID_FILE}"
else
  echo "No A2A server pid file; nothing to stop."
fi
