"""Compile a repair DAG into chain segments the SynAPS kernel can accept.

The kernel requires each order to be a strict chain (`seq_in_order` plus a
single `predecessor_op_id`). A repair card is a convergent DAG. S1 serializes
each job. S2 keeps maximal unbranched chains and lifts earliest-start windows
on the remaining edges until a fixpoint (ADR-0002).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from repairflow.model import Operation, RepairFlowProblem


@dataclass(frozen=True)
class Segment:
    id: str
    job_id: str
    op_ids: tuple[str, ...]


@dataclass(frozen=True)
class CrossEdge:
    src: str
    dst: str


@dataclass(frozen=True)
class CompiledDag:
    strategy: str
    segments: tuple[Segment, ...]
    cross_edges: tuple[CrossEdge, ...]
    window_lb: dict[str, datetime]
    iteration: int


def compile_dag(problem: RepairFlowProblem) -> CompiledDag:
    strategy = problem.policy.dag_strategy
    if strategy == "serialize":
        segments, cross = _serialize(problem)
    else:
        segments, cross = _segment(problem)
    return CompiledDag(
        strategy=strategy,
        segments=tuple(segments),
        cross_edges=tuple(cross),
        window_lb={},
        iteration=0,
    )


def propagate_windows(
    compiled: CompiledDag,
    *,
    starts: Mapping[str, datetime],
    ends: Mapping[str, datetime],
) -> tuple[CompiledDag, bool]:
    """Raise destination windows when a cross edge is still violated.

    Windows only grow. A satisfied edge does not force another solve: the
    schedule already in hand is the candidate the domain checker will judge.
    """

    if not compiled.cross_edges:
        return compiled, False
    windows = dict(compiled.window_lb)
    changed = False
    for edge in compiled.cross_edges:
        src_end = ends.get(edge.src)
        if src_end is None:
            continue
        lifted = _ceil_minute(src_end)
        previous = windows.get(edge.dst)
        dst_start = starts.get(edge.dst)
        violated = dst_start is None or dst_start < lifted
        needs_lift = previous is None or lifted > previous
        if violated and needs_lift:
            windows[edge.dst] = lifted if previous is None else max(previous, lifted)
            changed = True
    if not changed:
        return compiled, False
    return replace(compiled, window_lb=windows, iteration=compiled.iteration + 1), True


def _serialize(problem: RepairFlowProblem) -> tuple[list[Segment], list[CrossEdge]]:
    by_id = {op.id: op for op in problem.operations}
    segments: list[Segment] = []
    cross: list[CrossEdge] = []
    for job in sorted(problem.jobs, key=lambda row: row.id):
        ops = [op for op in problem.operations if op.job_id == job.id]
        if not ops:
            continue
        order = _topo(ops, by_id)
        segments.append(Segment(id=f"seg:{job.id}:{order[0]}", job_id=job.id, op_ids=tuple(order)))
    job_of = {op.id: op.job_id for op in problem.operations}
    for op in problem.operations:
        for pred in op.predecessor_ids:
            if job_of.get(pred) != op.job_id:
                cross.append(CrossEdge(src=pred, dst=op.id))
    cross.sort(key=lambda edge: (edge.src, edge.dst))
    return segments, cross


def _segment(problem: RepairFlowProblem) -> tuple[list[Segment], list[CrossEdge]]:
    by_id = {op.id: op for op in problem.operations}
    succ: dict[str, list[str]] = defaultdict(list)
    pred: dict[str, list[str]] = defaultdict(list)
    edges: list[tuple[str, str]] = []
    for op in problem.operations:
        for src in op.predecessor_ids:
            edges.append((src, op.id))
            succ[src].append(op.id)
            pred[op.id].append(src)
    chain_next: dict[str, str] = {}
    chain_prev: set[str] = set()
    for src, dst in edges:
        src_op = by_id[src]
        dst_op = by_id[dst]
        if src_op.job_id != dst_op.job_id:
            continue
        if len(succ[src]) == 1 and len(pred[dst]) == 1:
            chain_next[src] = dst
            chain_prev.add(dst)
    starts = [op.id for op in problem.operations if op.id not in chain_prev]
    starts.sort(key=lambda op_id: (by_id[op_id].job_id, by_id[op_id].sequence, op_id))
    segments: list[Segment] = []
    seen: set[str] = set()
    for start in starts:
        if start in seen:
            continue
        chain = [start]
        seen.add(start)
        while chain[-1] in chain_next:
            nxt = chain_next[chain[-1]]
            chain.append(nxt)
            seen.add(nxt)
        job_id = by_id[start].job_id
        segments.append(Segment(id=f"seg:{job_id}:{start}", job_id=job_id, op_ids=tuple(chain)))
    if len(seen) != len(by_id):
        missing = sorted(set(by_id) - seen)
        raise ValueError(f"DAG segmentation dropped operations: {missing[:8]}")
    chain_edges = set(chain_next.items())
    cross = [CrossEdge(src=src, dst=dst) for src, dst in edges if (src, dst) not in chain_edges]
    cross.sort(key=lambda edge: (edge.src, edge.dst))
    return segments, cross


def _topo(ops: list[Operation], by_id: dict[str, Operation]) -> list[str]:
    op_ids = {op.id for op in ops}
    indeg = {op.id: 0 for op in ops}
    succ: dict[str, list[str]] = defaultdict(list)
    for op in ops:
        for pred in op.predecessor_ids:
            if pred not in op_ids:
                continue
            indeg[op.id] += 1
            succ[pred].append(op.id)
    ready = sorted(
        [op_id for op_id, degree in indeg.items() if degree == 0],
        key=lambda op_id: (by_id[op_id].sequence, op_id),
    )
    ordered: list[str] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for nxt in succ.get(node, []):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=lambda op_id: (by_id[op_id].sequence, op_id))
    if len(ordered) != len(ops):
        raise ValueError("operation precedence graph contains a cycle")
    return ordered


def _ceil_minute(moment: datetime) -> datetime:
    if moment.second == 0 and moment.microsecond == 0:
        return moment
    return moment.replace(second=0, microsecond=0) + timedelta(minutes=1)
