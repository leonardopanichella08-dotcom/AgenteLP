// Test headless: 7 bot si sfidano per N secondi. Verifica NaN, uccisioni, evento Interrogazione.
import { createMatch, stepMatch } from '../src/game/sim.js';
import { COLLIDERS } from '../src/game/map.js';
import { circleFree } from '../src/game/collision.js';

const SECONDS = Number(process.argv[2] || 200);
const state = createMatch({ charId: null, loadoutId: null, eventDelay: 20 });
state.duration = 1e9; state.killLimit = 1e9;
const input = { moveX: 0, moveY: 0, lookDX: 0, lookDY: 0, fire: false, secondary: false, power: false, reload: false, sens: 0.005 };

let phases = new Set(), maxProj = 0, nan = 0, stuckInside = 0, illegalShots = 0, targetShots = 0, activeFrames = 0;
const dt = 1 / 60;
const t0 = performance.now();
for (let i = 0; i < SECONDS * 60; i++) {
  stepMatch(state, dt, input);
  phases.add(state.event.phase);
  const ev = state.event;
  maxProj = Math.max(maxProj, state.projectiles.filter((p) => p.active).length);
  for (const e of state.entities) {
    if (![e.x, e.z, e.yaw, e.pitch, e.hp, e.charge].every(Number.isFinite)) nan++;
    if (e.alive && !circleFree(COLLIDERS, e.x, e.z, 0.3)) stuckInside++;
    if (ev.phase === 'active' && e.firedAt === state.time) { if (e.id === ev.targetId) targetShots++; else illegalShots++; }
  }
}
const ms = performance.now() - t0;
console.log(`simulati ${SECONDS}s in ${ms.toFixed(0)}ms (${(ms / (SECONDS * 60)).toFixed(3)} ms/frame)`);
console.log('fasi evento viste:', [...phases].join(','), '| seq', state.event.seq);
console.log('Interrogazione: colpi dell\'interrogato', targetShots, '| colpi ILLEGALI degli impreparati', illegalShots);
console.log('NaN:', nan, '| frame con entità dentro un muro:', stuckInside, '| max proiettili:', maxProj);
for (const e of state.entities) console.log(e.name.padEnd(11), e.loadoutId.padEnd(8), 'K', String(e.kills).padStart(3), 'D', String(e.deaths).padStart(3), 'pos', e.x.toFixed(1), e.z.toFixed(1));
const totalK = state.entities.reduce((a, e) => a + e.kills, 0);
if (nan || totalK < 5 || illegalShots > 0 || stuckInside > 0) { console.error('FALLITO'); process.exit(1); }
console.log('OK');
