# RepairFlow documentation map

Use this page as the review route. Read the contract first, then the evidence, then the pilot boundary.

## Start here

1. [`../README.md`](../README.md): public scope, CLI, claims, and non-claims.
2. [`SOTA_EVIDENCE_PROTOCOL.md`](SOTA_EVIDENCE_PROTOCOL.md): what counts as evidence.
3. [`limitations.md`](limitations.md): explicit technical and business limits.
4. [`red-team-remediation.md`](red-team-remediation.md): confirmed findings and remaining blockers.

## Engineering review

- [`domain-assumptions.md`](domain-assumptions.md): model assumptions.
- [`SYNAPS_REPAIRFLOW_MVP_SKELETON.md`](SYNAPS_REPAIRFLOW_MVP_SKELETON.md): architecture and MVP plan.
- [`SOTA_2026.md`](SOTA_2026.md): current positioning and benchmark agenda.
- [`benchmark-protocol.md`](benchmark-protocol.md): reproducibility rules for synthetic comparisons.
- [`sbom-and-provenance.md`](sbom-and-provenance.md): supply-chain and evidence requirements.
- [`threat-model.md`](threat-model.md): offline deployment boundary and threats.
- [`data-mapping-1c-toir.md`](data-mapping-1c-toir.md): mapping template, not an integration claim.

## Pilot and jury review

- [`APPLICATION.md`](../APPLICATION.md): application-safe summary.
- [`jury-demo.md`](jury-demo.md): demo script.
- [`pilot-protocol.md`](pilot-protocol.md): 90-day shadow protocol.
- [`pilot-kpi-template.md`](pilot-kpi-template.md): KPI definitions without invented results.
- [`operator-decision-log.md`](operator-decision-log.md): human acceptance and rollback record.
- [`osint-and-pilot-gates.md`](osint-and-pilot-gates.md): public-source OSINT and entry requirements.
- [`release-checklist.md`](release-checklist.md): lab release versus pilot submission gates.

## Governance

- [`AI_USE.md`](AI_USE.md): assisted-development disclosure.
- [`../SECURITY.md`](../SECURITY.md): vulnerability reporting.
- [`adr/`](adr/): architecture decisions and release boundaries.

## Reviewer rule

A claim is publishable only when the exact source, commit, input, solver configuration, checker output, and denominator are available. Otherwise label it as an assumption, hypothesis, or roadmap item.
