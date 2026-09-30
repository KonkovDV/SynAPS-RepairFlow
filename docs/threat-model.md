# Threat model and offline deployment boundary

## Scope

RepairFlow is a read-only, offline/shadow planning aid. It must not write to EAM/ERP, issue transport commands, or make release-to-line decisions.

## Assets

Input work orders, technology cards, resource calendars, skills, spare availability, frozen assignments, generated plans, hashes, and operator decisions.

## Threats and controls

| Threat | Control | Verification |
|---|---|---|
| Sensitive crew identity in input | Use stable pseudonymous crew IDs; keep personnel mapping outside the bundle | Ingest rejects undocumented provenance |
| Malicious or stale plan | Independent checker, fail-closed status, result and input hashes | `repairflow check`, evidence bundle |
| Dependency substitution | Commit-pinned SynAPS, locked solver dependencies, SBOM | CI pin gate and release manifest |
| Network exfiltration | No runtime network requirement; install from an approved local mirror | Offline smoke test |
| Unauthorized plan acceptance | Human operator decision log; no automatic write-back | Pilot protocol |
| Compromised input file | Strict Pydantic schema, size limits, unknown-field rejection | Contract tests |
| Audit repudiation | Immutable evidence bundle with runtime metadata and hashes | Hash verification and signed release artifact |

## Pilot boundary

Start with synthetic or anonymized data, one repair contour, shadow output only, and a documented rollback to the existing process. A pilot does not authorize production control or safety-critical release decisions.
