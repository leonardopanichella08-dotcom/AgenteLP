// Costanti globali di gioco. Unità = metri.
export const WORLD = { halfX: 30, halfZ: 22, wallH: 6 };

export const BODY = {
  radius: 0.45, // raggio di collisione col mondo
  hitRadius: 0.55, // raggio colpibile dai proiettili
  eye: 1.62,
  height: 1.9,
  chest: 1.15,
  baseSpeed: 6.4,
  maxHp: 100,
};

export const MATCH = {
  killLimit: 15,
  duration: 300, // secondi
  respawn: 3,
  spawnProtect: 2,
};

// Evento "Interrogazione a Sorpresa"
export const EVENT = { minGap: 60, maxGap: 90, spin: 3, active: 7 };

export const POWER_DURATION = 5;
export const AI_SPEED_FACTOR = 0.86;
