export default function EndScreen({ result, onAgain, onLobby }) {
  const winner = result.ranking[0];
  const me = result.ranking.find((r) => r.isPlayer);
  const won = winner.isPlayer;
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/70 backdrop-blur-sm" data-ui>
      <div className="pop-in flex max-h-[92%] w-[min(92vw,460px)] flex-col gap-2 rounded-2xl border-2 border-white/20 bg-[#1b1f3b] p-4 shadow-2xl">
        <p className="text-center text-[11px] font-black uppercase tracking-widest text-white/60">Fine partita</p>
        <h2 className="text-center font-display text-2xl font-black leading-tight" style={{ color: winner.color }}>
          {won ? '🏆 HAI VINTO!' : `Vince ${winner.name}`}
        </h2>
        <div className="scroll-y flex flex-col gap-1">
          {result.ranking.map((r, i) => (
            <div key={r.id} className={`flex items-center gap-2 rounded-lg px-2 py-1 text-sm font-extrabold ${r.isPlayer ? 'bg-[#ffcf5a]/20' : 'bg-white/5'}`}>
              <span className="w-5 text-white/50">{i + 1}</span>
              <span className="h-3 w-3 rounded-full" style={{ background: r.color }} />
              <span className="flex-1 truncate">{r.name}</span>
              <span className="tabular-nums text-white/70">{r.kills} K</span>
              <span className="w-12 text-right tabular-nums text-white/40">{r.deaths} D</span>
            </div>
          ))}
        </div>
        {me && <p className="text-center text-xs font-bold text-white/60">Il tuo risultato: {me.kills} uccisioni, {me.deaths} morti</p>}
        <div className="mt-1 grid grid-cols-2 gap-2">
          <button type="button" onClick={onAgain} className="btn-touch rounded-xl border-b-4 border-[#b8860b] bg-[#ffcf5a] py-2 font-display text-lg font-black text-[#1b1f3b]">Rigioca</button>
          <button type="button" onClick={onLobby} className="btn-touch rounded-xl border-b-4 border-black/40 bg-white/15 py-2 font-display text-base font-black">Lobby</button>
        </div>
      </div>
    </div>
  );
}
