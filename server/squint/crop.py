import os
import numpy as np
from PIL import Image

KINDS = ["photo", "video", "text", "none"]
MODEL_W, MODEL_H = 160, 320
DEFAULT_MODEL = os.path.join(os.path.dirname(__file__), "..", "models", "screen.onnx")


class ScreenModel:
    def __init__(self, path=""):
        self.session = None
        path = path or (DEFAULT_MODEL if os.path.exists(DEFAULT_MODEL) else "")
        if not path or not os.path.exists(path):
            return
        try:
            import onnxruntime as ort
            getattr(ort, "disable_telemetry_events", lambda: None)()
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            self.session = ort.InferenceSession(path, opts, providers=["CPUExecutionProvider"])
            self.input = self.session.get_inputs()[0].name
            self.path = path
        except Exception:
            self.session = None

    @property
    def ready(self):
        return self.session is not None

    def predict(self, img):
        small = img.convert("RGB").resize((MODEL_W, MODEL_H), Image.BILINEAR)
        x = (np.asarray(small, dtype=np.float32) / 255.0).transpose(2, 0, 1)[None]
        box, logits = self.session.run(None, {self.input: x})
        e = np.exp(logits[0] - logits[0].max())
        probs = e / e.sum()
        k = int(probs.argmax())
        return box[0].tolist(), KINDS[k], float(probs[k])


def _runs(mask, gap):
    runs = []
    start = None
    quiet = 0
    for i, on in enumerate(mask):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet > gap:
                runs.append((start, i - quiet + 1))
                start = None
                quiet = 0
    if start is not None:
        runs.append((start, len(mask) - quiet))
    return runs


def _busy(axis_std, axis_edge):
    return (axis_std > 7) | (axis_edge > 2.5)


def heuristic_box(img):
    w, h = img.size
    g = np.asarray(img.convert("L"), dtype=np.float32)
    gap = max(4, h // 160)
    rows = _busy(g.std(axis=1), np.abs(np.diff(g, axis=1)).mean(axis=1))
    runs = _runs(rows, gap)
    if not runs:
        return (0, 0, w, h), 0.2
    top, bottom = max(runs, key=lambda r: r[1] - r[0])
    if bottom - top < h * 0.08:
        return (0, 0, w, h), 0.2
    band = g[top:bottom]
    cols = _busy(band.std(axis=0), np.abs(np.diff(band, axis=0)).mean(axis=0))
    cruns = _runs(cols, gap)
    if cruns:
        left, right = max(cruns, key=lambda r: r[1] - r[0])
    else:
        left, right = 0, w
    if right - left < w * 0.3:
        left, right = 0, w
    pad = max(2, h // 300)
    box = (max(0, left - pad), max(0, top - pad), min(w, right + pad), min(h, bottom + pad))
    area = (box[2] - box[0]) * (box[3] - box[1]) / float(w * h)
    return box, round(0.5 + 0.4 * min(1.0, area / 0.4), 2)


def _snap(g, box, margin):
    w = g.shape[1]
    h = g.shape[0]
    x0, y0, x1, y1 = box
    rows = _busy(g.std(axis=1), np.abs(np.diff(g, axis=1)).mean(axis=1))
    cols = _busy(g.std(axis=0), np.abs(np.diff(g, axis=0)).mean(axis=0))

    def edge(mask, pos, lo, hi, want_start):
        lo, hi = max(0, lo), min(len(mask) - 1, hi)
        best = pos
        for i in range(lo, hi):
            if want_start and mask[i] and not mask[max(0, i - 1)]:
                if abs(i - pos) < abs(best - pos):
                    best = i
            if not want_start and mask[i] and not mask[min(len(mask) - 1, i + 1)]:
                if abs(i + 1 - pos) < abs(best - pos):
                    best = i + 1
        return best

    my, mx = int(h * margin), int(w * margin)
    ny0 = edge(rows, y0, y0 - my, y0 + my, True)
    ny1 = edge(rows, y1, y1 - my, y1 + my, False)
    nx0 = edge(cols, x0, x0 - mx, x0 + mx, True)
    nx1 = edge(cols, x1, x1 - mx, x1 + mx, False)
    if ny1 - ny0 < h * 0.05 or nx1 - nx0 < w * 0.2:
        return box
    return (nx0, ny0, nx1, ny1)


def find_media(img, hint=None, model=None):
    w, h = img.size
    if hint:
        x0, y0, x1, y1 = hint
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(w, int(x1)), min(h, int(y1))
        if x1 - x0 > 32 and y1 - y0 > 32:
            return (x0, y0, x1, y1), 0.95, None
    if model is not None and model.ready:
        try:
            nb, kind, conf = model.predict(img)
            if kind == "none" and conf > 0.6:
                return (0, 0, w, h), round(conf, 2), "none"
            box = (int(nb[0] * w), int(nb[1] * h), int(nb[2] * w), int(nb[3] * h))
            if box[2] - box[0] > 32 and box[3] - box[1] > 32:
                hbox, hconf = heuristic_box(img)
                if _iou(box, hbox) >= 0.8:
                    box = hbox
                    conf = max(conf, hconf)
                else:
                    g = np.asarray(img.convert("L"), dtype=np.float32)
                    box = _snap(g, box, 0.06)
                return box, round(conf, 2), kind if conf >= 0.75 else None
        except Exception:
            pass
    box, conf = heuristic_box(img)
    return box, conf, None


def _iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])
    u = area(a) + area(b) - inter
    return inter / u if u else 0.0


def region_kind(img):
    small = img.convert("RGB").copy()
    small.thumbnail((160, 160))
    a = np.asarray(small).astype(np.int16)
    q = (a // 32).reshape(-1, 3)
    colours = len(np.unique(q, axis=0))
    gray = a.mean(axis=2)
    extreme = ((gray > 235) | (gray < 20)).mean()
    sat = (a.max(axis=2) - a.min(axis=2)).mean()
    if colours < 40 and extreme > 0.45:
        return "text"
    if colours < 60 and sat < 12:
        return "text"
    return "photo"


def strip_bars(img):
    box, _, _ = find_media(img)
    return img.crop(box)
