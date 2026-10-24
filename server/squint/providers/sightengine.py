from .base import Provider, Signal, register

URL = "https://api.sightengine.com/1.0/check.json"


@register
class Sightengine(Provider):
    name = "sightengine"
    kinds = {"image"}
    reliability = 0.7

    def ready(self):
        return bool(self.settings.sightengine_user and self.settings.sightengine_secret)

    async def check(self, kind, data, text="", client=None):
        r = await client.post(
            URL,
            data={"models": "genai,deepfake", "api_user": self.settings.sightengine_user, "api_secret": self.settings.sightengine_secret},
            files={"media": ("check.jpg", data)},
        )
        r.raise_for_status()
        j = r.json()
        out = []
        gen = (j.get("type") or {}).get("ai_generated")
        if gen is not None:
            out.append(Signal(self.name, float(gen), self.reliability, f"sightengine genai {gen:.0%}", {"type": j.get("type")}))
        df = (j.get("type") or {}).get("deepfake")
        if df is not None and df > 0.5:
            out.append(Signal("sightengine_deepfake", float(df), 0.6, f"face swap signal {df:.0%}"))
        return out
