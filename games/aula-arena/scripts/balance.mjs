// Bilanciamento: kill/morti medi per loadout su più partite bot-vs-bot.
import { createMatch, stepMatch } from '../src/game/sim.js';
const RUNS = Number(process.argv[2] || 8), SECONDS = Number(process.argv[3] || 300);
const input = { moveX: 0, moveY: 0, lookDX: 0, lookDY: 0, fire: false, secondary: false, power: false, reload: false, sens: 0.005 };
const agg = {}, aggC = {};
for (let r = 0; r < RUNS; r++) {
  const s = createMatch({ charId: null, eventDelay: 30 });
  s.duration = 1e9; s.killLimit = 1e9;
  for (let i = 0; i < SECONDS * 60; i++) stepMatch(s, 1 / 60, input);
  for (const e of s.entities) {
    const a = (agg[e.loadoutId] ??= { k: 0, d: 0, n: 0 }); a.k += e.kills; a.d += e.deaths; a.n++;
    const c = (aggC[e.id] ??= { k: 0, d: 0, n: 0, p: e.powerId }); c.k += e.kills; c.d += e.deaths; c.n++;
  }
}
const fmt = (o) => Object.entries(o).map(([k, v]) => `${k.padEnd(11)} K/gioc ${(v.k / v.n).toFixed(1).padStart(5)}  D/gioc ${(v.d / v.n).toFixed(1).padStart(5)}  K/D ${(v.k / Math.max(1, v.d)).toFixed(2)}`).join('\n');
console.log('— per loadout —\n' + fmt(agg) + '\n— per personaggio —\n' + fmt(aggC));
