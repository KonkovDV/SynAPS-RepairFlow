"""Public pages point at files that exist, and the README tables follow the code."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from repairflow.cli import main
from repairflow.reasons import REASON_CODES

_LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(([^)\s]+)\)")
_IMG = re.compile(r"<img\s[^>]*src=\"([^\"]+)\"")
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
_CHOICES = re.compile(r"\{([a-z,-]+)\}")


def _repo_root() -> Path:
    # The mutation sandbox copies only part of the tree; the checkout above it has every page.
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return here.parent


_ROOT = _repo_root()


def _pages() -> list[Path]:
    names = (
        "README.md",
        "APPLICATION.md",
        "AUDIT.md",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "LICENSES.md",
        "SECURITY.md",
    )
    pages = [_ROOT / name for name in names if (_ROOT / name).is_file()]
    pages.extend(sorted((_ROOT / "docs").rglob("*.md")))
    pages.extend(sorted((_ROOT / ".github").rglob("*.md")))
    return pages


def _slug(heading: str) -> str:
    text = _LINK.sub(lambda match: match.group(0).split("](", 1)[0].lstrip("!["), heading)
    text = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    text = _FENCE.sub("", path.read_text(encoding="utf-8"))
    seen: Counter[str] = Counter()
    anchors: set[str] = set()
    for heading in _HEADING.findall(text):
        slug = _slug(heading)
        anchors.add(slug if seen[slug] == 0 else f"{slug}-{seen[slug]}")
        seen[slug] += 1
    return anchors


def _targets(path: Path) -> list[str]:
    text = _FENCE.sub("", path.read_text(encoding="utf-8"))
    return _LINK.findall(text) + _IMG.findall(text)


def _broken(path: Path) -> list[str]:
    findings: list[str] = []
    for target in _targets(path):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue
        file_part, _, fragment = target.partition("#")
        resolved = (path.parent / file_part).resolve() if file_part else path
        if not resolved.exists():
            findings.append(f"{path.relative_to(_ROOT).as_posix()}: {target}")
            continue
        if fragment and resolved.suffix == ".md" and fragment not in _anchors(resolved):
            findings.append(f"{path.relative_to(_ROOT).as_posix()}: {target} (no heading)")
    return findings


def _section(title: str) -> str:
    text = (_ROOT / "README.md").read_text(encoding="utf-8")
    return text.split(f"\n## {title}\n", 1)[1].split("\n## ", 1)[0]


def _subcommands(argv: list[str], capsys: pytest.CaptureFixture[str]) -> list[str]:
    with pytest.raises(SystemExit):
        main(argv)
    usage = capsys.readouterr().out
    match = _CHOICES.search(usage)
    assert match is not None
    return match.group(1).split(",")


def test_relative_links_and_anchors_resolve() -> None:
    findings = [row for page in _pages() for row in _broken(page)]
    assert findings == []


def test_slug_matches_github_for_russian_headings() -> None:
    assert _slug("Как читать вердикт и код выхода") == "как-читать-вердикт-и-код-выхода"
    assert _slug("Посты, полосы и переналадка") == "посты-полосы-и-переналадка"
    assert _slug("Уровень A. Поминутный оракул") == "уровень-a-поминутный-оракул"


def test_readme_command_table_matches_the_parser(capsys: pytest.CaptureFixture[str]) -> None:
    commands = set(_subcommands(["--help"], capsys)) - {"log"}
    commands |= {f"log {name}" for name in _subcommands(["log", "--help"], capsys)}
    rows = re.findall(r"^\| `([a-z -]+)` \|", _section("Рабочий цикл и команды"), re.MULTILINE)
    assert sorted(rows) == sorted(commands)


def test_readme_reason_table_names_every_code() -> None:
    table = _section("Справочник кодов отказа")
    missing = [code for code in REASON_CODES if f"`{code}`" not in table]
    assert missing == []
