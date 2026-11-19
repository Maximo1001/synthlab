"""Envío de correo. 'console' escribe en el log (desarrollo); 'smtp' usa STARTTLS obligatorio."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app

OUTBOX: list[EmailMessage] = []  # usado por los tests


def send(to: str, subject: str, body: str) -> None:
    cfg = current_app.config
    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if cfg["TESTING"]:
        OUTBOX.append(msg)
        return
    if cfg["MAIL_BACKEND"] == "smtp":
        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
            smtp.starttls(context=ctx)
            if cfg["SMTP_USER"]:
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return
    # console: sólo en desarrollo tiene sentido; en producción avisamos fuerte.
    level = current_app.logger.info if cfg["DEV"] else current_app.logger.warning
    level("[mail:console] Para: %s | Asunto: %s\n%s", to, subject, body)
