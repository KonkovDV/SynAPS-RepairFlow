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
2. MUS/MCS explanations and a route-variant catalogue.
3. A hash lock of every transitive wheel, and a signed release artifact.
4. A kernel encoding of a closed calendar, a mixed skill-pool shift, or preemptive open-minute counting. Non-empty shifts are compiled. The domain checker still enforces the rest.
5. A named business owner, a legal entity and IP basis, and a signed data agreement for any real pilot.

`claim_status=verified` means full coverage and an empty hard notary. It does not mean optimality, a safety certificate, legal compliance, deployment, or a customer effect.

## Typed disruptions (2026-10-08)

| Attack | Result |
| --- | --- |
| Close a shared calendar so every post and crew stops | private calendar `DISRUPT-{id}`; the shared windows stay |
| Unknown post, crew, spare, operation, or predecessor | `ValueError`; nothing is skipped |
| Same duration, or a duplicate urgent job or operation id | `ValueError` |
| Receipt dated before `PART_DELAY.available_at` | that receipt is dropped, so it cannot bypass `available_from` |
| Issued plan kept after the event | recheck; the five types fail with the codes in `tests/test_disruption_events.py` |
| Move a visit that starts inside the next 8 hours when the event missed it | it stays; a direct hit is still released |
| Move an unrelated frozen slot | it stays |
| Count a no-op event as a success | the campaign raises if the expected code is absent |
| 5 types × tiny seeds 1–30 | `false_accept` 0, 150 replanned (`docs/disruption-campaign.json`) |
| First visit of a packed MVP lane | the tail is released and list repair can return `PARTIAL`; the demo uses the latest visit |
| Route-variant catalogue | not modeled |

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
