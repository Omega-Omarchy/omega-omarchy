import os
from pathlib import Path

import pytest

from omega_omarchy.generation import generate_world
from omega_omarchy.limitless_adapter import (
    LimitlessDecisionError,
    adopt_decision,
    build_request,
    contribute,
    limitless_available,
    query_before_work,
)

CATALOG = Path(__file__).resolve().parents[1] / "integrations" / "limitless" / "catalog"
HELLO = Path(os.environ.get("OMEGA_OMARCHY_LIMITLESS_FIXTURE", "tests/fixtures/no-limitless-catalog"))


@pytest.mark.skipif(
    not limitless_available() or not HELLO.is_dir(),
    reason="set OMEGA_OMARCHY_LIMITLESS_FIXTURE to an installed Limitless example catalog",
)
def test_real_hello_catalog_reuse_and_abstain():
    from limitless_library.connector import query_local

    reuse = query_local(
        HELLO,
        {
            "schemaVersion": "limitless.query/0.1",
            "taskKind": "render-greeting",
            "receiver": {"constraints": ["language:python", "runtime:any"], "toolchain": {"python": "3.12"}},
            "requestedUse": "evaluation",
            "tenantScope": "public",
            "evaluatedAt": "2026-08-11T12:00:00Z",
        },
    )
    assert reuse["decision"] == "reuse"
    assert reuse["treatment"] == "exact-adoption"
    method = query_local(
        HELLO,
        {
            "schemaVersion": "limitless.query/0.1",
            "taskKind": "render-greeting",
            "receiver": {"constraints": ["language:javascript", "runtime:any"], "toolchain": {"node": "24"}},
            "requestedUse": "evaluation",
            "tenantScope": "public",
            "evaluatedAt": "2026-08-11T12:00:00Z",
        },
    )
    assert method["decision"] == "instantiate"
    assert method["treatment"] == "method-guided"
    abstain = query_local(
        HELLO,
        {
            "schemaVersion": "limitless.query/0.1",
            "taskKind": "not-a-real-task",
            "receiver": {"constraints": ["language:python", "runtime:any"], "toolchain": {"python": "3.12"}},
            "requestedUse": "evaluation",
            "tenantScope": "public",
            "evaluatedAt": "2026-08-11T12:00:00Z",
        },
    )
    assert abstain["decision"] == "abstain"
    assert abstain["selected"] is None


@pytest.mark.skipif(not limitless_available(), reason="limitless-library not installed")
def test_game_catalog_precision_assist_adopted_not_merely_delivered():
    request = build_request("omega-precision-assist")
    decision = query_before_work(request, CATALOG)
    assert decision["decision"] == "reuse"
    world = generate_world("omega-fixture-1", force_logo=True)
    settings = {"precisionAssist": False}
    new_settings, receipt = adopt_decision(
        decision,
        catalog=CATALOG,
        settings=settings,
        world_digest=world.identity.digest(),
        enabled=True,
    )
    rec = receipt.to_record()
    assert rec["delivered"] is True
    assert rec["adopted"] is True
    assert new_settings["precisionAssist"] is True
    assert rec["worldDigestAfter"] != rec["worldDigestBefore"]


@pytest.mark.skipif(not limitless_available(), reason="limitless-library not installed")
def test_game_catalog_method_and_abstain_and_offline_fresh():
    method_decision = query_before_work(build_request("omega-movement-jump"), CATALOG)
    assert method_decision["treatment"] == "method-guided"
    world = generate_world("omega-fixture-1", force_logo=True)
    settings, receipt = adopt_decision(
        method_decision,
        catalog=CATALOG,
        settings={},
        world_digest=world.identity.digest(),
        enabled=True,
    )
    assert settings.get("jumpScale") == 1.12
    assert receipt.adopted is True
    abstain = query_before_work(build_request("omega-unknown-customization"), CATALOG)
    assert abstain["decision"] == "abstain"
    _, fresh = adopt_decision(
        abstain,
        catalog=CATALOG,
        settings={},
        world_digest=world.identity.digest(),
        enabled=True,
    )
    assert fresh.adopted is False
    assert "start-fresh" in fresh.reason
    _, offline = adopt_decision(
        method_decision,
        catalog=CATALOG,
        settings={},
        world_digest=world.identity.digest(),
        enabled=False,
    )
    assert offline.treatment == "offline-fresh"
    assert offline.delivered is False


def test_silent_publish_never_happens():
    result = contribute({"id": "c1"}, "local-only")
    assert result["published"] is False
    assert result["retained"] is True
    waiting = contribute({"id": "c1"}, "manual-public")
    assert waiting["published"] is False
    explicit = contribute({"id": "c1", "explicitPublish": True}, "manual-public")
    assert explicit["published"] is True
