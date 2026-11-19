# SYNTHLAB — Da forma a tu sonido

Web de producción musical: pads de batería, secuenciador por pasos y visualizador de audio
en el navegador, con **cuentas de usuario y backend seguro** (Flask + SQLite).

| Capa | Qué incluye |
|---|---|
| **Frontend** (`index.html`, `static/`) | Laboratorio Web Audio, catálogo con favoritos, recursos, contacto, newsletter, área «Mi cuenta», panel de administración. Sin JS ni CSS en línea (CSP estricta). |
| **Backend** (`synthlab/`) | API JSON: registro con verificación por correo, login con 2FA (TOTP + códigos de recuperación), recuperación de contraseña, sesiones revocables, patrones guardados y compartibles, favoritos, exportación de datos (RGPD), baja, panel admin y auditoría. |
| **Operación** | `gunicorn`, `nginx` (TLS + rate-limit), `systemd` bastionado, Docker no-root de solo lectura, CI con lint, tests, SAST, auditoría de dependencias y búsqueda de secretos. |

Si la página se sirve sin backend (por ejemplo, en GitHub Pages) funciona en **modo demostración**:
el laboratorio va completo y el área de cuenta explica que necesita el servidor.

## Arranque rápido (desarrollo)

Requisitos: Python ≥ 3.11 y [uv](https://docs.astral.sh/uv/).

```bash
uv sync
SYNTHLAB_ENV=development uv run flask --app synthlab:create_app run -p 5055
# abre http://127.0.0.1:5055
```

En desarrollo los correos (activación, reset, newsletter) se escriben en la consola y la propia
interfaz muestra un enlace «abrir enlace del correo» para no necesitar SMTP.
(En macOS evita el puerto 5000: lo ocupa AirPlay).

Crear un administrador:

```bash
SYNTHLAB_ENV=development uv run flask --app synthlab:create_app create-admin --email tu@correo.com --name "Tu nombre"
```

En producción el panel exige que el administrador tenga activada la verificación en dos pasos.

## Tests y calidad

```bash
uv run pytest --cov=synthlab      # 33 tests: auth, 2FA, CSRF, IDOR, SQLi, XSS, rate-limit, cabeceras...
uv run ruff check . && uv run ruff format --check .
uv run bandit -c pyproject.toml -r synthlab
```

## Producción

1. `cp .env.example .env` y rellena `SYNTHLAB_SECRET_KEY`, `SYNTHLAB_PUBLIC_URL`, `SYNTHLAB_TRUSTED_HOSTS` y el SMTP.
   Sin `SYNTHLAB_SECRET_KEY` ni `SYNTHLAB_PUBLIC_URL` la app **no arranca** (seguro por defecto).
2. Opción Docker: certificados en `deploy/certs/` y `docker compose up -d --build`.
3. Opción systemd: código en `/srv/synthlab`, `uv sync --no-dev`, entorno en `/etc/synthlab/synthlab.env`,
   copia `deploy/synthlab.service` + `deploy/synthlab-cleanup.{service,timer}` y `deploy/nginx.conf`
   (cambia el upstream a `127.0.0.1:8000`).
4. Con nginx delante, `SYNTHLAB_TRUSTED_PROXIES=1` para que la IP real llegue a logs y rate-limit.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/csrf` | Token CSRF (obligatorio en cabecera `X-CSRF-Token` para POST/PUT/PATCH/DELETE) |
| POST | `/api/auth/register` · `/verify` · `/resend-verification` | Alta y activación |
| POST | `/api/auth/login` · `/login/mfa` · `/logout` | Sesión (con 2FA si está activa) |
| POST | `/api/auth/forgot` · `/reset` | Recuperación de contraseña |
| GET/PATCH/DELETE | `/api/me` | Perfil / baja (requiere contraseña) |
| POST | `/api/me/password` · `/2fa/setup` · `/2fa/enable` · `/2fa/disable` · `/2fa/recovery-codes` | Seguridad de la cuenta |
| GET/DELETE | `/api/me/sessions[/<id>]` · POST `/sessions/revoke-others` | Sesiones activas |
| GET | `/api/me/export` | Descarga de todos tus datos |
| GET/POST/PUT/DELETE | `/api/patterns[/<id>]` · POST `/<id>/share` | Patrones del secuenciador |
| GET | `/api/shared/<slug>` | Patrón compartido (público, solo lectura) |
| GET/PUT/DELETE | `/api/favorites[/<producto>]` | Favoritos |
| POST | `/api/contact` · `/api/newsletter` · `/api/newsletter/confirm` | Contacto y newsletter (doble opt-in) |
| GET/POST | `/api/admin/stats` · `/users` · `/users/<id>` · `/audit` · `/messages` | Administración |

Los controles de seguridad están detallados en [SECURITY.md](SECURITY.md).

## Estructura

```
index.html, static/        frontend (también publicable en GitHub Pages)
synthlab/                  backend Flask (config, db, schema.sql, auth, account, api, admin, security, totp)
tests/                     pytest
deploy/                    nginx, systemd
login-sql/                 laboratorio original de pruebas (vulnerable a propósito, NO desplegar)
```
