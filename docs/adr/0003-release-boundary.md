# ADR-0003: release boundary for pilot readiness

## Decision

Release only as offline, shadow decision support for one repair contour. The generated plan is a candidate for a person to review. It is not an instruction to an operational control system.

## Rationale

The current model is a laboratory prototype. Synthetic fixtures and, later, an anonymized extract are the supported inputs. This boundary keeps fail-closed checking in place while a named process owner, a baseline, and a pilot agreement are still absent.

## Consequences

The README and any application distinguish a verified instance from business impact, production deployment, and customer adoption. A claim about savings, TRL above 4, or deployment needs its own cited evidence.
