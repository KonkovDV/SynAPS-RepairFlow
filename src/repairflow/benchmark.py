"""Portfolio benchmark: FIFO vs GREED across preset/seed combinations.

Data provenance: synthetic. Claim level: experiment.
Not SVARZ depot data; not a production pilot.

FIFO is an intentionally infeasible compact packing. A shorter FIFO makespan
is not a quality win; GREED is scored by independent checker exit 0.
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

# Documented synthetic portfolio. Frozen JOB-01-03 binds a crew that holds the op skills.
DEFAULT_MATRIX: list[tuple[str, int]] = [
    ("tiny", 1),
    ("tiny", 42),
    ("tiny", 99),
    ("repair-site-mvp", 42),
    ("repair-site-mvp", 7),
    ("repair-site-mvp", 13),
]

MAKESPAN_NOTE = "FIFO is an infeasible compact packing; a shorter FIFO makespan is not a quality win."


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


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
    makespan_min: float | None
    input_hash: str
    config_hash: str
    result_hash: str


@dataclass
class BenchmarkSummary:
    repairflow_version: str
    synaps_commit: str
    rows: list[BenchmarkRow] = field(default_factory=list)

    def _solver_rows(self, solver: str) -> list[BenchmarkRow]:
        return [row for row in self.rows if row.solver == solver]

    def verified_ratio(self) -> float:
        """Fraction of GREED runs that pass the independent checker (exit 0)."""
        greed_rows = self._solver_rows("GREED")
        if not greed_rows:
            return 0.0
        return round(sum(1 for row in greed_rows if row.verified) / len(greed_rows), 3)

    def fifo_mean_violations(self) -> float | None:
        fifo_rows = self._solver_rows("FIFO")
        if not fifo_rows:
            return None
        return round(sum(row.violations for row in fifo_rows) / len(fifo_rows), 1)

    def greed_mean_makespan(self) -> float | None:
        return _mean([row.makespan_min for row in self._solver_rows("GREED") if row.makespan_min is not None])

    def fifo_mean_makespan(self) -> float | None:
        return _mean([row.makespan_min for row in self._solver_rows("FIFO") if row.makespan_min is not None])

    def fifo_minus_greed_makespan(self) -> float | None:
        """FIFO minus GREED makespan. Negative is expected because FIFO is infeasible."""
        fifo: dict[tuple[str, int], float] = {
            (row.preset, row.seed): row.makespan_min
            for row in self._solver_rows("FIFO")
            if row.makespan_min is not None
        }
        greed: dict[tuple[str, int], float] = {
            (row.preset, row.seed): row.makespan_min
            for row in self._solver_rows("GREED")
            if row.makespan_min is not None
        }
        deltas = [fifo[key] - greed[key] for key in fifo if key in greed]
        return _mean(deltas)

    def greed_all_verified(self) -> bool:
        greed_rows = self._solver_rows("GREED")
        return bool(greed_rows) and all(row.verified for row in greed_rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repairflow_version": self.repairflow_version,
            "synaps_commit": self.synaps_commit,
            "claim_level": "experiment",
            "data_provenance": "synthetic",
            "kpis": {
                "greed_verified_ratio": self.verified_ratio(),
                "fifo_mean_violations": self.fifo_mean_violations(),
                "greed_mean_makespan_minutes": self.greed_mean_makespan(),
                "fifo_mean_makespan_minutes": self.fifo_mean_makespan(),
                "fifo_minus_greed_makespan_minutes": self.fifo_minus_greed_makespan(),
                "makespan_note": MAKESPAN_NOTE,
            },
            "rows": [row.__dict__ for row in self.rows],
        }


def resolve_matrix(
    presets: list[str] | None = None,
    seeds: list[int] | None = None,
    *,
    default: list[tuple[str, int]] | None = None,
) -> list[tuple[str, int]]:
    """Build the (preset, seed) list without silently crossing unrelated default seeds.

    - no flags: DEFAULT_MATRIX
    - --preset only: rows of the default matrix for those presets
    - --seeds only: rows of the default matrix for those seeds
    - both flags: explicit cartesian product of the requested presets and seeds
    """
    base = list(default) if default is not None else list(DEFAULT_MATRIX)
    if presets is None and seeds is None:
        return base
    if presets is not None and seeds is not None:
        return [(preset, seed) for preset in presets for seed in seeds]
    if presets is not None:
        wanted = set(presets)
        return [(preset, seed) for preset, seed in base if preset in wanted]
    wanted_seeds = set(seeds or [])
    return [(preset, seed) for preset, seed in base if seed in wanted_seeds]


def run_benchmark(
    *,
    matrix: list[tuple[str, int]] | None = None,
    solvers: list[str] | None = None,
    out_dir: Path | None = None,
) -> BenchmarkSummary:
    """Run FIFO+GREED on each (preset, seed) pair and collect metrics.

    Args:
        matrix: List of (preset, seed) pairs. Defaults to DEFAULT_MATRIX.
        solvers: Solver config names to run. Defaults to ["FIFO", "GREED"].
        out_dir: If given, write benchmark.json / .md / .html + per-instance reports.

    Returns:
        BenchmarkSummary with aggregated KPIs and per-run rows.
    """
    matrix = list(matrix) if matrix is not None else list(DEFAULT_MATRIX)
    solvers = list(solvers) if solvers is not None else ["FIFO", "GREED"]
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
                    coverage=_as_float(obj.get("coverage")),
                    makespan_min=_as_float(obj.get("makespan_minutes")),
                    input_hash=result.input_hash,
                    config_hash=result.config_hash,
                    result_hash=result.result_hash,
                )
            )

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_dict = summary.to_dict()
        summary_dict["evidence"] = evidence_stamp(
            input_hash=fingerprint_payload([row.input_hash for row in summary.rows]),
            config_hash=fingerprint_payload([row.config_hash for row in summary.rows]),
            data_provenance="synthetic",
        )
        (out_dir / "benchmark.json").write_text(
            json.dumps(summary_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (out_dir / "benchmark.md").write_text(_render_markdown(summary), encoding="utf-8")
        (out_dir / "benchmark.html").write_text(_render_html(summary), encoding="utf-8")
        for (preset, seed, solver), result in results.items():
            problem = problems[(preset, seed)]
            slug = f"{preset}-seed{seed}-{solver.lower()}"
            (out_dir / f"{slug}.html").write_text(render_html(problem, result), encoding="utf-8")
            (out_dir / f"{slug}.md").write_text(render_markdown(problem, result), encoding="utf-8")

    return summary


def _render_markdown(summary: BenchmarkSummary) -> str:
    verified = summary.verified_ratio()
    fifo_viol = summary.fifo_mean_violations()
    greed_mk = summary.greed_mean_makespan()
    fifo_mk = summary.fifo_mean_makespan()
    delta = summary.fifo_minus_greed_makespan()
    lines = [
        "# RepairFlow Benchmark Report",
        "",
        f"- RepairFlow {summary.repairflow_version} · SynAPS `{summary.synaps_commit}`",
        f"- GREED verified ratio: **{verified:.1%}** (independent checker exit 0)",
        f"- FIFO mean hard violations: **{fifo_viol}**",
        f"- GREED mean makespan: **{greed_mk} min**",
        f"- FIFO mean makespan: **{fifo_mk} min** (infeasible packing)",
        f"- FIFO−GREED makespan: **{delta} min** (negative = GREED longer, expected)",
        f"- {MAKESPAN_NOTE}",
        "",
        "| preset | seed | solver | status | verified | violations | coverage | makespan_min |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in summary.rows:
        cov = str(row.coverage) if row.coverage is not None else "—"
        mksp = str(row.makespan_min) if row.makespan_min is not None else "—"
        lines.append(
            f"| {row.preset} | {row.seed} | {row.solver} | {row.status}"
            f" | {row.verified} | {row.violations} | {cov} | {mksp} |"
        )
    lines.extend(
        [
            "",
            "## Claim limits",
            "",
            "- Synthetic data only; not SVARZ depot data.",
            "- GREED and FIFO are heuristics; OPTIMAL applies only when CP-SAT proves it.",
            "- Independent checker validates hard constraints; not a production deployment.",
            "- Frozen JOB-01-03 binds a crew that covers the operation skills (electrical → CREW-ELEC).",
        ]
    )
    return "\n".join(lines)


def _render_html(summary: BenchmarkSummary) -> str:
    from html import escape

    verified = summary.verified_ratio()
    fifo_viol = summary.fifo_mean_violations()
    greed_mk = summary.greed_mean_makespan()
    fifo_mk = summary.fifo_mean_makespan()
    delta = summary.fifo_minus_greed_makespan()
    rows_html = []
    for row in summary.rows:
        mark = "✓" if row.verified else "✗"
        cov = row.coverage if row.coverage is not None else "—"
        mksp = row.makespan_min if row.makespan_min is not None else "—"
        rows_html.append(
            "<tr>"
            f"<td>{escape(row.preset)}</td>"
            f"<td>{row.seed}</td>"
            f"<td>{escape(row.solver)}</td>"
            f"<td>{escape(row.status)}</td>"
            f"<td>{mark}</td>"
            f"<td>{row.violations}</td>"
            f"<td>{cov}</td>"
            f"<td>{mksp}</td>"
            "</tr>"
        )
    table_body = "".join(rows_html)
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
· SynAPS <code>{escape(summary.synaps_commit[:12])}</code></p>
<div class="kpi">
  <div class="kpi-card">
    <div class="kpi-val">{verified:.0%}</div>
    <div class="kpi-lab">GREED checker-verified ratio</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{fifo_viol if fifo_viol is not None else "n/a"}</div>
    <div class="kpi-lab">FIFO mean hard violations</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{greed_mk if greed_mk is not None else "n/a"} min</div>
    <div class="kpi-lab">GREED mean makespan</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{fifo_mk if fifo_mk is not None else "n/a"} min</div>
    <div class="kpi-lab">FIFO mean makespan (infeasible)</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{delta if delta is not None else "n/a"} min</div>
    <div class="kpi-lab">FIFO−GREED makespan (negative expected)</div>
  </div>
</div>
<table>
<thead><tr>
  <th>preset</th><th>seed</th><th>solver</th><th>status</th>
  <th>verified</th><th>violations</th><th>coverage</th><th>makespan_min</th>
</tr></thead>
<tbody>{table_body}</tbody>
</table>
<p class="note">{escape(MAKESPAN_NOTE)} Synthetic data only. Not SVARZ data or a
production pilot. Heuristic solvers (FIFO, GREED) are not called optimal.</p>
</body></html>
"""
