import { listAll, putSmall, deleteKeys, ID_RE, json } from './_store.js';
import { isValidTreatment } from '../src/treatments.js';

// Assegna (o rimuove, con treatment = null) il trattamento di un media.
export async function POST(request) {
  const { id, treatment } = await request.json().catch(() => ({}));
  if (!ID_RE.test(id || '')) return json({ error: 'id non valido' }, 400);
  if (treatment !== null && !isValidTreatment(treatment)) {
    return json({ error: 'trattamento non valido' }, 400);
  }
  try {
    const target = `tags/${id}/${treatment}`;
    const existing = await listAll(`tags/${id}/`);
    const stale = existing.filter((o) => o.key !== target).map((o) => o.key);
    if (stale.length) await deleteKeys(stale);
    if (treatment && !existing.some((o) => o.key === target)) await putSmall(target, '1');
    return json({ id, treatment });
  } catch (err) {
    console.error('tag error:', err);
    return json({ error: err.message }, 500);
  }
}
