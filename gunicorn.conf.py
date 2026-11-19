"""Configuración de gunicorn para producción (detrás de nginx)."""

import multiprocessing
import os

bind = os.environ.get("SYNTHLAB_BIND", "127.0.0.1:8000")
workers = int(os.environ.get("SYNTHLAB_WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = 2
timeout = 30
graceful_timeout = 20
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
forwarded_allow_ips = os.environ.get("SYNTHLAB_FORWARDED_ALLOW_IPS", "127.0.0.1")
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'
