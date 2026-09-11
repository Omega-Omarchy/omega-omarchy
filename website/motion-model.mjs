// The game's two arm links and wrist, expressed independently of the browser.
export const ASSEMBLY = Object.freeze({
  signContact: 1.2, signLift: 1.5, signMounted: 4, signRelease: 4.5, signWithdraw: 4.75,
  omegaContact: 6.1, omegaLift: 6.4, omegaMounted: 8.9, omegaRelease: 9.3, omegaWithdraw: 9.55,
  complete: 10.85,
});
export const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
export const lerp = (a, b, p) => a + (b - a) * p;
const point = (a, b, p) => ({x: lerp(a.x, b.x, p), y: lerp(a.y, b.y, p)});
const rad = degrees => degrees * Math.PI / 180;
const end = (p, length, angle) => ({x: p.x + length * Math.cos(angle), y: p.y + length * Math.sin(angle)});
const ease = (t, start, stop) => { const p = clamp((t - start) / (stop - start)); return p * p * (3 - 2 * p); };

export function layout(compact = false) {
  const view = compact
    ? {width: 760, height: 312, scale: 2.6, feet: 268, homes: [60, 700], signX: 140, signY: 128, signWidth: 480, drop: 60, omegaY: 102, font: 22, dock: {x: 103, y: 247}}
    : {width: 1160, height: 300, scale: 3.6, feet: 260, homes: [125, 1035], signX: 280, signY: 86, signWidth: 600, drop: 64, omegaY: 58, font: 24, dock: {x: 184, y: 243}};
  // The in-game installer offsets OMEGA 4 pixels into the 196-pixel wordmark.
  return {...view, omegaX: view.signX + view.signWidth * 4 / 196, letterSpacing: 4};
}

// Clamping avoids NaNs if a future pose asks the arm to reach beyond its links.
// Choreography tests separately ensure the intended grips are actually reachable.
export function solveArm(shoulder, target, upper, fore, bend = -1) {
  const dx = target.x - shoulder.x, dy = target.y - shoulder.y;
  const distance = clamp(Math.hypot(dx, dy), Math.abs(upper - fore) + 0.0001, upper + fore - 0.0001);
  const aim = Math.atan2(dy, dx);
  const spread = Math.acos(clamp((upper * upper + distance * distance - fore * fore) / (2 * upper * distance), -1, 1));
  const upperAngle = aim + bend * spread;
  const elbow = end(shoulder, upper, upperAngle);
  const wrist = end(shoulder, distance, aim);
  return {shoulder, elbow, wrist, angles: [upperAngle, Math.atan2(wrist.y - elbow.y, wrist.x - elbow.x)]};
}

function idleGrip(l, right, t) {
  const flip = a => right ? Math.PI - a : a;
  const phase = (t % 24) * Math.PI / 12;
  const shoulder = {x: l.homes[Number(right)], y: l.feet - 40 * l.scale};
  // The left custodian does a slower elbow dip and a small wrist flourish.
  const upper = flip(rad(right ? -83 + Math.sin(phase * 4) * 4 : -78 + Math.sin(phase * 2 + .8) * 6));
  const fore = flip(rad(right ? 68 + Math.sin(phase * 3 + 1) * 5 : 76 + Math.sin(phase * 3 + 2.2) * 7));
  const angle = flip(rad(right ? 20 + Math.sin(phase * 4 + 1) * 8 : 8 + Math.sin(phase * 5 + .3) * 13));
  const wrist = end(end(shoulder, 27 * l.scale, upper), 24 * l.scale, fore);
  return {grip: end(wrist, 14 * l.scale, angle), angle};
}

function blend(a, b, p) {
  let turn = (b.angle - a.angle) % (2 * Math.PI);
  if (turn > Math.PI) turn -= 2 * Math.PI;
  if (turn < -Math.PI) turn += 2 * Math.PI;
  return {grip: point(a.grip, b.grip, p), angle: a.angle + turn * p};
}

function carry(l, p) {
  // Raise the prefix above the arm before moving it onto the hanging sign.
  const q = point(l.dock, {x: l.omegaX + 4, y: l.omegaY + 14}, p);
  q.y -= Math.sin(p * Math.PI) * (l.width > 800 ? 50 : 22);
  return q;
}

export function sceneAt(seconds, l = layout()) {
  // Only idle oscillation repeats. Once installed, neither sign is removed.
  const t = Math.max(0, seconds);
  const a = ASSEMBLY;
  const lift = ease(t, a.signLift, a.signMounted);
  const signY = l.signY + l.drop * (1 - lift);
  const omegaProgress = ease(t, a.omegaLift, a.omegaMounted);
  const omegaGrip = carry(l, omegaProgress);
  const omega = {grip: omegaGrip, angle: 0};
  const robots = [false, true].map(right => {
    const idle = idleGrip(l, right, t);
    const hold = {grip: {x: l.signX + (right ? l.signWidth : 0), y: signY - 3}, angle: right ? Math.PI : 0};
    let pose;
    if (t < a.signContact) pose = blend(idle, hold, ease(t, 0, a.signContact));
    else if (t < a.signWithdraw) pose = hold;
    else if (right) pose = blend(hold, idle, ease(t, a.signWithdraw, a.omegaContact));
    else if (t < a.omegaContact) pose = blend(hold, omega, ease(t, a.signWithdraw, a.omegaContact));
    else if (t < a.omegaWithdraw) pose = omega;
    else pose = blend(omega, idle, ease(t, a.omegaWithdraw, a.complete));
    // Contact closes the claw; release opens it while it is still at the prop.
    // The separate dwell intervals prevent either jaw change during a reach.
    const closed = (t >= a.signContact && t < a.signRelease)
      || (!right && t >= a.omegaContact && t < a.omegaRelease);
    const shoulder = {x: l.homes[Number(right)], y: l.feet - 40 * l.scale};
    const requestedWrist = end(pose.grip, -14 * l.scale, pose.angle);
    const arm = solveArm(shoulder, requestedWrist, 27 * l.scale, 24 * l.scale, right ? 1 : -1);
    return {...arm, requestedGrip: pose.grip, grip: end(arm.wrist, 14 * l.scale, pose.angle), angle: pose.angle, closed, right};
  });
  return {t, robots, sign: {x: l.signX, y: signY, width: l.signWidth, height: l.signWidth * 46 / 196,
    alpha: ease(t, 0, .8), etch: ease(t, 0, 2.6), ropes: ease(t, a.signMounted, a.signRelease)},
    omega: {x: omegaGrip.x - 4, y: omegaGrip.y - 14, alpha: ease(t, a.signWithdraw, 5.2)}};
}

// Reflected motion never escapes its box, even across a resize or a long frame.
export function reflected(value, span) {
  if (span <= 0) return 0;
  const position = ((value % (span * 2)) + span * 2) % (span * 2);
  return position < span ? position : 2 * span - position;
}

export function effectsEnabled({paused, reduced, hidden}) {
  return !paused && !reduced && !hidden;
}

export const ROBOT_DETAILS = ['sixteen-bit', 'high', 'ultra'];
export const robotDetail = value => ROBOT_DETAILS.includes(value) ? value : 'ultra';

export function floatingLogoAt(seconds, width, height) {
  const size = 72, margin = 14, top = 88;
  return {size, x: margin + reflected(width * .72 + seconds * 48, width - size - margin * 2),
    y: top + reflected(34 + seconds * 31, height - top - size - margin)};
}

// Each emission is one expanding emblem, shared by the floater and clicks.
export function logoBurstAt(age) {
  const life = clamp(age / 1.6);
  return {size: 96 + 144 * (1 - (1 - life) ** 2), alpha: (1 - life) ** 1.5 * .5};
}
