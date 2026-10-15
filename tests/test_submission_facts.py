"""The fact sheet and the living attestation clauses come from the manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repairflow.submission_facts import (
    ATTEST_BEGIN,
    ATTEST_END,
    attest_core_clause,
    attest_murder_clause,
    load_facts,
    render_submission_facts,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_submission_facts_match_the_committed_sheet() -> None:
    rendered = load_facts(_ROOT)
    stored = (_ROOT / "docs" / "submission-facts.md").read_text(encoding="utf-8")
    assert stored.replace("\r\n", "\n") == rendered
    assert "false_accept 0" in rendered
    manifest = json.loads((_ROOT / "docs" / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert manifest["attests_commit"] in rendered
    assert manifest["ci_run_id"] in rendered


def test_living_attest_clauses_match_the_manifest() -> None:
    manifest = json.loads((_ROOT / "docs" / "evidence-manifest.json").read_text(encoding="utf-8"))
    core = (_ROOT / "docs" / "core-compat.md").read_text(encoding="utf-8")
    board = (_ROOT / "docs" / "murder-board.md").read_text(encoding="utf-8")
    assert _marked(core) == attest_core_clause(manifest)
    assert _marked(board) == attest_murder_clause(manifest)


def test_facts_refuse_a_manifest_that_is_not_stale() -> None:
    manifest = json.loads((_ROOT / "docs" / "evidence-manifest.json").read_text(encoding="utf-8"))
    campaign = json.loads((_ROOT / "docs" / "fault-campaign.json").read_text(encoding="utf-8"))
    disruption = json.loads((_ROOT / "docs" / "disruption-campaign.json").read_text(encoding="utf-8"))
    manifest["stale"] = False
    with pytest.raises(ValueError, match="stale"):
        render_submission_facts(manifest, campaign, disruption)


def _marked(text: str) -> str:
    return text.split(ATTEST_BEGIN, 1)[1].split(ATTEST_END, 1)[0]
