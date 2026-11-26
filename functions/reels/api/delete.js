import { listAll, deleteKeys, ID_RE, json } from './_store.js';

// Elimina definitivamente un media e il suo tag (es. file caricato per errore).
export async function POST(request) {
  const { id } = await request.json().catch(() => ({}));
  if (!ID_RE.test(id || '')) return json({ error: 'id non valido' }, 400);
  try {
    const [media, tags] = await Promise.all([listAll(`media/${id}/`), listAll(`tags/${id}/`)]);
    await deleteKeys([...media, ...tags].map((o) => o.key));
    return json({ ok: true });
  } catch (err) {
    return json({ error: err.message }, 500);
  }
}
