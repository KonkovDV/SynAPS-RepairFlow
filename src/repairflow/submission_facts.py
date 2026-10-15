"""Render the submission fact sheet and the living attestation clauses.

The numbers come from the manifest and the two campaign files. This module
does not invent a result, and it does not rewrite the demo script.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ATTEST_BEGIN = "<!-- attest:begin -->"
ATTEST_END = "<!-- attest:end -->"

_CLAUSE_FILES = ("docs/core-compat.md", "docs/murder-board.md")


def render_submission_facts(
    manifest: dict[str, Any],
    campaign: dict[str, Any],
    disruption: dict[str, Any],
) -> str:
    """One fact sheet. Every figure is a field of the three documents."""

    if manifest.get("stale") is not True:
        raise ValueError("evidence manifest must stay stale")
    if manifest.get("ci_result") != "success" or manifest.get("ci_includes_test_slow") is not True:
        raise ValueError("facts require a successful push that includes test-slow")
    commit = str(manifest["attests_commit"])
    run_id = str(manifest["ci_run_id"])
    pin = str(manifest["synaps_commit"])
    rows = [
        "# Сводка подачи",
        "",
        "Эту страницу пишет `tools/render_submission_facts.py` из манифеста и двух кампаний.",
        "Руками её не правят. Это не рассказ показа и не заявление об экономии.",
        "",
        "| Факт | Значение |",
        "| --- | --- |",
        f"| Проверенный коммит | `{commit}` |",
        f"| Push-прогон | `{run_id}`, {manifest['ci_result']}, включая `test-slow` |",
        f"| Манифест отстаёт от HEAD | {'да' if manifest['stale'] else 'нет'} |",
        f"| Заявление | `{manifest['claim_level']}` |",
        f"| Зрелость | TRL {manifest['trl']} |",
        f"| Пин SynAPS | `{pin}` |",
        (
            "| Кампания порчи | "
            f"checked {campaign['checked']}, false_accept {campaign['false_accept']}, "
            f"false_reject {campaign['false_reject']} |"
        ),
        (
            "| Кампания сбоев | "
            f"checked {disruption['checked']}, false_accept {disruption['false_accept']}, "
            f"replanned {disruption['replanned']}, пресет `{disruption['preset']}` |"
        ),
        "",
        "Кампания порчи на этой странице — префикс из `docs/fault-campaign.json`.",
        "Полный локальный прогон сюда не копируется.",
        "Кампания сбоев — `docs/disruption-campaign.json`.",
        "Сам коммит, который записывает эту страницу, себя не аттестует.",
        "",
    ]
    return "\n".join(rows)


def attest_core_clause(manifest: dict[str, Any]) -> str:
    short = str(manifest["attests_commit"])[:7]
    return f"Манифест доказательств аттестует RepairFlow `{short}`:"


def attest_murder_clause(manifest: dict[str, Any]) -> str:
    short = str(manifest["attests_commit"])[:7]
    run_id = str(manifest["ci_run_id"])
    return f"Манифест аттестует `{short}` по push-прогону `{run_id}`, включая `test-slow`."


def replace_attest_clause(text: str, clause: str) -> str:
    if text.count(ATTEST_BEGIN) != 1 or text.count(ATTEST_END) != 1:
        raise ValueError("a page needs one attest marker pair")
    head, rest = text.split(ATTEST_BEGIN, 1)
    _, tail = rest.split(ATTEST_END, 1)
    return f"{head}{ATTEST_BEGIN}{clause}{ATTEST_END}{tail}"


def load_facts(root: Path) -> str:
    manifest = json.loads((root / "docs" / "evidence-manifest.json").read_text(encoding="utf-8"))
    campaign = json.loads((root / "docs" / "fault-campaign.json").read_text(encoding="utf-8"))
    disruption = json.loads((root / "docs" / "disruption-campaign.json").read_text(encoding="utf-8"))
    return render_submission_facts(manifest, campaign, disruption)


def refresh_generated_facts(root: Path) -> None:
    """Rewrite the fact sheet and the two living attestation clauses."""

    manifest = json.loads((root / "docs" / "evidence-manifest.json").read_text(encoding="utf-8"))
    facts = load_facts(root)
    (root / "docs" / "submission-facts.md").write_text(facts, encoding="utf-8", newline="\n")
    clauses = {
        "docs/core-compat.md": attest_core_clause(manifest),
        "docs/murder-board.md": attest_murder_clause(manifest),
    }
    for relative in _CLAUSE_FILES:
        path = root / relative
        text = path.read_text(encoding="utf-8")
        path.write_text(replace_attest_clause(text, clauses[relative]), encoding="utf-8", newline="\n")
