import { useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { MAX_BOOMS, MAX_PROJECTILES, MAX_PUFFS, MAX_TRACERS } from '../game/sim.js';

/** Effetti a pool fisso (nessuna allocazione per frame): tracer, esplosioni, scintille, proiettili. */
export default function Effects({ stateRef }) {
  const fx = useMemo(() => {
    const group = new THREE.Group();
    const geos = [], mats = [];
    const g = (x) => (geos.push(x), x);
    const m = (x) => (mats.push(x), x);

    const unitBox = g(new THREE.BoxGeometry(1, 1, 1));
    const sphere = g(new THREE.SphereGeometry(1, 14, 10));
    const tracerMat = m(new THREE.MeshBasicMaterial({ color: '#fff2a8' }));
    const tracerRic = m(new THREE.MeshBasicMaterial({ color: '#ffa94d' }));

    const tracers = [];
    for (let i = 0; i < MAX_TRACERS; i++) {
      const segs = [];
      for (let s = 0; s < 3; s++) {
        const mesh = new THREE.Mesh(unitBox, tracerMat);
        mesh.visible = false; group.add(mesh); segs.push(mesh);
      }
      tracers.push(segs);
    }
    const booms = [];
    for (let i = 0; i < MAX_BOOMS; i++) {
      const a = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ color: '#ff9f43', transparent: true, depthWrite: false }));
      mats.push(a.material);
      a.visible = false; group.add(a); booms.push(a);
    }
    const puffs = [];
    for (let i = 0; i < MAX_PUFFS; i++) {
      const a = new THREE.Mesh(sphere, new THREE.MeshBasicMaterial({ color: '#fff', transparent: true, depthWrite: false }));
      mats.push(a.material);
      a.visible = false; group.add(a); puffs.push(a);
    }
    const projs = [];
    const rocketGeo = g(new THREE.CylinderGeometry(0.07, 0.07, 0.5, 10));
    const coneGeo = g(new THREE.ConeGeometry(0.09, 0.2, 10));
    const nadeGeo = g(new THREE.SphereGeometry(0.13, 12, 10));
    const rocketMat = m(new THREE.MeshBasicMaterial({ color: '#ff5252' }));
    const nadeMat = m(new THREE.MeshBasicMaterial({ color: '#4dd6ff' }));
    const nadeBlink = m(new THREE.MeshBasicMaterial({ color: '#ffffff' }));
    for (let i = 0; i < MAX_PROJECTILES; i++) {
      const grp = new THREE.Group();
      const r = new THREE.Mesh(rocketGeo, rocketMat); r.rotation.x = Math.PI / 2;
      const c = new THREE.Mesh(coneGeo, rocketMat); c.rotation.x = -Math.PI / 2; c.position.z = -0.35;
      const rk = new THREE.Group(); rk.add(r, c);
      const n = new THREE.Mesh(nadeGeo, nadeMat);
      grp.add(rk, n); grp.visible = false;
      group.add(grp);
      projs.push({ grp, rk, n });
    }
    const dispose = () => { geos.forEach((x) => x.dispose()); mats.forEach((x) => x.dispose()); };
    return { group, tracers, booms, puffs, projs, tracerMat, tracerRic, nadeMat, nadeBlink, dispose };
  }, []);

  useEffect(() => () => fx.dispose(), [fx]);

  const v = useMemo(() => ({ a: new THREE.Vector3(), b: new THREE.Vector3() }), []);

  useFrame(() => {
    const st = stateRef.current;
    if (!st) return;
    const t = st.time, F = st.fx;

    for (let i = 0; i < MAX_TRACERS; i++) {
      const tr = F.tracers[i], segs = fx.tracers[i];
      const age = t - tr.t0;
      const on = age >= 0 && age < 0.09 && tr.n >= 2;
      for (let s = 0; s < 3; s++) {
        const mesh = segs[s];
        if (!on || s >= tr.n - 1) { mesh.visible = false; continue; }
        v.a.set(tr.pts[s * 3], tr.pts[s * 3 + 1], tr.pts[s * 3 + 2]);
        v.b.set(tr.pts[s * 3 + 3], tr.pts[s * 3 + 4], tr.pts[s * 3 + 5]);
        const len = v.a.distanceTo(v.b);
        mesh.visible = len > 0.01;
        mesh.position.copy(v.a).add(v.b).multiplyScalar(0.5);
        mesh.lookAt(v.b);
        const th = 0.045 * (1 - age / 0.09) + 0.01;
        mesh.scale.set(th, th, len);
        mesh.material = tr.color === 0xffa94d ? fx.tracerRic : fx.tracerMat;
      }
    }
    for (let i = 0; i < MAX_BOOMS; i++) {
      const b = F.booms[i], mesh = fx.booms[i];
      const k = (t - b.t0) / (b.kind === 0 ? 0.4 : 0.6);
      if (k < 0 || k >= 1) { mesh.visible = false; continue; }
      mesh.visible = true;
      mesh.position.set(b.x, b.y, b.z);
      mesh.scale.setScalar(Math.max(0.05, b.r * (0.25 + 0.75 * Math.sqrt(k))));
      mesh.material.color.set(b.kind === 0 ? (k < 0.3 ? '#fff0b0' : '#ff9f43') : '#7ee8ff');
      mesh.material.opacity = (b.kind === 0 ? 0.9 : 0.45) * (1 - k);
    }
    for (let i = 0; i < MAX_PUFFS; i++) {
      const p = F.puffs[i], mesh = fx.puffs[i];
      const k = (t - p.t0) / 0.25;
      if (k < 0 || k >= 1) { mesh.visible = false; continue; }
      mesh.visible = true;
      mesh.position.set(p.x, p.y, p.z);
      mesh.scale.setScalar(0.05 + k * 0.16);
      mesh.material.color.setHex(p.color);
      mesh.material.opacity = 0.9 * (1 - k);
    }
    for (let i = 0; i < MAX_PROJECTILES; i++) {
      const p = st.projectiles[i], o = fx.projs[i];
      if (!p.active) { o.grp.visible = false; continue; }
      o.grp.visible = true;
      o.grp.position.set(p.x, p.y, p.z);
      if (p.type === 0) {
        o.rk.visible = true; o.n.visible = false;
        v.a.set(p.x + p.vx, p.y + p.vy, p.z + p.vz);
        o.grp.lookAt(v.a);
      } else {
        o.rk.visible = false; o.n.visible = true;
        const blink = (p.explodeAt - t) < 0.6 && Math.floor(t * 14) % 2 === 0;
        o.n.material = blink ? fx.nadeBlink : fx.nadeMat;
      }
    }
  });

  return <primitive object={fx.group} />;
}
