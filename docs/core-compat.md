# Core compatibility

Pinned commit: `1f7d5e0ede2944d21579574edf84976fe5e78808`.

This pin is `cf10ca3e8be39d9a46e5d983de75a8066f66ca39` plus auxiliary-resource
shift calendars. `6178c93b705ff58be21fa74a98651883a2da1169` remains the kernel
named by the attested evidence manifest until a later docs-only attestation.

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
| `AuxiliaryResource.calendar` | `list[ShiftInterval]`; empty means 24/7 |

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
A non-empty attended calendar is compiled to `ShiftInterval`s on the kernel
resource. CP-SAT and `FeasibilityChecker` keep occupancy `[start - setup, end]`
inside one of those intervals.

`KERNEL_CALENDAR_UNSUPPORTED` remains for three cases the kernel still cannot
represent without inverting the domain rule:

- an attended calendar with zero windows (a kernel empty list would mean 24/7);
- a fungible skill pool whose crews do not share one shift list;
- a preemptive operation on a published crew or aux shift (the kernel requires
  one window and does not count open minutes across a gap).

`plan()` calls `assert_kernel_calendar_compatibility` before `solve_schedule`,
and kernel disruption repair calls it before `repair_schedule`. Domain FIFO,
GREED, EDD and ATC do not: they keep enforcing those calendars themselves.
An unattended resource is compiled as open. A missing `calendar_id` stays open.
