import glob
import io
import math
import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CLASSES = ["photo", "video", "text", "none"]

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
FONTS = [f for f in FONT_CANDIDATES if os.path.exists(f)] or [None]

WORDS = ("the of and to in is you that it he was for on are as with his they at be this have from or one had by word but not what all were we when your can said there use an each which she do how their if will up other about out many then them these so some her would make like him into time has look two more write go see number no way could people my than first water been call who oil its now find long down day did get come made may part just wow omg lol real fake insane unreal seriously bro wait what no way crazy amazing love this honestly").split()
NAMES = ["wildlife.daily", "news_now", "sarah.k", "mike_j", "travelgram", "the.daily.photo", "random_user_22", "arjun_r", "priya.photos", "brooklyn.eats", "techcrunch", "bbcnews", "memes.central", "ucsd_life", "sunset_hunter"]
EMOJI_SUBS = ["🔥", "😮", "😂", "❤️", "👀", "💯", "😭", "🙌"]
LIGHT = {"bg": (255, 255, 255), "bg2": (250, 250, 250), "fg": (20, 20, 20), "mute": (120, 120, 120), "line": (230, 230, 230), "accent": (0, 149, 246)}
DARK = {"bg": (0, 0, 0), "bg2": (18, 18, 18), "fg": (240, 240, 240), "mute": (150, 150, 150), "line": (40, 40, 40), "accent": (0, 149, 246)}
WA_LIGHT = {"bg": (229, 221, 213), "bg2": (255, 255, 255), "fg": (20, 20, 20), "mute": (110, 110, 110), "line": (210, 200, 190), "accent": (220, 248, 198)}
WA_DARK = {"bg": (11, 20, 26), "bg2": (31, 44, 52), "fg": (230, 230, 230), "mute": (140, 150, 160), "line": (40, 55, 65), "accent": (0, 92, 75)}


def font(size, bold=False, rng=None):
    pool = [f for f in FONTS if f and (("Bold" in f or "SemiBold" in f or "Medium" in f) == bold)] or FONTS
    path = (rng or random).choice(pool)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def words(rng, n):
    out = []
    for _ in range(n):
        w = rng.choice(WORDS)
        if rng.random() < 0.05:
            w += rng.choice([".", ",", "!", "?"])
        out.append(w)
    s = " ".join(out)
    if rng.random() < 0.3:
        s += " " + rng.choice(EMOJI_SUBS)
    return s[0].upper() + s[1:]


def noise_field(rng, w, h, octaves=4, base=4):
    acc = np.zeros((h, w), dtype=np.float32)
    amp = 1.0
    for o in range(octaves):
        gw, gh = base * 2 ** o, max(1, int(base * 2 ** o * h / w))
        g = rng.random((gh + 1, gw + 1)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += amp * (np.asarray(img, dtype=np.float32) / 255.0)
        amp *= 0.5
    acc -= acc.min()
    acc /= max(1e-6, acc.max())
    return acc


def palette(rng):
    base = np.array([rng.integers(0, 256) for _ in range(3)], dtype=np.float32)
    second = (base + rng.normal(0, 80, 3)).clip(0, 255)
    third = np.array([rng.integers(0, 256) for _ in range(3)], dtype=np.float32)
    return base, second, third


POOL = []


def set_pool(paths):
    POOL.clear()
    POOL.extend(paths)


def pooled_photo(rng, w, h):
    for _ in range(3):
        path = POOL[int(rng.integers(0, len(POOL)))]
        try:
            im = Image.open(path)
            im.load()
            im = im.convert("RGB")
        except Exception:
            continue
        iw, ih = im.size
        target = w / h
        if iw / ih > target:
            nw = int(ih * target)
            x0 = int(rng.integers(0, max(1, iw - nw)))
            im = im.crop((x0, 0, x0 + nw, ih))
        else:
            nh = int(iw / target)
            y0 = int(rng.integers(0, max(1, ih - nh)))
            im = im.crop((0, y0, iw, y0 + nh))
        im = im.resize((w, h), Image.BILINEAR)
        if rng.random() < 0.2:
            d = ImageDraw.Draw(im)
            f = font(int(max(12, min(w, h) * rng.uniform(0.06, 0.12))), bold=True, rng=rng)
            t = words(rng, int(rng.integers(2, 6))).upper()
            tw = d.textlength(t, font=f)
            d.text((max(4, (w - tw) / 2), int(h * rng.choice([0.08, 0.8]))), t, font=f, fill="white", stroke_width=max(1, f.size // 12), stroke_fill="black")
        return im
    return None


def fake_photo(rng, w, h):
    w, h = max(16, int(w)), max(16, int(h))
    if POOL and rng.random() < 0.65:
        im = pooled_photo(rng, w, h)
        if im is not None:
            return im
    a, b, c = palette(rng)
    f1 = noise_field(rng, w, h, octaves=int(rng.integers(3, 6)), base=int(rng.integers(2, 6)))
    f2 = noise_field(rng, w, h, octaves=3, base=int(rng.integers(3, 9)))
    img = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        img[..., ch] = a[ch] * (1 - f1) + b[ch] * f1
        img[..., ch] = img[..., ch] * (1 - 0.35 * f2) + c[ch] * 0.35 * f2
    if rng.random() < 0.6:
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        img = img * (0.8 + 0.4 * yy) if rng.random() < 0.5 else img * (1.2 - 0.4 * yy)
    pil = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(pil, "RGBA")
    for _ in range(int(rng.integers(0, 7))):
        x0, y0 = rng.integers(-w // 4, w), rng.integers(-h // 4, h)
        rw, rh = rng.integers(w // 10, w // 2 + 1), rng.integers(h // 10, h // 2 + 1)
        col = tuple(int(v) for v in rng.integers(0, 256, 3)) + (int(rng.integers(120, 256)),)
        if rng.random() < 0.5:
            d.ellipse([x0, y0, x0 + rw, y0 + rh], fill=col)
        else:
            d.rounded_rectangle([x0, y0, x0 + rw, y0 + rh], radius=int(rng.integers(0, 40)), fill=col)
    if rng.random() < 0.35:
        pil = pil.filter(ImageFilter.GaussianBlur(radius=float(rng.uniform(0.5, 3))))
    if rng.random() < 0.25:
        f = font(int(max(14, min(w, h) * rng.uniform(0.06, 0.12))), bold=True, rng=rng)
        d = ImageDraw.Draw(pil)
        t = words(rng, int(rng.integers(2, 6))).upper()
        tw = d.textlength(t, font=f)
        x = max(4, (w - tw) / 2)
        y = int(h * rng.choice([0.08, 0.8]))
        d.text((x, y), t, font=f, fill="white", stroke_width=max(1, f.size // 12), stroke_fill="black")
    arr = np.asarray(pil, dtype=np.float32) + rng.normal(0, rng.uniform(1, 6), (h, w, 3))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def text_block(d, rng, box, theme, size=None, lines=None, bold_first=False):
    x0, y0, x1, y1 = box
    size = size or int(rng.integers(13, 20))
    f = font(size, rng=rng)
    y = y0
    n = lines or 999
    i = 0
    while y + size * 1.5 < y1 and i < n:
        cnt = int(rng.integers(4, 12))
        t = words(rng, cnt)
        while d.textlength(t, font=f) > (x1 - x0) and cnt > 2:
            cnt -= 1
            t = " ".join(t.split()[:cnt])
        if rng.random() < 0.12:
            t = t[: max(3, len(t) // 2)]
        ff = font(size, bold=True, rng=rng) if (bold_first and i == 0) else f
        d.text((x0, y), t, font=ff, fill=theme["fg"] if rng.random() < 0.85 else theme["mute"])
        y += int(size * rng.uniform(1.35, 1.7))
        i += 1
        if rng.random() < 0.15:
            y += size
    return y


def status_bar(d, rng, w, theme, h):
    f = font(int(h * 0.42), bold=True, rng=rng)
    t = f"{rng.integers(1, 13)}:{rng.integers(0, 60):02d}"
    d.text((int(w * 0.05), int(h * 0.28)), t, font=f, fill=theme["fg"])
    x = w - int(w * 0.05)
    for wd in (int(h * 0.5), int(h * 0.42), int(h * 0.42)):
        x -= wd + int(h * 0.2)
        d.rounded_rectangle([x, int(h * 0.33), x + wd, int(h * 0.66)], radius=3, fill=theme["fg"])
    if rng.random() < 0.6:
        d.ellipse([w // 2 - h // 5, h // 5, w // 2 + h // 5, h // 5 + 2 * h // 5], fill=(0, 0, 0))


def nav_bar(d, rng, w, h, theme, top):
    d.rectangle([0, top, w, h], fill=theme["bg2"])
    d.line([0, top, w, top], fill=theme["line"])
    n = int(rng.integers(3, 6))
    for i in range(n):
        cx = int(w * (i + 0.5) / n)
        cy = top + (h - top) // 2 - int(rng.integers(0, 8))
        s = int((h - top) * 0.22)
        if rng.random() < 0.5:
            d.ellipse([cx - s, cy - s, cx + s, cy + s], outline=theme["fg"], width=2)
        else:
            d.rounded_rectangle([cx - s, cy - s, cx + s, cy + s], radius=4, outline=theme["fg"], width=2)
    if rng.random() < 0.7:
        d.rounded_rectangle([w // 2 - w // 8, h - 10, w // 2 + w // 8, h - 6], radius=2, fill=theme["mute"])


def avatar(d, rng, x, y, r, theme):
    col = tuple(int(v) for v in rng.integers(40, 230, 3))
    d.ellipse([x, y, x + 2 * r, y + 2 * r], fill=col)
    if rng.random() < 0.5:
        d.ellipse([x - 3, y - 3, x + 2 * r + 3, y + 2 * r + 3], outline=(225, 48, 108), width=3)


def icon_row(d, rng, x, y, w, theme, n=4):
    s = int(w * 0.055)
    for i in range(n):
        cx = x + i * int(s * 1.9)
        if rng.random() < 0.5:
            d.ellipse([cx, y, cx + s, y + s], outline=theme["fg"], width=2)
        else:
            d.polygon([(cx, y + s), (cx + s // 2, y), (cx + s, y + s)], outline=theme["fg"])
    d.rounded_rectangle([x + w * 0.82, y, x + w * 0.82 + s, y + s], radius=3, outline=theme["fg"], width=2)


def video_overlay(d, rng, box, theme):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if rng.random() < 0.6:
        cx, cy, r = (x0 + x1) // 2, (y0 + y1) // 2, int(min(w, h) * rng.uniform(0.06, 0.12))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 140))
        d.polygon([(cx - r // 3, cy - r // 2), (cx - r // 3, cy + r // 2), (cx + r // 2, cy)], fill=(255, 255, 255, 230))
    if rng.random() < 0.7:
        py = y1 - int(h * rng.uniform(0.01, 0.06))
        d.rectangle([x0, py, x1, py + 3], fill=(255, 255, 255, 110))
        d.rectangle([x0, py, x0 + int(w * rng.random()), py + 3], fill=(255, 0, 0, 230) if rng.random() < 0.5 else (255, 255, 255, 230))
    if rng.random() < 0.6:
        f = font(int(max(11, h * 0.035)), rng=rng)
        t = f"{rng.integers(0, 10)}:{rng.integers(0, 60):02d}"
        tw = d.textlength(t, font=f)
        d.rounded_rectangle([x1 - tw - 18, y1 - 34, x1 - 6, y1 - 8], radius=4, fill=(0, 0, 0, 160))
        d.text((x1 - tw - 12, y1 - 31), t, font=f, fill="white")
    if rng.random() < 0.4:
        s = int(min(w, h) * 0.05)
        d.ellipse([x1 - s - 12, y0 + 12, x1 - 12, y0 + 12 + s], fill=(0, 0, 0, 140))


CANVAS_WIDTHS = [360, 390, 412, 430, 480, 540]


def _canvas(rng):
    w = int(rng.choice(CANVAS_WIDTHS))
    ratio = float(rng.choice([2.165, 2.17, 2.22, 2.0, 1.78, 2.1]))
    h = int(w * ratio)
    theme = rng.choice([LIGHT, LIGHT, DARK])
    img = Image.new("RGB", (w, h), theme["bg"])
    return img, w, h, theme


def t_feed(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * rng.uniform(0.028, 0.04))
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * rng.uniform(0.0, 0.03))
    if rng.random() < 0.6:
        f = font(int(w * 0.055), bold=True, rng=rng)
        d.text((int(w * 0.04), y + 8), rng.choice(["Instagram", "For you", "Home", "Following", "Feed"]), font=f, fill=theme["fg"])
        y += int(w * 0.14)
    if rng.random() < 0.45:
        for i in range(int(w / (w * 0.2))):
            avatar(d, rng, int(w * 0.03) + i * int(w * 0.2), y, int(w * 0.075), theme)
        y += int(w * 0.22)
    r = int(w * 0.045)
    avatar(d, rng, int(w * 0.035), y, r, theme)
    d.text((int(w * 0.035) + 2 * r + 12, y + r // 2), rng.choice(NAMES), font=font(int(w * 0.037), bold=True, rng=rng), fill=theme["fg"])
    y += 2 * r + int(w * 0.03)
    aspect = rng.choice([1.0, 1.25, 0.5625, 0.8, 1.0])
    pad = 0 if rng.random() < 0.7 else int(w * rng.uniform(0.02, 0.05))
    mw = w - 2 * pad
    mh = int(mw * aspect)
    mh = min(mh, int(h * 0.62))
    media = fake_photo(rng, mw, mh)
    img.paste(media, (pad, y))
    box = (pad, y, pad + mw, y + mh)
    cls = "photo"
    if rng.random() < 0.3:
        video_overlay(d, rng, box, theme)
        cls = "video"
    if rng.random() < 0.3:
        f = font(int(w * 0.03), rng=rng)
        d.rounded_rectangle([w - int(w * 0.14), y + 12, w - 12, y + 12 + int(w * 0.06)], radius=12, fill=(0, 0, 0, 150))
        d.text((w - int(w * 0.125), y + 16), f"{rng.integers(1, 9)}/{rng.integers(2, 10)}", font=f, fill="white")
    y += mh + int(w * 0.03)
    icon_row(d, rng, int(w * 0.035), y, w, theme)
    y += int(w * 0.1)
    d.text((int(w * 0.035), y), f"{rng.integers(10, 99999):,} likes", font=font(int(w * 0.035), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.06)
    text_block(d, rng, (int(w * 0.035), y, w - int(w * 0.035), int(h * 0.93)), theme, size=int(w * 0.035), lines=int(rng.integers(1, 5)))
    nav = int(h * rng.uniform(0.045, 0.06))
    nav_bar(d, rng, w, h, theme, h - nav)
    return img, box, cls


def t_reel(rng):
    img, w, h, theme = _canvas(rng)
    img.paste((0, 0, 0), (0, 0, w, h))
    d = ImageDraw.Draw(img, "RGBA")
    full = rng.random() < 0.55
    if full:
        box = (0, 0, w, h)
        img.paste(fake_photo(rng, w, h), (0, 0))
    else:
        mh = int(w * rng.choice([1.25, 1.33, 1.0, 1.5, 1.78]))
        mh = min(mh, h - 100)
        y0 = (h - mh) // 2 + int(rng.integers(-h // 12, h // 12))
        y0 = max(0, min(h - mh, y0))
        img.paste(fake_photo(rng, w, mh), (0, y0))
        box = (0, y0, w, y0 + mh)
    d = ImageDraw.Draw(img, "RGBA")
    status_bar(d, rng, w, {"fg": (255, 255, 255)}, int(h * 0.035))
    cls = "video"
    if rng.random() < 0.8:
        video_overlay(d, rng, box, theme)
    else:
        cls = "photo"
    x = w - int(w * 0.12)
    for i in range(4):
        cy = int(h * 0.55) + i * int(h * 0.09)
        s = int(w * 0.045)
        d.ellipse([x, cy, x + s, cy + s], outline="white", width=3) if rng.random() < 0.5 else d.polygon([(x, cy + s), (x + s // 2, cy), (x + s, cy + s)], fill="white")
        d.text((x - 4, cy + s + 4), f"{rng.integers(1, 999)}K", font=font(int(w * 0.03), bold=True, rng=rng), fill="white")
    r = int(w * 0.04)
    yb = int(h * rng.uniform(0.78, 0.86))
    avatar(d, rng, int(w * 0.04), yb, r, theme)
    d.text((int(w * 0.04) + 2 * r + 10, yb + r // 2), rng.choice(NAMES), font=font(int(w * 0.037), bold=True, rng=rng), fill="white")
    f = font(int(w * 0.035), rng=rng)
    yy = yb + 2 * r + 10
    for _ in range(int(rng.integers(1, 3))):
        d.text((int(w * 0.04), yy), words(rng, int(rng.integers(3, 8))), font=f, fill="white", stroke_width=1, stroke_fill=(0, 0, 0))
        yy += int(f.size * 1.5)
    if rng.random() < 0.7:
        nav_bar(d, rng, w, h, {"bg2": (0, 0, 0), "line": (30, 30, 30), "fg": (255, 255, 255), "mute": (120, 120, 120)}, h - int(h * 0.05))
        if full:
            box = (0, 0, w, h - int(h * 0.05))
    return img, box, cls


def t_story(rng):
    img, w, h, theme = _canvas(rng)
    img.paste(fake_photo(rng, w, h), (0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    n = int(rng.integers(1, 8))
    seg = (w - 24) // n
    for i in range(n):
        d.rounded_rectangle([12 + i * seg, int(h * 0.04), 12 + (i + 1) * seg - 4, int(h * 0.04) + 3], radius=2, fill=(255, 255, 255, 255 if i < n // 2 else 120))
    avatar(d, rng, 14, int(h * 0.055), int(w * 0.04), theme)
    d.text((14 + int(w * 0.08) + 10, int(h * 0.062)), rng.choice(NAMES) + f"  {rng.integers(1, 23)}h", font=font(int(w * 0.035), bold=True, rng=rng), fill="white")
    d.rounded_rectangle([int(w * 0.04), h - int(h * 0.075), w - int(w * 0.2), h - int(h * 0.03)], radius=24, outline="white", width=2)
    d.text((int(w * 0.07), h - int(h * 0.064)), "Send message", font=font(int(w * 0.035), rng=rng), fill="white")
    cls = "photo"
    if rng.random() < 0.35:
        video_overlay(d, rng, (0, int(h * 0.1), w, h - int(h * 0.1)), theme)
        cls = "video"
    return img, (0, int(h * 0.09), w, h - int(h * 0.09)), cls


def t_chat(rng):
    img, w, h, _ = _canvas(rng)
    theme = rng.choice([WA_LIGHT, WA_DARK, LIGHT, DARK])
    img.paste(theme["bg"], (0, 0, w, h))
    d = ImageDraw.Draw(img, "RGBA")
    if theme in (WA_LIGHT, WA_DARK) and rng.random() < 0.6:
        for _ in range(int(w * h / 4000)):
            x, y = rng.integers(0, w), rng.integers(0, h)
            d.ellipse([x, y, x + 3, y + 3], fill=(theme["fg"][0], theme["fg"][1], theme["fg"][2], 25))
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    hb = sb + int(h * 0.06)
    d.rectangle([0, sb, w, hb], fill=theme["bg2"])
    avatar(d, rng, int(w * 0.12), sb + int(h * 0.012), int(h * 0.018), theme)
    d.text((int(w * 0.12) + int(h * 0.05), sb + int(h * 0.018)), rng.choice(NAMES).replace(".", " ").title(), font=font(int(w * 0.04), bold=True, rng=rng), fill=theme["fg"])
    y = hb + int(h * 0.02)
    box, cls = None, "text"
    image_at = int(rng.integers(1, 5)) if rng.random() < 0.75 else -1
    i = 0
    text_top = y
    while y < h * 0.85:
        mine = rng.random() < 0.5
        bw = int(w * rng.uniform(0.45, 0.78))
        x0 = w - bw - int(w * 0.03) if mine else int(w * 0.03)
        fill = theme["accent"] if (mine and theme in (WA_LIGHT, WA_DARK)) else ((0, 132, 255) if mine else theme["bg2"])
        if i == image_at:
            mh = int(bw * rng.uniform(0.7, 1.4))
            if y + mh > h * 0.85:
                mh = int(h * 0.85 - y)
            d.rounded_rectangle([x0, y, x0 + bw, y + mh + 8], radius=14, fill=fill)
            inner = (x0 + 6, y + 6, x0 + bw - 6, y + mh - 2)
            img.paste(fake_photo(rng, inner[2] - inner[0], inner[3] - inner[1]), (inner[0], inner[1]))
            d = ImageDraw.Draw(img, "RGBA")
            box = inner
            cls = "photo"
            if rng.random() < 0.3:
                video_overlay(d, rng, inner, theme)
                cls = "video"
            y += mh + 8 + int(h * 0.012)
        else:
            lines = int(rng.integers(1, 5))
            size = int(w * 0.037)
            bh = int(lines * size * 1.5 + size * 1.2)
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=14, fill=fill)
            text_block(d, rng, (x0 + 12, y + 8, x0 + bw - 12, y + bh), {"fg": (255, 255, 255) if (mine and theme not in (WA_LIGHT,)) else theme["fg"], "mute": theme["mute"]}, size=size, lines=lines)
            y += bh + int(h * 0.012)
        i += 1
    if box is None:
        box = (int(w * 0.03), text_top, w - int(w * 0.03), int(h * 0.85))
    d.rounded_rectangle([int(w * 0.03), h - int(h * 0.075), w - int(w * 0.15), h - int(h * 0.03)], radius=24, fill=theme["bg2"])
    d.text((int(w * 0.07), h - int(h * 0.064)), "Message", font=font(int(w * 0.037), rng=rng), fill=theme["mute"])
    return img, box, cls


def t_email(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.02)
    d.text((int(w * 0.04), y), "←", font=font(int(w * 0.06), rng=rng), fill=theme["fg"])
    y += int(h * 0.06)
    f = font(int(w * 0.055), bold=False, rng=rng)
    d.text((int(w * 0.05), y), words(rng, int(rng.integers(3, 7))), font=f, fill=theme["fg"])
    y += int(w * 0.09)
    avatar(d, rng, int(w * 0.05), y, int(w * 0.045), theme)
    d.text((int(w * 0.05) + int(w * 0.12), y), rng.choice(["Chase Alerts", "Amazon", "IT Support", "Google", "Mom", "Netflix Billing", "UCSD Registrar", "Coinbase"]), font=font(int(w * 0.038), bold=True, rng=rng), fill=theme["fg"])
    d.text((int(w * 0.05) + int(w * 0.12), y + int(w * 0.05)), "to me", font=font(int(w * 0.032), rng=rng), fill=theme["mute"])
    y += int(w * 0.14)
    with_image = rng.random() < 0.3
    if with_image:
        mh = int(w * rng.uniform(0.4, 0.7))
        img.paste(fake_photo(rng, w - int(w * 0.1), mh), (int(w * 0.05), y))
        d = ImageDraw.Draw(img, "RGBA")
        box = (int(w * 0.05), y, w - int(w * 0.05), y + mh)
        y += mh + int(h * 0.02)
        text_block(d, rng, (int(w * 0.05), y, w - int(w * 0.05), int(h * 0.92)), theme, size=int(w * 0.037))
        return img, box, "photo"
    top = y
    y = text_block(d, rng, (int(w * 0.05), y, w - int(w * 0.05), int(h * 0.9)), theme, size=int(w * rng.uniform(0.034, 0.042)))
    if rng.random() < 0.5:
        d.rounded_rectangle([int(w * 0.05), y + 10, int(w * 0.6), y + 10 + int(w * 0.11)], radius=8, fill=(26, 115, 232))
        d.text((int(w * 0.09), y + 10 + int(w * 0.03)), rng.choice(["Verify account", "View invoice", "Sign in", "Confirm now"]), font=font(int(w * 0.036), bold=True, rng=rng), fill="white")
        y += int(w * 0.13)
    return img, (int(w * 0.05), top, w - int(w * 0.05), min(int(h * 0.9), y)), "text"


def t_youtube(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb
    mh = int(w * 0.5625)
    img.paste(fake_photo(rng, w, mh), (0, y))
    d = ImageDraw.Draw(img, "RGBA")
    box = (0, y, w, y + mh)
    video_overlay(d, rng, box, theme)
    y += mh + int(h * 0.015)
    d.text((int(w * 0.04), y), words(rng, int(rng.integers(5, 10))), font=font(int(w * 0.042), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.07)
    d.text((int(w * 0.04), y), f"{rng.integers(1, 900)}K views · {rng.integers(1, 12)} days ago", font=font(int(w * 0.032), rng=rng), fill=theme["mute"])
    y += int(w * 0.08)
    avatar(d, rng, int(w * 0.04), y, int(w * 0.04), theme)
    d.text((int(w * 0.04) + int(w * 0.11), y + 6), rng.choice(NAMES), font=font(int(w * 0.036), bold=True, rng=rng), fill=theme["fg"])
    d.rounded_rectangle([w - int(w * 0.3), y, w - int(w * 0.04), y + int(w * 0.08)], radius=20, fill=theme["fg"])
    y += int(w * 0.13)
    for i in range(int(rng.integers(1, 4))):
        d.rounded_rectangle([int(w * 0.04), y, w - int(w * 0.04), y + int(w * 0.3)], radius=12, fill=theme["bg2"], outline=theme["line"])
        text_block(d, rng, (int(w * 0.07), y + 12, w - int(w * 0.07), y + int(w * 0.28)), theme, size=int(w * 0.034), lines=int(rng.integers(1, 4)))
        y += int(w * 0.33)
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, box, "video"


def t_gallery(rng):
    img, w, h, theme = _canvas(rng)
    img.paste(theme["bg"], (0, 0, w, h))
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    aspect = rng.choice([1.333, 1.5, 1.777, 0.75, 1.0])
    mh = min(int(w * aspect), int(h * 0.8))
    y0 = sb + (h - sb - int(h * 0.08) - mh) // 2
    img.paste(fake_photo(rng, w, mh), (0, y0))
    d = ImageDraw.Draw(img, "RGBA")
    d.text((int(w * 0.04), sb + 10), "←", font=font(int(w * 0.06), rng=rng), fill=theme["fg"])
    d.text((int(w * 0.35), sb + 14), f"{rng.integers(1, 28)} Oct 2026, {rng.integers(1, 12)}:{rng.integers(0, 60):02d}", font=font(int(w * 0.035), rng=rng), fill=theme["fg"])
    icon_row(d, rng, int(w * 0.08), h - int(h * 0.06), w - int(w * 0.16), theme, n=4)
    cls = "photo"
    if rng.random() < 0.25:
        video_overlay(d, rng, (0, y0, w, y0 + mh), theme)
        cls = "video"
    return img, (0, y0, w, y0 + mh), cls


def t_article(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + 4
    d.rounded_rectangle([int(w * 0.04), y, w - int(w * 0.04), y + int(w * 0.09)], radius=18, fill=theme["bg2"], outline=theme["line"])
    d.text((int(w * 0.09), y + int(w * 0.025)), rng.choice(["bbc.com", "nytimes.com", "reddit.com/r/pics", "x.com/home", "medium.com"]), font=font(int(w * 0.034), rng=rng), fill=theme["mute"])
    y += int(w * 0.13)
    d.text((int(w * 0.05), y), words(rng, int(rng.integers(5, 10))), font=font(int(w * 0.055), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.16)
    hero = rng.random() < 0.6
    box, cls = None, "text"
    if hero:
        mh = int(w * rng.uniform(0.5, 0.75))
        img.paste(fake_photo(rng, w - int(w * 0.1), mh), (int(w * 0.05), y))
        d = ImageDraw.Draw(img, "RGBA")
        box, cls = (int(w * 0.05), y, w - int(w * 0.05), y + mh), "photo"
        y += mh + 8
        d.text((int(w * 0.05), y), words(rng, 6), font=font(int(w * 0.03), rng=rng), fill=theme["mute"])
        y += int(w * 0.07)
    top = y
    y = text_block(d, rng, (int(w * 0.05), y, w - int(w * 0.05), int(h * 0.93)), theme, size=int(w * rng.uniform(0.036, 0.044)))
    if not hero:
        box = (int(w * 0.05), top, w - int(w * 0.05), min(y, int(h * 0.93)))
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, box, cls


def t_none(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.02)
    d.text((int(w * 0.05), y), rng.choice(["Settings", "Notifications", "Inbox", "Wi-Fi", "Playlists", "Order history"]), font=font(int(w * 0.07), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.14)
    while y < h * 0.9:
        rh = int(w * rng.uniform(0.12, 0.2))
        if rng.random() < 0.5:
            avatar(d, rng, int(w * 0.05), y + 8, int(rh * 0.3), theme)
        else:
            d.rounded_rectangle([int(w * 0.05), y + 8, int(w * 0.05) + int(rh * 0.6), y + 8 + int(rh * 0.6)], radius=8, fill=theme["line"])
        d.text((int(w * 0.05) + int(rh * 0.75), y + 10), words(rng, int(rng.integers(1, 4))), font=font(int(w * 0.04), bold=True, rng=rng), fill=theme["fg"])
        d.text((int(w * 0.05) + int(rh * 0.75), y + 12 + int(w * 0.05)), words(rng, int(rng.integers(2, 6))), font=font(int(w * 0.032), rng=rng), fill=theme["mute"])
        if rng.random() < 0.3:
            d.rounded_rectangle([w - int(w * 0.17), y + rh // 2 - 12, w - int(w * 0.05), y + rh // 2 + 12], radius=12, fill=theme["accent"] if rng.random() < 0.5 else theme["line"])
        d.line([int(w * 0.05), y + rh, w, y + rh], fill=theme["line"])
        y += rh
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, (0, 0, 0, 0), "none"


def t_x(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.01)
    avatar(d, rng, int(w * 0.04), y, int(w * 0.045), theme)
    d.text((int(w * 0.04) + int(w * 0.11), y + 2), rng.choice(NAMES).replace(".", " ").title(), font=font(int(w * 0.038), bold=True, rng=rng), fill=theme["fg"])
    d.text((int(w * 0.04) + int(w * 0.11), y + int(w * 0.055)), "@" + rng.choice(NAMES) + " · " + f"{rng.integers(1, 23)}h", font=font(int(w * 0.033), rng=rng), fill=theme["mute"])
    y += int(w * 0.12)
    y = text_block(d, rng, (int(w * 0.04), y, w - int(w * 0.04), y + int(w * 0.28)), theme, size=int(w * 0.04), lines=int(rng.integers(1, 4)))
    y += int(w * 0.02)
    mh = int((w - int(w * 0.08)) * rng.choice([0.5625, 0.75, 1.0, 1.25]))
    mh = min(mh, int(h * 0.55))
    pad = int(w * 0.04)
    media = fake_photo(rng, w - 2 * pad, mh)
    mask = Image.new("L", media.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, media.size[0], media.size[1]], radius=int(w * 0.04), fill=255)
    img.paste(media, (pad, y), mask)
    d = ImageDraw.Draw(img, "RGBA")
    box = (pad, y, pad + media.size[0], y + mh)
    cls = "photo"
    if rng.random() < 0.3:
        video_overlay(d, rng, box, theme)
        cls = "video"
    y += mh + int(w * 0.03)
    for i, label in enumerate(["12", f"{rng.integers(1, 999)}", f"{rng.integers(1, 99)}K", ""]):
        x = int(w * 0.06) + i * int(w * 0.24)
        d.ellipse([x, y, x + int(w * 0.05), y + int(w * 0.05)], outline=theme["mute"], width=2)
        d.text((x + int(w * 0.065), y + 2), label, font=font(int(w * 0.032), rng=rng), fill=theme["mute"])
    y += int(w * 0.1)
    d.line([0, y, w, y], fill=theme["line"])
    y += int(w * 0.03)
    if y < h * 0.8:
        avatar(d, rng, int(w * 0.04), y, int(w * 0.045), theme)
        text_block(d, rng, (int(w * 0.04) + int(w * 0.11), y, w - int(w * 0.04), int(h * 0.92)), theme, size=int(w * 0.037), lines=int(rng.integers(1, 4)))
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, box, cls


def t_reddit(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.012)
    d.text((int(w * 0.04), y), "←", font=font(int(w * 0.06), rng=rng), fill=theme["fg"])
    d.text((int(w * 0.14), y + 6), "r/" + rng.choice(["pics", "mildlyinteresting", "nature", "interestingasfuck", "aww", "Damnthatsinteresting"]), font=font(int(w * 0.042), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.12)
    avatar(d, rng, int(w * 0.04), y, int(w * 0.03), theme)
    d.text((int(w * 0.04) + int(w * 0.08), y + 2), "u/" + rng.choice(NAMES) + " · " + f"{rng.integers(1, 23)}h", font=font(int(w * 0.032), rng=rng), fill=theme["mute"])
    y += int(w * 0.08)
    d.text((int(w * 0.04), y), words(rng, int(rng.integers(5, 12))), font=font(int(w * 0.045), bold=True, rng=rng), fill=theme["fg"])
    y += int(w * 0.14)
    mh = int(w * rng.choice([0.75, 1.0, 1.33, 1.5]))
    mh = min(mh, int(h * 0.55))
    media = fake_photo(rng, w, mh)
    if rng.random() < 0.5:
        img.paste(media, (0, y))
        box = (0, y, w, y + mh)
    else:
        pad = int(w * 0.04)
        media = media.resize((w - 2 * pad, mh))
        mask = Image.new("L", media.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, media.size[0], mh], radius=int(w * 0.03), fill=255)
        img.paste(media, (pad, y), mask)
        box = (pad, y, w - pad, y + mh)
    d = ImageDraw.Draw(img, "RGBA")
    cls = "photo"
    if rng.random() < 0.25:
        video_overlay(d, rng, box, theme)
        cls = "video"
    y += mh + int(w * 0.03)
    for i, label in enumerate([f"{rng.integers(1, 99)}K", f"{rng.integers(1, 999)}", "Share"]):
        x = int(w * 0.04) + i * int(w * 0.3)
        d.rounded_rectangle([x, y, x + int(w * 0.26), y + int(w * 0.09)], radius=20, fill=theme["bg2"], outline=theme["line"])
        d.text((x + int(w * 0.07), y + int(w * 0.025)), label, font=font(int(w * 0.032), rng=rng), fill=theme["fg"])
    y += int(w * 0.14)
    text_block(d, rng, (int(w * 0.04), y, w - int(w * 0.04), int(h * 0.93)), theme, size=int(w * 0.036), lines=int(rng.integers(1, 5)))
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, box, cls


def t_telegram(rng):
    img, w, h, _ = _canvas(rng)
    theme = rng.choice([LIGHT, DARK])
    bgc = (210, 220, 230) if theme is LIGHT else (14, 22, 33)
    img.paste(bgc, (0, 0, w, h))
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    hb = sb + int(h * 0.06)
    d.rectangle([0, sb, w, hb], fill=(82, 136, 193) if theme is LIGHT else (23, 33, 43))
    d.text((int(w * 0.14), sb + int(h * 0.015)), rng.choice(["Family", "Uni group", "News Channel", "Crypto Signals", rng.choice(NAMES).title()]), font=font(int(w * 0.042), bold=True, rng=rng), fill="white")
    d.text((int(w * 0.14), sb + int(h * 0.038)), f"{rng.integers(2, 900)} members", font=font(int(w * 0.03), rng=rng), fill=(220, 230, 240))
    y = hb + int(h * 0.02)
    box, cls = None, "text"
    image_at = int(rng.integers(0, 4))
    i = 0
    text_top = y
    while y < h * 0.86:
        mine = rng.random() < 0.4
        bw = int(w * rng.uniform(0.5, 0.8))
        x0 = w - bw - int(w * 0.03) if mine else int(w * 0.03)
        fill = (239, 253, 222) if (mine and theme is LIGHT) else ((255, 255, 255) if theme is LIGHT else ((43, 82, 120) if mine else (24, 37, 51)))
        if i == image_at:
            mh = int(bw * rng.uniform(0.6, 1.3))
            if y + mh > h * 0.86:
                mh = int(h * 0.86 - y)
            inner = (x0, y, x0 + bw, y + mh)
            media = fake_photo(rng, bw, mh)
            mask = Image.new("L", media.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw, mh], radius=14, fill=255)
            img.paste(media, (x0, y), mask)
            d = ImageDraw.Draw(img, "RGBA")
            box = inner
            cls = "photo"
            if rng.random() < 0.3:
                video_overlay(d, rng, inner, theme)
                cls = "video"
            d.rounded_rectangle([x0 + bw - 70, y + mh - 26, x0 + bw - 8, y + mh - 6], radius=8, fill=(0, 0, 0, 120))
            y += mh + int(h * 0.012)
        else:
            lines = int(rng.integers(1, 5))
            size = int(w * 0.037)
            bh = int(lines * size * 1.5 + size * 1.6)
            d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=14, fill=fill)
            if not mine and rng.random() < 0.7:
                d.text((x0 + 12, y + 6), rng.choice(NAMES).title(), font=font(int(w * 0.033), bold=True, rng=rng), fill=(41, 128, 185))
            text_block(d, rng, (x0 + 12, y + int(size * 1.3), x0 + bw - 12, y + bh), {"fg": theme["fg"] if theme is LIGHT else (235, 235, 235), "mute": theme["mute"]}, size=size, lines=lines)
            y += bh + int(h * 0.012)
        i += 1
    if box is None:
        box = (int(w * 0.03), text_top, w - int(w * 0.03), int(h * 0.86))
    d.rectangle([0, h - int(h * 0.075), w, h], fill=theme["bg2"])
    d.text((int(w * 0.16), h - int(h * 0.058)), "Message", font=font(int(w * 0.037), rng=rng), fill=theme["mute"])
    return img, box, cls


def t_news(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.01)
    d.text((int(w * 0.35), y + 4), rng.choice(["BBC NEWS", "The Times", "NDTV", "El País", "Folha"]), font=font(int(w * 0.045), bold=True, rng=rng), fill=(187, 25, 25) if rng.random() < 0.5 else theme["fg"])
    y += int(w * 0.13)
    hero_first = rng.random() < 0.6
    mh = int(w * rng.choice([0.5625, 0.66, 0.75]))
    box, cls = None, "text"
    if hero_first:
        img.paste(fake_photo(rng, w, mh), (0, y))
        d = ImageDraw.Draw(img, "RGBA")
        box, cls = (0, y, w, y + mh), "photo"
        if rng.random() < 0.2:
            video_overlay(d, rng, box, theme)
            cls = "video"
        y += mh + int(w * 0.02)
        d.text((int(w * 0.05), y), words(rng, 5), font=font(int(w * 0.028), rng=rng), fill=theme["mute"])
        y += int(w * 0.06)
    d.text((int(w * 0.05), y), rng.choice(["LIVE", "WORLD", "TECH", "SCIENCE"]), font=font(int(w * 0.03), bold=True, rng=rng), fill=(187, 25, 25))
    y += int(w * 0.06)
    f = font(int(w * 0.058), bold=True, rng=rng)
    for _ in range(int(rng.integers(1, 3))):
        d.text((int(w * 0.05), y), words(rng, int(rng.integers(4, 8))), font=f, fill=theme["fg"])
        y += int(f.size * 1.3)
    y += int(w * 0.03)
    d.text((int(w * 0.05), y), "By " + rng.choice(NAMES).replace(".", " ").title() + " · " + f"{rng.integers(1, 12)} hours ago", font=font(int(w * 0.03), rng=rng), fill=theme["mute"])
    y += int(w * 0.08)
    if not hero_first:
        img.paste(fake_photo(rng, w - int(w * 0.1), mh), (int(w * 0.05), y))
        d = ImageDraw.Draw(img, "RGBA")
        box, cls = (int(w * 0.05), y, w - int(w * 0.05), y + mh), "photo"
        y += mh + int(w * 0.04)
    top = y
    y = text_block(d, rng, (int(w * 0.05), y, w - int(w * 0.05), int(h * 0.94)), theme, size=int(w * rng.uniform(0.038, 0.046)))
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, box, cls


def t_tiktok_comments(rng):
    img, box, cls = t_reel(rng)
    w, h = img.size
    d = ImageDraw.Draw(img, "RGBA")
    theme = rng.choice([LIGHT, DARK])
    top = int(h * rng.uniform(0.42, 0.55))
    d.rounded_rectangle([0, top, w, h + 40], radius=28, fill=theme["bg"])
    d.text((int(w * 0.4), top + 16), f"{rng.integers(1, 9999)} comments", font=font(int(w * 0.036), bold=True, rng=rng), fill=theme["fg"])
    y = top + int(w * 0.14)
    while y < h - int(h * 0.09):
        avatar(d, rng, int(w * 0.04), y, int(w * 0.04), theme)
        d.text((int(w * 0.04) + int(w * 0.1), y), rng.choice(NAMES), font=font(int(w * 0.032), bold=True, rng=rng), fill=theme["mute"])
        text_block(d, rng, (int(w * 0.04) + int(w * 0.1), y + int(w * 0.045), w - int(w * 0.15), y + int(w * 0.2)), theme, size=int(w * 0.036), lines=int(rng.integers(1, 3)))
        y += int(w * rng.uniform(0.16, 0.24))
    d.rounded_rectangle([int(w * 0.04), h - int(h * 0.07), w - int(w * 0.04), h - int(h * 0.025)], radius=22, fill=theme["bg2"], outline=theme["line"])
    d.text((int(w * 0.08), h - int(h * 0.06)), "Add comment...", font=font(int(w * 0.036), rng=rng), fill=theme["mute"])
    x0, y0, x1, y1 = box
    return img, (x0, y0, x1, min(y1, top)), cls


def t_grid(rng):
    img, w, h, theme = _canvas(rng)
    d = ImageDraw.Draw(img, "RGBA")
    sb = int(h * 0.035)
    status_bar(d, rng, w, theme, sb)
    y = sb + int(h * 0.01)
    d.rounded_rectangle([int(w * 0.04), y, w - int(w * 0.04), y + int(w * 0.1)], radius=20, fill=theme["bg2"], outline=theme["line"])
    d.text((int(w * 0.1), y + int(w * 0.03)), rng.choice(["Search", "Explore", "For you"]), font=font(int(w * 0.036), rng=rng), fill=theme["mute"])
    y += int(w * 0.14)
    cols = int(rng.choice([2, 3]))
    gap = int(w * 0.012)
    tw = (w - gap * (cols + 1)) // cols
    big_idx = int(rng.integers(0, cols * 3))
    best = None
    yy = [y] * cols
    i = 0
    while min(yy) < h - int(h * 0.1):
        c = int(np.argmin(yy))
        th = int(tw * rng.uniform(0.8, 1.6))
        if i == big_idx and cols == 2:
            th = int(tw * 1.9)
        x0 = gap + c * (tw + gap)
        tile = fake_photo(rng, tw, th)
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, tw, th], radius=int(w * 0.03), fill=255)
        img.paste(tile, (x0, yy[c]), mask)
        area = tw * min(th, h - int(h * 0.05) - yy[c])
        if best is None or area > best[0]:
            best = (area, (x0, yy[c], x0 + tw, min(yy[c] + th, h - int(h * 0.05))))
        yy[c] += th + gap
        i += 1
    d = ImageDraw.Draw(img, "RGBA")
    nav_bar(d, rng, w, h, theme, h - int(h * 0.05))
    return img, best[1], "none"


def t_landscape(rng):
    w = int(rng.choice([800, 960, 1024]))
    h = int(w * rng.choice([0.5625, 0.625, 0.75]))
    theme = rng.choice([LIGHT, DARK, DARK])
    img = Image.new("RGB", (w, h), theme["bg"])
    d = ImageDraw.Draw(img, "RGBA")
    if rng.random() < 0.6:
        img.paste((0, 0, 0), (0, 0, w, h))
        mw = int(w * rng.uniform(0.7, 1.0))
        mh = min(h, int(mw * 0.5625))
        x0, y0 = (w - mw) // 2, (h - mh) // 2
        img.paste(fake_photo(rng, mw, mh), (x0, y0))
        d = ImageDraw.Draw(img, "RGBA")
        box = (x0, y0, x0 + mw, y0 + mh)
        video_overlay(d, rng, box, theme)
        return img, box, "video"
    sb = int(h * 0.05)
    status_bar(d, rng, w, theme, sb)
    side = int(w * 0.22)
    d.rectangle([0, sb, side, h], fill=theme["bg2"])
    for i in range(6):
        d.text((16, sb + 20 + i * int(h * 0.1)), words(rng, 2), font=font(int(h * 0.035), rng=rng), fill=theme["fg"])
    mw = int((w - side) * rng.uniform(0.55, 0.9))
    mh = min(int(h * 0.6), int(mw * 0.75))
    x0 = side + ((w - side) - mw) // 2
    y0 = sb + int(h * 0.08)
    img.paste(fake_photo(rng, mw, mh), (x0, y0))
    d = ImageDraw.Draw(img, "RGBA")
    text_block(d, rng, (side + 20, y0 + mh + 10, w - 20, h - 10), theme, size=int(h * 0.03), lines=3)
    return img, (x0, y0, x0 + mw, y0 + mh), "photo"


TEMPLATES = [t_feed, t_feed, t_reel, t_reel, t_story, t_chat, t_chat, t_email, t_email, t_youtube, t_gallery, t_article, t_none, t_x, t_x, t_reddit, t_telegram, t_news, t_tiktok_comments, t_grid, t_landscape]
HELD_OUT = {"reddit", "telegram", "news"}


def finish(img, rng):
    if rng.random() < 0.6:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=int(rng.integers(55, 96)))
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
    if rng.random() < 0.15:
        img = img.filter(ImageFilter.GaussianBlur(radius=float(rng.uniform(0.3, 0.8))))
    return img


def sample(rng=None, exclude=()):
    rng = rng or np.random.default_rng()
    pool = [t for t in TEMPLATES if t.__name__[2:] not in exclude] if exclude else TEMPLATES
    tpl = pool[int(rng.integers(0, len(pool)))]
    img, box, cls = tpl(rng)
    w, h = img.size
    img = finish(img, rng)
    x0, y0, x1, y1 = box
    norm = (x0 / w, y0 / h, x1 / w, y1 / h)
    return img, norm, CLASSES.index(cls), tpl.__name__[2:]


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/screen_samples"
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(0)
    for i in range(24):
        img, box, cls, name = sample(rng)
        d = ImageDraw.Draw(img)
        w, h = img.size
        if CLASSES[cls] != "none":
            d.rectangle([box[0] * w, box[1] * h, box[2] * w, box[3] * h], outline=(255, 0, 255), width=4)
        img.save(f"{out}/{i:02d}_{name}_{CLASSES[cls]}.jpg", quality=80)
    print(f"wrote 24 samples to {out}")
