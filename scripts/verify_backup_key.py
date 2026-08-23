# -*- coding: utf-8 -*-
"""Make, and prove, the key that off-site backups are encrypted with.

    python scripts/verify_backup_key.py --init      # once, per clinic
    python scripts/verify_backup_key.py             # prove it still works
    python scripts/verify_backup_key.py --check-latest

WHY THIS EXISTS

An off-site backup leaves the building - onto somebody else's storage, or onto
a USB stick that travels in a pocket. It holds every patient record, every
client's phone number and every invoice the clinic has ever raised, so it is
encrypted before it goes.

Which creates the failure that actually loses data: a key nobody ever tested.
The backups run nightly, the dashboard is green for a year, and the first time
anyone tries the key is the morning the disk died. That is the worst possible
moment to discover it was copied wrong.

So: run this after setting the key, and again whenever you change it. It does a
real round trip - encrypt, decrypt, compare - and with --check-latest it does
that against the actual newest archive rather than a sample.

The LOCAL backup is deliberately NOT encrypted. It sits on the clinic's own
disk beside the database it came from, and an encrypted local backup whose key
has been lost is not a backup at all.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)


def _init() -> int:
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    print("Your backup encryption key:\n")
    print("    %s\n" % key)
    print("PUT IT IN TWO PLACES BEFORE YOU CLOSE THIS WINDOW:")
    print("  1. the clinic's .env, as:")
    print("       BACKUP_ENCRYPTION_KEY=%s" % key)
    print("  2. your password manager - NOT only on the clinic's computer.")
    print("")
    print("If the clinic's disk dies and this key died with it, the off-site")
    print("backups it has been faithfully uploading all year cannot be opened")
    print("by anyone, including you. The key must not live only in the place")
    print("the backup exists to survive.")
    print("")
    print("Then prove it works:  python scripts/verify_backup_key.py")
    return 0


def _round_trip() -> int:
    from models import backup as bk

    key = bk.encryption_key()
    if not key:
        print("BACKUP_ENCRYPTION_KEY is not set in this environment.\n")
        print("Off-site copies are NOT being sent while it is missing - the")
        print("nightly backup refuses to put patient records on somebody")
        print("else's storage in the clear, and says so in the log.")
        print("")
        print("Make one:  python scripts/verify_backup_key.py --init")
        return 1

    import tempfile
    sample = os.urandom(64_000)          # about the size of a small clinic db
    tmp = tempfile.mkdtemp(prefix="aleefy-keycheck-")
    plain = os.path.join(tmp, "sample.db")
    with open(plain, "wb") as fh:
        fh.write(sample)
    try:
        enc = bk._encrypt_for_offsite(plain)
        if open(enc, "rb").read() == sample:
            print("REFUSING TO PASS: the 'encrypted' file is identical to the")
            print("plaintext. Nothing is being protected.")
            return 1
        back = bk.decrypt_archive(enc, os.path.join(tmp, "restored.db"))
        ok = open(back, "rb").read() == sample
    except Exception as exc:
        print("The key did not survive a round trip: %s" % exc)
        return 1
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if not ok:
        print("Decryption produced DIFFERENT bytes. Do not trust this key.")
        return 1

    print("  key length     : %d chars" % len(key.decode()))
    print("  encrypt        : ok  (ciphertext differs from the plaintext)")
    print("  decrypt        : ok  (byte-for-byte identical)")
    print("")
    print("  This key can open what it seals. Confirm it is also in your")
    print("  password manager, and not only on the clinic's computer.")
    return 0


def _check_latest() -> int:
    """Round-trip the newest REAL archive, not a sample."""
    from app import create_app
    from config import Config
    from models import backup as bk

    app = create_app(Config)
    with app.app_context():
        latest = bk.get_latest_backup()
        if not latest:
            print("No backup exists yet to check.")
            return 1
        path = bk.resolve_archive(latest["filename"])
        if not path or not os.path.exists(path):
            print("The newest backup is listed but not on disk: %s"
                  % latest["filename"])
            return 1

        print("  archive : %s (%s)" % (latest["filename"],
                                       latest.get("size_human", "?")))
        if not bk.encryption_key():
            print("  BACKUP_ENCRYPTION_KEY is not set - cannot check.")
            return 1
        try:
            enc = bk._encrypt_for_offsite(path)
            back = bk.decrypt_archive(enc, path + ".keycheck")
            same = open(back, "rb").read() == open(path, "rb").read()
        except Exception as exc:
            print("  FAILED: %s" % exc)
            return 1
        finally:
            for leftover in (path + bk.ENCRYPTED_SUFFIX, path + ".keycheck"):
                try:
                    if os.path.exists(leftover):
                        os.remove(leftover)
                except OSError:
                    pass

        if not same:
            print("  FAILED: the round trip changed the archive.")
            return 1
        print("  round trip : ok - this key opens the real backup")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true",
                    help="generate a new key (do this once, per clinic)")
    ap.add_argument("--check-latest", action="store_true",
                    help="round-trip the newest real archive, not a sample")
    a = ap.parse_args()

    if a.init:
        return _init()
    if a.check_latest:
        return _check_latest()
    return _round_trip()


if __name__ == "__main__":
    sys.exit(main())
