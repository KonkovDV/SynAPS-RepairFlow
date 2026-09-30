# ADR-0002. Repair DAG over a chain-only kernel

## Context

SynAPS `ScheduleProblem` accepts one predecessor per operation and requires that
predecessor to be the previous `seq_in_order` inside the same order. A repair card
is a convergent DAG: disassembly splits into parallel branches and assembly waits
for every branch.

Rejecting that graph makes RepairFlow a renamed chain scheduler. Silently keeping
only `predecessor_ids[0]` drops edges.

## Decision

1. The domain model accepts an acyclic `predecessor_ids` graph. A cycle is a
   validation error. An empty `eligible_work_center_ids` is a validation error.
2. `dag_compiler` offers two strategies:
   - `serialize`: topological order, one chain per job. Feasible for the chain
     implies feasible for the intra-job DAG. Parallel branches are lost.
   - `split_release_fixpoint` (default): maximal unbranched chains become kernel
     orders. Edges that are not inside a chain are release windows. Windows only
     grow. If they do not settle within `max_fixpoint_iter`, the result is
     `DAG_FIXPOINT_NOT_CONVERGED` and exit 2.
3. The domain checker evaluates the original edges, including joins. Segment
   chains are not a substitute for that check.
4. `claim_status=optimal` is allowed only for CP-SAT `OPTIMAL`, an empty hard
   notary, and a single compiled pass. A later fixpoint iteration caps the claim
   at `verified`. When cross edges exist, `optimality_scope` is
   `compiled_windows`: that is optimality of the compiled model, not a claim that
   the original DAG was optimized.

## Alternatives

- Wait for upstream DAG precedence. Recorded as a wish; it does not block the lab.
- Keep rejecting branches. Hides the repair card the domain is about.

## Consequences

Linear fixtures stay one segment per job and keep the previous kernel order id.
Branched cards produce several kernel orders. Heuristic plans that pass the notary
are `claim_status=verified` with solver status `HEURISTIC_FEASIBLE`. They are not
called optimal.
