"""Pin the CP-SAT mechanisms the notary assumes, without proving the kernel.

The solver lives in the pinned SynAPS package. This reads that source. It does
not solve, and it does not treat a string match as a line-by-line proof.
The notary remains the verdict.
"""

from __future__ import annotations

import inspect
import re

import synaps.solvers.cpsat_solver as cpsat_solver
import synaps.solvers.mode_choice as mode_choice

from repairflow import adapter
from repairflow.adapter import to_schedule_problem
from repairflow.synthetic import synthesize

_SOLVER = (
    "new_optional_interval_var",
    "add_no_overlap",
    "add_cumulative",
    "add_circuit",
    "predecessor_op_id",
    "Empty calendar is 24/7",
    "frozen_assignments",
    "eligible_wc_ids",
    "build_presence_intervals",
)

_ABSENT = ("spare", "preemptive")


def test_installed_cpsat_source_has_the_mechanisms_the_notary_names() -> None:
    solver = inspect.getsource(cpsat_solver)
    choice = inspect.getsource(mode_choice)
    folded = solver.casefold()
    missing = [name for name in _SOLVER if name not in solver and name not in folded]
    assert missing == []
    assert "add_exactly_one" in choice
    assert "empty ``modes`` list is unchanged" in choice
    both = f"{solver}\n{choice}".casefold()
    present = [name for name in _ABSENT if name in both]
    assert present == []
    assert re.search(r"\blag\b", both) is None


def test_the_adapter_sends_a_zero_lag_chain_and_not_a_lag_term() -> None:
    source = inspect.getsource(adapter)
    assert "predecessor_op_id=previous" in source
    assert "lag" not in source.casefold()


def test_the_compiler_does_not_send_execution_modes() -> None:
    problem = synthesize("tiny", seed=1)
    schedule, _id_map = to_schedule_problem(problem)
    assert all(not operation.modes for operation in schedule.operations)
    assert not schedule.precedence_edges
    assert "precedence_edges" not in inspect.getsource(adapter)
    assert "add_precedence_edge_constraints" in inspect.getsource(cpsat_solver)
