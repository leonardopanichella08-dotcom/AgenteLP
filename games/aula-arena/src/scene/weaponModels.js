import * as THREE from 'three';
import { toonMat, outlineMaterial } from './toon.js';

// Modelli stilizzati delle armi. Canna verso -Z, impugnatura vicino all'origine.
// `owned` raccoglie geometrie/materiali da liberare (il materiale contorno è condiviso).

function part(owned, geo, color, x, y, z, { rx = 0, ry = 0, rz = 0, outline = true } = {}) {
  owned.geos.push(geo);
  const m = toonMat(color); owned.mats.push(m);
  const mesh = new THREE.Mesh(geo, m);
  mesh.position.set(x, y, z);
  mesh.rotation.set(rx, ry, rz);
  if (outline) {
    const o = new THREE.Mesh(geo, outlineMaterial());
    o.scale.setScalar(1.12);
    o.userData.outline = true;
    mesh.add(o);
  }
  return mesh;
}

const box = (w, h, d) => new THREE.BoxGeometry(w, h, d, 1, 1, 1);
const cylZ = (r, len, seg = 12) => new THREE.CylinderGeometry(r, r, len, seg);

export function buildWeapon(id, owned) {
  const g = new THREE.Group();
  const HALF = Math.PI / 2;
  switch (id) {
    case 'rifle':
      g.add(part(owned, box(0.09, 0.12, 0.5), '#3b4260', 0, 0, -0.2));
      g.add(part(owned, cylZ(0.028, 0.34), '#20243a', 0, 0.02, -0.62, { rx: HALF }));
      g.add(part(owned, box(0.07, 0.17, 0.09), '#ff9f43', 0, -0.13, -0.12, { rx: 0.2 }));
      g.add(part(owned, box(0.075, 0.1, 0.22), '#5a6288', 0, -0.01, 0.2));
      g.add(part(owned, box(0.05, 0.05, 0.12), '#ffd23f', 0, 0.09, -0.3));
      g.userData.muzzle = [0, 0.02, -0.82];
      break;
    case 'pistol':
      g.add(part(owned, box(0.07, 0.09, 0.26), '#4a4f6e', 0, 0, -0.1));
      g.add(part(owned, box(0.062, 0.15, 0.075), '#ff5d8f', 0, -0.1, 0.0, { rx: -0.2 }));
      g.add(part(owned, cylZ(0.022, 0.1), '#20243a', 0, 0.01, -0.27, { rx: HALF }));
      g.userData.muzzle = [0, 0.01, -0.34];
      break;
    case 'shotgun':
      g.add(part(owned, cylZ(0.035, 0.72), '#4a4f6e', 0, 0.02, -0.4, { rx: HALF }));
      g.add(part(owned, cylZ(0.03, 0.55), '#2c3354', 0, -0.035, -0.33, { rx: HALF }));
      g.add(part(owned, box(0.095, 0.075, 0.2), '#c98a4b', 0, -0.045, -0.4));
      g.add(part(owned, box(0.09, 0.12, 0.3), '#8a5a33', 0, -0.03, 0.08));
      g.add(part(owned, box(0.075, 0.12, 0.22), '#8a5a33', 0, -0.1, 0.27, { rx: -0.35 }));
      g.userData.muzzle = [0, 0.02, -0.8];
      break;
    case 'bazooka':
      g.add(part(owned, cylZ(0.09, 0.95), '#55704a', 0, 0.02, -0.25, { rx: HALF }));
      g.add(part(owned, new THREE.CylinderGeometry(0.125, 0.09, 0.16, 14), '#ffd23f', 0, 0.02, -0.78, { rx: HALF }));
      g.add(part(owned, new THREE.CylinderGeometry(0.1, 0.13, 0.12, 14), '#3b4260', 0, 0.02, 0.28, { rx: HALF }));
      g.add(part(owned, box(0.07, 0.14, 0.09), '#3b4260', 0, -0.15, -0.1));
      g.add(part(owned, box(0.05, 0.07, 0.14), '#ff5252', 0, 0.12, -0.25));
      g.userData.muzzle = [0, 0.02, -0.88];
      break;
    default:
      break;
  }
  return g;
}

export const WEAPON_IDS = ['rifle', 'pistol', 'shotgun', 'bazooka'];

/** Libera geometrie e materiali tracciati in `owned`. */
export function disposeOwned(owned) {
  owned.geos.forEach((g) => g.dispose());
  owned.mats.forEach((m) => m.dispose());
  owned.texs?.forEach((t) => t.dispose());
  owned.geos.length = owned.mats.length = 0;
}
