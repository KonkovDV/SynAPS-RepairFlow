"""Lane demand for a fungible resource.

A resource with capacity K has K interchangeable lanes. An occupancy is the
half-open interval ``[start, end)``. Touching at an endpoint does not use two
lanes. The demand is the maximum number of intervals that cover one instant.
That maximum is attained at a start event, so a sweep that applies ends before
starts at the same timestamp is an exact oracle for the peak.

Lanes are not named. Two distinct tools remain two resources; ``max_parallel``
only stacks fungible slots on one resource.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Occupancy:
    start: datetime
    end: datetime
    operation_id: str


@dataclass(frozen=True, slots=True)
class Excess:
    """An arrival that made the number of open lanes greater than capacity."""

    operation_id: str
    other_operation_id: str | None
    start: datetime
    end: datetime
    active: int


def peak_concurrency(intervals: list[Occupancy]) -> int:
    """Maximum number of half-open intervals covering one instant."""

    peak = 0
    active = 0
    for _time, kind, _index in _events(intervals):
        if kind == 0:
            active -= 1
        else:
            active += 1
            if active > peak:
                peak = active
    return peak


def excess_arrivals(intervals: list[Occupancy], capacity: int) -> list[Excess]:
    """Arrivals that push the open-lane count strictly above ``capacity``."""

    if capacity < 0:
        raise ValueError("capacity must be non-negative")
    open_rows: dict[int, Occupancy] = {}
    witnesses: list[Excess] = []
    for time, kind, index in _events(intervals):
        if kind == 0:
            open_rows.pop(index, None)
            continue
        row = intervals[index]
        open_rows[index] = row
        active = len(open_rows)
        if active <= capacity:
            continue
        others = sorted(item.operation_id for key, item in open_rows.items() if key != index)
        end = min(item.end for item in open_rows.values())
        witnesses.append(
            Excess(
                operation_id=row.operation_id,
                other_operation_id=others[0] if others else None,
                start=time,
                end=end,
                active=active,
            )
        )
    return witnesses


def _events(intervals: list[Occupancy]) -> list[tuple[datetime, int, int]]:
    """Ends (kind 0) sort before starts (kind 1) at the same timestamp."""

    events: list[tuple[datetime, int, int]] = []
    for index, row in enumerate(intervals):
        if row.start >= row.end:
            continue
        events.append((row.end, 0, index))
        events.append((row.start, 1, index))
    events.sort(key=lambda item: (item[0], item[1], item[2]))
    return events
