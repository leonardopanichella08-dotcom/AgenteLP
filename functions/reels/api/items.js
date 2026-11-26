import { list } from '@vercel/blob';
import { json, blobOpts } from './_lib.js';
import { isValidTreatment } from '../src/treatments.js';

async function listAll(prefix) {
  const out = [];
  let cursor;
  do {
    const page = await list({ prefix, cursor, limit: 1000, ...blobOpts() });
    out.push(...page.blobs);
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return out;
}

const VIDEO_EXT = /\.(mp4|mov|m4v|webm|3gp|avi|mkv|hevc)$/i;

// Elenco di tutti i media con il trattamento assegnato.
// Media: media/<id>/<nome file>   Tag: tags/<id>/<trattamento>
export async function GET() {
  const [media, tags] = await Promise.all([listAll('media/'), listAll('tags/')]);

  const tagById = new Map();
  for (const t of tags) {
    const [, id, treatment] = t.pathname.split('/');
    if (id && isValidTreatment(treatment)) tagById.set(id, treatment);
  }

  const items = media
    .map((b) => {
      const [, id, ...rest] = b.pathname.split('/');
      const name = rest.join('/');
      return {
        id,
        name,
        url: b.url,
        downloadUrl: b.downloadUrl,
        size: b.size,
        uploadedAt: b.uploadedAt,
        kind: VIDEO_EXT.test(name) ? 'video' : 'image',
        treatment: tagById.get(id) || null,
      };
    })
    .sort((a, b) => a.id.localeCompare(b.id));

  return json({ items });
}
