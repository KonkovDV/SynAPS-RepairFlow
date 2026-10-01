from repairflow.planner import plan
from repairflow.synthetic import synthesize


def test_cpsat_tiny_refuses_crew_calendars() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="CPSAT-10")
    assert outcome.result.exit_code == 2
    assert outcome.result.verified_feasible is False
    assert outcome.result.claim_status != "optimal"
    assert any(row.code == "KERNEL_CALENDAR_UNSUPPORTED" for row in outcome.result.violations)


def test_rhc_greedy_cover_tiny_refuses_crew_calendars() -> None:
    outcome = plan(synthesize("tiny", seed=1), solver_config="RHC-GREEDY-COVER")
    assert outcome.result.exit_code == 2
    assert outcome.result.verified_feasible is False
    assert any(row.code == "KERNEL_CALENDAR_UNSUPPORTED" for row in outcome.result.violations)
