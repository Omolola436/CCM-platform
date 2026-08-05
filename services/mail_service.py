import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to_address, subject, body):
    server = current_app.config.get("SMTP_SERVER")
    if not server:
        current_app.logger.warning("SMTP is not configured; skipping email delivery")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{current_app.config.get('SMTP_FROM_NAME', 'CCMP')} <{current_app.config.get('SMTP_FROM_EMAIL', 'noreply@3consulting.com')}>"
    msg["To"] = to_address
    msg.set_content(body)

    try:
        with smtplib.SMTP(server, current_app.config.get("SMTP_PORT", 587)) as smtp:
            if current_app.config.get("SMTP_USE_TLS", True):
                smtp.starttls()
            if current_app.config.get("SMTP_USERNAME"):
                smtp.login(current_app.config["SMTP_USERNAME"], current_app.config["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception as exc:
        current_app.logger.exception("Failed to send email: %s", exc)
        return False
