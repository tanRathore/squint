import io
import os
import numpy as np
from PIL import Image
from .base import Provider, Signal, register

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "models", "detector.onnx")


def prep(img, size=224):
    im = img.convert("RGB")
    w, h = im.size
    s = size / min(w, h)
    im = im.resize((max(size, round(w * s)), max(size, round(h * s))))
    w, h = im.size
    l, t = (w - size) // 2, (h - size) // 2
    im = im.crop((l, t, l + size, t + size))
    a = np.asarray(im, dtype=np.float32) / 255.0
    a = (a - MEAN) / STD
    return a.transpose(2, 0, 1)[None]


@register
class LocalModel(Provider):
    name = "squint_model"
    kinds = {"image"}
    reliability = 0.6

    def __init__(self, settings):
        super().__init__(settings)
        self.session = None
        path = settings.local_model or (DEFAULT if os.path.exists(DEFAULT) else "")
        if path and os.path.exists(path):
            try:
                import onnxruntime as ort
                getattr(ort, "disable_telemetry_events", lambda: None)()
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 2
                self.session = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
                self.input = self.session.get_inputs()[0].name
            except Exception:
                self.session = None

    def ready(self):
        return self.session is not None

    async def check(self, kind, data, text="", client=None):
        img = Image.open(io.BytesIO(data))
        x = prep(img)
        out = self.session.run(None, {self.input: x})[0][0]
        if out.shape[-1] == 2:
            e = np.exp(out - out.max())
            p = float(e[1] / e.sum())
        else:
            p = float(1 / (1 + np.exp(-out[0])))
        return [Signal(self.name, p, self.reliability, f"our screenshot model: {p:.0%} synthetic")]
