"""
Fine-grained RBAC permission system for CCMP.

Each role maps to an explicit set of permission strings.
Use `role_has_permission(role, perm)` or `User.can(perm)` everywhere
instead of raw role comparisons.
"""

# ── Permission constants ──────────────────────────────────────────────────────

# Consent
VIEW_CONSENT_REGISTRY = "view:consent_registry"
CREATE_CONSENT        = "create:consent"
WITHDRAW_CONSENT      = "withdraw:consent"
REACTIVATE_CONSENT    = "reactivate:consent"
EXPORT_CONSENT        = "export:consent"
DELETE_CONSENT        = "delete:consent"

# Audit
VIEW_AUDIT_LOGS    = "view:audit_logs"
EXPORT_AUDIT_LOGS  = "export:audit_logs"
DELETE_AUDIT_LOGS  = "delete:audit_logs"

# Policy
VIEW_POLICIES   = "view:policies"
CREATE_POLICY   = "create:policy"
APPROVE_POLICY  = "approve:policy"
DELETE_POLICY   = "delete:policy"

# Users
VIEW_USERS   = "view:users"
CREATE_USER  = "create:user"
EDIT_USER    = "edit:user"
DELETE_USER  = "delete:user"

# Integrations / API
VIEW_INTEGRATIONS    = "view:integrations"
MANAGE_INTEGRATIONS  = "manage:integrations"
MANAGE_API_KEYS      = "manage:api_keys"

# Reports / Dashboard
VIEW_REPORTS    = "view:reports"
EXPORT_REPORTS  = "export:reports"
VIEW_DASHBOARD  = "view:dashboard"

# ── Role → permission mapping ─────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[str, set] = {
    # Full control
    "admin": {
        VIEW_CONSENT_REGISTRY, CREATE_CONSENT, WITHDRAW_CONSENT,
        REACTIVATE_CONSENT, EXPORT_CONSENT, DELETE_CONSENT,
        VIEW_AUDIT_LOGS, EXPORT_AUDIT_LOGS, DELETE_AUDIT_LOGS,
        VIEW_POLICIES, CREATE_POLICY, APPROVE_POLICY, DELETE_POLICY,
        VIEW_USERS, CREATE_USER, EDIT_USER, DELETE_USER,
        VIEW_INTEGRATIONS, MANAGE_INTEGRATIONS, MANAGE_API_KEYS,
        VIEW_REPORTS, EXPORT_REPORTS, VIEW_DASHBOARD,
    },

    # Operational manager — cannot delete audit logs, users, or policies
    "manager": {
        VIEW_CONSENT_REGISTRY, CREATE_CONSENT, WITHDRAW_CONSENT,
        REACTIVATE_CONSENT, EXPORT_CONSENT,
        VIEW_AUDIT_LOGS, EXPORT_AUDIT_LOGS,
        VIEW_POLICIES, CREATE_POLICY, APPROVE_POLICY,
        VIEW_USERS,
        VIEW_INTEGRATIONS,
        VIEW_REPORTS, EXPORT_REPORTS,
        VIEW_DASHBOARD,
    },

    # Data Protection Officer — read-heavy, can approve & withdraw, no destructive ops
    "dpo": {
        VIEW_CONSENT_REGISTRY, EXPORT_CONSENT, WITHDRAW_CONSENT,
        VIEW_AUDIT_LOGS, EXPORT_AUDIT_LOGS,
        VIEW_POLICIES, APPROVE_POLICY,
        VIEW_USERS,
        VIEW_REPORTS, EXPORT_REPORTS,
        VIEW_DASHBOARD,
    },

    # Auditor — read and export only
    "auditor": {
        VIEW_CONSENT_REGISTRY, EXPORT_CONSENT,
        VIEW_AUDIT_LOGS, EXPORT_AUDIT_LOGS,
        VIEW_POLICIES,
        VIEW_REPORTS, EXPORT_REPORTS,
        VIEW_DASHBOARD,
    },

    # Basic user — read-only
    "user": {
        VIEW_CONSENT_REGISTRY,
        VIEW_AUDIT_LOGS,
        VIEW_POLICIES,
        VIEW_DASHBOARD,
    },
}

VALID_ROLES: set[str] = set(ROLE_PERMISSIONS.keys())


def get_permissions(role: str) -> set:
    """Return the full permission set for a role."""
    return ROLE_PERMISSIONS.get(role, set())


def role_has_permission(role: str, permission: str) -> bool:
    """Check whether *role* includes *permission*."""
    return permission in get_permissions(role)
