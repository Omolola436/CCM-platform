# CCMP

Consent & Compliance Management Platform (CCMP) is a Flask application for
privacy operations, consent tracking, audit logs, and role-based access.

## Running on Replit

- Workflow: `Start application`
- Command: `python app.py`
- Preview port: `5000`
- Python dependencies: `requirements.txt`
- Database: PostgreSQL, using the `DATABASE_URL` environment variable

The app creates its tables and seeds a demo organization and administrator on
first startup. Existing databases are checked for recently added user security
columns, including password-reset fields.

## Configuration

`SESSION_SECRET` is used for Flask sessions. The seeded administrator can be
configured with `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `ORG_NAME`; SMTP settings
are optional and are only needed for email delivery.