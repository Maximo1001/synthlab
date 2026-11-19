// Cuentas, biblioteca de patrones, favoritos, contacto, newsletter y panel de administración.
// Todo lo que viene del servidor se inserta escapado con esc().
import { api, ApiError, detectBackend, resetCsrf } from './api.js';

export function initAccount(ctx) {
  const { $, $$, toast, esc, openModal, closeModal, getPattern, setPattern, SLUGS } = ctx;
  const S = { user: null, online: false, mode: 'login', mfaToken: null, resetToken: null,
    patterns: [], favs: new Set(), current: null, flash: '' };
  const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  const fail = (e, el) => { const m = e instanceof ApiError ? e.message : 'Error inesperado.'; if (el) el.textContent = m; else toast(m); };
  const busy = (btn, on) => { if (!btn) return; btn.disabled = on; btn.setAttribute('aria-busy', on); };

  /* ---------- campos ---------- */
  function field(id, lab, type, ac, extra = '') {
    const inp = `<input id="${id}" name="${id}" type="${type}" autocomplete="${ac}" ${extra}>`;
    return `<div class="fd"><label for="${id}">${lab}</label>${type === 'password'
      ? `<div class="pw">${inp}<button type="button" data-eye="${id}">Mostrar</button></div>` : inp}</div>`;
  }
  function wireEyes(root) {
    $$('[data-eye]', root).forEach(b => b.onclick = () => {
      const i = $('#' + b.dataset.eye); const s = i.type === 'password';
      i.type = s ? 'text' : 'password'; b.textContent = s ? 'Ocultar' : 'Mostrar';
    });
  }
  function strength(pw) {
    let s = 0; if (pw.length >= 12) s++; if (pw.length >= 16) s++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++; if (/\d/.test(pw)) s++; if (/[^A-Za-z0-9]/.test(pw)) s++;
    return Math.min(4, s);
  }
  function meter(inputId) {
    const inp = $('#' + inputId), m = $('#' + inputId + '-m'); if (!inp || !m) return;
    const L = ['Muy débil', 'Débil', 'Aceptable', 'Buena', 'Excelente'];
    inp.addEventListener('input', () => { const v = strength(inp.value); m.dataset.s = v; m.lastChild.textContent = inp.value ? L[v] : ''; });
  }
  const meterHtml = id => `<div class="meter" id="${id}-m" data-s="0" aria-live="polite"><i></i><span></span></div>`;

  /* ---------- diálogo con formulario (reutiliza el modal) ---------- */
  // onSubmit(values, errEl) se ejecuta en cada envío; si no lanza, el modal se cierra.
  function ask({ title, text = '', fields = [], submit = 'Confirmar', danger = false, onSubmit }) {
    openModal(`<button class="x" aria-label="Cerrar">✕</button><h3 id="mt">${title}</h3>${text ? `<p>${text}</p>` : ''}
      <form id="askf" novalidate>${fields.map(f => field(f.id, f.label, f.type || 'password', f.ac || 'current-password', f.extra || '')).join('')}
      <div class="er" id="asker" role="alert"></div><button class="btn ${danger ? 'dzb' : ''}" type="submit">${submit}</button></form>`);
    wireEyes($('#mb'));
    const f = $('#askf'), er = $('#asker'), btn = $('button[type=submit]', f); const first = $('input', f); first && first.focus();
    f.onsubmit = async e => {
      e.preventDefault(); er.textContent = ''; const v = {}; fields.forEach(x => v[x.id] = $('#' + x.id).value);
      busy(btn, true);
      try { const keep = await onSubmit(v, er); if (keep !== true) closeModal(); } catch (x) { fail(x, er); } finally { busy(btn, false); }
    };
  }

  /* ---------- navegación ---------- */
  function navUpd() {
    const u = S.user;
    $('#acc').textContent = u ? u.name.split(' ')[0] : 'Entrar';
    $('#acc2').textContent = u ? 'Mi cuenta' : 'Entrar';
    $$('.adm-only').forEach(el => el.hidden = !(u && u.role === 'admin'));
    renderSave(); renderFavs();
  }

  /* ---------- ACCOUNT: sin sesión ---------- */
  function renderAuth() {
    const box = $('#acBox'); box.className = 'ac';
    if (!S.online) {
      box.innerHTML = `<span class="tag">Cuenta</span><h2>Modo demostración</h2><div class="card"><p class="lead" style="margin:0">
        Esta copia se está sirviendo sin servidor (por ejemplo, desde GitHub Pages). El laboratorio funciona completo,
        pero el registro, los patrones guardados y los favoritos necesitan el backend de SYNTHLAB.
        Consulta el README para arrancarlo en local en un minuto.</p></div>`;
      return;
    }
    const m = S.mode;
    const titles = { login: 'Bienvenido de nuevo', register: 'Crea tu cuenta', forgot: 'Recupera tu acceso',
      mfa: 'Verificación en dos pasos', reset: 'Elige una nueva contraseña' };
    let form = '';
    if (m === 'login') form = field('f-e', 'Correo electrónico', 'email', 'email', 'required maxlength="254"') + field('f-p', 'Contraseña', 'password', 'current-password', 'required');
    if (m === 'register') form = field('f-n', 'Nombre', 'text', 'name', 'required maxlength="40"') + field('f-e', 'Correo electrónico', 'email', 'email', 'required maxlength="254"')
      + field('f-p', 'Contraseña (mín. 12 caracteres)', 'password', 'new-password', 'required minlength="12" maxlength="128"') + meterHtml('f-p')
      + field('f-p2', 'Repite la contraseña', 'password', 'new-password', 'required')
      + `<div class="hp" aria-hidden="true"><label for="f-w">Web</label><input id="f-w" tabindex="-1" autocomplete="off"></div>`
      + `<label class="ck"><input type="checkbox" id="f-t" required> Acepto la política de privacidad y el tratamiento de mis datos para gestionar la cuenta.</label>`;
    if (m === 'forgot') form = `<p class="mut">Te enviaremos un enlace de un solo uso, válido 30 minutos.</p>` + field('f-e', 'Correo electrónico', 'email', 'email', 'required');
    if (m === 'mfa') form = `<p class="mut">Introduce el código de 6 dígitos de tu app de autenticación o uno de tus códigos de recuperación.</p>` + field('f-c', 'Código', 'text', 'one-time-code', 'required inputmode="numeric" maxlength="11"');
    if (m === 'reset') form = field('f-p', 'Nueva contraseña (mín. 12)', 'password', 'new-password', 'required minlength="12"') + meterHtml('f-p') + field('f-p2', 'Repítela', 'password', 'new-password', 'required');
    const tabs = (m === 'login' || m === 'register') ? `<div class="tabs" role="tablist"><button role="tab" data-m="login" aria-selected="${m === 'login'}">Iniciar sesión</button><button role="tab" data-m="register" aria-selected="${m === 'register'}">Crear cuenta</button></div>` : '';
    const label = { login: 'Entrar', register: 'Crear cuenta', forgot: 'Enviar enlace', mfa: 'Verificar', reset: 'Guardar contraseña' }[m];
    const foot = m === 'login' ? '<button data-m="forgot">¿Has olvidado tu contraseña?</button>'
      : m === 'register' ? '¿Ya tienes cuenta? <button data-m="login">Inicia sesión</button>'
      : '<button data-m="login">Volver a iniciar sesión</button>';
    box.innerHTML = `<span class="tag">Únete a SYNTHLAB</span><h2>${titles[m]}</h2><div class="card">${tabs}
      <form id="af" novalidate>${form}<div class="er" id="er" role="alert"></div><div class="ok" id="okm" role="status"></div><button class="btn" type="submit">${label}</button></form>
      <p class="sw2">${foot}</p><p class="sec"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z"/></svg>Contraseñas con Argon2id · sesiones HttpOnly · 2FA opcional</p></div>`;
    $$('[data-m]', box).forEach(b => b.onclick = () => { S.mode = b.dataset.m; renderAuth(); });
    wireEyes(box); meter('f-p');
    if (S.flash) { $('#okm').innerHTML = S.flash; S.flash = ''; }
    const first = $('input', box); first && first.focus({ preventScroll: true });
    $('#af').onsubmit = async e => {
      e.preventDefault(); const er = $('#er'), ok = $('#okm'), btn = $('button[type=submit]', e.target); er.textContent = ''; ok.textContent = '';
      const v = id => ($('#' + id) || {}).value || '';
      const email = v('f-e').trim().toLowerCase();
      if ((m === 'login' || m === 'register' || m === 'forgot') && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return er.textContent = 'Escribe un correo válido.';
      if (m === 'register' || m === 'reset') {
        if (m === 'register' && v('f-n').trim().length < 2) return er.textContent = 'Escribe tu nombre.';
        if (v('f-p').length < 12) return er.textContent = 'La contraseña debe tener al menos 12 caracteres.';
        if (v('f-p') !== v('f-p2')) return er.textContent = 'Las contraseñas no coinciden.';
        if (m === 'register' && !$('#f-t').checked) return er.textContent = 'Debes aceptar la política de privacidad.';
      }
      busy(btn, true);
      try {
        if (m === 'login') {
          const r = await api('auth/login', { method: 'POST', body: { email, password: v('f-p') } });
          if (r.mfa_required) { S.mfaToken = r.mfa_token; S.mode = 'mfa'; renderAuth(); return; }
          await signedIn(r.user);
        } else if (m === 'mfa') {
          const r = await api('auth/login/mfa', { method: 'POST', body: { mfa_token: S.mfaToken, code: v('f-c') } });
          S.mfaToken = null; await signedIn(r.user);
        } else if (m === 'register') {
          const r = await api('auth/register', { method: 'POST', body: { name: v('f-n').trim(), email, password: v('f-p'), website: v('f-w') } });
          S.mode = 'login'; S.flash = esc(r.message) + devLink(r.dev_link); renderAuth();
        } else if (m === 'forgot') {
          const r = await api('auth/forgot', { method: 'POST', body: { email } });
          ok.innerHTML = esc(r.message) + devLink(r.dev_link);
        } else if (m === 'reset') {
          const r = await api('auth/reset', { method: 'POST', body: { token: S.resetToken, password: v('f-p') } });
          S.resetToken = null; S.mode = 'login'; S.flash = esc(r.message); renderAuth();
        }
      } catch (err) {
        if (err.data && err.data.code === 'unverified') {
          er.innerHTML = esc(err.message) + ' <button type="button" class="lnk" id="resend">Reenviar enlace</button>';
          $('#resend').onclick = async () => { try { const r = await api('auth/resend-verification', { method: 'POST', body: { email } }); toast(r.message); } catch (x) { fail(x); } };
        } else fail(err, er);
        if (m === 'mfa' && err.status === 401 && /caducado/.test(err.message)) { S.mode = 'login'; setTimeout(renderAuth, 1500); }
      } finally { busy(btn, false); }
    };
  }
  // Sólo en desarrollo el servidor devuelve el enlace (no hay correo real).
  const devLink = l => l ? `<br><small>Desarrollo: <a href="${esc(l)}">abrir enlace del correo</a></small>` : '';

  async function signedIn(user) {
    S.user = user; S.mode = 'login';
    await loadLibrary(); navUpd(); renderAccount();
    toast('Hola, ' + user.name.split(' ')[0]);
    location.hash = '#lab';
  }

  /* ---------- ACCOUNT: con sesión ---------- */
  async function renderAccount() {
    if (!S.user) return renderAuth();
    const u = S.user, box = $('#acBox'); box.className = 'ac wide';
    box.innerHTML = `<span class="tag">Mi cuenta</span><h2>Hola, ${esc(u.name.split(' ')[0])}</h2>
    <div class="dash">
      <div class="card"><div class="av">${esc(u.name[0].toUpperCase())}</div>
        <h3>Perfil</h3><p class="mut">${esc(u.email)}${u.role === 'admin' ? ' · <b class="badge">admin</b>' : ''}<br>Miembro desde ${fmtDate(u.created_at)}<br>Último acceso: ${fmtDate(u.last_login_at)}</p>
        <form id="pfn" class="row" novalidate>${field('p-n', 'Nombre', 'text', 'name', `maxlength="40" value="${esc(u.name)}"`)}<button class="btn o" type="submit">Guardar</button></form>
        <div class="er" id="pfer" role="alert"></div></div>
      <div class="card"><h3>Seguridad</h3>
        <div class="kv"><span>Verificación en dos pasos</span><b class="badge ${u.mfa ? 'on' : ''}">${u.mfa ? 'Activa' : 'Desactivada'}</b></div>
        <div class="pf">${u.mfa ? '<button class="btn o" id="mfaOff">Desactivar 2FA</button><button class="btn o" id="mfaCodes">Nuevos códigos de recuperación</button>' : '<button class="btn" id="mfaOn">Activar 2FA</button>'}
        <button class="btn o" id="chpw">Cambiar contraseña</button></div></div>
      <div class="card span2"><div class="sqh"><h3>Sesiones activas</h3><button class="btn o" id="revAll">Cerrar las demás</button></div><div id="sess" class="list"><p class="mut">Cargando…</p></div></div>
      <div class="card span2"><div class="sqh"><h3>Mis patrones</h3><a class="btn o" href="#lab">Ir al laboratorio</a></div><div id="libp" class="list"></div></div>
      <div class="card"><h3>Favoritos</h3><div id="libf" class="list"></div></div>
      <div class="card"><h3>Tus datos</h3><p class="mut">Descarga todo lo que guardamos sobre ti o elimina tu cuenta (RGPD).</p>
        <div class="pf"><button class="btn o" id="exp">Descargar mis datos (JSON)</button><button class="btn o" id="out">Cerrar sesión</button><button class="btn o dz" id="del">Eliminar mi cuenta</button></div></div>
    </div>`;
    wireEyes(box);
    $('#pfn').onsubmit = async e => { e.preventDefault(); try { const r = await api('me', { method: 'PATCH', body: { name: $('#p-n').value.trim() } }); S.user = r.user; navUpd(); renderAccount(); toast('Perfil actualizado'); } catch (x) { fail(x, $('#pfer')); } };
    $('#out').onclick = logout;
    $('#exp').onclick = async () => {
      try { const d = await api('me/export'); const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' })); a.download = 'synthlab-mis-datos.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      } catch (x) { fail(x); }
    };
    $('#del').onclick = async () => {
      ask({ title: 'Eliminar cuenta', text: 'Se borrarán tu perfil, tus patrones y tus favoritos. No se puede deshacer.', fields: [{ id: 'q-p', label: 'Confirma con tu contraseña' }], submit: 'Eliminar definitivamente', danger: true,
        onSubmit: async v => { await api('me', { method: 'DELETE', body: { password: v['q-p'] } }); S.user = null; S.patterns = []; S.favs = new Set(); await resetCsrf(); navUpd(); renderAuth(); toast('Cuenta eliminada'); location.hash = '#home'; } });
    };
    $('#chpw').onclick = async () => {
      ask({ title: 'Cambiar contraseña', text: 'Se cerrarán tus otras sesiones.', fields: [{ id: 'q-c', label: 'Contraseña actual' }, { id: 'q-n', label: 'Nueva contraseña (mín. 12)', ac: 'new-password' }, { id: 'q-n2', label: 'Repite la nueva', ac: 'new-password' }], submit: 'Cambiar',
        onSubmit: async (v, er) => {
          if (v['q-n'] !== v['q-n2']) { er.textContent = 'Las contraseñas no coinciden.'; return true; }
          const x = await api('me/password', { method: 'POST', body: { current: v['q-c'], new: v['q-n'] } }); toast(x.message); loadSessions();
        } });
    };
    const on = $('#mfaOn'), off = $('#mfaOff'), codes = $('#mfaCodes');
    if (on) on.onclick = mfaSetup;
    if (off) off.onclick = async () => {
      ask({ title: 'Desactivar 2FA', fields: [{ id: 'q-p', label: 'Contraseña' }, { id: 'q-c', label: 'Código actual de 6 dígitos', type: 'text', ac: 'one-time-code', extra: 'inputmode="numeric"' }], submit: 'Desactivar', danger: true,
        onSubmit: async v => { await api('me/2fa/disable', { method: 'POST', body: { password: v['q-p'], code: v['q-c'] } }); S.user.mfa = false; renderAccount(); toast('2FA desactivada'); } });
    };
    if (codes) codes.onclick = async () => {
      ask({ title: 'Nuevos códigos de recuperación', text: 'Los anteriores dejarán de funcionar.', fields: [{ id: 'q-p', label: 'Contraseña' }], submit: 'Generar',
        onSubmit: async v => { const x = await api('me/2fa/recovery-codes', { method: 'POST', body: { password: v['q-p'] } }); showCodes(x.recovery_codes); return true; } });
    };
    $('#revAll').onclick = async () => { try { const r = await api('me/sessions/revoke-others', { method: 'POST' }); toast(`${r.revoked} sesión(es) cerrada(s)`); loadSessions(); } catch (x) { fail(x); } };
    loadSessions(); renderLibrary();
  }
  function mfaSetup() {
    ask({ title: 'Activar verificación en dos pasos', text: 'Confirma tu contraseña para generar la clave.', fields: [{ id: 'q-p', label: 'Contraseña' }], submit: 'Continuar',
      onSubmit: async v => { const setup = await api('me/2fa/setup', { method: 'POST', body: { password: v['q-p'] } }); mfaShow(setup); return true; } });
  }
  function mfaShow(setup) {
    const grouped = setup.secret.match(/.{1,4}/g).join(' ');
    openModal(`<button class="x" aria-label="Cerrar">✕</button><h3 id="mt">Configura tu app</h3>
      <p>En Google Authenticator, Aegis, 1Password o similar, añade una cuenta con esta clave (tipo «basada en tiempo»):</p>
      <p class="code" id="sec">${esc(grouped)}</p><p><a class="lnk" href="${esc(setup.uri)}">Abrir en la app del móvil</a> · <button class="lnk" id="cpy" type="button">Copiar clave</button></p>
      <form id="mfaf" novalidate>${field('q-c', 'Código de 6 dígitos', 'text', 'one-time-code', 'inputmode="numeric" maxlength="6"')}<div class="er" id="mfer" role="alert"></div><button class="btn" type="submit">Activar</button></form>`);
    $('#cpy').onclick = () => navigator.clipboard && navigator.clipboard.writeText(setup.secret).then(() => toast('Clave copiada'));
    $('#q-c').focus();
    $('#mfaf').onsubmit = async e => {
      e.preventDefault();
      try { const x = await api('me/2fa/enable', { method: 'POST', body: { code: $('#q-c').value } }); S.user.mfa = true; showCodes(x.recovery_codes); renderAccount(); }
      catch (err) { fail(err, $('#mfer')); }
    };
  }
  function showCodes(codes) {
    openModal(`<button class="x" aria-label="Cerrar">✕</button><h3 id="mt">Códigos de recuperación</h3>
      <p>Guárdalos en un lugar seguro. Cada uno sirve <b>una sola vez</b> si pierdes el móvil. No volveremos a mostrarlos.</p>
      <ul class="codes">${codes.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
      <div class="pf"><button class="btn o" id="dlc" type="button">Descargar .txt</button><button class="btn" data-close type="button">Ya los he guardado</button></div>`);
    $('#dlc').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([codes.join('\n') + '\n'], { type: 'text/plain' })); a.download = 'synthlab-codigos-recuperacion.txt'; a.click(); };
  }

  async function loadSessions() {
    const el = $('#sess'); if (!el) return;
    try {
      const { sessions } = await api('me/sessions');
      el.innerHTML = sessions.map(s => `<div class="li"><div><b>${esc(browser(s.user_agent))}</b>${s.current ? ' <span class="badge on">esta</span>' : ''}<br><small>${esc(s.ip || '')} · activa ${fmtDate(s.last_seen)}</small></div>${s.current ? '' : `<button class="btn o sm" data-rev="${s.id}">Cerrar</button>`}</div>`).join('');
      $$('[data-rev]', el).forEach(b => b.onclick = async () => { try { await api('me/sessions/' + b.dataset.rev, { method: 'DELETE' }); loadSessions(); } catch (x) { fail(x); } });
    } catch (x) { el.textContent = x.message; }
  }
  const browser = ua => { ua = ua || ''; const b = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Navegador';
    const o = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS X/.test(ua) ? 'macOS' : /Windows/.test(ua) ? 'Windows' : /Linux/.test(ua) ? 'Linux' : ''; return o ? `${b} · ${o}` : b; };

  async function logout() {
    try { await api('auth/logout', { method: 'POST' }); } catch (x) { /* la cookie se limpia igual */ }
    S.user = null; S.patterns = []; S.favs = new Set(); S.current = null; await resetCsrf();
    navUpd(); renderAuth(); toast('Sesión cerrada'); location.hash = '#home';
  }

  /* ---------- biblioteca: patrones + favoritos ---------- */
  async function loadLibrary() {
    if (!S.user) return;
    try {
      const [p, f] = await Promise.all([api('patterns'), api('favorites')]);
      S.patterns = p.patterns; S.favs = new Set(f.favorites);
    } catch (x) { fail(x); }
  }
  function renderLibrary() {
    const lp = $('#libp'), lf = $('#libf');
    if (lp) {
      lp.innerHTML = S.patterns.length ? S.patterns.map(p => `<div class="li"><div><b>${esc(p.name)}</b><br><small>${p.bpm} BPM · ${fmtDate(p.updated_at)}${p.shared ? ' · compartido' : ''}</small></div>
        <div class="acts"><button class="btn o sm" data-load="${p.id}">Cargar</button><button class="btn o sm" data-share="${p.id}">${p.shared ? 'Enlace' : 'Compartir'}</button><button class="btn o sm dz" data-del="${p.id}" aria-label="Borrar ${esc(p.name)}">Borrar</button></div></div>`).join('')
        : '<p class="mut">Aún no has guardado patrones. Crea uno en el laboratorio y pulsa «Guardar».</p>';
      $$('[data-load]', lp).forEach(b => b.onclick = () => { loadPattern(+b.dataset.load); location.hash = '#lab'; });
      $$('[data-share]', lp).forEach(b => b.onclick = () => sharePattern(+b.dataset.share));
      $$('[data-del]', lp).forEach(b => b.onclick = async () => {
        if (!confirm('¿Borrar este patrón?')) return;
        try { await api('patterns/' + b.dataset.del, { method: 'DELETE' }); S.patterns = S.patterns.filter(p => p.id !== +b.dataset.del); if (S.current === +b.dataset.del) S.current = null; renderLibrary(); renderSave(); toast('Patrón borrado'); } catch (x) { fail(x); }
      });
    }
    if (lf) lf.innerHTML = S.favs.size ? [...S.favs].map(s => `<div class="li"><b>${esc(ctx.productName(s))}</b><a class="btn o sm" href="#products">Ver</a></div>`).join('') : '<p class="mut">Marca productos con ♥ para verlos aquí.</p>';
  }
  function loadPattern(id) {
    const p = S.patterns.find(x => x.id === id); if (!p) return;
    setPattern(p); S.current = id; renderSave(); toast(`«${p.name}» cargado`);
  }
  async function sharePattern(id) {
    try {
      const p = S.patterns.find(x => x.id === id);
      const r = p.shared ? { shared: p.shared } : await api(`patterns/${id}/share`, { method: 'POST', body: { enabled: true } });
      p.shared = r.shared; renderLibrary();
      const url = `${location.origin}${location.pathname}?pattern=${encodeURIComponent(r.shared)}#lab`;
      openModal(`<button class="x" aria-label="Cerrar">✕</button><h3 id="mt">Compartir «${esc(p.name)}»</h3><p>Cualquiera con este enlace podrá escuchar el patrón (sólo lectura). Tu correo no se muestra.</p>
        <p class="code">${esc(url)}</p><div class="pf"><button class="btn" id="cpl" type="button">Copiar enlace</button><button class="btn o dz" id="unsh" type="button">Dejar de compartir</button></div>`);
      $('#cpl').onclick = () => navigator.clipboard && navigator.clipboard.writeText(url).then(() => toast('Enlace copiado'));
      $('#unsh').onclick = async () => { try { await api(`patterns/${id}/share`, { method: 'POST', body: { enabled: false } }); p.shared = null; closeModal(); renderLibrary(); toast('Ya no se comparte'); } catch (x) { fail(x); } };
    } catch (x) { fail(x); }
  }

  /* ---------- barra de guardado del secuenciador ---------- */
  function renderSave() {
    const el = $('#sv'); if (!el) return;
    if (!S.online) { el.innerHTML = '<p class="mut">Modo demostración: los patrones se guardan con el backend activo.</p>'; return; }
    if (!S.user) { el.innerHTML = '<p class="mut"><a class="lnk" href="#account">Inicia sesión</a> para guardar y compartir tus patrones.</p>'; return; }
    const cur = S.patterns.find(p => p.id === S.current);
    el.innerHTML = `<form id="svf" class="row" novalidate><label class="sr" for="sv-n">Nombre del patrón</label><input id="sv-n" maxlength="40" placeholder="Nombre del patrón" value="${cur ? esc(cur.name) : ''}">
      <button class="btn sm" type="submit">${cur ? 'Actualizar' : 'Guardar'}</button>${cur ? '<button class="btn o sm" type="button" id="svnew">Guardar como nuevo</button>' : ''}
      <label class="sr" for="sv-l">Mis patrones</label><select id="sv-l"><option value="">Mis patrones (${S.patterns.length})</option>${S.patterns.map(p => `<option value="${p.id}" ${p.id === S.current ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></form>`;
    const save = async asNew => {
      const name = $('#sv-n').value.trim(); if (!name) return toast('Ponle un nombre al patrón');
      const body = { name, ...getPattern() };
      try {
        const r = (cur && !asNew) ? await api('patterns/' + cur.id, { method: 'PUT', body }) : await api('patterns', { method: 'POST', body });
        S.patterns = [r.pattern, ...S.patterns.filter(p => p.id !== r.pattern.id)]; S.current = r.pattern.id; renderSave(); renderLibrary(); toast('Patrón guardado');
      } catch (x) { fail(x); }
    };
    $('#svf').onsubmit = e => { e.preventDefault(); save(false); };
    const n = $('#svnew'); if (n) n.onclick = () => save(true);
    $('#sv-l').onchange = e => { if (e.target.value) loadPattern(+e.target.value); else { S.current = null; renderSave(); } };
  }

  /* ---------- favoritos en tarjetas ---------- */
  function renderFavs() {
    $$('[data-fav]').forEach(b => { const on = S.favs.has(b.dataset.fav); b.setAttribute('aria-pressed', on); b.title = on ? 'Quitar de favoritos' : 'Añadir a favoritos'; });
  }
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-fav]'); if (!b) return; e.preventDefault(); e.stopPropagation();
    if (!S.online) return toast('Los favoritos necesitan el backend');
    if (!S.user) { toast('Inicia sesión para guardar favoritos'); location.hash = '#account'; return; }
    const slug = b.dataset.fav, on = S.favs.has(slug);
    try { await api('favorites/' + slug, { method: on ? 'DELETE' : 'PUT' }); on ? S.favs.delete(slug) : S.favs.add(slug); renderFavs(); renderLibrary(); toast(on ? 'Quitado de favoritos' : 'Añadido a favoritos'); } catch (x) { fail(x); }
  }, true);

  /* ---------- contacto + newsletter ---------- */
  const ct = $('#ctf');
  if (ct) ct.onsubmit = async e => {
    e.preventDefault(); const er = $('#cter'), btn = $('button[type=submit]', ct); er.textContent = '';
    const body = { name: $('#ct-n').value.trim(), email: $('#ct-e').value.trim(), message: $('#ct-m').value.trim(), website: $('#ct-w').value };
    if (body.name.length < 2) return er.textContent = 'Escribe tu nombre.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(body.email)) return er.textContent = 'Escribe un correo válido.';
    if (body.message.length < 10) return er.textContent = 'El mensaje es demasiado corto.';
    busy(btn, true);
    try { const r = await api('contact', { method: 'POST', body }); ct.reset(); toast(r.message); } catch (x) { fail(x, er); } finally { busy(btn, false); }
  };
  const nl = $('#nlf');
  if (nl) nl.onsubmit = async e => {
    e.preventDefault(); const email = $('#nl-e').value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return toast('Escribe un correo válido');
    try { const r = await api('newsletter', { method: 'POST', body: { email } }); nl.reset(); toast(r.message); if (r.dev_link) console.info('[dev] confirmar newsletter:', r.dev_link); } catch (x) { fail(x); }
  };

  /* ---------- panel de administración ---------- */
  const A = { tab: 'users', q: '', ev: '', page: 1 };
  async function renderAdmin() {
    const box = $('#adBox'); if (!box) return;
    if (!S.user || S.user.role !== 'admin') { box.innerHTML = '<p class="mut">No autorizado.</p>'; return; }
    box.innerHTML = '<p class="mut">Cargando…</p>';
    let st;
    try { st = await api('admin/stats'); } catch (x) {
      box.innerHTML = `<div class="card adp"><h3>Panel bloqueado</h3><p class="mut">${esc(x.message)}</p>${x.data.code === 'mfa_required' ? '<a class="btn" href="#account">Activar 2FA en Mi cuenta</a>' : ''}</div>`; return;
    }
    const tiles = [['Usuarios', st.users], ['Verificados', st.verified], ['Con 2FA', st.mfa], ['Bloqueados', st.locked], ['Sesiones', st.sessions], ['Patrones', st.patterns], ['Mensajes', st.messages_open], ['Suscriptores', st.subscribers], ['Logins fallidos 24h', st.failed_logins_24h], ['CSRF bloqueados 24h', st.csrf_blocked_24h], ['Rate-limit 24h', st.rate_limited_24h]];
    box.innerHTML = `<div class="tiles">${tiles.map(([k, v]) => `<div class="tile"><b>${+v}</b><span>${k}</span></div>`).join('')}</div>
      <div class="tabs" role="tablist">${[['users', 'Usuarios'], ['audit', 'Auditoría'], ['messages', 'Mensajes']].map(([k, l]) => `<button role="tab" data-at="${k}" aria-selected="${A.tab === k}">${l}</button>`).join('')}</div><div id="adv" class="card adp"></div>`;
    $$('[data-at]', box).forEach(b => b.onclick = () => { A.tab = b.dataset.at; A.page = 1; renderAdmin(); });
    renderAdminTab();
  }
  async function renderAdminTab() {
    const v = $('#adv'); if (!v) return;
    try {
      if (A.tab === 'users') {
        const { users } = await api(`admin/users?q=${encodeURIComponent(A.q)}&page=${A.page}`);
        v.innerHTML = `<form id="aqf" class="row"><label class="sr" for="aq">Buscar</label><input id="aq" placeholder="Buscar por correo o nombre" value="${esc(A.q)}"><button class="btn sm" type="submit">Buscar</button></form>
          <div class="tbl"><table><thead><tr><th>Usuario</th><th>Estado</th><th>Alta</th><th>Acciones</th></tr></thead><tbody>${users.map(u => {
            const locked = u.locked_until && u.locked_until * 1000 > Date.now();
            const st = [u.role === 'admin' ? 'admin' : '', u.email_verified ? 'verificado' : 'sin verificar', u.mfa ? '2FA' : '', u.disabled ? 'deshabilitado' : '', locked ? 'bloqueado' : ''].filter(Boolean).join(' · ');
            const acts = [u.disabled ? ['enable', 'Habilitar'] : ['disable', 'Deshabilitar'], locked ? ['unlock', 'Desbloquear'] : null, u.role === 'admin' ? ['demote', 'Quitar admin'] : ['promote', 'Hacer admin'], ['logout', 'Cerrar sesiones']].filter(Boolean);
            return `<tr><td><b>${esc(u.name)}</b><br><small>${esc(u.email)}</small></td><td><small>${esc(st)}</small></td><td><small>${fmtDate(u.created_at)}</small></td><td>${u.id === S.user.id ? '<small>(tú)</small>' : acts.map(([a, l]) => `<button class="btn o sm" data-ua="${a}" data-uid="${u.id}">${l}</button>`).join(' ')}</td></tr>`;
          }).join('') || '<tr><td colspan="4">Sin resultados</td></tr>'}</tbody></table></div>${pager(users.length)}`;
        $('#aqf').onsubmit = e => { e.preventDefault(); A.q = $('#aq').value; A.page = 1; renderAdminTab(); };
        $$('[data-ua]', v).forEach(b => b.onclick = async () => { if (!confirm(`¿${b.textContent}?`)) return; try { await api('admin/users/' + b.dataset.uid, { method: 'POST', body: { action: b.dataset.ua } }); toast('Hecho'); renderAdminTab(); } catch (x) { fail(x); } });
      } else if (A.tab === 'audit') {
        const { events } = await api(`admin/audit?event=${encodeURIComponent(A.ev)}&page=${A.page}`);
        const EV = ['', 'login_ok', 'login_fallido', 'cuenta_bloqueada', 'registro', 'reset_solicitado', 'reset_ok', 'password_cambiada', '2fa_activado', 'csrf_rechazado', 'rate_limit', 'acceso_denegado', 'admin_accion', 'cuenta_eliminada'];
        v.innerHTML = `<div class="row"><label class="sr" for="aev">Evento</label><select id="aev">${EV.map(e => `<option value="${e}" ${e === A.ev ? 'selected' : ''}>${e || 'Todos los eventos'}</option>`).join('')}</select></div>
          <div class="tbl"><table><thead><tr><th>Fecha</th><th>Evento</th><th>Usuario</th><th>IP</th><th>Ruta</th><th>Estado</th></tr></thead><tbody>${events.map(e => `<tr><td><small>${fmtDate(e.ts)}</small></td><td><code>${esc(e.event)}</code></td><td><small>${esc(e.user_label || '-')}</small></td><td><small>${esc(e.ip || '')}</small></td><td><small>${esc(e.method + ' ' + e.path)}</small></td><td>${+e.status}</td></tr>`).join('') || '<tr><td colspan="6">Sin eventos</td></tr>'}</tbody></table></div>${pager(events.length)}`;
        $('#aev').onchange = e => { A.ev = e.target.value; A.page = 1; renderAdminTab(); };
      } else {
        const { messages } = await api(`admin/messages?page=${A.page}`);
        v.innerHTML = `<div class="list">${messages.map(m => `<div class="li msg ${m.handled ? 'done' : ''}"><div><b>${esc(m.name)}</b> <small>&lt;${esc(m.email)}&gt; · ${fmtDate(m.created_at)}</small><p>${esc(m.body)}</p></div>${m.handled ? '<small>atendido</small>' : `<button class="btn o sm" data-mh="${m.id}">Marcar atendido</button>`}</div>`).join('') || '<p class="mut">Sin mensajes.</p>'}</div>${pager(messages.length)}`;
        $$('[data-mh]', v).forEach(b => b.onclick = async () => { try { await api(`admin/messages/${b.dataset.mh}/handled`, { method: 'POST' }); renderAdminTab(); } catch (x) { fail(x); } });
      }
      $$('[data-pg]', v).forEach(b => b.onclick = () => { A.page += +b.dataset.pg; renderAdminTab(); });
    } catch (x) { v.textContent = x.message; }
  }
  const pager = n => `<div class="row pager">${A.page > 1 ? '<button class="btn o sm" data-pg="-1">← Anterior</button>' : ''}<small>Página ${A.page}</small>${n === 25 ? '<button class="btn o sm" data-pg="1">Siguiente →</button>' : ''}</div>`;

  /* ---------- enlaces de correo (?verify / ?reset / ?newsletter / ?pattern) ---------- */
  const goAccount = () => { if (location.hash === '#account') S.user ? renderAccount() : renderAuth(); else location.hash = '#account'; };
  async function handleLinks() {
    const q = new URLSearchParams(location.search); if (![...q.keys()].length) return;
    // el router de app.js fuerza «Inicio» en el evento load: navegamos después de él
    if (document.readyState !== 'complete') await new Promise(r => addEventListener('load', r, { once: true }));
    await new Promise(r => setTimeout(r, 0));
    const clean = () => history.replaceState(null, '', location.pathname + location.hash);
    const v = q.get('verify'), rs = q.get('reset'), nlt = q.get('newsletter'), pt = q.get('pattern');
    clean(); // no dejar tokens en el historial ni en Referer
    try {
      if (v) { const r = await api('auth/verify', { method: 'POST', body: { token: v } }); S.mode = 'login'; S.flash = esc(r.message); goAccount(); }
      if (rs) { S.resetToken = rs; S.mode = 'reset'; goAccount(); }
      if (nlt) { const r = await api('newsletter/confirm', { method: 'POST', body: { token: nlt } }); toast(r.message); }
      if (pt) { const r = await api('shared/' + encodeURIComponent(pt)); setPattern(r.pattern); location.hash = '#lab'; toast(`«${r.pattern.name}» de ${r.pattern.author}`); }
    } catch (x) { fail(x); }
  }

  /* ---------- arranque ---------- */
  addEventListener('hashchange', () => { if (location.hash === '#account') S.user ? renderAccount() : renderAuth(); if (location.hash === '#admin') renderAdmin(); });
  (async () => {
    S.online = await detectBackend();
    if (S.online) { try { S.user = (await api('me')).user; await loadLibrary(); } catch (e) { S.user = null; } }
    navUpd(); S.user ? renderAccount() : renderAuth();
    if (location.hash === '#admin') renderAdmin();
    if (S.online) handleLinks();
  })();
}
