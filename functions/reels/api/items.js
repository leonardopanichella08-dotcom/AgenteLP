import { listAll, presignGet, json } from './_store.js';
import { isValidTreatment } from '../src/treatments.js';

const VIDEO_EXT = /\.(mp4|mov|m4v|webm|3gp|avi|mkv|hevc)$/i;

// Elenco di tutti i media con il trattamento assegnato.
// Media: media/<id>/<nome file>   Tag: tags/<id>/<trattamento>
export async function GET() {
  try {
    const [media, tags] = await Promise.all([listAll('media/'), listAll('tags/')]);
    const tagById = new Map();
    for (const t of tags) {
      const [, id, treatment] = t.key.split('/');
      if (id && isValidTreatment(treatment)) tagById.set(id, treatment);
    }
    const items = await Promise.all(media.map(async (o) => {
      const [, id, ...rest] = o.key.split('/');
      const name = rest.join('/');
      return {
        id,
        name,
        url: await presignGet(o.key),
        downloadUrl: await presignGet(o.key, name),
        size: o.size,
        uploadedAt: o.lastModified,
        kind: VIDEO_EXT.test(name) ? 'video' : 'image',
        treatment: tagById.get(id) || null,
      };
    }));
    items.sort((a, b) => a.id.localeCompare(b.id));
    return json({ items });
  } catch (err) {
    console.error('items error:', err);
    return json({ error: err.message }, 500);
  }
}
