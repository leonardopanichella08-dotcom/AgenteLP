// I 7 personaggi giocabili.
//
// FOTO: metti il file in  public/avatars/<id>.jpg  (vedi public/avatars/README.md).
// Se manca, UI e faccia 3D usano un placeholder cartoon con le iniziali.

export const CHARACTERS = [
  { id: 'leonardo',   name: 'Leonardo Panichella', short: 'Leonardo',   initials: 'LP', photo: '/avatars/leonardo.jpg',   color: '#ff4d4d', skin: '#ffd2a8', role: 'Assaltatore',   loadout: 'assalto', power: 'speed' },
  { id: 'stefano',    name: 'Stefano Piccinini',   short: 'Stefano',    initials: 'SP', photo: '/avatars/stefano.jpg',    color: '#ffb020', skin: '#f6c196', role: 'Stratega',      loadout: 'tattico', power: 'shield' },
  { id: 'seba',       name: 'Seba',                short: 'Seba',       initials: 'SE', photo: '/avatars/seba.jpg',       color: '#2ecc71', skin: '#ffd8b8', role: 'Pugile',        loadout: 'brawler', power: 'rapid' },
  { id: 'riccardo',   name: 'Riccardo Pavone',     short: 'Riccardo',   initials: 'RP', photo: '/avatars/riccardo.jpg',   color: '#3da5ff', skin: '#f2bf94', role: 'Cecchino',      loadout: 'assalto', power: 'ricochet' },
  { id: 'lorenzo',    name: 'Lorenzo Ceri',        short: 'Lorenzo',    initials: 'LC', photo: '/avatars/lorenzo.jpg',    color: '#a35bff', skin: '#ffd2a8', role: 'Demolitore',    loadout: 'tattico', power: 'mega' },
  { id: 'federico',   name: 'Federico Pulcini',    short: 'Federico',   initials: 'FP', photo: '/avatars/federico.jpg',   color: '#ff5fa2', skin: '#f6c196', role: 'Infiltrato',    loadout: 'brawler', power: 'ghost' },
  { id: 'ferdinando', name: 'Ferdinando Canullo',  short: 'Ferdinando', initials: 'FC', photo: '/avatars/ferdinando.jpg', color: '#19d3c5', skin: '#ffd8b8', role: 'Medico da campo', loadout: 'assalto', power: 'regen' },
];

export const getCharacter = (id) => CHARACTERS.find((c) => c.id === id) || CHARACTERS[0];
