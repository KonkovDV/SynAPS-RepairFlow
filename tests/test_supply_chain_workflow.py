"""CI pins the action commits whose tags were reviewed for this phase."""

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


def test_actions_are_the_reviewed_commits() -> None:
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1" in CI
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0" in CI
    assert "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2" in CI
    assert "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131 # v7.0.0" in CI
    assert "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0" in CI
    assert "github/codeql-action/init@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2" in CODEQL
    assert "github/codeql-action/analyze@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2" in CODEQL
    assert "ossf/scorecard-action@2d1146689b8cda280b9bc96326124645441f03bc # v2.4.4" in SCORECARD
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
