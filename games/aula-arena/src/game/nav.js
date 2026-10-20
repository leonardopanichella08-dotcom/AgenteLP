// Griglia di navigazione + A* per i bot. Passo 1m, spazio libero calcolato dai collider.
import { WORLD } from './constants.js';
import { COLLIDERS } from './map.js';
import { circleFree } from './collision.js';

const STEP = 1;
const CLEAR = 0.58;
const W = Math.floor((2 * WORLD.halfX) / STEP);
const H = Math.floor((2 * WORLD.halfZ) / STEP);
const X0 = -WORLD.halfX + STEP / 2;
const Z0 = -WORLD.halfZ + STEP / 2;

const free = new Uint8Array(W * H);
for (let iz = 0; iz < H; iz++) {
  for (let ix = 0; ix < W; ix++) {
    free[iz * W + ix] = circleFree(COLLIDERS, X0 + ix * STEP, Z0 + iz * STEP, CLEAR) ? 1 : 0;
  }
}

export const NAV = { W, H, free, nodeX: (ix) => X0 + ix * STEP, nodeZ: (iz) => Z0 + iz * STEP };

const clampI = (v, max) => (v < 0 ? 0 : v > max ? max : v);
const toIx = (x) => clampI(Math.round((x - X0) / STEP), W - 1);
const toIz = (z) => clampI(Math.round((z - Z0) / STEP), H - 1);

/** Indice del nodo libero più vicino a (x,z), -1 se nessuno entro 8 celle. */
export function nearestNode(x, z) {
  const cx = toIx(x), cz = toIz(z);
  if (free[cz * W + cx]) return cz * W + cx;
  for (let r = 1; r <= 8; r++) {
    let best = -1, bd = Infinity;
    for (let dz = -r; dz <= r; dz++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dz)) !== r) continue;
        const ix = cx + dx, iz = cz + dz;
        if (ix < 0 || iz < 0 || ix >= W || iz >= H) continue;
        const i = iz * W + ix;
        if (!free[i]) continue;
        const d = dx * dx + dz * dz;
        if (d < bd) { bd = d; best = i; }
      }
    }
    if (best >= 0) return best;
  }
  return -1;
}

// ── A* con heap binario (buffer riusati: nessuna allocazione per ricerca) ──
const N = W * H;
const g = new Float32Array(N);
const parent = new Int32Array(N);
const stamp = new Uint32Array(N);
let curStamp = 0;
const heapNode = new Int32Array(N * 4);
const heapF = new Float32Array(N * 4);
let heapSize = 0;

function push(node, f) {
  let i = heapSize++;
  while (i > 0) {
    const p = (i - 1) >> 1;
    if (heapF[p] <= f) break;
    heapF[i] = heapF[p]; heapNode[i] = heapNode[p];
    i = p;
  }
  heapF[i] = f; heapNode[i] = node;
}
function pop() {
  const top = heapNode[0];
  const f = heapF[--heapSize], node = heapNode[heapSize];
  let i = 0;
  for (;;) {
    let c = i * 2 + 1;
    if (c >= heapSize) break;
    if (c + 1 < heapSize && heapF[c + 1] < heapF[c]) c++;
    if (heapF[c] >= f) break;
    heapF[i] = heapF[c]; heapNode[i] = heapNode[c];
    i = c;
  }
  heapF[i] = f; heapNode[i] = node;
  return top;
}

const DX = [1, -1, 0, 0, 1, 1, -1, -1];
const DZ = [0, 0, 1, -1, 1, -1, 1, -1];

/** Percorso da (sx,sz) a (gx,gz) come array piatto [x0,z0,x1,z1,...] (vuoto se irraggiungibile). */
export function findPath(sx, sz, gx, gz) {
  const s = nearestNode(sx, sz), t = nearestNode(gx, gz);
  if (s < 0 || t < 0) return [];
  const tx = t % W, tz = (t / W) | 0;
  curStamp++;
  heapSize = 0;
  stamp[s] = curStamp; g[s] = 0; parent[s] = -1;
  push(s, 0);
  let found = false;
  while (heapSize > 0) {
    const cur = pop();
    if (cur === t) { found = true; break; }
    const cx = cur % W, cz = (cur / W) | 0;
    const gc = g[cur];
    for (let k = 0; k < 8; k++) {
      const nx = cx + DX[k], nz = cz + DZ[k];
      if (nx < 0 || nz < 0 || nx >= W || nz >= H) continue;
      const ni = nz * W + nx;
      if (!free[ni]) continue;
      if (k >= 4 && (!free[cz * W + nx] || !free[nz * W + cx])) continue; // niente tagli d'angolo
      const ng = gc + (k < 4 ? 1 : 1.4142);
      if (stamp[ni] === curStamp && ng >= g[ni]) continue;
      stamp[ni] = curStamp; g[ni] = ng; parent[ni] = cur;
      const hx = Math.abs(nx - tx), hz = Math.abs(nz - tz);
      push(ni, ng + (hx + hz) + (1.4142 - 2) * Math.min(hx, hz));
    }
  }
  if (!found) return [];
  const rev = [];
  for (let n = t; n !== -1; n = parent[n]) rev.push(X0 + (n % W) * STEP, Z0 + ((n / W) | 0) * STEP);
  const out = new Array(rev.length);
  for (let i = 0; i < rev.length; i += 2) {
    out[rev.length - 2 - i] = rev[i];
    out[rev.length - 1 - i] = rev[i + 1];
  }
  return out;
}

/** Nodo libero casuale (per vagare). */
export function randomFreePoint(rand) {
  for (let i = 0; i < 40; i++) {
    const ix = Math.floor(rand() * W), iz = Math.floor(rand() * H);
    if (free[iz * W + ix]) return [X0 + ix * STEP, Z0 + iz * STEP];
  }
  return [0, 0];
}
