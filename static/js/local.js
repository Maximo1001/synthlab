// Modo local (GitHub Pages, sin servidor): emula la API guardando los datos en este navegador.
// Las contraseñas nunca se guardan: sólo PBKDF2-SHA256 (600.000 iteraciones, sal aleatoria de 128 bits).
// Limitación: los datos viven sólo en este navegador; no hay correo, 2FA ni panel de administración.

const K = { users: 'synthlab_local_users', session: 'synthlab_local_session', data: 'synthlab_local_data' };
const ITER = 600000;
const enc = new TextEncoder();

class LocalError extends Error { constructor(m, s) { super(m); this.status = s; } }
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { throw new LocalError('El navegador no permite guardar datos (¿modo privado?).', 500); } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* nada */ } },
};
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const rand = n => hex(crypto.getRandomValues(new Uint8Array(n)));
const now = () => Math.floor(Date.now() / 1000);

async function derive(pw, salt) {
  const key = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveBits']);
  return hex(await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: enc.encode(salt), iterations: ITER, hash: 'SHA-256' }, key, 256));
}
function same(a, b) { if (a.length !== b.length) return false; let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i); return r === 0; }

const COMMON = ['123456789012', 'password1234', 'qwertyuiop12', 'contraseña123', 'synthlab1234', 'qwerty123456'];
function policy(pw, email, name) {
  if (typeof pw !== 'string' || pw.length < 12) return 'La contraseña debe tener al menos 12 caracteres.';
  if (pw.length > 128) return 'La contraseña no puede superar 128 caracteres.';
  const low = pw.toLowerCase();
  if (COMMON.includes(low) || new Set(low).size < 5) return 'Esa contraseña es demasiado común o repetitiva.';
  const local = (email || '').split('@')[0];
  if ((local.length >= 4 && low.includes(local)) || (name && name.length >= 4 && low.includes(name.toLowerCase()))) return 'La contraseña no puede contener tu nombre ni tu correo.';
  return null;
}
const EMAIL = /^[^\s@<>()[\],;:"]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}$/;
const PRODUCTS = ['keystone-49', 'orbit-dj-2', 'helix-one', 'slicer-s4', 'pulse-16', 'core-io'];

const users = () => store.get(K.users, []);
const saveUsers = u => store.set(K.users, u);
const me = () => { const s = store.get(K.session, null); if (!s) return null; const u = users().find(x => x.id === s.uid);
  if (!u || now() - s.created > 12 * 3600) { store.del(K.session); return null; } return u; };
const data = uid => store.get(K.data, {})[uid] || { patterns: [], favorites: [], seq: 0 };
const saveData = (uid, d) => { const all = store.get(K.data, {}); all[uid] = d; store.set(K.data, all); };
const pub = u => ({ id: u.id, name: u.name, email: u.email, role: 'user', email_verified: true, mfa: false, created_at: u.created_at, last_login_at: u.last_login_at });
const need = () => { const u = me(); if (!u) throw new LocalError('Necesitas iniciar sesión.', 401); return u; };
const reauth = async (u, pw) => typeof pw === 'string' && same(await derive(pw, u.salt), u.hash);

// Patrón compartible sin servidor: todo el patrón viaja codificado en el enlace.
const b64u = s => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64u = s => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));
const packPattern = (p, author) => 'L' + b64u(JSON.stringify({ n: p.name, b: p.bpm, a: author, s: p.steps.map(r => r.join('')).join('.') }));
function validPattern(b) {
  const ok = b && typeof b.name === 'string' && b.name.trim().length >= 1 && b.name.trim().length <= 40
    && Number.isInteger(b.bpm) && b.bpm >= 60 && b.bpm <= 180
    && Array.isArray(b.steps) && b.steps.length === 4 && b.steps.every(r => Array.isArray(r) && r.length === 16 && r.every(v => v === 0 || v === 1));
  if (!ok) throw new LocalError('Patrón no válido.', 400);
  return { name: b.name.trim(), bpm: b.bpm, steps: b.steps };
}

let failures = 0, lockedUntil = 0;

export async function localApi(path, { method = 'GET', body = {} } = {}) {
  const [route, qs] = path.split('?'); void qs;
  const seg = route.split('/');
  const M = method;

  if (route === 'csrf') return { csrf: 'local' };
  if (route === 'me' && M === 'GET') return { user: pub(need()) };

  if (route === 'auth/register') {
    const email = String(body.email || '').trim().toLowerCase(), name = String(body.name || '').trim();
    if (!EMAIL.test(email)) throw new LocalError('Escribe un correo válido.', 400);
    if (name.length < 2 || name.length > 40) throw new LocalError('El nombre debe tener entre 2 y 40 caracteres.', 400);
    const err = policy(body.password, email, name); if (err) throw new LocalError(err, 400);
    const us = users();
    if (us.some(u => u.email === email)) throw new LocalError('Ya existe una cuenta con ese correo en este navegador.', 409);
    const salt = rand(16);
    us.push({ id: rand(8), email, name, salt, hash: await derive(body.password, salt), created_at: now(), last_login_at: null });
    saveUsers(us);
    return { ok: true, message: 'Cuenta creada en este navegador. Ya puedes iniciar sesión.' };
  }
  if (route === 'auth/login') {
    if (Date.now() < lockedUntil) throw new LocalError('Demasiados intentos. Espera un minuto.', 429);
    const email = String(body.email || '').trim().toLowerCase();
    const u = users().find(x => x.email === email);
    const h = await derive(String(body.password || ''), u ? u.salt : 'dummy-salt-equalize');
    if (!u || !same(h, u.hash)) {
      if (++failures >= 5) { lockedUntil = Date.now() + 60000; failures = 0; }
      throw new LocalError('Correo o contraseña incorrectos.', 401);
    }
    failures = 0;
    const us = users(); const x = us.find(y => y.id === u.id); x.last_login_at = now(); saveUsers(us);
    store.set(K.session, { uid: u.id, created: now() });
    return { ok: true, user: pub(x) };
  }
  if (route === 'auth/logout') { store.del(K.session); return { ok: true }; }
  if (route === 'auth/forgot') throw new LocalError('En modo local no se pueden enviar correos. Si olvidas la contraseña, crea una cuenta nueva.', 400);

  if (route === 'me' && M === 'PATCH') {
    const u = need(), name = String(body.name || '').trim();
    if (name.length < 2 || name.length > 40) throw new LocalError('El nombre debe tener entre 2 y 40 caracteres.', 400);
    const us = users(); us.find(x => x.id === u.id).name = name; saveUsers(us);
    return { user: pub(us.find(x => x.id === u.id)) };
  }
  if (route === 'me' && M === 'DELETE') {
    const u = need(); if (!await reauth(u, body.password)) throw new LocalError('La contraseña no es correcta.', 401);
    saveUsers(users().filter(x => x.id !== u.id));
    const all = store.get(K.data, {}); delete all[u.id]; store.set(K.data, all); store.del(K.session);
    return { ok: true };
  }
  if (route === 'me/password') {
    const u = need(); if (!await reauth(u, body.current)) throw new LocalError('La contraseña actual no es correcta.', 401);
    const err = policy(body.new, u.email, u.name); if (err) throw new LocalError(err, 400);
    const us = users(), x = us.find(y => y.id === u.id); x.salt = rand(16); x.hash = await derive(body.new, x.salt); saveUsers(us);
    return { ok: true, message: 'Contraseña actualizada.' };
  }
  if (route === 'me/export') {
    const u = need(), d = data(u.id);
    return { perfil: pub(u), patrones: d.patterns, favoritos: d.favorites, nota: 'Datos guardados sólo en este navegador.' };
  }
  if (route === 'me/sessions') return { sessions: [{ id: 1, current: true, ip: 'este navegador', user_agent: navigator.userAgent, created_at: now(), last_seen: now() }] };

  if (seg[0] === 'patterns') {
    const u = need(), d = data(u.id), id = seg[1] ? +seg[1] : null;
    const find = () => { const p = d.patterns.find(x => x.id === id); if (!p) throw new LocalError('No encontrado.', 404); return p; };
    if (!id && M === 'GET') return { patterns: [...d.patterns].sort((a, b) => b.updated_at - a.updated_at) };
    if (!id && M === 'POST') {
      if (d.patterns.length >= 50) throw new LocalError('Has alcanzado el máximo de 50 patrones.', 409);
      const p = { id: ++d.seq, ...validPattern(body), shared: null, updated_at: now() }; d.patterns.push(p); saveData(u.id, d); return { pattern: p };
    }
    if (id && seg[2] === 'share') {
      const p = find(); p.shared = body.enabled === false ? null : packPattern(p, u.name.split(' ')[0]); saveData(u.id, d); return { shared: p.shared };
    }
    if (id && M === 'GET') return { pattern: find() };
    if (id && M === 'PUT') { const p = find(); Object.assign(p, validPattern(body), { updated_at: now() }); if (p.shared) p.shared = packPattern(p, u.name.split(' ')[0]); saveData(u.id, d); return { pattern: p }; }
    if (id && M === 'DELETE') { find(); d.patterns = d.patterns.filter(x => x.id !== id); saveData(u.id, d); return { ok: true }; }
  }
  if (seg[0] === 'shared') {
    try {
      const slug = decodeURIComponent(seg[1] || '');
      if (!slug.startsWith('L') || slug.length > 600) throw 0;
      const o = JSON.parse(unb64u(slug.slice(1)));
      const steps = String(o.s).split('.').map(r => r.split('').map(c => (c === '1' ? 1 : 0)));
      const p = validPattern({ name: String(o.n), bpm: o.b, steps });
      return { pattern: { ...p, author: String(o.a || 'alguien').slice(0, 40) } };
    } catch (e) { throw new LocalError('Enlace de patrón no válido.', 404); }
  }
  if (seg[0] === 'favorites') {
    const u = need(), d = data(u.id);
    if (M === 'GET') return { favorites: d.favorites };
    if (!PRODUCTS.includes(seg[1])) throw new LocalError('Producto desconocido.', 404);
    d.favorites = d.favorites.filter(x => x !== seg[1]); if (M === 'PUT') d.favorites.push(seg[1]);
    saveData(u.id, d); return { ok: true };
  }
  if (route === 'contact' || route === 'newsletter') throw new LocalError('Esta función necesita el servidor de SYNTHLAB; en la versión de GitHub no está disponible.', 503);
  throw new LocalError('No disponible en modo local.', 404);
}
