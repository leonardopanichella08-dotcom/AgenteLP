import { presignPut, json } from './_store.js';

const PATH_RE = /^media\/[a-z0-9-]{8,40}\/[^/]{1,200}$/;
const MAX = 5 * 1024 * 1024 * 1024; // limite di un singolo PUT su R2

// Restituisce un URL firmato: il browser carica il file direttamente su R2
// (niente limite di 4.5 MB delle funzioni Vercel).
export async function POST(request) {
  const { pathname, contentType, size } = await request.json().catch(() => ({}));
  if (!PATH_RE.test(pathname || '')) return json({ error: 'Percorso non valido' }, 400);
  if (!/^(image|video)\//.test(contentType || '')) return json({ error: 'Sono ammessi solo foto e video' }, 400);
  if (!(size > 0 && size <= MAX)) return json({ error: 'File troppo grande (max 5 GB)' }, 400);
  try {
    return json({ url: await presignPut(pathname, contentType) });
  } catch (err) {
    console.error('upload error:', err);
    return json({ error: err.message }, 500);
  }
}
