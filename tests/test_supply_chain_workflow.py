"""CI pins the action tags whose release notes were read for this phase."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
CODEQL = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")
SCORECARD = (ROOT / ".github" / "workflows" / "scorecard.yml").read_text(encoding="utf-8")


def test_runners_stay_on_ubuntu_24_04() -> None:
    for text in (CI, CODEQL, SCORECARD):
        assert "ubuntu-latest" not in text
        assert "ubuntu-26" not in text
        assert "ubuntu-24.04" in text


def test_actions_are_the_reviewed_tags() -> None:
    assert "actions/checkout@v7.0.1" in CI
    assert "actions/setup-python@v7.0.0" in CI
    assert "actions/upload-artifact@v7.0.2" in CI
    assert "actions/download-artifact@v7.0.0" in CI
    assert "actions/dependency-review-action@v5.0.0" in CI
    assert "github/codeql-action/init@v4.38.2" in CODEQL
    assert "github/codeql-action/analyze@v4.38.2" in CODEQL
    assert "ossf/scorecard-action@v2.4.4" in SCORECARD
    assert "publish_results: false" in SCORECARD


def test_the_wheel_config_does_not_include_the_package_twice() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/repairflow"]' in project
    assert "force-include" not in project


def test_install_uses_hashes_and_the_demo_stays_offline() -> None:
    assert CI.count("--require-hashes") >= 2
    assert "--no-index" in CI
    assert "--no-build-isolation" in CI
    assert "-e ." not in CI
    assert "pip install -U pip" not in CI
    assert "repairflow demo" in CI
    assert "pull_request" not in SCORECARD.split("jobs:", maxsplit=1)[0]
