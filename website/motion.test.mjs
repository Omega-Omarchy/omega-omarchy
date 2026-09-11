import test from 'node:test';
import assert from 'node:assert/strict';
import {ASSEMBLY, layout, sceneAt, solveArm, reflected, effectsEnabled, robotDetail, floatingLogoAt, logoBurstAt} from './motion-model.mjs';

const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const close = (actual, expected, message) => assert.ok(Math.abs(actual - expected) < 1e-6, `${message}: ${actual} != ${expected}`);

for (const compact of [false, true]) {
  const l = layout(compact);
  const mode = compact ? 'compact' : 'wide';
  test(`${mode}: every grip is reachable with the game's original link lengths`, () => {
    for (let t = 0; t < ASSEMBLY.complete + 24; t += 1 / 60) {
      for (const r of sceneAt(t, l).robots) {
        close(distance(r.shoulder, r.elbow), 27 * l.scale, 'Upper arm length');
        close(distance(r.elbow, r.wrist), 24 * l.scale, 'Forearm length');
        close(distance(r.grip, r.requestedGrip), 0, `Grip drift at ${t}`);
        for (const p of [r.shoulder, r.elbow, r.wrist, r.grip]) {
          assert.ok(p.x >= 0 && p.x <= l.width && p.y >= 0 && p.y <= l.height, `Joint outside stage at ${t}`);
        }
      }
    }
  });
  test(`${mode}: the props stay attached during lifting and carrying`, () => {
    for (const t of [ASSEMBLY.signContact, ASSEMBLY.signLift, 2, 3.7, 4.2]) {
      const {robots, sign} = sceneAt(t, l);
      robots.forEach((robot, i) => {
        close(distance(robot.grip, {x: sign.x + i * sign.width, y: sign.y - 3}), 0, 'Wordmark grip');
        assert.equal(robot.closed, true);
      });
    }
    for (const t of [ASSEMBLY.omegaContact, ASSEMBLY.omegaLift, 7.5, 8.7, 9.2]) {
      const {robots, omega} = sceneAt(t, l);
      close(distance(robots[0].grip, {x: omega.x + 4, y: omega.y + 14}), 0, 'OMEGA grip');
      assert.equal(robots[0].closed, true);
    }
  });
  test(`${mode}: the signs stay installed forever, including across the former loop`, () => {
    for (const t of [ASSEMBLY.complete, 13, 17.4, 20.9, 23.99, 24, 24.01, 48, 60, 3600, 86400, 1e7]) {
      const scene = sceneAt(t, l);
      close(scene.sign.y, l.signY, 'Hanging position');
      close(scene.omega.x, l.omegaX, 'Prefix position');
      close(scene.omega.y, l.omegaY, 'Prefix height');
      assert.equal(scene.sign.alpha, 1);
      assert.equal(scene.sign.etch, 1);
      assert.equal(scene.sign.ropes, 1);
      assert.equal(scene.omega.alpha, 1);
      assert.ok(scene.robots.every(r => !r.closed));
      assert.ok(scene.robots[0].grip.x < scene.sign.x);
      assert.ok(scene.robots[1].grip.x > scene.sign.x + scene.sign.width);
    }
  });
  test(`${mode}: no prop or joint snaps at choreography boundaries or idle periods`, () => {
    for (const t of [0, ...Object.values(ASSEMBLY), 5.2, 24, 48]) {
      const a = sceneAt(t - .0001, l), b = sceneAt(t + .0001, l);
      assert.ok(distance(a.omega, b.omega) < .1, `OMEGA snaps at ${t}`);
      assert.ok(distance(a.sign, b.sign) < .1, `Sign snaps at ${t}`);
      assert.ok(Math.abs(a.sign.alpha - b.sign.alpha) < .01);
      for (let i = 0; i < 2; i++) {
        for (const key of ['elbow', 'wrist', 'grip']) assert.ok(distance(a.robots[i][key], b.robots[i][key]) < .1, `${key} snaps at ${t}`);
      }
    }
  });
  test(`${mode}: claws stay open on approach, close on contact, and open before withdrawing`, () => {
    const a = ASSEMBLY;
    for (let t = 0; t < a.complete + 1; t += .01) {
      sceneAt(t, l).robots.forEach((robot, i) => {
        const holding = (t >= a.signContact && t < a.signRelease)
          || (i === 0 && t >= a.omegaContact && t < a.omegaRelease);
        assert.equal(robot.closed, holding, `Incorrect claw state at ${t}`);
      });
    }
    for (const [i, contact, release, withdraw] of [
      [0, a.signContact, a.signRelease, a.signWithdraw],
      [1, a.signContact, a.signRelease, a.signWithdraw],
      [0, a.omegaContact, a.omegaRelease, a.omegaWithdraw],
    ]) {
      const arrival = sceneAt(contact, l);
      assert.equal(arrival.robots[i].closed, true);
      assert.equal(sceneAt(contact - .001, l).robots[i].closed, false);
      const released = sceneAt(release, l).robots[i];
      const beforeRetraction = sceneAt(withdraw - .001, l).robots[i];
      assert.equal(released.closed, false);
      assert.equal(beforeRetraction.closed, false);
      close(distance(released.grip, beforeRetraction.grip), 0, 'Claw opens at the prop before moving');
      assert.ok(distance(released.grip, sceneAt(withdraw + .3, l).robots[i].grip) > 1, 'Arm then withdraws');
    }
  });
  test(`${mode}: OMEGA uses the installer offset and both idle arms keep moving`, () => {
    close((l.omegaX - l.signX) / l.signWidth, 4 / 196, 'Installer offset');
    const a = sceneAt(13, l), b = sceneAt(14, l);
    for (let i = 0; i < 2; i++) assert.ok(distance(a.robots[i].wrist, b.robots[i].wrist) > .1);
    assert.deepEqual(a.sign, b.sign);
    assert.deepEqual(a.omega, b.omega);
  });
  test(`${mode}: the left idle is distinct without entering the sign`, () => {
    for (const t of [13, 14, 18, 24, 36]) {
      const [left, right] = sceneAt(t, l).robots;
      const mirrored = {x: l.width - right.grip.x, y: right.grip.y};
      assert.ok(distance(left.grip, mirrored) > 5, 'Independent idle gesture, including the wrist flourish');
      assert.ok(left.grip.x < l.signX);
    }
  });
}

test('Unreachable and zero-distance targets produce finite, fixed-length arms', () => {
  for (const target of [{x: 0, y: 0}, {x: 1000, y: -1000}]) {
    const r = solveArm({x: 0, y: 0}, target, 27, 24);
    close(distance(r.shoulder, r.elbow), 27, 'Upper arm length');
    close(distance(r.elbow, r.wrist), 24, 'Forearm length');
    assert.ok(r.angles.every(Number.isFinite));
  }
});

test('The bouncing artifact stays inside small and resized viewports', () => {
  for (const span of [-10, 0, 1, 280, 1920]) {
    for (const t of [-1e7, -10, 0, .5, 10, 1e7]) {
      const p = reflected(t, span);
      assert.ok(p >= 0 && p <= Math.max(0, span));
    }
  }
  close(reflected(79.999, 80), reflected(80.001, 80), 'Bounce is continuous');
});

test('Pause, reduced motion, and hidden tabs each stop the effects', () => {
  for (const paused of [false, true]) for (const reduced of [false, true]) for (const hidden of [false, true]) {
    assert.equal(effectsEnabled({paused, reduced, hidden}), !(paused || reduced || hidden));
  }
});

test('Robot detail accepts only the three actual asset tiers', () => {
  for (const detail of ['sixteen-bit', 'high', 'ultra']) assert.equal(robotDetail(detail), detail);
  for (const detail of [undefined, '../ultra', 'bogus']) assert.equal(robotDetail(detail), 'ultra');
});

test('The enlarged floater stays inside its viewport and logo bursts expire', () => {
  for (const [width, height] of [[800, 320], [1366, 768], [3840, 2160]]) {
    for (const t of [0, 7, 999.9, 1e7]) {
      const logo = floatingLogoAt(t, width, height);
      assert.equal(logo.size, 72);
      assert.ok(logo.x >= 0 && logo.x + logo.size <= width);
      assert.ok(logo.y >= 88 && logo.y + logo.size <= height);
    }
  }
  const start = logoBurstAt(0), middle = logoBurstAt(.7), end = logoBurstAt(1.6);
  assert.ok(start.size > floatingLogoAt(0, 1366, 768).size);
  assert.ok(middle.alpha < start.alpha && middle.size > start.size);
  assert.equal(end.alpha, 0);
  assert.equal(logoBurstAt(5).alpha, 0);
});
