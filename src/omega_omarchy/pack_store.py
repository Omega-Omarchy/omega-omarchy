"""Explicit, game-owned installation lifecycle for sealed content packs."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from .canonical import sha256_json
from .content_pack import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_MANIFEST_BYTES,
    MAX_PACK_BYTES,
    PACK_ID_RE,
    SHA256_RE,
    VERSION_RE,
    ContentPack,
    PackValidationError,
    validate_pack,
)
from .save import user_data_dir

STORE_SCHEMA_VERSION = "1.0.0"
MAX_STATE_BYTES = 512 * 1024
MAX_INSTALLED_PACKS = 256
MAX_ARCHIVE_MEMBERS = MAX_FILES + 64
MAX_ARCHIVE_BYTES = MAX_PACK_BYTES + MAX_MANIFEST_BYTES + 1024 * 1024


class PackStoreError(PackValidationError):
    """An installed-pack registry or lifecycle operation failed closed."""


class PackConsentRequired(PackStoreError):
    """Installation was requested without explicit review acceptance."""


@dataclass(frozen=True)
class PackReview:
    pack_id: str
    version: str
    schema_version: str
    game_schema_version: str
    generator_version: str
    license: str
    authors: tuple[str, ...]
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    content_digest: str
    source_label: str
    declared_source: str | None
    homepage: str | None
    files: int
    bytes: int
    entries: int

    @classmethod
    def from_pack(cls, pack: ContentPack, source_label: str) -> PackReview:
        return cls(
            pack_id=pack.pack_id,
            version=pack.version,
            schema_version=pack.schema_version,
            game_schema_version=pack.game_schema_version,
            generator_version=pack.generator_version,
            license=pack.license,
            authors=pack.authors,
            capabilities=pack.capabilities,
            dependencies=pack.dependencies,
            content_digest=pack.content_digest,
            source_label=source_label,
            declared_source=pack.source,
            homepage=pack.homepage,
            files=len(pack.files),
            bytes=sum(int(item["bytes"]) for item in pack.files),
            entries=len(pack.entries),
        )


@dataclass(frozen=True)
class InstalledPack:
    pack_id: str
    version: str
    content_digest: str
    relative_path: str
    source_label: str
    enabled: bool = False

    def identity(self) -> dict[str, str]:
        return {"id": self.pack_id, "version": self.version, "digest": self.content_digest}


def _safe_source_label(source: Path) -> str:
    label = re.sub(r"[^A-Za-z0-9._+-]", "_", source.name)[:96]
    return label or "content-pack"


def _safe_archive_path(raw: str) -> PurePosixPath:
    if not raw or "\\" in raw or "\x00" in raw:
        raise PackStoreError("archive contains a non-canonical path")
    path = PurePosixPath(raw.rstrip("/"))
    if (
        path.as_posix() != raw.rstrip("/")
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PackStoreError(f"archive contains unsafe path: {raw}")
    return path


def _archive_root(files: list[PurePosixPath]) -> tuple[str, ...]:
    manifests = [path for path in files if path.name == "pack.toml"]
    if len(manifests) != 1:
        raise PackStoreError("archive must contain exactly one pack.toml")
    manifest = manifests[0]
    if len(manifest.parts) == 1:
        return ()
    if len(manifest.parts) == 2:
        return (manifest.parts[0],)
    raise PackStoreError("archive pack.toml must be at the root or inside one top-level directory")


def _extract_zip(source: Path, destination: Path) -> Path:
    if source.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PackStoreError("archive exceeds compressed size limit")
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackStoreError(f"invalid ZIP content pack: {exc}") from exc
    with archive:
        members = archive.infolist()
        if not members or len(members) > MAX_ARCHIVE_MEMBERS:
            raise PackStoreError("archive member count exceeds limit")
        paths: list[PurePosixPath] = []
        seen: set[str] = set()
        total = 0
        for info in members:
            path = _safe_archive_path(info.filename)
            key = path.as_posix().casefold()
            if key in seen:
                raise PackStoreError(f"archive contains duplicate portable path: {path.as_posix()}")
            seen.add(key)
            mode = info.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind == stat.S_IFLNK or kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise PackStoreError(f"archive contains link or special file: {path.as_posix()}")
            if info.flag_bits & 0x1:
                raise PackStoreError("encrypted archives are unsupported")
            if info.is_dir():
                continue
            limit = MAX_MANIFEST_BYTES if path.name == "pack.toml" else MAX_FILE_BYTES
            if info.file_size > limit:
                raise PackStoreError(f"archive member exceeds size limit: {path.as_posix()}")
            total += info.file_size
            if total > MAX_PACK_BYTES + MAX_MANIFEST_BYTES:
                raise PackStoreError("archive exceeds expanded size limit")
            paths.append(path)
        prefix = _archive_root(paths)
        portable_files = {path.as_posix().casefold() for path in paths}
        for path in paths:
            for depth in range(1, len(path.parts)):
                parent = PurePosixPath(*path.parts[:depth]).as_posix().casefold()
                if parent in portable_files:
                    raise PackStoreError(
                        f"archive path is both a file and a directory: {path.as_posix()}"
                    )
        root = destination / "pack"
        root.mkdir(parents=True)
        for info in members:
            if info.is_dir():
                continue
            path = _safe_archive_path(info.filename)
            if prefix:
                if path.parts[:1] != prefix or len(path.parts) == 1:
                    raise PackStoreError("archive contains files outside its pack directory")
                relative = PurePosixPath(*path.parts[1:])
            else:
                relative = path
            target = root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            limit = MAX_MANIFEST_BYTES if relative.name == "pack.toml" else MAX_FILE_BYTES
            try:
                with archive.open(info) as incoming:
                    payload = incoming.read(limit + 1)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise PackStoreError(f"could not read archive member {path.as_posix()}: {exc}") from exc
            if len(payload) > limit:
                raise PackStoreError(f"archive member exceeds size limit: {path.as_posix()}")
            target.write_bytes(payload)
        return root


@contextmanager
def _prepared_source(source: Path) -> Iterator[tuple[ContentPack, str]]:
    source = Path(source)
    label = _safe_source_label(source)
    if source.is_symlink():
        raise PackStoreError("content-pack source may not be a symlink")
    if source.is_dir():
        yield validate_pack(source), label
        return
    if not source.is_file():
        raise PackStoreError("content-pack source must be a directory or ZIP archive")
    if source.suffix.lower() != ".zip":
        raise PackStoreError("content-pack archives must use the .zip format")
    with tempfile.TemporaryDirectory(prefix="omega-pack-review-") as temporary:
        root = _extract_zip(source, Path(temporary))
        yield validate_pack(root), label


def _state_digest(record: dict[str, Any]) -> str:
    return sha256_json({key: value for key, value in record.items() if key != "stateDigest"})


def _empty_state() -> dict[str, Any]:
    record: dict[str, Any] = {
        "schemaVersion": STORE_SCHEMA_VERSION,
        "installed": [],
        "enabled": [],
    }
    return {**record, "stateDigest": _state_digest(record)}


def _relative_install_path(pack: ContentPack) -> str:
    digest = pack.content_digest.removeprefix("sha256:")
    return f"installed/{pack.pack_id}/{pack.version}--{digest}"


def _validate_identity(value: Any, *, path_required: bool = False) -> dict[str, str]:
    required = {"id", "version", "digest"}
    if path_required:
        required |= {"path", "source"}
    if not isinstance(value, dict) or set(value) != required:
        raise PackStoreError("content-pack registry entry has an invalid shape")
    if not isinstance(value["id"], str) or not PACK_ID_RE.fullmatch(value["id"]):
        raise PackStoreError("content-pack registry contains an invalid id")
    if not isinstance(value["version"], str) or not VERSION_RE.fullmatch(value["version"]):
        raise PackStoreError("content-pack registry contains an invalid version")
    if not isinstance(value["digest"], str) or not SHA256_RE.fullmatch(value["digest"]):
        raise PackStoreError("content-pack registry contains an invalid digest")
    if path_required:
        path = value["path"]
        if not isinstance(path, str):
            raise PackStoreError("content-pack registry contains an invalid path")
        relative = PurePosixPath(path)
        if (
            relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or not relative.parts
            or relative.parts[0] != "installed"
        ):
            raise PackStoreError("content-pack registry contains an unsafe path")
        if (
            not isinstance(value["source"], str)
            or not re.fullmatch(r"[A-Za-z0-9._+-]{1,96}", value["source"])
        ):
            raise PackStoreError("content-pack registry contains an invalid source label")
    return value


class PackStore:
    """Manage explicitly installed packs without mutating the game installation."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else user_data_dir() / "content-packs"
        self.state_path = self.root / "state.json"
        self.lock_path = self.root / ".lock"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if self.root.exists() and self.root.is_symlink():
            raise PackStoreError("content-pack storage root may not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists() and self.lock_path.is_symlink():
            raise PackStoreError("content-pack registry lock may not be a symlink")
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return _empty_state()
        if self.state_path.is_symlink() or not self.state_path.is_file():
            raise PackStoreError("content-pack registry must be a regular file")
        if self.state_path.stat().st_size > MAX_STATE_BYTES:
            raise PackStoreError("content-pack registry exceeds size limit")

        def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise PackStoreError("content-pack registry contains a duplicate JSON key")
                value[key] = item
            return value

        try:
            state = json.loads(
                self.state_path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackStoreError(f"content-pack registry is unreadable: {exc}") from exc
        if not isinstance(state, dict) or set(state) != {"schemaVersion", "installed", "enabled", "stateDigest"}:
            raise PackStoreError("content-pack registry has an invalid shape")
        if state["schemaVersion"] != STORE_SCHEMA_VERSION:
            raise PackStoreError(f"unsupported content-pack registry schema {state['schemaVersion']}")
        if state["stateDigest"] != _state_digest(state):
            raise PackStoreError("content-pack registry digest mismatch")
        installed = state["installed"]
        enabled = state["enabled"]
        if (
            not isinstance(installed, list)
            or not isinstance(enabled, list)
            or len(installed) > MAX_INSTALLED_PACKS
            or len(enabled) > MAX_INSTALLED_PACKS
        ):
            raise PackStoreError("content-pack registry exceeds entry limit")
        installed_keys: set[tuple[str, str, str]] = set()
        versions: dict[tuple[str, str], str] = {}
        for item in installed:
            entry = _validate_identity(item, path_required=True)
            key = (entry["id"], entry["version"], entry["digest"])
            if key in installed_keys:
                raise PackStoreError("content-pack registry contains duplicate installations")
            installed_keys.add(key)
            version_key = (entry["id"], entry["version"])
            if version_key in versions and versions[version_key] != entry["digest"]:
                raise PackStoreError("content-pack registry contains a version collision")
            versions[version_key] = entry["digest"]
        enabled_ids: set[str] = set()
        for item in enabled:
            entry = _validate_identity(item)
            key = (entry["id"], entry["version"], entry["digest"])
            if key not in installed_keys:
                raise PackStoreError("enabled content pack is not installed")
            if entry["id"] in enabled_ids:
                raise PackStoreError("multiple versions of one content pack are enabled")
            enabled_ids.add(entry["id"])
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        body = {key: value for key, value in state.items() if key != "stateDigest"}
        record = {**body, "stateDigest": _state_digest(body)}
        descriptor, temporary_name = tempfile.mkstemp(prefix=".state-", dir=self.root)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(record, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(self.state_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def review(self, source: Path) -> PackReview:
        with _prepared_source(source) as (pack, label):
            return PackReview.from_pack(pack, label)

    def install(
        self,
        source: Path,
        *,
        accept: bool = False,
        accepted_digest: str | None = None,
    ) -> InstalledPack:
        if not accept or accepted_digest is None:
            raise PackConsentRequired(
                "installation requires explicit --accept bound to reviewed pack metadata"
            )
        with _prepared_source(source) as (source_pack, label):
            if source_pack.content_digest != accepted_digest:
                raise PackStoreError("content pack changed after review; review it again before installing")
            relative = _relative_install_path(source_pack)
            with self._locked():
                state = self._read_state()
                for item in state["installed"]:
                    if item["id"] == source_pack.pack_id and item["version"] == source_pack.version:
                        if item["digest"] != source_pack.content_digest:
                            raise PackStoreError(
                                f"pack {source_pack.pack_id} {source_pack.version} is already installed "
                                "with a different digest"
                            )
                        pack = self._validated_entry(item)
                        return self._installed_record(item, state, pack)
                staging = Path(tempfile.mkdtemp(prefix=".install-", dir=self.root))
                destination = self.root.joinpath(*PurePosixPath(relative).parts)
                created_destination = False
                try:
                    (staging / "pack.toml").write_bytes((source_pack.root / "pack.toml").read_bytes())
                    for declared in source_pack.files:
                        pack_path = PurePosixPath(str(declared["path"]))
                        target = staging.joinpath(*pack_path.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(source_pack.root.joinpath(*pack_path.parts).read_bytes())
                    staged_pack = validate_pack(staging)
                    if staged_pack.identity() != source_pack.identity():
                        raise PackStoreError("content pack changed while it was being installed")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        existing = validate_pack(destination)
                        if existing.identity() != source_pack.identity():
                            raise PackStoreError("installation destination contains different content")
                        shutil.rmtree(staging)
                    else:
                        staging.replace(destination)
                        created_destination = True
                    entry = {
                        "id": source_pack.pack_id,
                        "version": source_pack.version,
                        "digest": source_pack.content_digest,
                        "path": relative,
                        "source": label,
                    }
                    state["installed"].append(entry)
                    state["installed"].sort(key=lambda item: (item["id"], item["version"], item["digest"]))
                    self._write_state(state)
                except Exception:
                    if staging.exists():
                        shutil.rmtree(staging)
                    if created_destination and destination.exists():
                        shutil.rmtree(destination)
                    raise
                return self._installed_record(entry, state, source_pack)

    def _validated_entry(self, entry: dict[str, str]) -> ContentPack:
        root = self.root.joinpath(*PurePosixPath(entry["path"]).parts)
        store_root = self.root.resolve()
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise PackStoreError(f"installed pack {entry['id']} is missing: {exc}") from exc
        if not resolved.is_relative_to(store_root):
            raise PackStoreError(f"installed pack {entry['id']} escapes game-owned storage")
        pack = validate_pack(root)
        if pack.identity() != {"id": entry["id"], "version": entry["version"], "digest": entry["digest"]}:
            raise PackStoreError(f"installed pack identity mismatch: {entry['id']}")
        return pack

    @staticmethod
    def _enabled_keys(state: dict[str, Any]) -> set[tuple[str, str, str]]:
        return {(item["id"], item["version"], item["digest"]) for item in state["enabled"]}

    def _installed_record(
        self, entry: dict[str, str], state: dict[str, Any], pack: ContentPack | None = None
    ) -> InstalledPack:
        if pack is not None and pack.identity() != {
            "id": entry["id"],
            "version": entry["version"],
            "digest": entry["digest"],
        }:
            raise PackStoreError("installed pack record does not match validated content")
        key = (entry["id"], entry["version"], entry["digest"])
        return InstalledPack(
            pack_id=entry["id"],
            version=entry["version"],
            content_digest=entry["digest"],
            relative_path=entry["path"],
            source_label=entry["source"],
            enabled=key in self._enabled_keys(state),
        )

    def list(self) -> tuple[InstalledPack, ...]:
        with self._locked():
            state = self._read_state()
            return tuple(
                self._installed_record(item, state, self._validated_entry(item))
                for item in state["installed"]
            )

    def _select(self, state: dict[str, Any], pack_id: str, version: str | None) -> dict[str, str]:
        matches = [
            item
            for item in state["installed"]
            if item["id"] == pack_id and (version is None or item["version"] == version)
        ]
        if not matches:
            suffix = f" {version}" if version else ""
            raise PackStoreError(f"content pack is not installed: {pack_id}{suffix}")
        if len(matches) > 1:
            versions = ",".join(sorted(item["version"] for item in matches))
            raise PackStoreError(f"multiple versions installed for {pack_id}; choose one of: {versions}")
        return matches[0]

    def _validate_enabled(self, state: dict[str, Any]) -> None:
        from .content import load_content

        paths: list[Path] = []
        installed = {
            (item["id"], item["version"], item["digest"]): item for item in state["installed"]
        }
        for identity in state["enabled"]:
            entry = installed[(identity["id"], identity["version"], identity["digest"])]
            self._validated_entry(entry)
            paths.append(self.root.joinpath(*PurePosixPath(entry["path"]).parts))
        load_content(paths)

    def enable(self, pack_id: str, version: str | None = None) -> InstalledPack:
        with self._locked():
            state = self._read_state()
            entry = self._select(state, pack_id, version)
            identity = {"id": entry["id"], "version": entry["version"], "digest": entry["digest"]}
            state["enabled"] = [item for item in state["enabled"] if item["id"] != pack_id]
            state["enabled"].append(identity)
            state["enabled"].sort(key=lambda item: (item["id"], item["version"], item["digest"]))
            self._validate_enabled(state)
            self._write_state(state)
            return self._installed_record(entry, state)

    def disable(self, pack_id: str, version: str | None = None) -> InstalledPack:
        with self._locked():
            state = self._read_state()
            entry = self._select(state, pack_id, version)
            key = (entry["id"], entry["version"], entry["digest"])
            state["enabled"] = [
                item for item in state["enabled"] if (item["id"], item["version"], item["digest"]) != key
            ]
            self._validate_enabled(state)
            self._write_state(state)
            return self._installed_record(entry, state)

    def remove(self, pack_id: str, version: str | None = None) -> InstalledPack:
        with self._locked():
            state = self._read_state()
            entry = self._select(state, pack_id, version)
            record = self._installed_record(entry, state, self._validated_entry(entry))
            if record.enabled:
                raise PackStoreError(f"disable {pack_id} before removing it")
            root = self.root.joinpath(*PurePosixPath(entry["path"]).parts)
            tombstone = Path(tempfile.mkdtemp(prefix=".remove-", dir=self.root))
            tombstone.rmdir()
            root.replace(tombstone)
            state["installed"] = [item for item in state["installed"] if item is not entry]
            try:
                self._write_state(state)
            except Exception:
                tombstone.replace(root)
                raise
            try:
                shutil.rmtree(tombstone)
            except OSError as exc:
                raise PackStoreError(
                    f"removed {pack_id} from the registry but could not clean its staged files: {exc}"
                ) from exc
            try:
                root.parent.rmdir()
            except OSError:
                pass
            return record

    def enabled_paths(self) -> tuple[Path, ...]:
        with self._locked():
            state = self._read_state()
            self._validate_enabled(state)
            installed = {
                (item["id"], item["version"], item["digest"]): item for item in state["installed"]
            }
            return tuple(
                self.root.joinpath(
                    *PurePosixPath(
                        installed[(item["id"], item["version"], item["digest"])]["path"]
                    ).parts
                )
                for item in state["enabled"]
            )
