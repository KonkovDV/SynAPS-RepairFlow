"""The laboratory image installs only from the hashed wheelhouse."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
BASE = "python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258"


def test_image_installs_only_from_the_wheelhouse() -> None:
    assert f"FROM {BASE}" in DOCKERFILE
    assert "--no-index" in DOCKERFILE
    assert "--require-hashes" in DOCKERFILE
    assert "wheelhouse/synaps-*.whl" in DOCKERFILE
    assert "wheelhouse/synaps_repairflow-*.whl" in DOCKERFILE
    assert "https://pypi.org" not in DOCKERFILE
    assert "pip install -e" not in DOCKERFILE
    assert "USER nobody" in DOCKERFILE


def test_ci_builds_the_image_without_a_network() -> None:
    assert "offline-image:" in CI
    assert "needs: wheelhouse" in CI
    assert "docker pull " + BASE in CI
    assert "docker build --pull=false --network none" in CI
    assert "docker run --rm --network none" in CI
    assert "repairflow:lab version" in CI
