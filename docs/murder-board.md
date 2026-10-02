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

## Pilot

- Smallest safe pilot: one contour, an anonymized extract, offline replay, shadow output, a human decision, and rollback.
- Credible result: a fixed data contract, a baseline, a denominator, the exact environment, the independent checker, and archived decisions.
- Still outside the repository: rights chain, named process and data owners, information-security review, and a data agreement.
