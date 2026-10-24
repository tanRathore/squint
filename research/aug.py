import io
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PHONE_WIDTHS = [1080, 1170, 1179, 1284, 1290, 1440, 720, 828]
UI_BG = ["#ffffff", "#000000", "#121212", "#fafafa", "#0f0f0f", "#f5f5f5"]
WORDS = "just saw this and had to share wow cant believe its real look at the detail amazing or is it 👀 posted 2h ago liked by 4,201 others view all 318 comments".split()


def recompress(img, rng):
    fmt = rng.choice(["JPEG", "JPEG", "WEBP", "PNG"])
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=int(rng.integers(55, 96)), subsampling=rng.choice([0, 2]))
    elif fmt == "WEBP":
        try:
            img.convert("RGB").save(buf, "WEBP", quality=int(rng.integers(60, 95)))
        except Exception:
            img.convert("RGB").save(buf, "JPEG", quality=80)
    else:
        img.convert("RGB").save(buf, "PNG")
    buf.seek(0)
    out = Image.open(buf)
    out.load()
    return out.convert("RGB")


def fit_width(img, width, rng):
    w, h = img.size
    scale = width / w
    nh = int(round(h * scale))
    resample = rng.choice([Image.BILINEAR, Image.BICUBIC, Image.LANCZOS])
    return img.resize((width, nh), resample)


def phone_frame(img, rng, text=True):
    width = int(rng.choice(PHONE_WIDTHS))
    height = int(width * rng.choice([2.16, 2.17, 2.22, 1.78, 2.0]))
    media = fit_width(img, width, rng)
    if media.size[1] > height - 300:
        media = media.crop((0, 0, width, height - 300))
    bg = rng.choice(UI_BG)
    fg = "#111111" if bg in ("#ffffff", "#fafafa", "#f5f5f5") else "#eeeeee"
    shot = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(shot)
    status_h = int(width * rng.uniform(0.07, 0.1))
    d.text((int(width * 0.04), status_h // 3), rng.choice(["9:41", "10:08", "3:27", "21:14"]), fill=fg)
    d.rectangle([width - int(width * 0.14), status_h // 3, width - int(width * 0.04), status_h // 3 + 20], fill=fg)
    header_h = int(width * rng.uniform(0.08, 0.14))
    top = status_h + header_h
    d.ellipse([int(width * 0.04), status_h + header_h // 4, int(width * 0.04) + header_h // 2, status_h + 3 * header_h // 4], fill=rng.choice(["#888888", "#c0392b", "#2980b9"]))
    d.text((int(width * 0.04) + header_h // 2 + 16, status_h + header_h // 3), rng.choice(["someaccount", "news_daily", "wildlife.pics", "random_user_22"]), fill=fg)
    if rng.random() < 0.25:
        pad = int(width * rng.uniform(0.0, 0.12))
        shot.paste(media.resize((width - 2 * pad, int(media.size[1] * (width - 2 * pad) / width))), (pad, top))
    else:
        shot.paste(media, (0, top))
    y = top + media.size[1] + int(width * 0.03)
    if text and y < height - 200:
        for _ in range(int(rng.integers(1, 4))):
            line = " ".join(rng.choice(WORDS, size=int(rng.integers(4, 11))))
            d.text((int(width * 0.04), y), line, fill=fg)
            y += int(width * 0.04)
    nav_h = int(width * rng.uniform(0.06, 0.1))
    d.rectangle([0, height - nav_h, width, height], fill=rng.choice(["#f2f2f2", "#0a0a0a", bg]))
    for i in range(5):
        cx = int(width * (0.1 + 0.2 * i))
        d.rectangle([cx - 14, height - nav_h // 2 - 14, cx + 14, height - nav_h // 2 + 14], outline=fg)
    return shot, (0 if rng.random() < 0.75 else int(width * 0.0), top, width, top + media.size[1])


def letterbox(img, rng):
    width = int(rng.choice(PHONE_WIDTHS))
    height = int(width * 2.16)
    media = fit_width(img, width, rng)
    shot = Image.new("RGB", (width, height), "black")
    y = max(0, (height - media.size[1]) // 2)
    shot.paste(media.crop((0, 0, width, min(media.size[1], height))), (0, y))
    return shot, (0, y, width, y + min(media.size[1], height))


def screen_record(img, rng):
    small = img.resize((img.size[0] * 3 // 4, img.size[1] * 3 // 4), Image.BILINEAR)
    back = small.resize(img.size, Image.BILINEAR)
    if rng.random() < 0.5:
        back = back.filter(ImageFilter.GaussianBlur(radius=float(rng.uniform(0.3, 0.9))))
    return recompress(back, rng)


def degrade(img, rng=None, p_frame=0.6, p_letterbox=0.15, p_record=0.2):
    rng = rng or np.random.default_rng()
    img = img.convert("RGB")
    r = rng.random()
    if r < p_frame:
        shot, box = phone_frame(img, rng)
        shot = recompress(shot, rng)
        return shot.crop(box) if rng.random() < 0.8 else shot
    if r < p_frame + p_letterbox:
        shot, box = letterbox(img, rng)
        shot = recompress(shot, rng)
        return shot.crop(box)
    if r < p_frame + p_letterbox + p_record:
        return screen_record(img, rng)
    return recompress(img, rng)
