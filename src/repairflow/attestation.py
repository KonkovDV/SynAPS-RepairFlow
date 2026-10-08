"""Render the README evidence table from committed attestation files."""

from __future__ import annotations

from typing import Any

from repairflow.sbom import PINNED_ORTOOLS

_REPAIRFLOW_REPO = "https://github.com/KonkovDV/SynAPS-RepairFlow"
_SYNAPS_REPO = "https://github.com/KonkovDV/SynAPS"


def render_attestation_markdown(
    manifest: dict[str, Any],
    *,
    benchmark_sha256: str,
    campaign: dict[str, Any],
) -> str:
    commit = str(manifest["attests_commit"])
    run_id = str(manifest["ci_run_id"])
    pin = str(manifest["synaps_commit"])
    sweep = str(manifest["sweep_line_commit"])
    behind = "да" if manifest["stale"] else "нет"
    rows = [
        "| Факт | Значение |",
        "|---|---|",
        f"| Проверенный `main` | [`{commit[:7]}`]({_REPAIRFLOW_REPO}/commit/{commit}) |",
        (
            f"| CI для этого `main` | [Actions run {run_id}]"
            f"({_REPAIRFLOW_REPO}/actions/runs/{run_id}), "
            f"{manifest['ci_result']}, включая `test-slow` |"
        ),
        f"| Sweep-line commit | [`{sweep[:7]}`]({_REPAIRFLOW_REPO}/commit/{sweep}) |",
        f"| SynAPS pin | [`{pin[:7]}`]({_SYNAPS_REPO}/commit/{pin}) |",
        f"| Solver | `ortools=={PINNED_ORTOOLS}` |",
        (
            "| Benchmark | "
            f"[`benchmark/results/benchmark.json`](benchmark/results/benchmark.json), "
            f"SHA-256 `{benchmark_sha256}`, claim `{manifest['claim_level']}` |"
        ),
        (
            "| Fault campaign | "
            f"checked {campaign['checked']}, false_accept {campaign['false_accept']}, "
            f"false_reject {campaign['false_reject']}, "
            f"presets `{', '.join(str(item) for item in campaign['presets'])}`, "
            f"solvers `{', '.join(str(item) for item in campaign['solvers'])}` |"
        ),
        f"| Манифест отстаёт от HEAD | {behind} |",
        "| Данные | committed synthetic fixtures; customer data отсутствуют |",
        "| Зрелость | laboratory fixture / TRL 4; не pilot result |",
    ]
    return "\n".join(rows) + "\n"
