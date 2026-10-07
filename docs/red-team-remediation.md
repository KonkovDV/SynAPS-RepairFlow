# Red-team remediation

Date: 2026-09-30. This page describes `main`. It does not describe an import-time patch of the checker.

## Closed in the checker and the model

- **Auxiliary calendars.** Setup plus processing must sit inside one window of the aux calendar. A referenced calendar with zero windows is unavailable. The same rule applies to posts and crews. A non-empty shift is compiled into `AuxiliaryResource.calendar`. A zero-window attended calendar is not compiled as the kernel's 24/7 empty list.
- **Coverage.** `allow_partial_plan` does not hide a missing operation. The status is `PARTIAL` and the exit code is 2.
- **Checker primitives.** `reverse_ids` and `lookup_setup_minutes` used by the notary live in `checker_primitives.py`. `bind_concrete_crews` is a planner publication step, not a checker repair. `checker.py` does not import `repairflow.adapter`. A missing matrix cell, including a same-state cell, is `None`. The checker reports `MISSING_SETUP`. The kernel compile inserts 0 only when `policy.missing_setup` is `zero`.
- **Deadlines.** `due_date` is the KPI `DUE_MISSED`. `Job.deadline` is `DEADLINE_MISSED`. `Operation.latest_finish` is `WINDOW_BROKEN`.
- **DAG.** Acyclic cards compile. Cycles and an empty eligible-post list are validation errors.
- **Evidence.** Unified metrics, `check --verify-hashes`, runtime manifest inside `config_hash`, OR-Tools `9.15.6755`, and a direct CycloneDX SBOM.

Regression tests: `tests/test_verdict_safety.py`, `tests/test_dag_compiler.py`, `tests/test_exchange_and_inspection.py`, `tests/test_metrics_and_hashes.py`.

## Still outside this repository

1. A writer for the operator decision log.
2. MUS/MCS explanations, `POST_DOWN`, `PART_DELAY`, and a route-variant catalogue.
3. A signed release artifact. The wheel hashes themselves are now in `requirements-lock.txt`.
4. A kernel encoding of a closed calendar, a mixed skill-pool shift, or preemptive open-minute counting. Non-empty shifts are compiled. The domain checker still enforces the rest.
5. A named business owner, a legal entity and IP basis, and a signed data agreement for any real pilot.

`claim_status=verified` means full coverage and an empty hard notary. It does not mean optimality, a safety certificate, legal compliance, deployment, or a customer effect.

## Banned-phrase gate (2026-10-08)

`tests/test_banned_claims.py` reads `docs/BANNED_CLAIMS.txt` and scans `README.md`, `APPLICATION.md`, and `docs/**/*.md`. Owner decision O1 followed the plan's recommendation: rename the two literature pages. Narrowing the rule to "a result claim" was rejected because a test cannot judge that.

Closed by the matcher, each with a regression in that test:

- case, compatibility forms, and precomposed letters that decompose to the same phrase;
- zero-width and combining marks, stripped after decomposition so they cannot fuse into a different letter first;
- a short homoglyph map for letters that look like Latin;
- HTML escapes, tags, and markdown `*` / backtick splits;
- an allowlist hit is the whole source line, not a prefix, and each hit has its own reason.

Accepted limits, not treated as a pass:

- Russian morphology is not stemmed. A different ending is a different phrase.
- A phrase split by a newline or by `_` is not one line. `_` stays, because identifiers use it.
- `plans/` is not scanned. It is the instruction file and names the phrase list on purpose.
- `CHANGELOG.md` is not scanned. The historical mention was reworded anyway.
- README digits outside the generated evidence block are rejected in visible text. Digits that exist only in a markdown link destination are the pointer to a file, not a copied measurement. `APPLICATION.md` still says "90-day" as a hypothesis length; that page is outside the digit rule.
- One HTML unescape. A double-encoded entity is not decoded twice.

## Supply chain (2026-10-08)

Release notes read before the bump: checkout v7.0.0 blocks a fork checkout on `pull_request_target` and `workflow_run` (this repo uses `pull_request`); v7.0.1 is the patch on that line. setup-python v7.0.0 removes `pip-install`, which this workflow never set. upload-artifact v7.0.2 still zips by default; download-artifact stays on v7.0.0 so it still unpacks those zips. download v8 errors on a digest mismatch and changes unzipping, so it is not paired with upload v7. dependency-review v5.0.0 and CodeQL v4.38.2 are the Node 24 lines. Scorecard v2.4.4 runs on the schedule only, with `publish_results: false`, so a low score is an artifact and not a green gate.

Rejected:

- floating `@v7` tags;
- `ubuntu-latest`, because it becomes Ubuntu 26 on 19.10.2026;
- `pip install -U pip` in CI, because that upgrade has no hash;
- installing the SynAPS git URL inside the offline job, because `--no-index` does not stop a VCS requirement.

Accepted limits:

- the SynAPS wheel built in the online job has no hash;
- a local `pip install -e .` still lets pip fetch `hatchling==1.32.4` during build isolation; CI builds with `--no-build-isolation` after the hashed install;
- `force-include` of `src/repairflow` duplicated `repairflow/__init__.py` in a real wheel. Editable installs did not build that archive, so the duplicate stayed hidden. The wheel target now lists the package once. Dispatch `37700207661` installed the hashed lock: lint, fast tests, slow tests, the pin job, demo, and benchmark succeeded. The wheelhouse job failed on that duplicate, so the offline demo did not run.
- `setup-python` still downloads CPython;
- the checklist cites dispatch `37700478444` on `0f56005`. That run's offline demo installed from the wheelhouse. It is not an attestation of main.
- CodeQL and Scorecard have no run. GitHub dispatches a workflow only after the file exists on the default branch. Dependency review runs on a pull request, and this branch has none.
