# Changelog

## Unreleased

- `tests/oracle_minutes.py` is an independent minute oracle. It imports only
  `repairflow.model`, refuses a horizon over eight days or a timestamp off the
  minute, and is checked on hand-built plans. It does not judge the exchange-pool
  ledger. The fault-campaign report is still v1.
- Public claim pages are scanned against `docs/BANNED_CLAIMS.txt`.
  The two literature pages were renamed so a banned word is not a file name
  or a heading. A negation is an exact line in
  `docs/banned-claims-allowlist.txt` with its own reason. README measurements
  outside the generated evidence block are removed.
- The evidence manifest attests main `fc14c76` / push run `37690925608`,
  including `test-slow`, and kernel `f939727`. `tools/attest.py` writes the
  manifest and re-renders the README table; this note does not attest itself.
- `benchmark/results/SHA256SUMS` is the LF git blob of `benchmark.json`.
  A fresh GREED row is checked by input hash, status, coverage and makespan.
  `result_hash` stays in the snapshot and includes the machine runtime.
- CP-SAT is invoked up to 100 operations. That is the last size at which
  CPSAT-10 returned a checked plan on a synthetic one-skill card with published
  shifts. One hundred and twenty operations on that card timed out empty.
  Above 100 the recorded refusal `CPSAT_OPS_CAP` still does not call the solver.
- Crew and auxiliary calendars with published windows compile to
  `AuxiliaryResource.calendar` on SynAPS `f939727`. The kernel checker and
  CP-SAT keep occupancy inside one shift. An attended calendar with no windows,
  a skill pool with mixed shifts, and a preemptive operation on a published
  shift stay `KERNEL_CALENDAR_UNSUPPORTED`.
- `repairflow verify-plan` checks a shop CSV (заказ, операция, пост, бригада,
  оснастка, начало, конец) without calling the kernel. A clean plan is
  `domain_verified`, not `verified` and not `optimal`.
- Predecessor links carry `min_lag_min` and optional `max_lag_min`. A v1
  `predecessor_ids` list stays lag 0. A consumable with `receipts` is a
  reservoir over time. `skill_valid_until` yields `SKILL_EXPIRED` when the
  visit ends after the permit, not only when it starts after the permit.
- A kernel assignment with more than one crew is `AMBIGUOUS_CREW`. An aux kind
  other than crew or aux is `UNKNOWN_RESOURCE`. Missing required tooling is
  `AUX_MISSING`. `verified` accepts only kernel status `feasible`, `optimal`,
  or explicit `domain_only`. A deletion witness for precedence keeps both
  operations. Preemptive setup must lie inside an open window.
- `Policy.unsupported_dag` is deprecated and ignored. `dag_strategy` compiles
  the card. The slow CI job no longer treats an empty selection as a pass.
- Duration defaults to `exact`. `min` and `preemptive` are explicit. An empty
  calendar is closed for the planner and the checker. An unattended resource
  may run while its staffed calendar is closed. Frozen ingest checks auxiliary
  overlap, duration, and the setup cell.
- A dependency lock is `locked` only when every component has an archive
  SHA-256. The signature field stays `absent`.
- A rotable spare is not counted as a consumable. Sequential reuse after return
  stays admissible; overlap during use or return lag stays `SPARE_UNAVAILABLE`.
- An id map whose values are not unique is `INVALID_ID_MAP`, even when the
  operation and work-center keys match.
- CP-SAT above `CPSAT_OPS_CAP` is a recorded capability refusal (`CPSAT_OPS_CAP`),
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
- `repairflow.artifact_record.v1` records a local wheel or sdist digest, or a
  PEP 610 archive hash already on disk. It is not the installed-file manifest
  and it does not claim a signature or a transitive lockfile.
- `docs/evidence-manifest.json` records a checked main commit and that
  commit's own push CI, including `test-slow`, against SynAPS `f939727`.
- A `calendar_id` missing from `calendars` is `CALENDAR_BROKEN` inside the
  checker. A resource with no `calendar_id` stays open for the horizon.
- `docs/fault-campaign.json` records 10000 guaranteed-invalid mutations of
  synthetic tiny GREED with `false_accept` 0. `benchmark/results/benchmark.json`
  stores the synthetic FIFO/GREED rows with input, config, and result hashes.
- `domain_only` is the `verify-plan` claim. A kernel recheck of that token is
  not `verified` and not `optimal`.
- A non-synthetic resource without `calendar_id` must set
  `availability=always_open`. Synthetic fixtures may still omit the calendar.
- The README evidence table is rendered from `docs/evidence-manifest.json`.
  The manifest is `stale` while it does not name `HEAD`.
- `benchmark/results/benchmark.json` and `SHA256SUMS` hold the synthetic
  FIFO/GREED rows. `test-slow` runs on main, nightly, and pull requests
  labeled `slow`.
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
- Add the evidence protocol: benchmark ladder, claim hierarchy, disruption metrics and pilot gates.
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
