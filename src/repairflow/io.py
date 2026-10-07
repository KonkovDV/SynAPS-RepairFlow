"""Bounded file reads at the CLI trust boundary."""

from __future__ import annotations

from pathlib import Path

from repairflow.limits import MAX_JSON_BYTES


def read_bytes_limited(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"{path} is larger than {max_bytes} bytes; limit is {max_bytes}")
    return data


def read_text_limited(path: Path, *, max_bytes: int = MAX_JSON_BYTES) -> str:
    return read_bytes_limited(path, max_bytes=max_bytes).decode("utf-8")


def read_text_encoded(path: Path, encoding: str, *, max_bytes: int = MAX_JSON_BYTES) -> str:
    try:
        return read_bytes_limited(path, max_bytes=max_bytes).decode(encoding)
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not encoded as {encoding}") from exc
