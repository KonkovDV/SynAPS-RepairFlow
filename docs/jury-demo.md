# Jury demo

Synthetic site produced by `repairflow demo`. Not SVARZ. Do not recite counts from memory. Read them from the files the command writes, or from the generated evidence table in the README.

## What the demo does now

1. **Input.** `repairflow demo --out out` writes `out/repair-site-mvp.json`.
2. **FIFO.** `out/fifo.json`. The readiness line treats FIFO as a failing plan: violations are present and the exit is not success. Say what the file shows.
3. **GREED.** `out/greed.json` is the checked candidate. Say that the system built a candidate from the declared rules and that the checker accepted or rejected it. Do not say that AI solved it.
4. **CP-SAT.** On the tiny preset, `out/cpsat.json`, only when the demo does not skip it. Call the run exact only when that file's claim says so.
5. **Disruption.** `out/replan.json` and `out/replan-diff.json`. Speak about frozen work only when `broken_frozen_assignments` in the diff is empty. The demo also writes `out/post-down.json`: the latest visit's post is closed for that interval. The readiness line must show `CALENDAR_BROKEN` on the old plan, `replan_verified=True`, and `frozen_moved=0`. An early hole on a packed lane can still leave the list repair partial.
6. **Broken candidate.** `out/broken.json` is the GREED plan after a deliberate corruption. The readiness check requires a failing exit.

## Later beats, not part of this command

The submission script adds three beats `repairflow demo` does not perform:

- a shop sheet through `repairflow verify-plan` (a clean sheet is `domain_verified`, not `verified`);
- an explanation of an infeasible card (today: a deletion-minimal witness, not MUS/MCS);
- an operator log line and `repairflow log verify` (that log command is not implemented).

No figure on this page is a result. Results stay in the output files and in `docs/evidence-manifest.json`.
