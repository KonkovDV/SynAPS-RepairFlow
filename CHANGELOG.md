# Changelog

## Unreleased

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
