import { handleUpload, handleUploadPresigned } from '@vercel/blob/client';
import { issueSignedToken } from '@vercel/blob';
import { json, blobToken } from './_lib.js';

const PATH_RE = /^media\/[a-z0-9-]{8,40}\/[^/]{1,200}$/;
const LIMITS = {
  allowedContentTypes: ['image/*', 'video/*'],
  maximumSizeInBytes: 5 * 1024 * 1024 * 1024,
};

function checkPath(pathname) {
  if (!PATH_RE.test(pathname || '')) throw new Error('Percorso non valido');
}

// Rilascia al browser il permesso di caricare il file direttamente sul Blob store
// (niente limite di 4.5 MB delle funzioni Vercel: i video vanno diretti).
// Due modalità, scelte in automatico:
// - presigned (store collegato con BLOB_STORE_ID + OIDC, il default attuale di Vercel)
// - client token (store collegato con il vecchio BLOB_READ_WRITE_TOKEN)
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  try {
    if (body.type === 'blob.generate-presigned-url' || body.type === 'blob.upload-completed' && !blobToken()) {
      const result = await handleUploadPresigned({
        body,
        request,
        getSignedToken: async (pathname) => {
          checkPath(pathname);
          const token = await issueSignedToken({
            pathname,
            operations: ['put'],
            validUntil: Date.now() + 2 * 60 * 60 * 1000,
            ...LIMITS,
          });
          return { token, urlOptions: { ...LIMITS, addRandomSuffix: false, allowOverwrite: false } };
        },
      });
      return json(result);
    }
    const result = await handleUpload({
      body,
      request,
      token: blobToken(),
      onBeforeGenerateToken: async (pathname) => {
        checkPath(pathname);
        return { ...LIMITS, addRandomSuffix: false, allowOverwrite: false };
      },
    });
    return json(result);
  } catch (err) {
    console.error('upload error:', err);
    return json({ error: err.message }, 400);
  }
}
