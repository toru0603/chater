#!/usr/bin/env bash
set -euo pipefail

# Installer for WSL/Debian-based systems: gnupg, pass, pinentry
# Run locally (this script uses sudo). It will not generate a GPG key for you.

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer targets Debian/Ubuntu (WSL). For other OS install gnupg and pass manually." >&2
  exit 1
fi

echo "Installing gnupg, pass, pinentry-curses (requires sudo)"
sudo apt-get update --quiet && sudo apt-get install -y gnupg2 pass pinentry-curses

# Configure pinentry for gpg-agent (use curses pinentry in WSL)
mkdir -p "$HOME/.gnupg"
GPG_AGENT_CONF="$HOME/.gnupg/gpg-agent.conf"
if ! grep -q '^pinentry-program' "$GPG_AGENT_CONF" 2>/dev/null; then
  echo 'pinentry-program /usr/bin/pinentry-curses' >> "$GPG_AGENT_CONF"
  echo "Configured pinentry-program in $GPG_AGENT_CONF"
  # Restart gpg-agent
  gpgconf --kill gpg-agent || true
fi

# Check for a secret key
if ! gpg --list-secret-keys --keyid-format LONG | grep -q '^sec'; then
  cat <<'MSG'
No GPG secret key found.

Create one interactively with:
  gpg --full-generate-key

Choose RSA (default), 4096 bits, and a passphrase you control. After creation, re-run this script or run:
  ./scripts/setup-aws-vault-pass.sh
MSG
  exit 0
fi

cat <<'OK'
Dependencies installed and gpg-agent configured.
Next steps (WSL):
  1) If you don't have a GPG key, run: gpg --full-generate-key
  2) Run: ./scripts/setup-aws-vault-pass.sh
  3) Use: export AWS_VAULT_BACKEND=pass && ./scripts/aws-vault.sh add <PROFILE>
  4) Deploy with: export AWS_VAULT_BACKEND=pass && ./scripts/aws-vault.sh exec <PROFILE> -- npx cdk deploy --all --require-approval never
OK
