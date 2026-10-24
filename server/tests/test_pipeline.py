import numpy as np
import pytest
from squint import media
from squint.providers.base import Provider, Signal
from conftest import noisy_photo, phone_screenshot, text_screenshot, png_with_text, to_bytes, tone, has_ffmpeg, make_mp4


class FakeDetector(Provider):
    name = "hive"
    kinds = {"image", "video", "audio", "text"}

    def __init__(self, score):
        self.score = score

    def ready(self):
        return True

    async def check(self, kind, data, text="", client=None):
        return [Signal(self.name, self.score, 0.8, f"hive puts it at {self.score:.0%} synthetic")]


class Broken(Provider):
    name = "broken"
    kinds = {"image"}

    def ready(self):
        return True

    async def check(self, *a, **k):
        raise RuntimeError("provider is down")


async def test_plain_photo_without_providers_is_honest(pipeline):
    v = await pipeline.check(to_bytes(noisy_photo(1), "JPEG"), "IMG_1.jpg", "image/jpeg", "photos", "share", "d1")
    assert v.tier == "unclear" and v.confidence == "low"
    assert v.haptic.label == "three quick taps"


async def test_generator_metadata_is_decisive(pipeline):
    data = png_with_text(noisy_photo(2), "parameters", "portrait, Steps: 25, Model: sd_xl")
    v = await pipeline.check(data, "out.png", "image/png", "files", "share", "d1")
    assert v.tier == "likely_synthetic"
    assert v.haptic.label == "one long buzz"
    assert "stable diffusion" in " ".join(v.evidence)


async def test_screenshot_path_crops_and_remembers(pipeline):
    shot, truth = phone_screenshot(noisy_photo(3))
    data = to_bytes(shot)
    v1 = await pipeline.check(data, "Screenshot_1.png", "image/png", "com.instagram.android", "assistant", "d1")
    assert v1.region_kind == "photo"
    assert abs(v1.region[1] - truth[1]) < 40
    assert v1.seen_before is None
    v2 = await pipeline.check(data, "Screenshot_2.png", "image/png", "com.instagram.android", "assistant", "d2")
    assert v2.seen_before["sightings"] == 2
    assert "Seen 2 times" in v2.say


async def test_detector_signal_drives_tier(settings, index):
    from squint.pipeline import Pipeline
    p = Pipeline(settings, index, providers=[FakeDetector(0.93)])
    v = await p.check(to_bytes(noisy_photo(4), "JPEG"), "a.jpg", "image/jpeg", "x", "share", "d1")
    assert v.tier == "likely_synthetic" and v.confidence in ("medium", "high")
    p2 = Pipeline(settings, index, providers=[FakeDetector(0.04)])
    v = await p2.check(to_bytes(noisy_photo(5), "JPEG"), "b.jpg", "image/jpeg", "x", "share", "d1")
    assert v.tier in ("leaning_human", "no_ai_signals")
    assert v.haptic.label == "two short"


async def test_broken_provider_is_skipped(settings, index):
    from squint.pipeline import Pipeline
    p = Pipeline(settings, index, providers=[Broken(settings), FakeDetector(0.9)])
    v = await p.check(to_bytes(noisy_photo(6), "JPEG"), "a.jpg", "image/jpeg", "x", "share", "d1")
    assert v.tier == "likely_synthetic"


@pytest.mark.skipif(media.TESSERACT is None, reason="no tesseract")
async def test_text_screenshot_goes_down_text_path(pipeline):
    lines = ["Dear customer, we noticed unusual sign-in activity on your account.",
             "To avoid suspension please verify your account within 24 hours.",
             "Click this link to confirm your password and details now.",
             "Failure to act now will result in your account being locked."] * 3
    shot = text_screenshot(lines)
    v = await pipeline.check(to_bytes(shot), "Screenshot_3.png", "image/png", "com.google.android.gm", "assistant", "d1")
    assert v.kind == "text"
    assert v.region_kind == "text"
    assert any("scam" in e for e in v.evidence)


async def test_text_direct(pipeline):
    para = ("In today's fast-paced world, it's important to note that leveraging robust solutions can seamlessly elevate outcomes. "
            "Delve into the tapestry of possibilities and unlock your potential. ") * 6
    v = await pipeline.text(para, "gmail", "text", "d1")
    assert v.kind == "text"
    assert any("stock phrasing" in e for e in v.evidence)
    v2 = await pipeline.text(para, "gmail", "text", "d2")
    assert v2.seen_before["sightings"] == 2


@pytest.mark.skipif(not has_ffmpeg(), reason="no ffmpeg")
async def test_audio_path_fingerprints_and_matches(pipeline):
    x, sr = tone(4, seed=31)
    wav = media.to_wav(x, sr)
    v1 = await pipeline.check(wav, "clip.wav", "audio/wav", "whatsapp", "share", "d1")
    assert v1.kind == "audio"
    shifted = media.to_wav(np.concatenate([np.zeros(sr // 2, dtype=np.float32), x]), sr)
    v2 = await pipeline.check(shifted, "clip2.wav", "audio/wav", "whatsapp", "share", "d2")
    assert v2.seen_before and v2.seen_before["sightings"] == 2


@pytest.mark.skipif(not has_ffmpeg(), reason="no ffmpeg")
async def test_video_path(pipeline, tmp_path):
    frames = [np.asarray(noisy_photo(40 + i // 3, (320, 240))) for i in range(6)]
    data = make_mp4(frames, str(tmp_path / "v.mp4"))
    v1 = await pipeline.check(data, "v.mp4", "video/mp4", "tiktok", "share", "d1")
    assert v1.kind == "video"
    assert v1.seen_before is None
    v2 = await pipeline.check(data, "v.mp4", "video/mp4", "tiktok", "share", "d2")
    assert v2.seen_before and v2.seen_before["sightings"] == 2


def test_sniff():
    assert media.sniff(b"\x89PNG\r\n\x1a\n...", "x.png") == "image"
    assert media.sniff(b"\xff\xd8\xff\xe0", "x.jpg") == "image"
    assert media.sniff(b"\x00\x00\x00\x18ftypmp42", "x.mp4") == "video"
    assert media.sniff(b"RIFF....WAVE", "x.wav") == "audio"
    assert media.sniff(b"ID3\x03", "x.mp3") == "audio"
    assert media.sniff(b"hello there this is text", "note.txt") == "text"


@pytest.mark.skipif(not has_ffmpeg(), reason="no ffmpeg")
async def test_reencoded_video_still_matches(pipeline, tmp_path):
    import subprocess
    frames = [np.asarray(noisy_photo(70 + i // 3, (480, 360))) for i in range(9)]
    data = make_mp4(frames, str(tmp_path / "orig.mp4"), fps=3)
    v1 = await pipeline.check(data, "orig.mp4", "video/mp4", "tiktok", "share", "d1")
    assert v1.seen_before is None
    subprocess.run([media.FFMPEG, "-v", "error", "-y", "-i", str(tmp_path / "orig.mp4"), "-vf", "scale=320:-2", "-crf", "35", "-c:a", "aac", "-b:a", "48k", str(tmp_path / "reshared.mp4")], check=True)
    reshared = (tmp_path / "reshared.mp4").read_bytes()
    v2 = await pipeline.check(reshared, "reshared.mp4", "video/mp4", "whatsapp", "share", "d2")
    assert v2.seen_before and v2.seen_before["sightings"] == 2
