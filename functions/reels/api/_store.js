// Archivio file su Cloudflare R2 (API compatibile S3).
// Variabili d'ambiente richieste su Vercel:
//   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
// (R2_ENDPOINT solo per i test locali con un finto S3).
import {
  S3Client, ListObjectsV2Command, PutObjectCommand, DeleteObjectsCommand,
  GetObjectCommand, PutBucketCorsCommand,
} from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

export const REQUIRED_ENV = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET'];
export const missingEnv = () =>
  REQUIRED_ENV.filter((k) => !process.env[k] && !(k === 'R2_ACCOUNT_ID' && process.env.R2_ENDPOINT));

let client;
function s3() {
  if (!client) {
    client = new S3Client({
      region: 'auto',
      endpoint: process.env.R2_ENDPOINT || `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
      forcePathStyle: true,
      credentials: {
        accessKeyId: process.env.R2_ACCESS_KEY_ID,
        secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
      },
      // R2 non accetta i checksum aggiunti di default dalle versioni recenti dell'SDK
      // negli URL firmati: li chiediamo solo quando servono davvero.
      requestChecksumCalculation: 'WHEN_REQUIRED',
      responseChecksumValidation: 'WHEN_REQUIRED',
    });
  }
  return client;
}
const Bucket = () => process.env.R2_BUCKET;

export async function listAll(prefix) {
  const out = [];
  let ContinuationToken;
  do {
    const page = await s3().send(new ListObjectsV2Command({ Bucket: Bucket(), Prefix: prefix, ContinuationToken }));
    for (const o of page.Contents || []) out.push({ key: o.Key, size: o.Size, lastModified: o.LastModified });
    ContinuationToken = page.IsTruncated ? page.NextContinuationToken : undefined;
  } while (ContinuationToken);
  return out;
}

export function putSmall(key, body, contentType = 'text/plain') {
  return s3().send(new PutObjectCommand({ Bucket: Bucket(), Key: key, Body: body, ContentType: contentType }));
}

export async function deleteKeys(keys) {
  for (let i = 0; i < keys.length; i += 1000) {
    const chunk = keys.slice(i, i + 1000);
    if (chunk.length) {
      await s3().send(new DeleteObjectsCommand({ Bucket: Bucket(), Delete: { Objects: chunk.map((Key) => ({ Key })), Quiet: true } }));
    }
  }
}

// URL firmato con cui il browser carica il file direttamente su R2.
export function presignPut(key, contentType) {
  return getSignedUrl(s3(), new PutObjectCommand({ Bucket: Bucket(), Key: key, ContentType: contentType }), { expiresIn: 6 * 3600 });
}

// URL firmato per vedere (o scaricare) un file: l'archivio resta privato.
export function presignGet(key, downloadName) {
  const cmd = new GetObjectCommand({
    Bucket: Bucket(),
    Key: key,
    ...(downloadName
      ? { ResponseContentDisposition: `attachment; filename*=UTF-8''${encodeURIComponent(downloadName)}` }
      : {}),
  });
  return getSignedUrl(s3(), cmd, { expiresIn: 7 * 24 * 3600 });
}

// Permette al sito di caricare e scaricare dal browser (CORS del bucket).
export function ensureCors() {
  return s3().send(new PutBucketCorsCommand({
    Bucket: Bucket(),
    CORSConfiguration: {
      CORSRules: [{
        AllowedOrigins: ['*'],
        AllowedMethods: ['GET', 'PUT', 'HEAD'],
        AllowedHeaders: ['*'],
        ExposeHeaders: ['ETag'],
        MaxAgeSeconds: 3600,
      }],
    },
  }));
}

export const ID_RE = /^[a-z0-9-]{8,40}$/;

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}
