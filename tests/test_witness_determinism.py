"""Determinism and deletion-minimality tests for bounded domain witnesses."""

from __future__ import annotations

from repairflow.adapter import to_schedule_problem
from repairflow.checker import check_plan
from repairflow.explanations import deletion_minimal_operation_ids
from repairflow.model import PlannedAssignment, RepairFlowProblem, Violation
from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize
from repairflow.witnesses import domain_hard_witnesses, kernel_hard_witnesses, same_hard_decision


def _rotable_fixture() -> tuple[RepairFlowProblem, list[PlannedAssignment], list[str]]:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    kernel_compatible = problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})
    users = [op.id for op in kernel_compatible.operations if "SP-BEARING" in op.required_spare_ids][:2]
    assert len(users) == 2
    spares = [
        row.model_copy(
            update={
                "quantity": 1,
                "domain_attributes": {"kind": "rotable", "return_lag_min": 10_000},
            },
        )
        if row.id == "SP-BEARING"
        else row
        for row in kernel_compatible.spares
    ]
    operations = [
        op.model_copy(update={"required_spare_ids": ["SP-BEARING"]}) if op.id in users else op
        for op in kernel_compatible.operations
    ]
    loaded = kernel_compatible.model_copy(update={"spares": spares, "operations": operations})
    assignments = list(plan(loaded, solver_config="CPSAT-10").result.assignments)
    return loaded, assignments, sorted(users)


def test_deletion_minimal_witness_is_stable_under_assignment_order() -> None:
    problem, assignments, expected = _rotable_fixture()
    variants = [assignments, list(reversed(assignments))]
    expected_ids = set(expected)
    user_rows = [row for row in assignments if row.operation_id in expected_ids]
    variants.append(user_rows + [row for row in assignments if row.operation_id not in expected_ids])

    witnesses = [
        tuple(
            deletion_minimal_operation_ids(
                problem,
                rows,
                ReasonCode.SPARE_UNAVAILABLE,
            )
        )
        for rows in variants
    ]

    assert set(witnesses) == {tuple(expected)}


def test_deletion_minimal_witness_is_minimal_by_single_operation_removal() -> None:
    problem, assignments, expected = _rotable_fixture()
    witness = deletion_minimal_operation_ids(problem, assignments, ReasonCode.SPARE_UNAVAILABLE)
    schedule_problem, id_map = to_schedule_problem(problem)

    assert witness == expected
    for operation_id in witness:
        reduced = [row for row in assignments if row.operation_id != operation_id]
        violations = check_plan(
            problem,
            schedule_problem=schedule_problem,
            assignments=reduced,
            id_map=id_map,
            kernel_status="feasible",
        )
        assert not any(
            row.code == ReasonCode.SPARE_UNAVAILABLE and row.severity == "hard"
            for row in violations
        )


def test_witness_sorting_and_kernel_message_independence_are_deterministic() -> None:
    violations = [
        Violation(code="Z_CODE", message="z", operation_id="OP-2", resource_id="POST-2"),
        Violation(code="A_CODE", message="a", operation_id="OP-1", resource_id="POST-1"),
    ]
    domain = domain_hard_witnesses(list(reversed(violations)))
    kernel_a = kernel_hard_witnesses([{"kind": "KIND", "message": "first"}])
    kernel_b = kernel_hard_witnesses([{"kind": "KIND", "message": "different wording"}])

    assert [row.code for row in domain] == ["A_CODE", "Z_CODE"]
    assert kernel_a == kernel_b
    assert same_hard_decision(domain, kernel_a) is True
