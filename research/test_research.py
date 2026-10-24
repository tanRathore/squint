import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from aug import degrade, phone_frame, letterbox, recompress
from metrics import auc, eer, ece, report
from calibrate import design, fit


def blob(seed, size=(400, 300)):
    rng = np.random.default_rng(seed)
    a = rng.normal(120, 30, (size[1], size[0], 3)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(a)


def test_phone_frame_box_is_inside_and_media_sized():
    rng = np.random.default_rng(3)
    shot, box = phone_frame(blob(1), rng)
    assert shot.size[0] == box[2] - box[0] or box[0] > 0
    assert 0 <= box[1] < box[3] <= shot.size[1]
    assert box[3] - box[1] > 100


def test_letterbox_centres():
    shot, box = letterbox(blob(2), np.random.default_rng(1))
    assert box[1] > 0 and box[3] < shot.size[1]


def test_degrade_always_returns_rgb_image():
    rng = np.random.default_rng(7)
    for _ in range(20):
        out = degrade(blob(5), rng)
        assert out.mode == "RGB" and out.size[0] > 50


def test_recompress_changes_bytes_not_size():
    img = blob(9)
    out = recompress(img, np.random.default_rng(2))
    assert out.size == img.size


def test_auc_perfect_and_random():
    assert auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert abs(auc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) - 0.5) < 1e-9
    r = report([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0], ["a", "b", "a", "b"])
    assert r["auc"] == 1.0 and set(r["by_source"]) == {"a", "b"}


def test_ece_is_zero_when_calibrated():
    s = [0.1] * 9 + [0.9] * 9
    y = [1] + [0] * 8 + [1] * 8 + [0]
    e, _ = ece(s, y, bins=10)
    assert e < 0.02


def test_eer_returns_threshold():
    r, t = eer([0.9, 0.8, 0.3, 0.1], [1, 1, 0, 0])
    assert r == 0.0 and 0.3 < t <= 0.8


def test_calibrate_ranks_informative_signal_higher():
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(600):
        y = int(rng.random() < 0.5)
        good = np.clip(0.8 if y else 0.2, 0.01, 0.99) + rng.normal(0, 0.08)
        noise = rng.uniform(0.05, 0.95)
        rows.append({"label": y, "signals": [{"name": "good", "score": float(np.clip(good, 0.01, 0.99))}, {"name": "noise", "score": float(noise)}]})
    names = ["good", "noise"]
    X, yv = design(rows, names)
    w, b = fit(X, yv)
    assert w[0] > 3 * max(w[1], 0.01)


def test_crossval_prefers_fitted_weights_when_defaults_are_wrong():
    from calibrate import crossval
    rng = np.random.default_rng(1)
    rows = []
    for _ in range(400):
        y = int(rng.random() < 0.5)
        good = float(np.clip((0.85 if y else 0.15) + rng.normal(0, 0.1), 0.01, 0.99))
        noise = float(rng.uniform(0.05, 0.95))
        rows.append({"label": y, "signals": [{"name": "good", "score": good, "reliability": 0.1}, {"name": "noise", "score": noise, "reliability": 0.9}]})
    folds = crossval(rows, ["good", "noise"], l2=1.0, folds=2)
    assert len(folds) == 2
    for f in folds:
        assert f["fitted"]["acc"] > f["hand_tuned"]["acc"] + 0.1


def test_ocr_noise_keeps_most_of_the_text():
    import random
    sys.path.insert(0, str(Path(__file__).parent / "text"))
    from ocr_noise import noisy
    src = "The committee's report, published late on Tuesday, found that the project had run over budget." * 4
    out = noisy(src, random.Random(0), 0.05)
    assert out != src
    import difflib
    assert difflib.SequenceMatcher(None, src, out).ratio() > 0.75
    assert noisy(src, random.Random(0), 0.0) == src


def test_screen_generator_covers_every_template():
    sys.path.insert(0, str(Path(__file__).parent / "screen"))
    import gen
    gen.set_pool([])
    rng = np.random.default_rng(0)
    seen = set()
    for _ in range(80):
        img, box, cls, name = gen.sample(rng)
        seen.add(name)
        assert img.mode == "RGB"
        if gen.CLASSES[cls] != "none":
            assert 0 <= box[0] < box[2] <= 1.0001 and 0 <= box[1] < box[3] <= 1.0001, (name, box)
    assert {"x", "reddit", "telegram", "news", "grid", "landscape"} <= seen
    img, box, cls, name = gen.sample(rng, exclude=tuple(t.__name__[2:] for t in gen.TEMPLATES if t.__name__ != "t_reddit"))
    assert name == "reddit"
