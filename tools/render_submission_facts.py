"""Rewrite docs/submission-facts.md and the living attestation clauses.

The command reads the manifest and the two campaign files. It does not call
the network and it does not invent a sentence outside that sheet.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repairflow.submission_facts import refresh_generated_facts  # noqa: E402


def main() -> int:
    refresh_generated_facts(ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
