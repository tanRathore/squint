import argparse
import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from gen import CLASSES

W, H = 160, 320


def build_model():
    import torch
    import torch.nn as nn

    def block(cin, cout, stride):
        return nn.Sequential(nn.Conv2d(cin, cout, 3, stride, 1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))

    class ScreenNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = block(3, 16, 2)
            self.body = nn.Sequential(
                block(16, 32, 2), block(32, 48, 1), block(48, 64, 2), block(64, 96, 1), block(96, 128, 2), block(128, 160, 2),
            )
            self.coord_h = nn.Parameter(torch.linspace(-1, 1, H // 32).view(1, 1, -1, 1), requires_grad=False)
            self.coord_w = nn.Parameter(torch.linspace(-1, 1, W // 32).view(1, 1, 1, -1), requires_grad=False)
            self.reduce = nn.Sequential(nn.Conv2d(162, 64, 1, bias=False), nn.BatchNorm2d(64), nn.ReLU(inplace=True))
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(64 * (H // 32) * (W // 32), 256), nn.ReLU(inplace=True), nn.Dropout(0.2))
            self.box = nn.Linear(256, 4)
            self.cls = nn.Linear(256, len(CLASSES))

        def forward(self, x):
            f = self.body(self.stem(x))
            b = f.shape[0]
            f = torch.cat([f, self.coord_h.expand(b, 1, -1, f.shape[3]), self.coord_w.expand(b, 1, f.shape[2], -1)], dim=1)
            f = self.head(self.reduce(f))
            return torch.sigmoid(self.box(f)), self.cls(f)

    return ScreenNet()


def giou(a, b):
    import torch
    ax0, ay0, ax1, ay1 = a.unbind(-1)
    bx0, by0, bx1, by1 = b.unbind(-1)
    ix0, iy0 = torch.max(ax0, bx0), torch.max(ay0, by0)
    ix1, iy1 = torch.min(ax1, bx1), torch.min(ay1, by1)
    inter = (ix1 - ix0).clamp(min=0) * (iy1 - iy0).clamp(min=0)
    area_a = (ax1 - ax0).clamp(min=0) * (ay1 - ay0).clamp(min=0)
    area_b = (bx1 - bx0).clamp(min=0) * (by1 - by0).clamp(min=0)
    union = area_a + area_b - inter + 1e-6
    iou = inter / union
    cx0, cy0 = torch.min(ax0, bx0), torch.min(ay0, by0)
    cx1, cy1 = torch.max(ax1, bx1), torch.max(ay1, by1)
    hull = (cx1 - cx0) * (cy1 - cy0) + 1e-6
    return iou - (hull - union) / hull, iou


class Data:
    def __init__(self, prefix, train, exclude=()):
        self.x = np.load(prefix + "_x.npy", mmap_mode="r")
        self.box = np.load(prefix + "_box.npy")
        self.cls = np.load(prefix + "_cls.npy")
        with open(prefix + "_tpl.txt") as f:
            self.tpl = f.read().split("\n")
        self.keep = np.array([i for i, t in enumerate(self.tpl) if t not in exclude])
        self.train = train
        self.rng = np.random.default_rng(0)

    def __len__(self):
        return len(self.keep)

    def batch(self, idx):
        import torch
        idx = self.keep[idx]
        x = np.asarray(self.x[idx], dtype=np.float32) / 255.0
        box = self.box[idx].copy()
        if self.train:
            gain = self.rng.uniform(0.75, 1.25, (len(idx), 1, 1, 1)).astype(np.float32)
            bias = self.rng.uniform(-0.1, 0.1, (len(idx), 1, 1, 1)).astype(np.float32)
            x = np.clip(x * gain + bias, 0, 1)
            if self.rng.random() < 0.3:
                x = x[..., ::-1].copy()
                box = box[:, [2, 1, 0, 3]].copy()
                box[:, 0] = 1 - box[:, 0]
                box[:, 2] = 1 - box[:, 2]
                flip_mask = self.cls[idx] == CLASSES.index("none")
                box[flip_mask] = 0
        x = torch.from_numpy(np.ascontiguousarray(x.transpose(0, 3, 1, 2)))
        return x, torch.from_numpy(box), torch.from_numpy(self.cls[idx])


def evaluate(model, data, bs=64):
    import torch
    model.eval()
    ious, ok, per_tpl = [], [], {}
    none_idx = CLASSES.index("none")
    with torch.no_grad():
        for s in range(0, len(data), bs):
            idx = np.arange(s, min(len(data), s + bs))
            x, box, cls = data.batch(idx)
            pb, pc = model(x)
            pred_cls = pc.argmax(1)
            _, iou = giou(pb, box)
            for i, j in enumerate(data.keep[idx]):
                t = data.tpl[j]
                d = per_tpl.setdefault(t, {"n": 0, "iou": 0.0, "cls_ok": 0, "iou75": 0})
                d["n"] += 1
                d["cls_ok"] += int(pred_cls[i].item() == cls[i].item())
                if cls[i].item() != none_idx:
                    v = float(iou[i].item())
                    d["iou"] += v
                    d["iou75"] += int(v >= 0.75)
                    ious.append(v)
                ok.append(int(pred_cls[i].item() == cls[i].item()))
    out = {"n": len(data), "mean_iou": float(np.mean(ious)) if ious else 0.0, "iou75": float(np.mean([v >= 0.75 for v in ious])) if ious else 0.0, "cls_acc": float(np.mean(ok))}
    out["by_template"] = {t: {"n": d["n"], "mean_iou": round(d["iou"] / max(1, sum(1 for j in data.keep if data.tpl[j] == t and data.cls[j] != none_idx)), 3), "iou75": round(d["iou75"] / max(1, sum(1 for j in data.keep if data.tpl[j] == t and data.cls[j] != none_idx)), 3), "cls_acc": round(d["cls_ok"] / d["n"], 3)} for t, d in sorted(per_tpl.items())}
    model.train()
    return out


def export_onnx(model, path):
    import torch
    model.eval()
    dummy = torch.zeros(1, 3, H, W)
    try:
        torch.onnx.export(model, dummy, path, input_names=["input"], output_names=["box", "cls"], dynamic_axes={"input": {0: "batch"}, "box": {0: "batch"}, "cls": {0: "batch"}}, dynamo=True, external_data=False)
    except TypeError:
        torch.onnx.export(model, dummy, path, input_names=["input"], output_names=["box", "cls"], dynamic_axes={"input": {0: "batch"}, "box": {0: "batch"}, "cls": {0: "batch"}}, opset_version=17)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/screen_data")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--out", default="runs/screen")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--exclude", default="", help="comma separated template names to leave out of training")
    args = ap.parse_args()

    import torch
    torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    exclude = tuple(t for t in args.exclude.split(",") if t)
    train, val = Data(os.path.join(args.data, "train"), True, exclude), Data(os.path.join(args.data, "val"), False)
    print(f"{len(train)} train, {len(val)} val" + (f", holding out {', '.join(exclude)}" if exclude else ""))
    model = build_model()
    print(f"{sum(p.numel() for p in model.parameters()) / 1e6:.2f}M params")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * (len(train) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps, pct_start=0.15)
    ce = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
    none_idx = CLASSES.index("none")
    os.makedirs(args.out, exist_ok=True)
    best = -1
    rng = np.random.default_rng(1)
    for ep in range(args.epochs):
        t0 = time.time()
        order = rng.permutation(len(train))
        tot, n = 0.0, 0
        for s in range(0, len(order) - args.batch + 1, args.batch):
            x, box, cls = train.batch(np.sort(order[s:s + args.batch]))
            pb, pc = model(x)
            has = (cls != none_idx).float()
            g, _ = giou(pb, box)
            l_box = ((1 - g) * has).sum() / has.sum().clamp(min=1) + (torch.nn.functional.smooth_l1_loss(pb, box, reduction="none", beta=0.05).sum(1) * has).sum() / has.sum().clamp(min=1)
            loss = l_box + ce(pc, cls)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(cls)
            n += len(cls)
        rep = evaluate(model, val)
        print(f"epoch {ep + 1}: loss {tot / n:.4f}  val iou {rep['mean_iou']:.3f}  iou>=.75 {rep['iou75']:.3f}  cls {rep['cls_acc']:.3f}  ({time.time() - t0:.0f}s)")
        sys.stdout.flush()
        score = rep["mean_iou"] + rep["cls_acc"]
        if score > best:
            best = score
            torch.save(model.state_dict(), os.path.join(args.out, "screen.pt"))
            with open(os.path.join(args.out, "val_report.json"), "w") as f:
                json.dump(rep, f, indent=2)
    model.load_state_dict(torch.load(os.path.join(args.out, "screen.pt")))
    export_onnx(model, os.path.join(args.out, "screen.onnx"))
    print("exported", os.path.join(args.out, "screen.onnx"))


if __name__ == "__main__":
    main()
