import asyncio
import io
import struct
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "research" / "screen"))

from squint.config import Settings
from squint.index import Index_
from squint.pipeline import Pipeline


def png_with_prompt(img, prompt):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    body = b"parameters\x00" + prompt.encode()
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF)
    return data[:33] + chunk + data[33:]


def real_photo(seed):
    import glob
    paths = sorted(glob.glob(str(ROOT / "research" / "data" / "real" / "*" / "*.png")))
    if not paths:
        return None
    img = Image.open(paths[seed * 97 % len(paths)]).convert("RGB")
    img.thumbnail((960, 960))
    return img


def fake_photo(seed):
    rp = real_photo(seed)
    if rp is not None:
        return rp
    rng = np.random.default_rng(seed)
    a = np.zeros((720, 960, 3), dtype=np.float32)
    yy, xx = np.mgrid[0:720, 0:960]
    a[..., 0] = 120 + 70 * np.sin(xx / 120)
    a[..., 1] = 100 + 60 * np.cos(yy / 90)
    a[..., 2] = 140 + 50 * np.sin((xx + yy) / 150)
    a += rng.normal(0, 7, a.shape)
    img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(6):
        x, y = rng.integers(0, 800), rng.integers(0, 600)
        d.ellipse([x, y, x + rng.integers(60, 200), y + rng.integers(60, 200)], fill=tuple(int(c) for c in rng.integers(0, 255, 3)))
    return img


def app_screenshot(photo, which="feed", seed=3):
    try:
        import gen
    except ImportError:
        return None
    gen.CANVAS_WIDTHS[:] = [1080]
    rng = np.random.default_rng(seed)
    orig = gen.fake_photo
    gen.fake_photo = lambda r, w, h: photo.resize((int(w), int(h)))
    img, box, cls = getattr(gen, f"t_{which}")(rng)
    gen.fake_photo = orig
    return img


def to_bytes(img, fmt="PNG", **kw):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def show(label, v):
    print(f"\n{label}")
    print(f"  {v.headline}   p={v.p}  {v.confidence} confidence  {v.ms} ms" + ("  [quick]" if v.quick else ""))
    print(f"  buzz: {v.haptic.label}")
    print(f"  says: {v.say}")
    for e in v.evidence[:4]:
        print(f"   - {e}")


async def main():
    st = Settings(db_url="sqlite:///./demo.db")
    pipe = Pipeline(st, Index_(st.db_url, st.salt))
    print("providers configured:", ", ".join(pipe.provider_names()) or "none, local signals + index only")
    print("screen model:", "loaded" if pipe.screen.ready else "not found, heuristic crop")

    photo = fake_photo(1)
    label = "1. a real photo shared from the gallery" if real_photo(1) is not None else "1. a procedurally generated image shared from the gallery (so 'synthetic' is the right answer here; run research/collect_github.py for real photos)"
    show(label, await pipe.check(to_bytes(photo, "JPEG", quality=88), "IMG_4411.jpg", "image/jpeg", "com.google.android.apps.photos", "share", "demo"))

    sd = png_with_prompt(fake_photo(2), "snow leopard on a ridge at dawn, Steps: 30, Sampler: DPM++ 2M Karras, Model: sd_xl_base_1.0")
    show("2. an image straight out of stable diffusion, shared as the original file", await pipe.check(sd, "00042.png", "image/png", "com.whatsapp", "share", "demo"))

    shot = app_screenshot(fake_photo(3), "feed")
    if shot is not None:
        data = to_bytes(shot)
        t0 = time.time()
        q = await pipe.quick(data, "Screenshot.png", "com.instagram.android", "assistant", "demo-a")
        show(f"3. long-press power on an instagram post, quick path ({int((time.time() - t0) * 1000)} ms, decisive={q.decisive})", q)
        v = await pipe.check(data, "Screenshot.png", "image/png", "com.instagram.android", "assistant", "demo-a")
        show("4. same press, full check", v)
        again = await pipe.check(data, "Screenshot.png", "image/png", "com.instagram.android", "assistant", "demo-a", prev=(v.check_id, v.phash, str(time.time())))
        show("5. pressed again on the same screen within 45s", again)
        chat = app_screenshot(fake_photo(3), "chat", seed=5)
        v = await pipe.check(to_bytes(chat), "Screenshot.png", "image/png", "com.whatsapp", "assistant", "demo-b", lang="es")
        show("6. the same photo in a whatsapp chat, a different phone set to spanish", v)

    email = ("Dear valued customer, we noticed unusual sign-in activity on your account. To avoid suspension you must verify your account within 24 hours "
             "by clicking this link: http://185.22.14.9/secure-login. Failure to act now will result in your account being locked permanently. "
             "It's important to note that this is a robust, seamless process designed to elevate your security. Sincerely, The Security Team.")
    show("7. an email, read off the screen, phone set to hindi", await pipe.text(email, "com.google.android.gm", "assistant", "demo", lang="hi"))

    later = pipe.index.get_check(v.check_id)
    print(f"\n8. an hour later the phone opens the app and asks for that check's evidence")
    print(f"  {later['headline']}  (served from the check row, no media involved)")
    for e in later["evidence"][:3]:
        print(f"   - {e}")

    await pipe.aclose()
    s = pipe.index.stats()
    corrections = sum(s["feedback"].values()) if isinstance(s["feedback"], dict) else s["feedback"]
    print(f"\nindex now holds {s['items']} fingerprints, {corrections} corrections, and zero images.")


if __name__ == "__main__":
    asyncio.run(main())
