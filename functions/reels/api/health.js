import { put, del } from '@vercel/blob';
import { ACCESS, json, blobOpts, blobToken } from './_lib.js';

// Controllo di configurazione: si riesce a scrivere sul Blob store?
// `mode` dice al browser quale metodo di caricamento usare.
export async function GET() {
  const mode = blobToken() ? 'token' : 'presigned';
  const blobVars = Object.keys(process.env).filter((k) => /BLOB/i.test(k));
  if (mode === 'presigned' && !process.env.BLOB_STORE_ID) {
    return json({ ok: false, reason: 'no-token', blobVars });
  }
  try {
    const b = await put('health/ping.txt', 'ok', {
      access: ACCESS,
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType: 'text/plain',
      ...blobOpts(),
    });
    await del(b.url, blobOpts());
    return json({ ok: true, mode });
  } catch (err) {
    return json({ ok: false, reason: 'write-failed', error: err.message, mode, blobVars });
  }
}
