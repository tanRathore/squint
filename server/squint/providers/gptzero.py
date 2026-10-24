from .base import Provider, Signal, register

URL = "https://api.gptzero.me/v2/predict/text"


@register
class GptZero(Provider):
    name = "gptzero"
    kinds = {"text"}
    reliability = 0.45

    def ready(self):
        return bool(self.settings.gptzero_key)

    async def check(self, kind, data, text="", client=None):
        words = text.split()
        if len(words) < 40:
            return []
        r = await client.post(URL, headers={"x-api-key": self.settings.gptzero_key, "Content-Type": "application/json"}, json={"document": text[:50000], "multilingual": False})
        r.raise_for_status()
        doc = (r.json().get("documents") or [{}])[0]
        probs = doc.get("class_probabilities") or {}
        p = probs.get("ai")
        if p is None:
            p = doc.get("completely_generated_prob")
        if p is None:
            return []
        rel = self.reliability if len(words) > 150 else 0.3
        return [Signal(self.name, float(p), rel, f"text detector {p:.0%} machine written over {len(words)} words", {"class": doc.get("predicted_class")})]
