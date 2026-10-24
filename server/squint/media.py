import io
import os
import shutil
import subprocess
import tempfile
import warnings
import numpy as np
from PIL import Image

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
TESSERACT = shutil.which("tesseract")

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8", b"GIF8", b"RIFF", b"BM", b"II*\x00", b"MM\x00*")


def sniff(data, filename="", declared=""):
    name = (filename or "").lower()
    if data[:4] in (b"\x89PNG",) or data[:2] == b"\xff\xd8" or data[:4] == b"GIF8" or data[:2] == b"BM":
        return "image"
    if data[:4] == b"RIFF":
        return "audio" if data[8:12] == b"WAVE" else "image"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"M4A ", b"M4B ", b"mp42") and name.endswith((".m4a", ".aac")):
            return "audio"
        if brand in (b"heic", b"heix", b"mif1", b"avif"):
            return "image"
        return "video"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio"
    if data[:4] == b"OggS" or data[:4] == b"fLaC":
        return "audio"
    if data[:4] == b"\x1aE\xdf\xa3":
        return "video"
    if declared.startswith("image/"):
        return "image"
    if declared.startswith("video/"):
        return "video"
    if declared.startswith("audio/"):
        return "audio"
    if name.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi")):
        return "video"
    if name.endswith((".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus")):
        return "audio"
    if name.endswith((".txt", ".eml", ".md")):
        return "text"
    try:
        s = data.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    if len(data) < 200_000 and s.strip():
        printable = sum(1 for ch in s if ch.isprintable() or ch in "\n\r\t") / len(s)
        if printable > 0.95:
            return "text"
    return "unknown"


MAX_PIXELS = 80_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS * 2
warnings.simplefilter("ignore", Image.DecompressionBombWarning)


class TooLarge(ValueError):
    pass


def open_image(data):
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        if w * h > MAX_PIXELS:
            if img.format != "JPEG":
                raise TooLarge(f"{w}x{h} is more image than we'll decode")
            img.draft("RGB", (w // 4, h // 4))
        img.load()
    except TooLarge:
        raise
    except Image.DecompressionBombError:
        raise TooLarge("that image is far too large to decode")
    except Exception:
        raise ValueError("that image couldn't be decoded")
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _ffmpeg(data, args, timeout=60):
    if not FFMPEG:
        return b""
    try:
        p = subprocess.run([FFMPEG, "-v", "error", "-i", "pipe:0", *args, "pipe:1"], input=data, capture_output=True, timeout=timeout)
        if p.stdout:
            return p.stdout
    except subprocess.TimeoutExpired:
        return b""
    with tempfile.TemporaryDirectory(prefix="sq-") as d:
        path = os.path.join(d, "in.bin")
        with open(path, "wb") as f:
            f.write(data)
        try:
            p = subprocess.run([FFMPEG, "-v", "error", "-i", path, *args, "pipe:1"], capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return b""
        return p.stdout


def video_frames(data, fps=1.0, size=224, limit=24):
    raw = _ffmpeg(data, [
        "-vf", f"fps={fps},scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size}",
        "-frames:v", str(limit), "-pix_fmt", "rgb24", "-f", "rawvideo",
    ])
    n = len(raw) // (size * size * 3)
    if n == 0:
        return []
    arr = np.frombuffer(raw[: n * size * size * 3], dtype=np.uint8).reshape(n, size, size, 3)
    return [arr[i].copy() for i in range(n)]


def video_audio(data, sr=8000, seconds=60):
    raw = _ffmpeg(data, ["-t", str(seconds), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le"])
    if len(raw) < 2:
        return None, sr
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0, sr


def decode_audio(data, sr=8000, seconds=120):
    return video_audio(data, sr=sr, seconds=seconds)


def to_wav(samples, sr):
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def ocr(img):
    if not TESSERACT:
        return ""
    g = img.convert("L")
    if g.size[0] < 900:
        g = g.resize((g.size[0] * 2, g.size[1] * 2))
    buf = io.BytesIO()
    g.save(buf, format="PNG")
    try:
        p = subprocess.run([TESSERACT, "stdin", "stdout", "--psm", "6", "-l", "eng"], input=buf.getvalue(), capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        return ""
    text = p.stdout.decode("utf-8", "replace")
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
    return "\n".join(lines)


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def jpeg_bytes(img, quality=90):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
