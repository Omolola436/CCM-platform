"""
Request decorators for authentication and authorization.

Provides:
  - admin_required            — route only accessible by admins
  - manager_required          — route only accessible by admin/manager
  - role_required(*roles)     — route accessible by any of the listed roles
  - permission_required(perm) — fine-grained RBAC check (session users)
  - api_auth_required         — accepts session login OR a valid X-API-Key header
  - api_scope_required(scope, session_permission=None)
        For API key callers:  enforces the named scope on the key.
        For session callers:  enforces session_permission via RBAC (if supplied).
"""
from functools import wraps
from flask import abort, redirect, url_for, request, jsonify, g
from flask_login import current_user


# ── Session-based decorators ──────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role not in {"admin", "manager"}:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(permission: str):
    """
    Decorator that checks a fine-grained RBAC permission for session users.

    Usage::

        @bp.route("/export")
        @login_required
        @permission_required(EXPORT_CONSENT)
        def export():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── API authentication decorator ──────────────────────────────────────────────

def _api_unauthorized(msg: str):
    return jsonify({"success": False, "error": msg}), 401


def api_auth_required(f):
    """
    Accepts either:
      1. An active browser session (current_user.is_authenticated), or
      2. A valid ``X-API-Key: <raw_key>`` header.

    On success the resolved org_id is stored in ``flask.g.api_org_id`` and,
    for key-based auth, the APIKey record in ``flask.g.api_key``.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        raw_key = request.headers.get("X-API-Key", "").strip()

        if raw_key:
            # ── API key path ──────────────────────────────────────────────
            from models.api_key import APIKey
            from models import db

            api_key = APIKey.lookup(raw_key)
            if api_key is None:
                return _api_unauthorized("Invalid API key.")
            if not api_key.is_valid:
                return _api_unauthorized("API key is inactive or expired.")

            api_key.record_use()
            try:
                db.session.flush()
            except Exception:
                db.session.rollback()

            g.api_org_id = api_key.org_id
            g.api_key = api_key
            g.api_actor = f"api_key:{api_key.name}"
            return f(*args, **kwargs)

        elif current_user.is_authenticated:
            # ── Session path ──────────────────────────────────────────────
            g.api_org_id = current_user.org_id
            g.api_key = None
            g.api_actor = current_user.full_name
            return f(*args, **kwargs)

        else:
            return _api_unauthorized(
                "Authentication required. Provide X-API-Key header or log in."
            )

    return decorated


def api_scope_required(scope: str, session_permission: str = None):
    """
    Enforce authorization on API endpoints for both auth paths.

    - **API key callers** must possess ``scope`` on their key.
    - **Session callers** must have ``session_permission`` in their role's
      permission set (if ``session_permission`` is supplied; otherwise
      session callers pass through without scope restriction).

    Must be stacked *after* ``@api_auth_required``::

        @bp.route("/consents", methods=["POST"])
        @api_auth_required
        @api_scope_required("consents:write", session_permission=CREATE_CONSENT)
        def create_consent():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            api_key = getattr(g, "api_key", None)
            if api_key is not None:
                # Key-based: enforce scope
                if not api_key.has_scope(scope):
                    return jsonify({
                        "success": False,
                        "error": f"API key lacks required scope: '{scope}'",
                    }), 403
            else:
                # Session-based: enforce RBAC permission (if specified)
                if session_permission and not current_user.can(session_permission):
                    return jsonify({
                        "success": False,
                        "error": "Insufficient permissions for this operation.",
                    }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
