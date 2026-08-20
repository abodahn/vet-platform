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
# A full deploy also REMOVES server files that are no longer in git. It did not
# used to, and untarring over the top meant anything deleted from the repo lived
# on in production for ever: a removed template, a retired debug route, a file
# with a credential in it. Deleting it from git did not delete it from the box.
# Found when a renamed manifest kept serving 200 after a clean redeploy.
#
# Usage:  deploy/push_app.sh [file ...]     (no args = the whole app tree)
#         ALEEFY_NO_PRUNE=1 deploy/push_app.sh      (deploy, remove nothing)
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
FULL=0
if [ ${#FILES[@]} -eq 0 ]; then
  mapfile -t FILES < <(git ls-files -- . ':!:tests' ':!:docs')
  FULL=1
fi
echo "deploying ${#FILES[@]} file(s) at $SHORT"

# Pruning is only ever safe on a FULL deploy. On a partial one the manifest is
# whatever files were named on the command line, so "delete everything not in
# the manifest" would delete the entire application.
PRUNE=$FULL
[ "${ALEEFY_NO_PRUNE:-0}" = "1" ] && PRUNE=0

# Stage under /tmp first: the ubuntu login cannot write $APP, which is aleefy's.
"${SSH[@]}" "$HOST" "rm -rf /tmp/deploy && mkdir -p /tmp/deploy"
tar -czf - "${FILES[@]}" | "${SSH[@]}" "$HOST" "tar -xzf - -C /tmp/deploy"

# The list of what SHOULD exist, for the prune step to compare against.
printf '%s
' "${FILES[@]}" | "${SSH[@]}" "$HOST" "cat > /tmp/deploy-manifest.txt"

"${SSH[@]}" "$HOST" "sudo bash -s" <<REMOTE
set -euo pipefail
PRUNE=$PRUNE
cd /tmp/deploy
find . -type f -print0 | while IFS= read -r -d '' f; do
  install -D -o aleefy -g aleefy -m 644 "\$f" "$APP/\${f#./}"
done

if [ "$PRUNE" = "1" ]; then
  cd "$APP"
  # NEVER prune these. Each line is something the server owns and git does not:
  #
  #   data/        the clinic's database and its backups. Deleting this is the
  #                worst thing this script could possibly do.
  #   logs/        written by the running service
  #   __pycache__  regenerated on import; deleting it churns for no gain
  #   *.bak*       somebody kept that on purpose. Report it, do not remove it.
  #   .git         not deployed, but if it ever appears, leave it alone
  #
  # The list is deliberately conservative. A file that should have gone and did
  # not is untidy; a file that should have stayed and went can end a clinic.
  KEEP='^(data|logs)/|(^|/)__pycache__/|\.pyc|\.bak|(^|/)\.git/'

  find . -type f -printf '%P\n' | sort > /tmp/server-files.txt
  # grep exits 1 when nothing matches, which here means "nothing to prune" -
  # the clean case, and set -e would abort the deploy on success.
  grep -Fxv -f /tmp/deploy-manifest.txt /tmp/server-files.txt > /tmp/extra.txt || true
  grep -Ev "\$KEEP" /tmp/extra.txt > /tmp/prune.txt || true

  N=\$(wc -l < /tmp/prune.txt | tr -d ' ')
  if [ "\$N" != "0" ]; then
    echo "removing \$N file(s) no longer in git:"
    sed 's/^/  - /' /tmp/prune.txt
    # -- so a filename that begins with a dash is not read as an option.
    while IFS= read -r f; do [ -n "\$f" ] && rm -f -- "$APP/\$f"; done < /tmp/prune.txt
    # Directories left empty by the above, but never the protected ones.
    find . -mindepth 1 -type d -empty          -not -path './data*' -not -path './logs*' -not -path './.git*'          -delete 2>/dev/null || true
  else
    echo "nothing to prune"
  fi

  # An explicit if, not `[ ] && echo`: that form returns non-zero when the test
  # fails, and under set -e it would abort the deploy AFTER pruning but BEFORE
  # the service restart if anything ever moved it to the end of the block.
  KEPT=\$(grep -Ec "\$KEEP" /tmp/extra.txt || true)
  if [ "\$KEPT" != "0" ]; then
    echo "left \$KEPT protected file(s) alone (data, logs, backups)"
  fi
fi

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
