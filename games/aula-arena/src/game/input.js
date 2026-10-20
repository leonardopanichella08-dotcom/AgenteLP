// Stato di input condiviso e mutabile: scritto da Controls, letto dalla simulazione.
// Nessun setState nel percorso caldo => zero re-render e zero lag.
export const input = {
  moveX: 0, moveY: 0, // joystick: x = destra, y = avanti (-1..1)
  lookDX: 0, lookDY: 0, // pixel accumulati dall'ultimo frame
  fire: false,
  secondary: false, power: false, reload: false, // eventi "a fronte"
  sens: 0.0055, // radianti per pixel
};

export function resetInput() {
  input.moveX = input.moveY = input.lookDX = input.lookDY = 0;
  input.fire = input.secondary = input.power = input.reload = false;
}
