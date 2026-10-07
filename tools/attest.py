"""Record a checked main commit in the evidence manifest and re-render the README table.

Run this only after the commit's own push CI succeeded, including test-slow.
The script does not call the network. The manifest is committed after the
commit it names, so it is always behind HEAD and `stale` is always true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repairflow.attestation import render_attestation_markdown  # noqa: E402
from repairflow.versions import SYNAPS_COMMIT  # noqa: E402

MANIFEST = ROOT / "docs" / "evidence-manifest.json"
README = ROOT / "README.md"
BENCHMARK = ROOT / "benchmark" / "results" / "benchmark.json"
CAMPAIGN = ROOT / "docs" / "fault-campaign.json"
RUN_URL = "https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/"
BEGIN = "<!-- evidence:begin -->"
END = "<!-- evidence:end -->"
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def render_readme() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    table = render_attestation_markdown(manifest, benchmark_sha256=_lf_sha256(BENCHMARK), campaign=campaign)
    text = README.read_text(encoding="utf-8")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    README.write_text(head + BEGIN + "\n" + table + END + tail, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", help="full SHA of the checked main commit")
    parser.add_argument("--run-id", help="id of that commit's own push CI run")
    parser.add_argument(
        "--render-only", action="store_true", help="re-render README from the current manifest"
    )
    args = parser.parse_args()
    if args.render_only:
        render_readme()
        return 0
    if not args.commit or not args.run_id:
        parser.error("--commit and --run-id are required unless --render-only is set")
    if not _SHA.fullmatch(args.commit):
        parser.error("--commit must be a full 40-character lowercase SHA")
    if not args.run_id.isdigit():
        parser.error("--run-id must be numeric")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest.update(
        {
            "attests_commit": args.commit,
            "ci_run_id": args.run_id,
            "ci_run_url": RUN_URL + args.run_id,
            "ci_result": "success",
            "ci_includes_test_slow": True,
            "stale": True,
            "synaps_commit": SYNAPS_COMMIT,
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    render_readme()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
