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
`strict_setup_matrix=True`.

## CP-SAT size boundary

`CPSAT_OPS_CAP` is 80 operations on the submitted instance. A CP-SAT `plan` or
kernel repair above that count returns a recorded refusal (`CPSAT_OPS_CAP`)
and does not call `solve_schedule` or `repair_schedule`. The cap is not a
measured limit of a real shop and not a claim that an instance of 80 operations
reaches `optimal`. Domain list solvers are unaffected.

## Calendar capability boundary

The domain model supports calendars on work centres, crews and auxiliary resources.
The pinned SynAPS `AuxiliaryResource` contract has no calendar field. Consequently,
auxiliary-resource and crew calendars cannot be compiled into the kernel without
silently dropping constraints. They are represented by the stable compatibility
reason `KERNEL_CALENDAR_UNSUPPORTED`. `plan()` calls
`assert_kernel_calendar_compatibility` before `solve_schedule`, and kernel
disruption repair calls it before `repair_schedule`. Domain FIFO, GREED and EDD
do not: they keep enforcing those calendars in the list scheduler and the
independent checker. No upstream API extension is assumed here.

`cf10ca3e` was not swapped in. Moving the pin without recapturing the lab
fixtures would break the three-way SHA lock (`pyproject.toml`,
`requirements-lock.txt`, `versions.py`).
