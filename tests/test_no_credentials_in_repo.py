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
