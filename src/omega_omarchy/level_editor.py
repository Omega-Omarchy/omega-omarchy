"""Local editor packaging and read-only access to the game's traversal checks."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from .canonical import sha256_json
from .identity import GENERATOR_VERSION
from .reachability import find_spawn, normalize_ladder_tiles, reachable_from, validate_level
from .skyway import SKYWAY_BARRIER, upper_route_report

EDITOR_ASSETS = Path(__file__).resolve().parents[2] / "tools" / "level-editor"
GLYPHS = frozenset(".#=L+MDBOEXSCPH^!GNWIK")
MAX_REQUEST_BYTES = 256_000


def checked_tiles(value: Any) -> list[str]:
    if not isinstance(value, list) or not 5 <= len(value) <= 160:
        raise ValueError("Map height must be between 5 and 160 tiles.")
    if not all(isinstance(row, str) for row in value):
        raise ValueError("Map rows must be strings.")
    width = len(value[0])
    if not 8 <= width <= 640 or any(len(row) != width for row in value):
        raise ValueError("Map rows must have the same width, between 8 and 640 tiles.")
    if set("".join(value)) - GLYPHS:
        raise ValueError("Map contains an unsupported tile.")
    for glyph, name in (("S", "spawn"), ("X", "boss")):
        if sum(row.count(glyph) for row in value) != 1:
            raise ValueError(f"Map must contain exactly one {name} anchor.")
    return list(value)


def validate_draft(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Expected a map object.")
    tiles = checked_tiles(payload.get("tiles"))
    report = validate_level(tiles, require_all_logos=True)
    reached = reachable_from(tiles, find_spawn(tiles))
    upper = None
    upper_reached = set()
    if len(tiles) > SKYWAY_BARRIER and set(tiles[SKYWAY_BARRIER]) == {"K"}:
        # Drafts carry tile geometry, so infer landing cells rather than
        # trusting stale generation metadata after the author edits a deck.
        entries = [[x, y - 1] for y, row in enumerate(tiles[:SKYWAY_BARRIER]) for x, cell in enumerate(row)
                   if y > 0 and cell in {"=", "I", "+"} and tiles[y - 1][x] in {".", "C"}]
        upper = upper_route_report(tiles, {"entries": entries, "barrierY": SKYWAY_BARRIER})
        if entries:
            upper_reached = reachable_from(tiles, tuple(entries[0]))
        report["errors"] = [*report["errors"], *upper["errors"]]
        report["ok"] = report["ok"] and upper["ok"]
    # The checker is the same static graph used by generation. It does not
    # claim to simulate enemy pressure, moving-platform timing, or game feel.
    return {
        **report,
        "reachableCells": sorted(reached, key=lambda point: (point[1], point[0])),
        "mapDigest": sha256_json(tiles),
        "checker": "Omega static traversal graph",
        "upperRoute": upper,
        "upperReachableCells": sorted(upper_reached, key=lambda point: (point[1], point[0])),
    }


def build_editor(records: list[dict[str, Any]], destination: Path) -> None:
    data = {
        "generatorVersion": GENERATOR_VERSION,
        "records": [
            {**record, "baseDigest": sha256_json(record["chapter"]["tiles"])}
            for record in records
        ],
    }
    # The artifact works from file:// for editing/export; HTTP enables the
    # authoritative checker. User-supplied seeds cannot break out of JSON.
    encoded = json.dumps(data).replace("<", "\\u003c").replace("&", "\\u0026")
    template = (EDITOR_ASSETS / "editor.html").read_text()
    styles = (EDITOR_ASSETS / "editor.css").read_text()
    script = "\n".join((EDITOR_ASSETS / name).read_text() for name in ("state.js", "editor.js"))
    destination.write_text(
        template.replace("/*EDITOR_CSS*/", styles)
        .replace("/*EDITOR_JS*/", script)
        .replace("<!--EDITOR_DATA-->", encoded),
        encoding="utf-8",
    )


class EditorHandler(SimpleHTTPRequestHandler):
    """Serve one export directory; POSTs validate data and never write files."""

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if self.path not in {"/api/validate", "/api/repair-ladders"}:
            self._json(404, {"error": "Unknown editor action."})
            return
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            self._json(403, {"error": "Editor requests must use the local origin."})
            return
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{host}":
            self._json(403, {"error": "Cross-origin editor requests are disabled."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("Map request exceeds the editor size limit.")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/repair-ladders":
                if not isinstance(payload, dict):
                    raise ValueError("Expected a map object.")
                result = {"tiles": normalize_ladder_tiles(checked_tiles(payload.get("tiles")))}
            else:
                result = validate_draft(payload)
        except (ValueError, TypeError, RecursionError) as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, result)


def editor_server(directory: Path, port: int = 8814) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(
        ("127.0.0.1", port), partial(EditorHandler, directory=str(directory.resolve())),
    )
