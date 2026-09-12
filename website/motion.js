import {ASSEMBLY, layout, sceneAt, effectsEnabled, clamp, ROBOT_DETAILS, robotDetail, floatingLogoAt, logoBurstAt} from './motion-model.mjs';

const stage = document.querySelector('.logo-stage');
const canvas = document.querySelector('#robot-stage');
const field = document.querySelector('#pointer-field');
const button = document.querySelector('#motion-toggle');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = matchMedia('(any-pointer: fine)');
const parts = ['body', 'upper', 'fore', 'claw-open', 'claw-closed', 'joint'];
const MAX_PARTICLES = 72;

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Could not load ${src}`));
    image.src = src;
  });
}

async function start() {
  const ctx = canvas.getContext('2d');
  const fx = field.getContext('2d');
  if (!ctx || !fx) return;
  const loaded = await Promise.all([
    ...ROBOT_DETAILS.flatMap(detail => parts.map(name => loadImage(`assets/robots/${detail}/custodian-${name}.png`))),
    loadImage('assets/wordmark.png'), loadImage('assets/icon.png'),
  ]);
  const packs = Object.fromEntries(ROBOT_DETAILS.map((detail, tier) => [detail,
    Object.fromEntries(parts.map((name, index) => [name, loaded[tier * parts.length + index]]))]));
  let detail = robotDetail(document.documentElement.dataset.previewDetail);
  let art = packs[detail];
  const wordmark = loaded[parts.length * ROBOT_DETAILS.length], emblem = loaded[parts.length * ROBOT_DETAILS.length + 1];
  const tinted = document.createElement('canvas');
  tinted.width = wordmark.width; tinted.height = wordmark.height;
  const tint = tinted.getContext('2d');
  let colors, l, stageScale = 1, fieldScale = 1, width = 0, height = 0;
  let paused = false, inView = true, frame = 0, previous = null, elapsed = 0, ambientTime = 0;
  let particles = [], bursts = [], lastPointer = null;
  let lastLogoX = null, lastLogoY = null, lastLogoDirX = 0, lastLogoDirY = 0;
  try { paused = localStorage.getItem('omega-site-motion') === 'paused'; } catch { /* Optional preference. */ }
  if (paused || reduced.matches) elapsed = ASSEMBLY.complete;

  const enabled = () => effectsEnabled({paused, reduced: reduced.matches, hidden: document.hidden});
  const shouldRun = () => enabled() && (inView || finePointer.matches);

  function palette() {
    const css = getComputedStyle(document.documentElement);
    colors = {accent: css.getPropertyValue('--accent').trim(), blue: css.getPropertyValue('--blue').trim(), deep: css.getPropertyValue('--deep').trim()};
    tint.clearRect(0, 0, tinted.width, tinted.height);
    tint.globalCompositeOperation = 'source-over';
    tint.drawImage(wordmark, 0, 0);
    tint.globalCompositeOperation = 'source-in';
    tint.fillStyle = colors.accent;
    tint.fillRect(0, 0, tinted.width, tinted.height);
    tint.globalCompositeOperation = 'source-over';
    drawStage();
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, 2);
    l = layout(matchMedia('(max-width: 640px)').matches);
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    stageScale = canvas.width / l.width;
    width = document.documentElement.clientWidth;
    height = window.innerHeight;
    fieldScale = Math.min(dpr, 1.5, Math.sqrt(3_000_000 / Math.max(1, width * height)));
    field.width = Math.max(1, Math.round(width * fieldScale));
    field.height = Math.max(1, Math.round(height * fieldScale));
    particles = []; bursts = []; lastPointer = null;
    lastLogoX = null; lastLogoY = null; lastLogoDirX = 0; lastLogoDirY = 0;
    if (colors) drawStage();
    wake();
  }

  function part(name, anchor, angle, size, pivot) {
    ctx.save();
    ctx.translate(anchor.x, anchor.y);
    ctx.rotate(angle);
    ctx.drawImage(art[name], -pivot[0] * l.scale, -pivot[1] * l.scale, size[0] * l.scale, size[1] * l.scale);
    ctx.restore();
  }

  function robot(pose) {
    const x = pose.shoulder.x, s = l.scale;
    ctx.save();
    ctx.globalAlpha = .18;
    ctx.fillStyle = colors.accent;
    ctx.beginPath(); ctx.ellipse(x, l.feet + 3, 17 * s, 2 * s, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    ctx.drawImage(art.body, x - 15 * s, l.feet - 44 * s, 30 * s, 44 * s);
    part('upper', pose.shoulder, pose.angles[0], [36, 10], [4.5, 5]);
    part('fore', pose.elbow, pose.angles[1], [32, 9], [4, 4.5]);
    part(pose.closed ? 'claw-closed' : 'claw-open', pose.wrist, pose.angle, [22, 18], [3, 9]);
    for (const joint of [pose.shoulder, pose.elbow, pose.wrist]) {
      ctx.drawImage(art.joint, joint.x - 3.5 * s, joint.y - 3.5 * s, 7 * s, 7 * s);
    }
  }

  function drawStage() {
    if (!l || !colors) return;
    const moving = enabled();
    const scene = sceneAt(elapsed, l);
    const {sign, omega} = scene;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(stageScale, 0, 0, stageScale, 0, 0);
    ctx.imageSmoothingEnabled = detail !== 'sixteen-bit';

    // A few quiet pixels pass behind the installation crew.
    if (moving) {
      ctx.fillStyle = colors.accent;
      for (let i = 0; i < 18; i++) {
        const x = (i * 79 + 29) % l.width;
        const y = (i * 47 + 80) % l.height;
        ctx.globalAlpha = Math.max(0, Math.sin(elapsed * .8 - i)) * .14;
        ctx.fillRect(x, y, 3, 3);
      }
    }
    ctx.globalAlpha = sign.ropes * .52;
    ctx.strokeStyle = colors.accent; ctx.lineWidth = 1.5;
    for (const x of [sign.x, sign.x + sign.width]) {
      ctx.beginPath(); ctx.moveTo(x, l.omegaY - 18); ctx.lineTo(x, sign.y - 3); ctx.stroke();
      ctx.fillStyle = colors.accent; ctx.fillRect(x - 3, l.omegaY - 21, 6, 6);
    }
    ctx.globalAlpha = sign.alpha;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.globalAlpha = sign.alpha * .09;
    ctx.drawImage(tinted, sign.x, sign.y, sign.width, sign.height);
    ctx.globalAlpha = sign.alpha;
    ctx.beginPath(); ctx.rect(sign.x, sign.y, sign.width * sign.etch, sign.height); ctx.clip();
    ctx.drawImage(tinted, sign.x, sign.y, sign.width, sign.height);
    ctx.restore();
    if (sign.etch > 0 && sign.etch < 1) {
      const scanX = sign.x + sign.width * sign.etch;
      ctx.strokeStyle = colors.blue; ctx.globalAlpha = .55 * sign.alpha;
      ctx.beginPath(); ctx.moveTo(scanX, sign.y - 5); ctx.lineTo(scanX, sign.y + sign.height + 5); ctx.stroke();
      for (let i = 0; i < 7; i++) {
        ctx.fillStyle = i % 2 ? colors.accent : colors.blue;
        ctx.fillRect(scanX - (i * 13 + scene.t * 24) % 25, sign.y + (i * 29 + scene.t * 45) % sign.height, 3, 3);
      }
    }
    // The small corner fittings make the gripping and hanging positions visible.
    ctx.globalAlpha = sign.alpha * .65;
    ctx.strokeStyle = colors.accent;
    for (const [x, direction] of [[sign.x, 1], [sign.x + sign.width, -1]]) {
      ctx.beginPath(); ctx.moveTo(x, sign.y + 10); ctx.lineTo(x, sign.y - 3); ctx.lineTo(x + direction * 13, sign.y - 3); ctx.stroke();
    }
    ctx.globalAlpha = omega.alpha;
    ctx.fillStyle = colors.accent;
    ctx.font = `700 ${l.font}px JetBrains, monospace`;
    ctx.textBaseline = 'top';
    let letterX = omega.x;
    for (const letter of 'OMEGA') {
      ctx.fillText(letter, letterX, omega.y);
      letterX += ctx.measureText(letter).width + l.letterSpacing;
    }
    ctx.globalAlpha = 1;
    scene.robots.forEach(robot);
    // Keep the real heading available to assistive technology and as a fallback.
    stage.classList.add('motion-ready');
  }

  function drawField(dt) {
    fx.setTransform(1, 0, 0, 1, 0, 0);
    fx.clearRect(0, 0, field.width, field.height);
    if (!enabled() || !finePointer.matches) return;
    fx.setTransform(fieldScale, 0, 0, fieldScale, 0, 0);
    for (const p of particles) {
      p.age += dt;
      const life = 1 - p.age / .7;
      if (life <= 0) continue;
      fx.globalAlpha = life * .45;
      fx.fillStyle = p.blue ? colors.blue : colors.accent;
      const size = life > .55 ? 4 : 2;
      fx.fillRect(p.x, p.y - p.age * 16, size, size);
    }
    particles = particles.filter(p => p.age < .7);
    // The escaped Omega artifact bounces inside the viewport, below the nav.
    // It is faint and cannot capture clicks, selections, or keyboard focus.
    if (width >= 800 && height >= 320) {
      const logo = floatingLogoAt(ambientTime, width, height);
      if (lastLogoX !== null) {
        // A direction reversal on either axis means it just hit an edge.
        const dirX = Math.sign(logo.x - lastLogoX) || lastLogoDirX;
        const dirY = Math.sign(logo.y - lastLogoY) || lastLogoDirY;
        if ((lastLogoDirX && dirX !== lastLogoDirX) || (lastLogoDirY && dirY !== lastLogoDirY)) {
          bursts.push({x: logo.x + logo.size / 2, y: logo.y + logo.size / 2, age: 0});
          bursts = bursts.slice(-4);
        }
        lastLogoDirX = dirX; lastLogoDirY = dirY;
      }
      lastLogoX = logo.x; lastLogoY = logo.y;
      for (let i = 4; i >= 0; i--) {
        const {x, y, size} = floatingLogoAt(ambientTime - i * .12, width, height);
        fx.globalAlpha = i ? .045 * (5 - i) : .44;
        if (i) { fx.fillStyle = colors.accent; fx.fillRect(x + size / 2 - 2, y + size / 2 - 2, 4, 4); }
        else fx.drawImage(emblem, x, y, size, size);
      }
    }
    for (const burst of bursts) {
      burst.age += dt;
      const pulse = logoBurstAt(burst.age);
      fx.save();
      fx.globalAlpha = pulse.alpha;
      fx.translate(burst.x, burst.y);
      fx.drawImage(emblem, -pulse.size / 2, -pulse.size / 2, pulse.size, pulse.size);
      fx.restore();
    }
    bursts = bursts.filter(burst => burst.age < 1.6);
    fx.globalAlpha = 1;
  }

  function tick(now) {
    frame = 0;
    if (!shouldRun()) { previous = null; return; }
    const dt = previous === null ? 0 : clamp((now - previous) / 1000, 0, .05);
    previous = now;
    if (inView) { elapsed += dt; drawStage(); }
    ambientTime += dt;
    drawField(dt);
    frame = requestAnimationFrame(tick);
  }

  function wake() {
    if (shouldRun()) { if (!frame) frame = requestAnimationFrame(tick); }
    else { cancelAnimationFrame(frame); frame = 0; previous = null; }
  }

  function preferenceChanged() {
    // Skipping decorative motion completes the installation permanently.
    // Resuming, switching themes, resizing, or returning to the tab cannot replay it.
    if (paused || reduced.matches) elapsed = Math.max(elapsed, ASSEMBLY.complete);
    if (!enabled()) {
      particles = []; bursts = []; lastPointer = null;
      lastLogoX = null; lastLogoY = null; lastLogoDirX = 0; lastLogoDirY = 0;
      drawField(0);
    }
    button.hidden = false;
    button.disabled = reduced.matches;
    button.textContent = reduced.matches ? 'Reduced motion' : paused ? 'Resume motion' : 'Pause motion';
    button.title = reduced.matches ? 'Motion is reduced by your device preference.' : 'Control all decorative page animation';
    drawStage();
    wake();
  }

  button.addEventListener('click', () => {
    paused = !paused;
    try { localStorage.setItem('omega-site-motion', paused ? 'paused' : 'on'); } catch { /* Optional preference. */ }
    preferenceChanged();
  });
  window.addEventListener('pointermove', event => {
    if (!enabled() || event.pointerType === 'touch' || !finePointer.matches) return;
    const next = {x: event.clientX, y: event.clientY};
    if (lastPointer) {
      const distance = Math.hypot(next.x - lastPointer.x, next.y - lastPointer.y);
      const count = Math.min(10, Math.floor(distance / 8));
      if (!count) return;
      for (let i = 1; i <= count; i++) {
        const p = i / count;
        particles.push({x: Math.round((lastPointer.x + (next.x - lastPointer.x) * p) / 8) * 8,
          y: Math.round((lastPointer.y + (next.y - lastPointer.y) * p) / 8) * 8, age: 0, blue: i % 4 === 0});
      }
      particles = particles.slice(-MAX_PARTICLES);
    }
    lastPointer = next;
    wake();
  }, {passive: true});
  document.addEventListener('pointerleave', () => { lastPointer = null; });
  window.addEventListener('blur', () => { lastPointer = null; });
  window.addEventListener('pointerdown', event => {
    if (!enabled() || event.pointerType === 'touch' || event.button !== 0) return;
    if (event.target.closest('a,button,input,textarea,select,summary,label,[contenteditable]')) return;
    bursts.push({x: event.clientX, y: event.clientY, age: 0});
    bursts = bursts.slice(-4);
    wake();
  }, {passive: true});
  new IntersectionObserver(entries => {
    inView = entries[0].isIntersecting;
    wake();
  }).observe(stage);
  new ResizeObserver(resize).observe(stage);
  new MutationObserver(palette).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  window.addEventListener('resize', resize, {passive: true});
  document.addEventListener('visibilitychange', () => { previous = null; preferenceChanged(); });
  reduced.addEventListener('change', preferenceChanged);
  finePointer.addEventListener('change', () => { drawField(0); wake(); });
  document.addEventListener('omega-preview-detail', event => {
    detail = robotDetail(event.detail);
    art = packs[detail];
    drawStage();
  });
  resize();
  palette();
  preferenceChanged();
  document.fonts.ready.then(drawStage);
}

// Failed optional artwork never hides the HTML heading or disables the page.
start().catch(error => {
  stage.classList.remove('motion-ready');
  canvas.hidden = true; field.hidden = true; button.hidden = true;
  console.warn('Decorative animation unavailable:', error.message);
});
