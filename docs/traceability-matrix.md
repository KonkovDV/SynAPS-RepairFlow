# Requirements traceability

`implemented` means code and tests on `main`. `documented` means a boundary or a contract without the feature. `blocked` means it must not be claimed in a pilot submission.

| Requirement | Status | Evidence |
|---|---|---|
| Strict domain schema and UTC instants | implemented | `src/repairflow/model.py`, `tools/export_schemas.py` |
| Convergent DAG repair card | implemented | `src/repairflow/dag_compiler.py`, `tests/test_dag_compiler.py`, ADR-0002 |
| Finite posts and setup matrix | implemented | adapter, checker, setup tests |
| Crew skills and a named crew on the published plan | implemented | `checker_primitives.bind_concrete_crews` |
| Crew and aux calendars, including an empty calendar | implemented | domain checker, `tests/test_verdict_safety.py` |
| Crew calendars inside the kernel model | documented | kernel solve and kernel repair refuse `KERNEL_CALENDAR_UNSUPPORTED`; domain FIFO/GREED/EDD still enforce them |
| Full coverage as a verification condition | implemented | `allow_partial_plan` cannot yield exit 0 |
| Checker independent of the adapter | implemented | `checker.py` imports `checker_primitives` only |
| Blocking spares | implemented | checker spare tests |
| Exchange pool as a stock ledger | implemented | `src/repairflow/ledger.py`, ADR-0004 |
| Inspection that freezes issued work | implemented | `repairflow inspect`, ADR-0005 |
| Soft due date versus hard deadline | implemented | `DUE_MISSED` versus `DEADLINE_MISSED` |
| Disruption replan with frozen slots | implemented | replan tests |
| Canonical metrics and hash verification | implemented | `src/repairflow/metrics.py`, `repairflow check --verify-hashes` |
| SynAPS commit pin | implemented | `tools/verify_lock.py` |
| OR-Tools pin and direct SBOM | implemented | `ortools==9.15.6755`, `repairflow.sbom` |
| Transitive wheel hashes and a signed artifact | blocked | `docs/sbom-and-provenance.md` |
| Offline / shadow boundary | documented | threat model, ADR-0003, pilot protocol |
| Operator acceptance log | documented | JSONL contract; no writer |
| `POST_DOWN`, `PART_DELAY`, route-variant catalogue | blocked | `docs/limitations.md` |
| MUS/MCS explanations | blocked | cited as future work in `docs/SOTA_2026.md` |
| FTIM/MIC application readiness | blocked | legal entity, rights chain, named owner, data agreement |
| TRL 6 | blocked | declared level is TRL 4 |
| Customer effect or a savings claim | blocked | needs a baseline, a signed slice, and a reproducible analysis |
