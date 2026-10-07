# Threat model and offline deployment boundary

## Scope

RepairFlow is a read-only, offline planning aid. A solve does not write to EAM or ERP, does not issue transport commands, and does not decide release to line.

## Assets

Work orders, technology cards, resource calendars, skills, spare availability, frozen assignments, generated plans, hashes, and operator decisions.

## Threats and controls that exist in this repository

| Threat | Control that exists now | Where to look |
|---|---|---|
| A stale or edited plan presented as checked | Independent checker, full-coverage gate, input/config/result hashes | `repairflow check --verify-hashes` |
| Dependency substitution of the kernel | SynAPS commit pin checked by CI | `tools/verify_lock.py`, `tests/test_pin_regression.py` |
| Solver wheel drift | OR-Tools pinned to 9.15.6755; direct CycloneDX SBOM | `pyproject.toml`, `repairflow.sbom` |
| Extra fields in an instance | Pydantic `extra=forbid` and the generated schema | `tools/export_schemas.py`, `schemas/negative/` |
| Personal names inside a planning bundle | Field contract asks for pseudonymous crew ids | `docs/data-mapping-1c-toir.md` |

## Controls that are not implemented

- A signature on the release artifact.
- A hash lock of every transitive wheel.
- A signature on the operator log. The chain and the optional head hash are in `docs/operator-decision-log.md`. A rewritten suffix with a new head is not detected.
- Automatic rejection of a file because its provenance label is missing. `data_provenance` is a field; a pilot still needs a signed data agreement.
- A network-free installation story. Solving a local JSON file does not call out. `pip install` does.

## Pilot boundary

Start with synthetic or anonymized data, one repair contour, shadow output, and a documented rollback to the existing process. A pilot does not authorize production control.
