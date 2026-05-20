#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  One-click deployment script — Premium Animal Hospital Platform
#  Run as: bash deploy.sh
#  Tested on: Ubuntu 22.04 LTS
# ═══════════════════════════════════════════════════════════

set -e   # stop on first error
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!!]${NC} $1"; }
fail() { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

PLATFORM_DIR="/home/ahmed/vet/platform"
VENV_DIR="/home/ahmed/.venv"
SERVICE_NAME="vetplatform"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Premium Animal Hospital — Production Deployment"
echo "═══════════════════════════════════════════════════"
echo ""

# ── 1. System packages ────────────────────────────────────
log "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-venv \
    postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx \
    ufw git curl

# ── 2. Python virtual environment ─────────────────────────
log "Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ── 3. Install Python packages ────────────────────────────
log "Installing Python dependencies..."
pip install --upgrade pip -q
pip install gunicorn -q
pip install -r "$PLATFORM_DIR/requirements.txt" -q
log "All packages installed."

# ── 4. Create logs directory ──────────────────────────────
log "Creating log directory..."
mkdir -p "$PLATFORM_DIR/logs"
mkdir -p "$PLATFORM_DIR/data/backups"

# ── 5. Check .env file exists ─────────────────────────────
if [ ! -f "$PLATFORM_DIR/.env" ]; then
    fail ".env file not found at $PLATFORM_DIR/.env — create it first! See deploy/README.txt"
fi
log ".env file found."

# ── 6. PostgreSQL — create DB and user ───────────────────
log "Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE vetclinic;" 2>/dev/null || warn "Database 'vetclinic' already exists — skipping."
sudo -u postgres psql -c "CREATE USER vetapp WITH PASSWORD 'Ahmed@1122';" 2>/dev/null || warn "User 'vetapp' already exists — skipping."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE vetclinic TO vetapp;" 2>/dev/null

# ── 7. Systemd service ────────────────────────────────────
log "Installing systemd service..."
sudo cp "$PLATFORM_DIR/deploy/vetplatform.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
sleep 2
sudo systemctl is-active --quiet $SERVICE_NAME && log "Service is running." || fail "Service failed to start. Check: sudo journalctl -u $SERVICE_NAME -n 50"

# ── 8. Nginx ──────────────────────────────────────────────
log "Configuring Nginx..."
sudo cp "$PLATFORM_DIR/deploy/nginx.conf" /etc/nginx/sites-available/vetplatform
sudo ln -sf /etc/nginx/sites-available/vetplatform /etc/nginx/sites-enabled/vetplatform
sudo rm -f /etc/nginx/sites-enabled/default   # remove default placeholder
sudo nginx -t && sudo systemctl reload nginx
log "Nginx configured."

# ── 9. Firewall ───────────────────────────────────────────
log "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 5100/tcp   # block direct Gunicorn access from outside
log "Firewall: SSH, HTTP, HTTPS allowed. Port 5100 blocked externally."

# ── 10. SSL certificate ───────────────────────────────────
warn "SSL certificate: run this manually after pointing your domain DNS to this server:"
echo ""
echo "  sudo certbot --nginx -d YOUR_DOMAIN_HERE"
echo "  Then update deploy/nginx.conf with your actual domain and reload nginx."
echo ""

# ── Done ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Platform:  http://$(hostname -I | awk '{print $1}'):5100"
echo "  Login:     admin / Ahmed@1122"
echo "  Logs:      sudo journalctl -u vetplatform -f"
echo "             $PLATFORM_DIR/logs/error.log"
echo ""
warn "Change the admin password after first login!"
echo ""
