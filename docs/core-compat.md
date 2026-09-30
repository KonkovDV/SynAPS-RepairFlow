# Core compatibility

Pinned commit: `6178c93b705ff58be21fa74a98651883a2da1169`.

The plan named `cf10ca3e8be39d9a46e5d983de75a8066f66ca39` as the preferred pin and
`6178c93b…` as the fallback already used by GridPlan. This repository stays on the
fallback. The installed package's `direct_url.json` records that same commit, and
the chain rule the plan describes is present here.

Checked on this pin:

| Symbol | Present |
| --- | --- |
| `solve_schedule` / `repair_schedule` | yes |
| `ScheduleProblem` chain rule (`predecessor_op_id` follows `seq_in_order`) | yes |
| `verify_schedule_result(problem, result)` | yes |
| `FeasibilityChecker.check(problem, assignments, *, exhaustive=False, strict_setup_matrix=False, strict_grain=False, scope=None)` | yes |
| `proven_hard_violations` | yes |
| `pin_issued_plan` / `normalize_schedule_problem_data` | yes |
| `SolveRegime` | `NOMINAL`, `RUSH_ORDER`, `BREAKDOWN`, `MATERIAL_SHORTAGE`, `INTERACTIVE`, `WHAT_IF` |

RepairFlow calls `FeasibilityChecker.check` with `exhaustive=True` and
`strict_setup_matrix=True`. Auxiliary resources still have no calendar. Crew
shift windows are enforced by the domain checker, not by the kernel pool.

`cf10ca3e` was not swapped in. Moving the pin without recapturing the lab
fixtures would break the three-way SHA lock (`pyproject.toml`,
`requirements-lock.txt`, `versions.py`).
