(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("editor-data").textContent);
  const $ = id => document.getElementById(id);
  const canvas = $("map-canvas"), ctx = canvas.getContext("2d"), viewport = $("viewport");
  const palette = [
    [".", "Erase", "#33434d"], ["#", "Solid", "#61768b"], ["=", "Platform", "#b3c6d6"],
    ["I", "Invisible platform", "#9ece6a"], ["L", "Ladder", "#a8d98a"], ["+", "Crossing", "#8eda81"], ["^", "Bumper", "#73d8ce"],
    ["M", "Corruption", "#eb5e65"], ["B", "Reward block", "#54b6de"], ["D", "Crate", "#b18b61"],
    ["O", "Edit pickup", "#edc662"], ["C", "Item", "#a7a3ff"], ["P", "Penguin", "#fafafa"],
    ["H", "Secret", "#d1e9ec"], ["E", "Enemy", "#f4888e"],
  ];
  const names = Object.fromEntries(palette.map(([g, n]) => [g, n]));
  Object.assign(names, { K: "Boundary (protected)", S: "Spawn (protected)", X: "Boss (protected)", "!": "Anchor (protected)", G: "Gate", N: "Network node", W: "Wind" });
  const colors = Object.fromEntries(palette.map(([g, , c]) => [g, c]));
  Object.assign(colors, { K: "#223e51", S: "#ffffff", X: "#ff8bb1", "!": "#edc662", G: "#75879a", N: "#73d8ce", W: "#73d8ce" });
  let active, selected = "=", locked = true, scale = .5, cursor = [0, 0], gesture = null, space = false;
  const drafts = new Map();
  const status = message => { $("draft-status").textContent = message; };
  const key = record => `omega-level-draft-v1:${record.seed}:${record.baseDigest}`;
  const tiles = () => gesture?.kind === "paint" ? gesture.tiles : active.history.tiles;

  function portable() {
    return { format: "omega-level-draft-v1", generatorVersion: data.generatorVersion, seed: active.record.seed,
      chapterId: active.record.chapter.chapterId, baseDigest: active.record.baseDigest, tiles: active.history.tiles,
      changeCount: active.history.changes().length };
  }
  function save() {
    try {
      if (active.history.changes().length) localStorage.setItem(key(active.record), JSON.stringify(portable()));
      else localStorage.removeItem(key(active.record));
      status(active.history.changes().length ? "Draft saved in this browser" : "Original map · no changes");
    } catch { status("Browser storage unavailable or full · export to keep this draft"); }
  }
  function invalidate() {
    active.revision++;
    active.report = null;
    active.reached = null;
    active.upperReached = null;
    active.checking = false;
    $("validation-badge").textContent = "Needs check";
    $("validation-badge").className = "badge stale";
    $("validation-summary").textContent = "The map changed. Check traversal again to update the overlay.";
    $("validation-errors").replaceChildren();
  }
  function commit(rows, label) {
    if (locked || !active.history.commit(rows, label)) return;
    invalidate(); save(); update(); draw();
  }
  function update() {
    document.body.classList.toggle("locked", locked);
    $("lock").textContent = locked ? "🔒 Map locked" : "🔓 Editing unlocked";
    $("lock").classList.toggle("unlocked", !locked);
    $("lock").setAttribute("aria-pressed", String(locked));
    $("undo").disabled = locked || !active.history.canUndo;
    $("redo").disabled = locked || !active.history.canRedo;
    $("import").disabled = locked;
    $("history").disabled = locked;
    $("repair").disabled = locked || active.checking;
    $("validate").disabled = active.checking;
    $("validate").textContent = active.checking ? "Checking…" : "Check traversal";
    const count = active.history.changes().length;
    $("reset").disabled = locked || !count;
    $("change-count").textContent = `${count} changed ${count === 1 ? "tile" : "tiles"}`;
    $("history").replaceChildren(...active.history.entries.map((entry, i) => {
      const option = new Option(`${i}. ${entry.label}`, String(i));
      option.selected = i === active.history.index;
      return option;
    }));
    inspect();
  }
  function inspect() {
    const [x, y] = cursor, glyph = tiles()[y]?.[x];
    if (!glyph) return;
    const before = active.history.original[y][x];
    $("cursor-info").textContent = `(${x}, ${y}) · ${names[glyph] || glyph}${before !== glyph ? ` · was ${names[before] || before}` : ""}`;
  }
  function zoom(center = true) {
    const worldCenter = [(viewport.scrollLeft + viewport.clientWidth / 2) / scale, (viewport.scrollTop + viewport.clientHeight / 2) / scale];
    scale = $("zoom").value === "fit" ? (viewport.clientWidth - 2) / canvas.width : Number($("zoom").value);
    canvas.style.width = `${canvas.width * scale}px`;
    canvas.style.height = `${canvas.height * scale}px`;
    if (center) {
      viewport.scrollLeft = worldCenter[0] * scale - viewport.clientWidth / 2;
      viewport.scrollTop = worldCenter[1] * scale - viewport.clientHeight / 2;
    }
    draw();
  }
  function focusCell(x, y) {
    cursor = [x, y];
    viewport.scrollLeft = x * 16 * scale - viewport.clientWidth / 3;
    viewport.scrollTop = y * 16 * scale - viewport.clientHeight * .7;
    inspect(); draw();
  }
  function goSpawn() {
    const y = tiles().findIndex(row => row.includes("S"));
    if (y >= 0) focusCell(tiles()[y].indexOf("S"), y);
  }
  function switchMap(index) {
    gesture = null;
    if (!drafts.has(index)) {
      const record = data.records[index], history = new DraftHistory(record.chapter.tiles);
      let restoreError = "";
      try {
        const stored = localStorage.getItem(key(record));
        if (stored) history.commit(checkedDraftTiles(JSON.parse(stored), record), "Restored browser draft");
      } catch (error) { restoreError = `Could not restore draft: ${error.message}`; }
      drafts.set(index, { record, history, revision: 0, report: null, reached: null, checking: false, restoreError });
    }
    active = drafts.get(index); locked = true;
    $("map-select").value = String(index);
    const rows = active.history.tiles;
    canvas.width = rows[0].length * 16; canvas.height = rows.length * 16;
    $("map-info").textContent = `${rows[0].length} × ${rows.length} tiles · generator ${data.generatorVersion}`;
    // An in-flight response from a previous visit must not overwrite this view.
    active.revision++; active.checking = false;
    if (active.report) showReport(active.report);
    else {
      $("validation-badge").textContent = "Not checked"; $("validation-badge").className = "badge";
      $("validation-summary").textContent = "Check boss access, edit pickups, ladders and penguin routes using the game's checker.";
      $("validation-errors").replaceChildren();
    }
    status(active.restoreError || (active.history.changes().length ? "Browser draft restored" : "Original map · unlock to edit"));
    zoom(false); goSpawn(); update();
  }
  function draw() {
    if (!active) return;
    const rows = tiles(), w = rows[0].length, h = rows.length;
    const showReach = active.reached && $("reach-overlay").checked;
    const showChanges = $("changes-overlay").checked;
    ctx.fillStyle = "#0d1923"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (const [i, section] of (active.record.chapter.placements || []).entries()) {
      ctx.fillStyle = i % 2 ? "#142330" : "#101e29";
      ctx.fillRect(section.x * 16, 0, section.width * 16, canvas.height);
    }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const glyph = rows[y][x], xx = x * 16, yy = y * 16;
      if (glyph !== "." && glyph !== "K") {
        ctx.fillStyle = colors[glyph] || "#9bafa9";
        if (glyph === "L" || glyph === "+") {
          ctx.fillRect(xx + 4, yy, 2, 16); ctx.fillRect(xx + 10, yy, 2, 16);
          ctx.fillRect(xx + 4, yy + 5, 8, 2); ctx.fillRect(xx + 4, yy + 12, 8, 2);
          if (glyph === "+") ctx.fillRect(xx, yy, 16, 3);
        } else {
          ctx.fillRect(xx + 1, yy + (["=", "I"].includes(glyph) ? 0 : 1), 14, ["=", "I"].includes(glyph) ? 4 : 14);
          if (!"#=M".includes(glyph)) {
            ctx.fillStyle = "#0c141b"; ctx.font = "bold 12px monospace"; ctx.textAlign = "center";
            ctx.fillText(glyph, xx + 8, yy + 12);
          }
        }
      }
      if (showReach && active.reached.has(`${x},${y}`)) {
        ctx.fillStyle = "rgba(139,224,114,.28)"; ctx.fillRect(xx + 2, yy + 2, 12, 12);
      }
      if (showChanges && glyph !== active.history.original[y][x]) {
        ctx.strokeStyle = "#ffd782"; ctx.lineWidth = 2; ctx.strokeRect(xx + 1, yy + 1, 14, 14);
      }
    }
    if ($("grid").checked && scale >= .5) {
      ctx.strokeStyle = "rgba(114,146,165,.18)"; ctx.lineWidth = 1; ctx.beginPath();
      for (let x = 0; x <= w; x++) { ctx.moveTo(x * 16 + .5, 0); ctx.lineTo(x * 16 + .5, h * 16); }
      for (let y = 0; y <= h; y++) { ctx.moveTo(0, y * 16 + .5); ctx.lineTo(w * 16, y * 16 + .5); }
      ctx.stroke();
    }
    // Dynamic objects remain visible for context; this draft edits the tile layer.
    for (const [kind, color] of [["movingPlatforms", "#dd93ff"], ["tiltingPlatforms", "#ffa974"], ["windColumns", "#63cddd"]]) {
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash([4, 3]);
      for (const feature of active.record.chapter[kind] || []) ctx.strokeRect(feature.x * 16, feature.y * 16, feature.width * 16, (feature.height || .4) * 16);
    }
    ctx.setLineDash([]); ctx.strokeStyle = locked ? "#ffffff" : "#b4e77a"; ctx.lineWidth = 2;
    ctx.strokeRect(cursor[0] * 16 + 1, cursor[1] * 16 + 1, 14, 14);
  }
  function point(event) {
    const rect = canvas.getBoundingClientRect();
    return [Math.max(0, Math.min(canvas.width / 16 - 1, Math.floor((event.clientX - rect.left) / (16 * scale)))),
      Math.max(0, Math.min(canvas.height / 16 - 1, Math.floor((event.clientY - rect.top) / (16 * scale))))];
  }
  function finishGesture(cancel = false) {
    const previous = gesture; gesture = null;
    if (previous?.kind === "paint" && !cancel) commit(previous.tiles, `Paint ${names[previous.glyph]}`);
    draw(); inspect();
  }
  canvas.addEventListener("pointerdown", event => {
    if (event.button !== 0 && event.button !== 1) return;
    event.preventDefault(); viewport.focus(); canvas.setPointerCapture(event.pointerId);
    cursor = point(event);
    if (locked || space || event.button === 1 || $("tool").value === "pan") {
      gesture = { kind: "pan", x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
    } else if ($("tool").value === "paint") {
      gesture = { kind: "paint", tiles: active.history.tiles.slice(), last: cursor, glyph: selected };
      paintCell(gesture.tiles, ...cursor, selected);
      // Hide a previous route forecast as soon as a stroke starts.
      invalidate(); update();
    }
    draw(); inspect();
  });
  canvas.addEventListener("pointermove", event => {
    if (gesture?.kind === "pan") {
      viewport.scrollLeft = gesture.left + gesture.x - event.clientX;
      viewport.scrollTop = gesture.top + gesture.y - event.clientY;
    } else {
      cursor = point(event);
      if (gesture?.kind === "paint") {
        for (const [x, y] of strokeCells(gesture.last, cursor)) paintCell(gesture.tiles, x, y, gesture.glyph);
        gesture.last = cursor;
      }
      draw(); inspect();
    }
  });
  canvas.addEventListener("pointerup", () => finishGesture());
  canvas.addEventListener("pointercancel", () => finishGesture(true));
  canvas.addEventListener("lostpointercapture", () => { if (gesture) finishGesture(true); });
  window.addEventListener("blur", () => { space = false; finishGesture(true); });
  function historyAction(action) {
    if (locked || gesture) return;
    action(); invalidate(); save(); update(); draw();
  }
  document.addEventListener("keydown", event => {
    if (/INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return;
    if ((event.ctrlKey || event.metaKey) && ["z", "y"].includes(event.key.toLowerCase())) {
      event.preventDefault();
      historyAction(() => event.shiftKey || event.key.toLowerCase() === "y" ? active.history.redo() : active.history.undo());
      return;
    }
    if (document.activeElement !== viewport) return;
    if (event.code === "Space") { space = true; event.preventDefault(); return; }
    const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (directions[event.key]) {
      event.preventDefault(); const [dx, dy] = directions[event.key];
      cursor = [Math.max(0, Math.min(tiles()[0].length - 1, cursor[0] + dx)), Math.max(0, Math.min(tiles().length - 1, cursor[1] + dy))];
      const [px, py] = cursor.map(value => value * 16 * scale), size = 16 * scale;
      if (px < viewport.scrollLeft || px + size > viewport.scrollLeft + viewport.clientWidth) viewport.scrollLeft = px - viewport.clientWidth / 2;
      if (py < viewport.scrollTop || py + size > viewport.scrollTop + viewport.clientHeight) viewport.scrollTop = py - viewport.clientHeight / 2;
      draw(); inspect();
    } else if (["Enter", "Delete", "Backspace"].includes(event.key)) {
      event.preventDefault();
      if (!locked && !gesture) { const rows = tiles().slice(); paintCell(rows, ...cursor, event.key === "Enter" ? selected : "."); commit(rows, event.key === "Enter" ? `Paint ${names[selected]}` : "Erase tile"); }
    }
  });
  document.addEventListener("keyup", event => { if (event.code === "Space") space = false; });

  async function request(path, rows) {
    if (location.protocol === "file:") throw Error("Live checks need the local server. Run ./scripts/omega editor and open its editor link.");
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tiles: rows }) });
    if (!response.headers.get("content-type")?.includes("application/json")) throw Error("This server has no traversal checker. Run ./scripts/omega editor and open its editor link.");
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "The traversal checker could not read this map.");
    return result;
  }
  function showReport(report) {
    $("validation-badge").textContent = report.ok ? "Static checks passed" : "Needs attention";
    $("validation-badge").className = `badge ${report.ok ? "good" : "bad"}`;
    $("validation-summary").textContent = `${report.reachableCount} reachable cells · ${report.errors.length} issues. ${report.ok ? "Boss, edit pickups and required penguin routes are connected." : "Review the issues below and the green reachability overlay."}`;
    $("validation-errors").replaceChildren(...report.errors.map(error => {
      const li = document.createElement("li"); li.textContent = error;
      const match = /:(\d+):(\d+)$/.exec(error);
      if (match) {
        const button = document.createElement("button"); button.textContent = "Show tile";
        button.addEventListener("click", () => focusCell(Number(match[1]), Number(match[2]))); li.append(" ", button);
      }
      return li;
    }));
  }
  async function validate() {
    const draft = active, revision = draft.revision;
    draft.checking = true; update();
    try {
      const report = await request("/api/validate", draft.history.tiles);
      if (draft !== active || revision !== draft.revision) return;
      draft.report = report; draft.reached = new Set(report.reachableCells.map(([x, y]) => `${x},${y}`));
      draft.upperReached = new Set((report.upperReachableCells || []).map(([x, y]) => `${x},${y}`));
      showReport(report); draw();
    } catch (error) {
      if (draft !== active || revision !== draft.revision) return;
      $("validation-badge").textContent = "Check unavailable"; $("validation-badge").className = "badge bad";
      $("validation-summary").textContent = error.message;
    } finally { if (draft === active && revision === draft.revision) { draft.checking = false; update(); } }
  }
  $("validate").addEventListener("click", validate);
  $("repair").addEventListener("click", async () => {
    if (locked) return;
    const draft = active, revision = draft.revision;
    try {
      const result = await request("/api/repair-ladders", draft.history.tiles);
      if (locked || draft !== active || revision !== draft.revision) return;
      // Repair may never overwrite protected anchors, even if future checker rules change.
      const rows = checkedDraftTiles({ ...portable(), tiles: result.tiles }, draft.record);
      commit(rows, "Repair ladder ends"); await validate();
    } catch (error) { if (draft === active) status(error.message); }
  });
  $("lock").addEventListener("click", () => { finishGesture(true); locked = !locked; update(); draw(); });
  $("undo").addEventListener("click", () => historyAction(() => active.history.undo()));
  $("redo").addEventListener("click", () => historyAction(() => active.history.redo()));
  $("history").addEventListener("change", event => historyAction(() => active.history.seek(Number(event.target.value))));
  $("reset").addEventListener("click", () => commit(active.history.original, "Reset to original"));
  $("zoom").addEventListener("change", () => zoom());
  $("spawn").addEventListener("click", goSpawn);
  for (const id of ["grid", "reach-overlay", "changes-overlay"]) $(id).addEventListener("change", draw);
  window.addEventListener("resize", () => { if ($("zoom").value === "fit") zoom(); });
  $("map-select").addEventListener("change", event => switchMap(Number(event.target.value)));
  $("export").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(portable(), null, 2) + "\n"], { type: "application/json" });
    const link = document.createElement("a"), url = URL.createObjectURL(blob);
    link.href = url; link.download = `${active.record.seed.replace(/[^a-zA-Z0-9_-]/g, "_")}-level-draft.json`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); status("Draft exported · original map unchanged");
  });
  $("import").addEventListener("click", () => { if (!locked) $("import-file").click(); });
  $("import-file").addEventListener("change", async event => {
    const file = event.target.files[0], draft = active, revision = active.revision;
    if (!file || locked) return;
    try {
      if (file.size > 256000) throw Error("Draft file exceeds the 256 KB limit.");
      const value = JSON.parse(await file.text());
      if (locked || draft !== active || revision !== draft.revision) return;
      commit(checkedDraftTiles(value, draft.record), "Import draft");
    } catch (error) { status(`Import failed: ${error.message}`); }
    finally { event.target.value = ""; }
  });
  for (const [glyph, name, color] of palette) {
    const button = document.createElement("button"); button.className = "tile-button";
    button.setAttribute("aria-label", `${name} tile`); button.setAttribute("aria-pressed", String(selected === glyph));
    const swatch = document.createElement("span"); swatch.className = "swatch"; swatch.style.background = color; swatch.textContent = glyph;
    button.append(swatch, name);
    button.addEventListener("click", () => {
      selected = glyph;
      for (const other of $("palette").children) other.setAttribute("aria-pressed", String(other === button));
      $("tool").value = "paint";
    });
    $("palette").append(button);
  }
  data.records.forEach((record, i) => $("map-select").add(new Option(record.label || record.seed, String(i))));
  const initial = Number(new URLSearchParams(location.search).get("map") || 0);
  switchMap(Number.isInteger(initial) && initial >= 0 && initial < data.records.length ? initial : 0);
})();
