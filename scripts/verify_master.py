# -*- coding: utf-8 -*-
"""Check that a licence master secret is the right one, without printing it.

The master mints activation codes for every clinic ever sold. Losing it means
never issuing another code for anybody, including customers already paying;
leaking it means anybody can mint unlimited codes and they cannot be revoked.
So it lives in more than one place - and a copy you cannot verify is not a
backup, it is a hope.

This compares a copy against a recorded FINGERPRINT: a truncated SHA-256, which
proves a copy is correct without revealing a single character of it. The
fingerprint below is therefore safe to keep in the repository, and is the one
thing about the master that ever should be.

    python scripts/verify_master.py                      # the default location
    python scripts/verify_master.py D:/aleefy-vault/master.txt
    python scripts/verify_master.py --record             # after rotating it
"""
import hashlib
import io
import os
import sys

# Fingerprint of the current master. A hash, not the secret - see above.
# Regenerate with --record if the master is ever rotated.
EXPECTED = "F94D3F783ED350AB"

DEFAULT = os.path.join(os.path.expanduser("~"), ".aleefy", "master.txt")

# Places a copy is meant to live. Checked when no path is given.
KNOWN_COPIES = [
    DEFAULT,
    "D:/aleefy-vault/master.txt",
]


def fingerprint(path):
    try:
        m = io.open(path, encoding="utf-8").read().strip()
    except OSError:
        return None, None
    if not m:
        return "", None
    return m, hashlib.sha256(m.encode("utf-8")).hexdigest()[:16].upper()


def main():
    args = [a for a in sys.argv[1:] if a != "--record"]
    record = "--record" in sys.argv[1:]

    paths = args or KNOWN_COPIES
    results = []
    for p in paths:
        secret, fp = fingerprint(p)
        results.append((p, secret, fp))

    if record:
        good = [r for r in results if r[2]]
        if not good:
            print("Nothing readable to record a fingerprint from.")
            return 2
        print("Put this in scripts/verify_master.py:\n")
        print('    EXPECTED = "%s"\n' % good[0][2])
        print("It is a hash, not the secret, and is safe to commit.")
        return 0

    ok = 0
    print("Expected fingerprint: %s\n" % EXPECTED)
    for p, secret, fp in results:
        if fp is None:
            print("  MISSING   %s" % p)
        elif not secret:
            print("  EMPTY     %s" % p)
        elif fp == EXPECTED:
            print("  ok        %s" % p)
            ok += 1
        else:
            print("  MISMATCH  %s  (has %s)" % (p, fp))

    print("")
    if ok == 0:
        print("NO GOOD COPY FOUND. If every copy is gone, no activation code can")
        print("ever be issued again - for any clinic, including paying ones.")
        return 1
    if ok == 1:
        print("Only ONE good copy. That is a single disk away from losing the")
        print("ability to license anything, ever. Add another.")
        return 0

    print("%d good copies." % ok)
    print("")
    print("Both are still on this machine, so a theft or a fire takes both.")
    print("A password manager entry and a line on paper are the copies that")
    print("actually survive - and only you can make those.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
