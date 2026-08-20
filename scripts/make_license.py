# -*- coding: utf-8 -*-
"""Issue activation codes. VENDOR SIDE ONLY - never install this at a clinic.

THE THREE THINGS YOU WILL EVER DO WITH IT

  1. Once, ever - create your master secret:

         python scripts/make_license.py --init

     Store what it prints in a password manager AND somewhere that survives
     your laptop dying. Read the warning it prints. Lose this and you can never
     issue a code again, for any clinic, including ones already paying you.

  2. When you install at a new clinic - make their own secret:

         python scripts/make_license.py --derive --clinic hatem-vet

     Put the line it prints into THAT CLINIC'S .env file. Not into git.

  3. When a clinic phones for a code - at install, and once a year after:

         python scripts/make_license.py --clinic hatem-vet --machine ALF-7706-4095

     Read the code back to them. It works on that machine and no other.

The master secret is read from ALEEFY_LICENSE_MASTER. Set it in your shell,
never on a clinic machine, and never in this repository.
"""
import argparse
import os
import secrets
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import licensing as lic   # noqa: E402


def _master() -> str:
    m = (os.environ.get("ALEEFY_LICENSE_MASTER") or "").strip()
    if not m:
        print("ALEEFY_LICENSE_MASTER is not set in this shell.\n")
        print("If you have it, set it for this session:")
        print("   PowerShell : $env:ALEEFY_LICENSE_MASTER = '...'")
        print("   bash       : export ALEEFY_LICENSE_MASTER='...'")
        print("\nIf you have never made one:  python scripts/make_license.py --init")
        sys.exit(2)
    return m


def _plus_years(n: int) -> date:
    t = date.today()
    # End of the same month, n years out. Whole months keep the code short and
    # give the clinic the rest of the month rather than an awkward mid-month date.
    year, month = t.year + n, t.month
    return lic._end_of_month(year, month)


def main():
    ap = argparse.ArgumentParser(
        description="Issue Aleefy activation codes (vendor only).")
    ap.add_argument("--init", action="store_true",
                    help="create a new master secret (do this once, ever)")
    ap.add_argument("--derive", action="store_true",
                    help="print the .env line for one clinic's own secret")
    ap.add_argument("--clinic", default="",
                    help="clinic id, e.g. hatem-vet. Must match every time for "
                         "that clinic or their codes will stop working.")
    ap.add_argument("--machine", default="",
                    help="the ALF-xxxx-xxxx code the clinic reads to you")
    ap.add_argument("--years", type=int, default=1,
                    help="how long the code lasts (default 1)")
    args = ap.parse_args()

    if args.init:
        m = secrets.token_urlsafe(48)
        print("Your master secret:\n")
        print("    %s\n" % m)
        print("BEFORE YOU CLOSE THIS WINDOW:")
        print("  - Save it in a password manager.")
        print("  - Save a SECOND copy somewhere that survives your laptop dying.")
        print("  - It must never go into git, into a clinic's .env, or into a")
        print("    WhatsApp message.")
        print("\nIf it leaks, anybody can mint codes for every clinic and you")
        print("cannot revoke them. If you lose it, you can never issue another")
        print("code for anyone - including clinics already paying you.")
        return 0

    if args.derive:
        if not args.clinic:
            print("--derive needs --clinic <id>")
            return 2
        s = lic.derive_clinic_secret(_master(), args.clinic)
        print("Put this line in %s's .env file (which is gitignored):\n" % args.clinic)
        print("    ALEEFY_LICENSE_SECRET=%s\n" % s)
        print("Their .env only. Each clinic gets a different one, so a secret")
        print("taken from one installation is useless at any other.")
        return 0

    if not args.clinic or not args.machine:
        ap.print_help()
        print("\nExample:")
        print("  python scripts/make_license.py --clinic hatem-vet "
              "--machine ALF-7706-4095")
        return 2

    # Accept whatever they read out: ALF-7706-4095, alf 7706 4095, 77064095.
    machine = "".join(ch for ch in args.machine if ch.isdigit())
    if len(machine) != 8:
        print("That machine code does not look right: %r" % args.machine)
        print("Expected something like ALF-7706-4095 (eight digits).")
        return 2

    secret = lic.derive_clinic_secret(_master(), args.clinic).encode("utf-8")
    expiry = _plus_years(args.years)
    code = lic.make_code(secret, machine, expiry)

    print("")
    print("  Clinic   : %s" % args.clinic)
    print("  Machine  : ALF-%s-%s" % (machine[:4], machine[4:]))
    print("  Valid to : %s" % expiry.strftime("%d %B %Y"))
    print("")
    print("  READ THIS BACK TO THEM:   %s" % code)
    print("")
    print("  It only works on that machine. Diary a reminder to call them in")
    print("  %d month%s, one month before it lapses."
          % (args.years * 12 - 1, "" if args.years * 12 - 1 == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
