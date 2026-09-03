from omega_omarchy.agent import AgentError, apply_op, apply_op_tracked, empty_manifest, preview, rollback
import pytest


def test_preview_apply_rollback():
    manifest = empty_manifest("sha256:" + "ab" * 32)
    settings = {"quality": "clean-pixel", "sharePolicy": "local-only"}
    op = {"op": "set-quality", "value": "crt"}
    assert preview(manifest, op)["ok"] is True
    manifest, settings, txn = apply_op(manifest, op, settings)
    assert settings["quality"] == "crt"
    # Rollback must restore from the stored snapshot, not a caller-supplied copy.
    manifest, settings = rollback(manifest, settings, txn)
    assert settings["quality"] == "clean-pixel"


def test_rejects_host_writes_and_silent_auto_publish():
    manifest = empty_manifest("sha256:" + "cd" * 32)
    with pytest.raises(AgentError):
        apply_op_tracked(manifest, {"op": "set-quality", "hostWrite": "/etc/passwd", "value": "crt"}, {})
    with pytest.raises(AgentError):
        apply_op_tracked(manifest, {"op": "rm-rf-game"}, {})
    with pytest.raises(AgentError):
        apply_op_tracked(manifest, {"op": "set-share-policy", "value": "automatic-public"}, {})
