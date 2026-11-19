# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY synthlab ./synthlab
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN groupadd -r synthlab && useradd -r -g synthlab -d /app -s /usr/sbin/nologin synthlab \
 && mkdir -p /var/lib/synthlab /var/log/synthlab && chown synthlab:synthlab /var/lib/synthlab /var/log/synthlab
WORKDIR /app
COPY --from=build /app /app
COPY index.html gunicorn.conf.py ./
COPY static ./static
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SYNTHLAB_INSTANCE_DIR=/var/lib/synthlab SYNTHLAB_SECURITY_LOG=/var/log/synthlab/seguridad.log \
    SYNTHLAB_BIND=0.0.0.0:8000 SYNTHLAB_FRONTEND_DIR=/app
USER synthlab
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2)"
CMD ["gunicorn", "-c", "gunicorn.conf.py", "synthlab.wsgi:app"]
