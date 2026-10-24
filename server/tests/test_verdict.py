from squint import verdict as vd
from squint.providers.base import Signal


def S(name, score, rel, note="n"):
    return Signal(name, score, rel, note)


def test_fusion_moves_with_evidence():
    p0, _ = vd.fuse([])
    p1, _ = vd.fuse([S("hive", 0.9, 0.8)])
    p2, _ = vd.fuse([S("hive", 0.1, 0.8)])
    assert p2 < p0 < p1


def test_weak_signals_barely_move_it():
    p0, _ = vd.fuse([])
    p1, rel = vd.fuse([S("spectrum", 0.7, 0.2), S("residual", 0.68, 0.15)])
    assert abs(p1 - p0) < 0.15
    assert vd.tier_for(p1, rel, []) == "unclear"


def test_metadata_overrides_to_synthetic():
    sigs = [S("metadata", 0.97, 0.95), S("hive", 0.3, 0.8)]
    p, rel = vd.fuse(sigs)
    assert vd.tier_for(p, rel, sigs) == "likely_synthetic"


def test_camera_provenance_wins_unless_strong_detector_disagrees():
    sigs = [S("provenance", 0.05, 0.9), S("spectrum", 0.6, 0.2)]
    p, rel = vd.fuse(sigs)
    assert vd.tier_for(p, rel, sigs) == "verified_capture"
    sigs.append(S("hive", 0.95, 0.8))
    p, rel = vd.fuse(sigs)
    assert vd.tier_for(p, rel, sigs) != "verified_capture"


def test_tiers_cover_the_range():
    assert vd.tier_for(0.9, 1.5, []) == "likely_synthetic"
    assert vd.tier_for(0.7, 1.5, []) == "leaning_synthetic"
    assert vd.tier_for(0.5, 1.5, []) == "unclear"
    assert vd.tier_for(0.3, 1.5, []) == "leaning_human"
    assert vd.tier_for(0.1, 1.5, []) == "no_ai_signals"
    assert vd.tier_for(0.1, 0.6, []) == "leaning_human"


def test_every_tier_has_a_buzz_and_a_headline():
    for t in vd.TIERS:
        assert t in vd.HAPTICS and t in vd.HEADLINES
        h = vd.HAPTICS[t]
        assert len(h["pattern"]) == len(h["amplitudes"])


def test_say_line_never_calls_anything_real():
    for t in vd.TIERS:
        line = vd.say_line(t, [S("hive", 0.9, 0.8, "hive puts it at 90% synthetic")])
        assert " real" not in line.lower()
        assert len(line) < 220


def test_say_line_mentions_history_and_factcheck():
    item = {"sightings": 40, "first_seen": "2026-10-01T00:00:00"}
    line = vd.say_line("likely_synthetic", [S("hive", 0.9, 0.8, "hive puts it at 90% synthetic")], item, [{"publisher": "Reuters", "rating": "False"}])
    assert "Reuters" in line and "40 times" in line


def test_weights_file_overrides_reliability(tmp_path):
    f = tmp_path / "w.json"
    f.write_text('{"spectrum": 0.9}')
    w = vd.load_weights(str(f))
    p_weighted, _ = vd.fuse([S("spectrum", 0.8, 0.2)], w)
    p_plain, _ = vd.fuse([S("spectrum", 0.8, 0.2)])
    assert p_weighted > p_plain
