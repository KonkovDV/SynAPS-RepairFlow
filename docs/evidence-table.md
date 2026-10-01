# Unified solver evidence table

`repairflow.evidence_table.build_evidence_table` creates a machine-readable comparison for multiple solver results generated from one `RepairFlowProblem`.

The output schema is `repairflow.evidence_table.v1`. Rows are sorted by the caller's solver label and preserve, rather than infer, the following boundaries:

- `status`, `claim_status`, `solver_class`, `kernel_status`, and `optimality_scope`;
- `verified_feasible` and the actual process `exit_code`;
- input, configuration, and result hashes;
- RepairFlow version, pinned SynAPS commit, claim level, and data provenance;
- the same recomputed metrics used by the rest of the application.

The table refuses to combine results with different `input_hash` values. Its metric contract makes the common denominator explicit:

- makespan starts at `planning_horizon.start`;
- post utilization uses `sum_work_center_max_parallel * horizon_minutes`;
- coverage is assigned operations divided by total operations;
- verification means an independent checker exit of `0` with full coverage;
- optimality is a recorded row field and is never inferred from a heuristic solver name.

`tools/pack_evidence.py` writes `evidence-table.json` beside the problem, plans, checker output, and hashes. The table has its own deterministic `table_hash`, and its evidence stamp retains the common input hash and the ordered configuration-hash list.

This is comparison and provenance evidence for synthetic laboratory experiments. It is not a customer KPI, production result, safety certification, savings claim, sponsor statement, CP-MUS/MCS, or global/heuristic optimality claim. A pilot archive still needs an agreed baseline, data slice, operator protocol, and separately verified artifact provenance.
