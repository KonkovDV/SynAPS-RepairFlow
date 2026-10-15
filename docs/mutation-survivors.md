# Выжившие мутанты

`mutmut` 3.8.0 нуждается в `os.fork`, поэтому на этой машине Windows он не идёт. В Ubuntu WSL здесь только Python 3.14, а проект проверяется на 3.12. Задание лежит в `.github/workflows/ci.yml`, на `ubuntu-latest` и Python 3.12, по расписанию или по ручному запуску. Оно мутирует `checker.py`, `capacity.py`, `ledger.py` и `lane_setup.py`, затем гоняет `pytest -m "not slow"`. Счёт ниже снят с этого линуксового задания. В README он не копируется.

Run `37696570417` mutated the four files and then stopped while collecting tests. The sandbox is `mutants/`, and that run copied only those four files. `tests/test_agent_bus.py` imports `tools`, which was not in the sandbox, and mutmut stops at the first collection error. No mutant was executed. No score.

The package now copies as `source_paths = ["src/repairflow"]`. `only_mutate` stays the four notary modules, so planner and CLI are present for imports and are not mutated. `also_copy` adds `tools`, `docs`, `benchmark`, `schemas`, and the files the fast suite opens. It does not add `src/repairflow`: that directory is the mutated tree.

## Прогон 37697094085

Linux `workflow_dispatch` [37697094085](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37697094085) on `4167df4`, mutmut 3.8.0, `pytest -m "not slow"`. The job succeeded. This is not an attestation of main, and `8a2b282` is not the commit that was mutated.

`mutants/src/repairflow/*.meta` stores `exit_code_by_key`. Exit 1 is a killed mutant. Exit 0 is a survivor. No other exit code appears. `mutmut-results.txt` lists the same 801 survivors.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 61 | 5 | 66 |
| `checker.py` | 816 | 690 | 1506 |
| `lane_setup.py` | 97 | 8 | 105 |
| `ledger.py` | 146 | 98 | 244 |
| Total | 1120 | 801 | 1921 |

The score of this run is 1120/1921. The README evidence table does not copy it.

`capacity.py`, read against the source, not guessed from the name:

- `active > peak` changed to `>=`. Equal values do not change the stored peak. Equivalent.
- The negative-capacity sentence was wrapped in `XX`. The old test used an unanchored regex, so the wrapped sentence still matched. The test now requires the whole sentence. This run still counts the mutant as survived.
- `open_rows.pop(index, None)` lost the default. A start is an earlier event than its end, so the key is present. Equivalent on that sweep.
- A start kind of 1 changed to 2. Any non-zero kind is a start, and the sweep adds 1, not the kind. Ends stay kind 0, so they still sort first. Equivalent.
- `sort(key=None)` on a 3-tuple is the same order as the explicit key. Equivalent.

`lane_setup.py`:

- The tuple appended when a lane is opened is overwritten before anything reads it. Replacing that tuple with `None`, or its empty label with `XXXX`, does not change a later read. Equivalent dead store (`mutmut_49`, `mutmut_50`).
- `continue` changed to `break` after an overflow (`mutmut_52`). The public functions use only the first overflow. The shorter private list is not a tested contract. A later section marks this mutant equivalent for every caller, because nothing reads a later overflow.
- An unknown post defaulting to 2 lanes, a tie broken by the lane tuple instead of the index, an unknown operation forced through `setup_state`, an unknown operation labelled `XXXX`, and a placement whose post is `None` are not equivalent. Tests now cover those five. This run still counts them as survived.

The other 788 survivors, in `checker.py` and `ledger.py`, are not marked equivalent. Across all 801, 59 diffs only wrap a string in `XX` and 20 replace `continue` with `break`. Those counts include mutants already named above. Many others set a violation field to `None`. A missing assertion is not an equivalent mutant.

`continue` changed to `break` drops every later row in that loop. Tests in `tests/test_skip_does_not_hide_next.py` require the later finding: an unknown operation does not hide the next unknown post, a mutable freeze does not hide the next frozen rows, and one predecessor does not hide the next. Those tests are not part of run `37697094085`. The unknown operation and the unknown post also keep the visit start, end, and operation id.

## Прогон 37743200619

The four notary modules are unchanged from `4167df4` through `13dbb9d`. Mutant ids are the same keys. Exit 1 is killed. Exit 0 is survived. No other exit code appears.

Linux `workflow_dispatch` [37742695440](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37742695440) on `e8f6efa` killed 1126 and left 795. The six deaths against `37697094085` are the wrapped capacity sentence (`excess_arrivals` 4) and the five lane holes (`_colour_lanes` 17, 42, 57, 59, 72).

Linux `workflow_dispatch` [37743200619](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37743200619) on `13dbb9d` killed 1161 and left 760. Score 1161/1921. The other jobs on that run, including `test-slow`, also succeeded. This is not an attestation of main. `e89eefd` is not the mutated commit.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 851 | 655 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 146 | 98 | 244 |
| Total | 1161 | 760 | 1921 |

The 35 deaths against the `e8f6efa` artifact are all in `checker.py`. They were still alive on `37742695440`. The skip and visit-interval tests are in `13dbb9d`, so this run does not say which of those two commits killed which key. The dead keys are:

- `_ref_and_duration` 8, 9, 12, 13, 14, 15, 17, 18, 21, 47, 48, 49, 50, 53, 54, 55, 56
- `_frozen` 4, 8, 9, 11, 16, 17, 18, 23, 38, 46
- `_precedence` 11, 33, 40
- `_calendars_windows_horizon` 40, 60, 133
- `_setup` 16
- `_skills_and_eligibility` 9

Read from the mutant copies, the `continue` to `break` deaths in that list are `_ref_and_duration` 21, `_frozen` 4 and 23, `_precedence` 11 and 33, and `_skills_and_eligibility` 9. Several others replace a violation or a field with `None`, or invert `op is not None`. `_setup` 16 changes `op is None or placed is None` into `and`.

Still alive on `37743200619`, and not marked equivalent:

- `_spare_receipts` 7 and 15, `_due_release_spares` 9, 39, 82, and 89
- `_calendars_windows_horizon` 139 (`aux is None` then `break`)
- `_setup` 19 (`op is None or placed is None` then `break`)
- `_colour_lanes` 52 (overflow `continue` to `break`; public callers use the first overflow only)
- the other checker and ledger survivors, including `None` fields this run did not assert

Tests added after that run require the later finding: an unknown operation does not hide a short receipt, a release violation, spare overuse, or setup on the same post; a spare with no receipts does not hide a short receipt; a spare that has receipts does not hide a later availability or a consumable overuse; an unknown auxiliary does not hide a closed auxiliary calendar. Those tests are on `de135ae`. Run `37759423830` is the measurement of that commit.

## Прогон 37759423830

Linux `workflow_dispatch` [37759423830](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37759423830) on `de135ae` killed 1227 and left 694. Score 1227/1921. Exit codes are only 0 and 1. The other jobs on that run, including `test-slow`, succeeded. The four notary modules are still the same text as `4167df4`. This is not an attestation of main. `7be8040` is not the mutated commit.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 917 | 589 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 146 | 98 | 244 |
| Total | 1227 | 694 | 1921 |

Against run `37743200619`, 66 mutants died and none were born. Eight are the `continue` to `break` skips the new tests name: `_spare_receipts` 7 and 15, `_due_release_spares` 9, 39, 82, and 89, `_calendars_windows_horizon` 139, `_setup` 19. Thirty replace a field with `None`. The other 28 change a condition or drop a field on those same findings. `capacity.py`, `lane_setup.py`, and `ledger.py` did not move.

Still alive on this run, and not marked equivalent: the four capacity mutants already explained, `_colour_lanes` 49 and 50, all 98 ledger survivors, and the remaining checker survivors. The exchange-pool and rotable tests that target `_exchange_pool_violations` 10 and 30 and `_rotable_spare_violations` 6, 44, and 51 are on `7be8040`. They are not part of 1227/1921. `_colour_lanes` 52 is marked equivalent below. The README evidence table does not copy this score. Phase 1 stays open because 694 survivors are not all triaged.

`_exchange_pool_violations` 10 and 30, and `_rotable_spare_violations` 6, 44, and 51, are the same `continue` to `break` shape. Tests now require a later return after a different unit type, a stockout on a second pool, and a rotable clash after a consumable, after an invalid return lag, and after an unplaced use. Those tests are not in `37759423830` and not in 1227/1921. `_colour_lanes` 52 replaces `continue` with `break` after an overflow. `lane_local_setup_placements` reads only `overflows[0]`. `lane_setup_evidence` discards the list. The first overflow is the same either way, and nothing in the package reads a later one. Equivalent for every caller. Not a change to the private list's length as a contract.

The four remaining `capacity.py` survivors are the ones already marked equivalent (`peak_concurrency` 14, `excess_arrivals` 13, `_events` 8 and 9). `_colour_lanes` 49 and 50 stay the dead store. `_colour_lanes` 52 is equivalent for every caller, as written above. `ledger.py` did not move in this score. The README evidence table does not copy 1227/1921.

Thirty survivors only replace `suggested_relaxation=SUGGESTIONS[...]` with `None` or delete that argument: `_coverage` 9, `_skills_and_eligibility` 62, 86, 111, 120, `_precedence` 20, 29, 46, 55, 74, 83, `_calendar_fit` 43, `_spare_receipts` 55, `_due_release_spares` 68, 125, 133, 149, `_setup` 39, 48, `_frozen` 15, 42, 50, `_exchange_pool_violations` 44, 51, `_rotable_spare_violations` 26, 32, 64, 74, 101, 110. The checker call sites are equivalent: `_violation` fills a missing suggestion from that same table. The eight ledger ids are not. Those functions build `Violation` directly, so a missing sentence stays empty. `tests/test_boundary_survivors.py` requires the sentence on a stockout, an early rotable, an invalid return lag, and a rotable clash.

Nine further checker survivors are the same deletion. The diff also touches the closing parenthesis, which is why the first pass missed them: `_calendar_fit` 50, `_coverage` 14, `_capacity_overlaps` 43, `_due_release_spares` 76 and 156, `_frozen` 22, `_skills_and_eligibility` 69 and 94, `_spare_receipts` 61. Equivalent for the same reason.

Inside `_violation`, four edits do not change a returned finding. Default severity `HARD` is not `kpi`, so the level stays hard (`mutmut_2`). Every caller passes a `ReasonCode`, and `str` of that enum is its value (`mutmut_4` and `mutmut_5`). Every caller that reaches `_violation` passes a non-empty message, so the `REASON_RU` arm is not evaluated (`mutmut_38` through `mutmut_41`). `mutmut_42` (`or` changed to `and`) is not equivalent: a missing auxiliary has no suggestion argument, and the table has that sentence. The new test requires it.

`_spare_receipts` 22, 25, and 28 change an event order. The opening quantity and each receipt use an empty operation id, which sorts before any real operation id. Moving the opening quantity or a receipt onto the use's order, or moving the use later, still applies the paying quantity before the draw. Equivalent.

`tests/test_violation_identity.py` requires the visit, the ids, and the exact sentence on the findings those loops emit. `tests/test_boundary_survivors.py` pins the edges those loops compare with `<` and `>`. Neither file is in 1227/1921 or in the score below. A later dispatch can upload the uncapped campaign when `run_nightly` is true. That input defaults to false. `run_mutation` defaults to true, so the nightly upload can be requested without a second mutmut job. Dispatch `37810297431` is that upload.

## Прогон 37797011451

Linux `workflow_dispatch` [37797011451](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37797011451) on `e54e33a` killed 1261 and left 660. Score 1261/1921. Exit codes are only 0 and 1. `test-slow` on that run succeeded. This is not an attestation of main. The mutated tree does not contain `tests/test_violation_identity.py` or `tests/test_boundary_survivors.py`.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 917 | 589 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 180 | 64 | 244 |
| Total | 1261 | 660 | 1921 |

Against run `37759423830`, 34 mutants died and none were born. All 34 are in `ledger.py`. `capacity.py`, `checker.py`, and `lane_setup.py` did not move. The five named `continue` to `break` skips are among the deaths: `_exchange_pool_violations` 10 and 30, `_rotable_spare_violations` 6, 44, and 51. The other 29 are `_completion_times` 3, 11, 18, 19, 20, 21, 22, 26, 28; `_exchange_pool_violations` 11, 12, 13, 27, 42, 43, 49, 50, 52, 53, 54, 55, 56; `_rotable_spare_violations` 17, 24, 30, 98, 99, 107, 108. The README evidence table does not copy 1261/1921. Phase 1 stays open because 660 survivors are not all triaged.

Read from the mutant bodies of that artifact, not from the names:

- `_precedence` 1 changes the default `ignore_absent` from `False` to `True`. The only caller is `_constraint_violations`, and it always passes `ignore_absent=subset_mode`. The default is not read. Equivalent. `_constraint_violations` 24 deletes that argument, so the default is used. That one is not equivalent.
- `_duration_violation` 38 changes `if masks else held` into `if masks or True`. An empty mask list is the whole interval, and a non-empty list already takes that branch. The integer is the same. Equivalent.
- `spare_is_rotable` 12 drops the inner default, so a missing kind is `None`. `str(None).lower()` is not `rotable`, which is the same answer as the word `consumable`. Equivalent. Mutant 16 uses `CONSUMABLE`; `.lower()` still is not `rotable`. Equivalent. Mutant 8 renames `mode` to `MODE` and is not equivalent.
- `check_domain_assignments` 5 and `check_plan` 6 pass `model_dump(mode="PYTHON")`. That dump is the same dict as `mode="python"`, so the revalidated problem is unchanged. Equivalent.

`tests/test_more_survivors.py` requires the unknown-policy sentence, a missing return lag of zero, a spare that is rotable by `mode` alone, two returns at one moment against a demand of two, one return against that demand, a job with no operations, a later return after an incomplete job, preemptive work that ignores a closed unattended calendar and an unused auxiliary, a preemptive unknown post and crew, sort order by operation id and by resource id, and a subset that ignores a missing predecessor. Those tests are not in 1261/1921.

## Прогон 37829096222

Linux `workflow_dispatch` [37829096222](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37829096222) on `e027edd` killed 1562 and left 359. Score 1562/1921. Exit codes are only 0 and 1. `test-slow` on that run succeeded. The mutation job succeeded; it was not skipped. The tree contains `tests/test_violation_identity.py` and `tests/test_boundary_survivors.py`. It does not contain `tests/test_more_survivors.py`. This is not an attestation of main.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1199 | 307 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 199 | 45 | 244 |
| Total | 1562 | 359 | 1921 |

Against run `37797011451`, 301 mutants died and none were born. `capacity.py` and `lane_setup.py` did not move. Checker went from 917 killed to 1199. Ledger went from 180 killed to 199. The eight ledger suggestion deletions died (`_exchange_pool_violations` 44 and 51, `_rotable_spare_violations` 26, 32, 64, 74, 101, and 110), and `_violation` 42 died. Those were the ids the previous note said were not equivalent. `_completion_times` 12, 14, and 27 died. Mutant 27 changes `if complete and ends` into `if complete or ends`. Boundary tests that keep every job and pass only one or two operations leave the other jobs with no sinks. `complete` stays true, `ends` stays empty, and `max` of that empty list raises. Mutant 24, `complete = False` changed to `True`, is still alive. The sink loop walks a set, so that one is not marked equivalent. The README evidence table does not copy 1562/1921.

## Прогон 38228010896

Four scheduled runs on `b7c8c29` finished with mutation success and `test-slow` success: [37908445280](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37908445280), [38037961461](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38037961461), [38126032914](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38126032914), and [38228010896](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38228010896). Their `exit_code_by_key` maps are identical. The score below is that map. Killed 1587, survived 334, total 1921. Exit codes are only 0 and 1. The tree contains `tests/test_more_survivors.py` as well as the identity and boundary tests. `b7c8c29` attests `6f34389` and does not attest itself. These scheduled runs are not an attestation of main. The README evidence table does not copy 1587/1921.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1216 | 290 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 207 | 37 | 244 |
| Total | 1587 | 334 | 1921 |

Against run `37797011451`, 326 mutants died and none were born. Against run `37829096222`, 25 died and none were born. Those 25 are the edge tests that were not on `e027edd`: `_attended_masks` 3, 13, 23, 33, 35, 36, and 37; `_constraint_violations` 21 and 24; `_duration_violation` 9, 10, 11, 12, and 13; `_precedence` 14; `_sorted` 8; `check_plan` 48; `_exchange_pool_violations` 14 and 16; `_rotable_spare_violations` 10, 12, and 15; `spare_is_rotable` 3, 7, and 8. `check_plan` 48 passes `subset_mode=None`, and `None` does not ignore a missing predecessor. `_precedence` 14 deletes the missing-predecessor sentence, so the domain check no longer has that exact message.

`_attended_masks` 14, 24, and 34 are still alive. Picking a different center or crew, or passing `None` as the auxiliary calendar id, did not change the assertions those tests make. They are not marked equivalent.

Read from the mutant bodies, and still alive on this score:

- `spare_is_rotable` 10 stores `None` for a missing kind, and mutant 15 stores `XXconsumableXX`. Neither string is `rotable` after `.lower()`. Same answer as `consumable`. Equivalent, for the same reason as mutants 12 and 16.
- `_violation` 1 changes the default severity to `XXhardXX`. The stored level is `kpi` only when the argument is `kpi`, so it stays `hard`. Equivalent. Mutant 6 changes the non-`ReasonCode` arm to `str(None)`. Every caller passes a `ReasonCode`, including the capacity helper, so that arm is not evaluated. Equivalent.
- `_duration_violation` 50 changes the final `message = ""` to `None`. `policy_of` returns only `exact`, `min`, `preemptive`, or `invalid`, so that `else` is not reached. `if not message` would also treat `None` like `""`. Equivalent.
- `_exchange_pool_violations` 21 sets the initial `worst_at` to `""`. A reported stockout has already assigned a moment, because `initial_serviceable` is at least 0 and `worst` starts there. The initial value is not read. Equivalent.
- `_completion_times` 7 appends `None` instead of the successor id. The list is only tested for emptiness. Equivalent. Mutant 23 sets `complete` to `None`. `if complete and ends` is false either way. Equivalent.

Sixty-two survivors of 334 have one of these reasons or an earlier one. The other 272 do not. Phase 1 stays open. `_completion_times` 24 is one of the 272.

A recount of the four artifact directories agrees: the `exit_code_by_key` maps are identical, killed 1587, survived 334, total 1921, and the only exit codes are 0 and 1. All 62 named equivalents are still alive. None of the 272 is in that named set. Against `37829096222`, the 25 deaths are exactly the ids listed above. `checker.py`, `ledger.py`, `capacity.py`, and `lane_setup.py` are the same text from `e54e33a` through `b7c8c29`, so those ids name the same edits. This recount is not a new score.

`_job_of` 6 changes `op is None` into `(op is None) and False`, so a missing operation raises instead of returning no job. `_calendars_windows_horizon` calls `_job_of` for an unknown operation that sits outside the horizon. `_op` 3 drops the `None` default on that same path and raises `StopIteration`. Neither is equivalent.

`_spare_receipts` 23 replaces the opening event's operation id `""` with `XXXX`. That id is only a sort key. The opening quantity and every receipt are order 0 and add stock. A use is order 1, so it stays after those additions. Equivalent.

`_attended_masks` 14, 24, and 34 stayed alive because a different post, a different crew, or a dropped auxiliary calendar still left the open-minute count unchanged in the tests that existed. Tests now require the assigned post, the assigned crew, and a partial auxiliary window. A negative `return_lag_min` must be invalid (`_rotable_spare_violations` 16 changes `or` to `and`). A shop resource that declares `always_open` and has no calendar must stay silent (`_named_calendar_fit` 6 drops the `not`). An unknown operation outside the horizon must not raise. These tests are not in 1587/1921.

## Как читались 272

The paragraph above left 272 survivors without an equivalent reason. Reading those mutant bodies, not their names, gives 45 a reason. They are still alive in 1587/1921. The score does not change. `_spare_receipts` 23 was already one of them.

Observed on the installed Pydantic: `model_dump(mode=None)` and `model_dump(mode="XXpythonXX")` compare equal to `model_dump(mode="python")`. `mode="json"` does not. `check_domain_assignments` 3 and 4, and `check_plan` 4 and 5, therefore revalidate the same problem. A `RepairFlowProblem` round-trips through `mode="python"`, so the `except` arm is not evaluated. Mutants that only edit that arm are equivalent: `check_domain_assignments` 6, 7, 8, and 9, and `check_plan` 7, 8, 9, and 10. `check_domain_assignments` 13 passes `subset_mode=None`. Both `if not subset_mode` and `if ignore_absent` treat `None` like `False`. Equivalent. This is not `check_plan` 48, which died.

`check_plan` and `check_domain_assignments` revalidate before `_named_calendar_fit`. The model rejects a non-synthetic resource that has no calendar and does not declare `always_open`, and it rejects a `calendar_id` that is not in the instance. The two error returns are not evaluated. Mutants that only edit those returns are equivalent: `_named_calendar_fit` 8 through 21, and 27, 28, 29, 30, 33, 34, 35, and 36. Mutants 6 and 7 change the condition. Mutant 7 calls `declares_open_horizon(None)`, which raises `AttributeError`. Neither is equivalent.

`Violation.severity` defaults to `hard`, so deleting `severity="hard"` on a ledger `Violation` leaves the same value. `_rotable_spare_violations` 31, 73, and 109 are equivalent. `_capacity_overlaps` 35 and 50 pass no suggestion or `SUGGESTIONS.get(None)`. `_violation` fills `SUGGESTIONS.get(text)`, and the overlap codes are in that table. Equivalent. `_normalize_assignments` 12, 13, 20, and 21 change only the default kind string to `XXwcXX`, `WC`, `XXopXX`, or `OP`. A mapped id does not use the default. An unmapped id fails the `== "wc"` or `== "op"` test and stores `str` of the same uuid. Equivalent.

227 of the 272 still have no equivalent reason. `_completion_times` 24 is one of them. It sets `complete = True` when a sink is missing. It is not equivalent. Sinks are now sorted by operation id, which does not change a complete card or a card with any sink missing: the original still withholds the return. The sort makes the partial return observable, and `test_an_unfinished_later_sink_does_not_return_the_unit` requires the stockout. That test is not in 1587/1921. Dispatch `38555693129` checks out `eef52f8` and does not contain the sort. The other 226 are what `tests/test_kernel_binding.py` and `tests/test_open_edges.py` assert, together with the tests already on main for the assigned post, the assigned crew, the partial auxiliary window, the negative return lag, the always-open shop post, the unknown operation outside the horizon, and a rotable that also has receipts. Those assertions are not in 1587/1921. A later mutmut on a tree that contains them is the measurement. This section is not that measurement. Phase 1 stays open. The README does not copy the score.

## Диспетчерский прогон 38555693129

`workflow_dispatch` [38555693129](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38555693129) on `eef52f8` finished with mutation success and `test-slow` success. It is not an attestation of main. The tree contains `tests/test_kernel_binding.py` and `tests/test_open_edges.py`. It does not contain the later sink sort. Exit codes are only 0 and 1.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1401 | 105 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 233 | 11 | 244 |
| Total | 1798 | 123 | 1921 |

Against `38228010896`, 211 mutants died and none were born. None of the 62 earlier equivalents died. None of the 45 reasons read from the 272 died. Of those 272, 61 are still alive: the 45 reasons, plus 16 without one. `_capacity_overlaps` 9 sets `start = None` and the next line replaces it, because every caller passes `include_setup=True`. Equivalent. The other 15 are not equivalent and this dispatch did not kill them: `_normalize_assignments` 42, 49, and 50; `_precedence` 69 through 73 and 78 through 82 (the max-lag finding); `_spare_receipts` 11; `_completion_times` 24. The max-lag test added after this dispatch is not in 1798/1921. The sink sort is not in it either. Phase 1 stays open. The README does not copy 1798/1921.

## Диспетчерский прогон 38565194050

`workflow_dispatch` [38565194050](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38565194050) on `04ad612` finished with mutation success and `test-slow` success. It is not an attestation of main. The tree contains the sink sort and the max-lag test. Exit codes are only 0 and 1. Sorting the sinks added one mutant, so the ledger ids are not the same numbers as in 1798/1921.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1411 | 95 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 235 | 10 | 245 |
| Total | 1810 | 112 | 1922 |

In `checker.py` the mutant ids did not move. Ten died, all on the max-lag finding: `_precedence` 69, 70, 71, 72, 73, 78, 79, 80, 81, and 82. None were born. `_normalize_assignments` 42, 49, and 50 are still alive, and so is `_spare_receipts` 11. They are not equivalent. `_capacity_overlaps` 9 is still alive and remains equivalent.

In `ledger.py` the edit `complete = False` to `complete = True` is now mutant 25, and it died. Mutant 24 is now `complete = None` inside the missing-sink arm. `if complete and ends` is false for `None` and for `False`, so that one stays equivalent. Mutant 30, `max(ends)` to `max(None)`, is the new node and it died. Four survivors still have no equivalent reason: the three normalize ids and `_spare_receipts` 11. Phase 1 stays open. The README does not copy 1810/1922. Tests added after this dispatch call `check_plan` with a kernel row, so a dropped crew or auxiliary is visible, and a rotable draw before its receipt must not be reported as a consumable stockout. Those tests are not in 1810/1922.

## Диспетчерский прогон 38618458299

`workflow_dispatch` [38618458299](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38618458299) on `a4e4e90` finished with mutation success and `test-slow` success. It is not an attestation of main. The four notary modules are the same text as on `04ad612`, so the mutant ids did not move. Exit codes are only 0 and 1.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1415 | 91 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 235 | 10 | 245 |
| Total | 1814 | 108 | 1922 |

Against `38565194050`, four mutants died and none were born. They are `_normalize_assignments` 42, 49, and 50, and `_spare_receipts` 11. No recorded equivalent died. The other 108 survivors are the ones that already have a written equivalent reason. This artifact leaves no survivor without that reason. The README does not copy 1814/1922.

Accepted before the run, not as a pass:

- No `# pragma: no mutate` in those four modules.
- No mypy pre-filter. A type error can hide a mutant the tests would also miss.
- The slow campaign test stays out of the mutant runner. It repeats the same notary for minutes and would not add a distinct kill.
- The uncapped campaign is recorded in `docs/fault-campaign-nightly.json` (checked 109665, false_accept 0, false_reject 0). It is a local Windows run. Dispatch `37810297431` on `e364f34` uploaded `fault-campaign-nightly` with the same counts and the same `input_hash`. mutmut was skipped. That artifact is not an attestation of main. Phase 1 stays open. The later score is run `38228010896`: 334 survivors. Of the 272 that had no equivalent reason, 45 now have one, read from the mutant body. 227 do not. `_completion_times` 24 is one of those 227 and is not equivalent. Phase 1 stays open. See the section Reading the 272.

## Ночь 38698472141

Ночной прогон [38698472141](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/38698472141) на `7f6e9ae` закончился успехом mutation и `test-slow`. Это не аттестация `main`. Четыре модуля нотариуса на `7f6e9ae` совпадают с текущим `main`: аудит `0aa2ecf` уже внутри, поздние коммиты их не трогали. Идентификаторы мутантов поэтому называют текущий текст, а не прогон `38618458299`. Там было 1922 мутанта; здесь 2137, потому что `lane_setup.py` и `checker.py` выросли. Коды выхода только 0 и 1. README этот счёт не копирует.

| Модуль | Убито | Живо | Всего |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 1455 | 122 | 1577 |
| `lane_setup.py` | 210 | 39 | 249 |
| `ledger.py` | 235 | 10 | 245 |
| Всего | 1962 | 175 | 2137 |

Тела 175 выживших прочитаны по спанам артефакта, не по старому номеру. У 126 есть причина эквивалентности. У 49 нет. `tests/test_nightly_survivors.py` фиксирует исходное поведение этих 49 и в счёт 1962/2137 не входит. Фазу не закрывать: убийство этих 49 ещё не измерено.

Эквивалентны, потому что подстановка не меняет значение, которое потом читают:

- `capacity.py`: пик `>` и `>=` пишут одно и то же; `pop` без запасного значения попадает в уже открытый индекс; вид старта 2 для развёртки тот же, что 1; `sort` без ключа на тройке совпадает с явным ключом.
- `check_plan` 4–6 и `check_domain_assignments` 3–5: `model_dump(mode=None)`, `mode="XXpythonXX"` и `mode="PYTHON"` на этой сборке Pydantic дают тот же словарь, что `mode="python"`, и задача заново проходит валидацию.
- Ветвь `except` у `check_plan` 7–10 и `check_domain_assignments` 6–9 не выполняется: уже собранная `RepairFlowProblem` переживает этот круг.
- `check_domain_assignments` 13 передаёт `subset_mode=None`. И `if not subset_mode`, и `if ignore_absent` читают `None` как ложь.
- `_normalize_assignments` 12, 13, 20 и 21 меняют только запасную строку вида. И для `"wc"` / `"op"`, и для другой строки в назначение попадает `str` того же uuid.
- `_precedence` 1 меняет значение по умолчанию `ignore_absent`. Единственный вызов передаёт аргумент явно.
- `_capacity_overlaps` 9 ставит `start = None`, следующая строка его заменяет: все три вызова передают `include_setup=True`.
- `_duration_violation` 46 всегда зовёт `open_minutes`. Пустой список масок — это вся длина интервала, а до этой ветви доходят только целые минуты. 58 пишет `message = None` в недостижимом `else`: `policy_of` возвращает только `exact`, `min`, `preemptive` или `invalid`. `if not message` и для `None`, и для `""` пустой.
- `_named_calendar_fit` 8–21, 27–30 и 33–36 правят два отказа. У проверенной задачи их нет: неизвестный `calendar_id` модель отвергает раньше, а отсутствие календаря у несинтетики тоже. Синтетика без календаря из этой функции выходит пустым списком.
- `_spare_receipts` 22, 23, 25 и 28 меняют порядок или идентификатор события. Приход остаётся раньше расхода: у расхода непустой идентификатор операции, и он сортируется после пустого или после `"XXXX"`.
- `_due_release_spares` 44–46, 48, 49, 52, 53, 55–57 и 107 правят отказ «неизвестный ЗИП» и `continue` сразу за ним. Модель не пускает операцию с неизвестным артикулом, ветвь не выполняется.
- Стирание `suggested_relaxation` или подстановка `None` у `_violation` ничего не меняет: `None` заменяется на `SUGGESTIONS.get(text)`, а вызывающий код и так передавал эту строку. Это `_coverage` 9 и 14, `_skills_and_eligibility` 62, 69, 86, 94, 111 и 120, `_precedence` 20, 29, 46, 55, 74 и 83, `_capacity_overlaps` 35, 43 и 50, `_spare_receipts` 55 и 61, `_due_release_spares` 89, 97, 146, 154, 170 и 177, `_setup` 73 и 82, `_frozen` 15, 22, 48 и 56.
- `_violation` 1 и 2 меняют запасную серьёзность. `kpi` ставится только при явном `"kpi"`. 4–6 не выходят из `ReasonCode`: это `StrEnum`, `str` совпадает со значением, а ветвь `else` вызывающие не берут. 38–41 правят `REASON_RU.get` только когда сообщение пустое. Пустое сообщение в `_violation` не передаётся.
- `spare_is_rotable` 10, 12, 15 и 16: запасное значение, которое не равно `rotable` после `.lower()`, остаётся расходным. `_exchange_pool_violations` 21: начальное `worst_at` читается только после присваивания момента. `_rotable_spare_violations` 31, 73 и 109 убирают `severity="hard"`; у `Violation` это и есть значение по умолчанию. `_completion_times` 7 кладёт `None` вместо идентификатора преемника: список проверяется только на пустоту. 24 ставит `complete = None`; `if complete and ends` ложно и для `None`, и для `False`.
- `stamp_canonical_lanes` 12–17, 21, 24, 25 и 35 готовят список для `_colour_lanes(..., ignore_explicit=True)`. При таком флаге поле `lane` у заготовки не читается, а `model_copy(update=None)` и неизвестный ключ полосу не стирают. 35 копирует полосу `None` поверх уже пустой полосы.

Не эквивалентны. Исходное поведение зафиксировано в `tests/test_nightly_survivors.py`, не в этом прогоне:

- `_duration_violation` 14 и 15 переписывают фразу про нецелую минуту.
- `_calendar_fit` 45 и 52 стирают подсказку `WINDOW_BROKEN` у кода `CALENDAR_BROKEN`. В `SUGGESTIONS` ключа `CALENDAR_BROKEN` нет, поэтому `None` не восстанавливает ту же строку.
- `stamp_canonical_lanes` 6 и 28 заменяют `and` на `or` и перекрашивают уже названную полосу или одиночный пост. 40 кладёт `None` вместо строки плана.
- `_colour_lanes` 32, 36, 40–43, 54, 60, 65, 66, 68, 69, 80, 82, 88, 90, 103, 106–108, 127–129 и 154 меняют явную полосу, признак неоднозначности, поля свидетеля, `continue` на `break` или состояние `idle`. 151 и 152 эквивалентны: кортеж новой полосы тут же перезаписывается и не читается.
- `_setup` 31 подставляет одну минуту вместо нуля при политике `zero`. 43–48, 53–63, 92 и 100 портят фразу, поля или обрыв цикла у неоднозначной полосы и у пропущенной ячейки. 73 и 82 уже названы выше и эквивалентны.
