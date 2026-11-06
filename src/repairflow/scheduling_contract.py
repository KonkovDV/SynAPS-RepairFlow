"""Shared duration and calendar contract for the checker, planner, and ingest.

``exact`` is the default: the processing interval is ``duration_min`` minutes.
``min`` allows a longer interval. ``preemptive`` may cross closed gaps; only
open minutes count. An ``attendance=unattended`` resource keeps running when
its staffed calendar is closed. An empty calendar on an attended resource is
closed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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


def declares_open_horizon(attributes: Mapping[str, Any]) -> bool:
    """24/7 is allowed only when the resource says so."""
    return str(attributes.get("availability", "")).lower() == "always_open"


def held_minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def is_whole_minutes(start: datetime, end: datetime) -> bool:
    """True when ``end - start`` has no sub-minute remainder; held_minutes floors seconds."""
    return (end - start) % timedelta(minutes=1) == timedelta(0)


def merge_windows(windows: Iterable[Any]) -> list[tuple[datetime, datetime]]:
    """Coalesce touching or overlapping windows (objects with ``start``/``end``)."""
    merged: list[tuple[datetime, datetime]] = []
    for window in sorted(windows, key=lambda row: (row.start, row.end)):
        if merged and window.start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], window.end))
        else:
            merged.append((window.start, window.end))
    return merged


def open_minutes(start: datetime, end: datetime, masks: list[list[Window]]) -> int:
    """Minutes of ``[start, end)`` that sit in every attended window mask.

    An empty mask list means the interval is open for its whole length.
    Overlapping windows of one mask are one open stretch: a minute that
    sits in two windows is counted once.
    """

    if end <= start:
        return 0
    pieces: list[Window] = [(start, end)]
    for windows in masks:
        pieces = _intersect(pieces, _merge_spans(windows))
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
    pieces = _intersect([(start, horizon_end)], _merge_spans(masks[0]))
    for windows in masks[1:]:
        pieces = _intersect(pieces, _merge_spans(windows))
    remaining = minutes
    for left, right in pieces:
        span = held_minutes(left, right)
        if span >= remaining:
            return left + timedelta(minutes=remaining)
        remaining -= span
    return None


def _merge_spans(windows: list[Window]) -> list[Window]:
    """Coalesce touching or overlapping half-open spans. A point in two spans counts once."""

    merged: list[Window] = []
    for start, end in sorted(windows):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


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
