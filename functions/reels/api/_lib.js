// Helper condivisi dalle API (il prefisso "_" evita che Vercel lo esponga come rotta).
// Accesso libero: chiunque abbia il link vede e usa la stessa pagina.
export const ACCESS = 'public';
export const ID_RE = /^[a-z0-9-]{8,40}$/;

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

// Token del Blob store. Vercel di solito crea BLOB_READ_WRITE_TOKEN, ma se allo
// store è stato dato un prefisso personalizzato la variabile si chiama
// <PREFISSO>_READ_WRITE_TOKEN: la cerchiamo comunque.
export function blobToken() {
  if (process.env.BLOB_READ_WRITE_TOKEN) return process.env.BLOB_READ_WRITE_TOKEN;
  const hit = Object.entries(process.env).find(
    ([k, v]) => k.endsWith('READ_WRITE_TOKEN') && String(v).startsWith('vercel_blob_rw_'),
  );
  return hit ? hit[1] : undefined;
}

export const blobOpts = () => (blobToken() ? { token: blobToken() } : {});
