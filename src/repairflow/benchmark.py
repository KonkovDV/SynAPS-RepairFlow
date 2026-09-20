"""Portfolio benchmark: FIFO vs GREED across preset/seed combinations.

Data provenance: synthetic. Claim level: experiment.
Not SVARZ depot data; not a production pilot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repairflow.evidence import evidence_stamp, fingerprint_payload
from repairflow.model import RepairFlowProblem, RepairFlowResult
from repairflow.planner import plan
from repairflow.report import render_html, render_markdown
from repairflow.synthetic import synthesize
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT


@dataclass
class BenchmarkRow:
    preset: str
    seed: int
    solver: str
    status: str
    verified: bool
    exit_code: int
    violations: int
    coverage: float | None
    makespan_min: int | None
    input_hash: str
    config_hash: str


@dataclass
class BenchmarkSummary:
    repairflow_version: str
    synaps_commit: str
    rows: list[BenchmarkRow] = field(default_factory=list)

    def greed_gain_minutes(self) -> float | None:
        """Mean makespan reduction of GREED vs FIFO across matched (preset, seed) pairs."""
        fifo: dict[tuple[str, int], int] = {
            (r.preset, r.seed): r.makespan_min
            for r in self.rows
            if r.solver == "FIFO" and r.makespan_min is not None
        }
        greed: dict[tuple[str, int], int] = {
            (r.preset, r.seed): r.makespan_min
            for r in self.rows
            if r.solver == "GREED" and r.makespan_min is not None
        }
        deltas = [fifo[k] - greed[k] for k in fifo if k in greed]
        return round(sum(deltas) / len(deltas), 1) if deltas else None

    def verified_ratio(self) -> float:
        """Fraction of GREED runs that pass the independent checker (exit 0)."""
        greed_rows = [r for r in self.rows if r.solver == "GREED"]
        if not greed_rows:
            return 0.0
        return round(sum(1 for r in greed_rows if r.verified) / len(greed_rows), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repairflow_version": self.repairflow_version,
            "synaps_commit": self.synaps_commit,
            "greed_gain_minutes": self.greed_gain_minutes(),
            "greed_verified_ratio": self.verified_ratio(),
            "rows": [r.__dict__ for r in self.rows],
        }


# Default benchmark matrix: (preset, seed)
_DEFAULT_MATRIX: list[tuple[str, int]] = [
    ("tiny", 1),
    ("tiny", 42),
    ("tiny", 99),
    ("repair-site-mvp", 42),
    ("repair-site-mvp", 7),
    ("repair-site-mvp", 13),
]


def run_benchmark(
    *,
    matrix: list[tuple[str, int]] | None = None,
    solvers: list[str] | None = None,
    out_dir: Path | None = None,
) -> BenchmarkSummary:
    """Run FIFO+GREED on each (preset, seed) pair and collect metrics.

    Args:
        matrix: List of (preset, seed) pairs. Defaults to _DEFAULT_MATRIX.
        solvers: Solver config names to run. Defaults to ["FIFO", "GREED"].
        out_dir: If given, write benchmark.json / .md / .html + per-instance
                 reports into this directory.

    Returns:
        BenchmarkSummary with aggregated KPIs and per-run rows.
    """
    matrix = matrix or _DEFAULT_MATRIX
    solvers = solvers or ["FIFO", "GREED"]
    summary = BenchmarkSummary(
        repairflow_version=REPAIRFLOW_VERSION,
        synaps_commit=SYNAPS_COMMIT,
    )

    problems: dict[tuple[str, int], RepairFlowProblem] = {}
    results: dict[tuple[str, int, str], RepairFlowResult] = {}

    for preset, seed in matrix:
        problem = synthesize(preset, seed=seed)
        problems[(preset, seed)] = problem
        for solver in solvers:
            outcome = plan(problem, solver_config=solver)
            result = outcome.result
            results[(preset, seed, solver)] = result
            obj = result.objective
            summary.rows.append(
                BenchmarkRow(
                    preset=preset,
                    seed=seed,
                    solver=solver,
                    status=result.status.value,
                    verified=result.verified_feasible,
                    exit_code=result.exit_code,
                    violations=len(result.violations),
                    coverage=obj.get("coverage"),
                    makespan_min=obj.get("makespan_minutes"),
                    input_hash=result.input_hash,
                    config_hash=result.config_hash,
                )
            )

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_dict = summary.to_dict()
        summary_dict["evidence"] = evidence_stamp(
            input_hash=fingerprint_payload([r.input_hash for r in summary.rows]),
            config_hash=fingerprint_payload([r.config_hash for r in summary.rows]),
            data_provenance="synthetic",
        )
        (out_dir / "benchmark.json").write_text(
            json.dumps(summary_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / "benchmark.md").write_text(
            _render_markdown(summary), encoding="utf-8"
        )
        (out_dir / "benchmark.html").write_text(
            _render_html(summary), encoding="utf-8"
        )
        # Per-instance HTML + Markdown reports
        for (preset, seed, solver), result in results.items():
            problem = problems[(preset, seed)]
            slug = f"{preset}-seed{seed}-{solver.lower()}"
            (out_dir / f"{slug}.html").write_text(
                render_html(problem, result), encoding="utf-8"
            )
            (out_dir / f"{slug}.md").write_text(
                render_markdown(problem, result), encoding="utf-8"
            )

    return summary


def _render_markdown(summary: BenchmarkSummary) -> str:
    gain = summary.greed_gain_minutes()
    verified = summary.verified_ratio()
    lines = [
        "# RepairFlow Benchmark Report",
        "",
        f"- RepairFlow {summary.repairflow_version}"
        f" \u00b7 SynAPS `{summary.synaps_commit}`",
        f"- GREED gain vs FIFO: **{gain} min** (mean makespan reduction)",
        f"- GREED verified ratio: **{verified:.1%}**",
        "",
        "| preset | seed | solver | status | verified"
        " | violations | coverage | makespan_min |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in summary.rows:
        cov = str(r.coverage) if r.coverage is not None else "\u2014"
        mksp = str(r.makespan_min) if r.makespan_min is not None else "\u2014"
        lines.append(
            f"| {r.preset} | {r.seed} | {r.solver} | {r.status}"
            f" | {r.verified} | {r.violations} | {cov} | {mksp} |"
        )
    lines.extend(
        [
            "",
            "## Claim limits",
            "",
            "- Synthetic data only; not SVARZ depot data.",
            "- GREED and FIFO are heuristics; OPTIMAL applies"
            " only when CP-SAT proves it.",
            "- Independent checker validates hard constraints;"
            " not a production deployment.",
        ]
    )
    return "\n".join(lines)


def _render_html(summary: BenchmarkSummary) -> str:
    from html import escape

    gain = summary.greed_gain_minutes()
    verified = summary.verified_ratio()
    rows_html = "".join(
        "<tr>"
        f"<td>{escape(r.preset)}</td>"
        f"<td>{r.seed}</td>"
        f"<td>{escape(r.solver)}</td>"
        f"<td>{escape(r.status)}</td>"
        f"<td>{'\u2713' if r.verified else '\u2717'}</td>"
        f"<td>{r.violations}</td>"
        f"<td>{r.coverage if r.coverage is not None else '\u2014'}</td>"
        f"<td>{r.makespan_min if r.makespan_min is not None else '\u2014'}</td>"
        "</tr>"
        for r in summary.rows
    )
    gain_str = f"{gain} min" if gain is not None else "n/a"
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>RepairFlow Benchmark</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#0d1117;color:#c9d1d9;margin:24px}}
h1{{color:#f0f6fc}}
.kpi{{display:flex;gap:24px;margin:16px 0;flex-wrap:wrap}}
.kpi-card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px 24px}}
.kpi-val{{font-size:2em;font-weight:700;color:#58a6ff}}
.kpi-lab{{font-size:.85em;color:#8b949e}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #21262d;padding:6px 10px;text-align:left}}
th{{background:#161b22}}
tr:hover{{background:#1c2128}}
.note{{color:#8b949e;margin-top:24px;font-size:.85em}}
</style></head><body>
<h1>RepairFlow Benchmark</h1>
<p>RepairFlow {escape(summary.repairflow_version)}
\u00b7 SynAPS <code>{escape(summary.synaps_commit[:12])}</code></p>
<div class="kpi">
  <div class="kpi-card">
    <div class="kpi-val">{escape(gain_str)}</div>
    <div class="kpi-lab">GREED gain vs FIFO (mean makespan reduction)</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{verified:.0%}</div>
    <div class="kpi-lab">GREED checker-verified ratio</div>
  </div>
</div>
<table>
<thead><tr>
  <th>preset</th><th>seed</th><th>solver</th><th>status</th>
  <th>verified</th><th>violations</th><th>coverage</th><th>makespan_min</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
<p class="note">Synthetic data only. Not SVARZ data or a production pilot.
Heuristic solvers (FIFO, GREED) are not called optimal.</p>
</body></html>
"""
