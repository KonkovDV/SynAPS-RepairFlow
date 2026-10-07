# Mutation survivors

No mutation score is recorded. `mutmut` 3.8.0 needs `os.fork`, so it does not run on the Windows host. The Ubuntu WSL install on this machine has Python 3.14 only, and the project is tested on 3.12. The first run is the `mutation` job in `.github/workflows/ci.yml`, on `ubuntu-latest` and Python 3.12, for `schedule` or `workflow_dispatch`. It mutates `checker.py`, `capacity.py`, `ledger.py`, and `lane_setup.py`, then runs `pytest -m "not slow"`.

That job has not completed. Until its `mutmut results` artifact exists, this page lists no survivors and the evidence table has no mutation score.

Accepted before the run, not as a pass:

- No `# pragma: no mutate` in those four modules.
- No mypy pre-filter. A type error can hide a mutant the tests would also miss.
- The slow campaign test stays out of the mutant runner. It repeats the same notary for minutes and would not add a distinct kill.
- Survivors, once the artifact exists, are either killed by a new test or copied here with a reason. An equivalent mutant needs the reason. A missing test is not equivalent.
