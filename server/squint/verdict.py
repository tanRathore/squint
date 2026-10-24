import json
import math
import os
from datetime import datetime, timezone
from . import lang as L

TIERS = ["verified_capture", "no_ai_signals", "leaning_human", "unclear", "leaning_synthetic", "likely_synthetic"]

HAPTICS = {
    "likely_synthetic": {"pattern": [0, 650], "amplitudes": [0, 255], "label": "one long buzz"},
    "leaning_synthetic": {"pattern": [0, 420, 110, 110], "amplitudes": [0, 255, 0, 170], "label": "long then short"},
    "unclear": {"pattern": [0, 70, 70, 70, 70, 70], "amplitudes": [0, 200, 0, 200, 0, 200], "label": "three quick taps"},
    "leaning_human": {"pattern": [0, 110, 110, 110], "amplitudes": [0, 160, 0, 160], "label": "two short"},
    "no_ai_signals": {"pattern": [0, 110, 110, 110], "amplitudes": [0, 160, 0, 160], "label": "two short"},
    "verified_capture": {"pattern": [0, 90, 80, 380], "amplitudes": [0, 140, 0, 255], "label": "short then long"},
}

HEADLINES = {
    "likely_synthetic": "Likely AI-made",
    "leaning_synthetic": "Leaning AI, not certain",
    "unclear": "Can't tell from this",
    "leaning_human": "No strong AI signals",
    "no_ai_signals": "Nothing points to AI",
    "verified_capture": "Camera-verified capture",
}


def logit(p):
    p = min(max(p, 1e-3), 1 - 1e-3)
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def load_weights(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def fuse(signals, weights=None, prior=0.35):
    weights = weights or {}
    z = logit(prior)
    rel_total = 0.0
    for s in signals:
        r = float(weights.get(s.name, s.reliability))
        z += r * max(-4.0, min(4.0, logit(s.score)))
        rel_total += r
    return sigmoid(z), rel_total


def strongest(signals, synthetic=True):
    pool = [s for s in signals if (s.score >= 0.6) == synthetic and s.reliability >= 0.3]
    if not pool:
        return None
    return max(pool, key=lambda s: s.reliability * abs(s.score - 0.5))


def tier_for(p, rel_total, signals):
    camera = any(s.name == "provenance" and s.score <= 0.1 for s in signals)
    strong_ai = any(s.score >= 0.8 and s.reliability >= 0.6 for s in signals)
    if camera and not strong_ai:
        return "verified_capture"
    if any(s.name == "metadata" and s.score >= 0.9 for s in signals):
        return "likely_synthetic"
    if rel_total < 0.45:
        return "unclear"
    if p >= 0.8:
        return "likely_synthetic"
    if p >= 0.62:
        return "leaning_synthetic"
    if p > 0.38:
        return "unclear"
    if p > 0.2 or rel_total < 0.9:
        return "leaning_human"
    return "no_ai_signals"


def confidence_for(rel_total):
    if rel_total < 0.5:
        return "low"
    if rel_total < 1.2:
        return "medium"
    return "high"


def _when(dt, lang="en"):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    days = (datetime.now(timezone.utc).replace(tzinfo=None) - dt.replace(tzinfo=None)).days
    if days <= 0:
        return L.t(lang, "today")
    if days == 1:
        return L.t(lang, "yesterday")
    if days < 7:
        return L.t(lang, "days", n=days)
    if days < 60:
        return L.t(lang, "weeks", n=days // 7)
    return L.t(lang, "long", month=f"{L.MONTHS[lang][dt.month - 1]} {dt.year}")


def history_line(item, lang="en"):
    if not item or item.get("sightings", 1) < 2:
        return ""
    return L.t(lang, "seen", n=item["sightings"], when=_when(item["first_seen"], lang))


def say_line(tier, signals, item=None, factchecks=None, kind="image", screenshot=False, lang="en", region_kind=None, device_only=False):
    top = strongest(signals, synthetic=tier in ("likely_synthetic", "leaning_synthetic"))
    fc = (factchecks or [None])[0]
    bits = [L.t(lang, tier)]
    if tier in ("likely_synthetic", "leaning_synthetic"):
        if fc and tier == "likely_synthetic":
            bits.append(L.t(lang, "fact", publisher=fc["publisher"], rating=fc["rating"].lower()))
        elif top and top.name == "metadata":
            bits.append(L.t(lang, "metadata"))
        elif top and lang == "en" and top.note:
            bits.append(top.note.rstrip(".") + ".")
        elif top:
            bits.append(L.t(lang, "detector", pct=int(round(top.score * 100))))
    elif tier == "unclear":
        if kind == "text" and not any(s.name == "style" for s in signals):
            bits.append(L.t(lang, "too_short"))
        elif screenshot and kind != "text":
            bits.append(L.t(lang, "video") if region_kind == "video" else L.t(lang, "share_original"))
    if any(s.name == "phishing" for s in signals):
        bits.append(L.t(lang, "scam"))
    hist = history_line(item, lang)
    if hist:
        bits.append(hist)
    if device_only:
        bits.append(L.t(lang, "device_only"))
    return " ".join(bits)[:240]


def evidence_lines(signals, item=None, factchecks=None):
    out = []
    for s in sorted(signals, key=lambda s: -s.reliability * abs(s.score - 0.5)):
        if s.note:
            out.append(s.note)
    hist = history_line(item, "en")
    if hist:
        out.append(hist)
    for fc in factchecks or []:
        out.append(f"{fc['publisher']}: {fc['rating']}")
    seen = set()
    uniq = []
    for e in out:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq[:8]
