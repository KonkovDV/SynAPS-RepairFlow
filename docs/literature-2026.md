# Literature review, 2026

## Problem class

RepairFlow is a constrained multi-resource maintenance scheduler: precedence, alternative posts, qualified crews, tooling, setup times, calendars, spares, an exchange-pool ledger, and disruption replanning. A repair card may be a convergent DAG. The pinned SynAPS kernel accepts a chain inside an order, so `dag_compiler` splits the card into chain segments and the domain checker still judges the original edges. See ADR-0002.

## Evidence-backed positioning

- Constraint programming is a credible industrial approach for operational maintenance scheduling with precedence, deadlines, resources, and lexicographic objectives. See Sciau et al., 2024, [DOI 10.1016/j.jairtraman.2024.102537](https://doi.org/10.1016/j.jairtraman.2024.102537).
- Independent validation is the trust boundary between heuristics and exact solvers. A 2026 technician-constrained maintenance benchmark uses a validator that shares no code with the methods under test. See [SSRN 7095162](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7095162).
- MUS/MCS-style explanations are a credible next step for disrupted industrial schedules. See Bleukx et al., CP 2025, [DOI 10.4230/LIPIcs.CP.2025.6](https://doi.org/10.4230/LIPIcs.CP.2025.6). RepairFlow does not compute MUS or MCS.
- Learned dispatching is a research direction. It is not a reason to claim an AI planner.

## Open schedulers compared

Timefold's maintenance quickstart (Apache-2.0, `timefold-quickstarts` `java/maintenance-scheduling`) treats crew overlap, a minimum start, and a maximum end as hard, and an ideal end as soft. Those hard checks are already the crew-capacity, earliest-start, and latest-finish findings. The ideal end stays a KPI here (`DUE_MISSED`), which matches their soft band. Their tag penalty is not a RepairFlow constraint. RosterSpec's published verification notes treat a schedule verdict as deterministic: it must not depend on hash or iteration order. Python does not promise set order, so exchange-pool sinks are sorted by operation id. The return is still withheld until every sink of the card is placed, and a complete card still returns at the latest sink. Their solvers, scores, and models are not imported.

## What this project claims

The contribution is the domain contract, deterministic compilation into a pinned engine, an independent fail-closed checker, reproducible hashes, and a human-reviewed shadow workflow. It is not a new optimization algorithm and not a measured customer effect.

## Benchmark plan

The CI default is FIFO versus GREED on `tiny` seeds 1/42/99 and `repair-site-mvp` seeds 42/7/13. A paper-grade study would add the instance generator, an environment manifest, EDD, a CP-SAT reference, rolling-horizon disruptions, and intervals across seeds. That wider matrix is opt-in. It is not the CI default.
