// Helper condivisi dalle API (il prefisso "_" evita che Vercel lo esponga come rotta).
export const ACCESS = 'public';
export const ID_RE = /^[a-z0-9-]{8,40}$/;

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

import { timingSafeEqual } from 'node:crypto';

const same = (a, b) => {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && timingSafeEqual(x, y);
};

// Accesso con username + password impostati nelle variabili d'ambiente di Vercel.
// Se mancano, l'app resta chiusa (fail-closed).
export const configured = () => !!(process.env.APP_USERNAME && process.env.APP_PASSWORD);

export function checkCredentials(user, password) {
  if (!configured()) return false;
  const okUser = same(String(user).toLowerCase(), process.env.APP_USERNAME.toLowerCase());
  const okPass = same(password, process.env.APP_PASSWORD);
  return okUser && okPass;
}

export function authorized(request) {
  return checkCredentials(request.headers.get('x-app-user') || '', request.headers.get('x-app-password') || '');
}

export const unauthorized = () => json({ error: configured() ? 'login' : 'config' }, 401);
