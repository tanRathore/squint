import argparse
import glob
import json
import os
import random
import re
import sys
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from metrics import auc, ece, accuracy
import ocr_noise

DOMAINS = ["essay", "reuter", "wp"]
AI_DIRS = ["gpt", "claude", "gpt_prompt1", "gpt_prompt2", "gpt_semantic", "gpt_writing"]


def read(path, limit=6000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            t = f.read(limit)
    except OSError:
        return ""
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t.split()) >= 25 else ""


def load(root, per_domain_cap, seed=0):
    rng = random.Random(seed)
    docs = []
    for dom in DOMAINS:
        human = [p for p in glob.glob(os.path.join(root, dom, "human", "**", "*.txt"), recursive=True) if "prompts" not in p]
        ai = []
        for d in AI_DIRS:
            ai.extend(p for p in glob.glob(os.path.join(root, dom, d, "**", "*.txt"), recursive=True) if "prompts" not in p)
        rng.shuffle(human)
        rng.shuffle(ai)
        n = min(per_domain_cap, len(human), len(ai))
        for p in human[:n]:
            t = read(p)
            if t:
                docs.append((t, 0, dom))
        for p in ai[:n]:
            t = read(p)
            if t:
                docs.append((t, 1, dom))
    rng.shuffle(docs)
    return docs


def load_esl(root, cap=1500, seed=0):
    rng = random.Random(seed)
    out = []
    for sub in ("lang8", "ets"):
        paths = glob.glob(os.path.join(root, "other", sub, "**", "*.txt"), recursive=True)
        rng.shuffle(paths)
        for p in paths[:cap]:
            t = read(p)
            if t:
                out.append((t, sub))
    return out


def build():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline, make_union
    feats = make_union(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=80000, sublinear_tf=True, min_df=3, dtype=np.float32),
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=40000, sublinear_tf=True, min_df=3, dtype=np.float32, token_pattern=r"(?u)\b\w+\b|[^\w\s]"),
    )
    return make_pipeline(feats, LogisticRegression(C=3.0, max_iter=3000))


def score(model, docs):
    return model.predict_proba([d[0] for d in docs])[:, 1]


def truncate(docs, words):
    return [(" ".join(t.split()[:words]), y, d) for t, y, d in docs]


def with_noise(docs, rate, seed=7):
    rng = random.Random(seed)
    return [(ocr_noise.noisy(t, rng, rate), y, d) for t, y, d in docs]


def augmented(docs, seed=11):
    rng = random.Random(seed)
    extra = [(ocr_noise.noisy(t, rng, rng.uniform(0.01, 0.08)), y, d) for t, y, d in docs]
    return docs + extra


def report_on(name, model, te, y, rep, real_ocr):
    block = {}
    p = score(model, te)
    e, _ = ece(p, y)
    block["clean"] = {"auc": round(auc(p, y), 4), "acc": round(accuracy(p, y), 4), "ece": round(e, 4)}
    print(f"[{name}] clean: auc {auc(p, y):.3f} acc {accuracy(p, y):.3f} ece {e:.3f}")
    for rate in (0.03, 0.06, 0.10):
        pn = score(model, with_noise(te, rate))
        block[f"ocr_noise_{int(rate * 100):02d}"] = {"auc": round(auc(pn, y), 4), "acc": round(accuracy(pn, y), 4)}
        print(f"[{name}] simulated ocr noise {rate:.0%}: auc {auc(pn, y):.3f} acc {accuracy(pn, y):.3f}")
    if real_ocr:
        texts, ys = real_ocr
        pr = model.predict_proba(texts)[:, 1]
        block["tesseract"] = {"n": len(texts), "auc": round(auc(pr, ys), 4), "acc": round(accuracy(pr, ys), 4)}
        print(f"[{name}] rendered + tesseract ({len(texts)} docs): auc {auc(pr, ys):.3f} acc {accuracy(pr, ys):.3f}")
    for words in (40, 80, 150):
        pt = score(model, truncate(te, words))
        block[f"first_{words}_words"] = {"auc": round(auc(pt, y), 4), "acc": round(accuracy(pt, y), 4)}
        print(f"[{name}] first {words} words: auc {auc(pt, y):.3f} acc {accuracy(pt, y):.3f}")
    rep[name] = block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/tmp/sq/gb")
    ap.add_argument("--cap", type=int, default=1500)
    ap.add_argument("--out", default="runs/text")
    ap.add_argument("--augment", action="store_true", help="also train on OCR-noised copies and compare")
    ap.add_argument("--real-ocr", type=int, default=0, help="render this many test docs and read them back with tesseract")
    ap.add_argument("--skip-lodo", action="store_true")
    args = ap.parse_args()
    import joblib

    docs = load(args.data, args.cap)
    print(f"{len(docs)} docs, {sum(1 for d in docs if d[1])} ai, domains {sorted({d[2] for d in docs})}")
    rep = {"n": len(docs), "leave_one_domain_out": {}}

    for held in ([] if args.skip_lodo else DOMAINS):
        tr = [d for d in docs if d[2] != held]
        te = [d for d in docs if d[2] == held]
        m = build()
        m.fit([d[0] for d in tr], [d[1] for d in tr])
        p = score(m, te)
        y = [d[1] for d in te]
        rep["leave_one_domain_out"][held] = {"n": len(te), "auc": round(auc(p, y), 4), "acc": round(accuracy(p, y), 4)}
        print(f"held out {held}: auc {auc(p, y):.3f} acc {accuracy(p, y):.3f}")

    rng = random.Random(1)
    idx = list(range(len(docs)))
    rng.shuffle(idx)
    cut = int(len(idx) * 0.85)
    tr = [docs[i] for i in idx[:cut]]
    te = [docs[i] for i in idx[cut:]]
    y = [d[1] for d in te]
    real_ocr = None
    os.makedirs(args.out, exist_ok=True)
    cache = os.path.join(args.out, f"tesseract_{args.real_ocr}.json")
    if args.real_ocr and os.path.exists(cache):
        with open(cache) as f:
            texts, ys = json.load(f)
        real_ocr = (texts, ys)
        print(f"reusing {len(texts)} tesseract read-backs from {cache}")
    elif args.real_ocr and ocr_noise.TESSERACT:
        rng_o = random.Random(3)
        picks = rng_o.sample(te, min(args.real_ocr, len(te)))
        t0 = time.time()
        read_back = [(ocr_noise.through_tesseract(" ".join(t.split()[:220]), rng_o), yy) for t, yy, _ in picks]
        read_back = [(t, yy) for t, yy in read_back if len(t.split()) >= 25]
        real_ocr = ([t for t, _ in read_back], [yy for _, yy in read_back])
        with open(cache, "w") as f:
            json.dump(real_ocr, f)
        print(f"rendered {len(read_back)} docs and read them back with tesseract in {time.time() - t0:.0f}s")
    t0 = time.time()
    model = build()
    model.fit([d[0] for d in tr], [d[1] for d in tr])
    print(f"final fit on {len(tr)} docs in {time.time() - t0:.0f}s")
    rep["in_domain"] = {"n": len(te)}
    report_on("clean_trained", model, te, y, rep, real_ocr)
    esl = load_esl(args.data)
    chosen = model
    if args.augment:
        t0 = time.time()
        aug = build()
        tra = augmented(tr)
        aug.fit([d[0] for d in tra], [d[1] for d in tra])
        print(f"augmented fit on {len(tra)} docs in {time.time() - t0:.0f}s")
        report_on("noise_trained", aug, te, y, rep, real_ocr)
        a, b = rep["clean_trained"], rep["noise_trained"]
        noisy_keys = ["ocr_noise_06", "ocr_noise_10"] + (["tesseract"] if real_ocr else [])
        gain = min(b[k]["acc"] - a[k]["acc"] for k in noisy_keys)
        if b["clean"]["acc"] >= a["clean"]["acc"] - 0.003 and b["clean"]["auc"] >= a["clean"]["auc"] - 0.003 and gain > 0.005:
            chosen = aug
            rep["shipped"] = "noise_trained"
        else:
            rep["shipped"] = "clean_trained"
        print(f"shipping the {rep['shipped']} model (smallest accuracy gain under noise {gain:+.3f})")
    if esl:
        pe = chosen.predict_proba([t for t, _ in esl])[:, 1]
        for sub in ("lang8", "ets"):
            m = np.array([s == sub for _, s in esl])
            if m.any():
                fpr = float((pe[m] >= 0.5).mean())
                rep[f"esl_false_positive_{sub}"] = round(fpr, 4)
                print(f"non-native human writing ({sub}) flagged as AI at 0.5: {fpr:.1%}")
    joblib.dump(chosen, os.path.join(args.out, "text.joblib"), compress=3)
    with open(os.path.join(args.out, "report.json"), "w") as f:
        json.dump(rep, f, indent=2)
    print("saved", os.path.join(args.out, "text.joblib"), f"{os.path.getsize(os.path.join(args.out, 'text.joblib')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
