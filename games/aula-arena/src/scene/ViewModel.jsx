import { useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { WEAPONS } from '../game/weapons.js';
import { isUnprepared } from '../game/util.js';
import { outlineMaterial, toonMat } from './toon.js';
import { buildWeapon, disposeOwned, WEAPON_IDS } from './weaponModels.js';

const HALF = Math.PI / 2;
// Posizione delle mani (spalla -> mano) per arma, in coordinate del gruppo vista.
const HANDS = {
  rifle:   { r: [0.02, -0.1, 0.1], l: [0.0, -0.04, -0.42] },
  pistol:  { r: [0.0, -0.06, 0.02], l: [-0.06, -0.12, -0.02] },
  shotgun: { r: [0.0, -0.08, 0.14], l: [0.0, -0.05, -0.38] },
  bazooka: { r: [0.0, -0.18, -0.1], l: [0.0, -0.16, -0.5] },
};
const WEAPON_POS = new THREE.Vector3(0.27, -0.27, -0.5);
const UP = new THREE.Vector3(0, 1, 0);

/** Scena separata per braccia+arma in prima persona: renderizzata dopo un clearDepth,
 *  quindi non "entra mai" nei muri. */
export default function ViewModel({ stateRef, viewScene, viewCam }) {
  const owned = useMemo(() => ({ geos: [], mats: [], texs: [] }), []);
  const rig = useMemo(() => {
    const st = stateRef.current;
    const p = st.player;
    const root = new THREE.Group();
    const weapons = {};
    const wg = new THREE.Group();
    wg.position.copy(WEAPON_POS);
    root.add(wg);
    for (const id of WEAPON_IDS) { const w = buildWeapon(id, owned); w.visible = false; weapons[id] = w; wg.add(w); }

    const sleeve = toonMat(p.char.color), skin = toonMat(p.char.skin);
    owned.mats.push(sleeve, skin);
    const armGeo = new THREE.CapsuleGeometry(0.075, 0.9, 4, 10);
    const handGeo = new THREE.SphereGeometry(0.085, 12, 10);
    owned.geos.push(armGeo, handGeo);
    const mkArm = () => {
      const a = new THREE.Mesh(armGeo, sleeve);
      const o = new THREE.Mesh(armGeo, outlineMaterial()); o.scale.setScalar(1.12); a.add(o);
      const h = new THREE.Mesh(handGeo, skin);
      const ho = new THREE.Mesh(handGeo, outlineMaterial()); ho.scale.setScalar(1.14); h.add(ho);
      return { a, h };
    };
    const R = mkArm(), L = mkArm();
    wg.add(R.a, R.h, L.a, L.h);
    const muzzleFlash = new THREE.Mesh(new THREE.IcosahedronGeometry(0.1, 0), new THREE.MeshBasicMaterial({ color: '#ffe36b' }));
    owned.geos.push(muzzleFlash.geometry); owned.mats.push(muzzleFlash.material);
    muzzleFlash.visible = false;
    wg.add(muzzleFlash);

    const dir = new THREE.Vector3(), from = new THREE.Vector3(), to = new THREE.Vector3();
    function placeArm(arm, shoulder, hand) {
      from.set(...shoulder); to.set(...hand);
      dir.subVectors(to, from);
      const len = dir.length();
      arm.a.position.copy(from).addScaledVector(dir, 0.5);
      arm.a.quaternion.setFromUnitVectors(UP, dir.normalize());
      arm.a.scale.set(1, len / 0.9 > 0 ? len / 1.05 : 1, 1);
      arm.h.position.copy(to);
    }
    let handsFor = '';
    function setHands(id) {
      if (handsFor === id) return;
      handsFor = id;
      const h = HANDS[id];
      placeArm(R, [0.38, -0.55, 0.65], h.r);
      placeArm(L, [-0.45, -0.55, 0.65], h.l);
    }
    return { root, weapons, wg, muzzleFlash, setHands, lastCur: 0, switchAt: -9, shown: '', bobT: 0, lower: 0 };
  }, [stateRef, owned]);

  useEffect(() => {
    viewScene.add(rig.root);
    return () => { viewScene.remove(rig.root); disposeOwned(owned); };
  }, [rig, viewScene, owned]);

  useFrame(({ size }, delta) => {
    const st = stateRef.current;
    const p = st && st.player;
    if (!p) return;
    const dt = Math.min(delta, 0.05), t = st.time;
    // aspect sempre allineato al canvas (gestione resize/rotazione)
    const aspect = size.width / size.height;
    if (viewCam.aspect !== aspect) { viewCam.aspect = aspect; viewCam.updateProjectionMatrix(); }

    const wid = p.slots[p.cur];
    const isGadgetSlot = WEAPONS[wid].kind === 'gadget';
    const show = isGadgetSlot ? p.slots[0] : wid;
    if (rig.shown !== show) {
      for (const id of WEAPON_IDS) rig.weapons[id].visible = id === show;
      rig.shown = show;
      rig.setHands(show);
      rig.switchAt = t;
    }

    // animazioni
    const moving = Math.min(1, p.speedNow / 6);
    rig.bobT += dt * (3 + p.speedNow * 1.3);
    const bobX = Math.cos(rig.bobT) * 0.012 * moving;
    const bobY = Math.abs(Math.sin(rig.bobT)) * 0.016 * moving;
    const unprep = isUnprepared(st, p) || !p.alive;
    const targetLower = unprep ? 1 : 0;
    rig.lower += (targetLower - rig.lower) * Math.min(1, dt * 9);

    const w = WEAPONS[show];
    const reloadEnd = p.reloadEnd[p.cur];
    let reloadK = 0;
    if (reloadEnd > t && w.reload) reloadK = Math.sin(Math.min(1, 1 - (reloadEnd - t) / w.reload) * Math.PI);
    const equip = Math.max(0, 1 - (t - rig.switchAt) / 0.25);
    const gadgetK = Math.max(0, 1 - (t - p.gadgetAt) / 0.3);

    rig.wg.position.set(
      WEAPON_POS.x + bobX,
      WEAPON_POS.y + bobY - reloadK * 0.22 - equip * 0.3 - rig.lower * 0.75 + gadgetK * 0.05,
      WEAPON_POS.z + p.recoil * 0.09 + reloadK * 0.05,
    );
    rig.wg.rotation.set(p.recoil * 0.07 + reloadK * 0.5 + rig.lower * 0.6, -0.04 + reloadK * 0.15, rig.lower * -0.25);

    const flashOn = !isGadgetSlot && t - p.firedAt < 0.05;
    rig.muzzleFlash.visible = flashOn;
    if (flashOn) rig.muzzleFlash.position.set(...rig.weapons[show].userData.muzzle);

  });
  return null;
}

/** Contenitore: crea scena/camera "vista" e il passaggio di render finale. */
export function useViewLayer(stateRef) {
  const viewScene = useMemo(() => {
    const s = new THREE.Scene();
    s.add(new THREE.AmbientLight('#ffffff', 1.5));
    const d = new THREE.DirectionalLight('#ffffff', 1.6);
    d.position.set(0.5, 1, 1);
    s.add(d);
    return s;
  }, []);
  const viewCam = useMemo(() => new THREE.PerspectiveCamera(60, 16 / 9, 0.02, 10), []);
  useEffect(() => () => viewScene.clear(), [viewScene]);

  useFrame(({ gl, scene, camera }) => {
    const st = stateRef.current;
    gl.autoClear = true;
    gl.render(scene, camera);
    if (st && st.player && st.player.alive) {
      gl.autoClear = false;
      gl.clearDepth();
      gl.render(viewScene, viewCam);
      gl.autoClear = true;
    }
  }, 100);
  return { viewScene, viewCam };
}
