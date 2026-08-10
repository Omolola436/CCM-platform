"""
PolicySyncService — fetches policy URLs, detects changes, and auto-creates
new PolicyVersion records when the content changes.

Algorithm
---------
1. Fetch the URL (10-second timeout, 5 MB limit, headers spoofed to avoid bot blocks).
2. Strip HTML tags using stdlib html.parser (no extra dependency).
3. Normalise whitespace so minor formatting tweaks don't trigger false positives.
4. SHA-256 hash the normalised text.
5. Compare with the stored hash:
   - Same  → update last_checked_at, clear error.
   - Diff  → create a new PolicyVersion, update hash + last_changed_at.
6. Any HTTP / network error → store in last_error, do NOT overwrite hash.
"""
import hashlib
import re
import textwrap
from datetime import datetime, timezone
from html.parser import HTMLParser

import requests

from models import db, PolicyVersion
from models.policy_source import PolicySource
from services.audit_service import AuditService


# ── HTML stripping ────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "head", "meta", "link"}

    def __init__(self):
        super().__init__()
        self._skip  = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def text(self) -> str:
        return " ".join(self._parts)


def _strip_html(raw: str) -> str:
    p = _TextExtractor()
    p.feed(raw)
    return p.text()


def _normalise(text: str) -> str:
    """Collapse whitespace and lower-case so minor formatting changes are ignored."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


# ── Fetch ─────────────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CCMP-PolicyBot/1.0; +https://ccmp.3consulting.com)"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}
_TIMEOUT  = 10   # seconds
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _fetch(url: str) -> str:
    """Fetch *url* and return normalised plain text. Raises on error."""
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, stream=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    chunks = []
    total  = 0
    for chunk in resp.iter_content(chunk_size=65536, decode_unicode=False):
        total += len(chunk)
        if total > _MAX_BYTES:
            raise ValueError(f"Response exceeds {_MAX_BYTES // 1024} KB limit")
        chunks.append(chunk)

    raw = b"".join(chunks).decode("utf-8", errors="replace")

    if "html" in content_type.lower():
        raw = _strip_html(raw)

    return _normalise(raw)


# ── Core service ──────────────────────────────────────────────────────────────

class PolicySyncService:

    @staticmethod
    def sync_source(source: PolicySource) -> dict:
        """
        Fetch *source.url*, compare with stored hash, and create a new
        PolicyVersion when the content has changed.

        Returns a result dict with keys: changed (bool), error (str|None).
        """
        now = datetime.now(timezone.utc)
        try:
            text = _fetch(source.url)
        except Exception as exc:
            source.last_error     = str(exc)[:500]
            source.last_checked_at = now
            db.session.flush()
            return {"changed": False, "error": source.last_error}

        new_hash = _hash(text)
        source.last_checked_at = now
        source.last_error      = None  # clear previous error

        if source.content_hash == new_hash:
            # No change
            db.session.flush()
            return {"changed": False, "error": None}

        # ── Content changed — create a new PolicyVersion ──────────────────
        source.content_hash   = new_hash
        source.last_changed_at = now

        # Auto-generate version string, e.g. "auto-2026-08-05-v3"
        date_str = now.strftime("%Y-%m-%d")
        existing = (
            PolicyVersion.query
            .filter_by(org_id=source.org_id)
            .filter(PolicyVersion.version.like(f"auto-{date_str}-%"))
            .count()
        )
        version_str = f"auto-{date_str}-v{existing + 1}"

        if source.auto_set_current:
            PolicyVersion.query.filter_by(org_id=source.org_id).update({"is_current": False})

        # Truncate content to 50 000 chars for the DB field
        stored_content = textwrap.shorten(text, width=50_000, placeholder=" …[truncated]")

        pv = PolicyVersion(
            version      = version_str,
            title        = f"Auto-synced from {source.name} ({date_str})",
            content      = stored_content,
            summary      = (
                f"Automatically detected policy change at {source.url}. "
                f"Synced on {now.strftime('%d %b %Y %H:%M UTC')}."
            ),
            is_current   = source.auto_set_current,
            org_id       = source.org_id,
            source_id    = source.id,
            source_url   = source.url,
        )
        db.session.add(pv)
        db.session.flush()

        AuditService.log(
            action       = "Policy Auto-Synced",
            entity_type  = "PolicyVersion",
            entity_id    = pv.id,
            details      = (
                f"New version '{version_str}' created from '{source.url}'. "
                f"Auto-set current: {source.auto_set_current}."
            ),
            org_id       = source.org_id,
        )
        db.session.commit()
        return {"changed": True, "error": None, "version": version_str}

    @staticmethod
    def check_all_sources(app) -> None:
        """
        Background job — called by the APScheduler every N minutes.
        Runs each active source through sync_source().
        """
        with app.app_context():
            now = datetime.now(timezone.utc)
            sources = PolicySource.query.filter_by(is_active=True).all()
            for source in sources:
                if (
                    source.last_checked_at
                    and (now - source.last_checked_at).total_seconds()
                    < max(source.check_interval_min or 60, 5) * 60
                ):
                    continue
                try:
                    PolicySyncService.sync_source(source)
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    app.logger.error(
                        f"Policy sync error for source {source.id} ({source.url}): {exc}"
                    )
