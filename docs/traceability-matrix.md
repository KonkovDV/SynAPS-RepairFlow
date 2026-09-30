# Requirements traceability matrix

Status is intentionally conservative: `implemented` means covered by code and tests, `documented` means a boundary exists but the capability is not complete, and `blocked` means it must not be claimed in a pilot submission.

| Requirement | Status | Evidence / next gate |
|---|---|---|
| Strict domain schema and UTC instants | implemented | `src/repairflow/model.py`, contract tests |
| Linear technology-card validation | implemented | `tests/test_dag_and_setup.py` |
| Convergent DAG repair flow | blocked | implement compiler before claiming split/join support |
| Finite posts and setup matrix | implemented | adapter, checker, setup tests |
| Crew skills and concrete assignment | implemented with boundary | adapter/checker tests; individual calendars remain limited |
| Auxiliary capacity and calendar | remediation in PR | red-team regression tests; await CI |
| Full coverage as a verification condition | remediation in PR | partial-plan regression test; await CI |
| Independent checker source boundary | documented, not complete | remove adapter import from `checker.py`; add AST gate |
| Spares as consumable inventory | implemented | checker tests; rotable semantics are roadmap |
| Soft due dates versus hard deadlines | blocked | add explicit deadline field and objective metric |
| Disruption replan | implemented with boundary | frozen assignments and replan tests |
| Independent canonical metrics | blocked | add shared `metrics.py` and baseline parity tests |
| Reproducible hashes and SynAPS pin | implemented with boundary | pin regression and evidence tooling; full transitive lock pending |
| Full dependency hashes and SBOM | blocked | generate lock/SBOM in release workflow |
| Offline/shadow boundary | documented | threat model, ADR-0003, pilot protocol |
| Operator acceptance log | documented | JSONL contract; implementation and storage gate pending |
| FTIM/MIC application readiness | blocked | legal entity, rights chain, named owner, data agreement |
| TRL 6 claim | blocked | current declared level is TRL 4 |
| Customer effect / savings claim | blocked | requires baseline, signed data slice, and reproducible analysis |
