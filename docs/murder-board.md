# Murder board: questions the reviewer should ask

## Product truth

- Is this deployed? **No.** The repository is a TRL 4 laboratory artifact.
- Is this a replacement for 1C/EAM/CMMS? **No.** It is a read-only planning layer.
- Is SVARZ a confirmed customer? **No evidence in this repository.** Public sources establish the repair profile only.
- Is there a measured saving? **No.** Synthetic benchmarks are engineering evidence, not business impact.
- Does the system control vehicle release? **No.** Shadow output only.

## Technical truth

- What does `verified` mean? Full assignment coverage, no declared hard violations, and a present kernel status.
- What does it not mean? Optimality, safety certification, legal compliance, or economic benefit.
- What happens with an incomplete plan? It must be non-green and exit 2.
- What happens with an unavailable resource calendar? It must be a calendar violation, not unrestricted availability.
- Are arbitrary split/join repair DAGs supported? **No.** The current contract rejects unsupported branching.
- Is the checker completely source-independent? **Not yet.** The adapter import must be removed textually before that claim is made.

## Pilot truth

- What is the smallest safe pilot? One contour, anonymized extract, offline replay, shadow output, human acceptance, and rollback.
- What makes the result credible? Fixed data contract, baseline, denominator, exact environment, independent validation, and archived decisions.
- What blocks submission? Rights chain, named process/data owner, information-security review, data agreement, and unresolved technical gates.
