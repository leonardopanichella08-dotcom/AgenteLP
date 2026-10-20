import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { FLOOR, MAP_BOXES } from '../game/map.js';
import { gradient, outlineMaterial } from './toon.js';

/** Fonde tutta la mappa in UNA geometria con colori per-vertice (1 draw call)
 *  + una copia "gonfiata" lungo le normali per il contorno cartoon dei pezzi arrotondati. */
function buildWorld() {
  const parts = [];
  const outlineParts = [];
  const tmp = new THREE.Color();

  const prepare = (g, b, withOutline) => {
    g.translate(b.x, b.y, b.z);
    const ng = g.index ? g.toNonIndexed() : g;
    ng.deleteAttribute('uv');
    const n = ng.attributes.position.count;
    tmp.set(b.color);
    const col = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { col[i * 3] = tmp.r; col[i * 3 + 1] = tmp.g; col[i * 3 + 2] = tmp.b; }
    ng.setAttribute('color', new THREE.BufferAttribute(col, 3));
    if (withOutline) {
      const og = ng.clone();
      const p = og.attributes.position, nm = og.attributes.normal;
      for (let i = 0; i < p.count; i++) {
        p.setXYZ(i, p.getX(i) + nm.getX(i) * 0.035, p.getY(i) + nm.getY(i) * 0.035, p.getZ(i) + nm.getZ(i) * 0.035);
      }
      og.deleteAttribute('color');
      outlineParts.push(og);
    }
    if (ng !== g) g.dispose();
    parts.push(ng);
  };

  for (const b of MAP_BOXES) {
    let g;
    if (b.shape === 'cyl') g = new THREE.CylinderGeometry(b.r, b.r, b.h, 18);
    else if (b.shape === 'sphere') g = new THREE.SphereGeometry(b.r, 18, 12);
    else if (b.round) g = new RoundedBoxGeometry(b.w, b.h, b.d, 2, b.round);
    else g = new THREE.BoxGeometry(b.w, b.h, b.d);
    prepare(g, b, b.round > 0 || b.shape !== 'box');
  }
  const geo = mergeGeometries(parts, false);
  const outline = mergeGeometries(outlineParts, false);
  parts.forEach((p) => p.dispose());
  outlineParts.forEach((p) => p.dispose());

  // pavimento a scacchi pulito
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d');
  ctx.fillStyle = FLOOR.c1; ctx.fillRect(0, 0, 128, 128);
  ctx.fillStyle = FLOOR.c2; ctx.fillRect(0, 0, 64, 64); ctx.fillRect(64, 64, 64, 64);
  const floorTex = new THREE.CanvasTexture(c);
  floorTex.colorSpace = THREE.SRGBColorSpace;
  floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping;
  floorTex.repeat.set(FLOOR.w / 4, FLOOR.d / 4);
  floorTex.anisotropy = 4;
  return { geo, outline, floorTex };
}

export default function World() {
  const { geo, outline, floorTex } = useMemo(buildWorld, []);
  useEffect(() => () => { geo.dispose(); outline.dispose(); floorTex.dispose(); }, [geo, outline, floorTex]);
  const grad = gradient();
  return (
    <group>
      <mesh geometry={geo} frustumCulled={false}>
        <meshToonMaterial vertexColors gradientMap={grad} />
      </mesh>
      <mesh geometry={outline} material={outlineMaterial()} frustumCulled={false} />
      <mesh rotation-x={-Math.PI / 2} position-y={0}>
        <planeGeometry args={[FLOOR.w, FLOOR.d]} />
        <meshToonMaterial map={floorTex} gradientMap={grad} />
      </mesh>
    </group>
  );
}
