"""Normalized hard-decision witnesses.

A witness records which verifier rejected a plan and which stable code it used.
Domain reason codes and kernel kind strings are not required to be equal.
The hard decision is only whether that verifier's witness list is empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from repairflow.model import Violation


@dataclass(frozen=True, slots=True)
class HardWitness:
    verifier: Literal["domain", "kernel"]
    code: str
    operation_id: str | None = None
    resource_id: str | None = None


def domain_hard_witnesses(violations: list[Violation]) -> list[HardWitness]:
    rows = [
        HardWitness(
            verifier="domain",
            code=row.code,
            operation_id=row.operation_id,
            resource_id=row.resource_id,
        )
        for row in violations
        if row.severity == "hard"
    ]
    return sorted(rows, key=_key)


def kernel_hard_witnesses(rows: list[dict[str, Any]]) -> list[HardWitness]:
    """Project kernel hard rows onto the witness fields.

    The kernel payload's message text is ignored. Kind is the stable code.
    """

    witnesses = [HardWitness(verifier="kernel", code=str(row.get("kind") or "KERNEL")) for row in rows]
    return sorted(witnesses, key=_key)


def same_hard_decision(domain: list[HardWitness], kernel: list[HardWitness]) -> bool:
    """True when both verifiers are clean, or both report at least one hard witness."""

    return bool(domain) == bool(kernel)


def _key(row: HardWitness) -> tuple[str, str, str, str]:
    return (row.verifier, row.code, row.operation_id or "", row.resource_id or "")
