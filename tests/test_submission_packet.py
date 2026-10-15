"""The submission folder copies the public pages and hashes those bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.pack_submission import PAGES, main, pack


def test_submission_packet_matches_the_manifest(tmp_path: Path) -> None:
    packet = pack(tmp_path)
    manifest = json.loads(Path("docs/evidence-manifest.json").read_text(encoding="utf-8"))
    assert packet["schema"] == "repairflow.submission_packet.v1"
    assert packet["stale"] is True
    assert packet["attests_commit"] == manifest["attests_commit"]
    assert packet["ci_run_id"] == manifest["ci_run_id"]
    assert packet["synaps_commit"] == manifest["synaps_commit"]
    assert packet["claim_level"] == "experiment"
    files = packet["files"]
    assert isinstance(files, list)
    assert [row["path"] for row in files] == list(PAGES)
    for row in files:
        copied = (tmp_path / row["path"]).read_bytes()
        assert b"\r\n" not in copied
        assert hashlib.sha256(copied).hexdigest() == row["sha256"]
        source = Path(row["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert copied == source
    written = json.loads((tmp_path / "PACKET.json").read_text(encoding="utf-8"))
    assert written["attests_commit"] == packet["attests_commit"]
    assert main(["--out", str(tmp_path / "again")]) == 0


def test_submission_packet_refuses_a_fresh_manifest(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    manifest = json.loads(Path("docs/evidence-manifest.json").read_text(encoding="utf-8"))
    manifest["stale"] = False
    (root / "docs" / "evidence-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for relative in PAGES:
        if relative == "docs/evidence-manifest.json":
            continue
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    try:
        pack(tmp_path / "out", root)
    except ValueError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("a fresh manifest must not pack")
