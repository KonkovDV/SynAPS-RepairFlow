from pathlib import Path

import synaps

from repairflow.versions import REPAIRFLOW_VERSION, SYNAPS_COMMIT, SYNAPS_REPO


def test_pyproject_and_lock_share_the_full_sha() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    lock = (root / "requirements-lock.txt").read_text(encoding="utf-8")
    assert f'version = "{REPAIRFLOW_VERSION}"' in pyproject
    assert SYNAPS_COMMIT in pyproject
    assert SYNAPS_COMMIT in lock
    assert "synaps @ git+" in lock


def test_declared_repo_and_import() -> None:
    assert SYNAPS_REPO.endswith("/SynAPS")
    assert synaps.__name__ == "synaps"
