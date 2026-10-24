import re
from .base import Provider, Signal, register

URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

FALSE_WORDS = ("false", "fake", "altered", "manipulated", "ai-generated", "ai generated", "fabricated", "doctored", "misleading", "pants on fire", "satire", "miscaptioned")


def pick_query(text):
    lines = [l.strip() for l in text.splitlines() if len(l.strip().split()) >= 4]
    lines.sort(key=lambda l: -len(l))
    q = " ".join(lines[:2])[:220]
    q = re.sub(r"[^\w\s'\-]", " ", q)
    return re.sub(r"\s+", " ", q).strip()


@register
class FactCheck(Provider):
    name = "factcheck"
    kinds = {"text", "image", "video"}
    reliability = 0.75

    def ready(self):
        return bool(self.settings.factcheck_key)

    async def check(self, kind, data, text="", client=None):
        q = pick_query(text or "")
        if len(q.split()) < 4:
            return []
        r = await client.get(URL, params={"query": q, "key": self.settings.factcheck_key, "pageSize": 5, "languageCode": "en"})
        r.raise_for_status()
        claims = []
        for cl in r.json().get("claims", []) or []:
            for rev in cl.get("claimReview", []) or []:
                claims.append({
                    "publisher": (rev.get("publisher") or {}).get("name", ""),
                    "rating": rev.get("textualRating", ""),
                    "url": rev.get("url", ""),
                    "claim": cl.get("text", ""),
                })
        if not claims:
            return []
        flagged = [c for c in claims if any(w in c["rating"].lower() for w in FALSE_WORDS)]
        if flagged:
            c = flagged[0]
            return [Signal(self.name, 0.85, self.reliability, f"{c['publisher']} rated a matching claim {c['rating'].lower()}", {"claims": claims})]
        c = claims[0]
        return [Signal(self.name, 0.5, 0.2, f"{c['publisher']} has looked at a similar claim: {c['rating'].lower()}", {"claims": claims})]
