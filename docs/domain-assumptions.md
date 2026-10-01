# Domain assumptions

- One repair contour / shop, not a city-wide network.
- A job may be a convergent DAG (`predecessor_ids`, including a join). Cycles are
  rejected. The kernel still receives chains: `split_release_fixpoint` (default) or
  `serialize`. The domain checker evaluates the original edges, not the segments.
  See `docs/adr/0002-dag-over-chain-kernel.md`.
- Dates are timezone-aware ISO-8601. Unix timestamps are rejected.
- SynAPS encodes posts as work centres and crews/tooling as auxiliary resources.
  A published plan names a concrete `crew_id` when skills are required;
  skill-pools are an internal kernel encoding only. The checker does not fill
  a missing `crew_id`: that candidate is `CREW_UNBOUND`. An explicit unknown
  crew is `UNKNOWN_RESOURCE`. An explicit crew without the required skills is
  `SKILL_MISMATCH`.
- Consumable spares are a blocking availability constraint, not inventory optimisation.
  An exchange pool is a separate stock ledger: a unit returns when every sink of
  its card has finished, and dated demand withdraws stock. `hard=false` keeps a
  stockout as a KPI.
- A post, crew, or tool with capacity K has K fungible lanes. Occupancy is the
  half-open interval from setup start through processing end. The checker and
  the immutable-freeze ingest use the same sweep: demand is the maximum number
  of lanes open at one instant, and an endpoint touch does not take two lanes.
  Lanes are not named. Staggered visits that never exceed K are feasible.
  Setup state belongs to the lane. The next visit takes the matrix cell from
  the lane that became free earliest, and the lower index breaks ties. A centre
  already at `max_parallel` is an explicit capacity failure. A broken visit
  restarts at or after its old end. That lane's tail is rescheduled; the other
  lanes of the same post stay frozen with their own setup state.
- A resource with no `calendar_id` is open for the whole horizon. A calendar with
  zero windows means the resource is unavailable. A non-empty calendar is a hard
  single-window container, including tooling (`AuxResource.calendar_id`).
- `due_date` is a soft tardiness signal (`DUE_MISSED`, severity kpi). `deadline`
  on the job is hard (`DEADLINE_MISSED`, exit 2).
- `allow_partial_plan` does not produce exit 0. Missing operations are status
  `PARTIAL` and exit 2.
- Frozen rows with `immutable=true` must already be mutually feasible at ingest
  (overlap, calendar, precedence among frozen rows) and must survive replan.
  `immutable=false` is a note: it is stored and not enforced.
- Duplicate setup-matrix cells are rejected.
- Heuristic solvers never inherit the word OPTIMAL.
- Missing `idle → first_state` setup cells are a hard contract error. Under
  `missing_setup=reject` the instance is refused; a plan that still uses a missing
  cell is fail-closed as `MISSING_SETUP` (exit 2).
- CP-SAT is refused, and not invoked, when the instance has more than 80
  operations (`CPSAT_OPS_CAP`). The result records that route. It is not a
  fallback to GREED and not evidence that a real shop of that size is solvable.
  Domain FIFO, GREED, EDD and ATC do not use this cap.
- Kernel CP-SAT and RHC refuse a crew or auxiliary calendar
  (`KERNEL_CALENDAR_UNSUPPORTED`) instead of dropping it. Domain GREED remains
  the verified closer on `repair-site-mvp` and on the synthetic site. A kernel
  solve runs only when those calendars are absent. Named crews keep their shift
  windows in the domain checker.
- `ATC` is a local list-dispatch baseline with fixed lookahead `k = 2`. It is
  not a SynAPS solver. A clean ATC plan is checker-`verified` and is not
  `optimal`.
- A rotable spare is busy from its issue until the operation ends plus
  `return_lag_min`. The pinned kernel has no field for that reuse. When the
  domain ledger reports `SPARE_UNAVAILABLE`, the plan is not `verified` even
  if the kernel feasibility checker is empty.
- A converged fixpoint may lift cross-edge windows over several solves. The
  domain checker still judges the original edges. More than one iteration
  keeps the claim at `verified`.
