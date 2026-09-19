from repairflow.planner import plan
from repairflow.reasons import ReasonCode
from repairflow.synthetic import synthesize


def test_missing_idle_setup_cells_are_rejected_on_ingest() -> None:
    from repairflow.model import RepairFlowProblem

    problem = synthesize("tiny", seed=1)
    payload = problem.model_dump(mode="python")
    payload["setup_matrix"] = [row for row in payload["setup_matrix"] if row["from_state"] != "idle"]
    try:
        RepairFlowProblem.model_validate(payload)
        raised = False
    except ValueError as exc:
        raised = True
        assert "setup_matrix" in str(exc)
    assert raised


def test_missing_idle_first_state_is_fail_closed() -> None:
    from repairflow.model import RepairFlowProblem

    problem = synthesize("tiny", seed=1)
    payload = problem.model_dump(mode="python")
    payload["policy"] = {**payload["policy"], "missing_setup": "zero"}
    payload["setup_matrix"] = [row for row in payload["setup_matrix"] if row["from_state"] != "idle"]
    stripped = RepairFlowProblem.model_validate(payload)
    fifo = plan(stripped, solver_config="FIFO")
    assert fifo.result.exit_code == 2
    missing = [row for row in fifo.result.violations if row.code == ReasonCode.MISSING_SETUP]
    assert missing
    assert any(row.details.get("from_state") == "idle" for row in missing)
