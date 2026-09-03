"""Real Limitless query-before-work lifecycle with offline abstention."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import sha256_file_bytes, sha256_json, without

TASK_KIND_ASSIST = "omega-precision-assist"
TASK_KIND_JUMP = "omega-movement-jump"
TASK_KIND_UNKNOWN = "omega-unknown-customization"


class LimitlessDecisionError(ValueError):
    pass


def _catalog_root() -> Path:
    return Path(__file__).resolve().parents[2] / "integrations" / "limitless" / "catalog"


def limitless_available() -> bool:
    try:
        import limitless_library  # noqa: F401

        return True
    except ImportError:
        return False


def query_before_work(request: dict[str, Any], catalog: Path | None = None) -> dict[str, Any]:
    """Call the real Limitless local catalog when the library is installed.

    Offline / disabled path: the caller should not invoke this. When the
    library is missing, we fail closed with an abstention-shaped error rather
    than inventing a compatible component.
    """

    catalog = Path(catalog) if catalog is not None else _catalog_root()
    try:
        from limitless_library.connector import query_local
    except ImportError as exc:
        raise LimitlessDecisionError(
            "Limitless Library is not installed; customization will start fresh"
        ) from exc
    try:
        decision = query_local(catalog, request)
    except Exception as exc:  # catalog/schema errors are fail-closed
        raise LimitlessDecisionError(str(exc)) from exc
    return decision


def build_request(
    task_kind: str,
    *,
    objective: str | None = None,
    requested_use: str = "evaluation",
    tenant_scope: str = "public",
    language: str = "json",
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "schemaVersion": "limitless.query/0.1",
        "taskKind": task_kind,
        "receiver": {
            "constraints": [f"language:{language}", "runtime:omega-omarchy", "runtime:any"],
            "toolchain": {"python": "3.12", "omega": "0.1.0"},
        },
        "requestedUse": requested_use,
        "tenantScope": tenant_scope,
        "evaluatedAt": "2026-08-28T00:00:00Z",
    }
    if objective:
        request["objective"] = objective
    return request


@dataclass
class AdoptionReceipt:
    decision_digest: str
    treatment: str
    adopted: bool
    delivered: bool
    world_digest_before: str
    world_digest_after: str
    verifier: str
    reason: str

    def to_record(self) -> dict[str, Any]:
        record = {
            "adopted": self.adopted,
            "decisionDigest": self.decision_digest,
            "delivered": self.delivered,
            "reason": self.reason,
            "treatment": self.treatment,
            "verifier": self.verifier,
            "worldDigestAfter": self.world_digest_after,
            "worldDigestBefore": self.world_digest_before,
        }
        record["receiptDigest"] = sha256_json(without(record, "receiptDigest"))
        return record


def _load_selected_bytes(catalog: Path, decision: dict[str, Any]) -> bytes | None:
    selected = decision.get("selected")
    if not selected or selected["offer"]["kind"] != "exact-component":
        return None
    files = selected["offer"]["files"]
    if not files:
        return None
    # Use LocalCatalog to resolve the capsule root when available.
    from limitless_library.catalog import LocalCatalog

    root = LocalCatalog(catalog).selected_capsule_root(decision)
    source = files[0]["source"]
    path = root / source
    data = path.read_bytes()
    if sha256_file_bytes(data) != files[0]["digest"]:
        raise LimitlessDecisionError("delivered bytes do not match offer digest")
    return data


def adopt_decision(
    decision: dict[str, Any],
    *,
    catalog: Path,
    settings: dict[str, Any],
    world_digest: str,
    enabled: bool,
) -> tuple[dict[str, Any], AdoptionReceipt]:
    """Verify locally and apply only if the world actually changes as promised.

    Delivery is not adoption. Abstentions start fresh. Never publishes.
    """

    if not enabled:
        receipt = AdoptionReceipt(
            decision_digest="sha256:" + "0" * 64,
            treatment="offline-fresh",
            adopted=False,
            delivered=False,
            world_digest_before=world_digest,
            world_digest_after=world_digest,
            verifier="offline",
            reason="limitless-disabled-start-fresh",
        )
        return settings, receipt

    treatment = decision.get("treatment")
    digest = decision.get("decisionDigest", "")
    new_settings = dict(settings)

    if treatment == "abstain" or decision.get("decision") == "abstain":
        receipt = AdoptionReceipt(
            digest, "abstain", False, False, world_digest, world_digest, "limitless", "no-safe-selection-start-fresh"
        )
        return new_settings, receipt

    if treatment == "method-guided":
        method = decision["selected"]["offer"]["method"]
        # Receiver applies the source-free method itself.
        summary = method.get("summary", "")
        if "float" in summary.lower() or "jump" in summary.lower():
            new_settings["jumpScale"] = 1.12
            new_settings["challengeFloor"] = new_settings.get("challengeFloor", 1.0)
        applied = new_settings != settings
        after = sha256_json({"settings": new_settings, "base": world_digest})
        receipt = AdoptionReceipt(
            digest, "method-guided", applied, False, world_digest, after if applied else world_digest, "method-local", "method-applied" if applied else "method-no-change"
        )
        return new_settings, receipt

    # exact-adoption
    data = _load_selected_bytes(catalog, decision)
    delivered = data is not None
    if not delivered:
        receipt = AdoptionReceipt(digest, "exact-adoption", False, False, world_digest, world_digest, "bytes", "missing-bytes")
        return new_settings, receipt
    try:
        component = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LimitlessDecisionError("exact component is not JSON") from exc
    if component.get("kind") != "omega-precision-assist":
        receipt = AdoptionReceipt(digest, "exact-adoption", False, True, world_digest, world_digest, "schema", "incompatible-component")
        return new_settings, receipt
    new_settings["precisionAssist"] = True
    new_settings["coyoteBonus"] = int(component.get("coyoteBonus", 5))
    new_settings["bufferBonus"] = int(component.get("bufferBonus", 3))
    after = sha256_json({"settings": new_settings, "base": world_digest})
    adopted = new_settings.get("precisionAssist") is True
    receipt = AdoptionReceipt(
        digest,
        "exact-adoption",
        adopted,
        True,
        world_digest,
        after if adopted else world_digest,
        "json-schema+activation",
        "adopted" if adopted else "delivered-not-adopted",
    )
    return new_settings, receipt


def contribute(customization: dict[str, Any], policy: str) -> dict[str, Any]:
    """Honor saved sharing policy. Never silently publish."""

    if policy in {"local-only", None, ""}:
        return {"published": False, "retained": True, "reason": "local-only"}
    if policy == "manual-public":
        if not customization.get("explicitPublish"):
            return {"published": False, "retained": True, "reason": "awaiting-manual-publish"}
        return {"published": True, "retained": True, "reason": "explicit-manual-publish"}
    if policy == "agent-under-saved-policy":
        if not customization.get("agentAllowed"):
            return {"published": False, "retained": True, "reason": "agent-not-authorized-this-item"}
        return {"published": True, "retained": True, "reason": "agent-under-saved-policy"}
    if policy == "automatic-public":
        # Still requires the policy itself to have been explicitly chosen earlier.
        if not customization.get("policyChosenExplicitly"):
            return {"published": False, "retained": True, "reason": "automatic-policy-not-explicit"}
        return {"published": True, "retained": True, "reason": "automatic-public"}
    return {"published": False, "retained": True, "reason": "unknown-policy-fail-closed"}
