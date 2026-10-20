import { EVENT } from './constants.js';

export const rand = (a, b) => a + Math.random() * (b - a);
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

/** Differenza angolare normalizzata in [-PI, PI]. */
export function angleDiff(a, b) {
  let d = (b - a) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  else if (d < -Math.PI) d += Math.PI * 2;
  return d;
}

export const isPowerActive = (e, t, id) => t < e.powerUntil && (!id || e.powerId === id);

/** "Impreparato": durante l'Interrogazione tutti tranne l'interrogato. */
export const isUnprepared = (state, e) =>
  state.event.phase === 'active' && state.event.targetId !== e.id;

export const nextEventGap = () => rand(EVENT.minGap, EVENT.maxGap);
