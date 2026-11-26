import { put, del } from '@vercel/blob';
import { ACCESS, json, blobToken } from './_lib.js';

// Controllo di configurazione: c'è il token del Blob store e si riesce a scrivere?
export async function GET() {
  const token = blobToken();
  const blobVars = Object.keys(process.env).filter((k) => /BLOB/i.test(k));
  if (!token) {
    return json({ ok: false, reason: 'no-token', blobVars });
  }
  try {
    const b = await put('health/ping.txt', 'ok', {
      access: ACCESS,
      addRandomSuffix: false,
      allowOverwrite: true,
      contentType: 'text/plain',
      token,
    });
    await del(b.url, { token });
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, reason: 'write-failed', error: err.message, blobVars });
  }
}
