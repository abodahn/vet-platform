#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  HOST BOOTSTRAP — run ONCE per machine, before the first clinic.
#
#      sudo bash deploy/deploy.sh
#
#  This script used to deploy a single clinic and, in doing so, shipped the
#  same PostgreSQL password to every customer from a committed file. It no
#  longer creates databases, users, secrets or services: it only makes a bare
#  Ubuntu box able to host clinics.
#
#  One clinic is now:
#      scripts/provision/provision.sh --clinic <slug> --domain <fqdn>
#
#  Tested on Ubuntu 22.04 LTS.
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
log()  { echo "${GREEN}[OK]${NC}  $*"; }
warn() { echo "${YELLOW}[!!]${NC}  $*" >&2; }
fail() { echo "${RED}[ERR]${NC} $*" >&2; exit 1; }

WITH_POSTGRES=1
[[ "${1:-}" == "--no-postgres" ]] && WITH_POSTGRES=0   # SQLite-only clinic PC

[[ "$(uname -s)" == "Linux" ]] || fail "Linux only. On Windows, use WSL."

echo
echo "═══════════════════════════════════════════════════"
echo "  Aleefy — host bootstrap"
echo "═══════════════════════════════════════════════════"
echo

# ── 1. base packages ────────────────────────────────────────────────────────
log "installing base packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    ca-certificates curl git python3 python3-venv \
    nginx certbot python3-certbot-nginx ufw

# ── 2. docker (official repo — the distro package lags badly) ───────────────
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  log "docker already present"
else
  log "installing docker..."
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
       docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker
log "docker ready"

# ── 3. postgresql — ONE server, one database per clinic ─────────────────────
# Not one PostgreSQL per clinic: 10 postgres containers would not fit in the
# RAM of a EUR 5-7 VPS. Isolation comes from a per-clinic database + role with
# CONNECT revoked from PUBLIC (provision.sh does that per clinic).
if [[ $WITH_POSTGRES == 1 ]]; then
  sudo apt-get install -y -qq postgresql postgresql-contrib postgresql-client
  sudo systemctl enable --now postgresql
  log "postgresql ready (no databases created — provision.sh does that)"
else
  warn "--no-postgres: clinics on this host must use provision.sh --sqlite"
fi

# ── 4. firewall ─────────────────────────────────────────────────────────────
# Clinic containers publish on 127.0.0.1 only, so nothing but nginx is exposed.
log "configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
log "firewall: ssh, http, https"

# ── 5. clinic root ──────────────────────────────────────────────────────────
ROOT="${ALEEFY_ROOT:-/srv/aleefy}"
sudo mkdir -p "$ROOT/clinics"
sudo chmod 700 "$ROOT" "$ROOT/clinics"
log "clinic root: $ROOT (mode 700 — it holds every clinic's secrets)"

# ── 6. nightly inventory mail (optional, one line) ──────────────────────────
warn "Optional: get told when a clinic is down or has a stale backup.
     Add to root's crontab (crontab -e):
       0 8 * * * python3 $(pwd)/scripts/provision/inventory.py --quiet"

echo
echo "═══════════════════════════════════════════════════"
echo -e "  ${GREEN}Host ready.${NC} Now add a clinic:"
echo
echo "    scripts/provision/provision.sh --clinic acme --domain acme.aleefy.vet"
echo "    sudo certbot --nginx -d acme.aleefy.vet"
echo
echo "  See PROVISIONING.md."
echo "═══════════════════════════════════════════════════"
echo
