import { missingEnv, ensureCors, putSmall, deleteKeys, json } from './_store.js';

// Controllo configurazione prima di caricare: chiavi presenti, CORS impostato,
// scrittura possibile.
export async function GET() {
  const missing = missingEnv();
  if (missing.length) return json({ ok: false, reason: 'no-env', missing });
  let corsError = null;
  try {
    await ensureCors();
  } catch (err) {
    corsError = err.message; // es. chiave senza permessi Admin: CORS va impostato a mano
  }
  try {
    await putSmall('health/ping.txt', 'ok');
    await deleteKeys(['health/ping.txt']);
  } catch (err) {
    return json({ ok: false, reason: 'write-failed', error: `${err.name}: ${err.message}` });
  }
  return json({ ok: true, corsError });
}
