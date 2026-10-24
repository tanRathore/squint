import numpy as np
from PIL import Image
from squint import fingerprint as fp
from conftest import noisy_photo, tone


def test_phash_survives_resize_and_recompress(tmp_path):
    img = noisy_photo(3)
    a = fp.image_prints(img)
    small = img.resize((320, 240))
    small.save(tmp_path / "s.jpg", quality=60)
    b = fp.image_prints(Image.open(tmp_path / "s.jpg"))
    assert fp.hamming(a["phash"], b["phash"]) <= 8


def test_different_images_are_far():
    a = fp.image_prints(noisy_photo(1))
    b = fp.image_prints(noisy_photo(2).rotate(90, expand=True))
    assert fp.hamming(a["phash"], b["phash"]) > 12


def test_bands_round_trip():
    h = "a3f1c90e5b7d2468"
    bs = fp.bands(h)
    assert len(bs) == 4
    v = 0
    for i, b in enumerate(bs):
        v |= b << (i * 16)
    assert v == int(h, 16)


def test_audio_marks_match_shifted_copy():
    x, sr = tone(5.0, seed=4)
    q = fp.audio_marks(x, sr)
    assert len(q) > 50
    shifted = np.concatenate([np.zeros(int(0.7 * sr), dtype=np.float32), x])
    db = fp.audio_marks(shifted, sr)
    cands = [("song", h, t) for h, t in db]
    item, score = fp.audio_match(q, cands)
    assert item == "song"
    assert score > 0.3


def test_audio_marks_reject_other_audio():
    x, sr = tone(5.0, seed=4)
    y, _ = tone(5.0, seed=9)
    q = fp.audio_marks(x, sr)
    cands = [("other", h, t) for h, t in fp.audio_marks(y, sr)]
    _, score = fp.audio_match(q, cands)
    assert score < 0.15


def test_video_signature_samples_evenly():
    frames = [np.asarray(noisy_photo(i, (224, 224))) for i in range(20)]
    sig = fp.video_signature(frames, keep=6)
    assert len(sig) == 6
    assert fp.video_similarity(sig, sig) == 1.0


def test_audio_marks_survive_lossy_reencode(tmp_path):
    import subprocess
    from squint import media
    if not media.FFMPEG:
        return
    x, sr = tone(6, seed=77)
    wav = tmp_path / "a.wav"
    wav.write_bytes(media.to_wav(x, sr))
    out = tmp_path / "a.m4a"
    subprocess.run([media.FFMPEG, "-v", "error", "-y", "-i", str(wav), "-c:a", "aac", "-b:a", "48k", str(out)], check=True)
    y, sr2 = media.decode_audio(out.read_bytes(), sr=16000)
    q = fp.audio_marks(x, sr)
    item, score = fp.audio_match(q, [("a", h, t) for h, t in fp.audio_marks(y, sr2)])
    assert item == "a" and score > 0.8
