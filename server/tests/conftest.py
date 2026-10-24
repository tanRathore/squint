import io
import struct
import subprocess
import zlib
import numpy as np
import pytest
from PIL import Image, ImageDraw

from squint.config import Settings
from squint.index import Index_
from squint.pipeline import Pipeline
from squint import media


def png_with_text(img, key, value):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()
    body = key.encode() + b"\x00" + value.encode()
    chunk = struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body) & 0xFFFFFFFF)
    return data[:33] + chunk + data[33:]


def jpeg_with_app(img_or_bytes, marker, payload, quality=85):
    if isinstance(img_or_bytes, (bytes, bytearray)):
        data = bytes(img_or_bytes)
    else:
        buf = io.BytesIO()
        img_or_bytes.convert("RGB").save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
    seg = bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload
    return data[:2] + seg + data[2:]


def noisy_photo(seed=0, size=(640, 480)):
    rng = np.random.default_rng(seed)
    base = np.zeros((size[1], size[0], 3), dtype=np.float32)
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    base[..., 0] = 90 + 60 * np.sin(xx / 70.0)
    base[..., 1] = 110 + 50 * np.cos(yy / 55.0)
    base[..., 2] = 100 + 40 * np.sin((xx + yy) / 90.0)
    base += rng.normal(0, 6, base.shape)
    img = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(5):
        x0, y0 = rng.integers(0, size[0] - 80), rng.integers(0, size[1] - 80)
        w, h = rng.integers(60, size[0] // 2), rng.integers(60, size[1] // 2)
        col = tuple(int(c) for c in rng.integers(0, 255, 3))
        if rng.random() < 0.5:
            d.ellipse([x0, y0, x0 + w, y0 + h], fill=col)
        else:
            d.rectangle([x0, y0, x0 + w, y0 + h], fill=col)
    return img


def phone_screenshot(photo, top=200, size=(1080, 2340)):
    shot = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(shot)
    d.text((40, 30), "9:41", fill="black")
    d.rectangle([900, 35, 1040, 60], fill="black")
    d.text((40, 130), "someaccount  follow", fill="black")
    w = size[0]
    shot.paste(photo.resize((w, w)), (0, top))
    d.text((40, top + w + 40), "a caption that runs on for a while here", fill="black")
    d.rectangle([0, size[1] - 100, size[0], size[1]], fill="#f2f2f2")
    return shot, (0, top, w, top + w)


def text_screenshot(lines, size=(1080, 2340)):
    shot = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(shot)
    y = 240
    for l in lines:
        d.text((60, y), l, fill="black")
        y += 44
    return shot


def to_bytes(img, fmt="PNG", **kw):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


def tone(seconds=4.0, sr=16000, seed=0):
    t = np.arange(int(seconds * sr)) / sr
    rng = np.random.default_rng(seed)
    x = np.zeros_like(t)
    for f in rng.uniform(150, 3200, 7):
        x += rng.uniform(0.2, 0.8) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.3, 1.5) * t))
    x += rng.normal(0, 0.01, len(t))
    return (x / np.abs(x).max() * 0.8).astype(np.float32), sr


def has_ffmpeg():
    return media.FFMPEG is not None


def make_mp4(frames, path, fps=2):
    h, w = frames[0].shape[:2]
    cmd = [media.FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-c:a", "aac", path]
    subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), check=True, capture_output=True)
    with open(path, "rb") as f:
        return f.read()


@pytest.fixture
def settings(tmp_path):
    return Settings(db_url=f"sqlite:///{tmp_path}/t.db", salt="test", provider_timeout=2)


@pytest.fixture
def index(settings):
    return Index_(settings.db_url, settings.salt)


@pytest.fixture
def pipeline(settings, index):
    return Pipeline(settings, index, providers=[])
