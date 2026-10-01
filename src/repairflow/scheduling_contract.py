"""Shared duration and calendar contract for the checker, planner, and ingest.

``exact`` is the default: the processing interval is ``duration_min`` minutes.
``min`` allows a longer interval. ``preemptive`` may cross closed gaps; only
open minutes count. An ``attendance=unattended`` resource keeps running when
its staffed calendar is closed. An empty calendar on an attended resource is
closed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

POLICIES = frozenset({"exact", "min", "preemptive"})
Window = tuple[datetime, datetime]


def policy_of(attributes: Mapping[str, Any]) -> str:
    raw = attributes.get("duration_policy", "exact")
    if isinstance(raw, str) and raw in POLICIES:
        return raw
    return "invalid"


def is_unattended(attributes: Mapping[str, Any]) -> bool:
    return str(attributes.get("attendance", "attended")).lower() == "unattended"


def held_minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def open_minutes(start: datetime, end: datetime, masks: list[list[Window]]) -> int:
    """Minutes of ``[start, end)`` that sit in every attended window mask.

    An empty mask list means the interval is open for its whole length.
    """

    if end <= start:
        return 0
    pieces: list[Window] = [(start, end)]
    for windows in masks:
        pieces = _intersect(pieces, windows)
        if not pieces:
            return 0
    return sum(held_minutes(left, right) for left, right in pieces)


def end_covering_open_minutes(
    start: datetime,
    minutes: int,
    masks: list[list[Window]],
    horizon_end: datetime,
) -> datetime | None:
    """Return the end where open minutes reach ``minutes``, or None."""

    if minutes < 1 or start >= horizon_end:
        return None
    if not masks:
        end = start + timedelta(minutes=minutes)
        return end if end <= horizon_end else None
    pieces = _intersect([(start, horizon_end)], masks[0])
    for windows in masks[1:]:
        pieces = _intersect(pieces, windows)
    remaining = minutes
    for left, right in pieces:
        span = held_minutes(left, right)
        if span >= remaining:
            return left + timedelta(minutes=remaining)
        remaining -= span
    return None


def _intersect(pieces: list[Window], windows: list[Window]) -> list[Window]:
    out: list[Window] = []
    ordered = sorted(windows)
    for left, right in pieces:
        for win_start, win_end in ordered:
            lo = left if left >= win_start else win_start
            hi = right if right <= win_end else win_end
            if hi > lo:
                out.append((lo, hi))
    return out
