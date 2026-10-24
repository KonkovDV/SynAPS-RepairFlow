"""Every refusal code carries a Russian sentence and a Russian hint."""

from repairflow.checker import _violation
from repairflow.reasons import REASON_CODES, REASON_RU, SUGGESTIONS, ReasonCode


def test_every_reason_has_a_russian_sentence_and_a_hint() -> None:
    codes = {code.value for code in ReasonCode}
    assert codes == set(REASON_CODES)
    assert set(REASON_RU) == codes
    assert set(SUGGESTIONS) == codes
    assert all(text.strip() for text in REASON_RU.values())
    assert all(text.strip() for text in SUGGESTIONS.values())


def test_a_missing_hint_is_filled_from_the_code() -> None:
    hit = _violation(ReasonCode.UNKNOWN_OPERATION, "assignment names an unknown operation")
    assert hit.suggested_relaxation == SUGGESTIONS[ReasonCode.UNKNOWN_OPERATION]


def test_calendar_broken_repeats_the_window_hint() -> None:
    """Dropping the explicit window hint on this code stays the same sentence."""

    assert SUGGESTIONS[ReasonCode.CALENDAR_BROKEN] == SUGGESTIONS[ReasonCode.WINDOW_BROKEN]
