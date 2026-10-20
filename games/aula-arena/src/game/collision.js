// Collisioni: cerchio-vs-AABB (movimento), raggio-vs-AABB e raggio-vs-cilindro (proiettili).
// Nessuna allocazione nei percorsi caldi: i risultati secondari finiscono in HIT.

export const HIT = { nx: 0, ny: 0, nz: 0 };

/** Spinge fuori (x,z) dal bordo di ogni collider. Muta `pos` ({x,z}). Ritorna true se ha corretto. */
export function resolveCircle(colliders, pos, r) {
  let hit = false;
  for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i < colliders.length; i++) {
      const b = colliders[i];
      const cx = pos.x < b.minX ? b.minX : pos.x > b.maxX ? b.maxX : pos.x;
      const cz = pos.z < b.minZ ? b.minZ : pos.z > b.maxZ ? b.maxZ : pos.z;
      const dx = pos.x - cx;
      const dz = pos.z - cz;
      const d2 = dx * dx + dz * dz;
      if (d2 >= r * r) continue;
      hit = true;
      if (d2 > 1e-8) {
        const d = Math.sqrt(d2);
        const k = (r - d) / d;
        pos.x += dx * k;
        pos.z += dz * k;
      } else {
        // centro dentro il box: esci dal lato più vicino
        const l = pos.x - b.minX, rr = b.maxX - pos.x, t = pos.z - b.minZ, bt = b.maxZ - pos.z;
        const m = Math.min(l, rr, t, bt);
        if (m === l) pos.x = b.minX - r;
        else if (m === rr) pos.x = b.maxX + r;
        else if (m === t) pos.z = b.minZ - r;
        else pos.z = b.maxZ + r;
      }
    }
  }
  return hit;
}

/** True se un cerchio di raggio r in (x,z) non tocca alcun collider. */
export function circleFree(colliders, x, z, r) {
  for (let i = 0; i < colliders.length; i++) {
    const b = colliders[i];
    const cx = x < b.minX ? b.minX : x > b.maxX ? b.maxX : x;
    const cz = z < b.minZ ? b.minZ : z > b.maxZ ? b.maxZ : z;
    const dx = x - cx, dz = z - cz;
    if (dx * dx + dz * dz < r * r) return false;
  }
  return true;
}

/** Segmento (x1,z1)->(x2,z2) percorribile da un cerchio di raggio r? Campiona ogni ~0.4m. */
export function segmentFree(colliders, x1, z1, x2, z2, r) {
  const dx = x2 - x1, dz = z2 - z1;
  const len = Math.sqrt(dx * dx + dz * dz);
  const n = Math.max(1, Math.ceil(len / 0.4));
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    if (!circleFree(colliders, x1 + dx * t, z1 + dz * t, r)) return false;
  }
  return true;
}

/** Raggio vs AABB (metodo slab). Ritorna t d'ingresso o -1. Normale in HIT. */
export function rayAABB(ox, oy, oz, dx, dy, dz, b, maxT) {
  let tmin = 0, tmax = maxT;
  let nx = 0, ny = 0, nz = 0;

  if (Math.abs(dx) < 1e-9) {
    if (ox < b.minX || ox > b.maxX) return -1;
  } else {
    const inv = 1 / dx;
    let t1 = (b.minX - ox) * inv, t2 = (b.maxX - ox) * inv, s = -1;
    if (t1 > t2) { const tt = t1; t1 = t2; t2 = tt; s = 1; }
    if (t1 > tmin) { tmin = t1; nx = s; ny = 0; nz = 0; }
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return -1;
  }
  if (Math.abs(dy) < 1e-9) {
    if (oy < b.minY || oy > b.maxY) return -1;
  } else {
    const inv = 1 / dy;
    let t1 = (b.minY - oy) * inv, t2 = (b.maxY - oy) * inv, s = -1;
    if (t1 > t2) { const tt = t1; t1 = t2; t2 = tt; s = 1; }
    if (t1 > tmin) { tmin = t1; nx = 0; ny = s; nz = 0; }
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return -1;
  }
  if (Math.abs(dz) < 1e-9) {
    if (oz < b.minZ || oz > b.maxZ) return -1;
  } else {
    const inv = 1 / dz;
    let t1 = (b.minZ - oz) * inv, t2 = (b.maxZ - oz) * inv, s = -1;
    if (t1 > t2) { const tt = t1; t1 = t2; t2 = tt; s = 1; }
    if (t1 > tmin) { tmin = t1; nx = 0; ny = 0; nz = s; }
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return -1;
  }
  HIT.nx = nx; HIT.ny = ny; HIT.nz = nz;
  return tmin;
}

/** Primo impatto del raggio con il mondo. Ritorna t (o maxT se libero). Normale in HIT. */
export function raycastWorld(colliders, ox, oy, oz, dx, dy, dz, maxT) {
  let best = maxT, nx = 0, ny = 0, nz = 0;
  for (let i = 0; i < colliders.length; i++) {
    const t = rayAABB(ox, oy, oz, dx, dy, dz, colliders[i], best);
    if (t >= 0 && t < best) { best = t; nx = HIT.nx; ny = HIT.ny; nz = HIT.nz; }
  }
  // pavimento
  if (dy < -1e-9) {
    const t = -oy / dy;
    if (t >= 0 && t < best) { best = t; nx = 0; ny = 1; nz = 0; }
  }
  HIT.nx = nx; HIT.ny = ny; HIT.nz = nz;
  return best;
}

/** Raggio vs cilindro verticale (asse Y) centrato in (cx,cz). Ritorna t o -1. */
export function rayCylinder(ox, oy, oz, dx, dy, dz, cx, cz, r, y0, y1, maxT) {
  const fx = ox - cx, fz = oz - cz;
  const a = dx * dx + dz * dz;
  if (a < 1e-9) return -1;
  const b = 2 * (fx * dx + fz * dz);
  const c = fx * fx + fz * fz - r * r;
  const disc = b * b - 4 * a * c;
  if (disc < 0) return -1;
  const sq = Math.sqrt(disc);
  let t = (-b - sq) / (2 * a);
  if (t < 0) {
    t = (-b + sq) / (2 * a); // origine dentro il cilindro
    if (t < 0) return -1;
  }
  if (t > maxT) return -1;
  const y = oy + dy * t;
  if (y < y0 || y > y1) return -1;
  return t;
}

/** Linea di vista libera tra due punti (solo mondo). */
export function losClear(colliders, ax, ay, az, bx, by, bz) {
  const dx = bx - ax, dy = by - ay, dz = bz - az;
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (len < 1e-6) return true;
  const inv = 1 / len;
  const t = raycastWorld(colliders, ax, ay, az, dx * inv, dy * inv, dz * inv, len - 0.05);
  return t >= len - 0.06;
}
