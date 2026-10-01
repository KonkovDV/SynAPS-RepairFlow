# Changelog

## Unreleased

- CP-SAT above 80 operations is a recorded capability refusal (`CPSAT_OPS_CAP`),
  not an exception and not a silent fallback. The exact solver is not called.
  The result is empty, exit 2, not `verified` and not `optimal`.
- Exit 0 requires full coverage. `allow_partial_plan` no longer hides missing
  operations; those plans are `PARTIAL` / exit 2.
- Tooling calendars and empty calendars are hard. `due_date` stays soft;
  `Job.deadline` is hard. Duplicate setup cells and unknown replan ids are rejected.
  Immutable frozen rows are checked against each other at ingest.
- The checker no longer imports the adapter. Setup lookup used by the notary
  lives in `checker_primitives.py`.
- Schedule metrics (makespan from the horizon start, tardiness, setup, coverage)
  are recomputed for every solver. `repairflow check --verify-hashes` rejects a
  plan whose stored hashes do not match. OR-Tools is pinned to 9.15.6755.
  `EDD` is a feasible baseline. CP-SAT is warm-started from domain GREED.
- Post, crew, and tool capacity is a sweep-line lane count. Staggered visits
  that share a resource without exceeding `max_parallel` stay feasible.
  Endpoint contact does not consume two lanes. Frozen ingest uses the same oracle.
- Setup on a parallel work centre is lane-local. The checker and the domain
  list scheduler share that colouring: a lane is reused only after its
  occupancy ends, and overflow stays an explicit capacity failure.
- GREED/EDD disruption repair uses that same colouring. The broken slot is
  consumed, the tail of that lane is rescheduled, and the other lanes stay put.
- Kernel solvers and kernel disruption repair refuse a problem whose crew or
  auxiliary resource has a calendar. The pinned core has no field for that
  constraint. Domain FIFO, GREED and EDD still enforce it themselves.
- Sweep-line excess arrivals are checked against an independent critical-point
  reference, including setup occupancy. A hard capacity violation stays unverified.
- A rotable clash is a domain hard decision. The pinned kernel has no return-lag
  field, so its silence does not make that plan `verified`. A converged DAG
  fixpoint that both verifiers accept stays `verified` and is not `optimal`.
  A deletion-minimal operation set explains one hard code and is not a CP-MUS.
- `ATC` has a bounded local ordering contract in `repairflow.atc_baseline`.
  It is not planner-integrated, not a SynAPS config, and cannot produce an
  `optimal` or `verified` claim by itself.
- The checker no longer invents a `crew_id`. A skilled assignment without one
  is `CREW_UNBOUND`. An explicit unknown crew stays `UNKNOWN_RESOURCE`, and an
  explicit unqualified crew stays `SKILL_MISMATCH`.
- CSV bundles round-trip `exchange_pools`: stock, the hard flag, and each
  dated demand. A demand row missing either instant or quantity is rejected.
- `docs/evidence-manifest.json` records main `22d4770` and CI run `36903507601`,
  including `test-slow`, against the pinned SynAPS commit.
- Kernel and domain checkers agree on the hard decision for a compatible plan:
  clean stays `verified`; precedence, eligibility, work-centre calendar, auxiliary
  capacity, centre overlap and setup mismatch are rejected by both. Diagnostic
  text is not required to match. Crew and auxiliary calendars stay a separate
  kernel refusal.
- Pilot-boundary documents state TRL 4, shadow-only use, and the gates that
  are still external (legal entity, data owner, signed extract). The operator
  decision log is a contract, not a writer.

- `repairflow benchmark`: FIFO vs GREED portfolio on the documented synthetic
  matrix, HTML/JSON/Markdown KPI report, CI artifact. FIFO makespan is not treated
  as a quality baseline.
- Frozen `JOB-01-03` binds a crew that holds the operation skills. Ingest rejects
  a frozen crew/post that cannot execute the card. Checker reports `PRECEDENCE_BROKEN`
  when a predecessor is missing from the plan.
- Add committed-example schema verification to CI.
- Add SOTA/evidence protocol: benchmark ladder, claim hierarchy, disruption metrics and pilot gates.
- `test-slow` on `main` treats an empty `-m slow` selection (pytest exit 5) as pass.

## 0.1.0 — 2026-09-19

- Initial MVP: domain contract, SynAPS adapter, FIFO/GREED/CP-SAT/RHC routing,
  independent fail-closed checker, frozen replan, Gantt/diff, synthetic site,
  intentionally broken demo, SHA pin `6178c93b705ff58be21fa74a98651883a2da1169`.
- One-command readiness: `repairflow demo --out out` (FIFO dirty, GREED verified,
  CP-SAT OPTIMAL on `tiny`, broken plan exit 2, frozen slots kept).
- Linear tech-cards: `predecessor_ids` must match `sequence`. Published assignments
  name a concrete crew. Missing `idle → first_state` is fail-closed as `MISSING_SETUP`.
- Laboratory prototype. Not a customer pilot.
