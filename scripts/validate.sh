#!/usr/bin/env bash
# Validate the schemas offline with the same processing the Infrahub server runs.
# INFRAHUB_VERSION should match the Infrahub instance you load into.
set -euo pipefail
cd "$(dirname "$0")/.."
INFRAHUB_VERSION="${INFRAHUB_VERSION:-1.12.2}"

[ -d vendor/schema-library ] || scripts/fetch_upstream.sh
if [ ! -x .venv/bin/python ]; then
  uv venv -q -p 3.12 .venv
  uv pip install -q --python .venv/bin/python "infrahub-server==${INFRAHUB_VERSION}"
fi

.venv/bin/python tools/validate_schema.py \
  vendor/schema-library/base \
  schemas/security \
  schemas/paloalto
