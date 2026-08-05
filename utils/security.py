import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from flask import current_app, flash, redirect, request, session, url_for
from flask_login import current_user, logout_user
from wtforms.validators import ValidationError


class PasswordStrength:
    def __init__(self, min_length=12):
        self.min_length = min_length

    def __call__(self, form, field):
        result = validate_password_strength(field.data, min_length=self.min_length)
        if not result["valid"]:
            raise ValidationError("Password must be at least 12 characters and include uppercase, lowercase, a number, and a special character.")


def validate_password_strength(password, min_length=12):
    errors = []
    if not password:
        return {"valid": False, "errors": ["Password is required"]}
    if len(password) < min_length:
        errors.append(f"at least {min_length} characters")
    if not re.search(r"[A-Z]", password):
        errors.append("an uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("a lowercase letter")
    if not re.search(r"\d", password):
        errors.append("a number")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("a special character")
    if re.search(r"(.)\1\1", password):
        errors.append("avoid repeated characters")
    return {"valid": not errors, "errors": errors}


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def is_account_locked(user):
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return True
    if user.locked_until and user.locked_until <= datetime.now(timezone.utc):
        user.locked_until = None
        user.failed_login_attempts = 0
    return False


def handle_failed_login(user):
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    max_attempts = current_app.config.get("MAX_FAILED_LOGINS", 5)
    lockout_minutes = current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15)
    if user.failed_login_attempts >= max_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        user.failed_login_attempts = 0
    return user


def clear_failed_login_attempts(user):
    user.failed_login_attempts = 0
    user.locked_until = None
    return user


def generate_reset_token():
    return secrets.token_urlsafe(32)


def create_password_reset_token(user):
    token = generate_reset_token()
    user.reset_token = token
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return token


def is_reset_token_valid(user, token):
    return bool(user.reset_token and token and user.reset_token == token and user.reset_token_expires_at and user.reset_token_expires_at > datetime.now(timezone.utc))


def clear_reset_token(user):
    user.reset_token = None
    user.reset_token_expires_at = None
    return user


def enforce_session_timeout():
    if not current_user.is_authenticated:
        return None
    if request.endpoint in {"auth.login", "auth.logout", "static"}:
        return None
    last_activity = session.get("last_activity")
    now = datetime.now(timezone.utc)
    if last_activity:
        last_activity_dt = datetime.fromtimestamp(last_activity, tz=timezone.utc)
        timeout_minutes = current_app.config.get("SESSION_TIMEOUT_MINUTES", 30)
        if now - last_activity_dt > timedelta(minutes=timeout_minutes):
            logout_user()
            session.clear()
            flash("Your session expired due to inactivity. Please sign in again.", "warning")
            return redirect(url_for("auth.login"))
    session["last_activity"] = now.timestamp()
    return None


def is_rate_limited():
    attempts = session.get("login_attempts", 0)
    max_attempts = current_app.config.get("LOGIN_RATE_LIMIT_MAX", 10)
    if attempts >= max_attempts:
        return True
    session["login_attempts"] = attempts + 1
    return False


def reset_rate_limit():
    session.pop("login_attempts", None)
