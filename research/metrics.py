import numpy as np


def auc(scores, labels):
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels).astype(int)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=np.float64)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def eer(scores, labels):
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels).astype(int)
    best = (1.0, 0.5)
    for t in np.unique(s):
        pred = s >= t
        far = ((pred == 1) & (y == 0)).sum() / max(1, (y == 0).sum())
        frr = ((pred == 0) & (y == 1)).sum() / max(1, (y == 1).sum())
        gap = abs(far - frr)
        if gap < best[0]:
            best = (gap, (far + frr) / 2, t)
    return float(best[1]), float(best[2]) if len(best) > 2 else 0.5


def accuracy(scores, labels, threshold=0.5):
    s = np.asarray(scores)
    y = np.asarray(labels).astype(int)
    return float(((s >= threshold).astype(int) == y).mean())


def ece(scores, labels, bins=10):
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        m = (s >= lo) & (s < hi) if hi < 1 else (s >= lo) & (s <= hi)
        if not m.any():
            continue
        conf, acc = s[m].mean(), y[m].mean()
        total += abs(conf - acc) * m.sum() / len(s)
        rows.append({"lo": float(lo), "hi": float(hi), "n": int(m.sum()), "confidence": float(conf), "accuracy": float(acc)})
    return float(total), rows


def by_group(scores, labels, groups):
    out = {}
    g = np.asarray(groups)
    for name in np.unique(g):
        m = g == name
        out[str(name)] = {"n": int(m.sum()), "auc": auc(np.asarray(scores)[m], np.asarray(labels)[m]), "acc": accuracy(np.asarray(scores)[m], np.asarray(labels)[m])}
    return out


def report(scores, labels, groups=None):
    e, bins = ece(scores, labels)
    r, t = eer(scores, labels)
    out = {"n": len(scores), "auc": auc(scores, labels), "eer": r, "eer_threshold": t, "acc@0.5": accuracy(scores, labels), "ece": e, "calibration": bins}
    if groups is not None:
        out["by_source"] = by_group(scores, labels, groups)
    return out
