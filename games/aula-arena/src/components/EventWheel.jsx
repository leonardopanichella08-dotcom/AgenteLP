import { useEffect, useState } from 'react';
import { CHARACTERS } from '../game/characters.js';
import { EVENT } from '../game/constants.js';

const N = CHARACTERS.length;
const SEG = 360 / N;
const R = 96;

function wedge(i) {
  const a0 = ((i * SEG - 90) * Math.PI) / 180;
  const a1 = (((i + 1) * SEG - 90) * Math.PI) / 180;
  const x0 = Math.cos(a0) * R, y0 = Math.sin(a0) * R, x1 = Math.cos(a1) * R, y1 = Math.sin(a1) * R;
  return `M0 0 L${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`;
}

/** Ruota della fortuna: gira per EVENT.spin secondi e si ferma sull'interrogato (puntatore in alto). */
export default function EventWheel({ targetIndex, revealed }) {
  const [rot, setRot] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setRot(360 * 5 - (targetIndex + 0.5) * SEG)));
    return () => cancelAnimationFrame(id);
  }, [targetIndex]);

  return (
    <div className="relative pop-in" style={{ width: 'min(42vh, 210px)', height: 'min(42vh, 210px)' }}>
      <div
        className="h-full w-full rounded-full border-[5px] border-[#1b1f3b] bg-[#1b1f3b] shadow-2xl"
        style={{ transform: `rotate(${rot}deg)`, transition: `transform ${EVENT.spin}s cubic-bezier(0.12, 0.6, 0.1, 1)` }}
      >
        <svg viewBox="-100 -100 200 200" className="h-full w-full">
          {CHARACTERS.map((c, i) => (
            <g key={c.id}>
              <path d={wedge(i)} fill={c.color} stroke="#1b1f3b" strokeWidth="2" opacity={revealed && i !== targetIndex ? 0.35 : 1} />
              <text
                transform={`rotate(${i * SEG + SEG / 2 - 90}) translate(${R * 0.6} 0)`}
                textAnchor="middle" dominantBaseline="middle" fontSize={c.short.length > 7 ? 9 : 11.5} fontWeight="900" fill="#fff"
                stroke="#1b1f3b" strokeWidth="2.2" paintOrder="stroke"
              >
                {c.short}
              </text>
            </g>
          ))}
          <circle r="13" fill="#ffcf5a" stroke="#1b1f3b" strokeWidth="3" />
        </svg>
      </div>
      {/* puntatore */}
      <div className="absolute left-1/2 -top-3 -translate-x-1/2" style={{ width: 0, height: 0, borderLeft: '12px solid transparent', borderRight: '12px solid transparent', borderTop: '26px solid #ffcf5a', filter: 'drop-shadow(0 2px 0 #1b1f3b)' }} />
    </div>
  );
}
