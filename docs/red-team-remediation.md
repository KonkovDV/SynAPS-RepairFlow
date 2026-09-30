# Red-team remediation gate

Date: 2026-09-30. Scope: SynAPS RepairFlow `main` at `84fddb2762b0ba696c89e7c81805ff1a3d1c2670`.

## Fixed in this PR

- **P0-1, auxiliary calendars:** an auxiliary resource calendar is now checked over setup plus processing occupancy. A referenced calendar with zero windows means unavailable, not unrestricted. The check is fail-closed for FIFO, GREED, CP-SAT, and independent recheck paths.
- **P0-2, partial coverage:** `allow_partial_plan` no longer creates a green result. Missing assignments produce `PARTIAL`, `verified_feasible=false`, and exit code 2.
- **P0-3, shared primitives at runtime:** the checker receives checker-owned implementations for ID reversal, setup lookup, and crew binding through the package safety gate. This removes the runtime trust path from the adapter; a follow-up should replace the legacy imports in `checker.py` textually and add an AST import gate.

## Still blocking a submission

This branch is intentionally not a claim of production readiness. The following remain required before a pilot application:

1. Replace the tactical runtime compatibility gate with a direct source-level split between checker primitives and adapter primitives.
2. Add DAG compilation or keep the documented linear-card rejection. Do not advertise convergent repair workflows until the compiler exists.
3. Separate soft due dates from hard deadlines, model rotable spares, and make independent metrics canonical.
4. Pin OR-Tools and produce a hash-locked dependency file plus SBOM.
5. Add provenance manifest, runtime manifest, signed evidence option, and a real slow CI suite.
6. Add threat model, offline installation procedure, anonymized crew identifiers, and operator decision log.
7. Obtain a named business owner, a legal entity/IP basis, and a 90-day shadow-pilot data agreement.

## Evidence policy

Synthetic benchmark numbers are valid only for their exact preset, seed, solver, and commit. They are not evidence of effect at SВАРЗ or across Moscow Transport. Public sources confirm that SВАРЗ repairs transport components and that FTIM accepts pilot proposals, but they do not prove the local planning pain, data availability, or customer sponsorship.
