# RepairFlow SOTA and evidence protocol

## Purpose

RepairFlow is a domain adapter for auditable repair scheduling. The mathematical class is established: flexible job-shop / resource-constrained scheduling with sequence-dependent setup times, auxiliary resources and skills. The project must therefore compete on **correctness, auditability, reproducibility and pilot discipline**, not on an unsupported claim of a new solver.

Academic anchors:

- worker-constrained FJSP with sequence-dependent setup times: https://doi.org/10.1007/s00291-018-0537-z
- multi-resource CP/ALNS scheduling: https://doi.org/10.1016/j.ejor.2024.08.010
- FJSP with preventive maintenance and setup times: https://doi.org/10.1109/WSC57314.2022.10015273
- rolling-stock maintenance under uncertain durations: https://doi.org/10.1016/j.jrtpm.2020.100177
- technician routing and scheduling: https://doi.org/10.1007/978-3-031-12914-8_30
- infeasibility certificates: https://doi.org/10.1016/j.orl.2008.08.003

## Evidence hierarchy

Every result must carry four independent labels:

1. **data provenance** — `synthetic`, `open_data`, `customer_data`, `experiment`, `production_verified`;
2. **solver status** — `OPTIMAL`, `FEASIBLE`, `HEURISTIC_FEASIBLE`, `PARTIAL`, `INFEASIBLE`, `NOT_VERIFIED`;
3. **claim level** — `experiment`, `benchmark`, `pilot_candidate`, `production_verified`;
4. **verification status** — independent checker empty, full coverage, explicit kernel status.

`OPTIMAL` is permitted only for a bounded exact run with a proven bound and an empty independent checker. `GREED`, `ALNS` and `RHC` never inherit that word.

## Benchmark ladder

### Level A — correctness oracle

Use 5–20 operation fixtures where CP-SAT or exhaustive enumeration is a reference. Test precedence, setup, skills, calendars, auxiliary resources, frozen assignments and spares. The primary safety metric is **false-accept rate**, which must be zero.

### Level B — domain fixture

Use the committed repair-site fixture. Compare FIFO, RepairFlow GREED and bounded CP-SAT on the same input. Report:

- hard violations;
- coverage;
- time-to-first-feasible;
- makespan;
- tardiness;
- setup minutes;
- unassigned operations;
- checker time;
- result and input hashes.

### Level C — external scheduling instances

Use public FJSP/RCPSP instances only as algorithmic sanity checks. They do not prove transport applicability. Report upper/lower bounds, gap and runtime under the same hardware and time budget. Do not merge coverage, feasibility and optimality into one score.

### Level D — disruption replay

Apply post outage, crew unavailability, spare delay and duration extension. Measure:

- repair latency;
- changed assignments;
- frozen assignments preserved;
- hard violations after repair;
- plan churn.

A shorter makespan is not sufficient if the plan is unstable for the planner.

## Domain correctness gates

The MVP deliberately uses a linear technology-card contract. `predecessor_ids` must agree with `sequence`; unsupported branching must be rejected, not silently linearised. A future DAG release must change the adapter and checker together.

Every accepted assignment must name a concrete crew when a skill is required. A skill pool alone is not an operational assignment.

Missing `idle → first_state` setup is a hard rejection. Missing setup cells are not silently interpreted as zero when policy is `reject`.

## Pilot evidence

Before any customer claim, freeze:

- one contour and one process owner;
- an anonymised `repairflow.problem.v1` extract;
- a constraint catalogue agreed by a domain engineer;
- a historical baseline;
- a holdout interval;
- an operator accept/reject log;
- a written fallback procedure.

The first pilot is read-only/shadow. No write-back is allowed. Success is a measured gap on one contour, not a city-wide KPI.

## What the project may claim now

> RepairFlow is a reproducible laboratory domain package that builds candidate repair schedules and independently checks declared hard constraints.

It may not claim industrial savings, live SVARZ or Mosgortrans use, replacement of EAM/ERP/CMMS, certified labour-law compliance, complete explainability, or optimality of heuristic schedules.
