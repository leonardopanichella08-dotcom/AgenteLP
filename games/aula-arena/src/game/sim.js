// Simulazione di gioco pura (nessun import da browser/three): testabile in Node.
import { BODY, EVENT, MATCH, POWER_DURATION, WORLD, AI_SPEED_FACTOR } from './constants.js';
import { CHARACTERS } from './characters.js';
import { LOADOUTS, WEAPONS } from './weapons.js';
import { COLLIDERS, SPAWNS } from './map.js';
import { raycastWorld, rayCylinder, resolveCircle, losClear, HIT } from './collision.js';
import { botThink } from './bots.js';
import { clamp, isPowerActive, isUnprepared, nextEventGap, rand } from './util.js';

export const MAX_PROJECTILES = 24;
export const MAX_TRACERS = 48;
export const MAX_BOOMS = 10;
export const MAX_PUFFS = 32;

const magOf = (id) => (WEAPONS[id].kind === 'gadget' ? 0 : WEAPONS[id].mag);

function makeEntity(char, isPlayer, loadoutId) {
  const lo = LOADOUTS[loadoutId || char.loadout];
  return {
    id: char.id, char, isPlayer, name: char.short, color: char.color,
    x: 0, z: 0, vx: 0, vz: 0, yaw: 0, pitch: 0, speedNow: 0, walk: 0,
    hp: BODY.maxHp, alive: true, respawnAt: 0, protectUntil: 0,
    loadoutId: lo.id, slots: lo.slots, cur: 0,
    ammo: [magOf(lo.slots[0]), magOf(lo.slots[1])], reloadEnd: [0, 0],
    nextShot: 0, gadgetReadyAt: 0,
    charge: 0, powerId: char.power, powerUntil: 0,
    stunUntil: 0, dashUntil: 0, dashX: 0, dashZ: 0,
    kills: 0, deaths: 0,
    lastDamageAt: -99, hitDir: 0, hitMarkerAt: -99, killMarkerAt: -99, firedAt: -99, recoil: 0, gadgetAt: -99,
    intent: { wx: 0, wz: 0, fire: false, secondary: false, power: false, reload: false },
    ai: isPlayer ? null : { nextThink: Math.random() * 0.3, repathAt: 0, path: [], pi: 0, pathGx: 1e9, pathGz: 1e9, target: null, visible: false, acquiredAt: 0, strafe: 1, strafeUntil: 0, noiseYaw: 0, noisePitch: 0, noiseUntil: 0, pauseUntil: 0, burstEnd: 0, navAt: 0, steerX: 0, steerZ: 0, stuckX: 0, stuckZ: 0, stuckAt: 0, wanderX: 0, wanderZ: 0, hasWander: false },
  };
}

function makeFx() {
  return {
    tracers: Array.from({ length: MAX_TRACERS }, () => ({ t0: -9, n: 0, pts: new Float32Array(12), color: 0xffffff })),
    tIdx: 0,
    booms: Array.from({ length: MAX_BOOMS }, () => ({ t0: -9, x: 0, y: 0, z: 0, r: 1, kind: 0 })),
    bIdx: 0,
    puffs: Array.from({ length: MAX_PUFFS }, () => ({ t0: -9, x: 0, y: 0, z: 0, color: 0xffffff })),
    pIdx: 0,
  };
}

export function createMatch({ charId, loadoutId, eventDelay } = {}) {
  const entities = CHARACTERS.map((c) => makeEntity(c, c.id === charId, c.id === charId ? loadoutId : null));
  const player = entities.find((e) => e.isPlayer) || null;
  const state = {
    time: 0,
    entities, player,
    projectiles: Array.from({ length: MAX_PROJECTILES }, () => ({
      active: false, type: 0, owner: null, x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, born: 0, explodeAt: 0, weapon: null,
    })),
    fx: makeFx(),
    event: {
      phase: 'idle', seq: 0, nextAt: eventDelay ?? nextEventGap(),
      phaseStart: 0, phaseEnd: 0, targetId: null,
    },
    feed: [],
    over: false, result: null,
    killLimit: MATCH.killLimit, duration: MATCH.duration,
  };
  const spawns = [...SPAWNS].sort(() => Math.random() - 0.5);
  entities.forEach((e, i) => {
    const [x, z] = spawns[i % spawns.length];
    e.x = x; e.z = z;
    e.yaw = Math.atan2(-(0 - x), -(0 - z)); // guarda verso il centro
    e.protectUntil = MATCH.spawnProtect;
  });
  return state;
}

// ────────────────────────────────────────────────────────────────────────────
export function stepMatch(state, dt, input) {
  if (state.over) return;
  state.time += dt;
  updateEvent(state);

  const ents = state.entities;
  for (let i = 0; i < ents.length; i++) {
    const e = ents[i];
    if (e.isPlayer) playerIntent(state, e, input);
    else botThink(state, e, dt);
  }
  for (let i = 0; i < ents.length; i++) updateEntity(state, ents[i], dt);
  separate(ents);
  updateProjectiles(state, dt);
  checkEnd(state);
}

function playerIntent(state, p, input) {
  const it = p.intent;
  if (p.alive) {
    p.yaw -= input.lookDX * input.sens;
    p.pitch = clamp(p.pitch - input.lookDY * input.sens, -1.25, 1.25);
  }
  input.lookDX = 0; input.lookDY = 0;
  // movimento relativo alla visuale -> mondo
  const sy = Math.sin(p.yaw), cy = Math.cos(p.yaw);
  const f = input.moveY, r = input.moveX;
  it.wx = -sy * f + cy * r;
  it.wz = -cy * f - sy * r;
  const len = Math.hypot(it.wx, it.wz);
  if (len > 1) { it.wx /= len; it.wz /= len; }
  it.fire = input.fire;
  it.secondary = input.secondary; input.secondary = false;
  it.power = input.power; input.power = false;
  it.reload = input.reload; input.reload = false;
}

// ── eventi ──────────────────────────────────────────────────────────────────
function updateEvent(state) {
  const ev = state.event, t = state.time;
  if (ev.phase === 'idle') {
    if (t >= ev.nextAt) {
      ev.phase = 'spin'; ev.seq++;
      ev.phaseStart = t; ev.phaseEnd = t + EVENT.spin;
      ev.targetId = state.entities[Math.floor(Math.random() * state.entities.length)].id;
    }
  } else if (ev.phase === 'spin') {
    if (t >= ev.phaseEnd) { ev.phase = 'active'; ev.phaseStart = t; ev.phaseEnd = t + EVENT.active; }
  } else if (t >= ev.phaseEnd) {
    ev.phase = 'idle'; ev.targetId = null; ev.nextAt = t + nextEventGap();
  }
}

// ── entità ──────────────────────────────────────────────────────────────────
const scratch = { x: 0, z: 0 };

function updateEntity(state, ent, dt) {
  const t = state.time;
  if (!ent.alive) {
    if (t >= ent.respawnAt && !state.over) respawn(state, ent);
    return;
  }
  const it = ent.intent;
  const stunned = t < ent.stunUntil;
  const unprepared = isUnprepared(state, ent);

  // ricariche completate
  for (let s = 0; s < 2; s++) {
    if (ent.reloadEnd[s] > 0 && t >= ent.reloadEnd[s]) { ent.ammo[s] = magOf(ent.slots[s]); ent.reloadEnd[s] = 0; }
  }

  // potere
  const powerOn = t < ent.powerUntil;
  if (!powerOn) ent.charge = Math.min(100, ent.charge + 1.6 * dt);
  if (it.power && ent.charge >= 100 && !powerOn) {
    ent.powerUntil = t + POWER_DURATION; ent.charge = 0;
  }
  if (powerOn && ent.powerId === 'regen') ent.hp = Math.min(BODY.maxHp, ent.hp + 14 * dt);

  // movimento
  let speed = BODY.baseSpeed * (ent.isPlayer ? 1 : AI_SPEED_FACTOR);
  if (powerOn && ent.powerId === 'speed') speed *= 1.6;
  if (stunned) speed *= 0.4;
  const tvx = it.wx * speed, tvz = it.wz * speed;
  const k = Math.min(1, dt * 11);
  ent.vx += (tvx - ent.vx) * k;
  ent.vz += (tvz - ent.vz) * k;
  let mvx = ent.vx, mvz = ent.vz;
  if (t < ent.dashUntil) { mvx = ent.dashX * 17; mvz = ent.dashZ * 17; }
  scratch.x = ent.x + mvx * dt;
  scratch.z = ent.z + mvz * dt;
  resolveCircle(COLLIDERS, scratch, BODY.radius);
  const lim = WORLD.halfX - BODY.radius, limZ = WORLD.halfZ - BODY.radius;
  ent.x = clamp(scratch.x, -lim, lim);
  ent.z = clamp(scratch.z, -limZ, limZ);
  ent.speedNow = Math.hypot(mvx, mvz);
  ent.walk += ent.speedNow * dt * 1.7;
  ent.recoil = Math.max(0, ent.recoil - dt * 7);

  // azioni
  if (it.secondary && !stunned) secondaryAction(state, ent, unprepared);
  if (it.reload) startReload(state, ent);
  if (it.fire && !stunned && !unprepared) tryFire(state, ent);
}

function startReload(state, ent) {
  const s = ent.cur, w = WEAPONS[ent.slots[s]];
  if (w.kind === 'gadget' || ent.reloadEnd[s] > 0 || ent.ammo[s] >= w.mag) return;
  ent.reloadEnd[s] = state.time + w.reload;
}

function secondaryAction(state, ent, unprepared) {
  const w1 = WEAPONS[ent.slots[1]];
  if (w1.kind !== 'gadget') { ent.cur = 1 - ent.cur; return; }
  const t = state.time;
  if (t < ent.gadgetReadyAt) return;
  if (w1.gadget === 'dash') {
    let dx = ent.intent.wx, dz = ent.intent.wz;
    if (Math.hypot(dx, dz) < 0.2) { dx = -Math.sin(ent.yaw); dz = -Math.cos(ent.yaw); }
    const l = Math.hypot(dx, dz);
    ent.dashX = dx / l; ent.dashZ = dz / l; ent.dashUntil = t + 0.2;
    ent.gadgetReadyAt = t + w1.cooldown; ent.gadgetAt = t;
  } else if (w1.gadget === 'grenade' && !unprepared) {
    const cp = Math.cos(ent.pitch + 0.25);
    const p = acquireProjectile(state);
    p.type = 1; p.owner = ent; p.weapon = w1; p.born = t; p.explodeAt = t + 1.5;
    const dx = -Math.sin(ent.yaw) * cp, dy = Math.sin(ent.pitch + 0.25), dz = -Math.cos(ent.yaw) * cp;
    p.x = ent.x + dx * 0.6; p.y = BODY.eye - 0.15; p.z = ent.z + dz * 0.6;
    p.vx = dx * 15 + ent.vx * 0.5; p.vy = dy * 15; p.vz = dz * 15 + ent.vz * 0.5;
    ent.gadgetReadyAt = t + w1.cooldown; ent.gadgetAt = t;
  }
}

function acquireProjectile(state) {
  const list = state.projectiles;
  for (let i = 0; i < list.length; i++) if (!list[i].active) { list[i].active = true; return list[i]; }
  list[0].active = true; // pool esaurito: riusa il primo
  return list[0];
}

function tryFire(state, ent) {
  const t = state.time, s = ent.cur, w = WEAPONS[ent.slots[s]];
  if (w.kind === 'gadget') return;
  if (t < ent.nextShot || ent.reloadEnd[s] > 0) return;
  const rapid = isPowerActive(ent, t, 'rapid');
  if (!rapid && ent.ammo[s] <= 0) { startReload(state, ent); return; }

  ent.nextShot = t + 1 / (w.rate * (rapid ? 2 : 1));
  if (!rapid) ent.ammo[s]--;
  ent.firedAt = t;
  ent.recoil = Math.min(1.5, ent.recoil + w.recoil);

  // direzione base + (solo giocatore) assistenza alla mira per il touch
  const cp = Math.cos(ent.pitch);
  let bx = -Math.sin(ent.yaw) * cp, by = Math.sin(ent.pitch), bz = -Math.cos(ent.yaw) * cp;
  const ox = ent.x, oy = BODY.eye, oz = ent.z;
  if (ent.isPlayer) {
    const a = aimAssist(state, ent, bx, by, bz);
    if (a) { bx = a.x; by = a.y; bz = a.z; }
  }
  const spreadMul = ent.isPlayer ? 1 : 1.7;

  if (w.kind === 'rocket') {
    const p = acquireProjectile(state);
    p.type = 0; p.owner = ent; p.weapon = w; p.born = t;
    p.x = ox + bx * 0.7; p.y = oy - 0.1 + by * 0.7; p.z = oz + bz * 0.7;
    p.vx = bx * w.speed; p.vy = by * w.speed; p.vz = bz * w.speed;
    return;
  }
  const mega = isPowerActive(ent, t, 'mega') ? 2 : 1;
  const ric = isPowerActive(ent, t, 'ricochet');
  const sp = w.spread * spreadMul;
  for (let i = 0; i < w.pellets; i++) {
    let dx = bx + (Math.random() + Math.random() - 1) * sp;
    let dy = by + (Math.random() + Math.random() - 1) * sp;
    let dz = bz + (Math.random() + Math.random() - 1) * sp;
    const l = Math.hypot(dx, dy, dz);
    traceShot(state, ent, ox, oy, oz, dx / l, dy / l, dz / l, w, ric, mega);
  }
}

const assist = { x: 0, y: 0, z: 0 };
function aimAssist(state, ent, bx, by, bz) {
  let best = null, bestCos = Math.cos(0.1);
  for (let i = 0; i < state.entities.length; i++) {
    const o = state.entities[i];
    if (o === ent || !o.alive) continue;
    const dx = o.x - ent.x, dy = 1.15 - BODY.eye, dz = o.z - ent.z;
    const d = Math.hypot(dx, dy, dz);
    if (d > 45) continue;
    const c = (dx * bx + dy * by + dz * bz) / d;
    if (c > bestCos && losClear(COLLIDERS, ent.x, BODY.eye, ent.z, o.x, 1.15, o.z)) { bestCos = c; best = o; }
  }
  if (!best) return null;
  const dx = best.x - ent.x, dy = 1.15 - BODY.eye, dz = best.z - ent.z;
  const d = Math.hypot(dx, dy, dz);
  const k = 0.65;
  const ax = bx + (dx / d - bx) * k, ay = by + (dy / d - by) * k, az = bz + (dz / d - bz) * k;
  const l = Math.hypot(ax, ay, az);
  assist.x = ax / l; assist.y = ay / l; assist.z = az / l;
  return assist;
}

function pushTracer(state, ent, color) {
  const fx = state.fx, tr = fx.tracers[fx.tIdx];
  fx.tIdx = (fx.tIdx + 1) % MAX_TRACERS;
  tr.t0 = state.time; tr.n = 0; tr.color = color;
  return tr;
}
const addPt = (tr, x, y, z) => { const i = tr.n * 3; tr.pts[i] = x; tr.pts[i + 1] = y; tr.pts[i + 2] = z; tr.n++; };

function puff(state, x, y, z, color) {
  const fx = state.fx, p = fx.puffs[fx.pIdx];
  fx.pIdx = (fx.pIdx + 1) % MAX_PUFFS;
  p.t0 = state.time; p.x = x; p.y = y; p.z = z; p.color = color;
}

function traceShot(state, shooter, ox, oy, oz, dx, dy, dz, w, ric, dmgMul) {
  let range = w.range, bounces = ric ? 2 : 0;
  const tr = pushTracer(state, shooter, ric ? 0xffa94d : 0xfff2a8);
  // il tracciante parte dalla "canna": spostato lateralmente/in basso rispetto all'occhio
  const rx = Math.cos(shooter.yaw), rz = -Math.sin(shooter.yaw);
  addPt(tr, ox + rx * 0.28 + dx * 0.9, oy - 0.2 + dy * 0.9, oz + rz * 0.28 + dz * 0.9);
  for (let seg = 0; seg < 3; seg++) {
    const tw = raycastWorld(COLLIDERS, ox, oy, oz, dx, dy, dz, range);
    const nx = HIT.nx, ny = HIT.ny, nz = HIT.nz;
    let best = tw, target = null;
    const ents = state.entities;
    for (let i = 0; i < ents.length; i++) {
      const o = ents[i];
      if (o === shooter || !o.alive) continue;
      const tt = rayCylinder(ox, oy, oz, dx, dy, dz, o.x, o.z, BODY.hitRadius, 0, BODY.height, best);
      if (tt >= 0 && tt < best) { best = tt; target = o; }
    }
    const px = ox + dx * best, py = oy + dy * best, pz = oz + dz * best;
    addPt(tr, px, py, pz);
    if (target) {
      const head = py > 1.55 ? 1.5 : 1;
      applyDamage(state, target, w.damage * dmgMul * head, shooter, w);
      puff(state, px, py, pz, 0xff5a5a);
      return;
    }
    if (tw < range - 0.01) {
      puff(state, px, py, pz, 0xfff2a8);
      if (bounces > 0 && tr.n < 4) {
        const dot = dx * nx + dy * ny + dz * nz;
        dx -= 2 * dot * nx; dy -= 2 * dot * ny; dz -= 2 * dot * nz;
        ox = px + nx * 0.03; oy = py + ny * 0.03; oz = pz + nz * 0.03;
        range -= best; bounces--;
        continue;
      }
    }
    return;
  }
}

// ── danni e morti ───────────────────────────────────────────────────────────
function applyDamage(state, victim, amount, attacker, weapon) {
  const t = state.time;
  if (!victim.alive || t < victim.protectUntil) return;
  if (isPowerActive(victim, t, 'shield')) amount *= 0.25;
  victim.hp -= amount;
  victim.lastDamageAt = t;
  victim.charge = Math.min(100, victim.charge + amount * 0.12);
  if (attacker && attacker !== victim) {
    victim.hitDir = Math.atan2(attacker.x - victim.x, attacker.z - victim.z);
    attacker.hitMarkerAt = t;
    if (t >= attacker.powerUntil) attacker.charge = Math.min(100, attacker.charge + amount * 0.35);
  } else {
    victim.hitDir = victim.yaw; // danno da sé
  }
  if (victim.hp <= 0) kill(state, victim, attacker, weapon);
}

function kill(state, victim, attacker, weapon) {
  const t = state.time;
  victim.alive = false; victim.hp = 0; victim.deaths++;
  victim.respawnAt = t + MATCH.respawn;
  victim.vx = victim.vz = 0;
  victim.powerUntil = 0;
  if (attacker && attacker !== victim) {
    attacker.kills++;
    attacker.killMarkerAt = t;
    if (t >= attacker.powerUntil) attacker.charge = Math.min(100, attacker.charge + 20);
  } else if (victim.kills > 0) {
    victim.kills--; // autogol penalizza
  }
  state.feed.push({ t, killer: attacker ? attacker.name : '', killerColor: attacker ? attacker.color : '#fff', victim: victim.name, victimColor: victim.color, weapon: weapon ? weapon.name : '' });
  if (state.feed.length > 5) state.feed.shift();
}

function respawn(state, ent) {
  // spawn più lontano dai nemici vivi, con un po' di casualità fra i migliori
  const scored = SPAWNS.map(([x, z]) => {
    let m = 1e9;
    for (const o of state.entities) if (o !== ent && o.alive) m = Math.min(m, Math.hypot(o.x - x, o.z - z));
    return { x, z, m };
  }).sort((a, b) => b.m - a.m);
  const s = scored[Math.floor(Math.random() * Math.min(3, scored.length))];
  ent.x = s.x; ent.z = s.z; ent.vx = ent.vz = 0;
  ent.yaw = Math.atan2(s.x, s.z); ent.pitch = 0;
  ent.alive = true; ent.hp = BODY.maxHp;
  ent.protectUntil = state.time + MATCH.spawnProtect;
  ent.cur = 0;
  ent.ammo[0] = magOf(ent.slots[0]); ent.ammo[1] = magOf(ent.slots[1]);
  ent.reloadEnd[0] = ent.reloadEnd[1] = 0;
  ent.stunUntil = 0; ent.dashUntil = 0; ent.powerUntil = 0;
  ent.charge = Math.min(ent.charge, 60);
  if (ent.ai) { ent.ai.path = []; ent.ai.target = null; }
}

function separate(ents) {
  for (let i = 0; i < ents.length; i++) {
    const a = ents[i];
    if (!a.alive) continue;
    for (let j = i + 1; j < ents.length; j++) {
      const b = ents[j];
      if (!b.alive) continue;
      const dx = b.x - a.x, dz = b.z - a.z;
      const d2 = dx * dx + dz * dz, min = BODY.radius * 1.7;
      if (d2 < min * min && d2 > 1e-8) {
        const d = Math.sqrt(d2), push = (min - d) * 0.5 / d;
        a.x -= dx * push; a.z -= dz * push; b.x += dx * push; b.z += dz * push;
      }
    }
  }
}

// ── proiettili ──────────────────────────────────────────────────────────────
function insideSolid(x, y, z, pad) {
  for (let i = 0; i < COLLIDERS.length; i++) {
    const b = COLLIDERS[i];
    if (x > b.minX - pad && x < b.maxX + pad && y > b.minY - pad && y < b.maxY + pad && z > b.minZ - pad && z < b.maxZ + pad) return true;
  }
  return false;
}

function updateProjectiles(state, dt) {
  const t = state.time, list = state.projectiles;
  for (let i = 0; i < list.length; i++) {
    const p = list[i];
    if (!p.active) continue;
    if (p.type === 0) {
      const steps = Math.max(1, Math.ceil((p.weapon.speed * dt) / 0.3)), h = dt / steps;
      for (let s = 0; s < steps && p.active; s++) {
        p.x += p.vx * h; p.y += p.vy * h; p.z += p.vz * h;
        let boom = p.y < 0.05 || p.y > WORLD.wallH - 0.1 || insideSolid(p.x, p.y, p.z, 0.08);
        if (!boom) {
          for (let k = 0; k < state.entities.length; k++) {
            const o = state.entities[k];
            if (!o.alive || (o === p.owner && t - p.born < 0.35)) continue;
            const dx = o.x - p.x, dz = o.z - p.z;
            if (dx * dx + dz * dz < 0.5 * 0.5 && p.y > 0 && p.y < BODY.height) { boom = true; break; }
          }
        }
        if (boom) { explodeRocket(state, p); p.active = false; }
      }
      if (p.active && t - p.born > 4) p.active = false;
    } else {
      p.vy -= 18 * dt;
      let nx = p.x + p.vx * dt;
      if (insideSolid(nx, p.y, p.z, 0.12)) { p.vx *= -0.5; nx = p.x; }
      p.x = nx;
      let nz = p.z + p.vz * dt;
      if (insideSolid(p.x, p.y, nz, 0.12)) { p.vz *= -0.5; nz = p.z; }
      p.z = nz;
      let ny = p.y + p.vy * dt;
      if (ny < 0.15) { ny = 0.15; p.vy = -p.vy * 0.45; p.vx *= 0.8; p.vz *= 0.8; if (Math.abs(p.vy) < 1) p.vy = 0; }
      else if (ny > WORLD.wallH - 0.2) { ny = WORLD.wallH - 0.2; p.vy = -Math.abs(p.vy) * 0.4; }
      else if (insideSolid(p.x, ny, p.z, 0.1)) { p.vy *= -0.45; ny = p.y; }
      p.y = ny;
      if (t >= p.explodeAt) { explodeStun(state, p); p.active = false; }
    }
  }
}

function boom(state, x, y, z, r, kind) {
  const fx = state.fx, b = fx.booms[fx.bIdx];
  fx.bIdx = (fx.bIdx + 1) % MAX_BOOMS;
  b.t0 = state.time; b.x = x; b.y = y; b.z = z; b.r = r; b.kind = kind;
}

function explodeRocket(state, p) {
  const w = p.weapon, R = w.radius, mega = isPowerActive(p.owner, state.time, 'mega') ? 2 : 1;
  boom(state, p.x, p.y, p.z, R, 0);
  for (const o of state.entities) {
    if (!o.alive) continue;
    const d = Math.hypot(o.x - p.x, 0.95 - p.y, o.z - p.z);
    if (d > R + 0.4) continue;
    if (d > 0.9 && !losClear(COLLIDERS, p.x, Math.max(0.3, p.y), p.z, o.x, 0.95, o.z)) continue;
    let dmg = w.damage * mega * (1 - 0.75 * clamp(d / R, 0, 1));
    if (o === p.owner) dmg *= 0.5;
    applyDamage(state, o, dmg, p.owner, w);
  }
}

function explodeStun(state, p) {
  const w = p.weapon, R = w.radius;
  boom(state, p.x, p.y, p.z, R, 1);
  for (const o of state.entities) {
    if (!o.alive || o === p.owner) continue;
    const d = Math.hypot(o.x - p.x, 0.95 - p.y, o.z - p.z);
    if (d > R) continue;
    if (!losClear(COLLIDERS, p.x, Math.max(0.3, p.y), p.z, o.x, 0.95, o.z)) continue;
    o.stunUntil = Math.max(o.stunUntil, state.time + w.stun);
    applyDamage(state, o, w.damage * (1 - d / R), p.owner, w);
  }
}

// ── fine partita ────────────────────────────────────────────────────────────
function checkEnd(state) {
  if (state.over) return;
  let leader = null;
  for (const e2 of state.entities) if (!leader || e2.kills > leader.kills) leader = e2;
  if (leader.kills >= state.killLimit || state.time >= state.duration) {
    state.over = true;
    const ranking = [...state.entities].sort((a, b) => b.kills - a.kills || a.deaths - b.deaths);
    state.result = { winnerId: ranking[0].id, ranking: ranking.map((r) => ({ id: r.id, name: r.char.name, color: r.color, kills: r.kills, deaths: r.deaths, isPlayer: r.isPlayer })) };
  }
}
