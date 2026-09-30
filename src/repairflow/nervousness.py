"""How much a replanned card moves relative to the plan already shown."""

from __future__ import annotations

from dataclasses import dataclass

from repairflow.model import RepairFlowResult


@dataclass(frozen=True)
class PlanNervousness:
    moved: tuple[str, ...]
    reassigned: tuple[str, ...]
    added: tuple[str, ...]
    removed: tuple[str, ...]
    sum_abs_shift_min: int
    frozen_violations: int
    ratio: float

    def as_dict(self) -> dict[str, object]:
        return {
            "moved": list(self.moved),
            "reassigned": list(self.reassigned),
            "added": list(self.added),
            "removed": list(self.removed),
            "sum_abs_shift_min": self.sum_abs_shift_min,
            "frozen_violations": self.frozen_violations,
            "ratio": self.ratio,
        }


def compare(
    base: RepairFlowResult,
    new: RepairFlowResult,
    *,
    frozen_operation_ids: set[str] | None = None,
) -> PlanNervousness:
    before = {row.operation_id: row for row in base.assignments}
    after = {row.operation_id: row for row in new.assignments}
    moved: list[str] = []
    reassigned: list[str] = []
    shift_min = 0
    for op_id, old in before.items():
        current = after.get(op_id)
        if current is None:
            continue
        start_moved = current.start != old.start
        post_moved = current.work_center_id != old.work_center_id
        if start_moved or post_moved:
            moved.append(op_id)
            shift_min += int(abs((current.start - old.start).total_seconds()) // 60)
        if post_moved:
            reassigned.append(op_id)
    frozen_ids = frozen_operation_ids or set()
    frozen_violations = 0
    for op_id in sorted(frozen_ids):
        issued = before.get(op_id)
        placed = after.get(op_id)
        if issued is None:
            continue
        if placed is None:
            frozen_violations += 1
            continue
        crew_moved = issued.crew_id is not None and placed.crew_id != issued.crew_id
        if placed.start != issued.start or placed.work_center_id != issued.work_center_id or crew_moved:
            frozen_violations += 1
    added = tuple(sorted(op_id for op_id in after if op_id not in before))
    removed = tuple(sorted(op_id for op_id in before if op_id not in after))
    denominator = len(before) or 1
    return PlanNervousness(
        moved=tuple(sorted(moved)),
        reassigned=tuple(sorted(reassigned)),
        added=added,
        removed=removed,
        sum_abs_shift_min=shift_min,
        frozen_violations=frozen_violations,
        ratio=len(moved) / denominator,
    )
