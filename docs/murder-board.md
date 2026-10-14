# Murder board

## Product

- Deployed? No. The repository is a TRL 4 laboratory artifact.
- A replacement for 1C, EAM, or CMMS? No. It is a read-only planning layer.
- Is SVARZ a confirmed customer? No evidence in this repository. Public pages describe the plant's repair profile.
- A measured saving? No. Synthetic benchmarks are engineering evidence.
- Does the system control vehicle release? No. Shadow output only.

## Technical

- `claim_status=verified` means full operation coverage and an empty hard notary, including heuristic plans that pass `recheck`.
- `claim_status=domain_verified` is the shop-CSV notary. The kernel is not called. `verified_feasible` stays false.
- `optimal` means CP-SAT `OPTIMAL`, an empty hard notary, and one compiled pass. A later fixpoint iteration stays at `verified`.
- An incomplete plan is `PARTIAL`, exit 2. `allow_partial_plan` does not grant exit 0.
- A calendar with zero windows is unavailable (`CALENDAR_BROKEN`). A missing `calendar_id` means the resource is open across the horizon. A `calendar_id` that is not in `calendars` is an invalid instance.
- Convergent repair cards are compiled by `dag_compiler`. The kernel still sees chains. The domain checker judges the original edges. Cycles are rejected.
- The checker imports `checker_primitives`, not `repairflow.adapter`.
- MUS/MCS explanations, `POST_DOWN`, `PART_DELAY`, and a route-variant catalogue are not implemented.
- The operator decision log is a JSONL contract. There is no writer.

## Notary score

- Is 1587/1921 a closed phase? No. 334 mutants survived the four identical scheduled runs on `b7c8c29`. 272 of them have no equivalent reason.
- Does that score attest main? No. The manifest attests `d3cb6d1` from push `38300105511`, including `test-slow`. The mutation runs are scheduled jobs on the earlier commit `b7c8c29`. `b7c8c29` attests `6f34389` and does not attest itself.
- Did the edge tests fail to kill what they named? The 25 deaths against dispatch `37829096222` are those tests, and a recount of the artifacts matches that list exactly. `_attended_masks` 14, 24, and 34 survived them because the open-minute count did not change. `_completion_times` 24 survived every run on this source.
- Did any recorded equivalent die in these runs? No. The 62 named equivalents are still alive. The eight ledger suggestion deletions and `_violation` 42 did die earlier, and the note at that time said they were not equivalent.
- Is `_job_of` 6 equivalent? No. An unknown operation outside the horizon calls it. `_op` 3 is the same path. `_spare_receipts` 23 is equivalent: the changed operation id sorts only among order-0 additions.
- Is the score stable? The four scheduled artifacts from 9 October through 12 October have the same `exit_code_by_key`. The four notary modules did not change between `e54e33a` and `b7c8c29`. That is not a proof about a future source change.

## Pilot

- Smallest safe pilot: one contour, an anonymized extract, offline replay, shadow output, a human decision, and rollback.
- Credible result: a fixed data contract, a baseline, a denominator, the exact environment, the independent checker, and archived decisions.
- Still outside the repository: rights chain, named process and data owners, information-security review, and a data agreement.
