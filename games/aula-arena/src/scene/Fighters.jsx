import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { BODY } from '../game/constants.js';
import { POWERS, WEAPONS } from '../game/weapons.js';
import { isPowerActive, isUnprepared } from '../game/util.js';
import { makeLabel, outlineMaterial, shade, toonMat } from './toon.js';
import { getFaceTexture } from './faces.js';
import { buildWeapon, disposeOwned, WEAPON_IDS } from './weaponModels.js';

const HALF = Math.PI / 2;

/** Costruisce il personaggio 3D (imperativo: tanti micro-pezzi animati ogni frame). */
function createRig(entity) {
  const owned = { geos: [], mats: [], texs: [] };
  const geo = (g) => { owned.geos.push(g); return g; };
  const mat = (m) => { owned.mats.push(m); return m; };
  const char = entity.char;

  const shirt = mat(toonMat(char.color));
  const skin = mat(toonMat(char.skin));
  const pants = mat(toonMat('#2d3a6b'));
  const hair = mat(toonMat(shade(char.color, -0.22)));
  const bodyMats = [shirt, skin, pants, hair];
  const outlines = [];

  const mk = (g, m, parent, x, y, z, s = 1.08) => {
    const mesh = new THREE.Mesh(geo(g), m);
    mesh.position.set(x, y, z);
    if (s) {
      const o = new THREE.Mesh(g, outlineMaterial());
      o.scale.setScalar(s);
      mesh.add(o); outlines.push(o);
    }
    parent.add(mesh);
    return mesh;
  };

  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);

  // gambe (pivot all'anca)
  const legL = new THREE.Group(), legR = new THREE.Group();
  legL.position.set(-0.15, 0.62, 0); legR.position.set(0.15, 0.62, 0);
  mk(new THREE.CapsuleGeometry(0.115, 0.4, 4, 10), pants, legL, 0, -0.3, 0);
  mk(new THREE.CapsuleGeometry(0.115, 0.4, 4, 10), pants, legR, 0, -0.3, 0);
  body.add(legL, legR);

  // busto + testa
  mk(new THREE.CapsuleGeometry(0.27, 0.36, 4, 14), shirt, body, 0, 1.0, 0);
  const head = new THREE.Group();
  head.position.set(0, 1.62, 0);
  body.add(head);
  mk(new THREE.SphereGeometry(0.27, 20, 16), skin, head, 0, 0, 0);
  const cap = mk(new THREE.SphereGeometry(0.295, 18, 10, 0, Math.PI * 2, 0, Math.PI * 0.36), hair, head, 0, 0.03, 0.03, 1.07);
  cap.rotation.x = 0.55;
  const faceMat = mat(new THREE.MeshBasicMaterial({ map: getFaceTexture(char), transparent: true }));
  const face = new THREE.Mesh(geo(new THREE.CircleGeometry(0.235, 28)), faceMat);
  face.position.set(0, -0.01, -0.262);
  face.rotation.y = Math.PI;
  head.add(face);

  // braccia (pivot alla spalla) + arma
  const armL = new THREE.Group(), armR = new THREE.Group();
  armL.position.set(-0.34, 1.3, 0); armR.position.set(0.34, 1.3, 0);
  const armGeo = new THREE.CapsuleGeometry(0.08, 0.36, 4, 8);
  mk(armGeo, shirt, armL, 0, -0.26, 0);
  mk(armGeo, shirt, armR, 0, -0.26, 0);
  mk(new THREE.SphereGeometry(0.09, 10, 8), skin, armL, 0, -0.5, 0, 0);
  mk(new THREE.SphereGeometry(0.09, 10, 8), skin, armR, 0, -0.5, 0, 0);
  body.add(armL, armR);

  const weapons = {};
  const gunHold = new THREE.Group();
  gunHold.position.set(0.12, 1.12, -0.35);
  body.add(gunHold);
  for (const id of WEAPON_IDS) {
    const w = buildWeapon(id, owned);
    w.visible = false; weapons[id] = w; gunHold.add(w);
  }
  const flashMat = mat(new THREE.MeshBasicMaterial({ color: '#ffe36b' }));
  const flash = new THREE.Mesh(geo(new THREE.IcosahedronGeometry(0.11, 0)), flashMat);
  flash.visible = false; gunHold.add(flash);

  // ombra finta
  const shadowMat = mat(new THREE.MeshBasicMaterial({ color: '#000', transparent: true, opacity: 0.22, depthWrite: false }));
  const shadow = new THREE.Mesh(geo(new THREE.CircleGeometry(0.55, 16)), shadowMat);
  shadow.rotation.x = -HALF; shadow.position.y = 0.025;
  root.add(shadow);

  // aura potere + scudo
  const auraMat = mat(new THREE.MeshBasicMaterial({ color: '#fff', transparent: true, opacity: 0.85, side: THREE.DoubleSide, depthWrite: false }));
  const aura = new THREE.Mesh(geo(new THREE.RingGeometry(0.6, 0.8, 28)), auraMat);
  aura.rotation.x = -HALF; aura.position.y = 0.04; aura.visible = false;
  root.add(aura);
  const bubbleMat = mat(new THREE.MeshBasicMaterial({ color: '#4dd6ff', transparent: true, opacity: 0.22, depthWrite: false }));
  const bubble = new THREE.Mesh(geo(new THREE.SphereGeometry(1.05, 18, 12)), bubbleMat);
  bubble.position.y = 0.95; bubble.visible = false;
  root.add(bubble);

  // etichette (sempre rivolte alla camera)
  const tag = new THREE.Group();
  tag.position.y = 2.3;
  root.add(tag);
  const spriteOf = (text, opts, scale, y) => {
    const { tex, aspect } = makeLabel(text, opts);
    owned.texs.push(tex);
    const m = mat(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    const s = new THREE.Sprite(m);
    s.scale.set(scale * aspect, scale, 1);
    s.position.y = y;
    tag.add(s);
    return s;
  };
  spriteOf(entity.name, { font: 'bold 44px system-ui, sans-serif' }, 0.4, 0.14);
  const lblUnprep = spriteOf('IMPREPARATO', { bg: 'rgba(255,82,82,0.92)', font: 'bold 40px system-ui, sans-serif', h: 64 }, 0.3, 0.55);
  const lblAsked = spriteOf('INTERROGATO', { bg: 'rgba(255,207,90,0.96)', fg: '#1b1f3b', font: 'bold 40px system-ui, sans-serif', h: 64 }, 0.3, 0.55);
  lblUnprep.visible = lblAsked.visible = false;
  const hpBack = new THREE.Mesh(geo(new THREE.PlaneGeometry(0.8, 0.09)), mat(new THREE.MeshBasicMaterial({ color: '#1b1f3b', depthWrite: false })));
  hpBack.position.y = -0.14;
  const hpFillMat = mat(new THREE.MeshBasicMaterial({ color: '#5be37d', depthWrite: false }));
  const hpFill = new THREE.Mesh(geo(new THREE.PlaneGeometry(0.76, 0.055)), hpFillMat);
  hpFill.position.set(0, -0.14, 0.001);
  tag.add(hpBack, hpFill);

  let ghostOn = false;
  let curWeapon = '';
  const auraCol = new THREE.Color();

  function setGhost(on) {
    ghostOn = on;
    for (const m of bodyMats) { m.transparent = on; m.opacity = on ? 0.2 : 1; m.needsUpdate = true; }
    faceMat.opacity = on ? 0.2 : 1;
    for (const o of outlines) o.visible = !on;
  }

  function update(state, camera, dt) {
    const e = entity, t = state.time;
    const visible = e.alive && (t >= e.protectUntil || Math.floor(t * 12) % 2 === 0);
    root.visible = visible;
    if (!e.alive) return;

    root.position.set(e.x, 0, e.z);
    body.rotation.y = e.yaw;

    const ghost = isPowerActive(e, t, 'ghost');
    if (ghost !== ghostOn) setGhost(ghost);

    // camminata
    const sw = Math.sin(e.walk) * Math.min(1, e.speedNow / 5) * 0.85;
    legL.rotation.x = sw; legR.rotation.x = -sw;
    body.position.y = Math.abs(Math.sin(e.walk)) * 0.04 * Math.min(1, e.speedNow / 5);

    // braccia: alzate sull'arma, o abbassate se "impreparato"
    const unprep = isUnprepared(state, e);
    const k = Math.min(1, dt * 12);
    const tR = unprep ? 0.08 : -HALF + e.pitch * 0.6 + 0.12;
    const tL = unprep ? -0.08 : -HALF + e.pitch * 0.6 - 0.05;
    armR.rotation.x += (tR - armR.rotation.x) * k;
    armL.rotation.x += (tL - armL.rotation.x) * k;
    armL.rotation.z += ((unprep ? -0.05 : 0.38) - armL.rotation.z) * k;
    armR.rotation.z += ((unprep ? 0.05 : -0.1) - armR.rotation.z) * k;

    // arma corrente
    const wid = e.slots[e.cur];
    const showGun = !unprep && WEAPONS[wid].kind !== 'gadget';
    const want = showGun ? wid : '';
    if (want !== curWeapon) {
      for (const id of WEAPON_IDS) weapons[id].visible = id === want;
      curWeapon = want;
    }
    gunHold.rotation.x = e.pitch * 0.6 + e.recoil * 0.1;
    gunHold.position.z = -0.35 + e.recoil * 0.06;
    flash.visible = showGun && t - e.firedAt < 0.05;
    if (flash.visible && weapons[curWeapon]) {
      const m = weapons[curWeapon].userData.muzzle;
      flash.position.set(m[0], m[1], m[2]);
    }

    // flash colpo subito
    const f = Math.max(0, 1 - (t - e.lastDamageAt) / 0.18);
    for (const m of bodyMats) m.emissive.setScalar(f * 0.7);

    // potere attivo
    const pw = t < e.powerUntil ? POWERS[e.powerId] : null;
    aura.visible = !!pw;
    bubble.visible = !!pw && pw.id === 'shield';
    if (pw) {
      auraCol.set(pw.color); auraMat.color.copy(auraCol);
      const s = 1 + Math.sin(t * 9) * 0.08;
      aura.scale.set(s, s, 1);
      aura.rotation.z += dt * 2;
    }

    // etichette
    tag.quaternion.copy(camera.quaternion);
    const dist = Math.hypot(camera.position.x - e.x, camera.position.z - e.z);
    tag.visible = dist < 45 && !ghost;
    const asked = state.event.phase === 'active' && state.event.targetId === e.id;
    lblAsked.visible = asked;
    lblUnprep.visible = unprep;
    const r = Math.max(0, e.hp / BODY.maxHp);
    hpFill.scale.x = Math.max(0.001, r);
    hpFill.position.x = -(1 - r) * 0.38;
    hpFillMat.color.set(r > 0.5 ? '#5be37d' : r > 0.25 ? '#ffd23f' : '#ff5252');
  }

  function dispose() {
    disposeOwned(owned);
  }
  return { root, update, dispose };
}

function Fighter({ entity, stateRef }) {
  const group = useRef();
  const rig = useMemo(() => createRig(entity), [entity]);
  useEffect(() => {
    const g = group.current;
    g.add(rig.root);
    return () => { g.remove(rig.root); rig.dispose(); };
  }, [rig]);
  useFrame(({ camera }, delta) => {
    const st = stateRef.current;
    if (st) rig.update(st, camera, Math.min(delta, 0.05));
  });
  return <group ref={group} />;
}

export default function Fighters({ stateRef, entities }) {
  return (
    <>
      {entities.filter((e) => !e.isPlayer).map((e) => (
        <Fighter key={e.id} entity={e} stateRef={stateRef} />
      ))}
    </>
  );
}
