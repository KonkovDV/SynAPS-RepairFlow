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

1. A signature on the operator log. The chain writer is in `repairflow decide`.
2. MUS/MCS explanations, `POST_DOWN`, `PART_DELAY`, and a route-variant catalogue.
3. A hash lock of every transitive wheel, and a signed release artifact.
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

## Decision log chain (2026-10-08)

Closed, each with a regression in `tests/test_decision_log.py`:

- a changed field fails `event_hash`;
- swapping two lines fails the `prev_hash` link;
- a missing tail fails when the caller still has the tip hash;
- a legacy file is not treated as a broken chain, and it cannot be extended;
- a second writer blocks on `O_EXCL` instead of interleaving a line;
- `accepted` and `accepted_with_edits` are refused when `exit_code` is not 0.

Accepted limits:

- without the stored tip, a valid prefix verifies;
- rewriting the suffix and replacing the stored tip is not detected;
- `tools/append_decision.py` seals the chain and does not open the result file;
- `log stats` repeats rejection reasons and does not try to find a name inside them;
- a lock left by a crashed writer is not stolen; the next writer times out;
- directory `fsync` is skipped when the operating system refuses it.
