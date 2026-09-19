from repairflow import REPAIRFLOW_VERSION, SYNAPS_COMMIT
from repairflow.versions import CLAIM_LEVEL


def test_version_and_full_pin() -> None:
    assert REPAIRFLOW_VERSION == "0.1.0"
    assert len(SYNAPS_COMMIT) == 40
    assert all(char in "0123456789abcdef" for char in SYNAPS_COMMIT.lower())
    assert CLAIM_LEVEL == "experiment"
