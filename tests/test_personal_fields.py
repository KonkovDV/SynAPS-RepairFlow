"""domain_attributes may extend the contract, but not with a person's keys."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from repairflow.synthetic import synthesize


def test_known_extension_keys_still_load() -> None:
    problem = synthesize("tiny", seed=1)
    crew = problem.crews[0].model_copy(
        update={
            "domain_attributes": {
                "attendance": "unattended",
                "availability": "always_open",
                "defect_class": "leak",
                "skills": ["mechanical"],
            }
        }
    )
    assert crew.domain_attributes["defect_class"] == "leak"
    assert problem.domain_attributes["seed"] == 1


def test_a_surname_key_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    with pytest.raises(ValidationError, match="фамилия"):
        problem.crews[0].model_copy(update={"domain_attributes": {"фамилия": "скрыто"}})


def test_a_nested_phone_key_is_rejected() -> None:
    problem = synthesize("repair-site-mvp", seed=1)
    with pytest.raises(ValidationError, match="crew_phone"):
        problem.model_copy(update={"domain_attributes": {"notes": [{"crew_phone": "000"}]}})


def test_a_disguised_email_key_is_rejected() -> None:
    problem = synthesize("tiny", seed=1)
    with pytest.raises(ValidationError, match="e-mail"):
        problem.jobs[0].model_copy(update={"domain_attributes": {"e-mail": "a@b.c"}})


def test_a_note_rejects_email_phone_name_and_snils() -> None:
    problem = synthesize("tiny", seed=1)
    crew = problem.crews[0]
    for value in (
        "crew@example.com",
        "+7 000 000-00-00",
        "Иванов Иван Иванович",
        "Иванов И.И.",
        "112-233-445 95",
    ):
        with pytest.raises(ValidationError, match="personal record"):
            crew.model_copy(update={"domain_attributes": {"comment": value}})


def test_a_shop_note_without_those_shapes_still_loads() -> None:
    problem = synthesize("tiny", seed=1)
    crew = problem.crews[0].model_copy(
        update={"domain_attributes": {"comment": "Капитальный ремонт агрегата", "return_lag_min": 0}}
    )
    assert crew.domain_attributes["comment"] == "Капитальный ремонт агрегата"
    kept = problem.jobs[0].model_copy(update={"domain_attributes": {"comment": "112-233-445 90"}})
    assert kept.domain_attributes["comment"] == "112-233-445 90"
