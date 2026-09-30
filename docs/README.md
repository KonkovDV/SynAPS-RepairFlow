# RepairFlow documentation map

Read the contract, then the evidence, then the pilot boundary.

## Start here

1. [`../README.md`](../README.md): public scope, CLI, claims, and non-claims.
2. [`SOTA_EVIDENCE_PROTOCOL.md`](SOTA_EVIDENCE_PROTOCOL.md): what counts as evidence.
3. [`limitations.md`](limitations.md): explicit technical and business limits.
4. [`red-team-remediation.md`](red-team-remediation.md): what the checker closes, and what is still external.
5. [`traceability-matrix.md`](traceability-matrix.md): requirement, status, and evidence.

## Engineering review

- [`domain-assumptions.md`](domain-assumptions.md): model assumptions.
- [`core-compat.md`](core-compat.md): pinned SynAPS commit and the API this package calls.
- [`SYNAPS_REPAIRFLOW_MVP_SKELETON.md`](SYNAPS_REPAIRFLOW_MVP_SKELETON.md): architecture and MVP plan.
- [`adr/0002-dag-over-chain-kernel.md`](adr/0002-dag-over-chain-kernel.md): convergent cards compiled onto a chain kernel.
- [`adr/0004-exchange-pool-ledger.md`](adr/0004-exchange-pool-ledger.md): exchange stock is a ledger.
- [`adr/0005-inspection-rewrites-the-card.md`](adr/0005-inspection-rewrites-the-card.md): inspection freezes issued slots.
- [`SOTA_2026.md`](SOTA_2026.md): positioning and the benchmark agenda.
- [`benchmark-protocol.md`](benchmark-protocol.md): reproducibility rules for synthetic comparisons.
- [`sbom-and-provenance.md`](sbom-and-provenance.md): what the SBOM covers, and what it does not.
- [`threat-model.md`](threat-model.md): offline deployment boundary.
- [`data-mapping-1c-toir.md`](data-mapping-1c-toir.md): mapping template, not an integration.

## Pilot and jury review

- [`../APPLICATION.md`](../APPLICATION.md): application-safe summary.
- [`jury-demo.md`](jury-demo.md): demo script.
- [`pilot-protocol.md`](pilot-protocol.md): 90-day shadow protocol.
- [`pilot-kpi-template.md`](pilot-kpi-template.md): KPI definitions without invented results.
- [`operator-decision-log.md`](operator-decision-log.md): human acceptance record. The writer is not implemented.
- [`osint-and-pilot-gates.md`](osint-and-pilot-gates.md): public sources and entry requirements.
- [`release-checklist.md`](release-checklist.md): laboratory release versus a pilot submission.
- [`adr/0003-release-boundary.md`](adr/0003-release-boundary.md): shadow output is not an instruction to a control system.

## Governance

- [`AI_USE.md`](AI_USE.md): assisted-development disclosure.
- [`../SECURITY.md`](../SECURITY.md): vulnerability reporting.
- [`BANNED_CLAIMS.txt`](BANNED_CLAIMS.txt): phrases that must not appear in a public claim.
- [`../LICENSES.md`](../LICENSES.md): direct dependency licenses.

## Reviewer rule

A claim is publishable only when the exact source, commit, input, solver configuration, checker output, and denominator are available. Otherwise label it as an assumption, a hypothesis, or a roadmap item.
