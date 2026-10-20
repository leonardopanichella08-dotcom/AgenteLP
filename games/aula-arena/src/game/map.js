// Mappa "Scuola": aula centrale + anello di corridoi/stanze (biblioteca, mensa,
// spogliatoio, palestra). Solo dati: `MAP_BOXES` per il render, `COLLIDERS` per la fisica.
import { WORLD } from './constants.js';

const { halfX: HX, halfZ: HZ, wallH: WH } = WORLD;

export const MAP_BOXES = [];
export const COLLIDERS = [];

const P = {
  wall: '#fff0d4', band: '#4cc9b0', wallDark: '#ffe2b0', trim: '#ff7a59',
  wood: '#c98a4b', woodLight: '#e7b36a', ink: '#2c3354',
  desk: ['#ffcf5a', '#7ad7f0'], deskBody: ['#ff8a5c', '#5aa9ff'],
  locker: ['#3a86ff', '#2ec4b6', '#ff9f1c', '#ff5d8f'],
  books: ['#ff5d5d', '#ffd23f', '#3bceac', '#5aa9ff', '#c77dff', '#ff9f43', '#f8f4e3'],
  green: '#2f7d6b', white: '#ffffff', red: '#ff5252', blue: '#4d8dff',
};

function box(x, y, z, w, h, d, color, { solid = true, round = 0, shape = 'box' } = {}) {
  MAP_BOXES.push({ x, y, z, w, h, d, color, round, shape });
  if (solid) {
    COLLIDERS.push({
      minX: x - w / 2, maxX: x + w / 2, minY: y - h / 2, maxY: y + h / 2, minZ: z - d / 2, maxZ: z + d / 2,
    });
  }
}
// appoggiato a terra: (x,z) centro, h altezza
const grounded = (x, z, w, h, d, color, opt) => box(x, h / 2, z, w, h, d, color, opt);
function cyl(x, z, r, h, color, { solid = true, y0 = 0 } = {}) {
  MAP_BOXES.push({ x, y: y0 + h / 2, z, w: r * 2, h, d: r * 2, r, color, round: 0, shape: 'cyl' });
  if (solid) COLLIDERS.push({ minX: x - r, maxX: x + r, minY: y0, maxY: y0 + h, minZ: z - r, maxZ: z + r });
}
function ball(x, y, z, r, color, { solid = false } = {}) {
  MAP_BOXES.push({ x, y, z, w: r * 2, h: r * 2, d: r * 2, r, color, round: 0, shape: 'sphere' });
  if (solid) COLLIDERS.push({ minX: x - r, maxX: x + r, minY: y - r, maxY: y + r, minZ: z - r, maxZ: z + r });
}

// ── pseudo-random deterministico (mappa identica a ogni avvio) ──────────────
let seed = 7;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const pick = (arr) => arr[Math.floor(rnd() * arr.length)];

// ── Muri esterni ───────────────────────────────────────────────────────────
function outerWalls() {
  const T = 0.6;
  grounded(0, -HZ - T / 2, 2 * HX + 2 * T, WH, T, P.wall);
  grounded(0, HZ + T / 2, 2 * HX + 2 * T, WH, T, P.wall);
  grounded(-HX - T / 2, 0, T, WH, 2 * HZ, P.wall);
  grounded(HX + T / 2, 0, T, WH, 2 * HZ, P.wall);
  // fascia colorata (zoccolo) + cornice alta
  const b = 0.05;
  grounded(0, -HZ + b, 2 * HX, 1.1, 0.1, P.band, { solid: false });
  grounded(0, HZ - b, 2 * HX, 1.1, 0.1, P.band, { solid: false });
  grounded(-HX + b, 0, 0.1, 1.1, 2 * HZ, P.band, { solid: false });
  grounded(HX - b, 0, 0.1, 1.1, 2 * HZ, P.band, { solid: false });
  box(0, WH - 0.3, -HZ + b, 2 * HX, 0.5, 0.1, P.trim, { solid: false });
  box(0, WH - 0.3, HZ - b, 2 * HX, 0.5, 0.1, P.trim, { solid: false });
  box(-HX + b, WH - 0.3, 0, 0.1, 0.5, 2 * HZ, P.trim, { solid: false });
  box(HX - b, WH - 0.3, 0, 0.1, 0.5, 2 * HZ, P.trim, { solid: false });
  // finestre cartoon sui muri lunghi
  for (let x = -24; x <= 24; x += 12) {
    for (const z of [-HZ + 0.06, HZ - 0.06]) {
      box(x, 3.5, z, 3.2, 1.8, 0.08, '#9fe3ff', { solid: false });
      box(x, 3.5, z, 3.5, 0.18, 0.1, P.wood, { solid: false });
      box(x, 3.5, z, 0.18, 2.1, 0.1, P.wood, { solid: false });
    }
  }
}

// ── Aula centrale ──────────────────────────────────────────────────────────
const AX = 12, AZ = 9, DOOR = 2.6;

function aulaWalls() {
  const T = 0.6;
  // nord pieno
  grounded(0, -AZ, 2 * AX + T, WH, T, P.wallDark);
  // ovest/est con porta centrale
  for (const sx of [-1, 1]) {
    const len = AZ - DOOR;
    grounded(sx * AX, -(DOOR + len / 2), T, WH, len, P.wallDark);
    grounded(sx * AX, DOOR + len / 2, T, WH, len, P.wallDark);
    box(sx * AX, 5.1, 0, T, 1.8, 2 * DOOR, P.trim, { solid: false }); // architrave
  }
  // sud con porta centrale
  const lenS = AX - DOOR;
  grounded(-(DOOR + lenS / 2), AZ, lenS, WH, T, P.wallDark);
  grounded(DOOR + lenS / 2, AZ, lenS, WH, T, P.wallDark);
  box(0, 5.1, AZ, 2 * DOOR, 1.8, T, P.trim, { solid: false });
  // zoccolo colorato interno/esterno
  for (const sx of [-1, 1]) {
    grounded(sx * (AX - 0.33), -(DOOR + (AZ - DOOR) / 2), 0.08, 1.0, AZ - DOOR, P.trim, { solid: false });
    grounded(sx * (AX - 0.33), DOOR + (AZ - DOOR) / 2, 0.08, 1.0, AZ - DOOR, P.trim, { solid: false });
  }
}

function desk(cx, cz, ci) {
  const w = 3.0, d = 1.5;
  // collider unico (via fisica) + resa a pezzi
  COLLIDERS.push({ minX: cx - w / 2, maxX: cx + w / 2, minY: 0, maxY: 1.35, minZ: cz - d / 2, maxZ: cz + d / 2 });
  box(cx, 1.26, cz, w, 0.18, d, P.desk[ci], { solid: false, round: 0.07 });
  for (const sx of [-1, 1]) box(cx + sx * (w / 2 - 0.12), 0.58, cz, 0.22, 1.16, d - 0.1, P.deskBody[ci], { solid: false, round: 0.06 });
  box(cx, 0.8, cz - d / 2 + 0.14, w - 0.4, 0.8, 0.14, P.deskBody[ci], { solid: false, round: 0.05 });
  // materiale sul banco
  box(cx - 0.8, 1.42, cz + 0.1, 0.7, 0.14, 0.5, pick(P.books), { solid: false, round: 0.03 });
  box(cx + 0.5, 1.37, cz + 0.2, 0.5, 0.06, 0.4, P.white, { solid: false });
  cyl(cx + 1.0, cz - 0.3, 0.1, 0.22, pick(P.books), { solid: false, y0: 1.35 });
}

function aula() {
  aulaWalls();
  // lavagna
  box(0, 3.1, -AZ + 0.36, 10, 2.4, 0.1, P.green, { solid: false });
  box(0, 3.1, -AZ + 0.33, 10.5, 2.9, 0.08, P.wood, { solid: false });
  box(0, 1.85, -AZ + 0.5, 9, 0.12, 0.3, P.woodLight, { solid: false });
  for (let i = 0; i < 4; i++) box(-3 + i * 1.2, 1.97, -AZ + 0.52, 0.5, 0.06, 0.1, P.white, { solid: false });
  // doppia lavagna laterale + orologio
  cyl(7.7, -AZ + 0.4, 0.5, 0.08, P.white, { solid: false, y0: 4.3 });
  // cattedra + pedana
  grounded(0, -AZ + 2.4, 9, 0.18, 4.4, P.trim, { solid: false });
  grounded(0, -6.9, 4.6, 1.5, 1.5, P.wood, { round: 0.1 });
  box(0, 1.55, -6.9, 4.9, 0.14, 1.75, P.woodLight, { solid: false, round: 0.05 });
  ball(-1.6, 1.95, -6.9, 0.38, P.blue);
  box(1.3, 1.7, -6.8, 0.8, 0.16, 0.6, P.red, { solid: false, round: 0.03 });
  // banchi giganti
  for (const [ci, cx] of [[0, -9.1], [1, -5.0], [0, 5.0], [1, 9.1]]) {
    for (const cz of [-3, 0.6, 4.2]) desk(cx, cz, ci);
  }
  // tappeto
  cyl(0, 3, 2.4, 0.04, '#ff9aa2', { solid: false });
  // armadietto materiale vicino alla parete ovest
  grounded(-AX + 0.7, -7.6, 1.0, 2.8, 2.0, P.locker[2], { round: 0.08 });
  grounded(AX - 0.7, 7.6, 1.0, 2.8, 2.0, P.locker[0], { round: 0.08 });
}

// ── Ambienti dell'anello ───────────────────────────────────────────────────
function bookshelf(cx, cz, len, alongX = true) {
  const w = alongX ? len : 1.0, d = alongX ? 1.0 : len;
  grounded(cx, cz, w, 3.4, d, P.wood, { round: 0.08 });
  // dorsi dei libri su entrambe le facce lunghe (strisce colorate)
  const n = Math.floor(len / 0.9);
  for (let r = 0; r < 3; r++) {
    for (let i = 0; i < n; i++) {
      const off = -len / 2 + 0.5 + i * (len - 1) / Math.max(1, n - 1);
      const y = 0.85 + r * 1.05;
      for (const side of [-1, 1]) {
        const bx = alongX ? cx + off : cx + side * (w / 2 + 0.01);
        const bz = alongX ? cz + side * (d / 2 + 0.01) : cz + off;
        box(bx, y, bz, alongX ? 0.62 : 0.04, 0.7, alongX ? 0.04 : 0.62, pick(P.books), { solid: false });
      }
    }
  }
}

function lockerBank(cx, cz, len, alongX = true) {
  const w = alongX ? len : 1.2, d = alongX ? 1.2 : len;
  grounded(cx, cz, w, 2.7, d, P.locker[0], { round: 0.08 });
  const n = Math.floor(len / 1.4);
  for (let i = 0; i < n; i++) {
    const off = -len / 2 + 0.7 + i * 1.4;
    const col = P.locker[i % P.locker.length];
    for (const side of [-1, 1]) {
      const bx = alongX ? cx + off : cx + side * (w / 2 + 0.02);
      const bz = alongX ? cz + side * (d / 2 + 0.02) : cz + off;
      box(bx, 1.35, bz, alongX ? 1.25 : 0.06, 2.5, alongX ? 0.06 : 1.25, col, { solid: false });
      box(bx, 1.6, bz, alongX ? 0.5 : 0.1, 0.08, alongX ? 0.1 : 0.5, P.white, { solid: false });
    }
  }
}

function canteenTable(cx, cz, len) {
  grounded(cx, cz, len, 1.2, 1.8, P.woodLight, { round: 0.1 });
  box(cx, 1.25, cz, len + 0.2, 0.12, 2.0, P.wood, { solid: false, round: 0.05 });
  for (const s of [-1, 1]) grounded(cx, cz + s * 1.55, len, 0.55, 0.5, P.trim, { solid: false, round: 0.05 });
  for (let i = 0; i < 3; i++) cyl(cx - len / 3 + i * (len / 3), cz, 0.28, 0.1, pick(P.books), { solid: false, y0: 1.31 });
}

function pillar(cx, cz, r = 0.75, color = P.blue) {
  cyl(cx, cz, r, WH, color);
  cyl(cx, cz, r + 0.12, 0.5, P.trim, { solid: false });
}

function ringRooms() {
  // NW — Biblioteca
  bookshelf(-24, -17, 7, true);
  bookshelf(-24, -13, 7, true);
  bookshelf(-17, -19, 6, false);
  bookshelf(-16.5, -13, 5, false);
  bookshelf(-27, -20.4, 5, true);
  cyl(-20.5, -10.7, 1.3, 1.0, P.woodLight);
  cyl(-20.5, -10.7, 1.45, 0.1, P.wood, { solid: false, y0: 1.0 });
  for (const [sx, sz] of [[-22.2, -10.7], [-18.8, -10.7]]) cyl(sx, sz, 0.35, 0.65, P.trim);

  // NE — Mensa
  canteenTable(22, -18, 7);
  canteenTable(22, -13.4, 7);
  grounded(26.5, -20.9, 6, 1.3, 1.5, P.band, { round: 0.1 }); // bancone self-service
  box(26.5, 1.45, -20.9, 6.2, 0.14, 1.7, P.white, { solid: false, round: 0.04 });
  grounded(14.3, -16, 1.0, 3.0, 5.0, P.locker[1], { round: 0.08 }); // frigoriferi
  cyl(16.5, -11.2, 0.5, 1.0, P.green); // cestino

  // SW — Spogliatoio
  lockerBank(-24, 15, 6.4, true);
  lockerBank(-24, 19.2, 6.4, true);
  lockerBank(-15.8, 17, 6.4, false);
  grounded(-20, 11.3, 4.2, 0.6, 1.0, P.trim, { round: 0.06 }); // panca

  // SE — Palestra
  grounded(21.5, 14.2, 2.4, 1.3, 2.4, P.red, { round: 0.1 });
  grounded(24.3, 14.2, 2.4, 2.0, 2.4, P.blue, { round: 0.1 });
  grounded(24.3, 17.4, 2.4, 2.7, 2.4, P.locker[2], { round: 0.1 });
  ball(17.5, 1.0, 17.8, 1.0, '#ff7043', { solid: true });
  grounded(26.5, 11.2, 5.0, 0.18, 3.0, '#6fd08c', { solid: false }); // materassino
  grounded(15.5, 12.0, 1.0, 1.2, 4.6, P.trim, { round: 0.08 });
  // canestro
  cyl(HX - 1, 20.3, 0.1, 3.2, P.ink, { solid: false });
  box(HX - 1.1, 3.6, 20.3, 0.1, 1.1, 1.7, P.white, { solid: false });

  // Corridoio ovest
  pillar(-20, -4.2); pillar(-20, 4.2);
  grounded(-28.2, 0, 1.2, 0.7, 4.4, P.locker[3], { round: 0.08 });
  // Corridoio est — bacheche dei trofei
  grounded(20.2, -4.6, 1.2, 2.0, 3.2, P.woodLight, { round: 0.08 });
  box(19.55, 1.2, -4.6, 0.06, 1.6, 2.8, '#9fe3ff', { solid: false });
  grounded(20.2, 4.6, 1.2, 2.0, 3.2, P.woodLight, { round: 0.08 });
  box(19.55, 1.2, 4.6, 0.06, 1.6, 2.8, '#9fe3ff', { solid: false });
  pillar(27, -4.2, 0.75, P.locker[2]); pillar(27, 4.2, 0.75, P.locker[2]);

  // Corridoio nord — segreteria
  grounded(0, -16, 6.4, 1.3, 1.5, P.trim, { round: 0.1 });
  box(0, 1.35, -16, 6.7, 0.14, 1.8, P.white, { solid: false, round: 0.04 });
  pillar(-8.5, -14.5); pillar(8.5, -14.5);
  // Corridoio sud — bidelli + distributori
  grounded(0, 15.8, 6.4, 1.3, 1.5, P.band, { round: 0.1 });
  box(0, 1.35, 15.8, 6.7, 0.14, 1.8, P.white, { solid: false, round: 0.04 });
  grounded(-6.5, 20.6, 1.4, 2.4, 1.3, P.locker[3], { round: 0.1 });
  grounded(6.5, 20.6, 1.4, 2.4, 1.3, P.locker[0], { round: 0.1 });
  pillar(-8.5, 13.5); pillar(8.5, 13.5);
}

function ceiling() {
  box(0, WH + 0.1, 0, 2 * HX + 1.2, 0.2, 2 * HZ + 1.2, '#fff6e6', { solid: false });
  for (let x = -24; x <= 24; x += 12) {
    for (let z = -16; z <= 16; z += 8) box(x, WH - 0.04, z, 4.2, 0.1, 0.9, '#fffbe0', { solid: false });
  }
}

outerWalls();
aula();
ringRooms();
ceiling();

// Pavimento gestito dal render (texture a scacchi), non è un box.
export const FLOOR = { w: 2 * HX, d: 2 * HZ, c1: '#f8ebc8', c2: '#f1d9a3' };

// Punti di respawn (verificati da scripts/simtest.mjs).
export const SPAWNS = [
  [-25.5, 0], [27, 0], [0, -19.5], [0, 19.5],
  [-19, -15], [19, -15], [-19, 15], [19, 15],
  [-2, 2], [2, -3],
];
