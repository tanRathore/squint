import numpy as np


def band_energy(x, sr):
    n = 2048
    if len(x) < n * 4:
        return None
    frames = len(x) // n
    seg = x[: frames * n].reshape(frames, n)
    spec = np.abs(np.fft.rfft(seg * np.hanning(n), axis=1)).mean(axis=0)
    freqs = np.fft.rfftfreq(n, 1 / sr)

    def e(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        return float(spec[m].mean()) if m.any() else 0.0

    return {"low": e(80, 1000), "mid": e(1000, 3000), "high": e(3000, min(sr / 2, 7000)), "top": e(7000, sr / 2) if sr > 14000 else None}


def pause_regularity(x, sr):
    hop = int(sr * 0.02)
    if len(x) < hop * 100:
        return None
    frames = len(x) // hop
    rms = np.sqrt((x[: frames * hop].reshape(frames, hop) ** 2).mean(axis=1))
    thresh = max(1e-4, np.percentile(rms, 30))
    quiet = rms < thresh
    runs = []
    cur = 0
    for q in quiet:
        if q:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    runs = [r for r in runs if r >= 5]
    if len(runs) < 6:
        return None
    r = np.array(runs, dtype=np.float32)
    return float(r.std() / max(1.0, r.mean()))


def inspect_audio(x, sr):
    out = []
    if x is None or len(x) == 0:
        return out
    duration = len(x) / sr
    if duration < 1.5:
        return [("audio_length", 0.5, 0.0, f"only {duration:.1f}s of audio")]
    bands = band_energy(x, sr)
    if bands:
        ratio = bands["high"] / max(1e-6, bands["mid"])
        if bands["top"] is not None:
            cliff = bands["top"] / max(1e-6, bands["high"])
            if cliff < 0.02 and bands["high"] > 1e-4:
                out.append(("bandwidth", 0.6, 0.15, "hard cutoff above 7 kHz, common in synthesised speech"))
            else:
                out.append(("bandwidth", 0.45, 0.1, "full bandwidth audio"))
        elif ratio < 0.03:
            out.append(("bandwidth", 0.55, 0.1, "very little energy above 3 kHz"))
        else:
            out.append(("bandwidth", 0.5, 0.05, "spectrum unremarkable"))
    reg = pause_regularity(x, sr)
    if reg is not None:
        if reg < 0.35:
            out.append(("pauses", 0.6, 0.12, "pauses are unusually regular"))
        elif reg > 0.9:
            out.append(("pauses", 0.42, 0.1, "irregular, conversational pausing"))
        else:
            out.append(("pauses", 0.5, 0.05, "pause pattern unremarkable"))
    return out
