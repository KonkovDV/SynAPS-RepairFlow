"""Offline artifact identity stays distinct from the installed-file manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from repairflow.artifact_record import (
    ARTIFACT_SCHEMA,
    archive_identity_from_direct_url,
    build_artifact_record,
    hash_archive,
    installed_artifact_record,
)
from repairflow.evidence import fingerprint_payload


def test_hash_archive_is_the_wheel_bytes(tmp_path: Path) -> None:
    payload = b"wheel-bytes"
    path = tmp_path / "demo-1.0-py3-none-any.whl"
    path.write_bytes(payload)
    identity = hash_archive(path)
    assert identity["kind"] == "wheel"
    assert identity["status"] == "present"
    assert identity["sha256"] == hashlib.sha256(payload).hexdigest()
    assert identity["size_bytes"] == len(payload)


def test_hash_archive_rejects_an_unknown_suffix(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"nope")
    with pytest.raises(ValueError, match="unsupported artifact suffix"):
        hash_archive(path)


def test_sdist_and_direct_url_keep_signature_absent() -> None:
    identity = archive_identity_from_direct_url(
        {
            "url": "https://example.invalid/pkgs/demo-1.2.0.tar.gz",
            "archive_info": {"hash": "sha256=" + "ab" * 32},
        }
    )
    assert identity["kind"] == "sdist"
    assert identity["status"] == "present"
    record = build_artifact_record(
        [{"name": "Demo", "version": "1.2.0", "scope": "transitive", "archive": identity}]
    )
    assert record["schema"] == ARTIFACT_SCHEMA
    assert record["components"][0]["signature"] == {"status": "absent", "sha256": None}
    assert record["identities"]["signature"]["status"] == "absent"
    assert record["identities"]["runtime_file_manifest"]["is_wheel_hash"] is False
    assert record["identities"]["wheel_or_source"]["is_runtime_file_manifest"] is False
    assert record["lockfile_status"] == "absent"


def test_editable_and_missing_hash_are_not_present() -> None:
    editable = archive_identity_from_direct_url(
        {"url": "file:///src/repairflow", "dir_info": {"editable": True}}
    )
    assert editable["status"] == "editable"
    assert editable["sha256"] is None
    missing = archive_identity_from_direct_url({"url": "file:///x.whl", "archive_info": {}})
    assert missing["status"] == "absent"
    assert missing["sha256"] is None
    other = archive_identity_from_direct_url({"archive_info": {"hash": "md5=" + "ab" * 16}})
    assert other["status"] == "unsupported_hash"
    assert other["sha256"] is None


def test_present_without_sha256_is_rejected() -> None:
    with pytest.raises(ValueError, match="present archive requires sha256"):
        build_artifact_record(
            [
                {
                    "name": "demo",
                    "version": "1",
                    "scope": "direct",
                    "archive": {"status": "present", "sha256": None},
                }
            ]
        )


def test_record_hash_covers_the_body_without_itself() -> None:
    record = build_artifact_record(
        [
            {
                "name": "synaps",
                "version": "0",
                "scope": "direct",
                "archive": archive_identity_from_direct_url(None),
            }
        ]
    )
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    assert record["record_sha256"] == fingerprint_payload(body)
    assert record["schema"] != "repairflow.runtime_binding.v1"


def test_installed_record_does_not_claim_a_lock_or_a_signature() -> None:
    record = installed_artifact_record()
    assert record["schema"] == ARTIFACT_SCHEMA
    assert record["closure_status"] == "installed_environment_not_a_lock"
    assert record["identities"]["signature"]["is_wheel_hash"] is False
    assert record["components"]
    assert all(row["signature"]["status"] == "absent" for row in record["components"])
    scopes = {row["scope"] for row in record["components"]}
    assert "transitive" in scopes
