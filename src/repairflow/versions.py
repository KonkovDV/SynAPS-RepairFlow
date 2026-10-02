"""Package / upstream version pins (explicit, reproducible)."""

from typing import Literal

REPAIRFLOW_VERSION = "0.1.0"

# ISO 16290 TRL 4: lab fixtures and automated checks. Not a depot pilot.
ISO16290_TRL = 4
CLAIM_LEVEL: Literal["experiment"] = "experiment"

# SynAPS commit this RepairFlow release is validated against.
# Bump deliberately when upgrading the engine; never float on branch tips.
SYNAPS_COMMIT = "1f7d5e0ede2944d21579574edf84976fe5e78808"
SYNAPS_REPO = "https://github.com/KonkovDV/SynAPS"
