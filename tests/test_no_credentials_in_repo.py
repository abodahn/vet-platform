# -*- coding: utf-8 -*-
"""No working credential may live in a tracked file.

Three separate passwords reached this public repository: the admin password in
six commits, the demo admin password in the audit findings, and a shared staff
password published in docs/sale/02_DEMO_GUIDE.md — a file written to be handed
to buyers. Each was found by accident, weeks apart, and each had to be rotated
on a live server once it was.

Scrubbing a file does NOT undo the leak: git keeps the old blob, GitHub keeps
the fork, and the only real remedy is rotating the credential. So the point of
this test is not cleanup — it is to stop the FOURTH one, at the moment somebody
writes it, when rotation is still free.

It reads `git ls-files`, so it governs exactly what would be published, and
nothing about a developer's untracked scratch files.
"""
import re
import subprocess

# Passwords known to have leaked. They stay listed after rotation: this is the
# regression test for each specific incident, and a rotated password coming back
# into a file is a real event worth failing on.
KNOWN_LEAKED = [
    "Ahmed@1122",
    "Aleefy@Demo2026",
    "Demo@1234",
]

# Where a credential is legitimately named in order to REFUSE it.
ALLOWED = {
    "scripts/preflight.py",              # denylist: refuses to boot if in use
    # Also a denylist: it TRIES each leaked password against every account so
    # it can rotate whatever still answers to one. It has to name them to do
    # that, and a test that forbade it would forbid the fix.
    "scripts/rotate_demo_passwords.py",
    "tests/test_no_credentials_in_repo.py",
    "docs/AUDIT_FINDINGS.md",            # historical audit record — see below
}

# "password = something", "PASSWORD: something" with a real-looking value.
_ASSIGNED = re.compile(
    r"""(?ix)
    \b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token)\b
    \s*[:=]\s*
    ["'`]
    (?![^"'`]*(?:\{\{|\$\{|%s|\{\}|<|xxx|your|example|changeme|placeholder|\.\.\.))
    ([A-Za-z0-9@#$%^&*!._-]{8,})
    ["'`]
    """)

# Values that look like a secret but are not one.
_BENIGN = re.compile(
    r"""(?ix)^(
        password|passwd|secret|changeme|placeholder|example|
        [a-z_]+_here|test|testing|dummy|redacted|
        [\*x]{3,}
    )$""")


def _tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return [p for p in out.stdout.splitlines() if p.strip()]


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, IsADirectoryError):
        return ""


def test_no_known_leaked_password_is_reintroduced():
    """Each of these cost a live rotation. None may come back."""
    hits = []
    for path in _tracked():
        if path in ALLOWED:
            continue
        body = _read(path)
        for cred in KNOWN_LEAKED:
            if cred in body:
                hits.append("%s contains the leaked password %r" % (path, cred))
    assert not hits, (
        "A password that already leaked once is back in a tracked file:\n  "
        + "\n  ".join(hits)
        + "\n\nRemoving it from the file does not undo publication — rotate the "
          "credential as well.")


def test_no_new_password_is_hardcoded_in_tracked_source():
    """A literal assigned to something named like a secret."""
    hits = []
    for path in _tracked():
        # tests/ is excluded: a password there creates an account inside a
        # throwaway test database that never exists anywhere else. Treating
        # those as leaks would train people to ignore this check, which is the
        # only way it fails to do its job.
        if path.startswith("tests/"):
            continue
        if path in ALLOWED or not path.endswith((".py", ".html", ".js", ".sh", ".yml", ".yaml")):
            continue
        for n, line in enumerate(_read(path).splitlines(), 1):
            m = _ASSIGNED.search(line)
            if not m:
                continue
            value = m.group(1)
            if _BENIGN.match(value):
                continue
            # os.environ.get("X", "") style defaults are configuration, not a secret.
            if "environ" in line or "getenv" in line or "form.get" in line:
                continue
            hits.append("%s:%d  %s" % (path, n, line.strip()[:100]))
    assert not hits, (
        "A credential looks hardcoded in a tracked file:\n  " + "\n  ".join(hits)
        + "\n\nRead it from the environment instead. If this is a false "
          "positive, name the file in ALLOWED with a note saying why.")


def test_the_audit_record_is_the_only_documented_exception():
    """docs/AUDIT_FINDINGS.md is allowed to quote credentials because its
    reproduction steps are the evidence for findings already fixed — but that
    is a deliberate exception, not a habit, and it must not spread."""
    doc_exceptions = {p for p in ALLOWED if p.startswith("docs/")}
    assert doc_exceptions == {"docs/AUDIT_FINDINGS.md"}, \
        "another document has been granted permission to hold credentials"


# ─────────────────────────────────────────────────────────────────────────────
# Licence signing secrets
# ─────────────────────────────────────────────────────────────────────────────
#
# The licence master secret is a different class of leak from a password. A
# password opens one account and rotating it costs an afternoon. The master
# secret mints activation codes for EVERY clinic, and rotating it invalidates
# every code already issued — so every paying customer would have to be phoned
# and re-activated before their next renewal.
#
# Three passwords have already reached this repository. This is the guard for
# the one that would be far more expensive.

_KEY_MATERIAL = re.compile(
    r"""(?ix)
    (?: -----BEGIN [A-Z ]* PRIVATE\ KEY-----        # any PEM private key
      | \bALEEFY_LICENSE_MASTER\s*[:=]\s*['"]?[A-Za-z0-9_\-+/]{16,}
      | \bALEEFY_LICENSE_SECRET\s*[:=]\s*['"]?[0-9a-f]{32,}
    )
    """)

# Where these names may legitimately appear: docs explaining them, the script
# that generates them, and this test.
_KEY_ALLOWED = {
    "tests/test_no_credentials_in_repo.py",
    "scripts/make_license.py",
    "models/licensing.py",
    ".env.example",
}


def test_no_licence_signing_material_is_tracked():
    """A leaked master secret means unlimited free licences, and revoking it
    breaks every clinic already paying. It must never be committed."""
    offenders = []
    for path in _tracked():
        if path in _KEY_ALLOWED:
            continue
        body = _read(path)
        for m in _KEY_MATERIAL.finditer(body):
            line = body[:m.start()].count("\n") + 1
            offenders.append("%s:%d  %s" % (path, line, m.group(0)[:48]))

    assert not offenders, (
        "Licence signing material is in a tracked file:\n  "
        + "\n  ".join(offenders)
        + "\n\nRotating this is not like rotating a password: every activation "
          "code already issued stops working, and every clinic has to be phoned."
    )


# ─────────────────────────────────────────────────────────────────────────────
# The rotation tool
# ─────────────────────────────────────────────────────────────────────────────

def test_the_rotation_tool_covers_every_known_leak():
    """scripts/rotate_demo_passwords.py exists to stop a published password
    opening anything. If a password is listed as leaked here but the tool does
    not try it, an account keeps using it and nobody finds out."""
    src = _read("scripts/rotate_demo_passwords.py")
    assert src, "the rotation tool is missing"
    for pw in KNOWN_LEAKED:
        assert pw in src, (
            "%s is a known leaked password but the rotation tool never tries "
            "it, so an account still using it would be missed" % pw)


def test_the_rotation_tool_never_touches_the_admin_account():
    """The owner chose the admin password themselves and signs in with it.
    Rotating it here would lock them out of their own system with no warning
    and no way back except a shell on the server."""
    src = _read("scripts/rotate_demo_passwords.py")
    assert 'PROTECTED_USERNAMES = {"admin"}' in src, (
        "admin is no longer protected from rotation")
    assert 'if r["username"] in PROTECTED_USERNAMES:' in src, (
        "the protection is declared but never applied")


def test_rotated_passwords_are_never_printed_to_the_terminal():
    """They go to a file the caller names. A password in a terminal scrollback
    survives the session, and often a screen share."""
    src = _read("scripts/rotate_demo_passwords.py")
    assert "--out" in src, "there is no file to write the new passwords to"
    assert "NOT printed here" in src, "the tool does not promise to stay quiet"
    # The password variable must never reach a print().
    import re
    for m in re.finditer(r"print\((.*)\)", src):
        assert "new" not in m.group(1).split("%")[0].replace("new passwords", ""), (
            "a print() looks like it emits a generated password: %s" % m.group(0)[:70])
