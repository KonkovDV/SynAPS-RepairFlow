# Changelog

## Unreleased

- The evidence manifest attests main `cc8acce` / push run `38933763584`,
  including `test-slow`. This commit does not attest itself.
- The notary rejects a kernel schedule whose operation or work-center ids
  are not the compiled map, even when the operation count still matches.
  A fixed duration is not a duration distribution, and ISO 55001 is not claimed.
- Domain attributes reject a few personal value shapes, and the operator log
  can carry an HMAC witness of its tip. The witness key is not a release key.
  The native CP-SAT model stays unwired until it is measured.
- A shop-plan job mismatch records the file name and source line. An empty
  crew cell stays empty for the notary. A notary finding on that operation
  receives the same row. A repeated operation row is rejected. The shop file
  SHA-256 is the decoded byte string, under the same read limit as other files,
  and the text reason names the file and line. An empty shop file is rejected.
- The README now names the operator-log writer, separates the CI badge from
  the attested revision, and points at the page map. A documentation audit
  records what was wrong and what the audit does not close.
- The evidence manifest attests main `e34f782` / push run `38754698950`,
  including `test-slow`. This commit does not attest itself.
- The laboratory image is started with a read-only root. There is no health
  check: the container exits with the command.
- The evidence manifest attests main `c7757f3` / push run `38749261423`,
  including `test-slow`. This commit does not attest itself.
- `docs/submission-facts.md` is rendered from the manifest and the two campaign
  files. `tools/attest.py` also rewrites the living attestation clause.
- The evidence manifest attests main `a7ff737` / push run `38743808761`,
  including `test-slow`. This commit does not attest itself.
- GitHub Actions are pinned to the commit of the reviewed tag. The tag stays
  in a comment. A floating tag in a workflow is rejected.
- The evidence manifest attests main `ad6f7fa` / push run `38738246339`,
  including `test-slow`. This commit does not attest itself.
- `domain_attributes` rejects keys that name a person. The check is the key,
  not the value, and it is not a personal-data compliance claim.
- The laboratory image copies the install out of a build stage. The wheelhouse
  is not a layer of the final image.
- The evidence manifest attests main `0e1d02a` / push run `38733162076`,
  including `test-slow`. This commit does not attest itself.
- Nightly mutmut `38698472141` on `7f6e9ae` was read. 126 survivors are
  equivalent. 49 are not. `tests/test_nightly_survivors.py` records the
  original behaviour and is not part of that run. Phase 1 stays open.
  The README does not copy the score.
- The evidence manifest attests main `25e6e82` / push run `38724588580`,
  including `test-slow`. This commit does not attest itself.
- `tools/pack_submission.py` copies the submission pages into one folder and
  records their hashes. It does not generate the prose or add a result figure.
- The evidence manifest attests main `3f84202` / push run `38719812783`,
  including `test-slow`. This commit does not attest itself.
- `repairflow demo` writes a foreign shop sheet, a domain rejection, and a
  deletion-minimal witness beside the operator-log line.
- The evidence manifest attests main `4525533` / push run `38715742216`,
  including `test-slow`. This commit does not attest itself.
- `tools/append_decision.py` checks the problem and result files and will not
  accept a non-zero exit. `repairflow demo` appends that decision and checks
  the hash chain.
- The evidence manifest attests main `1f1f80c` / push run `38706879199`,
  including `test-slow`. This commit does not attest itself.
- The laboratory image installs from the hashed wheelhouse. The install step
  has no network. The base is Debian bookworm pinned by digest. Astra Linux
  and RED OS were not tested.
- The evidence manifest attests main `0aa2ecf` / push run `38647110145`,
  including `test-slow`. This commit does not attest itself.
- The evidence manifest attests main `246a850` / push run `38645887703`,
  including `test-slow`. This commit does not attest itself.
- The evidence manifest attests main `f7a8a2e` / push run `38634344366`,
  including `test-slow`. This commit does not attest itself.
- A CSV bundle requires `manifest.json` (encoding, delimiter, source timezone,
  provenance, export version). A 22:00–06:00 local shift is one window on the
  next date. A personnel number becomes an eight-hex crew code; the salt is
  not stored. The same CP1251 extract without the manifest is refused.
  There is no offline image and no Astra run.
  Dispatch `37704013170` checked `2a45feb` on Linux, including `test-slow`.
- `POST_DOWN`, `PART_DELAY`, `CREW_ABSENT`, `DURATION_OVERRUN`, and `URGENT_JOB`
  change the card and recheck the issued plan. `replan_disruption` freezes
  visits the event missed, including those that start inside the next 8 hours.
  On tiny seeds 1–30 the five types gave `false_accept` 0. A packed lane can
  still return `PARTIAL` when the hole is early; the demo takes the latest visit.
  Dispatch `37702688921` checked `6d7325d` on Linux, including `test-slow`.
  That run is not an attestation of main, and this note is not part of it.
- Operator decisions are a hash chain. `repairflow decide` checks the plan
  hashes and will not accept a non-zero exit. `repairflow log verify` catches
  a swapped or edited line, and a truncated tail when the tip hash is known.
  A legacy log without the chain is read-only.
- `schedule_hash` identifies a plan without the machine runtime.
  `result_hash` and `config_hash` still include that runtime.
  `repairflow check --verify-hashes` checks the new field.
- The wheel target no longer force-includes `src/repairflow` on top of
  the package list. A real wheel was adding `repairflow/__init__.py` twice.
- `requirements-lock.txt` is a universal hash freeze from
  `uv pip compile --generate-hashes`. `pydantic` is `2.13.5`.
  The SynAPS git pin stays a commit SHA with no wheel hash.
  CI installs with `--require-hashes` on `ubuntu-24.04`.
  `tzdata==2026.3`, now a runtime dependency of the CSV ingest, is in the
  lock with its hashes on every platform.
- Public pages are rewritten in plain language. Commands, verdict words, and
  the generated evidence table stay as they are. No score is copied.
- The evidence manifest attests main `93320f1` / push run `38629025631`,
  including `test-slow`. This commit does not attest itself.
- The boundary diagram runs top to bottom, so the node labels stay inside
  the repository column.
- The README gained a problem statement, a contents list, exit codes, a
  working cycle with the artifact of each command, a Mermaid boundary
  diagram, a reason-code table, a comparison with open schedulers, a
  documents table, and citation, contribution, and security pointers. The
  evidence table is unchanged and no score is copied.
- Dispatch `38618458299` on `a4e4e90` killed 1814 of 1922 and left 108.
  The four survivors that had no equivalent reason died. None were born.
  Every remaining survivor already has a written equivalent reason. This
  dispatch is not an attestation, and the README does not copy the score.
- A kernel crew with the required skill stays bound, and a kernel auxiliary
  that is on the visit is not missing. A rotable draw before its receipt is
  not a consumable stockout. These tests are not in 1810/1922. The README
  does not copy the score.
- Dispatch `38565194050` on `04ad612` killed 1810 of 1922 and left 112.
  The ten max-lag precedence mutants died. `complete = False` changed to
  `complete = True` died after the sink sort; that id is now 25. Four
  survivors still have no equivalent reason. This dispatch is not an
  attestation, and the README does not copy the score.
- Dispatch `38555693129` on `eef52f8` killed 1798 of 1921 and left 123.
  Against the previous artifact, 211 died and none were born. Fifteen of
  those survivors still have no equivalent reason. `_capacity_overlaps` 9
  is equivalent because setup always replaces the start. This dispatch is
  not an attestation, and the README does not copy the score.
- Exchange-pool sinks are sorted by operation id. A complete card still
  returns at the latest sink, and any missing sink still withholds the
  return. The order no longer depends on set iteration. This is not in
  1587/1921, and phase 1 stays open.
- Reading the 272 survivors that had no equivalent reason: 45 now have
  one, taken from the mutant body, including equal `model_dump` modes and
  the two `_named_calendar_fit` returns that validation never reaches. 227
  still do not. `_completion_times` 24 is one of them and is not equivalent.
  `tests/test_kernel_binding.py` and `tests/test_open_edges.py` assert the
  other 226. Those tests are not in 1587/1921. This is not an attestation
  of main, and the README does not copy the score.
- A recount of the four scheduled mutmut artifacts matches the recorded
  score: 1587 killed, 334 alive, identical exit codes, 62 equivalents still
  alive, 272 without a reason. `_job_of` 6 and `_op` 3 are not equivalent.
  `_spare_receipts` 23 is. New tests require the assigned post and crew, a
  partial auxiliary window, a negative return lag, an always-open shop post,
  and an unknown operation outside the horizon. They are not in 1587/1921.
  This is not an attestation of main.
- Four scheduled mutmut runs on `b7c8c29` agree: 1587 of 1921 killed,
  334 alive. The runs are `37908445280`, `38037961461`, `38126032914`,
  and `38228010896`. Exit codes are only 0 and 1. `tests/test_more_survivors.py`
  is in that tree. Dispatch `37829096222` on `e027edd` killed 1562 and left
  359; it did not contain that file. Sixty-two of the 334 have an equivalent
  reason. The other 272 do not. Phase 1 stays open. These runs are not an
  attestation of main, and the README does not copy the score.
- Survivor tests require an unknown duration policy, a missing return lag of
  zero, a rotable marked only by `mode`, two returns at one moment, one return
  against a demand of two, a job with no operations, a later return after an
  incomplete job, preemptive work that ignores a closed unattended calendar
  and an unused auxiliary, and violation order. A subset check ignores a
  missing predecessor. `_precedence` 1, `_duration_violation` 38,
  `spare_is_rotable` 12 and 16, and the `PYTHON` model dump are equivalent.
  These tests are not in the 1261/1921 score. Dispatch `37829096222` does not
  contain this file and is not an attestation of main.
- Dispatch `37810297431` on `e364f34` uploaded `fault-campaign-nightly`.
  It checked 109665 plans, with `false_accept` 0 and `false_reject` 0, the
  same `input_hash` as the committed Windows file. mutmut was skipped. This
  is not an attestation of main.
- `mutmut` 3.8.0 on Linux run `37797011451` (`e54e33a`) killed 1261 of 1921
  mutants and left 660 alive. Thirty-four ledger mutants died and none were
  born. Checker, capacity, and lane setup did not move. The five named
  exchange and rotable skips are among those deaths. Identity tests and
  boundary tests are not in this score. This is not an attestation of main.
- Boundary tests pin the horizon edges, an equal due date and deadline, the
  min-policy length, a zero spare, a receipt that spends the stock, draw order
  by operation id, max lag, preemptive setup edges, setup overlap, an unbound
  frozen crew, and which sink returns a unit. A ledger `Violation` does not
  fill a missing suggestion, so those sentences are required. Checker calls
  that only drop `suggested_relaxation` stay equivalent, including nine further
  call sites. `_violation` default severity, its `StrEnum` code, and the unused
  message fallback are equivalent. These tests are not a new mutation score.
  A dispatch uploads the uncapped campaign only when `run_nightly` is true, and
  can skip mutmut when `run_mutation` is false. Dispatch `37810297431` is
  that upload.
- A violation keeps the visit, the ids, and the sentence that named it.
  Replacing an explicit suggestion with `None` stays equivalent, because
  `_violation` fills that gap from the same table. The lane overflow
  `continue` to `break` is equivalent for every caller: only the first
  overflow is read. These notes are not a new mutation score.
- `mutmut` 3.8.0 on Linux run `37759423830` (`de135ae`) killed 1227 of 1921
  mutants and left 694 alive. The eight named spare, release, auxiliary, and
  same-post setup skips died in that run. Ledger did not move. `7be8040` is
  not part of the score. This is not an attestation of main.
- A different unit type must not hide a later pool return, a healthy pool must
  not hide the next pool, and a skipped rotable row must not hide a later clash.
  Those tests are not in run `37759423830` or in the 1161/1921 score.
- A skipped spare, an unknown auxiliary, and a setup row on the same post must
  not hide the next finding. Those tests are not in the 1161/1921 mutation score.
- `mutmut` 3.8.0 on Linux run `37743200619` (`13dbb9d`) killed 1161 of 1921
  mutants and left 760 alive. Run `37742695440` (`e8f6efa`) had killed 1126.
  The four notary modules did not change between those commits. The README
  does not copy the score. Spare-receipt skips, an unknown auxiliary, and a
  setup skip on the same post were still alive. This is not an attestation
  of main, and it does not include `e89eefd`.
- `tests/oracle_minutes.py` is an independent minute oracle. It imports only
  `repairflow.model`, refuses a horizon over eight days or a timestamp off the
  minute, and is checked on hand-built plans. It does not judge the exchange-pool
  ledger.
- `mutmut` 3.8.0 on Linux run `37697094085` (`4167df4`) killed 1120 of 1921
  mutants and left 801 alive. That score is not in the README. Four capacity
  survivors are equivalent; the wrapped error sentence is now matched in full.
  Five lane survivors are covered by new tests and were still alive in that run.
  The other checker and ledger survivors are not marked equivalent. A skipped
  notary row must not hide the next finding.
- The uncapped fault campaign on this Windows host checked 109665 plans,
  with `false_accept` 0 and `false_reject` 0 (`docs/fault-campaign-nightly.json`).
  The 10080 prefix stays the committed slow-test matrix. Some negative shifts
  in the full matrix are `may_pass`: both sides accept them. This file is not
  a scheduled CI artifact and not an attestation of main.
- Fault campaign v2 labels each mutation with that oracle. The committed
  matrix checks 10080 plans across `tiny` and `repair-site-mvp`, seeds 1–30,
  and GREED, EDD, ATC. `false_accept` is 0 and `false_reject` is 0. 9321 are
  `must_reject` and 759 are `may_pass` (a later shift or another post that
  both sides still accept). The nightly path keeps every applicable mutation.
  That uncapped run is not in this commit. `mutmut` is not run.
- Public claim pages are scanned against `docs/BANNED_CLAIMS.txt`.
  The two literature pages were renamed so a banned word is not a file name
  or a heading. A negation is an exact line in
  `docs/banned-claims-allowlist.txt` with its own reason. README measurements
  outside the generated evidence block are removed.
- The evidence manifest attests main `04ad612` / push run `38563996424`,
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
