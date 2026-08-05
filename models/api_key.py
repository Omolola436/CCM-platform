"""
APIKey model — stores hashed API keys for machine-to-machine access.

The raw key is generated once (and shown once) by `APIKey.generate()`.
Only the SHA-256 hash is persisted; the raw key is never stored.
"""
import secrets
import hashlib
from .base import db
from datetime import datetime, timezone

# Scopes available for API keys
API_KEY_SCOPES = [
    "consents:read",
    "consents:write",
    "consents:withdraw",
    "subjects:read",
    "audit:read",
    "sync:write",
]


class APIKey(db.Model):
    __tablename__ = "api_keys"

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    # SHA-256 hex digest of the raw key — never store the raw key
    key_hash     = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # First 12 chars of the raw key for display ("ccmp_XXXXXXXX…")
    key_prefix   = db.Column(db.String(16), nullable=False)
    scopes       = db.Column(db.JSON, nullable=False, default=list)
    org_id       = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active    = db.Column(db.Boolean, default=True, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at   = db.Column(db.DateTime(timezone=True), nullable=True)
    request_count = db.Column(db.Integer, default=0, nullable=False)
    created_at   = db.Column(db.DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc))

    # ── Class helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def generate() -> str:
        """Return a new raw API key (call once; never store the return value)."""
        return "ccmp_" + secrets.token_urlsafe(32)

    @staticmethod
    def hash_key(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def lookup(cls, raw: str) -> "APIKey | None":
        """Find an APIKey by its raw value, or return None."""
        return cls.query.filter_by(key_hash=cls.hash_key(raw)).first()

    # ── Instance helpers ──────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    def record_use(self):
        self.last_used_at = datetime.now(timezone.utc)
        self.request_count = (self.request_count or 0) + 1

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "name":          self.name,
            "key_prefix":    self.key_prefix,
            "scopes":        self.scopes,
            "is_active":     self.is_active,
            "is_expired":    self.is_expired,
            "last_used_at":  self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at":    self.expires_at.isoformat()   if self.expires_at   else None,
            "request_count": self.request_count,
            "created_at":    self.created_at.isoformat()   if self.created_at   else None,
        }
