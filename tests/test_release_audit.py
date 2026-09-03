from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import tomllib
import zipfile

import pytest

from tools.audit_release import (
    AllowRule,
    AuditError,
    Auditor,
    Finding,
    _load_allowlist,
    _parse_artifact,
    _record_vulnerability_report,
    _safe_locator,
    _spdx,
)


ROOT = Path(__file__).resolve().parents[1]


def test_secret_matches_are_fingerprinted_without_reproduction() -> None:
    secret = "-".join(("not", "a", "real", "secret", "value", "12345"))
    key_name = "api" + "_key"
    auditor = Auditor([])
    auditor.scan_bytes(
        f'{key_name}="{secret}"\n'.encode(),
        scope="test",
        locator="fixture.txt",
    )
    assert [finding.category for finding in auditor.findings] == ["secret-assignment"]
    serialized = json.dumps([asdict(finding) for finding in auditor.findings])
    assert secret not in serialized
    assert len(auditor.findings[0].fingerprint) == 20


def test_allow_rule_requires_matching_fingerprint_and_locator() -> None:
    finding = Finding("email-address", "review", "tree", "NOTICE", "abc123")
    rule = AllowRule("notice", "email-address", "tree", "NOTICE", "abc123", "required contact")
    other = AllowRule("other", "email-address", "tree", "NOTICE", "different", "wrong contact")
    assert rule.matches(finding)
    assert not other.matches(finding)


def test_sensitive_filename_fingerprint_is_stable_across_archive_prefixes() -> None:
    auditor = Auditor([])
    auditor.scan_path_name(scope="tree", locator=".env.example")
    auditor.scan_path_name(scope="artifact:source", locator="project/.env.example")
    assert len(auditor.findings) == 2
    assert auditor.findings[0].fingerprint == auditor.findings[1].fingerprint


def test_archive_scan_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "payload")
    with pytest.raises(AuditError, match="unsafe zip path"):
        Auditor([]).scan_archive(archive_path, label="unsafe")


def test_archive_scan_records_binary_digest_without_local_path(tmp_path: Path) -> None:
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("bundle/libomega.so", b"\0binary")
    auditor = Auditor([])
    auditor.scan_archive(archive_path, label="bundle")
    assert auditor.bundled_binaries == [
        {
            "path": "bundle/libomega.so",
            "size": 7,
            "sha256": "268576d50a742ae1cd715dd6a92d811c5b04f1a66a7e13ae15f75f315a3ebe5c",
        }
    ]


def test_safe_locator_redacts_machine_user_components() -> None:
    unix_path = "/" + "/".join(("home", "private-user", "project", "file"))
    windows_path = "C:" + "\\".join(("", "Users", "private-user", "project"))
    assert _safe_locator(unix_path) == "/<user>/project/file"
    assert _safe_locator(windows_path) == r"C:\Users\<user>\project"


def test_path_scanner_ignores_slash_separated_prose() -> None:
    auditor = Auditor([])
    auditor.scan_bytes(
        b"Review machine/workspace/temp path categories.",
        scope="test",
        locator="documentation.md",
    )
    assert auditor.findings == []


def test_current_tree_audit_tolerates_pending_tracked_deletions(tmp_path: Path, monkeypatch) -> None:
    import tools.audit_release as audit_module

    (tmp_path / "kept.txt").write_text("safe", encoding="utf-8")
    monkeypatch.setattr(audit_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        audit_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=b"kept.txt\0deleted.txt\0"),
    )

    summary = Auditor([]).scan_current_tree()

    assert summary["files"] == 1
    assert summary["deletedTrackedFiles"] == 1


def test_tracked_allowlist_has_explanations() -> None:
    rules = _load_allowlist(ROOT / "audit" / "release-audit.toml")
    assert rules
    assert all(rule.rule_id and rule.rationale for rule in rules)
    assert all(rule.category != "*" and rule.scope != "" and rule.locator != "" for rule in rules)


def test_spdx_inventory_contains_exact_project_packages() -> None:
    record = _spdx("a" * 40, "2026-08-29T00:00:00Z")
    names = {package["name"].lower() for package in record["packages"]}
    assert {
        "omega-omarchy",
        "pygame-ce",
        "pillow",
        "qrcode",
        "numpy",
        "pygbag",
        "pyinstaller",
    } == names
    assert str(record["documentNamespace"]).startswith("urn:uuid:")


def test_vulnerability_report_creates_deduplicated_blockers(tmp_path: Path) -> None:
    report = tmp_path / "pip-audit.json"
    report.write_text(
        json.dumps(
            {
                "dependencies": [
                    {
                        "name": "example",
                        "version": "1.0",
                        "vulns": [{"id": "PYSEC-TEST-1"}, {"id": "PYSEC-TEST-1"}],
                    }
                ],
                "fixes": [],
            }
        )
    )
    auditor = Auditor([])
    summary = _record_vulnerability_report(auditor, report)
    assert summary["vulnerabilities"] == 1
    assert len(auditor.findings) == 1
    assert auditor.findings[0].severity == "blocker"
    assert "PYSEC-TEST-1" in auditor.findings[0].locator


def test_audit_targets_match_project_security_pins() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = {item.split("==", 1)[0].lower(): item.split("==", 1)[1] for item in project["project"]["dependencies"]}
    dev = {
        item.split("==", 1)[0].lower(): item.split("==", 1)[1]
        for item in project["project"]["optional-dependencies"]["dev"]
    }
    targets = {}
    for raw_line in (ROOT / "requirements" / "audit-targets.txt").read_text().splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            name, pinned = line.split("==", 1)
            targets[name.lower()] = pinned
    assert all(targets[name] == pinned for name, pinned in {**runtime, **dev}.items())
    assert targets["pygments"] == "2.21.0"


def test_artifact_argument_requires_explicit_safe_label() -> None:
    assert _parse_artifact("native=dist/native.tar.gz") == (
        "native",
        Path("dist/native.tar.gz"),
    )
    with pytest.raises(Exception, match="artifact must be"):
        _parse_artifact("Native=dist/native.tar.gz")
