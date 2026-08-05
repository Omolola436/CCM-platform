import os
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from sqlalchemy import inspect, text
from config import Config
from models.base import db

login_manager = LoginManager()
csrf = CSRFProtect()
bcrypt = Bcrypt()


def ensure_consent_schema(app):
    inspector = inspect(db.engine)
    if "consents" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("consents")}
    if "source_document" not in existing_columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE consents ADD COLUMN source_document VARCHAR(255)"))
        app.logger.info("Added missing source_document column to consents table")


def ensure_audit_schema(app):
    inspector = inspect(db.engine)
    if "audit_logs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("audit_logs")}
    with db.engine.begin() as connection:
        if "actor_role" not in existing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN actor_role VARCHAR(50)"))
            app.logger.info("Added missing actor_role column to audit_logs table")
        if "location" not in existing_columns:
            connection.execute(text("ALTER TABLE audit_logs ADD COLUMN location VARCHAR(100)"))
            app.logger.info("Added missing location column to audit_logs table")


def ensure_user_security_schema(app):
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    with db.engine.begin() as connection:
        if "failed_login_attempts" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0 NOT NULL"))
            app.logger.info("Added failed_login_attempts column to users table")
        if "locked_until" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP"))
            app.logger.info("Added locked_until column to users table")
        if "last_login_ip" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45)"))
            app.logger.info("Added last_login_ip column to users table")
        if "last_login_location" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN last_login_location VARCHAR(100)"))
            app.logger.info("Added last_login_location column to users table")
        if "password_changed_at" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMP"))
            app.logger.info("Added password_changed_at column to users table")
        if "mfa_enabled" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE NOT NULL"))
            app.logger.info("Added mfa_enabled column to users table")
        if "mfa_secret" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN mfa_secret VARCHAR(255)"))
            app.logger.info("Added mfa_secret column to users table")
        if "mfa_last_verified_at" not in existing_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN mfa_last_verified_at TIMESTAMP"))
            app.logger.info("Added mfa_last_verified_at column to users table")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access CCMP."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    from routes import auth_bp, dashboard_bp, consent_bp, preference_bp, audit_bp, integration_bp, api_bp, admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(consent_bp)
    app.register_blueprint(preference_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(integration_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    csrf.exempt(api_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.before_request
    def before_request_security():
        from utils.security import enforce_session_timeout
        result = enforce_session_timeout()
        if result is not None:
            return result

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        )
        return response

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        unread = 0
        if current_user.is_authenticated:
            from models.notification import Notification
            unread = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        return dict(unread_notifications=unread)

    with app.app_context():
        db.create_all()
        ensure_consent_schema(app)
        ensure_audit_schema(app)
        ensure_user_security_schema(app)
        _seed(app)

    return app


def _seed(app):
    from models.organization import Organization
    from models.user import User
    from models.policy import PolicyVersion
    from models.consent import DataSubject, Consent, ConsentHistory
    from models.audit import AuditLog
    import random
    from datetime import datetime, timezone, timedelta

    if Organization.query.first():
        return

    org = Organization(name=app.config["CCMP_ORG_NAME"], domain="3consulting.com",
                       plan="enterprise", industry="Consulting", country="Nigeria")
    db.session.add(org)
    db.session.flush()

    admin = User(
        email=app.config["CCMP_ADMIN_EMAIL"],
        first_name="Platform", last_name="Admin",
        role="admin", org_id=org.id,
        password_hash=bcrypt.generate_password_hash(app.config["CCMP_ADMIN_PASSWORD"]).decode(),
    )
    db.session.add_all([admin])
    db.session.flush()

    notices = [
        PolicyVersion(version="v1.0", title="Privacy Notice v1.0",
                      content="Initial privacy notice covering data collection and processing under NDPA.",
                      summary="Basic NDPA-compliant privacy notice.", is_current=False,
                      effective_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
                      org_id=org.id, created_by=admin.id),
        PolicyVersion(version="v1.1", title="Privacy Notice v1.1",
                      content="Updated notice reflecting NDPA enforcement regulations.",
                      summary="Updated to reflect NDPA enforcement.", is_current=False,
                      effective_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
                      org_id=org.id, created_by=admin.id),
        PolicyVersion(version="v2.0", title="Privacy Notice v2.0",
                      content="Full GDPR and NDPA aligned privacy notice with enhanced data subject rights.",
                      summary="GDPR + NDPA aligned with enhanced rights.", is_current=True,
                      effective_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
                      org_id=org.id, created_by=admin.id),
    ]
    db.session.add_all(notices)
    db.session.flush()

    subjects_data = [
        ("Amina Okafor", "amina.okafor@example.com", "+234-801-000-0001", "Nigeria"),
        ("Chidi Nwosu", "chidi.nwosu@example.com", "+234-802-000-0002", "Nigeria"),
        ("Fatima Al-Hassan", "fatima.alhassan@example.com", "+234-803-000-0003", "Nigeria"),
        ("Emeka Eze", "emeka.eze@example.com", "+234-804-000-0004", "Nigeria"),
        ("Grace Adeyemi", "grace.adeyemi@example.com", "+234-805-000-0005", "Nigeria"),
        ("Tunde Bakare", "tunde.bakare@example.com", "+44-7700-900001", "UK"),
        ("Ngozi Obi", "ngozi.obi@example.com", "+234-807-000-0007", "Nigeria"),
        ("Yusuf Musa", "yusuf.musa@example.com", "+234-808-000-0008", "Nigeria"),
        ("Chisom Ikenna", "chisom.ikenna@example.com", "+1-555-000-0009", "USA"),
        ("Blessing Adeola", "blessing.adeola@example.com", "+234-810-000-0010", "Nigeria"),
    ]
    from models.consent import PURPOSES, LEGAL_BASES, CHANNELS
    statuses = ["Active", "Active", "Active", "Withdrawn", "Expired"]
    versions = ["v1.0", "v1.1", "v2.0"]
    now = datetime.now(timezone.utc)

    subjects = []
    for name, email, phone, country in subjects_data:
        s = DataSubject(name=name, email=email, phone=phone, country=country, org_id=org.id)
        db.session.add(s)
        subjects.append(s)
    db.session.flush()

    for subject in subjects:
        for _ in range(random.randint(2, 5)):
            days_ago = random.randint(1, 400)
            created = now - timedelta(days=days_ago)
            status = random.choice(statuses)
            ver = random.choice(versions)
            pv_obj = next((p for p in notices if p.version == ver), notices[-1])
            c = Consent(
                subject_id=subject.id, purpose=random.choice(PURPOSES),
                legal_basis=random.choice(LEGAL_BASES), channel=random.choice(CHANNELS),
                status=status, policy_version=ver, policy_version_id=pv_obj.id,
                org_id=org.id, created_by=admin.id, created_at=created, updated_at=created,
            )
            db.session.add(c)
            db.session.flush()
            h = ConsentHistory(
                consent_id=c.id, old_status=None, new_status="Active",
                changed_by=subject.name,
                reason=f"Consent granted for '{c.purpose}' via {c.channel}.",
                source=c.channel, ip_address=f"192.168.{random.randint(1,10)}.{random.randint(1,254)}",
                timestamp=created,
            )
            db.session.add(h)
            if status == "Withdrawn":
                withdrawn_at = created + timedelta(days=random.randint(1, 60))
                h2 = ConsentHistory(
                    consent_id=c.id, old_status="Active", new_status="Withdrawn",
                    changed_by=subject.name, reason="Withdrawal requested by data subject.",
                    source="Preference Centre",
                    ip_address=f"192.168.{random.randint(1,10)}.{random.randint(1,254)}",
                    timestamp=withdrawn_at,
                )
                db.session.add(h2)
            log = AuditLog(
                entity_type="Consent", entity_id=c.id,
                action="Consent Granted" if status == "Active" else ("Consent Withdrawn" if status == "Withdrawn" else "Consent Expired"),
                actor_id=admin.id, actor_email=admin.email, actor_name=admin.full_name,
                details=f"Purpose: {c.purpose} | Channel: {c.channel} | Policy: {ver}",
                ip_address=f"192.168.{random.randint(1,10)}.{random.randint(1,254)}",
                org_id=org.id, created_at=created,
            )
            db.session.add(log)

    from models.integration import Integration, Webhook
    db.session.add_all([
        Integration(name="Salesforce CRM", type="crm", description="Salesforce integration for contact consent sync",
                    endpoint="https://api.salesforce.com", status="active", org_id=org.id, created_by=admin.id),
        Integration(name="Mailchimp", type="email", description="Email marketing consent synchronization",
                    endpoint="https://api.mailchimp.com", status="active", org_id=org.id, created_by=admin.id),
        Integration(name="Google Analytics", type="analytics", description="Analytics consent gateway",
                    endpoint="https://analytics.google.com", status="inactive", org_id=org.id, created_by=admin.id),
    ])
    db.session.add(
        Webhook(name="Consent Events Webhook", url="https://webhook.site/ccmp-demo",
                events=["consent.granted", "consent.withdrawn"], status="active",
                org_id=org.id, created_by=admin.id)
    )
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
