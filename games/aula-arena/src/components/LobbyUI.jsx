import { CHARACTERS, getCharacter } from '../game/characters.js';
import { LOADOUTS, POWERS, WEAPONS } from '../game/weapons.js';
import { MATCH } from '../game/constants.js';
import Avatar from './Avatar.jsx';

const STAT_LABEL = { potenza: 'Potenza', raggio: 'Raggio', cadenza: 'Cadenza', mobilita: 'Mobilità' };

function Stat({ label, value, color }) {
  return (
    <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-white/80">
      <span className="w-[62px] shrink-0">{label}</span>
      <div className="flex gap-[3px]">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className="h-[7px] w-[14px] rounded-sm" style={{ background: i <= value ? color : 'rgba(255,255,255,0.15)' }} />
        ))}
      </div>
    </div>
  );
}

function RosterCard({ char, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`btn-touch relative flex w-[76px] shrink-0 flex-col items-center rounded-xl border-2 p-1 text-center short:w-full short:flex-row short:gap-2 short:text-left ${active ? 'border-[#ffcf5a] bg-white/15' : 'border-white/10 bg-white/5'}`}
      style={active ? { boxShadow: `0 0 18px ${char.color}aa` } : undefined}
    >
      <Avatar char={char} className="aspect-square w-full rounded-lg short:w-9 short:shrink-0" />
      <span className="mt-1 w-full truncate text-[11px] font-extrabold leading-tight short:mt-0">{char.short}</span>
      <span className="h-[3px] w-full rounded-full short:hidden" style={{ background: char.color }} />
      <span className="hidden h-6 w-[3px] shrink-0 rounded-full short:block" style={{ background: char.color }} />
    </button>
  );
}

export default function LobbyUI({ charId, loadoutId, onSelectChar, onSelectLoadout, onPlay, onFullscreen }) {
  const char = getCharacter(charId);
  const lo = LOADOUTS[loadoutId];
  const power = POWERS[char.power];

  return (
    <div className="scroll-y absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,#33407a_0%,#1b1f3b_60%)] short:overflow-hidden">
      <div className="safe-l safe-r safe-t safe-b mx-auto flex min-h-full max-w-5xl flex-col gap-3 short:grid short:h-full short:min-h-0 short:max-w-none short:grid-cols-[132px_minmax(0,1fr)_minmax(0,1.25fr)] short:grid-rows-[auto_minmax(0,1fr)_auto] short:gap-2">
        {/* intestazione */}
        <header className="flex items-center justify-between gap-2 short:col-span-3">
          <div>
            <h1 className="font-display text-2xl font-black leading-none tracking-tight text-[#ffcf5a] drop-shadow sm:text-3xl">
              AULA <span className="text-white">ARENA</span>
            </h1>
            <p className="text-[11px] font-bold uppercase tracking-widest text-white/60">
              Tutti contro tutti · primo a {MATCH.killLimit} · {MATCH.duration / 60} min
            </p>
          </div>
          <button type="button" onClick={onFullscreen} className="btn-touch rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-xs font-extrabold">
            ⛶ Schermo intero
          </button>
        </header>

        {/* scheda personaggio + loadout */}
        <section className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-[minmax(190px,32%)_1fr] short:contents">
          {/* scheda stile "operator" */}
          <div className="relative flex gap-3 overflow-hidden rounded-2xl border-2 border-white/15 bg-black/25 p-3 sm:flex-col short:col-start-2 short:row-start-2 short:flex-row short:gap-2 short:p-2" style={{ boxShadow: `inset 0 0 60px ${char.color}44` }}>
            <div className="relative w-[34%] shrink-0 sm:w-full short:w-[36%]">
              <Avatar char={char} className="aspect-square w-full rounded-xl border-[3px] border-[#1b1f3b] shadow-xl" />
              <span className="absolute left-2 top-2 rounded-md bg-[#1b1f3b]/85 px-2 py-0.5 text-[10px] font-black uppercase tracking-widest" style={{ color: char.color }}>
                {char.role}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-xl font-black leading-tight sm:text-2xl short:text-lg">{char.name}</h2>
              <div className="mt-2 rounded-lg border border-white/10 bg-white/10 p-2">
                <p className="text-[10px] font-black uppercase tracking-widest text-white/60">Superpotere · 5 secondi</p>
                <p className="text-sm font-extrabold" style={{ color: power.color }}>{power.icon} {power.name}</p>
                <p className="text-[11px] leading-snug text-white/75">{power.desc}</p>
              </div>
            </div>
          </div>

          {/* loadout */}
          <div className="flex flex-col gap-3 rounded-2xl border-2 border-white/15 bg-black/25 p-3 short:col-start-3 short:row-start-2 short:min-h-0 short:gap-1.5 short:overflow-hidden short:p-2">
            <p className="text-[10px] font-black uppercase tracking-widest text-white/60">Pacchetto armi / Loadout</p>
            <div className="grid grid-cols-3 gap-2">
              {Object.values(LOADOUTS).map((l) => (
                <button
                  key={l.id}
                  type="button"
                  onClick={() => onSelectLoadout(l.id)}
                  className={`btn-touch rounded-xl border-2 px-2 py-2 text-left ${l.id === loadoutId ? 'border-[#ffcf5a] bg-[#ffcf5a]/20' : 'border-white/10 bg-white/5'}`}
                >
                  <span className="block text-sm font-black">{l.name}</span>
                  <span className="block truncate text-[10px] font-bold text-white/60">
                    {l.slots.map((s) => WEAPONS[s].name).join(' + ')}
                  </span>
                  {l.id === char.loadout && <span className="mt-1 inline-block rounded bg-white/15 px-1.5 text-[9px] font-black uppercase">Di serie</span>}
                </button>
              ))}
            </div>
            <p className="text-xs font-semibold leading-snug text-white/80">{lo.desc}</p>
            <div className="flex flex-col gap-1.5">
              {Object.entries(lo.stats).map(([k, v]) => (
                <Stat key={k} label={STAT_LABEL[k]} value={v} color={char.color} />
              ))}
            </div>
            <p className="mt-auto rounded-lg bg-white/5 p-2 text-[11px] leading-snug text-white/70 short:hidden">
              🎓 Ogni 60-90 s scatta l&apos;<b className="text-[#ffcf5a]">Interrogazione a Sorpresa</b>: la ruota sceglie un
              interrogato. Per 7 secondi solo lui può sparare, gli altri sono <b>impreparati</b>: possono solo correre e schivare!
            </p>
          </div>
        </section>

        {/* roster */}
        <section className="short:col-start-1 short:row-span-2 short:row-start-2 short:min-h-0">
          <p className="mb-1 text-[10px] font-black uppercase tracking-widest text-white/60 short:hidden">Scegli il tuo compagno</p>
          <div className="lb-roster-list">
            {CHARACTERS.map((c) => (
              <RosterCard key={c.id} char={c} active={c.id === charId} onClick={() => onSelectChar(c.id)} />
            ))}
          </div>
        </section>

        <footer className="flex items-center justify-between gap-3 short:col-start-2 short:col-span-2 short:row-start-3">
          <p className="hidden text-[11px] font-semibold text-white/55 xs:block short:text-[10px]">
            Joystick a sinistra per muoverti · trascina a destra per guardare · tasto rosso per sparare.
            <br />PC: WASD + mouse · E potere · Q secondaria · R ricarica
          </p>
          <button
            type="button"
            onClick={onPlay}
            className="btn-touch ml-auto rounded-2xl border-b-4 border-[#b8860b] bg-[#ffcf5a] px-10 py-3 font-display text-xl font-black text-[#1b1f3b] shadow-lg short:py-2"
          >
            GIOCA ▶
          </button>
        </footer>
      </div>
    </div>
  );
}
