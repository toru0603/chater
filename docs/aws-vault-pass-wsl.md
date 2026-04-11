AWS Vault — pass+GPG setup for WSL

This document shows a secure setup for aws-vault on WSL using the `pass` backend (GPG-encrypted password store). It keeps long-term AWS keys encrypted with your GPG key instead of relying on OS keyrings.

Quick steps

1) Install dependencies (WSL / Ubuntu):
   sudo apt update && sudo apt install -y gnupg2 pass pinentry-curses

2) Configure pinentry for WSL (the installer script does this):
   echo 'pinentry-program /usr/bin/pinentry-curses' >> ~/.gnupg/gpg-agent.conf
   gpgconf --kill gpg-agent

3) Generate or import a GPG key (if you don't have one):
   gpg --full-generate-key
   # choose RSA, 4096 bits, set a passphrase

4) Initialize pass store with your GPG key:
   ./scripts/setup-aws-vault-pass.sh
   # the script lists your GPG keys; enter the key ID when prompted

5) Add AWS credentials with aws-vault (pass backend):
   export AWS_VAULT_BACKEND=pass
   ./scripts/aws-vault.sh add chater-deploy

6) Use aws-vault to run CDK commands:
   export AWS_VAULT_BACKEND=pass
   ./scripts/aws-vault.sh exec chater-deploy -- npx cdk deploy --all --require-approval never

Notes and troubleshooting

- If `pinentry` cannot prompt, ensure pinentry-curses is installed and configured in ~/.gnupg/gpg-agent.conf.
- If you see errors about the GPG TTY, try: export GPG_TTY=$(tty)
- The provided wrapper (scripts/aws-vault.sh) runs the bundled aws-vault if present at tools/bin/aws-vault. You can also install aws-vault system-wide and omit the wrapper.
- For maximum safety, keep your GPG private key backed up and protect its passphrase.

If any step requires assistance, run the installer script and then share the exact failing command/output; guidance will be provided.