# Bounded local ATC baseline contract

## Status

The repository contains a local ATC-shaped **ordering contract** in
`repairflow.atc_baseline`. It is an evaluation baseline and is deliberately
separate from the pinned SynAPS API.

The current contract orders a caller-supplied set of operation IDs. It does
not yet replace or extend the planner's FIFO, EDD, GREED, or kernel routing.
Planner integration is a separate change and must preserve the independent
checker boundary.

## Score

For operation `i`, the score is:

```text
ATC_i = (w_i / p_i) * exp(-max(d_i - now - p_i, 0) / (k * p_bar))
```

where:

- `w_i` is the RepairFlow `Job.priority`; larger values are more urgent,
  matching the existing EDD baseline;
- `p_i` is the operation duration in minutes;
- `d_i` is the job `due_date`, or the planning-horizon end when no due date is
  present;
- `now` is supplied explicitly by the caller;
- `p_bar` is the mean duration of the supplied operation set;
- `k` is finite and strictly positive, with the reference default `k = 2.0`.

Ties are deterministic: score descending, due date ascending, duration
ascending, then operation ID ascending.

## Explicit boundary

The module does **not**:

- infer readiness or precedence feasibility;
- assign work centres, crews, auxiliary resources, or lanes;
- model setup, calendars, spares, or disruption repair;
- call or extend SynAPS;
- run the independent checker;
- produce a schedule or a `verified` verdict;
- claim `optimal`, `safe`, production, or customer performance.

A caller must pass a ready set explicitly. Duplicate or unknown operation IDs
are rejected. The explicit `now` value makes the result reproducible and
prevents hidden wall-clock dependence.

## Evidence requirements for future integration

A planner-integrated ATC baseline must record at least:

1. the exact ATC formula and `k`;
2. the explicit ready-set construction and precedence evidence;
3. the `now` convention and timezone/instant representation;
4. seed, input hash, configuration hash, result hash, and SynAPS pin;
5. independent checker output and the same unified metrics used by FIFO, EDD,
   GREED, and exact paths;
6. a bounded statement that ATC is a heuristic baseline, not an optimality
   proof.

Until those fields are bound to a planner result, the module remains an
ordering reference rather than a scheduling solver.
