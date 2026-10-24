"""Pin the CP-SAT mechanisms the notary assumes, without proving the kernel.

The solver lives in the pinned SynAPS package. This reads that source. It does
not solve, and it does not treat a string match as a line-by-line proof.
The notary remains the verdict.
"""

from __future__ import annotations

import inspect

import synaps.solvers.cpsat_solver as cpsat_solver

from repairflow import adapter

_PRESENT = (
    "add_exactly_one",
    "new_optional_interval_var",
    "add_no_overlap",
    "add_cumulative",
    "add_circuit",
    "predecessor_op_id",
    "Empty calendar is 24/7",
    "frozen_assignments",
    "eligible_wc_ids",
)

_ABSENT = ("spare", "preemptive", "lag")


def test_installed_cpsat_source_has_the_mechanisms_the_notary_names() -> None:
    source = inspect.getsource(cpsat_solver)
    folded = source.casefold()
    missing = [name for name in _PRESENT if name not in source and name not in folded]
    assert missing == []
    present = [name for name in _ABSENT if name in folded]
    assert present == []


def test_the_adapter_sends_a_zero_lag_chain_and_not_a_lag_term() -> None:
    source = inspect.getsource(adapter)
    assert "predecessor_op_id=previous" in source
    assert "lag" not in source.casefold()
