"""Reject domain_attributes keys and a few value shapes that name a person.

A free note that matches none of these shapes can still carry a name.
Retention is a contract, not a number chosen here.
This is not a personal-data compliance claim.
"""

from __future__ import annotations

import re
from typing import Any

_PERSONAL_KEYS = frozenset(
    {
        "fio",
        "full_name",
        "first_name",
        "last_name",
        "middle_name",
        "given_name",
        "surname",
        "family_name",
        "patronymic",
        "фио",
        "фамилия",
        "имя",
        "отчество",
        "phone",
        "telephone",
        "mobile",
        "email",
        "e_mail",
        "телефон",
        "почта",
        "электронная_почта",
        "passport",
        "passport_number",
        "snils",
        "birth_date",
        "date_of_birth",
        "dob",
        "паспорт",
        "снилс",
        "дата_рождения",
        "personnel_number",
        "personnel_id",
        "tab_number",
        "tabel_number",
        "employee_number",
        "staff_number",
        "badge_number",
        "табельный",
        "табельный_номер",
        "табель",
    }
)

# Letters that look like Latin when the key is trying to spell a Latin word.
_HOMO = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ї": "i",
        "ѕ": "s",
    }
)


def _tokens(key: object) -> tuple[str, str]:
    raw = str(key).strip().casefold().replace("ё", "е")
    raw = "_".join(raw.replace("-", " ").replace(".", " ").split())
    return raw, raw.translate(_HOMO)


def _forbidden(token: str) -> bool:
    if token in _PERSONAL_KEYS:
        return True
    return any(part in _PERSONAL_KEYS for part in token.split("_") if part)


_EMAIL = re.compile(r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])")
_PHONE = re.compile(r"(?<!\d)(?:\+7|8)[\s(]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?!\d)")
_SNILS = re.compile(r"^\d{3}-?\d{3}-?\d{3}\s?\d{2}$")
_FIO = re.compile(
    r"(?u)(?<!\w)[А-ЯЁ][а-яё]{1,}\s+[А-ЯЁ][а-яё]{1,}\s+[А-ЯЁ][а-яё]*(?:вич|вна|ична|оглы|кызы)(?!\w)"
)
_INITIALS = re.compile(r"(?u)(?<!\w)[А-ЯЁ][а-яё]{1,}\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.(?!\w)")


def _snils_checksum(text: str) -> bool:
    compact = re.sub(r"[\s-]", "", text.strip())
    if not _SNILS.fullmatch(text.strip()) or len(compact) != 11:
        return False
    body, check = compact[:9], int(compact[9:])
    total = sum(int(digit) * weight for digit, weight in zip(body, range(9, 0, -1), strict=True))
    if total in {100, 101}:
        expected = 0
    elif total < 100:
        expected = total
    else:
        expected = total % 101
        if expected == 100:
            expected = 0
    return check == expected


def _personal_value(value: str) -> bool:
    if _EMAIL.search(value) or _PHONE.search(value) or _FIO.search(value) or _INITIALS.search(value):
        return True
    return _snils_checksum(value)


def reject_personal_attribute_keys(attributes: dict[str, Any]) -> dict[str, Any]:
    """Raise ValueError when a key or a value shape names a person."""

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                raw, folded = _tokens(key)
                if _forbidden(raw) or _forbidden(folded):
                    raise ValueError(
                        f"domain_attributes key {key!r} names a person; "
                        "keep a pseudonym outside this dictionary"
                    )
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, str) and _personal_value(node):
            raise ValueError(
                "domain_attributes value looks like a personal record; "
                "keep a pseudonym outside this dictionary"
            )

    walk(attributes)
    return attributes
