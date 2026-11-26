import { handleUpload } from '@vercel/blob/client';
import { json } from './_lib.js';

const PATH_RE = /^media\/[a-z0-9-]{8,40}\/[^/]{1,200}$/;

// Rilascia al browser un token per caricare il file direttamente sul Blob store
// (niente limite di 4.5 MB delle funzioni Vercel: i video vanno diretti).
export async function POST(request) {
  const body = await request.json();
  try {
    const result = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        if (!PATH_RE.test(pathname)) throw new Error('Percorso non valido');
        return {
          allowedContentTypes: ['image/*', 'video/*'],
          maximumSizeInBytes: 5 * 1024 * 1024 * 1024,
          addRandomSuffix: false,
          allowOverwrite: false,
        };
      },
    });
    return json(result);
  } catch (err) {
    return json({ error: err.message }, 400);
  }
}
