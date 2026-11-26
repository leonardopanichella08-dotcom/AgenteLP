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
