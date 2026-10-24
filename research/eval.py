import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from data import list_pairs
from metrics import report
from train import split_by_source


async def run(root, settings_overrides, degrade_first, split="val", limit=0, dump=None):
    from squint.config import Settings
    from squint.index import Index_
    from squint.pipeline import Pipeline
    from aug import degrade
    import numpy as np
    import io
    from PIL import Image

    st = Settings(db_url="sqlite:///:memory:", **settings_overrides)
    pipe = Pipeline(st, Index_(st.db_url))
    pairs = list_pairs(root)
    if split in ("train", "val"):
        tr, va = split_by_source(pairs)
        pairs = va if split == "val" else tr
    rng = np.random.default_rng(0)
    if limit and len(pairs) > limit:
        pairs = [pairs[i] for i in rng.choice(len(pairs), limit, replace=False)]
    print(f"{len(pairs)} images ({split})")
    scores, labels, groups, tiers = [], [], [], []
    sink = open(dump, "w") if dump else None
    for i, (path, label, source) in enumerate(pairs):
        data = Path(path).read_bytes()
        trigger = "share"
        if degrade_first:
            img = degrade(Image.open(io.BytesIO(data)), rng)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=90)
            data = buf.getvalue()
            trigger = "screenshot"
        v = await pipe.check(data, Path(path).name, "", source, trigger, "eval")
        scores.append(v.p)
        labels.append(label)
        groups.append(source)
        tiers.append(v.tier)
        if sink:
            sink.write(json.dumps({"path": path, "source": source, "label": label, "p": v.p, "tier": v.tier, "signals": [sg.model_dump() for sg in v.signals]}) + "\n")
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(pairs)}")
    if sink:
        sink.close()
    await pipe.aclose()
    rep = report(scores, labels, groups)
    rep["tiers"] = {t: tiers.count(t) for t in set(tiers)}
    rep["unclear_rate"] = tiers.count("unclear") / max(1, len(tiers))
    return rep


def main():
    ap = argparse.ArgumentParser(description="run the full squint pipeline over a labelled folder and score it")
    ap.add_argument("--data", default="data")
    ap.add_argument("--degrade", action="store_true", help="push every image through the screenshot simulator first")
    ap.add_argument("--model", default="", help="onnx model to plug in as the local provider")
    ap.add_argument("--out", default="eval_report.json")
    ap.add_argument("--split", default="val", choices=["val", "train", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dump", default="", help="write one json line per image with its signals, for calibrate.py")
    ap.add_argument("--weights", default="", help="fusion weights file to evaluate with")
    args = ap.parse_args()
    overrides = {"local_model": args.model} if args.model else {}
    if args.weights:
        overrides["weights_file"] = args.weights
    rep = asyncio.run(run(args.data, overrides, args.degrade, args.split, args.limit, args.dump or None))
    with open(args.out, "w") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("calibration", "by_source")}, indent=2))
    for src, r in rep.get("by_source", {}).items():
        print(f"  {src:<20} n={r['n']:<5} auc={r['auc']:.3f} acc={r['acc']:.3f}")


if __name__ == "__main__":
    main()
