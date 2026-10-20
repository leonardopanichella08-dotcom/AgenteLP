import { useState } from 'react';

/** Placeholder cartoon (SVG) mostrato finché non esiste la foto in public/avatars/. */
function Placeholder({ char }) {
  return (
    <svg viewBox="0 0 100 100" className="h-full w-full" role="img" aria-label={char.name}>
      <defs>
        <linearGradient id={`g-${char.id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={char.color} />
          <stop offset="1" stopColor="#1b1f3b" />
        </linearGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#g-${char.id})`} />
      <circle cx="50" cy="108" r="46" fill={char.color} stroke="#1b1f3b" strokeWidth="3" />
      <circle cx="50" cy="50" r="27" fill={char.skin} stroke="#1b1f3b" strokeWidth="3" />
      <path d="M23 46 Q50 8 77 46 Q50 30 23 46Z" fill="#1b1f3b" opacity="0.85" />
      <ellipse cx="40" cy="52" rx="4.5" ry="6" fill="#fff" /><circle cx="41" cy="53" r="2.6" fill="#1b1f3b" />
      <ellipse cx="60" cy="52" rx="4.5" ry="6" fill="#fff" /><circle cx="61" cy="53" r="2.6" fill="#1b1f3b" />
      <path d="M40 64 Q50 73 60 64" stroke="#1b1f3b" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="33" cy="62" r="4" fill="#ff6e6e" opacity="0.35" /><circle cx="67" cy="62" r="4" fill="#ff6e6e" opacity="0.35" />
      <text x="50" y="96" textAnchor="middle" fontSize="13" fontWeight="800" fill="#fff" stroke="#1b1f3b" strokeWidth="0.8" paintOrder="stroke">{char.initials}</text>
    </svg>
  );
}

export default function Avatar({ char, className = '' }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={`overflow-hidden ${className}`}>
      {failed ? (
        <Placeholder char={char} />
      ) : (
        <img
          key={char.id}
          src={char.photo}
          alt={char.name}
          draggable={false}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
