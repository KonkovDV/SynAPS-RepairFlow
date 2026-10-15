"""Copy the submission pages into one folder and hash them.

The prose stays where it was written. This command does not invent a result,
a score, or a new sentence. `stale` stays true: the manifest names an earlier
commit than the one that will contain this folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "README.md",
    "APPLICATION.md",
    "docs/jury-demo.md",
    "docs/traceability-matrix.md",
    "docs/murder-board.md",
    "docs/limitations.md",
    "docs/submission-facts.md",
    "docs/evidence-manifest.json",
    "docs/fault-campaign.json",
)


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def pack(out_dir: Path, root: Path | None = None) -> dict[str, object]:
    root = ROOT if root is None else root
    manifest_path = root / "docs" / "evidence-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    commit = manifest.get("attests_commit")
    run_id = manifest.get("ci_run_id")
    if manifest.get("stale") is not True:
        raise ValueError("evidence manifest must stay stale")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("evidence manifest has no attested commit")
    if not isinstance(run_id, str) or not run_id.isdigit():
        raise ValueError("evidence manifest has no CI run id")
    rows: list[dict[str, str]] = []
    for relative in PAGES:
        source = root / relative
        if not source.is_file():
            raise ValueError(f"missing submission page: {relative}")
        payload = _lf(source.read_bytes())
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        rows.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    packet = {
        "schema": "repairflow.submission_packet.v1",
        "attests_commit": commit,
        "ci_run_id": run_id,
        "ci_run_url": manifest.get("ci_run_url"),
        "synaps_commit": manifest.get("synaps_commit"),
        "claim_level": manifest.get("claim_level"),
        "stale": True,
        "files": rows,
    }
    (out_dir / "PACKET.json").write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out") / "submission")
    args = parser.parse_args(argv)
    try:
        packet = pack(args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"pack-submission: {exc}\n")
        return 1
    files = packet["files"]
    assert isinstance(files, list)
    sys.stdout.write(f"submission {packet['attests_commit']} files={len(files)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
