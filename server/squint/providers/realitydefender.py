from .base import Provider, Signal, register

BASE = "https://api.realitydefender.com/api"


@register
class RealityDefender(Provider):
    name = "realitydefender"
    kinds = {"image", "audio", "video"}
    reliability = 0.8

    def ready(self):
        return bool(self.settings.reality_defender_key)

    async def check(self, kind, data, text="", client=None):
        headers = {"X-API-KEY": self.settings.reality_defender_key}
        ext = {"image": "jpg", "video": "mp4", "audio": "wav"}[kind]
        r = await client.post(f"{BASE}/files/aws-presigned", headers=headers, json={"fileName": f"check.{ext}"})
        r.raise_for_status()
        j = r.json()
        put = await client.put(j["response"]["signedUrl"], content=data)
        put.raise_for_status()
        rid = j["requestId"]
        res = await client.get(f"{BASE}/media/users/{rid}", headers=headers)
        res.raise_for_status()
        body = res.json()
        status = (body.get("resultsSummary") or {}).get("status", "")
        score = (body.get("resultsSummary") or {}).get("metadata", {}).get("finalScore")
        if score is None:
            if status.upper() == "MANIPULATED":
                score = 90
            elif status.upper() == "AUTHENTIC":
                score = 10
            else:
                return []
        p = float(score) / 100.0
        return [Signal(self.name, p, self.reliability, f"reality defender says {status.lower() or 'score'} ({p:.0%})", {"status": status})]
