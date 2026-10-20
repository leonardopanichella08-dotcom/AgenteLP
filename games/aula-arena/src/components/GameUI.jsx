import { useEffect, useState } from 'react';
import { POWERS, WEAPONS } from '../game/weapons.js';
import { isPowerActive, isUnprepared } from '../game/util.js';
import { POWER_DURATION } from '../game/constants.js';
import HUD from './HUD.jsx';
import Controls from './Controls.jsx';

const GADGET_ICON = { dash: '💨', grenade: '💣' };
const norm = (a) => { const t = Math.PI * 2; return ((a + Math.PI) % t + t) % t - Math.PI; };

/** Fotografia leggera dello stato di gioco per la UI React (~12 Hz). */
function buildSnap(st) {
  const p = st.player, t = st.time, ev = st.event;
  const w = WEAPONS[p.slots[p.cur]];
  const s1 = WEAPONS[p.slots[1]];
  const pw = POWERS[p.powerId];
  const gadget = s1.kind === 'gadget';
  const cdLeft = Math.max(0, p.gadgetReadyAt - t);
  const sorted = [...st.entities].sort((a, b) => b.kills - a.kills || a.deaths - b.deaths);
  const top = sorted.slice(0, 3).map((e, i) => ({ id: e.id, name: e.name, color: e.color, kills: e.kills, isPlayer: e.isPlayer, rank: i + 1 }));
  if (!top.some((r) => r.isPlayer)) {
    top.push({ id: p.id, name: p.name, color: p.color, kills: p.kills, isPlayer: true, rank: sorted.indexOf(p) + 1 });
  }
  const target = ev.targetId ? st.entities.find((e) => e.id === ev.targetId) : null;
  const hitAge = t - p.hitMarkerAt, killAge = t - p.killMarkerAt, dmgAge = t - p.lastDamageAt;
  const rel = norm(p.hitDir - (p.yaw + Math.PI));
  const powerActive = isPowerActive(p, t);
  return {
    alive: p.alive, hp: p.hp, maxHp: 100, respawnIn: Math.max(0, p.respawnAt - t),
    timeLeft: Math.max(0, st.duration - t), killLimit: st.killLimit, top,
    feed: st.feed.slice(-4).map((f) => ({ ...f })),
    weaponName: w.name, ammo: p.ammo[p.cur], mag: w.mag, infinite: isPowerActive(p, t, 'rapid'),
    reloading: p.reloadEnd[p.cur] > t,
    charge: p.charge, powerActive, powerLeft: Math.max(0, p.powerUntil - t), powerName: pw.name, powerIcon: pw.icon, powerColor: pw.color,
    secondary: gadget
      ? { gadget: true, name: s1.name, icon: GADGET_ICON[s1.gadget], cdLeft, cdFrac: cdLeft / s1.cooldown }
      : { gadget: false, name: WEAPONS[p.slots[1 - p.cur]].name, icon: '⇄', cdLeft: 0, cdFrac: 0 },
    unprepared: isUnprepared(st, p), stunned: t < p.stunUntil, protect: t < p.protectUntil,
    hitMarker: hitAge < 0.25 ? 1 - hitAge / 0.25 : 0,
    killMarker: killAge < 0.4 ? 1 : 0,
    damageFlash: Math.max(dmgAge < 0.5 ? 1 - dmgAge / 0.5 : 0, p.alive && p.hp < 30 ? 0.25 : 0),
    hitAngle: -rel,
    event: {
      phase: ev.phase, seq: ev.seq, remaining: Math.max(0, ev.phaseEnd - t), elapsed: t - ev.phaseStart,
      targetName: target ? target.name : '', targetIndex: target ? st.entities.indexOf(target) : 0,
      youAsked: ev.targetId === p.id,
    },
    _powerDur: POWER_DURATION,
  };
}

export default function GameUI({ stateRef, input, pausedRef, paused, isTouch, onPause, onResume, onQuit, sens, onSens }) {
  const [snap, setSnap] = useState(() => buildSnap(stateRef.current));
  useEffect(() => {
    const id = setInterval(() => { if (stateRef.current) setSnap(buildSnap(stateRef.current)); }, 80);
    return () => clearInterval(id);
  }, [stateRef]);

  return (
    <div className="absolute inset-0 touch-none">
      <HUD snap={snap} />
      <Controls input={input} snap={snap} isTouch={isTouch} pausedRef={pausedRef} onPause={onPause} />
      {paused && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/65 backdrop-blur-sm" data-ui>
          <div className="pop-in flex w-[min(86vw,340px)] flex-col gap-3 rounded-2xl border-2 border-white/20 bg-[#1b1f3b] p-5 shadow-2xl">
            <h2 className="text-center font-display text-2xl font-black text-[#ffcf5a]">PAUSA</h2>
            <label className="text-xs font-extrabold uppercase tracking-wide text-white/70">
              Sensibilità visuale
              <input
                type="range" min="0.5" max="2" step="0.05" value={sens} onChange={(e) => onSens(Number(e.target.value))}
                className="mt-1 block w-full accent-[#ffcf5a]"
              />
            </label>
            <button type="button" onClick={onResume} className="btn-touch rounded-xl border-b-4 border-[#b8860b] bg-[#ffcf5a] py-2 font-display text-lg font-black text-[#1b1f3b]">Riprendi</button>
            <button type="button" onClick={onQuit} className="btn-touch rounded-xl border-b-4 border-black/40 bg-white/15 py-2 font-display text-base font-black">Esci alla lobby</button>
          </div>
        </div>
      )}
    </div>
  );
}
