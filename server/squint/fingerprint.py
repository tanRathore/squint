import numpy as np
from PIL import Image
import imagehash

HASH_BITS = 64
BANDS = 4
BAND_BITS = HASH_BITS // BANDS


def image_prints(img):
    g = img.convert("RGB")
    if max(g.size) > 512:
        g = g.copy()
        g.thumbnail((512, 512))
    return {
        "phash": str(imagehash.phash(g)),
        "dhash": str(imagehash.dhash(g)),
    }


def hex_int(h):
    return int(h, 16)


def hamming(a, b):
    return bin(hex_int(a) ^ hex_int(b)).count("1")


def bands(h):
    v = hex_int(h)
    mask = (1 << BAND_BITS) - 1
    return [(v >> (i * BAND_BITS)) & mask for i in range(BANDS)]


def frame_prints(frames):
    out = []
    for f in frames:
        out.append(str(imagehash.phash(Image.fromarray(f))))
    return out


def video_signature(frames, keep=8):
    hashes = frame_prints(frames)
    if len(hashes) <= keep:
        return hashes
    idx = np.linspace(0, len(hashes) - 1, keep).round().astype(int)
    return [hashes[i] for i in idx]


def video_similarity(a, b):
    if not a or not b:
        return 0.0
    best = 0
    for x in a:
        for y in b:
            d = hamming(x, y)
            if d <= 8:
                best += 1
                break
    return best / max(len(a), len(b))


def _resample(x, sr, target=8000):
    if sr == target:
        return x
    n = int(len(x) * target / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def _peaks(mag):
    edges = [0, 10, 20, 40, 80, 160, mag.shape[1]]
    peaks = []
    for t in range(mag.shape[0]):
        row = mag[t]
        thresh = row.mean() + row.std()
        for lo, hi in zip(edges, edges[1:]):
            seg = row[lo:hi]
            if not len(seg):
                continue
            f = lo + int(seg.argmax())
            if row[f] > thresh:
                peaks.append((t, f))
    return peaks


def audio_marks(samples, sr, fan=5, frame=1024, hop=512):
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    x = _resample(x, sr)
    if len(x) < frame:
        return []
    win = np.hanning(frame)
    n = 1 + (len(x) - frame) // hop
    frames = np.lib.stride_tricks.as_strided(
        x, shape=(n, frame), strides=(x.strides[0] * hop, x.strides[0])
    )
    spec = np.abs(np.fft.rfft(frames * win, axis=1))
    mag = np.log1p(spec)
    peaks = _peaks(mag)
    marks = []
    for i, (t1, f1) in enumerate(peaks):
        for j in range(i + 1, min(i + 1 + fan, len(peaks))):
            t2, f2 = peaks[j]
            dt = t2 - t1
            if dt <= 0 or dt > 63:
                continue
            h = ((f1 & 0x1FF) << 15) | ((f2 & 0x1FF) << 6) | (dt & 0x3F)
            marks.append((h, t1))
    return marks


def audio_match(query, candidates):
    if not query:
        return None, 0.0
    lookup = {}
    for h, t in query:
        lookup.setdefault(h, []).append(t)
    votes = {}
    for item_id, h, t_db in candidates:
        for t_q in lookup.get(h, ()):
            key = (item_id, t_db - t_q)
            votes[key] = votes.get(key, 0) + 1
    if not votes:
        return None, 0.0
    (item_id, _), count = max(votes.items(), key=lambda kv: kv[1])
    return item_id, min(1.0, count / max(1, len(query) * 0.3))
