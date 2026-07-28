#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  Stand up one clinic. Linux + Docker.
#
#    ./provision.sh --clinic happytails --domain happytails.aleefy.vet
#    ./provision.sh --clinic happytails --sqlite          # clinic PC, no PG
#    ./provision.sh --clinic happytails --upgrade         # refresh config only
#
#  Idempotent: an existing clinic is REFUSED, not overwritten. See --upgrade.
#  Prints credentials once, to the terminal, never to a file.
#
#  Host prerequisites (run deploy/deploy.sh once per machine):
#    docker + compose plugin, postgresql (unless --sqlite), nginx, python3
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
log()  { echo "${GREEN}[OK]${NC}  $*"; }
warn() { echo "${YELLOW}[!!]${NC}  $*" >&2; }
fail() { echo "${RED}[ERR]${NC} $*" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$HERE/../.." && pwd)"          # the platform checkout

ROOT="${ALEEFY_ROOT:-/srv/aleefy}"
CLINIC=""; DOMAIN=""; TITLE=""; PHONE=""
DB_HOST="127.0.0.1"; DB_PORT="5432"; SSLMODE=""
APP_IMAGE=""; USE_SQLITE=0; UPGRADE=0; NO_START=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clinic)     CLINIC="$2"; shift 2 ;;
    --domain)     DOMAIN="$2"; shift 2 ;;
    --title)      TITLE="$2"; shift 2 ;;
    --phone)      PHONE="$2"; shift 2 ;;
    --root)       ROOT="$2"; shift 2 ;;
    --db-host)    DB_HOST="$2"; shift 2 ;;
    --db-port)    DB_PORT="$2"; shift 2 ;;
    --sslmode)    SSLMODE="$2"; shift 2 ;;
    --image)      APP_IMAGE="$2"; shift 2 ;;
    --sqlite)     USE_SQLITE=1; shift ;;
    --upgrade)    UPGRADE=1; shift ;;
    --no-start)   NO_START=1; shift ;;
    -h|--help)    sed -n '2,15p' "$0"; exit 0 ;;
    *)            fail "unknown argument: $1" ;;
  esac
done

[[ -n "$CLINIC" ]] || fail "--clinic <slug> is required"
[[ "$CLINIC" =~ ^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$ ]] \
  || fail "bad slug '$CLINIC': 3-32 chars, a-z 0-9 and '-' only"
[[ "$(uname -s)" == "Linux" ]] \
  || fail "provisioning is a Linux operation (0600 file modes, systemd/docker,
       psql). On Windows use WSL, or provision on the server itself."

command -v docker >/dev/null || fail "docker not installed — run deploy/deploy.sh"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin missing"
command -v python3 >/dev/null || fail "python3 not installed"

CLINIC_DIR="$ROOT/clinics/$CLINIC"
ENV_FILE="$CLINIC_DIR/.env"
PROJECT="clinic-$CLINIC"

# Version label for the image tag and the inventory: the git revision of the
# checkout we are deploying from.
APP_VERSION="$(git -C "$SRC_DIR" describe --tags --always --dirty 2>/dev/null || echo unknown)"
[[ -n "$APP_IMAGE" ]] || APP_IMAGE="aleefy:$APP_VERSION"

echo
echo "  clinic     $CLINIC"
echo "  directory  $CLINIC_DIR"
echo "  image      $APP_IMAGE"
echo "  database   $([[ $USE_SQLITE == 1 ]] && echo 'SQLite (single box)' || echo "PostgreSQL @ $DB_HOST:$DB_PORT")"
echo

# ── 1. directories, before anything can half-write into them ────────────────
mkdir -p "$CLINIC_DIR/data/backups" "$CLINIC_DIR/logs"
chmod 700 "$CLINIC_DIR" "$CLINIC_DIR/data" "$CLINIC_DIR/data/backups"
log "directories ready"

# ── 2. secrets + .env (clinic_env.py refuses to clobber a live install) ─────
GEN_ARGS=(--clinic-dir "$CLINIC_DIR" --slug "$CLINIC" --domain "$DOMAIN"
          --title "$TITLE" --emergency-phone "$PHONE"
          --db-host "$DB_HOST" --db-port "$DB_PORT" --sslmode "$SSLMODE"
          --app-image "$APP_IMAGE" --app-version "$APP_VERSION")
[[ $USE_SQLITE == 1 ]] && GEN_ARGS+=(--sqlite)
[[ $UPGRADE    == 1 ]] && GEN_ARGS+=(--upgrade)

if ! GEN_OUT="$(python3 "$HERE/clinic_env.py" "${GEN_ARGS[@]}")"; then
  fail "refused to write .env — see the message above. Nothing was changed."
fi
eval "$(echo "$GEN_OUT" | grep -E '^(ACTION|DB_NAME|DB_USER|HOST_PORT|NEW_SECRETS)=')"
log ".env written ($ACTION, mode 600, port $HOST_PORT)"

# ── 3. database: its own DB, its own role, no reach into any other ──────────
if [[ $USE_SQLITE == 0 && "$NEW_SECRETS" == "yes" ]]; then
  command -v psql >/dev/null || fail "psql not installed (or use --sqlite)"
  DSN="$(python3 "$HERE/clinic_env.py" --print-value POSTGRES_DSN --env-file "$ENV_FILE")"
  # Strip postgresql://user:PASS@... — never echoed, never passed in argv.
  DB_PASS="${DSN#*://*:}"; DB_PASS="${DB_PASS%%@*}"

  # Heredoc, so the password travels on stdin. A password in `psql -c` is
  # visible in `ps` to every user on the box for as long as the query runs.
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
  ELSE
    ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END \$\$;
SQL
  if ! sudo -u postgres psql -tAc \
       "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
    sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
  fi
  # The cross-clinic guard. Without the REVOKE, PUBLIC keeps CONNECT and any
  # clinic's role can open any other clinic's database — patient data, one
  # `\c` away. This is the single-tenant boundary, enforced by the server.
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
REVOKE ALL ON DATABASE ${DB_NAME} FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL
  unset DSN DB_PASS
  log "PostgreSQL: database ${DB_NAME}, role ${DB_USER}, PUBLIC revoked"
elif [[ $USE_SQLITE == 1 ]]; then
  log "SQLite: $CLINIC_DIR/data/platform.db (created on first boot)"
else
  log "database untouched (--upgrade keeps the existing credentials)"
fi

# ── 4. compose project ──────────────────────────────────────────────────────
cp "$SRC_DIR/deploy/clinic-compose.yml" "$CLINIC_DIR/docker-compose.yml"
log "compose file installed"

# ── 5. image ────────────────────────────────────────────────────────────────
if ! docker image inspect "$APP_IMAGE" >/dev/null 2>&1; then
  log "building $APP_IMAGE (once per version, shared by every clinic)"
  docker build -q -t "$APP_IMAGE" "$SRC_DIR" >/dev/null
fi
log "image $APP_IMAGE ready"

# ── 6. nginx site (shared proxy, one server block per clinic) ───────────────
if [[ -n "$DOMAIN" ]] && command -v nginx >/dev/null; then
  sudo tee "/etc/nginx/sites-available/clinic-$CLINIC" >/dev/null <<NGINX
# clinic $CLINIC — generated by provision.sh, safe to regenerate
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 16m;   # matches MAX_CONTENT_LENGTH in config.py

    location / {
        proxy_pass http://127.0.0.1:$HOST_PORT;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX
  sudo ln -sf "/etc/nginx/sites-available/clinic-$CLINIC" \
              "/etc/nginx/sites-enabled/clinic-$CLINIC"
  sudo nginx -t && sudo systemctl reload nginx
  log "nginx: $DOMAIN -> 127.0.0.1:$HOST_PORT"
else
  warn "no --domain (or no nginx): clinic reachable only on 127.0.0.1:$HOST_PORT"
fi

# ── 7. start ────────────────────────────────────────────────────────────────
if [[ $NO_START == 1 ]]; then
  warn "--no-start: nothing launched. Start with:
       docker compose -f $CLINIC_DIR/docker-compose.yml up -d"
else
  ( cd "$CLINIC_DIR" && docker compose up -d )
  log "container started, waiting for health..."
  HEALTHY=0
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$HOST_PORT/healthz" >/dev/null 2>&1; then
      HEALTHY=1; break
    fi
    sleep 2
  done
  if [[ $HEALTHY == 1 ]]; then
    log "clinic is answering on 127.0.0.1:$HOST_PORT"
  else
    warn "not healthy after 60s. The clinic directory and secrets are intact;
       nothing needs re-provisioning. Look at:
         docker compose -f $CLINIC_DIR/docker-compose.yml logs --tail 50"
  fi
fi

# ── 8. credentials, once ────────────────────────────────────────────────────
# To the terminal, not to stdout: if the operator ran this with `| tee log.txt`
# the secrets would land in that file and live there forever.
if [[ "$NEW_SECRETS" == "yes" ]]; then
  OUT=/dev/stdout
  if [[ -w /dev/tty ]]; then OUT=/dev/tty; else
    warn "no terminal available — credentials follow on stdout. If you
       redirected this run to a file, DELETE that file after storing them."
  fi
  {
    echo
    echo "═══════════════════════════════════════════════════════════"
    echo "  $CLINIC — store these NOW, they are shown once"
    echo "═══════════════════════════════════════════════════════════"
    echo "  URL            ${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://127.0.0.1:$HOST_PORT}"
    echo "  admin user     $(python3 "$HERE/clinic_env.py" --print-value PLATFORM_ADMIN_USER --env-file "$ENV_FILE" 2>/dev/null || echo admin)"
    for KEY in PLATFORM_ADMIN_PASS WAITING_ROOM_TOKEN API_V1_KEY; do
      printf '  %-14s %s\n' "$KEY" \
        "$(python3 "$HERE/clinic_env.py" --print-value "$KEY" --env-file "$ENV_FILE")"
    done
    echo
    echo "  The session key and database password stay in $ENV_FILE (0600)."
    echo "  Put the three values above in the password manager, then close"
    echo "  this terminal. Change the admin password at first login."
    echo "═══════════════════════════════════════════════════════════"
    echo
  } > "$OUT"
else
  log "--upgrade: secrets unchanged, nothing to print"
fi

log "done: $CLINIC"
