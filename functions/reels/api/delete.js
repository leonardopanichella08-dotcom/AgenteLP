import { del, list } from '@vercel/blob';
import { ID_RE, json, blobOpts } from './_lib.js';

// Elimina definitivamente un media e il suo tag (es. file caricato per errore).
export async function POST(request) {
  const { id } = await request.json().catch(() => ({}));
  if (!ID_RE.test(id || '')) return json({ error: 'id non valido' }, 400);
  const [media, tags] = await Promise.all([
    list({ prefix: `media/${id}/`, ...blobOpts() }),
    list({ prefix: `tags/${id}/`, ...blobOpts() }),
  ]);
  const urls = [...media.blobs, ...tags.blobs].map((b) => b.url);
  if (urls.length) await del(urls, blobOpts());
  return json({ ok: true });
}
