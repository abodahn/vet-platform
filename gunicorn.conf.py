"""
Gunicorn production configuration
Premium Animal Hospital Platform
Run: gunicorn -c gunicorn.conf.py "app:create_app()"
"""
import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────
# Development: 127.0.0.1:5100  (Nginx in front)
# Production (Koyeb/Render): 0.0.0.0:8000  (platform handles SSL)
import os as _os
_port = _os.environ.get("PLATFORM_PORT", "8000")
bind    = f"0.0.0.0:{_port}"
backlog = 2048

# ── Workers ──────────────────────────────────────────────────
# Formula: (2 × CPU cores) + 1
# Change to your actual CPU count if different
workers     = (multiprocessing.cpu_count() * 2) + 1
worker_class = "sync"          # use "gevent" if you install gevent
threads     = 2                # threads per worker
timeout     = 120              # seconds before killing a stuck worker
keepalive   = 5

# ── Logging ──────────────────────────────────────────────────
loglevel       = "info"
accesslog      = "logs/access.log"
errorlog       = "logs/error.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process naming ────────────────────────────────────────────
proc_name = "vetplatform"

# ── Security ─────────────────────────────────────────────────
limit_request_line    = 4096
limit_request_fields  = 100
limit_request_field_size = 8190

# ── Reload on code change (dev only — set to False in prod) ──
reload = os.environ.get("PLATFORM_DEBUG", "0") == "1"
