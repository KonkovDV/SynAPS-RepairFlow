"""Public pages must not carry phrases from docs/BANNED_CLAIMS.txt.

The matcher folds case, compatibility characters, format and nonspacing
marks, a short homoglyph set, HTML escapes, and tags. It does not stem
Russian. An exception is an exact source line in the allowlist, and each
exception needs its own reason.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

_BANNED_PATH = Path("docs/BANNED_CLAIMS.txt")
_ALLOW_PATH = Path("docs/banned-claims-allowlist.txt")
_MARKUP = re.compile(r"<[^>\n]+>|[*`]")
_LINK_TARGET = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_CONFUSABLES = str.maketrans(
    {
        "а": "a",
        "в": "b",
        "е": "e",
        "ё": "e",
        "ѕ": "s",
        "і": "i",
        "ї": "i",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "у": "y",
        "х": "x",
    }
)
_REVIEWED_PHRASES = frozenset(
    {
        "SOTA",
        "ИИ-планирование",
        "все планируют в Excel",
        "внедрено на СВАРЗ",
        "готово к КИИ",
        "доказанный эффект",
        "заменяет 1С",
        "заменяет КСУПТ",
        "заменяет Оптуран",
        "нет конкурентов",
        "нейросеть",
        "обучено на данных Мосгортранса",
        "первая в мире",
        "пилот на СВАРЗ",
        "промышленная эксплуатация",
        "уникальная математика",
    }
)


def _fold(text: str) -> str:
    plain = _MARKUP.sub("", html.unescape(text))
    # Decompose before dropping marks, so S + acute and precomposed Ś both become S.
    decomposed = unicodedata.normalize("NFKD", plain)
    kept = "".join(ch for ch in decomposed if unicodedata.category(ch) not in {"Cf", "Mn"})
    return kept.casefold().translate(_CONFUSABLES)


def _load_phrases() -> frozenset[str]:
    phrases = {line.strip() for line in _BANNED_PATH.read_text(encoding="utf-8").splitlines() if line.strip()}
    if any(not phrase for phrase in phrases):
        raise AssertionError("blank banned phrase")
    return frozenset(phrases)


def _public_pages() -> list[Path]:
    pages = [Path("README.md"), Path("APPLICATION.md")]
    pages.extend(sorted(path for path in Path("docs").rglob("*.md") if path.is_file()))
    return pages


def _parse_allowlist(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    pending: str | None = None
    for raw in text.splitlines():
        if raw.startswith("# reason:"):
            if pending is not None:
                raise AssertionError("two reasons without an entry")
            pending = raw.split(":", 1)[1].strip()
            if len(pending) < 20:
                raise AssertionError("allowlist reason is too short")
            continue
        if raw.strip() == "":
            if pending is not None:
                raise AssertionError("blank line between a reason and its entry")
            continue
        if pending is None:
            raise AssertionError(f"allowlist entry without a reason: {raw}")
        path, sep, exact = raw.partition(":")
        if sep != ":" or not path or path.startswith(("/", "\\")) or ".." in Path(path).parts:
            raise AssertionError(f"allowlist path is not a repo-relative file: {path}")
        entries.append((pending, path, exact))
        pending = None
    if pending is not None:
        raise AssertionError("reason without an entry")
    return entries


def _visible_text(line: str) -> str:
    """Drop markdown link destinations. Labels and the surrounding prose stay."""
    current = line
    previous: str | None = None
    while current != previous:
        previous = current
        current = _LINK_TARGET.sub(r"\1", current)
    return current


def _has_digit(text: str) -> bool:
    folded = _fold(text)
    return any(unicodedata.category(ch).startswith("N") for ch in folded)


def _hits(line: str, phrases: frozenset[str] | set[str]) -> list[str]:
    folded = _fold(line)
    return sorted(phrase for phrase in phrases if _fold(phrase) in folded)


def test_banned_phrase_list_is_the_reviewed_set() -> None:
    assert _load_phrases() == _REVIEWED_PHRASES


def test_public_pages_include_readme_application_and_adr() -> None:
    pages = {path.as_posix() for path in _public_pages()}
    assert "README.md" in pages
    assert "APPLICATION.md" in pages
    assert "docs/adr/0002-dag-over-chain-kernel.md" in pages
    assert all(path.suffix == ".md" for path in _public_pages())


def test_folded_phrase_matches_disguise() -> None:
    phrases = frozenset({"SOTA"})
    assert _hits("sota", phrases) == ["SOTA"]
    assert _hits("S\u041eT\u0410", phrases) == ["SOTA"]
    assert _hits("S\u200bOTA", phrases) == ["SOTA"]
    assert _hits("S\u0301OTA", phrases) == ["SOTA"]
    assert _hits("\u015aOTA", phrases) == ["SOTA"]
    assert _hits("ＳＯＴＡ", phrases) == ["SOTA"]
    assert _hits("S**OTA**", phrases) == ["SOTA"]
    assert _hits("S&#79;TA", phrases) == ["SOTA"]
    assert _hits("S<i>OTA</i>", phrases) == ["SOTA"]
    assert _hits("S\u00adOTA", phrases) == ["SOTA"]
    phrase = next(item for item in _REVIEWED_PHRASES if item.startswith("заменяет 1"))
    latin_c = phrase.replace("\u0421", "C")
    assert latin_c != phrase
    assert _hits(latin_c, frozenset({phrase})) == [phrase]


def test_exact_allowlist_line_does_not_cover_a_neighbor() -> None:
    allowed = {"docs/a.md": {"нейросеть не используем"}}
    phrase = frozenset({"нейросеть"})
    exact = "нейросеть не используем"
    neighbor = "нейросеть не используем в бою"
    assert _hits(exact, phrase) == ["нейросеть"]
    assert exact in allowed["docs/a.md"]
    assert neighbor not in allowed["docs/a.md"]
    assert _hits(neighbor, phrase) == ["нейросеть"]


def test_ordinary_russian_does_not_match_the_phrase_list() -> None:
    sample = "Календарь бригады закрыт, пост свободен, смена до вечера."
    assert _hits(sample, _load_phrases()) == []


def test_allowlist_entries_are_exact_public_lines() -> None:
    entries = _parse_allowlist(_ALLOW_PATH.read_text(encoding="utf-8"))
    assert 0 < len(entries) <= 5
    pages = {path.as_posix(): set(path.read_text(encoding="utf-8").splitlines()) for path in _public_pages()}
    for _reason, path, exact in entries:
        assert path in pages
        assert exact in pages[path]


def test_public_pages_do_not_use_banned_phrases() -> None:
    phrases = _load_phrases()
    allowed: dict[str, set[str]] = {}
    for _reason, path, exact in _parse_allowlist(_ALLOW_PATH.read_text(encoding="utf-8")):
        allowed.setdefault(path, set()).add(exact)
    findings: list[str] = []
    for path in _public_pages():
        key = path.as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line in allowed.get(key, set()):
                continue
            for phrase in _hits(line, phrases):
                findings.append(f"{key}:{number}: {phrase}")
    assert findings == []


def test_readme_outside_the_evidence_block_has_no_digits() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    begin = "<!-- evidence:begin -->"
    end = "<!-- evidence:end -->"
    assert text.count(begin) == 1
    assert text.count(end) == 1
    head, rest = text.split(begin, 1)
    _block, tail = rest.split(end, 1)
    numbered = [line for line in (head + tail).splitlines() if _has_digit(_visible_text(line))]
    assert numbered == []


def test_readme_digit_rule_ignores_link_destinations_only() -> None:
    assert not _has_digit(_visible_text("[обзор](docs/literature-2026.md)"))
    assert _has_digit(_visible_text("[обзор 2026](docs/literature.md)"))
    assert _has_digit(_visible_text("pilot до 90 дней"))
    assert _has_digit(_visible_text("TRL &#52;"))
    assert _has_digit(_visible_text("see [обзор](docs/literature-2026.md) and 40%"))


def test_literature_pages_replaced_the_old_names() -> None:
    assert Path("docs/literature-2026.md").is_file()
    assert Path("docs/evidence-protocol.md").is_file()
    assert not Path("docs/SOTA_2026.md").exists()
    assert not Path("docs/SOTA_EVIDENCE_PROTOCOL.md").exists()
