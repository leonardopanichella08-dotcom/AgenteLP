import { useEffect, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { BODY, MATCH } from '../game/constants.js';
import { stepMatch } from '../game/sim.js';
import World from './World.jsx';
import Fighters from './Fighters.jsx';
import Effects from './Effects.jsx';
import ViewModel, { useViewLayer } from './ViewModel.jsx';
import { disposeToon } from './toon.js';
import { disposeFaces } from './faces.js';

const MAX_DPR = Math.min(typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1, 1.75);
const MIN_DPR = 0.6;

/** Passo di simulazione + risoluzione dinamica (mantiene ~60 FPS su GPU mobile). */
function GameLoop({ stateRef, input, pausedRef, onOver }) {
  const setDpr = useThree((s) => s.setDpr);
  const perf = useRef({ t: 0, frames: 0, dpr: MAX_DPR, cool: 3 });

  useFrame((_, delta) => {
    const st = stateRef.current;
    if (!st) return;
    const dt = Math.min(delta, 0.05);
    if (pausedRef.current) {
      input.lookDX = input.lookDY = 0;
    } else {
      stepMatch(st, dt, input);
    }
    if (st.over && !st.reported) { st.reported = true; onOver(st.result); }

    // regolazione adattiva della risoluzione
    const p = perf.current;
    p.t += delta; p.frames++;
    if (p.t >= 1.5) {
      const fps = p.frames / p.t;
      p.t = 0; p.frames = 0;
      if (p.cool > 0) { p.cool--; return; } // ignora il warm-up (compilazione shader)
      if (fps < 48 && p.dpr > MIN_DPR) { p.dpr = Math.max(MIN_DPR, p.dpr * 0.85); setDpr(p.dpr); }
      else if (fps > 58 && p.dpr < MAX_DPR) { p.dpr = Math.min(MAX_DPR, p.dpr + 0.1); setDpr(p.dpr); }
    }
  }, -10);
  return null;
}

/** Posiziona la camera sulla testa del giocatore (con bob, rinculo e camera di morte). */
function CameraRig({ stateRef }) {
  const { camera } = useThree();
  useEffect(() => { camera.rotation.order = 'YXZ'; }, [camera]);
  useFrame(() => {
    const st = stateRef.current;
    const p = st && st.player;
    if (!p) return;
    if (p.alive) {
      const m = Math.min(1, p.speedNow / 6);
      const bob = Math.sin(p.walk * 1.0) * 0.035 * m;
      camera.position.set(p.x, BODY.eye + bob, p.z);
      camera.rotation.set(p.pitch + p.recoil * 0.012, p.yaw, 0);
    } else {
      const since = st.time - (p.respawnAt - MATCH.respawn);
      const k = Math.min(1, since / 0.6);
      camera.position.set(p.x, BODY.eye - k * 1.2, p.z);
      camera.rotation.set(p.pitch * (1 - k) - k * 0.2, p.yaw, k * 0.9);
    }
  }, -5);
  return null;
}

function Layers({ stateRef }) {
  const { viewScene, viewCam } = useViewLayer(stateRef);
  return <ViewModel stateRef={stateRef} viewScene={viewScene} viewCam={viewCam} />;
}

function Cleanup() {
  const gl = useThree((s) => s.gl);
  useEffect(() => () => {
    disposeToon();
    disposeFaces();
    gl.renderLists.dispose();
  }, [gl]);
  return null;
}

export default function Scene3D({ stateRef, input, pausedRef, onOver }) {
  const entities = stateRef.current.entities;
  return (
    <Canvas
      dpr={MAX_DPR}
      frameloop="always"
      camera={{ fov: 74, near: 0.06, far: 120, position: [0, BODY.eye, 0] }}
      gl={{ antialias: MAX_DPR < 2, powerPreference: 'high-performance', alpha: false, stencil: false, preserveDrawingBuffer: false }}
      style={{ position: 'absolute', inset: 0, touchAction: 'none' }}
      onCreated={({ gl }) => {
        gl.setClearColor(new THREE.Color('#bfe6ff'));
        gl.outputColorSpace = THREE.SRGBColorSpace;
        if (window.__aula) { window.__aula.gl = gl; gl.info.autoReset = false; }
      }}
    >
      <hemisphereLight args={['#ffffff', '#ffe9c4', 1.35]} />
      <directionalLight position={[14, 24, 8]} intensity={1.7} />
      <GameLoop stateRef={stateRef} input={input} pausedRef={pausedRef} onOver={onOver} />
      <CameraRig stateRef={stateRef} />
      <World />
      <Fighters stateRef={stateRef} entities={entities} />
      <Effects stateRef={stateRef} />
      <Layers stateRef={stateRef} />
      <Cleanup />
    </Canvas>
  );
}
