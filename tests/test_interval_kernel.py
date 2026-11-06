"""The Rust peak and the Python sweep count the same half-open minutes."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.oracle_minutes import (
    _sweep_exceeds,
    reset_native_interval_kernel,
)
from tools.build_interval_kernel import build, output_path

ROOT = Path(__file__).resolve().parents[1]


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 12, hour, minute, tzinfo=UTC)


def _walk(intervals: list[tuple[datetime, datetime]], cap: int) -> bool:
    if not intervals or cap < 0:
        return cap < 0
    start = min(left for left, _right in intervals)
    end = max(right for _left, right in intervals)
    moment = start
    while moment < end:
        active = sum(1 for left, right in intervals if left <= moment < right)
        if active > cap:
            return True
        moment += timedelta(minutes=1)
    return False


def test_the_python_sweep_matches_a_minute_walk() -> None:
    cases = [
        ([(_at(8), _at(9)), (_at(8, 30), _at(10))], 1),
        ([(_at(8), _at(9)), (_at(9), _at(10))], 1),
        ([(_at(8), _at(10)), (_at(8), _at(9)), (_at(8, 30), _at(9, 30))], 2),
        ([(_at(8), _at(8))], 0),
        ([], 1),
    ]
    for intervals, cap in cases:
        assert _sweep_exceeds(intervals, cap) is _walk(intervals, cap)


def _ensure_kernel() -> None:
    library = output_path()
    source = ROOT / "native" / "interval_kernel.rs"
    stale = not library.is_file() or source.stat().st_mtime > library.stat().st_mtime
    if not stale:
        return
    try:
        build()
    except subprocess.CalledProcessError:
        if not library.is_file():
            raise


def test_the_rust_kernel_matches_the_python_sweep() -> None:
    if shutil.which("rustc") is None:
        pytest.skip("rustc is not installed")
    _ensure_kernel()
    reset_native_interval_kernel()
    from tests import oracle_minutes

    kernel = oracle_minutes._native_kernel()
    assert kernel is not None
    cases = [
        ([(_at(8), _at(9)), (_at(8, 30), _at(10))], 1),
        ([(_at(8), _at(9)), (_at(9), _at(10))], 1),
        ([(_at(8), _at(12)), (_at(9), _at(11)), (_at(10), _at(13))], 2),
        ([(_at(8), _at(8))], 1),
    ]
    for intervals, cap in cases:
        assert kernel.exceeds(intervals, cap) is _sweep_exceeds(intervals, cap)
    reset_native_interval_kernel()
