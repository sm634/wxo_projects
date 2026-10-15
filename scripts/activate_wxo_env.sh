#!/usr/bin/env bash
# Activates the watsonx Orchestrate environment "wxo_unipart_env" using the ADK,
# authenticating with the API key stored in the project's .env file.
#
# Reads WXO_API_KEY from .env.

set -euo pipefail

ENV_NAME="wxo_unipart_env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if ! command -v orchestrate >/dev/null 2>&1; then
  echo "Error: 'orchestrate' CLI not found. Install it with: pip install --upgrade ibm-watsonx-orchestrate" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: .env file not found at ${ENV_FILE}" >&2
  exit 1
fi

# Read WXO_API_KEY from .env without sourcing the file.
WXO_API_KEY="$(grep -E '^WXO_API_KEY=' "${ENV_FILE}" | head -n 1 | cut -d '=' -f 2- | tr -d '"'"'"'\r')"

if [[ -z "${WXO_API_KEY}" ]]; then
  echo "Error: WXO_API_KEY is not set in ${ENV_FILE}" >&2
  exit 1
fi

if ! orchestrate env list 2>/dev/null | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "Error: environment '${ENV_NAME}' does not exist. Run scripts/create_wxo_env.sh first." >&2
  exit 1
fi

echo "Activating environment '${ENV_NAME}'..."
orchestrate env activate "${ENV_NAME}" --api-key "${WXO_API_KEY}"
echo "Environment '${ENV_NAME}' is now active."
