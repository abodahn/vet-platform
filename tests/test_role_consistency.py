"""Every role string used for authorization must exist in models.database._SEED_ROLES.

A role name that is not seeded can never match session["user"]["role"], so it is
dead text that silently denies access while looking like it grants something.
This class of bug has shipped four separate times — hence a test rather than
four more manual fixes.

Runs on SQLite with no PostgreSQL: it only parses source, it never opens a DB.
"""
import ast
import os

import pytest

from models.database import _SEED_ROLES

VALID_ROLES = frozenset(name for (name, *_rest) in _SEED_ROLES)

BLUEPRINTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "blueprints")

# Blueprints owned by this check. Others are covered by their own agents/tests.
OWNED = (
    "launcher", "attendance", "uploads", "petsy", "crm", "doctor", "clinical",
    "boarding", "grooming", "procurement", "reports", "catalog", "notifications",
    "migration", "settings", "visits", "finance", "inventory", "whatsapp",
    "accounting", "pharmacy", "imaging",
)

# Known-bad role names awaiting a product decision (see the audit report).
# `hr` and `staff` have no seeded equivalent, so renaming them would either
# remove access somebody relies on or grant access somebody should not have.
# Each entry is (relative_path, role). Fix one -> delete its line here.
PENDING_PRODUCT_DECISION = frozenset({
    ("attendance/routes.py", "hr"),
    ("launcher/routes.py", "hr"),
    ("launcher/routes.py", "staff"),
    ("uploads/routes.py", "hr"),
})


def _role_containers(tree):
    """Yield (lineno, [string values]) for every node that plausibly holds roles.

    Two shapes count:
      * a role_required(...) call — its string args are roles by definition;
      * a list/tuple/set literal holding at least two seeded role names.
    The two-role floor keeps unrelated string lists (category orders, file
    extensions) out; every real role list in this codebase starts with
    "super_admin" plus at least one more.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name == "role_required":
                yield node.lineno, [a.value for a in node.args
                                    if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                continue
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            vals = [e.value for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(vals) == len(node.elts) and sum(v in VALID_ROLES for v in vals) >= 2:
                yield node.lineno, vals


def _owned_py_files():
    for bp in OWNED:
        for root, _dirs, files in os.walk(os.path.join(BLUEPRINTS_DIR, bp)):
            for f in sorted(files):
                if f.endswith(".py"):
                    yield os.path.join(root, f)


def _scan():
    """Return {(relpath, role)} and a human-readable list of hits with line numbers."""
    found, detail = set(), []
    for path in _owned_py_files():
        rel = os.path.relpath(path, BLUEPRINTS_DIR).replace(os.sep, "/")
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for lineno, vals in _role_containers(tree):
            for v in vals:
                if v not in VALID_ROLES:
                    found.add((rel, v))
                    detail.append(f"{rel}:{lineno}  {v!r}")
    return found, detail


def test_scanner_finds_something():
    """Guard against the scanner silently matching nothing (e.g. a moved dir)."""
    assert any(_owned_py_files()), "no blueprint sources scanned — check OWNED/BLUEPRINTS_DIR"


def test_no_unknown_role_names():
    found, detail = _scan()
    new = found - PENDING_PRODUCT_DECISION
    stale = PENDING_PRODUCT_DECISION - found
    msg = []
    if new:
        msg.append(
            "Role names not in models.database._SEED_ROLES:\n  "
            + "\n  ".join(sorted(f"{f}: {r!r}" for f, r in new))
            + "\nValid roles: " + ", ".join(sorted(VALID_ROLES))
            + "\nAll hits:\n  " + "\n  ".join(sorted(detail))
        )
    if stale:
        msg.append(
            "PENDING_PRODUCT_DECISION lists names that no longer appear — "
            "delete these entries from tests/test_role_consistency.py:\n  "
            + "\n  ".join(sorted(f"{f}: {r!r}" for f, r in stale))
        )
    assert not msg, "\n\n".join(msg)


@pytest.mark.parametrize("role", sorted(VALID_ROLES))
def test_every_seeded_role_can_see_a_launcher_module(role):
    """A seeded role with zero visible modules gets a blank launcher — fail closed
    is correct for unknown roles, but a real role landing there is a config bug."""
    from blueprints.launcher.routes import _visible_modules
    assert _visible_modules(role), f"seeded role {role!r} sees no launcher modules"


def test_unknown_role_sees_nothing():
    from blueprints.launcher.routes import _visible_modules
    assert _visible_modules("") == []
    assert _visible_modules("not_a_real_role") == []
