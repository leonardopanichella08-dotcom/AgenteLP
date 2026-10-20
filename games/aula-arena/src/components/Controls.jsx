import { useEffect, useRef } from 'react';

const STICK_R = 46; // raggio massimo di spostamento della manopola (px)
const DEAD = 0.14;

/** Gestione input a basso costo: scrive su `input` (oggetto mutabile) e sul DOM via ref.
 *  Nessun setState durante il gesto => nessun re-render, nessun lag. */
export default function Controls({ input, snap, isTouch, pausedRef, onPause }) {
  const stickBase = useRef(null);
  const stickKnob = useRef(null);
  const stick = useRef({ id: -1, cx: 0, cy: 0 });
  const look = useRef({ id: -1, x: 0, y: 0 });
  const fireBtn = useRef({ id: -1, x: 0, y: 0 });

  // ── tastiera + mouse (desktop / debug) ──
  useEffect(() => {
    if (isTouch) return undefined;
    const keys = new Set();
    const sync = () => {
      const f = (keys.has('KeyW') || keys.has('ArrowUp') ? 1 : 0) - (keys.has('KeyS') || keys.has('ArrowDown') ? 1 : 0);
      const r = (keys.has('KeyD') || keys.has('ArrowRight') ? 1 : 0) - (keys.has('KeyA') || keys.has('ArrowLeft') ? 1 : 0);
      const l = Math.hypot(f, r) || 1;
      input.moveY = f / l; input.moveX = r / l;
    };
    const down = (e) => {
      if (e.repeat) return;
      keys.add(e.code);
      if (e.code === 'KeyE' || e.code === 'ShiftLeft') input.power = true;
      if (e.code === 'KeyQ' || e.code === 'KeyF') input.secondary = true;
      if (e.code === 'KeyR') input.reload = true;
      if (e.code === 'Space') input.fire = true;
      sync();
    };
    const up = (e) => { keys.delete(e.code); if (e.code === 'Space') input.fire = false; sync(); };
    const move = (e) => {
      if (document.pointerLockElement && !pausedRef.current) { input.lookDX += e.movementX; input.lookDY += e.movementY; }
    };
    const md = (e) => {
      if (pausedRef.current || e.target.closest('[data-ui]')) return;
      if (!document.pointerLockElement) { document.body.requestPointerLock?.(); return; }
      if (e.button === 0) input.fire = true;
    };
    const mu = (e) => { if (e.button === 0) input.fire = false; };
    const lockChange = () => { if (!document.pointerLockElement && !pausedRef.current) onPause(); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('mousemove', move);
    window.addEventListener('mousedown', md);
    window.addEventListener('mouseup', mu);
    document.addEventListener('pointerlockchange', lockChange);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mousedown', md);
      window.removeEventListener('mouseup', mu);
      document.removeEventListener('pointerlockchange', lockChange);
      if (document.pointerLockElement) document.exitPointerLock();
      input.moveX = input.moveY = 0; input.fire = false;
    };
  }, [isTouch, input, pausedRef, onPause]);

  // ── joystick ──
  const stickMove = (e) => {
    const s = stick.current;
    if (e.pointerId !== s.id) return;
    let dx = e.clientX - s.cx, dy = e.clientY - s.cy;
    const len = Math.hypot(dx, dy);
    if (len > STICK_R) { dx = (dx / len) * STICK_R; dy = (dy / len) * STICK_R; }
    stickKnob.current.style.transform = `translate(${dx}px, ${dy}px)`;
    let mx = dx / STICK_R, my = -dy / STICK_R;
    const m = Math.hypot(mx, my);
    if (m < DEAD) { mx = my = 0; } else { const k = (m - DEAD) / (1 - DEAD) / m; mx *= k; my *= k; }
    input.moveX = mx; input.moveY = my;
  };
  const stickDown = (e) => {
    const r = stickBase.current.getBoundingClientRect();
    stick.current = { id: e.pointerId, cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
    e.currentTarget.setPointerCapture(e.pointerId);
    stickMove(e);
  };
  const stickUp = (e) => {
    if (e.pointerId !== stick.current.id) return;
    stick.current.id = -1;
    stickKnob.current.style.transform = 'translate(0px, 0px)';
    input.moveX = input.moveY = 0;
  };

  // ── area di visuale (parte destra) ──
  const lookDown = (e) => {
    look.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const lookMove = (e) => {
    const l = look.current;
    if (e.pointerId !== l.id) return;
    input.lookDX += e.clientX - l.x; input.lookDY += e.clientY - l.y;
    l.x = e.clientX; l.y = e.clientY;
  };
  const lookUp = (e) => { if (e.pointerId === look.current.id) look.current.id = -1; };

  // ── pulsante FUOCO: tenendolo premuto si può anche trascinare per mirare ──
  const fireDown = (e) => {
    fireBtn.current = { id: e.pointerId, x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
    input.fire = true;
  };
  const fireMove = (e) => {
    const f = fireBtn.current;
    if (e.pointerId !== f.id) return;
    input.lookDX += e.clientX - f.x; input.lookDY += e.clientY - f.y;
    f.x = e.clientX; f.y = e.clientY;
  };
  const fireUp = (e) => { if (e.pointerId === fireBtn.current.id) { fireBtn.current.id = -1; input.fire = false; } };

  // reset di sicurezza se il componente sparisce a metà gesto
  useEffect(() => () => { input.fire = false; input.moveX = input.moveY = 0; }, [input]);

  if (!isTouch) {
    return (
      <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/40 px-4 py-1 text-[11px] font-bold text-white/70">
        Click = cattura mouse · WASD · click/Spazio spara · E potere · Q secondaria · R ricarica · Esc pausa
      </div>
    );
  }

  const ready = snap.charge >= 100 && !snap.powerActive;
  const pwrPct = snap.powerActive ? (snap.powerLeft / 5) * 100 : snap.charge;
  const canShoot = snap.alive && !snap.unprepared && !snap.stunned;
  const secOn = snap.secondary.gadget ? snap.secondary.cdLeft <= 0 : true;

  return (
    <div className="absolute inset-0">
      {/* area di visuale */}
      <div
        className="absolute bottom-0 right-0 top-0 touch-none"
        style={{ left: '38%' }}
        onPointerDown={lookDown} onPointerMove={lookMove} onPointerUp={lookUp} onPointerCancel={lookUp}
      />

      {/* joystick fisso in basso a sinistra */}
      <div
        className="touch-none absolute bottom-0 left-0 flex items-center justify-center"
        style={{ width: 210, height: 210, paddingLeft: 'env(safe-area-inset-left)' }}
        onPointerDown={stickDown} onPointerMove={stickMove} onPointerUp={stickUp} onPointerCancel={stickUp}
        data-ui
      >
        <div ref={stickBase} className="relative flex h-[128px] w-[128px] items-center justify-center rounded-full border-2 border-white/35 bg-white/10 backdrop-blur-[1px]">
          <div ref={stickKnob} className="h-[58px] w-[58px] rounded-full border-2 border-white/70 bg-white/35 shadow-lg" style={{ willChange: 'transform' }} />
        </div>
      </div>

      {/* pulsanti azione (basso a destra) */}
      <div className="pointer-events-none absolute bottom-0 right-0" style={{ width: 300, height: 260, paddingRight: 'env(safe-area-inset-right)' }} data-ui>
        {/* FUOCO */}
        <button
          type="button"
          className={`btn-touch pointer-events-auto absolute flex items-center justify-center rounded-full border-4 text-3xl font-black shadow-xl ${canShoot ? 'border-white/80 bg-[#ff4d4d]/85' : 'border-white/30 bg-gray-500/60'}`}
          style={{ right: 22, bottom: 22, width: 100, height: 100 }}
          onPointerDown={fireDown} onPointerMove={fireMove} onPointerUp={fireUp} onPointerCancel={fireUp}
          aria-label="Spara"
        >
          <span className="pointer-events-none">🎯</span>
        </button>

        {/* SUPERPOTERE */}
        <button
          type="button"
          className={`btn-touch pointer-events-auto absolute flex items-center justify-center rounded-full ${ready ? 'ready-pulse' : ''}`}
          style={{
            right: 44, bottom: 138, width: 76, height: 76,
            background: `conic-gradient(${snap.powerColor} ${pwrPct * 3.6}deg, rgba(0,0,0,0.45) 0deg)`,
            padding: 5,
          }}
          onPointerDown={(e) => { e.preventDefault(); input.power = true; }}
          aria-label="Superpotere"
        >
          <span className={`flex h-full w-full items-center justify-center rounded-full border-2 text-2xl ${ready || snap.powerActive ? 'border-white bg-[#1b1f3b]' : 'border-white/30 bg-[#1b1f3b]/85'}`}>
            <span className={ready || snap.powerActive ? '' : 'opacity-50'}>{snap.powerIcon}</span>
          </span>
        </button>

        {/* SECONDARIA: cambio arma o gadget */}
        <button
          type="button"
          className="btn-touch pointer-events-auto absolute flex items-center justify-center overflow-hidden rounded-full border-[3px] border-white/60 bg-[#1b1f3b]/80 text-2xl"
          style={{ right: 140, bottom: 46, width: 66, height: 66, opacity: secOn ? 1 : 0.55 }}
          onPointerDown={(e) => { e.preventDefault(); input.secondary = true; }}
          aria-label={snap.secondary.name}
        >
          {snap.secondary.gadget && snap.secondary.cdLeft > 0 && (
            <span className="absolute inset-x-0 bottom-0 bg-black/60" style={{ height: `${snap.secondary.cdFrac * 100}%` }} />
          )}
          <span className="relative">{snap.secondary.icon}</span>
        </button>

        {/* RICARICA */}
        <button
          type="button"
          className="btn-touch pointer-events-auto absolute flex items-center justify-center rounded-full border-2 border-white/50 bg-[#1b1f3b]/75 text-lg"
          style={{ right: 150, bottom: 126, width: 46, height: 46 }}
          onPointerDown={(e) => { e.preventDefault(); input.reload = true; }}
          aria-label="Ricarica"
        >
          🔄
        </button>
      </div>

      {/* pausa */}
      <button
        type="button"
        onPointerDown={(e) => { e.preventDefault(); onPause(); }}
        className="btn-touch absolute flex h-9 w-9 items-center justify-center rounded-full border-2 border-white/50 bg-black/40 text-sm font-black"
        style={{ top: 'max(8px, env(safe-area-inset-top))', right: 'max(8px, env(safe-area-inset-right))' }}
        data-ui
        aria-label="Pausa"
      >
        II
      </button>
    </div>
  );
}
