import * as THREE from 'three';

// Risorse condivise per lo stile cartoon: gradiente a 3 toni + materiale contorno.
let grad = null;
let outline = null;

export function gradient() {
  if (!grad) {
    grad = new THREE.DataTexture(new Uint8Array([105, 175, 255]), 3, 1, THREE.RedFormat);
    grad.minFilter = grad.magFilter = THREE.NearestFilter;
    grad.generateMipmaps = false;
    grad.needsUpdate = true;
  }
  return grad;
}

export const toonMat = (color, extra = {}) =>
  new THREE.MeshToonMaterial({ color, gradientMap: gradient(), ...extra });

export function outlineMaterial() {
  if (!outline) outline = new THREE.MeshBasicMaterial({ color: '#1b1f3b', side: THREE.BackSide });
  return outline;
}

export function shade(hex, l) {
  const c = new THREE.Color(hex);
  c.offsetHSL(0, 0, l);
  return `#${c.getHexString()}`;
}

/** Etichetta di testo come texture canvas (nomi, stati). */
export function makeLabel(text, { bg = 'rgba(27,31,59,0.82)', fg = '#fff', font = 'bold 44px system-ui, sans-serif', h = 72, pad = 28 } = {}) {
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  ctx.font = font;
  const w = Math.ceil(ctx.measureText(text).width + pad * 2);
  c.width = w; c.height = h;
  ctx.font = font;
  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.roundRect(0, 0, w, h, h / 2);
  ctx.fill();
  ctx.fillStyle = fg;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, w / 2, h / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return { tex, aspect: w / h };
}

export function disposeToon() {
  grad?.dispose(); outline?.dispose();
  grad = null; outline = null;
}
