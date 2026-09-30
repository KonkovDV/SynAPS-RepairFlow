# Benchmark protocol

Full claim ladder and academic anchors: [`SOTA_EVIDENCE_PROTOCOL.md`](SOTA_EVIDENCE_PROTOCOL.md).

- Tag every number `synthetic_experiment` unless a customer holdout exists.
- Same input hash for FIFO vs GREED vs CP-SAT.
- Record RepairFlow version, full SynAPS SHA, config hash, seed, result hash.
- OPTIMAL is allowed only for CP-SAT with a proven bound and empty checker.
- Do not mix kernel 50k evidence into RepairFlow claims.
- Store JSON under `benchmark/results/` (gitignored payloads except `.gitkeep`).
- CLI: `repairflow benchmark --out bench` writes `benchmark.{json,md,html}` plus per-instance reports.
- Default matrix: `tiny` 1/42/99 and `repair-site-mvp` 42/7/13. `--preset` filters those pairs; `--preset` plus `--seeds` is an explicit cartesian product.
- Frozen `JOB-01-03` binds a crew that covers the operation skills (electrical restore → `CREW-ELEC`), so electrical seeds are not excluded from the portfolio.
- Exit `0` only if every GREED row is checker-verified; otherwise exit `2`.
- FIFO is an infeasible compact packing. A shorter FIFO makespan is not a quality win; report FIFO hard violations and GREED makespan as primary KPIs.
- Makespan, tardiness, setup and coverage in `objective` are recomputed from the horizon start for every solver. The solver's own numbers stay in `metadata.solver_objective`.
- `EDD` is a capacity-aware list scheduler (due date, then priority). It is a feasible baseline. Select it with `--solvers FIFO GREED EDD`.
- CP-SAT receives the domain GREED assignment as `warm_start_assignments` unless the caller already passed one.
- The published CI matrix stays the six pairs above. A 30-seed study is an explicit `--preset` plus `--seeds` product, not the default.
- CI uploads `bench/` even when the job fails so dirty cells remain inspectable.
