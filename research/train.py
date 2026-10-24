import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
import numpy as np

from data import ScreenshotDataset, list_pairs, torch_loader
from metrics import report

WEIGHTS = {
    "efficientnet_b0": "https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-weights/efficientnet_b0_ra-3dd342df.pth",
    "mobilenetv3_large_100": "https://github.com/rwightman/pytorch-image-models/releases/download/v0.1-weights/mobilenetv3_large_100_ra-f55367f5.pth",
}


def split_by_source(pairs, val_frac=0.15, seed=0):
    rng = np.random.default_rng(seed)
    by = {}
    for p in pairs:
        by.setdefault((p[1], p[2]), []).append(p)
    train, val = [], []
    for key, rows in by.items():
        rows = list(rows)
        rng.shuffle(rows)
        n = max(1, int(len(rows) * val_frac)) if len(rows) >= 4 else 0
        val.extend(rows[:n])
        train.extend(rows[n:])
    return train, val


def fetch_weights(arch, cache="runs/weights"):
    url = WEIGHTS.get(arch)
    if not url:
        return None
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, url.rsplit("/", 1)[-1])
    if not os.path.exists(path):
        print(f"fetching {arch} weights")
        urllib.request.urlretrieve(url, path)
    return path


def smoke_dataset(root, n=24):
    from PIL import Image, ImageDraw
    rng = np.random.default_rng(0)
    for label in ("real", "synthetic"):
        d = Path(root) / label / "smoke"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            a = rng.normal(128, 40 if label == "real" else 12, (320, 320, 3)).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(a)
            dr = ImageDraw.Draw(img)
            for _ in range(4):
                x, y = rng.integers(0, 260, 2)
                dr.ellipse([x, y, x + 60, y + 60], fill=tuple(int(c) for c in rng.integers(0, 255, 3)))
            img.save(d / f"{i}.png")


def export_onnx(model, path, size=224):
    import torch
    model.eval()
    dummy = torch.randn(1, 3, size, size, device=next(model.parameters()).device)
    kwargs = {"input_names": ["input"], "output_names": ["logits"], "dynamic_axes": {"input": {0: "batch"}, "logits": {0: "batch"}}}
    try:
        torch.onnx.export(model, dummy, path, dynamo=True, external_data=False, **kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, path, opset_version=17, **kwargs)
    print(f"onnx written to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--arch", default="efficientnet_b0")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--out", default="runs/latest")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--holdout", default="", help="comma separated source folders kept out of training and scored separately")
    ap.add_argument("--init", default="", help="start from this state dict instead of the imagenet backbone")
    args = ap.parse_args()

    import torch
    import timm
    torch.set_num_threads(args.threads)
    torch.manual_seed(0)

    if args.smoke:
        args.data = os.path.join(args.out, "smoke_data")
        smoke_dataset(args.data)
        args.epochs = 1
        args.batch = 8
        args.workers = 0

    pairs = list_pairs(args.data)
    if not pairs:
        print(f"no images under {args.data}/real and {args.data}/synthetic")
        return
    holdout = {h for h in args.holdout.split(",") if h}
    held_pairs = [p for p in pairs if p[2] in holdout]
    pairs = [p for p in pairs if p[2] not in holdout]
    train_pairs, val_pairs = split_by_source(pairs)
    n_syn = sum(1 for p in train_pairs if p[1] == 1)
    n_real = len(train_pairs) - n_syn
    print(f"{len(train_pairs)} train ({n_real} real / {n_syn} synthetic), {len(val_pairs)} val, {len({p[2] for p in pairs})} sources")
    if held_pairs:
        print(f"{len(held_pairs)} images from {sorted(holdout)} never seen in training")

    tr_ds = ScreenshotDataset(train_pairs, args.size, train=True)
    weights = torch.tensor([1.0 / n_real if p[1] == 0 else 1.0 / max(1, n_syn) for p in train_pairs], dtype=torch.double)
    sampler = torch.utils.data.WeightedRandomSampler(weights, num_samples=len(train_pairs), replacement=True)
    tr = torch_loader(tr_ds, args.batch, False, args.workers, sampler=sampler)
    va = torch_loader(ScreenshotDataset(val_pairs, args.size, train=False), args.batch, False, args.workers)
    held = torch_loader(ScreenshotDataset(held_pairs + [p for p in val_pairs if p[1] == 0], args.size, train=False), args.batch, False, args.workers) if held_pairs else None

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = timm.create_model(args.arch, pretrained=False, num_classes=2)
    if args.init:
        model.load_state_dict(torch.load(args.init, map_location="cpu"))
        print(f"warm start from {args.init}")
    elif not args.smoke:
        wpath = fetch_weights(args.arch)
        if wpath:
            sd = torch.load(wpath, map_location="cpu")
            sd = {k: v for k, v in sd.items() if not k.startswith(("classifier", "fc", "head"))}
            missing, unexpected = model.load_state_dict(sd, strict=False)
            print(f"loaded pretrained backbone, {len(missing)} head params fresh")
    model = model.to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.02)
    steps = max(1, args.epochs * len(tr))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps, pct_start=0.15)
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=0.05)

    os.makedirs(args.out, exist_ok=True)
    best = -1
    for ep in range(args.epochs):
        model.train()
        t0 = time.time()
        seen, running = 0, 0.0
        for x, y, _ in tr:
            x, y = x.to(dev), torch.as_tensor(y).to(dev)
            loss = loss_fn(model(x), y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            running += loss.item() * len(y)
            seen += len(y)
        model.eval()
        scores, labels, groups = [], [], []
        with torch.no_grad():
            for x, y, s in va:
                p = torch.softmax(model(x.to(dev)), dim=1)[:, 1].cpu().numpy()
                scores.extend(p.tolist())
                labels.extend([int(v) for v in y])
                groups.extend(s)
        rep = report(scores, labels, groups) if scores else {"auc": float("nan")}
        line = f"epoch {ep + 1}: loss {running / max(1, seen):.4f}  val auc {rep['auc']:.3f}  acc {rep.get('acc@0.5', float('nan')):.3f}  eer {rep.get('eer', float('nan')):.3f}"
        if held is not None:
            hs, hl, hg = [], [], []
            with torch.no_grad():
                for x, y, g in held:
                    hs.extend(torch.softmax(model(x.to(dev)), dim=1)[:, 1].cpu().numpy().tolist())
                    hl.extend(int(v) for v in y)
                    hg.extend(g)
            hrep = report(hs, hl, hg)
            pos = [sc for sc, lb in zip(hs, hl) if lb == 1]
            hrep["recall@0.5"] = float(np.mean([sc >= 0.5 for sc in pos])) if pos else float("nan")
            rep["held_out"] = {"sources": sorted(holdout), "n_synthetic": len(pos), "auc": hrep["auc"], "recall@0.5": hrep["recall@0.5"], "by_source": hrep.get("by_source", {})}
            line += f"  | unseen generators: auc {hrep['auc']:.3f} recall@0.5 {hrep['recall@0.5']:.3f}"
        print(line + f"  ({time.time() - t0:.0f}s)")
        sys.stdout.flush()
        score = rep["auc"] if rep["auc"] == rep["auc"] else 0
        if score >= best:
            best = score
            torch.save(model.state_dict(), os.path.join(args.out, "best.pt"))
            with open(os.path.join(args.out, "val_report.json"), "w") as f:
                json.dump(rep, f, indent=2)

    model.load_state_dict(torch.load(os.path.join(args.out, "best.pt"), map_location=dev))
    export_onnx(model, os.path.join(args.out, "squint.onnx"), args.size)
    print("done. copy squint.onnx to android/app/src/main/assets/ or point SQUINT_LOCAL_MODEL at it")


if __name__ == "__main__":
    main()
