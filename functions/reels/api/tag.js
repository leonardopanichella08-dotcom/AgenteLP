import { put, del, list } from '@vercel/blob';
import { ACCESS, ID_RE, authorized, unauthorized, json } from './_lib.js';
import { isValidTreatment } from '../src/treatments.js';

// Assegna (o rimuove, con treatment = null) il trattamento di un media.
export async function POST(request) {
  if (!authorized(request)) return unauthorized();
  const { id, treatment } = await request.json().catch(() => ({}));
  if (!ID_RE.test(id || '')) return json({ error: 'id non valido' }, 400);
  if (treatment !== null && !isValidTreatment(treatment)) {
    return json({ error: 'trattamento non valido' }, 400);
  }

  const existing = await list({ prefix: `tags/${id}/` });
  const stale = existing.blobs.filter((b) => b.pathname !== `tags/${id}/${treatment}`);
  if (stale.length) await del(stale.map((b) => b.url));

  if (treatment && stale.length === existing.blobs.length) {
    await put(`tags/${id}/${treatment}`, '1', {
      access: ACCESS,
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType: 'text/plain',
    });
  }
  return json({ id, treatment });
}
