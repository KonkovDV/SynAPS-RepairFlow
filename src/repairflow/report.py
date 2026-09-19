"""Markdown + static HTML/Gantt report. No CDN."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from repairflow.model import PlannedAssignment, RepairFlowProblem, RepairFlowResult, Violation
from repairflow.reasons import REASON_RU
from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT

KIND_COLOR = {
    "diagnose": "#2b6cb0",
    "disassemble": "#c05621",
    "restore": "#6b46c1",
    "assemble": "#2f855a",
    "test": "#d69e2e",
}


def render_markdown(problem: RepairFlowProblem, result: RepairFlowResult) -> str:
    banner = "проверен, exit 0" if result.verified_feasible else f"не выпускать, exit {result.exit_code}"
    lines = [
        f"# RepairFlow {problem.instance_id}",
        "",
        f"- статус: **{result.status.value}** ({banner})",
        f"- solver: `{result.solver_config}` · kernel `{result.kernel_status}`",
        f"- RepairFlow {REPAIRFLOW_VERSION} · SynAPS `{SYNAPS_COMMIT}`",
        f"- provenance: `{result.data_provenance}` · claim `{result.claim_level}`",
        f"- input_hash: `{result.input_hash}`",
        f"- config_hash: `{result.config_hash}`",
        f"- result_hash: `{result.result_hash}`",
        f"- coverage: {result.objective.get('coverage')} · "
        f"makespan {result.objective.get('makespan_minutes')} мин",
        f"- нарушения: {len(result.violations)}",
        "",
        "## Назначения",
        "",
        "| операция | заказ | пост | бригада | старт | конец | setup | причина |",
        "|---|---|---|---|---|---|---|---|",
    ]
    jobs = {op.id: op.job_id for op in problem.operations}
    for row in result.assignments:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.operation_id,
                    jobs.get(row.operation_id, ""),
                    row.work_center_id,
                    row.crew_id or "—",
                    row.start.isoformat(),
                    row.end.isoformat(),
                    str(row.setup_minutes),
                    row.reason.replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Нарушения", ""])
    if not result.violations:
        lines.append("Чекер пуст. Это не слово «оптимально», если solver не CP-SAT OPTIMAL.")
    else:
        for item in result.violations:
            lines.append(f"- `{item.code}` {item.message}")
    lines.extend(
        [
            "",
            "## Ограничения заявления",
            "",
            "- синтетический контур, не данные СВАРЗ и не пилот Дептранса;",
            "- не управляет выпуском транспорта и не записывает план в EAM/ERP;",
            "- GREED/RHC/FIFO не называются оптимальными.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(problem: RepairFlowProblem, result: RepairFlowResult) -> str:
    dirty = not result.verified_feasible
    banner = (
        f'<div class="banner fail">exit {result.exit_code} — план записан, выпускать нельзя</div>'
        if dirty
        else f'<div class="banner ok">exit {result.exit_code} {escape(result.status.value)}</div>'
    )
    return _page(
        title=f"RepairFlow {problem.instance_id}",
        dirty=dirty,
        body=(
            banner + f"<p class='meta'>pin {escape(SYNAPS_COMMIT[:12])} · {escape(result.solver_config)} · "
            f"{len(result.assignments)}/{len(problem.operations)} ops · "
            f"синтетика, не клиентский пилот</p>"
            + _hashes(result)
            + _violations(result.violations)
            + _gantt(problem, result)
            + _assignments(problem, result)
            + _limits_note()
        ),
    )


def _hashes(result: RepairFlowResult) -> str:
    return (
        "<ul class='meta'>"
        f"<li>input_hash <code>{escape(result.input_hash)}</code></li>"
        f"<li>config_hash <code>{escape(result.config_hash)}</code></li>"
        f"<li>result_hash <code>{escape(result.result_hash)}</code></li>"
        f"<li>kernel_status <code>{escape(result.kernel_status or '—')}</code></li>"
        "</ul>"
    )


def _violations(rows: list[Violation]) -> str:
    if not rows:
        return "<p class='meta'>Чекер пуст. Independent proof of hard constraints only.</p>"
    items = "".join(
        f"<li><code>{escape(row.code)}</code> {escape(row.message)}"
        f" <span class='hint'>{escape(REASON_RU.get(row.code, ''))}</span></li>"
        for row in rows
    )
    return f'<section class="red-list"><h2>Нарушения</h2><ul>{items}</ul></section>'


def _gantt(problem: RepairFlowProblem, result: RepairFlowResult) -> str:
    ops = {op.id: op for op in problem.operations}
    t0, t1 = _horizon(problem, result)
    span = max(1.0, (t1 - t0).total_seconds())
    by_center: dict[str, list[PlannedAssignment]] = {wc.code: [] for wc in problem.work_centers}
    id_to_code = {wc.id: wc.code for wc in problem.work_centers}
    dirty_ops = {row.operation_id for row in result.violations if row.operation_id}
    for asn in result.assignments:
        label = id_to_code.get(asn.work_center_id, asn.work_center_id)
        by_center.setdefault(label, []).append(asn)
    lanes = []
    for code, rows in by_center.items():
        bars = []
        for asn in sorted(rows, key=lambda item: item.start):
            op = ops.get(asn.operation_id)
            kind = "restore" if op is None else _kind(op)
            left = ((asn.start - t0).total_seconds() / span) * 100
            width = max(0.4, ((asn.end - asn.start).total_seconds() / span) * 100)
            color = KIND_COLOR.get(kind, "#4a5568")
            klass = "bar bad" if asn.operation_id in dirty_ops else "bar"
            title = escape(asn.reason or asn.operation_id)
            bars.append(
                f'<div class="{klass}" style="left:{left:.3f}%;width:{width:.3f}%;'
                f'background:{color}" title="{title}"></div>'
            )
        lanes.append(
            f'<div class="lane"><div class="label">{escape(code)}</div>'
            f'<div class="track">{"".join(bars)}</div></div>'
        )
    return f'<section id="gantt"><h2>Gantt по постам</h2><div class="gantt">{"".join(lanes)}</div></section>'


def _assignments(problem: RepairFlowProblem, result: RepairFlowResult) -> str:
    jobs = {op.id: op.job_id for op in problem.operations}
    rows = []
    for asn in result.assignments:
        rows.append(
            "<tr>"
            f"<td>{escape(asn.operation_id)}</td>"
            f"<td>{escape(jobs.get(asn.operation_id, ''))}</td>"
            f"<td>{escape(asn.work_center_id)}</td>"
            f"<td>{escape(asn.crew_id or '—')}</td>"
            f"<td>{escape(asn.start.isoformat())}</td>"
            f"<td>{escape(asn.end.isoformat())}</td>"
            f"<td>{asn.setup_minutes}</td>"
            f"<td>{escape(asn.reason)}</td>"
            "</tr>"
        )
    return (
        "<h2>Причины назначений</h2>"
        "<table><thead><tr><th>op</th><th>job</th><th>post</th><th>crew</th>"
        "<th>start</th><th>end</th><th>setup</th><th>reason</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _kind(operation: Any) -> str:
    mapping = {"01": "diagnose", "02": "disassemble", "03": "restore", "04": "assemble", "05": "test"}
    suffix = operation.id[-2:]
    if "electrical" in operation.required_skills:
        return "restore"
    return mapping.get(suffix, "restore")


def _horizon(problem: RepairFlowProblem, result: RepairFlowResult) -> tuple[datetime, datetime]:
    t0 = problem.planning_horizon.start
    t1 = problem.planning_horizon.end
    if result.assignments:
        t0 = min(t0, min(row.start for row in result.assignments))
        t1 = max(t1, max(row.end for row in result.assignments))
    return t0, t1


def _limits_note() -> str:
    return (
        "<p class='note'>RepairFlow не заменяет EAM/ERP, не управляет выпуском "
        "транспорта и не утверждает промышленный эффект. Синтетический эксперимент.</p>"
    )


def _page(*, title: str, dirty: bool, body: str) -> str:
    bg = "#2b1111" if dirty else "#102015"
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{ font-family: Segoe UI, sans-serif; background:{bg}; color:#f7fafc; margin:24px; }}
.banner {{ padding:12px 16px; border-radius:8px; font-weight:700; margin-bottom:16px; }}
.banner.ok {{ background:#276749; }}
.banner.fail {{ background:#c53030; }}
.meta {{ color:#cbd5e0; }}
code {{ color:#f6e05e; }}
.gantt {{ display:flex; flex-direction:column; gap:6px; }}
.lane {{ display:flex; align-items:center; gap:8px; }}
.label {{ width:110px; font-size:12px; }}
.track {{ position:relative; flex:1; height:18px; background:#1a202c; border-radius:4px; }}
.bar {{ position:absolute; top:2px; height:14px; border-radius:3px; opacity:.9; }}
.bar.bad {{ outline:2px solid #fc8181; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; }}
td,th {{ border-bottom:1px solid #2d3748; padding:4px 6px; text-align:left; }}
.red-list {{ background:#3c1515; padding:8px 16px; border-radius:8px; }}
.note {{ margin-top:24px; color:#a0aec0; }}
.hint {{ color:#fbd38d; }}
</style></head><body>
<h1>{escape(title)}</h1>
{body}
</body></html>
"""
