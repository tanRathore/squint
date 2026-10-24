import re
from collections import Counter

PHISH = [
    r"verify your (account|identity|payment)",
    r"account (has been|will be) (suspended|locked|closed)",
    r"unusual (sign[- ]?in|activity)",
    r"gift ?cards?",
    r"wire transfer",
    r"act (now|immediately)",
    r"within (24|48) hours",
    r"click (the|this) link",
    r"confirm your (password|details|information)",
    r"irs|social security|tax refund",
    r"you have (won|been selected)",
    r"crypto|bitcoin wallet",
]

TELLS = [
    r"\bdelve\b", r"\btapestry\b", r"\bin today's fast[- ]paced\b", r"\bit'?s (important|worth) (to note|noting)\b",
    r"\bas an ai\b", r"\bi hope this (email|message) finds you well\b", r"\bnavigat(e|ing) the (complex|ever[- ]changing)\b",
    r"\bunlock\b.*\bpotential\b", r"\belevate\b", r"\bseamless(ly)?\b", r"\brobust\b", r"\bleverag(e|ing)\b",
]


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def stylometry(text):
    t = clean(text)
    words = re.findall(r"[A-Za-z']+", t)
    if len(words) < 60:
        return None, "too short to read style"
    lower = [w.lower() for w in words]
    ttr = len(set(lower)) / len(lower)
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if len(s.split()) > 2]
    lens = [len(s.split()) for s in sents] or [len(words)]
    mean = sum(lens) / len(lens)
    var = sum((l - mean) ** 2 for l in lens) / len(lens)
    burst = (var ** 0.5) / max(1.0, mean)
    tells = sum(1 for pat in TELLS if re.search(pat, t, re.I))
    dashes = t.count("—") / max(1, len(sents))
    typos = sum(1 for w in lower if len(w) > 3 and Counter(w).most_common(1)[0][1] > len(w) * 0.6)
    score = 0.5
    notes = []
    if burst < 0.35:
        score += 0.1
        notes.append("very even sentence lengths")
    if tells >= 2:
        score += 0.12
        notes.append("stock phrasing common in machine text")
    if dashes > 0.5:
        score += 0.05
    if ttr < 0.42 and len(words) > 200:
        score += 0.05
    if typos:
        score -= 0.05
    if burst > 0.8:
        score -= 0.1
        notes.append("uneven, human-looking rhythm")
    return float(min(0.85, max(0.15, score))), ", ".join(notes) or "style unremarkable"


def phishing_notes(text):
    t = clean(text).lower()
    hits = [p for p in PHISH if re.search(p, t)]
    if not hits:
        return []
    urls = re.findall(r"https?://[^\s)>\]]+", t)
    odd = [u for u in urls if re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|bit\.ly|tinyurl|@|xn--", u)]
    notes = [f"reads like a pressure email ({len(hits)} scam patterns)"]
    if odd:
        notes.append("links point somewhere odd")
    return notes


def text_key(text):
    import hashlib
    norm = re.sub(r"[^a-z0-9]+", " ", clean(text).lower()).strip()
    return hashlib.sha256(norm.encode()).hexdigest()[:16]
