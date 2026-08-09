#!/usr/bin/env bash
# Deploy this working tree to the demo box, and STAMP WHAT WENT.
#
# /srv/aleefy/app is a file copy, not a git checkout, so nothing on the server
# knows what it is running. Every "did my fix land?" then costs an SSH session
# and a grep. This writes GIT_COMMIT and BUILD_DATE into the service env, which
# config.py already reads, so afterwards the answer is one authenticated GET:
#
#   curl -H "Authorization: Bearer $API_V1_KEY" https://demo.aleefy.online/healthz
#
# Usage:  deploy/push_app.sh [file ...]     (no args = the whole app tree)
set -euo pipefail

HOST="${ALEEFY_HOST:-ubuntu@63.186.196.107}"
KEY="${ALEEFY_KEY:-$HOME/.ssh/aleefy-demo.pem}"
KNOWN="${ALEEFY_KNOWN_HOSTS:-$HOME/.ssh/known_hosts_aleefy}"
APP=/srv/aleefy/app
ENVFILE=/etc/aleefy/aleefy.env

SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=20 -o UserKnownHostsFile="$KNOWN")
SCP=(scp -i "$KEY" -o BatchMode=yes -o UserKnownHostsFile="$KNOWN")

cd "$(dirname "$0")/.."

COMMIT=$(git rev-parse HEAD)
SHORT=${COMMIT:0:12}
DATE=$(date +%F)
# `|| true` because grep exits 1 when it matches nothing — which is the CLEAN
# case, and under `set -o pipefail` that would abort the deploy on success.
DIRTY=$(git status --porcelain -- . | { grep -v '^?? ' || true; } | wc -l | tr -d ' ')

if [ "$DIRTY" != "0" ]; then
  echo "REFUSING: $DIRTY tracked file(s) modified but not committed." >&2
  echo "A stamp that names a commit the server is not running is worse than no stamp." >&2
  git status --short -- . | { grep -v '^?? ' || true; } >&2
  exit 1
fi

FILES=("$@")
if [ ${#FILES[@]} -eq 0 ]; then
  mapfile -t FILES < <(git ls-files -- . ':!:tests' ':!:docs')
fi
echo "deploying ${#FILES[@]} file(s) at $SHORT"

# Stage under /tmp first: the ubuntu login cannot write $APP, which is aleefy's.
"${SSH[@]}" "$HOST" "rm -rf /tmp/deploy && mkdir -p /tmp/deploy"
tar -czf - "${FILES[@]}" | "${SSH[@]}" "$HOST" "tar -xzf - -C /tmp/deploy"

"${SSH[@]}" "$HOST" "sudo bash -s" <<REMOTE
set -euo pipefail
cd /tmp/deploy
find . -type f -print0 | while IFS= read -r -d '' f; do
  install -D -o aleefy -g aleefy -m 644 "\$f" "$APP/\${f#./}"
done

# The stamp. config.py:_git_commit() prefers GIT_COMMIT over reading .git,
# which is exactly the deployed case: there is no .git here.
sed -i '/^GIT_COMMIT=/d;/^BUILD_DATE=/d' "$ENVFILE"
printf 'GIT_COMMIT=%s\nBUILD_DATE=%s\n' "$COMMIT" "$DATE" >> "$ENVFILE"
chmod 640 "$ENVFILE"; chown root:aleefy "$ENVFILE"

systemctl restart aleefy
REMOTE

sleep 4
"${SSH[@]}" "$HOST" 'systemctl is-active aleefy'
echo "deployed $SHORT ($DATE)"
