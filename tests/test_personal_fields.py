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
