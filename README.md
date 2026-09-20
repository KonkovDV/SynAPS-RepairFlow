# SynAPS RepairFlow

Проверяемое планирование ремонта узлов и агрегатов городского транспорта.
Тонкий доменный пакет над зафиксированным ядром [SynAPS](https://github.com/KonkovDV/SynAPS).

| | |
| --- | --- |
| Version | **0.1.0** (synthetic runnable; not a depot pilot) |
| Default branch | `main` |
| SynAPS pin | [`6178c93`](https://github.com/KonkovDV/SynAPS/commit/6178c93b705ff58be21fa74a98651883a2da1169) |
| Maturity | ISO 16290 TRL 4 — laboratory fixture |
| Status words | `heuristic_feasible` / `verified` / `OPTIMAL` only if CP-SAT proved OPTIMAL **and** the independent checker is empty |
| Process exit | `0` verified (checker empty **and** full coverage), `2` plan written but dirty, `1` usage/error |

**Allowed claim.** RepairFlow builds an alternative repair-shop schedule from a formal instance (posts, crews, skills, tooling, precedence, setups, calendars, frozen slots, blocking spares) and independently proves that hard constraints hold or names the reason they fail. It works offline / in shadow mode.

**Not claimed.** Live SVARZ or Mosgortrans data, industrial KPI, replacement of EAM/ERP/CMMS, control of vehicle pull-out, or “AI decided”.

## Install

Python 3.12+:

```bash
pip install -e ".[dev]"
repairflow version
```

The kernel is pinned to `6178c93b705ff58be21fa74a98651883a2da1169`. CI fails if the SHA in `pyproject.toml`, `src/repairflow/versions.py` and `requirements-lock.txt` diverges.

## One-command MVP

```bash
repairflow demo --out out
```

The command:

1. synthesizes a repair site (not customer data);
2. builds a FIFO baseline;
3. builds a GREED candidate;
4. checks it independently;
5. stores input/config/result hashes and the kernel SHA;
6. writes Markdown + HTML/Gantt;
7. replans a disruption without moving frozen operations;
8. checks an intentionally broken plan (exit 2);
9. solves a tiny CP-SAT case.

Exit `0` only if the clean plan verifies and the broken plan stays fail-closed.

Evidence protocol: [`docs/SOTA_EVIDENCE_PROTOCOL.md`](docs/SOTA_EVIDENCE_PROTOCOL.md). Committed JSON examples are checked against public schemas by `python tools/verify_schema.py`.

## CLI

```bash
repairflow synthesize --preset repair-site-mvp --out data/repair-site-mvp.json
repairflow solve data/repair-site-mvp.json --preset FIFO --out out/fifo.json
repairflow solve data/repair-site-mvp.json --preset GREED --out out/greed.json
repairflow check data/repair-site-mvp.json out/greed.json --report out/greed.check.json
repairflow compare data/repair-site-mvp.json out/fifo.json out/greed.json --out out/compare.json
repairflow report data/repair-site-mvp.json out/greed.json --html out/report.html --md out/report.md
repairflow demo --preset broken-seed42
repairflow benchmark --out bench
```

`repairflow benchmark` runs FIFO vs GREED on the documented synthetic matrix
(`tiny` seeds 1/42/99, `repair-site-mvp` seeds 42/7/13) and writes
`bench/benchmark.{json,md,html}`. Exit `0` only if every GREED run is
checker-verified. FIFO is an infeasible compact packing — a shorter FIFO
makespan is not a quality win.

## Architecture

```
repair data → RepairFlow model/adapter → SynAPS search → RepairFlow checker
           → Gantt · diff · conflict reasons · operator decision
```

RepairFlow does not fork SynAPS. Domain GREED is the verified closer on the 52-op
`repair-site-mvp` fixture. Kernel `RHC-GREEDY-COVER` is available and checker-clean on
`tiny`; it is not claimed verified on the larger site. Published assignments name a
concrete crew; skill-pools stay inside the kernel adapter.

## Honest scope

In: one repair contour, 20–100 operations, JSON/CSV in, JSON/Markdown/HTML out.

Out: vehicle dispatch, SCADA, EAM write-back, failure prediction, e-bus charging, road routing, labour-law rostering, promised savings percentages.
