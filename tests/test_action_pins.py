"""Third-party Actions stay on a commit. The tag is only a comment."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_USES = re.compile(r"uses:\s+(\S+)\s+#\s*(v\d+\S*)\s*$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def test_workflow_actions_are_pinned_to_a_commit() -> None:
    files = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
    assert files
    seen = 0
    for path in files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "uses:" not in line:
                continue
            match = _USES.search(line.strip())
            assert match is not None, f"{path.name}:{lineno} has no commit pin"
            ref, _tag = match.group(1), match.group(2)
            _name, pin = ref.rsplit("@", 1)
            assert _SHA.fullmatch(pin), ref
            seen += 1
    assert seen >= 8
