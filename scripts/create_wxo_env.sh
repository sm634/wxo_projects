#!/usr/bin/env bash
# Creates the watsonx Orchestrate environment "wxo_unipart_env" using the ADK.
# If the environment already exists, the script reports it and exits.
#
# Reads WXO_URL from the project's .env file.

set -euo pipefail

ENV_NAME="wxo_unipart_env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if ! command -v orchestrate >/dev/null 2>&1; then
  echo "Error: 'orchestrate' CLI not found. Install it with: pip install --upgrade ibm-watsonx-orchestrate" >&2
  exit 1
fi

# Exit early if the environment already exists (first column of 'orchestrate env list').
if orchestrate env list 2>/dev/null | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "Environment '${ENV_NAME}' already exists."
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Error: .env file not found at ${ENV_FILE}" >&2
  exit 1
fi

# Read WXO_URL from .env without sourcing the file.
WXO_URL="$(grep -E '^WXO_URL=' "${ENV_FILE}" | head -n 1 | cut -d '=' -f 2- | tr -d '"'"'"'\r')"

if [[ -z "${WXO_URL}" ]]; then
  echo "Error: WXO_URL is not set in ${ENV_FILE}" >&2
  exit 1
fi

echo "Creating environment '${ENV_NAME}'..."
orchestrate env add -n "${ENV_NAME}" -u "${WXO_URL}" --type ibm_iam
echo "Environment '${ENV_NAME}' created. Run scripts/activate_wxo_env.sh to activate it."
