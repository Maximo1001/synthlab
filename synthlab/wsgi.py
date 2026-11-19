"""Punto de entrada WSGI: gunicorn 'synthlab.wsgi:app'."""

from synthlab import create_app

app = create_app()
