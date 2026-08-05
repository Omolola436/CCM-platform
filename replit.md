# CCMP — Consent & Compliance Management Platform

Flask-based privacy operations platform for managing consents, policies, users, and audit logs. Built for ISO/IEC 27034 alignment.

## Running the app

```
python -m flask run --host=0.0.0.0 --port=5000
```

The workflow "Start application" handles this automatically.

## Default admin credentials

| Field    | Value                          |
|----------|--------------------------------|
| Email    | admin@3consulting.com          |
| Password | Admin@CCMP2025!                |

Change the default password immediately after first login.

## Tech stack

- **Backend**: Flask 3.1 + SQLAlchemy 2 (PostgreSQL via Replit built-in DB)
- **Auth**: Flask-Login + Flask-Bcrypt + Flask-WTF (CSRF)
- **Rate limiting**: Flask-Limiter (in-memory; swap to Redis for production)
- **Reports**: ReportLab (PDF generation)

## Security architecture

### RBAC (Role-Based Access Control)
Roles: `admin`, `manager`, `dpo`, `auditor`, `user`
Permissions defined in `utils/permissions.py`. Use `@permission_required(PERM)` on routes and `current_user.can(PERM)` in templates/code.

### API Security
- API Keys stored as SHA-256 hashes in `api_keys` table (raw key shown once, never stored)
- `X-API-Key: <raw>` header accepted on all `/api/v1/*` routes
- Scopes enforced per-endpoint via `@api_scope_required("scope:name")`
- Session auth also accepted (browser users are not scope-restricted)
- Rate limit: 200 req/min / 2000 req/hr per IP (Flask-Limiter)
- Manage keys at `/admin/api-keys` (admin only)

### Consent Integrity
- Every status change creates an immutable `ConsentHistory` entry **before** the record is mutated
- `consent_fingerprint` (SHA-256 of immutable fields) stored at creation; verify with `ConsentService.verify_fingerprint(consent)`
- All lifecycle operations go through `ConsentService` — never update `consent.status` directly

### Security Headers
All responses include: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`, `Strict-Transport-Security` (HSTS, 1 year).

## Key files

| File | Purpose |
|------|---------|
| `utils/permissions.py` | RBAC permission constants + role→permission map |
| `utils/decorators.py` | `@permission_required`, `@api_auth_required`, `@api_scope_required` |
| `models/api_key.py` | APIKey model (hashed keys, scopes, expiry) |
| `services/consent_service.py` | All consent lifecycle ops + fingerprint verification |
| `app.py` | App factory, security headers, rate limiter |

## User preferences

- Keep existing project structure — do not restructure or migrate
