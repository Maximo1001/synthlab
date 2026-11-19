// Cliente de la API de SYNTHLAB: JSON + token CSRF. Sin servidor (GitHub Pages) usa el modo local.
import { localApi } from './local.js';
let csrf = null;
let online = null;

export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data || {}; }
}

async function refreshCsrf() {
  const r = await fetch('api/csrf', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
  const j = await r.json();
  csrf = j.csrf;
}

export async function detectBackend() {
  if (online !== null) return online;
  try {
    const r = await fetch('api/csrf', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    online = r.ok && (r.headers.get('content-type') || '').includes('application/json');
    if (online) csrf = (await r.json()).csrf;
  } catch (e) { online = false; }
  return online;
}

export async function api(path, { method = 'GET', body, retry = true } = {}) {
  if (!online) {
    try { return await localApi(path, { method, body }); }
    catch (e) { throw new ApiError(e.message || 'Error inesperado.', e.status || 500); }
  }
  const opt = { method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
  if (method !== 'GET') {
    if (!csrf) await refreshCsrf();
    opt.headers['Content-Type'] = 'application/json';
    opt.headers['X-CSRF-Token'] = csrf;
    opt.body = JSON.stringify(body || {});
  }
  let r;
  try { r = await fetch('api/' + path, opt); }
  catch (e) { throw new ApiError('No se pudo contactar con el servidor.', 0); }
  let data = {};
  try { data = await r.json(); } catch (e) { /* respuesta vacía */ }
  if (data && data.csrf) csrf = data.csrf;
  if (r.status === 403 && retry && /CSRF/.test(data.error || '')) {
    await refreshCsrf();
    return api(path, { method, body, retry: false });
  }
  if (!r.ok) {
    const wait = r.headers.get('Retry-After');
    const msg = data.error || 'Error ' + r.status;
    throw new ApiError(wait ? `${msg} (espera ${Math.ceil(wait / 60)} min)` : msg, r.status, data);
  }
  return data;
}

export async function resetCsrf() { csrf = null; await refreshCsrf().catch(() => {}); }
