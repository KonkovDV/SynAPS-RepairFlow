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

`continue` changed to `break` drops every later row in that loop. Tests in `tests/test_skip_does_not_hide_next.py` require the later finding: an unknown operation does not hide the next unknown post, a mutable freeze does not hide the next frozen rows, and one predecessor does not hide the next. Those tests are not part of run `37697094085`. The unknown operation and the unknown post also keep the visit start, end, and operation id; a `None` in those fields on another violation is still open. Spare-receipt skips and an unknown auxiliary are still open.

Accepted before the run, not as a pass:

- No `# pragma: no mutate` in those four modules.
- No mypy pre-filter. A type error can hide a mutant the tests would also miss.
- The slow campaign test stays out of the mutant runner. It repeats the same notary for minutes and would not add a distinct kill.
- The uncapped campaign is recorded in `docs/fault-campaign-nightly.json` (checked 109665, false_accept 0, false_reject 0). It is a local Windows run, not the scheduled CI artifact. Phase 1 stays open because the 801 survivors are not all triaged.
