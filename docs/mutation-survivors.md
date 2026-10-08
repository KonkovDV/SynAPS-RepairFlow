# Mutation survivors

`mutmut` 3.8.0 needs `os.fork`, so it does not run on the Windows host. The Ubuntu WSL install on this machine has Python 3.14 only, and the project is tested on 3.12. The job is in `.github/workflows/ci.yml`, on `ubuntu-latest` and Python 3.12, for `schedule` or `workflow_dispatch`. It mutates `checker.py`, `capacity.py`, `ledger.py`, and `lane_setup.py`, then runs `pytest -m "not slow"`. The score below is from that Linux job. It is not copied into the README.

Run `37696570417` mutated the four files and then stopped while collecting tests. The sandbox is `mutants/`, and that run copied only those four files. `tests/test_agent_bus.py` imports `tools`, which was not in the sandbox, and mutmut stops at the first collection error. No mutant was executed. No score.

The package now copies as `source_paths = ["src/repairflow"]`. `only_mutate` stays the four notary modules, so planner and CLI are present for imports and are not mutated. `also_copy` adds `tools`, `docs`, `benchmark`, `schemas`, and the files the fast suite opens. It does not add `src/repairflow`: that directory is the mutated tree.

## Run 37697094085

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
- `continue` changed to `break` after an overflow (`mutmut_52`). The public functions use only the first overflow. The shorter private list is not a tested contract. Left open. Not marked equivalent inside `_colour_lanes`.
- An unknown post defaulting to 2 lanes, a tie broken by the lane tuple instead of the index, an unknown operation forced through `setup_state`, an unknown operation labelled `XXXX`, and a placement whose post is `None` are not equivalent. Tests now cover those five. This run still counts them as survived.

The other 788 survivors, in `checker.py` and `ledger.py`, are not marked equivalent. Across all 801, 59 diffs only wrap a string in `XX` and 20 replace `continue` with `break`. Those counts include mutants already named above. Many others set a violation field to `None`. A missing assertion is not an equivalent mutant.

`continue` changed to `break` drops every later row in that loop. Tests in `tests/test_skip_does_not_hide_next.py` require the later finding: an unknown operation does not hide the next unknown post, a mutable freeze does not hide the next frozen rows, and one predecessor does not hide the next. Those tests are not part of run `37697094085`. The unknown operation and the unknown post also keep the visit start, end, and operation id.

## Run 37743200619

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

## Run 37759423830

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

## Run 37797011451

Linux `workflow_dispatch` [37797011451](https://github.com/KonkovDV/SynAPS-RepairFlow/actions/runs/37797011451) on `e54e33a` killed 1261 and left 660. Score 1261/1921. Exit codes are only 0 and 1. `test-slow` on that run succeeded. This is not an attestation of main. The mutated tree does not contain `tests/test_violation_identity.py` or `tests/test_boundary_survivors.py`.

| Module | Killed | Survived | Total |
| --- | ---: | ---: | ---: |
| `capacity.py` | 62 | 4 | 66 |
| `checker.py` | 917 | 589 | 1506 |
| `lane_setup.py` | 102 | 3 | 105 |
| `ledger.py` | 180 | 64 | 244 |
| Total | 1261 | 660 | 1921 |

Against run `37759423830`, 34 mutants died and none were born. All 34 are in `ledger.py`. `capacity.py`, `checker.py`, and `lane_setup.py` did not move. The five named `continue` to `break` skips are among the deaths: `_exchange_pool_violations` 10 and 30, `_rotable_spare_violations` 6, 44, and 51. The other 29 are `_completion_times` 3, 11, 18, 19, 20, 21, 22, 26, 28; `_exchange_pool_violations` 11, 12, 13, 27, 42, 43, 49, 50, 52, 53, 54, 55, 56; `_rotable_spare_violations` 17, 24, 30, 98, 99, 107, 108. The README evidence table does not copy 1261/1921. Phase 1 stays open because 660 survivors are not all triaged.

Accepted before the run, not as a pass:

- No `# pragma: no mutate` in those four modules.
- No mypy pre-filter. A type error can hide a mutant the tests would also miss.
- The slow campaign test stays out of the mutant runner. It repeats the same notary for minutes and would not add a distinct kill.
- The uncapped campaign is recorded in `docs/fault-campaign-nightly.json` (checked 109665, false_accept 0, false_reject 0). It is a local Windows run. Dispatch `37810297431` on `e364f34` uploaded `fault-campaign-nightly` with the same counts and the same `input_hash`. mutmut was skipped. That artifact is not an attestation of main. Phase 1 stays open because the 660 survivors of run `37797011451` are not all triaged.
