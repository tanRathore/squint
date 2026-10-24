import os
from .base import Provider, Signal, register

DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "models", "text.joblib")


@register
class TextModel(Provider):
    name = "squint_text"
    kinds = {"text"}
    reliability = 0.5

    def __init__(self, settings):
        super().__init__(settings)
        self.model = None
        path = getattr(settings, "text_model", "") or (DEFAULT if os.path.exists(DEFAULT) else "")
        if path and os.path.exists(path):
            try:
                import joblib
                self.model = joblib.load(path)
            except Exception:
                self.model = None

    def ready(self):
        return self.model is not None

    async def check(self, kind, data, text="", client=None):
        words = text.split()
        if len(words) < 25:
            return []
        p = float(self.model.predict_proba([text[:6000]])[0][1])
        rel = 0.5 if len(words) >= 120 else (0.38 if len(words) >= 60 else 0.25)
        return [Signal(self.name, p, rel, f"our text model: {p:.0%} machine written over {len(words)} words")]
