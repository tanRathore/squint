import io
import re
import struct
import zlib
import numpy as np
from PIL import Image, ImageFilter

GENERATORS = [
    ("stable diffusion", r"stable[\s_-]?diffusion|sd[-_ ]?xl|automatic1111|comfyui|invokeai|novelai"),
    ("midjourney", r"midjourney"),
    ("dall-e", r"dall[\s·.-]?e|openai"),
    ("adobe firefly", r"firefly|adobe\s+generative|generative\s+fill"),
    ("google imagen", r"imagen|gemini|synthid|nano\s*banana"),
    ("flux", r"black[\s-]?forest[\s-]?labs|\bflux\b"),
    ("ideogram", r"ideogram"),
    ("leonardo", r"leonardo\.ai"),
    ("runway", r"runway(ml)?"),
    ("sora", r"\bsora\b"),
    ("kling", r"kling"),
    ("veo", r"\bveo\b"),
    ("elevenlabs", r"eleven\s?labs"),
    ("suno", r"\bsuno\b"),
]

CAMERA_MAKERS = r"apple|samsung|google|sony|canon|nikon|leica|fujifilm|olympus|panasonic|xiaomi|oneplus|huawei|motorola|nothing|ricoh|hasselblad|dji|gopro"


def _png_chunks(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        yield kind, body
        pos += 12 + length
        if kind == b"IEND":
            break


def _png_text(data):
    out = {}
    for kind, body in _png_chunks(data):
        try:
            if kind == b"tEXt":
                k, _, v = body.partition(b"\x00")
                out[k.decode("latin-1")] = v.decode("latin-1", "replace")
            elif kind == b"iTXt":
                k, _, rest = body.partition(b"\x00")
                flag = rest[0:1]
                rest = rest[2:]
                _, _, rest = rest.partition(b"\x00")
                _, _, text = rest.partition(b"\x00")
                if flag == b"\x01":
                    text = zlib.decompress(text)
                out[k.decode("latin-1")] = text.decode("utf-8", "replace")
            elif kind == b"zTXt":
                k, _, rest = body.partition(b"\x00")
                out[k.decode("latin-1")] = zlib.decompress(rest[1:]).decode("latin-1", "replace")
        except Exception:
            continue
    return out


def _jpeg_segments(data):
    if not data.startswith(b"\xff\xd8"):
        return
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if marker == 0xDA or marker == 0xD9:
            break
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        yield marker, data[pos + 4:pos + 2 + length]
        pos += 2 + length


def _jpeg_quant_quality(data):
    tables = []
    for marker, body in _jpeg_segments(data):
        if marker != 0xDB:
            continue
        i = 0
        while i < len(body):
            precision = body[i] >> 4
            n = 64 * (2 if precision else 1)
            raw = body[i + 1:i + 1 + n]
            vals = struct.unpack(">64H", raw) if precision else list(raw)
            tables.append(np.array(vals, dtype=np.float32))
            i += 1 + n
    if not tables:
        return None
    mean = float(np.mean([t.mean() for t in tables]))
    if mean <= 1.05:
        return 100
    return int(max(1, min(100, 100 - mean * 1.5)))


def metadata_scan(data):
    notes = []
    blob = b""
    software = ""
    maker = ""
    c2pa = False
    source_type = ""

    if data.startswith(b"\x89PNG"):
        text = _png_text(data)
        blob = " ".join(f"{k}={v}" for k, v in text.items()).lower().encode()
        if any(k.lower() in ("parameters", "prompt", "workflow", "sd-metadata", "invokeai_metadata") for k in text):
            notes.append("png carries a generation prompt block")
            software = software or "stable diffusion family"
        for kind, body in _png_chunks(data):
            if kind == b"caBX" or b"c2pa" in body[:64]:
                c2pa = True
    elif data.startswith(b"\xff\xd8"):
        for marker, body in _jpeg_segments(data):
            if marker == 0xE1 and body.startswith(b"Exif"):
                blob += body.lower()
                m = re.search(rb"software\x00+[\x00-\x20]*([\x20-\x7e]{3,60})", body, re.I)
                if m:
                    software = m.group(1).decode("latin-1").strip("\x00 ")
            elif marker == 0xE1 and b"http://ns.adobe.com/xap" in body[:64]:
                blob += body.lower()
                m = re.search(rb"digitalsourcetype[^>]{0,120}?(trainedalgorithmicmedia|compositewithtrainedalgorithmicmedia|digitalcapture)", body, re.I)
                if m:
                    source_type = m.group(1).decode().lower()
                m = re.search(rb"CreatorTool[\"'>=\s]*([^<\"']{3,60})", body)
                if m and not software:
                    software = m.group(1).decode("latin-1", "replace")
            elif marker == 0xEB and b"c2pa" in body[:200].lower():
                c2pa = True
                blob += body.lower()
            elif marker == 0xEB and b"jumb" in body[:64].lower():
                c2pa = True
                blob += body.lower()
            elif marker == 0xFE:
                blob += body.lower()
    elif data[4:8] == b"ftyp" or data[4:12] == b"ftypisom":
        head = data[:2_000_000].lower()
        blob = head
        if b"c2pa" in head or b"jumb" in head:
            c2pa = True
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        head = data[:200_000].lower()
        blob = head
        if b"c2pa" in head:
            c2pa = True

    if b"c2pa.created" in blob or b"c2pa.actions" in blob:
        c2pa = True
    if b"trainedalgorithmicmedia" in blob:
        source_type = source_type or "trainedalgorithmicmedia"
    if b"digitalcapture" in blob and not source_type:
        source_type = "digitalcapture"

    generator = ""
    hay = (blob.decode("latin-1", "replace") + " " + software).lower()
    for name, pat in GENERATORS:
        if re.search(pat, hay):
            generator = name
            break
    if re.search(CAMERA_MAKERS, software.lower()) or re.search(rb"make\x00+[\x00-\x20]*(" + CAMERA_MAKERS.encode() + rb")", blob, re.I):
        maker = "camera"

    if generator:
        notes.append(f"metadata names {generator}")
    if source_type == "trainedalgorithmicmedia":
        notes.append("iptc digital source type says trained algorithmic media")
    if c2pa:
        notes.append("content credentials manifest present")
    if source_type == "digitalcapture":
        notes.append("iptc digital source type says camera capture")

    return {
        "generator": generator,
        "software": software[:80],
        "camera": maker == "camera",
        "c2pa": c2pa,
        "source_type": source_type,
        "notes": notes,
    }


def _radial_profile(power):
    h, w = power.shape
    cy, cx = h // 2, w // 2
    y, x = np.indices(power.shape)
    r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(int)
    total = np.bincount(r.ravel(), power.ravel())
    count = np.bincount(r.ravel())
    prof = total / np.maximum(count, 1)
    return prof[: min(cy, cx)]


def spectral_score(img):
    g = img.convert("L")
    g.thumbnail((256, 256))
    a = np.asarray(g, dtype=np.float32)
    if a.shape[0] < 64 or a.shape[1] < 64:
        return 0.5, "image too small for spectrum"
    a = a - a.mean()
    power = np.abs(np.fft.fftshift(np.fft.fft2(a))) ** 2
    prof = _radial_profile(power)
    prof = np.log1p(prof[1:])
    if len(prof) < 32:
        return 0.5, "image too small for spectrum"
    n = len(prof)
    mid = prof[n // 4 : n // 2].mean()
    high = prof[3 * n // 4 :].mean()
    slope = (mid - high) / max(1e-6, abs(mid))
    d = np.diff(prof[n // 2 :])
    bumps = int(((d[:-1] > 0) & (d[1:] < 0) & (np.abs(d[:-1]) > 0.08)).sum())
    score = 0.5
    note = "spectrum looks ordinary"
    if slope < 0.18:
        score += 0.2
        note = "unusually flat high frequency spectrum"
    if bumps >= 4:
        score += 0.15
        note = "periodic peaks in high frequencies"
    if slope > 0.45 and bumps < 2:
        score -= 0.15
    return float(min(0.95, max(0.05, score))), note


def residual_score(img):
    g = img.convert("L")
    g.thumbnail((384, 384))
    med = g.filter(ImageFilter.MedianFilter(3))
    a = np.asarray(g, dtype=np.float32)
    r = a - np.asarray(med, dtype=np.float32)
    energy = r.std() / max(1e-6, a.std())
    flat = (np.abs(r) < 1.0).mean()
    if energy < 0.04 and flat > 0.9:
        return 0.68, "almost no sensor noise in the residual"
    if energy > 0.18:
        return 0.38, "noisy residual, consistent with a camera or heavy compression"
    return 0.5, "residual noise unremarkable"


def jpeg_score(data):
    q = _jpeg_quant_quality(data)
    if q is None:
        return None, "not a jpeg"
    if q >= 97:
        return 0.56, f"jpeg saved at quality about {q}, typical of export tools"
    if q <= 80:
        return 0.45, f"jpeg quality about {q}, re-shared or messaging compression"
    return 0.5, f"jpeg quality about {q}"


def inspect_image(data, img):
    out = []
    meta = metadata_scan(data)
    if meta["generator"] or meta["source_type"] == "trainedalgorithmicmedia":
        out.append(("metadata", 0.97, 0.95, "; ".join(meta["notes"])))
    elif meta["c2pa"] and (meta["camera"] or meta["source_type"] == "digitalcapture"):
        out.append(("provenance", 0.05, 0.9, "content credentials from a camera capture"))
    elif meta["c2pa"]:
        out.append(("provenance", 0.6, 0.5, "content credentials present but origin unclear"))
    elif meta["camera"]:
        out.append(("metadata", 0.25, 0.4, f"camera metadata: {meta['software'] or 'maker tag'}"))
    s, note = spectral_score(img)
    out.append(("spectrum", s, 0.2, note))
    s, note = residual_score(img)
    out.append(("residual", s, 0.15, note))
    s, note = jpeg_score(data)
    if s is not None:
        out.append(("jpeg", s, 0.1, note))
    return out, meta
