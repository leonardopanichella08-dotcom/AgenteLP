import EventWheel from './EventWheel.jsx';

const fmtTime = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export default function HUD({ snap }) {
  const ev = snap.event;
  const showWheel = ev.phase === 'spin' || (ev.phase === 'active' && ev.elapsed < 1.6);
  const hpPct = Math.max(0, (snap.hp / snap.maxHp) * 100);
  const hpColor = hpPct > 50 ? '#5be37d' : hpPct > 25 ? '#ffd23f' : '#ff5252';

  return (
    <div className="pointer-events-none absolute inset-0 text-white hud-text">
      {/* vignetta danno */}
      <div className="absolute inset-0" style={{ boxShadow: 'inset 0 0 90px 20px rgba(255,40,40,0.9)', opacity: snap.damageFlash }} />
      {snap.stunned && <div className="absolute inset-0 bg-cyan-200/30" />}

      {/* indicatore direzione danno */}
      {snap.damageFlash > 0.05 && (
        <div className="absolute left-1/2 top-1/2" style={{ transform: `translate(-50%,-50%) rotate(${snap.hitAngle}rad)`, opacity: snap.damageFlash }}>
          <div style={{ marginTop: -120, width: 0, height: 0, borderLeft: '14px solid transparent', borderRight: '14px solid transparent', borderBottom: '26px solid #ff3b3b' }} />
        </div>
      )}

      {/* mirino */}
      {snap.alive && (
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="relative h-8 w-8">
            <span className="absolute left-1/2 top-0 h-2.5 w-[3px] -translate-x-1/2 rounded bg-white shadow-[0_0_0_1px_#1b1f3b]" />
            <span className="absolute bottom-0 left-1/2 h-2.5 w-[3px] -translate-x-1/2 rounded bg-white shadow-[0_0_0_1px_#1b1f3b]" />
            <span className="absolute left-0 top-1/2 h-[3px] w-2.5 -translate-y-1/2 rounded bg-white shadow-[0_0_0_1px_#1b1f3b]" />
            <span className="absolute right-0 top-1/2 h-[3px] w-2.5 -translate-y-1/2 rounded bg-white shadow-[0_0_0_1px_#1b1f3b]" />
            {snap.hitMarker > 0 && (
              <span className="absolute inset-[-6px] rotate-45 rounded-sm border-2" style={{ opacity: snap.hitMarker, borderColor: snap.killMarker > 0 ? '#ff4d4d' : '#fff' }} />
            )}
          </div>
        </div>
      )}

      {/* in alto a sinistra: timer + classifica */}
      <div className="safe-l safe-t absolute left-0 top-0">
        <div className="rounded-xl bg-black/45 px-3 py-1.5 backdrop-blur-sm">
          <div className="flex items-baseline gap-2">
            <span className="font-display text-xl font-black tabular-nums">{fmtTime(snap.timeLeft)}</span>
            <span className="text-[10px] font-bold uppercase tracking-wide text-white/60">primo a {snap.killLimit}</span>
          </div>
          <div className="mt-1 flex flex-col gap-[2px]">
            {snap.top.map((r, i) => (
              <div key={r.id} className={`flex items-center gap-1.5 text-[11px] font-extrabold leading-tight ${r.isPlayer ? 'text-[#ffcf5a]' : 'text-white/85'}`}>
                <span className="w-3 text-white/50">{i + 1}</span>
                <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />
                <span className="w-[74px] truncate">{r.name}</span>
                <span className="tabular-nums">{r.kills}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* kill feed */}
      <div className="absolute flex flex-col items-end gap-1" style={{ top: 'max(52px, calc(env(safe-area-inset-top) + 44px))', right: 'max(10px, env(safe-area-inset-right))' }}>
        {snap.feed.map((f) => (
          <div key={f.t} className="slide-up rounded-md bg-black/50 px-2 py-0.5 text-[11px] font-extrabold">
            <span style={{ color: f.killerColor }}>{f.killer || '☠'}</span>
            <span className="mx-1 text-white/60">▸</span>
            <span style={{ color: f.victimColor }}>{f.victim}</span>
          </div>
        ))}
      </div>

      {/* banner evento */}
      <div className="absolute inset-x-0 flex flex-col items-center gap-1" style={{ top: 'max(8px, env(safe-area-inset-top))' }}>
        {ev.phase === 'spin' && (
          <div className="alert-flash rounded-xl border-2 border-[#1b1f3b] bg-[#ff5252] px-4 py-1 font-display text-base font-black uppercase tracking-wide shadow-xl">
            ⚠ Interrogazione a sorpresa!
          </div>
        )}
        {ev.phase === 'active' && (
          <div className="pop-in flex flex-col items-center rounded-xl border-2 border-[#1b1f3b] bg-[#ffcf5a] px-4 py-1 text-[#1b1f3b] shadow-xl">
            <span className="font-display text-sm font-black uppercase leading-tight">
              Interrogato: {ev.targetName} · {Math.ceil(ev.remaining)}s
            </span>
            <span className="text-[11px] font-extrabold leading-tight">
              {ev.youAsked ? 'Tocca a te: spara a tutti!' : 'Sei IMPREPARATO: corri e schiva, non puoi sparare!'}
            </span>
          </div>
        )}
      </div>

      {showWheel && (
        <div key={ev.seq} className="absolute inset-0 flex items-center justify-center" style={{ paddingTop: 40 }}>
          <div className="flex flex-col items-center gap-2 rounded-3xl bg-black/35 p-4 backdrop-blur-[2px]">
            <EventWheel targetIndex={ev.targetIndex} revealed={ev.phase === 'active'} />
            {ev.phase === 'active' && <p className="pop-in font-display text-lg font-black text-[#ffcf5a] drop-shadow">{ev.targetName}!</p>}
          </div>
        </div>
      )}

      {/* messaggi centrali */}
      {!snap.alive && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <p className="font-display text-3xl font-black text-white drop-shadow-lg">Eliminato</p>
          <p className="text-sm font-bold text-white/80">Rientri in {Math.ceil(snap.respawnIn)}…</p>
        </div>
      )}

      {/* stato in basso al centro: vita + arma */}
      <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 pb-3" style={{ marginLeft: -10 }}>
        {snap.powerActive && (
          <div className="rounded-full px-3 py-0.5 text-xs font-black text-[#1b1f3b]" style={{ background: snap.powerColor }}>
            {snap.powerIcon} {snap.powerName} {snap.powerLeft.toFixed(1)}s
          </div>
        )}
        {snap.charge >= 100 && !snap.powerActive && (
          <div className="alert-flash rounded-full bg-[#ffcf5a] px-3 py-0.5 text-xs font-black text-[#1b1f3b]">{snap.powerIcon} SUPERPOTERE PRONTO</div>
        )}
        <div className="flex items-end gap-3">
          <div className="w-[150px]">
            <div className="h-[14px] overflow-hidden rounded-full border-2 border-[#1b1f3b] bg-black/50">
              <div className="h-full rounded-full transition-[width] duration-150" style={{ width: `${hpPct}%`, background: hpColor }} />
            </div>
            <p className="text-center text-[10px] font-black tabular-nums text-white/80">♥ {Math.ceil(snap.hp)}</p>
          </div>
          <div className="min-w-[90px] rounded-lg bg-black/45 px-2 py-0.5 text-center">
            <p className="text-[10px] font-extrabold uppercase leading-tight text-white/70">{snap.weaponName}</p>
            <p className="font-display text-lg font-black leading-none tabular-nums">
              {snap.reloading ? <span className="text-[#ffcf5a]">RICARICA…</span> : snap.infinite ? '∞' : <>{snap.ammo}<span className="text-xs text-white/50"> / {snap.mag}</span></>}
            </p>
          </div>
        </div>
        {snap.protect && <p className="text-[10px] font-black text-cyan-200">PROTETTO</p>}
      </div>

      <div className="rotate-hint pointer-events-none absolute inset-x-0 top-1/3 flex-col items-center justify-center gap-1 bg-black/70 py-4 text-center">
        <span className="text-4xl">📱↻</span>
        <span className="font-display text-lg font-black">Ruota il telefono in orizzontale</span>
      </div>
    </div>
  );
}
