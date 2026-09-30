"""Fail-closed compatibility tests for the pinned SynAPS kernel."""

from __future__ import annotations

import pytest

from repairflow.kernel_compat import (
    KERNEL_CALENDAR_UNSUPPORTED,
    assert_kernel_calendar_compatibility,
    unsupported_auxiliary_calendars,
)
from repairflow.synthetic import synthesize


def test_plain_synthetic_problem_is_kernel_calendar_compatible() -> None:
    problem = synthesize("tiny", seed=1)
    assert unsupported_auxiliary_calendars(problem) == []
    assert_kernel_calendar_compatibility(problem)


def test_auxiliary_calendar_is_rejected_with_stable_reason() -> None:
    problem = synthesize("tiny", seed=1)
    aux = problem.aux_resources[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"aux_resources": [aux, *problem.aux_resources[1:]]})
    assert unsupported_auxiliary_calendars(loaded) == [f"aux:{aux.id}:CAL-DAY"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)


def test_crew_calendar_is_rejected_with_stable_reason() -> None:
    problem = synthesize("tiny", seed=1)
    crew = problem.crews[0].model_copy(update={"calendar_id": "CAL-DAY"})
    loaded = problem.model_copy(update={"crews": [crew, *problem.crews[1:]]})
    assert unsupported_auxiliary_calendars(loaded) == [f"crew:{crew.id}:CAL-DAY"]
    with pytest.raises(ValueError, match=KERNEL_CALENDAR_UNSUPPORTED):
        assert_kernel_calendar_compatibility(loaded)
