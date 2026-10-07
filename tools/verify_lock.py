"""Fail CI when the lock drifts off the SynAPS pin or drops a wheel hash."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements-lock.txt"
VERSIONS = ROOT / "src" / "repairflow" / "versions.py"
PYPROJECT = ROOT / "pyproject.toml"
SHA_RE = re.compile(r'SYNAPS_COMMIT\s*=\s*"([0-9a-f]{40})"')
HASH_RE = re.compile(r"--hash=sha256:[0-9a-f]{64}(?![0-9a-f])")
GIT_RE = re.compile(r"^synaps @ git\+https://github\.com/KonkovDV/SynAPS\.git@([0-9a-f]{40})(?:\s|$)")
PYDANTIC_EXACT = re.compile(r"^pydantic==[0-9]")


def requirement_blocks(text: str) -> list[str]:
    """Join backslash continuations. Comments and blank lines separate blocks."""
    blocks: list[str] = []
    parts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        continued = line.endswith("\\")
        if continued:
            line = line[:-1].strip()
        if line:
            parts.append(line)
        if not continued and parts:
            blocks.append(" ".join(parts))
            parts = []
    if parts:
        blocks.append(" ".join(parts))
    return blocks


def audit_lock(text: str, expected_sha: str) -> list[str]:
    """Return fail-closed findings. An empty list means the lock is acceptable."""
    failures: list[str] = []
    if not expected_sha:
        failures.append("versions.py: SYNAPS_COMMIT is not a full SHA")
    blocks = requirement_blocks(text)
    if not blocks:
        failures.append("requirements-lock.txt: no requirements")
    saw_pin = False
    saw_pydantic = False
    for block in blocks:
        pin = GIT_RE.match(block)
        if pin is not None:
            saw_pin = True
            if expected_sha and pin.group(1) != expected_sha:
                failures.append("requirements-lock.txt: git pin SHA does not match versions.py")
            continue
        if HASH_RE.search(block) is None:
            name = block.split(maxsplit=1)[0]
            failures.append(f"requirements-lock.txt: missing hash for {name}")
        if block.startswith("pydantic==") or block.startswith("pydantic>") or block.startswith("pydantic<"):
            saw_pydantic = True
            if PYDANTIC_EXACT.match(block) is None:
                failures.append("requirements-lock.txt: pydantic is not an exact pin")
    if not saw_pin:
        failures.append("requirements-lock.txt: synaps is not a git pin")
    if not saw_pydantic:
        failures.append("requirements-lock.txt: pydantic pin missing")
    if "pydantic>=" in text or "pydantic <" in text:
        failures.append("requirements-lock.txt: pydantic is a range")
    return failures


def split_lock(text: str) -> tuple[str, str]:
    """Return the git pin and the hashed requirements as pip-installable text."""
    git_lines: list[str] = []
    hashed: list[str] = []
    for block in requirement_blocks(text):
        if GIT_RE.match(block) is not None:
            git_lines.append(block.split(" --hash=", maxsplit=1)[0].strip())
            continue
        hashed.append(block)
    git_text = "\n".join(git_lines)
    hashed_text = "\n".join(hashed)
    if git_text:
        git_text += "\n"
    if hashed_text:
        hashed_text += "\n"
    return git_text, hashed_text


def _expected_sha() -> str:
    match = SHA_RE.search(VERSIONS.read_text(encoding="utf-8"))
    if match is None:
        return ""
    return match.group(1)


def _emit(flag: str, args: list[str]) -> Path | None:
    if flag not in args:
        return None
    index = args.index(flag)
    if index + 1 >= len(args):
        sys.stderr.write(f"lock-pin failed: {flag} needs a path\n")
        raise SystemExit(1)
    return Path(args[index + 1])


def main() -> int:
    failures: list[str] = []
    expected = _expected_sha()
    lock = LOCK.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    failures.extend(audit_lock(lock, expected))
    if expected and expected not in pyproject:
        failures.append(f"pyproject.toml: missing pin {expected}")
    if "pydantic==" not in pyproject:
        failures.append("pyproject.toml: pydantic is not an exact pin")
    digest = hashlib.sha256(lock.encode("utf-8")).hexdigest()
    if failures:
        sys.stderr.write("lock-pin failed:\n")
        for row in failures:
            sys.stderr.write(f"  {row}\n")
        return 1
    hashed_out = _emit("--hashed-out", sys.argv[1:])
    git_out = _emit("--git-out", sys.argv[1:])
    if hashed_out is not None or git_out is not None:
        git_text, hashed_text = split_lock(lock)
        if git_out is not None:
            git_out.write_text(git_text, encoding="utf-8", newline="\n")
        if hashed_out is not None:
            hashed_out.write_text(hashed_text, encoding="utf-8", newline="\n")
    sys.stdout.write(f"lock-pin ok synaps={expected} lock_sha256={digest}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
