import os
import sys
import pytest
import numpy as np
from squint.crop import ScreenModel, find_media, DEFAULT_MODEL

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "research", "screen"))

pytestmark = pytest.mark.skipif(not os.path.exists(DEFAULT_MODEL), reason="screen model not bundled")


def iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])
    return inter / (area(a) + area(b) - inter)


def test_model_loads():
    m = ScreenModel()
    assert m.ready


def test_model_finds_media_in_generated_feed_and_chat():
    import gen
    m = ScreenModel()
    rng = np.random.default_rng(7)
    good = 0
    kinds_ok = 0
    n = 12
    for i in range(n):
        tpl = gen.t_feed if i % 2 == 0 else gen.t_chat
        img, box, cls = tpl(rng)
        w, h = img.size
        pred, conf, kind = find_media(img, None, m)
        if iou(pred, box) >= 0.6:
            good += 1
        if kind == cls:
            kinds_ok += 1
    assert good >= n * 0.7
    assert kinds_ok >= n * 0.6


def test_model_says_none_on_settings_screen():
    import gen
    m = ScreenModel()
    rng = np.random.default_rng(9)
    hits = 0
    for _ in range(6):
        img, _, _ = gen.t_none(rng)
        _, _, kind = find_media(img, None, m)
        hits += int(kind == "none")
    assert hits >= 3
