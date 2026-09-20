# Benchmark protocol

Full claim ladder and academic anchors: [`SOTA_EVIDENCE_PROTOCOL.md`](SOTA_EVIDENCE_PROTOCOL.md).

- Tag every number `synthetic_experiment` unless a customer holdout exists.
- Same input hash for FIFO vs GREED vs CP-SAT.
- Record RepairFlow version, full SynAPS SHA, config hash, seed.
- OPTIMAL is allowed only for CP-SAT with a proven bound and empty checker.
- Do not mix kernel 50k evidence into RepairFlow claims.
- Store JSON under `benchmark/results/` (gitignored payloads except `.gitkeep`).
