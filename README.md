# SynAPS RepairFlow

> **Auditable repair scheduling for urban-transport maintenance — offline, reproducible, and fail-closed.**

[![CI](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![License](https://img.shields.io/badge/license-MIT- green)](LICENSE)

## Executive summary for the jury

SynAPS RepairFlow is a **research-grade domain adapter and independent checker** for repair-shop scheduling. It represents jobs, operations, work centres, crews, skills, tooling, sequence-dependent setup, calendars, frozen assignments, spares and exchange-pool constraints. It produces candidate schedules and then checks them independently against the declared hard constraints.

The central claim is deliberately narrow:

> Given a formal repair instance, RepairFlow can construct a candidate schedule and independently report whether the declared hard constraints hold, or return structured reasons why they do not.

This is an **offline laboratory and shadow-mode decision-support system**. It is not a dispatch system, an EAM/ERP/CMMS replacement, a safety controller, or an autonomous “AI decision maker”.

### What the repository proves today

- the domain schema rejects malformed and ambiguous inputs rather than silently repairing them;
- candidate plans are checked outside the solver search path;
- resource capacity uses a half-open interval model and an exact sweep-line peak oracle;
- setup time is part of resource occupancy where the contract requires it;
- due-date lateness is separated from a hard deadline;
- frozen assignments, calendars, precedence, skills, auxiliary resources and spares are explicit checker concerns;
- inputs, configuration, solver pin and result hashes are part of the evidence path;
- CI executes the documented quality gates on the repository state.

### What the repository does **not** prove

It does not prove industrial savings, customer accuracy, production readiness, optimality of heuristic schedules, labour-law compliance, a live SVARZ/Mosgortrans deployment, or replacement of an operational planning system. No customer or sponsor relationship is inferred from public information.

## Current evidence boundary

| Item | Current repository fact |
|---|---|
| Current `main` | [`a3621fd`](https://github.com/KonkovDV/SynAPS-RepairFlow/commit/a3621fd538019f4dcc0c681d5634c022260382e9) |
| SynAPS dependency | [`6178c93`](https://github.com/KonkovDV/SynAPS/commit/6178c93b705ff58be21fa74a98651883a2da1169) |
| Python | 3.12+ |
| Solver dependency | `ortools==9.15.6755` |
| Data | committed synthetic fixtures; no customer data in the repository |
| Maturity | laboratory fixture / TRL 4 framing; not a pilot result |
| Latest sweep-line CI run | [Actions run 36765689986](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/36765689986) |

The commit, dependency pin, dataset provenance, solver status, claim level and checker output must be read together. A number without this context is not an evidence claim.

## The problem

Repair work is a constrained production-planning problem rather than a single “best schedule” button. A valid plan must respect, simultaneously:

- technology-card precedence and convergent dependencies;
- eligible work centres and capacity;
- concrete crew assignment and required skills;
- auxiliary resources and rotable/serviceable spares;
- sequence-dependent setup and lane occupancy;
- calendars and planning horizon;
- immutable/frozen work already released;
- soft `due_date` performance targets and hard `deadline` constraints;
- disruption and inspection changes without silently changing the contract.

A solver can return a schedule-shaped object while violating one of these constraints. RepairFlow therefore treats the independent checker as a first-class safety boundary, not as a formatting step after optimisation.

## How to run the reproducible demo

Requires Python 3.12+:

```bash
python -m venv .venv
source .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -e ".[dev]"

repairflow version
repairflow demo --out out
```

The demo uses synthetic data only. It builds baseline and candidate plans, checks them independently, writes hashes and evidence artefacts, exercises a disruption path, deliberately checks a broken plan, and runs a small exact CP-SAT case. The clean path must verify; the intentionally broken path must remain fail-closed.

Useful commands:

```bash
# Create a documented synthetic instance
repairflow synthesize --preset repair-site-mvp --out data/repair-site-mvp.json

# Build candidates
repairflow solve data/repair-site-mvp.json --preset FIFO  --out out/fifo.json
repairflow solve data/repair-site-mvp.json --preset EDD   --out out/edd.json
repairflow solve data/repair-site-mvp.json --preset GREED --out out/greed.json

# Independent verification and comparison
repairflow check data/repair-site-mvp.json out/greed.json \
  --verify-hashes --report out/greed.check.json
repairflow compare data/repair-site-mvp.json out/fifo.json out/greed.json \
  --out out/compare.json
repairflow report data/repair-site-mvp.json out/greed.json \
  --html out/report.html --md out/report.md

# Replanning and benchmark matrix
repairflow inspect data/repair-site-mvp.json out/greed.json event.json \
  --out out/inspected.json
repairflow benchmark --out bench
```

A shorter makespan is not a quality win if coverage is incomplete or the independent checker reports a hard violation. The benchmark therefore reports feasibility, coverage, tardiness, setup, makespan, checker time, hashes and provenance separately.

## Architecture and trust boundary

```text
formal instance
      │
      ▼
schema + domain validation ──► reject ambiguous / incomplete input
      │
      ▼
adapter + candidate planners ──► FIFO / EDD / GREED / bounded CP-SAT
      │
      ▼
independent checker ──► hard violations, KPI violations, structured reasons
      │
      ▼
evidence bundle ──► hashes · pin · metrics · report · reproducibility
      │
      ▼
human operator decision (shadow mode; no write-back)
```

The checker does not import solver search code. It normalises the candidate into the domain representation and verifies it against the formal instance. The planner is not allowed to redefine the meaning of “feasible” after the fact.

### Capacity semantics

A resource with capacity `K` is modelled as `K` interchangeable lanes. Occupancy is half-open, `[start, end)`, so an operation ending exactly when another starts does not consume two lanes. Events at the same timestamp process ends before starts. Setup is included in the occupancy interval where required. The same sweep-line oracle is used for ordinary assignments and immutable frozen assignments.

This fixes a common pairwise-overlap error: an interval that intersects an anchor is not automatically simultaneous with every other interval intersecting that anchor. The test suite includes staggered visits, touching endpoints, setup occupancy and a property-based comparison with an independent brute-force critical-point oracle.

### Domain boundary

The project currently uses a convergent technology-card model compiled to the pinned SynAPS chain kernel. The domain checker still evaluates the original dependency semantics. DAG support is a controlled boundary, not a licence to silently linearise unsupported semantics. The exchange-pool model is a ledger over time, not a simultaneous unlimited resource pool.

## Evidence model

Every result should carry four labels:

1. **Data provenance:** `synthetic`, `open_data`, `customer_data`, `experiment`, or `production_verified`.
2. **Solver status:** `OPTIMAL`, `FEASIBLE`, `HEURISTIC_FEASIBLE`, `PARTIAL`, `INFEASIBLE`, `NOT_VERIFIED`, or equivalent error state.
3. **Claim level:** `experiment`, `benchmark`, `pilot_candidate`, or `production_verified`.
4. **Independent verification:** full coverage, empty hard-violation set, concrete kernel status, and matching input/config/result hashes.

`OPTIMAL` is reserved for a bounded exact run with a proven bound and an empty independent checker. GREED, RHC and other heuristics do not inherit the word “optimal”. A local test run is development evidence, not a CI attestation.

### False-positive safety invariant

The principal safety metric is not “average schedule quality”. It is the rate at which an invalid plan is accepted as valid:

```text
false_accept_rate = invalid_plans_accepted_as_verified / invalid_plans_presented
```

For the correctness-oracle fixtures, the target is zero. Any change that improves a KPI while increasing false acceptance is a regression, not an improvement.

## Benchmark ladder

| Level | Purpose | Evidence expected |
|---|---|---|
| A — correctness oracle | 5–20 operation fixtures | exact reference, adversarial cases, false-accept rate |
| B — domain fixture | committed synthetic repair site | same input, same seed, baseline comparison, checker and hashes |
| C — public scheduling instances | algorithmic sanity check | bounds, gap, runtime, hardware and time budget |
| D — disruption replay | post outage, crew loss, spare delay, duration extension | repair latency, churn, frozen preservation and post-repair hard violations |
| E — shadow pilot | one agreed repair contour | anonymised data slice, baseline, holdout period, operator log and rollback |

The benchmark ladder prevents a synthetic fixture from being presented as transport-industry validation. Public FJSP/RCPSP results would be algorithmic context, not proof of applicability to a depot.

## Positioning against SOTA 2026

RepairFlow does not claim a new general-purpose solver. Flexible job-shop scheduling with sequence-dependent setup, multi-resource constraints, maintenance and technician scheduling is an established research area. The defensible contribution here is the **engineering evidence boundary**:

- explicit domain semantics instead of implicit solver assumptions;
- independent fail-closed verification;
- reproducible evidence with provenance and hashes;
- adversarial and property-based tests for resource semantics;
- separation of hard feasibility, soft performance and optimality;
- an explicit path from laboratory fixture to a read-only pilot.

Relevant 2024–2026 positioning sources are recorded in [`docs/SOTA_2026.md`](docs/SOTA_2026.md) and [`docs/SOTA_EVIDENCE_PROTOCOL.md`](docs/SOTA_EVIDENCE_PROTOCOL.md), including work on flexible job-shop scheduling, multi-resource CP/ALNS, maintenance scheduling, infeasibility certificates, robust filtering and conformal uncertainty. The repository does not copy published scores into its own results and does not call a roadmap method “implemented”.

## FTIM and pilot framing

Public OSINT is used to define a responsible entry gate, not to manufacture a customer story:

- [FTIM pilot programme](https://ftim.ru/pilotirovanie/) describes testing on Moscow Transport infrastructure, a measurable hypothesis and a pilot feasible within 90 days.
- The official [SVARZ profile](https://www.mosgortrans.ru/about/branches/filial-sokolnicheskii-vagonoremontno-stroitelnyi-zavod-svarz-gup-mosgortrans/) establishes that the plant repairs transport components; it does **not** establish a RepairFlow sponsor, current planning process or Excel workflow.
- The [Moscow Innovation Cluster pilot page](https://i.moscow/pilot) lists readiness and rights requirements; RepairFlow currently declares laboratory TRL 4 and does not claim to satisfy a production pilot gate.

A responsible first pilot would be read-only and shadow-only for one agreed repair contour:

1. name a process owner and data owner;
2. agree an anonymised problem extract and constraint catalogue;
3. freeze a historical baseline and holdout interval;
4. run RepairFlow without write-back;
5. log every operator accept/reject/edit decision;
6. measure hard violations, coverage, tardiness, makespan, setup, replanning latency and plan churn;
7. keep a written rollback to the current process.

No public page above proves sponsorship, deployment, savings, safety certification or operational acceptance.

## What we learned from RailBreak

The public [`KonkovDV/RailBreak`](https://github.com/KonkovDV/RailBreak) repository is a useful documentation precedent, not evidence for RepairFlow. Its jury-facing README and supporting artefacts demonstrate practices worth carrying over:

- a one-command jury path and explicit prerequisites;
- a results table with commit, data, method, metric, denominator and threshold;
- separate documents for assumptions, results, TЗ traceability and references;
- failure campaigns and “what this does not cover” sections;
- explicit distinction between current-head evidence and historical artefacts;
- honest treatment of missing inputs and degraded modes.

RepairFlow applies the same discipline to scheduling: every claim must point to a source file, exact commit, input/seed, solver configuration, checker output and denominator. RailBreak’s odometry numbers, ROS assumptions and public transport context are not RepairFlow results.

## Reproducibility and provenance

For a reviewable result, record:

- repository commit and dependency lock;
- SynAPS commit and OR-Tools version;
- input schema version, input hash and configuration hash;
- solver class, preset, random seed and time limit;
- checker version and complete violation output;
- metric definitions, denominator and missing-data policy;
- environment, Python version and CI run URL;
- whether the data are synthetic, open, anonymised or customer-provided.

The repository’s schema and evidence tools are part of CI:

```bash
python tools/verify_schema.py
python tools/export_schemas.py
python -m ruff format --check src tests tools
python -m ruff check src tests tools
python -m mypy --strict src/repairflow
python -m pytest -q -m "not slow"
repairflow demo --out out
repairflow benchmark --out bench
```

These commands establish reproducibility for the repository fixture. They do not establish production readiness.

## Limitations and threat model

Known limitations include:

- synthetic data are not a customer validation set;
- the pinned kernel is a dependency boundary, not a proof of domain correctness;
- heuristic schedules are not optimal;
- missing or ambiguous setup, calendar, skill, spare or relation data must not be interpreted as zero risk;
- soft due-date performance must not be reported as hard feasibility;
- a checker can only prove the constraints declared in its contract;
- a plan can be mathematically feasible and still be rejected by a human operator or a changed real-world condition;
- no EAM/ERP/CMMS write-back, dispatch control, SCADA integration or safety function is present;
- no live customer data, sponsor relationship or industrial KPI is claimed.

Security and provenance guidance is in [`SECURITY.md`](SECURITY.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/sbom-and-provenance.md`](docs/sbom-and-provenance.md) and [`LICENSES.md`](LICENSES.md).

## Documentation map

- [`docs/README.md`](docs/README.md) — documentation map and reviewer rule.
- [`docs/SOTA_EVIDENCE_PROTOCOL.md`](docs/SOTA_EVIDENCE_PROTOCOL.md) — evidence hierarchy and benchmark ladder.
- [`docs/SOTA_2026.md`](docs/SOTA_2026.md) — research positioning and agenda.
- [`docs/traceability-matrix.md`](docs/traceability-matrix.md) — requirement-to-evidence mapping.
- [`docs/domain-assumptions.md`](docs/domain-assumptions.md) — domain assumptions.
- [`docs/red-team-remediation.md`](docs/red-team-remediation.md) — checker gaps and remediation.
- [`docs/benchmark-protocol.md`](docs/benchmark-protocol.md) — reproducible comparisons.
- [`docs/jury-demo.md`](docs/jury-demo.md) — demonstration script.
- [`docs/pilot-protocol.md`](docs/pilot-protocol.md) — shadow-pilot protocol.
- [`docs/osint-and-pilot-gates.md`](docs/osint-and-pilot-gates.md) — public OSINT register and gates.
- [`APPLICATION.md`](APPLICATION.md) — concise application-safe summary.
- [`CITATION.cff`](CITATION.cff) — citation metadata.

## License and contact boundary

The repository is MIT-licensed unless a file states otherwise. Third-party dependency licences are listed in [`LICENSES.md`](LICENSES.md). For security issues, use [`SECURITY.md`](SECURITY.md).

This README is a research and engineering description. It is not a customer contract, safety case, procurement commitment or production-readiness certificate.
