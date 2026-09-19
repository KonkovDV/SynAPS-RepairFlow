# Domain assumptions

- One repair contour / shop, not a city-wide network.
- A job is a linear technology card. `predecessor_ids` must equal the previous
  `sequence` in the same job; a mismatch is rejected. Branching DAGs are out of scope.
- Dates are timezone-aware ISO-8601. Unix timestamps are rejected.
- SynAPS encodes posts as work centres and crews/tooling as auxiliary resources.
  A published assignment always names a concrete `crew_id` when skills are required;
  skill-pools are an internal kernel encoding only.
- Consumable spares are a blocking availability constraint, not inventory optimisation.
- Empty calendars mean 24/7; a non-empty calendar is a hard single-window container.
- Frozen rows with `immutable=true` must survive replan.
- Heuristic solvers never inherit the word OPTIMAL.
- Missing `idle → first_state` setup cells are a hard contract error. Under
  `missing_setup=reject` the instance is refused; a plan that still uses a missing
  cell is fail-closed as `MISSING_SETUP` (exit 2).
- Kernel GREED/RHC treat crews as auxiliary resources. The verified closer on the 52-op
  `repair-site-mvp` fixture is RepairFlow's domain GREED list-scheduler. Kernel
  `RHC-GREEDY-COVER` is exposed and checker-clean on `tiny`, but is not claimed verified
  on the larger fixture.
