// Helper condivisi dalle API (il prefisso "_" evita che Vercel lo esponga come rotta).
export const ACCESS = 'public';
export const ID_RE = /^[a-z0-9-]{8,40}$/;

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

// Password condivisa opzionale: se APP_PASSWORD non è impostata l'app è aperta.
export function checkPassword(value) {
  const expected = process.env.APP_PASSWORD;
  return !expected || value === expected;
}

export function authorized(request) {
  return checkPassword(request.headers.get('x-app-password') || '');
}

export const unauthorized = () => json({ error: 'password' }, 401);
