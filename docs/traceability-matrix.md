# Requirements traceability

`implemented` means code and tests on `main`. `documented` means a boundary or a contract without the feature. `blocked` means it must not be claimed in a pilot submission.

| Requirement | Status | Evidence |
|---|---|---|
| Strict domain schema and UTC instants | implemented | `src/repairflow/model.py`, `tools/export_schemas.py` |
| Convergent DAG repair card | implemented | `src/repairflow/dag_compiler.py`, `tests/test_dag_compiler.py`, ADR-0002 |
| Finite posts and setup matrix | implemented | adapter, checker, setup tests |
| Crew skills and a named crew on the published plan | implemented | planner names the crew on publication; the checker rejects `CREW_UNBOUND` |
| Crew and aux calendars, including an empty calendar | implemented | domain checker, `tests/test_verdict_safety.py` |
| Crew calendars inside the kernel model | implemented | non-empty shifts compile to `AuxiliaryResource.calendar`; empty, mixed-pool, and preemptive cases still refuse `KERNEL_CALENDAR_UNSUPPORTED` |
| CP-SAT on more than 80 operations | implemented | recorded `CPSAT_OPS_CAP` refusal; the exact solver is not called |
| Full coverage as a verification condition | implemented | `allow_partial_plan` cannot yield exit 0 |
| Checker independent of solver search | implemented | `checker.py` does not import planner search or `synaps.solvers`; the published verdict also reads the pinned SynAPS feasibility checker |
| One crew and a known aux kind on a kernel assignment | implemented | `AMBIGUOUS_CREW`, `UNKNOWN_RESOURCE`, `tests/test_red_team_notary.py` |
| Verified only for an admissible kernel status | implemented | `feasible`, `optimal`, or explicit `domain_only` |
| Predecessor lag, consumable receipts, skill expiry | implemented | `tests/test_domain_semantics.py`; v1 `predecessor_ids` stays lag 0 |
| Shop plan checked without the kernel | implemented | `repairflow verify-plan`; claim `domain_verified`; `tests/test_shop_plan.py` |
| Blocking spares | implemented | checker spare tests |
| Exchange pool as a stock ledger | implemented | `src/repairflow/ledger.py`, ADR-0004 |
| Inspection that freezes issued work | implemented | `repairflow inspect`, ADR-0005 |
| Soft due date versus hard deadline | implemented | `DUE_MISSED` versus `DEADLINE_MISSED` |
| Disruption replan with frozen slots | implemented | replan tests |
| Canonical metrics and hash verification | implemented | `src/repairflow/metrics.py`, `repairflow check --verify-hashes` |
| SynAPS commit pin | implemented | `tools/verify_lock.py` |
| OR-Tools pin and direct SBOM | implemented | `ortools==9.15.6755`, `repairflow.sbom` |
| Installed wheel or sdist identity, distinct from the file manifest | implemented | `repairflow.artifact_record`; signature stays `absent` |
| Dependency lock of archive SHA-256 values | implemented | `repairflow.dependency_lock`; `locked` only when every hash is present |
| Signed artifact | blocked | signature status stays `absent`; this build has no release key |
| Offline / shadow boundary | documented | threat model, ADR-0003, pilot protocol |
| Operator acceptance log | documented | JSONL contract; no writer |
| `POST_DOWN`, `PART_DELAY`, route-variant catalogue | blocked | `docs/limitations.md` |
| Rotable return lag inside the kernel model | documented | domain ledger is the authority; kernel silence is not `verified` |
| Deletion-minimal witness for one hard code | implemented | `explanations.py`; not a CP-MUS or MCS |
| MUS/MCS explanations | blocked | cited as future work in `docs/SOTA_2026.md` |
| FTIM/MIC application readiness | blocked | legal entity, rights chain, named owner, data agreement |
| TRL 6 | blocked | declared level is TRL 4 |
| Customer effect or a savings claim | blocked | needs a baseline, a signed slice, and a reproducible analysis |
