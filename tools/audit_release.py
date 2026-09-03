#!/usr/bin/env python3
"""Produce a redacted audit of Git history, release inputs, and dependencies."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "omega-release-audit/1"
MAX_MEMBERS = 50_000
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
MAX_FINDINGS_PER_CATEGORY_AND_RESOURCE = 20
LARGE_BLOB_BYTES = 1024 * 1024
PROJECT_DISTRIBUTIONS = (
    "omega-omarchy",
    "pygame-ce",
    "pillow",
    "qrcode",
    "numpy",
    "pygbag",
    "pyinstaller",
)


@dataclass(frozen=True)
class Pattern:
    category: str
    severity: str
    expression: re.Pattern[bytes]
    binary_safe: bool = False


PATTERNS = (
    Pattern(
        "private-key",
        "blocker",
        re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
        True,
    ),
    Pattern("github-token", "blocker", re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), True),
    Pattern("aws-access-key", "blocker", re.compile(rb"\bAKIA[0-9A-Z]{16}\b"), True),
    Pattern("slack-token", "blocker", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), True),
    Pattern(
        "bearer-token",
        "blocker",
        re.compile(rb"(?i)\bBearer[ \t]+[A-Za-z0-9._~+/=-]{20,}"),
        True,
    ),
    Pattern(
        "secret-assignment",
        "blocker",
        re.compile(
            rb"(?i)\b(?:password|passwd|client_secret|api[_-]?key|access[_-]?token|auth[_-]?token)"
            rb"[ \t]{0,8}[:=][ \t]{0,8}[\"']?[A-Za-z0-9._~+/=-]{8,}"
        ),
        True,
    ),
    Pattern("cookie-header", "review", re.compile(rb"(?im)^(?:Set-)?Cookie[ \t]*:")),
    Pattern(
        "email-address",
        "review",
        re.compile(rb"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ),
    Pattern(
        "local-user-path",
        "review",
        re.compile(rb"(?:/(?:home|Users)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\)"),
    ),
    Pattern(
        "workspace-path",
        "review",
        re.compile(rb"(?<![A-Za-z0-9._-])/(?:projects|workspace)/[A-Za-z0-9._/-]+"),
    ),
    Pattern("temporary-path", "review", re.compile(rb"/tmp/[A-Za-z0-9._/-]+")),
    Pattern(
        "internal-url",
        "review",
        re.compile(
            rb"(?i)https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|[A-Z0-9.-]+\.(?:internal|local))"
            rb"(?::[0-9]+)?(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]*)?"
        ),
    ),
    Pattern(
        "repository-coordinate",
        "review",
        re.compile(rb"(?i)(?:git@[A-Z0-9._-]+:[A-Z0-9._/-]+\.git|https?://[A-Z0-9._-]+/[A-Z0-9._/-]+\.git)"),
    ),
)

SENSITIVE_PATH = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\..*)?|id_(?:rsa|ed25519)|credentials?(?:\..*)?|cookies?(?:\..*)?|"
    r"secrets?(?:\..*)?|.*\.(?:pem|key|p12|pfx|kdbx|ovpn|iso|qcow2|vdi|vmdk))$"
)
PRIVATE_DESIGN_NAMES = {"OMEGA-OMARCHY-GAME-DESIGN.md", "ONE-SHOT-DEVELOPMENT-GOAL.md"}
ARCHIVE_SUFFIXES = (".zip", ".whl", ".pyz")
BINARY_SUFFIXES = (".so", ".dll", ".dylib", ".pyd")


class AuditError(RuntimeError):
    pass


@dataclass
class Finding:
    category: str
    severity: str
    scope: str
    locator: str
    fingerprint: str
    object_id: str = ""
    line: int | None = None
    allowed: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class AllowRule:
    rule_id: str
    category: str
    scope: str
    locator: str
    fingerprint: str
    rationale: str

    def matches(self, finding: Finding) -> bool:
        return (
            fnmatch(finding.category, self.category)
            and fnmatch(finding.scope, self.scope)
            and fnmatch(finding.locator, self.locator)
            and (self.fingerprint == "*" or finding.fingerprint == self.fingerprint)
        )


def _run(command: list[str], *, cwd: Path = ROOT) -> str:
    process = subprocess.run(command, cwd=cwd, check=False, text=True, capture_output=True)
    if process.returncode:
        raise AuditError(
            f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}{process.stderr}"
        )
    return process.stdout


def _git(*arguments: str) -> str:
    return _run(["git", *arguments])


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(category: str, value: bytes) -> str:
    return hashlib.sha256(category.encode("ascii") + b"\0" + value).hexdigest()[:20]


def _safe_locator(value: str) -> str:
    value = re.sub(r"/(?:home|Users)/[^/]+", "/<user>", value)
    value = re.sub(r"[A-Za-z]:\\Users\\[^\\]+", r"C:\\Users\\<user>", value)
    return "".join(character if character.isprintable() else "?" for character in value)[:500]


def _looks_text(data: bytes) -> bool:
    sample = data[:16_384]
    if b"\0" in sample:
        return False
    if not sample:
        return True
    decoded = sample.decode("utf-8", errors="replace")
    return decoded.count("\ufffd") / max(1, len(decoded)) < 0.01


def _load_allowlist(path: Path | None) -> list[AllowRule]:
    if path is None or not path.is_file():
        return []
    record = tomllib.loads(path.read_text(encoding="utf-8"))
    if record.get("schema_version") != 1:
        raise AuditError(f"unsupported audit allowlist schema: {path}")
    rules = []
    for index, item in enumerate(record.get("allow") or [], 1):
        if not isinstance(item, dict) or not item.get("category") or not item.get("rationale"):
            raise AuditError(f"invalid allowlist rule {index}: category and rationale are required")
        rules.append(
            AllowRule(
                rule_id=str(item.get("id") or f"allow-{index}"),
                category=str(item["category"]),
                scope=str(item.get("scope") or "*"),
                locator=str(item.get("locator") or "*"),
                fingerprint=str(item.get("fingerprint") or "*"),
                rationale=str(item["rationale"]),
            )
        )
    return rules


class Auditor:
    def __init__(self, allow_rules: list[AllowRule]) -> None:
        self.allow_rules = allow_rules
        self.findings: list[Finding] = []
        self._finding_keys: set[tuple[object, ...]] = set()
        self.large_blobs: list[dict[str, object]] = []
        self.artifacts: list[dict[str, object]] = []
        self.bundled_binaries: list[dict[str, object]] = []
        self.source_maps: list[str] = []

    def add_finding(self, finding: Finding) -> None:
        finding.locator = _safe_locator(finding.locator)
        key = (
            finding.category,
            finding.scope,
            finding.locator,
            finding.fingerprint,
            finding.object_id,
            finding.line,
        )
        if key in self._finding_keys:
            return
        self._finding_keys.add(key)
        for rule in self.allow_rules:
            if rule.matches(finding):
                finding.allowed = True
                finding.rationale = f"{rule.rule_id}: {rule.rationale}"
                break
        self.findings.append(finding)

    def scan_path_name(self, *, scope: str, locator: str, object_id: str = "") -> None:
        if SENSITIVE_PATH.search(locator):
            basename = PurePosixPath(locator).name
            self.add_finding(
                Finding(
                    "sensitive-file-name",
                    "review",
                    scope,
                    locator,
                    _fingerprint("sensitive-file-name", basename.encode("utf-8", errors="replace")),
                    object_id,
                )
            )
        if PurePosixPath(locator).name in PRIVATE_DESIGN_NAMES:
            basename = PurePosixPath(locator).name
            self.add_finding(
                Finding(
                    "private-design-document",
                    "review",
                    scope,
                    locator,
                    _fingerprint("private-design-document", basename.encode("utf-8", errors="replace")),
                    object_id,
                )
            )
        if locator.endswith(".map"):
            self.source_maps.append(_safe_locator(f"{scope}:{locator}"))

    def scan_bytes(
        self,
        data: bytes,
        *,
        scope: str,
        locator: str,
        object_id: str = "",
    ) -> None:
        is_text = _looks_text(data)
        for pattern in PATTERNS:
            if not is_text and not pattern.binary_safe:
                continue
            count = 0
            for match in pattern.expression.finditer(data):
                line = data.count(b"\n", 0, match.start()) + 1 if is_text else None
                self.add_finding(
                    Finding(
                        pattern.category,
                        pattern.severity,
                        scope,
                        locator,
                        _fingerprint(pattern.category, match.group(0).lower()),
                        object_id,
                        line,
                    )
                )
                count += 1
                if count >= MAX_FINDINGS_PER_CATEGORY_AND_RESOURCE:
                    break

    def scan_current_tree(self) -> dict[str, object]:
        raw_paths = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
        ).stdout
        paths = [value.decode("utf-8", errors="replace") for value in raw_paths.split(b"\0") if value]
        total_bytes = 0
        symlinks = 0
        deleted = 0
        for relative in paths:
            self.scan_path_name(scope="tree", locator=relative)
            path = ROOT / relative
            if not os.path.lexists(path):
                # A pending deletion is ordinary in a dirty review tree. The
                # history scan still inspects the indexed/reachable bytes.
                deleted += 1
                continue
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                data = os.readlink(path).encode("utf-8", errors="replace")
                symlinks += 1
            else:
                data = path.read_bytes()
            total_bytes += len(data)
            self.scan_bytes(data, scope="tree", locator=relative)
        return {
            "files": len(paths) - deleted,
            "deletedTrackedFiles": deleted,
            "bytes": total_bytes,
            "symlinks": symlinks,
        }

    def scan_history(self) -> dict[str, object]:
        objects: dict[str, str] = {}
        for line in _git("rev-list", "--objects", "--all").splitlines():
            object_id, _, path = line.partition(" ")
            if path:
                objects.setdefault(object_id, path)
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        if process.stdin is None or process.stdout is None:
            raise AuditError("could not open git cat-file batch pipes")
        blob_count = 0
        blob_bytes = 0
        try:
            for object_id, path in sorted(objects.items()):
                process.stdin.write(object_id.encode("ascii") + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().decode("ascii", errors="replace").strip().split()
                if len(header) != 3 or header[1] == "missing":
                    raise AuditError(f"could not read reachable object {object_id[:12]}")
                size = int(header[2])
                data = process.stdout.read(size)
                if len(data) != size or process.stdout.read(1) != b"\n":
                    raise AuditError(f"truncated reachable object {object_id[:12]}")
                if header[1] != "blob":
                    continue
                blob_count += 1
                blob_bytes += size
                self.scan_path_name(scope="history", locator=path, object_id=object_id[:12])
                self.scan_bytes(data, scope="history", locator=path, object_id=object_id[:12])
                if size >= LARGE_BLOB_BYTES:
                    self.large_blobs.append(
                        {
                            "object": object_id[:12],
                            "path": _safe_locator(path),
                            "size": size,
                            "suffix": PurePosixPath(path).suffix.lower(),
                        }
                    )
        finally:
            process.stdin.close()
            process.stdout.close()
            process.wait(timeout=10)
        self.large_blobs.sort(key=lambda item: (-int(item["size"]), str(item["path"])))
        return {"uniqueBlobs": blob_count, "blobBytes": blob_bytes}

    def scan_archive(self, path: Path, *, label: str) -> None:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                self._scan_zip(archive, label=label, prefix="", depth=0)
        elif tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*") as archive:
                self._scan_tar(archive, label=label)
        else:
            data = path.read_bytes()
            self.scan_bytes(data, scope=f"artifact:{label}", locator=path.name)
        self.artifacts.append(
            {
                "label": label,
                "kind": "file",
                "name": _safe_locator(path.name),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )

    def scan_directory(self, path: Path, *, label: str) -> None:
        digest = hashlib.sha256()
        count = 0
        total = 0
        for item in sorted(path.rglob("*")):
            if not item.is_file() or item.is_symlink():
                continue
            relative = item.relative_to(path).as_posix()
            data = item.read_bytes()
            count += 1
            total += len(data)
            digest.update(len(relative.encode()).to_bytes(4, "big"))
            digest.update(relative.encode())
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
            locator = f"{label}/{relative}"
            self.scan_path_name(scope=f"artifact:{label}", locator=locator)
            self.scan_bytes(data, scope=f"artifact:{label}", locator=locator)
            self._record_binary(locator, data)
        self.artifacts.append(
            {
                "label": label,
                "kind": "directory",
                "name": _safe_locator(path.name),
                "files": count,
                "size": total,
                "sha256": digest.hexdigest(),
            }
        )

    def _record_binary(self, locator: str, data: bytes) -> None:
        lowered = locator.lower()
        if any(lowered.endswith(suffix) or f"{suffix}." in lowered for suffix in BINARY_SUFFIXES):
            self.bundled_binaries.append(
                {"path": _safe_locator(locator), "size": len(data), "sha256": _sha256_bytes(data)}
            )

    def _scan_zip(self, archive: zipfile.ZipFile, *, label: str, prefix: str, depth: int) -> None:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS:
            raise AuditError(f"archive has too many members: {label}")
        expanded = 0
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise AuditError(f"unsafe zip path in {label}: {_safe_locator(member.filename)}")
            if member.is_dir():
                continue
            expanded += member.file_size
            if expanded > MAX_EXPANDED_BYTES:
                raise AuditError(f"archive expands beyond limit: {label}")
            data = archive.read(member)
            locator = f"{prefix}{member.filename}"
            self.scan_path_name(scope=f"artifact:{label}", locator=locator)
            self.scan_bytes(data, scope=f"artifact:{label}", locator=locator)
            self._record_binary(locator, data)
            if depth < 1 and member.filename.lower().endswith(ARCHIVE_SUFFIXES):
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:
                        self._scan_zip(
                            nested,
                            label=label,
                            prefix=f"{locator}!/",
                            depth=depth + 1,
                        )
                except zipfile.BadZipFile:
                    pass

    def _scan_tar(self, archive: tarfile.TarFile, *, label: str) -> None:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise AuditError(f"archive has too many members: {label}")
        expanded = 0
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise AuditError(f"unsafe tar path in {label}: {_safe_locator(member.name)}")
            self.scan_path_name(scope=f"artifact:{label}", locator=member.name)
            if member.issym() or member.islnk():
                self.scan_bytes(
                    member.linkname.encode("utf-8", errors="replace"),
                    scope=f"artifact:{label}",
                    locator=f"{member.name} -> link",
                )
                continue
            if not member.isfile():
                continue
            expanded += member.size
            if expanded > MAX_EXPANDED_BYTES:
                raise AuditError(f"archive expands beyond limit: {label}")
            source = archive.extractfile(member)
            if source is None:
                raise AuditError(f"could not read tar member: {_safe_locator(member.name)}")
            data = source.read()
            self.scan_bytes(data, scope=f"artifact:{label}", locator=member.name)
            self._record_binary(member.name, data)
            if member.name.lower().endswith(ARCHIVE_SUFFIXES):
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:
                        self._scan_zip(
                            nested,
                            label=label,
                            prefix=f"{member.name}!/",
                            depth=1,
                        )
                except zipfile.BadZipFile:
                    pass


def _refs() -> list[dict[str, str]]:
    output = _git(
        "for-each-ref",
        "--format=%(refname)%00%(objecttype)%00%(objectname)",
        "refs/heads",
        "refs/remotes",
        "refs/tags",
        "refs/notes",
    )
    values = []
    for line in output.splitlines():
        name, object_type, object_id = line.split("\0")
        values.append({"name": _safe_locator(name), "type": object_type, "object": object_id})
    return values


def _commit_audit(auditor: Auditor) -> tuple[list[dict[str, object]], dict[str, object]]:
    identities: dict[str, dict[str, object]] = {}
    commits = _git("rev-list", "--all").splitlines()
    for commit in commits:
        record = _git(
            "show",
            "-s",
            "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B",
            commit,
        ).rstrip("\n").split("\0", 5)
        if len(record) != 6:
            raise AuditError(f"could not parse commit metadata: {commit[:12]}")
        _, author_name, author_email, committer_name, committer_email, message = record
        for role, name, email in (
            ("author", author_name, author_email),
            ("committer", committer_name, committer_email),
        ):
            normalized = f"{name.strip()}\0{email.strip().lower()}".encode("utf-8", errors="replace")
            identity_id = hashlib.sha256(normalized).hexdigest()[:20]
            domain = email.rpartition("@")[2].lower() if "@" in email else "invalid"
            item = identities.setdefault(
                identity_id,
                {
                    "fingerprint": identity_id,
                    "domain": domain,
                    "noreply": domain == "users.noreply.github.com",
                    "roles": Counter(),
                    "commits": set(),
                },
            )
            item["roles"][role] += 1  # type: ignore[index]
            item["commits"].add(commit[:12])  # type: ignore[union-attr]
            if domain != "users.noreply.github.com":
                auditor.add_finding(
                    Finding(
                        "commit-identity",
                        "review",
                        "history-metadata",
                        f"commit:{commit[:12]}:{role}",
                        identity_id,
                    )
                )
        auditor.scan_bytes(
            message.encode("utf-8", errors="replace"),
            scope="commit-message",
            locator=f"commit:{commit[:12]}",
            object_id=commit[:12],
        )
    summary = []
    for item in identities.values():
        summary.append(
            {
                "fingerprint": item["fingerprint"],
                "domain": item["domain"],
                "noreply": item["noreply"],
                "roles": dict(item["roles"]),
                "commitCount": len(item["commits"]),
            }
        )
    summary.sort(key=lambda item: str(item["fingerprint"]))
    return summary, {"commits": len(commits), "identities": len(summary)}


def _spdx(head: str, created: str) -> dict[str, object]:
    packages = []
    for name in PROJECT_DISTRIBUTIONS:
        try:
            package = distribution(name)
        except PackageNotFoundError as exc:
            raise AuditError(f"SBOM dependency is not installed: {name}") from exc
        canonical = package.metadata.get("Name") or name
        declared = package.metadata.get("License-Expression") or package.metadata.get("License") or "NOASSERTION"
        declared = str(declared).splitlines()[0] or "NOASSERTION"
        spdx_id = "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", canonical)
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": canonical,
                "versionInfo": package.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": declared,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{canonical.lower().replace('_', '-')}@{package.version}",
                    }
                ],
            }
        )
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, f"omega-omarchy:{head}:{SCHEMA}")
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": package["SPDXID"],
        }
        for package in packages
    ]
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"omega-omarchy-{head[:12]}",
        "documentNamespace": f"urn:uuid:{document_id}",
        "creationInfo": {"created": created, "creators": ["Tool: omega-release-audit/1"]},
        "packages": packages,
        "relationships": relationships,
    }


def _pinned_requirement_version(path: Path, distribution_name: str) -> str:
    normalized = distribution_name.lower().replace("_", "-")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, pinned = line.split("==", 1)
        if name.lower().replace("_", "-") == normalized:
            return pinned
    raise AuditError(f"missing exact {distribution_name} pin in {path}")


def _build_distribution_inputs(destination: Path) -> list[tuple[str, Path]]:
    destination.mkdir(parents=True, exist_ok=True)
    source = destination / "omega-omarchy-source.tar.gz"
    _run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            "--prefix=omega-omarchy-source/",
            f"--output={source}",
            "HEAD",
        ]
    )
    wheel_dir = destination / "wheel"
    wheel_dir.mkdir()
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(ROOT),
        ]
    )
    wheels = sorted(wheel_dir.glob("omega_omarchy-*.whl"))
    if len(wheels) != 1:
        raise AuditError(f"expected one wheel, found: {[path.name for path in wheels]}")
    return [("source-archive", source), ("wheel", wheels[0])]


def _markdown(report: dict[str, object]) -> str:
    findings = report["findings"]
    unallowed = [item for item in findings if not item["allowed"]]  # type: ignore[index]
    lines = [
        "# Sanitized release audit",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Tool versions: audit `{report['toolVersions']['omegaReleaseAudit']}`, "  # type: ignore[index]
        f"Python `{report['toolVersions']['python']}`, "  # type: ignore[index]
        f"{report['toolVersions']['git']}`, pip-audit `{report['toolVersions']['pipAudit']}`",  # type: ignore[index]
        f"- Commit: `{report['head']}`",
        f"- Commit time: `{report['commitTime']}`",
        f"- Dirty worktree: `{str(report['dirty']).lower()}`",
        f"- Automated verdict: **{'REVIEW REQUIRED' if unallowed else 'PASS'}**",
        f"- Findings: {len(findings)} total; {len(unallowed)} unallowlisted",
        "",
        "Matched values are never written to this report. Fingerprints identify",
        "repeat findings without reproducing credentials, personal data, or local paths.",
        "",
        "## Public-ref inventory",
        "",
        "| Ref | Type | Object |",
        "|---|---|---|",
    ]
    for ref in report["refs"]:  # type: ignore[assignment]
        lines.append(f"| `{ref['name']}` | {ref['type']} | `{ref['object'][:12]}` |")
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "| Severity | Category | Scope | Locator | Line | Fingerprint | Disposition |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    for finding in findings:  # type: ignore[assignment]
        locator = str(finding["locator"]).replace("|", "\\|")
        line = finding["line"] or ""
        disposition = finding["rationale"] if finding["allowed"] else "REVIEW"
        disposition = str(disposition).replace("|", "\\|")
        lines.append(
            f"| {finding['severity']} | {finding['category']} | {finding['scope']} | "
            f"`{locator}` | {line} | `{finding['fingerprint']}` | {disposition} |"
        )
    lines.extend(
        [
            "",
            "## Scope summary",
            "",
            f"- Reachable commits: {report['history']['commits']}",  # type: ignore[index]
            f"- Unique reachable blobs: {report['history']['uniqueBlobs']}",  # type: ignore[index]
            f"- Current tracked files: {report['tree']['files']}",  # type: ignore[index]
            f"- Large reachable blobs (>= 1 MiB): {len(report['largeBlobs'])}",  # type: ignore[arg-type]
            f"- Source maps: {len(report['sourceMaps'])}",  # type: ignore[arg-type]
            f"- Bundled native-library records: {len(report['bundledBinaries'])}",  # type: ignore[arg-type]
            "",
            "## Required manual/external completion",
            "",
            "This automated record does not inspect GitHub issues, discussions, deleted",
            "or hidden remote refs, organization audit logs, Actions logs, release objects,",
            "credential-provider state, legal permission, or vulnerability databases unless",
            "a separate report is supplied. A second reviewer must inspect the configuration,",
            "sample history and binaries, review every allowlist rationale, and sign the exact",
            "candidate record before G7 can pass.",
            "",
        ]
    )
    return "\n".join(lines)


def _record_vulnerability_report(auditor: Auditor, path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dependencies = payload.get("dependencies") if isinstance(payload, dict) else payload
    if not isinstance(dependencies, list):
        raise AuditError("vulnerability report is not recognized pip-audit JSON")
    vulnerability_keys: set[tuple[str, str, str]] = set()
    for item in dependencies:
        if not isinstance(item, dict):
            continue
        package_name = str(item.get("name") or "unknown")
        package_version = str(item.get("version") or "unknown")
        for vulnerability in item.get("vulns") or []:
            if not isinstance(vulnerability, dict):
                continue
            vulnerability_id = str(vulnerability.get("id") or "unknown")
            vulnerability_keys.add((package_name, package_version, vulnerability_id))
    for package_name, package_version, vulnerability_id in sorted(vulnerability_keys):
        auditor.add_finding(
            Finding(
                "known-vulnerability",
                "blocker",
                "dependency-audit",
                f"package:{package_name}@{package_version}:{vulnerability_id}",
                _fingerprint("known-vulnerability", vulnerability_id.encode("utf-8")),
            )
        )
    return {
        "provided": True,
        "dependencies": len(dependencies),
        "vulnerabilities": len(vulnerability_keys),
        "sha256": _sha256_file(path),
    }


def audit(
    output: Path,
    *,
    artifacts: list[tuple[str, Path]],
    allowlist: Path | None,
    build_distributions: bool,
    require_clean: bool,
    vulnerability_report: Path | None,
) -> tuple[dict[str, object], Path, Path]:
    dirty = bool(_git("status", "--porcelain"))
    if require_clean and dirty:
        raise AuditError("release audit requires a clean worktree")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rules = _load_allowlist(allowlist)
    auditor = Auditor(rules)
    head = _git("rev-parse", "HEAD").strip()
    commit_time = _git("show", "-s", "--format=%cI", "HEAD").strip()
    refs = _refs()
    for ref in refs:
        auditor.scan_bytes(
            ref["name"].encode("utf-8", errors="replace"),
            scope="ref-name",
            locator=ref["name"],
        )
    tree_summary = auditor.scan_current_tree()
    history_summary = auditor.scan_history()
    identities, commit_summary = _commit_audit(auditor)
    history_summary.update(commit_summary)

    sbom = _spdx(head, commit_time)
    sbom_path = output / "sbom.spdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scan_targets = list(artifacts)
    scan_targets.append(("sbom", sbom_path))
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if build_distributions:
        temporary = tempfile.TemporaryDirectory(prefix="omega-release-audit-")
        scan_targets.extend(_build_distribution_inputs(Path(temporary.name)))
    if vulnerability_report is not None:
        scan_targets.append(("vulnerability-report", vulnerability_report))
    try:
        for label, path in scan_targets:
            resolved = path.resolve()
            if resolved.is_dir():
                auditor.scan_directory(resolved, label=label)
            elif resolved.is_file():
                auditor.scan_archive(resolved, label=label)
            else:
                raise AuditError(f"audit artifact does not exist: {label}={path}")
    finally:
        if temporary is not None:
            temporary.cleanup()

    vulnerability_summary: dict[str, object] = {"provided": False}
    if vulnerability_report is not None:
        vulnerability_summary = _record_vulnerability_report(auditor, vulnerability_report)

    findings = sorted(
        (asdict(item) for item in auditor.findings),
        key=lambda item: (
            item["allowed"],
            item["severity"],
            item["category"],
            item["scope"],
            item["locator"],
            item["fingerprint"],
        ),
    )
    report: dict[str, object] = {
        "schema": SCHEMA,
        "toolVersions": {
            "omegaReleaseAudit": SCHEMA.rsplit("/", 1)[-1],
            "python": platform.python_version(),
            "git": _git("--version").strip(),
            "pipAudit": _pinned_requirement_version(
                ROOT / "requirements" / "audit-tool.txt", "pip-audit"
            ),
        },
        "patternInventory": [
            {
                "category": pattern.category,
                "severity": pattern.severity,
                "binarySafe": pattern.binary_safe,
            }
            for pattern in PATTERNS
        ]
        + [
            {"category": "sensitive-file-name", "severity": "review", "binarySafe": True},
            {"category": "private-design-document", "severity": "review", "binarySafe": True},
        ],
        "head": head,
        "commitTime": commit_time,
        "dirty": dirty,
        "refs": refs,
        "tree": tree_summary,
        "history": history_summary,
        "identities": identities,
        "findings": findings,
        "largeBlobs": auditor.large_blobs,
        "artifacts": auditor.artifacts,
        "bundledBinaries": sorted(auditor.bundled_binaries, key=lambda item: str(item["path"])),
        "sourceMaps": sorted(set(auditor.source_maps)),
        "allowlist": [asdict(rule) for rule in rules],
        "vulnerabilityAudit": vulnerability_summary,
        "secondReviewer": {"status": "required", "identity": None, "date": None},
        "limitations": [
            "Only refs reachable in this clone were scanned.",
            "Remote issues, discussions, Actions logs, releases, hidden refs, "
            "and credential state require separate review.",
            "Automated matching cannot establish legal rights or replace a second reviewer.",
        ],
    }
    json_path = output / "release-audit.json"
    markdown_path = output / "release-audit.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return report, json_path, markdown_path


def _parse_artifact(value: str) -> tuple[str, Path]:
    label, separator, raw_path = value.partition("=")
    if not separator or not label or not raw_path or not re.fullmatch(r"[a-z0-9-]+", label):
        raise argparse.ArgumentTypeError("artifact must be LABEL=PATH with a lowercase label")
    return label, Path(raw_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "audit-local")
    parser.add_argument("--artifact", action="append", default=[], type=_parse_artifact)
    parser.add_argument("--allowlist", type=Path, default=ROOT / "audit" / "release-audit.toml")
    parser.add_argument("--build-distributions", action="store_true")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--vulnerability-report", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        report, json_path, markdown_path = audit(
            args.output,
            artifacts=args.artifact,
            allowlist=args.allowlist,
            build_distributions=args.build_distributions,
            require_clean=args.require_clean,
            vulnerability_report=args.vulnerability_report,
        )
    except (AuditError, OSError, ValueError, json.JSONDecodeError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"AUDIT_FAILED {exc}", file=sys.stderr)
        return 2
    unallowed = [item for item in report["findings"] if not item["allowed"]]  # type: ignore[index]
    report_digest = _sha256_file(json_path)
    print(
        f"AUDIT_{'REVIEW' if unallowed else 'OK'} commit={report['head']} "
        f"findings={len(report['findings'])} unallowlisted={len(unallowed)} "
        f"report_sha256={report_digest}"
    )
    print(f"AUDIT_JSON={json_path}")
    print(f"AUDIT_MARKDOWN={markdown_path}")
    if unallowed and not args.report_only:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
