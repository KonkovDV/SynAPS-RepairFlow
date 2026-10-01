from repairflow.model import RepairFlowProblem
from repairflow.planner import plan, recheck
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def _without_auxiliary_calendars(problem: RepairFlowProblem) -> RepairFlowProblem:
    crews = [row.model_copy(update={"calendar_id": None}) for row in problem.crews]
    aux_resources = [row.model_copy(update={"calendar_id": None}) for row in problem.aux_resources]
    return problem.model_copy(update={"crews": crews, "aux_resources": aux_resources})


def _skilled_ops_have_named_crews(solver_config: str, *, kernel: bool) -> None:
    problem = synthesize("tiny", seed=1)
    if kernel:
        problem = _without_auxiliary_calendars(problem)
    outcome = plan(problem, solver_config=solver_config)
    ops = {op.id: op for op in problem.operations}
    skilled = [row for row in outcome.result.assignments if ops[row.operation_id].required_skills]
    assert skilled
    assert all(row.crew_id for row in skilled)
    crews = {crew.id for crew in problem.crews}
    assert all(row.crew_id in crews for row in skilled)


def test_greed_assigns_a_named_crew() -> None:
    _skilled_ops_have_named_crews("GREED", kernel=False)


def test_cpsat_assigns_a_named_crew_without_auxiliary_calendars() -> None:
    _skilled_ops_have_named_crews("CPSAT-10", kernel=True)


def test_rhc_assigns_a_named_crew_without_auxiliary_calendars() -> None:
    _skilled_ops_have_named_crews("RHC-GREEDY-COVER", kernel=True)


def test_checker_rejects_unbound_skilled_candidate() -> None:
    problem = synthesize("tiny", seed=1)
    clean = plan(problem, solver_config="GREED")
    operations = {op.id: op for op in problem.operations}
    candidate = [
        row.model_copy(update={"crew_id": None}) if operations[row.operation_id].required_skills else row
        for row in clean.result.assignments
    ]

    outcome = recheck(
        problem,
        assignments=candidate,
        kernel_status="feasible",
        solver_config="unbound-crew-adversarial",
    )

    assert outcome.result.verified_feasible is False
    assert outcome.result.exit_code == 2
    assert outcome.result.claim_status == "rejected"
    assert any(row.code == ReasonCode.CREW_UNBOUND for row in outcome.result.violations)
    skilled = [row for row in outcome.result.assignments if operations[row.operation_id].required_skills]
    assert skilled
    assert all(row.crew_id is None for row in skilled)


def test_checker_rejects_an_unknown_explicit_crew() -> None:
    problem = synthesize("tiny", seed=1)
    clean = plan(problem, solver_config="GREED")
    skilled = next(op for op in problem.operations if op.required_skills)
    rows = [
        row.model_copy(update={"crew_id": "CREW-MISSING"}) if row.operation_id == skilled.id else row
        for row in clean.result.assignments
    ]
    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="feasible",
        solver_config="unknown-crew-adversarial",
    )
    assert outcome.result.verified_feasible is False
    assert any(
        row.code == ReasonCode.UNKNOWN_RESOURCE and row.resource_id == "CREW-MISSING"
        for row in outcome.result.violations
    )
    assert not any(
        row.code == ReasonCode.CREW_UNBOUND and row.operation_id == skilled.id
        for row in outcome.result.violations
    )
    kept = next(row for row in outcome.result.assignments if row.operation_id == skilled.id)
    assert kept.crew_id == "CREW-MISSING"


def test_checker_rejects_an_unqualified_explicit_crew() -> None:
    problem = synthesize("tiny", seed=1)
    clean = plan(problem, solver_config="GREED")
    skilled = next(op for op in problem.operations if "mechanical" in op.required_skills)
    rows = [
        row.model_copy(update={"crew_id": "CREW-TEST"}) if row.operation_id == skilled.id else row
        for row in clean.result.assignments
    ]
    outcome = recheck(
        problem,
        assignments=rows,
        kernel_status="feasible",
        solver_config="unqualified-crew-adversarial",
    )
    assert outcome.result.verified_feasible is False
    assert any(
        row.code == ReasonCode.SKILL_MISMATCH and row.operation_id == skilled.id
        for row in outcome.result.violations
    )
    kept = next(row for row in outcome.result.assignments if row.operation_id == skilled.id)
    assert kept.crew_id == "CREW-TEST"


def test_explicit_qualified_crew_stays_clean() -> None:
    problem = synthesize("tiny", seed=1)
    clean = plan(problem, solver_config="GREED")
    outcome = recheck(
        problem,
        assignments=list(clean.result.assignments),
        kernel_status="feasible",
        solver_config="explicit-crew",
    )
    assert outcome.result.verified_feasible is True
    assert outcome.result.exit_code == 0
    assert not any(row.code == ReasonCode.CREW_UNBOUND for row in outcome.result.violations)
