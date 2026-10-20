// Armi, gadget, loadout e superpoteri. Solo dati: nessuna logica.

export const WEAPONS = {
  rifle: {
    id: 'rifle', name: 'Fucile Automatico', kind: 'hitscan',
    damage: 9, rate: 9, mag: 30, reload: 1.7, spread: 0.022, range: 55,
    pellets: 1, recoil: 0.5, prefDist: 13, color: '#3b4260',
  },
  pistol: {
    id: 'pistol', name: 'Pistola Rapida', kind: 'hitscan',
    damage: 8, rate: 7, mag: 16, reload: 1.1, spread: 0.03, range: 40,
    pellets: 1, recoil: 0.35, prefDist: 10, color: '#4a4f6e',
  },
  shotgun: {
    id: 'shotgun', name: 'Fucile a Pompa', kind: 'hitscan',
    damage: 6, rate: 1.25, mag: 6, reload: 2.2, spread: 0.1, range: 16,
    pellets: 8, recoil: 1.4, prefDist: 6, color: '#7a4a2b',
  },
  bazooka: {
    id: 'bazooka', name: 'Bazooka', kind: 'rocket',
    damage: 90, rate: 0.75, mag: 2, reload: 2.4, spread: 0.01, range: 70,
    radius: 4.5, speed: 26, recoil: 1.6, prefDist: 15, color: '#55704a',
  },
  dash: {
    id: 'dash', name: 'Scatto Veloce', kind: 'gadget', gadget: 'dash', cooldown: 4,
  },
  grenade: {
    id: 'grenade', name: 'Granata Stordente', kind: 'gadget', gadget: 'grenade',
    cooldown: 7, radius: 6, stun: 2.5, damage: 12,
  },
};

export const LOADOUTS = {
  assalto: {
    id: 'assalto', name: 'Assalto', slots: ['rifle', 'pistol'],
    desc: 'Fucile automatico a medio raggio + pistola rapida.',
    stats: { potenza: 3, raggio: 4, cadenza: 5, mobilita: 3 },
  },
  brawler: {
    id: 'brawler', name: 'Brawler', slots: ['shotgun', 'dash'],
    desc: 'Fucile a pompa devastante da vicino + scatto veloce.',
    stats: { potenza: 5, raggio: 2, cadenza: 2, mobilita: 5 },
  },
  tattico: {
    id: 'tattico', name: 'Tattico', slots: ['bazooka', 'grenade'],
    desc: 'Bazooka ad area (proiettili lenti) + granata stordente.',
    stats: { potenza: 5, raggio: 4, cadenza: 1, mobilita: 2 },
  },
};

export const POWERS = {
  speed:    { id: 'speed',    name: 'Super-Velocità',         icon: '⚡', color: '#ffe14d', desc: 'Corri molto più veloce.' },
  shield:   { id: 'shield',   name: 'Scudo Digitale',         icon: '🛡️', color: '#4dd6ff', desc: 'Subisci il 75% di danni in meno.' },
  ricochet: { id: 'ricochet', name: 'Proiettili Rimbalzanti', icon: '🔁', color: '#ff9f43', desc: 'I colpi rimbalzano sui muri.' },
  rapid:    { id: 'rapid',    name: 'Raffica Infinita',       icon: '🔥', color: '#ff6b4d', desc: 'Cadenza doppia e niente ricarica.' },
  mega:     { id: 'mega',     name: 'Super Voto 10',          icon: '💯', color: '#ff4d8d', desc: 'I tuoi colpi fanno danno doppio.' },
  ghost:    { id: 'ghost',    name: 'Modalità Fantasma',      icon: '👻', color: '#b9a6ff', desc: 'Quasi invisibile ai nemici.' },
  regen:    { id: 'regen',    name: 'Pausa Merenda',          icon: '🍎', color: '#7bed6a', desc: 'Rigeneri vita rapidamente.' },
};
