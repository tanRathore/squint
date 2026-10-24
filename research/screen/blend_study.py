import argparse
import glob
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
import gen
from gen import CLASSES
from squint.crop import ScreenModel, heuristic_box, _snap, _iou


def rules(img, nb, kind, conf, hbox, hconf):
    w, h = img.size
    mbox = (int(nb[0] * w), int(nb[1] * h), int(nb[2] * w), int(nb[3] * h))
    g = np.asarray(img.convert("L"), dtype=np.float32)
    agree = _iou(mbox, hbox)
    snapped = _snap(g, mbox, 0.06)
    harea = (hbox[2] - hbox[0]) * (hbox[3] - hbox[1]) / (w * h)
    inside = _iou(hbox, mbox) > 0 and hbox[0] >= mbox[0] - w * 0.05 and hbox[2] <= mbox[2] + w * 0.05 and hbox[1] >= mbox[1] - h * 0.05 and hbox[3] <= mbox[3] + h * 0.05
    return {
        "model": mbox,
        "heuristic": hbox,
        "snap": snapped,
        "shipped (iou>=.8 -> heur, else snap)": hbox if agree >= 0.8 else snapped,
        "iou>=.6 -> heur, else snap": hbox if agree >= 0.6 else snapped,
        "heur if inside model+5% and area>=10%, else shipped": hbox if (inside and harea >= 0.10 and agree >= 0.4) else (hbox if agree >= 0.8 else snapped),
        "low kind conf (<.75) -> heur if agree>=.5, else shipped": hbox if (conf < 0.75 and agree >= 0.5) else (hbox if agree >= 0.8 else snapped),
        "mean of model and heur when agree>=.5, else shipped": tuple(int((a + b) / 2) for a, b in zip(mbox, hbox)) if agree >= 0.5 else (hbox if agree >= 0.8 else snapped),
    }


def main():
    ap = argparse.ArgumentParser(description="try crop blending rules offline on fresh screens")
    ap.add_argument("--model", default="runs/screen_v2/screen.onnx")
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--photos", default="../data/real")
    ap.add_argument("--out", default="runs/screen_v2/blend_study.json")
    args = ap.parse_args()
    pool = [p for p in glob.glob(os.path.join(args.photos, "**", "*.*"), recursive=True) if p.lower().endswith((".jpg", ".jpeg", ".png"))]
    gen.set_pool(pool)
    gen.CANVAS_WIDTHS[:] = [720, 1080, 1170, 1284]
    model = ScreenModel(args.model)
    rng = np.random.default_rng(424242)
    per_rule = {}
    per_tpl = {}
    for i in range(args.n):
        img, nbox, cls, name = gen.sample(rng)
        if CLASSES[cls] == "none":
            continue
        w, h = img.size
        truth = (nbox[0] * w, nbox[1] * h, nbox[2] * w, nbox[3] * h)
        nb, kind, conf = model.predict(img)
        if kind == "none" and conf > 0.6:
            continue
        hbox, hconf = heuristic_box(img)
        for rule, box in rules(img, nb, kind, conf, hbox, hconf).items():
            v = _iou(box, truth)
            per_rule.setdefault(rule, []).append(v)
            per_tpl.setdefault(name, {}).setdefault(rule, []).append(v)
    rep = {"n": len(next(iter(per_rule.values()))), "rules": {}, "by_template": {}}
    for rule, vals in per_rule.items():
        rep["rules"][rule] = {"mean_iou": round(float(np.mean(vals)), 4), "iou75": round(float(np.mean([v >= 0.75 for v in vals])), 4)}
        print(f"{rule:<58} iou {np.mean(vals):.3f}  >=.75 {np.mean([v >= 0.75 for v in vals]):.3f}")
    for t, d in sorted(per_tpl.items()):
        rep["by_template"][t] = {rule: round(float(np.mean(vals)), 3) for rule, vals in d.items()}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2)
    print("telegram:", rep["by_template"].get("telegram"))
    print("chat:", rep["by_template"].get("chat"))


if __name__ == "__main__":
    main()
