"""Fail-closed compatibility tests for the pinned SynAPS kernel."""

from __future__ import annotations

import pytest
import repairflow.kernel_compat as kernel_compat

from repairflow.model import RepairFlowProblem
from repairflow.synthetic import synthesize


def _kernel_compatible_problem() -> RepairFlowProblem:
    problem = synthesize("tiny", seed=1)
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def test_plain_synthetic_problem_is_kernel_calendar_compatible() -> None:
    problem = _kernel_compatible_problem()
    assert kernel_compat.unsupported_auxiliary_calendars(problem) == []
    kernel_compat.assert_kernel_calendar_compatibility(problem)


def test_auxiliary_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    aux = problem.aux_resources[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"aux_resources": [aux, *problem.aux_resources[1:]]})
    assert kernel_compat.unsupported_auxiliary_calendars(loaded) == [
        f"aux:{aux.id}:CAL-DAY"
    ]
    with pytest.raises(ValueError, match=kernel_compat.KERNEL_CALENDAR_UNSUPPORTED):
        kernel_compat.assert_kernel_calendar_compatibility(loaded)


def test_crew_calendar_is_rejected_with_stable_reason() -> None:
    problem = _kernel_compatible_problem()
    crew = problem.crews[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"crews": [crew, *problem.crews[1:]]})
    assert kernel_compat.unsupported_auxiliary_calendars(loaded) == [
        f"crew:{crew.id}:CAL-DAY"
    ]
    with pytest.raises(ValueError, match=kernel_compat.KERNEL_CALENDAR_UNSUPPORTED):
        kernel_compat.assert_kernel_calendar_compatibility(loaded)
