import hmac
import hashlib
import json
import requests as http_requests
from models import db, Webhook
from datetime import datetime, timezone


class WebhookService:

    @staticmethod
    def trigger(event, payload, org_id):
        webhooks = Webhook.query.filter_by(org_id=org_id, status="active").all()
        for wh in webhooks:
            events = wh.events or []
            if event in events or "*" in events:
                WebhookService._dispatch(wh, event, payload)

    @staticmethod
    def _dispatch(webhook, event, payload):
        body = json.dumps({"event": event, "data": payload,
                           "timestamp": datetime.now(timezone.utc).isoformat()})
        headers = {"Content-Type": "application/json", "X-CCMP-Event": event}
        if webhook.secret:
            sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers["X-CCMP-Signature"] = f"sha256={sig}"
        try:
            resp = http_requests.post(webhook.url, data=body, headers=headers, timeout=10)
            webhook.last_response_code = resp.status_code
        except Exception as e:
            webhook.last_response_code = 0
        webhook.last_triggered = datetime.now(timezone.utc)
        webhook.trigger_count = (webhook.trigger_count or 0) + 1
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
