import { authorized, unauthorized, json } from './_lib.js';

export function GET(request) {
  return authorized(request) ? json({ ok: true }) : unauthorized();
}
