"""One-command MVP runner used by docs and CI notes."""

from __future__ import annotations

import sys
from pathlib import Path

from repairflow.cli import main


def run() -> int:
    out = Path("benchmark") / "results" / "mvp"
    return main(["demo", "--out", str(out)])


if __name__ == "__main__":
    raise SystemExit(run() if not sys.argv[1:] else main(sys.argv[1:]))
