import argparse
import json
import math
import sqlite3
import numpy as np


def logit(p):
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def pull(db_path):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "select c.signals, f.label from checks c join feedback f on f.check_id = c.id where f.label in ('ai','human')"
    ).fetchall()
    con.close()
    out = []
    for sig_json, label in rows:
        try:
            sigs = json.loads(sig_json)
        except json.JSONDecodeError:
            continue
        out.append({"signals": sigs, "label": 1 if label == "ai" else 0})
    return out


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def design(rows, names):
    X = np.zeros((len(rows), len(names)), dtype=np.float64)
    y = np.zeros(len(rows), dtype=np.float64)
    for i, r in enumerate(rows):
        y[i] = r["label"]
        for s in r["signals"]:
            if s["name"] in names:
                X[i, names.index(s["name"])] = max(-4.0, min(4.0, logit(float(s["score"]))))
    return X, y


def fit(X, y, l2=1.0, iters=500, lr=0.05):
    n, d = X.shape
    w = np.zeros(d)
    b = 0.0
    for _ in range(iters):
        z = X @ w + b
        p = 1 / (1 + np.exp(-z))
        g = p - y
        w -= lr * (X.T @ g / n + l2 * w / n)
        b -= lr * g.mean()
    return w, b


def fuse_rows(rows, names, weights=None, prior=0.35):
    out = np.zeros(len(rows))
    for i, r in enumerate(rows):
        z = logit(prior)
        for s in r["signals"]:
            rel = weights.get(s["name"], s.get("reliability", 0.0)) if weights is not None else s.get("reliability", 0.0)
            z += rel * max(-4.0, min(4.0, logit(float(s["score"]))))
        out[i] = 1 / (1 + math.exp(-z))
    return out


def auc(p, y):
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def to_weights(w, names):
    pos = np.clip(w, 0, None)
    scale = 0.95 / pos.max() if pos.max() > 0 else 1.0
    return {n: round(float(v * scale), 3) for n, v in zip(names, pos) if v * scale >= 0.02}


def crossval(rows, names, l2, folds=2, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(rows))
    parts = np.array_split(idx, folds)
    y_all = np.array([r["label"] for r in rows], dtype=float)
    results = []
    for k in range(folds):
        test = parts[k]
        train = np.concatenate([parts[j] for j in range(folds) if j != k])
        X, y = design([rows[i] for i in train], names)
        w, b = fit(X, y, l2=l2)
        fitted = to_weights(w, names)
        te_rows = [rows[i] for i in test]
        yt = y_all[test]
        base = fuse_rows(te_rows, names)
        cal = fuse_rows(te_rows, names, fitted)
        results.append({
            "fold": k, "n": int(len(test)),
            "hand_tuned": {"auc": round(auc(base, yt), 4), "acc": round(float(((base >= 0.5) == (yt >= 0.5)).mean()), 4)},
            "fitted": {"auc": round(auc(cal, yt), 4), "acc": round(float(((cal >= 0.5) == (yt >= 0.5)).mean()), 4)},
        })
    return results


def main():
    ap = argparse.ArgumentParser(description="fit per-signal reliability weights from labelled checks")
    ap.add_argument("--db", help="squint sqlite db (uses checks joined with feedback)")
    ap.add_argument("--jsonl", help="or a jsonl of {signals:[{name,score}], label}")
    ap.add_argument("--out", default="weights.json")
    ap.add_argument("--min-rows", type=int, default=200)
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--cv", type=int, default=0, help="first check with this many folds that fitted weights beat the hand-tuned ones")
    ap.add_argument("--report", default="", help="where to write the cross-validation numbers")
    args = ap.parse_args()

    rows = pull(args.db) if args.db else load_jsonl(args.jsonl)
    if len(rows) < args.min_rows:
        print(f"only {len(rows)} labelled rows, want at least {args.min_rows} before touching the weights")
        return
    names = sorted({s["name"] for r in rows for s in r["signals"] if s["name"] not in ("phishing", "decode", "audio_length")})
    if args.cv:
        folds = crossval(rows, names, args.l2, args.cv)
        for f_ in folds:
            print(f"fold {f_['fold']} (n={f_['n']}): hand-tuned auc {f_['hand_tuned']['auc']:.3f} acc {f_['hand_tuned']['acc']:.3f}  |  fitted auc {f_['fitted']['auc']:.3f} acc {f_['fitted']['acc']:.3f}")
        better = all(f_["fitted"]["auc"] >= f_["hand_tuned"]["auc"] and f_["fitted"]["acc"] >= f_["hand_tuned"]["acc"] - 0.005 for f_ in folds)
        if args.report:
            with open(args.report, "w") as f:
                json.dump({"folds": folds, "fitted_weights_win": better, "n": len(rows)}, f, indent=2)
        if not better:
            print("fitted weights don't beat the hand-tuned ones on every fold, keeping the defaults")
            return
        print("fitted weights win on every fold, fitting on everything")
    X, y = design(rows, names)
    w, b = fit(X, y, l2=args.l2)
    weights = to_weights(w, names)
    p = 1 / (1 + np.exp(-(X @ w + b)))
    acc = float(((p >= 0.5) == (y >= 0.5)).mean())
    with open(args.out, "w") as f:
        json.dump(weights, f, indent=2, sort_keys=True)
    print(f"fit on {len(rows)} rows, train acc {acc:.3f}, prior logit {b:+.2f}")
    for n, v in sorted(weights.items(), key=lambda kv: -kv[1]):
        print(f"  {n:<22} {v:.3f}")
    print(f"wrote {args.out}. set SQUINT_WEIGHTS_FILE to it and restart the server")


if __name__ == "__main__":
    main()
