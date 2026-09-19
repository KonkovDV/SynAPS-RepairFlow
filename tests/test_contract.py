import json
from pathlib import Path

from jsonschema import Draft202012Validator

from repairflow.synthetic import synthesize


def test_problem_schema_accepts_mvp_fixture() -> None:
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas" / "repairflow.problem.v1.json").read_text(
            encoding="utf-8"
        )
    )
    problem = synthesize("repair-site-mvp", seed=42)
    Draft202012Validator(schema).validate(problem.model_dump(mode="json"))


def test_schema_examples_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    examples = root / "schemas" / "examples"
    problem_schema = json.loads((root / "schemas" / "repairflow.problem.v1.json").read_text(encoding="utf-8"))
    result_schema = json.loads((root / "schemas" / "repairflow.result.v1.json").read_text(encoding="utf-8"))
    diff_schema = json.loads((root / "schemas" / "repairflow.diff.v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(problem_schema).validate(
        json.loads((examples / "tiny.problem.json").read_text(encoding="utf-8"))
    )
    Draft202012Validator(result_schema).validate(
        json.loads((examples / "tiny.greed.result.json").read_text(encoding="utf-8"))
    )
    Draft202012Validator(diff_schema).validate(
        json.loads((examples / "tiny.diff.json").read_text(encoding="utf-8"))
    )


def test_unknown_fields_are_rejected() -> None:
    problem = synthesize("tiny", seed=1).model_dump(mode="json")
    problem["surprise"] = True
    try:
        from repairflow.model import RepairFlowProblem

        RepairFlowProblem.model_validate(problem)
        raised = False
    except Exception:
        raised = True
    assert raised
