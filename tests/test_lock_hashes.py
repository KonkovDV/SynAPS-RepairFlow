"""The lock is a hash freeze. Only the SynAPS git pin is allowed to omit a hash."""

from __future__ import annotations

from pathlib import Path

from tools.verify_lock import HASH_RE, audit_lock, requirement_blocks, split_lock

ROOT = Path(__file__).resolve().parents[1]
SHA = "f939727cd9369fd9b36438bfac7198f0c39c6d3b"
PIN = f"synaps @ git+https://github.com/KonkovDV/SynAPS.git@{SHA}"
FAKE_HASH = "--hash=sha256:" + ("ab" * 32)


def test_committed_lock_has_a_hash_on_every_wheel() -> None:
    lock = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert audit_lock(lock, SHA) == []
    assert "pydantic==2.13.5" in project
    assert "pydantic>=" not in project
    assert "ortools==9.15.6755" in lock
    assert "hatchling==1.32.4" in lock
    git_text, hashed_text = split_lock(lock)
    assert git_text.strip() == PIN
    assert "git+" not in hashed_text
    assert hashed_text.count("synaps @") == 0
    for block in requirement_blocks(hashed_text):
        assert HASH_RE.search(block) is not None


def test_a_wheel_without_a_hash_is_rejected() -> None:
    text = f"{PIN}\npydantic==2.13.5 \\\n    {FAKE_HASH}\nrequests==2.32.0\n"
    failures = audit_lock(text, SHA)
    assert any("requests" in row for row in failures)


def test_a_ranged_pydantic_pin_is_rejected() -> None:
    text = f"{PIN}\npydantic>=2.9 \\\n    {FAKE_HASH}\n"
    failures = audit_lock(text, SHA)
    assert any("exact pin" in row for row in failures)
    assert any("range" in row for row in failures)


def test_another_git_url_is_not_exempt() -> None:
    text = (
        f"{PIN}\n"
        "other @ git+https://example.invalid/other.git@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        f"pydantic==2.13.5 \\\n    {FAKE_HASH}\n"
    )
    failures = audit_lock(text, SHA)
    assert any("other" in row for row in failures)


def test_a_mismatched_kernel_sha_is_rejected() -> None:
    other = "a" * 40
    text = (
        f"synaps @ git+https://github.com/KonkovDV/SynAPS.git@{other}\npydantic==2.13.5 \\\n    {FAKE_HASH}\n"
    )
    failures = audit_lock(text, SHA)
    assert any("does not match" in row for row in failures)
