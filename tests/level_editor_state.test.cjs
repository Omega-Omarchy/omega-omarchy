const { test } = require("node:test");
const assert = require("node:assert/strict");
const { DraftHistory, paintCell, strokeCells, checkedDraftTiles } = require("../tools/level-editor/state.js");

test("a long stroke is one undo level; starting a new branch discards redo", () => {
  const original = ["S.......X", ".........", "#########"];
  const history = new DraftHistory(original);
  const stroke = history.tiles.slice();
  for (const [x, y] of strokeCells([1, 1], [7, 1])) paintCell(stroke, x, y, "=");
  history.commit(stroke, "Platform");
  assert.equal(history.tiles[1], ".=======.");
  assert.equal(history.entries.length, 2);
  history.undo(); assert.deepEqual(history.tiles, original);
  history.redo(); assert.equal(history.changes().length, 7);
  history.undo();
  const revised = history.tiles.slice(); paintCell(revised, 4, 1, "L");
  history.commit(revised, "Ladder");
  assert.equal(history.canRedo, false);
  assert.equal(history.changes().length, 1);
  assert.deepEqual(original, ["S.......X", ".........", "#########"]);
});

test("protected anchors and bounds survive fast strokes", () => {
  const rows = ["S...!...X"];
  for (const [x, y] of strokeCells([-3, 0], [12, 0])) paintCell(rows, x, y, "#");
  assert.deepEqual(rows, ["S###!###X"]);
  assert.equal(paintCell(rows, 1, 0, "S"), false);
});

test("history retains 100 undo levels and reset is itself undoable", () => {
  const history = new DraftHistory(["S.......X"]);
  for (let i = 0; i < 130; i++) history.commit([i % 2 ? "S..=....X" : "S..L....X"], "Change");
  assert.equal(history.entries.length, 101);
  const edited = history.tiles.slice();
  history.commit(history.original, "Reset");
  assert.equal(history.changes().length, 0);
  assert.deepEqual(history.undo(), edited);
  history.seek(0); assert.equal(history.canUndo, false);
  assert.equal(history.canRedo, true);
});

test("diagonal interpolation leaves no gaps and drafts remain independent", () => {
  const path = strokeCells([2, 8], [7, 1]);
  for (let i = 1; i < path.length; i++) {
    assert.ok(Math.abs(path[i][0] - path[i - 1][0]) <= 1);
    assert.ok(Math.abs(path[i][1] - path[i - 1][1]) <= 1);
  }
  const a = new DraftHistory(["S.......X"]), b = new DraftHistory(["S.......X"]);
  a.commit(["S..=....X"], "A");
  assert.equal(b.changes().length, 0);
});

test("portable drafts round trip but reject another base, malformed rows, and moved anchors", () => {
  const record = { seed: "test", baseDigest: "sha256:fixture", chapter: { tiles: ["S.......X"] } };
  const draft = { format: "omega-level-draft-v1", seed: "test", baseDigest: record.baseDigest, tiles: ["S..=....X"] };
  assert.deepEqual(checkedDraftTiles(JSON.parse(JSON.stringify(draft)), record), draft.tiles);
  for (const override of [{ seed: "different" }, { baseDigest: "new-generation" }, { tiles: ["S..X....X"] }, { tiles: [".S......X"] }, { tiles: ["bad"] }, { tiles: ["S..?...X"] }])
    assert.throws(() => checkedDraftTiles({ ...draft, ...override }, record));
});

test("invisible platforms can be authored while skyway seals stay protected", () => {
  const rows = ["S.......X", "KKKKKKKKK"];
  assert.equal(paintCell(rows, 4, 0, "I"), true);
  assert.equal(paintCell(rows, 4, 1, "."), false);
  assert.equal(paintCell(rows, 4, 0, "K"), false);
  const record = { seed: "sky", baseDigest: "base", chapter: { tiles: ["S.......X", "KKKKKKKKK"] } };
  const draft = { format: "omega-level-draft-v1", seed: "sky", baseDigest: "base", tiles: rows };
  assert.deepEqual(checkedDraftTiles(draft, record), rows);
  assert.throws(() => checkedDraftTiles({ ...draft, tiles: ["S...I...X", "KKKK.KKKK"] }, record));
});
