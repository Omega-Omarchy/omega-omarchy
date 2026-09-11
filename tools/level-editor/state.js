/* Shared, DOM-free editing state. One stroke is one undo level. */
class DraftHistory {
  constructor(tiles, limit = 100) {
    this.original = tiles.slice();
    this.entries = [{ tiles: tiles.slice(), label: "Original map" }];
    this.index = 0;
    this.limit = limit;
  }
  get tiles() { return this.entries[this.index].tiles; }
  get canUndo() { return this.index > 0; }
  get canRedo() { return this.index < this.entries.length - 1; }
  commit(tiles, label) {
    if (tiles.every((row, i) => row === this.tiles[i])) return false;
    this.entries = this.entries.slice(0, this.index + 1);
    this.entries.push({ tiles: tiles.slice(), label });
    if (this.entries.length > this.limit + 1) this.entries.shift();
    this.index = this.entries.length - 1;
    return true;
  }
  undo() { if (this.canUndo) this.index--; return this.tiles; }
  redo() { if (this.canRedo) this.index++; return this.tiles; }
  seek(index) {
    if (Number.isInteger(index) && index >= 0 && index < this.entries.length) this.index = index;
    return this.tiles;
  }
  changes() {
    const result = [];
    this.tiles.forEach((row, y) => [...row].forEach((after, x) => {
      const before = this.original[y][x];
      if (before !== after) result.push({ x, y, before, after });
    }));
    return result;
  }
}

function paintCell(tiles, x, y, glyph) {
  if (typeof glyph !== "string" || glyph.length !== 1 || !".#=L+MDBOECPH^GNWI".includes(glyph)) return false;
  if (!Number.isInteger(x) || !Number.isInteger(y) || y < 0 || y >= tiles.length || x < 0 || x >= tiles[0].length) return false;
  if ("SX!K".includes(tiles[y][x]) || "SX!K".includes(glyph) || tiles[y][x] === glyph) return false;
  tiles[y] = tiles[y].slice(0, x) + glyph + tiles[y].slice(x + 1);
  return true;
}

function strokeCells(from, to) {
  const result = [];
  let [x, y] = from;
  const [tx, ty] = to;
  const dx = Math.abs(tx - x), sx = x < tx ? 1 : -1;
  const dy = -Math.abs(ty - y), sy = y < ty ? 1 : -1;
  let error = dx + dy;
  while (true) {
    result.push([x, y]);
    if (x === tx && y === ty) break;
    const twice = 2 * error;
    if (twice >= dy) { error += dy; x += sx; }
    if (twice <= dx) { error += dx; y += sy; }
  }
  return result;
}

function checkedDraftTiles(value, record) {
  if (value?.format !== "omega-level-draft-v1" || value.baseDigest !== record.baseDigest || value.seed !== record.seed)
    throw Error("This draft belongs to a different map or generator output. Select its original map first.");
  const base = record.chapter.tiles, rows = value.tiles;
  if (!Array.isArray(rows) || rows.length !== base.length || rows.some(row => typeof row !== "string" || row.length !== base[0].length || /[^.#=L+MDBOEXSCPH^!GNWIK]/.test(row)))
    throw Error("Draft dimensions or tile types do not match this map.");
  for (let y = 0; y < rows.length; y++) for (let x = 0; x < rows[y].length; x++) {
    if (("SX!K".includes(base[y][x]) || "SX!K".includes(rows[y][x])) && base[y][x] !== rows[y][x])
      throw Error("Draft moves or overwrites a protected anchor.");
  }
  return rows;
}

if (typeof module !== "undefined") module.exports = { DraftHistory, paintCell, strokeCells, checkedDraftTiles };
