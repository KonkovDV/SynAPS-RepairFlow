"""A customer extract needs a manifest. A night shift is one window across two dates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from repairflow.cli import main
from repairflow.ingest import load_manifest, pseudonymize_crew
from repairflow.normalize import load_problem, write_csv_bundle
from repairflow.shop_plan import load_shop_plan
from repairflow.synthetic import synthesize

_SALT = "customer-salt-not-stored"
_PERSONNEL = "TAB-9001"


def _write(directory: Path, name: str, text: str, *, encoding: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(text.encode(encoding))


def _export(directory: Path, *, manifest: bool) -> None:
    """CP1251 semicolon extract. The night row is 22:00 then 06:00 on one date."""

    tables = {
        "jobs.csv": ("id;unit_type;priority\nJOB-1;engine;1\n"),
        "operations.csv": (
            "id;job_id;sequence;duration_min;eligible_work_center_ids;required_skills;setup_state\n"
            "JOB-1-01;JOB-1;1;30;POST-1;mechanical;engine\n"
        ),
        "work_centers.csv": ("id;code;calendar_id\nPOST-1;Пост;CAL-NIGHT\n"),
        "crews.csv": (
            f"id;code;skills;calendar_id;personnel_number\n;бригада;mechanical;CAL-NIGHT;{_PERSONNEL}\n"
        ),
        "calendars.csv": (
            "id;code;start;end\n"
            "CAL-NIGHT;ночь;2026-10-02T22:00:00;2026-10-02T06:00:00\n"
            "CAL-NIGHT;ночь;2026-10-03T22:00:00;2026-10-04T06:00:00\n"
        ),
        "setup_matrix.csv": (
            "from_state;to_state;duration_min\nidle;idle;0\nidle;engine;0\nengine;engine;0\nengine;idle;0\n"
        ),
    }
    for name, text in tables.items():
        _write(directory, name, text, encoding="cp1251")
    horizon = {
        "start": "2026-10-02T00:00:00+00:00",
        "end": "2026-10-05T00:00:00+00:00",
    }
    (directory / "horizon.json").write_text(json.dumps(horizon), encoding="utf-8")
    if manifest:
        payload = {
            "schema": "repairflow.ingest_manifest.v1",
            "encoding": "cp1251",
            "delimiter": ";",
            "source_tz": "Europe/Moscow",
            "data_provenance": "customer_data",
            "export_version": "2026-10-08",
        }
        (directory / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


def test_cp1251_night_shift_ingests_as_one_utc_window(tmp_path: Path) -> None:
    bundle = tmp_path / "export"
    _export(bundle, manifest=True)
    loaded = load_problem(bundle, crew_salt=_SALT)
    assert loaded.data_provenance == "customer_data"
    calendar = loaded.calendars[0]
    assert len(calendar.windows) == 2
    first, second = calendar.windows
    assert first.start == datetime(2026, 10, 2, 19, 0, tzinfo=UTC)
    assert first.end == datetime(2026, 10, 3, 3, 0, tzinfo=UTC)
    assert second.start == datetime(2026, 10, 3, 19, 0, tzinfo=UTC)
    assert second.end == datetime(2026, 10, 4, 3, 0, tzinfo=UTC)
    assert loaded.work_centers[0].code == "Пост"
    crew_id = loaded.crews[0].id
    assert crew_id == pseudonymize_crew(_PERSONNEL, _SALT)
    dumped = loaded.model_dump_json()
    assert _PERSONNEL not in dumped
    assert _SALT not in dumped
    for path in bundle.iterdir():
        blob = path.read_bytes()
        assert _SALT.encode() not in blob


def test_the_same_export_without_a_manifest_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "export"
    _export(bundle, manifest=False)
    with pytest.raises(ValueError, match="manifest.json"):
        load_problem(bundle, crew_salt=_SALT)


def test_utf8_bundle_without_a_manifest_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "tiny"
    write_csv_bundle(bundle, synthesize("tiny", seed=1))
    (bundle / "manifest.json").unlink()
    with pytest.raises(ValueError, match="manifest.json"):
        load_problem(bundle)


def test_duplicate_personnel_numbers_do_not_collapse(tmp_path: Path) -> None:
    bundle = tmp_path / "export"
    _export(bundle, manifest=True)
    text = (bundle / "crews.csv").read_bytes().decode("cp1251")
    (bundle / "crews.csv").write_bytes((text + text.split("\n", 1)[1]).encode("cp1251"))
    with pytest.raises(ValueError, match="collapsed"):
        load_problem(bundle, crew_salt=_SALT)


def test_unknown_timezone_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "repairflow.ingest_manifest.v1",
                "encoding": "utf-8",
                "delimiter": ",",
                "source_tz": "Not/AZone",
                "data_provenance": "customer_data",
                "export_version": "1",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="timezone"):
        load_manifest(path)


def test_cli_solve_does_not_print_the_salt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = tmp_path / "export"
    _export(bundle, manifest=True)
    out = tmp_path / "result.json"
    main(["solve", str(bundle), "--out", str(out), "--crew-salt", _SALT])
    captured = capsys.readouterr()
    assert _SALT not in captured.out
    assert _SALT not in captured.err
    assert _PERSONNEL not in captured.out
    if out.is_file():
        body = out.read_text(encoding="utf-8")
        assert _SALT not in body
        assert _PERSONNEL not in body


def test_shop_sheet_uses_the_manifest_clock(tmp_path: Path) -> None:
    problem = synthesize("tiny", seed=1)
    shop = tmp_path / "plan.csv"
    shop.write_bytes(
        (
            "заказ;операция;пост;бригада;оснастка;начало;конец;переналадка\n"
            "JOB-01;JOB-01-01;POST-U1;CREW-1;;2026-10-02T11:00:00;2026-10-02T12:00:00;0\n"
        ).encode("cp1251")
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "repairflow.ingest_manifest.v1",
                "encoding": "cp1251",
                "delimiter": ";",
                "source_tz": "Europe/Moscow",
                "data_provenance": "customer_data",
                "export_version": "1",
            }
        ),
        encoding="utf-8",
    )
    assignments, extra = load_shop_plan(shop, problem)
    assert extra == []
    assert assignments[0].start == datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    assert assignments[0].end == datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


def test_pseudonym_needs_the_same_salt_and_does_not_keep_the_number() -> None:
    code = pseudonymize_crew(_PERSONNEL, _SALT)
    assert code == pseudonymize_crew(_PERSONNEL, _SALT)
    assert code != pseudonymize_crew(_PERSONNEL, "other-salt")
    assert code.startswith("crew-")
    assert len(code) == len("crew-") + 8
    with pytest.raises(ValueError, match="salt"):
        pseudonymize_crew(_PERSONNEL, "")
