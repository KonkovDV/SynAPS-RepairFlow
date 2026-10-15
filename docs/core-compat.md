# Совместимость с ядром

Закреплённый коммит: `f939727cd9369fd9b36438bfac7198f0c39c6d3b`.

Этот пин — `cf10ca3e8be39d9a46e5d983de75a8066f66ca39` плюс календари смен
у вспомогательных ресурсов. Манифест доказательств аттестует RepairFlow `3f84202`:
прогон после вливания той ревизии шёл на том же пине.

Проверено на этом пине:

| Символ | Есть |
| --- | --- |
| `solve_schedule` / `repair_schedule` | да |
| `ScheduleProblem` chain rule (`predecessor_op_id` follows `seq_in_order`) | да |
| `verify_schedule_result(problem, result)` | да |
| `FeasibilityChecker.check(problem, assignments, *, exhaustive=False, strict_setup_matrix=False, strict_grain=False, scope=None)` | да |
| `proven_hard_violations` | да |
| `pin_issued_plan` / `normalize_schedule_problem_data` | да |
| `SolveRegime` | `NOMINAL`, `RUSH_ORDER`, `BREAKDOWN`, `MATERIAL_SHORTAGE`, `INTERACTIVE`, `WHAT_IF` |
| `AuxiliaryResource.calendar` | `list[ShiftInterval]`; пустой список значит круглосуточно |

RepairFlow вызывает `FeasibilityChecker.check` с `exhaustive=True` и
`strict_setup_matrix=True`.

## Предел размера CP-SAT

`CPSAT_OPS_CAP` — 100 операций на поданном экземпляре. `plan` через CP-SAT или
ремонт ядра выше этого числа возвращает записанный отказ (`CPSAT_OPS_CAP`)
и не вызывает `solve_schedule` или `repair_schedule`. На синтетической карте
с одним навыком и опубликованными сменами CPSAT-10 вернул проверенный план на 100
операциях и ушёл в тайм-аут с пустым планом на 120. Предел равен этому проверенному
число. Это не измеренный предел настоящего цеха и не заявление, что экземпляр
из 100 операций доходит до `optimal`. Доменные списочные решатели пределом не задеты.

## Граница календарей

Доменная модель держит календари постов, бригад и оснастки.
Непустой календарь с персоналом компилируется в `ShiftInterval` на ресурсе ядра.
CP-SAT и `FeasibilityChecker` держат занятость `[start - setup, end]`
внутри одного из этих интервалов.

`KERNEL_CALENDAR_UNSUPPORTED` остаётся в трёх случаях, которые ядро всё ещё не умеет
изобразить, не перевернув доменное правило:

- календарь с персоналом и без окон (пустой список в ядре значил бы круглосуточную работу);
- пул одинаковых навыков, чьи бригады не делят один список смен;
- прерываемая операция на опубликованной смене бригады или оснастки (ядро требует
  одно окно и не считает открытые минуты через разрыв).

`plan()` вызывает `assert_kernel_calendar_compatibility` до `solve_schedule`,
а ремонт сбоя через ядро — до `repair_schedule`. Доменные FIFO,
GREED, EDD и ATC так не делают: календари они держат сами.
Ресурс без персонала компилируется как открытый. Пропавший `calendar_id` остаётся открытым.
