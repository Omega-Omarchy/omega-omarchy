from __future__ import annotations

from http.client import HTTPConnection
import json
from threading import Thread

import pytest

from omega_omarchy.level_editor import build_editor, checked_tiles, editor_server, validate_draft
from omega_omarchy.reachability import validate_level
from omega_omarchy.skyway import add_skyway


def small_map() -> list[str]:
    return ["............"] * 5 + [".S........X.", "############"]


def test_editor_reports_the_game_checker_and_detects_a_blocked_boss():
    tiles = small_map()
    report = validate_draft({"tiles": tiles})
    assert report["ok"]
    assert (10, 5) in report["reachableCells"]
    blocked = [row[:6] + "#" + row[7:] for row in tiles]
    report = validate_draft({"tiles": blocked})
    assert not report["ok"]
    assert report["errors"] == validate_level(blocked, require_all_logos=True)["errors"]
    assert (10, 5) not in report["reachableCells"]
    assert tiles == small_map(), "validation is read-only"


def test_editor_checks_upper_route_separately_from_the_locked_base_route():
    tiles, _ = add_skyway(small_map(), "editor", "walled-garden")
    report = validate_draft({"tiles": tiles})
    assert report["ok"] and report["upperRoute"]["ok"]
    assert not any(y < 17 for x, y in report["reachableCells"])
    assert any(y < 17 for x, y in report["upperReachableCells"])
    for y in range(17):
        tiles[y] = tiles[y][:6] + "#" + tiles[y][7:]
    report = validate_draft({"tiles": tiles})
    assert report["bossReachableWithoutRare"]
    assert not report["ok"] and not report["upperRoute"]["ok"]


@pytest.mark.parametrize("value", [None, [], [3] * 8, ["." * 10] * 6, ["S.......X?"] * 5, ["S.......X."] + ["."] * 5])
def test_editor_rejects_malformed_maps(value):
    with pytest.raises(ValueError):
        checked_tiles(value)


def test_editor_embeds_untrusted_seed_as_data_and_is_standalone(tmp_path):
    target = tmp_path / "editor.html"
    build_editor([{"seed": "</script><script>alert(1)</script>", "chapter": {"tiles": small_map()}}], target)
    html = target.read_text()
    assert "</script><script>alert(1)" not in html
    assert "\\u003c/script>" in html
    assert "/*EDITOR_JS*/" not in html
    assert "class DraftHistory" in html
    assert '<script src=' not in html


def test_local_server_validation_repair_and_origin_boundary(tmp_path):
    (tmp_path / "index.html").write_text("workshop")
    with editor_server(tmp_path, 0) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("GET", "/index.html")
            response = conn.getresponse()
            assert response.status == 200 and response.read() == b"workshop"
            conn.request("POST", "/api/validate", json.dumps({"tiles": small_map()}), {"Content-Type": "application/json"})
            response = conn.getresponse()
            assert response.status == 200 and json.loads(response.read())["ok"]
            ladder = small_map()
            ladder[3] = "....L......."
            ladder[4] = "....L......."
            ladder[5] = ".S..L.....X."
            conn.request("POST", "/api/repair-ladders", json.dumps({"tiles": ladder}))
            response = conn.getresponse()
            repaired = json.loads(response.read())["tiles"]
            assert response.status == 200 and validate_draft({"tiles": repaired})["ok"]
            conn.request("POST", "/api/validate", json.dumps({"tiles": small_map()}), {"Origin": "https://unrelated.example"})
            response = conn.getresponse()
            assert response.status == 403
            response.read()
            conn.request("POST", "/api/validate", "{broken")
            response = conn.getresponse()
            assert response.status == 400
            response.read()
            conn.close()
            assert list(tmp_path.iterdir()) == [tmp_path / "index.html"], "POSTs never write drafts to disk"
        finally:
            server.shutdown()
            thread.join(timeout=5)
