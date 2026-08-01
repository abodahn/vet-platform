#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stand up an embedded PostgreSQL, seed it, and run the production-engine suite.

    python scripts/run_postgres_tests.py

Everything lands in a throwaway database called vetclinic_test. Nothing touches
a real clinic: the suite refuses any database whose name does not look like a
test database, and so does the seeder.

Why bother, when 1400+ tests already pass on SQLite: those tests cannot see
PostgreSQL-only failures. This suite found four — including one where a wrong
password raised UndefinedColumn instead of being reported as a wrong password,
leaving account lockout permanently disengaged.
"""
import os
import subprocess
import sys
from urllib.parse import urlparse

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PGDATA = os.path.join(os.path.dirname(PLATFORM), "pgdata")


def main() -> int:
    try:
        import pgembed
    except ImportError:
        print("pgembed is not installed. Run:  pip install -r requirements-dev.txt")
        return 2

    srv = pgembed.get_server(PGDATA, cleanup_mode=None)
    u = urlparse(srv.get_uri())
    admin = dict(host=u.hostname, port=u.port,
                 user=u.username or "postgres", password=u.password or "")
    print(f"PostgreSQL listening on {admin['host']}:{admin['port']}")

    import psycopg2
    c = psycopg2.connect(dbname="postgres", **admin)
    c.autocommit = True
    cur = c.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='vetclinic_test'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE vetclinic_test")
        print("created vetclinic_test")
    c.close()

    dsn = (f"postgresql://{admin['user']}:{admin['password']}"
           f"@{admin['host']}:{admin['port']}/vetclinic_test")
    env = dict(os.environ, TEST_POSTGRES_DSN=dsn, POSTGRES_DSN=dsn,
               PLATFORM_ADMIN_PASS="Demo@1234", FLASK_ENV="development",
               PYTHONIOENCODING="utf-8")

    print("seeding…")
    subprocess.run([sys.executable, os.path.join("scripts", "seed", "demo_showcase.py"),
                    "--postgres", dsn, "--quiet"], cwd=PLATFORM, env=env, check=True)

    print("running the suite…")
    print("(18 HTTP tests need the app running on :5100 against the same DSN)")
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest",
         "tests/test_postgres_full.py", "-q"],
        cwd=PLATFORM, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
