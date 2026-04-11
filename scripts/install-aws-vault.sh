#!/usr/bin/env bash
set -euo pipefail

# Installer: download aws-vault into tools/bin
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT_DIR/tools/bin"
mkdir -p "$OUT_DIR"

OS="$(uname | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH_TAG="amd64" ;; 
  aarch64|arm64) ARCH_TAG="arm64" ;;
  *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

case "$OS" in
  linux) OS_TAG="linux" ;; 
  darwin) OS_TAG="darwin" ;;
  mingw*|msys*|cygwin*|windows) OS_TAG="windows" ;;
  *) echo "Unsupported OS: $OS" >&2; exit 1 ;;
esac

ASSET_NAME="aws-vault-${OS_TAG}-${ARCH_TAG}"
if [ "$OS_TAG" = "windows" ]; then ASSET_NAME+='.exe'; fi
URL="https://github.com/99designs/aws-vault/releases/latest/download/${ASSET_NAME}"
OUT_PATH="$OUT_DIR/aws-vault"
if [ "$OS_TAG" = "windows" ]; then OUT_PATH+='.exe'; fi

echo "Downloading $URL -> $OUT_PATH"
curl -sSL -o "$OUT_PATH" "$URL"
chmod +x "$OUT_PATH"

cat <<EOF
Installed aws-vault to: $OUT_PATH
Add it to your PATH, or run it as:
  $OUT_PATH --version
Example usage:
  $OUT_PATH add chater-deploy
  $OUT_PATH exec chater-deploy -- npx cdk deploy --all --require-approval never
EOF
