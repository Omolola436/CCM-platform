import os


class Config:
    SECRET_KEY = os.environ.get("SESSION_SECRET") or os.environ.get("SECRET_KEY") or "ccmp-dev-secret-key-change-in-prod"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "postgresql://postgres:3consulting@localhost:5432/mydb"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = os.environ.get("REMEMBER_COOKIE_SECURE", "False").lower() == "true"
    REMEMBER_COOKIE_DURATION = 86400 * 7
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_PROTECTION = "strong"
    SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "30"))
    MAX_FAILED_LOGINS = int(os.environ.get("MAX_FAILED_LOGINS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))
    PERMANENT_SESSION_LIFETIME = 86400 * 7
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")

    SMTP_SERVER = os.environ.get("SMTP_SERVER")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"
    SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL") or "noreply@3consulting.com"
    SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME") or "CCMP"

    CCMP_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL") or "admin@3consulting.com"
    CCMP_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "Admin@CCMP2025!"
    CCMP_ORG_NAME = os.environ.get("ORG_NAME", "3Consulting")

    WEBHOOK_TIMEOUT = 10
    WEBHOOK_RETRY_LIMIT = 3
    POLICY_SYNC_LOOP_SECONDS = int(os.environ.get("POLICY_SYNC_LOOP_SECONDS", "60"))
    POLICY_SYNC_DISABLED = os.environ.get("POLICY_SYNC_DISABLED", "false").lower() == "true"
