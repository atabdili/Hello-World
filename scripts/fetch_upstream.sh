#!/usr/bin/env bash
# Fetch the upstream sources this schema builds on, pinned to known-good commits.
#   vendor/schema-library  - OpsMill schema-library (base schema we extend)
#   vendor/pan-os-codegen  - Palo Alto PAN-OS data-model specs (bootstrap input)
# Bump the SHAs deliberately, re-run tools/validate_schema.py and the bootstrap
# diff, then commit.
set -euo pipefail
cd "$(dirname "$0")/.."

SCHEMA_LIBRARY_SHA=0b83c8b49c07073c22c969082b052ab315727fe6
PANOS_CODEGEN_SHA=ee44e33cf576db65645123c4dc6eff6407e040ac

fetch() { # url dir sha
  if [ ! -d "$2/.git" ]; then git init -q "$2" && git -C "$2" remote add origin "$1"; fi
  git -C "$2" fetch -q --depth 1 origin "$3"
  git -C "$2" checkout -q --detach FETCH_HEAD
  echo "$2 @ $(git -C "$2" rev-parse --short HEAD)"
}

mkdir -p vendor
fetch https://github.com/opsmill/schema-library.git        vendor/schema-library "$SCHEMA_LIBRARY_SHA"
fetch https://github.com/PaloAltoNetworks/pan-os-codegen.git vendor/pan-os-codegen "$PANOS_CODEGEN_SHA"
