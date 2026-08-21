#!/usr/bin/env bash
# Put one clinic's licence secret where the app will read it.
#
# WHY THIS EXISTS
#
# The secret is derived from your master, so it must be generated on YOUR
# machine - but it has to end up in the CLINIC'S .env. Copying it by hand means
# a secret in your clipboard, in your shell history, and probably in a WhatsApp
# message. This derives and installs it in one step so it is never displayed.
#
#   scripts/install_license_secret.sh --clinic demo                 # local .env
#   scripts/install_license_secret.sh --clinic demo --remote        # the demo box
#
# Reads ALEEFY_LICENSE_MASTER from your shell. Create one first, once, with:
#   python scripts/make_license.py --init
set -euo pipefail

CLINIC=""
REMOTE=0
HOST="${ALEEFY_HOST:-ubuntu@63.186.196.107}"
KEY="${ALEEFY_KEY:-$HOME/.ssh/aleefy-demo.pem}"
ENVFILE="${ALEEFY_ENVFILE:-/etc/aleefy/aleefy.env}"

while [ $# -gt 0 ]; do
  case "$1" in
    --clinic) CLINIC="$2"; shift 2 ;;
    --remote) REMOTE=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -n "$CLINIC" ] || { echo "usage: $0 --clinic <id> [--remote]" >&2; exit 2; }

if [ -z "${ALEEFY_LICENSE_MASTER:-}" ]; then
  cat >&2 <<'MSG'
ALEEFY_LICENSE_MASTER is not set in this shell.

If you have it:
   PowerShell : $env:ALEEFY_LICENSE_MASTER = '...'
   bash       : export ALEEFY_LICENSE_MASTER='...'

If you have never made one:
   python scripts/make_license.py --init
MSG
  exit 2
fi

cd "$(dirname "$0")/.."
PY="${ALEEFY_PYTHON:-/d/vet/.venv/Scripts/python.exe}"
[ -x "$PY" ] || PY=python

# Derive into a variable. It is never echoed - printing it here would defeat
# the entire point of this script existing.
SECRET=$("$PY" - <<PYEOF
import os, sys
sys.path.insert(0, ".")
from models import licensing
print(licensing.derive_clinic_secret(os.environ["ALEEFY_LICENSE_MASTER"], "$CLINIC"))
PYEOF
)
[ -n "$SECRET" ] || { echo "derivation produced nothing - is models/licensing.py present?" >&2; exit 1; }

if [ "$REMOTE" = "1" ]; then
  # Written by a here-doc on stdin so the secret is never an argv entry, where
  # it would be visible to every other user on the box via ps.
  printf '%s' "$SECRET" | ssh -i "$KEY" -o BatchMode=yes "$HOST" \
    "sudo bash -c '
      S=\$(cat)
      sed -i \"/^ALEEFY_LICENSE_SECRET=/d\" $ENVFILE
      printf \"ALEEFY_LICENSE_SECRET=%s\n\" \"\$S\" >> $ENVFILE
      chmod 640 $ENVFILE; chown root:aleefy $ENVFILE
      systemctl restart aleefy
    '"
  echo "installed for '$CLINIC' on $HOST and restarted the service"
  echo "the secret was not printed, and is not in your shell history"
else
  TARGET=".env"
  [ -f "$TARGET" ] || touch "$TARGET"
  # Same rewrite locally: drop any old line, append the new one.
  "$PY" - "$TARGET" "$SECRET" <<'PYEOF'
import io, sys
path, secret = sys.argv[1], sys.argv[2]
lines = [l for l in io.open(path, encoding="utf-8").read().splitlines()
         if not l.startswith("ALEEFY_LICENSE_SECRET=")]
lines.append("ALEEFY_LICENSE_SECRET=%s" % secret)
io.open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYEOF
  echo "installed for '$CLINIC' in ./.env (which is gitignored)"
  echo "restart your local app so it picks the value up"
fi

echo
echo "Next: open Settings -> Licence, read the ALF-xxxx-xxxx number, and turn it"
echo "into a code with your phone or with:"
echo "  python scripts/make_license.py --clinic $CLINIC --machine ALF-xxxx-xxxx"
