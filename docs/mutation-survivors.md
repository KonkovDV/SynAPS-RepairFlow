# Mutation survivors

No mutation score is recorded. `mutmut` 3.8.0 needs `os.fork`, so it does not run on the Windows host. The Ubuntu WSL install on this machine has Python 3.14 only, and the project is tested on 3.12. The first run is the `mutation` job in `.github/workflows/ci.yml`, on `ubuntu-latest` and Python 3.12, for `schedule` or `workflow_dispatch`. It mutates `checker.py`, `capacity.py`, `ledger.py`, and `lane_setup.py`, then runs `pytest -m "not slow"`.

Run `37696570417` mutated the four files and then stopped while collecting tests. The sandbox is `mutants/`, and that run copied only those four files. `tests/test_agent_bus.py` imports `tools`, which was not in the sandbox, and mutmut stops at the first collection error. No mutant was executed. No score.

The package now copies as `source_paths = ["src/repairflow"]`. `only_mutate` stays the four notary modules, so planner and CLI are present for imports and are not mutated. `also_copy` adds `tools`, `docs`, `benchmark`, `schemas`, and the files the fast suite opens. It does not add `src/repairflow`: that directory is the mutated tree.

That job has not produced a score. Until a later `mutmut results` artifact exists, this page lists no survivors and the evidence table has no mutation score.

Accepted before the run, not as a pass:

- No `# pragma: no mutate` in those four modules.
- No mypy pre-filter. A type error can hide a mutant the tests would also miss.
- The slow campaign test stays out of the mutant runner. It repeats the same notary for minutes and would not add a distinct kill.
- Survivors, once the artifact exists, are either killed by a new test or copied here with a reason. An equivalent mutant needs the reason. A missing test is not equivalent.
