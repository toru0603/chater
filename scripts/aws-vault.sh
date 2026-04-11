#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT_DIR/tools/bin/aws-vault"
if [ ! -x "$BIN" ]; then
  echo "aws-vault binary not found or not executable at $BIN" >&2
  echo "Run scripts/install-aws-vault.sh to download it." >&2
  exit 1
fi
exec "$BIN" "$@"
