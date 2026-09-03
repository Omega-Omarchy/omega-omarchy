"""Capability-scoped, versioned game-manifest operations with rollback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import sha256_json, without

MANIFEST_SCHEMA = "omega-omarchy.game-manifest/1"
ALLOWED_OPS = {
    "set-quality",
    "set-crt",
    "set-movement",
    "set-accessibility",
    "set-share-policy",
    "preview-jump",
    "apply-palette",
}


class AgentError(ValueError):
    pass


def empty_manifest(world_digest: str) -> dict[str, Any]:
    record = {
        "ops": [],
        "schema": MANIFEST_SCHEMA,
        "worldDigest": world_digest,
    }
    record["manifestDigest"] = sha256_json(without(record, "manifestDigest"))
    return record


def _validate_op(op: dict[str, Any]) -> None:
    if op.get("op") not in ALLOWED_OPS:
        raise AgentError(f"capability not granted: {op.get('op')}")
    if "path" in op or "hostWrite" in op or "install" in op:
        raise AgentError("host filesystem writes are not a game capability")
    if op.get("op") == "set-share-policy" and op.get("value") == "automatic-public":
        if not op.get("explicit"):
            raise AgentError("automatic public sharing requires an explicit flag")


def preview(manifest: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    _validate_op(op)
    return {"ok": True, "op": op, "preview": True, "wouldApply": True}


def apply_op(manifest: dict[str, Any], op: dict[str, Any], settings: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    _validate_op(op)
    before = dict(settings)
    new_settings = dict(settings)
    kind = op["op"]
    if kind == "set-quality":
        new_settings["quality"] = op["value"]
    elif kind == "set-crt":
        crt = dict(new_settings.get("crt") or {})
        crt.update(op.get("value") or {})
        new_settings["crt"] = crt
    elif kind == "set-movement":
        value = op.get("value") or {}
        if "jumpScale" in value:
            new_settings["jumpScale"] = float(value["jumpScale"])
        if "speedScale" in value:
            new_settings["speedScale"] = float(value["speedScale"])
        if new_settings.get("jumpScale", 1) > 1.25:
            raise AgentError("jump scale exceeds challenge floor")
    elif kind == "set-accessibility":
        new_settings["accessibilityProfile"] = op["value"]
        if op["value"] == "precision-assist":
            new_settings["precisionAssist"] = True
    elif kind == "set-share-policy":
        new_settings["sharePolicy"] = op["value"]
    elif kind == "preview-jump":
        return manifest, new_settings, "preview-only"
    elif kind == "apply-palette":
        new_settings["palette"] = op["value"]
    txn = {
        "before": before,
        "op": op,
        "schema": MANIFEST_SCHEMA,
    }
    txn_id = sha256_json(txn)
    ops = list(manifest.get("ops") or [])
    ops.append({"op": op, "txn": txn_id, "before": before})
    new_manifest = {
        "ops": ops,
        "schema": MANIFEST_SCHEMA,
        "worldDigest": manifest["worldDigest"],
    }
    new_manifest["manifestDigest"] = sha256_json(without(new_manifest, "manifestDigest"))
    return new_manifest, new_settings, txn_id


def rollback(manifest: dict[str, Any], settings: dict[str, Any], txn_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ops = list(manifest.get("ops") or [])
    match = None
    for index, item in enumerate(ops):
        if item.get("txn") == txn_id:
            match = index
            break
    if match is None:
        raise AgentError("unknown transaction")
    # Only the last op can roll back (transactional stack).
    if match != len(ops) - 1:
        raise AgentError("rollback must be the latest transaction")
    item = ops.pop()
    snapshot = item.get("before")
    if not isinstance(snapshot, dict):
        raise AgentError("transaction is missing its before snapshot")
    restored = dict(snapshot)
    new_manifest = {
        "ops": ops,
        "schema": MANIFEST_SCHEMA,
        "worldDigest": manifest["worldDigest"],
    }
    new_manifest["manifestDigest"] = sha256_json(without(new_manifest, "manifestDigest"))
    return new_manifest, restored


def apply_op_tracked(
    manifest: dict[str, Any], op: dict[str, Any], settings: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    before = dict(settings)
    new_manifest, new_settings, txn_id = apply_op(manifest, op, settings)
    return new_manifest, new_settings, txn_id, before


def rollback_to(
    manifest: dict[str, Any], txn_id: str, before: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return rollback(manifest, before, txn_id)
