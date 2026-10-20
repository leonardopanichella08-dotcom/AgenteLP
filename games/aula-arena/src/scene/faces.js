// Texture della faccia 3D di ogni personaggio. Prova a caricare la foto reale
// (char.photo); finché non c'è (o se manca il file) resta il placeholder cartoon.
import * as THREE from 'three';

const SIZE = 256;
const cache = new Map();

function circleClip(ctx) {
  ctx.beginPath();
  ctx.arc(SIZE / 2, SIZE / 2, SIZE / 2 - 4, 0, Math.PI * 2);
  ctx.closePath();
}

function drawPlaceholder(ctx, char) {
  ctx.clearRect(0, 0, SIZE, SIZE);
  ctx.save();
  circleClip(ctx); ctx.clip();
  ctx.fillStyle = char.skin; ctx.fillRect(0, 0, SIZE, SIZE);
  // guance
  ctx.fillStyle = 'rgba(255,110,110,0.35)';
  ctx.beginPath(); ctx.arc(64, 160, 22, 0, 7); ctx.arc(192, 160, 22, 0, 7); ctx.fill();
  // occhi
  ctx.fillStyle = '#fff';
  ctx.beginPath(); ctx.ellipse(88, 112, 22, 28, 0, 0, 7); ctx.ellipse(168, 112, 22, 28, 0, 0, 7); ctx.fill();
  ctx.fillStyle = '#1b1f3b';
  ctx.beginPath(); ctx.arc(92, 118, 12, 0, 7); ctx.arc(164, 118, 12, 0, 7); ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.beginPath(); ctx.arc(96, 112, 4, 0, 7); ctx.arc(168, 112, 4, 0, 7); ctx.fill();
  // sorriso
  ctx.strokeStyle = '#1b1f3b'; ctx.lineWidth = 9; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.arc(128, 150, 40, 0.25, Math.PI - 0.25); ctx.stroke();
  // sopracciglia
  ctx.lineWidth = 8;
  ctx.beginPath(); ctx.moveTo(62, 76); ctx.lineTo(112, 70); ctx.moveTo(144, 70); ctx.lineTo(194, 76); ctx.stroke();
  ctx.restore();
  ctx.lineWidth = 8; ctx.strokeStyle = '#1b1f3b';
  circleClip(ctx); ctx.stroke();
}

function drawPhoto(ctx, img) {
  ctx.clearRect(0, 0, SIZE, SIZE);
  ctx.save();
  circleClip(ctx); ctx.clip();
  const s = Math.max(SIZE / img.width, SIZE / img.height); // "cover"
  const w = img.width * s, h = img.height * s;
  ctx.drawImage(img, (SIZE - w) / 2, (SIZE - h) / 2, w, h);
  ctx.restore();
  ctx.lineWidth = 10; ctx.strokeStyle = '#1b1f3b';
  circleClip(ctx); ctx.stroke();
}

export function getFaceTexture(char) {
  let entry = cache.get(char.id);
  if (entry) return entry.tex;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = SIZE;
  const ctx = canvas.getContext('2d');
  drawPlaceholder(ctx, char);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 2;
  entry = { tex, disposed: false };
  cache.set(char.id, entry);

  const img = new Image();
  img.onload = () => {
    if (entry.disposed) return;
    drawPhoto(ctx, img);
    tex.needsUpdate = true;
  };
  img.onerror = () => {}; // nessuna foto: resta il placeholder
  img.src = char.photo;
  return tex;
}

export function disposeFaces() {
  for (const e of cache.values()) { e.disposed = true; e.tex.dispose(); }
  cache.clear();
}
