# Red-team remediation

Date: 2026-09-30. This page describes `main`. It does not describe an import-time patch of the checker.

## Closed in the checker and the model

- **Auxiliary calendars.** Setup plus processing must sit inside one window of the aux calendar. A referenced calendar with zero windows is unavailable. The same rule applies to posts and crews. A non-empty shift is compiled into `AuxiliaryResource.calendar`. A zero-window attended calendar is not compiled as the kernel's 24/7 empty list.
- **Coverage.** `allow_partial_plan` does not hide a missing operation. The status is `PARTIAL` and the exit code is 2.
- **Checker primitives.** `reverse_ids` and `lookup_setup_minutes` used by the notary live in `checker_primitives.py`. `bind_concrete_crews` is a planner publication step, not a checker repair. `checker.py` does not import `repairflow.adapter`. A missing matrix cell, including a same-state cell, is `None`. The checker reports `MISSING_SETUP`. The kernel compile inserts 0 only when `policy.missing_setup` is `zero`.
- **Deadlines.** `due_date` is the KPI `DUE_MISSED`. `Job.deadline` is `DEADLINE_MISSED`. `Operation.latest_finish` is `WINDOW_BROKEN`.
- **DAG.** Acyclic cards compile. Cycles and an empty eligible-post list are validation errors.
- **Evidence.** Unified metrics, `check --verify-hashes`, runtime manifest inside `config_hash`, OR-Tools `9.15.6755`, and a direct CycloneDX SBOM.

Regression tests: `tests/test_verdict_safety.py`, `tests/test_dag_compiler.py`, `tests/test_exchange_and_inspection.py`, `tests/test_metrics_and_hashes.py`.

## Still outside this repository

1. A writer for the operator decision log.
2. MUS/MCS explanations, `POST_DOWN`, `PART_DELAY`, and a route-variant catalogue.
3. A hash lock of every transitive wheel, and a signed release artifact.
4. A kernel encoding of a closed calendar, a mixed skill-pool shift, or preemptive open-minute counting. Non-empty shifts are compiled. The domain checker still enforces the rest.
5. A named business owner, a legal entity and IP basis, and a signed data agreement for any real pilot.

`claim_status=verified` means full coverage and an empty hard notary. It does not mean optimality, a safety certificate, legal compliance, deployment, or a customer effect.
