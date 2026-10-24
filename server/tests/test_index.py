from squint import fingerprint as fp
from conftest import noisy_photo, tone


def test_record_and_near_lookup(index):
    prints = fp.image_prints(noisy_photo(11))
    item, counted = index.record("image", prints=prints, p=0.7, tier="leaning_synthetic", source_app="ig")
    assert counted and item["sightings"] == 1
    hit = index.near(prints["phash"])
    assert hit and hit[0]["id"] == item["id"] and hit[1] == 0
    again, counted2 = index.record("image", prints=prints, p=0.9, tier="likely_synthetic", source_app="x", match=hit[0])
    assert counted2 and again["sightings"] == 2
    assert 0.7 < again["p_mean"] < 0.9
    assert set(__import__("json").loads(again["apps"])) == {"ig", "x"}


def test_near_lookup_tolerates_small_changes(index):
    img = noisy_photo(12)
    prints = fp.image_prints(img)
    index.record("image", prints=prints)
    other = fp.image_prints(img.resize((300, 225)))
    hit = index.near(other["phash"])
    assert hit is not None


def test_unrelated_image_misses(index):
    index.record("image", prints=fp.image_prints(noisy_photo(13)))
    far = fp.image_prints(noisy_photo(14).rotate(90, expand=True))
    assert index.near(far["phash"]) is None


def test_audio_marks_round_trip(index):
    x, sr = tone(4, seed=21)
    marks = fp.audio_marks(x, sr)
    item, _ = index.record("audio", audio=marks, p=0.5)
    cands = index.audio_candidates(marks)
    found, score = fp.audio_match(marks, cands)
    assert found == item["id"] and score > 0.5


def test_check_log_feedback_and_stats(index):
    item, _ = index.record("image", prints=fp.image_prints(noisy_photo(15)))
    cid = index.log_check(item["id"], "device-abc", "ig", "assistant", "image", "unclear", 0.5, [], 120)
    assert index.add_feedback(cid, "ai")
    assert not index.add_feedback("nope", "ai")
    s = index.stats()
    assert s["checks"] == 1 and s["feedback"] == {"ai": 1}
    assert index.get(item["id"])["feedback_ai"] == 1


def test_device_id_is_hashed(index):
    h = index.device_hash("my-phone")
    assert h != "my-phone" and len(h) == 40
    assert index.device_hash("") is None


def test_purge_keeps_recent(index):
    item, _ = index.record("image", prints=fp.image_prints(noisy_photo(16)))
    index.log_check(item["id"], "d", "a", "t", "image", "unclear", 0.5, [], 1)
    assert index.purge(30) == 0
