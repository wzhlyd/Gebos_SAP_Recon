"""
Unified Reconciliation: runs UGB and/or IFRS reconciliation + report generation.

Usage:
  python src/reconcile.py          # runs both UGB and IFRS
  python src/reconcile.py ugb      # runs UGB only
  python src/reconcile.py ifrs     # runs IFRS only

Each run performs:
  1. Reconciliation (reconcile_ugb / reconcile_ifrs)
  2. Report generation (generate_report)
"""

import sys
from pathlib import Path

# Ensure src/ is on the path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reconcile_ugb
import reconcile_ifrs
import generate_report


def run_ugb():
    print("=" * 60)
    print("  UGB Reconciliation")
    print("=" * 60)
    reconcile_ugb.main()
    print()
    generate_report.generate_report("ugb")
    print()


def run_ifrs():
    print("=" * 60)
    print("  IFRS Reconciliation")
    print("=" * 60)
    reconcile_ifrs.main()
    print()
    generate_report.generate_report("ifrs")
    print()


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "both"

    if mode == "ugb":
        run_ugb()
    elif mode == "ifrs":
        run_ifrs()
    elif mode == "both":
        run_ugb()
        run_ifrs()
    else:
        print(f"ERROR: Unknown mode '{mode}'. Use: ugb, ifrs, or both")
        sys.exit(1)

    print("All done.")


if __name__ == "__main__":
    main()
