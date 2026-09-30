# ADR-0005. Inspection rewrites one card, then replans

## Context

Defectation changes the work, not only the dates. The kernel has no event
type for that. A revealed branch is new operations plus new precedence.

## Decision

`InspectionEvent` adds operations to one job and may replace `predecessor_ids`
on the join. `replan_after_inspection` freezes every assignment that already
exists, then runs domain GREED for the new branch only. Issued slots stay,
including on the inspected unit: a neighbour's setup depends on the previous
state on that post, so sliding an issued operation would rewrite a frozen
setup. If the branch does not fit before the frozen join, the plan is rejected.
The domain checker still sees the original edges, including the new join.

Nervousness compares the new plan with the plan that was shown. A ratio above
`policy.nervousness_warn_ratio` (default 0.10) is `NERVOUSNESS_HIGH` with
severity `kpi`. A frozen assignment that moved is already `FROZEN_MOVED`
(hard) and is also counted in `frozen_violations`.

## Consequences

Domain GREED is the freeze-aware closer for this event. Kernel
`repair_schedule` remains the path for `replan_after_disruption`, which
shifts existing operations and does not insert a branch.
