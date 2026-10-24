import io
import os
import random
import re
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

CONFUSIONS = {
    "l": ["1", "I", "|"], "1": ["l", "I"], "I": ["l", "1"], "O": ["0"], "0": ["O"], "o": ["0", "c"], "e": ["c"], "c": ["e"],
    "a": ["o"], "u": ["v"], "v": ["u"], "n": ["r"], "h": ["b"], "S": ["5"], "5": ["S"], "B": ["8"], "g": ["q"], "q": ["g"],
    "t": ["f"], "f": ["t"], "i": ["j", ";"], ",": [".", "'"], ".": [","], "'": ["`", "’", ""], '"': ["''", "“"], "-": ["—", "~"],
}
PAIRS = {"rn": "m", "m": "rn", "cl": "d", "vv": "w", "w": "vv", "ri": "n", "fi": "ﬁ", "fl": "ﬂ"}
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/noto", "/usr/share/fonts/truetype/freefont"]
TESSERACT = shutil.which("tesseract")


def noisy(text, rng, rate=0.04):
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        pair = text[i:i + 2]
        r = rng.random()
        if pair in PAIRS and r < rate * 0.6:
            out.append(PAIRS[pair])
            i += 2
            continue
        if r < rate * 0.5 and ch in CONFUSIONS:
            out.append(rng.choice(CONFUSIONS[ch]))
        elif r < rate * 0.65 and ch.isalpha():
            pass
        elif r < rate * 0.75 and ch == " ":
            pass
        elif r < rate * 0.85 and ch.isalpha() and i > 0 and text[i - 1].isalpha():
            out.append(" " + ch)
        elif r < rate * 0.9 and ch == " ":
            out.append("- ")
        else:
            out.append(ch)
        i += 1
    s = "".join(out)
    if rng.random() < rate * 8:
        s = re.sub(r"[\"“”]", "", s)
    return s


_fonts = []


def fonts():
    if _fonts:
        return _fonts
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            name = f.lower()
            if not name.endswith(".ttf") or any(w in name for w in ("bold", "italic", "oblique", "emoji", "symbol")):
                continue
            try:
                ImageFont.truetype(os.path.join(d, f), 32)
            except OSError:
                continue
            _fonts.append(os.path.join(d, f))
    return _fonts


def render(text, rng, width=1080):
    size = int(rng.choice([22, 26, 30, 34, 38, 42, 48]))
    path = rng.choice(fonts())
    font = ImageFont.truetype(path, size)
    margin = int(rng.uniform(30, 70))
    dark = rng.random() < 0.35
    fg, bg = ((230, 230, 230), (18, 18, 18)) if dark else ((20, 20, 20), rng.choice([(255, 255, 255), (250, 247, 240), (242, 242, 247)]))
    words = text.split()
    lines, cur = [], ""
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    for w in words:
        trial = (cur + " " + w).strip()
        if probe.textlength(trial, font=font) > width - 2 * margin and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lh = int(size * rng.uniform(1.25, 1.55))
    img = Image.new("RGB", (width, margin * 2 + lh * len(lines)), bg)
    d = ImageDraw.Draw(img)
    small = ImageFont.truetype(path, max(14, int(size * 0.7)))
    for i, ln in enumerate(lines):
        d.text((margin, margin + i * lh), ln, font=font, fill=fg)
        if rng.random() < 0.12:
            d.text((width - margin - 90, margin + i * lh + 4), rng.choice(["10:42", "Yesterday", "✓✓", "2h", "· Edited"]), font=small, fill=(140, 140, 140))
    if rng.random() < 0.7:
        scale = rng.uniform(0.4, 0.85)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.BILINEAR)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(rng.uniform(40, 90)))
    return buf.getvalue()


def ocr(jpeg):
    if not TESSERACT:
        return ""
    try:
        p = subprocess.run([TESSERACT, "stdin", "stdout", "--psm", "6", "-l", "eng"], input=jpeg, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return ""
    return re.sub(r"\s+", " ", p.stdout.decode("utf-8", "replace")).strip()


def through_tesseract(text, rng):
    return ocr(render(text, rng))


if __name__ == "__main__":
    rng = random.Random(0)
    sample = "The committee's report, published late on Tuesday, found that the project had run 40% over budget and that officials failed to flag the overrun."
    print(noisy(sample, rng, 0.05))
    print(noisy(sample, rng, 0.10))
    if TESSERACT:
        print(through_tesseract(sample, rng))
