#!/usr/bin/env bash
set -euo pipefail

# Initialize pass store with an existing GPG key and show aws-vault usage.
# Run this locally after install-pass-gpg.sh and after you have created/imported a GPG key.

for cmd in gpg pass; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd not found. Run scripts/install-pass-gpg.sh or install manually." >&2
    exit 1
  fi
done

# Show secret keys
echo "Available secret GPG keys:"
gpg --list-secret-keys --keyid-format LONG

echo
read -p "Enter the GPG key ID or full fingerprint to use for pass init (e.g. ABCDEF1234567890): " GPG_KEY
if [ -z "$GPG_KEY" ]; then
  echo "No key entered, aborting." >&2
  exit 1
fi

echo "Initializing pass with GPG key: $GPG_KEY"
pass init "$GPG_KEY"

echo "\npass initialized. Add AWS credentials using the pass backend via aws-vault. Examples:"
echo "  export AWS_VAULT_BACKEND=pass"
echo "  ./scripts/aws-vault.sh add chater-deploy   # follow prompts to enter Access Key/Secret"
echo "\nTo run CDK deploy using aws-vault (pass backend):"
echo "  export AWS_VAULT_BACKEND=pass"
echo "  ./scripts/aws-vault.sh exec chater-deploy -- npx cdk deploy --all --require-approval never"
