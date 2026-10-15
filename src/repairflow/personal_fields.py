"""Reject domain_attributes keys that name a person.

The check reads the key, not the value. A free note can still carry a name.
This is not a personal-data compliance claim.
"""

from __future__ import annotations

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


def reject_personal_attribute_keys(attributes: dict[str, Any]) -> dict[str, Any]:
    """Raise ValueError when a key names a person. Return the same mapping otherwise."""

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

    walk(attributes)
    return attributes
