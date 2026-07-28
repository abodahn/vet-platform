#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  Upgrade one clinic, or all of them. Linux + Docker.
#
#    ./upgrade.sh --clinic happytails --ref v1.4.0
#    ./upgrade.sh --clinic happytails --ref v1.4.0 --alembic 0002_audit_log_indexes
#    ./upgrade.sh --all --ref v1.4.0
#    ./upgrade.sh --clinic happytails --rollback
#
#  Order is fixed and not negotiable:
#     backup -> verify backup -> new image -> migrate -> restart -> health
#  A failed backup ABORTS before anything is touched. A failed health check
#  rolls the code back automatically; data is restored only by a human.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
log()  { echo "${GREEN}[OK]${NC}  $*"; }
warn() { echo "${YELLOW}[!!]${NC}  $*" >&2; }
fail() { echo "${RED}[ERR]${NC} $*" >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$HERE/../.." && pwd)"
ROOT="${ALEEFY_ROOT:-/srv/aleefy}"

CLINIC=""; REF=""; ALEMBIC_REV=""; ALL=0; ROLLBACK=0; SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clinic)   CLINIC="$2"; shift 2 ;;
    --ref)      REF="$2"; shift 2 ;;
    --alembic)  ALEMBIC_REV="$2"; shift 2 ;;
    --root)     ROOT="$2"; shift 2 ;;
    --all)      ALL=1; shift ;;
    --rollback) ROLLBACK=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -h|--help)  sed -n '2,17p' "$0"; exit 0 ;;
    *)          fail "unknown argument: $1" ;;
  esac
done

if [[ "$ALEMBIC_REV" == "head" ]]; then
  fail "'--alembic head' is refused, and so is alembic itself.
       There are deliberately TWO heads (0002_audit_log_indexes and
       0002_money_numeric). They are independent branches and must not both
       be applied. Name the one you mean — normally:
         --alembic 0002_audit_log_indexes
       Read MIGRATIONS.md before choosing anything else."
fi

# ── the actual work, per clinic ─────────────────────────────────────────────
upgrade_one() {
  local slug="$1"
  local dir="$ROOT/clinics/$slug"
  local env_file="$dir/.env"
  local state_file="$dir/.upgrade-state"      # no secrets in here

  [[ -f "$env_file" ]] || fail "$slug: no .env at $env_file — not provisioned?"

  # Load the clinic env into this subshell. `source`, not argv: a DSN on a
  # command line is visible in `ps` to every user on the box.
  set -a; . "$env_file"; set +a

  local host_port="${CLINIC_HOST_PORT:?CLINIC_HOST_PORT missing from .env}"
  local prev_image="${APP_IMAGE:?APP_IMAGE missing from .env}"

  echo
  echo "──────────────────────────────────────────────"
  echo "  $slug   (port $host_port, image $prev_image)"
  echo "──────────────────────────────────────────────"

  # ── 1. BACKUP. Nothing proceeds without a verified one. ────────────────
  # Run on the HOST, not in the container: models/backup.py is stdlib-only at
  # import time, and pg_dump lives on the host (the app image has no
  # postgresql-client — see PROVISIONING.md "Known gaps").
  local backup_json
  if ! backup_json="$(
        cd "$SRC_DIR" && PLATFORM_DB_PATH="$dir/data/platform.db" python3 - <<'PY'
import json, os, sys
import models.backup as bk

db_path = os.environ["PLATFORM_DB_PATH"]
bk.configure(db_path=db_path, backup_dir=os.path.join(os.path.dirname(db_path), "backups"))
result = bk.run_backup()
print(json.dumps(result))
sys.exit(0 if result.get("success") else 1)
PY
      )"; then
    fail "$slug: BACKUP FAILED — upgrade aborted, nothing was changed.
       $(echo "$backup_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("error","(no detail)"))' 2>/dev/null || echo "$backup_json")
       Fix the backup first: docker logs clinic-$slug, check disk space,
       check the POSTGRES_DSN in $env_file."
  fi
  local backup_file
  backup_file="$(echo "$backup_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["filename"])')"
  log "$slug: backup $backup_file"

  # ── 2. remember how to get back ────────────────────────────────────────
  local prev_rev
  prev_rev="$(cd "$SRC_DIR" && alembic -c db_migrations/alembic.ini current 2>/dev/null \
              | head -1 | awk '{print $1}')"
  printf 'PREV_IMAGE=%s\nPREV_ALEMBIC=%s\nBACKUP_FILE=%s\nUPGRADED_AT=%s\n' \
    "$prev_image" "${prev_rev:-unstamped}" "$backup_file" "$(date -Iseconds)" \
    > "$state_file"
  log "$slug: rollback point saved ($state_file)"

  # ── 3. new image ───────────────────────────────────────────────────────
  local new_image="$prev_image"
  if [[ -n "$REF" ]]; then
    new_image="aleefy:$REF"
    if [[ $SKIP_BUILD == 0 ]] && ! docker image inspect "$new_image" >/dev/null 2>&1; then
      log "building $new_image"
      git -C "$SRC_DIR" fetch --tags --quiet
      git -C "$SRC_DIR" checkout --quiet "$REF"
      docker build -q -t "$new_image" "$SRC_DIR" >/dev/null
    fi
    # sed -i keeps the file's 0600 mode; a rewrite would not.
    sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$new_image|" "$env_file"
    sed -i "s|^APP_VERSION=.*|APP_VERSION=$REF|" "$env_file"
    log "$slug: image -> $new_image"
  fi

  # ── 4. migrate (explicit revision only) ────────────────────────────────
  local migrated=0
  if [[ -n "$ALEMBIC_REV" ]]; then
    if ( cd "$SRC_DIR" && alembic -c db_migrations/alembic.ini upgrade "$ALEMBIC_REV" ); then
      migrated=1
      log "$slug: migrated to $ALEMBIC_REV"
    else
      warn "$slug: migration FAILED. Restoring the previous image and stopping."
      sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$prev_image|" "$env_file"
      ( cd "$dir" && docker compose up -d )
      fail "$slug: migration failed, code rolled back to $prev_image.
       The database may be half-migrated. Restore it from $backup_file —
       see 'Rolling back' in PROVISIONING.md. Do not retry blindly."
    fi
  fi

  # ── 5. restart + health, with automatic code rollback ──────────────────
  ( cd "$dir" && docker compose up -d )
  local healthy=0
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$host_port/healthz" >/dev/null 2>&1; then
      healthy=1; break
    fi
    sleep 2
  done

  if [[ $healthy == 1 ]]; then
    log "$slug: healthy on $new_image"
    return 0
  fi

  warn "$slug: unhealthy after 60s — rolling the code back to $prev_image"
  sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$prev_image|" "$env_file"
  ( cd "$dir" && docker compose up -d ) || true
  if [[ $migrated == 1 ]]; then
    warn "$slug: a migration ($ALEMBIC_REV) was applied and is NOT undone
       automatically. If the old code cannot read the new schema:
         cd $SRC_DIR && alembic -c db_migrations/alembic.ini downgrade ${prev_rev:-0001_baseline}
       If that fails, restore $backup_file (see PROVISIONING.md)."
  fi
  fail "$slug: upgrade failed, code rolled back. Backup: $backup_file"
}

# ── rollback on request (no upgrade, just go back) ──────────────────────────
rollback_one() {
  local slug="$1"
  local dir="$ROOT/clinics/$slug"
  local state_file="$dir/.upgrade-state"
  [[ -f "$state_file" ]] || fail "$slug: no $state_file — nothing recorded to roll back to."
  . "$state_file"
  sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$PREV_IMAGE|" "$dir/.env"
  ( cd "$dir" && docker compose up -d )
  log "$slug: code rolled back to $PREV_IMAGE"
  echo "  If the DATA also needs to go back, that is a separate, destructive"
  echo "  step a human must confirm — the newest backup taken before the"
  echo "  upgrade is: $BACKUP_FILE"
  echo "  Restore it from the app: System -> Backup -> Restore, or"
  echo "  cd $SRC_DIR && python3 -c \"import models.backup as bk; ...\" (PROVISIONING.md)"
  [[ "${PREV_ALEMBIC:-}" == "unstamped" ]] || \
    echo "  Schema was at: $PREV_ALEMBIC"
}

# ── dispatch ────────────────────────────────────────────────────────────────
targets=()
if [[ $ALL == 1 ]]; then
  for d in "$ROOT"/clinics/*/; do
    [[ -f "$d/.env" ]] && targets+=("$(basename "$d")")
  done
  [[ ${#targets[@]} -gt 0 ]] || fail "no provisioned clinics under $ROOT/clinics"
elif [[ -n "$CLINIC" ]]; then
  targets=("$CLINIC")
else
  fail "--clinic <slug> or --all is required"
fi

# --all upgrades one clinic at a time and STOPS at the first failure. Marching
# on would turn one bad release into twenty broken clinics; the ones already
# done stay done, the rest stay on the old version until someone looks.
failed=0
for slug in "${targets[@]}"; do
  if [[ $ROLLBACK == 1 ]]; then
    rollback_one "$slug"
  else
    ( upgrade_one "$slug" ) || { failed=1; break; }
  fi
done

if [[ $failed == 1 ]]; then
  fail "stopped at a failing clinic. Clinics upgraded before it are fine and
       still running; the rest were not touched. Fix, then re-run --all."
fi
log "all done (${#targets[@]} clinic(s))"
