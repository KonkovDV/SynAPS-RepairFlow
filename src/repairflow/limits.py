"""Lab quotas for RepairFlow I/O. These are DoS/ergonomics caps, not capacity SLAs."""

from __future__ import annotations

MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JOBS = 5_000
MAX_OPERATIONS = 20_000
MAX_WORK_CENTERS = 2_000
MAX_CREWS = 2_000
MAX_AUX = 5_000
MAX_SETUP = 200_000
MAX_CALENDARS = 2_000
MAX_CALENDAR_WINDOWS = 10_000
MAX_FROZEN = 20_000
MAX_SPARES = 20_000
MAX_POOLS = 500
MAX_PRED_PER_OP = 8
# Last size at which CPSAT-10 returned a checked plan on the synthetic one-skill
# card with published shifts: 100 operations, feasible, about 7s. The same card
# at 120 operations timed out with an empty plan. This is an invocation ceiling,
# not evidence that every 100-operation instance solves.
CPSAT_OPS_CAP = 100
MVP_TARGET_OPS = (20, 100)
