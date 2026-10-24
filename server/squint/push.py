import json
import logging
import time

log = logging.getLogger("squint.push")

ALERT_TIERS = {"likely_synthetic", "leaning_synthetic"}


class Apns:
    def __init__(self, settings, client):
        self.s = settings
        self.client = client
        self._jwt = None
        self._jwt_at = 0

    def ready(self):
        return bool(self.s.apns_key and self.s.apns_key_id and self.s.apns_team_id and self.s.apns_bundle_id)

    def _token(self):
        if self._jwt and time.time() - self._jwt_at < 2400:
            return self._jwt
        import jwt
        with open(self.s.apns_key) as f:
            key = f.read()
        self._jwt = jwt.encode({"iss": self.s.apns_team_id, "iat": int(time.time())}, key, algorithm="ES256", headers={"kid": self.s.apns_key_id})
        self._jwt_at = time.time()
        return self._jwt

    async def send(self, device_token, title, body, check_id):
        host = "https://api.sandbox.push.apple.com" if self.s.apns_sandbox else "https://api.push.apple.com"
        payload = {
            "aps": {"alert": {"title": title, "body": body}, "sound": "default", "interruption-level": "time-sensitive", "thread-id": "squint-watch"},
            "check_id": check_id,
        }
        headers = {
            "authorization": f"bearer {self._token()}",
            "apns-topic": self.s.apns_bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        r = await self.client.post(f"{host}/3/device/{device_token}", headers=headers, content=json.dumps(payload))
        if r.status_code >= 300:
            log.info("apns said %s: %s", r.status_code, r.text[:200])
        return r.status_code < 300


async def maybe_alert(app, device, verdict):
    if verdict.tier not in ALERT_TIERS:
        return
    apns = app.state.apns
    if not apns or not apns.ready():
        return
    token = app.state.index.push_token(device)
    if not token:
        return
    try:
        await apns.send(token, verdict.headline, verdict.say, verdict.check_id)
    except Exception as e:
        log.info("push failed: %s", e)
