import argparse
import glob
import json
import os
import sys
import time
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
import gen
from gen import CLASSES
from squint.crop import ScreenModel, find_media, heuristic_box


def iou(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area = lambda r: max(0, r[2] - r[0]) * max(0, r[3] - r[1])
    u = area(a) + area(b) - inter
    return inter / u if u else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="runs/screen/screen.onnx")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--photos", default="../data/real")
    ap.add_argument("--out", default="runs/screen/eval_report.json")
    args = ap.parse_args()
    pool = [p for p in glob.glob(os.path.join(args.photos, "**", "*.*"), recursive=True) if p.lower().endswith((".jpg", ".jpeg", ".png"))]
    gen.set_pool(pool)
    gen.CANVAS_WIDTHS[:] = [720, 1080, 1170, 1284]
    model = ScreenModel(args.model)
    print("model loaded:", model.ready)
    rng = np.random.default_rng(424242)
    rows = []
    t_model, t_heur = 0.0, 0.0
    for i in range(args.n):
        img, nbox, cls, name = gen.sample(rng)
        w, h = img.size
        truth = (nbox[0] * w, nbox[1] * h, nbox[2] * w, nbox[3] * h)
        t0 = time.perf_counter()
        hb, _ = heuristic_box(img)
        t_heur += time.perf_counter() - t0
        t0 = time.perf_counter()
        mb, conf, kind = find_media(img, None, model)
        t_model += time.perf_counter() - t0
        rows.append({
            "tpl": name, "cls": CLASSES[cls], "pred_kind": kind or "", "none": CLASSES[cls] == "none",
            "iou_model": iou(mb, truth) if CLASSES[cls] != "none" else None,
            "iou_heur": iou(hb, truth) if CLASSES[cls] != "none" else None,
            "kind_ok": (kind == CLASSES[cls]) if kind else None,
        })
    boxed = [r for r in rows if not r["none"]]
    rep = {
        "n": len(rows), "model_ready": model.ready,
        "mean_iou_model": float(np.mean([r["iou_model"] for r in boxed])),
        "mean_iou_heuristic": float(np.mean([r["iou_heur"] for r in boxed])),
        "iou75_model": float(np.mean([r["iou_model"] >= 0.75 for r in boxed])),
        "iou75_heuristic": float(np.mean([r["iou_heur"] >= 0.75 for r in boxed])),
        "kind_acc": float(np.mean([r["kind_ok"] for r in rows if r["kind_ok"] is not None])) if model.ready else None,
        "ms_model": round(1000 * t_model / len(rows), 1), "ms_heuristic": round(1000 * t_heur / len(rows), 1),
        "by_template": {},
    }
    for t in sorted({r["tpl"] for r in rows}):
        sub = [r for r in boxed if r["tpl"] == t]
        allt = [r for r in rows if r["tpl"] == t]
        rep["by_template"][t] = {
            "n": len(allt),
            "iou_model": round(float(np.mean([r["iou_model"] for r in sub])), 3) if sub else None,
            "iou_heuristic": round(float(np.mean([r["iou_heur"] for r in sub])), 3) if sub else None,
            "kind_acc": round(float(np.mean([r["kind_ok"] for r in allt if r["kind_ok"] is not None])), 3) if model.ready else None,
        }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps({k: v for k, v in rep.items() if k != "by_template"}, indent=2))
    for t, r in rep["by_template"].items():
        print(f"  {t:<10} n={r['n']:<4} model {r['iou_model']}  heuristic {r['iou_heuristic']}  kind {r['kind_acc']}")


if __name__ == "__main__":
    main()
