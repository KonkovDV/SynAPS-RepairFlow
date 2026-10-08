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
3. A hash lock of every transitive wheel, and a signed release artifact.
4. A kernel encoding of a closed calendar, a mixed skill-pool shift, or preemptive open-minute counting. Non-empty shifts are compiled. The domain checker still enforces the rest.
5. A named business owner, a legal entity and IP basis, and a signed data agreement for any real pilot.

`claim_status=verified` means full coverage and an empty hard notary. It does not mean optimality, a safety certificate, legal compliance, deployment, or a customer effect.

## Minute oracle (2026-10-08)

`tests/oracle_minutes.py` does not import the checker. Hand tests, not a diff against checker output, are the evidence so far.

Closed on those hand cases: one-minute overlap versus a shared endpoint, setup time inside occupancy, skill expiry at the visit end, hard deadline versus soft due date, a closed calendar, precedence lags, frozen position, setup cell, consumable receipts, rotable return lag, a preemptive gap, two lanes versus a third, and refusal of an eight-day-plus horizon or a sub-minute timestamp.

Accepted limit: the exchange-pool ledger is not judged.

## Fault campaign v2 (2026-10-08)

The oracle labels each mutation. `false_accept` means the checker verified a plan the oracle rejected. `false_reject` means the checker rejected a plan the oracle accepted. An unchanged plan is not counted. The oracle module was not edited to match the checker.

Committed matrix in `docs/fault-campaign.json`: `tiny` and `repair-site-mvp`, seeds 1–30, GREED, EDD and ATC, 56 mutations per verified baseline. checked 10080, false_accept 0, false_reject 0, must_reject 9321, may_pass 759. The reason string in that file is the false_reject explanation: the checker rejected no oracle-accepted plan in this matrix.

The 759 `may_pass` rows in the 56-prefix are real agreements, not invalid plans. They are later shifts (`shift+1`, `shift+5`, `shift+30`, `shift+240`) and some post changes. On that prefix every negative shift was a hard violation for both sides.

The uncapped local run is `docs/fault-campaign-nightly.json`: checked 109665, false_accept 0, false_reject 0, must_reject 102105, may_pass 7560. Same `input_hash` and kernel pin as the prefix. It ran on this Windows host for about 89 minutes. The CI job uploads that file only on the nightly schedule, so this copy is not a GitHub artifact and not an attestation of main. Negative shifts are no longer all `must_reject`: `shift-1`, `shift-5` and `shift-30` each have 315 `may_pass`, and `shift-240` has 444. Those rows are agreements. `false_accept` on each of them is 0.

Sampling: mutator families are round-robin, so the 56-prefix contains every family that applies on that baseline. A one-variant family appears once (`spare_overuse` 180, `rotable_clash` 180, `shift_frozen` 90 because only the repair-site preset freezes a row). `drop_aux` is 336 because `tiny` has no aux. Before this order, a prefix of 56 would have been the first operations' shifts and would have dropped spare, rotable and frozen.

A full pass of `tiny` seed 1 (GREED, EDD, ATC) and of `repair-site-mvp` seed 1 (GREED) also disagreed nowhere. That probe is not part of the committed denominator.

`exit_horizon` sets the visit end to one minute past the planning horizon. The problem horizon stays two or seven days, so the oracle's eight-day refusal does not apply. A mutation that raised `OracleLimit` would have aborted the run. None did.

Accepted limits, not a pass:

- The exchange-pool ledger is still not judged.
- 10080 is a prefix. The uncapped matrix on the same mutators checked 109665, with false_accept 0. A cap of 100000 was rejected because it would drop later operations. The slow pytest still re-runs only the prefix.
- `false_reject` 0 is this matrix only. The `may_pass` rows are slack moves, so a checker rule those moves never touch is unmeasured.
- Run `37696570417` died while collecting tests. Run `37697094085` on `4167df4` finished: 1120 killed, 801 survived, no other exit, score 1120/1921. Five capacity survivors were read: four are equivalent, and the wrapped error sentence is now an exact assertion. Two lane survivors are a dead store. Five lane survivors are covered by new tests and stay survived in that run. `continue` versus `break` on the overflow tail is open. A skipped notary row must not hide the next finding (`tests/test_skip_does_not_hide_next.py`); that test is not in the 1120/1921 run. The other checker and ledger survivors are not marked equivalent. This dispatch is not an attestation of main. See `docs/mutation-survivors.md`.

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
