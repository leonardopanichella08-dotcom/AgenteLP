// IA dei bot: percezione periodica, A* su griglia, strafe in combattimento,
// mira con ritardo di reazione / errore / raffiche. Riempie e.intent e ruota e.yaw/pitch.
import { BODY } from './constants.js';
import { WEAPONS } from './weapons.js';
import { COLLIDERS } from './map.js';
import { losClear, segmentFree } from './collision.js';
import { findPath, randomFreePoint } from './nav.js';
import { angleDiff, isPowerActive, isUnprepared } from './util.js';

const TURN_RATE = 5.5; // rad/s

function perceive(state, e, ai) {
  const t = state.time;
  let best = null, bestScore = Infinity, bestVisible = false;
  for (const o of state.entities) {
    if (o === e || !o.alive) continue;
    const d = Math.hypot(o.x - e.x, o.z - e.z);
    const ghost = isPowerActive(o, t, 'ghost') && d > 8;
    const visible = !ghost && d < 52 && losClear(COLLIDERS, e.x, BODY.eye, e.z, o.x, BODY.chest, o.z);
    if (ghost && ai.target !== o) continue;
    const score = d - (visible ? 14 : 0) - (o === ai.target ? 8 : 0);
    if (score < bestScore) { bestScore = score; best = o; bestVisible = visible; }
  }
  if (best !== ai.target) ai.acquiredAt = t;
  ai.target = best;
  if (bestVisible && !ai.visible) ai.acquiredAt = t; // appena visto: tempo di reazione
  ai.visible = bestVisible;
}

function followPath(e, ai, gx, gz, t) {
  const direct = Math.hypot(gx - e.x, gz - e.z) < 14 && segmentFree(COLLIDERS, e.x, e.z, gx, gz, 0.5);
  if (direct) { ai.steerX = gx; ai.steerZ = gz; return; }
  if (t >= ai.repathAt || Math.hypot(gx - ai.pathGx, gz - ai.pathGz) > 4) {
    ai.path = findPath(e.x, e.z, gx, gz);
    ai.pi = 0; ai.pathGx = gx; ai.pathGz = gz; ai.repathAt = t + 1.0;
  }
  const p = ai.path, n = p.length / 2;
  if (n === 0) { ai.steerX = gx; ai.steerZ = gz; return; }
  while (ai.pi < n - 1 && Math.hypot(p[ai.pi * 2] - e.x, p[ai.pi * 2 + 1] - e.z) < 0.9) ai.pi++;
  let best = ai.pi;
  for (let k = ai.pi + 1; k < Math.min(n, ai.pi + 7); k++) {
    if (segmentFree(COLLIDERS, e.x, e.z, p[k * 2], p[k * 2 + 1], 0.5)) best = k; else break;
  }
  ai.steerX = p[best * 2]; ai.steerZ = p[best * 2 + 1];
}

export function botThink(state, e, dt) {
  const it = e.intent, ai = e.ai, t = state.time;
  it.fire = false; it.secondary = false; it.power = false; it.reload = false; it.wx = 0; it.wz = 0;
  if (!e.alive) return;
  if (t < e.stunUntil) return;

  if (t >= ai.nextThink) { ai.nextThink = t + 0.18 + Math.random() * 0.1; perceive(state, e, ai); }
  const tgt = ai.target && ai.target.alive ? ai.target : null;
  const w = WEAPONS[e.slots[e.cur]];
  const pref = w.kind === 'gadget' ? 10 : w.prefDist;
  const unprepared = isUnprepared(state, e);

  let dist = 0, dx = 0, dz = 0;
  if (tgt) { dx = tgt.x - e.x; dz = tgt.z - e.z; dist = Math.hypot(dx, dz) || 0.001; }

  // ── movimento ──
  let mvx = 0, mvz = 0;
  if (t >= ai.navAt) {
    ai.navAt = t + 0.1;
    if (tgt && ai.visible) {
      if (t >= ai.strafeUntil) { ai.strafe = Math.random() < 0.5 ? -1 : 1; ai.strafeUntil = t + 0.8 + Math.random() * 1.6; }
      if (dist > pref + 3) followPath(e, ai, tgt.x, tgt.z, t);
      else { ai.steerX = NaN; }
    } else if (tgt) {
      followPath(e, ai, tgt.x, tgt.z, t);
    } else {
      if (!ai.hasWander || Math.hypot(ai.wanderX - e.x, ai.wanderZ - e.z) < 1.5) {
        [ai.wanderX, ai.wanderZ] = randomFreePoint(Math.random); ai.hasWander = true;
      }
      followPath(e, ai, ai.wanderX, ai.wanderZ, t);
    }
    // anti-incastro
    if (t >= ai.stuckAt) {
      if (Math.hypot(e.x - ai.stuckX, e.z - ai.stuckZ) < 0.35 && (it.wx !== 0 || it.wz !== 0)) {
        ai.repathAt = 0; ai.strafe = -ai.strafe; ai.hasWander = false;
      }
      ai.stuckX = e.x; ai.stuckZ = e.z; ai.stuckAt = t + 1.2;
    }
  }
  if (tgt && ai.visible && !(ai.steerX === ai.steerX)) {
    // nel raggio ideale: strafe, con piccola correzione di distanza
    const nx = dx / dist, nz = dz / dist;
    mvx = -nz * ai.strafe; mvz = nx * ai.strafe;
    if (dist < pref - 3) { mvx -= nx * 0.8; mvz -= nz * 0.8; }
    else if (dist > pref + 1) { mvx += nx * 0.3; mvz += nz * 0.3; }
    // non strafare contro un muro
    if (!segmentFree(COLLIDERS, e.x, e.z, e.x + mvx * 1.5, e.z + mvz * 1.5, 0.5)) { ai.strafe = -ai.strafe; mvx = -mvx; mvz = -mvz; }
  } else if (ai.steerX === ai.steerX) {
    mvx = ai.steerX - e.x; mvz = ai.steerZ - e.z;
  }
  const ml = Math.hypot(mvx, mvz);
  if (ml > 0.05) { it.wx = mvx / ml; it.wz = mvz / ml; }

  // ── mira ──
  let wantYaw, wantPitch;
  if (tgt && ai.visible) {
    if (t >= ai.noiseUntil) {
      ai.noiseUntil = t + 0.35;
      ai.noiseYaw = (Math.random() - 0.5) * 0.09; ai.noisePitch = (Math.random() - 0.5) * 0.05;
    }
    let tx = tgt.x, tz = tgt.z;
    if (w.kind === 'rocket') { const lead = (dist / w.speed) * 0.7; tx += tgt.vx * lead; tz += tgt.vz * lead; }
    wantYaw = Math.atan2(-(tx - e.x), -(tz - e.z)) + ai.noiseYaw;
    wantPitch = Math.atan2(BODY.chest - BODY.eye, dist) + ai.noisePitch;
  } else if (ml > 0.05) {
    wantYaw = Math.atan2(-it.wx, -it.wz); wantPitch = 0;
  } else { wantYaw = e.yaw; wantPitch = 0; }
  const dy = angleDiff(e.yaw, wantYaw);
  const step = TURN_RATE * dt;
  e.yaw += Math.abs(dy) < step ? dy : Math.sign(dy) * step;
  e.pitch += (wantPitch - e.pitch) * Math.min(1, dt * 8);

  // ── azioni ──
  const vis = tgt && ai.visible;
  if (vis && !unprepared && t > ai.acquiredAt + 0.3 && Math.abs(angleDiff(e.yaw, wantYaw)) < 0.1
      && dist < w.range * 0.85 && !(w.kind === 'rocket' && dist < 3.5)) {
    if (w.rate >= 4) { // armi automatiche: raffiche con pause
      if (t >= ai.burstEnd) { ai.pauseUntil = t + 0.25 + Math.random() * 0.5; ai.burstEnd = ai.pauseUntil + 0.6 + Math.random() * 1.1; }
      if (t >= ai.pauseUntil) it.fire = true;
    } else it.fire = true;
  }
  if (e.ammo[e.cur] === 0 && w.kind !== 'gadget') it.reload = true;
  else if (!vis && w.kind !== 'gadget' && e.ammo[e.cur] < w.mag * 0.5) it.reload = true;

  if (t >= ai.noiseUntil - 0.3 && vis) { // decisioni "lente": gadget / swap / potere
    const w1 = WEAPONS[e.slots[1]];
    if (w1.kind === 'gadget') {
      if (t >= e.gadgetReadyAt) {
        if (w1.gadget === 'grenade' && !unprepared && dist > 5 && dist < 16 && Math.random() < 0.04) it.secondary = true;
        if (w1.gadget === 'dash' && (dist > 10 || e.hp < 35) && Math.random() < 0.05) {
          it.secondary = true;
          const s = e.hp < 35 ? -1 : 1; it.wx = (dx / dist) * s; it.wz = (dz / dist) * s;
        }
      }
    } else if (e.ammo[e.cur] === 0 && e.ammo[1 - e.cur] > 0) it.secondary = true;
    else if (e.cur === 1 && e.ammo[0] > 0 && dist > 14) it.secondary = true;
    if (e.charge >= 100 && dist < 35) it.power = true;
  }
  if (!vis && e.cur === 1 && WEAPONS[e.slots[1]].kind !== 'gadget' && e.ammo[0] > 0) it.secondary = true;
}
