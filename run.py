"""
Aleefy — Smart Veterinary Platform — Entry Point
Run:  python run.py
Env:  set PLATFORM_PORT=5100  (default)
      set PLATFORM_DEBUG=1    (dev mode)
      All settings can be placed in a .env file in this directory.
"""

import os
import sys
import threading
import time
import subprocess
import webbrowser

# ── Auto-load .env file by stage ──────────────────────────────────────────────
def _load_env():
    """
    Load environment variables from the appropriate .env file.

    Priority order (first found wins):
      1. .env.<FLASK_ENV>   e.g. .env.development  or  .env.production
      2. .env               generic fallback
    Shell environment variables always win over file values.
    """
    base = os.path.dirname(__file__)
    flask_env = os.environ.get("FLASK_ENV", "development").lower()

    candidates = [
        os.path.join(base, f".env.{flask_env}"),   # stage-specific first
        os.path.join(base, ".env"),                 # generic fallback
    ]

    loaded_from = None
    for path in candidates:
        if os.path.exists(path):
            loaded_from = path
            break

    if not loaded_from:
        return

    with open(loaded_from, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:   # shell env vars always win
                os.environ[key] = val

    print(f"  config       : {os.path.basename(loaded_from)} [{flask_env.upper()}]")

_load_env()

from app import create_app
from config import Config

# ── freellmapi location ───────────────────────────────────────────────────────
_FREELLM_DIR  = os.path.join(os.path.expanduser("~"), "freellmapi")
_FREELLM_PORT = 3001
_freellm_proc = None   # module-level handle so we can shut it down on exit


def _freellmapi_running() -> bool:
    """Quick TCP check — is something already listening on port 3001?"""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", _FREELLM_PORT), timeout=1):
            return True
    except OSError:
        return False


def _start_freellmapi() -> None:
    """Launch the freellmapi Node server in the background (dev mode via npx tsx)."""
    global _freellm_proc

    if _freellmapi_running():
        print("  freellmapi  : already running on port 3001 [OK]")
        return

    server_dir = os.path.join(_FREELLM_DIR, "server")
    if not os.path.isdir(server_dir):
        print(f"  freellmapi  : server dir not found at {server_dir} — skipping")
        return

    try:
        # On Windows use npx.cmd; on Unix use npx
        npx = "npx.cmd" if sys.platform == "win32" else "npx"
        cmd = [npx, "tsx", "src/index.ts"]

        _freellm_proc = subprocess.Popen(
            cmd,
            cwd=server_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # Keep the child hidden but still running after the console closes
            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                           if sys.platform == "win32" else 0,
        )

        # Wait up to 15 s — Node cold-start can be slow on Windows
        print("  freellmapi  : starting...", end="", flush=True)
        for _ in range(30):
            time.sleep(0.5)
            if _freellmapi_running():
                print(f" [OK] (pid {_freellm_proc.pid})")
                return

        print(" [timeout — AI may take a moment to respond]")
    except FileNotFoundError:
        print("  freellmapi  : npx.cmd not found — make sure Node.js is in PATH")
    except Exception as e:
        print(f"  freellmapi  : could not start — {e}")


def _stop_freellmapi() -> None:
    """Terminate freellmapi when the platform shuts down."""
    global _freellm_proc
    if _freellm_proc and _freellm_proc.poll() is None:
        _freellm_proc.terminate()
        try:
            _freellm_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _freellm_proc.kill()
        print("  freellmapi  : stopped")


def _open_browser(url: str, delay: float = 1.4):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    # Start freellmapi AI router before the Flask app
    _start_freellmapi()

    app = create_app(Config)
    port  = Config.PORT
    debug = Config.DEBUG
    host  = Config.HOST

    url = f"http://localhost:{port}"
    print(f"\n{'='*60}")
    print(f"  Aleefy — Smart Veterinary Platform v2.0")
    print(f"  Happy Pets, Healthy Lives")
    print(f"{'='*60}")
    print(f"  Platform URL : {url}")
    print(f"  Legacy App   : {Config.LEGACY_APP_URL}")
    print(f"  freellmapi   : http://localhost:{_FREELLM_PORT}/v1")
    print(f"  Debug mode   : {debug}")
    print(f"  Database     : {Config.DATABASE_PATH}")
    print(f"{'='*60}\n")
    print(f"  Default login:  {Config.SEED_ADMIN_USER} / {Config.SEED_ADMIN_PASS}")
    print("  Press Ctrl+C to stop.\n")

    if not debug:
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        app.run(host=host, port=port, debug=debug, use_reloader=debug)
    finally:
        _stop_freellmapi()


if __name__ == "__main__":
    main()
