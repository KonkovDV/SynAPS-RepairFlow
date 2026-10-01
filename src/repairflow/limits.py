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
# Solver capability, not a DoS quota and not evidence that an 80-op instance solves.
CPSAT_OPS_CAP = 80
MVP_TARGET_OPS = (20, 100)
