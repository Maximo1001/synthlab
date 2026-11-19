# Seguridad de SYNTHLAB

Controles implementados, mapeados a OWASP Top 10 (2021) y ASVS. Cada uno tiene test en `tests/`.

## Autenticación y contraseñas (A07)
- **Argon2id** (`argon2-cffi`, t=3, m=19 MiB, p=1) con rehash automático si cambian los parámetros.
- Política NIST 800-63B: 12–128 caracteres, sin reglas de composición absurdas, bloqueo de contraseñas
  comunes/repetitivas o que contengan el nombre o el correo. Opcional: comprobación en Have I Been Pwned
  por k-anonimato (`SYNTHLAB_HIBP_CHECK`).
- **Sin enumeración de usuarios**: mismo mensaje y mismo coste (hash ficticio) para usuario inexistente,
  contraseña errónea o cuenta bloqueada; registro y «olvidé mi contraseña» responden igual exista o no el correo
  (el titular recibe un aviso).
- **Bloqueo progresivo** tras 5 fallos (15 min, duplicando hasta 24 h) + aviso por correo.
- **Verificación de correo** obligatoria antes del primer login.
- **2FA TOTP** (RFC 6238) con protección anti-reutilización del código, 8 códigos de recuperación de un solo uso
  (guardados como hash), obligatoria para administradores en producción.
- Recuperación de contraseña con token aleatorio de 256 bits, guardado como SHA-256, 30 min, un solo uso;
  al usarlo se cierran **todas** las sesiones. Los enlaces usan `SYNTHLAB_PUBLIC_URL` fija (no la cabecera Host).

## Sesiones (A07)
- Sesiones **de servidor**: la cookie sólo lleva un token aleatorio; en BD se guarda su hash. Revocables una a una,
  «cerrar las demás», y en bloque al cambiar/restablecer contraseña o al cambiar privilegios.
- Cookie `__Host-` + `Secure` + `HttpOnly` + `SameSite=Strict`. Rotación en cada login (anti fijación).
- Caducidad por inactividad (30 min) y absoluta (12 h).

## Control de acceso (A01)
- Autorización por objeto en todas las consultas (`WHERE id = ? AND user_id = ?`) → sin IDOR; respuesta 404
  para no confirmar la existencia de recursos ajenos.
- Rol `admin` comprobado en servidor; un admin no puede degradarse/deshabilitarse a sí mismo.
- Operaciones sensibles (baja, 2FA, cambio de contraseña) exigen re-autenticación.
- Enlaces compartidos con slug aleatorio de 72 bits, revocables, sin exponer el correo del autor.

## Inyección y XSS (A03)
- 100 % consultas parametrizadas; búsqueda del admin con `LIKE … ESCAPE` (comodines literales).
- Validación estricta de entrada (tipos, rangos, longitudes, lista blanca de productos).
- La API sólo devuelve JSON; el frontend escapa todo lo que inserta (`esc()`).
- **CSP estricta**: `script-src 'self'`, sin JS ni `<style>` en línea, `object-src 'none'`, `base-uri 'none'`,
  `frame-ancestors 'none'`.

## CSRF
Defensa en profundidad para todo método que cambia estado: Fetch Metadata (`Sec-Fetch-Site`), comprobación de
`Origin`, token doble envío (cookie `HttpOnly` + cabecera `X-CSRF-Token`, comparación en tiempo constante),
`SameSite=Strict` y `Content-Type: application/json` obligatorio (bloquea formularios cruzados).

## Abuso y disponibilidad
- Rate limiting persistido en SQLite (compartido entre workers): login por IP y por cuenta, registro, reset,
  2FA, contacto, newsletter… con `Retry-After`. Segunda capa en nginx (`limit_req`).
- Honeypot anti-bots en registro y contacto; `MAX_CONTENT_LENGTH` 64 KB; límites de cabeceras en gunicorn.

## Configuración segura (A05)
- Seguro por defecto: sin `SYNTHLAB_ENV=development` exige `SECRET_KEY` (≥32) y `PUBLIC_URL`, activa cookies
  `Secure`, HSTS (2 años, preload) y `upgrade-insecure-requests`.
- Cabeceras: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP, CORP,
  `Cache-Control: no-store` en la API. Errores sin trazas.
- Sólo se sirven `index.html` y `/static/`: nunca el resto del repositorio.
- Secretos fuera del código (`.env`, ignorado por git). BD con permisos `0600`.
- Contenedor no-root, sistema de ficheros de solo lectura, `cap_drop: ALL`, `no-new-privileges`;
  unidad systemd con `ProtectSystem=strict`, `NoNewPrivileges`, filtro de syscalls.

## Registro y monitorización (A09)
Log JSON en `SYNTHLAB_SECURITY_LOG` (además de la tabla `audit_log`), con el contrato
`ts/app/evento/usuario/ip/metodo/ruta/estado/detalle` apto para Wazuh/SIEM. Eventos: `registro`, `login_ok`,
`login_fallido`, `cuenta_bloqueada`, `mfa_fallido`, `reset_solicitado`, `reset_ok`, `password_cambiada`,
`2fa_activado`, `csrf_rechazado`, `rate_limit`, `acceso_denegado`, `admin_accion`, `cuenta_eliminada`…
Nunca se registran contraseñas ni tokens. Retención de auditoría: 180 días (`flask cleanup`).

## Privacidad (RGPD)
Exportación completa de datos del usuario, baja con borrado en cascada y anonimización de su rastro de auditoría,
newsletter con doble opt-in, consentimiento explícito en el registro.

## Cadena de suministro (A06/A08)
`uv.lock` con versiones fijadas; CI con `pip-audit`, `bandit`, `ruff` y `gitleaks`.

## Riesgos residuales conocidos
- El secreto TOTP se guarda en claro en la BD (protegida por permisos). Mejora: cifrarlo con una clave KMS.
- SQLite es adecuado para un único servidor; para varios nodos migrar a PostgreSQL y el rate-limit a Redis.
- `style-src-attr 'unsafe-inline'` es necesario por las variables CSS en atributos `style`; no permite JS.

## Notificar una vulnerabilidad
Usa el formulario de contacto o abre un aviso privado de seguridad en GitHub. No publiques detalles hasta que
esté corregida.
